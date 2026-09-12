#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'muslimsim'/'gui'/'live_feedback.py'
spec=importlib.util.spec_from_file_location('muslimsim_live_feedback_v4', MODULE)
mod=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod)

def item(value, phase='change', source='physical', updated=None):
    return {'value': value, 'phase': phase, 'source': source, 'updated': time.time() if updated is None else updated}

def check(c,m):
    if not c: raise AssertionError(m)

# PDC: Practice preview may change outputs, but physical maintained selectors are final visual truth.
state={'state':'running','mirror':{'mins_mode':0,'baro_unit':0,'vor1':1,'map_mode':2,'rotary_raw':{'mins':7}}}
preview={'mins_mode':0,'baro_unit':0,'vor1':0,'map_mode':0,'page':'practice'}
lab={'inputs':{'pdc_bb61_left':{
    'mins_mode':item(1,source='baseline'),
    'baro_unit':item(1),
    'vor1':item(2),
    'map_mode':item(3),
}}}
r=mod.compose_live_mirror('pdc_bb61_left',state,lab,practice_preview=preview)
check(r['mins_mode']==1 and r['baro_unit']==1 and r['vor1']==2 and r['map_mode']==3,'PDC physical selector pose did not win over Practice')
check(r['page']=='practice','Practice display/page overlay was lost')
check(r['rotary_raw']=={'mins':7},'raw live mirror field not preserved under Practice')

# PAP3: physical toggle state wins inside the authored values mapping; actual recorded LCD output wins display value.
state={'mirror':{'values':{'speed':210,'fd_capt':0,'at_arm':0}}}
preview={'values':{'speed':180,'fd_capt':0,'at_arm':0}}
lab={
 'inputs':{'pap3_mag':{'fd_capt':item(1),'at_arm':item(1)}},
 'outputs':{'pap3_mag':{'lcd':item({'speed':222})}},
}
r=mod.compose_live_mirror('pap3_mag',state,lab,practice_preview=preview)
check(r['values']['fd_capt']==1 and r['values']['at_arm']==1,'PAP3 physical toggles did not override Practice picture')
check(r['values']['speed']==222,'PAP3 actual high-level LCD output was not reflected')

# FCU high-level windows come from the same registered output adapter, not guessed packets.
lab={'outputs':{'fcu_32_efis':{'fcu_windows':item({'heading':273,'altitude':12000})}}}
r=mod.compose_live_mirror('fcu_32_efis',{'mirror':{'values':{'heading':100,'altitude':5000}}},lab,practice_preview={'values':{'heading':200}})
check(r['values']['heading']==273 and r['values']['altitude']==12000,'FCU recorded window output did not win')

# AGP physical maintained contacts must override virtual mechanical pose.
lab={'inputs':{'agp_bb80':{'gear_up':item(1),'gear_down':item(0,'release'),'brake_fan_on':item(1),'anti_skid_off':item(1)}}}
r=mod.compose_live_mirror('agp_bb80',{'mirror':{'controls':{'gear':'DOWN','brake_fan':False,'anti_skid':True}}},lab,practice_preview={'controls':{'gear':'DOWN'}})
check(r['controls']['gear']=='UP','AGP real gear lever did not override Practice')
check(r['controls']['brake_fan'] is True and r['controls']['anti_skid'] is False,'AGP maintained contact overlay failed')

# BB35/BB36 screen output uses only the high-level recorded screen adapter.
lab={'outputs':{'mcdu32_bb36':{'screen':item({'lines':['REAL PRACTICE OUTPUT','LINE 2']})}}}
r=mod.compose_live_mirror('mcdu32_bb36',{'mirror':{'lines':['LIVE']}},lab,practice_preview={'lines':['PREVIEW']})
check(r['lines'][0]=='REAL PRACTICE OUTPUT','MCDU recorded screen output did not reflect in Studio')

# Persistent physical button state and short rotary pulse semantics.
now=time.time()
lab={'inputs':{'x':{'held':item(1,updated=now-3),'rot':item(1,phase='press',updated=now-0.1),'oldrot':item(1,phase='press',updated=now-2)}}}
check(mod.physical_input_active(lab,'x','held',now_wall=now),'held physical input depends on diagnostic recency')
check(mod.physical_input_active(lab,'x','rot',kind='rotary',now_wall=now),'recent rotary pulse not visible')
check(not mod.physical_input_active(lab,'x','oldrot',kind='rotary',now_wall=now),'old rotary pulse remained active')

print('PASS Practice Data Plane V4: live mirror + Practice preview + persistent physical inputs + recorded outputs compose correctly')
