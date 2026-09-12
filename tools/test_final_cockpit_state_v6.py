from __future__ import annotations
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bridge=(ROOT/'bridge'/'final.py').read_text(encoding='utf-8-sig')
pdc=(ROOT/'muslimsim'/'devices'/'pdc_bb61_bb52.py').read_text(encoding='utf-8-sig')
studio=(ROOT/'muslimsim'/'gui'/'studio.py').read_text(encoding='utf-8-sig')
proxy=(ROOT/'muslimsim'/'hardware'/'physical_telemetry.py').read_text(encoding='utf-8-sig')
need_bridge=(
    'MUSLIMSIM_PHYSICAL_TELEMETRY_V6',
    'PhysicalTelemetryLabProxy',
    '_muslimsim_build_physical_telemetry_lab',
    'hardware_lab = _muslimsim_build_physical_telemetry_lab(',
    'physical-observer-error',
)
for token in need_bridge:
    if token not in bridge: raise AssertionError(f'bridge missing {token}')
if not any(token in bridge for token in (
    'return bool(hardware_lab is not None and hardware_lab.mode == "test")',
    'return hardware_lab.mode == "test"',
)):
    raise AssertionError('Practice observer exceptions are not fail-closed')
if 'MUSLIMSIM_PDC_VARIABLE_INPUT_V6' not in pdc or 'len(report) >= PDC_INPUT_REPORT_LEN' not in pdc:
    raise AssertionError('fixed PDC variable-length ID-01 input transport missing')
if 'MUSLIMSIM_PHYSICAL_TELEMETRY_V6' not in studio or 'Physical {telemetry_count}' not in studio or 'telemetry_sequence' not in studio or 'Physical OFF' not in studio:
    raise AssertionError('Studio physical telemetry health/sequence indicator missing')
if 'class PhysicalTelemetryLabProxy' not in proxy or 'telemetry_shadow' not in proxy:
    raise AssertionError('physical telemetry proxy missing')
# V6 must not reintroduce a MOZA runtime owner or simulator path.
moza=(ROOT/'muslimsim'/'devices'/'moza_a210.py').read_text(encoding='utf-8-sig')
if 'MUSLIMSIM_PHYSICAL_TELEMETRY_V6' in moza:
    raise AssertionError('V6 unexpectedly modified MOZA driver')
print('V6 final cockpit telemetry contract: PASS')
