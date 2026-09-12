"""Offline connection, naming and unplug/replug tests. No device handles."""
from __future__ import annotations
import ast
from pathlib import Path
import sys
import textwrap
import types
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def check():
    from muslimsim.hardware import discovery as d
    # Enumeration and reported identity, not manufacturer branding, determine inclusion.
    headset = dict(vendor_id=0x046D, product_id=0x0A38, product_string='Logi USB Headset',
                   manufacturer_string='Logitech', usage_page=12, usage=1)
    assert not d._looks_like_gaming_hardware(headset)
    joystick = dict(vendor_id=0x1234, product_id=0x1234, product_string='Example flight stick',
                    manufacturer_string='Example', usage_page=1, usage=4)
    assert d._looks_like_gaming_hardware(joystick)
    assert d._known_game_controller('Logitech Throttle', 0x046D) is None
    with patch.object(d, 'hid', types.SimpleNamespace(enumerate=lambda: [headset, joystick])), \
         patch.object(d, '_discover_windows_game_controllers', return_value=[]):
        result = d.discover_hid_devices(include_sdl=False)
    assert len(result) == 1 and 'Example flight stick' in result[0].title
    assert not result[0].recognised and 'winctrl' not in result[0].title.lower()
    assert d.hardware_presence({'state': 'running'}) is None
    assert d.hardware_presence({'state': 'waiting-for-a-new-device'}) is None
    assert d.hardware_presence({'state': 'no-power'}) is None
    assert d.hardware_presence({'usb_connected': False, 'connected': True}) is False
    assert d.hardware_presence({'usb_connected': True, 'connected': False, 'state': 'reconnecting'}) is True

    source = (PROJECT / 'muslimsim/gui/studio.py').read_text(encoding='utf-8')
    names = {'_merge_detected_devices', '_refresh_detected_devices', '_receive_discovery',
             '_receive_bridge_discovery', '_draw_device_surface', '_discovery_tick'}
    tree = ast.parse(source)
    methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=ast.parse('from __future__ import annotations').body + methods, type_ignores=[])
    ns = dict(time=types.SimpleNamespace(monotonic=lambda: 200.0), canonical_device_key=d.canonical_device_key,
              hardware_presence=d.hardware_presence, MUTED='gray', INK='white', WARN='orange')
    exec(compile(ast.fix_missing_locations(module), '<Studio inventory methods>', 'exec'), ns)
    # Exercise the actual status-to-sidebar section without simulator or GUI setup.
    start = source.index('        self._device_states = {', source.index('    def _receive_status('))
    stop = source.index('        lab = dict(response.get("lab") or {})', start)
    exec('def receive_states(self, response):\n' + textwrap.indent(textwrap.dedent(source[start:stop]), '    '), ns)

    class Listbox:
        def __init__(self): self.rows = []
        def delete(self, *args): self.rows.clear()
        def insert(self, _, title): self.rows.append(title)
        def selection_set(self, _): pass

    def row(key='ecam32', title='ECAM', **extra):
        return dict(key=key, title=title, product=title, manufacturer='', serial='', firmware='',
                    connected=True, recognised=True, **extra)

    h = types.SimpleNamespace(_bridge_inventory={}, _bridge_detected={}, _local_detected={},
        _device_states={}, _detected={}, _catalog={'ecam32': {'title': 'ECAM'}, 'tca_boeing': {'title': 'TCA'}},
        _device_enabled={}, _selected_device='ecam32', _selected_visual='ecam_eng',
        _capture_target='ecam_eng', _capture_device='ecam32', _learning=None,
        _local_detected_at=200.0, _bridge_inventory_at=200.0, _bridge_detected_at=200.0,
        device_list=Listbox())
    for name in names:
        setattr(h, name, types.MethodType(ns[name], h))
    h.receive_states = types.MethodType(ns['receive_states'], h)
    h._update_device_header = lambda: None
    h._merge_detected_devices()
    assert not h._device_rows and h._selected_device == ''
    h._local_detected = {'ecam32': row()}
    h._merge_detected_devices()
    assert h._device_rows == ['ecam32']
    # Negative USB evidence overrides a cached positive scan.
    h.receive_states({'devices': {'ecam32': {'state': 'disconnected', 'usb_connected': False}}})
    assert not h._device_rows and h._selected_device == ''
    assert h._capture_target is None and h._selected_visual is None
    # A registered/running worker alone is not a physical device.
    h._local_detected = {}
    h.receive_states({'devices': {'ecam32': {'state': 'running'}, 'tca_boeing': {'state': 'waiting'}}})
    assert not h._device_rows
    # Serial/SDL confirmed connection works without a local HID library.
    h.receive_states({'devices': {'tca_boeing': {'connected': True}}})
    assert h._device_rows == ['tca_boeing']
    h.receive_states({'devices': {'tca_boeing': {'connected': False}}})
    assert not h._device_rows
    # A new connection restores the same stable key, never a saved profile mutation.
    h._local_detected = {'ecam32': row()}
    h.receive_states({'devices': {'ecam32': {'usb_connected': True}}})
    assert h._device_rows == ['ecam32']
    # Slow/failed discovery is not evidence that attached controls disappeared.
    h._local_detected_at = h._bridge_detected_at = h._bridge_inventory_at = 190.0
    h._discover = lambda: None
    h.after = lambda *args: None
    h._discovery_tick()
    assert h._device_rows == ['ecam32']
    h._bridge_inventory = {'ecam32': row()}
    h._receive_bridge_discovery({'stale': True, 'devices': []})
    assert h._bridge_inventory and h._device_rows == ['ecam32']
    # All device pages survive simulator-down and generic service-offline states.
    from muslimsim.hardware.catalog import catalogue_snapshot
    h._catalog = {item['key']: item for item in catalogue_snapshot()['devices']}
    h._local_detected = {key: row(key, key) for key in h._catalog}
    h._local_detected_at = 200.0
    for mode in ('live', 'test'):
        for state_name in ('offline', 'waiting', 'waiting-for-simulator', 'registered', 'running'):
            h.receive_states({'devices': {key: {'state': state_name, 'connected': False} for key in h._catalog},
                              'lab': {'mode': mode, 'simulator_connected': False}})
            assert set(h._device_rows) == {d.canonical_device_key(key, key, key, '') for key in h._catalog}, (mode, state_name)
    # A successful empty scan and explicit physical absence still remove hardware.
    h._local_detected = {}
    h._bridge_inventory = {}
    h.receive_states({'devices': {key: {'usb_connected': False} for key in h._catalog}})
    h._merge_detected_devices()
    assert not h._device_rows

    # Unknown faceplate titles use the actual device name, never a WinCtrl fallback.
    drawn = []
    h._selected_device = 'unknown'
    h._detected = {'unknown': {'product': 'Logi USB Headset'}}
    canvas = types.SimpleNamespace(create_text=lambda *a, **kw: drawn.append(kw['text']))
    h._draw_device_surface(canvas, 900, 650)
    assert drawn[0] == 'Logi USB Headset'
    assert not any('WINCTRL' in text for text in drawn)
    print('  [ok] BUG-60 connected-only sidebar, unplug/replug, scan-failure resilience, simulator-independent presence, true device names and headset filtering')


if __name__ == '__main__':
    check()
