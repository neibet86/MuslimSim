#!/usr/bin/env python3
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'muslimsim'/'gui'/'studio.py'
s=p.read_text(encoding='utf-8-sig'); ast.parse(s)
def check(c,m):
    if not c: raise AssertionError(m)
check('MUSLIMSIM_PRACTICE_DATA_PLANE_V4' in s,'V4 Studio marker missing')
# Practice preview must be passed separately, not overwrite state['mirror'].
i=s.index('def _device_mirror')
j=s.index('\n    @staticmethod',i)
b=s[i:j]
check('practice_preview=preview' in b,'Practice preview is not a separate composition layer')
check('state["mirror"] = dict(preview)' not in b,'Practice still replaces the raw device mirror')
# PDC renderers may not reapply raw nested mirrors after common composition.
for marker in ('def _draw_fixed_pdc','def _draw_pdc_animated_asset_v2'):
    i=s.index(marker); j=s.find('\n    def ',i+5); block=s[i:j if j>0 else len(s)]
    check('merged.update(nested)' not in block and 'tmp.update(sr.get("mirror")' not in block,'PDC renderer still overwrites composed physical truth')
    check('_live_control_active' in block,'PDC renderer still depends only on diagnostic flashes')
# ECAM custom keycaps must use persistent physical state.
i=s.index('def _draw_ecam32'); j=s.find('\n    def ',i+5); block=s[i:j]
check('physical = self._live_control_active(key)' in block,'ECAM physical contact is not a persistent visual input')
# Generic controls still use the persistent common helper.
i=s.index('def _live_control_active'); j=s.find('\n    def ',i+5); block=s[i:j]
check('physical_input_active(' in block,'common live control helper not backed by HardwareLab input state')
print('PASS Studio V4 physical visuals: Practice no longer shadows live mirror; PDC/ECAM use persistent physical truth')
