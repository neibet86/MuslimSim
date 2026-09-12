#!/usr/bin/env python3
"""Run MuslimSim's input-chain self-tests.

No hardware, no simulator, no window.  Every timing test drives a fake clock,
so the suite is deterministic and a slow machine cannot make it flap.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.hardware.chains import (
    Chain,
    ChainContext,
    ChainError,
    ChainRuntime,
    ChainStore,
    STAGE_BY_KIND,
    STAGE_SPECS,
    build_chain,
    preset,
    stages_for,
    wrap_binding_sink,
)


class FakeClock:
    """Time that only moves when a test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, milliseconds: float) -> None:
        self.now += milliseconds / 1000.0


def _runtime(chain: Chain, clock: FakeClock, context: ChainContext | None = None) -> ChainRuntime:
    return ChainRuntime({("dev", "ctl"): chain}, clock=clock, context=context or ChainContext())


def _values(runtime: ChainRuntime, value: float, phase: str = "change") -> list[float]:
    return [emission.value for emission in runtime.run("dev", "ctl", value, phase)]


def _repeats(runtime: ChainRuntime, value: float, phase: str = "change") -> list[int]:
    return [emission.repeat for emission in runtime.run("dev", "ctl", value, phase)]


# --------------------------------------------------------------------------


def test_unconfigured_control_passes_through_unchanged() -> None:
    runtime = ChainRuntime({}, clock=FakeClock())
    emissions = runtime.run("dev", "ctl", 0.42, "change")
    assert len(emissions) == 1
    assert emissions[0].value == 0.42
    assert emissions[0].phase == "change"
    assert emissions[0].repeat == 1


def test_unknown_stage_is_refused_not_skipped() -> None:
    try:
        build_chain([{"kind": "teleport"}])
    except ChainError as exc:
        assert "teleport" in str(exc)
    else:
        raise AssertionError("an unknown stage kind must be refused")


def test_unknown_option_is_refused() -> None:
    try:
        build_chain([{"kind": "debounce", "options": {"milliseconds": 20}}])
    except ChainError as exc:
        assert "milliseconds" in str(exc)
    else:
        raise AssertionError("an unknown option must be refused")


def test_option_out_of_range_is_refused_not_clamped() -> None:
    try:
        build_chain([{"kind": "curve", "options": {"gamma": 99.0}}])
    except ChainError:
        pass
    else:
        raise AssertionError("an out-of-range option must be refused")


def test_impossible_acceleration_is_refused() -> None:
    try:
        build_chain([{"kind": "accelerate", "options": {"fast_ms": 300.0, "slow_ms": 100.0}}])
    except ChainError as exc:
        assert "shorter" in str(exc)
    else:
        raise AssertionError("fast must be shorter than slow")


def test_deadzone_centres_and_rescales() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "deadzone", "options": {"threshold": 0.1}}]), clock)
    assert _values(runtime, 0.05) == [0.0]
    assert abs(_values(runtime, 1.0)[0] - 1.0) < 1e-9
    assert abs(_values(runtime, 0.55)[0] - 0.5) < 1e-9


def test_accumulate_emits_whole_detents_and_carries_remainder() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "accumulate", "options": {"step": 4.0}}]), clock)
    for _ in range(3):
        assert _values(runtime, 1.0) == []          # three of four pulses
    emissions = runtime.run("dev", "ctl", 1.0)      # the fourth completes a detent
    assert [e.value for e in emissions] == [1.0]
    assert emissions[0].repeat == 1
    assert _values(runtime, 1.0) == []              # remainder carried, not replayed


def test_accumulate_handles_reverse_travel() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "accumulate", "options": {"step": 1.0}}]), clock)
    assert _values(runtime, -1.0) == [-1.0]
    assert _values(runtime, -2.0)[0] == -1.0


def test_acceleration_multiplies_a_fast_spin_only() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "accelerate",
                      "options": {"fast_ms": 30.0, "slow_ms": 200.0, "max_multiplier": 8.0}}]),
        clock,
    )
    assert _repeats(runtime, 1.0) == [1]            # first pulse has no interval yet

    clock.advance(500.0)
    assert _repeats(runtime, 1.0) == [1]            # deliberate turn stays one to one

    clock.advance(10.0)
    assert _repeats(runtime, 1.0) == [8]            # hard spin earns the ceiling

    clock.advance(115.0)                            # halfway between fast and slow
    middle = _repeats(runtime, 1.0)[0]
    assert 3 <= middle <= 6, middle


def test_direction_hold_rejects_one_bounce_but_not_a_real_reversal() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "direction_hold",
                      "options": {"reversals": 2, "settle_ms": 250.0}}]),
        clock,
    )
    for _ in range(3):
        clock.advance(20.0)
        assert _values(runtime, 1.0) == [1.0]

    clock.advance(20.0)
    assert _values(runtime, -1.0) == []             # a single bad pulse is swallowed

    clock.advance(20.0)
    assert _values(runtime, -1.0) == [-1.0]         # a genuine reversal gets through

    clock.advance(20.0)
    assert _values(runtime, -1.0) == [-1.0]


def test_direction_hold_lets_a_settled_wheel_change_freely() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "direction_hold",
                      "options": {"reversals": 2, "settle_ms": 200.0}}]),
        clock,
    )
    assert _values(runtime, 1.0) == [1.0]
    clock.advance(400.0)                            # the wheel stopped
    assert _values(runtime, -1.0) == [-1.0]         # so the other way is immediate


def test_debounce_drops_a_bouncing_edge() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "debounce", "options": {"ms": 25.0}}]), clock)
    assert _values(runtime, 1.0) == [1.0]
    clock.advance(5.0)
    assert _values(runtime, 1.0) == []
    clock.advance(30.0)
    assert _values(runtime, 1.0) == [1.0]


def test_latch_flips_on_press_and_swallows_the_release() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "latch"}]), clock)
    assert _values(runtime, 1.0, "press") == [1.0]
    assert _values(runtime, 0.0, "release") == []
    assert _values(runtime, 1.0, "press") == [0.0]


def test_tap_and_hold_are_separated_by_duration() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "tap", "options": {"hold_ms": 500.0}}]), clock)

    assert runtime.run("dev", "ctl", 1.0, "press") == []
    clock.advance(120.0)
    assert runtime.run("dev", "ctl", 0.0, "release")[0].phase == "tap"

    assert runtime.run("dev", "ctl", 1.0, "press") == []
    clock.advance(900.0)
    assert runtime.run("dev", "ctl", 0.0, "release")[0].phase == "hold"


def test_rate_limit_drops_the_excess_and_counts_it() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "ratelimit", "options": {"per_second": 10.0}}]), clock)
    assert _values(runtime, 1.0) == [1.0]
    clock.advance(20.0)
    assert _values(runtime, 1.0) == []
    clock.advance(200.0)
    assert _values(runtime, 1.0) == [1.0]
    assert runtime.snapshot()["dropped"]["dev.ctl"] == 1


def test_when_gates_on_another_control() -> None:
    clock = FakeClock()
    observed = {"other": 0.0}
    context = ChainContext(lambda key: observed.get(key))
    runtime = _runtime(
        build_chain([{"kind": "when",
                      "options": {"key": "other", "min": 0.5, "max": 1.5}}]),
        clock, context,
    )
    assert _values(runtime, 1.0) == []
    observed["other"] = 1.0
    assert _values(runtime, 1.0) == [1.0]


def test_when_blocks_an_unknown_key_by_default() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "when", "options": {"key": "nothing", "min": 0.5, "max": 1.5}}]),
        clock, ChainContext(lambda key: None),
    )
    assert _values(runtime, 1.0) == []


def test_a_layer_button_changes_what_another_control_does() -> None:
    """One physical button turning a nine-button panel into eighteen actions."""
    clock = FakeClock()
    context = ChainContext()
    runtime = ChainRuntime(
        {
            ("dev", "shift"): preset("shift-modifier"),
            ("dev", "ctl"): build_chain(
                [{"kind": "when", "options": {"key": "layer:shift", "min": 0.5, "max": 1.5}}]
            ),
        },
        clock=clock, context=context,
    )

    assert runtime.run("dev", "ctl", 1.0) == []                 # layer down: inert
    assert runtime.run("dev", "shift", 1.0, "press") == []      # modifier swallows itself
    assert context.layers["shift"] is True
    assert [e.value for e in runtime.run("dev", "ctl", 1.0)] == [1.0]

    runtime.run("dev", "shift", 0.0, "release")
    assert context.layers["shift"] is False
    assert runtime.run("dev", "ctl", 1.0) == []


def test_pickup_guard_waits_for_the_axis_to_cross() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "pickup", "options": {"reference": "sim.value"}}]),
        clock, ChainContext(lambda key: 0.5 if key == "sim.value" else None),
    )
    assert _values(runtime, 0.10) == []
    assert _values(runtime, 0.20) == []
    assert _values(runtime, 0.60) == [0.60]         # crossed 0.5, so it takes over
    assert _values(runtime, 0.10) == [0.10]         # and stays armed


def test_hold_to_repeat_needs_the_tick_and_stops_on_release() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "repeat", "options": {"delay_ms": 400.0, "interval_ms": 100.0}}]),
        clock,
    )
    assert _values(runtime, 1.0, "press") == [1.0]
    assert runtime.tick() == []                     # not due yet

    clock.advance(450.0)
    assert len(runtime.tick()) == 1                 # first repeat

    clock.advance(50.0)
    assert runtime.tick() == []

    clock.advance(60.0)
    assert len(runtime.tick()) == 1

    runtime.run("dev", "ctl", 0.0, "release")
    clock.advance(1000.0)
    assert runtime.tick() == []                     # release disarms it


def test_the_fcu_preset_behaves_the_way_a_real_knob_does() -> None:
    clock = FakeClock()
    runtime = _runtime(preset("fcu-altitude-knob"), clock)

    clock.advance(600.0)
    slow = runtime.run("dev", "ctl", 1.0)
    assert [e.repeat for e in slow] == [1]          # one click, one step

    total = 0
    for _ in range(6):
        clock.advance(15.0)                         # a hard spin
        for emission in runtime.run("dev", "ctl", 1.0):
            total += emission.repeat
    assert total > 6, total                         # coarser than one-to-one


def test_wrapper_applies_the_repeat_count_and_honours_the_ceiling() -> None:
    clock = FakeClock()
    runtime = _runtime(
        build_chain([{"kind": "accelerate",
                      "options": {"fast_ms": 30.0, "slow_ms": 200.0, "max_multiplier": 16.0}}]),
        clock,
    )
    calls: list[float] = []

    def inner(device_key, control_key, binding, value, phase):
        calls.append(value)

    sink = wrap_binding_sink(inner, runtime, max_repeat=4)
    sink("dev", "ctl", None, 1.0, "change")
    clock.advance(5.0)
    sink("dev", "ctl", None, 1.0, "change")

    assert len(calls) == 5                          # one, then four rather than sixteen


def test_wrapper_is_transparent_without_a_chain() -> None:
    runtime = ChainRuntime({}, clock=FakeClock())
    seen: list[tuple] = []
    sink = wrap_binding_sink(lambda *a: seen.append(a), runtime)
    sink("dev", "ctl", "binding", 0.75, "change")
    assert seen == [("dev", "ctl", "binding", 0.75, "change")]


def test_reset_forgets_accumulated_state() -> None:
    clock = FakeClock()
    runtime = _runtime(build_chain([{"kind": "accumulate", "options": {"step": 4.0}}]), clock)
    runtime.run("dev", "ctl", 1.0)
    runtime.run("dev", "ctl", 1.0)
    runtime.forget("dev", "ctl")
    for _ in range(3):
        assert _values(runtime, 1.0) == []          # the carried remainder is gone
    assert _values(runtime, 1.0) == [1.0]


def test_palette_only_offers_stages_that_fit_the_control() -> None:
    rotary = {spec.kind for spec in stages_for("rotary")}
    axis = {spec.kind for spec in stages_for("axis")}
    button = {spec.kind for spec in stages_for("button")}

    assert "accumulate" in rotary and "accumulate" not in button
    assert "curve" in axis and "curve" not in rotary
    assert "latch" in button and "latch" not in axis
    assert all(spec.applies_to for spec in STAGE_SPECS)


def test_every_stage_has_a_working_default_chain() -> None:
    """A stage a user can pick must build with nothing filled in."""
    for spec in STAGE_SPECS:
        options = {option.name: option.default for option in spec.options}
        if spec.kind == "when":
            options["key"] = "other"
        if spec.kind == "pickup":
            options["reference"] = "sim.value"
        chain = build_chain([{"kind": spec.kind, "options": options}])
        assert chain.stages[0].kind == spec.kind
        assert STAGE_BY_KIND[spec.kind].label


def test_store_round_trips_and_refuses_a_newer_schema() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "hardware_chains.json"

        store = ChainStore(path)
        store.set_chain("Default", "fcu_efis", "alt_knob", preset("fcu-altitude-knob"))
        store.save()

        reopened = ChainStore(path)
        reopened.load()
        chains = reopened.chains_for("Default")
        assert ("fcu_efis", "alt_knob") in chains
        assert chains[("fcu_efis", "alt_knob")].stages[0].kind == "direction_hold"

        path.write_text('{"schema": 99, "profiles": {}}', encoding="utf-8")
        try:
            ChainStore(path).load()
        except ChainError as exc:
            assert "newer" in str(exc)
        else:
            raise AssertionError("a newer schema must be refused, not opened hopefully")


def test_describe_reads_in_signal_order() -> None:
    assert preset("fcu-altitude-knob").describe() == (
        "reject bounce -> accumulate detents -> acceleration -> rate limit"
    )


# --------------------------------------------------------------------------


def run_self_tests() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    return len(tests)


if __name__ == "__main__":
    count = run_self_tests()
    print(f"Input-chain self-test passed: {count} checks, no hardware or simulator touched.")
