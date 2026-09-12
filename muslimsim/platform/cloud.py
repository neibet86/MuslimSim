from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import secrets
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import AuthenticationError, ConflictError, PlatformError, ValidationError
from .profiles import ProfileDatabase


@dataclass
class RabtaConfig:
    auth_base: str = "https://auth.rabta.dev"
    api_base: str = "https://api.rabta.dev"
    project_id: str = ""
    public_api_key: str = ""
    client_name: str = "MuslimSim Studio"
    timeout_seconds: float = 15.0

    def normalized(self) -> "RabtaConfig":
        return RabtaConfig(
            auth_base=self.auth_base.rstrip("/"),
            api_base=self.api_base.rstrip("/"),
            project_id=str(self.project_id or "").strip(),
            public_api_key=str(self.public_api_key or "").strip(),
            client_name=str(self.client_name or "MuslimSim Studio").strip(),
            timeout_seconds=max(3.0, min(float(self.timeout_seconds), 60.0)),
        )


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    if not data:
        return _DataBlob(0, None), None
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


class SecureTokenStore:
    """Stores Rabta tokens with Windows DPAPI under the current user account."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def dpapi_available(self) -> bool:
        return os.name == "nt" and hasattr(ctypes, "windll")

    def _protect_windows(self, raw: bytes) -> bytes:
        incoming, incoming_buf = _blob(raw)
        entropy, entropy_buf = _blob(b"MuslimSim.Platform.V7.Rabta")
        outgoing = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        ok = crypt32.CryptProtectData(
            ctypes.byref(incoming), "MuslimSim Rabta token", ctypes.byref(entropy),
            None, None, 0x01, ctypes.byref(outgoing),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData)
        finally:
            kernel32.LocalFree(outgoing.pbData)

    def _unprotect_windows(self, raw: bytes) -> bytes:
        incoming, incoming_buf = _blob(raw)
        entropy, entropy_buf = _blob(b"MuslimSim.Platform.V7.Rabta")
        outgoing = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(incoming), None, ctypes.byref(entropy),
            None, None, 0x01, ctypes.byref(outgoing),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData)
        finally:
            kernel32.LocalFree(outgoing.pbData)

    def save(self, payload: Mapping[str, Any]) -> None:
        raw = json.dumps(dict(payload), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if self.dpapi_available:
            envelope = {"schema": 1, "protected": "dpapi-user", "data": base64.b64encode(self._protect_windows(raw)).decode("ascii")}
        else:
            # Non-Windows is supported only for development. File permissions
            # are restricted and the envelope makes the weaker protection
            # visible rather than pretending it is equivalent to DPAPI.
            envelope = {"schema": 1, "protected": "filesystem-user", "data": base64.b64encode(raw).decode("ascii")}
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
        try:
            os.chmod(temp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(temp, self.path)

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        envelope = json.loads(self.path.read_text(encoding="utf-8"))
        raw = base64.b64decode(str(envelope.get("data") or ""))
        if envelope.get("protected") == "dpapi-user":
            if not self.dpapi_available:
                raise AuthenticationError("Rabta token was protected by Windows DPAPI and cannot be opened on this operating system")
            raw = self._unprotect_windows(raw)
        return dict(json.loads(raw.decode("utf-8")))

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class RabtaClient:
    def __init__(self, config: RabtaConfig, token_store: SecureTokenStore) -> None:
        self.config = config.normalized()
        self.token_store = token_store
        self.session = token_store.load()

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None = None,
        authenticated: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MuslimSim-Platform/7",
            **dict(headers or {}),
        }
        if self.config.public_api_key:
            request_headers.setdefault("apikey", self.config.public_api_key)
        if authenticated:
            token = str(self.session.get("access_token") or "")
            if not token:
                raise AuthenticationError("Sign in to Rabta before syncing profiles")
            request_headers["Authorization"] = f"Bearer {token}"
        data = None if body is None else json.dumps(dict(body), separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method.upper(), headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = response.read()
                return dict(json.loads(payload.decode("utf-8"))) if payload else {}
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(payload)
            except ValueError:
                detail = {"error": payload or exc.reason}
            if exc.code == 401 and authenticated and self.session.get("refresh_token"):
                self.refresh()
                return self._request(method, url, body=body, authenticated=authenticated, headers=headers)
            if exc.code == 409:
                raise ConflictError(str(detail)) from exc
            if exc.code in {401, 403}:
                raise AuthenticationError(str(detail)) from exc
            raise PlatformError(f"Rabta HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PlatformError(f"Rabta is unreachable: {exc.reason}") from exc

    def signup(self, email: str, password: str, *, display_name: str = "") -> dict[str, Any]:
        email = str(email).strip().lower()
        if "@" not in email or len(password) < 8:
            raise ValidationError("Enter a valid email and a password of at least eight characters")
        payload = self._request(
            "POST",
            f"{self.config.auth_base}/signup",
            body={
                "email": email,
                "password": password,
                "data": {
                    "display_name": str(display_name or ""),
                    "product": "muslimsim",
                    "project_id": self.config.project_id,
                },
            },
        )
        if payload.get("access_token"):
            self._save_session(payload)
        return payload

    def login(self, email: str, password: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"grant_type": "password"})
        payload = self._request(
            "POST", f"{self.config.auth_base}/token?{query}",
            body={"email": str(email).strip().lower(), "password": str(password)},
        )
        if not payload.get("access_token"):
            raise AuthenticationError("Rabta did not return an access token")
        self._save_session(payload)
        return {"user": payload.get("user"), "expires_in": payload.get("expires_in")}

    def refresh(self) -> None:
        refresh_token = str(self.session.get("refresh_token") or "")
        if not refresh_token:
            raise AuthenticationError("No Rabta refresh token is available")
        query = urllib.parse.urlencode({"grant_type": "refresh_token"})
        payload = self._request(
            "POST", f"{self.config.auth_base}/token?{query}",
            body={"refresh_token": refresh_token},
        )
        self._save_session(payload)

    def _save_session(self, payload: Mapping[str, Any]) -> None:
        user = dict(payload.get("user") or {})
        self.session = {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token") or self.session.get("refresh_token"),
            "expires_in": payload.get("expires_in"),
            "expires_at": time.time() + float(payload.get("expires_in") or 3600),
            "token_type": payload.get("token_type", "bearer"),
            "user_id": user.get("id") or payload.get("user_id") or "",
            "email": user.get("email") or payload.get("email") or "",
        }
        self.token_store.save(self.session)

    def logout(self) -> None:
        self.session = {}
        self.token_store.clear()

    def status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.config.auth_base and self.config.api_base),
            "signed_in": bool(self.session.get("access_token")),
            "user_id": self.session.get("user_id", ""),
            "email": self.session.get("email", ""),
            "project_id": self.config.project_id,
            "token_protection": "dpapi-user" if self.token_store.dpapi_available else "filesystem-user-development",
        }

    def push_mutations(self, database: ProfileDatabase, *, limit: int = 100) -> dict[str, Any]:
        items = database.outbox(limit)
        if not items:
            return {"pushed": 0, "acknowledged": [], "conflicts": []}
        response = self._request(
            "POST",
            f"{self.config.api_base}/v1/muslimsim/sync/push",
            authenticated=True,
            body={"project_id": self.config.project_id, "mutations": items, "client": self.config.client_name},
        )
        acknowledged = [str(value) for value in response.get("acknowledged") or []]
        database.acknowledge_mutations(acknowledged)
        for conflict in response.get("conflicts") or []:
            database.record_conflict(
                str(conflict.get("entity_type") or "unknown"),
                str(conflict.get("entity_id") or ""),
                conflict.get("local"), conflict.get("remote"),
            )
        return {
            "pushed": len(items),
            "acknowledged": acknowledged,
            "conflicts": list(response.get("conflicts") or []),
        }

    def pull_profiles(self, cursor: str = "") -> dict[str, Any]:
        query = urllib.parse.urlencode({"project_id": self.config.project_id, "cursor": cursor})
        return self._request(
            "GET", f"{self.config.api_base}/v1/muslimsim/sync/pull?{query}", authenticated=True,
        )

    def sync(self, database: ProfileDatabase, cursor: str = "") -> dict[str, Any]:
        pushed = self.push_mutations(database)
        pulled = self.pull_profiles(cursor)
        imported = 0
        for document in pulled.get("profiles") or []:
            try:
                database.import_profile(document, activate=False)
                imported += 1
            except Exception as exc:
                database.record_conflict("profile", str(document.get("profile", {}).get("profile_id") or ""), {}, document)
        return {
            "pushed": pushed,
            "pulled": len(pulled.get("profiles") or []),
            "imported": imported,
            "cursor": pulled.get("cursor", cursor),
        }
