#!/usr/bin/env python3
"""Repair the MuslimSim BB35 PFD/PFP separate-path handoff in place.

The repair is marker-based and intentionally leaves all established key maps,
font conversion, X-Plane datarefs, and renderers untouched.  It replaces only
runtime lifecycle methods after their classes have been defined.

Fixed issues:
* v46 graphical worker receives its required display-page getter;
* old eight-argument workers remain supported;
* persistent native F0 and character F2 planes are cleared/hidden at handoff;
* full font/page/frame bursts share the MuslimSim WinCtrl output arbiter;
* a dead display thread is restarted instead of leaving BB35 black forever.
"""

from __future__ import annotations

import argparse
import codecs
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Optional

REPAIR_START = "# >>> MUSLIMSIM BB35 CLEAN HANDOFF REPAIR >>>"
REPAIR_END = "# <<< MUSLIMSIM BB35 CLEAN HANDOFF REPAIR <<<"


@dataclass(frozen=True)
class TextFormat:
    newline: str
    had_utf8_bom: bool


@dataclass(frozen=True)
class PatchResult:
    module: Path
    changed: bool
    backup: Optional[Path]


def repair_block() -> str:
    return r'''# >>> MUSLIMSIM BB35 CLEAN HANDOFF REPAIR >>>
# Version 1.1: clean persistent F0/F2 planes, v46 worker compatibility, and
# serialized multi-report display bursts.  This block is installed by
# tools/patch_bb35_pfd_pfp_handoff.py and is safe to replace in place.
import contextlib as _bb35_contextlib
import inspect as _bb35_inspect
import struct as _bb35_struct

try:
    from .winctrl_output_bus import (
        output_transaction as _bb35_output_transaction,
        wrap_hid_device as _bb35_wrap_hid_device,
    )
except Exception:
    @_bb35_contextlib.contextmanager
    def _bb35_output_transaction(_label, *, settle_after=0.0):
        yield
        if settle_after > 0.0:
            time.sleep(float(settle_after))

    def _bb35_wrap_hid_device(device, *, label, product_id=None):
        return device


_BB35_HANDOFF_REPAIR_VERSION = "1.1"
HANDOFF_SETTLE = max(float(HANDOFF_SETTLE), 0.35)


def _bb35_repair_hide_f2_grid_packet():
    """Move the persistent F2 character grid completely off the LCD."""
    packet = bytearray(PACKET_SIZE)
    packet[:4] = bytes((0xF0, 0x00, 0x00, 0x2A))

    p = 4
    packet[p:p + 25] = bytes((
        BB35_IDENTIFIER, BB35_FAMILY, 0x00, 0x00,
        0x18, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00,
        0x08, 0x00, 0x00, 0x00,
        0xFF, 0x07,  # x = 2047
        0xFF, 0x07,  # y = 2047
        0x01, 0x00,
        0x01, 0x00,
    ))

    c = 29
    packet[c:c + 17] = bytes((
        BB35_IDENTIFIER, BB35_FAMILY, 0x00, 0x00,
        0x05, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x01, 0x00, 0x00, 0x00, 0x00,
    ))
    return bytes(packet)


class _BB35RepairCanvas:
    """Minimal native F0 canvas used only to clear the hidden graphics plane."""
    _PAYLOAD_BYTES = 56

    def __init__(self, device):
        self.device = device
        self.sequence = 1
        self.transaction = int(time.monotonic() * 1000) & 0xFFFFFFFF
        self._stream = bytearray()
        self._foreground = None
        self._background = None

    def command(self, function_id, data=b""):
        data = bytes(data)
        body = bytearray()
        body.extend(_bb35_struct.pack(
            "<I",
            int(BB35_IDENTIFIER) | (int(BB35_FAMILY) << 8),
        ))
        body.extend(_bb35_struct.pack("<I", int(function_id)))
        body.extend(_bb35_struct.pack("<I", self.transaction))
        body.append(0)
        body.extend(_bb35_struct.pack("<I", len(data)))
        body.extend(data)
        self._stream.extend(body)
        self.transaction = (self.transaction + 1) & 0xFFFFFFFF
        if int(function_id) == 0x103:
            self.flush()

    def flush(self):
        if not self._stream:
            return
        for offset in range(0, len(self._stream), self._PAYLOAD_BYTES):
            payload = self._stream[offset:offset + self._PAYLOAD_BYTES]
            report = bytearray(PACKET_SIZE)
            report[0] = 0xF0
            report[1] = 0x00
            report[2] = self.sequence & 0xFF
            report[3] = len(payload)
            report[4:4 + len(payload)] = payload
            self.device.write(list(report))
            self.sequence = (self.sequence + 1) & 0xFF
        self._stream.clear()

    @staticmethod
    def _rgb(red, green, blue):
        return tuple(max(0, min(255, int(value))) for value in (red, green, blue))

    def colours(self, foreground, background=None):
        foreground = self._rgb(*foreground)
        background = foreground if background is None else self._rgb(*background)
        if self._foreground != foreground:
            self.command(0x112, bytes((0xFF, *foreground)))
            self._foreground = foreground
        if self._background != background:
            self.command(0x113, bytes((0xFF, *background)))
            self._background = background

    def colour(self, red, green, blue):
        colour = self._rgb(red, green, blue)
        self.colours(colour, colour)

    def fill(self, x, y, width, height):
        self.command(
            0x110,
            _bb35_struct.pack(
                "<HHHH",
                max(0, int(x)),
                max(0, int(y)),
                max(1, int(width)),
                max(1, int(height)),
            ),
        )


def _bb35_repair_clear_f0(canvas, passes=2):
    for _ in range(max(1, int(passes))):
        canvas.colour(6, 7, 13)
        canvas.fill(0, 0, 640, 480)
        canvas.command(0x103)


def _bb35_repair_deep_canvas(canvas):
    current = canvas
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        nested = getattr(current, "_canvas", None)
        if nested is None:
            break
        current = nested
    return current


def _bb35_repair_rebind_canvas_device(canvas, old_device, new_device):
    current = canvas
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        for attribute in ("device", "_device"):
            try:
                if getattr(current, attribute, None) is old_device:
                    setattr(current, attribute, new_device)
            except Exception:
                pass
        current = getattr(current, "_canvas", None)


def _bb35_repair_lock_canvas_flush(canvas):
    target = _bb35_repair_deep_canvas(canvas)
    if target is None or getattr(target, "_muslimsim_output_bus_flush", False):
        return
    original_flush = target.flush

    def locked_flush():
        with _bb35_output_transaction("BB35-PFD-frame"):
            return original_flush()

    target.flush = locked_flush
    target._muslimsim_output_bus_flush = True


def _bb35_repair_worker_args(path):
    args = [
        path.device,
        path.canvas,
        path.api_version,
        path.pfd_ids,
        path.refresh_interval,
        path.stop_evt,
        path.status,
        path.status_lock,
    ]

    try:
        signature = _bb35_inspect.signature(path.pfd_worker)
        parameters = list(signature.parameters.values())
        positional = [
            parameter
            for parameter in parameters
            if parameter.kind in (
                _bb35_inspect.Parameter.POSITIONAL_ONLY,
                _bb35_inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        accepts_varargs = any(
            parameter.kind == _bb35_inspect.Parameter.VAR_POSITIONAL
            for parameter in parameters
        )
        needs_page_getter = (
            "display_page_getter" in signature.parameters
            or accepts_varargs
            or len(positional) >= 9
        )
    except Exception:
        needs_page_getter = False

    if needs_page_getter:
        path._repair_page_getter = lambda: "pfd"
        args.append(path._repair_page_getter)

    return tuple(args)


def _bb35_repair_pfd_start(self):
    self.stop_evt.clear()
    raw_device = None
    try:
        # open_pfd uploads the font and draws its boot page.  Hold the shared
        # output transaction even before the raw handle can be wrapped.
        with _bb35_output_transaction(
            "BB35-PFD-enter",
            settle_after=0.04,
        ):
            raw_device, self.canvas = self.open_pfd()
            self.device = _bb35_wrap_hid_device(
                raw_device,
                label="BB35-PFD",
                product_id=BB35_PID,
            )
            _bb35_repair_rebind_canvas_device(
                self.canvas,
                raw_device,
                self.device,
            )
            _bb35_repair_lock_canvas_flush(self.canvas)

            # Both display planes persist across close/open.  Hide F2, then
            # repaint every F0 pixel while the LCD is dark.
            _set_brightness(self.device, 1, 0)
            self.device.write(list(_bb35_repair_hide_f2_grid_packet()))
            _bb35_repair_clear_f0(self.canvas, 2)
            _set_brightness(self.device, 0, 128)
            _set_brightness(self.device, 1, 220)

        self.worker = threading.Thread(
            target=self.pfd_worker,
            args=_bb35_repair_worker_args(self),
            name="BB35-PFD-PATH",
            daemon=True,
        )
        self.keys = threading.Thread(
            target=self._key_reader,
            name="BB35-PFD-SECRET",
            daemon=True,
        )
        self.worker.start()
        self.keys.start()
        time.sleep(0.06)

        if not self.worker.is_alive():
            error = self.status.get("error") if isinstance(self.status, dict) else None
            raise RuntimeError(
                "graphical PFD worker stopped during startup"
                + (f": {error}" if error else "")
            )

        print(
            "BB35 PATH -> PFD (clean F0; F2 hidden; "
            "v46 page-selector compatible; PERIOD x3 for PFP/FMC)"
        )
    except Exception:
        self.stop_evt.set()
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
        elif raw_device is not None:
            try:
                raw_device.close()
            except Exception:
                pass
        self.device = None
        self.canvas = None
        self.worker = None
        self.keys = None
        raise


def _bb35_repair_pfd_stop(self):
    self.stop_evt.set()
    if self.keys is not None:
        self.keys.join(timeout=1.5)
    if self.worker is not None:
        self.worker.join(timeout=10.0)
        if self.worker.is_alive():
            print(
                "BB35 PFD worker did not stop cleanly; closing its HID handle "
                "to unblock the handoff."
            )

    if self.device is not None:
        try:
            with _bb35_output_transaction(
                "BB35-PFD-leave",
                settle_after=0.08,
            ):
                _set_brightness(self.device, 1, 0)
                if self.canvas is not None:
                    _bb35_repair_clear_f0(self.canvas, 2)
                self.device.write(list(_bb35_repair_hide_f2_grid_packet()))
        except Exception as exc:
            if self.diagnose:
                print(f"BB35 PFD cleanup warning: {exc}")
        try:
            self.device.close()
        except Exception:
            pass

    self.device = None
    self.canvas = None
    self.worker = None
    self.keys = None


def _bb35_repair_fmc_start(self):
    if websocket is None:
        raise RuntimeError("websocket-client unavailable")
    if not self.font_path.is_file():
        raise RuntimeError(f"BB35 FMC font missing: {self.font_path}")

    packets = _load_font_packets(self.font_path)
    self.stop_evt.clear()
    raw_device = None
    try:
        with _bb35_output_transaction(
            "BB35-FMC-enter",
            settle_after=0.06,
        ):
            raw_device = _open_bb35()
            self.device = _bb35_wrap_hid_device(
                raw_device,
                label="BB35-FMC",
                product_id=BB35_PID,
            )
            self._repair_f0_canvas = _BB35RepairCanvas(self.device)

            _set_brightness(self.device, 1, 0)
            self.device.write(list(_bb35_repair_hide_f2_grid_packet()))
            _bb35_repair_clear_f0(self._repair_f0_canvas, 2)

            print(
                "BB35 PFP/FMC physical layout: "
                f"{PFP_CELL_WIDTH}x{PFP_CELL_HEIGHT} cells, "
                f"grid x={PFP_GRID_X} y={PFP_GRID_Y}"
            )
            for packet in packets:
                self.device.write(list(packet))
            time.sleep(0.20)
            self.device.write(list(_black_packet()))
            self.device.write(list(_grid_packet()))
            for packet in _blank_f2_packets():
                self.device.write(list(packet))
            _set_brightness(self.device, 0, 128)
            _set_brightness(self.device, 1, 220)

        keypad = threading.Thread(
            target=self._key_reader,
            name="BB35-FMC-KEYPAD",
            daemon=True,
        )
        ws_thread = threading.Thread(
            target=self._ws_worker,
            name="BB35-FMC-WS",
            daemon=True,
        )
        display = threading.Thread(
            target=self._display_worker,
            name="BB35-FMC-DISPLAY",
            daemon=True,
        )
        self.threads = [keypad, ws_thread, display]
        for thread in self.threads:
            thread.start()
        print(
            "BB35 PATH -> PFP/FMC (F0 cleared; clean F2 page; "
            "PERIOD x3 for PFD)"
        )
    except Exception:
        self.stop_evt.set()
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
        elif raw_device is not None:
            try:
                raw_device.close()
            except Exception:
                pass
        self.device = None
        self.threads = []
        raise


def _bb35_repair_fmc_display_worker(self):
    previous = None
    last_write = 0.0
    self.dirty.set()
    while not self.stop_evt.is_set():
        self.dirty.wait(0.10)
        if not self.dirty.is_set():
            continue
        self.dirty.clear()
        elapsed = time.monotonic() - last_write
        if elapsed < FMC_REFRESH_MIN:
            self.stop_evt.wait(FMC_REFRESH_MIN - elapsed)
            if self.stop_evt.is_set():
                return
        with self.state_lock:
            values = dict(self.fmc_state)
        lines, colors = _compose_page(values)
        state = (lines, colors)
        if state == previous:
            continue
        try:
            with _bb35_output_transaction("BB35-FMC-page"):
                for packet in _page_packets(lines, colors):
                    self.device.write(list(packet))
            previous = state
            last_write = time.monotonic()
            if self.diagnose:
                print("BB35 FMC page -> " + lines[0].strip())
        except Exception as exc:
            if self.diagnose and not self.stop_evt.is_set():
                print(f"BB35 FMC display stopped: {exc}")
            return


def _bb35_repair_fmc_stop(self):
    self.stop_evt.set()
    self.dirty.set()
    for thread in self.threads:
        thread.join(timeout=3.0)
    self.threads = []

    if self.device is not None:
        try:
            with _bb35_output_transaction(
                "BB35-FMC-leave",
                settle_after=0.10,
            ):
                _set_brightness(self.device, 1, 0)
                for packet in _blank_f2_packets():
                    self.device.write(list(packet))
                self.device.write(list(_bb35_repair_hide_f2_grid_packet()))
                canvas = getattr(self, "_repair_f0_canvas", None)
                if canvas is None:
                    canvas = _BB35RepairCanvas(self.device)
                _bb35_repair_clear_f0(canvas, 2)
        except Exception as exc:
            if self.diagnose:
                print(f"BB35 FMC cleanup warning: {exc}")
        try:
            self.device.close()
        except Exception:
            pass

    self.device = None
    self._repair_f0_canvas = None


def _bb35_repair_active_healthy(active):
    worker = getattr(active, "worker", None)
    if worker is not None:
        return bool(worker.is_alive())
    threads = list(getattr(active, "threads", ()) or ())
    return not threads or all(thread.is_alive() for thread in threads)


def _bb35_repair_router_run(self):
    while not self.stop_evt.is_set():
        try:
            self.active = self._make_path()
            self.active.start()
        except Exception as exc:
            self.active = None
            if not self.stop_evt.is_set():
                print(
                    f"BB35 {self.mode.upper()} path start failed: {exc}; "
                    "retrying"
                )
                self.stop_evt.wait(1.0)
            continue

        requested_toggle = False
        restart_dead_path = False

        while not self.stop_evt.is_set():
            if self.toggle_evt.wait(0.05):
                requested_toggle = True
                break
            if not _bb35_repair_active_healthy(self.active):
                restart_dead_path = True
                print(
                    f"BB35 {self.mode.upper()} display worker stopped; "
                    "performing a clean same-mode restart."
                )
                break

        if self.stop_evt.is_set():
            break

        if requested_toggle:
            self.toggle_evt.clear()

        old_mode = self.mode
        if self.active is not None:
            self.active.stop()
            self.active = None

        self.stop_evt.wait(HANDOFF_SETTLE)
        if self.stop_evt.is_set():
            break

        if requested_toggle and not restart_dead_path:
            self.mode = "fmc" if old_mode == "pfd" else "pfd"
            print(f"BB35 HANDOFF: {old_mode.upper()} -> {self.mode.upper()}")

    if self.active is not None:
        self.active.stop()
        self.active = None


BB35PFDPath.start = _bb35_repair_pfd_start
BB35PFDPath.stop = _bb35_repair_pfd_stop
BB35FMCPath.start = _bb35_repair_fmc_start
BB35FMCPath._display_worker = _bb35_repair_fmc_display_worker
BB35FMCPath.stop = _bb35_repair_fmc_stop
MuslimSimBB35PathRouter._run = _bb35_repair_router_run
# <<< MUSLIMSIM BB35 CLEAN HANDOFF REPAIR <<<

'''


def _decode_source(path: Path) -> tuple[str, TextFormat]:
    raw = path.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), TextFormat(newline, had_bom)


def _encode_source(text: str, text_format: TextFormat) -> bytes:
    normalized = text.replace("\r\n", "\n")
    if text_format.newline == "\r\n":
        normalized = normalized.replace("\n", "\r\n")
    data = normalized.encode("utf-8")
    return codecs.BOM_UTF8 + data if text_format.had_utf8_bom else data


def _replace_marker(content: str, replacement: str) -> tuple[str, bool]:
    start = content.find(REPAIR_START)
    if start < 0:
        return content, False
    end = content.find(REPAIR_END, start)
    if end < 0:
        raise RuntimeError("BB35 repair start marker exists without end marker")
    end += len(REPAIR_END)
    while end < len(content) and content[end] == "\n":
        end += 1
    return content[:start] + replacement + content[end:], True


def patch_source(content: str) -> tuple[str, tuple[str, ...]]:
    required = (
        "class BB35PFDPath:",
        "class BB35FMCPath:",
        "class MuslimSimBB35PathRouter:",
        "def run_self_test()",
        "def _blank_f2_packets",
        "def _load_font_packets",
    )
    missing = [token for token in required if token not in content]
    if missing:
        raise RuntimeError(
            "This is not the expected MuslimSim BB35 separate-path module; "
            "missing " + ", ".join(missing)
        )

    block = repair_block()
    updated, replaced = _replace_marker(content, block)
    if not replaced:
        match = re.search(r"(?m)^def run_self_test\(\)\s*->\s*None:\s*$", updated)
        if match is None:
            match = re.search(r"(?m)^def run_self_test\(\):\s*$", updated)
        if match is None:
            raise RuntimeError("Could not locate BB35 run_self_test insertion anchor")
        updated = updated[:match.start()] + block + updated[match.start():]
        action = "added BB35 clean-handoff repair"
    else:
        action = "updated BB35 clean-handoff repair"

    try:
        compile(updated, "<BB35 repair pending module>", "exec")
    except SyntaxError as exc:
        raise RuntimeError(
            f"Pending BB35 module does not compile: line {exc.lineno}: {exc.msg}"
        ) from exc

    if updated == content:
        action = "BB35 clean-handoff repair already current"
    return updated, (action,)


def _atomic_write(path: Path, data: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.bb35-repair-",
        suffix=".pending",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def patch_module(module: Path, *, dry_run: bool = False) -> PatchResult:
    module = module.expanduser().resolve()
    if not module.is_file():
        raise FileNotFoundError(f"BB35 module not found: {module}")

    content, text_format = _decode_source(module)
    updated, _actions = patch_source(content)
    changed = updated != content
    if dry_run or not changed:
        return PatchResult(module, changed, None)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = module.with_name(
        f"{module.name}.before-clean-handoff-{stamp}.bak"
    )
    suffix = 1
    while backup.exists():
        backup = module.with_name(
            f"{module.name}.before-clean-handoff-{stamp}-{suffix}.bak"
        )
        suffix += 1

    shutil.copy2(module, backup)
    try:
        _atomic_write(module, _encode_source(updated, text_format))
        written, _ = _decode_source(module)
        compile(written, str(module), "exec")
    except Exception:
        shutil.copy2(backup, module)
        raise

    return PatchResult(module, True, backup)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Patch MuslimSim BB35 PFD/PFP handoff and v46 worker compatibility."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(r"D:\MuslimSim"),
    )
    parser.add_argument("--module", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    module = (
        args.module
        if args.module is not None
        else args.root / "muslimsim" / "devices" / "pfp_bb35_separate_paths.py"
    )
    try:
        result = patch_module(module, dry_run=bool(args.dry_run))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"BB35 module: {result.module}")
    if args.dry_run:
        print(
            "Dry run passed; repair would change the module."
            if result.changed
            else "Dry run passed; repair is already current."
        )
    elif result.changed:
        print(f"Backup: {result.backup}")
        print("BB35 clean F0/F2 handoff and worker compatibility installed.")
    else:
        print("BB35 clean-handoff repair already current; no backup needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
