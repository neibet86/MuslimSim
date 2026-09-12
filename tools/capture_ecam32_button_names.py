"""Guided, physical-name capture for the WINCTRL ECAM32 (BB70).

The BB70 reports raw matrix bits.  Packet order does not establish which
Airbus legend is printed above a bit, so this tool asks the owner to press the
18 labelled buttons one at a time and stores only those observed relations.

Studio and the bridge must be closed.  This tool is the sole temporary HID
owner, keeps every capture-proven output at zero, sends the normal blackout on
exit, and then releases the panel.  It never connects to a simulator.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import time
from typing import Iterable, Mapping, Sequence


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.ecam32 import (  # noqa: E402
    ECAM32_A320_CONTROLS,
    ECAM32_PID,
    ECAM32_VID,
    Ecam32RawEvent,
    MuslimSimECAM32,
)
from muslimsim.hardware.profiles import HardwareProfileStore  # noqa: E402


DEVICE_KEY = "ecam32"
CAPTURE_TIMEOUT_SECONDS = 45.0
QUIET_AFTER_RELEASE_SECONDS = 0.25
READY_TIMEOUT_SECONDS = 12.0
CAPTURE_LABEL_OVERRIDES = {
    "ecam_clr_left": "LEFT CLR",
    "ecam_clr_right": "RIGHT CLR",
}


class CaptureError(RuntimeError):
    """The requested map could not be captured or safely persisted."""


def validate_complete_assignments(assignments: Mapping[str, str]) -> dict[str, str]:
    """Return a clean 18-button map, rejecting omissions and duplicate bits."""

    expected = tuple(key for key, _label, _role in ECAM32_A320_CONTROLS)
    missing = [key for key in expected if not str(assignments.get(key) or "").strip()]
    extra = sorted(set(assignments) - set(expected))
    if missing:
        raise CaptureError("Missing ECAM buttons: " + ", ".join(missing))
    if extra:
        raise CaptureError("Unknown ECAM buttons: " + ", ".join(extra))
    cleaned = {key: str(assignments[key]).strip() for key in expected}
    raw_values = tuple(cleaned.values())
    duplicates = sorted({raw for raw in raw_values if raw_values.count(raw) > 1})
    if duplicates:
        raise CaptureError("One physical contact was assigned twice: " + ", ".join(duplicates))
    for raw in raw_values:
        if not raw.startswith("raw_r01_b") or "_bit" not in raw:
            raise CaptureError(f"Invalid BB70 contact name: {raw}")
    return cleaned


def running_muslimsim_processes(root: Path = PROJECT) -> tuple[str, ...]:
    """Fail closed unless Windows confirms that Studio/bridge is not running."""

    if os.name != "nt":
        raise CaptureError("This physical BB70 capture is supported on Windows only.")
    escaped = str(root).replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; $root='" + escaped + "'; "
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -match '^MuslimSim( Studio)?\\.exe$') -or "
        "($_.Name -match '^(python|pythonw|py|pyw)([0-9.]*)\\.exe$' -and $_.CommandLine -and ("
        "$_.CommandLine -like ('*'+$root+'*MuslimSim Studio.pyw*') -or "
        "$_.CommandLine -like ('*'+$root+'*launch.py*') -or "
        "$_.CommandLine -like ('*'+$root+'*launch_msfs24.py*') -or "
        "$_.CommandLine -like ('*'+$root+'*bridge\\final.py*') -or "
        "$_.CommandLine -like ('*'+$root+'*muslimsim_panel.py*'))) } | "
        "ForEach-Object { '{0} {1}' -f $_.ProcessId,$_.Name }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        raise CaptureError(f"Could not verify that Studio is closed: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "Windows process check failed").strip()
        raise CaptureError(f"Could not safely verify that Studio is closed: {detail}")
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def default_profile_paths() -> tuple[Path, ...]:
    """Use every existing MuslimSim aircraft/simulator profile file."""

    root = Path(os.environ.get("APPDATA") or Path.home()) / "MuslimSim"
    existing = tuple(sorted(root.glob("hardware_profiles*.json")))
    return existing or (root / "hardware_profiles.json",)


def _drain(events: "queue.Queue[Ecam32RawEvent]") -> None:
    while True:
        try:
            events.get_nowait()
        except queue.Empty:
            return


def capture_one_contact(
    events: "queue.Queue[Ecam32RawEvent]",
    used: Iterable[str],
    *,
    timeout: float = CAPTURE_TIMEOUT_SECONDS,
) -> str:
    """Capture exactly one press, its release, then a short quiet interval."""

    used_contacts = set(used)
    deadline = time.monotonic() + max(0.2, float(timeout))
    candidate = ""
    while time.monotonic() < deadline:
        remaining = max(0.01, min(0.25, deadline - time.monotonic()))
        try:
            event = events.get(timeout=remaining)
        except queue.Empty:
            continue
        control = str(event.control)
        phase = str(event.phase)
        if not candidate:
            if phase != "press" or int(event.value) != 1:
                continue
            candidate = control
            continue
        if control != candidate:
            raise CaptureError(
                "More than one ECAM contact changed. Release every button and try this name again."
            )
        if phase != "release" or int(event.value) != 0:
            continue

        quiet_until = time.monotonic() + QUIET_AFTER_RELEASE_SECONDS
        while time.monotonic() < quiet_until:
            try:
                extra = events.get(timeout=max(0.01, quiet_until - time.monotonic()))
            except queue.Empty:
                break
            if str(extra.control) != candidate or (
                str(extra.phase) == "press" and int(extra.value) == 1
            ):
                raise CaptureError(
                    "Another contact changed before the panel was quiet. Try this name again."
                )
        if candidate in used_contacts:
            raise CaptureError(
                "That physical button was already assigned. Press the button named by this prompt."
            )
        return candidate
    if candidate:
        raise CaptureError("The press was seen, but its release was not. Release it and try again.")
    raise CaptureError("No ECAM button press was seen before the timer ended.")


def _wait_for_reader(reader: MuslimSimECAM32) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        snapshot = reader.live_snapshot()
        if snapshot.get("status") == "running":
            return
        time.sleep(0.1)
    snapshot = reader.live_snapshot()
    raise CaptureError(str(snapshot.get("detail") or "The ECAM32 did not become ready."))


def _load_profile_stores(paths: Sequence[Path]) -> tuple[HardwareProfileStore, ...]:
    stores: list[HardwareProfileStore] = []
    for path in paths:
        store = HardwareProfileStore(path)
        store.load()
        stores.append(store)
    return tuple(stores)


def save_assignments(
    assignments: Mapping[str, str],
    profile_paths: Sequence[Path],
) -> tuple[Path, ...]:
    """Back up, apply to every named profile, and roll back on any failure."""

    checked = validate_complete_assignments(assignments)
    stores = _load_profile_stores(profile_paths)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backups: dict[Path, Path | None] = {}
    for store in stores:
        path = store.path
        if path.exists():
            backup_dir = path.parent / "Backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"{path.stem}_before_ecam32_names_{stamp}{path.suffix}"
            shutil.copy2(path, backup)
            backups[path] = backup
        else:
            backups[path] = None

    audit_root = stores[0].path.parent
    audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = audit_root / f"ecam32_button_names_{stamp}.json"
    audit_path.write_text(
        json.dumps(
            {
                "device": DEVICE_KEY,
                "captured_at": dt.datetime.now().astimezone().isoformat(),
                "profiles": [str(store.path) for store in stores],
                "assignments": checked,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    try:
        for store in stores:
            for profile_name in store.names():
                for visual_key, raw_control in checked.items():
                    store.set_learned_control(
                        DEVICE_KEY,
                        visual_key,
                        raw_control,
                        profile=profile_name,
                    )
            store.save()
    except Exception:
        for path, backup in backups.items():
            try:
                if backup is None:
                    if path.exists():
                        path.unlink()
                else:
                    shutil.copy2(backup, path)
            except OSError:
                pass
        try:
            audit_path.unlink()
        except OSError:
            pass
        raise
    return tuple(backup for backup in backups.values() if backup is not None) + (audit_path,)


def capture_label(visual_key: str, face_label: str) -> str:
    """Use a single-line, unambiguous name in the command window."""

    return CAPTURE_LABEL_OVERRIDES.get(visual_key, face_label.replace("\n", " "))


def _capture_step_label(index: int, label: str) -> str:
    return f"{index:02d} of {len(ECAM32_A320_CONTROLS):02d}  {label}"


def run_capture(profile_paths: Sequence[Path]) -> int:
    print("")
    print("=" * 72)
    print("  MUSLIMSIM ECAM32 - CORRECT BUTTON-NAME CAPTURE")
    print("=" * 72)
    print("")
    print("This will ask for every labelled ECAM button once.")
    print("The panel stays dark. Nothing is sent to X-Plane or MSFS.")
    print("")
    print("Close MuslimSim Studio completely before continuing.")
    answer = input("Type READY after Studio is closed, or Q to quit: ").strip().upper()
    if answer == "Q":
        print("No changes were made.")
        return 1
    if answer != "READY":
        raise CaptureError("READY was not entered. No changes were made.")

    running = running_muslimsim_processes()
    if running:
        raise CaptureError(
            "Studio or its hardware service is still running: " + ", ".join(running)
            + ". Close it completely, then run this command again."
        )

    # Load and validate every target before claiming the HID or asking for 18
    # presses.  A damaged profile can therefore never waste a complete capture.
    stores = _load_profile_stores(profile_paths)
    print("")
    print("The finished physical map will be used by:")
    for store in stores:
        print(f"  - {store.path.name} ({', '.join(store.names())})")

    try:
        import hid  # type: ignore[import-not-found]
    except Exception as exc:
        raise CaptureError(f"The ECAM HID runtime is not installed: {exc}") from exc
    if not list(hid.enumerate(ECAM32_VID, ECAM32_PID)):
        raise CaptureError("WINCTRL 32 ECAM (BB70) was not found. Connect it and try again.")

    event_queue: "queue.Queue[Ecam32RawEvent]" = queue.Queue()
    reader = MuslimSimECAM32(input_sink=event_queue.put, hid_api=hid)
    assignments: dict[str, str] = {}
    reader.start()
    try:
        _wait_for_reader(reader)
        print("")
        print("ECAM32 is connected and dark.")
        print("For each line: release all buttons, press ENTER, then tap only")
        print("the named physical button once and release it.")
        print("")
        for index, (visual_key, label, _role) in enumerate(ECAM32_A320_CONTROLS, start=1):
            prompt_label = capture_label(visual_key, label)
            while True:
                print("-" * 72)
                print(_capture_step_label(index, prompt_label))
                command = input("Release all ECAM buttons. ENTER = listen, Q = quit: ").strip().upper()
                if command == "Q":
                    print("Capture cancelled. No profile changes were made.")
                    return 1
                _drain(event_queue)
                print(f"NOW TAP {prompt_label} ONCE, THEN RELEASE IT...")
                try:
                    raw = capture_one_contact(event_queue, assignments.values())
                except CaptureError as exc:
                    print(f"NOT ACCEPTED: {exc}")
                    print("This same name will be asked again.")
                    continue
                assignments[visual_key] = raw
                print(f"OK - {prompt_label} captured.")
                break

        checked = validate_complete_assignments(assignments)
        print("")
        print("=" * 72)
        print("  ALL 18 BUTTONS CAPTURED")
        print("=" * 72)
        for key, label, _role in ECAM32_A320_CONTROLS:
            print(f"  {capture_label(key, label):<12} {checked[key]}")
        print("")
        answer = input("Type SAVE to install this map, or anything else to cancel: ").strip().upper()
        if answer != "SAVE":
            print("No profile changes were made.")
            return 1
    finally:
        # The device driver sends every capture-proven OFF packet, closes the
        # HID handle, and never continues fighting another application.
        reader.stop()

    running = running_muslimsim_processes()
    if running:
        raise CaptureError(
            "Studio was opened before saving. Nothing was changed. Close it and run the capture again."
        )
    written = save_assignments(assignments, profile_paths)
    print("")
    print("SUCCESS - the measured ECAM32 button names are installed.")
    print("Backups and the capture record:")
    for path in written:
        print(f"  {path}")
    print("")
    print("You may now start MuslimSim Studio and tap BLEED, ELEC, and the")
    print("other buttons to confirm each matching Studio button responds.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the real BB70 contact behind each ECAM name.")
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Profile JSON to update; repeat for more than one. Default: every existing MuslimSim profile file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Offline import/profile-path check only; does not open hardware or write profiles.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested = tuple(Path(item).expanduser().resolve() for item in args.profile)
    paths = tuple(dict.fromkeys(requested)) or default_profile_paths()
    if args.check:
        validate_complete_assignments({
            key: f"raw_r01_b{index // 8 + 1:02d}_bit{index % 8}"
            for index, (key, _label, _role) in enumerate(ECAM32_A320_CONTROLS)
        })
        print("ECAM32 guided capture check passed.")
        print("Profile targets:")
        for path in paths:
            print(f"  {path}")
        return 0
    return run_capture(paths)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nCapture cancelled. No unconfirmed ECAM map was installed.")
        raise SystemExit(1)
    except (CaptureError, OSError, ValueError) as exc:
        print("")
        print(f"STOPPED SAFELY: {exc}")
        print("No unconfirmed ECAM map was installed.")
        raise SystemExit(2)
