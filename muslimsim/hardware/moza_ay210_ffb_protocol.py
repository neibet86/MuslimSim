"""Shared MOZA AY210 force-feedback protocol layer - no MOZA SDK, no FFB-Bridge.

This module is the single source of truth for every byte this project has
proven works on the real AY210 hardware. It exists so
`tools/probe_moza_ay210_ffb_bench.py` (the standalone bench-verification
script) and the live bridge FFB engine never carry two independently-drifting
copies of the same hard-won protocol.

See `tools/probe_moza_ay210_ffb_bench.py`'s own module docstring for the full
story of how this was found, and `BUG_REGISTER.md`'s BUG-21 tenth follow-up
for the complete narrative (including two real bugs caught during
development: a background poll loop that accidentally re-sent one-time
commands every cycle, and a stale-serial-buffer race in connect detection -
both cautionary examples for anything built on top of this module).

Confirmed-working mechanism, in order:
  1. CDC serial (Windows COM port on the same VID/PID) - a periodic poll
     pattern that must run continuously (the connection is dropped, and the
     firmware logs a real "Host Disconnect", if it stops), which is also
     what makes the firmware log "Host Connecting" -> "Host Connected".
  2. A one-time serial write of param 0x85 = 1 (ENABLE_FFB_COMMAND), sent
     once per power cycle after Host Connected - a persistent latch
     (confirmed idempotent: resending it once already-armed produces no
     further log line and no adverse effect).
  3. HID interrupt OUT - a reset-then-arm sequence (part of
     CONNECTION_SETUP_SEQUENCE)
     immediately before any Condition/Periodic/Constant-Force report is
     honored, plus the six SET_REPORT Feature reports
     (FEATURE_REPORT_SEQUENCE) that define the effect blocks.
Only after all three does a Condition-report (0x13) coefficient change,
Periodic-report (0x14) magnitude, or Constant-Force (0x15) magnitude
actually move the motor - before that, every write is fully acknowledged in
the firmware's own debug log and produces zero physical force.

Physically confirmed so far: the spring/condition effect only, and only
under exact byte-for-byte replay of one real capture. The encoder functions
below (`build_set_condition`/`build_set_periodic`/`build_constant_force`)
let a caller compute NEW values instead of replaying fixed ones - before
trusting one for a genuinely new value, confirm it reproduces a known
captured packet byte-for-byte first (see each function's docstring for the
exact reference packet to check against).
"""

from __future__ import annotations

import threading
import time
from typing import List, Optional, Tuple

try:
    import hid
except ImportError:  # pragma: no cover - optional dependency
    hid = None

try:
    import serial
except ImportError:  # pragma: no cover - optional dependency
    serial = None

VID = 0x346E
PID = 0x1001
DEFAULT_SERIAL_PORT = "COM4"
SERIAL_BAUD = 115200

# ---------------------------------------------------------------------------
# One-time per-connection commands
# ---------------------------------------------------------------------------

# The persistent per-power-cycle "force feedback active" latch (serial param
# 0x85 = 1). Ties directly, in the firmware's own log, to
# "steer set mode: 1" -> "Table 7, Param 49 Written: 1" -> "steer set mode:
# 2". Idempotent: resending it while already in mode 2 produces no further
# log line and no adverse effect - always send it after observing
# "Host Connected", never try to track "did I already do this" state
# yourself (see BUG_REGISTER.md tenth follow-up for why that's actively
# dangerous across a physical replug).
ENABLE_FFB_COMMAND = "7e031f1285000145"
DISARM_GAIN_COMMAND = "7e031f1299000058"

# A real 100%-setting FFB-Bridge flight capture ("100%.pcapng") revealed a
# whole family of percentage-style gain parameters this project had never
# written before - CONNECTION_SETUP_SEQUENCE only ever zeroes "af" (Table 7
# Param 15, one of the four condition params af/b0/b1/b2) and never
# revisits it, but real FFB-Bridge usage sets it to a real value (0.25)
# during normal flight. Confirmed on real hardware: 'af' set to 1.0 (100)
# is a genuine force-gain multiplier, independent of the raw
# build_set_condition() coefficient field - a fixed 12000 coefficient felt
# unmistakably stiffer with af=1.0 than without, and af=1.0 combined with
# the proven-comfortable 28000 coefficient ceiling was step-tested "strong
# but comfortable," not excessive. Timing in the real capture (values set
# once at what looked like a profile-load moment, never continuously
# adjusted mid-flight) suggests this is a per-profile calibration constant
# FFB-Bridge sets once per aircraft/effect, not a live tunable knob - so
# `.mslm` exposes it the same way (see ffb_profiles.py's spring
# 'extra_gain' option), applied once per connection, not every tick.
#
# A related family, 'da' + a one-byte index (00-03, Table 8 Params 16-19),
# was also found and step-tested individually - da02/da03 showed up as
# 0.70 in the same real capture, but isolated single-parameter step tests
# on real hardware could not distinguish any of the four from ordinary
# push-to-push variability (unlike 'af', which was unambiguous). Left
# unimplemented pending a more controlled measurement.
#
# Checksum formula, independently verified against 8 real captured
# examples (ENABLE_FFB_COMMAND, the gain-arm write, both 'af' writes, and
# all four 'da' writes - every one lands on the exact same offset):
#     checksum = (0x7e + 0x03 + 0x1f + 0x12 + param + index + value + 13) & 0xFF
#
# A second capture session (live MOZA Cockpit, one Basic Settings /
# Physics Model Settings slider changed at a time, each change correlated
# to its own "Table N, Param M Written" log line by timestamp) identified
# 'af'/'b0'/'b1'/'b2' as Cockpit's own "Spring"/"Damper"/"Inertia"/
# "Friction" sliders respectively - confirmed on real hardware: 'af' alone
# clearly stiffens the spring, 'b0' alone produces a friction-like drag
# felt on BOTH axes (not axis-specific), matching the "Damper" name.
# 'b1'/'b2' (Inertia/Friction) were only confirmed via the log correlation,
# not independently felt in isolation.
GAIN_PARAM_AF = 0xAF  # Spring
GAIN_PARAM_DAMPER = 0xB0  # 'b0' - confirmed on real hardware, feels like friction/drag
GAIN_PARAM_INERTIA = 0xB1  # 'b1'
GAIN_PARAM_FRICTION = 0xB2  # 'b2'
# Overall Force Feedback Intensity (Table 7, Param 52) and Maximum Torque
# Output (Table 7, Param 100) - found via the same one-slider-at-a-time
# capture method, each independently checksum-verified against 7-11 real
# captured values.
GAIN_PARAM_OVERALL_INTENSITY = 0xAE
GAIN_PARAM_MAX_TORQUE = 0xA9
# Friction Compensation Strength (Table 8, Param 65 - the Basic Settings
# field under the "Friction Calibration" button, NOT the same as 'b2'
# Friction above). Uses a 2-byte parameter address (0xE1, index 0x16)
# rather than the single-byte "af"-style param+index=0x00 shape, but the
# exact same write shape and checksum formula otherwise - confirmed
# against two real captured values (100 -> "...e116641a", 58 ->
# "...e1163af0").
GAIN_PARAM_FRICTION_COMPENSATION = 0xE1
GAIN_PARAM_FRICTION_COMPENSATION_INDEX = 0x16


def build_gain_param_write(param: int, index: int, value_byte: int) -> str:
    """Build a single-byte-value serial parameter write, matching the shape
    ENABLE_FFB_COMMAND/DISARM_GAIN_COMMAND/CONNECTION_SETUP_SEQUENCE's own
    'af'/'b0'/'b1'/'b2' writes already use: `7e 03 1f 12 PARAM INDEX VALUE
    CHECKSUM`. For the 'af'/'da' gain family, value_byte is 0-100,
    encoding a 0.0-1.0 float the firmware's own debug log reports back in
    that form (confirmed: raw byte 0x19=25 logged as "0.25000", 0x46=70 as
    "0.70000") - other params (like ENABLE_FFB_COMMAND's own 0x85) reuse
    this same write shape for a plain flag byte instead.

    Reference check: build_gain_param_write(0x85, 0x00, 1) must equal
    ENABLE_FFB_COMMAND, and build_gain_param_write(0xAF, 0x00, 25) must
    equal "7e031f12af001987" - both real captured commands.
    """

    body = [0x7E, 0x03, 0x1F, 0x12, int(param) & 0xFF, int(index) & 0xFF, int(value_byte) & 0xFF]
    body.append((sum(body) + 13) & 0xFF)
    return bytes(body).hex()

# The six SET_REPORT Feature reports (control endpoint 0x00) that define the
# effect blocks. Sent once per connection, before any Output-report effect
# writes take hold.
FEATURE_REPORT_SEQUENCE: Tuple[str, ...] = (
    "21010000",
    "21080000",
    "21080000",
    "21090000",
    "210b0000",
    "210a0000",
)

# The complete one-time connection-setup sequence, replayed verbatim right
# after ENABLE_FFB_COMMAND: four condition parameters ("af", "b0", "b1",
# "b2" in the device's own raw param-byte numbering - logged by the
# firmware as Table 7 Params 15, 16, 53, 54) explicitly zeroed over serial
# (each written then read back to confirm before the next write), the HID
# open ("1c03"), all six effect-block definitions (each a Feature report
# paired with a report-0x11 Set Effect write - channels 1 through 6, with
# channel 1 defined twice), a constant-force init to zero, baseline
# report-0x13 Condition zeroing for channels 2/3/4/5/6, and finally the
# gain-arm write to serial param "99" (Table 7 Param 101 = 1.0) with its
# read-back confirmation. Extracted verbatim from "Centering spring.pcapng"
# via tools/probe_moza_ay210_ffb_bench.py's FULL_SESSION_REPLAY, t=0.268254s
# through t=0.937906s (relative), retimed to start at 0. Each tuple is
# (offset, kind, hexstr) exactly like FULL_SESSION_REPLAY - "kind" is one of
# "hid" / "feature" / "serial", dispatched the same way.
CONNECTION_SETUP_SEQUENCE: Tuple[Tuple[float, str, str], ...] = (
    (0.000000, "serial", "7e031f12af00006e"),
    (0.027905, "serial", "7e031e12af00006d"),
    (0.044054, "serial", "7e031f12b000006f"),
    (0.075773, "serial", "7e031e12b000006e"),
    (0.091018, "serial", "7e031f12b1000070"),
    (0.122813, "serial", "7e031e12b100006f"),
    (0.139318, "serial", "7e031f12b2000071"),
    (0.169837, "serial", "7e031e12b2000070"),
    (0.186568, "serial", "7e031e12d7000095"),
    (0.187875, "hid", "1c03"),
    (0.201852, "serial", "7e031e12d8000096"),
    (0.216871, "serial", "7e031e12b8000076"),
    (0.232830, "serial", "7e031e12b9000077"),
    (0.251017, "feature", "21010000"),
    (0.263866, "serial", "7e031e12d7000095"),
    (0.265525, "hid", "110101ff7f000000000000ffff040000000000000000"),
    (0.279851, "serial", "7e031e12d8000096"),
    (0.294839, "serial", "7e031e12b8000076"),
    (0.310865, "serial", "7e031e12b9000077"),
    (0.326373, "feature", "21080000"),
    (0.343921, "hid", "110208ff7f000000000000ff00042823000000000000"),
    (0.374013, "feature", "21080000"),
    (0.389962, "hid", "110308ff7f000000000000ff00042823000000000000"),
    (0.421003, "feature", "21090000"),
    (0.437893, "hid", "110409ff7f000000000000ff00042823000000000000"),
    (0.467178, "feature", "210b0000"),
    (0.483844, "hid", "11050bff7f000000000000ff00042823000000000000"),
    (0.513175, "serial", "7e031e12d7000095"),
    (0.528838, "serial", "7e031e12d8000096"),
    (0.544696, "serial", "7e031e12b8000076"),
    (0.559738, "serial", "7e031e12b9000077"),
    (0.575701, "feature", "210a0000"),
    (0.591987, "hid", "11060aff7f000000000000ff00042823000000000000"),
    (0.623609, "hid", "110101ff7f000000000000ffff040000000000000000"),
    (0.624569, "hid", "15010000"),
    (0.625846, "hid", "130200000000400040ff7fff7f6606"),
    (0.627421, "hid", "130201000000400040ff7fff7f6606"),
    (0.628570, "hid", "13030000000000000000000000b77e"),
    (0.630484, "hid", "13030100000000000000000000b77e"),
    (0.631704, "hid", "130400000000000000000000000000"),
    (0.632430, "hid", "130401000000000000000000000000"),
    (0.633698, "hid", "130500000000000000000000000000"),
    (0.635458, "hid", "130501000000000000000000000000"),
    (0.637772, "hid", "130600000000000000000000000000"),
    (0.638460, "hid", "130601000000000000000000000000"),
    (0.641222, "serial", "7e031f12990064bc"),
    (0.669652, "serial", "7e011e129955"),
)

# The real captured close/disable sequence (from the same session's later
# teardown), reused to leave the device in a clean state no matter how a
# caller exits.
TEARDOWN_SEQUENCE: List[Tuple[float, str]] = [
    (0.000000, "1c03"),
    (0.001596, "1c03"),
    (0.002540, "1a010300"),
    (0.003507, "1b01"),
    (0.004563, "1a020300"),
    (0.005559, "1b02"),
    (0.006535, "1a030300"),
    (0.007536, "1b03"),
    (0.008508, "1a040300"),
    (0.009519, "1b04"),
    (0.010522, "1a050300"),
    (0.011560, "1b05"),
    (0.012519, "1a060300"),
    (0.013515, "1b06"),
]

# The channel-enable heartbeat (channels 4, 5, 6, 2 - the Centering Spring
# channels). Must repeat roughly every ~0.3s or the effect goes stale.
CHANNEL_ENABLE_HEARTBEAT: Tuple[str, ...] = ("1a040101", "1a050101", "1a060101", "1a020101")
OPEN_COMMAND = "1c03"

# The real read-only serial poll cadence that must keep running for the
# entire connection lifetime - sending it is what makes the firmware log
# Host Connecting -> Host Connected, and stopping it mid-session was
# observed to trigger a real "Host Disconnect". Deliberately contains no
# "1f12" (write) commands - those must fire exactly once, from
# CONNECTION_SETUP_SEQUENCE/ENABLE_FFB_COMMAND, never repeated by this loop.
CONNECT_POLL_LOOP: Tuple[Tuple[float, str], ...] = (
    (0.000000, "7e011e12500c"),
    (0.014991, "7e011e12510d"),
    (0.030954, "7e011e12520e"),
    (0.046945, "7e031e1285000043"),
    (0.062964, "7e031e12de00009c"),
    (0.078212, "7e021e12e117b5"),
    (0.094249, "7e031e12a9000067"),
    (0.110376, "7e031e12ae00006c"),
    (0.125292, "7e011e129955"),
    (0.141223, "7e031e12af00006d"),
    (0.156297, "7e031e12b000006e"),
    (0.171204, "7e031e12b100006f"),
    (0.186486, "7e031e12b2000070"),
    (0.202584, "7e031e12d7000095"),
    (0.217483, "7e031e12d8000096"),
    (0.233467, "7e031e12b8000076"),
    (0.248491, "7e031e12b9000077"),
    (0.296159, "7e031e12af00006d"),
    (0.344027, "7e031e12b000006e"),
    (0.391067, "7e031e12b100006f"),
    (0.438091, "7e031e12b2000070"),
    (0.454822, "7e031e12d7000095"),
    (0.470106, "7e031e12d8000096"),
    (0.485125, "7e031e12b8000076"),
    (0.501084, "7e031e12b9000077"),
    (0.532120, "7e031e12d7000095"),
    (0.548105, "7e031e12d8000096"),
    (0.563093, "7e031e12b8000076"),
    (0.579119, "7e031e12b9000077"),
    (0.781429, "7e031e12d7000095"),
    (0.797092, "7e031e12d8000096"),
    (0.812950, "7e031e12b8000076"),
    (0.827992, "7e031e12b9000077"),
    (0.937906, "7e011e129955"),
    (2.006827, "7e031e12de00009c"),
    (2.021854, "7e021e12e117b5"),
    (2.036734, "7e011e129955"),
)

# ---------------------------------------------------------------------------
# MOZA AB6 - a second, distinct device sharing this same HID report
# descriptor and "7e"-framed serial protocol (same checksum formula: sum of
# preceding bytes + 13, mod 256 - confirmed against 300+ real AB6-captured
# frames with zero mismatches). Everything below was captured live from a
# real AB6 (VID 0x346E, PID 0x1002, COM6 on this project's own machine) doing
# a controlled disconnect -> reconnect while USBPcap was running - the same
# "prove don't guess" discipline used for the AY210 above, not copied or
# assumed from it. Two confirmed real differences from the AY210, found by
# this capture rather than assumed: the enable-latch write uses VALUE=0x00
# here (AY210 uses 0x01 - see AB6_ENABLE_FFB_COMMAND), and MOZA Cockpit sent
# no active HID teardown at all on disconnect for the AB6 - the firmware
# logged "Host Disconnect" on its own once the serial poll loop simply
# stopped (see AB6_TEARDOWN_SEQUENCE). Basic Settings gain-param bytes
# (af/b0/b1/b2) were NOT re-probed here - `moza_ab6_calibration_notes.md`
# already confirms those are shared with the AY210 from an earlier capture.
# ---------------------------------------------------------------------------

AB6_VID = 0x346E
AB6_PID = 0x1002
AB6_DEFAULT_SERIAL_PORT = "COM6"

# The AB6's own persistent per-power-cycle FFB-active latch. Confirmed real
# (checksum-verified) at t=36.4066s in a capture spanning a full "Host
# Disconnect" -> "Host Connecting" -> "Host Connected" cycle - sent once,
# mid-"Host Connecting", before "Host Connected" was logged (the AY210's own
# equivalent write instead fires *after* "Host Connected" - a second
# confirmed real timing difference between the two devices, not assumed).
# VALUE=0x00 here, not 0x01 like the AY210's ENABLE_FFB_COMMAND - confirmed
# by exhaustive search: no other write to param 0x85 exists anywhere in the
# 60-second capture this was found in.
AB6_ENABLE_FFB_COMMAND = "7e031f1285000044"

# The AB6's own real captured connection setup burst, t=0 aligned to the
# first serial frame after "Host Connecting" was logged, ending right before
# the steady-state poll cadence below begins. Reference check: this is a
# verbatim, checksum-verified transcription of `ab6_capture3_cold.pcapng`
# (dev 49, VID:PID 346E:1002) - every frame here satisfies the same
# `(sum(preceding bytes) + 13) & 0xFF` checksum as every AY210 encoder.
AB6_CONNECTION_SETUP_SEQUENCE: Tuple[Tuple[float, str, str], ...] = (
    (0.000000, "serial", "7e031e1286000044"),
    (0.004643, "serial", "7e031e12b9000077"),
    (0.004643, "serial", "7e031e12b8000076"),
    (0.057828, "serial", "7e031f12e11701b8"),
    (0.057828, "serial", "7e031f12ba00017a"),
    (0.061200, "serial", "7e021e125c0019"),
    (0.102312, "serial", "7e031e1286000044"),
    (0.104769, "serial", "7e031e12b9000077"),
    (0.104769, "serial", "7e031e12b8000076"),
    (0.158336, "serial", "7e071f120f000f14283c50a9"),
    (0.158336, "serial", "7e071f120f800f14283c5029"),
    (0.158987, "serial", "7e031f1271000030"),
    (0.160767, "serial", "7e071f120f010f14283c50aa"),
    (0.160767, "serial", "7e071f120f810f14283c502a"),
    (0.160767, "serial", "7e071f120f040f14283c50ad"),
    (0.160767, "serial", "7e071f120f840f14283c502d"),
    (0.161974, "serial", "7e031f1271010031"),
    (0.163266, "serial", "7e041f12e10f006414"),
    (0.163266, "serial", "7e041f12e103106418"),
    (0.165080, "serial", "7e031f1265000226"),
    (0.165080, "serial", "7e051f12e111100114d8"),
    (0.166155, "serial", "7e061f126600004100f25b"),
    (0.166398, "serial", "7e031f126700092f"),
    (0.168040, "serial", "7e031f1269000028"),
    (0.168040, "serial", "7e031f1268000128"),
    (0.168040, "serial", "7e031f126b00012b"),
    (0.168459, "serial", "7e031f126b01012c"),
    (0.169041, "serial", "7e041f12e10f016415"),
    (0.169041, "serial", "7e041f12e103206428"),
    (0.169041, "serial", "7e021f127d003b"),
    (0.170005, "serial", "7e051f12e111100228ed"),
    (0.170005, "serial", "7e041f120f80200170"),
    (0.170005, "serial", "7e041f120f802164d4"),
    (0.170005, "serial", "7e041f120f802264d5"),
    (0.170005, "serial", "7e041f120f80011464"),
    (0.170005, "serial", "7e041f120f80022879"),
    (0.170005, "serial", "7e041f120f80033c8e"),
    (0.171391, "serial", "7e041f120f800450a3"),
    (0.171391, "serial", "7e041f120f80111474"),
    (0.171391, "serial", "7e041f120f80122889"),
    (0.171391, "serial", "7e041f120f80133c9e"),
    (0.171391, "serial", "7e041f120f801450b3"),
    (0.171391, "serial", "7e041f120f801564c8"),
    (0.171391, "serial", "7e041f120f002001f0"),
    (0.171391, "serial", "7e181f126c0000060f0020143128423c535064640000000000000000cb"),
    (0.171391, "serial", "7e181f126c0100060000141428283c3c5050646400000000000000009f"),
    (0.172237, "serial", "7e041f120f00216454"),
    (0.172237, "serial", "7e031f12cf00008e"),
    (0.178066, "serial", "7e031f12cb00018b"),
    (0.178066, "serial", "7e041f120f00226455"),
    (0.178066, "serial", "7e041f120f000114e4"),
    (0.178066, "serial", "7e041f120f000228f9"),
    (0.178066, "serial", "7e041f120f00033c0e"),
    (0.178066, "serial", "7e041f120f00045023"),
    (0.178066, "serial", "7e041f120f001114f4"),
    (0.178066, "serial", "7e041f120f00122809"),
    (0.178066, "serial", "7e041f120f00133c1e"),
    (0.178066, "serial", "7e041f120f00145033"),
    (0.178066, "serial", "7e041f120f00156448"),
    (0.178066, "serial", "7e041f120f81200171"),
    (0.178066, "serial", "7e041f120f812164d5"),
    (0.178066, "serial", "7e041f120f812264d6"),
    (0.178066, "serial", "7e041f120f81011465"),
    (0.178066, "serial", "7e041f120f8102287a"),
    (0.178066, "serial", "7e041f120f81033c8f"),
    (0.178066, "serial", "7e041f120f810450a4"),
    (0.178066, "serial", "7e041f120f81111475"),
    (0.178066, "serial", "7e041f120f8112288a"),
    (0.178066, "serial", "7e041f120f81133c9f"),
    (0.178066, "serial", "7e041f120f811450b4"),
    (0.178066, "serial", "7e041f120f811564c9"),
    (0.178066, "serial", "7e041f120f012001f1"),
    (0.178066, "serial", "7e041f120f01216455"),
    (0.180513, "serial", "7e041f120f01226456"),
    (0.180513, "serial", "7e041f120f010114e5"),
    (0.180513, "serial", "7e041f120f010228fa"),
    (0.180513, "serial", "7e041f120f01033c0f"),
    (0.180513, "serial", "7e041f120f01045024"),
    (0.180513, "serial", "7e041f120f011114f5"),
    (0.180513, "serial", "7e041f120f0112280a"),
    (0.180513, "serial", "7e041f120f01133c1f"),
    (0.180513, "serial", "7e041f120f01145034"),
    (0.180513, "serial", "7e041f120f01156449"),
    (0.180513, "serial", "7e041f120f84200073"),
    (0.180513, "serial", "7e041f120f842164d8"),
    (0.180513, "serial", "7e041f120f842264d9"),
    (0.180513, "serial", "7e041f120f84011468"),
    (0.180513, "serial", "7e041f120f8402287d"),
    (0.191226, "serial", "7e041f120f84033c92"),
    (0.191226, "serial", "7e041f120f840450a7"),
    (0.191226, "serial", "7e041f120f84111478"),
    (0.191226, "serial", "7e041f120f8412288d"),
    (0.191226, "serial", "7e041f120f84133ca2"),
    (0.191226, "serial", "7e041f120f841450b7"),
    (0.191226, "serial", "7e041f120f841564cc"),
    (0.191226, "serial", "7e041f120f042000f3"),
    (0.191226, "serial", "7e041f120f04216458"),
    (0.191226, "serial", "7e041f120f04226459"),
    (0.191226, "serial", "7e041f120f040114e8"),
    (0.191226, "serial", "7e041f120f040228fd"),
    (0.191226, "serial", "7e041f12e1031114c9"),
    (0.191226, "serial", "7e051f12e11110033c02"),
    (0.191226, "serial", "7e041f120f04033c12"),
    (0.191226, "serial", "7e041f120f04045027"),
    (0.191226, "serial", "7e041f12e10900640e"),
    (0.191226, "serial", "7e041f12e1090114bf"),
    (0.191226, "serial", "7e031f12e10e00ae"),
    (0.191226, "serial", "7e031f12ad0064d0"),
    (0.191226, "serial", "7e041f120f041114f8"),
    (0.191226, "serial", "7e041f120f0412280d"),
    (0.191226, "serial", "7e041f120f04133c22"),
    (0.191226, "serial", "7e041f120f04145037"),
    (0.191226, "serial", "7e041f120f0415644c"),
    (0.191226, "serial", "7e031f12e11200b2"),
    (0.191226, "serial", "7e031f12e10601a7"),
    (0.191226, "serial", "7e031f12e10101a2"),
    (0.191226, "serial", "7e051f12e110100000c2"),
    (0.205046, "serial", "7e041f12e10a0032dd"),
    (0.205046, "serial", "7e041f12e10b0032de"),
    (0.205046, "serial", "7e041f12e10a0132de"),
    (0.205046, "serial", "7e041f12e10b0132df"),
    (0.205046, "serial", "7e031f12ab0164cf"),
    (0.205046, "serial", "7e031f12ab0264d0"),
    (0.205046, "serial", "7e031f129e00005d"),
    (0.205046, "serial", "7e031f12ad0164d1"),
    (0.205046, "serial", "7e031f12ac0164d0"),
    (0.205046, "serial", "7e031f12ac0264d1"),
    (0.205046, "serial", "7e031f12a2000061"),
    (0.205046, "serial", "7e021f125a0018"),
    (0.205046, "serial", "7e031f12b0002190"),
    (0.205046, "serial", AB6_ENABLE_FFB_COMMAND),
    (0.205046, "serial", "7e031f12b2000a7b"),
    (0.205046, "serial", "7e031f1299005eb6"),
    (0.205046, "serial", "7e031f12c9000189"),
    (0.205046, "serial", "7e031f12b1000c7c"),
    (0.205046, "serial", "7e031f12a90064cc"),
    (0.205046, "serial", "7e031f12ae0046b3"),
    (0.205046, "serial", "7e031e1286000044"),
    (0.205046, "serial", "7e031e12b9000077"),
    (0.205046, "serial", "7e031e12b8000076"),
    (0.205046, "serial", "7e031f12af0032a0"),
    (0.205046, "serial", "7e031f12d1000a9a"),
    (0.205046, "serial", "7e031f12d0000190"),
    (0.205046, "serial", "7e031f12d2000596"),
    (0.205046, "serial", "7e031f12c0000281"),
    (0.205046, "serial", "7e031f12c6030088"),
    (0.205046, "serial", "7e031f12c6020087"),
    (0.205046, "serial", "7e031f12c6000085"),
    (0.205046, "serial", "7e031f12c6010086"),
    (0.214780, "serial", "7e031f12d9000199"),
    (0.214780, "serial", "7e031f12db0164ff"),
    (0.214780, "serial", "7e031f12db0064fe"),
    (0.214780, "serial", "7e031f12db036401"),
    (0.214780, "serial", "7e031f12db026400"),
    (0.214780, "serial", "7e031f12dd016401"),
    (0.214780, "serial", "7e031f12dd006400"),
    (0.214780, "serial", "7e031f12dd036403"),
    (0.214780, "serial", "7e031f12dd026402"),
    (0.214780, "serial", "7e031f12dc016400"),
    (0.214780, "serial", "7e031f12dc0064ff"),
    (0.214780, "serial", "7e031f12dc036402"),
    (0.214780, "serial", "7e031f12dc026401"),
    (0.214780, "serial", "7e031f12da0164fe"),
    (0.214780, "serial", "7e031f12935214b8"),
    (0.214780, "serial", "7e031f12935328cd"),
    (0.214780, "serial", "7e031f1293543ce2"),
    (0.214780, "serial", "7e031f12935550f7"),
    (0.214780, "serial", "7e031f129356640c"),
    (0.214780, "serial", "7e031f12da0064fd"),
    (0.214780, "serial", "7e031f1293321498"),
    (0.214780, "serial", "7e031f12933328ad"),
    (0.214780, "serial", "7e031f1293343cc2"),
    (0.214780, "serial", "7e031f12933550d7"),
    (0.214780, "serial", "7e031f12933664ec"),
    (0.214780, "serial", "7e031f12da036400"),
    (0.214780, "serial", "7e031f12945214b9"),
    (0.214780, "serial", "7e031f12945328ce"),
    (0.214780, "serial", "7e031f1294543ce3"),
    (0.214780, "serial", "7e031f12945550f8"),
    (0.214780, "serial", "7e041f12e1032114d9"),
    (0.214780, "serial", "7e051f12e11110045017"),
    (0.214780, "serial", "7e031f129456640d"),
    (0.214780, "serial", "7e031f12da0264ff"),
    (0.214780, "serial", "7e031f1294321499"),
    (0.223087, "serial", "7e031f12943328ae"),
    (0.223087, "serial", "7e031f1294343cc3"),
    (0.223087, "serial", "7e031f12943550d8"),
    (0.223087, "serial", "7e031f12943664ed"),
    (0.223087, "serial", "7e031f12cd0064f0"),
    (0.223087, "serial", "7e031f12cd0242d0"),
    (0.223087, "serial", "7e031f12ce0064f1"),
    (0.223087, "serial", "7e031f12ce0264f3"),
    (0.223087, "serial", "7e051f12e11010016427"),
    (0.223087, "serial", "7e031f12c3000082"),
    (0.223087, "serial", "7e031f12c5030087"),
    (0.223087, "serial", "7e031f12c5020086"),
    (0.223087, "serial", "7e031f12c5000084"),
    (0.223087, "serial", "7e031f12c5050089"),
    (0.223087, "serial", "7e031f12c5010085"),
    (0.223087, "serial", "7e031f12c4001497"),
    (0.223087, "serial", "7e031f12c5040088"),
    (0.244732, "serial", "7e051f12e1111005642c"),
    (0.245793, "serial", "7e051f12e11010026428"),
    (0.247199, "serial", "7e051f12e111000114c8"),
    (0.248400, "serial", "7e051f12e110000000b2"),
    (0.251101, "serial", "7e051f12e111000228dd"),
    (0.251257, "serial", "7e051f12e11000016417"),
    (0.255154, "serial", "7e051f12e11100033cf2"),
    (0.256404, "serial", "7e051f12e11000026418"),
    (0.257953, "serial", "7e051f12e11100045007"),
    (0.260139, "serial", "7e051f12e110110000c3"),
    (0.260139, "serial", "7e051f12e1110005641c"),
    (0.263075, "serial", "7e051f12e11011016428"),
    (0.263391, "serial", "7e051f12e111110114d9"),
    (0.266025, "serial", "7e051f12e11011026429"),
    (0.266175, "serial", "7e051f12e111110228ee"),
    (0.268973, "serial", "7e051f12e110010000b3"),
    (0.270081, "serial", "7e051f12e11111033c03"),
    (0.272311, "serial", "7e051f12e11001016418"),
    (0.274377, "serial", "7e051f12e11111045018"),
    (0.276600, "serial", "7e051f12e11001026419"),
    (0.278222, "serial", "7e051f12e1111105642d"),
    (0.282004, "serial", "7e051f12e111010114c9"),
    (0.286075, "serial", "7e051f12e111010228de"),
    (0.290201, "serial", "7e051f12e11101033cf3"),
    (0.294114, "serial", "7e051f12e11101045008"),
    (0.297822, "serial", "7e051f12e1110105641d"),
)

# The AB6's own steady-state serial poll cadence, active for the whole
# connection lifetime exactly like CONNECT_POLL_LOOP above (same rule:
# stopping it triggers a real "Host Disconnect"). Captured immediately after
# AB6_CONNECTION_SETUP_SEQUENCE settles - one real ~1.07s window, safe to
# repeat indefinitely (background_poll_loop() already re-runs whatever
# sequence it is given in a loop).
AB6_CONNECT_POLL_LOOP: Tuple[Tuple[float, str], ...] = (
    (0.000000, "7e031e1286000044"),
    (0.003495, "7e031e12b9000077"),
    (0.005809, "7e031e12b8000076"),
    (0.066468, "7e000614a5"),
    (0.066701, "7e000615a6"),
    (0.067370, "7e00061aab"),
    (0.067370, "7e000616a7"),
    (0.067370, "7e000617a8"),
    (0.067370, "7e000618a9"),
    (0.067370, "7e000619aa"),
    (0.067370, "7e01431306e8"),
    (0.100684, "7e031e1286000044"),
    (0.103605, "7e031e12b9000077"),
    (0.105748, "7e031e12b8000076"),
    (0.200831, "7e031e1286000044"),
    (0.200831, "7e000613a4"),
    (0.205945, "7e031e12b9000077"),
    (0.205945, "7e031e12b8000076"),
    (0.302583, "7e031e1286000044"),
    (0.306050, "7e031e12b9000077"),
    (0.306050, "7e031e12b8000076"),
    (0.402953, "7e031e1286000044"),
    (0.405877, "7e031e12b9000077"),
    (0.405877, "7e031e12b8000076"),
    (0.440602, "7e031e12a9000067"),
    (0.502339, "7e031e1286000044"),
    (0.506026, "7e031e12b9000077"),
    (0.506026, "7e031e12b8000076"),
    (0.566381, "7e000615a6"),
    (0.566381, "7e000614a5"),
    (0.567371, "7e01431306e8"),
    (0.567371, "7e000616a7"),
    (0.567371, "7e000617a8"),
    (0.567371, "7e000618a9"),
    (0.567371, "7e000619aa"),
    (0.567371, "7e00061aab"),
    (0.602987, "7e031e1286000044"),
    (0.606091, "7e031e12b9000077"),
    (0.606091, "7e031e12b8000076"),
    (0.702383, "7e031e1286000044"),
    (0.704003, "7e000613a4"),
    (0.706172, "7e031e12b9000077"),
    (0.706172, "7e031e12b8000076"),
    (0.803364, "7e031e1286000044"),
    (0.806358, "7e031e12b9000077"),
    (0.806358, "7e031e12b8000076"),
    (0.903297, "7e031e1286000044"),
    (0.905893, "7e031e12b9000077"),
    (0.905893, "7e031e12b8000076"),
    (0.942002, "7e031e12a9000067"),
    (1.002729, "7e031e1286000044"),
    (1.006380, "7e031e12b9000077"),
    (1.006566, "7e031e12b8000076"),
    (1.066833, "7e000614a5"),
    (1.066833, "7e000615a6"),
    (1.067984, "7e00061aab"),
    (1.067984, "7e000616a7"),
    (1.067984, "7e000617a8"),
    (1.067984, "7e000618a9"),
    (1.067984, "7e000619aa"),
    (1.067984, "7e01431306e8"),
)

# Confirmed real: MOZA Cockpit sent zero HID Interrupt-OUT (endpoint 0x03)
# traffic anywhere in a 60-second capture spanning a full disconnect ->
# reconnect cycle for the AB6 - no active teardown sequence exists to
# replay. `replay_teardown()` with this empty tuple is therefore a
# deliberate, evidence-based no-op, not an unfilled stub.
AB6_TEARDOWN_SEQUENCE: Tuple[Tuple[float, str], ...] = ()


class MozaDeviceProfile:
    """Bundles one MOZA device's own identity + captured protocol timings,
    so `open_ay210()`/`replay_connection_setup()`/`background_poll_loop()`/
    `replay_teardown()` can each be pointed at a specific real device instead
    of only ever reading this module's own AY210-shaped globals. Every field
    here must trace to a real capture from that specific device - see
    AY210_PROFILE/AB6_PROFILE's own construction below for what that means
    in practice (the AY210 profile simply wraps the module's pre-existing,
    already-proven globals; nothing about them changes)."""

    __slots__ = (
        "name", "vid", "pid", "default_serial_port",
        "enable_ffb_command", "connection_setup_sequence",
        "connect_poll_loop", "teardown_sequence", "confirmed_physics_fields",
    )

    def __init__(
        self, *, name: str, vid: int, pid: int, default_serial_port: str,
        enable_ffb_command: str,
        connection_setup_sequence: Tuple[Tuple[float, str, str], ...],
        connect_poll_loop: Tuple[Tuple[float, str], ...],
        teardown_sequence: Tuple[Tuple[float, str], ...],
        confirmed_physics_fields: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.name = name
        self.vid = vid
        self.pid = pid
        self.default_serial_port = default_serial_port
        self.enable_ffb_command = enable_ffb_command
        self.connection_setup_sequence = connection_setup_sequence
        self.connect_poll_loop = connect_poll_loop
        self.teardown_sequence = teardown_sequence
        # None means "every field in PHYSICS_FIELD_TO_GAIN_PARAM is
        # confirmed for this device" (the AY210's own long-standing
        # behavior - every field was found via a live MOZA Cockpit slider
        # capture for this exact device). A device with only some fields
        # confirmed (e.g. the AB6 - see AB6_PROFILE below) must list them
        # explicitly here so the engine's gain-param sync never sends a
        # write for a (param, index) address that was never confirmed to
        # mean the same thing on that device.
        self.confirmed_physics_fields = confirmed_physics_fields


# The AY210's own profile - wraps this module's pre-existing, already-proven
# globals verbatim. Constructing this changes nothing about how any existing
# caller of VID/PID/DEFAULT_SERIAL_PORT/ENABLE_FFB_COMMAND/CONNECTION_SETUP_
# SEQUENCE/CONNECT_POLL_LOOP/TEARDOWN_SEQUENCE behaves - it only gives the
# engine a single object to pass around for callers that want to be
# device-agnostic (see MozaAy210FfbEngine's own `device_profile` parameter).
AY210_PROFILE = MozaDeviceProfile(
    name="AY210",
    vid=VID, pid=PID, default_serial_port=DEFAULT_SERIAL_PORT,
    enable_ffb_command=ENABLE_FFB_COMMAND,
    connection_setup_sequence=CONNECTION_SETUP_SEQUENCE,
    connect_poll_loop=CONNECT_POLL_LOOP,
    teardown_sequence=tuple(TEARDOWN_SEQUENCE),
)

AB6_PROFILE = MozaDeviceProfile(
    name="AB6",
    vid=AB6_VID, pid=AB6_PID, default_serial_port=AB6_DEFAULT_SERIAL_PORT,
    enable_ffb_command=AB6_ENABLE_FFB_COMMAND,
    connection_setup_sequence=AB6_CONNECTION_SETUP_SEQUENCE,
    connect_poll_loop=AB6_CONNECT_POLL_LOOP,
    teardown_sequence=AB6_TEARDOWN_SEQUENCE,
    # Per moza_ab6_calibration_notes.md: 'af'/'b0'/'b1'/'b2' (spring/damper/
    # inertia/friction) and the 0x99 gain-arm byte are confirmed identical
    # to the AY210's own addresses. overall_intensity/max_torque/
    # friction_compensation were never byte-confirmed for the AB6 - left
    # out here so the engine never sends a write to an unproven address.
    confirmed_physics_fields=("spring_gain", "damper", "inertia", "friction"),
)

# ---------------------------------------------------------------------------
# Effect data transcribed from this project's own capture analysis.
#
# Only the spring/condition mechanism (CONNECTION_SETUP_SEQUENCE + a live
# build_set_condition() ramp) has been physically confirmed on real
# hardware. Everything below is transcribed from earlier byte-level
# analysis this session performed against real captures under
# D:\ProgramFiles\Wireshark\ and D:\ProgramFiles\Wireshark\CAPTURES\ (not
# re-derived from scratch), but has NOT yet been driven live and physically
# verified the way the spring effect has - see BUG_REGISTER.md tenth
# follow-up and the FFB-engine plan for the staged verification this data
# still needs before anything built on it is trusted.
# ---------------------------------------------------------------------------

# report 0x13's EffectBlockIndex used for BOTH the spring (±coefficient/
# saturation/deadband fields) and trim (CP Offset field) effects - they are
# two fields of the SAME packet per axis, not independent effects. Source:
# "Centering spring.pcapng" (spring) and "Trim.pcapng" (trim CP-Offset).
CONDITION_EFFECT_BLOCK_INDEX = 2

# Which report-0x13 ParameterBlockOffset corresponds to which physical axis.
# Established from "Trim.pcapng": two sequential trim tests toggled the two
# ParameterBlockOffset values in the SAME order the tests were listed
# (pitch settle-point tested first, held CP=14745 from t=6.55s until the
# second test began at t=28.34s; roll settle-point tested second, CP=14745
# from t=28.42s onward) - offset=1 changed first (pitch), offset=0 changed
# second (roll).
AXIS_PARAMETER_BLOCK_OFFSET = {"pitch": 1, "roll": 0}

# report 0x14 (Set Periodic) presets, decoded from FFB-Bridge's own
# "Effect Gains.pcapng" bench-test capture: each of the 17 listed tests
# produced a distinct, isolated ~2-second burst on a specific (channel,
# frequency_code) pair, in the same order the tests are listed in FFB-
# Bridge's own UI, cross-checked against each burst's peak magnitude.
# "ground_accel_pitch" is deliberately absent here - it went through report
# 0x15 (constant force), not 0x14, and belongs with constant-force
# reference data instead. "stall_buffet" is the one two-channel exception
# (both 7 and 8 fire together, "shaking the whole stick" per FFB-Bridge's
# own description) - represented as a tuple of (channel, frequency_code)
# pairs rather than a single pair.
RUMBLE_PRESETS = {
    "runway_rumble": {"channels": ((7, 80),), "reference_magnitude": 6881},
    "gear_bumps": {"channels": ((7, 35),), "reference_magnitude": 3734},
    "brake_shudder": {"channels": ((7, 110),), "reference_magnitude": 7200},
    "nosewheel_shimmy": {"channels": ((7, 130),), "reference_magnitude": 6683},
    "stall_buffet": {"channels": ((7, 50), (8, 55)), "reference_magnitude": 8601},
    "overspeed_buffet": {"channels": ((7, 30),), "reference_magnitude": 8493},
    "mach_buffet": {"channels": ((7, 25),), "reference_magnitude": 5568},
    "spoiler_buffet": {"channels": ((7, 45),), "reference_magnitude": 7922},
    "flap_buffet": {"channels": ((7, 55),), "reference_magnitude": 5591},
    "gear_buffet": {"channels": ((7, 90),), "reference_magnitude": 5139},
    "turbulence": {"channels": ((7, 180),), "reference_magnitude": 9668},
    "reverse_rumble": {"channels": ((7, 70),), "reference_magnitude": 5590},
    "engine_rumble": {"channels": ((7, 30),), "reference_magnitude": 4562},
}

# Periodic/rumble channels (7, 8) are NOT covered by CONNECTION_SETUP_SEQUENCE
# (that sequence was extracted from "Centering spring.pcapng", which only
# ever exercised channels 1-6). Cross-referencing "Effect Gains.pcapng"
# showed every rumble preset's first report-0x14 write is preceded by its
# own report-0x11 (Set Effect) definition on that channel - without it, a
# 0x14 write is presumably fully acknowledged with zero physical effect,
# the same trap the spring effect was stuck in before CONNECTION_SETUP_SEQUENCE
# was found. Each preset's own definition has a 2-byte "parameter" field
# (offset 14-15) that visibly differs from test to test (bc34, e457, 2823,
# 7869, ...) - but nosewheel_shimmy (frequency_code 130) and mach_buffet
# (frequency_code 25) were captured using the IDENTICAL parameter (7869)
# despite unrelated frequencies, so this field does not appear to encode
# the oscillation frequency itself (frequency_code in build_set_periodic's
# own report already does that, independently verified via each preset's
# isolated burst). Rather than guess at what this field means, each
# channel is armed with ONE proven-real captured definition (not a
# synthesized value) and reused regardless of which preset later writes to
# that channel - genuinely untested whether a *different* preset than the
# one it was captured from behaves identically, so log verification before
# physical testing matters here even more than usual.
RUMBLE_CHANNEL_ARM = {
    # Channel 7: two identical generic zeroed defs then the real one,
    # extracted verbatim from the "runway_rumble" test (the first rumble
    # test in "Effect Gains.pcapng", t=4.590612-4.671274).
    7: (
        "110704ff7f000000000000ffff040000000000000000",
        "110704ff7f000000000000ffff040000000000000000",
        "110704ff7f000000000000ffff04bc34000000000000",
    ),
    # Channel 8: same shape, extracted from the "stall_buffet" test (the
    # only test that ever used channel 8), t=112.524973-112.557495.
    8: (
        "110805ff7f000000000000ffff040000000000000000",
        "110805ff7f000000000000ffff040000000000000000",
        "110805ff7f000000000000ffff04e880000000000000",
    ),
}

# report 0x15 (global Constant Force, channel 1) reference data from the
# "Ground accel (pitch cue)" and "Airspeed load" tests - a steady,
# non-periodic push whose magnitude ramped as high as ~2867-3623 in
# observed captures - proven, on real hardware, to be far too weak on its
# own to feel on a free (unopposed) yoke at all (see
# moza_ay210_ffb_engine.py's own history for the step-up test that found
# 25000-32767 "strong but comfortable" instead). A follow-up step test
# through the u16 boundary CONFIRMED the field is signed (int16): 32767 is
# the true maximum push in the positive direction - see
# build_constant_force()'s docstring for the full story.
CONSTANT_FORCE_OBSERVED_MAGNITUDE_RANGE = (0, 3623)


def open_ay210(*, vid: int = VID, pid: int = PID) -> "hid.device":
    """Open the FFB-capable HID interface for a MOZA device by VID/PID.

    Defaults to the AY210's own VID/PID for every existing caller - pass
    `vid=AB6_VID, pid=AB6_PID` (or `device_profile.vid/pid` from a
    `MozaDeviceProfile`) to open an AB6 instead. Both devices expose the same
    HID report descriptor (usage_page 0x01, usage 0x04) on this interface -
    confirmed byte-for-byte identical for the AB6 in an earlier capture.
    """
    if hid is None:
        raise RuntimeError("hidapi is not installed (pip install hid)")
    devices = list(hid.enumerate(vid, pid))
    matches = [
        item for item in devices
        if int(item.get("usage_page") or 0) == 0x01 and int(item.get("usage") or 0) == 0x04
    ]
    if not matches:
        raise FileNotFoundError(
            f"MOZA device ({vid:04X}:{pid:04X}) HID interface is not connected"
        )
    path = matches[0].get("path")
    if not path:
        raise RuntimeError("MOZA HID path is unavailable")
    device = hid.device()
    device.open_path(path)
    return device


def open_serial(port: str = DEFAULT_SERIAL_PORT) -> "serial.Serial":
    if serial is None:
        raise RuntimeError("pyserial is not installed (pip install pyserial)")
    ser = serial.Serial(port, SERIAL_BAUD, timeout=0.1)
    # The AY210 keeps streaming its debug log even with nobody listening, so
    # opening the port can immediately hand back bytes queued from BEFORE
    # this connection even started - including a stale "Host Connected"
    # left over from a previous session. A single reset_input_buffer() was
    # not enough - USB-layer data already "in flight" at the moment of the
    # flush kept arriving a few milliseconds later and refilling the
    # buffer, so flush twice with a short gap to actually drain it.
    ser.reset_input_buffer()
    time.sleep(0.3)
    ser.reset_input_buffer()
    return ser


def send_hid(device: "hid.device", hexstr: str) -> None:
    device.write(bytes.fromhex(hexstr))


def send_feature_report(device: "hid.device", hexstr: str) -> None:
    device.send_feature_report(bytes.fromhex(hexstr))


def send_serial(ser: "serial.Serial", lock: threading.Lock, hexstr: str) -> None:
    with lock:
        ser.write(bytes.fromhex(hexstr))


def background_poll_loop(
    ser: "serial.Serial", stop: threading.Event, lock: threading.Lock,
    poll_loop: Tuple[Tuple[float, str], ...] = CONNECT_POLL_LOOP,
) -> None:
    """Must be started once per connection and left running for the whole
    session - see CONNECT_POLL_LOOP's docstring comment above. Pass
    `device_profile.connect_poll_loop` for a non-AY210 device (defaults to
    the AY210's own loop for every existing caller)."""

    loop_duration = poll_loop[-1][0]
    while not stop.is_set():
        cycle_start = time.monotonic()
        for offset, hexstr in poll_loop:
            if stop.is_set():
                return
            target = cycle_start + offset
            now = time.monotonic()
            if target > now and stop.wait(target - now):
                return
            try:
                send_serial(ser, lock, hexstr)
            except Exception:
                return
        remaining = loop_duration - (time.monotonic() - cycle_start)
        if remaining > 0 and stop.wait(remaining):
            return


def wait_for_connected(ser: "serial.Serial", timeout: float) -> bool:
    """Read the device's own debug log until it prints
    "[INFO]motor_app.c:598 Host Connected." (or the timeout elapses).

    Do not try to reject "too fast" matches as stale-buffer artifacts - a
    warm reconnect shortly after a previous session can genuinely complete
    in well under a second, and filtering by elapsed time was proven (this
    session) to discard that real event and then never see another, since
    the device only logs Connected once. open_serial()'s double
    reset_input_buffer() is what actually handles stale data."""

    needle = b"Host Connected"
    buf = b""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk
            if needle in buf:
                return True
            buf = buf[-len(needle):]
    return False


def replay_teardown(
    device: "hid.device",
    sequence: Tuple[Tuple[float, str], ...] = tuple(TEARDOWN_SEQUENCE),
) -> None:
    """Pass `device_profile.teardown_sequence` for a non-AY210 device
    (defaults to the AY210's own sequence for every existing caller). An
    empty sequence (confirmed real for the AB6 - MOZA Cockpit sends no
    active HID teardown, disconnect is detected passively when the serial
    poll loop simply stops) is a safe no-op here."""

    start = time.monotonic()
    for offset, hexstr in sequence:
        target = start + offset
        now = time.monotonic()
        if target > now:
            time.sleep(target - now)
        send_hid(device, hexstr)


def replay_connection_setup(
    device: "hid.device", ser: "serial.Serial", lock: threading.Lock,
    sequence: Tuple[Tuple[float, str, str], ...] = CONNECTION_SETUP_SEQUENCE,
) -> None:
    """Send CONNECTION_SETUP_SEQUENCE with its real captured timing. Must be
    sent exactly once per connection, right after ENABLE_FFB_COMMAND and
    before any live build_set_condition()/build_set_periodic()/
    build_constant_force() write is expected to take hold - never repeated
    on every tick. Pass `device_profile.connection_setup_sequence` for a
    non-AY210 device (defaults to the AY210's own sequence for every
    existing caller)."""

    start = time.monotonic()
    for offset, kind, hexstr in sequence:
        target = start + offset
        now = time.monotonic()
        if target > now:
            time.sleep(target - now)
        if kind == "hid":
            send_hid(device, hexstr)
        elif kind == "feature":
            send_feature_report(device, hexstr)
        elif kind == "serial":
            send_serial(ser, lock, hexstr)


# ---------------------------------------------------------------------------
# Encoders - the only genuinely new protocol code in this module. Each
# packs decoded values into the wire format, replacing "replay this exact
# hex string" with "encode this number". Before trusting one for a new
# value, confirm it reproduces a known captured packet byte-for-byte -
# see each docstring for the exact reference.
# ---------------------------------------------------------------------------


def _u16(value: int) -> bytes:
    return int(value).to_bytes(2, "little", signed=False)


def _s16(value: int) -> bytes:
    return int(value).to_bytes(2, "little", signed=True)


def replay_rumble_channel_arm(device: "hid.device", channel: int) -> None:
    """Send RUMBLE_CHANNEL_ARM's one-time three-packet sequence for a
    periodic/rumble channel (7 or 8). Must be sent once per connection,
    before the first build_set_periodic() write to that channel - see
    RUMBLE_CHANNEL_ARM's module-level comment for why."""

    sequence = RUMBLE_CHANNEL_ARM.get(channel)
    if not sequence:
        raise ValueError(f"no known arm sequence for rumble channel {channel}")
    zero1, zero2, real = sequence
    send_hid(device, zero1)
    time.sleep(0.05)
    send_hid(device, zero2)
    time.sleep(0.01)
    send_hid(device, real)


def build_set_condition(
    effect_block_index: int,
    axis_offset: int,
    cp_offset: int,
    coef_pos: int,
    coef_neg: int,
    sat_pos: int,
    sat_neg: int,
    deadband: int,
) -> bytes:
    """Report 0x13 (Set Condition), 15 bytes.

    Reference check: build_set_condition(2, 0, 0, 16384, 16384, 32767,
    32767, 1638) must equal bytes.fromhex("130200000000400040ff7fff7f6606")
    - the real captured baseline condition packet from "Centering
    spring.pcapng" (channel 2, offset 0, centered/no-trim, 50% spring,
    full saturation).

    cp_offset is signed (-32768..32767, positive/negative meaning
    unverified beyond "some positive value shifted CP" per the trim
    capture); coef_pos/coef_neg/sat_pos/sat_neg/deadband are unsigned
    0..65535 (observed range 0..32767 in every capture so far).
    """

    return (
        bytes([0x13, int(effect_block_index) & 0xFF, int(axis_offset) & 0xFF])
        + _s16(cp_offset)
        + _u16(coef_pos)
        + _u16(coef_neg)
        + _u16(sat_pos)
        + _u16(sat_neg)
        + _u16(deadband)
    )


def build_set_periodic(channel: int, magnitude: int, frequency_code: int) -> bytes:
    """Report 0x14 (Set Periodic), 12 bytes.

    Reference check: build_set_periodic(8, 0x000009c0, 0xb4) must equal
    bytes.fromhex("1408c00900000000b4000000") - a real captured packet from
    the Cessna 172 flight capture.

    magnitude and frequency_code are both unsigned 32-bit LE fields;
    frequency_code only ever took small values (0-255 seen) despite the
    4-byte width in every capture analyzed.
    """

    return (
        bytes([0x14, int(channel) & 0xFF])
        + int(magnitude).to_bytes(4, "little", signed=False)
        + b"\x00\x00"
        + int(frequency_code).to_bytes(4, "little", signed=False)
    )


def build_constant_force(magnitude: int, channel: int = 1) -> bytes:
    """Report 0x15 (Constant Force), 4 bytes.

    Reference check: build_constant_force(0x0b33) must equal
    bytes.fromhex("1501330b") - a real captured packet from the "Airspeed
    load" test (channel 1).

    CONFIRMED SIGNED (int16), not unsigned - a real hardware step test
    through the u16 boundary (32767 -> 32768 -> 33000 -> 40000 -> 50000 ->
    65535) showed the push reverse direction and then get progressively
    WEAKER approaching 65535, exactly matching int16 wraparound (32768 ==
    -32768, 65535 == -1). There is never a legitimate reason to pass a
    value above 32767 expecting "more force" - it means "reversed and
    weaker." magnitude is accepted signed (-32768..32767); values 0..32767
    encode identically whether treated as signed or unsigned, so this is
    fully backward compatible with every previously-verified positive
    value.

    `channel` defaults to 1 - every capture and every profile-driven write
    so far only ever used channel 1, and live hardware confirmed it drives
    PITCH (positive magnitude pitches the yoke toward the pilot), not roll.
    `channel=2` is an untested hypothesis (never seen in any capture) being
    probed live to check whether a second constant-force channel exists for
    roll - do not trust it as "confirmed" until a real hardware test proves
    it moves something.
    """

    return bytes([0x15, int(channel) & 0xFF]) + _s16(magnitude)


__all__ = (
    "VID", "PID", "DEFAULT_SERIAL_PORT", "SERIAL_BAUD",
    "ENABLE_FFB_COMMAND", "DISARM_GAIN_COMMAND", "FEATURE_REPORT_SEQUENCE",
    "CONNECTION_SETUP_SEQUENCE", "TEARDOWN_SEQUENCE", "CHANNEL_ENABLE_HEARTBEAT",
    "OPEN_COMMAND", "CONNECT_POLL_LOOP",
    "GAIN_PARAM_AF", "GAIN_PARAM_DAMPER", "GAIN_PARAM_INERTIA", "GAIN_PARAM_FRICTION",
    "GAIN_PARAM_OVERALL_INTENSITY", "GAIN_PARAM_MAX_TORQUE",
    "GAIN_PARAM_FRICTION_COMPENSATION", "GAIN_PARAM_FRICTION_COMPENSATION_INDEX",
    "CONDITION_EFFECT_BLOCK_INDEX", "AXIS_PARAMETER_BLOCK_OFFSET",
    "RUMBLE_PRESETS", "RUMBLE_CHANNEL_ARM", "CONSTANT_FORCE_OBSERVED_MAGNITUDE_RANGE",
    "AB6_VID", "AB6_PID", "AB6_DEFAULT_SERIAL_PORT", "AB6_ENABLE_FFB_COMMAND",
    "AB6_CONNECTION_SETUP_SEQUENCE", "AB6_CONNECT_POLL_LOOP", "AB6_TEARDOWN_SEQUENCE",
    "MozaDeviceProfile", "AY210_PROFILE", "AB6_PROFILE",
    "open_ay210", "open_serial", "send_hid", "send_feature_report",
    "send_serial", "background_poll_loop", "wait_for_connected",
    "replay_teardown", "replay_connection_setup", "replay_rumble_channel_arm",
    "build_set_condition", "build_set_periodic", "build_constant_force",
    "build_gain_param_write",
)
