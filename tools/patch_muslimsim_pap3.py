#!/usr/bin/env python3
"""Safely add the independent WinCtrl PAP3 manager to MuslimSim final.py.

The patch is deliberately small and marker-based. It never replaces existing
PU Overhead, throttle, PFD, MCDU, AGP, or pedal code. Before changing the live
bridge it compiles the pending source, creates a timestamped backup, and writes
atomically.
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
from typing import Iterable, Optional


IMPORT_START = "# >>> MUSLIMSIM PAP3 IMPORT >>>"
IMPORT_END = "# <<< MUSLIMSIM PAP3 IMPORT <<<"
ARGUMENT_START = "    # >>> MUSLIMSIM PAP3 ARGUMENTS >>>"
ARGUMENT_END = "    # <<< MUSLIMSIM PAP3 ARGUMENTS <<<"
STARTUP_START = "    # >>> MUSLIMSIM PAP3 STARTUP >>>"
STARTUP_END = "    # <<< MUSLIMSIM PAP3 STARTUP <<<"
SHUTDOWN_START = "        # >>> MUSLIMSIM PAP3 SHUTDOWN >>>"
SHUTDOWN_END = "        # <<< MUSLIMSIM PAP3 SHUTDOWN <<<"


@dataclass(frozen=True)
class TextFormat:
    newline: str
    had_utf8_bom: bool


@dataclass(frozen=True)
class PatchResult:
    bridge: Path
    changed: bool
    backup: Optional[Path]
    actions: tuple[str, ...]


def _import_block() -> str:
    return '''# >>> MUSLIMSIM PAP3 IMPORT >>>
try:
    from muslimsim.devices.pap3_mcp import MuslimSimPAP3MCP
    _MUSLIMSIM_PAP3_ERROR = None
except Exception as _muslimsim_pap3_import_error:
    MuslimSimPAP3MCP = None
    _MUSLIMSIM_PAP3_ERROR = _muslimsim_pap3_import_error
# <<< MUSLIMSIM PAP3 IMPORT <<<

'''


def _argument_block(at_switch_type: str) -> str:
    return f'''    # >>> MUSLIMSIM PAP3 ARGUMENTS >>>
    parser.add_argument(
        "--no-pap3",
        action="store_true",
        help="Disable the separate WINCTRL PAP3 Boeing MCP manager",
    )
    parser.add_argument(
        "--pap3-refresh",
        type=float,
        default=0.12,
        help="Minimum seconds between dirty PAP3 LCD writes (default: 0.12)",
    )
    parser.add_argument(
        "--pap3-start-delay",
        type=float,
        default=3.0,
        help=(
            "Seconds PAP3 waits before its first output burst so BB35/BB36 "
            "finish display initialization (default: 3.0)"
        ),
    )
    parser.add_argument(
        "--pap3-at-switch",
        choices=("magnetic", "standard"),
        default="{at_switch_type}",
        help="Physical PAP3 A/T ARM switch type (default: {at_switch_type})",
    )
    parser.add_argument(
        "--diagnose-pap3",
        action="store_true",
        help="Print PAP3 HID edges, WebSocket reconnects, and MCP actions",
    )
    # <<< MUSLIMSIM PAP3 ARGUMENTS <<<

'''


def _startup_block() -> str:
    return '''    # >>> MUSLIMSIM PAP3 STARTUP >>>
    # PAP3 is a separate WinCtrl device and owns its own HID handle, input
    # reader, X-Plane WebSocket, output writer, and reconnect loop. A missing
    # PAP3 cannot stop any already-working MuslimSim device.
    pap3_mcp = None
    if (
        not args.no_winctrl
        and not args.no_pap3
        and not args.dry_run
        and aircraft_profile in (
            AIRCRAFT_PROFILE_ZIBO,
            AIRCRAFT_PROFILE_B738_COMPATIBLE,
        )
    ):
        if MuslimSimPAP3MCP is None:
            print(
                "WARNING: PAP3 MCP module unavailable: "
                f"{_MUSLIMSIM_PAP3_ERROR}"
            )
        else:
            try:
                pap3_mcp = MuslimSimPAP3MCP(
                    api_version=api_version,
                    api_root=API_ROOT,
                    refresh_interval=args.pap3_refresh,
                    startup_delay=args.pap3_start_delay,
                    at_switch_type=args.pap3_at_switch,
                    diagnose=(
                        args.diagnose_pap3
                        or args.diagnose_controls
                    ),
                )
                pap3_mcp.start()
                print(
                    "PAP3 MCP manager enabled: auto-detect/reconnect, "
                    "Zibo MCP controls, native displays, annunciators, "
                    "brightness, and A/T solenoid."
                )
            except Exception as exc:
                print(f"WARNING: PAP3 MCP startup failed: {exc}")
                pap3_mcp = None
    elif (
        not args.no_pap3
        and aircraft_profile == AIRCRAFT_PROFILE_LEVELUP
    ):
        print(
            "PAP3 MCP: skipped for LevelUp profile; "
            "current MuslimSim mapping targets Zibo/B738-compatible."
        )
    # <<< MUSLIMSIM PAP3 STARTUP <<<

'''


def _shutdown_block() -> str:
    return '''        # >>> MUSLIMSIM PAP3 SHUTDOWN >>>
        if pap3_mcp is not None:
            try:
                pap3_mcp.stop()
                print("PAP3 MCP stopped and blacked out.")
            except Exception as exc:
                print(f"PAP3 MCP shutdown warning: {exc}")
        # <<< MUSLIMSIM PAP3 SHUTDOWN <<<
'''


def _decode_source(path: Path) -> tuple[str, TextFormat]:
    raw = path.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Bridge is not UTF-8 text: {path}: {exc}") from exc

    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), TextFormat(newline, had_bom)


def _encode_source(text: str, text_format: TextFormat) -> bytes:
    normalized = text.replace("\r\n", "\n")
    if text_format.newline == "\r\n":
        normalized = normalized.replace("\n", "\r\n")
    encoded = normalized.encode("utf-8")
    if text_format.had_utf8_bom:
        encoded = codecs.BOM_UTF8 + encoded
    return encoded


def _replace_marker_block(
    content: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> tuple[str, bool]:
    start = content.find(start_marker)
    if start < 0:
        return content, False

    end = content.find(end_marker, start)
    if end < 0:
        raise RuntimeError(
            f"Found PAP3 start marker without end marker: {start_marker}"
        )
    end += len(end_marker)
    if end < len(content) and content[end] == "\n":
        end += 1
    if end < len(content) and content[end] == "\n":
        end += 1

    return content[:start] + replacement + content[end:], True


def _line_start(content: str, position: int) -> int:
    start = content.rfind("\n", 0, position)
    return 0 if start < 0 else start + 1


def _insert_import(content: str) -> tuple[str, str]:
    if IMPORT_START in content:
        return content, "guarded import already present"

    match = re.search(r"(?m)^API_ROOT\s*=", content)
    if match is None:
        raise RuntimeError(
            "Could not locate the top-level API_ROOT constant for the PAP3 import."
        )
    pos = _line_start(content, match.start())
    return content[:pos] + _import_block() + content[pos:], "added guarded import"


def _insert_or_update_arguments(
    content: str,
    at_switch_type: str,
) -> tuple[str, str]:
    replacement = _argument_block(at_switch_type)
    content, replaced = _replace_marker_block(
        content,
        ARGUMENT_START,
        ARGUMENT_END,
        replacement,
    )
    if replaced:
        return content, f"updated PAP3 arguments (A/T default={at_switch_type})"

    match = re.search(r"(?m)^    parser\.add_argument\(", content)
    if match is None:
        raise RuntimeError(
            "Could not locate the first parser.add_argument call in main()."
        )
    return (
        content[:match.start()] + replacement + content[match.start():],
        f"added PAP3 arguments (A/T default={at_switch_type})",
    )


def _insert_startup(content: str) -> tuple[str, str]:
    replacement = _startup_block()
    content, replaced = _replace_marker_block(
        content,
        STARTUP_START,
        STARTUP_END,
        replacement,
    )
    if replaced:
        return content, "updated PAP3 startup manager"

    anchor = '    print()\n    print("Running. Press Ctrl+C to stop.")\n'
    pos = content.rfind(anchor)
    if pos < 0:
        # Permit minor wording changes while still requiring the same main()
        # indentation and an unambiguous final Running line.
        matches = list(
            re.finditer(
                r'(?m)^    print\(["\']Running\.[^\n]*["\']\)\s*$',
                content,
            )
        )
        if not matches:
            raise RuntimeError(
                "Could not locate MuslimSim's final 'Running...' startup anchor."
            )
        pos = _line_start(content, matches[-1].start())
    return content[:pos] + replacement + content[pos:], "added startup manager"


def _insert_shutdown(content: str) -> tuple[str, str]:
    if SHUTDOWN_START in content:
        return content, "shutdown manager already present"

    matches = list(re.finditer(r"(?m)^        stop_evt\.set\(\)\s*$", content))
    if not matches:
        raise RuntimeError(
            "Could not locate the final stop_evt.set() in MuslimSim shutdown."
        )
    match = matches[-1]
    line_end = content.find("\n", match.end())
    if line_end < 0:
        line_end = len(content)
        suffix = "\n"
    else:
        line_end += 1
        suffix = ""
    insertion = _shutdown_block()
    return (
        content[:line_end] + suffix + insertion + content[line_end:],
        "added shutdown/blackout manager",
    )


def patch_source(content: str, at_switch_type: str) -> tuple[str, tuple[str, ...]]:
    switch_type = at_switch_type.strip().lower()
    if switch_type not in {"magnetic", "standard"}:
        raise ValueError("A/T switch type must be magnetic or standard")

    original = content
    actions: list[str] = []

    content, action = _insert_import(content)
    actions.append(action)
    content, action = _insert_or_update_arguments(content, switch_type)
    actions.append(action)
    content, action = _insert_startup(content)
    actions.append(action)
    content, action = _insert_shutdown(content)
    actions.append(action)

    # Syntax validation is intentionally done on the exact pending source.
    try:
        compile(content, "<MuslimSim PAP3 pending bridge>", "exec")
    except SyntaxError as exc:
        raise RuntimeError(
            f"Pending PAP3 bridge does not compile: line {exc.lineno}: {exc.msg}"
        ) from exc

    if content == original:
        actions.append("no source changes required")
    return content, tuple(actions)


def _candidate_bridges(root: Path) -> Iterable[Path]:
    preferred = (root / "bridge" / "final.py", root / "final.py")
    yielded: set[Path] = set()
    for candidate in preferred:
        if candidate.is_file():
            resolved = candidate.resolve()
            yielded.add(resolved)
            yield resolved

    fallback = sorted(
        (p.resolve() for p in root.rglob("final.py") if p.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in fallback:
        if candidate not in yielded:
            yielded.add(candidate)
            yield candidate


def resolve_bridge(root: Path, requested: Optional[Path]) -> Path:
    if requested is not None:
        bridge = requested.expanduser().resolve()
        if not bridge.is_file():
            raise FileNotFoundError(f"Bridge file not found: {bridge}")
        return bridge

    if not root.is_dir():
        raise FileNotFoundError(f"MuslimSim root not found: {root}")

    candidate = next(iter(_candidate_bridges(root)), None)
    if candidate is None:
        raise FileNotFoundError(
            f"Could not find final.py below {root}; pass --bridge explicitly."
        )
    return candidate


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.pap3-",
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


def patch_bridge(
    bridge: Path,
    at_switch_type: str,
    *,
    dry_run: bool = False,
) -> PatchResult:
    content, text_format = _decode_source(bridge)
    patched, actions = patch_source(content, at_switch_type)
    changed = patched != content

    if dry_run or not changed:
        return PatchResult(bridge, changed, None, actions)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = bridge.with_name(f"{bridge.name}.before-pap3-{timestamp}.bak")
    suffix = 1
    while backup.exists():
        backup = bridge.with_name(
            f"{bridge.name}.before-pap3-{timestamp}-{suffix}.bak"
        )
        suffix += 1

    shutil.copy2(bridge, backup)
    try:
        _atomic_write(bridge, _encode_source(patched, text_format))
        # Verify the bytes as written, not just the normalized in-memory text.
        written, _ = _decode_source(bridge)
        compile(written, str(bridge), "exec")
    except Exception:
        shutil.copy2(backup, bridge)
        raise

    return PatchResult(bridge, True, backup, actions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely patch the unified MuslimSim bridge for PAP3 MCP support."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(r"D:\MuslimSim"),
        help=r"MuslimSim root (default: D:\MuslimSim)",
    )
    parser.add_argument(
        "--bridge",
        type=Path,
        help="Explicit active final.py path",
    )
    parser.add_argument(
        "--at-switch",
        choices=("magnetic", "standard"),
        default="magnetic",
        help="Default physical A/T switch type",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without changing the bridge",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = args.root.expanduser().resolve()
        bridge = resolve_bridge(root, args.bridge)
        result = patch_bridge(
            bridge,
            args.at_switch,
            dry_run=bool(args.dry_run),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Bridge: {result.bridge}")
    for action in result.actions:
        print(f"  - {action}")

    if args.dry_run:
        print(
            "Dry run passed; bridge would change."
            if result.changed
            else "Dry run passed; bridge is already current."
        )
    elif result.changed:
        print(f"Backup: {result.backup}")
        print("PAP3 bridge patch installed and syntax-checked.")
    else:
        print("PAP3 bridge patch already current; no backup was needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
