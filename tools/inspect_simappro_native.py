"""Read-only inspection of SimAppPro's native WinCtrl libraries."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import pefile


DEFAULT_FILES = (
    Path(r"C:\Program Files (x86)\SimAppPro\resources\app.asar.unpacked\WWTHID_JSAPI.node"),
    Path(r"C:\Program Files (x86)\SimAppPro\resources\app.asar.unpacked\WWTHID.dll"),
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, default=DEFAULT_FILES)
    parser.add_argument(
        "--pattern",
        default=(
            r"lcd|line|draw|rect|pixel|bitmap|image|curve|screen|font|utf|fill|"
            r"refresh|feature|grid|grip|polygon|ellipse|circle|point"
        ),
        help="Case-insensitive regex applied to printable strings",
    )
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    matcher = re.compile(args.pattern, re.IGNORECASE)
    ascii_strings = re.compile(rb"[ -~]{4,}")

    for path in args.files:
        print(f"FILE {path}")
        pe = pefile.PE(str(path), fast_load=False)
        print("EXPORTS")
        exports = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
        if exports:
            for symbol in exports.symbols:
                name = (symbol.name or b"").decode("ascii", "replace")
                print(f"{name}\tRVA=0x{symbol.address:X}\tordinal={symbol.ordinal}")
        else:
            print("(none)")

        strings = {
            match.group().decode("ascii", "replace")
            for match in ascii_strings.finditer(path.read_bytes())
        }
        matches = sorted(value for value in strings if matcher.search(value))
        print("MATCHING ASCII STRINGS")
        for value in matches[: max(1, args.limit)]:
            print(value)
        print(f"COUNT {len(matches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
