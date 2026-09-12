"""Report, per device, whether Practice mode actually reaches physical output.

Reads only.  It drives the real HardwareLab in Test mode and routes its
practice snapshot through the real ControlServer.apply_practice_snapshot, with
apply_lab_output replaced by a recorder.  The answer is therefore the shipping
code path's own behaviour, not a reading of it.

Three things are measured separately, because they fail separately:

  model    the practice cockpit model (VirtualZiboPreview) carries state for
           this device at all
  reacts   exercising one of the device's own controls changes that state
  posts    a physical output write is actually produced for the device

No hardware, simulator, HID handle or profile file is opened or written.
"""

from __future__ import annotations

from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muslimsim.control.server import ControlServer
from muslimsim.hardware.catalog import ALL_HARDWARE
from muslimsim.hardware.lab import HardwareLab, LabError


def main() -> None:
    lab = HardwareLab()
    server = ControlServer.__new__(ControlServer)
    server._lock = threading.RLock()
    server._practice_signature = None

    written: list[tuple[str, str]] = []

    def record(device_key, control_key, value, source="probe"):
        written.append((str(device_key), str(control_key)))

    server.apply_lab_output = record
    lab.set_practice_output_sink(server.apply_practice_snapshot)
    lab.set_mode("test")

    rows = []
    for item in ALL_HARDWARE:
        device = item.key
        inputs = [
            c for c in item.controls
            if c.is_input and c.status == "implemented"
        ]
        outputs = [c for c in item.controls if c.is_output]

        modelled = device in lab.practice_snapshot()
        before_state = repr(lab.practice_snapshot().get(device))

        written.clear()
        for control in inputs[:40]:
            try:
                lab.input(
                    device, control.key, 1.0,
                    phase="press", source="probe", route=False,
                )
            except LabError:
                continue

        reacts = repr(lab.practice_snapshot().get(device)) != before_state
        posts = sorted({control for dev, control in written if dev == device})

        # Opening the device's page is the other way to ask it to respond, and
        # for a device with no catalogued input it is the only way.
        written.clear()
        try:
            lab.practice_wake(device)
        except LabError:
            pass
        page = sorted({control for dev, control in written if dev == device})
        posts = sorted(set(posts) | set(page))

        rows.append((device, len(inputs), len(outputs), modelled, reacts, posts))

    width = max(len(row[0]) for row in rows)
    print(
        f"{'device'.ljust(width)}  inputs  outputs  model  reacts  "
        "posts (physical writes produced)"
    )
    print("-" * (width + 62))

    def mark(flag: bool) -> str:
        return " yes " if flag else "  -  "

    silent = []
    for device, n_in, n_out, modelled, reacts, posts in rows:
        print(
            f"{device.ljust(width)}  {n_in:6d}  {n_out:7d}  "
            f"{mark(modelled)}  {mark(reacts)}   "
            f"{', '.join(posts) if posts else '(nothing)'}"
        )
        if not posts:
            silent.append((device, n_out))

    print()
    print(f"{len(rows)} catalogued devices.")
    print(
        f"{len(silent)} produce no physical output at all when their own "
        "controls are exercised in Practice:"
    )
    for device, n_out in silent:
        note = (
            f"{n_out} output control(s) that stay dark"
            if n_out
            else "input-only device"
        )
        print(f"  - {device.ljust(width)} {note}")


if __name__ == "__main__":
    main()
