from __future__ import annotations

import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Mapping

from .locator import read_locator


class PlatformManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MuslimSim Device Platform V7")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.client = None
        self.cursor = 0
        self.events: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.stop_event = threading.Event()
        self.platform: dict[str, Any] = {}
        self.device_rows: dict[str, dict[str, Any]] = {}
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(80, self._drain)
        threading.Thread(target=self._connector, name="PlatformV7-Manager-Connector", daemon=True).start()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="MuslimSim Device Platform", font=("Segoe UI Semibold", 17)).pack(side="left")
        self.connection = tk.StringVar(value="Looking for the private MuslimSim hardware service…")
        ttk.Label(header, textvariable=self.connection).pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._build_devices_tab()
        self._build_monitor_tab()
        self._build_learning_tab()
        self._build_profiles_tab()
        self._build_cloud_tab()

        self.footer = tk.StringVar(value="Ctrl+Shift+D opens this manager from MuslimSim Studio.")
        ttk.Label(self, textvariable=self.footer, anchor="w", padding=(14, 4)).pack(fill="x")

    def _build_devices_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(frame, text="Devices")
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Refresh", command=self._request_status).pack(side="left")
        ttk.Label(toolbar, text="Assigned role:").pack(side="left", padx=(16, 4))
        self.role = tk.StringVar(value="unassigned")
        ttk.Combobox(
            toolbar, textvariable=self.role, state="readonly", width=18,
            values=("unassigned", "captain", "first_officer", "center", "left", "right", "pilot", "copilot", "observer"),
        ).pack(side="left")
        ttk.Button(toolbar, text="Apply role", command=self._set_role).pack(side="left", padx=6)
        ttk.Label(toolbar, text="Vendor labels are observations; this role is your saved cockpit assignment.").pack(side="left", padx=12)

        columns = ("status", "role", "vendor", "legacy", "identity", "confirmation")
        self.devices = ttk.Treeview(frame, columns=columns, show="tree headings", selectmode="browse")
        self.devices.heading("#0", text="Adopted device")
        headings = {
            "status": "Status", "role": "Assigned role", "vendor": "Current vendor label",
            "legacy": "Driver key", "identity": "Portable identity", "confirmation": "Migration state",
        }
        widths = {"status": 90, "role": 120, "vendor": 190, "legacy": 150, "identity": 180, "confirmation": 170}
        for key in columns:
            self.devices.heading(key, text=headings[key])
            self.devices.column(key, width=widths[key], stretch=True)
        self.devices.column("#0", width=190, stretch=True)
        self.devices.pack(fill="both", expand=True)
        self.devices.bind("<<TreeviewSelect>>", self._device_selected)

    def _build_monitor_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(frame, text="Live + Practice Monitor")
        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 8))
        self.monitor_summary = tk.StringVar(value="No physical samples yet")
        ttk.Label(top, textvariable=self.monitor_summary).pack(side="left")
        ttk.Label(top, text="This view observes the same data in Live and Practice; Practice never routes to X-Plane.").pack(side="right")
        columns = ("control", "value", "phase", "source", "sequence", "updated")
        self.monitor = ttk.Treeview(frame, columns=columns, show="tree headings")
        self.monitor.heading("#0", text="Device")
        for key, title, width in (
            ("control", "Control", 220), ("value", "Value", 150), ("phase", "Phase", 90),
            ("source", "Source", 110), ("sequence", "#", 80), ("updated", "Updated", 120),
        ):
            self.monitor.heading(key, text=title)
            self.monitor.column(key, width=width, stretch=True)
        self.monitor.column("#0", width=180, stretch=True)
        self.monitor.pack(fill="both", expand=True)

    def _build_learning_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="Learn / Relearn")
        form = ttk.Frame(frame)
        form.pack(fill="x")
        ttk.Label(form, text="Device key").grid(row=0, column=0, sticky="w")
        self.learn_device = tk.StringVar()
        self.learn_device_box = ttk.Combobox(form, textvariable=self.learn_device, width=30)
        self.learn_device_box.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        ttk.Label(form, text="Expected control").grid(row=0, column=1, sticky="w")
        self.learn_kind = tk.StringVar(value="any")
        ttk.Combobox(form, textvariable=self.learn_kind, state="readonly", values=("any", "button", "selector", "rotary", "axis", "hat"), width=16).grid(row=1, column=1, sticky="w", padx=(0, 10))
        ttk.Button(form, text="Start learning", command=self._learn_start).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Cancel", command=lambda: self._request("platform_learn_cancel")).grid(row=1, column=3, padx=4)
        form.columnconfigure(0, weight=1)

        self.learn_status = tk.StringVar(value="Move exactly one physical control after starting.")
        ttk.Label(frame, textvariable=self.learn_status, padding=(0, 12)).pack(fill="x")

        assign = ttk.LabelFrame(frame, text="Name and assignment", padding=10)
        assign.pack(fill="x", pady=(6, 10))
        self.semantic = tk.StringVar()
        self.binding_kind = tk.StringVar(value="command")
        self.binding_target = tk.StringVar()
        self.binding_scale = tk.StringVar(value="1.0")
        self.binding_deadband = tk.StringVar(value="0.0")
        self.binding_invert = tk.BooleanVar(value=False)
        labels = (("Learned name", self.semantic), ("Target", self.binding_target), ("Scale", self.binding_scale), ("Deadband", self.binding_deadband))
        for index, (label, variable) in enumerate(labels):
            ttk.Label(assign, text=label).grid(row=0, column=index, sticky="w", padx=(0, 8))
            ttk.Entry(assign, textvariable=variable, width=28 if index < 2 else 10).grid(row=1, column=index, sticky="ew", padx=(0, 8))
        ttk.Label(assign, text="Type").grid(row=0, column=4, sticky="w")
        ttk.Combobox(assign, textvariable=self.binding_kind, state="readonly", values=("command", "dataref", "action", "disabled"), width=12).grid(row=1, column=4, sticky="w")
        ttk.Checkbutton(assign, text="Invert", variable=self.binding_invert).grid(row=1, column=5, padx=10)
        ttk.Button(assign, text="Save learned control + assignment", command=self._learn_commit).grid(row=1, column=6, padx=(16, 0))
        assign.columnconfigure(0, weight=1)
        assign.columnconfigure(1, weight=2)

        columns = ("control", "score", "samples", "phase", "kind")
        self.candidates = ttk.Treeview(frame, columns=columns, show="headings")
        for key, title, width in (("control", "Candidate", 300), ("score", "Score", 90), ("samples", "Samples", 90), ("phase", "Phases", 170), ("kind", "Kind", 100)):
            self.candidates.heading(key, text=title)
            self.candidates.column(key, width=width, stretch=True)
        self.candidates.pack(fill="both", expand=True)

    def _build_profiles_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(frame, text="Profiles")
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="New profile", command=self._new_profile).pack(side="left")
        ttk.Button(toolbar, text="Activate", command=self._select_profile).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Export JSON", command=self._export_profile).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Import JSON", command=self._import_profile).pack(side="left", padx=6)
        self.profile_tree = ttk.Treeview(frame, columns=("aircraft", "revision", "cloud", "dirty"), show="tree headings")
        self.profile_tree.heading("#0", text="Profile")
        for key, title, width in (("aircraft", "Aircraft", 180), ("revision", "Local revision", 120), ("cloud", "Cloud revision", 120), ("dirty", "Pending sync", 110)):
            self.profile_tree.heading(key, text=title)
            self.profile_tree.column(key, width=width, stretch=True)
        self.profile_tree.pack(fill="both", expand=True)

    def _build_cloud_tab(self) -> None:
        frame = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(frame, text="Rabta Cloud")
        self.cloud_auth = tk.StringVar(value="https://auth.rabta.dev")
        self.cloud_api = tk.StringVar(value="https://api.rabta.dev")
        self.cloud_project = tk.StringVar()
        self.cloud_key = tk.StringVar()
        self.cloud_email = tk.StringVar()
        self.cloud_password = tk.StringVar()
        fields = (
            ("Rabta Auth URL", self.cloud_auth, False), ("Rabta API URL", self.cloud_api, False),
            ("MuslimSim project ID", self.cloud_project, False), ("Public project key", self.cloud_key, True),
            ("Email", self.cloud_email, False), ("Password", self.cloud_password, True),
        )
        for row, (label, var, secret) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=var, width=72, show="•" if secret else "").grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        frame.columnconfigure(1, weight=1)
        actions = ttk.Frame(frame)
        actions.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(16, 8))
        ttk.Button(actions, text="Save connection", command=self._cloud_configure).pack(side="left")
        ttk.Button(actions, text="Create account", command=self._cloud_signup).pack(side="left", padx=6)
        ttk.Button(actions, text="Sign in", command=self._cloud_login).pack(side="left", padx=6)
        ttk.Button(actions, text="Sync now", command=lambda: self._request("platform_cloud_sync")).pack(side="left", padx=6)
        ttk.Button(actions, text="Sign out", command=lambda: self._request("platform_cloud_logout")).pack(side="left", padx=6)
        self.cloud_status = tk.StringVar(value="Offline-first: local profiles work without a Rabta account.")
        ttk.Label(frame, textvariable=self.cloud_status, wraplength=900, justify="left").grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=8)

    # -------------------------------------------------------------- connection
    def _connector(self) -> None:
        while not self.stop_event.is_set():
            if self.client is None:
                try:
                    locator = read_locator()
                    if locator:
                        from muslimsim.control.client import ControlClient
                        client = ControlClient(int(locator["port"]), str(locator["token"]))
                        if client.ping():
                            self.client = client
                            self.events.put(("connection", "Connected to the private hardware service"))
                            self._request_status()
                except Exception as exc:
                    self.events.put(("connection", f"Waiting for MuslimSim Studio… {exc}"))
                    self.client = None
                self.stop_event.wait(1.0)
                continue
            try:
                response = self.client.request("platform_poll", cursor=self.cursor, timeout=0.75, max_events=512)
                self.events.put(("poll", response))
            except Exception as exc:
                self.events.put(("connection", f"Hardware service disconnected: {exc}"))
                self.client = None
                self.stop_event.wait(0.5)

    def _request(self, command: str, **kwargs: Any) -> None:
        client = self.client
        if client is None:
            self.footer.set("MuslimSim Studio's private hardware service is not connected.")
            return
        def worker() -> None:
            try:
                result = client.request(command, **kwargs)
                self.events.put(("result", (command, result)))
            except Exception as exc:
                self.events.put(("error", f"{command}: {exc}"))
        threading.Thread(target=worker, name=f"PlatformV7-{command}", daemon=True).start()

    def _request_status(self) -> None:
        self._request("platform_status")

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connection":
                    self.connection.set(str(payload))
                elif kind == "poll":
                    self._apply_poll(payload)
                elif kind == "result":
                    command, result = payload
                    self._apply_result(command, result)
                elif kind == "error":
                    self.footer.set(str(payload))
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.after(80, self._drain)

    # -------------------------------------------------------------- rendering
    def _apply_poll(self, response: Mapping[str, Any]) -> None:
        self.cursor = int(response.get("cursor", self.cursor))
        latest = dict(response.get("latest") or {})
        for device, controls in latest.items():
            for control, sample in dict(controls or {}).items():
                iid = f"{device}\0{control}"
                updated = time.strftime("%H:%M:%S", time.localtime(float(sample.get("timestamp", time.time()))))
                values = (str(control), repr(sample.get("value")), sample.get("phase", ""), sample.get("source", ""), sample.get("sequence", ""), updated)
                if self.monitor.exists(iid):
                    self.monitor.item(iid, text=str(device), values=values)
                else:
                    self.monitor.insert("", "end", iid=iid, text=str(device), values=values)
        self.monitor_summary.set(
            f"Physical controls: {response.get('control_count', 0)}  •  Devices: {response.get('device_count', 0)}  •  Sample #{self.cursor}"
        )
        if response.get("events"):
            self._request("platform_learn_status")

    def _apply_result(self, command: str, result: Mapping[str, Any]) -> None:
        if command == "platform_status":
            self.platform = dict(result)
            telemetry = dict(result.get("telemetry") or {})
            self.cursor = max(self.cursor, int(telemetry.get("cursor", 0)))
            self._render_devices(result.get("devices") or [])
            self._render_profiles(dict(result.get("profiles") or {}))
            self._render_cloud(dict(result.get("cloud") or {}))
            self.connection.set(
                f"Connected  •  {dict(result.get('authority') or {}).get('mode', 'live').title()}  •  "
                f"Physical {telemetry.get('control_count', 0)}  •  #{telemetry.get('cursor', 0)}"
            )
        elif command == "platform_devices":
            self._render_devices(result.get("devices") or [])
        elif command in {"platform_set_role", "platform_adopt"}:
            self._request_status()
        elif command == "platform_learn_status":
            self._render_learning(result)
        elif command == "platform_learn_start":
            self._render_learning(result)
            self.footer.set("Learning started. Move exactly one physical control.")
        elif command == "platform_learn_commit":
            self.footer.set("Learned control and assignment saved locally; it is queued for Rabta sync.")
            self._request_status()
        elif command.startswith("platform_profile") or command in {"platform_binding_set", "platform_binding_delete", "platform_calibration_set"}:
            self._request_status()
        elif command.startswith("platform_cloud"):
            self._render_cloud(result if command != "platform_cloud_sync" else dict(self.platform.get("cloud") or {}))
            self.footer.set(f"Rabta operation complete: {command.removeprefix('platform_cloud_')}")
            self._request_status()

    def _render_devices(self, rows: Any) -> None:
        self.device_rows = {str(row.get("adoption_id")): dict(row) for row in rows if isinstance(row, Mapping)}
        current = set(self.devices.get_children())
        desired = set(self.device_rows)
        for iid in current - desired:
            self.devices.delete(iid)
        keys = []
        for iid, row in self.device_rows.items():
            portable = "serial-backed" if row.get("portable_key") else "serial-less / adopted"
            confirmation = "Touch to identify" if row.get("needs_confirmation") else ("Vendor role changed" if row.get("role_change_detected") else "Ready")
            values = (
                row.get("state", "offline"), row.get("assigned_role", "unassigned"),
                row.get("vendor_product", ""), row.get("legacy_key", ""), portable, confirmation,
            )
            if self.devices.exists(iid):
                self.devices.item(iid, text=row.get("friendly_name") or iid, values=values)
            else:
                self.devices.insert("", "end", iid=iid, text=row.get("friendly_name") or iid, values=values)
            if row.get("legacy_key"):
                keys.append(str(row["legacy_key"]))
        self.learn_device_box.configure(values=tuple(sorted(set(keys))))

    def _render_learning(self, result: Mapping[str, Any]) -> None:
        status = str(result.get("status") or "idle")
        selected = result.get("selected")
        self.learn_status.set(f"Learning: {status}" + (f"  •  selected {selected[0]}.{selected[1]}" if selected else ""))
        for item in self.candidates.get_children():
            self.candidates.delete(item)
        for candidate in result.get("candidates") or []:
            self.candidates.insert("", "end", values=(
                f"{candidate.get('device_key')}.{candidate.get('control_key')}",
                f"{float(candidate.get('score', 0)):.1f}", candidate.get("samples", 0),
                ", ".join(candidate.get("phases") or []), candidate.get("kind", ""),
            ))
        if selected and not self.semantic.get():
            self.semantic.set(str(selected[1]))

    def _render_profiles(self, data: Mapping[str, Any]) -> None:
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)
        active = str(dict(data.get("active") or {}).get("profile_id") or "")
        for row in data.get("profiles") or []:
            iid = str(row.get("profile_id"))
            self.profile_tree.insert("", "end", iid=iid, text=("✓ " if iid == active else "") + str(row.get("name")), values=(
                row.get("aircraft", "generic"), row.get("revision", 0), row.get("cloud_revision", 0), "yes" if row.get("dirty") else "no",
            ))

    def _render_cloud(self, data: Mapping[str, Any]) -> None:
        if data.get("signed_in"):
            self.cloud_status.set(
                f"Signed in as {data.get('email') or data.get('user_id')}  •  project {data.get('project_id') or 'not selected'}  •  "
                f"token protection {data.get('token_protection')}"
            )
        else:
            self.cloud_status.set(
                "Not signed in. Local profiles remain fully available. Rabta access/refresh tokens are stored with Windows user DPAPI."
            )

    # --------------------------------------------------------------- actions
    def _device_selected(self, _event: object = None) -> None:
        selected = self.devices.selection()
        if selected:
            self.role.set(str(self.device_rows.get(selected[0], {}).get("assigned_role") or "unassigned"))

    def _set_role(self) -> None:
        selected = self.devices.selection()
        if not selected:
            self.footer.set("Select an adopted device first.")
            return
        self._request("platform_set_role", adoption_id=selected[0], role=self.role.get())

    def _learn_start(self) -> None:
        self._request("platform_learn_start", device_key=self.learn_device.get().strip(), expected_kind=self.learn_kind.get(), timeout=20.0)

    def _learn_commit(self) -> None:
        semantic = self.semantic.get().strip()
        if not semantic:
            self.footer.set("Enter a learned name before saving.")
            return
        try:
            scale = float(self.binding_scale.get())
            deadband = float(self.binding_deadband.get())
        except ValueError:
            self.footer.set("Scale and deadband must be numbers.")
            return
        binding = {
            "kind": self.binding_kind.get(), "target": self.binding_target.get().strip(),
            "invert": self.binding_invert.get(), "scale": scale, "deadband": deadband,
        }
        self._request("platform_learn_commit", semantic_key=semantic, label=semantic, binding=binding)

    def _new_profile(self) -> None:
        name = simpledialog.askstring("New MuslimSim profile", "Profile name:", parent=self)
        if name:
            aircraft = simpledialog.askstring("Aircraft family", "Aircraft/profile family:", initialvalue="zibo", parent=self) or "generic"
            self._request("platform_profile_create", name=name.strip(), aircraft=aircraft.strip(), copy_active=True)

    def _select_profile(self) -> None:
        selected = self.profile_tree.selection()
        if selected:
            self._request("platform_profile_select", profile_id=selected[0])

    def _export_profile(self) -> None:
        client = self.client
        if client is None:
            return
        selected = self.profile_tree.selection()
        def worker() -> None:
            try:
                document = client.request("platform_profile_export", profile_id=selected[0] if selected else "")
                self.events.put(("export", document))
                path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=(("JSON", "*.json"),))
                if path:
                    Path(path).write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
                    self.footer.set(f"Profile exported to {path}")
            except Exception as exc:
                self.events.put(("error", str(exc)))
        # File dialogs must run on Tk's thread; request first in a worker, then
        # enqueue a callback instead of blocking the hardware service.
        def request_only() -> None:
            try:
                document = client.request("platform_profile_export", profile_id=selected[0] if selected else "")
                self.events.put(("callable", lambda: self._save_export(document)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=request_only, daemon=True).start()

    def _save_export(self, document: Mapping[str, Any]) -> None:
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", filetypes=(("JSON", "*.json"),))
        if path:
            Path(path).write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
            self.footer.set(f"Profile exported to {path}")

    def _import_profile(self) -> None:
        path = filedialog.askopenfilename(parent=self, filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not path:
            return
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror("Profile import", str(exc), parent=self)
            return
        self._request("platform_profile_import", document=document, activate=True)

    def _cloud_configure(self) -> None:
        self._request(
            "platform_cloud_configure", auth_base=self.cloud_auth.get(), api_base=self.cloud_api.get(),
            project_id=self.cloud_project.get(), public_api_key=self.cloud_key.get(),
        )

    def _cloud_signup(self) -> None:
        self._cloud_configure()
        self._request("platform_cloud_signup", email=self.cloud_email.get(), password=self.cloud_password.get())

    def _cloud_login(self) -> None:
        self._cloud_configure()
        self._request("platform_cloud_login", email=self.cloud_email.get(), password=self.cloud_password.get())

    def _close(self) -> None:
        self.stop_event.set()
        self.destroy()

    def _drain(self) -> None:  # type: ignore[override]
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connection":
                    self.connection.set(str(payload))
                elif kind == "poll":
                    self._apply_poll(payload)
                elif kind == "result":
                    command, result = payload
                    self._apply_result(command, result)
                elif kind == "error":
                    self.footer.set(str(payload))
                elif kind == "callable":
                    payload()
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.after(80, self._drain)


def main() -> int:
    app = PlatformManager()
    app.mainloop()
    return 0


# >>> MUSLIMSIM_PLATFORM_V7_ASSIGNMENT_TAB >>>
try:
    from .assignment_editor import attach_assignment_tab as _platform_v7_attach_assignment_tab
    _platform_v7_manager_original_init = PlatformManager.__init__

    def _platform_v7_manager_init(self, *args, **kwargs):
        _platform_v7_manager_original_init(self, *args, **kwargs)
        def _attach():
            try:
                editor = _platform_v7_attach_assignment_tab(self)
                if editor is not None:
                    self._platform_v7_assignment_editor = editor
            except Exception as exc:
                status = getattr(self, "status", None) or getattr(self, "footer", None)
                if hasattr(status, "set"):
                    status.set(f"Assign/Reassign tab unavailable: {exc}")
        try:
            self.after_idle(_attach)
        except Exception:
            _attach()

    _platform_v7_manager_init.__name__ = _platform_v7_manager_original_init.__name__
    PlatformManager.__init__ = _platform_v7_manager_init
except Exception:
    # The core manager remains usable if a minimal Tk build cannot load the
    # optional editor. The installer test imports both modules and reports it.
    pass
# <<< MUSLIMSIM_PLATFORM_V7_ASSIGNMENT_TAB <<<

if __name__ == "__main__":
    raise SystemExit(main())
