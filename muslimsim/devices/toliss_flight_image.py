"""Demand-driven captain PFD/ND and EWD images; no simulator/control writes.

Independent mappings preserve the proven SD v1 path and allow each LCD to
select a different instrument. The plugin caps all three at two captures/sec
combined. This is a fidelity trial, not yet a smooth-flight display claim.
"""
from __future__ import annotations

import mmap
import struct
import threading

from . import toliss_sd_image as sd

MAGIC = 0x4D534649
# IDs are this protocol's identities, NOT Airbus SDPage IDs.
PAGE_IDS = {'pfd': 100, 'nd': 101, 'ewd': 102}
REGIONS = {'pfd': (6, 2834, 750), 'nd': (764, 2834, 750),
           'ewd': (1521, 2426, 620)}


def resize_native(raw, side):
    """Exact pixel-centre nearest sampling, GL bottom-up to LCD top-down."""
    try:
        from PIL import Image
    except ImportError:
        offsets = tuple((2*x+1)*side//1280*4 for x in range(640))
        return tuple(b''.join(raw[base+x:base+x+3] for x in offsets)
                     for y in range(480)
                     for base in [(side-1-(2*y+1)*side//960)*side*4])
    image = Image.frombytes('RGBA', (side, side), raw)
    packed = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).resize(
        (640,480), Image.Resampling.NEAREST).convert('RGB').tobytes()
    return tuple(packed[y*1920:(y+1)*1920] for y in range(480))


class Stream:
    def __init__(self, page):
        self.page = page
        self.side = REGIONS[page][2]
        self.size = 64+self.side*self.side*4
        self.mapping = None
        self.last = None
        self.raw = None
        self.rows = None
        self.lock = threading.Lock()

    def present(self):
        return self.mapping is not None and self.mapping[:8] == struct.pack('<II', MAGIC, 1)

    def renew_demand(self):
        if self.mapping is not None:
            self.mapping[40:48] = struct.pack('<Q',sd._ticks())

    def header(self, raw, now, *, allow_busy=False):
        if len(raw) != 64:
            return None
        h = sd.HEADER.unpack(raw)
        if (h[:2] != (MAGIC,1) or h[2] == 0 or h[4] != PAGE_IDS[self.page]
                or h[5:8] != (self.side,self.side,self.side*4)):
            return None
        if allow_busy and h[2] & 1:
            return h
        if h[2] & 1 or h[3] != 1 or not 0 <= now-h[8] <= 2000:
            return None
        return h

    def retain(self, raw, now):
        if (self.last is not None and 0 <= now-self.last[0][1] <= 2000
                and self.header(raw, now, allow_busy=True) is not None):
            return self.last
        self.last = None
        return None

    def read_frame(self):
        with self.lock:
            try:
                if self.mapping is None:
                    self.mapping = mmap.mmap(-1, self.size,
                        tagname='Local\\MuslimSim.ToLiss.'+self.page.upper()+'.v1')
                now = sd._ticks()
                self.mapping[40:48] = struct.pack('<Q',now)
                before = self.mapping[:64]
                h = self.header(before, now)
                if h is None:
                    return self.retain(before, now)
                key = h[2],h[8]
                if self.last is not None and self.last[0] == key:
                    return self.last
                raw = self.mapping[64:self.size]
                after = self.mapping[:64]
                if before[:40] != after[:40]:
                    return self.retain(after,sd._ticks())
                # Idle frames do not redo the resize; both owners share rows.
                if raw != self.raw:
                    self.rows = resize_native(raw,self.side)
                    self.raw = raw
                self.last = key,h[4],self.rows,h[10]
                return self.last
            except (OSError, ValueError, AttributeError):
                self.last = None
                return None


STREAMS = {page: Stream(page) for page in PAGE_IDS}


def available(page):
    """Do not darken the working vector page when the new plugin is absent."""
    stream = STREAMS.get(page)
    if stream is None:
        return False
    if stream.mapping is None:
        stream.read_frame()
    return stream.present()


def draw(canvas, page, frame=None, viewport=None):
    stream = STREAMS.get(page)
    if stream is None:
        return False
    return sd.draw(canvas,page,frame,viewport,reader=stream.read_frame,
                   page_ids=PAGE_IDS,present=stream.present,heartbeat=stream.renew_demand,
                   latest=page == 'pfd')
