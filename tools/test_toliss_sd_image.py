"""Offline SD pixel/lease/transport tests. Opens no hardware or simulator."""
from pathlib import Path
import ast
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from muslimsim.devices import toliss_sd_image as sd


class Canvas:
    def __init__(self):
        self.pixels = bytearray(640 * 480 * 3)
        self.fg = None
        self.commands = 0
        self.byte_count = 0
        self.max_reports = 0
        self.total_reports = 0

    def colour(self, *rgb):
        if getattr(self, '_foreground', None) != rgb:
            self.byte_count += 21
            self._foreground = rgb
        if getattr(self, '_background', None) != rgb:
            self.byte_count += 21
            self._background = rgb
        self.fg = rgb

    def fill(self, x, y, w, h):
        assert 0 <= x < x+w <= 640 and 0 <= y < y+h <= 480
        self.byte_count += 25
        for row in range(y, y+h):
            start = (row*640+x)*3
            self.pixels[start:start+w*3] = bytes(self.fg)*w

    def flush(self):
        reports = (self.byte_count+55)//56
        self.max_reports = max(self.max_reports, reports)
        self.total_reports += reports
        self.byte_count = 0

    def command(self, command):
        assert command == 0x103
        self.byte_count += 17
        self.commands += 1
        self.flush()

    def rows(self):
        return tuple(bytes(self.pixels[((y+8)*640+96)*3:((y+8)*640+96+448)*3]) for y in range(448))


def finish(canvas, frame):
    for tick in range(1000):
        assert sd.draw(canvas, "bleed", frame)
        if canvas._toliss_sd_pixels["pending"] is None:
            return tick+1
    raise AssertionError("unbounded image job")


def check():
    raw = sd.HEADER.pack(0x4D534453, 1, 2, 1, 1, 620, 620, 2480, 1000, 1000, 10, 0)
    assert sd.decode_header(raw, 1000)
    assert not sd.decode_header(raw, 3001)
    assert not sd.decode_header(raw, 999)
    good = ((2,1000),1,(b'complete',),10)
    sd._last_good = good
    busy_header = bytearray(raw)
    struct.pack_into('<I', busy_header, 8, 3)
    struct.pack_into('<I', busy_header, 12, 0)
    assert sd._retain_complete(busy_header, 1010) is good
    assert sd._retain_complete(busy_header, 3000) is good
    assert sd._retain_complete(busy_header, 3001) is None
    assert sd._retain_complete(busy_header, 999) is None
    wrong_page = bytearray(busy_header); struct.pack_into('<i', wrong_page, 16, 2)
    assert sd._retain_complete(wrong_page, 1010) is None
    off = bytearray(raw); struct.pack_into('<I', off, 12, 0)
    assert sd._retain_complete(off, 1010) is None
    assert sd._retain_complete(bytes(64),1010) is None
    sd._last_good = None
    for offset, value in ((0,0),(4,2),(8,3),(12,0),(20,4096),(24,4096),(28,0)):
        bad = bytearray(raw); struct.pack_into("<I", bad, offset, value)
        assert not sd.decode_header(bad, 1000)
    source = bytearray(620*620*4)
    source[:620*4] = bytes((0,255,0,255))*620
    source[-620*4:] = bytes((255,0,0,255))*620
    rows = sd.resize_rgba(source)
    assert rows[0] == bytes((255,0,0))*448
    assert rows[-1] == bytes((0,255,0))*448
    c = Canvas()
    finish(c, ((2,1000),1,rows,10))
    assert c.rows() == rows
    reports = c.total_reports
    finish(c, ((4,1500),1,rows,10))
    assert c.total_reports == reports  # unchanged sequence has zero output
    assert not sd.draw(c, "elec", ((6,2000),1,rows,10))
    assert c.total_reports == reports
    assert not sd.draw(c, "bleed", ((6,2000),2,rows,10))
    assert c._toliss_sd_pixels is None
    # Rapidly changing live frames cannot restart and starve a pending job.
    busy = tuple(b"".join(bytes(((x+y)%256, y%256, x%256)) for x in range(448)) for y in range(448))
    c2 = Canvas()
    sd.draw(c2, "bleed", ((2,1000),1,busy,10))
    assert c2._toliss_sd_pixels["offset"] == sd.MAX_RECTS
    assert c2.commands == 1  # every batch is committed, not just flush()ed
    assert sd.image_status(c2)['image_commits'] == 1
    sd.draw(c2, "bleed", ((4,1500),1,rows,10))
    assert c2._toliss_sd_pixels["offset"] == 2*sd.MAX_RECTS
    assert c2.commands == 2
    sd.invalidate(c2)
    assert c2._toliss_sd_pixels is None
    assert not sd.image_status(c2)['image_active']
    assert c2.max_reports <= 243

    # Worker order: both must gate connectivity/power and self-test before pixels.
    bridge = (ROOT/'bridge/final.py').read_text(encoding='utf-8')
    # Execute the production failure handler without opening a USB device.
    tree = ast.parse(bridge)
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
                   and isinstance(node.body[0], ast.Expr)
                   and isinstance(node.body[0].value, ast.Call)
                   and any(isinstance(value, ast.Constant)
                           and isinstance(value.value, str)
                           and value.value.startswith('WARNING: BB36 ToLiss MCDU startup failed:')
                           for value in ast.walk(node.body[0])))
    from types import SimpleNamespace
    registered = []
    stopped = []
    scope = dict(exc=OSError('fixture: display unavailable'),
                 control_server=SimpleNamespace(register=registered.append),
                 DeviceRegistration=lambda key, **kwargs: SimpleNamespace(key=key, **kwargs),
                 toliss_mcdu_router=SimpleNamespace(stop=lambda: stopped.append(True)))
    exec(compile(ast.Module(body=handler.body,type_ignores=[]),'<BB36 startup failure>','exec'),scope)
    assert stopped and scope['toliss_mcdu_router'] is None
    result = registered[0].status()
    assert result == dict(state='error',error='OSError: fixture: display unavailable',connected=False,live=False)
    for name in ('_toliss_bb36_mirror_output_worker', '_toliss_bb35_display_output_worker'):
        block = bridge.split('def '+name+'(',1)[1].split('\ndef ',1)[0]
        assert block.index('if not secondary_connected or not powered:') < block.index('draw_sd_image(canvas, page,')
        assert block.index('_toliss_display_selftest(') < block.index('draw_sd_image(canvas, page,')
        assert "image_status(canvas)['image_sequence'] is not None" in block

    # Full-width layouts reach both sides, use the real native page identity,
    # and do not impose the obsolete 96px inset on either physical panel.
    assert sd.PAGE_IDS == dict(eng=0,bleed=1,press=2,elec=3,hyd=4,fuel=5,
                              apu=6,cond=7,door=8,wheel=9,fctl=10,status=12)
    for page, page_id in sd.PAGE_IDS.items():
        fitted = Canvas()
        f = ((2,1000),page_id,rows,10)
        assert sd.draw(fitted,page,f,viewport=(0,0,640,480))
        while fitted._toliss_sd_pixels['pending'] is not None:
            sd.draw(fitted,page,f,viewport=(0,0,640,480))
        assert fitted.pixels[:640*3] == bytes((255,0,0))*640
        assert fitted.pixels[-640*3:] == bytes((0,255,0))*640
    # Producer settling owns the page without drawing legacy or partial pixels.
    original_map = sd._mapping
    try:
        sd._mapping = bytearray(raw)
        settling = Canvas()
        assert sd.draw(settling,'elec',((2,1000),1,rows,10))
        assert settling.total_reports == 0
        assert sd.image_status(settling)['image_sequence'] is None
    finally:
        sd._mapping = original_map

    evidence = ROOT/'diagnostics/toliss-ecam/texture_trial_20260910/apu_bleed_on_20260910_181011.png'
    if evidence.exists():
        from PIL import Image
        im = Image.open(evidence).crop((2151,1050,2771,1670)).convert('RGBA')
        source = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
        start = time.perf_counter(); actual = sd.resize_rgba(source)
        decode_ms = (time.perf_counter()-start)*1000
        expected = im.resize((448,448), Image.Resampling.NEAREST).convert('RGB').tobytes()
        assert b''.join(actual) == expected
        live = Canvas(); start = time.perf_counter()
        ticks = finish(live, ((2,1000),1,actual,10))
        assert live.commands == ticks
        assert live.rows() == actual  # every resampled pixel, not just numbers
        full_reports = live.total_reports
        elapsed = (time.perf_counter()-start)*1000
        modified = list(actual); changed = bytearray(modified[200]); changed[300:330] = bytes((0,255,0))*10
        modified[200] = bytes(changed); modified = tuple(modified)
        finish(live, ((4,1500),1,modified,10))
        assert live.rows() == modified  # exact erasure/replacement of old pixels
        assert live.max_reports <= 243
        # Exercise actual production framing as well as the pixel emulator.
        from test_toliss_displays import _load_bridge, _CountingDevice
        bridge_module = _load_bridge()
        device = _CountingDevice()
        native = bridge_module._PfpNativeCanvas(device)
        finish(native, ((2,1000),1,actual,10))
        assert device.reports == full_reports, (device.reports, full_reports)
        mcdu_device = _CountingDevice()
        mcdu_native = bridge_module._PfpNativeCanvas(mcdu_device, identifier=bridge_module.MCDU_PFD_IDENTIFIER)
        finish(mcdu_native, ((2,1000),1,actual,10))
        assert full_reports <= mcdu_device.reports <= full_reports + ticks
        print(f'Actual BB36 framing: {mcdu_device.reports} reports, {ticks} separated refresh commits (fake USB only)')
        print(f'Live fixture: decode={decode_ms:.1f}ms full={elapsed:.1f}ms including test raster; '
              f'{full_reports} reports/{ticks} chunks, max={live.max_reports} reports/chunk; '
              f'10-pixel delta={live.total_reports-full_reports} reports')
    print('PASS: exact pixels, delta/idle, bounded chunks, pending frame, stale/off/page guards and both worker gates')


if __name__ == '__main__':
    check()
