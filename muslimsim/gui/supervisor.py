"""Own the bridge as a child process and keep its output off Tk's thread."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import queue
import re
import secrets
import subprocess
import sys
import threading
from typing import Optional

from ..control.client import ControlClient, ControlClientError


_PORT_LINE = re.compile(r"^CONTROL CHANNEL PORT\s+(\d+)\s*$")
SIMULATOR_XPLANE = "xplane"
SIMULATOR_MSFS24 = "msfs24"
_SIMULATORS = frozenset({SIMULATOR_XPLANE, SIMULATOR_MSFS24})
from ..hardware.msfs24_aircraft import (
    MSFS24_AIRCRAFT_KEYS, MSFS24_DEFAULT_AIRCRAFT,
)

AIRCRAFT_ZIBO = "zibo"
AIRCRAFT_LEVELUP = "levelup"
AIRCRAFT_TOLISS = "toliss"
AIRCRAFT_C172_NG = "c172ng"
_XPLANE_AIRCRAFT = frozenset({
    AIRCRAFT_ZIBO, AIRCRAFT_LEVELUP, AIRCRAFT_TOLISS, AIRCRAFT_C172_NG,
})


class _WindowsChildJob:
    """Keep every bridge child tied to the lifetime of the Studio process."""

    _KILL_ON_JOB_CLOSE = 0x00002000
    _EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self) -> None:
        self.handle = None
        self._kernel32 = None
        if os.name != "nt":
            return

        from ctypes import wintypes

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        limits = _ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            handle,
            self._EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            kernel32.CloseHandle(handle)
            return
        self._kernel32 = kernel32
        self.handle = handle

    def assign(self, process: subprocess.Popen[str]) -> bool:
        if self.handle is None or self._kernel32 is None:
            return os.name != "nt"
        process_handle = getattr(process, "_handle", None)
        if process_handle is None:
            return False
        return bool(
            self._kernel32.AssignProcessToJobObject(
                self.handle, process_handle
            )
        )


def _normalise_simulator(value: str) -> str:
    simulator = str(value or "").strip().casefold()
    if simulator not in _SIMULATORS:
        raise ValueError("Simulator must be 'xplane' or 'msfs24'")
    return simulator


def _normalise_xplane_aircraft(value: str) -> str:
    aircraft = str(value or "").strip().casefold()
    if aircraft not in _XPLANE_AIRCRAFT:
        raise ValueError("X-Plane aircraft must be zibo, levelup, toliss, or c172ng")
    return aircraft


def _normalise_msfs24_aircraft(value: str) -> str:
    aircraft = str(value or "").strip().casefold()
    if aircraft not in MSFS24_AIRCRAFT_KEYS:
        raise ValueError("Unknown MSFS 2024 aircraft")
    return aircraft


def default_profile_path(
    simulator: str = SIMULATOR_XPLANE,
    aircraft: str = AIRCRAFT_ZIBO,
    msfs_aircraft: str = MSFS24_DEFAULT_AIRCRAFT,
) -> Path:
    root = Path(os.environ.get("APPDATA") or Path.home()) / "MuslimSim"
    if _normalise_simulator(simulator) == SIMULATOR_MSFS24:
        selected_msfs = _normalise_msfs24_aircraft(msfs_aircraft)
        if selected_msfs == MSFS24_DEFAULT_AIRCRAFT:
            # Keep the existing MSFS profile file exactly where it was.
            return root / "hardware_profiles_msfs24.json"
        return root / f"hardware_profiles_msfs24_{selected_msfs}.json"
    selected = _normalise_xplane_aircraft(aircraft)
    if selected == AIRCRAFT_ZIBO:
        # Keep the existing Zibo profile file exactly where it was.
        return root / "hardware_profiles.json"
    return root / f"hardware_profiles_{selected}.json"


class BridgeSupervisor:
    """Starts a bridge process; no HID/serial/simulator code reaches the GUI."""

    def __init__(
        self,
        *,
        profile_path: Optional[Path] = None,
        simulator: str = SIMULATOR_XPLANE,
        aircraft: str = AIRCRAFT_ZIBO,
        msfs_aircraft: str = MSFS24_DEFAULT_AIRCRAFT,
    ) -> None:
        self._profile_override = Path(profile_path) if profile_path is not None else None
        self._simulator = _normalise_simulator(simulator)
        self._aircraft = _normalise_xplane_aircraft(aircraft)
        self._msfs_aircraft = _normalise_msfs24_aircraft(msfs_aircraft)
        self.profile_path = self._profile_path_for(
            self._simulator, self._aircraft, self._msfs_aircraft,
        )
        self._seed_msfs_profile_if_new(
            self._simulator, self._aircraft, self._msfs_aircraft, self.profile_path,
        )
        self.output: "queue.Queue[str]" = queue.Queue()
        self._state_lock = threading.RLock()
        self._process: Optional[subprocess.Popen[str]] = None
        self._token = ""
        self._port: Optional[int] = None
        self._reader: Optional[threading.Thread] = None
        self._recovering = False
        self._allow_recovery = True
        self._child_job = _WindowsChildJob()

    @property
    def simulator(self) -> str:
        with self._state_lock:
            return self._simulator

    @property
    def aircraft(self) -> str:
        with self._state_lock:
            return self._aircraft

    def _seed_msfs_profile_if_new(
        self, simulator: str, aircraft: str, msfs_aircraft: str, path: Path,
    ) -> None:
        """A first-time MSFS workspace inherits its family siblings' mappings.

        Only ever runs when the profile file does not exist yet, so it can
        never overwrite saved work, and only within one catalogue family, where
        the target function provably exists on the other airframe.  After this
        the workspace is fully independent: editing the A321 never changes the
        A320 again.
        """

        if simulator != SIMULATOR_MSFS24 or Path(path).exists():
            return
        try:
            from ..hardware.mapping_transfer import seed_msfs24_profile
            from ..hardware.msfs24_aircraft import MSFS24_AIRCRAFT

            siblings = {
                item.key: self._profile_path_for(SIMULATOR_MSFS24, aircraft, item.key)
                for item in MSFS24_AIRCRAFT
            }
            seed_msfs24_profile(Path(path), msfs_aircraft, siblings)
        except Exception:
            # Inheritance is a convenience. A workspace must still open when it
            # cannot be seeded.
            pass

    @property
    def msfs_aircraft(self) -> str:
        with self._state_lock:
            return self._msfs_aircraft

    def _profile_path_for(
        self, simulator: str, aircraft: str,
        msfs_aircraft: str = MSFS24_DEFAULT_AIRCRAFT,
    ) -> Path:
        simulator = _normalise_simulator(simulator)
        aircraft = _normalise_xplane_aircraft(aircraft)
        msfs_aircraft = _normalise_msfs24_aircraft(msfs_aircraft)
        if self._profile_override is None:
            return default_profile_path(simulator, aircraft, msfs_aircraft)
        if simulator == SIMULATOR_XPLANE:
            if aircraft == AIRCRAFT_ZIBO:
                return self._profile_override
            suffix = self._profile_override.suffix or ".json"
            return self._profile_override.with_name(f"{self._profile_override.stem}_{aircraft}{suffix}")
        suffix = self._profile_override.suffix or ".json"
        if msfs_aircraft == MSFS24_DEFAULT_AIRCRAFT:
            return self._profile_override.with_name(f"{self._profile_override.stem}_msfs24{suffix}")
        return self._profile_override.with_name(
            f"{self._profile_override.stem}_msfs24_{msfs_aircraft}{suffix}"
        )

    @property
    def running(self) -> bool:
        with self._state_lock:
            process = self._process
        return process is not None and process.poll() is None

    @property
    def recovering(self) -> bool:
        """True only while Studio is quietly replacing its own bridge child."""

        with self._state_lock:
            return self._recovering

    @property
    def client(self) -> Optional[ControlClient]:
        with self._state_lock:
            process = self._process
            port = self._port
            token = self._token
        # A finished child leaves its last loopback port number in memory.
        # Never hand that stale address back to Studio: doing so keeps the UI
        # polling a dead socket and prevents its existing exited-child restart
        # path from launching the next bridge generation.
        if (
            process is None
            or process.poll() is not None
            or port is None
            or not token
        ):
            return None
        # A status response includes the live state of every active device.
        # During the first few seconds after X-Plane connects, a display
        # worker can legitimately be finishing one HID/serial transaction.
        # Give that snapshot a modest, bounded window instead of mistaking a
        # slow picture for a dead bridge and replaying every device startup.
        return ControlClient(port, token, timeout=8.0)

    def start(self) -> None:
        with self._state_lock:
            self._allow_recovery = True
            process = self._process
            if process is not None and process.poll() is None:
                return
            self._launch_locked()

    def _launch_locked(self) -> None:
        """Launch a child while holding ``_state_lock``.

        The reader receives the exact process instance.  An old reader can
        therefore never publish its old control port after a recovery has
        already started a new bridge.
        """

        self._token = secrets.token_urlsafe(24)
        self._port = None
        root = Path(__file__).resolve().parents[2]
        launcher = root / (
            "launch_msfs24.py" if self._simulator == SIMULATOR_MSFS24 else "launch.py"
        )
        # Studio may use a UI-only Python distribution when the normal
        # hardware runtime has a damaged Tk installation.  The bridge must
        # still use the original runtime because it owns hidapi, serial and
        # websocket support.  The launcher supplies this explicit path only
        # for that recovery case.
        configured_runtime = Path(os.environ.get("MUSLIMSIM_BRIDGE_PYTHON", ""))
        default_runtime = Path(sys.executable)
        if os.name == "nt" and default_runtime.name.casefold() == "pythonw.exe":
            # Keep Studio itself on pythonw, but run its hidden hardware child
            # with the console-capable sibling runtime.  Several of the PU
            # overhead's SDL/DirectInput interfaces never deliver switch
            # changes when their process image is pythonw.exe even though the
            # same installed Python and pygame build works through python.exe.
            # CREATE_NO_WINDOW + SW_HIDE below still guarantees that no
            # command window is shown to the user.
            console_runtime = default_runtime.with_name("python.exe")
            if console_runtime.is_file():
                default_runtime = console_runtime
        bridge_runtime = (
            str(configured_runtime)
            if configured_runtime.is_file()
            else str(default_runtime)
        )
        command = [
            # The bridge reports its loopback port before waiting for X-Plane.
            # Unbuffered stdout lets the panel discover it in simulator-down mode.
            bridge_runtime, "-u", "-B", str(launcher),
            "--control-port=0", f"--control-token={self._token}",
            f"--lab-profile={self.profile_path}",
        ]
        if self._simulator == SIMULATOR_XPLANE:
            # This does not force an aircraft in the simulator. The X-Plane
            # bridge still detects the loaded aircraft before accepting a
            # mapping; the flag chooses only Studio's isolated profile and
            # function library.
            command.extend((
                f"--mapping-aircraft={self._aircraft}",
                # The PFP is a normal Studio-owned live display. Omitting
                # this left BB35 stopped unless a separate bridge was started
                # manually outside Studio.
                "--with-pfd",
                # The controlled routers draw their own first frame. Avoid a
                # soft reboot that can race their first HID session and flash
                # the real PFP/MCDU screens when Studio opens.
                "--no-display-startup-refresh",
                # MOZA A210 yoke -> X-Plane native joystick-axis assignment
                # (see bridge/final.py's MUSLIMSIM MOZA A210 NATIVE
                # AXIS-ASSIGNMENT V1). Off by default in the bridge's own
                # argparse since it is a no-op without a MOZA A210 present,
                # but Studio's own launch must actually request it - the
                # owner's whole point was automatic, not a manual
                # command-line flag they have to remember every launch.
                "--moza-yoke",
                # MOZA AY210 real force-feedback output (see
                # moza_ay210_ffb_engine.py's module docstring - all four
                # effect types plus the physics gain family are physically
                # confirmed). Same reasoning as --moza-yoke just above: off
                # by default in the bridge's own argparse, a graceful no-op
                # (a caught, logged warning, nothing crashes) when no AY210
                # is connected, but Studio's own launch must request it so
                # the FFB panel it now draws is ever reachable without a
                # separately hand-launched bridge process - which the
                # bridge's own single-instance mutex refuses anyway once
                # Studio's own child is already running.
                "--moza-ffb",
            ))
        # The desktop studio owns all status/progress presentation.  Its
        # bridge must never flash a second command window in front of the UI.
        creation_flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen(
            command,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creation_flags,
            startupinfo=startupinfo,
        )
        self._child_job.assign(process)
        self._process = process
        self._reader = threading.Thread(
            target=self._read_output,
            args=(process,),
            name="MuslimSim-Bridge-Output",
            daemon=True,
        )
        self._reader.start()

    def request_simulator_change(self, simulator: str) -> bool:
        """Change simulator on a worker, keeping the Tk event loop free."""

        return self.request_workspace_change(simulator, self.aircraft)

    def request_aircraft_change(self, aircraft: str) -> bool:
        """Change the X-Plane mapping workspace without blocking Studio."""

        return self.request_workspace_change(SIMULATOR_XPLANE, aircraft)

    def request_msfs24_aircraft_change(self, msfs_aircraft: str) -> bool:
        """Change the MSFS 2024 mapping workspace without blocking Studio."""

        return self.request_workspace_change(
            SIMULATOR_MSFS24, self.aircraft, msfs_aircraft,
        )

    def request_workspace_change(
        self, simulator: str, aircraft: str,
        msfs_aircraft: Optional[str] = None,
    ) -> bool:
        """Replace the child for one isolated simulator/aircraft workspace.

        ``msfs_aircraft`` defaults to the airframe already selected, so every
        existing two-argument caller keeps behaving exactly as it did.
        """

        wanted = _normalise_simulator(simulator)
        wanted_aircraft = _normalise_xplane_aircraft(aircraft)
        wanted_msfs = _normalise_msfs24_aircraft(
            self.msfs_aircraft if msfs_aircraft is None else msfs_aircraft
        )
        with self._state_lock:
            if self._recovering:
                return False
            same_workspace = (
                wanted_msfs == self._msfs_aircraft
                if wanted == SIMULATOR_MSFS24
                else wanted_aircraft == self._aircraft
            )
            if wanted == self._simulator and same_workspace and self.running:
                return False
            self._recovering = True
        threading.Thread(
            target=self._switch_simulator_child,
            args=(wanted, wanted_aircraft, wanted_msfs),
            name="MuslimSim-Workspace-Switch",
            daemon=True,
        ).start()
        return True

    def _switch_simulator_child(
        self, simulator: str, aircraft: str,
        msfs_aircraft: str = MSFS24_DEFAULT_AIRCRAFT,
    ) -> None:
        with self._state_lock:
            process = self._process
        if process is not None:
            self._terminate_process(process)
        with self._state_lock:
            if self._process is process:
                self._process = None
                self._port = None
            self._simulator = simulator
            self._aircraft = aircraft
            self._msfs_aircraft = msfs_aircraft
            self.profile_path = self._profile_path_for(simulator, aircraft, msfs_aircraft)
            self._seed_msfs_profile_if_new(
                simulator, aircraft, msfs_aircraft, self.profile_path,
            )
            try:
                if self._allow_recovery:
                    self._launch_locked()
            finally:
                self._recovering = False

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for raw in process.stdout:
            line = raw.rstrip()
            match = _PORT_LINE.match(line)
            if match:
                with self._state_lock:
                    if self._process is process:
                        self._port = int(match.group(1))
            self.output.put(line)

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        """Stop an owned child only; never touch a user-owned bridge."""

        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    def request_recovery(self) -> bool:
        """Replace an unresponsive child without pausing Tk's event loop.

        This is deliberately a single-flight operation.  Status polling can
        produce several timeouts while one USB driver is wedged; they must not
        create several bridge processes or flash a console window.
        """

        with self._state_lock:
            if not self._allow_recovery or self._recovering:
                return False
            self._recovering = True
        threading.Thread(
            target=self._recover_child,
            name="MuslimSim-Bridge-Recovery",
            daemon=True,
        ).start()
        return True

    def _recover_child(self) -> None:
        with self._state_lock:
            process = self._process
        if process is not None:
            self._terminate_process(process)
        with self._state_lock:
            if self._process is process:
                self._process = None
                self._port = None
            try:
                if self._allow_recovery:
                    self._launch_locked()
            finally:
                self._recovering = False

    def drain_output(self) -> list[str]:
        lines: list[str] = []
        while True:
            try:
                lines.append(self.output.get_nowait())
            except queue.Empty:
                return lines

    def stop(self) -> None:
        with self._state_lock:
            self._allow_recovery = False
            process = self._process
        if process is None:
            return
        client = self.client
        if client is not None:
            try:
                client.request("shutdown")
                process.wait(timeout=3.0)
            except (ControlClientError, subprocess.TimeoutExpired):
                pass
        self._terminate_process(process)
        with self._state_lock:
            if self._process is process:
                self._process = None
                self._port = None
