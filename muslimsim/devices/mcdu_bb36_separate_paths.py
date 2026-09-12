#!/usr/bin/env python3
"""MuslimSim BB36 TRUE separate FMC / PFD path router.

Device
------
WINCTRL 32 MCDU CAPTAIN
VID 0x4098 / PID 0xBB36
native hardware address 0x32 / 0xBB

Default mode
------------
FMC, preserving the device's existing MuslimSim behavior.

Physical switch
---------------
Press PERIOD (.) three times quickly:

    FMC -- . . . --> PFD
    PFD -- . . . --> FMC

The physical PERIOD key on HARDWARE_MCDU is hardware index 41.

Path separation
---------------
FMC path:
    fresh BB36 HID handle
    original native 0x32/0xBB font/config
    original MCDU 24x14 F2 renderer
    Zibo FMC1 WebSocket display + keypad
    its own state and workers

PFD path:
    fresh BB36 HID handle
    original native 0x32/0xBB glyph upload
    fresh native F0 canvas from final.py
    existing MuslimSim graphical PFD worker
    its own state and workers

Handoff:
    stop active workers
    FMC blanks its own F2 page before surrender
    close active BB36 HID handle completely
    short settle
    open the other mode from scratch

FMC and PFD never own the same BB36 HID handle at the same time.
"""

from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import hid
except ImportError:
    hid = None

try:
    import websocket
except ImportError:
    websocket = None

# Reuse the already-proven BB36 FMC protocol implementation byte-for-byte
# instead of making a second copy of its packet and Zibo mappings.
from .mcdu_bb36 import (
    MCDU_VID,
    MCDU_PID,
    MCDU_IDENTIFIER,
    MCDU_FAMILY,
    MCDU_COLUMNS,
    MCDU_ROWS,
    MCDU_DISPLAY_MIN_INTERVAL,
    MCDU_WS_RECV_TIMEOUT,
    MCDU_WS_RECONNECT_SECONDS,
    MCDU_BRIGHTNESS_DATAREF,
    MCDU_BRIGHTNESS_INDEX,
    MCDU_FMC_DATAREFS,
    MCDU_KEY_MAP,
    COLOR_WHITE,
    COLOR_AMBER,
    COLOR_GREEN,
    COLOR_MAGENTA,
    _read_font_packets,
    _black_background_packet,
    _text_grid_packet,
    _set_brightness,
    _compose_zibo_page,
    _page_packets,
    _button_bits,
    _resolve_dataref_id,
    _resolve_command_id,
    _ws_decode_text,
    _ws_scalar,
)
from .cdu_exec_alert import (
    BB36_EXEC_DASH_LIGHT_CHANNEL,
    EXEC_LIGHT_OFF,
    EXEC_LIGHT_ON,
    ZIBO_CAPTAIN_EXEC_LIGHT_DATAREFS,
    exec_light_active,
    exec_light_output_value,
)

BB36_PERIOD_INDEX = 41
BB36_SECRET_TAPS = 3
BB36_SECRET_GAP = 0.60
BB36_DISPLAY_SLASH_INDEX = 70
BB36_DISPLAY_SLASH_TAPS = 2
BB36_DISPLAY_SLASH_GAP = 0.55
BB36_DISPLAY_PAGE_ORDER = ("pfd", "nd", "eng_pri", "mfd", "hyd")
BB36_HANDOFF_SETTLE = 0.18
BB36_POWER_DATAREF = "sim/cockpit/electrical/avionics_on"

# ---------------------------------------------------------------------------
# WINCTRL 32 MCDU CAPTAIN screen characteristics
#
# Measured on the panel with tools/probe_mcdu_graphics_plane.py, which paints
# labelled bands across the framebuffer and is read off a photograph.
#
# The framebuffer is 640x480, but the glass does not show all of it: bands at
# rows 0-9 and 470-479 never appeared, while every band between did.  So the
# visible area is roughly rows 10-469, and anything addressed outside that is
# written and simply never seen.
BB36_NATIVE_WIDTH = 640
BB36_NATIVE_HEIGHT = 480
BB36_VISIBLE_TOP = 10
BB36_VISIBLE_BOTTOM = 469

# The character page: 24x14 cells of 23x29 at (52, 37), so it covers
# x 52..604 and y 37..443.  That leaves bands of bare graphics plane above and
# below it -- about 27 rows at the top and 26 at the bottom of the visible
# area -- which is where a previous PFD session shows through.
#
# This is NOT to be "fixed" by copying the PFP 3N's font rebuild.  The .xpwwf
# resource is authored at 23x29, which is this panel's own pitch; the PFP 3N
# rebuilds it to 23x32 because ITS six line-select rows need that spacing.
# Applying that here would push this panel's rows out of line with its own
# LSK keys, which is the one thing its geometry currently gets right.
BB36_CELL_WIDTH = 23
BB36_CELL_HEIGHT = 29
BB36_PAGE_ORIGIN_X = 0x34          # 52
BB36_PAGE_ORIGIN_Y = 0x25          # 37
BB36_PFP3N_CELL_HEIGHT = 32        # what the PFP uses, and why it differs
# ---------------------------------------------------------------------------

# The MCDU's two display planes are independent, and the character plane the
# FMC uses covers only the middle of the glass -- 24x14 cells from (52, 37),
# so x 52..460 and y 37..443 of a 640x480 screen.  Anything the PFD left on
# the graphics plane outside that stays visible as a frame around the FMC
# page.  Since the panel starts in FMC mode, nothing was ever clearing it.


# The FMC page is a 24x14 character grid, so the MCDU's standby message is
# built the same way -- through the proven page path, not as graphics.
MUSLIMSIM_NAME = "MUSLIMSIM"
BB36_STANDBY_SIM_STOPPED = ("SIM STOPPED", "START X-PLANE")
BB36_STANDBY_UNPOWERED = ("AIRCRAFT UNPOWERED", "BATTERY SWITCH ON")


def _standby_page(reason: str, remedy: str):
    """Build the MuslimSim standby page as FMC character rows.

    A dark panel and a panel showing nothing look identical, so the MCDU says
    which one it is.  Previously it simply stayed black whenever the CDU had
    nothing to show, while the PFP beside it explained itself.
    """
    lines = [" " * MCDU_COLUMNS for _ in range(MCDU_ROWS)]
    colors = [tuple([COLOR_WHITE] * MCDU_COLUMNS) for _ in range(MCDU_ROWS)]

    def place(row: int, text: str, colour: int) -> None:
        text = str(text)[:MCDU_COLUMNS]
        start = max(0, (MCDU_COLUMNS - len(text)) // 2)
        padded = (" " * start + text).ljust(MCDU_COLUMNS)[:MCDU_COLUMNS]
        lines[row] = padded
        colors[row] = tuple(
            colour if padded[column] != " " else COLOR_WHITE
            for column in range(MCDU_COLUMNS)
        )

    place(0, MUSLIMSIM_NAME, COLOR_MAGENTA)
    place(3, "FMC OFFLINE", COLOR_AMBER)
    place(5, reason, COLOR_WHITE)
    place(7, remedy, COLOR_GREEN)
    place(11, "DEVELOPED BY", COLOR_WHITE)
    place(12, MUSLIMSIM_NAME, COLOR_MAGENTA)
    place(13, "WINCTRL MCDU", COLOR_GREEN)

    return tuple(lines), tuple(colors)


def _bb36_hide_f2_grid_packet() -> bytes:
    """Move BB36's persistent character grid away from the live F0 LCD."""

    packet = bytearray(64)
    packet[:4] = bytes((0xF0, 0x00, 0x00, 0x2A))
    packet[4:29] = bytes((
        MCDU_IDENTIFIER, MCDU_FAMILY, 0x00, 0x00,
        0x18, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00,
        0x08, 0x00, 0x00, 0x00,
        0xFF, 0x07,  # x = 2047, safely outside the 640-pixel glass
        0xFF, 0x07,  # y = 2047, safely outside the 480-pixel glass
        0x01, 0x00,
        0x01, 0x00,
    ))
    packet[29:46] = bytes((
        MCDU_IDENTIFIER, MCDU_FAMILY, 0x00, 0x00,
        0x05, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x01, 0x00, 0x00, 0x00, 0x00,
    ))
    return bytes(packet)


def _bb36_blank_f2_packets():
    lines = tuple(" " * MCDU_COLUMNS for _ in range(MCDU_ROWS))
    colors = tuple(
        tuple(COLOR_WHITE for _ in range(MCDU_COLUMNS))
        for _ in range(MCDU_ROWS)
    )
    return _page_packets(lines, colors)


# Set from final.py by --trace-pfp-handoff, so this panel's handoff can be
# read side by side with the PFP 3N's.  Off by default and pure pass-through.
TRACE_HANDOFF = False


class _TracingDevice:
    """Pass-through HID handle that reports what a path sends, and when."""

    def __init__(self, device, label: str) -> None:
        self._device = device
        self._label = label
        self._phases = []
        self._current = None
        self._started = time.monotonic()

    @staticmethod
    def _kind(report) -> str:
        data = bytes(report)

        if not data:
            return "empty"

        if data[0] == 0x02 and len(data) > 8 and data[6] == 0x49:
            return f"brightness ch{data[7]}={data[8]}"

        if data[0] == 0xF2:
            return "F2 character page"

        if data[0] == 0xF0:
            # One stream, not three.  Splitting on byte 1 and byte 3 chopped a
            # single font upload into hundreds of alternating fragments and
            # made the trace unreadable.
            return "F0 stream (font upload or graphics)"

        return f"other 0x{data[0]:02X}"

    def write(self, report):
        kind = self._kind(report)
        now = time.monotonic()

        if self._current is None or self._current[0] != kind:
            self._current = [kind, 0, now, now]
            self._phases.append(self._current)

        self._current[1] += 1
        self._current[3] = now

        return self._device.write(report)

    def read(self, *args, **kwargs):
        return self._device.read(*args, **kwargs)

    def set_nonblocking(self, *args, **kwargs):
        return self._device.set_nonblocking(*args, **kwargs)

    def close(self):
        self.report("closing")
        return self._device.close()

    def __getattr__(self, name):
        return getattr(self._device, name)

    def report(self, moment: str) -> None:
        if not self._phases:
            return

        total = sum(phase[1] for phase in self._phases)
        elapsed = time.monotonic() - self._started
        print(f"TRACE {self._label} [{moment}] {total} reports in {elapsed:.3f}s")

        for kind, count, first, last in self._phases:
            span = last - first
            print(f"TRACE     {count:5d}  {span:6.3f}s  {kind}")

        self._phases = []
        self._current = None


def _open_bb36():
    if hid is None:
        raise RuntimeError("hidapi unavailable; install hidapi")

    devices = hid.enumerate(MCDU_VID, MCDU_PID)
    if not devices:
        raise FileNotFoundError(
            "WINCTRL 32 MCDU CAPTAIN BB36 not connected"
        )

    info = devices[0]
    path = info.get("path")

    if not path:
        raise RuntimeError("BB36 HID path unavailable")

    device = hid.device()
    device.open_path(path)

    try:
        device.set_nonblocking(1)
    except Exception:
        pass

    return device


class _TriplePeriodDetector:
    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self.count = 0
        self.last = 0.0

    def press(self) -> bool:
        now = time.monotonic()

        if self.count and now - self.last > BB36_SECRET_GAP:
            self.count = 0

        self.count += 1
        self.last = now

        if self.count >= BB36_SECRET_TAPS:
            self.count = 0
            self.callback()
            return True

        return False


class _DoubleSlashDetector:
    """Detect two quick physical SLASH presses in the BB36 PFD path."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self.count = 0
        self.last = 0.0

    def press(self) -> bool:
        now = time.monotonic()

        if self.count and now - self.last > BB36_DISPLAY_SLASH_GAP:
            self.count = 0

        self.count += 1
        self.last = now

        if self.count >= BB36_DISPLAY_SLASH_TAPS:
            self.count = 0
            self.callback()
            return True

        return False


# MUSLIMSIM_BB36_LIVE_OWNER_TAKEOVER_V3_ROUTER
# BB36's MCDU LCD endpoint is kept below the real simulator source cadence. The
# working BB35/PFP3N path and every other panel retain their existing cadence.
BB36_PFD_MIN_REFRESH_SECONDS = 0.120
BB36_PFD_STARTUP_GRACE_SECONDS = 8.0
# MUSLIMSIM_BB36_STALL_THRESHOLD_V6
# 3.0 s was too tight, and the recorded staleness proves it in two clean
# populations: 5561 of 5665 stalls read 8.0/8.1 s - no heartbeat at all after
# the path started, which is a genuinely wedged panel - while the other ~104
# read 3.0 to 3.6 s, clustered just above the old threshold.  Those are live
# panels having one slow frame, and each one cost a full teardown and reopen,
# font upload included, of hardware that was working.  6.0 s clears the worst
# recorded slow frame with margin and still sits below the 8.0 s startup
# grace, so a real wedge is still caught on the first check after the grace.
BB36_PFD_PROGRESS_TIMEOUT_SECONDS = 6.0
# MUSLIMSIM_BB36_RECOVERY_V7
# A path must remain genuinely healthy for two minutes before a previous
# recovery episode is forgotten. V6 cleared the backoff after the first
# healthy supervisor check (~8 s), which is why repeated 8.1-second wedges
# kept returning to "attempt 1" and reopening the panel indefinitely.
BB36_RECOVERY_STABILITY_SECONDS = 120.0
BB36_RECOVERY_SOFT_RESTART_LIMIT = 1
BB36_RECOVERY_CIRCUIT_OPEN_SECONDS = 60.0
BB36_RECOVERY_RETIRED_JOIN_SECONDS = 2.0
# MUSLIMSIM_BB36_PERSISTENT_F0_OWNER_V4
# Keypad read failures are recoverable input failures, not display failures.
# Keep the one live F0 display owner untouched while a fresh input-only HID
# handle is opened. PERIOD x3 selects a graphical FMC page inside this same
# owner; it never enters the firmware's separate F2 presentation.
BB36_INPUT_REOPEN_DELAY_SECONDS = 0.20
BB36_INPUT_REOPEN_RETRY_SECONDS = 0.50
BB36_GRAPHICAL_FMC_PAGE = "fmc"


def _bb36_live_owner_v3_log(message: Any) -> None:
    """Append low-volume BB36 ownership evidence without touching other panels."""
    try:
        root = Path(__file__).resolve().parents[2]
        log_path = root / "logs" / "bb36_live_owner_takeover_v3.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        thread_name = threading.current_thread().name
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} [{thread_name}] {str(message)}\n")
    except Exception:
        pass


class BB36PFDPath:
    """Fresh graphics-only BB36 session using final.py's PFD renderer."""

    def __init__(
        self,
        open_pfd: Callable[[], Tuple[Any, Any]],
        pfd_worker: Callable[..., None],
        api_version: str,
        pfd_ids: Dict[str, int],
        refresh_interval: float,
        toggle_callback: Callable[[], None],
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
        api_root: str = "http://127.0.0.1:8086",
    ) -> None:
        self.open_pfd = open_pfd
        self.pfd_worker = pfd_worker
        self.api_version = api_version
        self.pfd_ids = pfd_ids
        try:
            requested_refresh = float(refresh_interval)
        except (TypeError, ValueError):
            requested_refresh = BB36_PFD_MIN_REFRESH_SECONDS
        self.refresh_interval = max(
            BB36_PFD_MIN_REFRESH_SECONDS,
            requested_refresh,
        )
        self.toggle_callback = toggle_callback
        self.diagnose = diagnose
        self.input_router = input_router
        self.api_root = str(api_root).rstrip("/")

        # Display output and keypad input are deliberately separate handles when
        # Windows permits it.  A blocked F0 write can no longer starve // or ....
        self.device = None
        self.input_device = None
        self.input_device_is_shared = False
        self.canvas = None
        self.stop_evt = threading.Event()
        self.worker = None
        self.key_reader = None
        self.fmc_command_worker = None
        self.fmc_key_queue: "queue.Queue[Tuple[str, int]]" = queue.Queue()
        self.simulator_connected = threading.Event()
        self.simulator_connected.set()

        self.started_monotonic = 0.0
        self.key_heartbeat_monotonic = 0.0
        self.key_report_count = 0
        self.output_report_count = 0
        self.retired_output_worker = None

        self.status = {
            "frames": 0,
            "error": None,
            "last_sample_ms": None,
            "last_render_ms": None,
            "live": False,
            "heartbeat_monotonic": 0.0,
            "heartbeat_phase": "not-started",
            "output_progress_monotonic": 0.0,
            "f0_reports": 0,
            "key_heartbeat_monotonic": 0.0,
            "key_reports": 0,
            "input_handle": "pending",
            "input_recovering": False,
            "key_error": "",
        }
        self.status_lock = threading.Lock()

        # Local graphical-page selection for the current BB36 PFD session.
        self.display_page_lock = threading.Lock()
        self.display_page = "pfd"

    def set_simulator_connected(self, connected: bool) -> None:
        # The same F0 session remains the sole owner while X-Plane is down and
        # after it reconnects.  Only the graphical FMC command transport is
        # gated; no display handle is closed or reconfigured.
        if connected:
            self.simulator_connected.set()
        else:
            self.simulator_connected.clear()
            try:
                while True:
                    self.fmc_key_queue.get_nowait()
            except queue.Empty:
                pass

    def get_display_page(self) -> str:
        with self.display_page_lock:
            return self.display_page

    def _cycle_display_page(self) -> None:
        with self.display_page_lock:
            current = self.display_page
            if current == BB36_GRAPHICAL_FMC_PAGE:
                self.display_page = "pfd"
            else:
                try:
                    index = BB36_DISPLAY_PAGE_ORDER.index(current)
                except ValueError:
                    index = 0
                self.display_page = BB36_DISPLAY_PAGE_ORDER[
                    (index + 1) % len(BB36_DISPLAY_PAGE_ORDER)
                ]
            page = self.display_page

        print(
            f"BB36 DISPLAY -> {page.upper().replace('_', ' ')} "
            "(SLASH / x2)"
        )
        _bb36_live_owner_v3_log(
            f"GRAPHICAL PAGE -> {page.upper()} (SLASH x2)"
        )

    def _toggle_graphical_fmc(self) -> None:
        """PERIOD x3 toggles FMC/PFD inside the existing F0 owner."""
        with self.display_page_lock:
            if self.display_page == BB36_GRAPHICAL_FMC_PAGE:
                self.display_page = "pfd"
            else:
                self.display_page = BB36_GRAPHICAL_FMC_PAGE
            page = self.display_page

        print(
            "BB36 SECRET: PERIOD x3 -> "
            f"{page.upper()} (persistent F0 owner; no F2 handoff)"
        )
        _bb36_live_owner_v3_log(
            f"GRAPHICAL MODE -> {page.upper()} (PERIOD x3; persistent F0)"
        )

    def _note_output_progress(self) -> None:
        """Publish a heartbeat only after an F0 report was accepted."""
        now = time.monotonic()
        self.output_report_count += 1
        with self.status_lock:
            self.status["output_progress_monotonic"] = now
            self.status["f0_reports"] = int(self.output_report_count)

    def retired_output_quiesced(self, wait_seconds: float = 0.0) -> bool:
        """True only when a previously closed output worker has actually left."""
        thread = self.retired_output_worker
        if thread is None:
            return True
        if thread.is_alive() and wait_seconds > 0.0:
            thread.join(timeout=max(0.0, float(wait_seconds)))
        if thread.is_alive():
            return False
        self.retired_output_worker = None
        return True

    def start(self) -> None:
        self.stop_evt.clear()

        # The bridge opener now gives the live owner a fresh output handle instead
        # of reusing the pre-open standby reader's handle/canvas.
        self.device, self.canvas = self.open_pfd()

        # The fitted canvas can wrap the native writer. Attach the recovery
        # heartbeat to the raw F0 canvas without changing one output byte.
        raw_canvas = self.canvas
        while getattr(raw_canvas, "_canvas", None) is not None:
            raw_canvas = raw_canvas._canvas
        if hasattr(raw_canvas, "set_progress_callback"):
            try:
                raw_canvas.set_progress_callback(self._note_output_progress)
            except Exception:
                pass

        if TRACE_HANDOFF:
            self.device = _TracingDevice(self.device, "BB36 PFD")

            # The fitted canvas may wrap another canvas.  Retarget the actual raw
            # canvas owner so traced writes and the output worker use one handle.
            target = self.canvas
            while getattr(target, "_canvas", None) is not None:
                target = target._canvas

            if getattr(target, "device", None) is not None:
                target.device = self.device

            if target is not self.canvas:
                self.canvas.device = self.device

            print("TRACE BB36 PFD path opened (the open itself is not traced)")

        # Open a second handle for input.  Windows HID normally permits this and
        # delivers the same input stream to each open handle.  If a local driver
        # denies the second open, retain a safe shared-handle fallback plus the
        # progress watchdog below.
        try:
            self.input_device = _open_bb36()
            self.input_device_is_shared = False
            input_mode = "dedicated"
            print("BB36 PFD INPUT: dedicated keypad handle opened.")
            _bb36_live_owner_v3_log("PFD INPUT dedicated keypad handle opened")
        except Exception as exc:
            self.input_device = self.device
            self.input_device_is_shared = True
            input_mode = "shared-fallback"
            print(
                "WARNING: BB36 dedicated keypad handle unavailable; "
                f"using shared fallback: {type(exc).__name__}: {exc}"
            )
            _bb36_live_owner_v3_log(
                "PFD INPUT shared-handle fallback: "
                f"{type(exc).__name__}: {exc}"
            )

        # The new F0 owner begins with the alert dark.  Only the shared Live
        # output worker can illuminate it after simulator and power authority.
        _set_brightness(
            self.device,
            BB36_EXEC_DASH_LIGHT_CHANNEL,
            EXEC_LIGHT_OFF,
        )

        now = time.monotonic()
        self.started_monotonic = now
        self.key_heartbeat_monotonic = now
        with self.status_lock:
            self.status["heartbeat_monotonic"] = now
            self.status["heartbeat_phase"] = "starting"
            self.status["output_progress_monotonic"] = now
            self.status["f0_reports"] = 0
            self.status["key_heartbeat_monotonic"] = now
            self.status["input_handle"] = input_mode
            self.status["error"] = None

        self.worker = threading.Thread(
            target=self.pfd_worker,
            args=(
                self.device,
                self.canvas,
                self.api_version,
                self.pfd_ids,
                self.refresh_interval,
                self.stop_evt,
                self.status,
                self.status_lock,
                self.get_display_page,
            ),
            name="BB36-PFD-PATH",
            daemon=True,
        )

        self.key_reader = threading.Thread(
            target=self._key_reader,
            name="BB36-PFD-SECRET",
            daemon=True,
        )
        self.fmc_command_worker = threading.Thread(
            target=self._graphical_fmc_command_worker,
            name="BB36-F0-FMC-COMMANDS",
            daemon=True,
        )

        # Start input first so // and ... remain observable even while the first
        # full graphical frame is being committed. The command worker owns no
        # HID output; it sends only Zibo FMC commands over WebSocket.
        self.key_reader.start()
        self.fmc_command_worker.start()
        self.worker.start()

        if TRACE_HANDOFF and isinstance(self.device, _TracingDevice):
            self.device.report("PFD entry")

        print(
            "BB36 PATH -> PFD "
            f"(fresh live output; {input_mode} input; "
            f"{1.0 / self.refresh_interval:.1f} Hz maximum; "
            "SLASH x2 cycles PFD/ND/ENG PRI/MFD/HYD; "
            "PERIOD x3 toggles graphical FMC without F0/F2 handoff)"
        )
        _bb36_live_owner_v3_log(
            f"PFD OWNER START input={input_mode} "
            f"refresh={self.refresh_interval:.3f}s"
        )

    def _open_replacement_input_handle(self) -> Optional[Any]:
        """Reopen only BB36 keypad input; never touch the live display handle."""
        while not self.stop_evt.is_set():
            with self.status_lock:
                self.status["input_recovering"] = True
                self.status["input_handle"] = "recovering-dedicated"
            try:
                replacement = _open_bb36()
                old = self.input_device
                self.input_device = replacement
                self.input_device_is_shared = False
                if old is not None and old is not self.device:
                    try:
                        old.close()
                    except Exception:
                        pass
                now = time.monotonic()
                self.key_heartbeat_monotonic = now
                with self.status_lock:
                    self.status["input_recovering"] = False
                    self.status["input_handle"] = "dedicated"
                    self.status["key_error"] = ""
                    self.status["key_heartbeat_monotonic"] = now
                print("BB36 PFD INPUT: keypad handle recovered without restarting display.")
                _bb36_live_owner_v3_log(
                    "PFD INPUT RECOVERED: dedicated keypad handle reopened; "
                    "display owner preserved"
                )
                return replacement
            except Exception as exc:
                with self.status_lock:
                    self.status["key_error"] = f"{type(exc).__name__}: {exc}"
                self.key_heartbeat_monotonic = time.monotonic()
                self.stop_evt.wait(BB36_INPUT_REOPEN_RETRY_SECONDS)

        return None

    def _key_reader(self) -> None:
        reader = self.input_device or self.device
        if reader is None:
            with self.status_lock:
                self.status["key_error"] = "BB36 keypad handle is unavailable"
            return

        previous = None
        period_detector = _TriplePeriodDetector(self._toggle_graphical_fmc)
        slash_detector = _DoubleSlashDetector(self._cycle_display_page)
        next_status_publish = 0.0

        while not self.stop_evt.is_set():
            self.key_heartbeat_monotonic = time.monotonic()
            try:
                report = reader.read(128)
            except Exception as exc:
                if self.stop_evt.is_set():
                    return

                with self.status_lock:
                    self.status["key_error"] = f"{type(exc).__name__}: {exc}"
                    self.status["input_recovering"] = True

                print(
                    "BB36 PFD INPUT ERROR: "
                    f"{type(exc).__name__}: {exc}; reopening keypad only"
                )
                _bb36_live_owner_v3_log(
                    "PFD INPUT ERROR: "
                    f"{type(exc).__name__}: {exc}; keypad-only recovery"
                )

                # Never close self.device here.  The log proves the dedicated
                # keypad handle is what dies after ~10-15 minutes; closing the
                # F0 output handle in response was what turned an input fault
                # into a full BB36 display restart/freeze.
                if reader is not self.device:
                    try:
                        reader.close()
                    except Exception:
                        pass

                self.stop_evt.wait(BB36_INPUT_REOPEN_DELAY_SECONDS)
                reader = self._open_replacement_input_handle()
                if reader is None:
                    return
                previous = None
                continue

            now = time.monotonic()
            self.key_heartbeat_monotonic = now
            if now >= next_status_publish:
                with self.status_lock:
                    self.status["key_heartbeat_monotonic"] = now
                    self.status["key_reports"] = self.key_report_count
                    self.status["input_recovering"] = False
                next_status_publish = now + 0.50

            if not report:
                self.stop_evt.wait(0.001)
                continue

            self.key_report_count += 1
            bits = _button_bits(bytes(report))

            if bits is None:
                continue

            if previous is None:
                previous = bits
                continue

            changed = previous ^ bits
            for index in range(96):
                mask = 1 << index
                if not changed & mask:
                    continue

                edge = "press" if bits & mask else "release"

                # PERIOD and SLASH are permanent display-lifecycle contacts.
                # Hardware Lab/custom mappings must never consume them.
                if index == BB36_PERIOD_INDEX:
                    if edge == "press":
                        with self.display_page_lock:
                            on_fmc = self.display_page == BB36_GRAPHICAL_FMC_PAGE
                        if on_fmc:
                            # In graphical FMC mode, preserve normal single/
                            # double PERIOD behavior; the command worker delays
                            # them until the secret-tap window expires.
                            self.fmc_key_queue.put((edge, index))
                        else:
                            period_detector.press()
                        _bb36_live_owner_v3_log("KEY 41 PRESS PERIOD")
                    continue

                if index == BB36_DISPLAY_SLASH_INDEX:
                    if edge == "press":
                        slash_detector.press()
                        _bb36_live_owner_v3_log("KEY 70 PRESS SLASH")
                    continue

                consumed = False
                if self.input_router is not None:
                    try:
                        consumed = bool(self.input_router(index, edge))
                    except Exception:
                        consumed = False

                if consumed:
                    continue

                with self.display_page_lock:
                    on_fmc = self.display_page == BB36_GRAPHICAL_FMC_PAGE
                if on_fmc:
                    self.fmc_key_queue.put((edge, index))

            previous = bits

    def _graphical_fmc_command_worker(self) -> None:
        """Route FMC keys while the screen remains on the persistent F0 owner."""
        pending_periods = 0
        period_deadline = 0.0
        last_period = 0.0
        req_counter = [7000]

        def send(ws: Any, payload: Dict[str, Any]) -> None:
            ws.send(json.dumps(payload, separators=(",", ":")))

        def next_req() -> int:
            req_counter[0] += 1
            return req_counter[0]

        def command_phase(
            ws: Any,
            command_id: int,
            active: bool,
        ) -> None:
            send(
                ws,
                {
                    "req_id": next_req(),
                    "type": "command_set_is_active",
                    "params": {
                        "commands": [{
                            "id": int(command_id),
                            "is_active": bool(active),
                        }]
                    },
                },
            )

        while not self.stop_evt.is_set():
            if websocket is None:
                self.stop_evt.wait(1.0)
                continue

            if not self.simulator_connected.is_set():
                try:
                    while True:
                        self.fmc_key_queue.get_nowait()
                except queue.Empty:
                    pass
                self.stop_evt.wait(MCDU_WS_RECONNECT_SECONDS)
                continue

            ws = None
            try:
                commands: Dict[str, int] = {}
                for _label, action in MCDU_KEY_MAP.values():
                    if not action or action.startswith("__") or action in commands:
                        continue
                    try:
                        commands[action] = _resolve_command_id(
                            self.api_root,
                            self.api_version,
                            action,
                        )
                    except Exception:
                        pass

                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(MCDU_WS_RECV_TIMEOUT)

                while not self.stop_evt.is_set():
                    now = time.monotonic()

                    if pending_periods and now >= period_deadline:
                        action = MCDU_KEY_MAP[BB36_PERIOD_INDEX][1]
                        command_id = commands.get(action) if action else None
                        if command_id is not None:
                            for _ in range(pending_periods):
                                command_phase(ws, command_id, True)
                                command_phase(ws, command_id, False)
                        pending_periods = 0

                    processed = 0
                    while processed < 128:
                        try:
                            edge, index = self.fmc_key_queue.get_nowait()
                        except queue.Empty:
                            break
                        processed += 1
                        index = int(index)

                        with self.display_page_lock:
                            on_fmc = self.display_page == BB36_GRAPHICAL_FMC_PAGE
                        if not on_fmc:
                            pending_periods = 0
                            continue

                        if index == BB36_PERIOD_INDEX:
                            if edge != "press":
                                continue
                            current = time.monotonic()
                            if (
                                pending_periods
                                and current - last_period > BB36_SECRET_GAP
                            ):
                                action = MCDU_KEY_MAP[BB36_PERIOD_INDEX][1]
                                command_id = commands.get(action) if action else None
                                if command_id is not None:
                                    for _ in range(pending_periods):
                                        command_phase(ws, command_id, True)
                                        command_phase(ws, command_id, False)
                                pending_periods = 0

                            pending_periods += 1
                            last_period = current
                            period_deadline = current + BB36_SECRET_GAP
                            if pending_periods >= BB36_SECRET_TAPS:
                                pending_periods = 0
                                period_deadline = 0.0
                                self._toggle_graphical_fmc()
                            continue

                        if edge == "press" and pending_periods:
                            action = MCDU_KEY_MAP[BB36_PERIOD_INDEX][1]
                            command_id = commands.get(action) if action else None
                            if command_id is not None:
                                for _ in range(pending_periods):
                                    command_phase(ws, command_id, True)
                                    command_phase(ws, command_id, False)
                            pending_periods = 0
                            period_deadline = 0.0

                        mapping = MCDU_KEY_MAP.get(index)
                        if mapping is None:
                            continue
                        _label, action = mapping
                        if action is None or action.startswith("__"):
                            continue
                        command_id = commands.get(action)
                        if command_id is None:
                            continue
                        command_phase(
                            ws,
                            command_id,
                            edge == "press",
                        )

                    try:
                        ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

            except Exception as exc:
                if self.diagnose and not self.stop_evt.is_set():
                    print(
                        "BB36 graphical FMC command reconnect: "
                        f"{type(exc).__name__}: {exc}"
                    )
                self.stop_evt.wait(MCDU_WS_RECONNECT_SECONDS)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

    @staticmethod
    def _close_stale_output_for_recovery(device: Any) -> None:
        try:
            device.close()
        except Exception:
            pass

    def stop(
        self,
        *,
        final: bool = False,
        recovery: bool = False,
    ) -> bool:
        """Tear this path down and report whether the output worker quiesced.

        Normal shutdown/handoff keeps the historical sequence. A *verified*
        recovery stall is different: close the stale BB36 output handle first
        so a blocked native HID write can unwind before any replacement owner
        is opened.

        Returning ``False`` means the old daemon thread still exists. The
        router must not open another BB36 output owner until it is gone.
        """
        self.stop_evt.set()

        input_device = self.input_device
        output_device = self.device
        output_closed = False

        if recovery and output_device is not None:
            _bb36_live_owner_v3_log(
                "PFD RECOVERY RETIRE: closing stale output handle before joins"
            )
            self._close_stale_output_for_recovery(
                output_device
            )
            output_closed = True

        # A nonblocking keypad reader normally exits immediately. Close only
        # its dedicated input handle if the first bounded join does not return.
        if self.key_reader is not None:
            self.key_reader.join(timeout=0.75)
            if (
                self.key_reader.is_alive()
                and input_device is not None
                and input_device is not output_device
            ):
                try:
                    input_device.close()
                except Exception:
                    pass
                self.key_reader.join(timeout=0.75)

        if self.fmc_command_worker is not None:
            self.fmc_command_worker.join(timeout=1.25)

        worker_thread = self.worker
        if worker_thread is not None:
            worker_thread.join(timeout=1.50 if recovery else 2.50)

        worker_still_alive = bool(
            worker_thread is not None and worker_thread.is_alive()
        )

        # Normal teardown preserves the old "join, then close stale handle"
        # behavior. Recovery already closed first because health proved the
        # output path had stopped making progress.
        if worker_still_alive and not output_closed and output_device is not None:
            print(
                "BB36 PFD output did not stop within 2.5 s; "
                "closing the stale output handle for clean recovery."
            )
            _bb36_live_owner_v3_log(
                "PFD OUTPUT stalled during stop; closing stale handle"
            )

        elif worker_still_alive and recovery:
            worker_thread.join(timeout=1.00)
            worker_still_alive = worker_thread.is_alive()

        if worker_still_alive:
            self.retired_output_worker = worker_thread
            _bb36_live_owner_v3_log(
                "PFD RECOVERY RETIRE INCOMPLETE: output worker still alive "
                "after stale handle close"
            )
        else:
            self.retired_output_worker = None

        if (
            TRACE_HANDOFF
            and not worker_still_alive
            and isinstance(output_device, _TracingDevice)
        ):
            output_device.report("PFD leaving")

        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Only final manager shutdown darkens. Recovery/handoff never adds a
        # blackout flash. If recovery already closed the stale handle, no
        # further output is attempted through it.
        if final and output_device is not None:
            if (
                not recovery
                and not output_closed
                and not worker_still_alive
            ):
                try:
                    output_device.write(list(_black_background_packet()))
                    _set_brightness(
                        output_device,
                        BB36_EXEC_DASH_LIGHT_CHANNEL,
                        EXEC_LIGHT_OFF,
                    )
                    _set_brightness(output_device, 1, 0)
                    _set_brightness(output_device, 0, 0)
                except Exception:
                    pass
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

        if output_device is not None and not output_closed:
            try:
                output_device.close()
            except Exception:
                pass
            output_closed = True

        if worker_still_alive and worker_thread is not None:
            worker_thread.join(timeout=1.00)
            worker_still_alive = worker_thread.is_alive()
            if worker_still_alive:
                self.retired_output_worker = worker_thread
                _bb36_live_owner_v3_log(
                    "PFD RECOVERY RETIRE INCOMPLETE: output worker still alive "
                    "after stale handle close"
                )
            else:
                self.retired_output_worker = None

        # In shared-fallback mode the output close also releases a keypad read.
        if self.key_reader is not None and self.key_reader.is_alive():
            self.key_reader.join(timeout=1.00)
            if self.key_reader.is_alive():
                _bb36_live_owner_v3_log(
                    "PFD INPUT reader remained alive after handle close"
                )

        if input_device is not None and input_device is not output_device:
            try:
                input_device.close()
            except Exception:
                pass

        self.device = None
        self.input_device = None
        self.input_device_is_shared = False
        self.canvas = None
        self.worker = None
        self.key_reader = None
        self.fmc_command_worker = None

        return not worker_still_alive


class BB36FMCPath:
    """Fresh original BB36 MCDU/FMC session using its native F2 renderer."""

    def __init__(
        self,
        api_root: str,
        api_version: str,
        font_path: str,
        toggle_callback: Callable[[], None],
        refresh_interval: float = MCDU_DISPLAY_MIN_INTERVAL,
        brightness: int = 220,
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.api_version = api_version
        self.font_path = Path(font_path).expanduser().resolve()
        self.toggle_callback = toggle_callback
        self.refresh_interval = max(0.02, float(refresh_interval))
        self.brightness = max(0, min(255, int(brightness)))
        self.diagnose = diagnose
        self.input_router = input_router

        self.device = None
        self.stop_evt = threading.Event()
        self.key_queue: "queue.Queue[Tuple[str,int]]" = queue.Queue()

        self.fmc_state: Dict[str, str] = {}
        self.state_lock = threading.Lock()
        self.dirty = threading.Event()
        self.simulator_connected = threading.Event()
        self.simulator_connected.set()

        self.threads = []

    def set_simulator_connected(self, connected: bool) -> None:
        """Publish transport state without reopening or power-cycling BB36."""

        if connected:
            self.simulator_connected.set()
        else:
            self.simulator_connected.clear()
            # Never reveal a page from the previous simulator session after
            # recovery.  Fresh WebSocket values repopulate this cache.
            with self.state_lock:
                self.fmc_state.clear()
        self.dirty.set()

    def start(self) -> None:
        if websocket is None:
            raise RuntimeError("websocket-client unavailable")
        if not self.font_path.is_file():
            raise RuntimeError(
                f"BB36 FMC font missing: {self.font_path}"
            )

        self.stop_evt.clear()
        self.device = _open_bb36()

        if TRACE_HANDOFF:
            self.device = _TracingDevice(self.device, "BB36 FMC")

        # Native MCDU resource is already 0x32/0xBB. No PFP retargeting.
        packets = _read_font_packets(self.font_path)

        for packet in packets:
            self.device.write(list(packet))

        time.sleep(0.20)

        self.device.write(list(_black_background_packet()))
        self.device.write(list(_text_grid_packet()))

        # Start with an explicitly blank 24x14 page.
        blank_lines = tuple(
            " " * MCDU_COLUMNS
            for _ in range(MCDU_ROWS)
        )
        blank_colors = tuple(
            tuple(0x0042 for _ in range(MCDU_COLUMNS))
            for _ in range(MCDU_ROWS)
        )

        for packet in _page_packets(blank_lines, blank_colors):
            self.device.write(list(packet))

        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Start hidden/off.  The FMC display worker enables brightness only
        # while it has a connected, non-empty Zibo page.
        _set_brightness(self.device, 1, 0)
        _set_brightness(self.device, 0, 0)
        _set_brightness(
            self.device,
            BB36_EXEC_DASH_LIGHT_CHANNEL,
            EXEC_LIGHT_OFF,
        )
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

        keypad = threading.Thread(
            target=self._key_reader,
            name="BB36-FMC-KEYPAD",
            daemon=True,
        )
        ws_thread = threading.Thread(
            target=self._ws_worker,
            name="BB36-FMC-WS",
            daemon=True,
        )
        display = threading.Thread(
            target=self._display_worker,
            name="BB36-FMC-DISPLAY",
            daemon=True,
        )

        self.threads = [keypad, ws_thread, display]

        for thread in self.threads:
            thread.start()

        if TRACE_HANDOFF and isinstance(self.device, _TracingDevice):
            self.device.report("FMC entry")

        print(
            'BB36 PATH -> FMC '
            '(fresh original 0x32/F2 session; PERIOD x3 switches to PFD)'
        )

    def _key_reader(self) -> None:
        previous = None

        while not self.stop_evt.is_set():
            try:
                report = self.device.read(128)
            except Exception:
                return

            if not report:
                self.stop_evt.wait(0.001)
                continue

            bits = _button_bits(bytes(report))

            if bits is None:
                continue

            if previous is None:
                previous = bits
                continue

            changed = bits ^ previous

            if changed:
                for index in range(96):
                    mask = 1 << index

                    if changed & mask:
                        self.key_queue.put(
                            (
                                "press" if bits & mask else "release",
                                index,
                            )
                        )

            previous = bits

    @staticmethod
    def _send(ws: Any, payload: Dict[str, Any]) -> None:
        ws.send(json.dumps(payload, separators=(",", ":")))

    @staticmethod
    def _next_req(counter: list) -> int:
        counter[0] += 1
        return counter[0]

    def _resolve_ids(self):
        fmc_ids = {}

        for key, name in MCDU_FMC_DATAREFS.items():
            try:
                fmc_ids[key] = _resolve_dataref_id(
                    self.api_root,
                    self.api_version,
                    name,
                )
            except Exception:
                pass

        if "line00_l" not in fmc_ids or "entry" not in fmc_ids:
            raise RuntimeError(
                "required Zibo FMC1 display refs unavailable"
            )

        commands = {}

        names = sorted({
            action
            for _label, action in MCDU_KEY_MAP.values()
            if action and not action.startswith("__")
        })

        for name in names:
            try:
                commands[name] = _resolve_command_id(
                    self.api_root,
                    self.api_version,
                    name,
                )
            except Exception:
                pass

        try:
            brightness_id = _resolve_dataref_id(
                self.api_root,
                self.api_version,
                MCDU_BRIGHTNESS_DATAREF,
            )
        except Exception:
            brightness_id = None
        try:
            power_id = _resolve_dataref_id(
                self.api_root, self.api_version, BB36_POWER_DATAREF
            )
        except Exception:
            power_id = None
        exec_light_id = None
        for name in ZIBO_CAPTAIN_EXEC_LIGHT_DATAREFS:
            try:
                exec_light_id = _resolve_dataref_id(
                    self.api_root, self.api_version, name
                )
                break
            except Exception:
                pass

        return fmc_ids, commands, brightness_id, power_id, exec_light_id

    def _command_phase(
        self,
        ws: Any,
        req_counter: list,
        command_id: int,
        active: bool,
    ) -> None:
        self._send(
            ws,
            {
                "req_id": self._next_req(req_counter),
                "type": "command_set_is_active",
                "params": {
                    "commands": [{
                        "id": int(command_id),
                        "is_active": bool(active),
                    }]
                },
            },
        )

    def _pulse_periods(
        self,
        ws: Any,
        req_counter: list,
        commands: Dict[str, int],
        count: int,
    ) -> None:
        action = MCDU_KEY_MAP[BB36_PERIOD_INDEX][1]
        command_id = commands.get(action) if action else None

        if command_id is None:
            return

        for _ in range(max(0, int(count))):
            self._command_phase(
                ws,
                req_counter,
                command_id,
                True,
            )
            self._command_phase(
                ws,
                req_counter,
                command_id,
                False,
            )

    def _ws_worker(self) -> None:
        pending_periods = 0
        period_deadline = 0.0
        last_period = 0.0
        req_counter = [2000]
        brightness = self.brightness / 255.0
        exec_active = False
        last_exec_output: Optional[int] = None

        def apply_exec_output(powered: bool) -> None:
            nonlocal last_exec_output
            target = exec_light_output_value(
                exec_active,
                simulator_connected=self.simulator_connected.is_set(),
                display_powered=powered,
            )
            if target != last_exec_output and self.device is not None:
                _set_brightness(
                    self.device,
                    BB36_EXEC_DASH_LIGHT_CHANNEL,
                    target,
                )
                last_exec_output = target

        while not self.stop_evt.is_set():
            if not self.simulator_connected.is_set():
                # Never resolve/replay commands against a stopped simulator.
                # Drop old physical edges so they cannot fire after recovery.
                try:
                    while True:
                        self.key_queue.get_nowait()
                except queue.Empty:
                    pass
                exec_active = False
                apply_exec_output(False)
                self.stop_evt.wait(MCDU_WS_RECONNECT_SECONDS)
                continue

            ws = None
            powered = False

            try:
                # Resolve on every fresh transport. X-Plane may assign new
                # numeric IDs after a full process restart.
                resolved = tuple(self._resolve_ids())
                if len(resolved) == 5:
                    (
                        fmc_ids,
                        commands,
                        brightness_id,
                        power_id,
                        exec_light_id,
                    ) = resolved
                elif len(resolved) == 3:
                    fmc_ids, commands, brightness_id = resolved
                    power_id = None
                    exec_light_id = None
                else:
                    raise RuntimeError(
                        "BB36 FMC ID resolver returned "
                        f"{len(resolved)} values; expected 3 or 5"
                    )
                id_to_key = {
                    str(int(value)): key
                    for key, value in fmc_ids.items()
                }
                brightness_key = (
                    str(int(brightness_id))
                    if brightness_id is not None
                    else None
                )
                power_key = (
                    str(int(power_id))
                    if power_id is not None
                    else None
                )
                exec_light_key = (
                    str(int(exec_light_id))
                    if exec_light_id is not None
                    else None
                )
                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(MCDU_WS_RECV_TIMEOUT)

                subscriptions = [
                    {"id": int(ref_id)}
                    for ref_id in fmc_ids.values()
                ]

                if brightness_id is not None:
                    subscriptions.append({
                        "id": int(brightness_id),
                        "index": MCDU_BRIGHTNESS_INDEX,
                    })
                if power_id is not None:
                    subscriptions.append({"id": int(power_id)})
                if exec_light_id is not None:
                    subscriptions.append({"id": int(exec_light_id)})

                self._send(
                    ws,
                    {
                        "req_id": self._next_req(req_counter),
                        "type": "dataref_subscribe_values",
                        "params": {
                            "datarefs": subscriptions,
                        },
                    },
                )

                if power_id is None:
                    powered = True
                apply_exec_output(powered)

                while (
                    not self.stop_evt.is_set()
                    and self.simulator_connected.is_set()
                ):
                    now = time.monotonic()

                    # A single/double period still behaves normally as an FMC
                    # decimal point once the secret timeout expires.
                    if pending_periods and now >= period_deadline:
                        self._pulse_periods(
                            ws,
                            req_counter,
                            commands,
                            pending_periods,
                        )
                        pending_periods = 0

                    processed = 0

                    while processed < 128:
                        try:
                            edge, index = self.key_queue.get_nowait()
                        except queue.Empty:
                            break

                        processed += 1
                        index = int(index)

                        consumed = False
                        if self.input_router is not None:
                            try:
                                consumed = bool(self.input_router(index, edge))
                            except Exception:
                                consumed = False
                        if consumed:
                            continue

                        # Secret mode switch: physical PERIOD at index 41.
                        if index == BB36_PERIOD_INDEX:
                            if edge != "press":
                                continue

                            current = time.monotonic()

                            if (
                                pending_periods
                                and current - last_period > BB36_SECRET_GAP
                            ):
                                self._pulse_periods(
                                    ws,
                                    req_counter,
                                    commands,
                                    pending_periods,
                                )
                                pending_periods = 0

                            pending_periods += 1
                            last_period = current
                            period_deadline = current + BB36_SECRET_GAP

                            if pending_periods >= BB36_SECRET_TAPS:
                                pending_periods = 0
                                period_deadline = 0.0
                                self.toggle_callback()

                            continue

                        # Any other key ends an incomplete secret sequence.
                        if edge == "press" and pending_periods:
                            self._pulse_periods(
                                ws,
                                req_counter,
                                commands,
                                pending_periods,
                            )
                            pending_periods = 0
                            period_deadline = 0.0

                        mapping = MCDU_KEY_MAP.get(index)

                        if mapping is None:
                            continue

                        label, action = mapping

                        if action is None:
                            continue

                        if action in (
                            "__brightness_up__",
                            "__brightness_down__",
                        ):
                            if edge != "press":
                                continue

                            delta = (
                                0.1
                                if action == "__brightness_up__"
                                else -0.1
                            )

                            brightness = max(
                                0.0,
                                min(1.0, brightness + delta),
                            )

                            if brightness_id is not None:
                                self._send(
                                    ws,
                                    {
                                        "req_id": self._next_req(req_counter),
                                        "type": "dataref_set_values",
                                        "params": {
                                            "datarefs": [{
                                                "id": int(brightness_id),
                                                "index": MCDU_BRIGHTNESS_INDEX,
                                                "value": brightness,
                                            }]
                                        },
                                    },
                                )

                            _set_brightness(
                                self.device,
                                1,
                                round(brightness * 255),
                            )
                            continue

                        command_id = commands.get(action)

                        if command_id is None:
                            continue

                        self._command_phase(
                            ws,
                            req_counter,
                            command_id,
                            edge == "press",
                        )

                        if edge == "press" and self.diagnose:
                            print(
                                f"BB36 FMC key {index:02d} {label}"
                            )

                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

                    if not raw:
                        continue

                    message = json.loads(raw)

                    if message.get("type") != "dataref_update_values":
                        continue

                    updates = message.get("data", {})

                    if not isinstance(updates, dict):
                        continue

                    changed = False

                    with self.state_lock:
                        for raw_id, value in updates.items():
                            key = str(raw_id).strip()

                            if (
                                brightness_key is not None
                                and key == brightness_key
                            ):
                                brightness = max(
                                    0.0,
                                    min(
                                        1.0,
                                        _ws_scalar(value, brightness),
                                    ),
                                )
                                continue

                            if power_key is not None and key == power_key:
                                powered = _ws_scalar(value, 0.0) >= 0.5
                                apply_exec_output(powered)
                                continue

                            if (
                                exec_light_key is not None
                                and key == exec_light_key
                            ):
                                exec_active = exec_light_active(value)
                                apply_exec_output(powered)
                                continue

                            display_key = id_to_key.get(key)

                            if display_key is None:
                                continue

                            text = _ws_decode_text(value)

                            if self.fmc_state.get(display_key) != text:
                                self.fmc_state[display_key] = text
                                changed = True

                    if changed:
                        self.dirty.set()

            except Exception as exc:
                if self.diagnose and not self.stop_evt.is_set():
                    print(
                        f"BB36 FMC WebSocket reconnect: {exc}"
                    )

                self.stop_evt.wait(MCDU_WS_RECONNECT_SECONDS)

            finally:
                exec_active = False
                try:
                    apply_exec_output(False)
                except Exception:
                    pass
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

    def _display_worker(self) -> None:
        previous = None
        previous_connected: Optional[bool] = None
        previous_visible: Optional[bool] = None
        last_write = 0.0
        self.dirty.set()

        while not self.stop_evt.is_set():
            self.dirty.wait(0.10)

            connected = self.simulator_connected.is_set()
            connection_changed = connected != previous_connected
            if not self.dirty.is_set() and not connection_changed:
                continue

            self.dirty.clear()

            elapsed = time.monotonic() - last_write

            if elapsed < self.refresh_interval:
                self.stop_evt.wait(
                    self.refresh_interval - elapsed
                )

                if self.stop_evt.is_set():
                    return

            with self.state_lock:
                values = dict(self.fmc_state)

            if not connected:
                lines, colors = _standby_page(*BB36_STANDBY_SIM_STOPPED)
            else:
                lines, colors = _compose_zibo_page(values)

            # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
            # Standby/empty pages remain useful for the software mirror, but the
            # physical BB36 must be black/off unless a real connected Zibo FMC
            # page is present.
            visible = bool(
                connected
                and values
                and any(line.strip() for line in lines)
            )
            if connected and not any(line.strip() for line in lines):
                lines, colors = _standby_page(*(
                    BB36_STANDBY_SIM_STOPPED
                    if not values
                    else BB36_STANDBY_UNPOWERED
                ))
            # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

            state = (lines, colors)

            if visible != previous_visible:
                try:
                    _set_brightness(self.device, 0, 128 if visible else 0)
                    _set_brightness(self.device, 1, self.brightness if visible else 0)
                except Exception:
                    return
                previous_visible = visible

            if state == previous:
                previous_connected = connected
                continue

            try:
                for packet in _page_packets(lines, colors):
                    self.device.write(list(packet))

                previous = state
                previous_connected = connected
                last_write = time.monotonic()

                if self.diagnose:
                    print(
                        "BB36 FMC page -> "
                        + lines[0].strip()
                    )

            except Exception:
                return

    def stop(self, *, final: bool = False) -> None:
        # ``final`` is accepted so the router can stop either path the same
        # way.  This path already blanks and darkens on every teardown, which
        # the incoming session depends on, so it is deliberately unchanged.
        self.stop_evt.set()
        self.dirty.set()

        for thread in self.threads:
            thread.join(timeout=1.5)

        self.threads = []

        if self.device is not None:
            try:
                # FMC is still the sole owner here. Blank the entire F2 page
                # before the fresh native-F0 PFD session is opened.
                blank_lines = tuple(
                    " " * MCDU_COLUMNS
                    for _ in range(MCDU_ROWS)
                )
                blank_colors = tuple(
                    tuple(0x0042 for _ in range(MCDU_COLUMNS))
                    for _ in range(MCDU_ROWS)
                )

                for packet in _page_packets(
                    blank_lines,
                    blank_colors,
                ):
                    self.device.write(list(packet))

                # BB35 sends this after blanking its page; BB36 was not.
                self.device.write(list(_black_background_packet()))
                # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
                _set_brightness(
                    self.device,
                    BB36_EXEC_DASH_LIGHT_CHANNEL,
                    EXEC_LIGHT_OFF,
                )
                _set_brightness(self.device, 1, 0)
                _set_brightness(self.device, 0, 0)
                # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

                time.sleep(0.06)

            except Exception:
                pass

            try:
                self.device.close()
            except Exception:
                pass

            self.device = None


class MuslimSimBB36PathRouter:
    """Supervisor: exactly one fresh BB36 FMC or PFD path at a time."""

    def __init__(
        self,
        api_root: str,
        api_version: str,
        font_path: str,
        open_pfd: Callable[[], Tuple[Any, Any]],
        pfd_worker: Callable[..., None],
        pfd_ids: Dict[str, int],
        pfd_refresh: float,
        fmc_refresh: float = MCDU_DISPLAY_MIN_INTERVAL,
        # The PFP 3N hardcodes 'pfd' and has no option at all.  This keeps
        # the option, because the MCDU can usefully start on its FMC page,
        # but defaults to the same view the PFP comes up on.
        start_mode: str = "pfd",
        diagnose: bool = False,
        hard_reset: Optional[Callable[[], None]] = None,
        input_router: Optional[Callable[[int, str], bool]] = None,
        recovery_power_cycle: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.api_root = api_root
        self.api_version = api_version
        self.font_path = font_path
        self.open_pfd = open_pfd
        self.pfd_worker = pfd_worker
        self.pfd_ids = pfd_ids
        self.pfd_refresh = pfd_refresh
        self.fmc_refresh = fmc_refresh
        self.diagnose = diagnose
        # Hard resets the panel on every triple-PERIOD.  final.py owns that
        # sequence; this class only says when.
        self.hard_reset = hard_reset
        self.input_router = input_router
        # MUSLIMSIM_BB36_FIRMWARE_WEDGE_RECOVERY_V5
        # A BB36 firmware wedge survives closing/reopening HID handles and even
        # restarting Studio; the user's physical USB unplug/replug clears it.
        # This callback is therefore reserved for health-failure recovery only.
        # It is NEVER called by // or ... graphical page changes.
        self.recovery_power_cycle = recovery_power_cycle

        normalized = str(start_mode).strip().lower()

        if normalized not in ("fmc", "pfd"):
            normalized = "fmc"

        self.mode = normalized

        self.stop_evt = threading.Event()
        self.toggle_evt = threading.Event()
        self.supervisor = None
        self.active = None
        self.simulator_connected = True

    def set_simulator_connected(self, connected: bool) -> None:
        """Tell the current sole display owner whether X-Plane is alive."""

        self.simulator_connected = bool(connected)
        active = self.active
        if active is not None and hasattr(active, "set_simulator_connected"):
            active.set_simulator_connected(self.simulator_connected)

    def request_toggle(self) -> None:
        # Captures and the on-device investigation show that repeated F0/F2
        # mode handoffs progressively disable BB36 until a real USB power
        # cycle.  PERIOD keeps its normal FMC command/mapping; it is no longer
        # a hidden display-mode switch in production.
        print(
            'BB36 PERIOD x3 display handoff ignored: '
            'mixed F0/F2 sessions are unsafe on this firmware'
        )

    def start(self) -> None:
        if (
            self.supervisor is not None
            and self.supervisor.is_alive()
        ):
            return

        self.stop_evt.clear()
        # stop() uses this event to wake the supervisor.  Clear that internal
        # wake-up before a later device/profile start; otherwise the router
        # mistakes it for the pilot's PERIOD x3 request and flips PFD/FMC.
        self.toggle_evt.clear()

        self.supervisor = threading.Thread(
            target=self._run,
            name="BB36-PATH-ROUTER",
            daemon=True,
        )
        self.supervisor.start()

    def _make_path(self):
        if self.mode == "pfd":
            path = BB36PFDPath(
                self.open_pfd,
                self.pfd_worker,
                self.api_version,
                self.pfd_ids,
                self.pfd_refresh,
                self.request_toggle,
                self.diagnose,
                self.input_router,
            )
        else:
            path = BB36FMCPath(
                self.api_root,
                self.api_version,
                self.font_path,
                self.request_toggle,
                self.fmc_refresh,
                220,
                self.diagnose,
                self.input_router,
            )
        if hasattr(path, "set_simulator_connected"):
            path.set_simulator_connected(self.simulator_connected)
        return path

    def studio_snapshot(self) -> Dict[str, Any]:
        """Return the current physical-screen model without opening HID."""

        active = self.active
        snapshot: Dict[str, Any] = {"mode": self.mode, "state": "starting"}
        if active is None:
            return snapshot
        if isinstance(active, BB36FMCPath):
            with active.state_lock:
                values = dict(active.fmc_state)
            lines, _colors = _compose_zibo_page(values)
            if not self.simulator_connected:
                lines, _colors = _standby_page(*BB36_STANDBY_SIM_STOPPED)
            elif not any(line.strip() for line in lines):
                lines, _colors = _standby_page(*BB36_STANDBY_SIM_STOPPED)
            snapshot.update({
                "state": "fmc",
                "lines": list(lines),
                "standby": "SIM STOPPED" if not self.simulator_connected else "",
            })
            return snapshot
        if isinstance(active, BB36PFDPath):
            with active.status_lock:
                status = dict(active.status)
            snapshot.update({
                "state": "pfd",
                "page": active.get_display_page(),
                "pfd": status.get("mirror", {}),
                "live": bool(status.get("live")),
                "frames": int(status.get("frames", 0) or 0),
                "detail": str(status.get("error") or ""),
            })
        return snapshot

    def _run(self) -> None:
        while not self.stop_evt.is_set():
            try:
                self.active = self._make_path()
                self.active.start()

            except Exception as exc:
                self.active = None

                if not self.stop_evt.is_set():
                    print(
                        f"BB36 {self.mode.upper()} path start failed: "
                        f"{exc}; retrying"
                    )
                    self.stop_evt.wait(1.0)

                continue
            requested_toggle = False
            restart_dead_path = False
            while not self.stop_evt.is_set():
                if self.toggle_evt.wait(0.05):
                    requested_toggle = True
                    break
                worker = getattr(self.active, "worker", None)
                threads = list(getattr(self.active, "threads", ()) or ())
                healthy = (
                    bool(worker.is_alive())
                    if worker is not None
                    else (not threads or all(thread.is_alive() for thread in threads))
                )
                if not healthy:
                    restart_dead_path = True
                    print(
                        f"BB36 {self.mode.upper()} display worker stopped; "
                        "performing a clean same-mode restart."
                    )
                    break

            if self.stop_evt.is_set():
                break

            if requested_toggle:
                self.toggle_evt.clear()
            old_mode = self.mode

            # Complete teardown before the other path even exists.
            if self.active is not None:
                self.active.stop()
                self.active = None

            # Let Windows release the handle before another session claims it.
            self.stop_evt.wait(BB36_HANDOFF_SETTLE)

            if self.stop_evt.is_set():
                break

            # Hard reset only for the user's deliberate mode handoff.  A dead
            # worker gets the normal clean close/reopen lifecycle without a
            # second device reset or a visible reboot flash.
            if requested_toggle and not restart_dead_path and self.hard_reset is not None:
                try:
                    self.hard_reset()
                except Exception as exc:
                    print(f"WARNING: MCDU hard reset failed: {exc}")

            self.stop_evt.wait(BB36_HANDOFF_SETTLE)

            if self.stop_evt.is_set():
                break


            if requested_toggle and not restart_dead_path:
                self.mode = (
                    "pfd"
                    if old_mode == "fmc"
                    else "fmc"
                )

                print(
                    f"BB36 HANDOFF: "
                    f"{old_mode.upper()} -> {self.mode.upper()}"
                )

        if self.active is not None:
            self.active.stop()
            self.active = None

    def stop(self) -> None:
        self.stop_evt.set()
        self.toggle_evt.set()

        if self.supervisor is not None:
            self.supervisor.join(timeout=8.0)

        self.supervisor = None

# MUSLIMSIM_BB36_COMPLETE_LIFECYCLE_V2
# Keep the captured BB36 PFD/FMC protocol paths above intact.  This exported
# subclass adds only physical USB lifecycle, worker supervision, truthful
# Studio status, and the explicitly requested PERIOD x3 handoff.
BB36_USB_POLL_SECONDS = 0.15
BB36_USB_RECONNECT_SETTLE = 1.00
# MUSLIMSIM_BB36_RECOVERY_BACKOFF_V6
BB36_RECOVERY_BACKOFF_MAX_SECONDS = 30.0


def _bb36_present() -> bool:
    """Return physical Windows HID enumeration truth without opening BB36."""
    if hid is None:
        return False
    try:
        return bool(hid.enumerate(MCDU_VID, MCDU_PID))
    except Exception:
        return False


_MuslimSimBB36PathRouterLifecycleBase = MuslimSimBB36PathRouter


class MuslimSimBB36PathRouter(_MuslimSimBB36PathRouterLifecycleBase):
    """Current BB36 behavior plus truthful hotplug and same-mode recovery."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Deliberately forward the current constructor unchanged.  The removed
        # V1 adapter injected hide_f2, which this constructor does not accept.
        super().__init__(*args, **kwargs)
        self._usb_status_lock = threading.Lock()
        self._usb_status = "starting"
        self._usb_status_detail = ""
        self._health_failure_detail = ""
        # MUSLIMSIM_BB36_RECOVERY_BACKOFF_V6
        self._recovery_failure_count = 0
        self._recovery_failure_detail = ""

        # MUSLIMSIM_BB36_RECOVERY_V7
        # Keep recovery episodes stateful across short-lived reopened paths.
        self._unstable_path_count = 0
        self._open_failure_count = 0
        self._automatic_power_cycle_blocked = False
        self._automatic_power_cycle_block_reason = ""
        self._retired_path: Optional[BB36PFDPath] = None
        self._resume_display_page = "pfd"

    def _get_usb_status(self) -> Tuple[str, str]:
        with self._usb_status_lock:
            return self._usb_status, self._usb_status_detail

    def _set_usb_status(self, state: str, detail: str = "") -> bool:
        normalized = str(state or "starting").strip().lower()
        message = str(detail or "").strip()
        with self._usb_status_lock:
            changed = (
                normalized != self._usb_status
                or message != self._usb_status_detail
            )
            self._usb_status = normalized
            self._usb_status_detail = message
        return changed

    def request_toggle(self) -> None:
        # V4 safety contract: never ask the router for an F0/F2 teardown.
        # PERIOD x3 is handled inside BB36PFDPath as a graphical page toggle.
        active = self.active
        if isinstance(active, BB36PFDPath):
            active._toggle_graphical_fmc()
        else:
            print(
                "BB36 PERIOD x3 ignored outside persistent F0 owner; "
                "unsafe F0/F2 handoff is disabled"
            )

    def _make_path(self):
        """Always use one persistent F0 owner, including the graphical FMC."""
        path = BB36PFDPath(
            self.open_pfd,
            self.pfd_worker,
            self.api_version,
            self.pfd_ids,
            self.pfd_refresh,
            self.request_toggle,
            self.diagnose,
            self.input_router,
            api_root=self.api_root,
        )
        requested_page = str(
            getattr(self, "_resume_display_page", "pfd") or "pfd"
        ).strip().lower()
        if str(self.mode).strip().lower() == "fmc":
            requested_page = BB36_GRAPHICAL_FMC_PAGE
        if requested_page in set(BB36_DISPLAY_PAGE_ORDER) | {
            BB36_GRAPHICAL_FMC_PAGE
        }:
            with path.display_page_lock:
                path.display_page = requested_page
        path.set_simulator_connected(self.simulator_connected)
        # The router mode now describes the transport owner: always F0/PFD.
        self.mode = "pfd"
        return path

    def _record_health(self, record: bool, detail: str) -> None:
        """Publish a health verdict only for the supervisor's own check.

        MUSLIMSIM_BB36_READ_ONLY_HEALTH_V6: ``live_snapshot`` runs this same
        predicate on every Studio status poll, from an HTTP request thread.
        Letting those polls write ``_health_failure_detail`` raced the
        supervisor into printing the wrong recovery reason, and letting them
        log wrote "PFD HEALTH FAILURE" lines attributed to
        ``process_request_thread``.  Only the supervisor records now.
        """
        if not record:
            return
        self._health_failure_detail = detail

    def _active_is_healthy(self, *, record: bool = True) -> bool:
        active = self.active
        if active is None or not _bb36_present():
            self._record_health(record, "BB36 physical device/path is absent")
            return False

        device = getattr(active, "device", None)
        if device is None:
            self._record_health(record, "BB36 active output handle is absent")
            return False

        if isinstance(active, BB36PFDPath):
            worker = getattr(active, "worker", None)
            key_reader = getattr(active, "key_reader", None)
            if worker is None or not worker.is_alive():
                self._record_health(record, "BB36 PFD output worker stopped")
                return False
            if key_reader is None or not key_reader.is_alive():
                self._record_health(record, "BB36 PFD keypad reader stopped")
                return False

            now = time.monotonic()
            started = float(getattr(active, "started_monotonic", 0.0) or 0.0)
            if started <= 0.0 or now - started < BB36_PFD_STARTUP_GRACE_SECONDS:
                self._record_health(record, "")
                return True

            try:
                with active.status_lock:
                    status = dict(active.status)
            except Exception:
                status = {}

            output_heartbeat = float(
                status.get("heartbeat_monotonic", 0.0) or 0.0
            )
            output_progress = float(
                status.get("output_progress_monotonic", 0.0) or 0.0
            )
            key_heartbeat = float(
                getattr(active, "key_heartbeat_monotonic", 0.0) or 0.0
            )
            input_recovering = bool(status.get("input_recovering", False))

            # V7 health follows the newest real sign of output progress. A
            # long frame that is still successfully delivering F0 fragments
            # must not be torn down merely because frame-complete is delayed.
            output_latest = max(output_heartbeat, output_progress)
            output_age = (
                now - output_latest
                if output_latest > 0.0
                else float("inf")
            )
            key_age = (
                now - key_heartbeat
                if key_heartbeat > 0.0
                else float("inf")
            )

            stale = []
            if output_age > BB36_PFD_PROGRESS_TIMEOUT_SECONDS:
                stale.append(f"output progress stale {output_age:.1f}s")
            if (
                not input_recovering
                and key_age > BB36_PFD_PROGRESS_TIMEOUT_SECONDS
            ):
                stale.append(f"keypad heartbeat stale {key_age:.1f}s")

            if stale:
                stale_detail = "BB36 PFD " + "; ".join(stale)
                self._record_health(record, stale_detail)
                if record:
                    _bb36_live_owner_v3_log(
                        "PFD HEALTH FAILURE: " + stale_detail
                    )
                return False

            self._record_health(record, "")
            # MUSLIMSIM_BB36_RECOVERY_V7
            # Do not forget an unstable episode after one healthy check.
            # Repeated 8-second wedges previously reset to "attempt 1" forever.
            # Only sustained output for the full stability window clears the
            # circuit/backoff state.
            if (
                record
                and started > 0.0
                and now - started >= BB36_RECOVERY_STABILITY_SECONDS
                and (
                    self._unstable_path_count
                    or self._recovery_failure_count
                    or self._automatic_power_cycle_blocked
                )
            ):
                _bb36_live_owner_v3_log(
                    "RECOVERY STABLE: BB36 remained healthy for "
                    f"{BB36_RECOVERY_STABILITY_SECONDS:.0f}s; "
                    "clearing recovery circuit"
                )
                self._unstable_path_count = 0
                self._recovery_failure_count = 0
                self._recovery_failure_detail = ""
                self._automatic_power_cycle_blocked = False
                self._automatic_power_cycle_block_reason = ""
            return True

        if isinstance(active, BB36FMCPath):
            threads = list(getattr(active, "threads", ()) or ())
            healthy = bool(threads and all(thread.is_alive() for thread in threads))
            self._record_health(
                record,
                "" if healthy else "BB36 FMC worker stopped",
            )
            return healthy

        self._record_health(record, "Unknown BB36 active path type")
        return False

    def _recovery_attempt_is_loggable(self) -> bool:
        """True for the first few recovery attempts, then one in twenty."""
        attempt = int(getattr(self, "_recovery_failure_count", 0) or 0) + 1
        return attempt <= 3 or attempt % 20 == 0

    def _recovery_backoff_seconds(self) -> float:
        """Slow the retry down once recovery has proved it cannot succeed.

        MUSLIMSIM_BB36_RECOVERY_BACKOFF_V6: the fixed 1.50 s wait reopened the
        BB36 - font upload included - every twelve seconds for as long as
        Studio stayed running, against a panel that was never going to answer.
        The first retries keep their old speed, so a transient wedge is still
        cleared as quickly as before.
        """
        failures = int(getattr(self, "_recovery_failure_count", 0) or 0)
        if failures <= 0:
            return 1.50
        return min(
            BB36_RECOVERY_BACKOFF_MAX_SECONDS,
            1.50 * (2.0 ** min(failures, 5)),
        )

    def _attempt_firmware_power_cycle(self, detail: str) -> bool:
        """Power-cycle only BB36 after a verified live-owner wedge.

        The log and physical test prove that reopening HID is insufficient once
        the controller wedges: only a USB/PnP power cycle restores //, ... and
        the display.  This path is entered only after the existing heartbeat
        supervisor has already declared the active BB36 unhealthy.
        """
        if self._automatic_power_cycle_blocked:
            return False

        callback = getattr(self, "recovery_power_cycle", None)
        if callback is None:
            _bb36_live_owner_v3_log(
                "FIRMWARE RECOVERY unavailable: no BB36 power-cycle callback"
            )
            return False

        self._set_usb_status(
            "firmware-reset",
            "BB36 firmware stalled; cycling only mcdu32_bb36",
        )
        # MUSLIMSIM_BB36_RECOVERY_BACKOFF_V6
        # One overnight session wrote 2211 identical START/FAILED pairs while
        # the panel stayed frozen.  Keep the first few attempts verbatim, then
        # one in twenty, so the evidence survives without burying the log.
        verbose = self._recovery_attempt_is_loggable()
        if verbose:
            _bb36_live_owner_v3_log(
                "FIRMWARE RECOVERY START: "
                + str(detail or "BB36 health failure")
            )
            print(
                "BB36 firmware wedge detected; attempting automatic BB36-only "
                "USB/PnP power cycle."
            )

        try:
            result = callback()
            self._recovery_failure_detail = ""
            _bb36_live_owner_v3_log(
                "FIRMWARE RECOVERY COMMAND COMPLETE: " + repr(result)
            )
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self._recovery_failure_count += 1
            self._recovery_failure_detail = message
            if "administrator rights" in message.casefold():
                self._automatic_power_cycle_blocked = True
                self._automatic_power_cycle_block_reason = message
            if verbose:
                _bb36_live_owner_v3_log(
                    "FIRMWARE RECOVERY FAILED "
                    f"(attempt {self._recovery_failure_count}): {message}"
                )
                print(
                    "WARNING: automatic BB36 USB/PnP recovery failed: "
                    f"{message}"
                )
            if self._recovery_failure_count == 1:
                # The one recovery this panel actually responds to is a USB
                # power cycle, and pnputil refuses it outside an elevated
                # session.  Say so once, plainly, instead of retrying in
                # silence: a Studio restart cannot clear a wedged BB36.
                print(
                    "BB36 is stalled in its own firmware. Restarting Studio "
                    "will not clear it. Run Studio as Administrator so it can "
                    "power-cycle the MCDU32 itself, or unplug and replug the "
                    "panel."
                )
            self._set_usb_status(
                "firmware-stalled",
                "BB36 firmware stalled and automatic recovery is unavailable: "
                + message,
            )
            return False

        # The PnP cycle may take a moment to disappear and enumerate again.
        gone_seen = False
        deadline = time.monotonic() + 8.0
        while not self.stop_evt.is_set() and time.monotonic() < deadline:
            present = _bb36_present()
            if not present:
                gone_seen = True
            elif gone_seen:
                self.stop_evt.wait(0.80)
                _bb36_live_owner_v3_log(
                    "FIRMWARE RECOVERY SUCCESS: BB36 disappeared/re-enumerated"
                )
                print("BB36 automatic USB/PnP recovery succeeded.")
                return True
            self.stop_evt.wait(0.10)

        # Some Windows restart methods do not expose a visible enumerate gap.
        # Accept a present device after the command, but record that distinction.
        if not self.stop_evt.is_set() and _bb36_present():
            self.stop_evt.wait(0.80)
            _bb36_live_owner_v3_log(
                "FIRMWARE RECOVERY COMPLETE: BB36 present after restart command"
            )
            return True

        _bb36_live_owner_v3_log(
            "FIRMWARE RECOVERY FAILED: BB36 did not return before timeout"
        )
        return False

    def _retired_path_quiesced(
        self,
        *,
        wait_seconds: float = 0.0,
    ) -> bool:
        retired = self._retired_path
        if retired is None:
            return True
        try:
            quiet = bool(
                retired.retired_output_quiesced(
                    wait_seconds=wait_seconds
                )
            )
        except Exception:
            quiet = False
        if quiet:
            self._retired_path = None
        return quiet

    def _stop_active_path(
        self,
        *,
        final: bool = False,
        recovery: bool = False,
    ) -> bool:
        """Stop the sole active path and report whether its output is quiescent."""

        active = self.active
        self.active = None
        if active is None:
            return self._retired_path_quiesced(
                wait_seconds=0.0
            )

        try:
            if isinstance(active, BB36PFDPath):
                clean = bool(
                    active.stop(
                        final=final,
                        recovery=recovery,
                    )
                )
            else:
                active.stop(final=final)
                clean = True
        except Exception as exc:
            clean = False
            if self.diagnose:
                print(f"BB36 active-path stop warning: {exc}")

        if recovery and isinstance(active, BB36PFDPath) and not clean:
            # Keep a reference to the retired object only so the supervisor can
            # prove the old daemon thread is gone before opening a replacement.
            self._retired_path = active
        elif self._retired_path is active:
            self._retired_path = None

        return bool(
            clean
            and self._retired_path_quiesced(
                wait_seconds=0.0
            )
        )


    def live_snapshot(self) -> Dict[str, Any]:
        """Physical USB truth plus the currently active BB36 display stream."""
        present = _bb36_present()
        state, detail = self._get_usb_status()
        mode = str(getattr(self, "mode", "pfd")).strip().lower() or "pfd"
        active = self.active
        # MUSLIMSIM_BB36_READ_ONLY_HEALTH_V6: this runs on Studio's HTTP status
        # threads, so it must observe health without recording or logging it.
        healthy = bool(present and self._active_is_healthy(record=False))

        snapshot: Dict[str, Any] = {
            "state": "disconnected" if not present else state,
            "mode": mode,
            "connected": healthy,
            "usb_connected": present,
            "live": healthy,
            "detail": detail,
            "values": {},
        }

        if not present or active is None:
            return snapshot

        if isinstance(active, BB36PFDPath):
            try:
                with active.status_lock:
                    display_status = dict(active.status)
            except Exception:
                display_status = {}

            raw_pfd = display_status.get("mirror", {})
            pfd = dict(raw_pfd) if isinstance(raw_pfd, dict) else {}
            values = display_status.get("values", {})
            if not isinstance(values, dict):
                values = {}
            if not values and isinstance(pfd.get("values"), dict):
                values = dict(pfd.get("values") or {})

            page = str(active.get_display_page() or "pfd")
            pfd.setdefault("page", page)
            pfd["values"] = dict(values)
            visible_mode = "fmc" if page == BB36_GRAPHICAL_FMC_PAGE else "pfd"

            snapshot.update({
                "state": visible_mode if healthy else state,
                "mode": visible_mode,
                "page": page,
                "pfd": pfd,
                "values": dict(values),
                "live": bool(display_status.get("live")) and healthy,
                "connected": healthy,
                "frames": int(display_status.get("frames", 0) or 0),
                "status": display_status,
                "detail": str(
                    display_status.get("error") or detail or ""
                ),
            })
            return snapshot

        if isinstance(active, BB36FMCPath):
            try:
                with active.state_lock:
                    values = dict(active.fmc_state)
            except Exception:
                values = {}

            try:
                lines, _colors = _compose_zibo_page(values)
            except Exception:
                lines = tuple()

            snapshot.update({
                "state": "fmc" if healthy else state,
                "lines": list(lines),
                "values": values,
                "live": healthy,
                "connected": healthy,
            })

        return snapshot

    def service_snapshot(self) -> Dict[str, Any]:
        """One authoritative status object for the private hardware service."""
        snapshot = self.live_snapshot()

        if not snapshot.get("usb_connected", False):
            snapshot["state"] = "disconnected"
            snapshot["connected"] = False
            snapshot["live"] = False
            snapshot["values"] = {}
            snapshot["mirror"] = {
                "state": "offline",
                "lines": [],
            }
            return snapshot

        try:
            mirror = super().studio_snapshot()
        except Exception as exc:
            mirror = {}
            snapshot["detail"] = (
                f"{snapshot.get('detail') or ''} "
                f"Studio mirror error: {exc}"
            ).strip()

        snapshot["mirror"] = (
            dict(mirror) if isinstance(mirror, dict) else {}
        )
        return snapshot

    def start(self) -> None:
        if self.supervisor is not None and self.supervisor.is_alive():
            return
        self.stop_evt.clear()
        self.toggle_evt.clear()
        self._set_usb_status("starting", "BB36 lifecycle supervisor starting")
        self.supervisor = threading.Thread(
            target=self._run,
            name="BB36-PATH-ROUTER",
            daemon=True,
        )
        self.supervisor.start()

    def _run(self) -> None:
        while not self.stop_evt.is_set():
            if not _bb36_present():
                changed = self._set_usb_status(
                    "waiting-for-bb36",
                    "WINCTRL 32 MCDU CAPTAIN BB36 is disconnected",
                )
                self._stop_active_path()
                self._retired_path_quiesced(wait_seconds=0.10)
                # A real unplug/replug is a physical firmware reset, so a new
                # enumeration begins a fresh recovery episode.
                self._unstable_path_count = 0
                self._recovery_failure_count = 0
                self._recovery_failure_detail = ""
                self._automatic_power_cycle_blocked = False
                self._automatic_power_cycle_block_reason = ""
                self._open_failure_count = 0
                if changed:
                    print("BB36 USB disconnected; waiting for 4098:BB36.")
                self.stop_evt.wait(BB36_USB_POLL_SECONDS)
                continue

            # Never open a second output owner while an old daemon is still
            # unwinding from a verified stalled HID write.
            if not self._retired_path_quiesced(wait_seconds=0.0):
                self._set_usb_status(
                    "firmware-stalled",
                    "Previous BB36 output worker is still retiring; "
                    "replacement owner is blocked",
                )
                self.stop_evt.wait(BB36_USB_POLL_SECONDS)
                continue

            previous_state, _previous_detail = self._get_usb_status()
            if previous_state in {
                "waiting-for-bb36",
                "disconnected",
                "offline",
            }:
                print("BB36 USB reconnected; reopening the same display mode.")
                self._set_usb_status(
                    "reconnecting",
                    f"Reopening BB36 {str(self.mode).upper()} path",
                )
                self.stop_evt.wait(BB36_USB_RECONNECT_SETTLE)
                if self.stop_evt.is_set():
                    break

            try:
                self._set_usb_status(
                    "connecting",
                    f"Opening BB36 {str(self.mode).upper()} path",
                )
                self.active = self._make_path()
                self.active.start()
                self._set_usb_status(
                    "connected",
                    f"BB36 {str(self.mode).upper()} path live",
                )
                print(f"BB36 {str(self.mode).upper()} path connected.")
            except Exception as exc:
                self._stop_active_path()
                if not self.stop_evt.is_set():
                    self._open_failure_count += 1
                    delay = min(
                        30.0,
                        1.0 * (
                            2.0 ** min(
                                self._open_failure_count - 1,
                                5,
                            )
                        ),
                    )
                    self._set_usb_status(
                        "reconnecting" if _bb36_present() else "waiting-for-bb36",
                        f"{type(exc).__name__}: {exc}",
                    )
                    print(
                        f"BB36 {str(self.mode).upper()} path start failed: "
                        f"{exc}; retry in {delay:.1f}s"
                    )
                    self.stop_evt.wait(delay)
                continue

            self._open_failure_count = 0

            reason = ""
            while not self.stop_evt.is_set():
                if self.toggle_evt.wait(BB36_USB_POLL_SECONDS):
                    reason = "toggle"
                    break
                if not _bb36_present():
                    reason = "usb-disconnected"
                    break
                if not self._active_is_healthy():
                    reason = "path-failed"
                    break

            if self.stop_evt.is_set():
                break

            if reason in {"usb-disconnected", "path-failed"}:
                if reason == "usb-disconnected":
                    self._set_usb_status(
                        "waiting-for-bb36",
                        "WINCTRL 32 MCDU CAPTAIN BB36 is disconnected",
                    )
                    print("BB36 USB disconnected; live path released.")
                    self._stop_active_path()
                    self.stop_evt.wait(BB36_USB_RECONNECT_SETTLE)
                    continue

                _health_detail = str(
                    getattr(self, "_health_failure_detail", "")
                    or f"BB36 {str(self.mode).upper()} worker stopped"
                )
                self._set_usb_status("reconnecting", _health_detail)
                print(
                    f"BB36 {str(self.mode).upper()} path unhealthy: "
                    f"{_health_detail}"
                )

                # MUSLIMSIM_BB36_RECOVERY_V7
                #
                # Retire the sole owner FIRST. A blocked F0 write holds a HID
                # handle; attempting PnP restart while that stale owner is
                # still live is the wrong order. Capture the graphical page so
                # same-mode recovery does not throw the user back to PFD.
                active = self.active
                if isinstance(active, BB36PFDPath):
                    try:
                        self._resume_display_page = (
                            active.get_display_page()
                        )
                    except Exception:
                        pass

                self._unstable_path_count += 1
                retired_clean = self._stop_active_path(
                    recovery=True
                )

                if (
                    retired_clean
                    and self._unstable_path_count
                    <= BB36_RECOVERY_SOFT_RESTART_LIMIT
                ):
                    # One bounded close/reopen is enough for a transient HID
                    # handle failure. Do not power-cycle healthy firmware on
                    # the first event.
                    self._set_usb_status(
                        "reconnecting",
                        "BB36 stale handle retired cleanly; "
                        "performing one same-page soft reopen",
                    )
                    _bb36_live_owner_v3_log(
                        "RECOVERY SOFT REOPEN: first unstable path; "
                        f"resume={self._resume_display_page}"
                    )
                    self.stop_evt.wait(1.50)
                    continue

                recovered = False
                if not self._automatic_power_cycle_blocked:
                    recovered = self._attempt_firmware_power_cycle(
                        _health_detail
                    )

                # A successful USB/PnP cycle should release a blocked daemon.
                # Prove that before a new output owner can exist.
                if recovered:
                    retired_clean = self._retired_path_quiesced(
                        wait_seconds=BB36_RECOVERY_RETIRED_JOIN_SECONDS
                    )
                    if retired_clean:
                        self._set_usb_status(
                            "reconnecting",
                            "BB36 firmware recovery completed; reopening "
                            f"{self._resume_display_page.upper()}",
                        )
                        self.stop_evt.wait(BB36_USB_RECONNECT_SETTLE)
                        continue

                block_reason = str(
                    self._automatic_power_cycle_block_reason
                    or self._recovery_failure_detail
                    or (
                        "previous output worker is still alive"
                        if not retired_clean
                        else "firmware recovery unavailable"
                    )
                )
                self._set_usb_status(
                    "firmware-stalled",
                    "BB36 recovery circuit open: " + block_reason,
                )
                _bb36_live_owner_v3_log(
                    "RECOVERY CIRCUIT OPEN: "
                    f"unstable_paths={self._unstable_path_count}; "
                    f"retired_clean={retired_clean}; "
                    f"reason={block_reason}; "
                    f"probe_in={BB36_RECOVERY_CIRCUIT_OPEN_SECONDS:.0f}s"
                )
                # Do not thrash HID/USB every few seconds. After the cooldown,
                # one soft probe is permitted only if the retired owner is gone.
                self.stop_evt.wait(BB36_RECOVERY_CIRCUIT_OPEN_SECONDS)
                continue

            # PERIOD x3 remains the only deliberate mode transition.
            self.toggle_evt.clear()
            old_mode = str(self.mode)
            self._set_usb_status(
                "handoff",
                f"{old_mode.upper()} path closing",
            )
            self._stop_active_path()

            self.stop_evt.wait(BB36_HANDOFF_SETTLE)
            if self.stop_evt.is_set():
                break

            if self.hard_reset is not None:
                try:
                    self.hard_reset()
                except Exception as exc:
                    print(f"WARNING: MCDU hard reset failed: {exc}")

            self.stop_evt.wait(BB36_HANDOFF_SETTLE)
            if self.stop_evt.is_set():
                break

            self.mode = "fmc" if old_mode == "pfd" else "pfd"
            print(
                f"BB36 HANDOFF: {old_mode.upper()} -> "
                f"{str(self.mode).upper()}"
            )

        # The supervisor loop has ended, so this is the shutdown teardown
        # rather than a handoff.  This is the one call that darkens.
        self._stop_active_path(final=True)
        self._set_usb_status("stopped", "BB36 lifecycle supervisor stopped")

    def stop(self) -> None:
        self._set_usb_status("stopping", "BB36 lifecycle supervisor stopping")
        self.stop_evt.set()
        self.toggle_evt.set()
        if self.supervisor is not None:
            self.supervisor.join(timeout=8.0)
        self.supervisor = None

        # A previously retired daemon owns no open HID handle, but keep the
        # shutdown bounded and truthful about whether it actually left.
        if not self._retired_path_quiesced(wait_seconds=1.0):
            _bb36_live_owner_v3_log(
                "PFD RETIRED WORKER still alive at router shutdown"
            )


def run_self_test() -> None:
    if (MCDU_VID, MCDU_PID) != (0x4098, 0xBB36):
        raise AssertionError("BB36 VID/PID changed")

    if BB36_PERIOD_INDEX != 41:
        raise AssertionError(
            "BB36 HARDWARE_MCDU PERIOD must remain hardware index 41"
        )

    if BB36_SECRET_TAPS != 3:
        raise AssertionError(
            "BB36 mode switching must require exactly three PERIOD presses"
        )

    if BB36_DISPLAY_SLASH_INDEX != 70 or BB36_DISPLAY_SLASH_TAPS != 2:
        raise AssertionError(
            "BB36 display-page switch must be SLASH hardware index 70 x2"
        )

    if (
        MCDU_KEY_MAP[BB36_PERIOD_INDEX][1]
        != "laminar/B738/button/fmc1_period"
    ):
        raise AssertionError("BB36 PERIOD command mapping invalid")

    if (
        MCDU_KEY_MAP[0][1]
        != "laminar/B738/button/fmc1_1L"
    ):
        raise AssertionError("BB36 LSK1L mapping invalid")

    if (
        MCDU_KEY_MAP[73][1]
        != "laminar/B738/button/fmc1_clr"
    ):
        raise AssertionError("BB36 CLR mapping invalid")
    if BB36_EXEC_DASH_LIGHT_CHANNEL != 15:
        raise AssertionError("BB36 EXEC dash must remain channel 15")
    if not exec_light_active({"value": 1}) or exec_light_active(None):
        raise AssertionError("BB36 EXEC dash indication must remain discrete")
    if (
        exec_light_output_value(
            1.0, simulator_connected=False, display_powered=True
        ) != EXEC_LIGHT_OFF
        or exec_light_output_value(
            1.0, simulator_connected=True, display_powered=False
        ) != EXEC_LIGHT_OFF
        or exec_light_output_value(
            1.0, simulator_connected=True, display_powered=True
        ) != EXEC_LIGHT_ON
    ):
        raise AssertionError("BB36 EXEC alert escaped Live output authority")

    class _ExecPacketDevice:
        def __init__(self) -> None:
            self.writes = []

        def write(self, report: Any) -> int:
            packet = bytes(report)
            self.writes.append(packet)
            return len(packet)

    exec_device = _ExecPacketDevice()
    _set_brightness(
        exec_device,
        BB36_EXEC_DASH_LIGHT_CHANNEL,
        EXEC_LIGHT_ON,
    )
    if (
        len(exec_device.writes) != 1
        or exec_device.writes[0][1] != MCDU_IDENTIFIER
        or exec_device.writes[0][6:9]
        != bytes((0x49, BB36_EXEC_DASH_LIGHT_CHANNEL, EXEC_LIGHT_ON))
    ):
        raise AssertionError("BB36 EXEC dash packet is invalid")

    callbacks = []
    detector = _TriplePeriodDetector(
        lambda: callbacks.append("toggle")
    )

    if detector.press():
        raise AssertionError("first PERIOD toggled BB36 too early")

    if detector.press():
        raise AssertionError("second PERIOD toggled BB36 too early")

    if not detector.press():
        raise AssertionError("third PERIOD did not toggle BB36")

    if callbacks != ["toggle"]:
        raise AssertionError("BB36 triple-PERIOD callback count invalid")

    lines, colors = _compose_zibo_page({
        "line00_l": "MENU",
        "entry": "ABC",
    })

    packets = _page_packets(lines, colors)

    if (
        len(packets) != 16
        or any(len(packet) != 64 for packet in packets)
    ):
        raise AssertionError("BB36 FMC page packet geometry invalid")

    hidden_grid = _bb36_hide_f2_grid_packet()
    if len(hidden_grid) != 64 or hidden_grid[:4] != bytes((0xF0, 0, 0, 0x2A)):
        raise AssertionError("BB36 live-plane grid handoff packet invalid")
    if hidden_grid[21:25] != bytes((0xFF, 0x07, 0xFF, 0x07)):
        raise AssertionError("BB36 F2 grid is not moved outside the LCD")

    pfd_path = BB36PFDPath(
        lambda: (None, None), lambda *args: None, "v3", {}, 0.10,
        lambda: None,
    )
    pfd_path.set_simulator_connected(True)
    if pfd_path.get_display_page() != "pfd":
        raise AssertionError("BB36 reconnect changed its persistent F0 page")

    stable_router = MuslimSimBB36PathRouter(
        "http://127.0.0.1:8086", "v3", ".",
        lambda: (None, None), lambda *args: None, {}, 0.10,
    )
    stable_router.request_toggle()
    if stable_router.toggle_evt.is_set() or stable_router.mode != "pfd":
        raise AssertionError("BB36 PERIOD must not request an unsafe F0/F2 handoff")

    restart_router = MuslimSimBB36PathRouter(
        "http://127.0.0.1:8086", "v3", ".",
        lambda: (None, None), lambda *args: None, {}, 0.10,
    )
    restart_router.toggle_evt.set()
    restart_router._run = lambda: None
    restart_router.start()
    restart_router.supervisor.join(timeout=1.0)
    if restart_router.toggle_evt.is_set() or restart_router.mode != "pfd":
        raise AssertionError("BB36 device restart must preserve PFD mode")

    offline_path = BB36FMCPath(
        "http://127.0.0.1:8086", "v3", ".", lambda: None
    )
    offline_path.fmc_state["line00_l"] = "STALE"
    offline_path.set_simulator_connected(False)
    if offline_path.simulator_connected.is_set() or offline_path.fmc_state:
        raise AssertionError("BB36 disconnect must clear its stale FMC cache")
