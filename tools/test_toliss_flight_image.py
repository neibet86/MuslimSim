"""Native flight-image protocol and exact LCD pixels; no live handles."""
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_flight_image as flight
from muslimsim.devices import toliss_sd_image as sd
from test_toliss_sd_image import Canvas


def check():
    old_ticks=sd._ticks
    try:
        sd._ticks=lambda: 1000
        for page in ('pfd','nd','ewd'):
            stream=flight.Stream(page)
            side=stream.side
            # Channel identity cannot masquerade as a native SD page.
            header=sd.HEADER.pack(flight.MAGIC,1,2,1,flight.PAGE_IDS[page],
                                  side,side,side*4,1000,1000,123,0)
            assert stream.header(header,1000)
            assert not stream.header(header,3001)
            assert not stream.header(header,999)
            raw=bytes((10,20,30,255))*(side*side)
            stream.mapping=bytearray(header+raw)
            assert stream.present()
            first=stream.read_frame()
            assert first[1]==flight.PAGE_IDS[page]
            assert first[2]==(bytes((10,20,30))*640,)*480
            assert stream.read_frame() is first
            struct.pack_into('<I',stream.mapping,8,4)
            second=stream.read_frame()
            assert second[2] is first[2], 'idle source must reuse decoded pixels'
            struct.pack_into('<I',stream.mapping,8,5)
            struct.pack_into('<I',stream.mapping,12,0)
            assert stream.read_frame() is second, 'odd copy must not cause fallback'
            struct.pack_into('<I',stream.mapping,8,6)
            assert stream.read_frame() is None, 'stable OFF must fail closed'
            for offset,value in ((0,0),(4,2),(16,999),(20,1),(24,1),(28,1)):
                bad=bytearray(header); struct.pack_into('<I',bad,offset,value)
                assert stream.header(bad,1000) is None
            canvas=Canvas()
            # Both viewports: exact fill to their measured edges, never crop.
            for viewport in ((0,0,640,480),(0,10,640,440)):
                sd.invalidate(canvas)
                for _ in range(100):
                    assert flight.draw(canvas,page,first,viewport)
                    if canvas._toliss_sd_pixels['pending'] is None:
                        break
                else:
                    raise AssertionError('image never completed')
                vx,vy,vw,vh=viewport
                for y in range(vy,vy+vh):
                    assert canvas.pixels[y*1920:(y+1)*1920]==first[2][0]
                reports=canvas.total_reports
                flight.draw(canvas,page,first,viewport)
                assert canvas.total_reports==reports, 'idle image wrote USB reports'
        # Non-uniform test: accelerated decoder must match integer sampling
        # including orientation and alpha removal, with no palette changes.
        side=750
        raw=b''.join(bytes((x%256,y%256,(x+y)%256,255))
                     for y in range(side) for x in range(side))
        start=time.perf_counter()
        actual=flight.resize_native(raw,side)
        elapsed=(time.perf_counter()-start)*1000
        expected=tuple(b''.join(bytes(((2*x+1)*side//1280%256,
                       (side-1-(2*y+1)*side//960)%256,
                       ((2*x+1)*side//1280+side-1-(2*y+1)*side//960)%256))
                       for x in range(640)) for y in range(480))
        assert actual==expected
        from unittest.mock import patch
        with patch.dict(sys.modules, {'PIL': None}):
            start=time.perf_counter()
            fallback=flight.resize_native(raw,side)
            fallback_ms=(time.perf_counter()-start)*1000
        assert fallback==actual, 'optional acceleration changed sampled pixels'
        old_streams=flight.STREAMS
        try:
            absent=flight.Stream('pfd')
            absent.mapping=bytearray(absent.size)
            flight.STREAMS={'pfd':absent}
            assert not flight.available('pfd')
            assert not flight.available('cdu')
        finally:
            flight.STREAMS=old_streams
        # Production code retains power/self-test gate precedence (SD test).
        producer=(ROOT/'tools/XTextureExtractor-trial/muslimsim_flight_stream.h').read_text()
        assert 'now-ms_flight_last<500' in producer
        assert 'now-s.data->demand<=1500' in producer
        assert 'width==4096 && height==4096' in producer
        assert 'glReadPixels(s.x,s.y,s.side,s.side' in producer
        assert 'glGetTexImage' not in producer
        bridge=(ROOT/'bridge/final.py').read_text(encoding='utf-8')
        assert bridge.count('(page in FLIGHT_PAGE_IDS and flight_image_available(page))')==2
        print(f'  [ok] native PFD/ND/EWD identity, power/staleness, exact pixels, idle reuse; resize {elapsed:.2f}ms vs fallback {fallback_ms:.2f}ms')
    finally:
        sd._ticks=old_ticks


if __name__=='__main__':
    check()
