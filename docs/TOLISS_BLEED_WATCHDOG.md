# BLEED centre-valve watchdog — resolved 2026-09-10 (BUG-53)

Requested by the owner: observe whichever source changes the native centre
valve and use the evidence to establish a rule. The later ground-power and
APU-on native screenshots now provide both required orientations: the centre
symbol follows `XBleedInd`, not `APUBleedInd`.

## What ran

`tools/watch_toliss_bleed_valves.py` performed GET-only local X-Plane API reads
every 0.5 seconds for four hours. Its fixed five fields are:

- `AirbusFBW/XBleedInd` and `AirbusFBW/APUBleedInd`: actual indications.
- `AirbusFBW/XBleedSwitch` and `AirbusFBW/APUBleedSwitch`: command positions.
- `AirbusFBW/SDBLEED`: whether the BLEED page is selected.

It resolves IDs once on connection, samples only those fields and refreshes
the catalogue at most once per 30 seconds on reconnect. It logs baseline,
changed values, failures and shutdown, not every identical sample.
Reconnect establishes a fresh baseline rather than inventing a valve edge.

Output: `diagnostics/bleed-watchdog/status.json` and a timestamped
`*_events.jsonl`. Status includes PID, start/last-seen UTC, sample/event counts,
last readings, errors and the `mapping_verified: false` flag. A temporary
two-second smoke test used a separate `smoke-test/` output directory.

The recorder ended normally at 2026-09-10 08:54:01 UTC after 28,753 read-only
samples. Its JSON retains `mapping_verified: false` because the recorder itself
could not inspect pixels; that historical result is not rewritten after later
visual evidence.

## What the evidence can establish

A sole XBleedInd edge is an isolated X BLEED candidate; a sole APUBleedInd
edge is an APU candidate. Both changing is ambiguous. A switch-only change
proves neither the valve position nor the native graphic. The recorder cannot
see the native screen and does not promote any candidate automatically.

The acceptance rule required timestamped native centre-symbol observations in
both orientations, showing which indication it follows. Those observations are
now present. They were obtained during owner-controlled normal operation; the
watchdog never manipulated aircraft controls.

The current renderer uses the now-observed rule: `XBleedInd=0` is the isolated
vertical/closed symbol; `XBleedInd=1` is horizontal/open on the manifold. The
APU branch independently follows `APUBleedInd` and its open valve is vertical
on that vertical pipe. This remains display-only; the watchdog never rewrites
running code, commands the simulator, opens HID/SDL or restarts Studio.

Initial recorded sequence (UTC, 2026-09-10): APU BLEED switch 0→1 at
04:59:02.205; APUBleedInd 0→1 at 04:59:02.669; XBleedInd 0→1 at
04:59:05.211 with XBleedSwitch unchanged at 1. The 2.54-second separation
does not identify the native symbol without a simultaneous visual observation.
Both candidates changing in that old operation was inconclusive by itself.
The owner's later native APU-on screen, paired with read-only values
`APUBleedInd=1` and `XBleedInd=1`, shows the horizontal centre valve and the
separate vertical APU valve. The supplied ground-power screen shows the centre
valve vertical with X BLEED closed. Together they close the orientation audit.

## Stop and safety

The recorder ended automatically after four hours. A file named
`diagnostics/bleed-watchdog/STOP` also requests a clean stop; it is never
deleted automatically. Stop only this diagnostic, not another Python process
or Studio. Disabling the scheduled follow-up does not itself stop the local
recorder; its time limit or STOP file does.

Regression coverage is in `tools/test_toliss_wheel_bleed_details.py` and the
mandatory known-regression suite. Offline full/delta pixel agreement and
candidate-classification tests do not constitute native-cockpit acceptance.
