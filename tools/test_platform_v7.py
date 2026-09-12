from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.platform.authority import AuthorityCoordinator, RouteDecision
from muslimsim.platform.contracts import Capability, DeviceRole, DeviceSighting, InputEvent, RuntimeMode, TransportIdentity, ValidationError
from muslimsim.platform.identity import IdentityResolver, family_key, local_match_key, portable_key, role_hint_from_text
from muslimsim.platform.learning import LearningEngine
from muslimsim.platform.pdc_transport import normalize_input_report
from muslimsim.platform.profiles import ProfileDatabase
from muslimsim.platform.registry import DeviceLeaseBroker, load_manifest
from muslimsim.platform.telemetry import TelemetryJournal
from muslimsim.platform.updates import UpdateManifest, Version


class IdentityTests(unittest.TestCase):
    def sighting(self, *, serial: str = "", product: str = "WINCTRL PDC CAPTAIN", path: str = "A") -> DeviceSighting:
        return DeviceSighting(
            identity=TransportIdentity(
                transport="usb-hid", vendor_id=0x4098, product_id=0xBB61,
                serial_number=serial, product=product, manufacturer="WinCtrl",
                usage_page=1, usage=4, descriptor_hash="abc", path=path,
            ),
            source="test", observed_at=time.time(), legacy_key="pdc_bb61_left",
            capabilities=Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING,
            vendor_role_hint=role_hint_from_text(product), driver_id="test.pdc",
        )

    def test_serial_identity_survives_windows_and_vendor_role_label(self) -> None:
        resolver = IdentityResolver()
        original = resolver.adopt(self.sighting(serial="SER123", product="PDC CAPTAIN", path="old"), role=DeviceRole.CAPTAIN)
        moved = self.sighting(serial="SER123", product="PDC FIRST OFFICER", path="new-windows-path")
        matched, reason = resolver.observe(moved)
        self.assertIs(matched, original)
        self.assertEqual(reason, "portable-serial")
        self.assertTrue(matched.role_change_detected)
        self.assertEqual(matched.assigned_role, DeviceRole.CAPTAIN)

    def test_serialless_twins_are_not_silently_merged(self) -> None:
        resolver = IdentityResolver()
        resolver.adopt(self.sighting(product="PDC LEFT", path=""), role=DeviceRole.CAPTAIN)
        resolver.adopt(self.sighting(product="PDC RIGHT", path=""), role=DeviceRole.FIRST_OFFICER)
        unknown = self.sighting(product="PDC", path="")
        matched, reason = resolver.match(unknown)
        self.assertIsNone(matched)
        self.assertEqual(reason, "ambiguous-touch-required")

    def test_windows_path_is_not_portable_identity(self) -> None:
        a = self.sighting(serial="", path="USB#ONE").identity
        b = self.sighting(serial="", path="USB#TWO").identity
        self.assertEqual(family_key(a), family_key(b))
        self.assertEqual(portable_key(a), "")
        self.assertNotEqual(local_match_key(a), local_match_key(b))


class TelemetryTests(unittest.TestCase):
    def test_bounded_latest_value_and_edge_retention(self) -> None:
        journal = TelemetryJournal(max_edges=16, max_history=64)
        for index in range(5000):
            journal.publish("throttle", "axis", index / 5000.0, kind="axis")
        journal.publish("panel", "button", 1, phase="press", kind="button")
        journal.publish("panel", "button", 0, phase="release", kind="button")
        snap = journal.snapshot()
        self.assertEqual(snap["latest"]["throttle"]["axis"]["value"], 4999 / 5000.0)
        phases = [item["phase"] for item in snap["edges"] if item["control_key"] == "button"]
        self.assertEqual(phases[-2:], ["press", "release"])
        self.assertEqual(snap["control_count"], 2)

    def test_cursor_poll_returns_only_new_values(self) -> None:
        journal = TelemetryJournal()
        first = journal.publish("pedals", "rudder", 0.1)
        poll = journal.poll(first.sequence, timeout=0.0)
        self.assertFalse(poll["events"])
        second = journal.publish("pedals", "rudder", 0.2)
        poll = journal.poll(first.sequence, timeout=0.0)
        self.assertEqual(poll["cursor"], second.sequence)
        self.assertEqual(poll["latest"]["pedals"]["rudder"]["value"], 0.2)


class AuthorityTests(unittest.TestCase):
    def test_practice_never_routes_to_simulator(self) -> None:
        authority = AuthorityCoordinator()
        authority.update_runtime(simulator_connected=True, aircraft_loaded=True, aircraft_powered=True)
        authority.set_mode(RuntimeMode.PRACTICE)
        self.assertEqual(authority.input_decision(), RouteDecision.PRACTICE_ONLY)
        self.assertTrue(authority.output_allowed())
        authority.set_mode(RuntimeMode.LIVE)
        self.assertEqual(authority.input_decision(), RouteDecision.LIVE_ROUTE)

    def test_outputs_require_aircraft_power(self) -> None:
        authority = AuthorityCoordinator()
        authority.update_runtime(simulator_connected=True, aircraft_loaded=True, aircraft_powered=False)
        authority.set_mode(RuntimeMode.PRACTICE)
        self.assertFalse(authority.output_allowed())


class LearningTests(unittest.TestCase):
    def test_button_wins_over_axis_jitter(self) -> None:
        engine = LearningEngine()
        engine.start(baseline={"pedals": {"rudder": {"value": 0.0}}})
        for value in (0.001, -0.001, 0.002):
            engine.observe(InputEvent("pedals", "rudder", value, kind="axis", timestamp=time.time()))
        engine.observe(InputEvent("pdc", "key_12", 1, phase="press", kind="button", timestamp=time.time()))
        engine.observe(InputEvent("pdc", "key_12", 0, phase="release", kind="button", timestamp=time.time()))
        selected = engine.selected()
        self.assertEqual((selected.device_key, selected.control_key), ("pdc", "key_12"))

    def test_relearning_session_can_target_one_device(self) -> None:
        engine = LearningEngine()
        engine.start(device_key="fcu", replace_control="heading_inc")
        engine.observe(InputEvent("pdc", "key_1", 1, phase="press", kind="button", timestamp=time.time()))
        engine.observe(InputEvent("fcu", "raw_bit_9", 1, phase="press", kind="button", timestamp=time.time()))
        self.assertEqual(engine.selected().control_key, "raw_bit_9")


class ProfileTests(unittest.TestCase):
    def test_offline_profile_round_trip_and_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = ProfileDatabase(Path(directory) / "profiles.sqlite3")
            try:
                device = __import__("muslimsim.platform.contracts", fromlist=["AdoptedDevice"]).AdoptedDevice(
                    adoption_id="dev-1", family_key="family", assigned_role=DeviceRole.CAPTAIN,
                    friendly_name="PDC L", legacy_key="pdc_bb61_left",
                )
                db.save_device(device)
                created = db.create_profile("Zibo Captain", "zibo", copy_active=False)
                pid = created["profile"]["profile_id"]
                db.set_binding("dev-1", "heading_inc", {"kind": "command", "target": "laminar/test", "scale": 1.0}, device_key="pdc_bb61_left", profile_id=pid)
                db.set_learned_control("dev-1", "raw_9", "heading_inc", profile_id=pid)
                db.set_calibration("dev-1", "axis", {"minimum": 0, "center": 0.5, "maximum": 1, "deadzone": 0.02}, profile_id=pid)
                exported = db.export_profile(pid)
                self.assertEqual(exported["schema"], 1)
                self.assertTrue(db.outbox())
                imported = db.import_profile({**exported, "profile": {**exported["profile"], "name": "Imported Zibo"}}, activate=False)
                self.assertEqual(imported["profile"]["name"], "Imported Zibo")
            finally:
                db.close()


class RegistryTests(unittest.TestCase):
    def test_single_owner_lease(self) -> None:
        broker = DeviceLeaseBroker()
        lease = broker.acquire("usb:1", "bridge", "live")
        with self.assertRaises(Exception):
            broker.acquire("usb:1", "studio", "practice")
        broker.release(lease)
        broker.acquire("usb:1", "studio", "practice")

    def test_manifest_output_requires_blackout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.muslimsim-device.json"
            path.write_text(json.dumps({
                "schema": 1, "plugin_id": "test.unsafe", "title": "Unsafe",
                "match": [{"vid": "0x1234", "pid": "0x5678"}],
                "capabilities": ["output"],
                "controls": [{"key": "button", "kind": "button", "report_id": "0x01", "byte_offset": 1, "bit": 0}],
            }), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_manifest(path)

    def test_input_manifest_decodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "safe.muslimsim-device.json"
            path.write_text(json.dumps({
                "schema": 1, "plugin_id": "test.input", "title": "Input",
                "match": [{"vid": "0x1234", "pid": "0x5678"}],
                "controls": [
                    {"key": "button", "kind": "button", "report_id": "0x01", "byte_offset": 1, "bit": 2},
                    {"key": "axis", "kind": "axis", "report_id": "0x01", "byte_offset": 2, "width": 2},
                ],
            }), encoding="utf-8")
            manifest = load_manifest(path)
            values = manifest.parse(bytes([1, 4, 0x34, 0x12]))
            self.assertEqual(values, {"button": 1, "axis": 0x1234})


class PdcTransportTests(unittest.TestCase):
    def test_accepts_capture_proven_17_and_64_byte_input(self) -> None:
        logical = bytes([1]) + bytes(range(1, 17))
        self.assertEqual(normalize_input_report(logical), logical)
        padded = logical + bytes(64 - len(logical))
        self.assertEqual(normalize_input_report(padded), logical)

    def test_rejects_output_ack(self) -> None:
        self.assertIsNone(normalize_input_report(bytes([2]) + bytes(13)))
        self.assertIsNone(normalize_input_report(bytes([1]) + bytes(10)))


class UpdateTests(unittest.TestCase):
    def test_semantic_versions(self) -> None:
        self.assertGreater(Version.parse("7.1.0"), Version.parse("7.0.9"))

    def test_unsigned_manifest_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            UpdateManifest.from_mapping({
                "schema": 1, "version": "7.1.0", "package_url": "https://updates.example/package.zip",
                "sha256": "0" * 64, "signature": "", "key_id": "",
            })


if __name__ == "__main__":
    unittest.main(verbosity=2)
