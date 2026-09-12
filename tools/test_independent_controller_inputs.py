"""Run the real shared SDL reader with fake controllers, never hardware."""
from pathlib import Path
import ast,contextlib,io,sys,types,importlib.util,math,queue,collections
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))

def run_reader(source,devices,bank='1&2',moving=True):
 spec=importlib.util.spec_from_file_location('_independent_reader_fixture',PROJECT/'bridge/final.py')
 bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
 tree=ast.parse(source)
 function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_pu_controller_reader')
 clock=types.SimpleNamespace(now=0.0,armed=None)
 events=[]
 class RecordingDeque(collections.deque):
  def __setitem__(self,index,item):
   events.append(item)
   super().__setitem__(index,item)
  def append(self,item):
   events.append(item)
   super().append(item)
 class Queue(queue.Queue):
  def __init__(self):
   super().__init__()
   self.queue=RecordingDeque()
  def put(self,item):
   super().put(item)
   if item[0]=='startup_hardware_snapshot':clock.armed=clock.now
 class Stop:
  def is_set(self):return clock.now>=8.0
  def wait(self,delay):clock.now+=max(float(delay),0.005);return self.is_set()
 class Joy:
  def __init__(self,key):self.key=key
  def get_name(self):return {'pu':'PU OVHD','winctrl':'WINCTRL URSA MINOR 32 Throttle Metal R','pedals':'WINCTRL Orion Combat Rudder Pedals Metal','tca':'TCA Quadrant Boeing '+bank}[self.key]
  def get_numbuttons(self):return {'pu':128,'winctrl':41,'pedals':0,'tca':17}[self.key]
  def get_numaxes(self):return {'pu':1,'winctrl':8,'pedals':3,'tca':6}[self.key]
  def get_numhats(self):return 0
  def get_instance_id(self):return devices.index(self.key)+1
  def get_button(self,index):return False
  def get_axis(self,index):
   if self.key=='pu':return 0.0
   if moving and clock.armed is not None and clock.now-clock.armed>1.5:
    return 0.8*math.sin((clock.now-clock.armed)*4)
   return -0.5
  def init(self):pass
  def quit(self):pass
 noop=lambda *a,**k:None
 pg=types.SimpleNamespace(init=noop,quit=noop,NOFRAME=0,JOYDEVICEADDED=1,JOYDEVICEREMOVED=2,
  display=types.SimpleNamespace(init=noop,set_mode=noop,quit=noop),
  joystick=types.SimpleNamespace(init=noop,quit=noop,get_count=lambda:len(devices),Joystick=lambda i:Joy(devices[i])),
  event=types.SimpleNamespace(pump=noop,get=lambda *a:[]))
 ns=dict(vars(bridge));ns.update(pygame=pg,time=types.SimpleNamespace(monotonic=lambda:clock.now))
 exec(compile(ast.Module(body=[function],type_ignores=[]),'<real SDL reader>','exec'),ns)
 output=io.StringIO()
 with contextlib.redirect_stdout(output):
  ns['_pu_controller_reader'](Queue(),Stop(),0,-1.0,1.0,False,False)
 errors=[line for line in output.getvalue().splitlines() if 'error:' in line.lower() or 'failed:' in line.lower()]
 assert not errors,errors
 return events,clock.now

def check():
 source=(PROJECT/'bridge/final.py').read_text(encoding='utf-8')
 for bank in ['1&2','3&4']:
  for devices in [('winctrl',),('tca',),('pedals',),('tca','winctrl','pedals'),('tca','pu','winctrl','pedals')]:
   events,elapsed=run_reader(source,devices,bank)
   assert elapsed>=8.0,(devices,'reader exited early')
   snapshot=next(e[1] for e in events if e[0]=='startup_hardware_snapshot')
   assert snapshot['reader_available']
   if 'pu' not in devices:
    assert snapshot['pu_values']=={} and snapshot['pu_labels']=={} and snapshot['starters']=={}
    allowed={'startup_hardware_snapshot','startup_winctrl_axes_baseline','startup_pedals_axes_baseline','winctrl_axes','winctrl_flap_axis','pedal_axes','tca_axis','tca_button'}
    assert all(e[0] in allowed for e in events),{e[0] for e in events}
   if 'winctrl' in devices:assert sum(e[0]=='winctrl_axes' for e in events)>5
   if 'pedals' in devices:assert sum(e[0]=='pedal_axes' for e in events)>5
   if 'tca' in devices:
    assert sum(e[0]=='tca_axis' and e[-1]=='live' for e in events)>5
    assert all(e[1]==bank for e in events if e[0] in {'tca_axis','tca_button'})
   stationary,_=run_reader(source,devices,bank,moving=False)
   assert not any(e[0] in {'winctrl_axes','pedal_axes'} or (e[0] in {'tca_axis','tca_button'} and e[-1]=='live') for e in stationary),'stationary startup emitted live controls'
 from muslimsim.hardware import device_lifecycle as dl
 registry=dl.DeviceLifecycleRegistry()
 for name in ['MOZA A210','MOZA AY210 FFB Base','']:
  assert registry._matches({'vendor_id':0x346e,'product_id':0x1001,'product_string':name},dl.DEVICE_SPECS['moza_a210'])
 assert not registry._matches({'vendor_id':0x346e,'product_id':0x1002,'product_string':'MOZA AB6 FFB Base'},dl.DEVICE_SPECS['moza_a210'])
 print('Independent controllers: 20 moving/stationary runs, both TCA banks, no phantom PU/startup commands; MOZA identity PASS')

if __name__=='__main__':check()
