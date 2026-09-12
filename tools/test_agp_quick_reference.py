#!/usr/bin/env python3
"""Offline placement/content checks for the AGP left-side quick guide."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.gui.studio import MuslimSimStudio


class FakeCanvas:
    def __init__(self) -> None:
        self.next_id = 1
        self.items = {}

    def _add(self, kind: str, coords, **kwargs):
        item = self.next_id
        self.next_id += 1
        self.items[item] = {
            "kind": kind,
            "coords": tuple(coords),
            **kwargs,
        }
        return item

    def create_round_rect(self, *coords, **kwargs):
        return self._add("round_rect", coords, **kwargs)

    def create_text(self, x, y, **kwargs):
        return self._add("text", (x, y), **kwargs)

    def bbox(self, item):
        data = self.items[item]
        text = str(data.get("text") or "")
        width = float(data.get("width") or 120)
        # Conservative compact text-height approximation.
        wrapped = 0
        for line in text.splitlines() or [""]:
            chars_per_line = max(8, int(width / 6.0))
            wrapped += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
        x, y = data["coords"]
        return (x, y, x + width, y + wrapped * 11)

    def texts(self):
        return [
            str(item.get("text") or "")
            for item in self.items.values()
            if item["kind"] == "text"
        ]


class Harness:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def _device_mirror(self, key: str):
        assert key == "agp_bb80"
        return {"page": self.mode}


def visible_hardware_left(
    authored_width: float,
    authored_height: float,
    offset_x: float,
) -> float:
    scale = min(
        max(1.0, authored_width - 24.0) / 900.0,
        max(1.0, authored_height - 24.0) / 660.0,
    )
    scale = max(0.45, scale)
    local_ox = (authored_width - 900.0 * scale) / 2.0
    return offset_x + local_ox + 24.0 * scale


def render(viewport_width, viewport_height, authored_width, authored_height, ox, oy, mode="radio"):
    canvas = FakeCanvas()
    MuslimSimStudio._draw_agp_quick_reference(
        Harness(mode),
        canvas,
        viewport_width,
        viewport_height,
        authored_width,
        authored_height,
        ox,
        oy,
    )
    return canvas


def main() -> int:
    checks = 0

    # This approximates the user's screenshot: a normal faceplate viewport
    # with a meaningful empty blue gap LEFT of the visible landing-gear panel.
    normal = render(1280, 700, 980, 680, 150, 10)
    texts = "\n".join(normal.texts())
    required = (
        "AGP QUICK GUIDE",
        "CURRENT: RADIO",
        "TERR ON ND",
        "RADIO <-> NAV",
        "= VHF1 / VHF2 / VHF3",
        "CHR turn = coarse tune",
        "RST push = ACTIVE/STBY",
        "SET long = edit / next digit",
        "Flashing digit = selected",
        "SET tap = finish / stop flash",
        "RUN = STBY",
        "STP = ALT OFF",
        "RST spring = ALT ON > TA > TA/RA",
        "RST turn = SPEED",
        "CHR turn = ALTITUDE",
        "SET turn = HEADING",
        "GEAR UP / DOWN",
        "AUTO BRK LO / MED / MAX",
    )
    for token in required:
        checks += 1
        assert token in texts, token

    cards = [
        item for item in normal.items.values()
        if item["kind"] == "round_rect"
    ]
    checks += 1
    assert cards, "left-side guide card was not drawn"
    card = cards[0]
    left, top, right, bottom = card["coords"]

    hardware_left = visible_hardware_left(980, 680, 150)
    checks += 1
    assert right <= hardware_left - 9.0, (
        card["coords"], hardware_left
    )
    checks += 1
    assert left >= 12.0, card["coords"]
    checks += 1
    assert right < 150 + 980, (
        "guide incorrectly went to the right side",
        card["coords"],
    )

    # Current mode follows the bridge mirror.
    nav = render(1280, 700, 980, 680, 150, 10, "navigation")
    checks += 1
    assert "CURRENT: NAV" in "\n".join(nav.texts())

    # A larger host keeps the guide adjacent to the hardware, not stranded
    # against the far-left window edge.
    wide = render(1600, 760, 980, 680, 310, 40)
    wide_cards = [
        item for item in wide.items.values()
        if item["kind"] == "round_rect"
    ]
    checks += 1
    assert wide_cards
    wleft, _, wright, _ = wide_cards[0]["coords"]
    whardware = visible_hardware_left(980, 680, 310)
    checks += 1
    assert abs((whardware - 10.0) - wright) < 1.0
    checks += 1
    assert wleft > 12.0, "wide guide should stay next to AGP hardware"

    # If there truly is no safe left blue gap, hide instead of covering the
    # landing-gear panel.
    narrow = render(1000, 700, 980, 680, 10, 10)
    checks += 1
    assert not narrow.items, "guide covered hardware in a too-narrow viewport"

    print(f"AGP left quick-reference check passed: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
