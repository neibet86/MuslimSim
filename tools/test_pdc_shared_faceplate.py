"""Shared PDC layout and physical feedback regressions; no hardware handles."""
from __future__ import annotations
import ast
import copy
from pathlib import Path
import sys
import time
import types

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from muslimsim.gui.pdc_faceplate import control_keys, selector_value, recent_input, rotary_angle, BB62_UNCAPTURED


class Canvas:
    def __init__(self): self.items = {}; self.serial = 0
    def __getattr__(self, name):
        if name.startswith('create_'):
            def create(*coords, **opts):
                self.serial += 1
                self.items[self.serial] = [name, coords, opts]
                return self.serial
            return create
        raise AttributeError(name)
    def addtag_withtag(self, tag, item):
        self.items[item][2].setdefault('tags', [])
        self.items[item][2]['tags'] = list(self.items[item][2]['tags']) + [tag]
    def keys(self):
        return {t.partition(':')[2] for _, _, o in self.items.values()
                for t in o.get('tags', []) if t.startswith('control:')}


def harness(device, mirror=None, practice=False):
    from muslimsim.hardware.catalog import catalogue_snapshot
    from muslimsim.gui.live_feedback import compose_live_mirror, physical_input_active
    source = ast.parse((PROJECT/'muslimsim/gui/studio.py').read_bytes())
    names = {'_draw_fixed_pdc', '_tag', '_pdc_flat_request_frame', '_visual_controls', '_learned_source'}
    methods = [x for x in ast.walk(source) if isinstance(x, ast.FunctionDef) and x.name in names]
    ns = {'__name__': 'muslimsim.gui.studio', 'time': time,
          '_EXPOSE_UNVERIFIED_CONTROLS': {'pdc_bb62'}, '_LEGACY_SUPERSEDED_CONTROLS': set()}
    body = ast.parse('from __future__ import annotations').body + methods
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), '<PDC drawing>', 'exec'), ns)
    h = types.SimpleNamespace(_selected_device=device, _selected_visual='', _flash_until={},
         _device_states={device: {'state': 'offline', 'present': True}},
         _detected={device: {'product': 'WINWING 3M PDC L' if device == 'pdc_bb61_left' else 'WINWING 3N PDC R',
                             'product_id': 0xBB51 if device == 'pdc_bb61_left' else 0xBB62}},
         _cockpit_sides={}, _catalog={x['key']: x for x in catalogue_snapshot()['devices']},
         learned={}, frames=[], _draw_faceplate=lambda: None)
    h.mirror = mirror if mirror is not None else {'input_values': {}, 'lab_inputs': {}}
    h._device_mirror = lambda _: h.mirror
    h._learned = lambda: h.learned
    h._pdc_flat_animate = lambda key, target, *args: target
    h._pdc_range_turn_angle = lambda *args: 0
    h._live_control_active = lambda key: physical_input_active(
        {'inputs': {device: h.mirror.get('lab_inputs', {})}}, device,
        h._learned_source(key) or key, kind='button', now_wall=time.time())
    h.after = lambda delay, fn: h.frames.append((delay,fn))
    for name in names: setattr(h, name, types.MethodType(ns[name],h))
    return h


def draw(h, canvas=None):
    canvas = canvas if canvas is not None else Canvas()
    h._draw_fixed_pdc(canvas, 1120, 720)
    return canvas


def check():
    from muslimsim.gui.live_feedback import compose_live_mirror
    from muslimsim.devices.pdc_bb62 import PDC_CONTROLS
    from muslimsim.devices.pdc_bb61_bb52 import BB61_MOMENTARY, BB61_DETENT_KNOBS
    baseline = {'map_mode': 0, 'map_range': 0, 'mins_mode': 0, 'baro_unit': 0, 'vor1': 0, 'vor2': 0}
    for mode in ('live', 'test'):
        records = {k: {'value': v, 'phase': 'change', 'source': 'physical', 'updated': 1}
                   for k,v in baseline.items()}
        lab = {'simulator_connected': False, 'mode': mode, 'inputs': {'pdc_bb61_left': records}}
        m = compose_live_mirror('pdc_bb61_left', {}, lab, practice_preview={'map_mode': 3})
        h = harness('pdc_bb61_left',m)
        c = draw(h)
        assert set(BB61_MOMENTARY.values()) <= c.keys()
        assert {k+'_'+d for k in BB61_DETENT_KNOBS for d in ('dec','inc')} <= c.keys()
        assert set(baseline)-{'map_range'} <= c.keys()
        assert {'range_dec','range_inc'} <= c.keys()
        assert selector_value('pdc_bb61_left',m,'map_mode',-1,{}) == 0
        assert not any('USB NOT CONNECTED' == o.get('text') for _,_,o in c.items.values())
        assert not h.frames, 'Missing control data must not perpetually schedule draws'
        assert 'vsd' in c.keys()
        # Each button visibly changes even after its input diagnostic is gone.
        for control in BB61_MOMENTARY.values():
            records[control] = {'value': 1, 'phase': 'press', 'source': 'physical', 'updated': time.time()}
            h.mirror = compose_live_mirror('pdc_bb61_left', {}, lab)
            changed = draw(h)
            assert any(o.get('fill') == '#17463f' for _,_,o in changed.items.values()), control
            records[control]['value'] = 0; records[control]['phase'] = 'release'
            h.mirror = compose_live_mirror('pdc_bb61_left', {}, lab)
            assert recent_input(h.mirror,control,time.time()), control
            del records[control]
    from muslimsim.gui.pdc_faceplate import cyclic_range_angle
    state = {}
    assert cyclic_range_angle(state, 7) == 0
    for step in range(1, 33):
        assert cyclic_range_angle(state, (7+step)%8) == step*45
    for step in range(1, 41):
        assert cyclic_range_angle(state, (7-step)%8) == 1440-step*45
    assert cyclic_range_angle(state, -1) == -360
    assert cyclic_range_angle(state, state['position']) == -360
    left = draw(harness('pdc_bb61_left'))
    right_h = harness('pdc_bb62'); right = draw(right_h)
    assert set(PDC_CONTROLS) <= right.keys(), set(PDC_CONTROLS)-right.keys()
    assert set(BB62_UNCAPTURED) <= right.keys()
    assert 'vsd' not in right.keys()
    left_h = harness('pdc_bb61_left')
    assert 'vsd' in left_h._visual_controls()
    assert left_h._learned_source('vsd') == 'vsd'
    left_h.learned['vsd'] = 'wxr'
    assert left_h._learned_source('vsd') == 'wxr'
    assert left_h._learned_source('tfc') == 'tfc'
    # Common visible labels stay at exactly the same coordinates.
    def labels(c): return {o['text']: coords for _,coords,o in c.items.values() if 'text' in o}
    l, r = labels(left), labels(right)
    assert any(text.startswith('WINCTRL 3M PDC  —') for text in l)
    assert any(text.startswith('WINCTRL 3N PDC  —') for text in r)
    assert not any('WINWING' in text or '3M PDC L' in text for text in l)
    assert not {'5','10','20','40','80','160','320','640'} & set(l)
    assert {'5','10','20','40','80','160','320','640'} <= set(r)
    assert 'map_range' not in left.keys()
    assert {'range_dec','range_inc'} <= left.keys()
    legacy = harness('pdc_bb61_left')
    legacy._detected['pdc_bb61_left'].update(product_id=0xBB61, product='WINWING 3N PDC L')
    assert {'5','640'} <= set(labels(draw(legacy)))
    assert 'vsd' not in draw(legacy).keys()
    assert 'vsd' not in legacy._visual_controls()
    for text in ('MINS','BARO','RST','STD','FPV','MTRS','WXR','STA','WPT','ARPT','DATA','POS','TERR','RANGE','CTR','TFC'):
        assert l[text] == r[text], text
    for k in BB62_UNCAPTURED:
        assert k in right_h._visual_controls()
        assert right_h._learned_source(k) == ''
    right_h.learned['vsd'] = 'raw_bit_16'
    assert right_h._learned_source('vsd') == 'raw_bit_16'
    assert right_h._learned_source('wxr') == 'wxr'
    # Existing BB62 per-position inputs drive shared selector geometry.
    from muslimsim.gui.pdc_faceplate import BB62_CHOICES
    for key, choices in BB62_CHOICES.items():
        for index, choice in enumerate(choices):
            m={'lab_inputs': {choice: {'value': 1, 'phase': 'press', 'updated': 10}}}
            assert selector_value('pdc_bb62',m,key,-1,{}) == index
    # No historic startup pulse; quick completed tap still turns once.
    for device in ('pdc_bb61_left','pdc_bb62'):
        for prefix in ('mins','baro'):
            state={}; m={'lab_inputs': {}}
            dec, inc = [control_keys(device,prefix+'_'+d)[0] for d in ('dec','inc')]
            assert rotary_angle(state,m,dec,inc)==0
            m['lab_inputs'][inc]={'phase':'release','updated':11,'value':0}
            assert rotary_angle(state,m,dec,inc)==24
            assert rotary_angle(state,m,dec,inc)==24
            m['lab_inputs'][dec]={'phase':'press','updated':12,'value':1}
            assert rotary_angle(state,m,dec,inc)==0
            m['lab_inputs'][dec]={'phase':'release','updated':13,'value':0}
            assert rotary_angle(state,m,dec,inc)==0
            assert rotary_angle({},m,dec,inc)==0
    # Bound frame requests and verify BB62 can complete an animation.
    right_h.frames=[];right_h._pdc_flat_frame_pending=False
    right_h._pdc_flat_request_frame();right_h._pdc_flat_request_frame()
    assert len(right_h.frames)==1
    right_h.frames[0][1]();assert not right_h._pdc_flat_frame_pending
    print('Shared PDC: identical geometry, all captured click targets, selectors, button/rotary feedback, preserved assignments: PASS')


def render_check():
    import tkinter as tk
    from muslimsim.gui.studio import _rounded_rect
    if not hasattr(tk.Canvas,'create_round_rect'): tk.Canvas.create_round_rect=_rounded_rect
    root=tk.Tk();root.withdraw()
    try:
        for device in ('pdc_bb61_left','pdc_bb62','pdc_bb52_right'):
            canvas=tk.Canvas(root,width=1120,height=720)
            h = harness(device)
            draw(h,canvas)
            root.update_idletasks()
            assert len(canvas.find_all()) > 100
            initial = {prefix: canvas.coords(canvas.find_withtag('pdc-rotation:'+prefix)[0])
                       for prefix in ('mins','baro')}
            for prefix in ('mins','baro'):
                inc = control_keys(device,prefix+'_inc')[0]
                h.mirror['lab_inputs'][inc] = {'phase': 'release', 'updated': time.time(), 'value': 0}
            canvas.delete('all'); draw(h,canvas)
            for prefix in ('mins','baro'):
                assert initial[prefix] != canvas.coords(canvas.find_withtag('pdc-rotation:'+prefix)[0])
            for key,x,y in [('wxr',115,630),('mins_rst' if device != 'pdc_bb62' else 'mins_reset',210,215)]:
                assert any('control:'+key in canvas.gettags(item) for item in canvas.find_overlapping(x,y,x,y))
            if device in {'pdc_bb61_left','pdc_bb52_right'}:
                assert any('control:vsd' in canvas.gettags(item) for item in canvas.find_overlapping(560,275,560,275))
            print(device,'real Tk canvas:',len(canvas.find_all()),'items, hit regions and moving needles PASS')
            canvas.destroy()
    finally: root.destroy()

if __name__=='__main__':
    check()
    if '--render' in sys.argv: render_check()
