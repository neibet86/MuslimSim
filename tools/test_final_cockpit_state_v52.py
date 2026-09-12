from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'bridge/final.py').read_text(encoding='utf-8-sig')
s=(ROOT/'muslimsim/gui/studio.py').read_text(encoding='utf-8-sig')
m=(ROOT/'muslimsim/devices/moza_a210.py').read_text(encoding='utf-8-sig')
p=(ROOT/'muslimsim/devices/pdc_bb61_bb52.py').read_text(encoding='utf-8-sig')
c=(ROOT/'muslimsim/hardware/catalog.py').read_text(encoding='utf-8-sig')
for text,name in ((b,'bridge'),(s,'studio'),(m,'moza'),(p,'pdc'),(c,'catalog')):
    ast.parse(text, filename=name)
assert 'MUSLIMSIM_FINAL_COCKPIT_STATE_V52' in b
assert 'MUSLIMSIM_FINAL_COCKPIT_STATE_V51' in b
assert 'MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51' in p
assert 'MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51' in c
assert 'def _moza_live_axes' in s
assert 'return self._moza_live_axes("moza_a210")' in s
assert 'self._device_input_value(str(device), key, 0.0)' in s
assert 'class MuslimSimMozaA210' in m
assert 'decode_moza_a210_report' in m
print('V5.2 MOZA-preserving cockpit contract: PASS')
