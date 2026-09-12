"""Throttle calibration: the forward band and the below-idle band, separately.

The WinCtrl quadrant is Airbus-shaped -- one continuous lever travel -- and a
737 has two quite different things along it.  Showing that as a single slider
is what makes idle and reverse hard to tell apart, so this shows two:

    FORWARD   IDLE |=========| TOGA          the 737 thrust lever, 0..100%
    REVERSE   IDLE |=========| FULL REV      below idle, gated by the handle
                       ^REV IDLE

Each band is drawn only over its own travel, so at the idle detent both read
zero and there is no ambiguity about which side of it the lever is on.

The two detents are measured, not assumed.  They differ between units, and
the values previously baked into the bridge put this machine's left lever
1.85% above idle with the lever sitting in its idle detent.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional
import tkinter as tk
from tkinter import messagebox, ttk

from ..hardware.throttle import (
    RAW_MAX,
    LeverCalibration,
    ThrottleCalibration,
    ThrottleReader,
    ThrottleSample,
    outputs,
)
from .widgets import COLOURS, StatusDot

BAND_HEIGHT = 26
BAND_MIN_WIDTH = 300

SIDES = (("left", "Engine 1  (left lever)"), ("right", "Engine 2  (right lever)"))


class BandMeter(tk.Canvas):
    """One band of the lever's travel, drawn over that band only."""

    def __init__(self, master, kind: str, **kwargs) -> None:
        super().__init__(
            master,
            height=BAND_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=COLOURS["panel_alt"],
            **kwargs,
        )
        #: "forward" or "reverse"; they differ in colour and in what the
        #: markers mean.
        self.kind = kind
        self._value = 0.0
        self._active = True
        self._gate: Optional[float] = None
        self._note = ""
        self.bind("<Configure>", lambda _event: self._redraw())

    def update_value(
        self,
        value: float,
        *,
        active: bool = True,
        gate: Optional[float] = None,
        note: str = "",
    ) -> None:
        self._value = max(0.0, min(1.0, float(value)))
        self._active = bool(active)
        self._gate = gate
        self._note = note
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")

        width = max(self.winfo_width(), BAND_MIN_WIDTH)
        height = BAND_HEIGHT
        pad = 3

        self.create_rectangle(0, 0, width, height,
                              fill=COLOURS["panel_alt"], outline="")

        if self.kind == "forward":
            fill = COLOURS["ok"]
        else:
            fill = COLOURS["warn"] if self._active else COLOURS["off"]

        span = width - pad * 2
        end = pad + span * self._value

        if self._value > 0.0:
            self.create_rectangle(pad, pad, end, height - pad,
                                  fill=fill, outline="")

        # The REV IDLE gate: where Zibo's reverse first responds.
        if self._gate is not None:
            x = pad + span * max(0.0, min(1.0, self._gate))
            self.create_line(x, 0, x, height, fill=COLOURS["accent"], width=2)
            self.create_text(x + 4, height - 8, text="REV IDLE", anchor="w",
                             fill=COLOURS["accent"], font=("Segoe UI", 7))

        text = f"{self._value * 100:5.1f}%"

        if self._note:
            text = f"{text}   {self._note}"

        self.create_text(
            width - 8, height / 2, text=text, anchor="e",
            fill=COLOURS["text"] if self._active else COLOURS["muted"],
            font=("Consolas", 9),
        )


class LeverPanel(ttk.Frame):
    """One lever: its raw reading, its handle, and both bands."""

    def __init__(self, master, side: str, title: str) -> None:
        super().__init__(master, style="Card.TFrame", padding=(12, 10))

        self.side = side

        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(fill="x")

        ttk.Label(head, text=title, style="Card.TLabel").pack(side="left")

        self.handle_dot = StatusDot(head, bg=COLOURS["panel"])
        self.handle_dot.pack(side="right", padx=(6, 0))
        self.handle_label = ttk.Label(head, text="REV handle", style="Tiny.TLabel")
        self.handle_label.pack(side="right")

        self.raw_label = ttk.Label(head, text="raw ----", style="Tiny.TLabel")
        self.raw_label.pack(side="right", padx=(0, 18))

        forward_row = ttk.Frame(self, style="Card.TFrame")
        forward_row.pack(fill="x", pady=(10, 2))
        ttk.Label(forward_row, text="FORWARD", width=9,
                  style="Tiny.TLabel").pack(side="left")
        ttk.Label(forward_row, text="IDLE", width=5,
                  style="Tiny.TLabel").pack(side="left")
        self.forward = BandMeter(forward_row, "forward")
        self.forward.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(forward_row, text="TOGA", width=5,
                  style="Tiny.TLabel").pack(side="left")

        reverse_row = ttk.Frame(self, style="Card.TFrame")
        reverse_row.pack(fill="x", pady=(4, 2))
        ttk.Label(reverse_row, text="REVERSE", width=9,
                  style="Tiny.TLabel").pack(side="left")
        ttk.Label(reverse_row, text="IDLE", width=5,
                  style="Tiny.TLabel").pack(side="left")
        self.reverse = BandMeter(reverse_row, "reverse")
        self.reverse.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(reverse_row, text="F.REV", width=5,
                  style="Tiny.TLabel").pack(side="left")

        self.points = ttk.Label(self, text="", style="Tiny.TLabel")
        self.points.pack(fill="x", pady=(8, 0))

    def update_from(
        self,
        sample: ThrottleSample,
        calibration: LeverCalibration,
    ) -> None:
        raw = sample.raw_for(self.side)
        reverse_active = sample.reverse_active(self.side)

        self.raw_label.configure(text=f"raw {raw}")
        self.handle_dot.set("warn" if reverse_active else "off")
        self.handle_label.configure(
            text="REV handle up" if reverse_active else "REV handle down"
        )

        forward, reverse = outputs(
            raw, calibration,
            reverse_active=reverse_active,
            idle_contact=sample.idle_contact(self.side),
        )

        self.forward.update_value(forward)

        # Where the REV IDLE gate sits along the reverse band, so the marker
        # lands on the physical detent rather than at an arbitrary fraction.
        span = max(1, calibration.idle_raw - calibration.full_rev_raw)
        gate = (calibration.idle_raw - calibration.rev_idle_raw) / span

        self.reverse.update_value(
            reverse,
            active=reverse_active,
            gate=gate,
            note="" if reverse_active else "handle down - inert",
        )

        self.points.configure(
            text=f"IDLE {calibration.idle_raw}    "
                 f"REV IDLE {calibration.rev_idle_raw}    "
                 f"TOGA {calibration.max_raw}    "
                 f"FULL REV {calibration.full_rev_raw}"
        )


class ThrottleView(ttk.Frame):
    """The Throttle tab: both levers, both bands, and the capture."""

    def __init__(
        self,
        master,
        reader: ThrottleReader,
        *,
        calibration: ThrottleCalibration,
        on_save: Callable[[], None],
        bridge_is_running: Callable[[], bool],
    ) -> None:
        super().__init__(master, padding=(14, 12))

        self.reader = reader
        self.calibration = calibration
        self._on_save = on_save
        self._bridge_is_running = bridge_is_running
        self.panels: Dict[str, LeverPanel] = {}

        self._build()

    def _build(self) -> None:
        head = ttk.Frame(self)
        head.pack(fill="x")

        ttk.Label(head, text="Throttle", style="Heading.TLabel").pack(side="left")

        self.status = ttk.Label(head, text="", style="Status.TLabel")
        self.status.pack(side="right")

        ttk.Label(
            self,
            text="The quadrant is one continuous travel; a 737 has a thrust "
                 "lever above IDLE and a reverse lever below it.  Both bands "
                 "read zero at the idle detent, so there is no doubt which "
                 "side of it you are on.  Below IDLE does nothing until the "
                 "reverse handle is raised.",
            style="Status.TLabel", wraplength=980, justify="left",
        ).pack(fill="x", pady=(4, 8))

        self.warning = ttk.Label(self, text="", style="Status.TLabel",
                                 wraplength=980, justify="left")
        self.warning.pack(fill="x", pady=(0, 6))

        for side, title in SIDES:
            panel = LeverPanel(self, side, title)
            panel.pack(fill="x", pady=(0, 10))
            self.panels[side] = panel

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(4, 0))

        ttk.Button(
            actions, text="1.  Capture IDLE", style="Accent.TButton", width=20,
            command=self._capture_idle,
        ).pack(side="left")

        ttk.Button(
            actions, text="2.  Capture REV IDLE", width=22,
            command=self._capture_rev_idle,
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            actions, text="Restore defaults", width=18,
            command=self._restore,
        ).pack(side="left", padx=(8, 0))

        self.state_label = ttk.Label(self, text="", style="Status.TLabel",
                                     wraplength=980, justify="left")
        self.state_label.pack(fill="x", pady=(10, 0))

        self._refresh_state()

    # -- live --------------------------------------------------------------

    def tick(self) -> None:
        if self._bridge_is_running():
            self.warning.configure(
                text="The bridge is running and holds the throttle.  Stop it "
                     "from the Devices tab to calibrate; the bands below will "
                     "not move until you do.",
                foreground=COLOURS["warn"],
            )
        elif self.reader.error:
            self.warning.configure(text=self.reader.error,
                                   foreground=COLOURS["bad"])
        else:
            self.warning.configure(text="", foreground=COLOURS["muted"])

        sample = self.reader.sample()

        for side, panel in self.panels.items():
            panel.update_from(
                sample,
                self.calibration.left if side == "left" else self.calibration.right,
            )

        age = self.reader.age()
        self.status.configure(
            text="live" if age < 1.0 else "no data from the throttle"
        )

    # -- capture -----------------------------------------------------------

    def _capture_idle(self) -> None:
        if not self._ready():
            return

        sample = self.reader.sample()
        self.calibration.left.idle_raw = sample.left_raw
        self.calibration.right.idle_raw = sample.right_raw
        self._finish("IDLE captured.  Now step 2.")

    def _capture_rev_idle(self) -> None:
        if not self._ready():
            return

        sample = self.reader.sample()
        self.calibration.left.rev_idle_raw = sample.left_raw
        self.calibration.right.rev_idle_raw = sample.right_raw
        self._finish("REV IDLE captured.")

    def _ready(self) -> bool:
        if self._bridge_is_running():
            messagebox.showinfo(
                "Bridge is running",
                "Stop the bridge before calibrating: it holds the throttle, "
                "so nothing here is reading the live position.",
                parent=self,
            )
            return False

        if self.reader.age() > 1.0:
            messagebox.showerror(
                "No throttle data",
                self.reader.error or "The throttle is not reporting.",
                parent=self,
            )
            return False

        return True

    def _finish(self, message: str) -> None:
        ok, why = self.calibration.valid()
        self.calibration.calibrated = ok
        self._on_save()
        self._refresh_state()

        if ok:
            self.state_label.configure(text=message, foreground=COLOURS["ok"])
        else:
            self.state_label.configure(
                text=f"{message}  But this is not usable yet: {why}",
                foreground=COLOURS["warn"],
            )

    def _restore(self) -> None:
        if not messagebox.askyesno(
            "Restore defaults",
            "Replace the measured points with the values built into the "
            "bridge?\n\nThose came from one particular throttle, and on this "
            "machine they place the left lever about 1.9% above idle at its "
            "own idle detent.",
            parent=self,
        ):
            return

        self.calibration.left = LeverCalibration(idle_raw=19308, rev_idle_raw=13976)
        self.calibration.right = LeverCalibration(idle_raw=20165, rev_idle_raw=14115)
        self.calibration.calibrated = False
        self._on_save()
        self._refresh_state()

    def _refresh_state(self) -> None:
        ok, why = self.calibration.valid()

        if not self.calibration.calibrated:
            self.state_label.configure(
                text="Not calibrated on this throttle yet.  Put both levers in "
                     "the IDLE detent and press 1; then raise both reverse "
                     "handles, pull back to the REV IDLE detent, and press 2.",
                foreground=COLOURS["warn"],
            )
        elif ok:
            self.state_label.configure(
                text="Calibrated.  The bridge is started with these points, so "
                     "IDLE is exactly idle and the reverse band begins where "
                     "your detent actually is.",
                foreground=COLOURS["ok"],
            )
        else:
            self.state_label.configure(text=why, foreground=COLOURS["bad"])
