from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Mapping, Optional


RequestFn = Callable[..., None]


class AssignmentEditor(ttk.Frame):
    """Device-scoped learn result assignment and future-driver control surface."""

    def __init__(self, master: Any, request: RequestFn) -> None:
        super().__init__(master, padding=12)
        self._request = request
        self._catalog: Dict[str, Dict[str, Any]] = {}
        self._adoptions: Dict[str, Dict[str, Any]] = {}

        self.device = tk.StringVar()
        self.adoption = tk.StringVar()
        self.control = tk.StringVar()
        self.kind = tk.StringVar(value="disabled")
        self.target = tk.StringVar()
        self.invert = tk.BooleanVar(value=False)
        self.scale = tk.StringVar(value="1.0")
        self.deadband = tk.StringVar(value="0.0")
        self.fixed_value = tk.StringVar()
        self.status = tk.StringVar(value="Choose a device and learned physical control.")

        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Assign / Reassign", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )
        ttk.Label(
            self,
            text=("Bindings are device-scoped and revisioned. Reassign replaces only this "
                  "control; Disable keeps an explicit no-action decision."),
            wraplength=760,
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 12))

        self.device_box = self._row_combo(2, "Device", self.device)
        self.device_box.bind("<<ComboboxSelected>>", self._device_changed)
        self._row_entry(3, "Adoption ID", self.adoption)
        self.control_box = self._row_combo(4, "Physical / learned control", self.control)
        self.kind_box = self._row_combo(
            5, "Binding kind", self.kind,
            values=("disabled", "command", "dataref", "action"), readonly=True,
        )
        self._row_entry(6, "Target function / dataref / action", self.target)

        options = ttk.Frame(self)
        options.grid(row=7, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(options, text="Invert", variable=self.invert).pack(side="left")
        ttk.Label(options, text="Scale").pack(side="left", padx=(18, 4))
        ttk.Entry(options, textvariable=self.scale, width=9).pack(side="left")
        ttk.Label(options, text="Deadband").pack(side="left", padx=(18, 4))
        ttk.Entry(options, textvariable=self.deadband, width=9).pack(side="left")
        ttk.Label(options, text="Fixed value (optional)").pack(side="left", padx=(18, 4))
        ttk.Entry(options, textvariable=self.fixed_value, width=10).pack(side="left")

        actions = ttk.Frame(self)
        actions.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 8))
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(actions, text="Save assignment", command=self.save).pack(side="left", padx=6)
        ttk.Button(actions, text="Disable control", command=self.disable).pack(side="left", padx=6)
        ttk.Button(actions, text="Clear assignment", command=self.clear).pack(side="left", padx=6)
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="Start future-device driver", command=self.plugin_start).pack(side="left")
        ttk.Button(actions, text="Stop future-device driver", command=self.plugin_stop).pack(side="left", padx=6)

        ttk.Label(self, textvariable=self.status, wraplength=800).grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=(8, 0)
        )
        self.after_idle(self.refresh)

    def _row_entry(self, row: int, label: str, variable: tk.StringVar) -> ttk.Entry:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        widget = ttk.Entry(self, textvariable=variable)
        widget.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        return widget

    def _row_combo(self, row: int, label: str, variable: tk.StringVar,
                   values: tuple[str, ...] = (), readonly: bool = False) -> ttk.Combobox:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        widget = ttk.Combobox(
            self, textvariable=variable, values=values,
            state="readonly" if readonly else "normal",
        )
        widget.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        return widget

    def _send(self, command: str, done: Optional[Callable[[Dict[str, Any]], None]] = None,
              **payload: Any) -> None:
        callback = done or (lambda result: self.status.set(str(result.get("message") or "Done.")))
        try:
            self._request(command, done=callback, **payload)
        except Exception as exc:
            self.status.set(f"{command} failed: {exc}")

    def refresh(self) -> None:
        self.status.set("Refreshing device, adoption, and learned-control data…")
        self._send("status", self._receive_status)

    def _receive_status(self, response: Dict[str, Any]) -> None:
        catalogue = response.get("catalogue") or response.get("catalog") or {}
        devices = catalogue.get("devices") if isinstance(catalogue, Mapping) else None
        if not isinstance(devices, list):
            devices = []
        self._catalog = {
            str(item.get("key")): dict(item)
            for item in devices if isinstance(item, Mapping) and item.get("key")
        }

        platform = response.get("platform_v7") or response.get("platform")
        if not isinstance(platform, Mapping):
            lab = response.get("lab")
            platform = lab.get("platform_v7") if isinstance(lab, Mapping) else {}
        adopted = platform.get("adopted_devices") if isinstance(platform, Mapping) else []
        if isinstance(adopted, Mapping):
            adopted = list(adopted.values())
        if not isinstance(adopted, list):
            adopted = []
        self._adoptions = {
            str(item.get("adoption_id") or item.get("id")): dict(item)
            for item in adopted if isinstance(item, Mapping) and (item.get("adoption_id") or item.get("id"))
        }

        keys = sorted(set(self._catalog) | {
            str(item.get("device_key") or item.get("family_key") or "")
            for item in self._adoptions.values()
        } - {""})
        self.device_box.configure(values=keys)
        if not self.device.get() and keys:
            self.device.set(keys[0])
        self._device_changed()
        sample = platform.get("sample_sequence") if isinstance(platform, Mapping) else None
        self.status.set(
            f"Ready. {len(keys)} device families; {len(self._adoptions)} adopted devices"
            + (f"; physical sample #{sample}." if sample is not None else ".")
        )

    def _device_changed(self, _event: object = None) -> None:
        key = self.device.get().strip()
        spec = self._catalog.get(key, {})
        controls = spec.get("controls") if isinstance(spec, Mapping) else []
        names = []
        if isinstance(controls, list):
            names.extend(str(item.get("key")) for item in controls
                         if isinstance(item, Mapping) and item.get("key"))
        for item in self._adoptions.values():
            family = str(item.get("device_key") or item.get("family_key") or "")
            if family == key:
                adoption_id = str(item.get("adoption_id") or item.get("id") or "")
                if adoption_id:
                    self.adoption.set(adoption_id)
                learned = item.get("learned_controls")
                if isinstance(learned, Mapping):
                    names.extend(str(name) for name in learned)
        self.control_box.configure(values=sorted(set(names)))

    def _binding(self, kind: Optional[str] = None) -> Dict[str, Any]:
        binding_kind = str(kind or self.kind.get()).strip().lower()
        if binding_kind not in {"disabled", "command", "dataref", "action"}:
            raise ValueError("Binding kind must be disabled, command, dataref, or action")
        try:
            scale = float(self.scale.get().strip() or "1")
            deadband = float(self.deadband.get().strip() or "0")
        except ValueError as exc:
            raise ValueError("Scale and deadband must be numbers") from exc
        result: Dict[str, Any] = {
            "kind": binding_kind,
            "target": self.target.get().strip(),
            "invert": bool(self.invert.get()),
            "scale": scale,
            "deadband": deadband,
        }
        raw_value = self.fixed_value.get().strip()
        if raw_value:
            result["value"] = float(raw_value)
        if binding_kind == "disabled":
            result["target"] = ""
        elif not result["target"]:
            raise ValueError("A target is required for this binding kind")
        return result

    def _identity(self) -> tuple[str, str, str]:
        device = self.device.get().strip()
        control = self.control.get().strip()
        adoption = self.adoption.get().strip()
        if not device or not control:
            raise ValueError("Choose a device and physical/learned control")
        return device, adoption, control

    def save(self) -> None:
        try:
            device, adoption, control = self._identity()
            binding = self._binding()
        except Exception as exc:
            messagebox.showerror("Assignment", str(exc), parent=self)
            return
        self.status.set(f"Saving {device}.{control}…")
        self._send(
            "platform_binding_set", self._saved,
            device=device, adoption_id=adoption, control=control, binding=binding,
        )

    def disable(self) -> None:
        self.kind.set("disabled")
        self.target.set("")
        self.save()

    def clear(self) -> None:
        try:
            device, adoption, control = self._identity()
        except Exception as exc:
            messagebox.showerror("Assignment", str(exc), parent=self)
            return
        self.status.set(f"Clearing {device}.{control}…")
        self._send(
            "platform_binding_clear", self._saved,
            device=device, adoption_id=adoption, control=control,
        )

    def _saved(self, response: Dict[str, Any]) -> None:
        revision = response.get("revision") or response.get("profile_revision")
        self.status.set("Assignment saved" + (f" at profile revision {revision}." if revision else "."))
        self.refresh()

    def plugin_start(self) -> None:
        device = self.device.get().strip()
        if not device:
            return
        self.status.set(f"Starting future-device driver {device}…")
        self._send("platform_plugin_start", device=device)

    def plugin_stop(self) -> None:
        device = self.device.get().strip()
        if not device:
            return
        self.status.set(f"Stopping future-device driver {device}…")
        self._send("platform_plugin_stop", device=device)


def attach_assignment_tab(manager: Any) -> Optional[AssignmentEditor]:
    """Attach to the first Notebook without depending on Manager internals."""
    notebook = None
    for value in vars(manager).values():
        if isinstance(value, ttk.Notebook):
            notebook = value
            break
    if notebook is None:
        stack = list(getattr(manager, "winfo_children", lambda: ())())
        while stack:
            widget = stack.pop(0)
            if isinstance(widget, ttk.Notebook):
                notebook = widget
                break
            stack.extend(getattr(widget, "winfo_children", lambda: ())())
    request = getattr(manager, "_request", None)
    if notebook is None or not callable(request):
        return None
    editor = AssignmentEditor(notebook, request)
    notebook.add(editor, text="Assign / Reassign")
    return editor
