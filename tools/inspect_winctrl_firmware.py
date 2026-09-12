"""Read-only structural inspection of cached SimAppPro firmware containers."""

from __future__ import annotations

from collections import Counter
import math
from pathlib import Path


FILES = (
    Path(r"C:\Users\noureddine aidoudi\AppData\Roaming\SimAppPro\Download\Firmware\MCDU-32"),
    Path(r"C:\Users\noureddine aidoudi\AppData\Roaming\SimAppPro\Download\Firmware\PFP-3N"),
)


def entropy(data: bytes) -> float:
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def main() -> int:
    contents = [path.read_bytes() for path in FILES]
    for path, data in zip(FILES, contents):
        print(f"{path.name}: {len(data)} bytes, entropy {entropy(data):.4f} bits/byte")
        print(f"  head: {data[:32].hex(' ')}")
        for block_size in (4, 8, 16, 32):
            blocks = [data[i:i + block_size] for i in range(0, len(data), block_size)]
            repeated = sum(count - 1 for count in Counter(blocks).values() if count > 1)
            print(f"  {block_size:2d}-byte repeated blocks: {repeated}")

    left, right = contents
    differing = [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
    print(f"differing positions: {len(differing)}")
    for index in differing[:200]:
        print(f"  0x{index:06X}: {left[index]:02X} -> {right[index]:02X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
