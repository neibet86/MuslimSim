from __future__ import annotations
import importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'muslimsim'/'devices'/'pdc_bb61_bb52.py'
spec=importlib.util.spec_from_file_location('pdc_transport_v6',SRC)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; assert spec.loader; spec.loader.exec_module(mod)
# Canonical minimum form remains accepted.
assert mod._is_input_report(bytes([0x01])+bytes(16))
# Actual direct Python HID captures from both user panels are 64-byte padded ID-01 reports.
left=bytes.fromhex('01 00 24 00 8d 00 09 00 00 30 00 e0 7f 00 00 00')+bytes(48)
right=bytes.fromhex('01 00 48 00 1a 44 00 00 00 00 00 00 00 01 00 00')+bytes(48)
assert len(left)==64 and len(right)==64
assert mod._is_input_report(left)
assert mod._is_input_report(right)
# Output acknowledgement remains excluded by report ID, regardless of its 14-byte length.
assert not mod._is_input_report(bytes.fromhex('02 60 cb 00 00 03 49 00 ff 00 00 00 00 00'))
assert not mod._is_input_report(bytes.fromhex('02 50 cb 00 00 03 49 00 ff 00 00 00 00 00'))
# Too-short ID-01 data is never decoded.
assert not mod._is_input_report(bytes([1])+bytes(15))
print('V6 fixed PDC HID transport: PASS')
