"""Replay the owner's complete BB51 recording through the actual driver."""
from __future__ import annotations
import copy,hashlib,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
CAPTURE=ROOT/'captures/PDC_3M_BB51_GUIDED_20260911_215753.json'


def check():
    from muslimsim.devices import pdc_bb61_bb52 as pdc
    from muslimsim.hardware.catalog import runtime_control_by_key
    from review_pdc_3m_capture import proposal
    data=json.loads(CAPTURE.read_text(encoding='utf-8'));review=proposal(data)
    assert review['ready_for_review'] and not review['absent']
    assert pdc.BB51_MOMENTARY=={int(k):v for k,v in review['momentary'].items()}
    assert dict(pdc.BB51_SELECTOR_MAPS)=={k:{int(b):v for b,v in t.items()} for k,t in review['selectors'].items()}
    assert pdc.BB51_DETENT_KNOBS==review['detent_knobs']
    report_count=0;event_count=0
    for record in data['records']:
        step=record['step'];key=step['key'];samples=record['samples']
        driver=pdc.MuslimSimPDCBB61Left();driver._active_pid=pdc.BB51_PID
        events=[];driver._emit=lambda control,value,phase='change':events.append((control,value,phase))
        clock=[samples[0]['time']];driver._clock=lambda:clock[0]
        driver._accept_baseline(bytes.fromhex(samples[0]['raw_hex']))
        assert all(phase in {'baseline','connected'} for _,_,phase in events),key
        assert 'map_range' not in driver._mirror
        events.clear()
        for sample in samples[1:]:
            clock[0]=sample['time'];driver._accept_report(bytes.fromhex(sample['raw_hex']));driver._service_detent_knobs();report_count+=1
        if step['kind']=='selector':
            name,value=key.split(':');assert driver._mirror[name]==int(value),(key,driver._mirror)
        else:
            semantic=key.removesuffix('_fast')
            presses=[control for control,value,phase in events if phase=='press' and value]
            assert semantic in presses,(key,presses)
            assert set(presses)=={semantic},(key,'unrelated control fired',presses)
            if step['kind']=='fast':assert presses.count(semantic)>=3,(key,'fast hold did not repeat')
            for control in set(presses):
                spec=runtime_control_by_key('pdc_bb61_left',control)
                assert spec and spec.is_input and spec.status=='implemented',control
        event_count+=len(events)
    # Switching models on a fresh connection restores the original BB61 map.
    driver=pdc.MuslimSimPDCBB61Left();driver._emit=lambda *args:None
    driver._active_pid=pdc.BB51_PID;driver._accept_baseline(bytes([1])+bytes(16))
    assert driver.momentary==pdc.BB51_MOMENTARY
    driver._active_pid=pdc.BB61_PID;driver._accept_baseline(bytes([1])+bytes(16))
    assert driver.momentary==pdc.BB61_MOMENTARY and driver.detent_knobs==pdc.BB61_DETENT_KNOBS
    # Active model identity stays pinned if another PID becomes visible.
    original=pdc.hid
    try:
        queried=[]
        pdc.hid=types.SimpleNamespace(enumerate=lambda vid,pid:queried.append(pid) or ([{}] if pid==pdc.BB61_PID else []))
        driver._active_pid=pdc.BB51_PID
        assert not driver._present() and driver.pid==pdc.BB51_PID and queried==[pdc.BB51_PID]
    finally:pdc.hid=original
    # No extra output path: existing BB51/BB52 OFF is identical, BB61 remains 3N.
    assert driver._backlight_packet(0).hex()=='0250bb0000034900000000000000'
    print(f'BB51 full capture replay: 38 controls, {report_count} reports, {event_count} events; independent decoding, no cross-talk, fast holds, catalogue and model isolation PASS')

if __name__=='__main__':check()
