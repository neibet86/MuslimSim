"""Audited ToLiss SD inputs (BUG-41/53), never photographic sample values.

Evidence and unresolved fields: docs/TOLISS_ECAM_TELEMETRY_AUDIT.md.
The live A321 1.8 API supplies types; absent/ill-shaped values stay unknown.
No commands, timers, aircraft-state simulation, or independent subscriptions.
"""
import math


DATAREFS = {
    "ref_cockpit_temp": "AirbusFBW/CockpitTemperature_degC",
    "ref_cabin_fwd": "AirbusFBW/CabinZone1Temperature_degC",
    "ref_cabin_aft": "AirbusFBW/CabinZone2Temperature_degC",
    "ref_cockpit_trim": "AirbusFBW/CockpitTrim",
    "ref_zone1_trim": "AirbusFBW/Zone1Trim",
    "ref_zone2_trim": "AirbusFBW/Zone2Trim",
    "ref_cockpit_selected_temp": "AirbusFBW/CockpitTemp",
    "ref_fwd_selected_temp": "AirbusFBW/FwdCabinTemp",
    "ref_aft_selected_temp": "AirbusFBW/AftCabinTemp",
    "ref_ac_buses": "AirbusFBW/ACBusVoltages",
    "ref_dc_buses": "AirbusFBW/DCBusVoltages",
    "ref_elec_connect_left": "AirbusFBW/SDELConnectLeft",
    "ref_elec_connect_right": "AirbusFBW/SDELConnectRight",
    "ref_du_brightness": "AirbusFBW/DUBrightness",
    "ref_du_selftest": "AirbusFBW/DUSelfTestTimeLeft",
    "ref_aircraft_path": "sim/aircraft/view/acf_relative_path",
    "ref_fuel_mass": "sim/flightmodel/weight/m_fuel",
    "ref_fuel_flow_kg_sec": "sim/cockpit2/engine/indicators/fuel_flow_kg_sec",
    "ref_fuel_used": "sim/cockpit2/fuel/fuel_totalizer_sum_engine_kg",
    "ref_oil_quantity": "sim/cockpit2/engine/indicators/oil_quantity_ratio",
    "ref_fuel_temp": "sim/cockpit2/fuel/fuel_temp_at_fuel_tank",
    "ref_oxygen_psi": "sim/cockpit2/oxygen/indicators/o2_bottle_pressure_psi",
    "ref_battery_amps": "sim/cockpit2/electrical/battery_amps",
    "ref_generator_amps": "sim/cockpit2/electrical/generator_amps",
    "ref_bus_load_amps": "sim/cockpit2/electrical/bus_load_amps",
    "ref_fuel_pumps": "AirbusFBW/FuelPumpOHPArray",
    "ref_fuel_auto_pumps": "AirbusFBW/FuelAutoPumpSDArray",
    "ref_fuel_crossfeed": "AirbusFBW/FuelXFVSDArray",
    "ref_pack_fcv_1": "AirbusFBW/Pack1FCVInd",
    "ref_pack_fcv_2": "AirbusFBW/Pack2FCVInd",
    "ref_ram_air": "AirbusFBW/RamAirValveSD",
    "ref_hot_air": "AirbusFBW/HotAirValve",
    "ref_cargo_isol_fwd": "AirbusFBW/FwdIsolValve",
    "ref_cargo_isol_aft": "AirbusFBW/AftIsolValve",
    "ref_safety_valve": "AirbusFBW/SafetyValve",
    "ref_hyd_pumps": "AirbusFBW/HydPumpArray",
    "ref_fcc": "AirbusFBW/FCCAvailArray",
    "ref_ail_l_avail": "AirbusFBW/LAilAvailArray",
    "ref_ail_r_avail": "AirbusFBW/RAilAvailArray",
    "ref_elev_l_avail": "AirbusFBW/LElevAvailArray",
    "ref_elev_r_avail": "AirbusFBW/RElevAvailArray",
    "ref_trim_powered": "AirbusFBW/PitchTrimPowered",
    "ref_cockpit_windows": "AirbusFBW/CockpitWindowPosition",
    "ref_slides_armed": "AirbusFBW/SlideArmedArray",
    "ref_tire_pressure": "AirbusFBW/TirePressureArray",
    **{
        f"ref_status_{row}_{colour}": f"AirbusFBW/SDline{row}{colour}"
        for row in range(1, 19) for colour in "garwb"
    },
}
TEXT_KEYS = frozenset(
    {"ref_aircraft_path"}
    | {f"ref_status_{row}_{colour}" for row in range(1, 19) for colour in "garwb"}
)
UNKNOWN = math.nan
PA_PER_PSI = 6894.757293
POWER_KEYS = ("ref_ac_buses", "ref_du_brightness", "ref_du_selftest")
# Precomputed once by the feed: an unrelated ND/engine update does not copy
# or fingerprint the whole feed on each BB35/BB36 refresh.
PAGE_EXTRA_KEYS = {
    "eng": ("ref_fuel_used", "ref_oil_quantity"),
    "apu": ("bleed_press_l", "bleed_press_r", "bleed_ambient_pressure_pa"),
    "fuel": ("ref_aircraft_path", "ref_fuel_mass", "ref_fuel_flow_kg_sec", "ref_fuel_used", "ref_fuel_temp",
             "ref_fuel_pumps", "ref_fuel_auto_pumps", "ref_fuel_crossfeed"),
    "cond": ("ref_cockpit_temp", "ref_cabin_fwd", "ref_cabin_aft", "ref_cockpit_trim", "ref_zone1_trim", "ref_zone2_trim", "ref_cockpit_selected_temp", "ref_fwd_selected_temp", "ref_aft_selected_temp", "ref_hot_air", "ref_cargo_isol_fwd", "ref_cargo_isol_aft"),
    "cruise": ("ref_cockpit_temp", "ref_cabin_fwd", "ref_cabin_aft"),
    "bleed": (
        "ref_pack_fcv_1", "ref_pack_fcv_2", "ref_ram_air", "eng_gen_n2",
        "ref_status_2_g", "ref_status_2_a",
        "ref_status_5_g", "ref_status_5_a",
        "ref_status_13_g", "ref_status_13_a",
    ),
    "elec": ("ref_dc_buses", "ref_elec_connect_left", "ref_elec_connect_right", "ref_battery_amps", "ref_generator_amps", "ref_bus_load_amps", "eng_gen_oiltemp"),
    "press": ("cruise_delta_p", "cond_vent_inlet", "cond_vent_extract", "ref_safety_valve"),
    "hyd": ("ref_hyd_pumps",),
    "door": ("ref_aircraft_path", "ref_cockpit_windows", "ref_slides_armed", "ref_oxygen_psi"),
    "fctl": ("ref_ail_l_avail", "ref_ail_r_avail", "ref_elev_l_avail", "ref_elev_r_avail", "ref_fcc", "ref_trim_powered"),
    "wheel": ("fctl_spoilers", "hyd_press", "hyd_altn_brake", "hyd_brake_accu", "ref_tire_pressure") + tuple(f"fctl_spoiler_{i}" for i in range(1,11)),
    "status": tuple(
        f"ref_status_{row}_{colour}"
        for row in range(1, 19) for colour in "garwb"
    ),
}


def scalar(raw, key):
    value = raw.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else UNKNOWN


def array(raw, key, index):
    values = raw.get(key)
    if not isinstance(values, (tuple, list)) or not 0 <= index < len(values):
        return UNKNOWN
    return scalar({key: values[index]}, key)


def _clamp_ratio(value):
    return max(0.0, min(1.0, value)) if math.isfinite(value) else UNKNOWN


def _gauge_pressure_psi(raw, key):
    """Convert ToLiss's absolute bleed pressure to the gauge value on the SD."""
    absolute = scalar(raw, key)
    ambient_pa = scalar(raw, "bleed_ambient_pressure_pa")
    if not math.isfinite(absolute) or not math.isfinite(ambient_pa) or ambient_pa < 0:
        return UNKNOWN
    return float(round(max(0.0, absolute - ambient_pa / PA_PER_PSI)))


def _sd_number(raw, row, start, end):
    """Read a number from its native fixed SD text columns, never another gauge."""
    green = raw.get(f"ref_status_{row}_g")
    amber = raw.get(f"ref_status_{row}_a")
    if not isinstance(green, str):
        return UNKNOWN
    green = green.replace("\x00", " ")
    amber = amber.replace("\x00", " ") if isinstance(amber, str) else ""
    if "X" in amber[start:end].upper():
        return UNKNOWN
    token = green[start:end].strip()
    if not token:
        return UNKNOWN
    try:
        value = float(token)
    except ValueError:
        return UNKNOWN
    return value if math.isfinite(value) else UNKNOWN


def _effective_engine_bleed(raw, engine, gauge_pressure):
    """Keep native fault codes; recover only ToLiss's observed stale zero."""
    native = scalar(raw, f"bleed_ind_{engine}")
    if native in (1.0, 2.0, 3.0):
        return native
    if native != 0.0:
        return UNKNOWN
    switch = scalar(raw, f"bleed_switch_{engine}")
    running = array(raw, "bleed_engine_running", engine - 1)
    n2 = array(raw, "eng_gen_n2", engine - 1)
    apu_supply = scalar(raw, "bleed_apu_ind")
    if (switch == 1.0 and running == 1.0 and math.isfinite(n2) and n2 > 50.0
            and apu_supply == 0.0 and math.isfinite(gauge_pressure)
            and gauge_pressure > 4.0):
        return 1.0
    return 0.0


def available(raw, key, count):
    values = [array(raw, key, i) for i in range(count)]
    if any(value == 1 for value in values):
        return 1.0
    return 0.0 if all(value == 0 for value in values) else UNKNOWN


def display_mode(raw, page):
    """Real DU countdown, not a made-up timer on app start or page selection.

    All these displays need an AC supply. Charged BAT/HotBus alone is not
    proof of that supply. Individual AC-bus routing remains an audit item.
    """
    buses = raw.get("ref_ac_buses")
    if not isinstance(buses, (list, tuple)) or not any(
        isinstance(v, (int, float)) and math.isfinite(v) and v > 1 for v in buses
    ):
        return "off"
    index = {"pfd": 0, "nd": 1, "cdu": 6}.get(page, 5)
    brightness = array(raw, "ref_du_brightness", index)
    remaining = array(raw, "ref_du_selftest", index)
    if not math.isfinite(brightness) or brightness <= 0 or not math.isfinite(remaining) or remaining < 0:
        return "off"
    return "selftest" if remaining > 0 else "ready"


def values(page, raw):
    """Authoritative overrides of the legacy guessed translations.

    Every call is bounded to the selected page. Never walks the catalogue.
    Missing engineering exports are deliberately not filled from generic
    values known to disagree with ToLiss (oxygen, battery amps, GPU volts).
    """
    out = {}
    # BUG-44 owner policy: a live, physically equivalent simulator value is
    # preferable to a blank field when ToLiss does not export the exact SD
    # validity bit. Keep the generic X-Plane TAT/SAT and loaded mass supplied
    # by _toliss_ecam_common_values; never replace them with picture constants.
    a321 = "tolissa321" in str(raw.get("ref_aircraft_path", "")).lower()
    if page == "cruise":
        out.update(cruise_fwd_temp=scalar(raw, "ref_cabin_fwd"),
                   cruise_aft_temp=scalar(raw, "ref_cabin_aft"))
    if page == "cond":
        out.update(cond_cockpit_temp=scalar(raw, "ref_cockpit_temp"),
                   cond_fwd_cabin_temp=scalar(raw, "ref_cabin_fwd"),
                   cond_aft_cabin_temp=scalar(raw, "ref_cabin_aft"),
                   # These are the three live cockpit selector targets. The
                   # undocumented *Trim ratios remain subscribed for audit,
                   # but a 0..1 trim ratio is not a temperature gauge value.
                   cond_duct_ckpt=scalar(raw, "ref_cockpit_selected_temp"),
                   cond_duct_fwd=scalar(raw, "ref_fwd_selected_temp"),
                   cond_duct_aft=scalar(raw, "ref_aft_selected_temp"),
                   cond_hot_air=scalar(raw, "ref_hot_air"),
                   cond_fwd_cargo_temp=scalar(raw, "cond_fwd_cargo_temp"),
                   cond_aft_cargo_temp=scalar(raw, "cond_aft_cargo_temp"),
                   cond_cargo_hot_air=scalar(raw, "cond_cargo_hot_air"),
                   cond_fwd_isol=scalar(raw, "ref_cargo_isol_fwd"),
                   cond_aft_isol=scalar(raw, "ref_cargo_isol_aft"))
    if page in ("eng", "fuel"):
        for i in range(2):
            # X-Plane totalizer is an explicit fallback, pending burn check.
            out[f"eng_used_{i}"] = array(raw, "ref_fuel_used", i)
    if page == "eng":
        for i in range(2):
            powered = array(raw, "eng_fadec", i)
            out[f"eng_fadec_valid_{i}"] = powered
            if not math.isfinite(powered) or powered <= 0:
                for name in ("oil_qt", "oilpress", "oiltemp", "vib", "vib_n2"):
                    out[f"eng_{name}_{i}"] = UNKNOWN
            else:
                oil_ratio = array(raw, "ref_oil_quantity", i)
                # Provisional A321 conversion: the live 0.85 ratio aligns with
                # the native ~14 QT indication on a 16.5-quart display range.
                out[f"eng_oil_qt_{i}"] = oil_ratio * 16.5
                n1 = array(raw, "eng_gen_n1", i)
                n2 = array(raw, "eng_gen_n2", i)
                # ToLiss publishes no calibrated vibration dataref. Keep these
                # live and moving from engine speeds until native sweeps can
                # establish a better curve; never use picture constants.
                out[f"eng_vib_{i}"] = n1 / 70.0 if math.isfinite(n1) else UNKNOWN
                out[f"eng_vib_n2_{i}"] = n2 / 115.0 if math.isfinite(n2) else UNKNOWN
    elif page == "apu":
        if scalar(raw, "apu_master") != 1:
            out.update(apu_n_pct=UNKNOWN, apu_egt=UNKNOWN, apu_bleed_press=UNKNOWN)
        elif scalar(raw, "apu_bleed_ind") == 1:
            pressures = [_gauge_pressure_psi(raw, key) for key in ("bleed_press_l", "bleed_press_r")]
            known = [value for value in pressures if math.isfinite(value)]
            out["apu_bleed_press"] = sum(known) / len(known) if known else UNKNOWN
    elif page == "bleed":
        out["bleed_ram"] = scalar(raw, "ref_ram_air")
        out["bleed_intercon"] = scalar(raw, "bleed_intercon")
        out["bleed_ground_hp"] = scalar(raw, "bleed_ground_hp")
        out["bleed_ground_lp"] = scalar(raw, "bleed_ground_lp")
        sd_columns = {
            1: ((2, 4, 7), (5, 4, 7), (13, 5, 8)),
            2: ((2, 26, 29), (5, 26, 29), (13, 27, 30)),
        }
        for i in (1, 2):
            out[f"bleed_pack_switch_{i}"] = scalar(raw, f"ref_pack_fcv_{i}")
            # PackTemp is the upper-arc pointer, while PackFlow's 0.8..1.2
            # native range is the lower-arc pointer. Neither is a temperature.
            out[f"bleed_pack_pointer_{i}"] = _clamp_ratio(
                scalar(raw, f"bleed_pack{i}_temp")
            )
            flow = scalar(raw, f"bleed_pack{i}_flow")
            out[f"bleed_pack_flow_{i}"] = _clamp_ratio((flow - 0.8) * 2.5) \
                if math.isfinite(flow) else UNKNOWN
            top, compressor, duct = sd_columns[i]
            out[f"bleed_pack_temp_{i}"] = _sd_number(raw, *top)
            out[f"bleed_pack_outlet_{i}"] = _sd_number(raw, *compressor)
            out[f"bleed_temp_{i}"] = _sd_number(raw, *duct)
            pressure_key = "bleed_press_l" if i == 1 else "bleed_press_r"
            pressure = _gauge_pressure_psi(raw, pressure_key)
            out[pressure_key] = pressure
            out[f"bleed_ind_{i}"] = _effective_engine_bleed(raw, i, pressure)
    elif page == "press":
        mode_lights = scalar(raw, "press_mode_lights")
        out.update(press_delta_p=scalar(raw, "cruise_delta_p"),
                   press_ldg_elev=UNKNOWN,  # Selector has no FMGC validity bit.
                   # Provisional ToLiss encoding observed with AUTO/SYS2:
                   # CabPressModeLights==1. Preserve unknown for other codes.
                   press_active_system=2.0 if mode_lights == 1 else
                                       1.0 if mode_lights == 0 else UNKNOWN,
                   press_inlet=scalar(raw, "cond_vent_inlet"),
                   press_extract=scalar(raw, "cond_vent_extract"),
                   press_safety=scalar(raw, "ref_safety_valve"))
    elif page == "elec":
        # SDELEC/SDELECDC are scalar page buttons and ElecOHPArray is switches,
        # but ToLiss publishes real bus/battery measurements and source
        # connection bitfields separately. XHSI's QPAC decoder documents bit 0
        # of SDELConnectLeft/Right and the SDACCrossConnect source codes.
        def powered(key, index):
            voltage = array(raw, key, index)
            return float(voltage > 1) if math.isfinite(voltage) else UNKNOWN

        def connected(value, mask=1):
            if not math.isfinite(value) or value < 0 or not float(value).is_integer():
                return UNKNOWN
            return float(bool(int(value) & mask))

        for i in (0, 1):
            out[f"elec_bat_v_{i}"] = array(raw, "elec_bat_volts", i)
            out[f"elec_bat_a_{i}"] = array(raw, "ref_battery_amps", i)
        out.update(
            elec_ac_bus_1=powered("ref_ac_buses", 0),
            elec_ac_bus_2=powered("ref_ac_buses", 1),
            elec_ac_ess=powered("ref_ac_buses", 2),
            elec_dc_bus_1=powered("ref_dc_buses", 0),
            elec_dc_bus_2=powered("ref_dc_buses", 1),
            elec_dc_bat=powered("ref_dc_buses", 2),
            elec_dc_ess=powered("ref_dc_buses", 3),
            elec_gen_1=connected(scalar(raw, "ref_elec_connect_left")),
            elec_gen_2=connected(scalar(raw, "ref_elec_connect_right")),
            # Provisional engineering values: the energized AC/DC bus voltage
            # is the best live value available downstream of each GEN/TR.
            elec_tr_v_1=array(raw, "ref_dc_buses", 0),
            elec_tr_v_2=array(raw, "ref_dc_buses", 1),
        )
        for i in (1, 2):
            connected_gen = out[f"elec_gen_{i}"]
            out[f"elec_gen_v_{i}"] = (
                array(raw, "ref_ac_buses", i - 1) if connected_gen == 1
                else 0.0 if connected_gen == 0 else UNKNOWN
            )
            amps = array(raw, "ref_generator_amps", i - 1)
            # Provisional 300 A full-scale conversion for the ECAM percent
            # field. It remains explicitly derived from a changing live amp
            # source, not a photographed load value.
            out[f"elec_gen_load_{i}"] = amps / 3.0 if math.isfinite(amps) else UNKNOWN
            out[f"elec_gen_hz_{i}"] = 400.0 if connected_gen == 1 else 0.0 if connected_gen == 0 else UNKNOWN
            out[f"elec_tr_a_{i}"] = array(raw, "ref_bus_load_amps", i + 1)
            # No IDG-temperature export exists in this ToLiss catalogue. The
            # live engine oil temperature is the owner's requested provisional
            # moving proxy until native comparisons establish a calibrated map.
            out[f"elec_idg_temp_{i}"] = array(raw, "eng_gen_oiltemp", i - 1)
        cross = scalar(raw, "elec_ac_cross")
        if math.isfinite(cross) and cross >= 0 and float(cross).is_integer():
            source = int(cross)
            out.update(elec_apu_gen=float(source in (1, 2, 3)),
                       elec_ext_pow=float(source in (4, 5, 6)),
                       elec_ac_tie=float(source in (3, 6, 7)))
        else:
            out.update(elec_apu_gen=UNKNOWN, elec_ext_pow=UNKNOWN,
                       elec_ac_tie=UNKNOWN)
    elif page == "hyd":
        for i, name in enumerate("gby"):
            out["hyd_pump_" + name] = array(raw, "ref_hyd_pumps", i)
        for name, index in (("g", 0), ("y", 2)):
            pressure = array(raw, "hyd_press", index)
            out["hyd_fire_valve_" + name] = float(pressure >= 1450) if math.isfinite(pressure) else UNKNOWN
    elif page == "fuel":
        for i, name in ((1, "l"), (0, "ctr"), (2, "r")):
            out["fuel_qty_" + name] = array(raw, "ref_fuel_mass", i) if a321 else UNKNOWN
        for i in (0, 1):
            out[f"fuel_flow_kg_min_{i}"] = array(raw, "ref_fuel_flow_kg_sec", i) * 60
            out[f"fuel_lp_code_{i}"] = array(raw, "fuel_lp_valve", i)
        out["fuel_crossfeed_code"] = array(raw, "ref_fuel_crossfeed", 0)
        out["fuel_temp_l"] = array(raw, "ref_fuel_temp", 1) if a321 else UNKNOWN
        out["fuel_temp_r"] = array(raw, "ref_fuel_temp", 2) if a321 else UNKNOWN
        for i in range(6):
            key = "ref_fuel_auto_pumps" if i in (2,3) else "ref_fuel_pumps"
            out[f"fuel_pump_code_{i}"] = array(raw, key, i)
    elif page == "door":
        for name, index in (("exit_l", 4), ("exit_r", 5), ("aft_l", 6), ("aft_r", 7)):
            out["door_" + name] = array(raw, "door_pax", index) if a321 else UNKNOWN
        for i in range(2):
            out[f"door_window_{i}"] = array(raw, "ref_cockpit_windows", i)
        for i in range(8):
            out[f"door_slide_{i}"] = array(raw, "ref_slides_armed", i)
        # CockpitDoorLockState describes the security door, not nose/windows.
        out["door_cockpit"] = UNKNOWN
        # X-Plane exposes one live cockpit oxygen bottle. Until ToLiss exports
        # independent bottles, feed both displayed positions from that sensor.
        out["door_oxy_psi_1"] = scalar(raw, "ref_oxygen_psi")
        out["door_oxy_psi_2"] = scalar(raw, "ref_oxygen_psi")
    if page in ("fctl", "wheel"):
        for i in range(1, 11):
            out[f"{page}_spoiler_{i}"] = scalar(raw, f"fctl_spoiler_{i}")
            out[f"{page}_spoiler_status_{i}"] = array(raw, "fctl_spoilers", i-1)
    if page == "wheel":
        # Supply-derived indications, not independent BSCU fault simulation.
        # Full ToLiss fault/discrete mapping remains in the acceptance audit.
        def supply(index):
            pressure=array(raw,"hyd_press",index)
            return float(pressure>=1450) if math.isfinite(pressure) else UNKNOWN
        green,yellow=supply(0),supply(2)
        switch=scalar(raw,"wheel_antiskid")
        alternate=scalar(raw,"hyd_altn_brake")
        normal=(0.0 if green==0 or alternate==1 or switch==0 else
                1.0 if green==1 and alternate==0 and switch==1 else UNKNOWN)
        skid=(0.0 if switch==0 or (green==0 and yellow==0) else
              1.0 if switch==1 and (green==1 or yellow==1) else UNKNOWN)
        auto=(0.0 if normal==0 or skid==0 else 1.0 if normal==1 and skid==1 else UNKNOWN)
        accu=scalar(raw,"hyd_brake_accu")
        accu_only=(1.0 if normal==0 and yellow==0 and accu==1 else
                   0.0 if normal==1 or yellow==1 or accu==0 else UNKNOWN)
        out.update(wheel_g_available=green,wheel_y_available=yellow,
                   wheel_norm_available=normal,wheel_alt_available=yellow,
                   wheel_skid_available=skid,wheel_auto_available=auto,
                   wheel_accu_only=accu_only)
        # Provisional installed-aircraft order: the A321 exposes a 16-slot
        # compatibility array; its first two entries are nose wheels and the
        # next four are main wheels. Live values are used without constants.
        for i in range(6):
            out[f"wheel_tire_{i}"] = array(raw, "ref_tire_pressure", i)
    if page == "status":
        rows = []
        for row in range(1, 19):
            layers = tuple(
                (colour, str(raw.get(f"ref_status_{row}_{colour}", "")))
                for colour in "garwb"
                if str(raw.get(f"ref_status_{row}_{colour}", "")).strip()
            )
            if layers:
                rows.append((row, layers))
        out["status_rows"] = tuple(rows)
        # ToLiss publishes five colour layers for every native STATUS line.
        # A completely empty set means no deferred status item in the current
        # aircraft version and is the best available NORMAL indication.
        out["status_normal"] = not rows
    if page == "fctl":
        for name, key, count in (("aileron_l", "ref_ail_l_avail", 3),
                                 ("aileron_r", "ref_ail_r_avail", 3),
                                 ("elevator_l", "ref_elev_l_avail", 2),
                                 ("elevator_r", "ref_elev_r_avail", 2),
                                 ("rudder", "fctl_rudder_avail", 4)):
            out[f"fctl_{name}_available"] = available(raw, key, count)
        for i in range(5):
            out[f"fctl_fcc_{i}"] = array(raw, "ref_fcc", i)
        out["fctl_trim_powered"] = scalar(raw, "ref_trim_powered")
    return out
