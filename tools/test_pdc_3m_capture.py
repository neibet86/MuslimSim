"""Guard the targeted read-only capture feed and labelled BB51 evidence."""
from __future__ import annotations
import sys, threading, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))


def check():
    from muslimsim.control.server import ControlServer, DeviceRegistration
    from capture_pdc_3m import capture_steps, validate_samples, read_sample
    calls=[]
    server=object.__new__(ControlServer)
    server.token='fixture';server._lock=threading.RLock();server.lab=types.SimpleNamespace(mode='test')
    def snapshot():calls.append('read');return {'pid':'BB51','state':'connected','serial':'test-unit','raw_hex':('01'+'00'*16),'buttons':[]}
    def forbidden(*args):raise AssertionError('Capture invoked a state-changing operation')
    server._devices={'pdc_bb61_left':DeviceRegistration('pdc_bb61_left',diagnostics=snapshot,start=forbidden,stop=forbidden,output=forbidden),
                     'unrelated':DeviceRegistration('unrelated',diagnostics=forbidden)}
    assert not server.handle({'cmd':'device_diagnostics','device':'pdc_bb61_left','token':'wrong'})['ok']
    assert not calls
    reply=server.handle({'cmd':'device_diagnostics','device':'pdc_bb61_left','token':'fixture'})
    assert reply['ok'] and calls==['read'] and reply['diagnostics']['pid']=='BB51'
    assert not server.handle({'cmd':'device_diagnostics','device':'missing','token':'fixture'})['ok']
    class Client:
        def request(self,cmd,**fields):
            assert cmd=='device_diagnostics' and fields=={'device':'pdc_bb61_left'}
            return reply
    assert read_sample(Client(),'test-unit')['serial']=='test-unit'
    for field,value in [('mode','live'),('pid','BB61'),('serial','another-unit')]:
        target=reply if field=='mode' else reply['diagnostics'];old=target[field];target[field]=value
        try:
            try:read_sample(Client(),'test-unit')
            except RuntimeError:pass
            else:raise AssertionError('Capture accepted '+field)
        finally:target[field]=old
    steps=capture_steps();keys=[s['key'] for s in steps]
    assert len(keys)==len(set(keys)) and len(keys)==38
    assert {'vsd','range_inc','range_dec','mins_inc_fast','baro_dec_fast'}<=set(keys)
    button=steps[0]
    still=[{'time':i,'raw_hex':'01','buttons':[4]} for i in range(3)]
    assert not validate_samples(button,still)[0]
    moved=[still[0],{'time':1,'raw_hex':'0101','buttons':[4,6]},still[2]]
    assert validate_samples(button,moved)[0]
    selector=next(s for s in steps if s['kind']=='selector')
    assert validate_samples(selector,still)[0]
    assert not validate_samples(selector,moved)[0]
    from review_pdc_3m_capture import proposal
    import copy
    synthetic={'pid':'BB51','serial':'fixture','complete':True,'records':[]}
    selector_bits={};pulse_bits={};knob_bits={};next_bit=1
    for step in steps:
        if step['kind'] in {'button','encoder'}:
            pulse_bits[step['key']]=next_bit;next_bit+=1
        elif step['kind']=='selector':
            group,index=step['key'].split(':');selector_bits.setdefault(group,{})[int(index)]=next_bit;next_bit+=1
    for group in ('mins','baro'):
        knob_bits[group]={name:next_bit+i for i,name in enumerate(('dec','inc','dec_fast','inc_fast','rest'))};next_bit+=5
    rest={values[0] for values in selector_bits.values()} | {v['rest'] for v in knob_bits.values()}
    for step in steps:
        key=step['key'];kind=step['kind'];states=[set(rest)]
        if kind in {'button','encoder'}:states += [rest|{pulse_bits[key]},set(rest)]
        elif kind=='selector':
            group,index=key.split(':');target=rest-set(selector_bits[group].values())|{selector_bits[group][int(index)]}
            states += [target,target]
        else:
            group,direction,*fast=key.split('_');phase=direction+('_fast' if fast else '')
            target=rest-{knob_bits[group]['rest']}|{knob_bits[group][phase]}
            states += [target,set(rest)]
        samples=[{'serial':'fixture','buttons':sorted(b),'raw_hex':'fixture','time':i*2} for i,b in enumerate(states)]
        synthetic['records'].append({'step':step,'valid':True,'samples':samples})
    verified=proposal(synthetic)
    assert verified['ready_for_review'],verified['issues']
    assert verified['detent_knobs']==knob_bits
    broken=copy.deepcopy(synthetic);broken['records'][1]['samples']=broken['records'][0]['samples']
    assert not proposal(broken)['ready_for_review']
    broken=copy.deepcopy(synthetic);broken['records'][0]['samples'][0]['serial']='other'
    assert not proposal(broken)['ready_for_review']
    broken=copy.deepcopy(synthetic);broken['complete']=False
    try:proposal(broken)
    except ValueError:pass
    else:raise AssertionError('Incomplete capture accepted')
    print('BB51 capture: authenticated targeted reads, no side effects, Practice/identity gates, 38 labelled controls, motion validation PASS')

if __name__=='__main__':check()
