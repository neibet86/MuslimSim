"""Mirror what the cockpit displays are showing, and really restart them.

Two things the control panel needs from the PFP and the MCDU:

**A picture of what is on the glass.**  Not a diagram of what should be there
-- the actual frame, drawn by the same renderer the bridge draws with, from
the same values the bridge drew from.  `bridge/final.py` reports those values
over the control channel (see `muslimsim_display_telemetry`), and this module
runs them back through `muslimsim/devices/pfp_renderer.py` onto an image.
Anything wrong on the panel is therefore wrong here too, which is the whole
point: a mirror that quietly looks better than the hardware would be worse
than no mirror.

**A restart that is really a restart.**  Blanking a panel and redrawing it is
not a reboot; the controller never restarts and whatever state wedged it is
still there.  A reboot is a USB re-enumeration -- the device drops off the
bus, its firmware starts again, and it shows the WinCtrl logo on the way up,
exactly as it does when the cable is pulled.  That is what `reboot` does, and
it is why the application asks for Administrator: Windows will not
re-enumerate a device without it.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from . import usb
from .catalog import DeviceSpec, get as get_device

PROJECT = Path(__file__).resolve().parents[2]

WIDTH = 640
HEIGHT = 480
BACKGROUND = (6, 7, 13)

#: The label the bridge reports for each panel in its telemetry.
PANEL_LABELS = {
    "pfp": ("BB35", "PFP"),
    "mcdu": ("BB36", "MCDU"),
}

PAGES = ("pfd", "nd", "eng_pri", "mfd")


# --------------------------------------------------------------------------
# Lazy imports
# --------------------------------------------------------------------------

_lock = threading.Lock()
_frame_factory: Optional[Callable[[], Any]] = None
_fitted_canvas: Optional[type] = None
_renderers: Dict[str, Optional[Callable]] = {}
_import_error: Optional[str] = None
#: The last render failure, so the panel can say why the mirror is blank
#: instead of showing an empty box and leaving you to guess.
_render_error: Optional[str] = None


def _load() -> None:
    """Import the renderer and the MCDU viewport, once, on first use.

    The renderer package is pure and cheap.  `bridge/final.py` is neither, so
    it is imported only for the MCDU's viewport wrapper -- reimplementing that
    geometry here would let the mirror drift away from the panel the first
    time someone tuned one and not the other.
    """
    global _frame_factory, _fitted_canvas, _import_error

    if _frame_factory is not None or _import_error is not None:
        return

    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))

    try:
        from PIL import Image, ImageDraw  # noqa: F401

        from muslimsim.devices import pfp_renderer

        _renderers["pfd"] = getattr(pfp_renderer, "draw_live_pfd", None)

        try:
            from muslimsim.devices import nd_renderer

            _renderers["nd"] = getattr(nd_renderer, "draw_live_nd", None)
        except Exception:
            _renderers["nd"] = None

        # The offline frame emulator lives with the tools; it accepts the same
        # command set as the real canvas and paints onto a PIL image.
        tool = PROJECT / "tools" / "render_pfp_frame_png.py"
        spec = importlib.util.spec_from_file_location("_ms_frame", tool)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        base = getattr(module, "PfpFrame")

        class _MirrorFrame(base):
            """A frame that draws to an image and writes to no hardware.

            `identifier` matters: the MCDU's viewport wrapper reads it from
            the canvas it wraps, and a frame without one cannot be fitted.
            """

            device = None
            identifier = 0x31

            def command(self, code: int, data: bytes = b"") -> None:
                return None

        _frame_factory = _MirrorFrame

    except Exception as exc:
        _import_error = f"the display renderer could not be loaded: {exc}"
        return

    # The MCDU squeezes the PFD into its shorter bezel.  Optional: without it
    # the MCDU mirror simply shows the unfitted picture.
    try:
        spec = importlib.util.spec_from_file_location(
            "_ms_bridge_geometry", PROJECT / "bridge" / "final.py"
        )
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        _fitted_canvas = getattr(bridge, "_McduPfdFittedCanvas", None)
    except Exception:
        _fitted_canvas = None


def import_error() -> Optional[str]:
    _load()
    return _import_error


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@dataclass
class PanelTelemetry:
    """One panel's current frame, as the bridge reported it."""

    label: str = ""
    page: str = "pfd"
    values: Dict[str, float] = None
    standby: Optional[str] = None
    source: str = ""
    stamp: float = 0.0

    def __post_init__(self) -> None:
        if self.values is None:
            self.values = {}

    @classmethod
    def from_payload(cls, label: str, payload: Mapping[str, Any]) -> "PanelTelemetry":
        values = payload.get("values")

        return cls(
            label=str(label),
            page=str(payload.get("page", "pfd")),
            values=dict(values) if isinstance(values, Mapping) else {},
            standby=payload.get("standby"),
            source=str(payload.get("source", "")),
            stamp=float(payload.get("stamp", 0.0) or 0.0),
        )


def telemetry_for(panels: Mapping[str, Any], device_key: str) -> Optional[PanelTelemetry]:
    """Pick one device's telemetry out of the bridge's report.

    The bridge keys its telemetry by the label it prints in its own logs
    ("BB35", "BB36"), which is not the catalogue key, so the match is by
    fragment rather than equality.
    """
    fragments = PANEL_LABELS.get(device_key, ())

    for label, payload in panels.items():
        text = str(label).upper()

        if any(fragment.upper() in text for fragment in fragments):
            if isinstance(payload, Mapping):
                return PanelTelemetry.from_payload(label, payload)

    return None


def render(
    values: Mapping[str, float],
    *,
    page: str = "pfd",
    mcdu: bool = False,
):
    """Draw one frame and return it as a PIL image, or None if unavailable."""
    _load()

    if _frame_factory is None:
        return None

    global _render_error

    with _lock:
        try:
            from PIL import ImageDraw

            frame = _frame_factory()

            if mcdu:
                # The MCDU's own identifier, so the viewport and any
                # per-panel geometry behave as they do on the hardware.
                frame.identifier = 0x32

            # Start from the panel's own background, not PIL's black, so the
            # mirror's unpainted area matches the glass.
            ImageDraw.Draw(frame.image).rectangle(
                [0, 0, WIDTH - 1, HEIGHT - 1], fill=BACKGROUND
            )

            canvas: Any = frame

            if mcdu and _fitted_canvas is not None:
                canvas = _fitted_canvas(frame)

            drawer = _renderers.get(page if page in _renderers else "pfd")

            if drawer is None:
                drawer = _renderers.get("pfd")

            if drawer is None:
                return None

            drawer(canvas, dict(values))
            _render_error = None
            return frame.image

        except Exception as exc:
            _render_error = f"{type(exc).__name__}: {exc}"
            return None


def render_error() -> Optional[str]:
    """Why the last render produced nothing, if it did."""
    return _render_error


# --------------------------------------------------------------------------
# A real restart
# --------------------------------------------------------------------------


@dataclass
class RebootResult:
    ok: bool
    message: str
    needs_admin: bool = False
    seconds: float = 0.0


def reboot(device_key: str) -> RebootResult:
    """Re-enumerate a panel: a true firmware restart, logo and all.

    This is deliberately not a blank-and-redraw.  Redrawing leaves the
    controller in whatever state it was already in, which is no use when that
    state is the problem.  Pulling the device off the bus and letting Windows
    bring it back restarts its firmware, and the WinCtrl logo appearing is the
    proof that it happened.
    """
    import time

    device: Optional[DeviceSpec] = get_device(device_key)

    if device is None:
        return RebootResult(False, f"Unknown device: {device_key}")

    if not device.detectable() or not device.usb_resettable:
        return RebootResult(
            False,
            f"{device.title} is not a USB device, so it cannot be "
            "re-enumerated.",
        )

    started = time.monotonic()
    result = usb.reset_device(device.vid, device.pid)
    elapsed = time.monotonic() - started

    if result.ok:
        return RebootResult(
            True,
            f"{device.title} restarted: it left the USB bus and came back. "
            "The WinCtrl logo appears while its firmware starts.",
            seconds=elapsed,
        )

    return RebootResult(False, result.message, result.needs_admin, elapsed)


def can_reboot() -> Tuple[bool, str]:
    """Whether a real reboot is possible right now, and why not if it is not."""
    if not usb.is_windows():
        return False, "Re-enumerating USB devices is implemented on Windows only."

    if not usb.is_admin():
        return (
            False,
            "A real restart re-enumerates the device on the USB bus, which "
            "Windows only allows with Administrator rights.  Restart this "
            "application as administrator to enable it.",
        )

    return True, ""
