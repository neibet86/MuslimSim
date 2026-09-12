"""Offline regression checks for the ECAM32 guided name capture."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.ecam32 import ECAM32_A320_CONTROLS, Ecam32RawEvent  # noqa: E402
from muslimsim.hardware.profiles import HardwareProfileStore, MappingBinding  # noqa: E402
from tools.capture_ecam32_button_names import (  # noqa: E402
    CaptureError,
    capture_one_contact,
    save_assignments,
    validate_complete_assignments,
)


def event(control: str, value: int) -> Ecam32RawEvent:
    return Ecam32RawEvent(
        control=control,
        value=value,
        phase="press" if value else "release",
        report_id=1,
        byte_index=1,
        bit_index=1,
    )


def complete_map() -> dict[str, str]:
    return {
        key: f"raw_r01_b{index // 8 + 1:02d}_bit{index % 8}"
        for index, (key, _label, _role) in enumerate(ECAM32_A320_CONTROLS)
    }


def expect_error(callback, text: str) -> None:
    try:
        callback()
    except CaptureError as exc:
        assert text.casefold() in str(exc).casefold(), str(exc)
    else:
        raise AssertionError(f"Expected CaptureError containing {text!r}")


def main() -> int:
    # The original panel had eighteen labelled Airbus contacts.  The
    # owner-provided Ecam Blank capture later proved four additional physical
    # blank keycaps; the guided map must preserve all twenty-two contacts.
    assert len(ECAM32_A320_CONTROLS) == 22
    assert tuple(key for key, _label, _role in ECAM32_A320_CONTROLS[-4:]) == (
        "ecam_blank_1", "ecam_blank_2", "ecam_blank_3", "ecam_blank_4",
    )
    assignments = validate_complete_assignments(complete_map())
    assert len(assignments) == 22

    missing = complete_map()
    missing.pop("ecam_bleed")
    expect_error(lambda: validate_complete_assignments(missing), "missing")
    duplicate = complete_map()
    duplicate["ecam_bleed"] = duplicate["ecam_elec"]
    expect_error(lambda: validate_complete_assignments(duplicate), "twice")

    events: "queue.Queue[Ecam32RawEvent]" = queue.Queue()
    contact = "raw_r01_b02_bit3"
    events.put(event(contact, 1))
    events.put(event(contact, 0))
    assert capture_one_contact(events, (), timeout=0.5) == contact

    duplicate_events: "queue.Queue[Ecam32RawEvent]" = queue.Queue()
    duplicate_events.put(event(contact, 1))
    duplicate_events.put(event(contact, 0))
    expect_error(
        lambda: capture_one_contact(duplicate_events, (contact,), timeout=0.5),
        "already assigned",
    )

    ambiguous: "queue.Queue[Ecam32RawEvent]" = queue.Queue()
    ambiguous.put(event(contact, 1))
    ambiguous.put(event("raw_r01_b02_bit4", 1))
    expect_error(lambda: capture_one_contact(ambiguous, (), timeout=0.5), "more than one")

    root = Path(tempfile.mkdtemp(prefix="muslimsim-ecam32-test-"))
    first_path = root / "hardware_profiles.json"
    second_path = root / "hardware_profiles_msfs24.json"
    first = HardwareProfileStore(first_path)
    first.load()
    first.set_binding(
        "ecam32",
        assignments["ecam_eng"],
        MappingBinding(kind="disabled", simulator="xplane"),
    )
    first.save()
    second = HardwareProfileStore(second_path)
    second.load()
    second.create("Airliner", copy_active=True)
    second.save()

    written = save_assignments(assignments, (first_path, second_path))
    assert len(written) == 3
    assert written[-1].name.startswith("ecam32_button_names_")
    reopened = HardwareProfileStore(first_path)
    reopened.load()
    assert reopened.learned_controls("ecam32") == assignments
    assert reopened.has_binding("ecam32", assignments["ecam_eng"])
    reopened_second = HardwareProfileStore(second_path)
    reopened_second.load()
    for name in reopened_second.names():
        assert reopened_second.learned_controls("ecam32", profile=name) == assignments
    audit = json.loads(written[-1].read_text(encoding="utf-8"))
    assert audit["assignments"] == assignments

    print("ECAM32 guided button capture checks passed: 18 labelled + 4 captured blank contacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
