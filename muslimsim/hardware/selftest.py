"""No-hardware checks for catalogue, persistence, and loopback control safety."""

from __future__ import annotations

from pathlib import Path
import tempfile
import time

from .catalog import AGP_HID_CONTROL_MAP, ALL_HARDWARE, device_by_key, runtime_control_by_key
from . import discovery as hardware_discovery
from .lab import HardwareLab
from .profiles import HardwareProfileStore, MappingBinding, ProfileError
from .zibo_library import offline_functions, search_functions
from .xplane_library import (
    AIRCRAFT_C172_NG,
    aircraft_title as xplane_aircraft_title,
    offline_xplane_functions,
    search_xplane_functions,
)
from ..devices.ecam32 import (
    ECAM32_CAPTURED_CONTACT_LED_INDEX,
    ECAM32_WAKE_REPORT,
    decode_report_transition,
    ecam32_led_report,
    is_ecam32_key_report,
)
from ..devices.moza_a210 import decode_moza_a210_report


def run_self_tests() -> None:
    c172_functions = offline_xplane_functions(AIRCRAFT_C172_NG, include_axes=True)
    if len(c172_functions) < 40:
        raise AssertionError("C172 NG Digital command library is unexpectedly small")
    if not search_xplane_functions(c172_functions, "g1000 pilot autopilot", limit=10):
        raise AssertionError("C172 NG Digital G1000 commands are unavailable")
    if any(
        str(item.get("target") or "").startswith("laminar/B738/")
        for item in c172_functions
    ):
        raise AssertionError("A Zibo-only target leaked into the C172 NG workspace")
    if xplane_aircraft_title(AIRCRAFT_C172_NG) != "AirfoilLabs C172 NG Digital":
        raise AssertionError("C172 NG Digital workspace title is incorrect")

    class _FakeHid:
        @staticmethod
        def enumerate() -> list[dict[str, object]]:
            return [
                {"vendor_id": 0x4098, "product_id": 0xBA01, "product_string": "WINCTRL 32 FCU", "serial_number": "known"},
                {"vendor_id": 0x7A11, "product_id": 0x3210, "manufacturer_string": "WINCTRL", "product_string": "WINCTRL new panel", "serial_number": "new"},
                {"vendor_id": 0x1234, "product_id": 0x5678, "manufacturer_string": "Other vendor", "product_string": "Other device", "serial_number": "skip"},
            ]

    original_hid = hardware_discovery.hid
    original_pygame = hardware_discovery.pygame
    original_windows_discovery = hardware_discovery._discover_windows_game_controllers
    try:
        hardware_discovery.hid = _FakeHid()
        hardware_discovery.pygame = None
        hardware_discovery._discover_windows_game_controllers = lambda: []
        scanned = hardware_discovery.discover_hid_devices()
    finally:
        hardware_discovery.hid = original_hid
        hardware_discovery.pygame = original_pygame
        hardware_discovery._discover_windows_game_controllers = original_windows_discovery
    scanned_keys = {device.key for device in scanned}
    if "fcu_32_efis" not in scanned_keys or not any(key.startswith("unrecognised_hid_7a11_3210") for key in scanned_keys):
        raise AssertionError("HID discovery must show both known and new WINCTRL-branded panels")
    if len(scanned) != 2:
        raise AssertionError("HID discovery must not list unrelated devices")
    if hardware_discovery.canonical_device_key("game_controller_alias", "PU OVHD 737") != "pu_overhead":
        raise AssertionError("PU OVHD driver aliases must resolve to the one PU Overhead panel")
    if hardware_discovery.canonical_device_key("game_controller_alias", "MOZA AB6 base") != "moza_ab6":
        raise AssertionError("Moza AB6 controller-name aliases must open the AB6 calibration page")

    class _FakeJoystick:
        def get_init(self) -> bool:
            return False

        def init(self) -> None:
            return None

        def get_name(self) -> str:
            return "Generic Flight Controller"

        def get_guid(self) -> str:
            return "test-guid"

        def get_instance_id(self) -> int:
            return 17

    class _FakeJoystickModule:
        def get_init(self) -> bool:
            return True

        def init(self) -> None:
            return None

        def get_count(self) -> int:
            return 1

        def Joystick(self, _index: int) -> _FakeJoystick:
            return _FakeJoystick()

    class _FakePygame:
        joystick = _FakeJoystickModule()

    try:
        hardware_discovery.hid = None
        hardware_discovery.pygame = _FakePygame()
        hardware_discovery._discover_windows_game_controllers = lambda: []
        controllers = hardware_discovery.discover_hid_devices()
    finally:
        hardware_discovery.hid = original_hid
        hardware_discovery.pygame = original_pygame
        hardware_discovery._discover_windows_game_controllers = original_windows_discovery
    if len(controllers) != 1 or controllers[0].source != "sdl" or not controllers[0].key.startswith("game_controller_test-guid"):
        raise AssertionError("generic Windows game controllers must be visible without a vendor map")
    if hardware_discovery._known_game_controller("PU OVHD 737") != ("pu_overhead", "PU Overhead"):
        raise AssertionError("SDL-only PU overhead must open its verified catalogue page")
    if hardware_discovery._known_game_controller("MOZA AB6 Flight Base") != ("moza_ab6", "MOZA AB6 FFB Base"):
        raise AssertionError("Moza AB6 must still open its page from its SDL controller name alone")
    if hardware_discovery._KNOWN_GENERIC_USB.get((0x3561, 0x8561)) != ("pu_overhead", "PU Overhead"):
        raise AssertionError("Windows HID PU overhead identity must open its verified catalogue page")
    pdc = device_by_key("pdc_bb62")
    if pdc is None or pdc.control("fpv") is None:
        raise AssertionError("capture-verified BB62 control map is missing")
    if pdc.control("unmapped_vendor_output").testable:
        raise AssertionError("unknown BB62 output selector must remain blocked")
    fcu = device_by_key("fcu_32_efis")
    if fcu is None or fcu.control("mach") is None or fcu.control("unknown_bit_503") is None:
        raise AssertionError("FCU/EFIS verified/control-safe report map is missing")
    if fcu.control("unknown_bit_503").remappable:
        raise AssertionError("unknown FCU/EFIS report bits must stay non-remappable")
    if fcu.control("fcu_windows") is None or fcu.control("captain_baro") is None:
        raise AssertionError("FCU/EFIS native display outputs are missing")
    throttle = device_by_key("winctrl_throttle")
    required_trim_selector = {
        "trim_mode_crank", "trim_mode_norm", "trim_mode_ign_start",
        "rudder_trim_left", "rudder_trim_reset", "rudder_trim_right",
    }
    if throttle is None or not required_trim_selector.issubset({item.key for item in throttle.controls}):
        raise AssertionError("WinCtrl trim-role selector map is missing")
    if throttle.control("trim_mode_norm").choices != ("RUDDER",):
        raise AssertionError("WinCtrl NORM must select the rudder trim role")
    if throttle.control("trim_mode_crank").choices != ("PITCH",):
        raise AssertionError("WinCtrl CRANK must select the pitch trim role")
    if throttle.control("trim_mode_ign_start").choices != ("AILERON",):
        raise AssertionError("WinCtrl IGN/START must select the aileron trim role")
    required_throttle_capture = {
        "aux_button_1", "aux_button_2",
        "throttle_backlight", "flaps_airbrake_backlight", "trim_display_backlight",
        "engine_1_fault_light", "engine_1_fire_light",
        "engine_2_fault_light", "engine_2_fire_light",
        "vibration_motor_1", "vibration_motor_2",
    }
    if not required_throttle_capture.issubset({item.key for item in throttle.controls}):
        raise AssertionError("WinCtrl throttle light, vibration, and captured-button map is missing")
    if not throttle.control("aux_button_1").remappable or not throttle.control("vibration_motor_1").testable:
        raise AssertionError("WinCtrl captured inputs/outputs must retain their safe laboratory roles")
    moza_a210 = device_by_key("moza_a210")
    moza_ab6 = device_by_key("moza_ab6")
    if (
        moza_a210 is None or moza_ab6 is None
        or not moza_a210.control("axis_x").remappable
        or moza_a210.control("button_128") is None
        or not moza_a210.control("button_128").remappable
        or moza_ab6.control("force_feedback_profile").testable
    ):
        raise AssertionError("A210 capture-proven HID inputs and AB6 output safety must remain distinct")
    moza_report = decode_moza_a210_report(bytes.fromhex(
        "010000ffffff7fffff000000000000ffff0800000000000081aa2a00000000000000"
    ))
    if (
        moza_report is None
        or moza_report["axes"]["axis_x"] != 0
        or moza_report["axes"]["axis_y"] != 65535
        or moza_report["axes"]["axis_z"] != 32767
        or len(moza_report["buttons"]) != 128
    ):
        raise AssertionError("MOZA A210 report 01 decoder must retain the capture-proven axes and button range")
    pfp = device_by_key("pfp3n_bb35")
    if pfp is None or pfp.control("key_24") is None:
        raise AssertionError("captured PFP3N keypad map is missing")
    mcdu = device_by_key("mcdu32_bb36")
    if mcdu is None or mcdu.control("key_73") is None:
        raise AssertionError("captured MCDU32 keypad map is missing")
    ecam = device_by_key("ecam32")
    captured_ecam = runtime_control_by_key("ecam32", "raw_r01_b02_bit5")
    if ecam is None or ecam.control("panel_wake") is None or ecam.control("panel_backlight") is None or ecam.control("led_04") is None or captured_ecam is None or not captured_ecam.remappable:
        raise AssertionError("ECAM must expose learned BB70 contacts plus capture-proven wake/backlight/indicator output")
    ecam_edges = decode_report_transition(bytes((0x01, 0x00, 0x00)), bytes((0x01, 0x00, 0x04)))
    if len(ecam_edges) != 1 or ecam_edges[0].control != "raw_r01_b02_bit2":
        raise AssertionError("ECAM raw capture must ignore report ID and preserve the observed contact bit")
    if ECAM32_WAKE_REPORT != bytes.fromhex("0201000000010000000000000000"):
        raise AssertionError("ECAM wake report must retain its captured wire form")
    if ecam32_led_report(0x04, 1) != bytes.fromhex("0270bb0000034904010000000000"):
        raise AssertionError("ECAM LED on packet must retain its captured wire form")
    if ecam32_led_report(0x11, 0) != bytes.fromhex("0270bb0000034911000000000000"):
        raise AssertionError("ECAM LED off packet must retain its captured wire form")
    if ecam32_led_report(0x00, 255) != bytes.fromhex("0270bb0000034900ff0000000000"):
        raise AssertionError("ECAM yellow backlight zone 1 must retain its captured full-brightness wire form")
    if ecam32_led_report(0x01, 255) != bytes.fromhex("0270bb0000034901ff0000000000"):
        raise AssertionError("ECAM yellow backlight zone 2 must retain its captured full-brightness wire form")
    if ECAM32_CAPTURED_CONTACT_LED_INDEX.get("raw_r01_b02_bit6") != 0x0E:
        raise AssertionError("ECAM captured contact/lamp relation must retain report-byte indexing")
    if not is_ecam32_key_report(bytes.fromhex("010800000000000000000000")):
        raise AssertionError("ECAM physical key report was not recognised")
    if not is_ecam32_key_report(bytes.fromhex("010800000000000000000000") + bytes(52)):
        raise AssertionError("ECAM padded hidapi key report was not recognised")
    if is_ecam32_key_report(bytes.fromhex("0270cb0000010000000000000000")):
        raise AssertionError("ECAM output acknowledgement must never become a key baseline")
    agp = device_by_key("agp_bb80")
    required_agp = {
        "brake_fan_on", "brake_fan_off", "anti_skid_on", "anti_skid_off",
        "rst_ccw", "rst", "rst_cw", "date_ccw", "date_press", "date_cw",
        "utc_gps", "utc_int", "utc_set", "timer_run", "timer_stop",
        "timer_reset", "terr_on_nd", "gear_up", "gear_down",
    }
    if agp is None or not required_agp.issubset({item.key for item in agp.controls}):
        raise AssertionError("complete A320 AGP control map is missing")
    if AGP_HID_CONTROL_MAP.get(22) != "terr_on_nd" or AGP_HID_CONTROL_MAP.get(24) != "gear_down":
        raise AssertionError("A320 AGP HID position map is incorrect")
    if agp.control("raw_bit_95") is None or agp.control("raw_bit_95").remappable:
        raise AssertionError("unassigned AGP report bits must remain visible but non-remappable")
    offline_axes = offline_functions(include_axes=True)
    if not any(item.get("label") == "Engine 1 starter GRD" for item in offline_axes):
        raise AssertionError("offline simulator function library is missing starter choices")
    if not any(item.get("kind") == "dataref" for item in offline_axes):
        raise AssertionError("offline simulator function library is missing safe axis choices")
    if not search_functions(offline_axes, "parking brake"):
        raise AssertionError("simulator function library search is unavailable")
    with tempfile.TemporaryDirectory() as directory:
        store = HardwareProfileStore(Path(directory) / "profiles.json")
        store.load()
        store.set_binding("pdc_bb62", "fpv", MappingBinding("command", "sim/test/command"))
        store.set_calibration("pu_overhead", {"starter_retract_ms": 310})
        store.set_calibration("moza_a210", {
            "preset_id": "a210_pmdg_b777_msfs2024",
            "overall_strength": 80,
            "g_force_enabled": False,
        })
        moza_calibration = store.calibration("moza_a210")
        if moza_calibration.get("preset_id") != "a210_pmdg_b777_msfs2024" or moza_calibration.get("overall_strength") != 80 or moza_calibration.get("g_force_enabled"):
            raise AssertionError("captured Moza calibration values did not validate/persist")
        try:
            store.set_calibration("moza_ab6", {"preset_id": "a210_ifly_b737max_msfs2024"})
        except ProfileError:
            pass
        else:
            raise AssertionError("Moza calibration must reject a preset from a different physical base")
        store.set_learned_control("fcu_32_efis", "speed_push", "speed_push")
        store.set_learned_control("ecam32", "ecam_eng", "raw_r01_b02_bit5")
        store.set_binding("ecam32", "raw_r01_b02_bit5", MappingBinding("command", "sim/test/ecam_eng"))
        store.set_binding(
            "pu_overhead", "engine_start_1",
            MappingBinding(
                "command", "sim/engines/engage_starter_1",
                trigger_value=0.0, mechanical="spring_return",
            ),
        )
        spring_binding = store.binding("pu_overhead", "engine_start_1")
        if spring_binding.mechanical != "spring_return" or spring_binding.trigger_value != 0.0:
            raise AssertionError("verified PU spring-return mapping did not persist")
        try:
            store.set_binding(
                "pdc_bb62", "fpv",
                MappingBinding("command", "sim/test/command", mechanical="spring_return"),
            )
        except ProfileError:
            pass
        else:
            raise AssertionError("spring return must stay exclusive to verified PU selectors")
        store.create("Bench", copy_active=True)
        if store.binding("pdc_bb62", "fpv").target != "sim/test/command":
            raise AssertionError("new profile did not inherit per-device mapping")
        store.select("Default")
        store.save()
        reopened = HardwareProfileStore(store.path)
        reopened.load()
        if reopened.binding("pdc_bb62", "fpv").target != "sim/test/command":
            raise AssertionError("mapping profile did not persist")
        if reopened.learned_controls("fcu_32_efis").get("speed_push") != "speed_push":
            raise AssertionError("learned FCU visual-control binding did not persist")
        if reopened.learned_controls("ecam32").get("ecam_eng") != "raw_r01_b02_bit5":
            raise AssertionError("captured ECAM visual-control binding did not persist")
        reopened.set_binding("fcu_32_efis", "mach", MappingBinding())
        if not reopened.has_binding("fcu_32_efis", "mach"):
            raise AssertionError("explicit disabled mapping did not suppress device default")
        reopened.set_device_enabled("pdc_bb62", False)
        reopened.save()
        if reopened.device_enabled("pdc_bb62"):
            raise AssertionError("per-profile device activation did not persist an off choice")
        reopened.set_device_enabled("pdc_bb62", True)
        reopened.save()
        lab = HardwareLab(reopened)
        lab.set_aircraft_context(
            AIRCRAFT_C172_NG,
            "Aircraft/Airfoillabs/C172 NG DIGITAL/C172_NG_DIGITAL.acf",
            AIRCRAFT_C172_NG,
        )
        aircraft_context = dict(lab.snapshot().get("aircraft") or {})
        if aircraft_context.get("profile") != AIRCRAFT_C172_NG:
            raise AssertionError("Detected aircraft identity is missing from Studio status")
        if not lab.self_test()["ok"]:
            raise AssertionError("hardware catalogue self-check failed")
        lab.configure_binding("pdc_bb62", "fpv", MappingBinding("action", "lab:reset-device"))
        if reopened.binding("pdc_bb62", "fpv").target != "lab:reset-device":
            raise AssertionError("safe local action did not validate/persist")
        lab.set_mode("test")
        if lab.input("pdc_bb62", "fpv", 1, phase="press")["value"] != 1.0:
            raise AssertionError("virtual input did not retain state")
        for control in (
            "brake_fan_on", "anti_skid_off", "timer_run", "terr_on_nd", "gear_up",
            "rst_cw", "chr_right", "date_ccw",
        ):
            lab.input("agp_bb80", control, 1, phase="press")
        agp_preview = lab.practice_snapshot()["agp_bb80"]
        agp_controls = dict(agp_preview.get("controls") or {})
        if not agp_controls.get("brake_fan") or agp_controls.get("anti_skid"):
            raise AssertionError("A320 AGP practice switch states are incorrect")
        if (
            not agp_controls.get("terrain")
            or agp_controls.get("gear") != "UP"
            or agp_controls.get("xpdr_mode") != "stby"
        ):
            raise AssertionError("AGP RADIO/NAV practice actions are not applied")
        if dict(agp_preview.get("rotary_raw") or {}) != {"rst": 1, "chr": 1, "date": -1}:
            raise AssertionError("A320 AGP raw rotary counters are not mirrored")
        # The first TERR press above put AGP in NAV. RADIO-only ATC selector
        # contacts must be inert there; only TERR may move back to RADIO.
        lab.input("agp_bb80", "timer_reset", 1, phase="press")
        if dict(
            lab.practice_snapshot()["agp_bb80"].get("controls") or {}
        ).get("xpdr_mode") != "stby":
            raise AssertionError(
                "AGP NAV mode leaked a RADIO-only ATC selector action"
            )
        lab.input("agp_bb80", "terr_on_nd", 1, phase="press")
        if lab.practice_snapshot()["agp_bb80"].get("page") != "radio":
            raise AssertionError("AGP TERR must toggle NAV back to RADIO")
        lab.input("agp_bb80", "timer_stop", 1, phase="press")
        if dict(
            lab.practice_snapshot()["agp_bb80"].get("controls") or {}
        ).get("xpdr_mode") != "off":
            raise AssertionError("AGP STP must select ALT OFF after RUN/STBY")
        lab.input("agp_bb80", "timer_reset", 1, phase="press")
        if dict(
            lab.practice_snapshot()["agp_bb80"].get("controls") or {}
        ).get("xpdr_mode") != "on":
            raise AssertionError("AGP spring RST must advance ALT OFF -> ALT ON")
        result = lab.output_test("pap3_mag", "all_on")
        if "lcd" not in result["applied"]:
            raise AssertionError("PAP3 virtual output test did not include LCD")
        result = lab.output_test("fcu_32_efis", "all_on")
        if "fcu_windows" not in result["applied"]:
            raise AssertionError("FCU/EFIS virtual output test did not include native windows")
        # Import here to avoid a package cycle during normal bridge import.
        from ..control.client import ControlClient
        from ..control.server import ControlServer, DeviceRegistration
        device_actions: list[str] = []
        server = ControlServer(
            lab,
            port=0,
            token="self-test-token",
            function_catalog=lambda query, limit, _aircraft="": {
                "functions": search_functions(offline_functions(include_axes=True), query, limit=limit),
                "source": "built-in",
            },
            hardware_discovery=lambda: {
                "devices": [{"key": "unrecognised_hid_7a11_3210_new", "title": "New panel"}],
            },
        )
        server.register(DeviceRegistration(
            "pdc_bb62",
            start=lambda: device_actions.append("start"),
            stop=lambda: device_actions.append("stop"),
            status=lambda: {"state": "running"},
        ))
        port = server.start()
        try:
            client = ControlClient(port, "self-test-token")
            if not client.ping():
                raise AssertionError("loopback control ping failed")
            disabled = client.request("device_enable_set", device="pdc_bb62", enabled=False)
            if disabled.get("enabled") or device_actions != ["stop"]:
                raise AssertionError("device off command did not stop the registered manager")
            ignored = lab.input("pdc_bb62", "fpv", 1, phase="press")
            if not ignored.get("disabled") or not ignored.get("routed"):
                raise AssertionError("disabled device input escaped its active-profile gate")
            enabled = client.request("device_enable_set", device="pdc_bb62", enabled=True)
            if not enabled.get("enabled") or device_actions != ["stop", "start"]:
                raise AssertionError("device on command did not restore the registered manager")
            created = client.request("profile_create", name="Control channel profile")
            if created["profile"].get("active_profile") != "Control channel profile":
                raise AssertionError("control channel did not select the new profile")
            selected = client.request("profile_select", name="Default")
            if selected["profile"].get("active_profile") != "Default":
                raise AssertionError("control channel did not switch mapping profiles")
            functions = client.request("function_catalog", query="starter", limit=10)
            if not functions.get("functions") or functions.get("source") != "built-in":
                raise AssertionError("loopback simulator function library is unavailable")
            discovered = {"devices": []}
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                discovered = client.request("hardware_discovery")
                if discovered.get("devices"):
                    break
                time.sleep(0.02)
            if not discovered.get("devices") or discovered["devices"][0].get("key") != "unrecognised_hid_7a11_3210_new":
                raise AssertionError("loopback hardware discovery did not expose a new panel")
            status = client.request("status")
            inventory = dict(status.get("hardware_discovery") or {})
            if not inventory.get("devices") or inventory["devices"][0].get("key") != "unrecognised_hid_7a11_3210_new":
                raise AssertionError("regular bridge status did not retain the hardware inventory")
            denied = server.handle({"cmd": "ping", "token": "wrong"})
            if denied.get("ok") or denied.get("error") != "Not authorised":
                raise AssertionError("control channel accepted a bad token")
        finally:
            server.stop()

# MUSLIMSIM_AGP_RADIO_NAV_V2_SELFTEST

# MUSLIMSIM_AGP_RADIO_NAV_V2_2_SELFTEST
