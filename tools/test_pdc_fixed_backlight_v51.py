from __future__ import annotations
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'muslimsim'/'devices'/'pdc_bb61_bb52.py'
spec=importlib.util.spec_from_file_location('pdc_fixed_v51',SRC)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; assert spec.loader; spec.loader.exec_module(mod)
left=mod.MuslimSimPDCBB61Left(); right=mod.MuslimSimPDCBB52Right()
assert left._backlight_packet(255).hex() == '0260bb0000034900ff0000000000'
assert left._backlight_packet(0).hex() == '0260bb0000034900000000000000'
assert right._backlight_packet(255).hex() == '0250bb0000034900ff0000000000'
assert right._backlight_packet(0).hex() == '0250bb0000034900000000000000'
assert not mod._is_input_report(bytes.fromhex('0260cb0000034900ff0000000000'))
assert not mod._is_input_report(bytes.fromhex('0250cb0000034900ff0000000000'))
assert mod._is_input_report(bytes.fromhex('010022801202090000a07ff07f00000000'))
assert mod._is_input_report(bytes.fromhex('010048001a440000000000000061000000'))
class Fake:
    def __init__(self): self.writes=[]
    def write(self,data): self.writes.append(bytes(data)); return len(data)
f=Fake(); left.set_lab_output('panel_backlight',1.0); left._write_requested_backlight(f)
assert f.writes[-1].hex()=='0260bb0000034900ff0000000000'
f=Fake(); right.set_lab_output('panel_backlight',0); right._write_requested_backlight(f)
assert f.writes[-1].hex()=='0250bb0000034900000000000000'
try: left.set_lab_output('unknown',1)
except ValueError: pass
else: raise AssertionError('unknown PDC output was accepted')
print('V5.1 fixed PDC backlight: PASS')
