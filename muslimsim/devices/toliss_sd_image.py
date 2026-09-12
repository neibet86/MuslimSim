"""Opt-in-by-producer live BLEED pixels through the existing native canvas.

No PNG polling, numeric OCR, simulator writes, HID handles or palette guesses.
The twelve manually selectable SD page IDs were verified against native commands.
PFD/ND and automatic CRUISE remain on their existing renderers pending validation.
Full frames are chunked; stable frames emit nothing. Two panels share decoding.
"""
from __future__ import annotations

import ctypes
import mmap
import struct
import threading
import time
from collections import Counter

NAME = r"Local\MuslimSim.ToLiss.SD.v1"
SIZE = 64 + 620 * 620 * 4
SIDE = 448
PAGE_IDS = {'eng':0, 'bleed':1, 'press':2, 'elec':3, 'hyd':4, 'fuel':5,
            'apu':6, 'cond':7, 'door':8, 'wheel':9, 'fctl':10, 'status':12}
HEADER = struct.Struct("<III IiIII QQQQ")
MAX_RECTS = 200  # <=240 F0 reports including worst-case colour changes
_lock = threading.Lock()
_mapping = None
_decoded = None
_decoded_key = None
_last_good = None
_kernel = None


def _ticks():
    global _kernel
    if _kernel is None:
        _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        _kernel.GetTickCount64.restype = ctypes.c_ulonglong
    return _kernel.GetTickCount64()


def decode_header(raw, now):
    """Reject partial, malformed, unpowered and stale producer frames."""
    if len(raw) != 64:
        return None
    h = HEADER.unpack(raw)
    magic, version, seq, power, page, width, height, stride, tick, _, _, _ = h
    if (magic != 0x4D534453 or version != 1 or seq == 0 or seq & 1
            or power != 1 or (width, height, stride) != (620, 620, 2480)
            or not 0 <= now - tick <= 2000):
        return None
    return h


def resize_rgba(raw, width=SIDE, height=SIDE):
    # GL bottom-left -> LCD top-left. Fixed geometry: no project-sized scans.
    offsets = tuple(min(619, (2 * x + 1) * 620 // (2 * width)) * 4 for x in range(width))
    result = []
    for y in range(height):
        src_y = 619 - min(619, (2 * y + 1) * 620 // (2 * height))
        base = src_y * 2480
        result.append(b"".join(raw[base+x:base+x+3] for x in offsets))
    return tuple(result)


def _retain_complete(raw, now):
    """A seqlock collision is not source loss. Never extend image freshness."""
    if _last_good is None or len(raw) != 64:
        return None
    h = HEADER.unpack(raw)
    if (h[:2] != (0x4D534453, 1) or h[4] != _last_good[1]
            or h[5:8] != (620, 620, 2480)
            or not 0 <= now - _last_good[0][1] <= 2000):
        return None
    # Odd sequence owns the buffer and temporarily sets powered=0. A stable
    # even sequence with powered=0 is a real invalidation, not a copy collision.
    if h[2] & 1 or decode_header(raw, now) is not None:
        return _last_good
    return None


def read_frame():
    """One demand lease and decode cache shared by both panel owners."""
    global _mapping, _decoded, _decoded_key, _last_good
    with _lock:
        try:
            if _mapping is None:
                _mapping = mmap.mmap(-1, SIZE, tagname=NAME)
            now = _ticks()
            _mapping[40:48] = struct.pack("<Q", now)
            before = _mapping[:64]
            h = decode_header(before, now)
            if h is None:
                retained = _retain_complete(before, now)
                if retained is None:
                    _last_good = None
                return retained
            key = (h[2], h[8])
            if key != _decoded_key:
                raw = _mapping[64:SIZE]
                # Demand is consumer-owned; only compare producer fields.
                after = _mapping[:64]
                if before[:40] != after[:40]:
                    retained = _retain_complete(after, _ticks())
                    if retained is None:
                        _last_good = None
                    return retained
                _decoded = resize_rgba(raw, 640, 480)
                _decoded_key = key
            _last_good = key, h[4], _decoded, h[10]
            return _last_good
        except (OSError, ValueError, AttributeError):
            _last_good = None
            return None


def rectangles(rows, previous=None):
    """Exact changed RGB runs, vertically merged and grouped by colour."""
    active = {}
    done = []
    for y, row in enumerate(rows):
        width = len(row)//3
        old = previous[y] if previous is not None else None
        current = {}
        if row != old:
            x = 0
            while x < width:
                offset = x * 3
                colour = row[offset:offset+3]
                if old is not None and old[offset:offset+3] == colour:
                    x += 1
                    continue
                end = x + 1
                while end < width and row[end*3:end*3+3] == colour:
                    end += 1
                key = (x, end, colour)
                top, height = active.pop(key, (y, 0))
                current[key] = (top, height + 1)
                x = end
        for (x, end, colour), (top, height) in active.items():
            done.append((colour, x, top, end-x, height))
        active = current
    for (x, end, colour), (top, height) in active.items():
        done.append((colour, x, top, end-x, height))
    done.sort(key=lambda r: r[0])
    return done


def invalidate(canvas):
    canvas._toliss_sd_pixels = None
    canvas._toliss_image_power = None


def fair_pfd_rectangles(rects, width):
    """Small alternating left/right/centre runs; neither tape waits for the other."""
    bands = [[], [], []]
    for rect in rects:
        centre = rect[1] + rect[3] // 2
        band = 0 if centre < width//3 else 1 if centre >= 2*width//3 else 2
        bands[band].append(rect)
    return [rect for start in range(0, max(map(len,bands), default=0), 32)
            for band in bands for rect in band[start:start+32]]


def committed_rows(rows, rects):
    """Shadow only successfully committed pixels, including erasures."""
    updated = list(rows)
    dirty = {}
    for colour,x,y,width,height in rects:
        for line in range(y,y+height):
            if line not in dirty:
                dirty[line] = bytearray(rows[line])
            dirty[line][x*3:(x+width)*3] = colour*width
    for line,row in dirty.items():
        updated[line] = bytes(row)
    return tuple(updated)


def set_image_power(canvas, powered, setter):
    """Brightness is a state transition, not a per-drawing-batch command."""
    if getattr(canvas, '_toliss_image_power', None) != powered:
        setter(powered)
        canvas._toliss_image_power = powered


def renew_demand():
    if _mapping is not None:
        _mapping[40:48] = struct.pack('<Q', _ticks())


def image_status(canvas):
    state = getattr(canvas, '_toliss_sd_pixels', None)
    if state is None:
        return dict(image_active=False, image_pending_rects=0, image_commits=0,
                    image_sequence=None)
    pending = state.get('pending')
    metrics = state.get('transport', {})
    return dict(image_active=True,
                image_pending_rects=max(0, len(pending)-state['offset']) if pending else 0,
                image_commits=state.get('commits',0), image_sequence=state.get('key'),
                image_usb_reports=metrics.get('reports',0),
                image_usb_write_ms=round(metrics.get('write_ms',0),2),
                image_usb_max_write_ms=round(metrics.get('max_write_ms',0),2),
                image_batch_ms=round(state.get('batch_ms',0),2))


def draw(canvas, page, frame=None, viewport=None, *, reader=None, page_ids=None, present=None, heartbeat=None, latest=False):
    """Return True when owning a verified SD page, including source settling.

    Existing caller power/self-test gates run before this function. A stale
    stream withdraws ownership; caller then rebuilds the numeric renderer.
    Each bounded drawing batch is refreshed. The firmware must not accumulate
    a multi-thousand-command uncommitted frame across multiple worker ticks.
    """
    ids = PAGE_IDS if page_ids is None else page_ids
    if page not in ids:
        return False
    if frame is None:
        frame = (reader or read_frame)()
    if frame is None or frame[1] != ids[page]:
        if getattr(canvas, "_toliss_sd_pixels", None) is not None:
            invalidate(canvas)
            from .systems_renderer_toliss import invalidate as invalidate_systems
            invalidate_systems(canvas)
        # Once the installed producer is present, do not briefly substitute
        # the old numerical artwork while native SD page selection settles.
        return (present() if present is not None else
                _mapping is not None and _mapping[:8] == struct.pack('<II',0x4D534453,1))
    key, _, rows, capture_us = frame
    state = getattr(canvas, "_toliss_sd_pixels", None)
    native = getattr(canvas, "native_canvas", canvas)
    vx, vy, vw, vh = viewport or (96,8,SIDE,SIDE)
    width, height = len(rows[0])//3, len(rows)
    if state is None:
        # Fill the background once; avoid transmitting thousands of redundant
        # background strips during full recovery. Does not discard any colour.
        counts = Counter(row[x:x+3] for row in rows for x in range(0, width*3, 3))
        background = counts.most_common(1)[0][0]
        native.colour(0, 0, 0); native.fill(0, 0, 640, 480)
        native.colour(*background); native.fill(vx, vy, vw, vh)
        base = (background * width,) * height
        state = {"key": None, "rows": base, "pending": None, "offset": 0, "commits": 0}
        canvas._toliss_sd_pixels = state
    if (latest and state['key'] is not None and state['pending'] is not None
            and state.get('target_key') != key):
        # Initial page still finishes once, so a moving source cannot keep it
        # black forever. Thereafter discard UNSENT old work, never USB writes.
        state['pending'] = None
    if state["pending"] is None:
        if state["key"] == key:
            return True
        state["pending"] = rectangles(rows, state["rows"])
        if latest and state['key'] is not None:
            state['pending'] = fair_pfd_rectangles(state['pending'], width)
        state["target"] = rows
        state["target_key"] = key
        state["offset"] = 0
        state["capture_us"] = capture_us
    pending = state["pending"]
    offset = state["offset"]
    stop = min(offset + MAX_RECTS, len(pending))
    # Each batch is a self-contained LCD transaction. Reassert its first
    # colour even when the software cache matches the preceding batch.
    if stop > offset:
        native._foreground = None
        native._background = None
    source_width, source_height = len(rows[0])//3, len(rows)
    for colour, x, y, width, height in pending[offset:stop]:
        native.colour(*colour)
        left, right = x*vw//source_width, (x+width)*vw//source_width
        top, bottom = y*vh//source_height, (y+height)*vh//source_height
        if right > left and bottom > top:
            native.fill(vx+left, vy+top, right-left, bottom-top)
    state["offset"] = stop
    if stop > offset or state["key"] is None:
        # A slow USB burst must not expire the 1500ms producer lease. Renew
        # from successful writes only; never keep a dead/stopped owner alive
        # with a detached timer. Preserve BB36's existing recovery callback.
        original = getattr(native, '_progress_callback', None)
        progress_setter = getattr(native, 'set_progress_callback', None)
        due = [0.0]
        def progress():
            now = time.monotonic()
            if now >= due[0]:
                (heartbeat or renew_demand)()
                due[0] = now + 0.25
            if original is not None:
                original()
        metrics = state.setdefault('transport', dict(reports=0,write_ms=0.0,max_write_ms=0.0))
        native._image_transfer_metrics = metrics
        started = time.perf_counter()
        try:
            if callable(progress_setter):
                progress_setter(progress)
            native.command(0x103)
            state['commits'] += 1
        except Exception:
            invalidate(canvas)
            raise
        finally:
            state['batch_ms'] = (time.perf_counter()-started)*1000
            native._image_transfer_metrics = None
            if callable(progress_setter):
                progress_setter(original)
    if latest:
        state['rows'] = committed_rows(state['rows'], pending[offset:stop])
    if stop == len(pending):
        state["rows"] = state.pop("target")
        state["key"] = state.pop("target_key")
        state["pending"] = None
    return True
