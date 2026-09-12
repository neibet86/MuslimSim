"""MuslimSim clean-PC runtime and Windows driver bootstrap.

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V3

This module is deliberately outside every cockpit protocol. It never decides
what a button does and never opens a cockpit device for normal operation.

It answers three deployment questions:

1. Did the MuslimSim executable bundle its own Python-side dependencies?
2. Does Windows currently expose a connected supported product through the
   transport class its existing MuslimSim owner expects?
3. If a reviewed signed local INF driver bundle is embedded in MuslimSim, can
   it be installed safely without MobiFlight, SPAD.next or a manufacturer
   cockpit application?

Product identity remains product/protocol. PnP instance IDs, COM numbers, HID
paths, SDL indices, GUIDs and unit serial numbers are locators/diagnostics only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .device_manager import (
    HIDEndpoint,
    SDLControllerEndpoint,
    SerialEndpoint,
    hid_endpoints,
    serial_endpoints,
    sdl_endpoints,
)
from .product_registry import PRODUCTS, ProductSpec
from .runtime_bundle import dependency_snapshot


@dataclass(frozen=True)
class PnpUSBDevice:
    vendor_id: int
    product_id: int
    instance_id: str
    friendly_name: str = ""
    class_name: str = ""
    status: str = ""
    problem_code: int = 0
    service: str = ""
    driver_provider: str = ""
    source: str = "windows-pnp"

    def searchable_text(self) -> str:
        return " ".join(
            (
                self.instance_id,
                self.friendly_name,
                self.class_name,
                self.status,
                self.service,
                self.driver_provider,
            )
        ).casefold()

    def snapshot(self) -> Dict[str, Any]:
        # A PnP instance ID is intentionally exposed only as a diagnostic
        # locator. It is not persisted as a MuslimSim product identity.
        return asdict(self)


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _usb_id(value: object) -> Tuple[int, int]:
    text = str(value or "")
    match = re.search(
        r"VID[_:=]([0-9A-F]{4}).*?PID[_:=]([0-9A-F]{4})",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return (0, 0)
    return (int(match.group(1), 16), int(match.group(2), 16))


def _powershell_json(script: str, *, timeout: float = 5.0) -> Any:
    if os.name != "nt":
        return None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=float(timeout),
            check=False,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def windows_pnp_usb_devices(
    inventory: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Tuple[PnpUSBDevice, ...]:
    """Enumerate present USB/PnP devices without opening any cockpit handle."""
    if inventory is None:
        raw = _powershell_json(
            r"""
$items = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -match 'VID_[0-9A-Fa-f]{4}.*PID_[0-9A-Fa-f]{4}' } |
    ForEach-Object {
        $problem = 0
        $service = ''
        $provider = ''
        try {
            $problem = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_ProblemCode' -ErrorAction Stop).Data
        } catch {}
        try {
            $service = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_Service' -ErrorAction Stop).Data
        } catch {}
        try {
            $provider = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_DriverProvider' -ErrorAction Stop).Data
        } catch {}
        [PSCustomObject]@{
            InstanceId = $_.InstanceId
            FriendlyName = $_.FriendlyName
            Class = $_.Class
            Status = $_.Status
            ProblemCode = $problem
            Service = $service
            DriverProvider = $provider
        }
    }
$items | ConvertTo-Json -Compress
"""
        )
        if raw is None:
            rows: Sequence[Mapping[str, Any]] = ()
        elif isinstance(raw, list):
            rows = tuple(item for item in raw if isinstance(item, Mapping))
        elif isinstance(raw, Mapping):
            rows = (raw,)
        else:
            rows = ()
    else:
        rows = tuple(item for item in inventory if isinstance(item, Mapping))

    result: List[PnpUSBDevice] = []
    for row in rows:
        instance_id = str(row.get("InstanceId") or row.get("instance_id") or "")
        vid, pid = _usb_id(instance_id)
        if not vid or not pid:
            vid = _int(row.get("vendor_id"))
            pid = _int(row.get("product_id"))
        if not vid or not pid:
            continue
        result.append(
            PnpUSBDevice(
                vendor_id=vid,
                product_id=pid,
                instance_id=instance_id,
                friendly_name=str(
                    row.get("FriendlyName") or row.get("friendly_name") or ""
                ),
                class_name=str(row.get("Class") or row.get("class_name") or ""),
                status=str(row.get("Status") or row.get("status") or ""),
                problem_code=_int(
                    row.get("ProblemCode")
                    if "ProblemCode" in row
                    else row.get("problem_code")
                ),
                service=str(row.get("Service") or row.get("service") or ""),
                driver_provider=str(
                    row.get("DriverProvider")
                    or row.get("driver_provider")
                    or ""
                ),
            )
        )
    return tuple(result)


def _resource_root(project_root: object = None) -> Path:
    if project_root is not None:
        return Path(project_root)
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parents[2]


def driver_manifest_path(project_root: object = None) -> Path:
    return _resource_root(project_root) / "muslimsim" / "hardware" / "driver_bundles.json"


def load_driver_manifest(project_root: object = None) -> Dict[str, Any]:
    path = driver_manifest_path(project_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "schema": 0,
            "policy": "",
            "families": {},
            "packages": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(raw, Mapping):
        return {
            "schema": 0,
            "policy": "",
            "families": {},
            "packages": [],
            "error": "manifest root is not an object",
        }
    packages = raw.get("packages")
    families = raw.get("families")
    return {
        "schema": _int(raw.get("schema")),
        "policy": str(raw.get("policy") or ""),
        "families": dict(families) if isinstance(families, Mapping) else {},
        "packages": list(packages) if isinstance(packages, list) else [],
        "error": "",
    }


def _pnp_matches(spec: ProductSpec, row: PnpUSBDevice) -> bool:
    if (row.vendor_id, row.product_id) in spec.usb_ids:
        return True
    return spec.matches_text(row.friendly_name, row.instance_id)


def _serial_matches(spec: ProductSpec, row: SerialEndpoint) -> bool:
    if (row.vendor_id, row.product_id) in spec.usb_ids:
        return True
    return spec.matches_text(
        row.description, row.manufacturer, row.product, row.hwid, row.pnp_id
    )


def _hid_matches(spec: ProductSpec, row: HIDEndpoint) -> bool:
    if (row.vendor_id, row.product_id) in spec.usb_ids:
        return True
    return spec.matches_text(row.product, row.manufacturer)


def _sdl_matches(spec: ProductSpec, row: SDLControllerEndpoint) -> bool:
    return spec.matches_text(row.name)


def _native_family(family: str) -> bool:
    return family in {
        "windows-native",
        "windows-hid",
        "windows-game",
        "windows-hid-game",
    }


def _package_usb_ids(package: Mapping[str, Any]) -> Tuple[Tuple[int, int], ...]:
    result = []
    for item in package.get("usb_ids", ()) if isinstance(package, Mapping) else ():
        text = str(item or "").strip()
        match = re.fullmatch(r"([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})", text)
        if match:
            result.append((int(match.group(1), 16), int(match.group(2), 16)))
    return tuple(result)


def _available_driver_packages(
    spec: ProductSpec,
    manifest: Mapping[str, Any],
    *,
    project_root: object = None,
) -> List[Dict[str, Any]]:
    root = _resource_root(project_root)
    result = []
    for raw in manifest.get("packages", ()) if isinstance(manifest, Mapping) else ():
        if not isinstance(raw, Mapping):
            continue
        family = str(raw.get("family") or "")
        usb_ids = _package_usb_ids(raw)
        if family != spec.driver_family and not any(
            identity in spec.usb_ids for identity in usb_ids
        ):
            continue
        inf_relative = str(raw.get("inf") or "").replace("\\", "/").lstrip("/")
        inf_path = (root / inf_relative).resolve() if inf_relative else None
        available = bool(inf_path and inf_path.is_file())
        result.append(
            {
                "key": str(raw.get("key") or ""),
                "family": family,
                "inf": inf_relative,
                "sha256": str(raw.get("sha256") or "").lower(),
                "allowed_signers": [
                    str(item)
                    for item in raw.get("allowed_signers", ())
                    if str(item).strip()
                ],
                "available": available,
            }
        )
    return result


def clean_pc_readiness(
    project_root: object = None,
    *,
    include_sdl: bool = False,
    pnp_inventory: Optional[Sequence[Mapping[str, Any]]] = None,
    serial_inventory: Optional[Sequence[SerialEndpoint]] = None,
    hid_inventory: Optional[Sequence[HIDEndpoint]] = None,
    sdl_inventory: Optional[Sequence[SDLControllerEndpoint]] = None,
    runtime_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a read-only clean-PC deployment report.

    `include_sdl=False` is deliberate for Studio/background use because the
    bridge already owns SDL. A diagnostic run with Studio closed may set True.
    """
    runtime = (
        dict(runtime_snapshot)
        if runtime_snapshot is not None
        else dependency_snapshot(project_root)
    )
    pnp = windows_pnp_usb_devices(pnp_inventory)
    serial_rows = (
        tuple(serial_inventory)
        if serial_inventory is not None
        else serial_endpoints()
    )
    hid_rows = (
        tuple(hid_inventory)
        if hid_inventory is not None
        else hid_endpoints()
    )
    sdl_rows = (
        tuple(sdl_inventory)
        if sdl_inventory is not None
        else (sdl_endpoints() if include_sdl else ())
    )
    manifest = load_driver_manifest(project_root)

    products = []
    driver_issues = []
    for spec in PRODUCTS:
        pnp_matches = [row for row in pnp if _pnp_matches(spec, row)]
        serial_matches = [
            row for row in serial_rows if "serial" in spec.transports and _serial_matches(spec, row)
        ]
        hid_matches = [
            row for row in hid_rows if "hid" in spec.transports and _hid_matches(spec, row)
        ]
        sdl_matches = [
            row for row in sdl_rows
            if {"sdl", "usb-gaming"}.intersection(spec.transports)
            and _sdl_matches(spec, row)
        ]

        connected = bool(pnp_matches or serial_matches or hid_matches or sdl_matches)
        pnp_problem = any(
            (row.problem_code not in {0}) or (
                row.status and row.status.casefold() not in {"ok", "started"}
            )
            for row in pnp_matches
        )

        expected_transport_ready = True
        reason = "not connected"
        if connected:
            family = spec.driver_family
            if family in {"wch-ch34x", "pu-composite"} and "serial" in spec.transports:
                expected_transport_ready = bool(serial_matches)
                reason = (
                    "serial endpoint available"
                    if expected_transport_ready
                    else "USB product present but no matching COM endpoint"
                )
            elif family == "windows-hid":
                expected_transport_ready = bool(hid_matches)
                reason = (
                    "HID interface available"
                    if expected_transport_ready
                    else "USB product present but no matching HID interface"
                )
            elif family == "windows-hid-game":
                expected_transport_ready = bool(hid_matches) or (
                    bool(sdl_matches) if include_sdl else bool(pnp_matches)
                )
                reason = (
                    "Windows HID/game interface available"
                    if expected_transport_ready
                    else "USB product present but expected HID/game interface is unavailable"
                )
            elif family == "windows-game":
                expected_transport_ready = (
                    bool(sdl_matches) if include_sdl else bool(pnp_matches)
                )
                reason = (
                    "Windows game-controller device present"
                    if expected_transport_ready
                    else "game-controller interface unavailable"
                )
            else:
                expected_transport_ready = bool(
                    serial_matches or hid_matches or sdl_matches or pnp_matches
                )
                reason = "Windows device present"

            if pnp_problem:
                expected_transport_ready = False
                reason = "Windows PnP reports a device/driver problem"

        packages = _available_driver_packages(
            spec, manifest, project_root=project_root
        )
        auto_installable = any(item["available"] for item in packages)

        row = {
            "key": spec.key,
            "title": spec.title,
            "driver_family": spec.driver_family,
            "connected": connected,
            "driver_ready": bool(expected_transport_ready),
            "reason": reason,
            "auto_installable": bool(auto_installable),
            "serial_ports": [item.port for item in serial_matches],
            "hid_interfaces": len(hid_matches),
            "sdl_instances": [item.instance_id for item in sdl_matches],
            "pnp": [item.snapshot() for item in pnp_matches],
            "bundled_driver_packages": packages,
        }
        products.append(row)
        if connected and not expected_transport_ready:
            driver_issues.append(
                {
                    "key": spec.key,
                    "title": spec.title,
                    "driver_family": spec.driver_family,
                    "reason": reason,
                    "auto_installable": bool(auto_installable),
                }
            )

    runtime_ready = bool(runtime.get("ready", False))
    return {
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
        "policy": {
            "python_dependencies": "bundled in MuslimSim.exe; no end-user pip",
            "cockpit_software": "not required",
            "driver_install": (
                "local signed INF bundles only; SHA-256 + Authenticode checked; "
                "no network download and no unsigned driver"
            ),
            "identity": (
                "product/protocol only; serial number, COM, HID path, SDL "
                "index/GUID and PnP instance ID are runtime locators"
            ),
        },
        "runtime": runtime,
        "driver_manifest": {
            "schema": manifest.get("schema", 0),
            "error": manifest.get("error", ""),
            "package_count": len(manifest.get("packages", ())),
        },
        "products": products,
        "driver_issues": driver_issues,
        "ready": runtime_ready and not driver_issues,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _authenticode_signature(path: Path) -> Dict[str, str]:
    if os.name != "nt":
        return {"status": "unsupported-platform", "subject": ""}
    escaped = str(path).replace("'", "''")
    raw = _powershell_json(
        f"""
$sig = Get-AuthenticodeSignature -LiteralPath '{escaped}'
[PSCustomObject]@{{
    Status = [string]$sig.Status
    Subject = if ($sig.SignerCertificate) {{ [string]$sig.SignerCertificate.Subject }} else {{ '' }}
}} | ConvertTo-Json -Compress
"""
    )
    if not isinstance(raw, Mapping):
        return {"status": "unavailable", "subject": ""}
    return {
        "status": str(raw.get("Status") or ""),
        "subject": str(raw.get("Subject") or ""),
    }


def _is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def validate_local_driver_package(
    package: Mapping[str, Any],
    *,
    project_root: object = None,
) -> Dict[str, Any]:
    """Validate hash and Authenticode before any pnputil invocation."""
    root = _resource_root(project_root).resolve()
    inf_relative = str(package.get("inf") or "").replace("\\", "/").lstrip("/")
    if not inf_relative:
        return {"ok": False, "reason": "manifest package has no INF path"}
    inf = (root / inf_relative).resolve()
    try:
        inf.relative_to(root)
    except ValueError:
        return {"ok": False, "reason": "INF path escapes MuslimSim resources"}
    if inf.suffix.casefold() != ".inf" or not inf.is_file():
        return {"ok": False, "reason": "INF file is not present"}

    expected = str(package.get("sha256") or "").strip().lower()
    actual = _sha256_file(inf)
    if not expected or expected != actual:
        return {
            "ok": False,
            "reason": "INF SHA-256 does not match the reviewed manifest",
            "actual_sha256": actual,
        }

    signature = _authenticode_signature(inf)
    status = signature["status"].casefold()
    if status != "valid":
        return {
            "ok": False,
            "reason": f"Authenticode signature is not valid: {signature['status']}",
            "signer": signature["subject"],
        }

    allowed = [
        str(item).casefold()
        for item in package.get("allowed_signers", ())
        if str(item).strip()
    ]
    subject = signature["subject"]
    if allowed and not any(token in subject.casefold() for token in allowed):
        return {
            "ok": False,
            "reason": "driver signer is not in the reviewed allow-list",
            "signer": subject,
        }

    return {
        "ok": True,
        "reason": "reviewed local signed INF is valid",
        "inf": str(inf),
        "sha256": actual,
        "signer": subject,
    }


def install_missing_signed_drivers(
    project_root: object = None,
    *,
    readiness: Optional[Mapping[str, Any]] = None,
    runner: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Install only reviewed local signed INF bundles needed by detected products.

    There is intentionally no web download, no manufacturer application
    install, no arbitrary executable launch and no unsigned-driver override.
    """
    report = (
        dict(readiness)
        if readiness is not None
        else clean_pc_readiness(project_root, include_sdl=False)
    )
    manifest = load_driver_manifest(project_root)
    packages = [
        item for item in manifest.get("packages", ())
        if isinstance(item, Mapping)
    ]
    issues = [
        item for item in report.get("driver_issues", ())
        if isinstance(item, Mapping)
    ]

    if not issues:
        return {
            "ok": True,
            "changed": False,
            "results": [],
            "message": "No connected supported product needs a driver repair.",
        }
    if os.name != "nt":
        return {
            "ok": False,
            "changed": False,
            "results": [],
            "message": "Windows driver installation is available only on Windows.",
        }
    if not _is_admin():
        return {
            "ok": False,
            "changed": False,
            "results": [],
            "message": "Administrator rights are required for driver installation.",
        }

    run = runner or subprocess.run
    results = []
    changed = False
    for issue in issues:
        family = str(issue.get("driver_family") or "")
        candidates = [
            package for package in packages
            if str(package.get("family") or "") == family
        ]
        if not candidates:
            results.append(
                {
                    "key": issue.get("key"),
                    "ok": False,
                    "changed": False,
                    "message": (
                        "No reviewed signed driver bundle is embedded for "
                        f"{family}."
                    ),
                }
            )
            continue

        installed = False
        for package in candidates:
            validation = validate_local_driver_package(
                package, project_root=project_root
            )
            if not validation.get("ok"):
                results.append(
                    {
                        "key": issue.get("key"),
                        "ok": False,
                        "changed": False,
                        "message": validation.get("reason"),
                    }
                )
                continue

            command = [
                "pnputil.exe",
                "/add-driver",
                str(validation["inf"]),
                "/install",
            ]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                completed = run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                    creationflags=creationflags,
                )
                returncode = int(getattr(completed, "returncode", 1))
                stdout = str(getattr(completed, "stdout", "") or "")
                stderr = str(getattr(completed, "stderr", "") or "")
            except Exception as exc:
                results.append(
                    {
                        "key": issue.get("key"),
                        "ok": False,
                        "changed": False,
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            ok = returncode == 0
            results.append(
                {
                    "key": issue.get("key"),
                    "ok": ok,
                    "changed": ok,
                    "message": stdout.strip() or stderr.strip() or f"pnputil exit {returncode}",
                }
            )
            if ok:
                changed = True
                installed = True
                break
        if not installed:
            continue

    return {
        "ok": all(bool(item.get("ok")) for item in results) if results else False,
        "changed": changed,
        "results": results,
        "message": (
            "Reviewed signed driver installation completed."
            if changed
            else "No driver package was installed."
        ),
    }


def format_readiness(report: Mapping[str, Any]) -> str:
    lines = []
    lines.append("MuslimSim clean-PC readiness")
    lines.append("=" * 72)
    runtime = report.get("runtime", {})
    lines.append(
        "Bundled Python/runtime dependencies: "
        + ("READY" if runtime.get("ready") else "MISSING")
    )
    modules = runtime.get("modules", ())
    for item in modules if isinstance(modules, (list, tuple)) else ():
        if isinstance(item, Mapping):
            lines.append(
                f"  {'OK' if item.get('available') else 'MISSING':7} "
                f"{item.get('module')}: {item.get('purpose')}"
            )
    lines.append("")
    lines.append("Detected supported products / Windows driver state")
    lines.append("-" * 72)
    any_connected = False
    for item in report.get("products", ()):
        if not isinstance(item, Mapping) or not item.get("connected"):
            continue
        any_connected = True
        state = "READY" if item.get("driver_ready") else "DRIVER ISSUE"
        install = "signed bundle available" if item.get("auto_installable") else "no embedded repair bundle"
        lines.append(
            f"  {state:12} {item.get('title')} [{item.get('driver_family')}]"
        )
        lines.append(f"               {item.get('reason')} | {install}")
    if not any_connected:
        lines.append("  No supported connected product was detected.")
    lines.append("")
    lines.append(
        "Overall: "
        + ("READY" if report.get("ready") else "ATTENTION REQUIRED")
    )
    lines.append(
        "Policy: no end-user pip, no MobiFlight/SPAD/manufacturer cockpit app; "
        "only reviewed local signed Windows INF drivers may be installed."
    )
    return "\n".join(lines)


__all__ = [
    "PnpUSBDevice",
    "windows_pnp_usb_devices",
    "driver_manifest_path",
    "load_driver_manifest",
    "clean_pc_readiness",
    "validate_local_driver_package",
    "install_missing_signed_drivers",
    "format_readiness",
]

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V3_BOOTSTRAP = True
