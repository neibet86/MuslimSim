"""Visual calibration for pedals, throttles and yokes.

Calibration is a thing you do with your hands while watching the result, so
this shows a live bar per axis and a button that says "move it as far as it
goes". Nothing here asks anyone to read a number off a console and type it
somewhere else.

The numbers shown are SDL's, because SDL is what the bridge reads these
devices through.  Calibrating against a different source would look right and
behave wrong.

One process at a time can own an SDL controller, so the bridge must not be
holding the device.  The view says so plainly rather than showing frozen bars.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional
import tkinter as tk
from tkinter import ttk

from ..hardware.axes import (
    MOVEMENT_THRESHOLD,
    AxisCalibration,
    AxisReader,
    ControllerInfo,
    MovementWatcher,
)
from .widgets import COLOURS

BAR_HEIGHT = 22
BAR_MIN_WIDTH = 260


class AxisBar(tk.Canvas):
    """One axis, drawn live: travel, captured range, centre and deadzone."""

    def __init__(self, master, label: str, **kwargs) -> None:
        super().__init__(
            master,
            height=BAR_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=COLOURS["panel_alt"],
            **kwargs,
        )
        self.label = label
        self._raw = 0.0
        self._calibration: Optional[AxisCalibration] = None
        self._captured: Optional[tuple] = None
        self.bind("<Configure>", lambda _event: self._redraw())

    def update_value(
        self,
        raw: float,
        calibration: Optional[AxisCalibration] = None,
        captured: Optional[tuple] = None,
    ) -> None:
        self._raw = float(raw)
        self._calibration = calibration
        self._captured = captured
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")

        width = max(self.winfo_width(), BAR_MIN_WIDTH)
        height = BAR_HEIGHT
        margin = 2

        self.create_rectangle(
            0, 0, width, height, fill=COLOURS["panel_alt"], outline=""
        )

        # The travel the calibration will actually use.
        if self._captured:
            low, high = self._captured
            left = self._to_x(low, width)
            right = self._to_x(high, width)
            self.create_rectangle(
                left, margin, right, height - margin,
                fill="#1d3350", outline="",
            )

        # Raw SDL position, always drawn from the true -1..+1 range so a
        # miscalibrated axis is visibly miscalibrated rather than hidden.
        position = self._to_x(self._raw, width)

        fill = COLOURS["accent"]

        if self._calibration is not None:
            travel = self._calibration.normalise(self._raw)
            fill = COLOURS["ok"] if 0.001 < travel < 0.999 else COLOURS["accent"]

        self.create_rectangle(
            margin, margin, max(margin + 1, position), height - margin,
            fill=fill, outline="",
        )

        # Centre marker.
        if self._calibration is not None and self._calibration.centre is not None:
            centre_x = self._to_x(self._calibration.centre, width)
            self.create_line(
                centre_x, 0, centre_x, height, fill=COLOURS["warn"], width=2
            )

        self.create_line(
            width / 2, height - 4, width / 2, height, fill=COLOURS["line"]
        )

        text = f"{self._raw:+.3f}"

        if self._calibration is not None:
            text += f"   {self._calibration.normalise(self._raw) * 100:5.1f}%"

        self.create_text(
            width - 8, height / 2, text=text, anchor="e",
            fill=COLOURS["text"], font=("Consolas", 9),
        )

    @staticmethod
    def _to_x(value: float, width: int) -> float:
        clamped = max(-1.0, min(1.0, float(value)))
        return (clamped + 1.0) / 2.0 * width


class CalibrationView(ttk.Frame):
    """The calibration tab: pick a controller, watch it, capture its range."""

    def __init__(
        self,
        master,
        reader: AxisReader,
        *,
        calibrations: Dict[str, Dict[int, AxisCalibration]],
        on_save: Callable[[], None],
        bridge_is_running: Callable[[], bool],
    ) -> None:
        super().__init__(master, padding=(14, 12))

        self.reader = reader
        self.calibrations = calibrations
        self._on_save = on_save
        self._bridge_is_running = bridge_is_running

        self.controller: Optional[ControllerInfo] = None
        self.bars: List[AxisBar] = []
        self.labels: List[ttk.Label] = []
        self.watcher: Optional[MovementWatcher] = None
        self._capturing = False

        self._build()

    # -- layout ------------------------------------------------------------

    def _build(self) -> None:
        head = ttk.Frame(self)
        head.pack(fill="x")

        ttk.Label(head, text="Calibration", style="Heading.TLabel").pack(side="left")

        self.status = ttk.Label(head, text="", style="Status.TLabel")
        self.status.pack(side="right")

        chooser = ttk.Frame(self)
        chooser.pack(fill="x", pady=(10, 4))

        ttk.Label(chooser, text="Controller", style="Status.TLabel").pack(side="left")

        self.choice = tk.StringVar()
        self.combo = ttk.Combobox(
            chooser, textvariable=self.choice, state="readonly", width=44
        )
        self.combo.pack(side="left", padx=(8, 0))
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._select())

        ttk.Button(chooser, text="Rescan", width=9,
                   command=self.refresh_controllers).pack(side="left", padx=(8, 0))

        self.warning = ttk.Label(self, text="", style="Tiny.TLabel",
                                 wraplength=760, justify="left")
        self.warning.pack(fill="x", pady=(2, 6))

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(2, 8))

        self.capture_button = ttk.Button(
            actions, text="Capture range", style="Accent.TButton",
            command=self._toggle_capture,
        )
        self.capture_button.pack(side="left")

        ttk.Button(actions, text="Set centre here", width=16,
                   command=self._set_centre).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Reset this device", width=17,
                   command=self._reset).pack(side="left", padx=(8, 0))

        ttk.Label(
            actions,
            text="Press Capture, move every pedal and lever to both ends, "
                 "then press it again.",
            style="Status.TLabel",
        ).pack(side="left", padx=(14, 0))

        self.axes_frame = ttk.Frame(self)
        self.axes_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.buttons_label = ttk.Label(self, text="", style="Tiny.TLabel")
        self.buttons_label.pack(fill="x", pady=(8, 0))

        self.refresh_controllers()

    # -- controllers -------------------------------------------------------

    def refresh_controllers(self) -> None:
        controllers = self.reader.controllers()
        names = [f"[{c.index}] {c.name}" for c in controllers]
        self.combo.configure(values=names)

        if not controllers:
            self.status.configure(text=self.reader.error or "No controllers found")
            return

        if not self.choice.get() or self.choice.get() not in names:
            # Default to something worth calibrating rather than index 0.
            preferred = next(
                (
                    c for c in controllers
                    if any(word in c.name.lower()
                           for word in ("pedal", "throttle", "yoke", "base"))
                ),
                controllers[0],
            )
            self.choice.set(f"[{preferred.index}] {preferred.name}")

        self._select()

    def _select(self) -> None:
        text = self.choice.get()

        if not text.startswith("["):
            return

        try:
            index = int(text[1:text.index("]")])
        except (ValueError, IndexError):
            return

        self.controller = next(
            (c for c in self.reader.controllers() if c.index == index), None
        )
        self._build_axes()

    def _build_axes(self) -> None:
        for child in self.axes_frame.winfo_children():
            child.destroy()

        self.bars = []
        self.labels = []

        if self.controller is None:
            return

        stored = self.calibrations.setdefault(self._key(), {})

        for axis in range(self.controller.axes):
            row = ttk.Frame(self.axes_frame)
            row.pack(fill="x", pady=3)

            label = ttk.Label(row, text=f"Axis {axis}", width=9,
                              style="Status.TLabel")
            label.pack(side="left")
            self.labels.append(label)

            bar = AxisBar(row, f"Axis {axis}")
            bar.pack(side="left", fill="x", expand=True, padx=(6, 8))
            self.bars.append(bar)

            invert = tk.BooleanVar(
                value=stored.get(axis, AxisCalibration()).invert
            )

            def _toggle(a=axis, v=invert) -> None:
                calibration = self.calibrations.setdefault(
                    self._key(), {}
                ).setdefault(a, AxisCalibration())
                calibration.invert = v.get()
                self._on_save()

            ttk.Checkbutton(row, text="Invert", variable=invert,
                            command=_toggle).pack(side="left")

    def _key(self) -> str:
        if self.controller is None:
            return ""

        # Keyed by name, not index: SDL renumbers devices when one is
        # unplugged, and a calibration that jumps to another device would be
        # worse than none.
        return self.controller.name

    # -- live update -------------------------------------------------------

    def tick(self) -> None:
        """Called from the window's timer; keeps the bars moving."""
        if self.controller is None:
            return

        if self._bridge_is_running():
            self.warning.configure(
                text="The bridge is running and owns these controllers.  "
                     "Stop it from the Devices tab before calibrating, or the "
                     "bars below will not move.",
                foreground=COLOURS["warn"],
            )
        else:
            self.warning.configure(text="", foreground=COLOURS["muted"])

        values = self.reader.axes(self.controller.index)
        stored = self.calibrations.get(self._key(), {})

        if self.watcher is not None:
            self.watcher.sample()

        for index, bar in enumerate(self.bars):
            raw = values[index] if index < len(values) else 0.0
            captured = None

            if self.watcher is not None and index < len(self.watcher.extremes):
                captured = self.watcher.extremes[index]

            bar.update_value(raw, stored.get(index), captured)

        pressed = [
            str(i) for i, down in enumerate(self.reader.buttons(self.controller.index))
            if down
        ]
        self.buttons_label.configure(
            text="Buttons held: " + (", ".join(pressed) if pressed else "none")
        )

        age = self.reader.age()

        if age > 1.0:
            self.status.configure(text="No data from SDL")
        else:
            self.status.configure(text=f"live  ({age * 1000:.0f} ms)")

    # -- actions -----------------------------------------------------------

    def _toggle_capture(self) -> None:
        if self.controller is None:
            return

        if self._capturing:
            self._finish_capture()
            return

        self.watcher = MovementWatcher(self.reader, self.controller.index)
        self._capturing = True
        self.capture_button.configure(text="Finish capture")
        self.status.configure(text="capturing - move everything to both ends")

    def _finish_capture(self) -> None:
        self._capturing = False
        self.capture_button.configure(text="Capture range")

        if self.watcher is None:
            return

        stored = self.calibrations.setdefault(self._key(), {})
        captured = 0

        for axis in range(len(self.watcher.extremes)):
            calibration = self.watcher.calibration_for(axis)

            if calibration is None:
                # Nothing moved on this axis: keep whatever was there rather
                # than replacing a good calibration with a dead range.
                continue

            existing = stored.get(axis)

            if existing is not None:
                calibration.invert = existing.invert
                calibration.deadzone = existing.deadzone

            stored[axis] = calibration
            captured += 1

        self.watcher = None
        self._on_save()

        if captured:
            self.status.configure(text=f"captured {captured} axes")
        else:
            self.status.configure(
                text=f"nothing moved more than {MOVEMENT_THRESHOLD:.0%}"
            )

    def _set_centre(self) -> None:
        if self.controller is None:
            return

        values = self.reader.axes(self.controller.index)
        stored = self.calibrations.setdefault(self._key(), {})

        for axis, value in enumerate(values):
            calibration = stored.setdefault(axis, AxisCalibration())
            calibration.centre = value

        self._on_save()
        self.status.configure(text="centre captured at the current position")

    def _reset(self) -> None:
        self.calibrations.pop(self._key(), None)
        self.watcher = None
        self._capturing = False
        self.capture_button.configure(text="Capture range")
        self._build_axes()
        self._on_save()
        self.status.configure(text="calibration cleared for this device")
