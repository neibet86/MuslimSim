# MOZA AB6 calibration parameter map (NOT AY210 - see caveat below)

Found via live USBPcap capture while MOZA Cockpit was open and its
Basic Settings / Physics Model Settings sliders were changed one at a
time, correlating each change to the resulting
`[INFO]param_manage.c:340 Table N, Param M Written: <raw> <float>`
firmware log line. **This session's later correction: Cockpit was
apparently targeting the AB6 joystick during this probing, not the
AY210 yoke this whole project otherwise builds against - do not assume
these param numbers apply to the AY210 without re-verifying.** The
METHOD (one-field-at-a-time capture + Table/Param log correlation, and
the checksum formula below) is device-agnostic and was reused to redo
this properly for the AY210.

## Confirmed parameter map (AB6)

| UI field | Parameter | Raw byte name |
|---|---|---|
| Gain (Physics Model Settings) | Table 7, Param 15 | `af` (0xAF) |
| Damper | Table 7, Param 16 | `b0` (0xB0) |
| Overall Force Feedback Intensity | Table 7, Param 52 | - |
| Inertia | Table 7, Param 53 | `b1` (0xB1) |
| Friction | Table 7, Param 54 | `b2` (0xB2) |
| Maximum Torque Output | Table 7, Param 100 | - |
| Spring (Basic Settings) | Table 8, Param 65 | - (integer 0-100, not float) |
| Gain-arm (already known from AY210 work) | Table 7, Param 101 | `99` (0x99) |

Param 17/18 (Table 7) move in lockstep with Param 100 at a consistent
~1.214x ratio every step observed - likely a derived/calibration pair,
not independently adjustable.

## Checksum formula for constructing new single-value writes

Verified against 8+ independent real captured examples (device-agnostic -
same formula confirmed separately on the AY210):

```
checksum = (0x7e + 0x03 + 0x1f + 0x12 + param + index + value + 13) & 0xFF
```

Write shape: `7e 03 1f 12 PARAM INDEX VALUE CHECKSUM` (single-byte value,
0-100 encodes a 0.0-1.0 float via byte/100, except where noted as raw
integer instead, e.g. Table 8 Param 65).

## "Calibration and Reset" (axis calibration)

Uploads a large 128-entry lookup table (Table 5, params 0-127) whose
values are unstructured binary (not meaningful as float32) - a raw
calibration/response curve, not named settings. A few small per-axis
constants also get written (Table 3 & 4, params 26-29, values 0.1 and
20.0 each, identical across both tables - likely per-axis deadzone/noise
threshold). MuslimSim does not need to replicate this: calibration is a
one-time Cockpit-side operation, and MuslimSim consumes the resulting
already-calibrated raw axis values through the standard HID input report
(`muslimsim/devices/moza_a210.py`'s `decode_moza_a210_report`) regardless
of what curve is currently loaded on the device.
