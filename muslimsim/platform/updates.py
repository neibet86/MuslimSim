from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import PlatformError, ValidationError


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, value: str) -> "Version":
        text = str(value).strip().lstrip("v")
        core, _, prerelease = text.partition("-")
        parts = core.split(".")
        if len(parts) != 3 or any(not item.isdigit() for item in parts):
            raise ValidationError(f"Invalid semantic version {value!r}")
        return cls(*(int(item) for item in parts), prerelease=prerelease)

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        return value if not self.prerelease else f"{value}-{self.prerelease}"


@dataclass(frozen=True)
class UpdateManifest:
    schema: int
    version: str
    package_url: str
    sha256: str
    signature: str
    key_id: str
    minimum_platform: str = "7.0.0"
    release_notes: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UpdateManifest":
        manifest = cls(
            schema=int(data.get("schema", 0)),
            version=str(data.get("version") or ""),
            package_url=str(data.get("package_url") or ""),
            sha256=str(data.get("sha256") or "").lower(),
            signature=str(data.get("signature") or ""),
            key_id=str(data.get("key_id") or ""),
            minimum_platform=str(data.get("minimum_platform") or "7.0.0"),
            release_notes=str(data.get("release_notes") or ""),
        )
        if manifest.schema != 1:
            raise ValidationError("Unsupported MuslimSim update manifest schema")
        Version.parse(manifest.version)
        if len(manifest.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in manifest.sha256):
            raise ValidationError("Update manifest has an invalid SHA-256")
        if not manifest.package_url.startswith("https://"):
            raise ValidationError("Update packages must use HTTPS")
        if not manifest.signature or not manifest.key_id:
            raise ValidationError("Unsigned MuslimSim updates are refused")
        return manifest

    def signed_payload(self) -> bytes:
        return json.dumps(
            {
                "schema": self.schema,
                "version": self.version,
                "package_url": self.package_url,
                "sha256": self.sha256,
                "key_id": self.key_id,
                "minimum_platform": self.minimum_platform,
                "release_notes": self.release_notes,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


class UpdateVerifier:
    """Strict Ed25519 verifier. Missing crypto support disables updates safely."""

    def __init__(self, public_keys: Mapping[str, str]) -> None:
        self.public_keys = {str(key): str(value) for key, value in public_keys.items()}

    def verify(self, manifest: UpdateManifest) -> None:
        encoded = self.public_keys.get(manifest.key_id)
        if not encoded:
            raise PlatformError(f"Unknown MuslimSim update signing key {manifest.key_id!r}")
        try:
            import base64
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError as exc:
            raise PlatformError(
                "Signed updates are disabled because the cryptography package is unavailable; "
                "MuslimSim will not fall back to unsigned updates"
            ) from exc
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
            key.verify(base64.b64decode(manifest.signature), manifest.signed_payload())
        except Exception as exc:
            raise PlatformError("MuslimSim update signature verification failed") from exc


class UpdateManager:
    def __init__(self, current_version: str, staging_directory: str | Path, verifier: UpdateVerifier) -> None:
        self.current_version = Version.parse(current_version)
        self.staging_directory = Path(staging_directory).expanduser().resolve()
        self.staging_directory.mkdir(parents=True, exist_ok=True)
        self.verifier = verifier

    def fetch_manifest(self, url: str, *, timeout: float = 15.0) -> UpdateManifest:
        if not str(url).startswith("https://"):
            raise ValidationError("Update manifest must use HTTPS")
        with urllib.request.urlopen(str(url), timeout=max(3.0, min(timeout, 60.0))) as response:
            data = json.loads(response.read().decode("utf-8"))
        manifest = UpdateManifest.from_mapping(data)
        self.verifier.verify(manifest)
        return manifest

    def available(self, manifest: UpdateManifest) -> bool:
        return Version.parse(manifest.version) > self.current_version

    def stage(self, manifest: UpdateManifest, *, timeout: float = 60.0) -> Path:
        self.verifier.verify(manifest)
        destination = self.staging_directory / f"MuslimSim-{manifest.version}.zip"
        temp = destination.with_suffix(destination.suffix + ".partial")
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(manifest.package_url, timeout=max(5.0, min(timeout, 300.0))) as response, temp.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    handle.write(chunk)
            if digest.hexdigest() != manifest.sha256:
                raise PlatformError("Downloaded MuslimSim package SHA-256 does not match the signed manifest")
            os.replace(temp, destination)
            return destination
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
