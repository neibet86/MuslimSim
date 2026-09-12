"""Temporary GET-only diagnostic watchdog for the native BLEED centre valve.

Records BOTH candidate outputs and switches; never drives the aircraft, opens
HID, restarts Studio or guesses a permanent mapping from a coincident edge.
Native-symbol observations are required before a candidate becomes a rule.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
NAMES=("AirbusFBW/XBleedInd", "AirbusFBW/APUBleedInd",
       "AirbusFBW/XBleedSwitch", "AirbusFBW/APUBleedSwitch", "AirbusFBW/SDBLEED")
INDICATORS=NAMES[:2]


def now():
    return datetime.now(timezone.utc).isoformat()


def get(url):
    with urllib.request.urlopen(url,timeout=3) as response:
        return json.load(response)


def classify(before,after):
    changes={name:{"before":before.get(name),"after":after.get(name)}
             for name in NAMES if before.get(name)!=after.get(name)}
    actual=[name for name in INDICATORS if name in changes]
    return {"changes":changes,"changed_indicators":actual,
            "isolated_candidate":actual[0] if len(actual)==1 else None,
            "mapping_verified":False,
            "reason":"Native centre-symbol orientation has not been observed."}


def run(api,out,duration,interval):
    out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log=out/(stamp+"_events.jsonl")
    status_file=out/"status.json"
    stop_file=out/"STOP"
    status={"pid":os.getpid(),"started_utc":now(),"read_only":True,
            "running":True,"log":str(log),"event_count":0,"sample_count":0,
            "provisional_source":"AirbusFBW/XBleedInd","mapping_verified":False,
            "sampling_interval_seconds":interval,"duration_seconds":duration,
            "error":None,"last_values":{}}
    def publish():
        temporary=out/(f"status_{os.getpid()}.tmp")
        temporary.write_text(json.dumps(status,indent=2),encoding="utf-8")
        os.replace(temporary,status_file)
    def event(data):
        with log.open("a",encoding="utf-8") as stream:
            stream.write(json.dumps({"utc":now(),**data},allow_nan=False)+"\n")
    ids={}
    previous=None
    start=time.monotonic()
    next_catalog=0.0
    next_publish=0.0
    publish()
    try:
        with ThreadPoolExecutor(max_workers=len(NAMES)) as pool:
            while time.monotonic()-start<duration and not stop_file.exists():
                tick=time.monotonic()
                try:
                    if not ids:
                        if tick<next_catalog:
                            time.sleep(min(1,max(0,next_catalog-tick)))
                            continue
                        next_catalog=tick+30
                        catalog=get(api+"/api/v2/datarefs")["data"]
                        ids={item["name"]:item["id"] for item in catalog if item["name"] in NAMES}
                        if set(ids)!=set(NAMES):
                            ids={}
                            raise RuntimeError("Required ToLiss BLEED outputs are not all published")
                    def fetch(name):
                        value=get(api+f"/api/v2/datarefs/{ids[name]}/value")["data"]
                        if not isinstance(value,(int,float)):
                            raise ValueError(name+" is not a scalar indication")
                        return name,value
                    current=dict(pool.map(fetch,NAMES))
                    status["sample_count"]+=1
                    status["last_seen_utc"]=now()
                    status["last_values"]=current
                    if previous is None:
                        event({"kind":"baseline","values":current,"mapping_verified":False})
                    else:
                        delta=classify(previous,current)
                        if delta["changes"]:
                            event({"kind":"change",**delta})
                            status["event_count"]+=1
                            status["last_event"]=delta
                            next_publish=0
                    previous=current
                    status["error"]=None
                except Exception as error:
                    message=f"{type(error).__name__}: {error}"
                    if message!=status["error"]:
                        event({"kind":"unavailable","error":message})
                        next_publish=0
                    status["error"]=message
                    status["last_values"]={}
                    ids={}
                    previous=None  # Reconnect cannot masquerade as a valve edge.
                if tick>=next_publish:
                    publish()
                    next_publish=tick+10
                time.sleep(max(0,interval-(time.monotonic()-tick)))
    finally:
        status.update(running=False,finished_utc=now())
        publish()
        event({"kind":"stopped","event_count":status["event_count"]})
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api",default="http://127.0.0.1:8086")
    parser.add_argument("--out",type=Path,default=ROOT/"diagnostics"/"bleed-watchdog")
    parser.add_argument("--duration",type=float,default=14400)
    parser.add_argument("--interval",type=float,default=.5)
    args=parser.parse_args()
    if args.duration<=0 or args.interval<.25:
        parser.error("Duration must be positive and interval at least 0.25 seconds")
    print(json.dumps(run(args.api.rstrip("/"),args.out,args.duration,args.interval),indent=2))


if __name__=="__main__":
    main()
