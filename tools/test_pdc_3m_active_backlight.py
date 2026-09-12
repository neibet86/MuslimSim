"""3M-only active backlight policy and captured shutdown OFF, fake HID only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from muslimsim.devices import pdc_bb61_bb52 as mod

def check():
 class Device:
  def __init__(self,owner=None):self.writes=[];self.closed=False;self.owner=owner
  def write(self,data):
   self.writes.append(bytes(data))
   if self.owner is not None:self.owner.stop_evt.set()
   return len(data)
  def close(self):self.closed=True
 for cls,pid in [(mod.MuslimSimPDCBB61Left,0xBB51),(mod.MuslimSimPDCBB52Right,0xBB52)]:
  owner=cls(keep_3m_backlight_on=True);owner._active_pid=pid;device=Device()
  owner._write_requested_backlight(device)
  assert device.writes==[bytes.fromhex('0250bb0000034900ff0000000000')]
  for mode in ('live','test'):
   for requested in (0,1,64,255):
    owner.set_lab_output('panel_backlight',requested)
    owner._write_requested_backlight(device)
    assert len(device.writes)==1,(mode,requested,'unchanged output resent')
  owner._write_requested_backlight(device,force=True)
  assert device.writes[-1][8]==255
  # Exercise the actual reader's connect and shutdown path with a fake handle.
  stopping=cls(keep_3m_backlight_on=True);stopping._active_pid=pid;device=Device(stopping)
  stopping._enumerate=lambda:[{}]
  stopping._open=lambda:(device,{})
  stopping._read_first_stable=lambda device:b''
  stopping._accept_baseline=lambda report:None
  original=mod.hid;mod.hid=object()
  try:stopping._reader_loop()
  finally:mod.hid=original
  assert [packet[8] for packet in device.writes]==[255,0]
  assert device.closed and stopping.status=='stopped'
 # The opt-in must not affect 3N or default callers, including explicit OFF.
 for enabled,pid in [(True,0xBB61),(True,0xBB62),(False,0xBB51),(False,0xBB52)]:
  owner=mod.MuslimSimPDCBB61Left(keep_3m_backlight_on=enabled);owner._active_pid=pid
  device=Device();owner._write_requested_backlight(device);assert not device.writes
  for requested in (0,64,255,0):
   owner.set_lab_output('panel_backlight',requested);owner._write_requested_backlight(device)
   assert device.writes[-1][8]==requested
 print('3M active backlight: captured ON, delta-only writes, reconnect and actual shutdown OFF; 3N/default behavior preserved PASS')

if __name__=='__main__':check()
