from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'bridge/final.py').read_text(encoding='utf-8-sig')
p=(ROOT/'muslimsim/devices/pdc_bb61_bb52.py').read_text(encoding='utf-8-sig')
c=(ROOT/'muslimsim/hardware/catalog.py').read_text(encoding='utf-8-sig')
assert 'MUSLIMSIM_FINAL_COCKPIT_STATE_V51' in b
assert 'output=pdc_bb61_left.set_lab_output' in b
assert 'output=pdc_bb52_right.set_lab_output' in b
assert '("pdc_bb61_left", "panel_backlight", 0xFF)' in b
assert '("pdc_bb52_right", "panel_backlight", 0xFF)' in b
assert 'desired_pdc_power = bool(cockpit_output_ready)' in b
assert 'MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51' in p
assert 'MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51' in c
assert 'BB61 02 60 BB 00 00 03 49 00 brightness' in c
assert 'BB52 02 50 BB 00 00 03 49 00 brightness' in c
print('V5.1 final cockpit contract: PASS')
