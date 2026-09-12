"""Count native glyph tiles for every moving PFD pitch-ladder mark.

This is an offline sizing tool.  It builds the major paired 10/20-degree
rungs, the centred 5-degree rungs, and the centred 2.5-degree rungs from one
continuous raster per angle, then reports how many unique native cells the
complete ladder needs.  It never opens X-Plane or a physical display.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw


ANGLES = (-45,) + tuple(range(-44, 45, 2)) + (45,)
VARIANTS = {
    "major": ((-42, -10), (10, 42)),
    "medium": ((-16, 16),),
    "minor": ((-8, 8),),
}


def analyse(cell_width: int, cell_height: int, thickness: int) -> None:
    canvas_width = cell_width * math.ceil(120 / cell_width)
    canvas_height = cell_height * math.ceil(120 / cell_height)
    center_x = canvas_width / 2.0
    center_y = canvas_height / 2.0
    all_patterns: set[bytes] = set()
    by_variant: dict[str, set[bytes]] = {}
    total_tiles = 0
    max_tiles = 0

    for name, segments in VARIANTS.items():
        patterns: set[bytes] = set()
        for angle in ANGLES:
            image = Image.new("1", (canvas_width, canvas_height), 0)
            draw = ImageDraw.Draw(image)
            radians = math.radians(float(angle))
            tangent = math.cos(radians), math.sin(radians)
            for start, end in segments:
                draw.line(
                    (
                        round(center_x + start * tangent[0]),
                        round(center_y + start * tangent[1]),
                        round(center_x + end * tangent[0]),
                        round(center_y + end * tangent[1]),
                    ),
                    fill=1,
                    width=thickness,
                )
            pixels = image.load()
            angle_tiles = 0
            for y0 in range(0, canvas_height, cell_height):
                for x0 in range(0, canvas_width, cell_width):
                    bits = bytes(
                        1 if pixels[x0 + x, y0 + y] else 0
                        for y in range(cell_height)
                        for x in range(cell_width)
                    )
                    if any(bits):
                        patterns.add(bits)
                        all_patterns.add(bits)
                        angle_tiles += 1
            total_tiles += angle_tiles
            max_tiles = max(max_tiles, angle_tiles)
        by_variant[name] = patterns

    print(
        f"cell={cell_width}x{cell_height} thickness={thickness}: "
        f"unique={len(all_patterns)}, total={total_tiles}, "
        f"max/shape/angle={max_tiles}, slots={(len(all_patterns) + 93) // 94}"
    )
    print("  " + ", ".join(
        f"{name}={len(patterns)}" for name, patterns in by_variant.items()
    ))


def main() -> None:
    for cell_width, cell_height in (
        (17, 16), (24, 16), (32, 16), (40, 16),
        (17, 20), (24, 20), (32, 20), (40, 20),
        (17, 29), (24, 24), (32, 32), (40, 40),
    ):
        for thickness in (2, 3):
            analyse(cell_width, cell_height, thickness)


if __name__ == "__main__":
    main()
