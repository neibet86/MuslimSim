"""Responsive Tk virtual panel for the verified Hardware Lab catalogue."""

from __future__ import annotations

import concurrent.futures
import queue
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, Optional

from ..control.client import ControlClientError
from ..hardware.catalog import catalogue_snapshot
from .supervisor import BridgeSupervisor


class HardwareLabApp(tk.Tk):
    """An intentionally generic virtual panel generated from control specs."""

    def __init__(self, supervisor: Optional[BridgeSupervisor] = None) -> None:
        super().__init__()
        self.supervisor = supervisor or BridgeSupervisor()
        self.title("MuslimSim Hardware Laboratory")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self._catalog = catalogue_snapshot()["devices"]
        self._selected: Optional[Dict[str, Any]] = None
        self._futures = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="MuslimSim-Panel")
        self._ui_results: "queue.Queue[tuple[Callable[[Any], None], Any, Optional[BaseException]]]" = queue.Queue()
        self._status = tk.StringVar(value="Bridge is not running. Virtual catalogue is available.")
        self._test_mode = tk.BooleanVar(value=False)
        self._profile_name = tk.StringVar(value="Default")
        self._device_status: Dict[str, Any] = {}
        self._profile_document: Dict[str, Any] = {}
        self._live_labels: Dict[tuple[str, str], ttk.Label] = {}
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._choose_device(0)
        self.after(100, self._tick)

    def _build(self) -> None:
        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Start bridge", command=self._start_bridge).pack(side="left")
        ttk.Button(toolbar, text="Stop bridge", command=self._stop_bridge).pack(side="left", padx=(6, 0))
        ttk.Checkbutton(toolbar, text="Test mode (no simulator writes)", variable=self._test_mode, command=self._set_mode).pack(side="left", padx=16)
        ttk.Button(toolbar, text="Run self-test", command=lambda: self._request("self_test", done=self._show_self_test)).pack(side="left")
        ttk.Label(toolbar, text="Profile").pack(side="left", padx=(18, 4))
        self._profile_picker = ttk.Combobox(toolbar, textvariable=self._profile_name, values=("Default",), width=16, state="readonly")
        self._profile_picker.pack(side="left")
        self._profile_picker.bind("<<ComboboxSelected>>", self._select_profile)
        ttk.Button(toolbar, text="New profile…", command=self._create_profile).pack(side="left", padx=(5, 0))
        ttk.Label(toolbar, textvariable=self._status).pack(side="right")

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        left = ttk.Frame(paned, padding=6)
        right = ttk.Frame(paned, padding=6)
        paned.add(left, weight=1)
        paned.add(right, weight=4)

        ttk.Label(left, text="Devices").pack(anchor="w")
        self.devices = tk.Listbox(left, exportselection=False, height=18)
        self.devices.pack(fill="both", expand=True)
        for device in self._catalog:
            suffix = "" if device["status"] == "implemented" else " — not implemented"
            self.devices.insert("end", device["title"] + suffix)
        self.devices.bind("<<ListboxSelect>>", self._on_select)
        ttk.Button(left, text="Restore mapping defaults", command=lambda: self._request("restore_defaults", done=lambda _: self._refresh_view())).pack(fill="x", pady=(8, 0))

        header = ttk.Frame(right)
        header.pack(fill="x")
        self.title_label = ttk.Label(header, font=("Segoe UI", 15, "bold"))
        self.title_label.pack(side="left")
        self.identity_label = ttk.Label(header)
        self.identity_label.pack(side="left", padx=12)
        self.restart_button = ttk.Button(header, text="Restart device", command=self._restart_device)
        self.restart_button.pack(side="right")
        self.power_button = ttk.Button(header, text="Power cycle", command=self._power_cycle_device)
        self.power_button.pack(side="right", padx=(0, 6))
        self.calibrate_button = ttk.Button(header, text="Actuator timing…", command=self._configure_actuator)
        self.calibrate_button.pack(side="right", padx=(0, 6))
        self.reset_button = ttk.Button(header, text="Reset virtual state", command=self._reset_device)
        self.reset_button.pack(side="right", padx=(0, 6))

        self.description = tk.StringVar()
        ttk.Label(right, textvariable=self.description, wraplength=760, justify="left").pack(fill="x", pady=(4, 8))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        self.panel_tab = ttk.Frame(notebook, padding=6)
        self.output_tab = ttk.Frame(notebook, padding=6)
        self.diag_tab = ttk.Frame(notebook, padding=6)
        notebook.add(self.panel_tab, text="Virtual panel & mapping")
        notebook.add(self.output_tab, text="Output tests")
        notebook.add(self.diag_tab, text="Live diagnostics")

        self.controls_canvas = tk.Canvas(self.panel_tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.panel_tab, orient="vertical", command=self.controls_canvas.yview)
        self.controls_frame = ttk.Frame(self.controls_canvas)
        self.controls_frame.bind("<Configure>", lambda _e: self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all")))
        self.controls_canvas.create_window((0, 0), window=self.controls_frame, anchor="nw")
        self.controls_canvas.configure(yscrollcommand=scrollbar.set)
        self.controls_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        outputs = ttk.Frame(self.output_tab)
        outputs.pack(fill="x")
        for label, action in (("All on", "all_on"), ("All off", "all_off"), ("Checker / pattern", "checker"), ("Reset test", "reset")):
            ttk.Button(outputs, text=label, command=lambda a=action: self._output_test(a)).pack(side="left", padx=(0, 6))
        ttk.Button(outputs, text="Send display text…", command=self._display_text).pack(side="left")
        self.output_note = tk.StringVar(value="Tests always update the virtual panel. Hardware is written only through a verified bridge driver.")
        ttk.Label(self.output_tab, textvariable=self.output_note, wraplength=760, justify="left").pack(anchor="w", pady=12)

        self.diagnostics = tk.Text(self.diag_tab, height=20, wrap="word", state="disabled")
        self.diagnostics.pack(fill="both", expand=True)

    def _on_select(self, _event: object) -> None:
        picked = self.devices.curselection()
        if picked:
            self._choose_device(int(picked[0]))

    def _choose_device(self, index: int) -> None:
        if not 0 <= index < len(self._catalog):
            return
        self.devices.selection_clear(0, "end")
        self.devices.selection_set(index)
        self._selected = self._catalog[index]
        device = self._selected
        self.title_label.configure(text=device["title"])
        self.identity_label.configure(text=f"{device['identity']}  •  {device['transport']}")
        message = device.get("notes") or "No additional notes."
        self.description.set(f"Driver: {device['driver']}\nStatus: {device['status']}. {message}")
        self.restart_button.configure(state="normal" if device["status"] == "implemented" else "disabled")
        self.power_button.configure(state="normal" if device["status"] == "implemented" else "disabled")
        self.calibrate_button.configure(state="normal" if device["key"] == "pu_overhead" else "disabled")
        self._refresh_view()

    def _refresh_view(self) -> None:
        for child in self.controls_frame.winfo_children():
            child.destroy()
        self._live_labels.clear()
        device = self._selected
        if device is None:
            return
        for row, control in enumerate(device["controls"]):
            frame = ttk.Frame(self.controls_frame, padding=(2, 3))
            frame.grid(row=row, column=0, sticky="ew")
            frame.columnconfigure(1, weight=1)
            status = "" if control["status"] == "implemented" else f" [{control['status']}]"
            ttk.Label(frame, text=control["label"] + status, width=31).grid(row=0, column=0, sticky="w")
            detail = f"{control['kind']} • {control['raw']}"
            if control.get("notes"):
                detail += " — " + control["notes"]
            ttk.Label(frame, text=detail, foreground="#666").grid(row=0, column=1, sticky="w")
            if control["direction"] in {"input", "bidirectional"} and control["status"] == "implemented":
                widget_frame = ttk.Frame(frame)
                widget_frame.grid(row=0, column=2, padx=8)
                self._input_widget(widget_frame, device, control)
                if control.get("remappable"):
                    ttk.Button(frame, text="Map…", command=lambda d=device, c=control: self._edit_binding(d, c)).grid(row=0, column=3)
            elif control["direction"] in {"output", "bidirectional"}:
                ttk.Label(frame, text="output", foreground="#0a6").grid(row=0, column=2, padx=8)
            live_label = ttk.Label(frame, text="", foreground="#245")
            live_label.grid(row=0, column=4, padx=(8, 0), sticky="w")
            self._live_labels[(device["key"], control["key"])] = live_label
        self.controls_frame.columnconfigure(0, weight=1)

    def _input_widget(self, parent: ttk.Frame, device: Dict[str, Any], control: Dict[str, Any]) -> None:
        key = control["key"]
        kind = control["kind"]
        if kind == "axis":
            value = tk.DoubleVar(value=0.0)
            ttk.Scale(parent, from_=0.0, to=1.0, variable=value, length=130, command=lambda _v: self._virtual_input(device, control, value.get(), "change")).pack(side="left")
        elif kind == "selector" and control.get("choices"):
            value = tk.StringVar(value=control["choices"][0])
            box = ttk.Combobox(parent, textvariable=value, values=control["choices"], width=10, state="readonly")
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda _e: self._virtual_input(device, control, float(control["choices"].index(value.get())), "press"))
        elif kind == "rotary":
            # Direction is part of the verified control key (for example
            # MINS knob CW vs CCW), so one row represents one detent pulse.
            ttk.Button(parent, text="Turn", command=lambda: self._virtual_input(device, control, 1, "press")).pack(side="left")
        elif kind == "toggle":
            value = tk.BooleanVar(value=False)
            ttk.Checkbutton(parent, variable=value, command=lambda: self._virtual_input(device, control, int(value.get()), "press" if value.get() else "release")).pack(side="left")
        else:
            ttk.Button(parent, text="Press", command=lambda: self._virtual_input(device, control, 1, "press")).pack(side="left")

    def _start_bridge(self) -> None:
        try:
            self.supervisor.start()
            self._status.set("Starting bridge; the hardware lab will attach as soon as it is ready…")
        except OSError as exc:
            messagebox.showerror("Cannot start bridge", str(exc), parent=self)

    def _stop_bridge(self) -> None:
        self._async(self.supervisor.stop, lambda _result: self._status.set("Bridge stopped."))

    def _set_mode(self) -> None:
        self._request("lab_mode", mode="test" if self._test_mode.get() else "live", done=lambda result: self._status.set(f"Hardware lab is in {result['mode']} mode."))

    def _select_profile(self, _event: object) -> None:
        name = self._profile_name.get().strip()
        if name:
            self._request("profile_select", name=name, done=lambda result: self._sync_profile(result.get("profile")))

    def _create_profile(self) -> None:
        name = simpledialog.askstring("New hardware profile", "Profile name (copies the current mappings and safe calibration):", parent=self)
        if name and name.strip():
            self._request("profile_create", name=name.strip(), copy_active=True, done=lambda result: self._sync_profile(result.get("profile")))

    def _restart_device(self) -> None:
        if self._selected:
            self._request("restart", device=self._selected["key"], done=lambda _r: self._status.set("Restart requested."))

    def _reset_device(self) -> None:
        if self._selected:
            self._request("lab_reset", device=self._selected["key"], done=lambda _r: self._status.set("Virtual state reset."))

    def _power_cycle_device(self) -> None:
        if self._selected is None:
            return
        if not messagebox.askyesno(
            "Power cycle device",
            "Restart this device's verified USB parent? The device will temporarily disconnect. Administrator rights are required.",
            parent=self,
        ):
            return
        self._request("power_cycle", device=self._selected["key"], done=lambda _r: self._status.set("Verified USB power cycle complete."))

    def _configure_actuator(self) -> None:
        if self._selected is None or self._selected["key"] != "pu_overhead":
            return
        value = simpledialog.askinteger(
            "PU engine-start retract timing",
            "Pulse duration in milliseconds (50–1000).\n\nOnly this timed P1 retract is confirmed by the PU protocol. There is no supported motor strength, endpoint, or direction setting.",
            parent=self, minvalue=50, maxvalue=1000, initialvalue=310,
        )
        if value is not None:
            self._request("calibration_set", device="pu_overhead", values={"starter_retract_ms": value}, done=lambda _r: self._status.set("PU auto-retract timing saved for this hardware profile."))

    def _virtual_input(self, device: Dict[str, Any], control: Dict[str, Any], value: Any, phase: str) -> None:
        self._request("lab_input", device=device["key"], control=control["key"], value=value, phase=phase, done=lambda _r: None)

    def _output_test(self, action: str) -> None:
        if self._selected:
            self._request("lab_output_test", device=self._selected["key"], action=action, done=lambda result: self._status.set(f"{action.replace('_', ' ').title()} applied to {len(result['result']['applied'])} virtual outputs."))

    def _display_text(self) -> None:
        if self._selected is None:
            return
        text = simpledialog.askstring("Display test", "Text/value for virtual displays:", parent=self)
        if text is not None:
            self._request("lab_output_test", device=self._selected["key"], action="text", payload={"text": text}, done=lambda _r: self._status.set("Virtual display text updated."))

    def _edit_binding(self, device: Dict[str, Any], control: Dict[str, Any]) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"Map {control['label']}")
        dialog.transient(self)
        dialog.grab_set()
        current = dict(
            self._profile_document.get("profiles", {})
            .get(self._profile_document.get("active_profile"), {})
            .get("bindings", {})
            .get(f"{device['key']}.{control['key']}", {})
            or {}
        )
        ttk.Label(dialog, text="Target type").grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
        kind = tk.StringVar(value=str(current.get("kind", "command")))
        ttk.Combobox(dialog, textvariable=kind, values=("command", "dataref", "action", "disabled"), state="readonly").grid(row=0, column=1, padx=10, pady=(10, 4))
        ttk.Label(dialog, text="Command, dataref, or lab:reset-device").grid(row=1, column=0, padx=10, pady=4, sticky="w")
        target = tk.StringVar(value=str(current.get("target", "")))
        ttk.Entry(dialog, textvariable=target, width=46).grid(row=1, column=1, padx=10, pady=4)
        ttk.Label(dialog, text="Constant value (optional)").grid(row=2, column=0, padx=10, pady=4, sticky="w")
        value = tk.StringVar(value="" if current.get("value") is None else str(current["value"]))
        ttk.Entry(dialog, textvariable=value, width=18).grid(row=2, column=1, padx=10, pady=4, sticky="w")
        invert = tk.BooleanVar(value=bool(current.get("invert", False)))
        ttk.Checkbutton(dialog, text="Invert input", variable=invert).grid(row=3, column=1, padx=10, pady=4, sticky="w")
        ttk.Label(dialog, text="Deadband (0–1)").grid(row=4, column=0, padx=10, pady=4, sticky="w")
        deadband = tk.StringVar(value=str(current.get("deadband", 0.0)))
        ttk.Entry(dialog, textvariable=deadband, width=18).grid(row=4, column=1, padx=10, pady=4, sticky="w")
        ttk.Label(dialog, text="Scale (−16 to 16)").grid(row=5, column=0, padx=10, pady=4, sticky="w")
        scale = tk.StringVar(value=str(current.get("scale", 1.0)))
        ttk.Entry(dialog, textvariable=scale, width=18).grid(row=5, column=1, padx=10, pady=4, sticky="w")
        def save() -> None:
            raw: Dict[str, Any] = {"kind": kind.get(), "target": target.get(), "invert": invert.get()}
            if value.get().strip():
                try:
                    raw["value"] = float(value.get())
                except ValueError:
                    messagebox.showerror("Invalid value", "Constant value must be a number.", parent=dialog)
                    return
            try:
                raw["deadband"] = float(deadband.get())
                raw["scale"] = float(scale.get())
            except ValueError:
                messagebox.showerror("Invalid mapping", "Deadband and scale must be numbers.", parent=dialog)
                return
            self._request("binding_set", device=device["key"], control=control["key"], binding=raw, done=lambda _r: (dialog.destroy(), self._status.set("Mapping saved.")))
        ttk.Button(dialog, text="Save mapping", command=save).grid(row=6, column=1, padx=10, pady=(8, 10), sticky="e")

    def _request(self, command: str, *, done: Callable[[Any], None], **fields: Any) -> None:
        client = self.supervisor.client
        if client is None:
            self._status.set("Bridge control channel is not ready; virtual controls need the child bridge running.")
            return
        self._async(lambda: client.request(command, **fields), done)

    def _async(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        future = self._futures.submit(work)
        def completed(item: concurrent.futures.Future[Any]) -> None:
            try:
                self._ui_results.put((done, item.result(), None))
            except BaseException as exc:  # UI displays expected offline failures cleanly.
                self._ui_results.put((done, None, exc))
        future.add_done_callback(completed)

    def _show_self_test(self, result: Dict[str, Any]) -> None:
        details = result["result"]
        if details["ok"]:
            self._status.set(f"Self-test passed ({details['devices']} devices in catalogue).")
        else:
            messagebox.showerror("Hardware lab self-test failed", "\n".join(details["errors"]), parent=self)

    def _tick(self) -> None:
        for line in self.supervisor.drain_output():
            self._append_diagnostic(line)
        while True:
            try:
                done, value, error = self._ui_results.get_nowait()
            except queue.Empty:
                break
            if error is not None:
                self._status.set(str(error))
            else:
                done(value)
        client = self.supervisor.client
        if client is not None:
            self._async(lambda: client.request("status"), self._receive_status)
        elif self.supervisor.running:
            self._status.set("Bridge started; waiting for its loopback control channel…")
        self.after(800, self._tick)

    def _receive_status(self, response: Dict[str, Any]) -> None:
        lab = response.get("lab") or {}
        self._device_status = dict(response.get("devices") or {})
        self._sync_profile(lab.get("profile"))
        self._update_live_controls(lab)
        mode = lab.get("mode")
        if mode in {"live", "test"} and self._test_mode.get() != (mode == "test"):
            self._test_mode.set(mode == "test")
        for event in lab.get("diagnostics", [])[-8:]:
            self._append_diagnostic(f"{event.get('device')}: {event.get('event')} {event.get('detail')}")
        self._status.set(f"Bridge connected • lab {mode or 'live'} • simulator {'connected' if lab.get('simulator_connected') else 'down'}")

    def _sync_profile(self, profile: Any) -> None:
        if not isinstance(profile, dict):
            return
        profiles = profile.get("profiles")
        active = profile.get("active_profile")
        if not isinstance(profiles, dict) or not isinstance(active, str) or active not in profiles:
            return
        self._profile_document = profile
        names = tuple(str(name) for name in profiles)
        self._profile_picker.configure(values=names)
        if self._profile_name.get() != active:
            self._profile_name.set(active)

    def _update_live_controls(self, lab: Dict[str, Any]) -> None:
        inputs = lab.get("inputs") if isinstance(lab.get("inputs"), dict) else {}
        outputs = lab.get("outputs") if isinstance(lab.get("outputs"), dict) else {}
        for (device_key, control_key), label in self._live_labels.items():
            item = dict(inputs.get(device_key, {}).get(control_key) or {})
            direction = "input"
            if not item:
                item = dict(outputs.get(device_key, {}).get(control_key) or {})
                direction = "output"
            if not item:
                label.configure(text="")
                continue
            value = item.get("value")
            source = item.get("source", direction)
            phase = item.get("phase")
            suffix = f" • {phase}" if phase else ""
            label.configure(text=f"live {direction}: {value!s} ({source}){suffix}")

    def _append_diagnostic(self, text: str) -> None:
        self.diagnostics.configure(state="normal")
        self.diagnostics.insert("end", text + "\n")
        self.diagnostics.see("end")
        self.diagnostics.configure(state="disabled")

    def _on_close(self) -> None:
        self.supervisor.stop()
        self._futures.shutdown(wait=False, cancel_futures=True)
        self.destroy()
