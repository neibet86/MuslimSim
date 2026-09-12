"""Watch what the PFP and MCDU are showing, and really restart them.

The picture here is not an illustration.  It is the same renderer, fed the
same values the bridge fed the panel on its last frame, so if the glass is
wrong this is wrong in the same way.  That is the only kind of mirror worth
having: one that flatters the hardware would send you looking for faults that
are not there.

"Restart" means a USB re-enumeration, not a blank-and-redraw.  Redrawing
leaves the controller in whatever state it was in, which is no help when that
state is the fault.  Pulling the device off the bus restarts its firmware, and
the WinCtrl logo on the way back up is the proof it happened.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
import tkinter as tk
from tkinter import messagebox, ttk

from ..hardware import catalog, displays
from ..hardware.displays import PanelTelemetry
from .widgets import COLOURS, StatusDot

VIEW_WIDTH = 480
VIEW_HEIGHT = 360

PAGE_NAMES = {
    "pfd": "PFD",
    "nd": "ND",
    "eng_pri": "ENG PRI",
    "mfd": "MFD",
}


class PanelMirror(ttk.Frame):
    """One panel: its live picture, what it is showing, and its restart."""

    def __init__(
        self,
        master,
        device_key: str,
        *,
        on_reboot: Callable[[str], None],
        on_soft_reset: Callable[[str], None],
    ) -> None:
        super().__init__(master, style="Card.TFrame", padding=(10, 10))

        self.device_key = device_key
        self.device = catalog.get(device_key)
        self._on_reboot = on_reboot
        self._on_soft_reset = on_soft_reset
        self._photo = None
        self._last_stamp = -1.0

        self._build()

    def _build(self) -> None:
        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(fill="x")

        ttk.Label(head, text=self.device.title, style="Card.TLabel").pack(side="left")

        self.dot = StatusDot(head, bg=COLOURS["panel"])
        self.dot.pack(side="right", padx=(6, 0))
        self.state_label = ttk.Label(head, text="no data", style="Tiny.TLabel")
        self.state_label.pack(side="right")

        self.canvas = tk.Canvas(
            self, width=VIEW_WIDTH, height=VIEW_HEIGHT,
            bg="#05070a", highlightthickness=1,
            highlightbackground=COLOURS["line"], bd=0,
        )
        self.canvas.pack(pady=(8, 6))

        self.page_label = ttk.Label(self, text="", style="Tiny.TLabel")
        self.page_label.pack(fill="x")

        row = ttk.Frame(self, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))

        self.reboot_button = ttk.Button(
            row, text="Restart screen", style="Danger.TButton", width=16,
            command=lambda: self._on_reboot(self.device_key),
        )
        self.reboot_button.pack(side="left")

        ttk.Button(
            row, text="Redraw", width=10,
            command=lambda: self._on_soft_reset(self.device_key),
        ).pack(side="left", padx=(8, 0))

        self.reboot_note = ttk.Label(self, text="", style="Tiny.TLabel",
                                     wraplength=VIEW_WIDTH, justify="left")
        self.reboot_note.pack(fill="x", pady=(6, 0))

        self._show_message("waiting for the bridge")

    # -- painting ----------------------------------------------------------

    def _show_message(self, text: str) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            VIEW_WIDTH / 2, VIEW_HEIGHT / 2, text=text,
            fill=COLOURS["muted"], font=("Segoe UI", 10),
        )
        self._photo = None

    def update_from(self, telemetry: Optional[PanelTelemetry]) -> None:
        if telemetry is None:
            self.dot.set("off")
            self.state_label.configure(text="not running")
            self.page_label.configure(text="")
            self._show_message("this panel is not being driven")
            return

        if telemetry.standby:
            self.dot.set("warn")
            self.state_label.configure(text="standby")
            self.page_label.configure(
                text=f"Showing the MuslimSim standby card: {telemetry.standby}"
            )
            self._show_message(f"STANDBY\n{telemetry.standby}")
            return

        image = displays.render(
            telemetry.values,
            page=telemetry.page,
            mcdu=(self.device_key == "mcdu"),
        )

        if image is None:
            self.dot.set("bad")
            self.state_label.configure(text="cannot draw")
            reason = displays.render_error() or displays.import_error() or ""
            self._show_message(f"the mirror could not draw this frame\n{reason}")
            return

        try:
            from PIL import Image, ImageTk

            scaled = image.resize((VIEW_WIDTH, VIEW_HEIGHT), Image.BILINEAR)
            self._photo = ImageTk.PhotoImage(scaled)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        except Exception as exc:
            self._show_message(f"could not show the frame: {exc}")
            return

        self.dot.set("ok")
        self.state_label.configure(text="live")

        page = PAGE_NAMES.get(telemetry.page, telemetry.page.upper())
        self.page_label.configure(
            text=f"Showing {page}   -   data via {telemetry.source or 'unknown'}"
        )

    def set_reboot_available(self, available: bool, why: str) -> None:
        self.reboot_button.state(["!disabled"] if available else ["disabled"])
        self.reboot_note.configure(text="" if available else why)


class DisplayView(ttk.Frame):
    """The Displays tab: both panels, side by side, live."""

    def __init__(
        self,
        master,
        *,
        on_reboot: Callable[[str], None],
        on_soft_reset: Callable[[str], None],
    ) -> None:
        super().__init__(master, padding=(14, 12))

        head = ttk.Frame(self)
        head.pack(fill="x")

        ttk.Label(head, text="Displays", style="Heading.TLabel").pack(side="left")

        self.status = ttk.Label(head, text="", style="Status.TLabel")
        self.status.pack(side="right")

        ttk.Label(
            self,
            text="These are drawn by the same renderer the bridge uses, from "
                 "the values it drew its last frame with.  What is wrong here "
                 "is wrong on the glass.",
            style="Status.TLabel", wraplength=980, justify="left",
        ).pack(fill="x", pady=(4, 10))

        row = ttk.Frame(self)
        row.pack(fill="both", expand=True)

        self.mirrors: Dict[str, PanelMirror] = {}

        for key in ("pfp", "mcdu"):
            mirror = PanelMirror(
                row, key, on_reboot=on_reboot, on_soft_reset=on_soft_reset
            )
            mirror.pack(side="left", padx=(0, 12), anchor="n")
            self.mirrors[key] = mirror

        self.refresh_reboot_availability()

    def refresh_reboot_availability(self) -> None:
        available, why = displays.can_reboot()

        for mirror in self.mirrors.values():
            mirror.set_reboot_available(available, why)

    def update_from(self, panels: Dict[str, Any]) -> None:
        for key, mirror in self.mirrors.items():
            mirror.update_from(displays.telemetry_for(panels, key))

        if panels:
            self.status.configure(text=f"{len(panels)} panel(s) reporting")
        else:
            self.status.configure(text="no telemetry - is the bridge running?")
