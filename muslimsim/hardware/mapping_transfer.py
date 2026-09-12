"""Move MSFS 2024 mappings between aircraft workspaces without merging them.

Each aircraft keeps its own profile file, so a mapping made for one airframe can
never appear in another by accident.  That isolation is the safety property and
it is not weakened here: this module only ever *copies*, and only in one
direction, into a workspace the caller names.

Two transfers are supported, and they are deliberately different:

* **Same catalogue family** - Fenix A320/A319/A321, the three FSLabs variants,
  the PMDG 737s.  These draw from the identical imported function library, so a
  binding's target provably exists on the other airframe and every mapping
  transfers verbatim.  This is the only case allowed to happen automatically,
  when a workspace is opened for the first time and has no profile yet.
* **Different family** - PMDG to Fenix, say.  There is no reliable equivalence
  between `laminar/B738/...`, `AirbusFBW/...` and a PMDG LVAR, so nothing is
  guessed.  A binding transfers only when its exact target is present in the
  destination aircraft's own library, and everything else is reported as
  skipped with a reason.  A button that looks mapped but fires the wrong
  command is worse than one that is not mapped at all.

X-Plane and MSFS workspaces are never transferred between.  The bridge already
refuses to dispatch a foreign-simulator binding; this refuses to write one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .msfs24_aircraft import msfs24_aircraft, msfs24_family
from .msfs24_library import all_msfs24_functions
from .profiles import HardwareProfileStore, MappingBinding, ProfileError


def _family_targets(family: Optional[str]) -> set[str]:
    """Every command/dataref target the given catalogue family provides."""

    if not family:
        return set()
    targets: set[str] = set()
    for entry in all_msfs24_functions():
        if str(entry.get("aircraft") or "") != family:
            continue
        target = str(entry.get("target") or "").strip()
        if target:
            targets.add(target)
    return targets


def _loaded_store(path: Path) -> HardwareProfileStore:
    store = HardwareProfileStore(Path(path))
    store.load()
    return store


def copy_msfs24_bindings(
    source_path: Path,
    target_path: Path,
    *,
    source_key: str,
    target_key: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy what transfers safely from one MSFS airframe workspace to another.

    Returns a report naming every mapping copied and every one skipped, with
    the reason.  Nothing is written when nothing could be copied.
    """

    source_air = msfs24_aircraft(source_key)
    target_air = msfs24_aircraft(target_key)
    if source_air is None or target_air is None:
        raise ProfileError("Both aircraft must be offered MSFS 2024 airframes")
    if source_air.key == target_air.key:
        raise ProfileError("Source and destination are the same aircraft")

    report: dict[str, Any] = {
        "source": source_air.title, "target": target_air.title,
        "same_family": source_air.family is not None and source_air.family == target_air.family,
        "copied": [], "skipped": [], "written": False,
    }

    if not Path(source_path).exists():
        report["skipped"].append({
            "control": "*", "reason": f"{source_air.title} has no saved mappings yet",
        })
        return report

    source = _loaded_store(Path(source_path))
    target = _loaded_store(Path(target_path))

    allowed = None if report["same_family"] else _family_targets(target_air.family)

    document = source.snapshot()
    active = str(document.get("active_profile") or "")
    raw_bindings = ((document.get("profiles") or {}).get(active) or {}).get("bindings")
    if not isinstance(raw_bindings, dict):
        raw_bindings = {}

    for compound, raw in sorted(raw_bindings.items()):
        if not isinstance(raw, dict):
            continue
        device_key, _, control_key = str(compound).partition(".")
        if not device_key or not control_key:
            continue
        binding = MappingBinding(**raw)

        if str(binding.kind) == "disabled":
            continue
        if str(binding.simulator or "xplane").casefold() != "msfs24":
            report["skipped"].append({
                "control": compound, "reason": "not an MSFS 2024 mapping",
            })
            continue
        if not overwrite and target.has_binding(device_key, control_key):
            report["skipped"].append({
                "control": compound, "reason": f"{target_air.title} already maps this control",
            })
            continue
        if allowed is not None and str(binding.target) not in allowed:
            report["skipped"].append({
                "control": compound,
                "reason": f"{binding.target} is not in the {target_air.brand} library",
            })
            continue
        try:
            target.set_binding(device_key, control_key, binding)
        except ProfileError as exc:
            report["skipped"].append({"control": compound, "reason": str(exc)})
            continue
        report["copied"].append({"control": compound, "target": str(binding.target)})

    if report["copied"]:
        target.save()
        report["written"] = True
    return report


def seed_msfs24_profile(
    target_path: Path,
    target_key: str,
    sibling_paths: dict[str, Path],
) -> Optional[dict[str, Any]]:
    """Give a brand-new workspace its family siblings' mappings, once.

    Called only when ``target_path`` does not exist yet, so this can never
    overwrite work.  After seeding the workspace is fully independent: editing
    the A321 never touches the A320 again.

    ``sibling_paths`` maps every other MSFS aircraft key to its profile path.
    Returns ``None`` when there was nothing to inherit.
    """

    target_path = Path(target_path)
    if target_path.exists():
        return None
    family = msfs24_family(target_key)
    if not family:
        return None

    candidates = [
        (path, key) for key, path in sibling_paths.items()
        if key != target_key and msfs24_family(key) == family and Path(path).exists()
    ]
    if not candidates:
        return None
    # Newest sibling wins: it is the one the owner has been working in.
    newest_path, newest_key = max(candidates, key=lambda item: Path(item[0]).stat().st_mtime)

    report = copy_msfs24_bindings(
        Path(newest_path), target_path,
        source_key=newest_key, target_key=target_key,
    )
    report["seeded"] = True
    return report


def describe_report(report: dict[str, Any]) -> str:
    """One readable line for the Studio footer."""

    copied = len(report.get("copied") or ())
    skipped = len(report.get("skipped") or ())
    source = report.get("source", "the other aircraft")
    target = report.get("target", "this aircraft")
    if not copied and not skipped:
        return f"{source} had no mappings to copy to {target}."
    if not copied:
        return f"Nothing transferred from {source} to {target}: {skipped} mapping(s) skipped."
    if report.get("same_family"):
        return (
            f"{copied} mapping(s) inherited from {source}. {target} now has its own "
            "independent copy; editing one no longer changes the other."
        )
    return (
        f"{copied} mapping(s) copied from {source} to {target}; {skipped} skipped "
        "because the function does not exist on this aircraft."
    )


__all__ = (
    "copy_msfs24_bindings", "describe_report", "seed_msfs24_profile",
)
