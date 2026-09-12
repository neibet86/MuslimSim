"""Safe standalone character-page previews for the BB35 and BB36 keypads.

The normal path routers own these HID devices while X-Plane is running.  This
module is deliberately smaller: it uses only the pre-existing F2 character
page setup/writers and the already captured 96-bit keypad reports.  It makes
the panels useful in Studio practice mode without creating a simulator
connection, graphics renderer, or a second interpretation of the protocol.
"""

from __future__ import annotations

from pathlib import Path
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from . import pfp_bb35_separate_paths as _pfp
from . import mcdu_bb36_separate_paths as _mcdu


PageSink = Callable[[int, str], None]


def _normalise_lines(value: Any, columns: int, rows: int) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        value = value.get("lines", value.get("text", ""))
    if isinstance(value, str):
        source: Iterable[Any] = value.splitlines() or (value,)
    elif isinstance(value, Sequence):
        source = value
    else:
        raise ValueError("practice screen expects text or a list of text lines")
    lines = [str(item).replace("\n", " ")[:columns].ljust(columns) for item in source]
    return tuple((lines + [" " * columns] * rows)[:rows])


class _F2PracticePreview:
    """One HID owner with a fixed-format test page and captured keypad input."""

    def __init__(
        self,
        *,
        title: str,
        opener: Callable[[], Any],
        decode_buttons: Callable[[bytes], Optional[int]],
        setup: Callable[[Any], None],
        page_packets: Callable[[tuple[str, ...]], Iterable[bytes]],
        columns: int,
        rows: int,
        input_sink: Optional[PageSink] = None,
    ) -> None:
        self.title = title
        self._opener = opener
        self._decode_buttons = decode_buttons
        self._setup = setup
        self._page_packets = page_packets
        self._columns = columns
        self._rows = rows
        self._input_sink = input_sink
        self._lock = threading.Lock()
        self._lines = _normalise_lines((title, "PRACTICE COCKPIT"), columns, rows)
        self._status = "stopped"
        self._status_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    def _set_status(self, value: str) -> None:
        with self._status_lock:
            self._status = value

    def set_lab_output(self, control: str, value: Any) -> None:
        if control != "screen":
            raise ValueError(f"{self.title} practice preview does not expose {control}")
        lines = _normalise_lines(value, self._columns, self._rows)
        with self._lock:
            self._lines = lines

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"MuslimSim-{self.title}-Practice", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._set_status("stopped")

    def _run(self) -> None:
        device = None
        try:
            device = self._opener()
            self._setup(device)
            self._set_status("practice-preview")
            previous_bits: Optional[int] = None
            previous_lines: Optional[tuple[str, ...]] = None
            while not self._stop.is_set():
                with self._lock:
                    lines = self._lines
                if lines != previous_lines:
                    for packet in self._page_packets(lines):
                        device.write(list(packet))
                    previous_lines = lines
                report = device.read(128)
                if report:
                    bits = self._decode_buttons(bytes(report))
                    if bits is not None:
                        if previous_bits is not None:
                            changed = bits ^ previous_bits
                            for index in range(96):
                                if changed & (1 << index) and self._input_sink is not None:
                                    edge = "press" if bits & (1 << index) else "release"
                                    try:
                                        self._input_sink(index, edge)
                                    except Exception:
                                        pass
                        previous_bits = bits
                self._stop.wait(0.012)
        except FileNotFoundError:
            self._set_status("waiting-for-device")
        except RuntimeError as exc:
            self._set_status("missing-font" if "font" in str(exc).lower() else "preview-error")
        except Exception:
            self._set_status("preview-error")
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass


def make_pfp3n_preview(font_path: Path, input_sink: Optional[PageSink] = None) -> _F2PracticePreview:
    """Build a BB35 preview using its original retargeted F2 initialization."""

    path = Path(font_path)

    def setup(device: Any) -> None:
        if not path.is_file():
            raise RuntimeError(f"BB35 FMC font missing: {path}")
        for packet in _pfp._load_font_packets(path):
            device.write(list(packet))
        time.sleep(0.20)
        device.write(list(_pfp._black_packet()))
        device.write(list(_pfp._grid_packet()))
        for packet in _pfp._blank_f2_packets():
            device.write(list(packet))
        _pfp._set_brightness(device, 0, 128)
        _pfp._set_brightness(device, 1, 220)

    def packets(lines: tuple[str, ...]) -> Iterable[bytes]:
        colors = tuple(tuple(_pfp.COLOR_WHITE for _ in range(_pfp.PFP_COLUMNS)) for _ in range(_pfp.PFP_ROWS))
        return _pfp._page_packets(lines, colors)

    return _F2PracticePreview(
        title="PFP3N BB35", opener=_pfp._open_bb35,
        decode_buttons=_pfp._button_bits, setup=setup, page_packets=packets,
        columns=_pfp.PFP_COLUMNS, rows=_pfp.PFP_ROWS, input_sink=input_sink,
    )


def make_mcdu32_preview(font_path: Path, input_sink: Optional[PageSink] = None) -> _F2PracticePreview:
    """Build a BB36 preview using its native F2 initialization."""

    path = Path(font_path)

    def setup(device: Any) -> None:
        if not path.is_file():
            raise RuntimeError(f"BB36 FMC font missing: {path}")
        for packet in _mcdu._read_font_packets(path):
            device.write(list(packet))
        time.sleep(0.20)
        device.write(list(_mcdu._black_background_packet()))
        device.write(list(_mcdu._text_grid_packet()))
        blank = tuple(" " * _mcdu.MCDU_COLUMNS for _ in range(_mcdu.MCDU_ROWS))
        colors = tuple(tuple(_mcdu.COLOR_WHITE for _ in range(_mcdu.MCDU_COLUMNS)) for _ in range(_mcdu.MCDU_ROWS))
        for packet in _mcdu._page_packets(blank, colors):
            device.write(list(packet))
        _mcdu._set_brightness(device, 0, 128)
        _mcdu._set_brightness(device, 1, 220)

    def packets(lines: tuple[str, ...]) -> Iterable[bytes]:
        colors = tuple(tuple(_mcdu.COLOR_WHITE for _ in range(_mcdu.MCDU_COLUMNS)) for _ in range(_mcdu.MCDU_ROWS))
        return _mcdu._page_packets(lines, colors)

    return _F2PracticePreview(
        title="MCDU32 BB36", opener=_mcdu._open_bb36,
        decode_buttons=_mcdu._button_bits, setup=setup, page_packets=packets,
        columns=_mcdu.MCDU_COLUMNS, rows=_mcdu.MCDU_ROWS, input_sink=input_sink,
    )


__all__ = ["make_pfp3n_preview", "make_mcdu32_preview"]
