"""Short-lived-client side of the MuslimSim loopback control channel."""

from __future__ import annotations

import socket
from typing import Any, Mapping

from .protocol import MAX_LINE_BYTES, ProtocolError, decode, encode


class ControlClientError(RuntimeError):
    pass


class ControlClient:
    def __init__(self, port: int, token: str, *, timeout: float = 1.0) -> None:
        self.port = int(port)
        self.token = str(token)
        self.timeout = max(0.1, float(timeout))

    def request(self, command: str, **fields: Any) -> dict[str, Any]:
        request = {"cmd": command, "token": self.token, **fields}
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=self.timeout) as connection:
                connection.settimeout(self.timeout)
                connection.sendall(encode(request))
                buffer = bytearray()
                while not buffer.endswith(b"\n"):
                    chunk = connection.recv(min(65536, MAX_LINE_BYTES - len(buffer)))
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if len(buffer) > MAX_LINE_BYTES:
                        raise ControlClientError("Control response is too large")
        except OSError as exc:
            raise ControlClientError(f"Bridge control channel is unavailable: {exc}") from exc
        try:
            response = decode(bytes(buffer))
        except ProtocolError as exc:
            raise ControlClientError(str(exc)) from exc
        if not response.get("ok"):
            raise ControlClientError(str(response.get("error") or "Bridge rejected request"))
        return response

    def ping(self) -> bool:
        try:
            return bool(self.request("ping").get("ok"))
        except ControlClientError:
            return False

