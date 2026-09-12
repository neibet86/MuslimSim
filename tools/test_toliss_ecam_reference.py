"""BUG-40 offline reference-layout and data-honesty guards; no hardware."""
from pathlib import Path
import math
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_ecam_synoptics as art
from muslimsim.devices import systems_renderer_toliss as systems
from muslimsim.devices.pfp_renderer import _OpRecorder


class Capture(systems._BoundsCanvas):
    def __init__(self):
        self.labels=[]
        self.features=set()

    def text(self,x,y,value,fg,bg,font):
        super().text(x,y,value,fg,bg,font)
        self.labels.append((value,fg))

    def record_feature(self,name):
        self.features.add(name)


def check_reference_layouts():
    expected={"eng","bleed","press","cond","elec","hyd","fuel","door","wheel","apu","fctl","status"}
    assert set(art.HANDLERS)==expected
    systems.assert_layout_contract()
    for page in expected:
        capture=Capture()
        systems.draw_toliss_system_frame(capture,page,{})
        assert {"REFERENCE_"+page.upper(),"ECAM_THREE_COLUMN_FOOTER"}<=capture.features
        assert {"TAT","SAT","ISA","GW","KG"}<={t for t,_ in capture.labels}
        assert any(t=="XX" and colour==art.AMBER for t,colour in capture.labels)
        assert ("NORMAL",art.GREEN) not in capture.labels
    capture=Capture()
    systems.draw_toliss_system_frame(capture,"status",{"status_master_warn":0,"status_master_caut":0})
    assert ("NORMAL",art.GREEN) not in capture.labels, "Acknowledging a caution cannot establish normal STATUS"
    capture=Capture()
    systems.draw_toliss_system_frame(capture,"status",{"status_normal":True})
    assert ("NORMAL",art.GREEN) in capture.labels
    # Real surface output, not the control input, must move each symbol.
    for key in [f"fctl_spoiler_{i}" for i in range(1,11)]+[
        "fctl_aileron_l","fctl_aileron_r","fctl_elevator_l","fctl_elevator_r","fctl_rudder"]:
        a,b=_OpRecorder(),_OpRecorder()
        systems.draw_toliss_system_frame(a,"fctl",{key:0})
        systems.draw_toliss_system_frame(b,"fctl",{key:.8})
        assert a.ops!=b.ops,key
    # Feed adapter neither invents absent readings nor mixes engineering units.
    def element(raw,key,index=0):
        value=raw.get(key,math.nan)
        return value[index] if isinstance(value,list) and index<len(value) else value
    fuel=art.reference_values("fuel",{"ref_fuel_flow_kg_sec":[.3,.4]},element)
    assert fuel["fuel_flow_kg_min_0"]==18 and fuel["fuel_flow_kg_min_1"]==24
    wheel=art.reference_values("wheel",{"fctl_spoiler_7":.42},element)
    assert wheel["wheel_spoiler_7"]==.42 and math.isnan(wheel["wheel_spoiler_1"])
    # BUG-44: empty native ToLiss SDline colour layers are the provisional
    # normal-status indication; a cleared master caution alone is not used.
    status = art.reference_values("status",{"status_master_caut":0},element)
    assert status["status_normal"] is True and status["status_rows"] == ()
    # Expensive immutable line rasterization must be cached, not catalogue work.
    art._line_runs.cache_clear()
    a,b=_OpRecorder(),_OpRecorder()
    systems.draw_toliss_system_frame(a,"fctl",{})
    before=art._line_runs.cache_info()
    systems.draw_toliss_system_frame(b,"fctl",{})
    after=art._line_runs.cache_info()
    assert before.misses==after.misses and after.hits>before.hits
    assert a.ops==b.ops


def check_delta_pixels():
    """Native opaque glyphs must not erase pipes or leave moving-symbol ghosts."""
    from PIL import ImageChops
    import render_pfp_frame_png as emulator
    from render_toliss_ecam_reference import sample_values
    initial=sample_values()
    moved={key:(value+.1 if isinstance(value,(float,int)) and not isinstance(value,bool) else value)
           for key,value in initial.items()}
    moved.update(fctl_rudder=-.3,fctl_aileron_l=.4,fctl_elevator_r=.6,fctl_spoiler_2=.7)
    for page in art.PAGE_TITLES:
        delta,full=emulator.PfpFrame(),emulator.PfpFrame()
        systems.draw_live_toliss_system_page(delta,page,initial)
        systems.draw_live_toliss_system_page(delta,page,moved)
        systems.draw_live_toliss_system_page(full,page,moved)
        assert ImageChops.difference(delta.image,full.image).getbbox() is None,page
        assert not systems.draw_live_toliss_system_page(delta,page,moved),page


if __name__=="__main__":
    check_reference_layouts()
    check_delta_pixels()
    print("BUG-40: twelve reference pages, bounds, unknown values, live surface geometry, cache, idle suppression and exact full/delta pixels passed.")
