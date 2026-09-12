"""Standalone MOZA AY210 force-feedback bench test - no MOZA SDK, no FFB-Bridge.

CONFIRMED WORKING (live-tested): this script drives the AY210's real spring
motor to full strength, physically indistinguishable from FFB-Bridge's own
"Centering Spring" self-test, using nothing but raw HID + a CDC serial port
this project reverse-engineered from USBPcap captures. No MOZA SDK, no
Pit House, no FFB-Bridge process running.

All of the general-purpose protocol bytes and connection machinery this
script uses now live in `muslimsim/hardware/moza_ay210_ffb_protocol.py`,
shared with the live bridge FFB engine so the two can never silently
diverge on the hard-won bytes. This script keeps only what's specific to
itself: FULL_SESSION_REPLAY (one exact captured session, used to physically
re-verify the raw protocol in isolation) and the demo's own print/hold/
timeout logic.

The AY210 speaks on three independent USB channels, and getting real force
out of it required all three, in the right order:
  1. CDC serial (endpoint 0x02 OUT, Windows COM4) - a periodic poll pattern
     that must run continuously or the firmware logs a real
     "Host Disconnect"; sustaining it long enough makes the firmware log
     "Host Connecting" -> "Host Connected".
  2. A one-time serial write of param 0x85 = 1 (ENABLE_FFB_COMMAND), sent
     once per power cycle after Host Connected. The firmware's own log ties
     it directly to steer.c's "steer set mode: 1" -> "Table 7, Param 49
     Written: 1" -> "steer set mode: 2" - mode 2 is force-feedback-active.
     This is a persistent per-power-cycle latch: once mode 2 is reached, it
     survives later disconnects/reconnects, so it will only log once even
     across many runs of this script against the same powered-on device.
  3. HID interrupt OUT (endpoint 0x03) - a reset-then-arm sequence (four
     parameters explicitly zeroed, then a gain-arm write) followed by the
     Condition-report coefficient ramp that is the actual spring effect,
     plus HID Feature reports (SET_REPORT over the control endpoint, 0x00)
     defining the effect blocks - both replayed verbatim from a real,
     isolated single-test capture ("Centering spring.pcapng").
Steps 1-2 without step 3 produce a correctly-armed device with no effect
configured; step 3 without steps 1-2 (every earlier version of this script)
produces a fully-acknowledged parameter table - every write confirmed via
the debug log - and zero physical force, because the motor stays gated in
steer mode 1 the whole time. Both were necessary; neither was sufficient
alone.

Endpoint 0x03 OUT / 0x83 IN and the Feature-report control endpoint all live
on USB interface 2 (HID) of the AY210 - confirmed from the capture's own
CONFIGURATION DESCRIPTOR. That HID path (VID 346E / PID 1001, usage_page=1
usage=4) is the same one already opened read-only by
muslimsim/devices/moza_a210.py; the serial channel is a second interface on
the same VID/PID, enumerated separately by Windows as a COM port.

Safety:
* The whole run is capped at HARD_TIMEOUT_SECONDS; a watchdog thread forces
  the real captured teardown sequence and closes both handles if the main
  sequence ever hangs.
* Ctrl+C, any exception, and normal completion all funnel through the same
  finally block.
* The spring magnitude reached here is exactly what FFB-Bridge's own
  Centering Spring self-test reaches - nothing is amplified beyond what MOZA
  already ships as a customer-facing hardware check.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from muslimsim.hardware.moza_ay210_ffb_protocol import (  # noqa: E402
    CHANNEL_ENABLE_HEARTBEAT,
    DEFAULT_SERIAL_PORT,
    DISARM_GAIN_COMMAND,
    ENABLE_FFB_COMMAND,
    SERIAL_BAUD,
    TEARDOWN_SEQUENCE,
    VID,
    PID,
    background_poll_loop as _shared_background_poll_loop,
    open_ay210 as _shared_open_ay210,
    open_serial as _shared_open_serial,
    replay_teardown as _shared_replay_teardown,
    send_hid as _shared_send_hid,
    send_serial as _shared_send_serial,
    wait_for_connected as _shared_wait_for_connected,
)

try:
    import hid  # noqa: F401  (imported for the module-level None-check pattern below)
except ImportError:
    hid = None

try:
    import serial  # noqa: F401
except ImportError:
    serial = None

SERIAL_PORT = DEFAULT_SERIAL_PORT
HARD_TIMEOUT_SECONDS = 60.0
EXTRA_HOLD_SECONDS = 10.0
WAIT_FOR_CONNECT_SECONDS = 15.0

# 236 packets, captured verbatim across all three channels from a fresh,
# isolated single-test capture (device address 63, VID 346E / PID 1001,
# "Centering spring.pcapng"), t=5.99s through t=8.95s of the source
# capture, retimed to start at 0. This superseded an earlier extraction
# from a longer mixed-test session that reproduced Host Connected and the
# gain-arm confirmation but still produced zero physical force - watching
# this fresh capture's own debug log revealed a 5-step reset-then-arm
# sequence the old extraction never included: writing params "af", "b0",
# "b1", "b2" to 0 (each confirmed via a read-back before the next write)
# BEFORE the gain-arm write to param "99". Covers: that full reset+arm
# sequence, the six SET_REPORT feature reports, effect/condition setup,
# and the complete Centering Spring coefficient ramp to full strength.
# Unmodified - see module docstring.
FULL_SESSION_REPLAY: List[Tuple[float, str, str]] = [
    (0.000000, "serial", "7e011e12500c"),
    (0.014991, "serial", "7e011e12510d"),
    (0.030954, "serial", "7e011e12520e"),
    (0.046945, "serial", "7e031e1285000043"),
    (0.062964, "serial", "7e031e12de00009c"),
    (0.078212, "serial", "7e021e12e117b5"),
    (0.094249, "serial", "7e031e12a9000067"),
    (0.110376, "serial", "7e031e12ae00006c"),
    (0.125292, "serial", "7e011e129955"),
    (0.141223, "serial", "7e031e12af00006d"),
    (0.156297, "serial", "7e031e12b000006e"),
    (0.171204, "serial", "7e031e12b100006f"),
    (0.186486, "serial", "7e031e12b2000070"),
    (0.202584, "serial", "7e031e12d7000095"),
    (0.217483, "serial", "7e031e12d8000096"),
    (0.233467, "serial", "7e031e12b8000076"),
    (0.248491, "serial", "7e031e12b9000077"),
    (0.268254, "serial", "7e031f12af00006e"),
    (0.296159, "serial", "7e031e12af00006d"),
    (0.312308, "serial", "7e031f12b000006f"),
    (0.344027, "serial", "7e031e12b000006e"),
    (0.359272, "serial", "7e031f12b1000070"),
    (0.391067, "serial", "7e031e12b100006f"),
    (0.407572, "serial", "7e031f12b2000071"),
    (0.438091, "serial", "7e031e12b2000070"),
    (0.454822, "serial", "7e031e12d7000095"),
    (0.456129, "hid", "1c03"),
    (0.470106, "serial", "7e031e12d8000096"),
    (0.485125, "serial", "7e031e12b8000076"),
    (0.501084, "serial", "7e031e12b9000077"),
    (0.519271, "feature", "21010000"),
    (0.532120, "serial", "7e031e12d7000095"),
    (0.533779, "hid", "110101ff7f000000000000ffff040000000000000000"),
    (0.548105, "serial", "7e031e12d8000096"),
    (0.563093, "serial", "7e031e12b8000076"),
    (0.579119, "serial", "7e031e12b9000077"),
    (0.594627, "feature", "21080000"),
    (0.612175, "hid", "110208ff7f000000000000ff00042823000000000000"),
    (0.642267, "feature", "21080000"),
    (0.658216, "hid", "110308ff7f000000000000ff00042823000000000000"),
    (0.689257, "feature", "21090000"),
    (0.706147, "hid", "110409ff7f000000000000ff00042823000000000000"),
    (0.735432, "feature", "210b0000"),
    (0.752098, "hid", "11050bff7f000000000000ff00042823000000000000"),
    (0.781429, "serial", "7e031e12d7000095"),
    (0.797092, "serial", "7e031e12d8000096"),
    (0.812950, "serial", "7e031e12b8000076"),
    (0.827992, "serial", "7e031e12b9000077"),
    (0.843955, "feature", "210a0000"),
    (0.860241, "hid", "11060aff7f000000000000ff00042823000000000000"),
    (0.891863, "hid", "110101ff7f000000000000ffff040000000000000000"),
    (0.892823, "hid", "15010000"),
    (0.894100, "hid", "130200000000400040ff7fff7f6606"),
    (0.895675, "hid", "130201000000400040ff7fff7f6606"),
    (0.896824, "hid", "13030000000000000000000000b77e"),
    (0.898738, "hid", "13030100000000000000000000b77e"),
    (0.899958, "hid", "130400000000000000000000000000"),
    (0.900684, "hid", "130401000000000000000000000000"),
    (0.901952, "hid", "130500000000000000000000000000"),
    (0.903712, "hid", "130501000000000000000000000000"),
    (0.906026, "hid", "130600000000000000000000000000"),
    (0.906714, "hid", "130601000000000000000000000000"),
    (0.909476, "serial", "7e031f12990064bc"),
    (0.937906, "serial", "7e011e129955"),
    (0.955036, "hid", "1df2"),
    (0.961243, "hid", "1304000000cd0ccd0ccc2ccc2c0000"),
    (0.962713, "hid", "1304010000cd0ccd0ccc2ccc2c0000"),
    (0.964207, "hid", "1a040101"),
    (0.965575, "hid", "130500000066066606660666060000"),
    (0.966916, "hid", "130501000066066606660666060000"),
    (0.968746, "hid", "1a050101"),
    (0.970155, "hid", "130600000066066606660666060000"),
    (0.970673, "hid", "130601000066066606660666060000"),
    (0.971663, "hid", "1a060101"),
    (0.974186, "hid", "13030100000000000000000000cc6c"),
    (0.974700, "hid", "13030000000000000000000000cc6c"),
    (0.977409, "hid", "13020100000b000b000d000d001f05"),
    (0.979447, "hid", "130200000010001000120012001f05"),
    (0.980726, "hid", "1a020101"),
    (1.018276, "hid", "13020100002c012c01610161011f05"),
    (1.019697, "hid", "1302000000ad01ad01f901f9011f05"),
    (1.048420, "hid", "1302010000bf01bf010e020e021f05"),
    (1.049720, "hid", "13020000007f027f02f002f0021f05"),
    (1.079576, "hid", "130201000059025902c302c3021f05"),
    (1.080698, "hid", "13020000005b035b03f203f2031f05"),
    (1.111565, "hid", "1302010000f502f5027b037b031f05"),
    (1.112714, "hid", "130200000039043904f804f8041f05"),
    (1.142575, "hid", "13020100008c038c032c042c041f05"),
    (1.143721, "hid", "130200000011051105f605f6051f05"),
    (1.174619, "hid", "130201000028042804e404e4041f05"),
    (1.175681, "hid", "1302000000f005f005fc06fc061f05"),
    (1.206184, "hid", "1302010000c204c204990599051f05"),
    (1.207665, "hid", "1302000000cc06cc06ff07ff071f05"),
    (1.237084, "hid", "1302010000590559054a064a061f05"),
    (1.238725, "hid", "1302000000a307a307fc08fc081f05"),
    (1.268046, "hid", "1302010000f005f005fc06fc061f05"),
    (1.268693, "hid", "13020000007b087b08fa09fa091f05"),
    (1.272087, "hid", "1df2"),
    (1.272742, "hid", "1a040101"),
    (1.273790, "hid", "1a050101"),
    (1.274749, "hid", "1a060101"),
    (1.275661, "hid", "1a020101"),
    (1.299587, "hid", "130201000089068906b107b1071f05"),
    (1.300717, "hid", "130200000056095609fc0afc0a1f05"),
    (1.331632, "hid", "130201000026072607680868081f05"),
    (1.332693, "hid", "1302000000360a360a030c030c1f05"),
    (1.363555, "hid", "1302010000c107c1071f091f091f05"),
    (1.364669, "hid", "1302000000140b140b080d080d1f05"),
    (1.395128, "hid", "13020100005b085b08d509d5091f05"),
    (1.396675, "hid", "1302000000f00bf00b0b0e0b0e1f05"),
    (1.427087, "hid", "1302010000f708f7088c0a8c0a1f05"),
    (1.428699, "hid", "1302000000ce0cce0c110f110f1f05"),
    (1.458052, "hid", "13020100008e098e093d0b3d0b1f05"),
    (1.458686, "hid", "1302000000a60da60d0f100f101f05"),
    (1.488991, "hid", "1302010000250a250aef0bef0b1f05"),
    (1.489682, "hid", "13020000007d0e7d0e0c110c111f05"),
    (1.520530, "hid", "1302010000be0abe0aa40ca40c1f05"),
    (1.521703, "hid", "1302000000590f590f0e120e121f05"),
    (1.551510, "hid", "1302010000550b550b550d550d1f05"),
    (1.552709, "hid", "1302000000311031100c130c131f05"),
    (1.583553, "hid", "1302010000f10bf10b0d0e0d0e1f05"),
    (1.584685, "hid", "130200000010111011131413141f05"),
    (1.585808, "hid", "1df2"),
    (1.586757, "hid", "1a040101"),
    (1.587670, "hid", "1a050101"),
    (1.588679, "hid", "1a060101"),
    (1.589705, "hid", "1a020101"),
    (1.615133, "hid", "13020100008b0c8b0cc20ec20e1f05"),
    (1.616733, "hid", "1302000000ec11ec11151515151f05"),
    (1.647323, "hid", "1302010000280d280d7b0f7b0f1f05"),
    (1.648717, "hid", "1302000000cc12cc121d161d161f05"),
    (1.678100, "hid", "1302010000be0dbe0d2b102b101f05"),
    (1.679714, "hid", "1302000000a213a213191719171f05"),
    (1.709582, "hid", "1302010000580e580ee010e0101f05"),
    (1.710703, "hid", "13020000007d147d141b181b181f05"),
    (1.741128, "hid", "1302010000f10ef10e951195111f05"),
    (1.742672, "hid", "1302000000591559151d191d191f05"),
    (1.772094, "hid", "1302010000890f890f461246121f05"),
    (1.773693, "hid", "1302000000311631161b1a1b1a1f05"),
    (1.802911, "hid", "13020100001d101d10f512f5121f05"),
    (1.804002, "hid", "130200000005170517151b151b1f05"),
    (1.833610, "hid", "1302010000b410b410a713a7131f05"),
    (1.834740, "hid", "1302000000dd17dd17131c131c1f05"),
    (1.864785, "hid", "13020100004c114c11591459141f05"),
    (1.865700, "hid", "1302000000b618b618121d121d1f05"),
    (1.896821, "hid", "1302010000e811e811111511151f05"),
    (1.897669, "hid", "130200000095199519181e181e1f05"),
    (1.898820, "hid", "1df2"),
    (1.899745, "hid", "1a040101"),
    (1.900739, "hid", "1a050101"),
    (1.902679, "hid", "1a060101"),
    (1.904684, "hid", "1a020101"),
    (1.927596, "hid", "13020100007e127e12c215c2151f05"),
    (1.928822, "hid", "13020000006b1a6b1a151f151f1f05"),
    (1.960455, "hid", "13020100001f131f137e167e161f05"),
    (1.961690, "hid", "1302000000501b501b222022201f05"),
    (1.990995, "hid", "1302010000b313b3132d172d171f05"),
    (1.991688, "hid", "1302000000251c251c1c211c211f05"),
    (2.006827, "serial", "7e031e12de00009c"),
    (2.021854, "serial", "7e021e12e117b5"),
    (2.036734, "serial", "7e011e129955"),
    (2.053039, "hid", "1302010000e014e014901890181f05"),
    (2.053757, "hid", "1302000000d31dd31d162316231f05"),
    (2.083789, "hid", "130201000078157815411941191f05"),
    (2.084708, "hid", "1302000000ab1eab1e142414241f05"),
    (2.115299, "hid", "130201000011161116f619f6191f05"),
    (2.116706, "hid", "1302000000871f871f172517251f05"),
    (2.146779, "hid", "1302010000ab16ab16ab1aab1a1f05"),
    (2.147672, "hid", "130200000061206120182618261f05"),
    (2.177736, "hid", "1302010000421742175c1b5c1b1f05"),
    (2.178738, "hid", "130200000039213921162716271f05"),
    (2.209602, "hid", "1302010000dd17dd17131c131c1f05"),
    (2.210696, "hid", "1302000000172217221b281b281f05"),
    (2.240555, "hid", "130201000074187418c51cc51c1f05"),
    (2.241714, "hid", "1302000000ef22ef22192919291f05"),
    (2.243713, "hid", "1df2"),
    (2.245693, "hid", "1a040101"),
    (2.246684, "hid", "1a050101"),
    (2.247670, "hid", "1a060101"),
    (2.248696, "hid", "1a020101"),
    (2.271564, "hid", "13020100000b190b19761d761d1f05"),
    (2.272706, "hid", "1302000000c723c723172a172a1f05"),
    (2.301544, "hid", "13020100009d199d19221e221e1f05"),
    (2.302692, "hid", "1302000000972497240d2b0d2b1f05"),
    (2.332669, "hid", "1302010000351a351ad51ed51e1f05"),
    (2.333710, "hid", "1302000000702570250b2c0b2c1f05"),
    (2.363568, "hid", "1302010000cc1acc1a861f861f1f05"),
    (2.364688, "hid", "130200000047264726092d092d1f05"),
    (2.394642, "hid", "1302010000631b631b382038201f05"),
    (2.395688, "hid", "13020000001f271f27072e072e1f05"),
    (2.425403, "hid", "1302010000f91bf91be920e9201f05"),
    (2.426697, "hid", "1302000000f627f627032f032f1f05"),
    (2.456488, "hid", "1302010000901c901c9b219b211f05"),
    (2.457684, "hid", "1302000000ce28ce28023002301f05"),
    (2.488632, "hid", "13020100002c1d2c1d522252221f05"),
    (2.489737, "hid", "1302000000ad29ad29073107311f05"),
    (2.519318, "hid", "1302010000c31dc31d032303231f05"),
    (2.520707, "hid", "1302000000842a842a053205321f05"),
    (2.550334, "hid", "13020100005a1e5a1eb523b5231f05"),
    (2.551728, "hid", "13020000005c2b5c2b033303331f05"),
    (2.553826, "hid", "1df2"),
    (2.554705, "hid", "1a040101"),
    (2.555690, "hid", "1a050101"),
    (2.556692, "hid", "1a060101"),
    (2.557704, "hid", "1a020101"),
    (2.582334, "hid", "1302010000f61ef61e6d246d241f05"),
    (2.583725, "hid", "13020000003b2c3b2c093409341f05"),
    (2.613648, "hid", "13020100008e1f8e1f202520251f05"),
    (2.614726, "hid", "1302000000152d152d093509351f05"),
    (2.644934, "hid", "130201000027202720d325d3251f05"),
    (2.645700, "hid", "1302000000ee2dee2d093609361f05"),
    (2.675639, "hid", "1302010000bd20bd20842684261f05"),
    (2.676700, "hid", "1302000000c42ec42e053705371f05"),
    (2.707978, "hid", "1302010000592159213b273b271f05"),
    (2.708715, "hid", "1302000000a32fa32f0b380b381f05"),
    (2.739292, "hid", "1302010000f321f321f127f1271f05"),
    (2.740701, "hid", "1302000000803080300f390f391f05"),
    (2.770180, "hid", "130201000089228922a228a2281f05"),
    (2.771752, "hid", "1302000000573157310b3a0b3a1f05"),
    (2.801159, "hid", "130201000020232023532953291f05"),
    (2.802730, "hid", "13020000002e322e32093b093b1f05"),
    (2.832027, "hid", "1302010000b723b723042a042a1f05"),
    (2.832694, "hid", "130200000005330533063c063c1f05"),
    (2.863967, "hid", "130201000053245324bb2abb2a1f05"),
    (2.864714, "hid", "1302000000e433e4330c3d0c3d1f05"),
    (2.865697, "hid", "1df2"),
    (2.866706, "hid", "1a040101"),
    (2.868757, "hid", "1a050101"),
    (2.869716, "hid", "1a060101"),
    (2.870712, "hid", "1a020101"),
    (2.895584, "hid", "1302010000ed24ed24712b712b1f05"),
    (2.896714, "hid", "1302000000c034c0340f3e0f3e1f05"),
    (2.926553, "hid", "130201000083258325222c222c1f05"),
    (2.927687, "hid", "1302000000973597350c3f0c3f1f05"),
    (2.957958, "hid", "130201000014261426cc2ccc2c1f05"),
    (2.958713, "hid", "130200000066366636004000401f05"),
]

# Roughly when the interesting part begins: the "1c03" reconnect that leads
# straight into the reset+arm sequence and the coefficient ramp.
TEST_STARTS_AT = 0.25


# The connect/enable/teardown machinery below is shared, proven-identical
# code from muslimsim/hardware/moza_ay210_ffb_protocol.py - aliased here
# under this script's original names so the rest of the file (and anyone
# comparing this script against its own history) doesn't need to change.
open_ay210 = _shared_open_ay210
send_hid = _shared_send_hid
send_serial = _shared_send_serial
background_poll_loop = _shared_background_poll_loop
wait_for_connected = _shared_wait_for_connected


def open_serial() -> "serial.Serial":
    return _shared_open_serial(SERIAL_PORT)


def replay_full_session(device: "hid.device", ser: "serial.Serial", lock: threading.Lock) -> None:
    print(f"-- replaying {len(FULL_SESSION_REPLAY)} real packets across HID + feature + serial --")
    start = time.monotonic()
    announced = False
    for offset, kind, hexstr in FULL_SESSION_REPLAY:
        target = start + offset
        now = time.monotonic()
        if target > now:
            time.sleep(target - now)
        if not announced and offset >= TEST_STARTS_AT:
            print()
            print(">>> TEST STARTING NOW - push/wiggle the yoke and feel for any change <<<")
            announced = True
        if kind == "hid":
            send_hid(device, hexstr)
        elif kind == "feature":
            device.send_feature_report(bytes.fromhex(hexstr))
        elif kind == "serial":
            send_serial(ser, lock, hexstr)


def hold_stiff(device: "hid.device", seconds: float) -> None:
    """Keep resending the real channel-enable heartbeat so the final ramped
    state stays alive for a while after the recorded session ends, instead
    of lapsing the instant playback stops."""

    print(f"-- extending the hold for {seconds:.0f}s so there is time to push the yoke --")
    start = time.monotonic()
    next_heartbeat = start
    next_tick = start + 1.0
    while True:
        now = time.monotonic()
        if now - start >= seconds:
            return
        if now >= next_heartbeat:
            for hexstr in CHANNEL_ENABLE_HEARTBEAT:
                send_hid(device, hexstr)
            next_heartbeat = now + 0.300
        if now >= next_tick:
            remaining = seconds - (now - start)
            print(f"   ...{remaining:.0f}s remaining")
            next_tick = now + 1.0
        time.sleep(0.005)


def replay_teardown(device: "hid.device") -> None:
    print(f"-- teardown: {len(TEARDOWN_SEQUENCE)} packets --")
    _shared_replay_teardown(device)


def main() -> int:
    device = None
    ser = None
    watchdog_triggered = threading.Event()
    poll_stop = threading.Event()
    poll_thread: "threading.Thread | None" = None
    serial_lock = threading.Lock()

    def watchdog() -> None:
        if watchdog_triggered.wait(HARD_TIMEOUT_SECONDS):
            return
        print("WATCHDOG: hard timeout reached, forcing teardown", file=sys.stderr)
        if device is not None:
            try:
                replay_teardown(device)
            except Exception:
                pass

    watchdog_thread = threading.Thread(target=watchdog, daemon=True)
    watchdog_thread.start()

    try:
        print(f"Opening AY210 serial port ({SERIAL_PORT})...")
        ser = open_serial()
        print("Opening MOZA AY210 HID interface...")
        device = open_ay210()

        poll_thread = threading.Thread(
            target=background_poll_loop, args=(ser, poll_stop, serial_lock), daemon=True
        )
        poll_thread.start()
        print(f"-- polling for up to {WAIT_FOR_CONNECT_SECONDS:.1f}s, watching the device's own "
              f"debug log for 'Host Connected' (polling keeps running for the rest of this "
              f"program, unlike earlier versions, since stopping it was seen to trigger a real "
              f"Host Disconnect) --")
        connected = wait_for_connected(ser, WAIT_FOR_CONNECT_SECONDS)
        if not connected:
            print("WARNING: never saw 'Host Connected' in the debug log - proceeding anyway.",
                  file=sys.stderr)

        print("Sending the one-time 'enable force feedback' write (param 0x85=1).")
        send_serial(ser, serial_lock, ENABLE_FFB_COMMAND)
        time.sleep(0.3)
        print("Both channels open and FFB enabled. Replaying the complete real session verbatim.")
        print("Nothing is invented below this line - every byte was captured live.")
        replay_full_session(device, ser, serial_lock)
        print()
        print("Recorded session complete.")
        hold_stiff(device, EXTRA_HOLD_SECONDS)
        return 0
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted - tearing down.")
        return 130
    finally:
        watchdog_triggered.set()
        if device is not None:
            try:
                replay_teardown(device)
                print("Teardown complete.")
            except Exception as exc:
                print(f"WARNING: teardown failed cleanly: {exc}", file=sys.stderr)
        if ser is not None:
            try:
                send_serial(ser, serial_lock, DISARM_GAIN_COMMAND)
            except Exception:
                pass
        poll_stop.set()
        if poll_thread is not None:
            poll_thread.join(timeout=1.0)
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        if device is not None:
            try:
                device.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
