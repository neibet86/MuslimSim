"""Offline UI-to-profile reassignment guard; no Tk, hardware or simulator."""
from __future__ import annotations

import ast
import copy
from pathlib import Path
import re
import sys
import tempfile
import time
import types

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def check():
    from muslimsim.hardware.catalog import catalogue_snapshot, runtime_control_by_key
    from muslimsim.hardware.profiles import HardwareProfileStore, MappingBinding

    names = {'_show_selection', '_begin_learn', '_start_live_capture',
             '_learned_source', '_capture_input_is_assignable', '_process_physical_events'}
    tree = ast.parse((PROJECT / 'muslimsim/gui/studio.py').read_bytes())
    methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    for method in methods:
        method.decorator_list = []
    module = ast.Module(body=ast.parse('from __future__ import annotations').body + methods, type_ignores=[])
    pattern = re.compile(r'^raw_r[0-9a-f]{2}_b[0-9]{2}_bit[0-7]$')
    namespace = dict(time=time, runtime_control_by_key=runtime_control_by_key,
                     _CAPTURE_RAW_PATTERN={'ecam32': pattern},
                     SIMULATOR_XPLANE='xplane', SIMULATOR_MSFS24='msfs24', AIRCRAFT_ZIBO='zibo')
    exec(compile(ast.fix_missing_locations(module), '<Studio reassignment methods>', 'exec'), namespace)

    class Value:
        def __init__(self, value=''): self.value = value
        def get(self): return self.value
        def set(self, value): self.value = value

    class Button:
        def state(self, values): self.enabled = '!disabled' in values
        def configure(self, **values): self.text = values.get('text')

    checked = 0
    with tempfile.TemporaryDirectory(prefix='muslimsim-reassign-') as directory:
        store = HardwareProfileStore(Path(directory) / 'profiles.json')
        store.load()
        for device in catalogue_snapshot()['devices']:
            controls = [c for c in device['controls'] if c['direction'] in {'input', 'bidirectional'}
                        and c['status'] == 'implemented' and c['remappable']]
            if len(controls) < 2:
                continue
            key = device['key']
            first, second = controls[:2]
            visual = first['key'] if key != 'ecam32' else 'ecam_eng'
            old_raw = first['key'] if key != 'ecam32' else 'raw_r01_b01_bit0'
            new_raw = second['key'] if key != 'ecam32' else 'raw_r01_b01_bit1'
            store.set_learned_control(key, visual, old_raw)
            store.set_learned_control(key, 'other_location', old_raw)
            store.set_binding(key, old_raw, MappingBinding())
            before = copy.deepcopy(store._document)
            requests = []
            h = types.SimpleNamespace(
                _selected_device=key, _selected_visual=visual, _profile={},
                capture_button=Button(), footer=Value(), selection_title=Value(),
                selection_source=Value(), selection_note=Value(), simulator_mode=Value('xplane'),
                xplane_aircraft=Value('zibo'), practice_mode=Value(False),
                _latest_diagnostic=0, _learning=None, _capture_target=None,
            )
            for name in names:
                function = namespace[name]
                setattr(h, name, function if name == '_capture_input_is_assignable' else types.MethodType(function, h))
            for name in ('_refresh_spare_controls', '_update_reset_button_visibility', '_draw_faceplate'):
                setattr(h, name, lambda: None)
            h._visual_controls = lambda: {visual: dict(first), new_raw: dict(second)}
            h._custom_label = lambda _: ''
            h._learned = lambda: store.learned_controls(key)
            h._activate_visual = lambda *args, **kwargs: None
            h._request = lambda command, **values: requests.append((command, values))
            h._show_selection()
            assert h.capture_button.enabled, key
            assert store._document == before, 'Viewing a control changed saved assignments'
            h._begin_learn()
            assert h._capture_target == visual, key
            assert store._document == before, 'Arming capture changed saved assignments'

            def event(raw, **overrides):
                result = {'time': time.time() + 1, 'event': 'input', 'device': key,
                          'detail': {'source': 'physical', 'phase': 'change', 'control': raw}}
                result.update(overrides)
                return result

            # Ignore stale presses, other devices, virtual input, and unknown controls.
            for sample in (event(new_raw, time=0), event(new_raw, device='other_device'),
                           event(new_raw, detail={'source': 'virtual', 'phase': 'change', 'control': new_raw}),
                           event('not_a_real_control')):
                h._latest_diagnostic = 0
                h._process_physical_events({'diagnostics': [sample]})
                assert not requests, (key, sample)
            h._latest_diagnostic = 0
            h._process_physical_events({'diagnostics': [event(new_raw)]})
            assert len(requests) == 1 and requests[0][0] == 'learn_set', key
            values = requests[0][1]
            assert (values['device'], values['visual'], values['raw_control']) == (key, visual, new_raw)
            store.set_learned_control(key, visual, new_raw)
            expected = copy.deepcopy(before)
            expected['profiles'][store.active_profile]['learned'][key][visual] = new_raw
            assert store._document == expected, 'An unrelated assignment or binding changed'
            assert h._learned_source(visual) == new_raw, key
            h.practice_mode.set(True)
            h._capture_target = None
            h._begin_learn()
            assert h._capture_target is None, 'Practice armed a saved assignment'
            checked += 1

        store.save()
        reload = HardwareProfileStore(store.path) if hasattr(store, 'path') else HardwareProfileStore(Path(directory) / 'profiles.json')
        reload.load()
        assert reload._document == store._document, 'Assignments changed on reload'
    assert checked >= 17, checked
    print(f'  [ok] BUG-59 optional reassignment across {checked} device catalogs; existing assignments preserved')


if __name__ == '__main__':
    check()
