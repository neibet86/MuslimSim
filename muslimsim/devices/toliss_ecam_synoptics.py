"""Reference-shaped Airbus SD artwork, shared by BB35 and BB36 (BUG-40).

Native primitives only: no screenshot backgrounds, hardware ownership or
simulator writes. Unknown telemetry is amber XX, never a photographed value.
Coordinates are the orthographic instrument face, not the photographed bezel.
Existing font slots are reused without changing any PFD/ND/CDU font bytes.
"""
from __future__ import annotations

from functools import lru_cache
import math

from .pfp_renderer import BLACK, WHITE, GREEN, CYAN, AMBER, RED, _finite, _clamp
from .systems_renderer import _fill, _outline, _arc

GREY = (85, 90, 96)
# Instrument field from the supplied ground-power reference, not the bezel.
# Local to SD artwork; does not change PFD/ND fonts, palette, or blackout.
BLACK = (34, 49, 70)
PAGE_TITLES = {
    "eng": "ENGINE", "bleed": "BLEED", "press": "CAB PRESS",
    "cond": "COND", "elec": "ELEC", "hyd": "HYD", "fuel": "FUEL",
    "door": "DOOR/OXY", "wheel": "WHEEL", "apu": "APU",
    "fctl": "F/CTL", "status": "STATUS",
}


def feature(c, name):
    callback = getattr(c, "record_feature", None)
    if callable(callback):
        callback(name)


@lru_cache(maxsize=2048)
def _line_runs(x0, y0, x1, y1, thickness):
    """Cache raster runs once; long straight pipes are a single rectangle."""
    if y0 == y1:
        return ((min(x0, x1), y0, abs(x1-x0)+thickness, thickness),)
    if x0 == x1:
        return ((x0, min(y0, y1), thickness, abs(y1-y0)+thickness),)
    rows = {}
    steps = max(abs(x1-x0), abs(y1-y0))
    for i in range(steps+1):
        x, y = round(x0+(x1-x0)*i/steps), round(y0+(y1-y0)*i/steps)
        for dy in range(thickness):
            lo, hi = rows.get(y+dy, (x, x+thickness))
            rows[y+dy] = min(lo, x), max(hi, x+thickness)
    runs = []
    for y, (lo, hi) in sorted(rows.items()):
        if runs and runs[-1][0] == lo and runs[-1][2] == hi-lo and runs[-1][1]+runs[-1][3] == y:
            x, sy, w, h = runs[-1]
            runs[-1] = x, sy, w, h+1
        else:
            runs.append((lo, y, hi-lo, 1))
    return tuple(runs)


def line(c, x0, y0, x1, y1, colour=WHITE, thickness=2):
    c.colour(*colour)
    for rect in _line_runs(round(x0), round(y0), round(x1), round(y1), thickness):
        c.fill(*rect)


def poly(c, points, colour=WHITE):
    for start, end in zip(points, points[1:]):
        line(c, *start, *end, colour)


def text(c, x, y, label, colour=WHITE, *, center=False, font=4):
    label = str(label)
    if center:
        x -= len(label)*17//2
    if "°" not in label:
        c.text(round(x), round(y), label, colour, BLACK, font)
        return
    # The LCD transport is ASCII-only. Draw the degree ring explicitly,
    # keeping the existing 17-pixel text advance and all other font slots.
    offset = 0
    for part in label.split("°")[:-1]:
        if part:
            c.text(round(x + offset), round(y), part, colour, BLACK, font)
        offset += len(part) * 17
        c.colour(*colour)
        for dx, dy, w, h in ((4, 1, 4, 1), (3, 2, 1, 4),
                             (8, 2, 1, 4), (4, 6, 4, 1)):
            c.fill(round(x + offset + dx), round(y + dy), w, h)
        offset += 17
    tail = label.rsplit("°", 1)[1]
    if tail:
        c.text(round(x + offset), round(y), tail, colour, BLACK, font)


def number(c, x, y, value, decimals=0, *, center=True, limit=6, colour=None):
    known = _finite(value)
    label = f"{float(value):.{decimals}f}" if known else "XX"
    # Bad/out-of-range data must not spill over adjacent system graphics.
    if len(label) > limit:
        label, known = "XX", False
    text(c, x, y, label, (colour or GREEN) if known else AMBER, center=center, font=5)


def state_colour(value):
    return GREEN if _finite(value) and float(value) > 0.5 else AMBER


def _active(value):
    """True only for code 1; fault codes 2/3 must never look operative."""
    if isinstance(value, (list, tuple)):
        return any(_active(item) for item in value)
    return _finite(value) and float(value) == 1.0


def triangle(c, x, y, colour=GREEN, direction="up"):
    if direction == "right":
        points = ((x-5,y-5),(x+5,y),(x-5,y+5),(x-5,y-5))
    elif direction == "left":
        points = ((x+5,y-5),(x-5,y),(x+5,y+5),(x+5,y-5))
    else:
        points = ((x-5,y+4),(x,y-5),(x+5,y+4),(x-5,y+4))
    poly(c, points, colour)


def valve(c, x, y, value, *, vertical=True, radius=12, closed_amber=False, force_colour=None):
    known = _finite(value)
    colour = GREEN if known and not (closed_amber and float(value) <= .5) else AMBER
    if force_colour is not None:
        colour = force_colour
    _fill(c, x-radius-2, y-radius-2, 2*radius+5, 2*radius+5, BLACK)
    _arc(c, x, y, radius, 0, 360, colour, 2)
    if not known:
        line(c, x-4, y-4, x+4, y+4, AMBER)
        line(c, x-4, y+4, x+4, y-4, AMBER)
    elif (float(value) > 0.5) == vertical:
        line(c, x, y-radius, x, y+radius, colour)
    else:
        line(c, x-radius, y, x+radius, y, colour)


def gauge(c, x, y, value, low, high, *, radius=43, decimals=0, start=180, end=360, red_end=False, invalid_amber=False):
    _arc(c, x, y, radius, start, end, AMBER if invalid_amber and not _finite(value) else WHITE, 2)
    if red_end:
        _arc(c, x, y, radius, end-14, end, RED, 3)
    if _finite(value):
        a = math.radians(start+(end-start)*_clamp((float(value)-low)/(high-low),0,1))
        line(c, x, y, x+(radius+3)*math.cos(a), y+(radius+3)*math.sin(a), GREEN)
    number(c, x, y-8, value, decimals)


def header(c, page):
    _fill(c, 0, 0, 640, 480, BLACK)
    label = PAGE_TITLES[page]
    centered = page in ("apu", "hyd", "door", "status")
    x = (640-len(label)*17)//2 if centered else 38
    y = 74 if page == "wheel" else 4
    text(c, x, y, label, font=5)
    if page == "wheel":
        # Slot 5's W is only 11 px high while H/E/L are 16 px. Repair this
        # title locally, without altering the shared PFD/ND font package.
        _fill(c,x,y,17,29,BLACK)
        poly(c,((x+2,y+6),(x+5,y+21),(x+8,y+13),(x+11,y+21),(x+14,y+6)))
        feature(c,"WHEEL_CAPITAL_W")
    line(c, x+2, y+29, x+len(label)*17-2, y+29)
    feature(c, "AIRBUS_ECAM_HEADER")
    feature(c, "REFERENCE_"+page.upper())


def permanent_data(c, v):
    """Three-column SD strip. Slot-4 ink safely permits 22-pixel row spacing."""
    _fill(c, 34, 407, 572, 73, BLACK)
    for y, name, key in ((407,"TAT","ecam_tat"),(429,"SAT","ecam_sat"),(451,"ISA","ecam_isa")):
        if name == "ISA" and not v.get("ecam_show_isa", True):
            continue
        text(c, 40, y, name)
        value = v.get(key)
        label = f"{float(value):+03.0f}" if _finite(value) and abs(float(value)) < 100 else "XX"
        text(c, 100, y, label, GREEN if label != "XX" else AMBER)
        text(c, 182, y, "°C", CYAN)
    utc = v.get("ecam_utc")
    minutes = int(float(utc)//60) % 1440 if _finite(utc) else None
    label = f"{minutes//60:02d} H {minutes%60:02d}" if minutes is not None else "XX H XX"
    text(c, 309, 430, label, GREEN if minutes is not None else AMBER, center=True)
    text(c, 403, 414, "GW")
    if _finite(v.get("ecam_gw")):
        number(c, 497, 414, v.get("ecam_gw"), limit=5)
    else:
        text(c, 497, 414, "--", CYAN, center=True, font=5)
    text(c, 565, 414, "KG", CYAN)
    line(c, 34, 407, 605, 407)
    line(c, 225, 408, 225, 477)
    line(c, 393, 408, 393, 477)
    feature(c, "AIRBUS_ECAM_PERMANENT_DATA")
    feature(c, "ECAM_THREE_COLUMN_FOOTER")


def self_test(c):
    """No footer, countdown text, or app-owned startup delay."""
    _fill(c, 0, 0, 640, 480, BLACK)
    text(c, 320, 222, "SELF TEST IN PROGRESS", GREEN, center=True)
    text(c, 320, 249, "(MAX 40 SECONDS)", GREEN, center=True)


def eng(c, v):
    for x, i in ((185,0),(455,1)):
        number(c,x,49,v.get(f"eng_used_{i}"))
        gauge(c,x,154,v.get(f"eng_oil_qt_{i}"),0,25,decimals=1,invalid_amber=True)
        gauge(c,x,224,v.get(f"eng_oilpress_{i}"),0,100,invalid_amber=True)
        number(c,x,256,v.get(f"eng_oiltemp_{i}"))
        number(c,x,306,v.get(f"eng_vib_{i}"),1)
        number(c,x,333,v.get(f"eng_vib_n2_{i}"),1)
    for y, label, colour in ((45,"F.USED",WHITE),(68,"KG",CYAN),(106,"OIL",WHITE),(133,"QT",CYAN),(204,"PSI",CYAN),(256,"°C",CYAN),(304,"VIB N1",WHITE),(333,"N2",WHITE)):
        text(c,320,y,label,colour,center=True)


def bleed(c, v):
    pack_1 = _active(v.get("bleed_pack_switch_1"))
    pack_2 = _active(v.get("bleed_pack_switch_2"))
    # The native distribution-duct outline remains green in the unpressurised
    # ground-power reference; its three outlet triangles carry pack state.
    poly(c,((156,78),(156,54),(483,54),(483,78)),GREEN)
    triangle(c,195,48,GREEN if pack_1 else AMBER)
    triangle(c,320,48,GREEN if pack_1 or pack_2 else AMBER)
    triangle(c,443,48,GREEN if pack_2 else AMBER)
    valve(c,320,93,v.get("bleed_ram"))
    text(c,320,112,"RAM",center=True)
    text(c,320,135,"AIR",center=True)

    engine_1 = _active(v.get("bleed_ind_1"))
    engine_2 = _active(v.get("bleed_ind_2"))
    apu = _active(v.get("bleed_apu_ind"))
    ground = _active(v.get("bleed_ground_hp")) or _active(v.get("bleed_ground_lp"))
    xbleed_value = v.get("bleed_xbleed_ind")
    xbleed_known = _finite(xbleed_value)
    # XBleedInd is authoritative.  BleedIntercon=3 can preserve supply-side
    # colouring while that one indication is momentarily absent, but it must
    # never invent the valve symbol itself.
    connected = _active(xbleed_value)
    if not xbleed_known and _finite(v.get("bleed_intercon")):
        connected = float(v.get("bleed_intercon")) >= 3.0
    left_source = engine_1 or apu or ground
    right_source = engine_2
    left_supplied = left_source or (connected and right_source)
    right_supplied = right_source or (connected and left_source)
    side_supplied = {1:left_supplied, 2:right_supplied}

    # The A321 manifold is a real connected system, not two pressure columns.
    # Leave a gap exactly under the crossbleed disc so its horizontal/vertical
    # state is not overdrawn by the pipe behind it.
    if connected or apu or ground:
        if left_supplied:
            line(c,156,223,364,223,GREEN)
        if right_supplied:
            line(c,388,223,483,223,GREEN)
    valve(c,376,223,xbleed_value,vertical=False)
    feature(c,"BLEED_CROSS_MANIFOLD")
    if xbleed_known:
        feature(c,"BLEED_XBLEED_HORIZONTAL" if connected else "BLEED_XBLEED_VERTICAL")
    else:
        feature(c,"BLEED_XBLEED_UNKNOWN")

    # Ground-air connection marker is present even when no cart is connected.
    triangle(c,278,238,WHITE)
    text(c,278,246,"GND",center=True)
    feature(c,"BLEED_GND_MARKER")

    # The APU branch is displayed when the indicated APU bleed valve is open.
    # Its valve is a vertical-flow valve; this is independent of X BLEED.
    if apu:
        line(c,320,223,320,252,GREEN)
        valve(c,320,264,v.get("bleed_apu_ind"),vertical=True,closed_amber=True)
        line(c,320,276,320,284,GREEN)
        text(c,320,288,"APU",center=True)
        feature(c,"BLEED_APU_BRANCH")
        feature(c,"BLEED_APU_VALVE_VERTICAL")

    for i,x in ((1,156),(2,483)):
        opened = engine_1 if i == 1 else engine_2
        colour = GREEN if opened else AMBER
        supply_colour = GREEN if side_supplied[i] else AMBER
        # The manifold can be pressurised by the APU while the engine source
        # below its closed IP valve remains amber and disconnected.
        line(c,x,218,x,250,supply_colour)
        line(c,x,304,x,328,supply_colour)
        number(c,x-15,81,v.get(f"bleed_pack_temp_{i}"))
        text(c,x+12,81,"°C",CYAN)
        number(c,x-15,133,v.get(f"bleed_pack_outlet_{i}"))
        text(c,x+12,133,"°C",CYAN)
        pack_arc(c,x,151,v.get(f"bleed_pack_pointer_{i}"),GREEN)
        flow_colour=GREEN if _active(v.get(f"bleed_pack_switch_{i}")) else AMBER
        pack_arc(c,x,204,v.get(f"bleed_pack_flow_{i}"),flow_colour)
        text(c,x-69,112,"C")
        text(c,x+55,112,"H")
        text(c,x-78,165,"LO")
        text(c,x+52,165,"HI")
        # Both flow-valve leads start at the LEFT foot of the lower arc.
        valve(c,x,206,v.get(f"bleed_pack_switch_{i}"),closed_amber=True)
        poly(c,((x-33,185),(x-8,198)),flow_colour)
        _fill(c,x-38,250,76,54,BLACK)
        _outline(c,x-38,250,76,54,WHITE,2)
        pressure = v.get("bleed_press_l" if i==1 else "bleed_press_r")
        pressure_colour = GREEN if _finite(pressure) and float(pressure) > 4.0 else AMBER
        number(c,x,248,pressure,colour=pressure_colour)
        number(c,x,276,v.get(f"bleed_temp_{i}"))
        text(c,x+45 if i==1 else x-96,248,"PSI",CYAN)
        text(c,x+45 if i==1 else x-79,276,"°C",CYAN)
        ip_value = v.get(f"bleed_ind_{i}")
        ip_draw = 1.0 if opened else 0.0 if _finite(ip_value) else math.nan
        valve(c,x,340,ip_draw,closed_amber=True)
        if _finite(ip_value):
            feature(c,f"BLEED_IP_{'VERTICAL' if opened else 'HORIZONTAL'}_{i}")
        inner=x+58 if i==1 else x-58
        line(c,x,352,x,390,colour)
        if opened:
            line(c,x,360,inner-12 if i==1 else inner+12,360,GREEN)
            feature(c,f"BLEED_IP_HP_CONNECTED_{i}")
        # HP stub is separate on the no-bleed reference, not a bridged pipe.
        outer=inner+29 if i==1 else inner-29
        poly(c,((inner+12 if i==1 else inner-12,360),(outer,360),(outer,375)),colour)
        # HP is a valve state, never inferred from pressure shared by the APU.
        # Closed is vertical on the horizontal HP pipe in the native page.
        hp_value = v.get(f"bleed_hp_{i}")
        hp_open = _active(hp_value)
        hp_normal = _finite(hp_value) and float(hp_value) in (0.0, 1.0)
        hp_colour = GREEN if opened and hp_normal else AMBER
        hp_draw = 1.0 if hp_open else 0.0 if _finite(hp_value) else math.nan
        valve(c,inner,360,hp_draw,vertical=False,closed_amber=True,
              force_colour=hp_colour)
        if _finite(hp_value):
            feature(c,f"BLEED_HP_{'HORIZONTAL' if hp_open else 'VERTICAL'}_{i}")
        text(c,x-61 if i==1 else x+48,326,str(i),colour,font=5)
        text(c,x,376,"IP",center=True)
        text(c,inner+29 if i==1 else inner-29,376,"HP",center=True)
        _outline(c,x-38,250,76,54,WHITE,2)
        # Bottom border is the flow arc, not a rectangular line through it.
        poly(c,((x-49,186),(x-49,77),(x+49,77),(x+49,186)))
    feature(c,"BLEED_FOUR_PACK_ARCS")


def pack_arc(c,x,y,ratio,colour):
    _arc(c,x,y,38,210,330,WHITE,2)
    if _finite(ratio) and 0<=float(ratio)<=1:
        angle=math.radians(210+120*float(ratio))
        line(c,x,y-14,x+38*math.cos(angle),y+38*math.sin(angle),colour)


def cond(c, v):
    text(c,452,4,"TEMP: °C",CYAN)
    poly(c,((91,94),(123,70),(520,70),(538,80)))
    poly(c,((91,120),(123,130),(521,130),(538,120)))
    for x in (244,388):
        line(c,x,71,x,129)
    for x,label,key in ((168,"CKPT","cond_cockpit_temp"),(315,"FWD","cond_fwd_cabin_temp"),(462,"AFT","cond_aft_cabin_temp")):
        text(c,x,75,label,center=True)
        number(c,x,100,v.get(key))
        line(c,x,183,x,207,state_colour(v.get("cond_hot_air")))
        gauge(c,x,181,v.get("cond_duct_"+label.lower()),0,80,radius=18)
        text(c,x-43,164,"C")
        text(c,x+25,164,"H")
    line(c,168,207,558,207,state_colour(v.get("cond_hot_air")))
    valve(c,548,207,v.get("cond_hot_air"),vertical=False,closed_amber=True)
    text(c,562,180,"HOT")
    text(c,562,203,"AIR")
    poly(c,((315,207),(315,371),(177,371),(177,325)),state_colour(v.get("cond_cargo_hot_air")))
    poly(c,((471,325),(471,371),(554,371)),state_colour(v.get("cond_cargo_hot_air")))
    for x,label,key in ((177,"FWD","cond_fwd_cargo_temp"),(471,"AFT","cond_aft_cargo_temp")):
        _outline(c,x-66,248,112,47,WHITE,2)
        text(c,x-58,252,label)
        number(c,x+17,269,v.get(key))
        valve(c,x+46,259,v.get("cond_"+label.lower()+"_isol"))
        valve(c,x,308,v.get("cond_cargo_hot_air"))
        _arc(c,x,346,19,210,330,WHITE,2)
        text(c,x-45,328,"C")
        text(c,x+27,328,"H")
    valve(c,548,371,v.get("cond_cargo_hot_air"),vertical=False,closed_amber=True)
    text(c,562,346,"HOT")
    text(c,562,369,"AIR")


def press(c, v):
    text(c,267,4,"LDG ELEV")
    text(c,431,4,"AUTO",GREEN if v.get("press_mode")==0 else WHITE)
    number(c,520,31,v.get("press_ldg_elev"),limit=5)
    text(c,569,31,"FT",CYAN)
    for x,label,unit,key,lo,hi,dec in ((132,"ΔP","PSI","press_delta_p",0,10,1),(318,"V/S","FT/MIN","press_cabin_vs",-2000,2000,0),(505,"CAB ALT","FT","press_cabin_alt",0,10000,0)):
        text(c,x,61,label,center=True)
        text(c,x,86,unit,CYAN,center=True)
        gauge(c,x,171,v.get(key),lo,hi,radius=47,decimals=dec,
              start=90 if key=="press_cabin_vs" else 145,
              end=270 if key=="press_cabin_vs" else 315,
              red_end=key=="press_cabin_alt")
    poly(c,((107,351),(107,233),(534,233),(534,267)))
    line(c,107,351,534,351)
    system = v.get("press_active_system")
    text(c,310,244,f"SYS{int(system)}" if system in (1,2) else "XX",GREEN if system in (1,2) else AMBER,center=True)
    text(c,263,286,"VENT",center=True)
    for x,label,key in ((193,"INLET","press_inlet"),(305,"OUTLET","press_extract")):
        valve(c,x,351,v.get(key),radius=5)
        text(c,x,317,label,center=True)
    _arc(c,469,343,47,200,275,WHITE,2)
    out=v.get("press_outflow")
    if _finite(out):
        a=math.radians(180+90*_clamp(float(out),0,1))
        line(c,469,343,469+47*math.cos(a),343+47*math.sin(a),GREEN)
    else:
        text(c,452,319,"XX",AMBER)
    valve(c,534,294,v.get("press_safety"),radius=5)
    text(c,534,269,"SAFETY",center=True)
    for x,label in ((125,"PACK 1"),(509,"PACK 2")):
        triangle(c,x,374,AMBER)
        text(c,x,377,label,center=True)


def elec(c, v):
    # Connection topology is fixed; telemetry colours it, not the snapshot.
    for x,i in ((159,0),(483,1)):
        _outline(c,x-49,42,98,72)
        text(c,x,41,f"BAT {i+1}",center=True)
        number(c,x-9,63,v.get(f"elec_bat_v_{i}"))
        text(c,x+24,63,"V",CYAN)
        number(c,x-9,86,v.get(f"elec_bat_a_{i}"))
        text(c,x+24,86,"A",CYAN)
    for x,y,label,key in ((107,128,"DC 1","elec_dc_bus_1"),(320,75,"DC BAT","elec_dc_bat"),(320,155,"DC ESS","elec_dc_ess"),(532,128,"DC 2","elec_dc_bus_2"),(107,261,"AC 1","elec_ac_bus_1"),(320,261,"AC ESS","elec_ac_ess"),(532,261,"AC 2","elec_ac_bus_2")):
        _fill(c,x-59,y,119,28,GREY)
        # Opaque cell background deliberately matches the bus strip.
        c.text(x-len(label)*17//2,y,label,state_colour(v.get(key)),GREY,4)
    poly(c,((107,156),(107,173)),state_colour(v.get("elec_dc_bus_1")))
    poly(c,((532,156),(532,173)),state_colour(v.get("elec_dc_bus_2")))
    line(c,320,103,320,153,state_colour(v.get("elec_dc_bat")))
    line(c,167,275,260,275,state_colour(v.get("elec_ac_ess")))
    for x,i in ((107,1),(532,2)):
        _outline(c,x-49,179,98,73)
        text(c,x,178,f"TR {i}",center=True)
        number(c,x-9,201,v.get(f"elec_tr_v_{i}"))
        text(c,x+26,201,"V",CYAN)
        number(c,x-9,224,v.get(f"elec_tr_a_{i}"))
        text(c,x+26,224,"A",CYAN)
        line(c,x,290,x,309,state_colour(v.get(f"elec_gen_{i}")))
        triangle(c,x,299,state_colour(v.get(f"elec_gen_{i}")))
        _outline(c,x-58,313,116,90)
        text(c,x,309,f"GEN {i}",center=True)
        for y,unit,key in ((330,"%","load"),(352,"V","v"),(374,"HZ","hz")):
            number(c,x-16,y,v.get(f"elec_gen_{key}_{i}"))
            text(c,x+25,y,unit,CYAN)
    triangle(c,295,199,WHITE)
    text(c,319,198,"TR ESS",center=True)
    text(c,336,226,"EMER GEN",center=True)
    text(c,320,310,"APU GEN",center=True)
    text(c,320,347,"IDG °C",center=True)
    number(c,274,373,v.get("elec_idg_temp_1"))
    number(c,373,373,v.get("elec_idg_temp_2"))
    for x in (159,483):
        _outline(c,x-49,42,98,72)
    for x in (107,532):
        _outline(c,x-49,179,98,73)
        _outline(c,x-58,313,116,90)


def hyd(c, v):
    for x,key,label in ((141,"g","GREEN"),(319,"b","BLUE"),(498,"y","YELLOW")):
        value=v.get("hyd_press_"+key)
        colour=GREEN if _finite(value) and float(value)>=1450 else AMBER
        triangle(c,x,50,colour)
        text(c,x,59,label,colour,center=True)
        number(c,x,88,value,colour=colour)
        line(c,x,124,x,376,colour)
        pump_y=252 if key=="b" else 215
        if v.get("hyd_pump_"+key) == 2:
            text(c,x,pump_y-2,"LO",AMBER,center=True)
        _outline(c,x-19,pump_y,38,25,colour)
        if key != "b":
            # Fire shutoff valve state is separate from hydraulic pressure.
            valve(c,x,279,v.get("hyd_fire_valve_"+key))
            text(c,x+31,258,"1" if key=="g" else "2")
        else:
            text(c,x+27,231,"ELEC")
        _outline(c,x-7,328,15,66,WHITE)
        _fill(c,x-7,380,15,14,AMBER)
        qty=v.get("hyd_qty_"+key)
        if _finite(qty):
            ratio=float(qty) if float(qty)<=1.5 else float(qty)/100
            line(c,x-6,391,x-6,391-60*_clamp(ratio,0,1),GREEN,5)
        else:
            text(c,x+16,356,"XX",AMBER)
    text(c,230,99,"PSI",CYAN,center=True)
    text(c,411,99,"PSI",CYAN,center=True)
    line(c,220,151,412,151,state_colour(v.get("hyd_ptu_mode")))
    triangle(c,220,151,state_colour(v.get("hyd_ptu_mode")),"left")
    triangle(c,412,151,state_colour(v.get("hyd_ptu_mode")),"right")
    _arc(c,319,151,16,0,180,GREEN if _finite(v.get("hyd_press_b")) else AMBER,2)
    text(c,362,155,"PTU")
    text(c,252,188,"RAT")
    triangle(c,310,201,state_colour(v.get("hyd_rat_mode")),"right")
    text(c,524,168,"ELEC")
    triangle(c,514,181,state_colour(v.get("hyd_y_elec_mode")),"left")


def fuel(c, v):
    for x,i in ((168,0),(472,1)):
        code=v.get(f"fuel_lp_code_{i}")
        text(c,x,42,str(i+1),GREEN if code==3 else AMBER,center=True)
        number(c,x,68,v.get(f"eng_used_{i}"))
        line(c,x,113,x,208,GREEN if code in (1,2,3) else AMBER)
        fuel_valve(c,x,110,code,engine=True)
    text(c,320,35,"F.USED",center=True)
    text(c,320,58,"1+2",center=True)
    used=[v.get(f"eng_used_{i}") for i in (0,1)]
    number(c,320,81,sum(used) if all(_finite(n) for n in used) else None)
    text(c,320,106,"KG",CYAN,center=True)
    fuel_valve(c,320,146,v.get("fuel_crossfeed_code"))
    text(c,95,143,"APU")
    triangle(c,154,157,state_colour(v.get("fuel_apu_ff")),"left")
    poly(c,((57,240),(252,207),(386,207),(580,240),(580,297),(57,297),(57,240)))
    line(c,252,207,243,297)
    line(c,386,207,397,297)
    for tank,(x,key) in enumerate(((168,"l"),(320,"ctr"),(472,"r"))):
        number(c,x,257,v.get("fuel_qty_"+key))
        for pump,dx in enumerate((-19,19)):
            code=v.get(f"fuel_pump_code_{tank*2+pump}")
            # Current ToLiss A321 uses both 1 and 3 for operating wing pumps;
            # code 3 is not a LO indication on a full, pressurised wing tank.
            wing_running = key != "ctr" and code in (1,3)
            colour=GREEN if code==1 or wing_running else AMBER
            _fill(c,x+dx-15,207,30,30,BLACK)
            if wing_running:
                line(c,x+dx,211,x+dx,234,colour)
            elif code in (0,1,2):
                line(c,x+dx-10,222,x+dx+10,222,colour)
            elif code==3 and not wing_running:
                text(c,x+dx-13,212,"LO",AMBER,font=3)
            # Native text cells are opaque: outline after LO, not before it.
            _outline(c,x+dx-15,207,30,30,colour)
        if key != "ctr":
            number(c,x,300,v.get("fuel_temp_"+key))
            text(c,x+35,300,"°C",CYAN)
    text(c,47,334,"F.FLOW")
    text(c,77,356,"1+2")
    flow=[v.get(f"fuel_flow_kg_min_{i}") for i in (0,1)]
    number(c,310,344,sum(flow) if all(_finite(n) for n in flow) else None)
    text(c,366,344,"KG/MIN",CYAN)
    _outline(c,42,379,328,27)
    text(c,48,375,"FOB")
    number(c,219,375,v.get("fuel_fob"))
    text(c,314,375,"KG",CYAN)
    _outline(c,42,379,328,27)


def fuel_valve(c,x,y,code,*,engine=False):
    # AirbusFBW enums documented by XHSI; 1 is CLOSED, not truthy OPEN.
    mapping = ({1:(0,AMBER),2:(1,AMBER),3:(1,GREEN)} if engine else
               {1:(0,GREEN),2:(1,GREEN),3:(0,AMBER),4:(1,AMBER)})
    if code == 0:
        _fill(c,x-14,y-14,29,29,BLACK)
        _arc(c,x,y,12,0,360,AMBER,2)
        line(c,x-8,y+8,x+8,y-8,AMBER)
    else:
        position,colour=mapping.get(code,(None,AMBER))
        valve(c,x,y,position,vertical=engine,force_colour=colour)


def door(c, v):
    text(c,445,37,"CKPT OXY")
    number(c,438,62,v.get("door_oxy_psi_1"),limit=4)
    text(c,480,62,"PSI",CYAN)
    number(c,574,62,v.get("door_oxy_psi_2"),limit=4)
    poly(c,((291,396),(282,380),(278,134),(291,97),(307,79),(330,79),(348,97),(361,134),(356,380),(348,396)))
    poly(c,((278,224),(244,243),(279,237)))
    poly(c,((359,224),(393,243),(359,237)))
    for x,y,w,h,key in ((298,109,19,8,"door_cockpit"),(295,131,9,16,"door_window_0"),(335,131,9,16,"door_window_1"),(275,160,10,16,"door_pax_0"),(353,160,10,16,"door_pax_1"),(277,246,10,16,"door_pax_2"),(351,246,10,16,"door_pax_3"),(277,278,10,16,"door_exit_l"),(351,278,10,16,"door_exit_r"),(279,362,10,16,"door_aft_l"),(349,362,10,16,"door_aft_r"),(342,187,18,14,"door_cargo_0"),(341,307,18,14,"door_cargo_1"),(343,336,8,12,"door_bulk")):
        value=v.get(key)
        colour=GREEN if _finite(value) and float(value)<0.1 else AMBER
        opened = _finite(value) and float(value) >= .1
        if opened:
            _fill(c,x,y,w,h,AMBER)
            left=x<320
            label = "CARGO" if "cargo" in key else "BULK" if "bulk" in key else "EXIT" if "exit" in key else "CABIN"
            if "window" not in key and key != "door_cockpit":
                for dx in (18,40,62):
                    line(c,x-dx if left else x+w+dx,y+7,x-dx-10 if left else x+w+dx+10,y+7,AMBER)
                text(c,91 if left else 440,y-7,label,AMBER)
        else:
            _outline(c,x,y,w,h,colour)
    for i,y in enumerate((150,236,270,352)):
        for side,x in ((0,178),(1,376)):
            if v.get(f"door_slide_{2*i+side}") == 1:
                text(c,x,y,"SLIDE")


def spoilers(c, v, prefix, baseline=63):
    for i,x in enumerate((138,178,218,258,298,350,390,430,470,510),1):
        value=v.get(f"{prefix}_spoiler_{i}")
        known=_finite(value)
        status=v.get(f"{prefix}_spoiler_status_{i}")
        colour=GREEN if known and status in (0,1) else AMBER
        y=baseline-abs(320-x)//23
        if status == 2:
            text(c,x,y-24,str(6-i if i<=5 else i-5),AMBER,center=True)
        line(c,x-7,y,x+7,y,colour)
        if known and float(value)>0.015:
            tip=y-27*_clamp(float(value),0,1)
            line(c,x,y,x,tip,colour)
            line(c,x,tip,x-4,tip+6,colour)
            line(c,x,tip,x+4,tip+6,colour)


def wheel(c, v):
    spoilers(c,v,"wheel",57)
    for x,y,key in ((320,103,"wheel_gear_n"),(132,205,"wheel_gear_l"),(511,205,"wheel_gear_r")):
        state=v.get(key)
        colour=GREEN if state==2 else AMBER
        for dx in (-31,31) if key.endswith("n") else (0,):
            line(c,x+dx-38,y,x+dx+38,y,colour)
            _arc(c,x+dx,y,4,0,360,WHITE,2)
        if state in (1,2):
            gear_triangle(c,x,y+6,GREEN if state==2 else RED)
            feature(c,"WHEEL_DOWN_TRIANGLE_"+key[-1].upper())
        elif not _finite(state):
            text(c,x,y+8,"XX",AMBER,center=True)
    for x,i in ((262,0),(378,1)):
        number(c,x,137,v.get(f"wheel_tire_{i}"))
        _arc(c,x,151,24,35,145,WHITE,2)
    text(c,320,137,"PSI",CYAN,center=True)
    wheel_legends(c,v)
    for x,indices in ((133,(0,1)),(511,(2,3))):
        for dx,i in zip((-55,55),indices):
            xx=x+dx
            _arc(c,xx,286,26,225,315,WHITE,2)
            _arc(c,xx,336,26,45,135,WHITE,2)
            temp=v.get(("wheel_brake_temp_lo","wheel_brake_temp_li","wheel_brake_temp_ri","wheel_brake_temp_ro")[i])
            number(c,xx,272,temp)
            text(c,xx,299,str(i+1),center=True)
            number(c,xx,326,v.get(f"wheel_tire_{i+2}"))
        text(c,x,272,"°C",CYAN,center=True)
        text(c,x,299,"REL",center=True)
        text(c,x,326,"PSI",CYAN,center=True)


def gear_triangle(c,x,y,colour):
    poly(c,((x-20,y),(x+20,y),(x,y+25),(x-20,y)),colour)
    for dx in (-15,-10,-5,0,5,10,15):
        line(c,x+dx,y+3,x+dx,y+25-abs(dx)*1.25,colour)


def wheel_legends(c,v):
    """Entire centre block; missing data is not silently treated as healthy."""
    def tag(x,y,label,available):
        c.text(x,y,label,GREEN if available==1 else AMBER,GREY,4)
    if v.get("wheel_nws_avail")==0:
        tag(218,180,"Y",v.get("wheel_y_available"))
        text(c,244,180,"N/W STEERING",AMBER)
        feature(c,"WHEEL_NWS_LEGEND")
    norm=v.get("wheel_norm_available")
    alt=v.get("wheel_alt_available")
    skid=v.get("wheel_skid_available")
    auto=v.get("wheel_auto_available")
    abnormal=any(value==0 for value in (norm,alt,skid,auto))
    if abnormal:
        text(c,267,260,"ANTI SKID",GREEN if skid==1 else AMBER)
        tag(240,286,"G",v.get("wheel_g_available"))
        text(c,267,286,"NORM BRK",GREEN if norm==1 else AMBER)
        tag(240,312,"Y",v.get("wheel_y_available"))
        text(c,267,312,"ALTN BRK",GREEN if alt==1 else AMBER)
        feature(c,"WHEEL_BRAKING_LEGENDS")
    if v.get("wheel_accu_only")==1:
        text(c,267,339,"ACCU ONLY",GREEN)
        poly(c,((263,355),(250,355),(250,345)),GREEN)
        triangle(c,250,341,GREEN)
        feature(c,"WHEEL_ACCU_ONLY")
    armed=next((label for label,key in (("LO","wheel_autobrk_lo"),("MED","wheel_autobrk_med"),("MAX","wheel_autobrk_max"))
                if _finite(v.get(key)) and float(v[key])>0),None)
    if auto==0 or armed:
        text(c,267,373,"AUTO BRK",GREEN if auto==1 else AMBER)
        if armed:
            text(c,440,373,armed,GREEN if auto==1 else AMBER)
        feature(c,"WHEEL_AUTO_BRK")


def apu(c, v):
    text(c,119,88,"APU GEN")
    valve(c,494,87,v.get("apu_bleed_ind"))
    _outline(c,444,113,105,59)
    text(c,497,111,"BLEED",center=True)
    number(c,471,142,v.get("apu_bleed_press"))
    text(c,494,142,"PSI",CYAN)
    _outline(c,444,113,105,59)
    poly(c,((123,213),(123,191),(550,191),(550,213)))
    for y,key,label,unit,high in ((266,"apu_n_pct","N","%",110),(361,"apu_egt","EGT","°C",1100)):
        gauge(c,204,y,v.get(key),0,high,radius=47,start=150,end=310,red_end=True)
        text(c,321,y-47,label,center=True)
        text(c,321,y-21,unit,CYAN,center=True)


def surface(c,x,y0,y1,value,left,available=None):
    line(c,x,y0,x,y1)
    for y in (y0,(y0+y1)//2,y1):
        line(c,x-3,y,x+3,y)
    if _finite(value):
        y=(y0+y1)/2-_clamp(float(value),-1,1)*(y1-y0)*0.46
        triangle(c,x-10 if left else x+10,y,GREEN if available == 1 else AMBER,"right" if left else "left")
    else:
        text(c,x-17,(y0+y1)//2-14,"XX",AMBER)


def hyd_letters(c,x,y,letters,v):
    colours=[]
    for letter in letters:
        value=v.get("fctl_hyd_"+letter.lower())
        colours.append(GREEN if _finite(value) and float(value)>=1450 else AMBER)
    start=0
    while start<len(letters):
        end=start+1
        while end<len(letters) and colours[end]==colours[start]:
            end+=1
        c.text(x+start*17,y,letters[start:end],colours[start],GREY,4)
        start=end


def fctl(c, v):
    poly(c,((116,65),(116,59),(272,42)))
    poly(c,((367,42),(525,59),(525,65)))
    hyd_letters(c,291,34,"GBY",v)
    spoilers(c,v,"fctl",94)
    line(c,151,109,261,100)
    line(c,376,100,487,109)
    text(c,320,92,"SPD BRK",center=True)
    feature(c,"FCTL_TEN_SPOILERS")
    for x,left,label,key in ((101,False,"L AIL","fctl_aileron_l"),(539,True,"R AIL","fctl_aileron_r")):
        surface(c,x,140,217,v.get(key),left,v.get(key+"_available"))
        text(c,x-37 if not left else x+12,115,label,center=True)
        hyd_letters(c,x+17 if not left else x-55,212,"BG" if not left else "GB",v)
    feature(c,"FCTL_AILERONS")
    for x,label,count in ((213,"ELAC",2),(384,"SEC",3)):
        text(c,x,143,label,center=True)
        for i in range(count):
            xx=x-29+i*21
            fcc_index = i if label == "ELAC" else i+2
            text(c,xx+44,170+i*9,str(i+1),state_colour(v.get(f"fctl_fcc_{fcc_index}")),font=3)
            poly(c,((xx,193+i*9),(xx+63,193+i*9),(xx+63,179+i*9)))
    text(c,305,237,"PITCH TRIM",center=True)
    trim=v.get("fctl_pitch_trim_deg")
    label=f"{abs(float(trim)):.1f}° {'UP' if float(trim)>=0 else 'DN'}" if _finite(trim) and abs(float(trim))<100 else "XX"
    text(c,312,263,label,GREEN if label!="XX" and v.get("fctl_trim_powered")==1 else AMBER,center=True)
    hyd_letters(c,421,237,"GY",v)
    poly(c,((265,282),(238,297),(238,313),(287,307)))
    poly(c,((371,282),(400,297),(400,313),(352,307)))
    text(c,320,291,"RUD",center=True)
    hyd_letters(c,292,318,"GBY",v)
    for x,left,label,key in ((198,False,"L ELEV","fctl_elevator_l"),(442,True,"R ELEV","fctl_elevator_r")):
        surface(c,x,283,360,v.get(key),left,v.get(key+"_available"))
        text(c,x-70 if not left else x+70,286,label,center=True)
        hyd_letters(c,x-58 if not left else x+21,336,"BG" if not left else "YB",v)
    feature(c,"FCTL_ELEVATORS")
    _arc(c,320,335,58,54,126,WHITE,2)
    rudder=v.get("fctl_rudder")
    if _finite(rudder):
        a=math.radians(90-30*_clamp(float(rudder),-1,1))
        tip=(320+57*math.cos(a),335+57*math.sin(a))
        poly(c,((315,355),tip,(325,355),(315,355)),GREEN if v.get("fctl_rudder_available")==1 else AMBER)
    else:
        text(c,320,356,"XX",AMBER,center=True)
    feature(c,"FCTL_RUDDER")


def status(c, v):
    line(c,374,52,374,394)
    rows = v.get("status_rows") or ()
    if rows:
        colours = {"g": GREEN, "a": AMBER, "r": RED, "w": WHITE, "b": CYAN}
        # Each ToLiss SDlineN* string is one colour layer of the native line.
        # Draw the layers at the same origin so their embedded spacing remains
        # authoritative; do not synthesize status wording from warning lamps.
        for row, layers in rows:
            y = 58 + (int(row) - 1) * 18
            for colour, value in layers:
                text(c, 41, y, value[:34], colours.get(colour, WHITE), font=3)
        feature(c,"STATUS_NATIVE_SD_LINES")
    elif v.get("status_normal") is True:
        text(c,212,208,"NORMAL",GREEN,center=True)
    else:
        text(c,210,186,"STATUS DATA",AMBER,center=True)
        text(c,210,211,"UNAVAILABLE",AMBER,center=True)
        # Retain known warning indications without calling them the SD list.
        y=268
        for key,label,colour in (("status_master_warn","WARNING",RED),
                                 ("status_master_caut","CAUTION",AMBER)):
            if _finite(v.get(key)) and float(v[key])>=.5:
                text(c,210,y,label,colour,center=True)
                y+=29
        y=89
        for key,label,colour in (("status_ap_warn","AP OFF",RED),
                                 ("status_athr_warn","A/THR OFF",RED),
                                 ("status_retard_warn","RETARD",AMBER),
                                 ("status_ospeed_warn","OVERSPEED",RED)):
            if _finite(v.get(key)) and float(v[key])>=.5:
                text(c,488,y,label,colour,center=True)
                y+=29


HANDLERS = {name: globals()[name] for name in PAGE_TITLES}


def reference_values(page, raw, element):
    """Reuse the single feed; do not add a second reader or guessed units.

    Unsupported engineering values deliberately remain absent. In particular,
    oil quantity ratio is not quarts, oxygen-mask state is not PSI and SD* array
    drawing codes are not generator volts, tank quantities or normal status.
    """
    from .toliss_ecam_telemetry import values
    return values(page, raw)


def draw(c, page, values):
    header(c,page)
    HANDLERS[page](c,values)
