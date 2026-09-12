#!/usr/bin/env python3
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/'bridge'/'final.py'
H=ROOT/'bridge'/'pu_physical_authority.py'
fs=F.read_text(encoding='utf-8-sig')
hs=H.read_text(encoding='utf-8-sig')
ast.parse(fs); tree=ast.parse(hs)
def check(c,m):
    if not c: raise AssertionError(m)
check('MUSLIMSIM_STARTUP_PRACTICE_AUTHORITY_V32' in fs,'V3.2 bridge marker missing')
# Helper is a compatibility dependency only: public API + protected exclusions, no internal shape assumption.
classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PUPhysicalAuthorityMonitor']
check(len(classes)==1,'PUPhysicalAuthorityMonitor missing/ambiguous')
methods={n.name for n in classes[0].body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
check({'start','arm','disarm','replace_targets','set_target'} <= methods,'PU authority public API changed')
keys=None
for n in tree.body:
    if isinstance(n,(ast.Assign,ast.AnnAssign)):
        targets=n.targets if isinstance(n,ast.Assign) else [n.target]
        if any(isinstance(t,ast.Name) and t.id=='NEVER_REPLAY_KEYS' for t in targets):
            keys=set(ast.literal_eval(n.value)); break
check(keys is not None,'NEVER_REPLAY_KEYS missing')
check({'apu_start','pu_eng1_start','pu_eng2_start','engine1_start','engine2_start'} <= keys,'protected spring/starter exclusions changed')
# Startup baseline must be a pure sink: disarm only, no target seed or arm.
a=fs.index('evt[0] == "startup_pu_authority_baseline"')
b=fs.index('evt[0] == "pu_authority_restore"',a)
block=fs[a:b]
check('pu_authority_monitor.disarm()' in block,'startup monitor is not explicitly passive')
check('replace_targets(' not in block,'startup baseline still seeds authority targets')
check('pu_authority_monitor.arm()' not in block,'startup baseline still arms restore authority')
for token in ('irs_left_target =','wiper_target =','stage4_targets[','stage5_ign_target ='):
    check(token not in block,f'startup still seeds live controller: {token}')
# Restore is fail-closed unless bridge-side authority has been armed by movement.
r=fs.index('evt[0] == "pu_authority_restore"')
rend=fs.index('# <<< MUSLIMSIM_PU_PHYSICAL_AUTHORITY_V1 EVENTS >>>',r)
rblock=fs[r:rend]
check('or not pu_authority_bridge_armed' in rblock,'inactive authority restore is not suppressed')
check('hardware_lab.mode == "test"' in rblock,'Practice restore suppression missing')
# Real maintained movement is the only arm path after startup.
check('authority_movement = _muslimsim_pu_authority_event_is_maintained(evt)' in fs,'movement classifier not used')
call=fs.index('authority_movement = _muslimsim_pu_authority_event_is_maintained(evt)')
window=fs[call:call+900]
check('pu_authority_monitor.arm()' in window and 'and not pu_authority_bridge_armed' in window,'post-start movement arm gate missing')
# Practice entry and exit both clear helper targets; return Live never auto-arms.
ms=fs.index('MUSLIMSIM_STARTUP_PRACTICE_AUTHORITY_V32 MODE GATE')
me=fs.index('MUSLIMSIM_STARTUP_PRACTICE_AUTHORITY_V32 MODE GATE',ms+10)
mode=fs[ms:me]
check(mode.count('pu_authority_monitor.replace_targets({})')>=2,'Practice/Live transition does not clear authority targets')
check(mode.count('pu_authority_monitor.disarm()')>=2,'Practice/Live transition does not disarm authority')
check('pu_authority_monitor.arm()' not in mode,'return Live still auto-arms stale authority')
# Fixed-side PDC may not replay held state at attach.
check('pdc_bb61_left.replay_maintained()' not in fs and 'pdc_bb52_right.replay_maintained()' not in fs,'PDC startup maintained replay remains')
# Practice must consume all observer fallthrough, including route=False axes.
obs=fs.index('def _muslimsim_observe_lab_event')
obs_end=fs.index('\n    try:\n',obs)
ob=fs[obs:obs_end]
check('return hardware_lab.mode == "test"' in ob,'Practice observer is not fail-closed')
check('str(evt[0]).startswith("startup_")' in ob,'startup observer gate missing')
# Live-only periodic controller/output gates.
for token in ('and not practice_mode_active\n                    and now >= next_agp_display_read','and not practice_mode_active\n                    and now >= next_winctrl_trim','and not practice_mode_active\n                    and now >= next_stage5_step'):
    check(token in fs,f'Practice live-output gate missing: {token}')
print('PASS V3.2 bridge-only startup/Practice authority contract; PU helper internals untouched')
