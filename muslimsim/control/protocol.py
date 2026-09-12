"""Wire-level helpers shared by the JSON-lines client and server."""

from __future__ import annotations

import json
import secrets
from typing import Any, Mapping


PROTOCOL_VERSION = 2
MAX_LINE_BYTES = 1024 * 1024


class ProtocolError(ValueError):
    pass


def new_token() -> str:
    return secrets.token_urlsafe(24)


def encode(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def decode(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError("Request is too large")
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Invalid JSON request") from exc
    if not isinstance(value, dict):
        raise ProtocolError("Request must be an object")
    return value

