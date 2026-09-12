"""Report glyph-pattern counts for continuous PFD pitch-rung tile designs."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw


ANGLES = tuple(range(-45, 46, 2))


def analyse(
    outer: int,
    gap: int,
    thickness: int,
    cell_width: int,
    cell_height: int,
) -> tuple[int, int, int]:
    canvas_width = cell_width * math.ceil((outer * 2 + 20) / cell_width)
    canvas_height = cell_height * math.ceil((outer * 2 + 20) / cell_height)
    patterns: set[bytes] = set()
    total_tiles = 0
    maximum_tiles = 0
    cx = canvas_width / 2.0
    cy = canvas_height / 2.0
    for angle in ANGLES:
        image = Image.new("1", (canvas_width, canvas_height), 0)
        draw = ImageDraw.Draw(image)
        radians = math.radians(angle)
        tangent = (math.cos(radians), math.sin(radians))
        for start, end in ((-outer, -gap), (gap, outer)):
            draw.line(
                (
                    round(cx + start * tangent[0]),
                    round(cy + start * tangent[1]),
                    round(cx + end * tangent[0]),
                    round(cy + end * tangent[1]),
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
                    angle_tiles += 1
        total_tiles += angle_tiles
        maximum_tiles = max(maximum_tiles, angle_tiles)
    return len(patterns), total_tiles, maximum_tiles


def main() -> None:
    for cell_width, cell_height in ((17, 29), (24, 24), (32, 32), (40, 40)):
        for outer, gap in ((30, 10), (36, 10), (42, 10)):
            for thickness in (2, 3):
                unique, total, maximum = analyse(
                    outer, gap, thickness, cell_width, cell_height
                )
                print(
                    f"cell={cell_width:2d}x{cell_height:2d} outer={outer:2d} "
                    f"gap={gap:2d} thickness={thickness}: "
                    f"unique={unique:3d}, total={total:3d}, max/angle={maximum}"
                )


if __name__ == "__main__":
    main()
