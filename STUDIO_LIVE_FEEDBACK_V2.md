# Studio live feedback V2

## Symptom

Physical panels continued controlling X-Plane, but Studio did not reliably show
buttons, maintained switches, knob activity, LCDs or live panel values. Because
the simulator-dispatch path was healthy, this was not a device-driver failure.

## Audit finding

Every bridge status reply already carried two independent read-only sources:

1. `devices[device].mirror` (when that manager implemented one);
2. `lab.inputs` / `lab.outputs`, the authoritative latest HardwareLab state.

Studio's `_device_mirror()` returned only source 1. Common buttons used only
`_flash_until`, which was created by processing the last 100 diagnostic events.
That history is intentionally bounded and can be evicted by other panel traffic.
The latest state in `lab.inputs` survives that eviction, but the common
faceplates were not using it.

The audit test deliberately generated 150 physical input records: the diagnostic
ring correctly shrank to 100 while the latest physical control state remained
intact. A real `ControlServer`/`ControlClient` round trip then proved both the
LCD mirror and physical input arrive at Studio. The broken boundary was
therefore Studio consumption, not the bridge or simulator route.

## Fix

`muslimsim/gui/live_feedback.py` composes one view without changing authority:

- custom mirror first;
- missing display fields may fall back to top-level/diagnostic status;
- exact lab input/output records are added under `lab_inputs`/`lab_outputs`;
- simple `input_values`/`output_values` are provided for renderers;
- generic `inputs`/`outputs` are filled only where the custom mirror is missing;
- common control drawing reads the physical latest-state directly;
- relative rotaries illuminate briefly from recent physical change;
- FCU maintained selectors are synchronized idempotently from latest state.

## Safety

The module contains no HID/serial/SDL import, no DataRef write, no command
activation and no device output write. It is an observer only. Practice preview
semantics remain unchanged.
## V2 control-channel discovery correction

V2 keeps the V1 read-only Studio composition unchanged and adds one narrowly
scoped bridge-startup correction. `bridge/final.py` already starts the loopback
`ControlServer` before X-Plane, but it used to announce the selected ephemeral
port only after simulator-down practice initialization, including a physical
WinCtrl trim-display write. Studio and the bridge control-channel smoke test
cannot connect until they know that port.

The V2 installer does **not** replace `bridge/final.py`. It edits the live file
in place only when one exact, unique startup ordering is recognized. The three
existing control-channel announcement lines are moved after the in-memory practice wiring and before physical startup I/O, and made `flush=True`. No simulator command/dataref,
HID/SDL/COM owner, device registration, display protocol, timing, mapping,
power rule, or telemetry producer is changed.

The guarded installer AST-parses the result, verifies the announcement is unique
and precedes the first bridge-startup hardware output, runs a dedicated static
ordering test, then runs the existing full bridge control-channel test. Any
validation failure restores both Studio and bridge files from the backup.
