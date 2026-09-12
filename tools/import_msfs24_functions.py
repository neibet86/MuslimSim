#!/usr/bin/env python3
"""Import owner-supplied MSFS 2024 command sources into the Studio catalogue.

Reads the archives the owner dropped into the project and folds every usable
entry into ``muslimsim/hardware/msfs24_command_catalog.json``.  Nothing is
invented: an entry appears only where a source file actually documents it, and
every entry records which file it came from.

Sources understood:

* **Rowsfire MobiFlight ``.mcc``** - MobiFlight Connector XML.  Each ``<config>``
  is a labelled control whose ``<onPress>``/``<onRelease>`` carry executable
  MSFS RPN calculator code.  This is the large one, and the only source that
  gives FlyByWire anything at all.
* **SPAD.neXt profile XML** - Honeycomb bindings whose ``TargetDataDefinition``
  names a real ``SIMCONNECT:`` event or ``LVAR:``.
* **MobiFlight ``.mfproj``** - the newer JSON project format, read from any
  file sitting loose in the project folder.  Input items carry the same RPN
  actions; output items name the LVAR that drives a lamp.
* **Stream Deck ``.lua``** - the ``A32NX_*`` LVARs a script reads.

The iFly YourControls YAML is deliberately not imported here; its command half
is CDU-only and needs its own trigger-number model.

Run with no arguments for a dry run:

    py tools/import_msfs24_functions.py
    py tools/import_msfs24_functions.py --apply
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

CATALOGUE = PROJECT / "muslimsim" / "hardware" / "msfs24_command_catalog.json"

# Family names come from the aircraft module so the importer and the selector
# can never disagree about how a family is spelled.
from muslimsim.hardware.msfs24_aircraft import (  # noqa: E402
    FAMILY_FBW_A32NX as FAMILY_FBW,
    FAMILY_FENIX,
    FAMILY_FSLABS,
    FAMILY_IFLY_MAX8,
    FAMILY_INIBUILDS_A350,
    FAMILY_PMDG_737,
    FAMILY_PMDG_777,
)

# Filename fragments to catalogue family. Order matters: the first hit wins, so
# the more specific patterns are listed first.
_FAMILY_PATTERNS = (
    ("ifly", FAMILY_IFLY_MAX8),
    ("b38m", FAMILY_IFLY_MAX8),
    ("737max", FAMILY_IFLY_MAX8),
    ("inibuilds", FAMILY_INIBUILDS_A350),
    ("inia350", FAMILY_INIBUILDS_A350),
    ("a350", FAMILY_INIBUILDS_A350),
    ("fslabs", FAMILY_FSLABS),
    ("fslab", FAMILY_FSLABS),
    # Both spellings appear in the owner's files: "PMDG-777" and "PMDG777".
    ("pmdg-738", FAMILY_PMDG_737),
    ("pmdg738", FAMILY_PMDG_737),
    ("pmdg-737", FAMILY_PMDG_737),
    ("pmdg737", FAMILY_PMDG_737),
    ("pmdg-777", FAMILY_PMDG_777),
    ("pmdg777", FAMILY_PMDG_777),
    ("fenix", FAMILY_FENIX),
    ("fbw", FAMILY_FBW),
    ("flybywire", FAMILY_FBW),
    ("a32nx", FAMILY_FBW),
)

# Aircraft present in the sources but not offered by Studio yet. Importing them
# would leave functions no workspace can reach, so they are reported instead.
_UNOFFERED: tuple[str, ...] = ()


def _family_for(name: str):
    lowered = name.casefold()
    for fragment in _UNOFFERED:
        if fragment in lowered:
            return None, "aircraft not offered by Studio"
    for fragment, family in _FAMILY_PATTERNS:
        if fragment in lowered:
            return family, ""
    return None, "aircraft could not be identified from the filename"


def _panel_of(name: str) -> str:
    """The Rowsfire product a config came from, used as its category."""

    stem = Path(name).stem
    stem = re.sub(r"\.mcc$", "", stem, flags=re.I)
    parts = re.split(r"[-_]", stem)
    tail = [p.strip() for p in parts if p.strip()]
    return tail[-1] if tail else stem


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _mcc_entries(name: str, text: str):
    """Labelled controls with executable RPN from one MobiFlight config."""

    family, why = _family_for(name)
    panel = _panel_of(name)
    found = []
    for block in re.findall(r"<config guid=.*?</config>", text, re.S):
        label = re.search(r"<description>(.*?)</description>", block, re.S)
        label = _clean(label.group(1)) if label else ""
        settings = re.search(r'<settings[^>]*name="([^"]*)"', block)
        if not label and settings:
            label = _clean(settings.group(1))
        for action, command in re.findall(r'<on(\w+) type="[^"]*" command="([^"]*)"', block):
            code = _clean(
                command.replace("&#xA;", " ").replace("&gt;", ">")
                .replace("&lt;", "<").replace("&amp;", "&").replace("&quot;", '"')
            )
            if not code:
                continue
            found.append({
                "family": family, "skip_reason": why,
                "label": f"{label} ({action})" if label else code[:60],
                "category": panel,
                "target": code,
                "kind": "command",
                "protocol": "rpn",
                "source": name,
            })
    return found


def _walk_actions(node, found):
    """Collect every MSFS custom-input action anywhere inside a config item.

    MobiFlight nests actions differently per device - ``inputMultiplexer``,
    ``button``, ``inputEncoder`` and so on - so the item is walked rather than
    assuming one shape.  A future device type is picked up without a change
    here.
    """

    if isinstance(node, dict):
        action = str(node.get("Type") or "")
        command = node.get("Command")
        if action.startswith("MSFS2020") and isinstance(command, str) and command.strip():
            found.append(command.strip())
        for key, value in node.items():
            if key in {"Type", "Command"}:
                continue
            _walk_actions(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_actions(value, found)
    return found


def _mfproj_entries(name: str, text: str):
    """Labelled controls from a MobiFlight JSON project (.mfproj)."""

    family, why = _family_for(name)
    panel = _panel_of(name)
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return []

    found = []
    for config in document.get("ConfigFiles") or ():
        for item in config.get("ConfigItems") or ():
            label = _clean(item.get("Name") or "")
            for command in _walk_actions(item, []):
                found.append({
                    "family": family, "skip_reason": why,
                    "label": f"{label} ({command.split()[0]})" if label else command[:60],
                    "category": panel,
                    "target": _clean(command),
                    "kind": "command", "protocol": "rpn", "source": name,
                })
            source = item.get("Source") or {}
            value = ((source.get("SimConnectValue") or {}).get("Value") or "").strip()
            if value:
                found.append({
                    "family": family, "skip_reason": why,
                    "label": label or value[:60],
                    "category": panel,
                    "target": value,
                    "kind": "dataref", "protocol": "lvar", "source": name,
                })
    return found


def _spad_entries(name: str, text: str):
    """SimConnect events and LVARs a SPAD.neXt profile binds."""

    found = []
    for target in sorted(set(re.findall(r'TargetDataDefinition="([^"]+)"', text))):
        if target.startswith("SIMCONNECT:"):
            kind, protocol, value = "command", "simconnect", target.split(":", 1)[1]
        elif target.startswith("LVAR:"):
            kind, protocol, value = "dataref", "lvar", "L:" + target.split(":", 1)[1]
        else:
            continue
        found.append({
            "family": FAMILY_FBW, "skip_reason": "",
            "label": value.replace("_", " ").title(),
            "category": "Honeycomb Alpha/Bravo profile",
            "target": value, "kind": kind, "protocol": protocol, "source": name,
        })
    return found


def _lua_entries(name: str, text: str):
    """A32NX LVARs a Stream Deck script reads."""

    found = []
    for var in sorted(set(re.findall(r"L:(A32NX_[A-Za-z0-9_]+)", text))):
        found.append({
            "family": FAMILY_FBW, "skip_reason": "",
            "label": var.replace("_", " ").title(),
            "category": "Stream Deck A320 script",
            "target": "L:" + var, "kind": "dataref", "protocol": "lvar",
            "source": name,
        })
    return found


def collect(root: Path):
    """Every candidate entry from the archives sitting in the project folder."""

    candidates = []
    archives = {
        "Rowsfire-MobiFlightConnector-main.zip": (".mcc", _mcc_entries),
        "FBW A32NX Honeycomb Alpha Bravo_gOGwS.zip": (".xml", _spad_entries),
        "FlyByWire A32NX v0.8_wa6gv.zip": (".lua", _lua_entries),
    }
    # MobiFlight projects the owner drops in loose, not inside an archive.
    for loose in sorted(root.glob("*.mfproj")):
        candidates.extend(
            _mfproj_entries(loose.name, loose.read_text(encoding="utf-8-sig", errors="replace"))
        )

    missing = []
    for archive, (suffix, parser) in archives.items():
        path = root / archive
        if not path.exists():
            missing.append(archive)
            continue
        with zipfile.ZipFile(path) as bundle:
            for info in bundle.infolist():
                if not info.filename.lower().endswith(suffix):
                    continue
                text = bundle.read(info).decode("utf-8-sig", errors="replace")
                candidates.extend(parser(Path(info.filename).name, text))
    return candidates, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the catalogue")
    parser.add_argument("--root", default=str(PROJECT), help="folder holding the archives")
    args = parser.parse_args()

    candidates, missing = collect(Path(args.root))
    for name in missing:
        print(f"  missing archive, skipped: {name}")

    document = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    functions = list(document.get("functions") or ())
    existing = {(str(f.get("aircraft") or ""), str(f.get("target") or "")) for f in functions}

    added, skipped = [], collections.Counter()
    seen = set()
    for item in candidates:
        family = item["family"]
        if not family:
            skipped[item["skip_reason"] or "unidentified"] += 1
            continue
        key = (family, item["target"])
        if key in existing or key in seen:
            skipped["already in the catalogue"] += 1
            continue
        seen.add(key)
        added.append({
            "id": "msfs24:import:%d" % (len(existing) + len(added) + 1),
            "kind": item["kind"],
            "protocol": item["protocol"],
            "target": item["target"],
            "label": item["label"],
            "category": f"{family} • {item['category']}",
            "aircraft": family,
            "description": f"Imported from {item['source']}",
            "raw_type": item["protocol"],
            "source": item["source"],
            "source_url": "",
        })

    per_family = collections.Counter(entry["aircraft"] for entry in added)
    print("\nWould add %d entries:" % len(added) if not args.apply else "\nAdding %d entries:" % len(added))
    for family, count in sorted(per_family.items()):
        before = sum(1 for f in functions if str(f.get("aircraft") or "") == family)
        print(f"   {family:<26} {before:>5} -> {before + count}")
    if skipped:
        print("\nSkipped:")
        for reason, count in skipped.most_common():
            print(f"   {count:>5}  {reason}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write the catalogue.")
        return 0
    if not added:
        print("\nNothing new to write.")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = PROJECT / "Backup" / f"msfs24_command_catalog_before_import_{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CATALOGUE, backup)

    document["functions"] = functions + added
    sources = document.get("source") or ""
    document["source"] = f"{sources}; Rowsfire MobiFlight, SPAD.neXt and Stream Deck imports {stamp}"
    CATALOGUE.write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8",
    )
    print(f"\nBackup: {backup.name}")
    print(f"Catalogue now holds {len(document['functions'])} functions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
