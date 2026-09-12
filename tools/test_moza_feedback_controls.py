"""File and live-worker tests with fake engines; never opens HID or serial."""
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import threading
import time
from unittest.mock import patch
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from muslimsim.hardware.moza_feedback_profiles import Repository,compile_document,test_profile
from muslimsim.hardware.moza_feedback_service import FeedbackService
from muslimsim.hardware import ffb_profiles as profiles


def wait_for(predicate,timeout=2):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.01)
    raise AssertionError('Timed out waiting for feedback state')


class FakeEngine:
    instances=[]
    def __init__(self,**kw):
        self.running=False;self.connected=False;self.profile=None;self.ticks=[];self.stops=0
        self.__class__.instances.append(self)
    def set_active_profile(self,p):self.profile=p
    def start(self):self.running=True
    def stop(self):self.running=False;self.connected=False;self.stops+=1
    def tick(self,read):
        self.connected=True
        sample={e.options['dataref']:read(e.options['dataref']) for e in self.profile.effects}
        sample['physics']={field:read(setting.dataref) for field,setting in self.profile.physics.items() if setting.dataref}
        self.ticks.append(sample)
    def status_snapshot(self):return {'running':self.running,'connected':self.connected}
    def diagnostics_snapshot(self):return {'last_effect_values':{}}




class FakeTestSession(FakeEngine):
    """Legacy profile-sampling fixture; real test packets have their own guard."""
    def __init__(self,device,controls,kind,cancelled,clock):
        super().__init__()
        self.clock=clock;self.controls=controls
        self.set_active_profile(test_profile(device,controls,kind))
    def start(self):
        super().start();self.deadline=self.clock()+self.controls.get('seconds',3)
    def update(self,controls):self.controls=controls
    def tick(self,read):
        def test_read(ref):
            if ref.startswith('test.physics.'):
                field=ref.removeprefix('test.physics.')
                return self.controls.get('physics',{}).get(field,0)
            return self.controls.get(ref.removeprefix('test.'),0)
        super().tick(test_read)


def check_captured_packets():
    from muslimsim.hardware.moza_ay210_ffb_engine import MozaAy210FfbEngine
    from muslimsim.hardware import moza_ay210_ffb_protocol as proto
    for device,wire in [('moza_a210',proto.AY210_PROFILE),('moza_ab6',proto.AB6_PROFILE)]:
        engine=MozaAy210FfbEngine(device_profile=wire)
        engine.set_active_profile(test_profile(device,{'roll':-.4,'pitch':.4,'strength':.2}))
        engine._device=object();engine._serial=object();engine._status.connected=True
        packets=[];serial=[]
        values={'test.strength':.2,'test.roll':-.4,'test.pitch':.4}
        with patch.object(proto,'send_hid',side_effect=lambda dev,packet:packets.append(packet)), patch.object(proto,'send_serial',side_effect=lambda *args:serial.append(args[-1])), patch.object(proto,'replay_rumble_channel_arm'), patch.object(proto,'send_feature_report'):
            read=lambda ref:values.get(ref,.5)
            engine.tick(read)
            state=engine.diagnostics_snapshot()['axis_state']
            assert state['roll']['cp_offset']<0 and state['pitch']['cp_offset']>0
            assert state['roll']['coef_pos']==6400
            assert state['roll']['deadband']==0
            values['test.strength']=1.0
            engine.tick(read)
            assert engine.diagnostics_snapshot()['axis_state']['pitch']['coef_pos']==32000
            values['test.strength']=.2
            values['test.roll']=.4;values['test.pitch']=-.4
            for _ in range(10):engine.tick(read)
            state=engine.diagnostics_snapshot()['axis_state']
            assert state['roll']['cp_offset']>0 and state['pitch']['cp_offset']<0
            sent={k for k,v in engine.diagnostics_snapshot()['physics_sent'].items() if v is not None}
            assert sent==set(wire.confirmed_physics_fields or profiles.PHYSICS_FIELD_DEFAULTS)
            for texture in (proto.AB6_RUMBLE_PRESETS if wire is proto.AB6_PROFILE else proto.RUMBLE_PRESETS):
                engine.set_active_profile(test_profile(device,{'vibration':.2,'texture':texture},'vibration'))
                packets.clear();engine.tick(lambda ref:.2 if ref=='test.vibration' else .5)
                spec=(proto.AB6_RUMBLE_PRESETS if wire is proto.AB6_PROFILE else proto.RUMBLE_PRESETS)[texture]
                for channel,frequency in spec['channels']:
                    expected=proto.build_set_periodic(channel,round(.2*spec['reference_magnitude']),frequency).hex()
                    assert expected in packets,(device,texture)
            engine.set_active_profile(test_profile(device,{'force':.2,'strength':.2},'constant_force'))
            engine.tick(lambda ref:.04 if ref=='test.force_gain' else .5)
            packets.clear();engine.tick(lambda ref:None)
            assert proto.build_constant_force(0).hex() in packets,'Missing data left constant push active'
            engine.set_active_profile(profiles.build_profile({'schema':1,'device':device,'name':'Disabled','effects':[],'physics':{}}))
            engine.tick(lambda ref:0)
            packets.clear();engine.tick(lambda ref:0)
            assert not packets,'Already-neutral axes were written repeatedly'
    print('Captured encoders: signed roll/pitch, all vibration textures, AB6 field gate, stale-force zero and neutral delta writes PASS.')


def check_connection_handshake():
    from muslimsim.hardware import moza_ay210_ffb_protocol as proto
    from muslimsim.hardware.moza_ay210_ffb_engine import MozaAy210FfbEngine
    assert proto.AB6_ENABLE_FFB_COMMAND=='7e031f1285000145', 'Working AB6 capture reports mode 1, not idle mode 0'
    class Serial:
        def __init__(self,chunks):self.chunks=list(chunks)
        def read(self,n):
            time.sleep(.002)
            return self.chunks.pop(0) if self.chunks else b''
    stream=Serial([b'Host Con'])
    tail=bytearray()
    assert not proto.wait_for_connected(stream,.001,buffer=tail)
    stream.chunks.append(b'nected.')
    assert proto.wait_for_connected(stream,.05,buffer=tail), 'Split firmware line was lost'
    for device in (proto.AB6_PROFILE,proto.AY210_PROFILE):
        engine=MozaAy210FfbEngine(device_profile=device)
        engine._device=object()
        engine._serial=Serial([b'Host Connecting.' if device is proto.AB6_PROFILE else b'Host Connected.'])
        events=[]
        def setup(*args):
            if device is proto.AB6_PROFILE and args[-1] is proto.AB6_EFFECT_SETUP_SEQUENCE:
                events.append('effects')
            else:
                assert args[-1] is device.connection_setup_sequence
                events.append('setup')
        def send(ser,lock,command):
            assert command==device.enable_ffb_command
            events.append('latch')
            if device is proto.AB6_PROFILE:ser.chunks.append(b'Host Connected.')
        with patch.object(proto,'replay_connection_setup',setup),patch.object(proto,'send_serial',send):
            engine._maybe_connect_and_arm()
            assert engine._status.connected, device.name
            engine._maybe_connect_and_arm()
        assert events==(['setup','latch','effects'] if device is proto.AB6_PROFILE else ['latch','setup']),events
    print('MOZA connection: split firmware messages, AB6 pre-connect setup, AY210 original order and one-time setup PASS (fake serial).')

def check_reconnect_grace():
    with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,APPDATA=td):
        service=FeedbackService('moza_ab6',lambda ref:None,lambda:False,engine_factory=FakeEngine,test_factory=FakeTestSession,reconnect_delay=.2)
        try:
            count=len(FakeEngine.instances)
            service.start_worker()
            controls={'vibration':0,'seconds':.3}
            service.command('test_start',{'kind':'vibration','controls':controls})
            time.sleep(.05)
            assert len(FakeEngine.instances)==count,'Startup grace was skipped'
            wait_for(lambda:service.status().get('connected'))
            service.command('stop_test',{})
            wait_for(lambda:not service.status().get('connected'))
            count=len(FakeEngine.instances)
            service.command('test_start',{'kind':'vibration','controls':controls})
            time.sleep(.05)
            assert len(FakeEngine.instances)==count,'Rapid test skipped disconnect grace'
            service.command('stop_test',{})
            time.sleep(.22)
            assert len(FakeEngine.instances)==count,'Stop during grace opened hardware later'
        finally:service.close()
    print('MOZA reconnect: startup/retry grace and cancellation during wait PASS.')


def check():
    check_connection_handshake()
    check_reconnect_grace()
    check_captured_packets()
    with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,APPDATA=tmp):
        for device in profiles.ALLOWED_DEVICES:
            repo=Repository(device)
            raw={'schema':1,'device':device,'name':'Flight','effects':[
                {'id':'road','kind':'rumble','preset':'runway_rumble','dataref':'speed',
                 'curve':[{'kind':'scale','options':{'out_min':0,'out_max':1}}]}],
                 'physics':{},'tuning':{'effects':{'road':{'enabled':False,'strength':.4}}}}
            saved,path=repo.save(raw,create=True)
            assert path.exists() and not compile_document(saved,device).effects
            raw['tuning']['effects']['road']['enabled']=True
            repo.save(raw,path)
            assert list((repo.directory.parent/'ffb_backups'/device).glob('*.mslm'))
            loaded,loaded_path=repo.load('Flight')
            assert loaded_path.resolve()==path.resolve() and compile_document(loaded,device).effects
            # The file takes precedence even when it has a bundled display name.
            if device=='moza_a210':
                raw['name']='Boeing 737-800'
                repo.save(raw,create=True)
                loaded,_=repo.load('Boeing 737-800')
                assert loaded['effects'][0]['id']=='road'
            before=path.read_bytes()
            bad=copy.deepcopy(raw);bad['device']='wrong'
            try:repo.save(bad,path)
            except ValueError:pass
            else:raise AssertionError('Wrong-base file accepted')
            assert before==path.read_bytes()
            movement=test_profile(device,{'roll':-.5,'pitch':.5,'strength':.1})
            assert {e.options.get('axis') for e in movement.effects}=={'roll','pitch'}
            assert {e.options['dataref'] for e in movement.effects}=={'test.strength','test.roll','test.pitch'}
            for texture in (('runway_rumble','gear_bumps') if device=='moza_ab6' else ('runway_rumble','stall_buffet','engine_rumble')):
                assert test_profile(device,{'texture':texture,'vibration':.2},'vibration').effects
            for value in (float('nan'),float('inf'),2):
                try:test_profile(device,{'roll':value})
                except ValueError:pass
                else:raise AssertionError('Unsafe axis value accepted')
            service=FeedbackService(device,lambda ref:28,lambda:False,engine_factory=FakeEngine,test_factory=FakeTestSession,reconnect_delay=0)
            service.start_worker()
            try:
                before_count=len(FakeEngine.instances)
                time.sleep(.05)
                assert len(FakeEngine.instances)==before_count,'Idle service opened hardware'
                assert service.command('select_profile',{'name':'Flight'})['ok']
                assert service.command('test_start',{'kind':'movement','controls':{'roll':-.5,'pitch':.5,'strength':.1,'seconds':.3}})['ok']
                wait_for(lambda:service.status().get('connected'))
                engine=FakeEngine.instances[-1]
                assert engine.ticks[-1]['test.roll']==-.5 and engine.ticks[-1]['test.pitch']==.5
                service.command('test_update',{'kind':'movement','controls':{'roll':.2,'pitch':-.3,'strength':.2,'seconds':.3}})
                wait_for(lambda:engine.ticks[-1]['test.roll']==.2)
                assert engine.ticks[-1]['test.pitch']==-.3
                assert all(engine.ticks[-1]['physics'][field]==0 for field in ('spring_gain','damper','inertia','friction'))
                service.command('test_update',{'kind':'movement','controls':{'roll':.2,'pitch':-.3,'strength':.2,'seconds':.3,'physics':{'spring_gain':.6}}})
                wait_for(lambda:engine.ticks[-1]['physics']['spring_gain']==.6)
                wait_for(lambda:not engine.running)
                assert service.status()['mode']=='stopped'
                service.command('test_start',{'kind':'vibration','controls':{'texture':'runway_rumble','vibration':.15,'seconds':5}})
                wait_for(lambda:service.status().get('connected'))
                engine=FakeEngine.instances[-1]
                wait_for(lambda:not engine.running,timeout=2)
                assert service.status()['mode']=='stopped','Lost UI lease did not stop motor'
                assert 'contact' in service.status()['test_result']
                service.command('enable_live',{})
                count=len(FakeEngine.instances);time.sleep(.06)
                assert len(FakeEngine.instances)==count,'Offline flight mode opened motor'
                service.online=lambda:True
                wait_for(lambda:service.status().get('connected'))
                engine=FakeEngine.instances[-1]
                service.command('stop',{})
                wait_for(lambda:not engine.running)
            finally:service.close()
            assert not service.thread.is_alive()
        assert all(not e.running for e in FakeEngine.instances)
    print('MOZA feedback: real files, disabled effects, roll/pitch, vibration, live updates, timeout, lost-UI lease, Stop and shutdown PASS (fake hardware).')


if __name__=='__main__':check()
