"""Render exactly what the PFP screen will show, without touching the PFP.

This is an offline emulator of the PFP's native drawing surface.  It accepts
the same `colour` / `fill` / `text` command set as the real display canvas in
`bridge/final.py`, so it can run the live renderer in
`muslimsim/devices/pfp_renderer.py` and save the resulting 640x480 frame as a
PNG.

Text is drawn with the exact variable-size native glyph resources the
controller receives: 17x29 slots 3/4/5/6 and the guarded 40x40 continuous
pitch-rung tiles in slots 7/8.  Their opaque backgrounds are represented
faithfully.

It never opens the PFP HID device, COM5, the WinCtrl hardware, or X-Plane.

Usage:
    python tools/render_pfp_frame_png.py                 # every scenario
    python tools/render_pfp_frame_png.py --scenario high
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from typing import Tuple

from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices import pfp_renderer
from muslimsim.devices.pfp_renderer import HEIGHT, WIDTH, FONT_CELL_HEIGHT, FONT_CELL_WIDTH

OUTPUT_DIR = PROJECT / "PNG"
FONT_BUILDER = PROJECT / "tools" / "build_pfp_dual_font.py"
FONT_RESOURCE = (
    PROJECT / "bridge" / "winctrl-pfp-b737-cockpit-font3-4-5-6-8.xpwwf"
)


def _load_font_builder():
    """Import the font builder for its resource parser and cell geometry."""
    spec = importlib.util.spec_from_file_location("_pfp_font_builder", FONT_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_font_glyphs(
    font_id: int,
) -> tuple[dict[str, Image.Image], tuple[int, int]]:
    """Decode the glyphs from the font resource the panel is actually sent.

    Reading the uploaded resource rather than re-rasterising the typeface means
    the emulator also shows the static shape tiles that are stored in the
    font's spare glyph codes.
    """
    builder = _load_font_builder()
    raw = FONT_RESOURCE.read_bytes()
    header = None
    for _identifier, function_id, _transaction, _flag, data in builder._command_records(raw):
        if function_id != 0x106 or len(data) < 24:
            continue
        if int.from_bytes(data[:4], "little") == int(font_id):
            header = data
            break
    if header is None:
        raise RuntimeError(f"font slot {font_id} is missing from {FONT_RESOURCE.name}")
    width = int.from_bytes(header[4:6], "little")
    height = int.from_bytes(header[6:8], "little")
    glyph_size = int.from_bytes(header[8:12], "little")
    bytes_per_row = (width + 7) // 8
    if glyph_size != 4 + bytes_per_row * height:
        raise RuntimeError(f"font slot {font_id} has inconsistent geometry")
    memory = builder._font_memory(raw, int(font_id))
    glyphs: dict[str, Image.Image] = {}
    for glyph_start in range(0, len(memory), glyph_size):
        glyph = memory[glyph_start:glyph_start + glyph_size]
        if len(glyph) != glyph_size:
            continue
        codepoint = int.from_bytes(glyph[:4], "little")
        mask = Image.new("L", (width, height), 0)
        pixels = mask.load()
        for row in range(height):
            for byte_index in range(bytes_per_row):
                value = glyph[4 + row * bytes_per_row + byte_index]
                for bit in range(8):
                    x = byte_index * 8 + bit
                    if x < width and value & (1 << (7 - bit)):
                        pixels[x, row] = 255
        glyphs[chr(codepoint)] = mask
    return glyphs, (width, height)


class PfpFrame:
    """The PFP native command surface, drawn into a PIL image instead of USB."""

    def __init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        self._colour = (255, 255, 255)
        self.fills = 0
        self.texts = 0
        self.colour_changes = 0
        loaded = {
            font_id: _load_font_glyphs(font_id)
            for font_id in (3, 4, 5, 6, 7, 8)
        }
        self._glyphs = {font_id: item[0] for font_id, item in loaded.items()}
        self._font_sizes = {font_id: item[1] for font_id, item in loaded.items()}
        self._muslimsim_bank_line_font = True

    # -- native command set -------------------------------------------------
    def colour(self, red: int, green: int, blue: int) -> None:
        self._colour = (int(red), int(green), int(blue))
        self.colour_changes += 1

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        self.fills += 1
        if width <= 0 or height <= 0:
            return
        patch = Image.new("RGB", (int(width), int(height)), self._colour)
        self.image.paste(patch, (int(x), int(y)))

    def text(
        self,
        x: int,
        y: int,
        value: str,
        foreground: Tuple[int, int, int],
        background: Tuple[int, int, int],
        font_id: int,
    ) -> None:
        self.texts += 1
        cell_width, cell_height = self._font_sizes.get(
            int(font_id), (FONT_CELL_WIDTH, FONT_CELL_HEIGHT)
        )
        for index, character in enumerate(value):
            cell = Image.new("RGB", (cell_width, cell_height), tuple(background))
            ink = Image.new("RGB", (cell_width, cell_height), tuple(foreground))
            cell.paste(ink, (0, 0), self._glyph(character, font_id))
            self.image.paste(cell, (int(x) + index * cell_width, int(y)))

    def command(self, _code: int) -> None:
        """The LCD refresh; nothing to do for an offline frame."""

    # -- helpers ------------------------------------------------------------
    def _glyph(self, character: str, font_id: int) -> Image.Image:
        font = self._glyphs.get(int(font_id), self._glyphs[6])
        width, height = self._font_sizes.get(
            int(font_id), (FONT_CELL_WIDTH, FONT_CELL_HEIGHT)
        )
        return font.get(character, Image.new("L", (width, height), 0))

    @property
    def primitives(self) -> int:
        return self.fills + self.texts


def render_nd(values: dict) -> PfpFrame:
    """Render one ND page through the same emulated command surface."""
    from muslimsim.devices import nd_renderer

    frame = PfpFrame()
    nd_renderer.draw_nd_frame(frame, values)
    return frame


def render(values: dict) -> PfpFrame:
    frame = PfpFrame()
    if values:
        pfp_renderer.draw_live_pfd(frame, values)
    else:
        frame.colour(*pfp_renderer.BLACK)
        frame.fill(0, 0, WIDTH, HEIGHT)
        frame.colour(*pfp_renderer.AMBER)
        frame.text(160, 200, "NO SIM DATA", pfp_renderer.AMBER, pfp_renderer.BLACK, 6)
    return frame


class _CountingDevice:
    """A stand-in for the PFP HID handle that only counts what would be sent."""

    def __init__(self) -> None:
        self.reports = 0
        self.byte_count = 0

    def write(self, report) -> int:
        self.reports += 1
        self.byte_count += len(report)
        return len(report)


def usb_cost(values: dict) -> tuple[int, int]:
    """Return (HID reports, payload bytes) for one frame, using the real canvas.

    This runs the bridge's own `_PfpNativeCanvas` against a counting device, so
    the number is the traffic the panel would actually receive.  No HID handle
    is opened.
    """
    from muslimsim.core.engine import _load_engine

    bridge = _load_engine()
    device = _CountingDevice()
    canvas = bridge._PfpNativeCanvas(device)
    canvas._muslimsim_bank_line_font = True
    if values:
        pfp_renderer.draw_live_pfd(canvas, values)
    canvas.command(0x103)  # native LCD refresh, which flushes the frame
    return device.reports, device.byte_count


def main() -> int:
    from show_pfd_preview import scenario_values  # noqa: E402  (same tools folder)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("normal", "high", "low", "offline", "minimums", "minimums-reached",
                 "radio-minimums", "zero", "extreme", "below-sea-level",
                 "bands", "takeoff-bugs", "all"),
        default="all", help="Which flight condition to draw.")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR, help="Output folder (default: PNG/).")
    parser.add_argument("--prefix", default="pfp-frame", help="Output file prefix.")
    args = parser.parse_args()

    names = ("normal", "high", "low") if args.scenario == "all" else (args.scenario,)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"MuslimSim PFP frame emulator -> {args.out}")
    for name in names:
        frame = render(scenario_values(name))
        path = args.out / f"{args.prefix}-{name}.png"
        frame.image.save(path, "PNG", optimize=True)
        reports, byte_count = usb_cost(scenario_values(name))
        print(f"  {path.name:<28} {frame.fills:4d} fills  {frame.texts:3d} text runs  "
              f"{frame.colour_changes:3d} colours  ->  {reports:4d} HID reports "
              f"({byte_count / 1024.0:.1f} KiB)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
