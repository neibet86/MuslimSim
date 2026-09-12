from __future__ import annotations
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'muslimsim'/'hardware'/'physical_telemetry.py'
spec=importlib.util.spec_from_file_location('physical_telemetry_v6',SRC)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; assert spec.loader; spec.loader.exec_module(mod)

class FakeLab:
    def __init__(self):
        self.mode='live'; self.enabled=True; self.inputs={}; self.raise_for=set()
    def device_enabled(self, device): return self.enabled
    def input(self, device, control, value, *, phase='change', source='virtual', route=True):
        if (device,control) in self.raise_for: raise RuntimeError('catalog mismatch')
        self.inputs.setdefault(device,{})[control]={'value':value,'phase':phase,'source':source,'updated':0.0}
        return {'routed':False}
    def snapshot(self):
        return {'mode':self.mode,'inputs':self.inputs,'outputs':{},'diagnostics':[]}
    def ping(self): return 'delegate-ok'

base=FakeLab(); proxy=mod.PhysicalTelemetryLabProxy(base)
assert proxy.ping()=='delegate-ok'
proxy.input('winctrl_throttle','left_thrust',32123,source='physical',route=False)
snap=proxy.snapshot()
assert snap['inputs']['winctrl_throttle']['left_thrust']['value']==32123
assert snap['physical_telemetry']['sequence']==1
assert snap['physical_telemetry']['devices']['winctrl_throttle']==1

# The central purpose: physical truth survives semantic/catalog rejection.
base.raise_for.add(('winctrl_pedals','rudder'))
try:
    proxy.input('winctrl_pedals','rudder',-0.42,source='physical',route=False)
except RuntimeError:
    pass
else:
    raise AssertionError('fake catalog rejection did not occur')
snap=proxy.snapshot()
assert abs(snap['inputs']['winctrl_pedals']['rudder']['value']+0.42)<1e-9
assert snap['inputs']['winctrl_pedals']['rudder']['telemetry_shadow'] is True


# In Practice, the same validation failure is consumed telemetry-only so no
# direct device wrapper can fall through to a simulator dispatcher.
base.mode='test'
result=proxy.input('winctrl_pedals','rudder',0.25,source='physical',route=False)
assert result['routed'] is True and result['telemetry_only'] is True
assert abs(proxy.snapshot()['inputs']['winctrl_pedals']['rudder']['value']-0.25)<1e-9
base.mode='live'

# Baselines are visible but virtual UI edits do not masquerade as physical truth.
proxy.input('winctrl_throttle','right_thrust',20000,phase='baseline',source='baseline',route=False)
before=proxy.snapshot()['physical_telemetry']['sequence']
proxy.input('winctrl_throttle','right_thrust',12345,source='virtual',route=False)
after=proxy.snapshot()['physical_telemetry']['sequence']
assert after==before

# User-disabled devices remain blocked even in the telemetry safety layer.
base.enabled=False
before=proxy.snapshot()['physical_telemetry']['sequence']
try:
    proxy.input('winctrl_pedals','left_toe_brake',0.8,source='physical',route=False)
except Exception:
    pass
after=proxy.snapshot()['physical_telemetry']['sequence']
assert after==before
print('V6 physical telemetry proxy: PASS')
