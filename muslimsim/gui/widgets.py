"""Reusable pieces of the control panel: indicators, cards and dialogs.

Kept apart from `app.py` so the window's logic stays readable.  Nothing here
knows about the bridge or the hardware -- widgets are handed values and
callbacks and do only presentation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Sequence
import tkinter as tk
from tkinter import ttk

from ..hardware.catalog import DeviceSpec, Option

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

COLOURS = {
    "bg": "#12161c",
    "panel": "#1a2029",
    "panel_alt": "#212936",
    "line": "#2c3644",
    "text": "#e6ebf2",
    "muted": "#8b97a8",
    "accent": "#4c8dff",
    "ok": "#3ddc84",
    "warn": "#ffb020",
    "bad": "#ff5c5c",
    "off": "#49525f",
}

DOT_STATES = {
    "ok": COLOURS["ok"],
    "warn": COLOURS["warn"],
    "bad": COLOURS["bad"],
    "off": COLOURS["off"],
}


class StatusDot(tk.Canvas):
    """A small coloured lamp with a text label beside it."""

    def __init__(self, master, text: str = "", size: int = 10, **kwargs):
        super().__init__(
            master,
            width=size + 2,
            height=size + 2,
            highlightthickness=0,
            bd=0,
            bg=kwargs.pop("bg", COLOURS["panel"]),
            **kwargs,
        )
        self._size = size
        self._item = self.create_oval(
            1, 1, size, size, fill=COLOURS["off"], outline=""
        )
        self.label_text = text

    def set(self, state: str) -> None:
        self.itemconfigure(self._item, fill=DOT_STATES.get(state, COLOURS["off"]))


class DeviceCard(ttk.Frame):
    """One panel's row: what it is, whether it is there, and what to do to it."""

    def __init__(
        self,
        master,
        device: DeviceSpec,
        *,
        on_toggle: Callable[[str, bool], None],
        on_soft_reset: Callable[[str], None],
        on_usb_reset: Callable[[str], None],
        on_configure: Callable[[str], None],
        on_probe: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, style="Card.TFrame", padding=(10, 8))

        self.device = device
        self._on_toggle = on_toggle
        self._on_soft_reset = on_soft_reset
        self._on_usb_reset = on_usb_reset
        self._on_configure = on_configure
        self._on_probe = on_probe

        self.enabled = tk.BooleanVar(value=True)
        self._build()

    def _build(self) -> None:
        device = self.device

        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x")

        self.check = ttk.Checkbutton(
            header,
            text=device.title,
            variable=self.enabled,
            style="Card.TCheckbutton",
            command=lambda: self._on_toggle(device.key, self.enabled.get()),
        )
        self.check.pack(side="left")

        if not device.can_disable:
            # No flag turns this device off, so the checkbox would lie.
            self.check.state(["disabled"])
            self.enabled.set(True)

        self.usb_dot = StatusDot(header, bg=COLOURS["panel"])
        self.usb_dot.pack(side="right", padx=(6, 0))
        self.usb_label = ttk.Label(header, text="USB", style="Tiny.TLabel")
        self.usb_label.pack(side="right")

        self.state_dot = StatusDot(header, bg=COLOURS["panel"])
        self.state_dot.pack(side="right", padx=(6, 10))
        self.state_label = ttk.Label(header, text="idle", style="Tiny.TLabel")
        self.state_label.pack(side="right")

        self.purpose = ttk.Label(
            self, text=device.purpose, style="Muted.TLabel", wraplength=430,
            justify="left",
        )
        self.purpose.pack(fill="x", pady=(2, 6))

        row = ttk.Frame(self, style="Card.TFrame")
        row.pack(fill="x")

        self.reset_button = ttk.Button(
            row, text="Reset", width=8,
            command=lambda: self._on_soft_reset(device.key),
        )
        self.reset_button.pack(side="left")

        self.usb_button = ttk.Button(
            row, text="Power cycle", width=13,
            command=lambda: self._on_usb_reset(device.key),
        )
        self.usb_button.pack(side="left", padx=(6, 0))

        if not device.usb_resettable or not device.detectable():
            self.usb_button.state(["disabled"])

        if device.options:
            ttk.Button(
                row, text="Configure", width=11,
                command=lambda: self._on_configure(device.key),
            ).pack(side="left", padx=(6, 0))

        if device.probes:
            self.probe_button = ttk.Menubutton(row, text="Diagnostics", width=12)
            menu = tk.Menu(
                self.probe_button, tearoff=0,
                bg=COLOURS["panel_alt"], fg=COLOURS["text"],
                activebackground=COLOURS["accent"], activeforeground="#ffffff",
                bd=0,
            )

            for label, command in device.probes:
                menu.add_command(
                    label=label,
                    command=lambda c=command: self._on_probe(device.key, c),
                )

            self.probe_button["menu"] = menu
            self.probe_button.pack(side="left", padx=(6, 0))

        self.detail = ttk.Label(self, text="", style="Tiny.TLabel",
                                wraplength=430, justify="left")
        self.detail.pack(fill="x", pady=(6, 0))

    # -- updates -----------------------------------------------------------

    def set_present(self, present: Optional[bool]) -> None:
        if present is None:
            self.usb_dot.set("off")
            self.usb_label.configure(text="n/a")
            return

        self.usb_dot.set("ok" if present else "bad")
        self.usb_label.configure(text="plugged in" if present else "not found")

    def set_state(self, state: str, detail: str = "") -> None:
        if state == "disabled" and not self.device.can_disable:
            # It cannot be off, so never draw it as off.
            state, detail = "idle", "Always on; this device has no off switch."

        mapping = {
            "running": ("ok", "running"),
            "stopped": ("off", "stopped"),
            "disabled": ("off", "disabled"),
            "error": ("bad", "error"),
            "unsupported": ("off", "no driver"),
            "idle": ("off", "idle"),
        }
        dot, text = mapping.get(state, ("off", state))
        self.state_dot.set(dot)
        self.state_label.configure(text=text)
        self.detail.configure(text=detail)

    def set_controls_enabled(self, live: bool) -> None:
        """Soft reset only means something while the bridge is running."""
        self.reset_button.state(["!disabled"] if live else ["disabled"])


class OptionForm(ttk.Frame):
    """A form built from a device's option definitions."""

    def __init__(self, master, options: Sequence[Option],
                 values: Mapping[str, Any]) -> None:
        super().__init__(master, padding=(4, 4))
        self.vars: Dict[str, tk.Variable] = {}
        self.options = list(options)

        for row, option in enumerate(self.options):
            current = values.get(option.flag, option.default)

            ttk.Label(self, text=option.label).grid(
                row=row * 2, column=0, sticky="w", pady=(6, 0)
            )

            if option.kind == "bool":
                variable: tk.Variable = tk.BooleanVar(value=bool(current))
                widget = ttk.Checkbutton(self, variable=variable, text="")
            elif option.kind == "choice":
                variable = tk.StringVar(
                    value=str(current if current is not None else "")
                )
                widget = ttk.Combobox(
                    self, textvariable=variable, values=list(option.choices),
                    state="readonly", width=22,
                )
            else:
                variable = tk.StringVar(
                    value="" if current is None else str(current)
                )
                widget = ttk.Entry(self, textvariable=variable, width=24)

            widget.grid(row=row * 2, column=1, sticky="w", padx=(12, 0),
                        pady=(6, 0))
            self.vars[option.flag] = variable

            hint = option.help

            if option.kind in ("float", "int") and option.minimum is not None:
                # `%g` turns a whole-number bound like 1000000 into "1e+06",
                # which reads as a typo in a baud-rate field.
                if option.kind == "int":
                    bounds = f"{int(option.minimum)} to {int(option.maximum)}"
                else:
                    bounds = f"{option.minimum:g} to {option.maximum:g}"

                hint = f"{hint}  ({bounds})" if hint else f"Range {bounds}"

            if hint:
                ttk.Label(self, text=hint, style="Tiny.TLabel").grid(
                    row=row * 2 + 1, column=0, columnspan=2, sticky="w",
                    padx=(2, 0),
                )

        self.columnconfigure(1, weight=1)

    def result(self) -> Dict[str, Any]:
        """The form's values, clamped by each option's own rules."""
        values: Dict[str, Any] = {}

        for option in self.options:
            raw = self.vars[option.flag].get()

            if option.kind == "bool":
                values[option.flag] = bool(raw)
                continue

            text = str(raw).strip()

            if text == "":
                values[option.flag] = None
                continue

            values[option.flag] = option.clamp(text)

        return values


class ConfigDialog(tk.Toplevel):
    """Modal settings for one device."""

    def __init__(self, master, device: DeviceSpec,
                 values: Mapping[str, Any]) -> None:
        super().__init__(master)
        self.title(f"{device.title} settings")
        self.configure(bg=COLOURS["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.result: Optional[Dict[str, Any]] = None

        ttk.Label(self, text=device.title, style="Heading.TLabel").pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        ttk.Label(self, text=device.purpose, style="Muted.TLabel",
                  wraplength=420, justify="left").pack(
            anchor="w", padx=14, pady=(2, 8)
        )

        self.form = OptionForm(self, device.options, values)
        self.form.pack(fill="both", expand=True, padx=10)

        note = ttk.Label(
            self,
            text="Changes apply the next time the bridge starts.",
            style="Tiny.TLabel",
        )
        note.pack(anchor="w", padx=14, pady=(10, 0))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=self._save).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _save(self) -> None:
        self.result = self.form.result()
        self.destroy()


class TextPrompt(tk.Toplevel):
    """A one-line prompt, for naming a profile."""

    def __init__(self, master, title: str, prompt: str, initial: str = ""):
        super().__init__(master)
        self.title(title)
        self.configure(bg=COLOURS["bg"])
        self.resizable(False, False)
        self.transient(master)
        self.result: Optional[str] = None

        ttk.Label(self, text=prompt).pack(anchor="w", padx=14, pady=(14, 6))

        self.variable = tk.StringVar(value=initial)
        entry = ttk.Entry(self, textvariable=self.variable, width=34)
        entry.pack(padx=14)
        entry.focus_set()
        entry.bind("<Return>", lambda _event: self._ok())

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", command=self._ok).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _ok(self) -> None:
        text = self.variable.get().strip()

        if text:
            self.result = text

        self.destroy()


def apply_theme(root: tk.Misc) -> None:
    """A dark theme close to the cockpit's own, applied once at startup."""
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=COLOURS["bg"], foreground=COLOURS["text"])
    style.configure("TFrame", background=COLOURS["bg"])
    style.configure("Card.TFrame", background=COLOURS["panel"],
                    relief="flat", borderwidth=1)
    style.configure("TLabel", background=COLOURS["bg"],
                    foreground=COLOURS["text"])
    style.configure("Card.TLabel", background=COLOURS["panel"],
                    foreground=COLOURS["text"])
    style.configure("Muted.TLabel", background=COLOURS["panel"],
                    foreground=COLOURS["muted"], font=("Segoe UI", 8))
    style.configure("Tiny.TLabel", background=COLOURS["panel"],
                    foreground=COLOURS["muted"], font=("Segoe UI", 8))
    style.configure("Heading.TLabel", background=COLOURS["bg"],
                    foreground=COLOURS["text"], font=("Segoe UI", 12, "bold"))
    style.configure("Title.TLabel", background=COLOURS["bg"],
                    foreground=COLOURS["text"], font=("Segoe UI", 15, "bold"))
    style.configure("Status.TLabel", background=COLOURS["bg"],
                    foreground=COLOURS["muted"], font=("Segoe UI", 9))

    style.configure("TButton", background=COLOURS["panel_alt"],
                    foreground=COLOURS["text"], borderwidth=0, padding=(10, 5))
    style.map(
        "TButton",
        background=[("active", COLOURS["line"]), ("disabled", COLOURS["panel"])],
        foreground=[("disabled", COLOURS["off"])],
    )

    style.configure("Accent.TButton", background=COLOURS["accent"],
                    foreground="#ffffff", padding=(14, 6))
    style.map("Accent.TButton",
              background=[("active", "#3d7ae6"),
                          ("disabled", COLOURS["panel_alt"])])

    style.configure("Danger.TButton", background="#7a2b2b",
                    foreground="#ffe8e8", padding=(12, 6))
    style.map("Danger.TButton",
              background=[("active", "#9c3636"),
                          ("disabled", COLOURS["panel_alt"])])

    style.configure("TCheckbutton", background=COLOURS["bg"],
                    foreground=COLOURS["text"])
    style.configure("Card.TCheckbutton", background=COLOURS["panel"],
                    foreground=COLOURS["text"], font=("Segoe UI", 10, "bold"))
    style.map("Card.TCheckbutton",
              background=[("active", COLOURS["panel"])])

    # Entries need the field colour mapped as well as configured: clam keeps
    # a light default for the focused and readonly states, which on this
    # palette turns a focused box white with white text in it.
    style.configure("TEntry", fieldbackground=COLOURS["panel_alt"],
                    foreground=COLOURS["text"], borderwidth=0,
                    insertcolor=COLOURS["text"],
                    lightcolor=COLOURS["line"], darkcolor=COLOURS["line"],
                    bordercolor=COLOURS["line"])
    style.map(
        "TEntry",
        fieldbackground=[("focus", COLOURS["panel_alt"]),
                         ("readonly", COLOURS["panel"]),
                         ("disabled", COLOURS["panel"])],
        foreground=[("disabled", COLOURS["off"])],
    )
    style.configure("TCombobox", fieldbackground=COLOURS["panel_alt"],
                    background=COLOURS["panel_alt"], foreground=COLOURS["text"],
                    arrowcolor=COLOURS["text"], borderwidth=0)
    # A readonly combobox ignores `fieldbackground` unless the readonly state
    # is mapped explicitly, and defaults to white -- which is glaring on a
    # dark panel.
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLOURS["panel_alt"]),
                         ("disabled", COLOURS["panel"])],
        foreground=[("readonly", COLOURS["text"]),
                    ("disabled", COLOURS["off"])],
        selectbackground=[("readonly", COLOURS["panel_alt"])],
        selectforeground=[("readonly", COLOURS["text"])],
    )
    # The check glyph is drawn in `indicatorforeground` on a background of
    # `indicatorbackground`; left at the theme defaults both are near-white
    # and the tick is unreadable.
    for _name in ("TCheckbutton", "Card.TCheckbutton"):
        style.map(
            _name,
            indicatorbackground=[("selected", COLOURS["accent"]),
                                 ("!selected", COLOURS["panel_alt"])],
            indicatorforeground=[("selected", "#ffffff")],
        )
    style.configure("TMenubutton", background=COLOURS["panel_alt"],
                    foreground=COLOURS["text"], padding=(10, 5))
    style.configure("TNotebook", background=COLOURS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=COLOURS["panel"],
                    foreground=COLOURS["muted"], padding=(14, 7))
    style.map("TNotebook.Tab",
              background=[("selected", COLOURS["panel_alt"])],
              foreground=[("selected", COLOURS["text"])])
    style.configure("Vertical.TScrollbar", background=COLOURS["panel_alt"],
                    troughcolor=COLOURS["bg"], borderwidth=0,
                    arrowcolor=COLOURS["muted"])
