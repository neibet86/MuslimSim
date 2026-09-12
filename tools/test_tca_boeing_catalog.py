"""Check the TCA Boeing catalogue against the key spelling the bridge uses.

This exists because the mismatch it checks for was completely silent.  The V2
catalogue declared `bank12_button_00` while
`_tca_boeing_control_aliases()` in bridge/final.py looks up
`bank12_button_4` and twelve other unpadded spellings.  Every button lookup
missed, every contact failed to route, and nothing anywhere reported an error:
`_tca_boeing_lab_input()` simply caches the miss and returns None at joystick
poll rate.  The same catalogue described axes 0..2 while the three real levers
are on 3, 4 and 5, so the levers had no entry at all.

A renamed key, a re-padded index, or a lever moved to a different axis would
all reintroduce that silence.  This turns it into a failing test.

No hardware, no simulator, no SDL.

Usage:
    python tools/test_tca_boeing_catalog.py
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import tempfile  # noqa: E402

from muslimsim.hardware.catalog import (  # noqa: E402
    DEFAULT_BINDINGS,
    device_by_key,
)
from muslimsim.hardware.lab import HardwareLab  # noqa: E402
from muslimsim.hardware.profiles import (  # noqa: E402
    HardwareProfileStore,
    MappingBinding,
    validate_binding,
)
from muslimsim.hardware.zibo_library import SAFE_AXIS_FUNCTIONS  # noqa: E402

# The captured truth for the owner's unit, bank 1&2, 2026-08-31.
CAPTURED_AXES = {3: "Left slide", 4: "Middle slide", 5: "Right slide"}
CAPTURED_BUTTONS = {
    1: "Middle slide button",
    2: "Right slide button",
    4: "Middle slide reverse lever",
    5: "Right slide reverse lever",
    6: "Side button 2",
    7: "Side button 3",
    8: "Side button 4",
    9: "Side button 1",
    10: "Side button 5",
    11: "Select knob position 1",
    12: "Select knob position 2",
    13: "Select knob position 3",
    14: "Top knob - counter-clockwise",
    15: "Top knob - clockwise",
    16: "Knob pushbutton",
}
PHANTOM_AXES = (0, 1, 2)


def bridge_alias_spellings(code: str, kind: str, index: int):
    """The first spellings _tca_boeing_control_aliases() tries, in its order.

    Kept as a local copy on purpose: importing bridge/final.py to read the real
    function would pull in 21k lines of module-level bridge setup.  If that
    function's spelling changes, this test must be updated with it -- which is
    the point.  See ``MUSLIMSIM TCA BOEING ONE UNIT LIVE V5`` in bridge/final.py.
    """
    word = "3_4" if code == "34" else "1_2"
    if kind == "axis":
        return (
            f"bank{code}_axis_{index}",
            f"bank_{code}_axis_{index}",
            f"bank_{word}_axis_{index}",
        )
    return (
        f"bank{code}_button_{index}",
        f"bank_{code}_button_{index}",
        f"bank_{word}_button_{index}",
    )


def main() -> int:
    spec = device_by_key("tca_boeing")
    if spec is None:
        print("FAIL: no tca_boeing device in the catalogue", file=sys.stderr)
        return 1

    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    # 1. Every captured control exists under the bridge's own first spelling.
    for index, label in CAPTURED_AXES.items():
        key = bridge_alias_spellings("12", "axis", index)[0]
        control = spec.control(key)
        check(control is not None, f"axis key missing from catalogue: {key}")
        if control is not None:
            check(
                control.status == "implemented",
                f"{key} is '{control.status}', so remappable is False and the "
                f"Studio cannot bind {label}",
            )
            check(control.remappable, f"{key} is not remappable")

    for index, label in CAPTURED_BUTTONS.items():
        key = bridge_alias_spellings("12", "button", index)[0]
        control = spec.control(key)
        check(control is not None, f"button key missing from catalogue: {key}")
        if control is not None:
            check(
                control.status == "implemented",
                f"{key} is '{control.status}', so remappable is False and the "
                f"Studio cannot bind {label}",
            )

    # 2. No key may be zero-padded: the alias chain never tries that spelling.
    for control in spec.controls:
        tail = control.key.rsplit("_", 1)[-1]
        check(
            not (len(tail) > 1 and tail.startswith("0") and tail.isdigit()),
            f"zero-padded key {control.key} can never be looked up by the bridge",
        )

    # 3. The three phantom axes must not be advertised as usable.
    for index in PHANTOM_AXES:
        control = spec.control(f"bank12_axis_{index}")
        check(control is not None, f"bank12_axis_{index} missing")
        if control is not None:
            check(
                control.status != "implemented",
                f"bank12_axis_{index} carries no lever but is marked implemented",
            )

    # 4. The owner's one unit re-enumerates as 1&2 or 3&4. The same captured
    #    SDL identities must remain selectable in either position, but 3&4
    #    receives no guessed aircraft defaults.
    for kind, controls in (("axis", CAPTURED_AXES), ("button", CAPTURED_BUTTONS)):
        for index, label in controls.items():
            key = f"bank34_{kind}_{index}"
            control = spec.control(key)
            check(control is not None, f"{key} missing")
            if control is not None:
                check(
                    control.status == "implemented" and control.remappable,
                    f"{key} cannot be selected when the physical quadrant is "
                    f"set to 3&4 ({label})",
                )

    # 5. The out-of-the-box rules must be real, valid, offerable bindings.
    defaults = DEFAULT_BINDINGS.get("tca_boeing", {})
    check(
        not any(key.startswith("bank34_") for key in defaults),
        "bank 3&4 acquired an invented aircraft default",
    )
    expected = {
        "bank12_axis_3": "laminar/B738/flt_ctrls/speedbrake_lever",
        "bank12_axis_4": "sim/cockpit2/engine/actuators/throttle_ratio_all",
        "bank12_axis_5": "laminar/B738/flt_ctrls/flap_lever",
        "bank12_button_4": "laminar/B738/flt_ctrls/reverse_lever1",
        "bank12_button_5": "laminar/B738/flt_ctrls/reverse_lever2",
    }
    offerable = {item["target"] for item in SAFE_AXIS_FUNCTIONS}
    for key, target in expected.items():
        raw = defaults.get(key)
        check(raw is not None, f"default rule missing for {key}")
        if raw is None:
            continue
        check(
            raw.get("target") == target,
            f"{key} default points at {raw.get('target')!r}, expected {target!r}",
        )
        try:
            validate_binding("tca_boeing", key, MappingBinding(**raw))
        except Exception as exc:
            check(False, f"{key} default is not a valid binding: {exc}")
        control = spec.control(key)
        check(
            control is not None and control.status == "implemented",
            f"{key} has a default rule but is not an implemented control",
        )
        if key.startswith("bank12_axis_"):
            # (1 - raw) * scale must send rest (+1.0) to the safe end and the
            # far end of travel (-1.0) to full.
            check(raw.get("invert") is True, f"{key} default must invert")
            check(
                abs(float(raw.get("scale", 1.0)) - 0.5) < 1e-9,
                f"{key} default scale must be 0.5 for a -1..+1 lever",
            )
            check(
                target in offerable,
                f"{target} is a default but is not in SAFE_AXIS_FUNCTIONS, so "
                f"the owner cannot pick it back after rebinding",
            )

    # 6. Precedence: a saved binding always beats a declared default, an
    #    explicit disable is honoured, and restoring brings the rules back.
    store = HardwareProfileStore(Path(tempfile.mkdtemp()) / "profiles.json")
    lab = HardwareLab(store)
    key = "bank12_axis_4"

    check(
        lab._binding("tca_boeing", key).target == expected[key],
        "a fresh profile does not get the out-of-the-box rule",
    )
    store.set_binding(
        "tca_boeing", key,
        MappingBinding(kind="dataref", target="laminar/B738/axis/throttle1",
                       invert=True, scale=0.5),
    )
    check(
        lab._binding("tca_boeing", key).target == "laminar/B738/axis/throttle1",
        "a saved user binding did not override the default",
    )
    store.set_binding("tca_boeing", key, MappingBinding(kind="disabled"))
    check(
        lab._binding("tca_boeing", key).kind == "disabled",
        "an explicit disable was overridden by the default",
    )
    store.restore_defaults()
    check(
        lab._binding("tca_boeing", key).target == expected[key],
        "restoring the profile did not bring the rules back",
    )

    # 7. No other device may acquire a default from this table: every one of
    #    them still falls through to its own bridge dispatcher.
    check(
        set(DEFAULT_BINDINGS) == {"tca_boeing"},
        "DEFAULT_BINDINGS names a device other than tca_boeing, which changes "
        "the meaning of an absent binding for hardware that has a dispatcher",
    )
    check(
        lab._binding("pap3_mag", "n1").kind == "disabled",
        "pap3_mag gained a default binding it should not have",
    )

    if failures:
        print("TCA Boeing catalogue self-test FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1

    print(
        "TCA Boeing catalogue self-test passed: %d checks. Every captured "
        "control resolves under the bridge's alias spelling, the out-of-the-box "
        "rules are valid bindings, and a saved binding still beats them. "
        "No hardware or simulator touched." % checks
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
