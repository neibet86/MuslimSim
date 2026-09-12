"""Real Studio test session against simulated transports; never opens hardware."""
from pathlib import Path
import sys, time, types, threading, tempfile, os
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muslimsim.hardware.force_test_session import ForceTestSession, packet, effect_plan, validate_controls
from muslimsim.hardware import moza_ay210_ffb_protocol as wire


class Serial:
    def __init__(self, *args, **kw):
        self.values = {(153,0,None):0, (133,0,None):0, (174,0,None):70,
                       (175,0,None):0, (176,0,None):7, (177,0,None):9, (178,0,None):11,
                       (225,7,None):0, (225,6,None):1,
                       (225,10,0):35, (225,10,1):50, (225,9,0):100, (225,9,1):20}
        self.before=dict(self.values)
        self.sent=[];self.q=bytearray();self.closed=False
        self.fail_setting=None;self.fail_restore=None;self.on_write=lambda frame:None
    def reset_input_buffer(self):self.q.clear()
    @property
    def in_waiting(self):return len(self.q)
    def write(self, frame):
        pos=0
        while pos<len(frame):
            size=frame[pos+1]+5
            f=bytes(frame[pos:pos+size]);pos+=size
            assert packet(list(f[:-1]))==f
            self.sent.append(f)
            address,sub=f[4:6]
            axis=f[6] if address==225 and sub in (9,10,12) else None
            key=(address,sub,axis)
            if f[2]==31 and key in self.values:self.values[key]=f[7] if axis is not None else f[6]
            if f[2]==30:
                value=self.values[key]
                if self.fail_setting==key and value==100:value=99
                if self.fail_restore==key and value==self.before[key]:value=99
                body=[126,3,158,33,address,sub,value] if axis is None else [126,4,158,33,address,sub,axis,value]
                self.q.extend(packet(body))
            self.on_write(f)
        return len(frame)
    def read(self,n):
        result=bytes(self.q[:n]);del self.q[:n];return result
    def close(self):self.closed=True


class Hid:
    def __init__(self):self.sent=[];self.closed=False;self.fail=False;self.padded=True
    def write(self,frame):self.sent.append(('hid',bytes(frame)));return max(64,len(frame)) if self.padded else len(frame)
    def send_feature_report(self,frame):
        if self.fail:raise IOError('Allocation failed')
        self.sent.append(('feature',bytes(frame)));return len(frame)
    def close(self):self.closed=True


def make(device='moza_ab6',kind='movement',controls=None,cancelled=lambda:False,clock=time.monotonic):
    serial,hid=Serial(),Hid()
    session=ForceTestSession(device,controls or {'roll':1,'pitch':-1,'strength':1},kind,cancelled,
        clock=clock,serial_factory=lambda *a,**k:serial,
        ports=lambda:[types.SimpleNamespace(vid=13422,pid=4098 if device=='moza_ab6' else 4097,device='FAKE')],
        hid_factory=lambda **kw:hid)
    return session,serial,hid


def restored(session,serial,hid):
    session.stop()
    assert serial.values==serial.before,(serial.values,serial.before)
    assert serial.closed and hid.closed


def check():
    for device in ('moza_a210','moza_ab6'):
        for kind in ('roll','pitch','movement'):
            for roll,pitch in ((1,1),(1,-1),(-1,1),(-1,-1)):
                session,serial,hid=make(device,kind,{'roll':roll,'pitch':pitch,'strength':1})
                session.start()
                arm=serial.sent.index(bytes.fromhex('7e031f12990064bc'))
                targets=[f for f in serial.sent[:arm] if f[4:6]==bytes([225,12])]
                assert {f[6] for f in targets}==set(session.axes)
                for f in targets:assert int.from_bytes(f[7:9],'big')==(65535 if (roll,pitch)[f[6]]>0 else 0)
                assert serial.values[175,0,None]==100
                for axis in session.axes:assert serial.values[225,9,axis]==serial.values[225,10,axis]==100
                serial.sent.clear();session.tick();serial.sent.clear()
                for _ in range(100):session.tick()
                assert not serial.sent,'Unchanged targets were repeatedly sent'
                session.update({'roll':0,'pitch':0,'strength':.5})
                session.tick()
                for axis in session.axes:assert serial.values[225,10,axis]==50
                restored(session,serial,hid)
        for kind,param,etype in [('damping',176,9),('friction',178,11),('inertia',177,10)]:
            session,serial,hid=make(device,kind,{'strength':1})
            session.start();session.tick()
            assert serial.values[174,0,None]==100 and serial.values[param,0,None]==100
            assert ('feature',bytes([33,etype,0,0])) in hid.sent
            for axis in (0,1):assert ('hid',wire.build_set_condition(1,axis,0,32000,32000,32000,32000,0)) in hid.sent
            session.update({'strength':.5});session.tick()
            assert serial.values[param,0,None]==50
            restored(session,serial,hid)
        for texture in (wire.AB6_RUMBLE_PRESETS if device=='moza_ab6' else wire.RUMBLE_PRESETS):
            session,serial,hid=make(device,'vibration',{'vibration':1,'texture':texture})
            session.start();session.tick()
            assert not any(frame[1]==8 for method,frame in hid.sent if method=='feature'),'Unexpected spring allocation'
            _,updates,channels=effect_plan(device,'vibration',{'vibration':1,'texture':texture})
            assert all(('hid',frame) in hid.sent for frame in updates)
            assert all(('hid',bytes([26,c,1,1])) in hid.sent for c in channels)
            restored(session,serial,hid)
        for kind,controls in [('spring',{'physics':{'spring_gain':.8}}),('constant_force',{'force':-1,'strength':1})]:
            session,serial,hid=make(device,kind,controls);session.start();session.tick()
            if kind=='constant_force':assert ('hid',wire.build_constant_force(-32000)) in hid.sent
            restored(session,serial,hid)
    # Setup failure on the second axis still restores both distinct original settings.
    session,serial,hid=make();serial.fail_setting=(225,10,1)
    try:session.start();raise AssertionError('Expected setup failure')
    except RuntimeError as exc:assert 'read back' in str(exc)
    assert serial.values==serial.before and bytes.fromhex('7e031f12990064bc') not in serial.sent
    session,serial,hid=make(kind='inertia');hid.fail=True
    try:session.start();raise AssertionError('Expected allocation failure')
    except IOError:pass
    assert serial.values==serial.before
    # Stop during setup prevents gain-on and restores already changed fields.
    cancelled=threading.Event();session,serial,hid=make(cancelled=cancelled.is_set)
    serial.on_write=lambda f:cancelled.set() if f[2]==31 and f[4]==175 else None
    try:session.start();raise AssertionError('Expected cancellation')
    except RuntimeError:pass
    assert serial.values==serial.before and bytes.fromhex('7e031f12990064bc') not in serial.sent
    # Independent deadline cannot be extended by slider updates.
    now=[1.0];session,serial,hid=make(clock=lambda:now[0]);session.start()
    deadline=session.deadline;session.update({'roll':0,'pitch':0,'seconds':5});assert session.deadline==deadline
    now[0]=deadline
    try:session.tick();raise AssertionError('Expected expiry')
    except RuntimeError:pass
    restored(session,serial,hid)
    # Another active output owner is never disarmed/taken over.
    session,serial,hid=make();serial.values[153,0,None]=100
    try:session.start();raise AssertionError('Expected owner refusal')
    except RuntimeError as exc:assert 'Another output' in str(exc)
    assert serial.values[153,0,None]==100 and not any(f[2]==31 for f in serial.sent)
    for controls in ({'strength':float('nan')},{'pitch':2},{'seconds':9},{'physics':{'unknown':1}}):
        try:validate_controls('moza_ab6',controls,'movement');raise AssertionError('Invalid input accepted')
        except ValueError:pass
    session,serial,hid=make(kind='inertia');session.start();serial.fail_restore=(174,0,None)
    try:session.stop();raise AssertionError('Restoration failure was hidden')
    except RuntimeError as exc:assert 'cleanup needs attention' in str(exc)
    assert serial.closed and hid.closed and serial.values[153,0,None]==0
    normalized=validate_controls('moza_ab6',{'strength':'1','pitch':'-1'},'pitch')
    assert normalized['strength']==1 and normalized['pitch']==-1
    # Both native report lengths and Windows padded lengths are successful.
    session,serial,hid=make();hid.padded=False
    session.start();session.tick();restored(session,serial,hid)
    for feature in (False,True):
        for count in (-1,0,1,None):
            session,serial,hid=make();session.hid=hid
            if feature:hid.send_feature_report=lambda frame,count=count:count
            else:hid.write=lambda frame,count=count:count
            try:session._hid(bytes.fromhex('1c03'),feature);raise AssertionError('Failed/short write was accepted')
            except IOError as exc:assert 'requested 2 bytes' in str(exc)
    for device in ('moza_a210','moza_ab6'):
        for movement_strength in (0,.15,.5,1):
            for force in (-1,0,1):
                _,updates,_=effect_plan(device,'constant_force',{'force':force,'strength':movement_strength})
                assert updates==[wire.build_constant_force(force*32000)],'Movement strength reduced constant push'
        session,serial,hid=make(device,'constant_force',{'force':1,'strength':0})
        session.start();session.tick()
        assert session.diagnostics_snapshot()['requested_constant_force']==32000
        session.update({'force':-1,'strength':0});session.tick()
        assert ('hid',wire.build_constant_force(-32000)) in hid.sent
        restored(session,serial,hid)
    check_service()
    check_countdown()
    print('Studio force session PASS: full-travel targets, isolated effects, 32000 range, AE100, delta updates, original-setting restoration, setup failure, Stop, expiry, ownership and UI lease.')


def check_service():
    from muslimsim.hardware.moza_feedback_service import FeedbackService
    def wait(predicate):
        end=time.monotonic()+3
        while not predicate():
            assert time.monotonic()<end,'Service did not reach expected state'
            time.sleep(.01)
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'APPDATA':tmp}):
        instances=[]
        def factory(device,controls,kind,cancelled,**kw):
            result=make(device,kind,controls,cancelled,kw['clock']);instances.append(result);return result[0]
        service=FeedbackService('moza_ab6',lambda ref:None,lambda:False,reconnect_delay=0,test_factory=factory)
        service.start_worker()
        try:
            assert not instances,'Opening the service starts motors'
            for kind in ('movement','inertia','vibration'):
                assert service.command('test_start',{'kind':kind,'controls':{'seconds':.2,'strength':1,'vibration':1,'texture':'runway_rumble'}})['ok']
                wait(lambda:service.status()['mode']=='stopped')
                wait(lambda:instances[-1][1].closed)
                assert not service.status()['last_error'],service.status()
                assert instances[-1][1].values==instances[-1][1].before
            service.command('test_start',{'kind':'pitch','controls':{'seconds':5,'pitch':1}})
            wait(lambda:service.status().get('connected'))
            service.command('test_update',{'kind':'pitch','controls':{'seconds':5,'pitch':-1}})
            wait(lambda:any(f[4:6]==bytes([225,12]) and f[7:9]==b'\x00\x00' for f in instances[-1][1].sent))
            service.command('stop',{})
            wait(lambda:instances[-1][1].closed)
            assert instances[-1][1].values==instances[-1][1].before
            service.command('test_start',{'kind':'inertia','controls':{'seconds':5}})
            wait(lambda:service.status().get('connected'))
            wait(lambda:service.status()['mode']=='stopped')
            wait(lambda:instances[-1][1].closed)
            assert 'contact' in service.status()['test_result']
            assert instances[-1][1].values==instances[-1][1].before
        finally:service.close()



def check_countdown():
    from muslimsim.hardware.moza_feedback_service import FeedbackService
    def wait(predicate):
        end=time.monotonic()+2
        while not predicate():
            assert time.monotonic()<end,'Countdown service did not reach expected state'
            time.sleep(.01)
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'APPDATA':tmp}):
        now=[100.0];instances=[]
        def factory(device,controls,kind,cancelled,**kw):
            result=make(device,kind,controls,cancelled,kw['clock']);instances.append(result);return result[0]
        service=FeedbackService('moza_a210',lambda ref:None,lambda:False,clock=lambda:now[0],reconnect_delay=0,test_factory=factory)
        service.start_worker()
        def advance(seconds,heartbeat=True):
            with service.lock:
                now[0]+=seconds
                if heartbeat:service.command('test_heartbeat',{})
            service.wake.set();time.sleep(.08)
        def start():
            assert service.command('test_start',{'kind':'constant_force','controls':{'force':1,'seconds':.2}})['ok']
        try:
            start();advance(1);assert not instances and service.status()['test_countdown']==2
            service.command('test_update',{'kind':'constant_force','controls':{'force':-1,'seconds':.2}})
            advance(1.99);assert not instances,'Hardware opened before three seconds'
            advance(.01);wait(lambda:service.status().get('connected'))
            assert instances[-1][0].diagnostics_snapshot()['requested_constant_force']==-32000
            assert abs(service.test_deadline-(now[0]+.2))<.0001,'Countdown consumed output duration'
            advance(.21);wait(lambda:instances[-1][1].closed)
            assert instances[-1][1].values==instances[-1][1].before
            for action in ('stop','stop_test'):
                count=len(instances);start();advance(.5);service.command(action,{})
                advance(4);assert len(instances)==count and service.status()['mode']=='stopped'
            count=len(instances);start();advance(1.6,heartbeat=False)
            wait(lambda:service.status()['mode']=='stopped');assert len(instances)==count
            assert 'contact' in service.status()['test_result']
            start()
            service.command('test_start',{'kind':'roll','controls':{'roll':1,'seconds':.2}})
            wait(lambda:len(instances)==count+1 and service.status().get('connected'))
            assert instances[-1][0].kind=='roll','Replacement test did not cancel pending push'
        finally:service.close()
        assert all(s.values==s.before and s.closed for _,s,_ in instances)
    print('Constant-push countdown PASS: no hardware before 3s; full test duration; slider update, Stop, window close, lost contact and replacement-test handling.')

if __name__=='__main__':check()
