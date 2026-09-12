"""Slow-transfer liveness and transition-only brightness, without hardware."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_sd_image as sd
from test_toliss_sd_image import Canvas


def check():
    canvas=Canvas()
    powers=[]
    for _ in range(48):
        sd.set_image_power(canvas,False,powers.append)
        sd.set_image_power(canvas,False,powers.append)
    sd.set_image_power(canvas,True,powers.append)
    for _ in range(100):
        sd.set_image_power(canvas,True,powers.append)
    assert powers==[False,True], 'repeated brightness traffic during loading/idle'
    sd.invalidate(canvas)
    sd.set_image_power(canvas,False,powers.append)
    assert powers==[False,True,False], 'page change must re-establish off state'
    sd.invalidate(canvas)
    def fail(value):
        raise OSError('brightness failed')
    try:
        sd.set_image_power(canvas,False,fail)
    except OSError:
        pass
    else:
        raise AssertionError('write error hidden')
    assert canvas._toliss_image_power is None, 'failed power write cached'

    clock=[10.0]
    leases=[]
    recovery=[]
    class SlowCanvas(Canvas):
        def __init__(self):
            super().__init__()
            self._progress_callback=lambda: recovery.append(clock[0])
        def set_progress_callback(self,callback):
            self._progress_callback=callback
        def command(self,command):
            for _ in range(60):
                clock[0]+=0.05  # 3-second burst exceeds producer lease
                self._progress_callback()
            super().command(command)
    slow=SlowCanvas()
    original=slow._progress_callback
    rows=(bytes((1,2,3))*448,)*448
    with patch.object(sd.time,'monotonic',lambda:clock[0]):
        sd.draw(slow,'bleed',((2,10000),1,rows,10),heartbeat=lambda:leases.append(clock[0]))
    assert len(recovery)==60 and len(leases)>=10
    assert all(b-a<0.31 for a,b in zip(leases,leases[1:]))
    assert clock[0]-leases[-1]<0.31
    assert slow._progress_callback is original
    assert slow._image_transfer_metrics is None
    assert sd.image_status(slow)['image_sequence']==(2,10000)

    class FailedCanvas(SlowCanvas):
        def command(self,command):
            raise OSError('USB failed')
    failed=FailedCanvas()
    original=failed._progress_callback
    try:
        sd.draw(failed,'bleed',((2,10000),1,rows,10))
    except OSError:
        pass
    else:
        raise AssertionError('USB failure hidden')
    assert failed._progress_callback is original
    assert failed._image_transfer_metrics is None
    assert failed._toliss_sd_pixels is None
    print('  [ok] slow 3s burst renews lease only on progress; recovery callback preserved; 48-batch brightness 194 -> 4 reports')


if __name__=='__main__':
    check()
