from __future__ import annotations

from typing import Iterable

PDC_INPUT_REPORT_ID = 0x01
PDC_OUTPUT_ACK_REPORT_ID = 0x02
PDC_LOGICAL_INPUT_SIZE = 17
PDC_OUTPUT_ACK_SIZE = 14


def normalize_input_report(report: bytes | bytearray | Iterable[int]) -> bytes | None:
    """Return the logical PDC input prefix or ``None`` for ACK/invalid traffic.

    Windows/hidapi may return the real BB61/BB52 report padded to 64 bytes.
    The capture-proven logical payload is the first 17 bytes.  Output reports
    generate 14-byte ID-02 acknowledgements and must never become button input.
    """

    raw = bytes(report)
    if not raw:
        return None
    if raw[0] == PDC_OUTPUT_ACK_REPORT_ID:
        return None
    if raw[0] != PDC_INPUT_REPORT_ID or len(raw) < PDC_LOGICAL_INPUT_SIZE:
        return None
    return raw[:PDC_LOGICAL_INPUT_SIZE]
