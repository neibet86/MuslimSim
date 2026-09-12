from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any, Mapping

from .cloud import SecureTokenStore


def runtime_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".muslimsim"
    path = root / "MuslimSim" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def locator_path() -> Path:
    return runtime_directory() / "platform_v7.locator"


def write_locator(port: int, token: str, *, pid: int | None = None, root: str = "") -> Path:
    payload = {
        "schema": 1,
        "port": int(port),
        "token": str(token),
        "pid": int(pid or os.getpid()),
        "root": str(root),
        "written_at": time.time(),
    }
    store = SecureTokenStore(locator_path())
    store.save(payload)
    return store.path


def read_locator() -> dict[str, Any]:
    payload = SecureTokenStore(locator_path()).load()
    if not payload:
        return {}
    if int(payload.get("schema", 0)) != 1:
        return {}
    try:
        port = int(payload.get("port", 0))
    except (TypeError, ValueError):
        return {}
    if not (1 <= port <= 65535) or not payload.get("token"):
        return {}
    return payload


def remove_locator(*, pid: int | None = None) -> None:
    path = locator_path()
    if pid is not None and path.exists():
        try:
            payload = read_locator()
            if int(payload.get("pid", -1)) != int(pid):
                return
        except Exception:
            return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
