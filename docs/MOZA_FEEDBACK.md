# MuslimSim feedback for A210 and AB6

Select the connected base in Studio and open **FEEDBACK & TESTS —
ROLL / PITCH / VIBRATION**, below the preset selector.

## Tests with the simulator off

Keep other force-control applications and the isolated bench windows closed.
Opening this page does not start output. A reconnect countdown may appear
before setup; the test timer starts when output begins.

On **Hardware tests**, set the roll/pitch targets and movement strength, then
choose **Test roll**, **Test pitch**, or **Test diagonal**. Targets cover the
full tested travel range; they are not measured degrees. Sliders update an
active test without extending its deadline. **Return to centre** explicitly
starts a centering request when no movement test is running.

Choose a vibration pattern and strength, then **Test vibration**. A210 exposes
its captured patterns; AB6 exposes its own runway-rumble and gear-bump patterns.
Constant push remains a separate signed-force test, with physical orientation
still requiring confirmation on AB6.

On **Test resistance**, each spring, damper, friction and inertia slider has its
own test button. Move the control to feel the selected resistance. Dedicated
damping/friction/inertia use the stronger combination confirmed on the bench,
with coefficients up to 32000 and temporary overall intensity 100%. The original
overall setting and resistance settings return afterward. The optional fixed
preset settings override these resistance sliders when explicitly selected.
Movement uses its tested spring/travel setup independently of resistance tests.

New-window strength defaults are 100%. Existing saved test values stay as saved;
check the displayed percentages when comparing Studio with the 100% bench test.
Each test lasts at most five seconds. **STOP ALL FEEDBACK**, closing the window,
lost window contact or expiry ends output and restores original base settings.
Position tests may relax toward the normal resting position after output stops.

## Presets and flight feedback

**Browse** imports a .mslm file and starts in the selected base's preset folder:

- A210: `%APPDATA%\MuslimSim\ffb_profiles`
- AB6: `%APPDATA%\MuslimSim\ffb_profiles_moza_ab6`

**New** creates a starter. **Flight effects** edits enabled effects, strengths,
patterns, triggers and curves. **Resistance** edits supported flight resistance
fields. Leaving a dynamic field unchecked preserves its aircraft-driven curve.
**Full preset** exposes the complete document. **Apply changes** updates the draft;
**Save** writes it, including test settings; **Save As** creates another preset.
Existing saves are backed up under `%APPDATA%\MuslimSim\ffb_backups`.
Hardware assignments remain independent.

**Enable flight feedback** runs the existing aircraft-driven preset when power
and telemetry are readable. Manual test settings do not automatically become
flight forces. Studio physical checks come first; transferring the tested feel
into each aircraft's curves and verifying in-flight response remains a separate
tuning step. Do not assume a preset name certifies its physical response.

## Implementation and validation

MuslimSim uses its own bridge, protocol library and capture-tested output code.
No vendor SDK code, binaries or assets were copied or added. Each base retains
one output owner; the manual test session never reads joystick HID reports.

Offline transport/lifecycle guards and the full known-regression suite pass.
Real Tk tests cover both windows and their routes. Bench-confirmed physical
results include A210 roll/pitch travel and AB6 pitch travel, right roll, one
diagonal, vibration and improved damping/friction/inertia. The stronger AB6
inertia setting was accepted by the owner. Studio physical results and flight
latency/feel must still be confirmed separately.

Constant-push strength is independent of Movement strength: its signed slider alone spans -32000 to +32000. Diagnostics expose the requested magnitude for the last test.

**Constant push warning:** The first push can be strong. Keep your hands on the yoke/control stick throughout the test. Clicking Test starts a three-second countdown before output. Stop or closing the window cancels the countdown.
