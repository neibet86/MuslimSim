"""One-shot, GET-only ECAM telemetry audit. Never commands aircraft/hardware.

Captures published values and their actual API types, not a screenshot fixture.
Use --label to record the aircraft state YOU established in X-Plane. The label
is not an assertion that the tool independently verified that flight phase.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import base64
import json
import re
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from muslimsim.devices.mcdu_bb36_toliss_paths import TOLISS_MCDU_SECONDARY_DATAREFS
MIRROR_REFS = frozenset(name for group in TOLISS_MCDU_SECONDARY_DATAREFS.values() for name in group.values())
LEAVES=re.compile(r"^(SD|DU|ECAM|FCC|ADR|IR[SU]|FADEC|ENG|APU|Hyd|Fuel|Bat|Elec|Bus|Write|Gross|Pack|CockpitTemp|Cabin|Zone|CockpitTrim|Fwd|Aft|Bulk|HotAir|Cargo|PaxDoor|EmerExit|Slide|CockpitWindow|Outflow|Safety|LandElev|Vent|RamAirValve|[LR].*Bleed|XBleed|Bleed|Tire|Brake|.*Gear|NWS|Altn|AutoBrk|PitchTrim|Rudder|SDSpoiler|SpoilerPosition|TotalWeight|AircraftType|EngineType|TimeSince)")


def get(url):
    with urllib.request.urlopen(url,timeout=8) as response:
        return json.load(response)


def capture(api):
    catalog=get(api+"/api/v2/datarefs")["data"]
    selected=[entry for entry in catalog if (
        entry["name"] in MIRROR_REFS
        or
        entry["name"].startswith("AirbusFBW/") and LEAVES.search(entry["name"].split("/",1)[1])
        or entry["name"].startswith(("sim/cockpit2/electrical/","sim/cockpit2/engine/indicators/","sim/cockpit2/fuel/","sim/cockpit2/oxygen/indicators/"))
        or entry["name"] in ("sim/aircraft/view/acf_relative_path","sim/aircraft/view/acf_ICAO","sim/flightmodel/weight/m_fuel","sim/flightmodel/weight/m_total","sim/flightmodel/failures/onground_any","sim/cockpit2/gauges/indicators/TAT_pilot","sim/cockpit2/gauges/indicators/SAT_pilot"))]
    def fetch(entry):
        result=dict(entry)
        try:
            value=get(api+f"/api/v2/datarefs/{entry['id']}/value")["data"]
            if entry.get("value_type")=="data" and isinstance(value,str):
                value=base64.b64decode(value).decode("utf-8",errors="replace").rstrip("\0")
            result["value"]=value
        except Exception as error:
            result["error"]=str(error)
        return entry["name"],result
    with ThreadPoolExecutor(max_workers=6) as pool:
        values=dict(pool.map(fetch,selected))
    return {"captured_utc":datetime.now(timezone.utc).isoformat(),
            "capabilities":get(api+"/api/capabilities"),"read_only":True,
            "catalog":catalog,"values":values}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api",default="http://127.0.0.1:8086")
    parser.add_argument("--label",default="observed")
    args=parser.parse_args()
    data=capture(args.api.rstrip("/"))
    data["operator_label"]=args.label
    output=ROOT/"diagnostics"/"toliss-ecam"
    output.mkdir(parents=True,exist_ok=True)
    label=re.sub(r"[^A-Za-z0-9_-]","_",args.label)
    file=output/(datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+label+".json")
    file.write_text(json.dumps(data,indent=2,allow_nan=False),encoding="utf-8")
    print(file)
    print(f"GET-only: {len(data['values'])} actual values; no commands, subscriptions or hardware opened.")


if __name__=="__main__":
    main()
