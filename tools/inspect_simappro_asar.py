"""Search SimAppPro's Electron ASAR without extracting or modifying it.

The tool understands the small Chromium-pickle header used by Electron ASAR
archives, walks its file index, and prints matching source lines.  It is a
read-only reverse-engineering aid for the WinCtrl display protocol.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import sys
from typing import Iterator


DEFAULT_ASAR = Path(r"C:\Program Files (x86)\SimAppPro\resources\app.asar")


def _walk(files: dict, prefix: str = "") -> Iterator[tuple[str, dict]]:
    for name, metadata in files.items():
        path = f"{prefix}/{name}" if prefix else name
        children = metadata.get("files")
        if isinstance(children, dict):
            yield from _walk(children, path)
        else:
            yield path, metadata


def _index(archive: Path) -> tuple[int, list[tuple[str, dict]]]:
    with archive.open("rb") as stream:
        header = stream.read(16)
        if len(header) != 16:
            raise ValueError("ASAR header is truncated")
        pickle_payload, header_pickle_size, _json_pickle_size, json_size = (
            struct.unpack("<IIII", header)
        )
        if pickle_payload != 4 or json_size <= 0:
            raise ValueError("Unrecognised Electron ASAR header")
        raw_index = stream.read(json_size)
    index = json.loads(raw_index.decode("utf-8"))
    return 8 + header_pickle_size, list(_walk(index["files"]))


def main() -> int:
    # SimAppPro contains translated strings that are not representable on a
    # legacy Windows console code page.  Keep source inspection reliable.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asar", type=Path, default=DEFAULT_ASAR)
    parser.add_argument("--pattern", required=True, help="Case-insensitive regex")
    parser.add_argument("--path", default=r"\.(?:js|json|ts|html)$", help="Path regex")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--line-range",
        help="Only print source lines in an inclusive START:END range",
    )
    args = parser.parse_args()

    matcher = re.compile(args.pattern, re.IGNORECASE)
    path_matcher = re.compile(args.path, re.IGNORECASE)
    line_start, line_end = 1, 2**31 - 1
    if args.line_range:
        start_text, separator, end_text = args.line_range.partition(":")
        if not separator:
            parser.error("--line-range must be START:END")
        line_start, line_end = int(start_text), int(end_text)
    data_base, entries = _index(args.asar)
    hits = 0
    with args.asar.open("rb") as stream:
        for path, metadata in entries:
            if metadata.get("unpacked") or not path_matcher.search(path):
                continue
            size = int(metadata.get("size", 0))
            offset = metadata.get("offset")
            if not offset or size <= 0 or size > 32 * 1024 * 1024:
                continue
            stream.seek(data_base + int(offset))
            text = stream.read(size).decode("utf-8", "replace")
            for number, line in enumerate(text.splitlines(), 1):
                if number < line_start or number > line_end:
                    continue
                if matcher.search(line):
                    print(f"{path}:{number}: {line[:500]}")
                    hits += 1
                    if hits >= max(1, args.limit):
                        return 0
    print(f"matches: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
