#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
from muslimsim.gui.live_feedback import compose_live_mirror

def check(c,m):
    if not c: raise AssertionError(m)
lab={'inputs':{'winctrl_throttle':{
    'left_thrust':{'value':41234,'phase':'change','source':'physical','updated':1.0},
    'engine_1_idle':{'value':1,'phase':'press','source':'physical','updated':2.0},
}}, 'outputs':{}}
preview={'values':{'rudder_trim_display':1.2},'controls':{'mode':'PRACTICE'}}
state={'state':'running','mirror':dict(preview)}
m=compose_live_mirror('winctrl_throttle',state,lab)
check(m['values']['rudder_trim_display']==1.2,'Practice LCD/base mirror was lost')
check(m['input_values']['left_thrust']==41234,'physical Practice axis missing')
check(m['lab_inputs']['engine_1_idle']['source']=='physical','physical Practice button metadata missing')
source=(ROOT/'muslimsim'/'gui'/'studio.py').read_text(encoding='utf-8-sig')
ast.parse(source)
start=source.index('    def _device_mirror')
end=source.index('    @staticmethod',start)
body=source[start:end]
check('return dict(preview)' not in body,'Practice still returns preview before lab composition')
check('state["mirror"] = dict(preview)' in body and 'compose_live_mirror(' in body,
      'Practice mirror does not combine preview + lab feedback')
print('Studio Practice feedback V3: PASS')
