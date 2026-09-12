"""Discover MOZA Flight SDK devices and list their parameters/commands - read-only.

Studio's SAVED CALIBRATION panel for MOZA A210/AB6 currently only writes a
local JSON profile.  No Moza output protocol is present anywhere in this
project, so nothing today makes OVERALL/MAX TORQUE/DAMPER/FRICTION/INERTIA/
SPRING or the FLIGHT EFFECTS toggles move the physical AY210 yoke base or the
AB6 base.  The user wants those saved numbers to actually drive the hardware
without needing Moza Cockpit's own window open.

MOZA ships two separate SDKs.  The Racing SDK (`RS21_sdk`) has no flight-base
awareness at all and its own readme requires "MOZA Pit House (SDK version)".
The Flight SDK (`MOZA_SDK`, this one) covers `MOZA_DC_AS` aircraft devices -
wheelbase/stick/throttle/control panel/screen - and its docs only ever
mention a generic background "device service", never Cockpit or Pit House by
name.  That is the SDK this probe uses, and the two open questions before any
line of production code gets written are:

  1. Are the AY210 and AB6 visible to this SDK at all on this machine?
  2. Does "device service" mean Moza Cockpit's GUI window has to be running,
     or does discovery work with Cockpit fully closed?

This tool answers both empirically instead of guessing. It initializes the
SDK, waits for the device service to enumerate devices (matching the 5s wait
in MOZA's own `c_api_example.c`), lists every device found, and for each
MOZA_DC_AS device opens it and prints its full parameter list and command
list - the real IDs and names the vendor's own docs say to read from
`Moza_DeviceParameterGetList`/`Moza_DeviceCommandGetList`, not guessed. It
cross-references those names against Studio's own calibration field names
(`muslimsim/hardware/moza_presets.py`) so a likely match for OVERALL/MAX
TORQUE/DAMPER/FRICTION/INERTIA/SPRING is flagged inline.

READ-ONLY, on purpose: this script only calls Moza_Initialize, the *_GetList
functions, and (unless --skip-value-read) a single Moza_DeviceParameterGetValueSync
read of one already-readable parameter, to prove a live value round-trip.
It never calls Moza_DeviceParameterSetValue(Sync), never calls
Moza_DeviceCommandSend(Sync), and never sends any MainCtrl_Ffb* command. No
torque, no effect, no vibration, no motor motion of any kind is possible from
this script. It is safe to run with the AY210/AB6 powered and connected.

Recommended test sequence for question 2 above:

    1. Close Moza Cockpit completely (check Task Manager too).
    2. python tools/probe_moza_flight_sdk.py
    3. Note whether Moza_Initialize succeeds and whether the AY210/AB6 show
       up in the device list.
    4. Open Moza Cockpit and run the same command again.
    5. Compare the two runs.

Usage:
    python tools/probe_moza_flight_sdk.py
    python tools/probe_moza_flight_sdk.py --dll "C:\\path\\to\\MOZA_SDK.dll"
    python tools/probe_moza_flight_sdk.py --wait 8 --timeout-ms 5000
    python tools/probe_moza_flight_sdk.py --skip-value-read
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import time
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

DEFAULT_WAIT_SECONDS = 5.0
DEFAULT_TIMEOUT_MS = 3000


# ---------------------------------------------------------------------------
# Locating MOZA_SDK.dll
# ---------------------------------------------------------------------------

def _find_dll(explicit: str | None) -> Path:
    """Resolve the path to MOZA_SDK.dll without hardcoding a machine-specific path."""
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"--dll path does not exist: {candidate}")

    env = os.environ.get("MOZA_SDK_DLL")
    if env and Path(env).is_file():
        return Path(env)

    # Future home once the SDK is vendored into the project (not done yet).
    vendored = PROJECT / "vendor" / "moza_sdk" / "bin" / "MOZA_SDK.dll"
    if vendored.is_file():
        return vendored

    # The Flight SDK download, wherever under the user's Downloads it landed.
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        candidates = sorted(downloads.glob("**/MOZA_SDK/x64-release/bin/MOZA_SDK.dll"))
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        "Could not find MOZA_SDK.dll. Pass --dll <path>, set the MOZA_SDK_DLL "
        "environment variable, or place it at vendor/moza_sdk/bin/MOZA_SDK.dll."
    )


# ---------------------------------------------------------------------------
# ctypes structures, matching x64-release/include/moza/moza.h exactly.
#
# MOZA_LOG_CONTEXT is declared BEFORE the header's `#pragma pack(push, 1)`,
# so it keeps natural/default alignment. Every other struct below (MOZA_VALUE,
# MOZA_DEVICE_INFO, MOZA_PARAMETER_INFO, MOZA_COMMAND_INFO) is declared INSIDE
# that pack(1) region, so each one sets _pack_ = 1 to match.
# ---------------------------------------------------------------------------

class MOZA_LOG_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("level", ctypes.c_int32),
        ("message", ctypes.c_char_p),
        ("messageSize", ctypes.c_uint32),
        ("category", ctypes.c_char_p),
        ("categorySize", ctypes.c_uint32),
        ("reserved", ctypes.c_uint64 * 4),
    ]


class _MOZA_STRING_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("data", ctypes.c_char_p), ("size", ctypes.c_uint32)]


class _MOZA_BINARY_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("size", ctypes.c_uint32)]


class _MOZA_LIST_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("items", ctypes.c_void_p), ("size", ctypes.c_uint32)]


class _MOZA_VALUE_DATA(ctypes.Union):
    _pack_ = 1
    _fields_ = [
        ("intValue", ctypes.c_int64),
        ("uintValue", ctypes.c_uint64),
        ("doubleValue", ctypes.c_double),
        ("boolValue", ctypes.c_uint8),
        ("stringValue", _MOZA_STRING_VALUE),
        ("binaryValue", _MOZA_BINARY_VALUE),
        ("listValue", _MOZA_LIST_VALUE),
    ]


class MOZA_VALUE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("type", ctypes.c_int32),
        ("data", _MOZA_VALUE_DATA),
    ]


class MOZA_DEVICE_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("name", ctypes.c_char * 64),
        ("portName", ctypes.c_char * 256),
        ("vendorId", ctypes.c_uint16),
        ("productId", ctypes.c_uint16),
        ("category", ctypes.c_int32),
        ("type", ctypes.c_int32),
        ("state", ctypes.c_int32),
        ("hidDeviceCount", ctypes.c_uint8),
        ("reserved", ctypes.c_void_p),
    ]


class MOZA_PARAMETER_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("id", ctypes.c_int32),
        ("name", ctypes.c_char * 64),
        ("readable", ctypes.c_uint8),
        ("writable", ctypes.c_uint8),
        ("reserved", ctypes.c_void_p),
    ]


class MOZA_COMMAND_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("id", ctypes.c_int32),
        ("name", ctypes.c_char * 64),
        ("requestArgumentsCount", ctypes.c_uint8),
        ("responseArgumentsCount", ctypes.c_uint8),
        ("reserved", ctypes.c_void_p),
    ]


MOZA_LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(MOZA_LOG_CONTEXT), ctypes.c_void_p)

# --- enum/errno name tables, straight from moza.h's comments -----------------

ERRNO_NAMES = {
    -1: "UNKNOWN",
    0: "NO_ERROR",
    1: "SERVICE_NOT_FOUND",
    2: "SERVICE_VERSION_MISMATCH",
    3: "INVALID_ARGUMENT",
    4: "NOT_INITIALIZED",
    5: "ALREADY_INITIALIZED",
    6: "BUFFER_TOO_SMALL",
    7: "DEVICE_NOT_FOUND",
    8: "DEVICE_NOT_OPEN",
    9: "INVALID_HANDLE",
    10: "BUSY",
    11: "TIMEOUT",
    12: "NOT_SUPPORTED",
    13: "PARAMETER_READ_COMMAND_ERROR",
    14: "PARAMETER_WRITE_COMMAND_ERROR",
    15: "INDEX_OUT_OF_BOUNDS",
    16: "PENDING",
}

CATEGORY_NAMES = {0: "UNKNOWN", 1: "RS (racing)", 2: "AS (aircraft/flight)"}
STATE_NAMES = {0: "UNKNOWN", 1: "NORMAL", 2: "DISCONNECTED"}
VALUE_TYPE_NAMES = {
    0: "INVALID", 1: "NULL", 2: "INT", 3: "UINT", 4: "DOUBLE",
    5: "BOOL", 6: "STRING", 7: "BINARY", 8: "LIST",
}
AS_TYPE_BITS = (
    (1 << 0, "WHEELBASE"),
    (1 << 1, "THROTTLE"),
    (1 << 2, "RUDDER"),
    (1 << 3, "MOTOR"),
    (1 << 4, "STICK"),
    (1 << 5, "THROTTLE_PANEL"),
    (1 << 6, "OTHER/ACCESSORY"),
    (1 << 7, "FORCE_FEEDBACK_THROTTLE"),
    (1 << 8, "CONTROL_PANEL"),
    (1 << 11, "SCREEN"),
)


def errno_name(value: int) -> str:
    return f"{ERRNO_NAMES.get(value, 'ERRNO')}({value})"


def describe_as_type(value: int) -> str:
    matched = [name for bit, name in AS_TYPE_BITS if value & bit]
    return "+".join(matched) if matched else f"0x{value:X}"


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Studio field cross-reference (best-effort; never fatal if it can't import).
# ---------------------------------------------------------------------------

def _studio_field_keywords() -> dict[str, set[str]]:
    try:
        from muslimsim.hardware.moza_presets import MOZA_EDITABLE_KEYS
    except Exception:
        return {}
    keywords: dict[str, set[str]] = {}
    for field in MOZA_EDITABLE_KEYS:
        base = field
        for suffix in ("_strength", "_enabled", "_brightness", "_reversal", "_deadzone"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        words = {word for word in base.split("_") if len(word) >= 4}
        if words:
            keywords[field] = words
    return keywords


def _studio_match(param_name: str, field_keywords: dict[str, set[str]]) -> str | None:
    tokens = set(re.split(r"[^a-z0-9]+", param_name.lower()))
    for field, words in field_keywords.items():
        if tokens & words:
            return field
    return None


# ---------------------------------------------------------------------------
# SDK wrapper
# ---------------------------------------------------------------------------

class MozaSdk:
    """Thin, read-only ctypes wrapper. Binds only what this probe needs."""

    def __init__(self, dll_path: Path):
        self.lib = ctypes.CDLL(str(dll_path))
        self._bind()
        self._log_cb_ref = None  # keep the CFUNCTYPE instance alive

    def _bind(self) -> None:
        lib = self.lib

        lib.Moza_Initialize.restype = ctypes.c_int32
        lib.Moza_Initialize.argtypes = []

        lib.Moza_Shutdown.restype = None
        lib.Moza_Shutdown.argtypes = []

        lib.Moza_GetSdkVersionString.restype = ctypes.c_char_p
        lib.Moza_GetSdkVersionString.argtypes = []

        lib.Moza_SetLogCallback.restype = ctypes.c_int32
        lib.Moza_SetLogCallback.argtypes = [MOZA_LOG_CALLBACK, ctypes.c_void_p]

        lib.Moza_DeviceGetList.restype = ctypes.c_int32
        lib.Moza_DeviceGetList.argtypes = [
            ctypes.POINTER(MOZA_DEVICE_INFO), ctypes.POINTER(ctypes.c_uint32)
        ]

        lib.Moza_DeviceOpen.restype = ctypes.c_int32
        lib.Moza_DeviceOpen.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]

        lib.Moza_DeviceClose.restype = ctypes.c_int32
        lib.Moza_DeviceClose.argtypes = [ctypes.c_void_p]

        lib.Moza_DeviceParameterGetList.restype = ctypes.c_int32
        lib.Moza_DeviceParameterGetList.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(MOZA_PARAMETER_INFO), ctypes.POINTER(ctypes.c_uint32)
        ]

        lib.Moza_DeviceCommandGetList.restype = ctypes.c_int32
        lib.Moza_DeviceCommandGetList.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(MOZA_COMMAND_INFO), ctypes.POINTER(ctypes.c_uint32)
        ]

        lib.Moza_DeviceParameterGetValueSync.restype = ctypes.c_int32
        lib.Moza_DeviceParameterGetValueSync.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(MOZA_VALUE)
        ]

        lib.Moza_ValueDestroy.restype = None
        lib.Moza_ValueDestroy.argtypes = [ctypes.POINTER(MOZA_VALUE)]

    def set_log_callback(self, fn) -> None:
        self._log_cb_ref = MOZA_LOG_CALLBACK(fn)
        self.lib.Moza_SetLogCallback(self._log_cb_ref, None)

    def initialize(self) -> int:
        return self.lib.Moza_Initialize()

    def shutdown(self) -> None:
        self.lib.Moza_Shutdown()

    def sdk_version(self) -> str:
        raw = self.lib.Moza_GetSdkVersionString()
        return raw.decode("utf-8", errors="replace") if raw else "?"

    def device_list(self) -> list[MOZA_DEVICE_INFO]:
        count = ctypes.c_uint32(0)
        err = self.lib.Moza_DeviceGetList(None, ctypes.byref(count))
        if err != 0 or count.value == 0:
            return []
        arr = (MOZA_DEVICE_INFO * count.value)()
        got = ctypes.c_uint32(count.value)
        err = self.lib.Moza_DeviceGetList(arr, ctypes.byref(got))
        if err != 0:
            raise RuntimeError(f"Moza_DeviceGetList(data) failed: {errno_name(err)}")
        return list(arr)[: got.value]

    def device_open(self, device_id: int):
        handle = ctypes.c_void_p()
        err = self.lib.Moza_DeviceOpen(device_id, ctypes.byref(handle))
        if err != 0:
            raise RuntimeError(f"Moza_DeviceOpen failed: {errno_name(err)}")
        return handle

    def device_close(self, handle) -> None:
        self.lib.Moza_DeviceClose(handle)

    def parameter_list(self, handle) -> list[MOZA_PARAMETER_INFO]:
        count = ctypes.c_uint32(0)
        err = self.lib.Moza_DeviceParameterGetList(handle, None, ctypes.byref(count))
        if err != 0 or count.value == 0:
            return []
        arr = (MOZA_PARAMETER_INFO * count.value)()
        got = ctypes.c_uint32(count.value)
        err = self.lib.Moza_DeviceParameterGetList(handle, arr, ctypes.byref(got))
        if err != 0:
            raise RuntimeError(f"Moza_DeviceParameterGetList(data) failed: {errno_name(err)}")
        return list(arr)[: got.value]

    def command_list(self, handle) -> list[MOZA_COMMAND_INFO]:
        count = ctypes.c_uint32(0)
        err = self.lib.Moza_DeviceCommandGetList(handle, None, ctypes.byref(count))
        if err != 0 or count.value == 0:
            return []
        arr = (MOZA_COMMAND_INFO * count.value)()
        got = ctypes.c_uint32(count.value)
        err = self.lib.Moza_DeviceCommandGetList(handle, arr, ctypes.byref(got))
        if err != 0:
            raise RuntimeError(f"Moza_DeviceCommandGetList(data) failed: {errno_name(err)}")
        return list(arr)[: got.value]

    def parameter_get_value(self, handle, parameter_id: int, timeout_ms: int):
        """Read-only. Never writes: there is no SetValue call anywhere in this class."""
        value = MOZA_VALUE()
        err = self.lib.Moza_DeviceParameterGetValueSync(handle, parameter_id, timeout_ms, ctypes.byref(value))
        if err != 0:
            return err, None
        try:
            result = _format_value(value)
        finally:
            self.lib.Moza_ValueDestroy(ctypes.byref(value))
        return err, result


def _format_value(value: MOZA_VALUE) -> str:
    vtype = value.type
    data = value.data
    if vtype == 2:  # INT
        return str(data.intValue)
    if vtype == 3:  # UINT
        return str(data.uintValue)
    if vtype == 4:  # DOUBLE
        return f"{data.doubleValue:g}"
    if vtype == 5:  # BOOL
        return "true" if data.boolValue else "false"
    if vtype == 6:  # STRING
        return _decode(data.stringValue.data) if data.stringValue.data else ""
    return f"<{VALUE_TYPE_NAMES.get(vtype, vtype)}>"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dll", default=None, help="Explicit path to MOZA_SDK.dll")
    parser.add_argument("--wait", type=float, default=DEFAULT_WAIT_SECONDS,
                         help=f"Seconds to wait for the device service to enumerate (default {DEFAULT_WAIT_SECONDS})")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS,
                         help=f"Timeout for the single parameter value read (default {DEFAULT_TIMEOUT_MS})")
    parser.add_argument("--skip-value-read", action="store_true",
                         help="Skip the single read-only parameter value read entirely")
    parser.add_argument("--quiet-log", action="store_true",
                         help="Do not print forwarded SDK internal log messages")
    args = parser.parse_args()

    print("SAFETY: this script only initializes the SDK, lists devices, lists")
    print("parameters/commands, and (unless --skip-value-read) performs one")
    print("read-only parameter value fetch. No SetValue, no CommandSend, no")
    print("MainCtrl_Ffb* command is called anywhere in this script.\n")

    try:
        dll_path = _find_dll(args.dll)
    except FileNotFoundError as error:
        print(str(error))
        return 2
    print(f"Using MOZA_SDK.dll: {dll_path}\n")

    try:
        sdk = MozaSdk(dll_path)
    except OSError as error:
        print(f"Could not load MOZA_SDK.dll: {error}")
        return 2

    if not args.quiet_log:
        def _on_log(context_ptr, _user_data):
            try:
                ctx = context_ptr.contents
                level = ctx.level
                message = ctx.message[: ctx.messageSize].decode("utf-8", errors="replace") if ctx.message else ""
                category = ctx.category[: ctx.categorySize].decode("utf-8", errors="replace") if ctx.category else ""
                level_name = {0: "DEBUG", 1: "INFO", 2: "WARNING", 3: "CRITICAL", 4: "FATAL"}.get(level, str(level))
                print(f"  [sdk-log {level_name}] {category}: {message}")
            except Exception as error:  # never let a callback exception reach the C caller
                print(f"  [sdk-log] <callback decode error: {error}>")

        sdk.set_log_callback(_on_log)

    err = sdk.initialize()
    print(f"Moza_Initialize -> {errno_name(err)}")
    if err == 1:  # SERVICE_NOT_FOUND
        print("The MOZA device service is not reachable. This is the exact")
        print("condition question 2 in this script's docstring is about -")
        print("run this again with Moza Cockpit closed AND with it open, and")
        print("compare the two results.")
        return 1
    if err not in (0, 5):  # 5 = ALREADY_INITIALIZED, harmless
        print("Moza_Initialize did not succeed; stopping before touching any device.")
        return 1

    try:
        print(f"SDK version: {sdk.sdk_version()}\n")

        print(f"Waiting {args.wait:.1f}s for the device service to enumerate devices "
              f"(matches the vendor's own c_api_example.c)...")
        time.sleep(args.wait)

        devices = sdk.device_list()
        print(f"\nDiscovered {len(devices)} device(s).\n")

        if not devices:
            print("No MOZA devices found. If Moza Cockpit was closed for this run,")
            print("try again with it open to see whether that changes anything -")
            print("that comparison is exactly what determines the dependency.")
            return 0

        field_keywords = _studio_field_keywords()
        as_device_count = 0

        for info in devices:
            name = _decode(info.name)
            port = _decode(info.portName)
            category = CATEGORY_NAMES.get(info.category, str(info.category))
            state = STATE_NAMES.get(info.state, str(info.state))
            type_desc = describe_as_type(info.type) if info.category == 2 else f"0x{info.type:X}"
            print(f"- id={info.id} name={name!r} category={category} type={type_desc} state={state}")
            print(f"  port={port!r} vendorId=0x{info.vendorId:04X} productId=0x{info.productId:04X} "
                  f"hidDeviceCount={info.hidDeviceCount}")

            if info.category != 2:  # only MOZA_DC_AS is relevant to the AY210/AB6
                print("  (not an MOZA_DC_AS device - skipping parameter/command dump)\n")
                continue

            as_device_count += 1
            handle = None
            try:
                handle = sdk.device_open(info.id)

                params = sdk.parameter_list(handle)
                print(f"  {len(params)} parameter(s):")
                first_readable = None
                for p in params:
                    pname = _decode(p.name)
                    match = _studio_match(pname, field_keywords)
                    flag = f"   <-- looks related to Studio's '{match}'" if match else ""
                    print(f"    id={p.id:<6} readable={bool(p.readable)!s:<5} "
                          f"writable={bool(p.writable)!s:<5} name={pname}{flag}")
                    if first_readable is None and p.readable:
                        first_readable = (p.id, pname)

                commands = sdk.command_list(handle)
                print(f"  {len(commands)} command(s):")
                for c in commands:
                    cname = _decode(c.name)
                    print(f"    id={c.id:<6} reqArgs={c.requestArgumentsCount} "
                          f"respArgs={c.responseArgumentsCount} name={cname}")

                if not args.skip_value_read and first_readable is not None:
                    pid, pname = first_readable
                    print(f"  Reading one value (read-only): parameter id={pid} name={pname!r} ...")
                    read_err, value_str = sdk.parameter_get_value(handle, pid, args.timeout_ms)
                    if read_err == 0:
                        print(f"    -> {value_str}")
                    else:
                        print(f"    -> {errno_name(read_err)} (no value; this is still a read, nothing was written)")
                print()
            finally:
                if handle is not None:
                    sdk.device_close(handle)

        print(f"Summary: {len(devices)} device(s) total, {as_device_count} of them MOZA_DC_AS "
              "(the flight category the AY210/AB6 belong to).")
        print("No parameter was ever set, no command was ever sent, no FFB effect")
        print("was ever registered by this script.")
        return 0
    finally:
        sdk.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
