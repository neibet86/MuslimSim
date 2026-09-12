"""MuslimSim Studio: a visual, no-console hardware configuration surface.

This is intentionally a device studio rather than a generic list of HID
fields.  It presents a working faceplate, identifies the few unassigned
physical contacts visually, and binds verified inputs to simulator functions.
The bridge remains the child process and the sole owner of input handles.
"""

from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path as _FaultPath
import queue
import re
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ..control.client import ControlClientError
from ..hardware.catalog import catalogue_snapshot, runtime_control_by_key
from ..hardware.discovery import canonical_device_key, discover_hid_devices, hardware_presence
from ..hardware.msfs24_library import offline_msfs24_functions, search_msfs24_functions
from ..hardware.msfs24_aircraft import (
    msfs24_aircraft, msfs24_aircraft_title, msfs24_brands, msfs24_family,
)
from ..hardware.moza_presets import (
    MOZA_UI_PRESETS,
    effective_calibration as effective_moza_calibration,
    presets_for_device as moza_presets_for_device,
)
from ..hardware.toliss_throttle_calibration import (
    DETENT_LABELS as TOLISS_THROTTLE_DETENT_LABELS,
    DETENT_ORDER as TOLISS_THROTTLE_DETENT_ORDER,
    RAW_AXIS_MAX as TOLISS_THROTTLE_RAW_AXIS_MAX,
    default_calibration as default_toliss_throttle_calibration,
    normalise_calibration as normalise_toliss_throttle_calibration,
)
from ..hardware.virtual_zibo import VirtualZiboPreview
from ..hardware.xplane_library import (
    aircraft_title as xplane_aircraft_title,
    offline_xplane_functions,
    search_xplane_functions,
)
from .live_feedback import (
    compose_live_mirror,
    physical_input_active,
)
from ..devices.ecam32 import (
    ECAM32_A320_CONTROLS,
    ECAM32_A320_PAGE_KEYS,
    ECAM32_CAPTURED_CONTACT_LED_INDEX,
)
from .supervisor import (
    AIRCRAFT_C172_NG, AIRCRAFT_LEVELUP, AIRCRAFT_TOLISS, AIRCRAFT_ZIBO,
    BridgeSupervisor, SIMULATOR_MSFS24, SIMULATOR_XPLANE,
)

# MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
# V5+ uses bridge-owned coordinated Practice output authority. The old
# selected-page wake heartbeat is intentionally retired; physical telemetry
# remains independent and the bridge starts/releases the verified output group.

# MUSLIMSIM_MOZA_AB6_CAPTURE_V1
# The eight axes both Moza bases declare. Kept in one place because the
# AB6's seed pose listed only three of them, and the first live report
# publishing all eight raised KeyError and blanked its whole page.
MOZA_AXIS_KEYS = (
    "axis_x", "axis_y", "axis_z", "axis_rx", "axis_ry", "axis_rz",
    "axis_slider", "axis_dial",
)

# MUSLIMSIM_MOZA_AY210_FFB_PHYSICS_V1
# The seven real MOZA Cockpit gain parameters found this session (one
# Cockpit slider at a time, live USB capture, correlated to its own
# firmware log line) - see muslimsim/hardware/moza_ay210_ffb_engine.py's
# PHYSICS_FIELD_TO_GAIN_PARAM for the raw bytes. Unlike the rest of this
# panel's legacy calibration UI (moza_presets.py, local-only, never sent to
# hardware), these seven ARE genuinely wired: every adjustment here reaches
# the AY210 FFB engine's set_physics_override() over the same
# "device_command" RPC the axis-assignment dialog already uses.
MOZA_FFB_PHYSICS_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("Spring", "spring_gain"),
    ("Damper", "damper"),
    ("Inertia", "inertia"),
    ("Friction", "friction"),
    ("Overall Force Feedback Intensity", "overall_intensity"),
    ("Maximum Torque Output", "max_torque"),
    ("Friction Compensation Strength", "friction_compensation"),
)
# The two mapping-presets built from real owner-supplied MOZA Cockpit
# presets ("...tony v1.2") - see muslimsim/hardware/ffb_profiles.py's
# PRESETS. Keyed by the *old* moza_presets.py preset_id already shown on
# this panel's preset cards, so selecting one there also asks the real FFB
# engine to load the corresponding `.mslm` profile.
MOZA_FFB_PRESET_ID_TO_MSLM: Dict[str, str] = {
    "a210_ifly_b737max_msfs2024": "b737_max_tony",
    "a210_pmdg_b777_msfs2024": "b777_tony",
}

# MUSLIMSIM_CONNECTION_BANNER_V1
# Transient control-channel states. They are footer text, so nothing ever
# took them down again: three failed polls during bridge startup - 0.3 s at
# ten polls a second - left "waiting for its live update" on screen for the
# rest of the session, long after the status poll had recovered.
BANNER_WAITING_UPDATE = "Waiting for the latest hardware update…"
BANNER_STILL_CONNECTED = "Hardware is still connected; waiting for its live update…"
BANNER_SERVICE_STOPPED = "Hardware service stopped; reconnecting devices…"
CONNECTION_BANNERS = (
    BANNER_WAITING_UPDATE,
    BANNER_STILL_CONNECTED,
    BANNER_SERVICE_STOPPED,
)
CONNECTION_RECOVERED_FOOTER = "Select a device to begin."


BG = "#0a1020"
PANEL = "#151f34"
PANEL_ALT = "#1d2942"
INK = "#eaf1ff"
MUTED = "#92a3c4"
ACCENT = "#4fd1c5"
BLUE = "#5aa9ff"
WARN = "#ffbf69"
DANGER = "#ff7070"

# Faceplates are drawn on one stable design surface.  Growing the desktop
# window adds breathing room around a panel; it never stretches one control
# away from another.  The minimum Studio window keeps this entire surface
# visible instead of allowing a small resize to pile text and buttons on top
# of each other.
FACEPLATE_DESIGN_WIDTH = 980
FACEPLATE_DESIGN_HEIGHT = 680


# Owner photographs confirm the P7 outputs are recessed *annunciator lenses*,
# not round indicator dots.  Their labels and colours match the already
# captured 32-bit P7 order in the existing PU serial driver.  Coordinates are
# percentage centres in the photographed panel, so the entire group scales
# with the Studio faceplate without a bitmap asset.
PU_ANNUNCIATOR_LAYOUT: tuple[tuple[int, str, float, float, float, float, str], ...] = (
    (0, "GPS", 3.3, 2.0, 4.5, 3.1, "red"),
    (1, "ALIGN", 8.0, 2.0, 4.8, 3.1, "red"),
    (2, "ON DC", 12.9, 2.0, 4.8, 3.1, "red"),
    (3, "ALIGN", 17.8, 2.0, 4.8, 3.1, "red"),
    (4, "ON DC", 22.7, 2.0, 4.8, 3.1, "red"),
    (5, "LOW\nPRESS", 8.5, 39.4, 5.4, 4.2, "red"),
    (6, "LOW\nPRESS", 14.2, 39.4, 5.4, 4.2, "red"),
    (7, "LOW\nPRESS", 5.8, 56.4, 5.4, 4.2, "red"),
    (8, "LOW\nPRESS", 11.7, 56.4, 5.4, 4.2, "red"),
    (9, "LOW\nPRESS", 17.5, 56.4, 5.4, 4.2, "red"),
    (10, "LOW\nPRESS", 22.5, 56.4, 5.4, 4.2, "red"),
    (11, "YAW\nDAMPER", 31.9, 1.0, 5.8, 3.8, "red"),
    (12, "GRD PWR\nAVAIL", 37.5, 2.4, 5.8, 3.8, "blue"),
    (13, "TRANSFER\nBUS OFF", 29.3, 26.5, 6.4, 4.8, "red"),
    (14, "TRANSFER\nBUS OFF", 45.9, 28.4, 6.4, 4.8, "red"),
    (15, "SOURCE\nOFF", 29.3, 31.4, 6.1, 4.1, "red"),
    (16, "SOURCE\nOFF", 45.9, 33.2, 6.1, 4.1, "red"),
    (17, "GEN OFF\nBUS", 29.3, 36.8, 5.8, 4.2, "blue"),
    (18, "APU GEN\nOFF BUS", 37.2, 34.1, 6.5, 4.3, "blue"),
    (19, "GEN OFF\nBUS", 44.9, 36.8, 5.8, 4.2, "blue"),
    (20, "MAINT", 29.6, 55.1, 5.5, 3.7, "white"),
    (21, "LOW OIL\nPRESS", 35.0, 55.1, 5.8, 3.7, "red"),
    (22, "FAULT", 40.2, 55.1, 5.3, 3.7, "red"),
    (23, "OVER\nSPEED", 44.7, 55.1, 5.5, 3.7, "red"),
    (24, "ON", 55.4, 2.7, 4.4, 3.1, "green"),
    (25, "ON", 60.1, 2.7, 4.4, 3.1, "green"),
    (26, "ON", 64.8, 2.7, 4.4, 3.1, "green"),
    (27, "ON", 69.5, 2.7, 4.4, 3.1, "green"),
    (28, "LOW\nPRESS", 54.0, 36.8, 5.5, 3.7, "red"),
    (29, "LOW\nPRESS", 59.3, 36.8, 5.5, 3.7, "red"),
    (30, "LOW\nPRESS", 64.8, 36.8, 5.5, 3.7, "red"),
    (31, "LOW\nPRESS", 70.1, 36.8, 5.5, 3.7, "red"),
)

PU_TOGGLE_KEYS = frozenset({
    "fuel_ctr_l", "fuel_ctr_r", "fuel_l_fwd", "fuel_l_aft", "fuel_r_aft", "fuel_r_fwd", "yaw_damper",
    "window_heat_r_fwd", "window_heat_l_fwd", "window_heat_l_side", "window_heat_r_side",
    "probe_heat_capt", "probe_heat_fo", "wing_anti_ice", "eng1_anti_ice", "eng2_anti_ice",
    "hyd_elec2", "hyd_elec1", "hyd_eng2", "hyd_eng1", "bleed_air_1", "bleed_air_apu", "bleed_air_2",
    "landing_light_left", "landing_light_right", "runway_turnoff_left", "runway_turnoff_right", "taxi_light",
    "logo_light", "beacon_light", "wing_light",
})

# Values are the same stable positions published by the real SDL decoder.
PU_SELECTOR_VALUES: Dict[str, tuple[int, ...]] = {
    "irs_left": (0, 1, 2, 3), "irs_right": (0, 1, 2, 3), "wiper_selector": (0, 1, 2, 3),
    "no_smoking": (0, 2), "fasten_belts": (0, 1, 2), "l_pack": (0, 1, 2),
    "isolation_valve": (0, 1, 2), "r_pack": (0, 1, 2), "apu_start": (0, 1, 2),
    "engine_start_1": (0, 1, 2, 3), "ignition_source": (-1, 0, 1), "engine_start_2": (0, 1, 2, 3),
    "position_lights": (-1, 0, 1),
}


# These are output-test items, not virtual inputs.  They are intentionally
# kept outside the mapping source list: a light or motor cannot accidentally
# become a simulator command.  Clicks travel only through the local loopback
# laboratory channel to the capture-confirmed B930 driver.
WINCTRL_THROTTLE_OUTPUT_KEYS = frozenset({
    "throttle_backlight", "flaps_airbrake_backlight", "trim_display_backlight",
    "engine_1_fault_light", "engine_1_fire_light",
    "engine_2_fault_light", "engine_2_fire_light",
    "vibration_motor_1", "vibration_motor_2",
})
WINCTRL_THROTTLE_OUTPUT_DEFAULTS: Dict[str, int] = {
    "throttle_backlight": 0x33,
    "flaps_airbrake_backlight": 0x33,
    "trim_display_backlight": 0xFF,
    "engine_1_fault_light": 0,
    "engine_1_fire_light": 0,
    "engine_2_fault_light": 0,
    "engine_2_fire_light": 0,
    "vibration_motor_1": 0,
    "vibration_motor_2": 0,
}


# AGP A320 contacts are now named directly from the hardware map.  Kept as an
# empty legacy table only so profiles saved during the short Capture-only
# period can still open and migrate cleanly.
AGP_CAPTURE_TARGETS: Dict[str, str] = {}


# Devices whose remaining "unknown"/"unimplemented" catalog entries are
# confirmed spare hardware bits with a fixed, already-known electrical
# identity (generated by catalog.py's own _unknown_bits() helper, or - for
# tca_boeing - its equivalent hand-authored per-index table).  Exactly which
# physical HID position produces raw_bit_N/raw_button_N/bankNN_button_N never
# changes; only its real-world meaning was never confirmed.  That is a
# fundamentally different situation from ECAM32 (see _CAPTURE_LIVE_DISCOVERY_
# DEVICES below), where the raw identity itself is only known once observed
# live.  For every device here, no physical-press "Capture" step is needed at
# all: exposing the entry as an ordinary visual control lets the owner assign
# it a simulator function immediately, the same way every other already-named
# control on the same device already works, and discover which physical
# button it is simply by pressing things and watching the 2D panel light up.
#
# Limited to devices where the live bridge reader is confirmed to actually
# forward that exact raw_bit_N/raw_button_N/bankNN_button_N event today (see
# each device's own hardware_lab.input() call in bridge/final.py /
# devices/pdc_bb62.py) - not merely declared as a catalog placeholder.
# pu_overhead's one remaining unknown bit and winctrl_throttle's ~59 are
# still catalog-only: their SDL reader loops do not yet publish an unmapped
# button index as any kind of diagnostic (winctrl_throttle's loop caps at
# button_no 41, which does not even match the catalog's own declared 96-bit
# range), so listing them here would let the owner "map" a control that can
# never actually fire - a worse trap than leaving it out. Add a device only
# once its reader is confirmed to publish the fallback, the same way AGP/
# PDC/PAP3/TCA already do.
_EXPOSE_UNVERIFIED_CONTROLS = frozenset({
    "agp_bb80", "pdc_bb62", "pap3_mag", "tca_boeing",
})

# Individual (device, key) pairs that must stay excluded even though their
# catalog status is "unknown"/"unimplemented" - each is a legacy control
# superseded by its own separately captured replacements, not a spare bit.
# Exposing it too would just duplicate an existing, already-working control.
_LEGACY_SUPERSEDED_CONTROLS = frozenset({
    ("winctrl_throttle", "flaps"),
})

# Devices where a physical press must genuinely be observed before its raw
# HID identity is known at all (the matrix/scan wiring behind a given labelled
# button was never enumerated ahead of time), so a one-time Capture step is
# the only way to learn which live control name a specific button produces.
# Every other device's remaining unknowns already have a fixed, catalog-known
# identity (see _EXPOSE_UNVERIFIED_CONTROLS above) and need no such step.
_CAPTURE_LIVE_DISCOVERY_DEVICES = frozenset({"ecam32"})

# The exact live-diagnostic naming each _CAPTURE_LIVE_DISCOVERY_DEVICES
# driver publishes for a contact it has just observed for the first time
# (mirrors catalog.py's own _ECAM32_CAPTURE_CONTROL - kept as a separate
# literal here since Studio must recognise this live-protocol detail even if
# the catalog copy is ever renamed). Adding a future live-discovery device
# only needs one entry here plus one in _CAPTURE_LIVE_DISCOVERY_DEVICES -
# nothing in _process_physical_events()/_start_live_capture() is hardcoded
# to a device name.
_CAPTURE_RAW_PATTERN: Dict[str, "re.Pattern[str]"] = {
    "ecam32": re.compile(r"^raw_r[0-9a-f]{2}_b[0-9]{2}_bit[0-7]$"),
}

# ECAM32_A320_CONTROLS entries with no drawn location on the faceplate
# diagram - the panel photo/legend only confirms eighteen positions plus the
# two blank keycaps that already had an empty filler cell, so a genuinely
# unplaced control reaches the "Other physical contact" picker instead of a
# guessed pixel position (see _draw_ecam32's grid in muslimsim/gui/studio.py).
_ECAM32_OFF_PANEL_CONTROLS = frozenset({"ecam_blank_3", "ecam_blank_4"})


# These panels can be installed for either crew member.  A physical device
# remains one device; the switch below supplies its virtual cockpit companion
# rather than pretending that another USB unit is attached.
# PDC keys are all included — Studio is the authority on which PDC is Captain
# and which is FO, regardless of how WinCtrl has the panel configured.
SIDE_CAPABLE_DEVICES = frozenset({
    "pdc_bb51", "pdc_bb62", "pdc_bb61_left", "pdc_bb52_right",
    "pfp3n_bb35", "mcdu32_bb36",
})
CAPTAIN_SIDE = "Captain / left"
FIRST_OFFICER_SIDE = "First officer / right"

# Path to the persisted panel role assignments — user-controlled, survives restarts.
_PANEL_ROLES_PATH = _FaultPath(__file__).parent.parent.parent / "config" / "panel_roles.json"
_PDC_ROLES_PATH = _FaultPath(__file__).parent.parent.parent / "config" / "pdc_roles.json"  # legacy, read-only


class MuslimSimStudio(tk.Tk):
    """A stable visual front-end for laboratory configuration."""

    def __init__(self, supervisor: Optional[BridgeSupervisor] = None) -> None:
        super().__init__()
        self.supervisor = supervisor or BridgeSupervisor()
        self.title("MuslimSim Studio")
        self.geometry("1760x940")
        # Below this width the old fluid canvas would compress labels and
        # controls together.  A professional panel should keep its physical
        # geometry, so Windows simply stops the resize at this safe size.
        self.minsize(1650, 900)
        self.configure(bg=BG)
        self._catalog = {item["key"]: item for item in catalogue_snapshot()["devices"]}
        # Live-feedback lookup is built once.  Drawing hundreds of controls at
        # 10 Hz must not rescan the entire catalogue merely to learn whether a
        # control is a button, selector, rotary or axis.
        self._control_kinds: Dict[str, Dict[str, str]] = {
            str(device_key): {
                str(control.get("key") or ""): str(control.get("kind") or "")
                for control in dict(spec).get("controls", ())
                if isinstance(control, dict) and control.get("key")
            }
            for device_key, spec in self._catalog.items()
        }
        self._detected: Dict[str, Dict[str, Any]] = {}
        self._local_detected: Dict[str, Dict[str, Any]] = {}
        self._bridge_detected: Dict[str, Dict[str, Any]] = {}
        self._bridge_inventory: Dict[str, Dict[str, Any]] = {}
        self._selected_device = ""
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        self._practice_wake_device: Optional[str] = None
        self._practice_wake_sent = 0.0
        self._cockpit_sides: Dict[str, str] = {
            "pdc_bb51": CAPTAIN_SIDE,
            "pdc_bb62": FIRST_OFFICER_SIDE,
            "pdc_bb61_left": CAPTAIN_SIDE,
            "pdc_bb52_right": FIRST_OFFICER_SIDE,
            "pfp3n_bb35": CAPTAIN_SIDE,
            "mcdu32_bb36": CAPTAIN_SIDE,
        }
        self._load_panel_roles()
        self._selected_visual: Optional[str] = None
        self._profile: Dict[str, Any] = {}
        self._lab: Dict[str, Any] = {}
        self._device_states: Dict[str, Dict[str, Any]] = {}
        self._device_enabled: Dict[str, bool] = {}
        self._preview = VirtualZiboPreview()
        self._preview_snapshot: Dict[str, Dict[str, Any]] = dict(self._preview.snapshot())
        self._preview_output_signature = ""
        self._practice_outputs_dirty = True
        # TCA Practice uses the same raw convention as the proven SDL reader:
        # +1.0 is the bottom/rest stop and -1.0 is full travel.  These six
        # independent poses let one selected quadrant or a complete two-unit
        # set be represented without changing the physical reader.
        self._tca_practice_axes: Dict[str, float] = {
            f"bank{bank}_axis_{axis}": 1.0
            for bank in ("12", "34")
            for axis in (3, 4, 5)
        }
        self._tca_axis_tracks: Dict[str, Dict[str, Any]] = {}
        self._tca_drag_axis: Optional[str] = None
        # Pointer motion may be much faster than the loopback channel.  One
        # background drain keeps only the newest value and publishes it at the
        # same 15 ms cadence as the live TCA reader.  It never redraws Tk.
        self._tca_route_lock = threading.Lock()
        self._tca_route_latest: Dict[str, tuple[int, float, str, int]] = {}
        self._tca_route_sequence = 0
        self._tca_route_epoch = 0
        self._tca_route_worker_running = False
        self._learning: Optional[str] = None
        self._learning_started = 0.0
        self._latest_diagnostic = 0.0
        self._flash_until: Dict[str, float] = {}
        self._fcu_values: Dict[str, int] = {
            "speed": 250, "heading": 90, "altitude": 10000, "vs": 0,
        }
        # A local faceplate cache also keeps real BA01 inputs visibly alive
        # in Live mode, where the hardware supplies input edges but does not
        # publish selector-position telemetry.
        self._fcu_efis_visual: Dict[str, Dict[str, Any]] = {
            side: {
                "unit": "inhg", "std": False, "mode": "nav", "range": 40,
                "nav1": "off", "nav2": "off",
                "buttons": {
                    "fd": False, "ls": False, "cstr": False, "wpt": False,
                    "vord": False, "ndb": False, "arpt": False,
                },
            }
            for side in ("left", "right")
        }
        self._pap3_values: Dict[str, int] = {
            "course_capt": 0, "speed": 250, "heading": 90,
            "altitude": 10000, "vertical_speed": 0, "course_fo": 0,
        }
        self._agp_page = "clock"
        self._agp_gear = "DOWN"
        self._agp_autobrake = "OFF"
        self._agp_brake_fan = False
        self._agp_anti_skid = True
        self._agp_terrain = False
        self._agp_clock_source = "GPS"
        self._agp_date_visible = False
        self._agp_chrono_running = False
        self._agp_elapsed_running = False
        self._agp_rotary_raw = {"rst": 0, "chr": 0, "date": 0}
        # >>> MUSLIMSIM AGP FACEPLATE V1 >>>
        # Which pages the AGP's three windows show: "clock" is the panel as it
        # has always been, "radio" re-tasks them as a radio/transponder head.
        # View state only - it never changes what the hardware reports.
        # None means "follow the bridge's page"; a click sets it explicitly.
        self._agp_display_mode = None
        # <<< MUSLIMSIM AGP FACEPLATE V1 <<<
        self._capture_target: Optional[str] = None
        self._capture_device: Optional[str] = None
        self._capture_started = 0.0
        self._ecam_awake = False
        self._ecam_active_page = ""
        # The B930 report verifies the two held directions and centre/reset
        # contact, but does not publish a numeric trim-position dataref.  A
        # clearly local practice value keeps the faceplate useful without
        # claiming a live readback the driver does not actually possess.
        # The physical three-position MODE selector chooses the trim role:
        # CRANK is pitch trim, NORM is rudder trim, IGN/START is aileron
        # trim - a full pitch/roll/yaw set across the one selector.  CRANK
        # reuses the "STAB" value/display channel the rocker's real
        # stabilizer-trim wiring already writes, rather than a second,
        # unconnected pitch number - see WINCTRL PITCH TRIM WHEEL V1.
        self._throttle_trim_selector = "trim_mode_norm"
        self._throttle_trim_mode: Optional[str] = "RUDDER"
        self._throttle_trim_values: Dict[str, float] = {"STAB": 4.9, "RUDDER": 0.0, "AILERON": 0.0}
        # How long the LCD spells out the newly selected role before it
        # switches back to showing that role's live trim number.
        self._throttle_trim_label_until: float = 0.0
        # These are Studio practice poses only.  The supplied Moza presets
        # describe calibration values but not a HID report position, so the
        # visual yoke/stick must never pretend to show live physical motion.
        self._moza_practice_axes: Dict[str, Dict[str, float]] = {
            "moza_a210": {
                "axis_x": 0.50, "axis_y": 0.50, "axis_z": 0.50,
                "axis_rx": 0.50, "axis_ry": 0.50, "axis_rz": 0.50,
                "axis_slider": 0.50, "axis_dial": 0.50,
            },
            "moza_ab6": {
                "axis_x": 0.50, "axis_y": 0.50, "axis_z": 0.50,
                "axis_rx": 0.50, "axis_ry": 0.50, "axis_rz": 0.50,
                "axis_slider": 0.50, "axis_dial": 0.50,
            },
        }
        # A faceplate is a physical drawing, not a fluid collection of
        # controls.  These pages let the owner view the supplied A210 base,
        # detachable-yoke and MAX3 reference layouts without stacking them.
        self._moza_layout_page: Dict[str, str] = {
            "moza_a210": "base",
            "moza_ab6": "base",
        }
        # Local, optimistic mirror of the AY210 FFB engine's live "physics"
        # block (real serial writes, unlike the rest of moza_presets.py's
        # calibration UI - see MOZA_FFB_PHYSICS_FIELDS). Seeded from
        # _moza_ffb_diagnostics()'s live-reported values whenever they are
        # available, and updated immediately on every slider click so the
        # panel never waits a full poll cycle to reflect the owner's own
        # action.
        self._moza_ffb_physics_local: Dict[str, int] = {}
        # Real .mslm profiles discovered by the bridge (bundled Tony-derived
        # presets plus anything dropped in or saved from this panel) - a
        # Both bases keep their own asynchronous preset list and selection.
        self._moza_ffb_pickers = {
            key: {"names": [], "open": False, "fetch_at": 0.0, "active": None, "error": ""}
            for key in ("moza_a210", "moza_ab6")
        }
        # Same local-optimistic-mirror idiom as _moza_ffb_physics_local, but
        # for the per-effect live gain multiplier (100% = the profile's own
        # curve, unmodified) - set_effect_gain_override() on the engine.
        self._moza_ffb_effect_gain_local: Dict[str, int] = {}
        self._pu_battery_on = False
        self._workers = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="MuslimSim-Studio")
        # Hardware-display writes can be substantially slower than reading a
        # status packet.  They get one coalescing worker of their own, so a
        # busy LCD never makes physical-control feedback wait behind it.
        self._output_workers = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="MuslimSim-Output")
        self._results: "queue.Queue[tuple[Callable[[Any], None], Any, Optional[BaseException], bool]]" = queue.Queue()
        self._status_pending = False
        # One tick used to repaint the whole faceplate up to three times: the
        # practice preview step, the status reply and the flash expiry each drew
        # independently. They now mark the canvas dirty and the tick paints once,
        # which is the same final picture for a third of the canvas work.
        self._redraw_pending = False
        self._painted_signature = None
        self._status_seen = False
        self._control_failures = 0
        # Polling is intentionally less frequent than the Tk redraw pulse.
        # A full diagnostic snapshot can contain every device's raw values;
        # asking for one on each redraw needlessly competes with the bridge
        # during an X-Plane aircraft handoff.
        self._next_status_poll = 0.0
        self._output_sync_pending = False
        self._output_sync_dirty = False
        self._discovery_pending = False
        self._bridge_discovery_pending = False
        self._mode_initialised = False
        # Start in Live.  The bridge already knows how to wait safely for a
        # simulator, while Studio selecting Practice during its first status
        # pulse could overwrite a just-running Zibo session with test output
        # before the connection state had arrived.  Practice remains one
        # deliberate click away for standalone hardware work.
        self.practice_mode = tk.BooleanVar(value=False)
        self.simulator_mode = tk.StringVar(value=self.supervisor.simulator)
        self.xplane_aircraft = tk.StringVar(value=self.supervisor.aircraft)
        self.msfs_aircraft = tk.StringVar(value=self.supervisor.msfs_aircraft)
        self._simulator_toggle_buttons: Dict[str, tk.Button] = {}
        self._aircraft_toggle_buttons: Dict[str, tk.Button] = {}
        self._msfs_brand_buttons: Dict[str, tk.Widget] = {}
        self._msfs_brand_aircraft: Dict[str, tuple] = {}
        # This is deliberately an output-test latch, not a claim that Studio
        # can switch USB power.  When enabled it sends one verified COM5 test
        # frame (lamps, windows, gauge and backlight) through the bridge.
        self.pu_wake_test = tk.BooleanVar(value=False)
        self.cockpit_side = tk.StringVar(value=CAPTAIN_SIDE)
        # MUSLIMSIM_GAZE_FOCUS_TOGGLE_V1
        # Off until the owner asks for it. The service is built on first use,
        # so a machine with no eye tracker never loads the runtime at all.
        self.gaze_focus_enabled = tk.BooleanVar(value=False)
        self.gaze_focus_label = tk.StringVar(value="Eye focus")
        self._gaze_service = None
        self._gaze_label_shown = "Eye focus"
        self._gaze_telemetry_seen = -1
        self._device_rows: list[str] = []

        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(80, self._start_bridge)
        self.after(100, self._tick)
        self.after(120, self._discover)
        self.after(1400, self._discovery_tick)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=INK, font=("Segoe UI Semibold", 21))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("TButton", background=PANEL_ALT, foreground=INK, borderwidth=0, padding=(10, 7))
        style.map("TButton", background=[("active", "#2a3b5c")])
        style.configure("Accent.TButton", background="#186e74", foreground="white")
        style.map("Accent.TButton", background=[("active", "#238e91")])
        from .dropdown_theme import apply_dropdown_theme
        apply_dropdown_theme(self, PANEL_ALT)

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(22, 16), style="TFrame")
        header.pack(fill="x")
        # Keep identity/status on their own line.  Mapping controls below are
        # given a dedicated rail, so resizing never makes header text collide
        # with the simulator or safety selectors.
        title_bar = ttk.Frame(header, style="TFrame")
        title_bar.pack(fill="x")
        ttk.Label(title_bar, text="MuslimSim Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(title_bar, text="Visual hardware mapping", style="Sub.TLabel").pack(side="left", padx=(14, 0), pady=(7, 0))
        self.connection_text = tk.StringVar(value="Starting private bridge…")
        ttk.Label(title_bar, textvariable=self.connection_text, style="Sub.TLabel").pack(side="right", pady=(7, 0))
        control_bar = tk.Frame(header, bg=BG, highlightthickness=0)
        control_bar.pack(fill="x", pady=(12, 0))
        # This is intentionally a cockpit-style mode selector rather than a
        # generic checkbox.  It makes the important safety state obvious at a
        # glance: Practice never sends aircraft changes; Live enables saved
        # mappings only after the user deliberately moves the switch.
        self._practice_mode_frame = tk.Frame(control_bar, bg=BG, highlightthickness=0)
        self._practice_mode_frame.pack(side="left", padx=(0, 28), pady=(0, 1))
        tk.Label(
            self._practice_mode_frame, text="CONTROL MODE", bg=BG, fg=MUTED,
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(anchor="w", padx=2)
        self._practice_mode_switch = tk.Canvas(
            self._practice_mode_frame, width=214, height=35, bg=BG,
            highlightthickness=0, bd=0, cursor="hand2", takefocus=True,
        )
        self._practice_mode_switch.pack(anchor="w", pady=(2, 0))
        self._practice_mode_switch.bind("<Button-1>", self._toggle_practice_mode)
        self._practice_mode_switch.bind("<Return>", self._toggle_practice_mode)
        self._practice_mode_switch.bind("<space>", self._toggle_practice_mode)
        self._refresh_practice_mode_switch()
        # A segmented cockpit-style selector replaces the old tiny radio
        # buttons.  The aircraft selector is intentionally inside the
        # X-Plane workspace; ToLiss cannot appear in the MSFS workspace.
        self._workspace_toggle = tk.Frame(control_bar, bg=BG, highlightthickness=0)
        self._workspace_toggle.pack(side="left", pady=(0, 1))
        self._aircraft_toggle_frame = tk.Frame(self._workspace_toggle, bg=BG)
        tk.Label(
            self._aircraft_toggle_frame, text="X-PLANE AIRCRAFT", bg=BG, fg=MUTED,
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(anchor="w", padx=2)
        aircraft_rail = tk.Frame(self._aircraft_toggle_frame, bg="#121d31", highlightbackground="#314663", highlightthickness=1)
        aircraft_rail.pack(anchor="w", pady=(2, 0))
        for value, label in (
            (AIRCRAFT_ZIBO, "ZIBO 737"),
            (AIRCRAFT_LEVELUP, "LEVELUP 737"),
            (AIRCRAFT_TOLISS, "TOLISS AIRBUS"),
            (AIRCRAFT_C172_NG, "C172 NG DIGITAL"),
        ):
            button = tk.Button(
                aircraft_rail, text=label, command=lambda item=value: self._choose_xplane_aircraft(item),
                bg="#18263d", fg="#b9c8e3", activebackground="#28466b", activeforeground="white",
                relief="flat", bd=0, padx=9, pady=6, cursor="hand2",
                font=("Segoe UI Semibold", 8), takefocus=False,
            )
            button.pack(side="left", padx=1, pady=1)
            self._aircraft_toggle_buttons[value] = button
        # The MSFS 2024 add-on aircraft are grouped by developer.  A brand with
        # more than one airframe is a drop-down; iFly ships one, so it stays a
        # plain button rather than a one-item menu.
        self._msfs_toggle_frame = tk.Frame(self._workspace_toggle, bg=BG)
        tk.Label(
            self._msfs_toggle_frame, text="MSFS 2024 AIRCRAFT", bg=BG, fg=MUTED,
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(anchor="w", padx=2)
        msfs_rail = tk.Frame(self._msfs_toggle_frame, bg="#121d31", highlightbackground="#314663", highlightthickness=1)
        msfs_rail.pack(anchor="w", pady=(2, 0))
        for brand, entries in msfs24_brands():
            self._msfs_brand_aircraft[brand] = entries
            if len(entries) == 1:
                only = entries[0]
                widget = tk.Button(
                    msfs_rail, text=f"{brand.upper()} {only.label}".strip(),
                    command=lambda item=only.key: self._choose_msfs24_aircraft(item),
                    bg="#18263d", fg="#b9c8e3", activebackground="#28466b", activeforeground="white",
                    relief="flat", bd=0, padx=9, pady=6, cursor="hand2",
                    font=("Segoe UI Semibold", 8), takefocus=False,
                )
            else:
                widget = tk.Menubutton(
                    msfs_rail, text=brand.upper(), direction="below",
                    bg="#18263d", fg=BLUE, activebackground="#28466b", activeforeground=BLUE,
                    relief="flat", bd=0, padx=9, pady=6, cursor="hand2",
                    font=("Segoe UI Semibold", 8), takefocus=False,
                )
                menu = tk.Menu(
                    widget, tearoff=0, bg="#12203a", fg=BLUE,
                    activebackground="#28466b", activeforeground=BLUE,
                    font=("Segoe UI", 9), bd=0,
                )
                for entry in entries:
                    # An airframe with no imported functions is still offered,
                    # and says so, rather than looking identical to one that
                    # has a library behind it.
                    suffix = "" if entry.has_functions else "   (no functions imported)"
                    menu.add_radiobutton(
                        label=f"{entry.label}{suffix}", value=entry.key,
                        variable=self.msfs_aircraft,
                        command=lambda item=entry.key: self._choose_msfs24_aircraft(item),
                    )
                widget.configure(menu=menu)
            widget.pack(side="left", padx=1, pady=1)
            self._msfs_brand_buttons[brand] = widget

        self._simulator_toggle_frame = tk.Frame(self._workspace_toggle, bg=BG)
        tk.Label(
            self._simulator_toggle_frame, text="SIMULATOR", bg=BG, fg=MUTED,
            font=("Segoe UI", 7, "bold"), anchor="w",
        ).pack(anchor="w", padx=2)
        simulator_rail = tk.Frame(self._simulator_toggle_frame, bg="#121d31", highlightbackground="#314663", highlightthickness=1)
        simulator_rail.pack(anchor="w", pady=(2, 0))
        for value, label in ((SIMULATOR_XPLANE, "X-PLANE"), (SIMULATOR_MSFS24, "MSFS 2024")):
            button = tk.Button(
                simulator_rail, text=label, command=lambda item=value: self._choose_simulator(item),
                bg="#18263d", fg="#b9c8e3", activebackground="#28466b", activeforeground="white",
                relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                font=("Segoe UI Semibold", 8), takefocus=False,
            )
            button.pack(side="left", padx=1, pady=1)
            self._simulator_toggle_buttons[value] = button
        self._simulator_toggle_frame.pack(side="right")
        self._refresh_workspace_toggle()

        body = ttk.Frame(self, padding=(18, 0, 18, 18))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(body, style="Panel.TFrame", padding=12)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ttk.Label(sidebar, text="Connected hardware", style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        ttk.Label(sidebar, text="Detected automatically", style="PanelMuted.TLabel").pack(anchor="w", pady=(2, 10))
        self.device_list = tk.Listbox(
            sidebar, bg=PANEL, fg=INK, selectbackground="#29486e", selectforeground="white",
            highlightthickness=0, borderwidth=0, activestyle="none", width=32,
            font=("Segoe UI", 10), exportselection=False,
        )
        self.device_list.pack(fill="both", expand=True)
        self.device_list.bind("<<ListboxSelect>>", self._select_device)
        ttk.Button(
            sidebar, text="Rescan hardware", command=lambda: self._discover(force=True),
        ).pack(fill="x", pady=(10, 0))

        studio = ttk.Frame(body, style="Panel.TFrame", padding=14)
        studio.grid(row=0, column=1, sticky="nsew")
        studio.columnconfigure(0, weight=1)
        studio.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(studio, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.device_title = tk.StringVar(value="WINCTRL 32 FCU + 32 EFIS L/R")
        self.device_detail = tk.StringVar(value="Waiting for device discovery")
        ttk.Label(toolbar, textvariable=self.device_title, style="Panel.TLabel", font=("Segoe UI Semibold", 15)).pack(anchor="w")
        ttk.Label(toolbar, textvariable=self.device_detail, style="PanelMuted.TLabel").pack(anchor="w", pady=(2, 0))
        self.cockpit_side_picker = ttk.Combobox(
            toolbar,
            textvariable=self.cockpit_side,
            values=(CAPTAIN_SIDE, FIRST_OFFICER_SIDE),
            state="readonly",
            width=19,
        )
        self.cockpit_side_picker.bind("<<ComboboxSelected>>", self._set_cockpit_side)

        work = ttk.Frame(studio, style="Panel.TFrame")
        work.grid(row=1, column=0, sticky="nsew")
        work.columnconfigure(0, weight=1)
        work.rowconfigure(0, weight=1)
        self.faceplate = tk.Canvas(work, bg="#0d1527", highlightthickness=0, cursor="hand2")
        self.faceplate.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.faceplate.bind("<Configure>", lambda _event: self._draw_faceplate())
        self.faceplate.bind("<Button-1>", self._faceplate_click)
        self.faceplate.bind("<B1-Motion>", self._faceplate_drag)
        self.faceplate.bind("<ButtonRelease-1>", self._faceplate_release)

        inspector = ttk.Frame(work, style="Panel.TFrame", padding=(12, 4), width=280)
        inspector.grid(row=0, column=1, sticky="ns")
        inspector.grid_propagate(False)
        ttk.Label(inspector, text="Control setup", style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        self.selection_title = tk.StringVar(value="Select a control on the panel")
        self.selection_source = tk.StringVar(value="")
        self.selection_note = tk.StringVar(value="Click a button, switch or knob on the visual panel to configure it.")
        ttk.Label(inspector, textvariable=self.selection_title, style="Panel.TLabel", wraplength=250, font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(16, 4))
        ttk.Label(inspector, textvariable=self.selection_source, style="PanelMuted.TLabel", wraplength=250).pack(anchor="w")
        self.selection_note_label = ttk.Label(inspector, textvariable=self.selection_note, style="PanelMuted.TLabel", wraplength=250, justify="left")
        activation = tk.Frame(inspector, bg=PANEL, highlightbackground="#344865", highlightthickness=1)
        activation.pack(fill="x", pady=(0, 12))
        self.device_activation_hint = tk.StringVar(value="Device activation is loading…")
        tk.Label(
            activation, text="DEVICE ACTIVATION", bg=PANEL, fg=MUTED,
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(fill="x", padx=9, pady=(8, 1))
        tk.Label(
            activation, textvariable=self.device_activation_hint, bg=PANEL, fg="#b9c8e3",
            font=("Segoe UI", 8), anchor="w", wraplength=235, justify="left",
        ).pack(fill="x", padx=9, pady=(0, 7))
        self.device_activation_button = tk.Button(
            activation, text="", command=self._toggle_selected_device_enabled,
            bg="#176c67", fg="white", activebackground="#21877f", activeforeground="white",
            relief="flat", bd=0, padx=9, pady=8, cursor="hand2",
            font=("Segoe UI Semibold", 9), takefocus=False,
        )
        self.device_activation_button.pack(fill="x", padx=9, pady=(0, 9))
        self.capture_button = ttk.Button(inspector, text="Assign hardware button", style="Accent.TButton", command=self._begin_learn)
        self.capture_button.pack(fill="x", pady=(0, 7))
        self.capture_button.state(("disabled",))
        # Some devices expose more physical contacts than their faceplate
        # diagram has a drawn legend for (a spare bit whose exact HID
        # position is known, but whose real-world button was never
        # confirmed - see _EXPOSE_UNVERIFIED_CONTROLS). This picker is the
        # only way to reach one of those directly, since nothing is drawn
        # for it on the 2D panel to click. It is hidden for every device
        # that has none.
        self.spare_control_label = ttk.Label(
            inspector, text="Other physical contact (no confirmed legend yet):",
            style="PanelMuted.TLabel", wraplength=250, justify="left",
        )
        self.spare_control_label.pack(anchor="w", pady=(0, 2))
        self._spare_control_by_display: Dict[str, str] = {}
        self.spare_control_name = tk.StringVar(value="")
        self.spare_control_picker = ttk.Combobox(
            inspector, textvariable=self.spare_control_name, state="disabled", width=30, values=(),
        )
        self.spare_control_picker.pack(fill="x", pady=(0, 7))
        self.spare_control_picker.bind("<<ComboboxSelected>>", self._select_spare_control)
        ttk.Button(inspector, text="Choose simulator function", command=self._map_selected).pack(fill="x", pady=4)
        ttk.Button(inspector, text="Rename this control…", command=self._rename_selected).pack(fill="x", pady=4)
        self._test_button = ttk.Button(inspector, text="Test virtual control", command=self._test_selected)
        self._test_button.pack(fill="x", pady=4)
        # Appears only when the current device has custom bindings; pack_forget hides it.
        self.device_reset_button = ttk.Button(
            inspector, text="Reset device to built-in defaults",
            command=self._reset_device_bindings,
        )
        ttk.Separator(inspector).pack(fill="x", pady=18)
        ttk.Label(inspector, text="Profile", style="PanelMuted.TLabel").pack(anchor="w")
        self.profile_name = tk.StringVar(value="Default")
        self.profile_picker = ttk.Combobox(inspector, textvariable=self.profile_name, state="readonly", width=24, values=("Default",))
        self.profile_picker.pack(fill="x", pady=(4, 6))
        self.profile_picker.bind("<<ComboboxSelected>>", self._switch_profile)
        ttk.Button(inspector, text="New profile…", command=self._new_profile).pack(fill="x")
        ttk.Button(inspector, text="Restore this profile", command=self._restore_profile).pack(fill="x", pady=(7, 0))

        footer = ttk.Frame(self, padding=(22, 0, 22, 16))
        footer.pack(fill="x")
        self.footer = tk.StringVar(value="Select a device to begin.")
        ttk.Label(footer, textvariable=self.footer, style="Sub.TLabel").pack(anchor="w")
        self._refresh_device_activation()

    # ----- process / discovery -------------------------------------------------

    def _start_bridge(self) -> None:
        try:
            self.supervisor.start()
        except OSError as exc:
            self.connection_text.set(f"Could not start the private bridge: {exc}")

    def _toggle_practice_mode(self, _event: Optional[tk.Event] = None) -> str:
        """Move the visual safety switch and route through the usual bridge API."""

        self.practice_mode.set(not self.practice_mode.get())
        self._refresh_practice_mode_switch()
        self._set_practice_mode()
        return "break"

    def _refresh_practice_mode_switch(self) -> None:
        """Render the compact physical-style Practice/Live selector."""

        canvas = getattr(self, "_practice_mode_switch", None)
        if canvas is None:
            return
        canvas.delete("mode-switch")
        practice = bool(self.practice_mode.get())
        active_fill = "#176e63" if practice else "#815c20"
        active_edge = "#38d8bf" if practice else "#ffd36d"
        active_text = "#eafff8" if practice else "#fff6da"
        muted_text = "#8698b8"

        # Long dark track with two labelled detents; the bright moving pill
        # is deliberately readable from across a cockpit setup.
        canvas.create_rectangle(1, 1, 213, 34, fill="#101b2d", outline="#405574", width=1, tags="mode-switch")
        canvas.create_line(107, 5, 107, 30, fill="#30435f", width=1, tags="mode-switch")
        left, right = (4, 104) if practice else (110, 210)
        canvas.create_rectangle(left, 4, right, 31, fill=active_fill, outline=active_edge, width=1, tags="mode-switch")
        canvas.create_oval(
            (12 if practice else 182), 9, (30 if practice else 200), 27,
            fill=active_edge, outline="", tags="mode-switch",
        )
        canvas.create_text(
            64, 17, text="PRACTICE", anchor="center",
            fill=active_text if practice else muted_text,
            font=("Segoe UI Semibold", 9, "bold"), tags="mode-switch",
        )
        canvas.create_text(
            158, 17, text="LIVE", anchor="center",
            fill=active_text if not practice else muted_text,
            font=("Segoe UI Semibold", 9, "bold"), tags="mode-switch",
        )
        canvas.create_text(
            212, 17, text="SAFE" if practice else "SIM", anchor="e",
            fill="#a6cfc6" if practice else "#ffe2a5",
            font=("Segoe UI", 6, "bold"), tags="mode-switch",
        )

    def _refresh_workspace_toggle(self) -> None:
        """Keep the compact visual selector honest about the active workspace."""

        simulator = self.simulator_mode.get()
        for value, button in self._simulator_toggle_buttons.items():
            selected = value == simulator
            background = "#1763bb" if value == SIMULATOR_XPLANE and selected else (
                "#13766f" if selected else "#18263d"
            )
            button.configure(
                bg=background, fg="white" if selected else "#b9c8e3",
                activebackground=background,
            )
        if simulator == SIMULATOR_XPLANE:
            if not self._aircraft_toggle_frame.winfo_ismapped():
                self._aircraft_toggle_frame.pack(side="left", padx=(0, 9))
        else:
            self._aircraft_toggle_frame.pack_forget()
        if simulator == SIMULATOR_MSFS24:
            if not self._msfs_toggle_frame.winfo_ismapped():
                self._msfs_toggle_frame.pack(side="left", padx=(0, 9))
        else:
            self._msfs_toggle_frame.pack_forget()
        selected_aircraft = self.xplane_aircraft.get()
        for value, button in self._aircraft_toggle_buttons.items():
            selected = simulator == SIMULATOR_XPLANE and value == selected_aircraft
            background = "#2a72c7" if selected else "#18263d"
            button.configure(
                bg=background, fg="white" if selected else "#b9c8e3",
                activebackground=background,
            )
        # A brand button carries the chosen airframe so the active MSFS
        # workspace is readable without opening its menu.
        selected_msfs = self.msfs_aircraft.get()
        for brand, widget in self._msfs_brand_buttons.items():
            entries = self._msfs_brand_aircraft.get(brand, ())
            chosen = next((item for item in entries if item.key == selected_msfs), None)
            active = simulator == SIMULATOR_MSFS24 and chosen is not None
            background = "#13766f" if active else "#18263d"
            if len(entries) == 1:
                text = f"{brand.upper()} {entries[0].label}".strip()
            else:
                text = f"{brand.upper()}  {chosen.label}" if active else brand.upper()
            widget.configure(
                text=text, bg=background, fg="white" if active else "#b9c8e3",
                activebackground=background,
            )

    def _choose_simulator(self, simulator: str) -> None:
        self.simulator_mode.set(simulator)
        self._set_simulator_mode()

    def _choose_xplane_aircraft(self, aircraft: str) -> None:
        self.xplane_aircraft.set(aircraft)
        self.simulator_mode.set(SIMULATOR_XPLANE)
        self._set_simulator_mode()

    def _choose_msfs24_aircraft(self, aircraft: str) -> None:
        self.msfs_aircraft.set(aircraft)
        self.simulator_mode.set(SIMULATOR_MSFS24)
        self._set_simulator_mode()

    def _auto_select_loaded_xplane_aircraft(self, lab: Dict[str, Any]) -> bool:
        """Move Studio to the isolated workspace named by the loaded .acf."""

        if (
            self.simulator_mode.get() != SIMULATOR_XPLANE
            or not bool(lab.get("simulator_connected"))
            or self.supervisor.recovering
        ):
            return False
        aircraft = lab.get("aircraft")
        if not isinstance(aircraft, dict):
            return False
        detected = str(aircraft.get("profile") or "").strip().casefold()
        if detected not in self._aircraft_toggle_buttons:
            return False
        if detected == self.xplane_aircraft.get():
            return False

        self.xplane_aircraft.set(detected)
        self._set_simulator_mode()
        if self.xplane_aircraft.get() != detected:
            return False
        title = xplane_aircraft_title(detected)
        self.footer.set(
            f"Detected {title} from X-Plane. Loading its separate controls and mapping profile…"
        )
        return True

    def _set_simulator_mode(self) -> None:
        """Switch bridge/profile on a worker; never freeze the Studio UI."""

        requested = self.simulator_mode.get()
        aircraft = self.xplane_aircraft.get()
        msfs_choice = self.msfs_aircraft.get()
        if (
            requested == self.supervisor.simulator
            and (
                msfs_choice == self.supervisor.msfs_aircraft
                if requested == SIMULATOR_MSFS24
                else aircraft == self.supervisor.aircraft
            )
        ):
            self._refresh_workspace_toggle()
            return
        if not self.supervisor.request_workspace_change(requested, aircraft, msfs_choice):
            self.simulator_mode.set(self.supervisor.simulator)
            self.xplane_aircraft.set(self.supervisor.aircraft)
            self.msfs_aircraft.set(self.supervisor.msfs_aircraft)
            self._refresh_workspace_toggle()
            return
        self._profile = {}
        self._lab = {}
        self._device_states = {}
        self._device_enabled = {}
        self._bridge_detected = {}
        self._mode_initialised = False
        self._latest_diagnostic = 0.0
        self._status_seen = False
        self._set_connection_text("Changing simulator workspace…")
        self._refresh_workspace_toggle()
        if requested == SIMULATOR_MSFS24:
            title = msfs24_aircraft_title(msfs_choice)
            if msfs24_family(msfs_choice):
                self.footer.set(
                    f"{title} workspace selected. It has its own MSFS 2024 mapping "
                    "profile, separate from X-Plane; dispatch stays off until the "
                    "MSFS connector is built."
                )
            else:
                self.footer.set(
                    f"{title} workspace selected. Its hardware can be practised and "
                    "mapped later, but the imported catalogue has no functions for "
                    "it yet, so the function browser will be empty."
                )
        else:
            self.footer.set(
                f"{xplane_aircraft_title(aircraft)} workspace selected. "
                "It has its own X-Plane function library and mapping profiles."
            )

    def _activation_workspace_title(self) -> str:
        if self.simulator_mode.get() == SIMULATOR_MSFS24:
            return msfs24_aircraft_title(self.msfs_aircraft.get())
        return xplane_aircraft_title(self.xplane_aircraft.get())

    def _refresh_device_activation(self) -> None:
        """Show the selected device's profile-scoped operating switch."""

        if not hasattr(self, "device_activation_button"):
            return
        key = self._selected_device
        if key not in self._catalog:
            self.device_activation_hint.set("This device has no saved hardware definition yet.")
            self.device_activation_button.configure(
                text="DEVICE CONTROL UNAVAILABLE", state="disabled", bg="#263448",
            )
            return
        workspace = self._activation_workspace_title()
        profile = self.profile_name.get() or "Default"
        enabled = bool(self._device_enabled.get(key, True))
        if enabled:
            self.device_activation_hint.set(
                f"Running for {workspace} • profile {profile}. This setting is separate for every aircraft."
            )
            self.device_activation_button.configure(
                text="●  DEVICE RUNNING  —  TURN OFF", state="normal",
                bg="#176c67", activebackground="#21877f", fg="white",
            )
        else:
            self.device_activation_hint.set(
                f"Off for {workspace} • profile {profile}. Its physical inputs and supported outputs are blocked."
            )
            self.device_activation_button.configure(
                text="○  DEVICE OFF  —  TURN ON", state="normal",
                bg="#3b4659", activebackground="#56647a", fg="#f3f6fb",
            )

    def _toggle_selected_device_enabled(self) -> None:
        key = self._selected_device
        if key not in self._catalog:
            return
        if self.supervisor.client is None:
            self.footer.set("The private hardware service is starting…")
            self._refresh_device_activation()
            return
        wanted = not bool(self._device_enabled.get(key, True))
        self.device_activation_button.configure(state="disabled")

        def applied(result: Dict[str, Any]) -> None:
            self._device_enabled[key] = bool(result.get("enabled", wanted))
            profile = result.get("profile")
            if isinstance(profile, dict):
                self._profile = profile
                active = str(profile.get("active_profile") or "Default")
                self.profile_name.set(active)
            self._refresh_device_activation()
            self._refresh_profile_status(
                f"{self._catalog[key]['title']} is now " + ("running." if wanted else "off.")
            )

        self._request("device_enable_set", device=key, enabled=wanted, done=applied)

    def _submit(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        future = self._workers.submit(work)

        self._collect_future(future, done)

    def _submit_output(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        """Run slow device-output work away from live input/status traffic."""

        future = self._output_workers.submit(work)
        self._collect_future(future, done)

    def _collect_future(
        self,
        future: concurrent.futures.Future[Any],
        done: Callable[[Any], None],
        *,
        health_check: bool = False,
    ) -> None:
        """Return any worker result to Tk's event loop without touching Tk here."""

        def complete(item: concurrent.futures.Future[Any]) -> None:
            try:
                self._results.put((done, item.result(), None, health_check))
            except BaseException as exc:
                self._results.put((done, None, exc, health_check))

        future.add_done_callback(complete)

    def _request(
        self,
        command: str,
        *,
        done: Callable[[Dict[str, Any]], None],
        health_check: bool = False,
        **fields: Any,
    ) -> bool:
        """Submit one bridge request.

        Returns ``False`` when nothing was sent, so a caller holding a
        single-flight latch can release it.  Every existing caller ignores the
        result and behaves exactly as before.
        """

        client = self.supervisor.client
        if client is None:
            self.footer.set("The private hardware service is starting…")
            return False
        try:
            future = self._workers.submit(lambda: client.request(command, **fields))
        except RuntimeError:
            # The worker pool is shutting down with Studio; no result will
            # arrive for this call either.
            return False
        self._collect_future(future, done, health_check=health_check)
        return True

    def _discover(self, *, force: bool = False) -> None:
        if not self._discovery_pending:
            self._discovery_pending = True
            # Never open SDL/DirectInput devices from the GUI process.  The
            # 1.4-second discovery pulse used to construct pygame Joystick
            # objects for the PU and B930 over and over while the child bridge
            # was polling those same handles.  Raw PU axes survived, but PU
            # button contacts and every WinCtrl throttle input went silent.
            # HID + Windows PnP discovery still finds known and generic gaming
            # hardware without claiming its live input interface.
            self._submit(
                lambda: discover_hid_devices(include_sdl=False),
                self._receive_discovery,
            )
        # Studio can run with a UI-only Python runtime that has no hidapi.
        # Ask the already-running child bridge too: it owns the hardware
        # runtime and can report a newly attached, even unconfigured, panel.
        if not self._bridge_discovery_pending:
            client = self.supervisor.client
            if client is not None:
                self._bridge_discovery_pending = True
                self._submit(
                    lambda: self._bridge_hardware_discovery(client, force=force),
                    self._receive_bridge_discovery,
                )

    @staticmethod
    def _bridge_hardware_discovery(client: Any, *, force: bool = False) -> Dict[str, Any]:
        try:
            return dict(client.request("hardware_discovery", force=force))
        except ControlClientError:
            # A normal bridge restart should not leave the Rescan button
            # permanently busy or erase a still-visible prior inventory.
            return {"available": False}

    def _discovery_tick(self) -> None:
        self._discover()
        self.after(1400, self._discovery_tick)

    def _receive_discovery(self, devices: Iterable[Any]) -> None:
        self._discovery_pending = False
        self._local_detected = {device.key: device.snapshot() for device in devices}
        self._local_detected_at = time.monotonic()
        self._merge_detected_devices()

    def _receive_bridge_discovery(self, response: Dict[str, Any]) -> None:
        self._bridge_discovery_pending = False
        if not response.get("available", True) or response.get("stale"):
            # A failed scan is not an unplug. The next successful inventory
            # (including an empty one) replaces this last confirmed snapshot.
            return
        # A fresh Windows inventory may still be running in the bridge.  Do
        # not erase an already visible sidebar merely because its first
        # immediate reply is an intentionally empty cache.
        if response.get("refreshing") and not response.get("devices"):
            return
        inventory: Dict[str, Dict[str, Any]] = {}
        for device in list(response.get("devices") or ()):
            if not isinstance(device, dict):
                continue
            key = str(device.get("key") or "")
            if not key:
                continue
            item = dict(device)
            item["source"] = "bridge-hid"
            inventory[key] = item
        self._bridge_inventory_at = time.monotonic()
        if inventory != self._bridge_inventory:
            self._bridge_inventory = inventory
            self._merge_detected_devices()

    def _merge_detected_devices(self) -> None:
        # Local HID discovery gives the richest USB strings when available;
        # the bridge inventory fills that gap for UI-only Python installs.
        # Registered-device status then supplies its live running state.
        merged: Dict[str, Dict[str, Any]] = {}
        now = time.monotonic()
        sources = (
            (self._bridge_inventory, getattr(self, "_bridge_inventory_at", 0.0)),
            (self._bridge_detected, getattr(self, "_bridge_detected_at", 0.0)),
            (self._local_detected, getattr(self, "_local_detected_at", 0.0)),
        )
        for source, observed_at in sources:
            for incoming_key, raw_item in source.items():
                item = dict(raw_item)
                key = canonical_device_key(
                    str(incoming_key), item.get("key"), item.get("title"), item.get("product"), item.get("manufacturer"),
                )
                item["key"] = key
                if hardware_presence(item) is False:
                    continue
                # A confirmed unplug overrides older positive scan caches.
                status_at = getattr(self, "_bridge_detected_at", 0.0)
                if status_at >= observed_at and hardware_presence(self._device_states.get(key, {})) is False:
                    continue
                if key == "pu_overhead":
                    item["title"] = "PU Overhead"
                    item["recognised"] = True
                existing = merged.get(key)
                # Keep the verified identity when a generic driver alias and
                # a recognised panel describe the same connected hardware.
                if existing and bool(existing.get("recognised")) and not bool(item.get("recognised")):
                    continue
                merged[key] = item
        if merged != self._detected or not getattr(self, "_inventory_rendered", False):
            self._detected = merged
            self._refresh_detected_devices()
            self._inventory_rendered = True

    def _refresh_detected_devices(self) -> None:
        """Keep bridge-observed hardware visible when the UI has no hidapi."""

        current = self._selected_device
        self._device_rows = list(self._detected)
        self.device_list.delete(0, "end")
        for key in self._device_rows:
            device = self._detected[key]
            enabled = bool(self._device_enabled.get(key, True))
            self.device_list.insert(
                "end", f"{'●' if enabled else '○'}  {device['title']}{'' if enabled else '  — off'}",
            )
        if not self._device_rows:
            self.device_list.insert("end", "No MuslimSim panel hardware detected")
        if current not in self._detected:
            current = "fcu_32_efis" if "fcu_32_efis" in self._detected else (self._device_rows[0] if self._device_rows else "")
        if current != self._selected_device:
            self._selected_visual = None
            self._capture_target = None
            self._capture_device = None
            self._learning = None
        self._selected_device = current
        if current in self._device_rows:
            index = self._device_rows.index(current)
            self.device_list.selection_set(index)
        self._update_device_header()

    def _select_device(self, _event: object) -> None:
        chosen = self.device_list.curselection()
        if not chosen or chosen[0] >= len(self._device_rows):
            return
        self._selected_device = self._device_rows[int(chosen[0])]
        self._selected_visual = None
        self._learning = None
        self._update_device_header()
        # MUSLIMSIM_PRACTICE_ALL_DEVICES_V1
        self._practice_page_wake(immediate=True)

    def _update_device_header(self) -> None:
        detected = self._detected.get(self._selected_device)
        spec = self._catalog.get(self._selected_device)
        self.device_title.set((detected or spec or {}).get("title", self._selected_device or "No connected hardware"))
        if detected:
            if detected.get("source") == "bridge":
                state_record = self._device_states.get(self._selected_device, {})
                if not isinstance(state_record, dict):
                    state_record = {}
                state = str(state_record.get("state") or "connected")
                # MUSLIMSIM_BB36_COMPLETE_LIFECYCLE_V2_STUDIO
                offline_states = {
                    # MUSLIMSIM_HOWALT_DIRECT_V1_STUDIO
                    "muslimrtp_d201": {"disconnected", "offline", "waiting", "waiting-for-usb", "reconnecting", "stopped"},
                    "muslimatc_d203": {"disconnected", "offline", "waiting", "waiting-for-usb", "reconnecting", "stopped"},
                    "pfp3n_bb35": {
                        "disconnected", "offline", "waiting-for-pfp3n",
                        "reconnecting", "stopped",
                    },
                    "mcdu32_bb36": {
                        "disconnected", "offline", "waiting-for-bb36",
                        "reconnecting", "stopped",
                    },
                    # MUSLIMSIM_DEVICE_LIFECYCLE_V1_STUDIO
                    'fcu_32_efis': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'pdc_bb62': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'pap3_mag': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'pu_overhead': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'winctrl_throttle': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'winctrl_pedals': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'moza_a210': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'agp_bb80': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    'ecam32': {"disconnected", "offline", "waiting-for-usb", "reconnecting", "stopped"},
                    "pdc_bb61_left": {
                        "disconnected", "offline", "waiting-for-usb",
                        "reconnecting", "stopped", "starting", "connecting",
                    },
                    "pdc_bb52_right": {
                        "disconnected", "offline", "waiting-for-usb",
                        "reconnecting", "stopped", "starting", "connecting",
                    },
                }
                physical_panel_offline = (
                    state.strip().lower()
                    in offline_states.get(self._selected_device, set())
                )
                if physical_panel_offline:
                    self.device_detail.set(
                        f"Not currently detected  •  private hardware service  •  {state}"
                    )
                else:
                    self.device_detail.set(
                        f"Connected through the private hardware service  •  {state}"
                    )
            else:
                self.device_detail.set(
                    f"Connected  •  {detected['product']}  •  serial {detected['serial']}  •  firmware {detected['firmware']}"
                )
        elif spec:
            self.device_detail.set(f"Not currently detected  •  {spec['identity']}")
        else:
            self.device_detail.set("Detected device has no captured configuration definition yet." if detected else "Connect a device to see it here.")
        if self._selected_device in SIDE_CAPABLE_DEVICES:
            self.cockpit_side.set(self._cockpit_sides.get(self._selected_device, CAPTAIN_SIDE))
            self.cockpit_side_picker.pack(anchor="e", side="right", padx=(12, 0), pady=(3, 0))
            self.device_detail.set(f"{self.device_detail.get()}  •  virtual companion: {self._companion_side()}")
        else:
            self.cockpit_side_picker.pack_forget()
        self._refresh_device_activation()
        self._draw_faceplate()
        self._show_selection()

    def _companion_side(self) -> str:
        return FIRST_OFFICER_SIDE if self.cockpit_side.get() == CAPTAIN_SIDE else CAPTAIN_SIDE

    def _load_panel_roles(self) -> None:
        """Load persisted panel role assignments from config/panel_roles.json.

        Falls back to the legacy config/pdc_roles.json on first run so that
        users who already had PDC assignments do not lose them.
        """
        def _apply(data: dict) -> None:
            for key, side in data.get("sides", {}).items():
                if str(side) in (CAPTAIN_SIDE, FIRST_OFFICER_SIDE):
                    self._cockpit_sides[str(key)] = str(side)

        try:
            if _PANEL_ROLES_PATH.exists():
                _apply(json.loads(_PANEL_ROLES_PATH.read_text(encoding="utf-8")))
            elif _PDC_ROLES_PATH.exists():
                _apply(json.loads(_PDC_ROLES_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass

    def _save_panel_roles(self) -> None:
        """Persist all side-capable panel role assignments to config/panel_roles.json."""
        try:
            _PANEL_ROLES_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "schema": "muslimsim-panel-roles-v1",
                "sides": {k: v for k, v in self._cockpit_sides.items()
                          if k in SIDE_CAPABLE_DEVICES},
            }
            _PANEL_ROLES_PATH.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _set_cockpit_side(self, _event: object = None) -> None:
        if self._selected_device not in SIDE_CAPABLE_DEVICES:
            return
        self._cockpit_sides[self._selected_device] = self.cockpit_side.get()
        self._save_panel_roles()
        self.footer.set(
            f"{self.cockpit_side.get()} virtual cockpit reference selected. The connected physical panel remains one device; choose its side-specific simulator functions when remapping."
        )
        self._update_device_header()

    def _toggle_pu_wake(self) -> None:
        """Send the known non-actuator PU output test through the loopback.

        The panel's USB power cannot safely be switched in software.  Its
        confirmed COM5 protocol *can* wake the display/backlight/lamp path,
        so this control uses an explicit laboratory output test and excludes
        the P1 starter solenoid.
        """

        if self._selected_device != "pu_overhead":
            self.pu_wake_test.set(False)
            return
        if self.pu_wake_test.get():
            payload: Dict[str, Any] = {
                "flt_altitude": "88888",
                "land_altitude": "88888",
                "apu_egt": 50.0,
                "panel_backlight": 1.0,
            }
            payload.update({f"lamp_{bit}": 1.0 for bit in range(32)})
            self.practice_mode.set(True)
            self._request(
                "lab_output_test", device="pu_overhead", action="values", payload=payload,
                done=lambda _result: self.footer.set(
                    "PU panel awake: lamps, altitude windows, EGT and backlight are in the safe test pattern."
                ),
            )
        else:
            # Leave simulator-down displays alive when the lamp test ends.
            # all_off would correctly clear lamps, but it also zeroed both
            # altitude windows and the backlight, which looks like a frozen
            # panel instead of a ready practice cockpit.
            payload = {
                "flt_altitude": 10000,
                "land_altitude": 1000,
                "apu_egt": 0.0,
                "panel_backlight": 1.0,
            }
            payload.update({f"lamp_{bit}": 0.0 for bit in range(32)})
            self._request(
                "lab_output_test", device="pu_overhead", action="values", payload=payload,
                done=lambda _result: self.footer.set(
                    "PU output test cleared. The altitude windows remain live for normal Practice input."
                ),
            )

    # ----- visual panel --------------------------------------------------------

    @staticmethod
    def _fcu_controls() -> Dict[str, Dict[str, Any]]:
        controls: Dict[str, Dict[str, Any]] = {}
        for name, label, group, delta in (
            ("speed_dec", "SPEED −", "speed", -1), ("speed_inc", "SPEED +", "speed", 1),
            ("speed_push", "SPEED push", "speed", 0), ("speed_pull", "SPEED pull", "speed", 0),
            ("heading_dec", "HDG −", "heading", -1), ("heading_inc", "HDG +", "heading", 1),
            ("heading_push", "HDG push", "heading", 0), ("heading_pull", "HDG pull", "heading", 0),
            ("altitude_dec", "ALT −", "altitude", -100), ("altitude_inc", "ALT +", "altitude", 100),
            ("altitude_push", "ALT push", "altitude", 0), ("altitude_pull", "ALT pull", "altitude", 0),
            ("vs_dec", "V/S −", "vs", -100), ("vs_inc", "V/S +", "vs", 100),
            ("vs_push", "V/S push", "vs", 0), ("vs_pull", "V/S pull", "vs", 0),
        ):
            controls[name] = {"label": label, "group": group, "delta": delta, "kind": "knob"}
        for name, label in (
            ("mach", "SPD/MACH"), ("loc", "LOC"), ("trk", "TRK/FPA"), ("ap1", "AP 1"), ("ap2", "AP 2"),
            ("athr", "A/THR"), ("exped", "EXPED"), ("metric", "METRIC"), ("appr", "APPR"),
            ("altitude_step_100", "ALT 100"), ("altitude_step_1000", "ALT 1000"),
        ):
            controls[name] = {"label": label, "kind": "button"}
        for prefix, crew in (("left", "CAPT"), ("right", "FO")):
            for suffix, label in (
                ("fd", "FD"), ("ls", "LS"), ("cstr", "CSTR"), ("wpt", "WPT"),
                ("vord", "VOR.D"), ("ndb", "NDB"), ("arpt", "ARPT"),
                ("std_push", "STD PUSH"), ("std_pull", "STD PULL"),
                ("inhg", "inHg"), ("hpa", "hPa"),
            ):
                controls[f"{prefix}_{suffix}"] = {"label": f"{crew} {label}", "kind": "button"}
            for suffix, label in (
                ("mode_ls", "MODE LS"), ("mode_vor", "MODE VOR"), ("mode_nav", "MODE NAV"),
                ("mode_arc", "MODE ARC"), ("mode_plan", "MODE PLAN"),
                ("range_10", "RANGE 10"), ("range_20", "RANGE 20"), ("range_40", "RANGE 40"),
                ("range_80", "RANGE 80"), ("range_160", "RANGE 160"), ("range_320", "RANGE 320"),
                ("nav1_adf", "NAV 1 ADF"), ("nav1_off", "NAV 1 OFF"), ("nav1_vor", "NAV 1 VOR"),
                ("nav2_adf", "NAV 2 ADF"), ("nav2_off", "NAV 2 OFF"), ("nav2_vor", "NAV 2 VOR"),
            ):
                controls[f"{prefix}_{suffix}"] = {"label": f"{crew} {label}", "kind": "selector"}
            controls[f"{prefix}_baro_dec"] = {"label": f"{crew} BARO −", "group": "baro", "delta": -1, "kind": "knob"}
            controls[f"{prefix}_baro_inc"] = {"label": f"{crew} BARO +", "group": "baro", "delta": 1, "kind": "knob"}
        return controls

    def _apply_fcu_efis_visual(self, visual_key: str) -> None:
        """Record a verified BA01 input as the corresponding faceplate pose."""

        side, separator, control = visual_key.partition("_")
        panel = self._fcu_efis_visual.get(side) if separator else None
        if panel is None:
            return
        if control == "inhg":
            panel["unit"] = "inhg"
            panel["std"] = False
        elif control == "hpa":
            panel["unit"] = "hpa"
            panel["std"] = False
        elif control == "std_push":
            panel["std"] = True
        elif control == "std_pull":
            panel["std"] = False
        elif control.startswith("mode_"):
            panel["mode"] = control.removeprefix("mode_")
        elif control.startswith("range_"):
            try:
                panel["range"] = int(control.removeprefix("range_"))
            except ValueError:
                return
        elif control.startswith("nav1_"):
            panel["nav1"] = control.removeprefix("nav1_")
        elif control.startswith("nav2_"):
            panel["nav2"] = control.removeprefix("nav2_")
        elif control in panel["buttons"]:
            buttons = panel["buttons"]
            buttons[control] = not bool(buttons.get(control))

    def _draw_faceplate(self) -> None:
        canvas = self.faceplate
        canvas.delete("all")
        # Do not use the current window size as an aircraft-panel blueprint.
        # A wider window should not pull related switches apart, and a narrow
        # one must not force labels and hit areas into the same pixels.  Draw
        # every faceplate at its fixed authored size then centre that surface
        # in any extra room around it.
        viewport_width = max(canvas.winfo_width(), 1)
        viewport_height = max(canvas.winfo_height(), 1)
        width = FACEPLATE_DESIGN_WIDTH
        height = FACEPLATE_DESIGN_HEIGHT
        if self._selected_device == "fcu_32_efis":
            self._draw_fcu(canvas, width, height)
        elif self._selected_device == "pdc_bb62":
            self._draw_fixed_pdc(canvas, width, height)
        elif self._selected_device == "pdc_bb51":
            self._draw_pdc_efis(canvas, width, height)
        elif self._selected_device == "pap3_mag":
            self._draw_pap3(canvas, width, height)
        elif self._selected_device == "agp_bb80":
            # >>> MUSLIMSIM AGP FACEPLATE V1 >>>
            # Authored the same way the HOWALT faceplates are.  The original
            # generated layout stays as the fallback so a drawing error can
            # never leave the panel unusable.
            try:
                from ..devices.agp_faceplate import draw_agp_faceplate
                draw_agp_faceplate(self, canvas, width, height)
            except Exception:
                self._draw_agp(canvas, width, height)
            # <<< MUSLIMSIM AGP FACEPLATE V1 <<<
        elif self._selected_device == "pu_overhead":
            self._draw_pu_overhead(canvas, width, height)
        elif self._selected_device == "winctrl_throttle":
            self._draw_winctrl_throttle(canvas, width, height)
        elif self._selected_device == "winctrl_pedals":
            self._draw_winctrl_pedals(canvas, width, height)
        elif self._selected_device in {"moza_a210", "moza_ab6"}:
            self._draw_moza_calibration(canvas, width, height)
        elif self._selected_device == "ecam32":
            self._draw_ecam32(canvas, width, height)
        elif self._selected_device in {"pdc_bb61_left", "pdc_bb52_right"}:
            self._draw_fixed_pdc(canvas, width, height)
        elif self._selected_device == "pfp3n_bb35":
            # >>> MUSLIMSIM PFP3N AUTHORED FACEPLATE V1 >>>
            # Photo-authored Studio surface; the proven BB35 owner remains
            # untouched. Keep the generic keypad as a fail-safe fallback.
            try:
                from ..devices.pfp_bb35_faceplate import draw_pfp3n_faceplate
                draw_pfp3n_faceplate(self, canvas, width, height)
            except Exception:
                self._draw_fmc_keypad(canvas, width, height)
            # <<< MUSLIMSIM PFP3N AUTHORED FACEPLATE V1 <<<
        elif self._selected_device == "mcdu32_bb36":
            # >>> MUSLIMSIM MCDU32 AUTHORED FACEPLATE V1 >>>
            # Photo-authored Studio surface; the proven BB36 owner remains
            # untouched. Keep the generic keypad as a fail-safe fallback.
            try:
                from ..devices.mcdu_bb36_faceplate import draw_mcdu32_faceplate
                draw_mcdu32_faceplate(self, canvas, width, height)
            except Exception:
                self._draw_fmc_keypad(canvas, width, height)
            # <<< MUSLIMSIM MCDU32 AUTHORED FACEPLATE V1 <<<
        elif self._selected_device == "tca_boeing":
            self._draw_tca_boeing_set(canvas, width, height)
        # MUSLIMSIM_HOWALT_V4_STUDIO
        elif self._selected_device in {"muslimrtp_d201", "muslimatc_d203"}:
            from ..devices.howalt_v4_faceplates import draw_howalt_faceplate
            draw_howalt_faceplate(self, canvas, width, height)
        else:
            self._draw_device_surface(canvas, width, height)
        offset_x = max(0.0, (viewport_width - width) / 2)
        offset_y = max(0.0, (viewport_height - height) / 2)
        if offset_x or offset_y:
            try:
                canvas.move("all", offset_x, offset_y)
            except AttributeError:
                # Headless rendering tests use a deliberately tiny canvas
                # stand-in; the authored geometry remains valid there.
                pass
        if self._selected_device == "agp_bb80":
            # Use only the spare dark-blue Studio workspace beside the fixed
            # authored AGP.  Never shrink, stretch or move the hardware panel
            # to make room for help text.
            self._draw_agp_quick_reference(
                canvas,
                viewport_width,
                viewport_height,
                width,
                height,
                offset_x,
                offset_y,
            )

        if self._selected_device == "tca_boeing" and self._tca_axis_tracks:
            # The authored faceplate is centred after it is drawn.  Keep drag
            # geometry in the same moved canvas coordinate system.
            for track in self._tca_axis_tracks.values():
                track["top"] = float(track["top"]) + offset_y
                track["bottom"] = float(track["bottom"]) + offset_y
                track["current_y"] = float(track["current_y"]) + offset_y

    def _draw_agp_quick_reference(
        self,
        canvas: tk.Canvas,
        viewport_width: float,
        viewport_height: float,
        authored_width: float,
        authored_height: float,
        offset_x: float,
        offset_y: float,
    ) -> None:
        """Draw the AGP guide in the unused blue area LEFT of visible hardware.

        The user-designated location is the dark-blue gap immediately left of
        the AGP landing-gear lever. That gap partly lives inside the authored
        980x680 canvas, so using the authored-surface edge as the old placement
        boundary was too conservative and could hide the guide.

        This calculation mirrors the AGP faceplate's fixed 900x660 reference
        fit only far enough to find the first visible hardware pixel:
        reference x=24 is the left edge of the landing-gear panel. The guide
        ends before that edge and therefore cannot cover, move, shrink or
        stretch any AGP hardware.
        """

        edge = 12.0
        hardware_gap = 10.0
        min_width = 104.0
        max_width = 300.0

        # Match muslimsim.devices.agp_faceplate._fit() without importing or
        # changing the authored faceplate module.
        ref_width = 900.0
        ref_height = 660.0
        ref_hardware_left = 24.0
        scale = min(
            max(1.0, float(authored_width) - 24.0) / ref_width,
            max(1.0, float(authored_height) - 24.0) / ref_height,
        )
        scale = max(0.45, scale)
        local_ox = (
            float(authored_width) - ref_width * scale
        ) / 2.0

        visible_hardware_left = (
            float(offset_x)
            + local_ox
            + ref_hardware_left * scale
        )

        # Keep the card directly beside the AGP rather than at the far-left
        # edge when a very wide monitor leaves extra empty workspace.
        card_right = visible_hardware_left - hardware_gap
        available = card_right - edge
        if available < min_width:
            return
        card_width = min(max_width, available)
        card_left = card_right - card_width

        card_top = max(edge, float(offset_y) + 8.0)
        card_bottom = min(
            float(viewport_height) - edge,
            float(offset_y) + float(authored_height) - 8.0,
        )
        if card_bottom - card_top < 430.0:
            return

        mirror = self._device_mirror("agp_bb80")
        mode = str(mirror.get("page") or "radio").strip().lower()
        if mode not in {"radio", "navigation"}:
            mode = "radio"

        canvas.create_round_rect(
            card_left,
            card_top,
            card_right,
            card_bottom,
            radius=10,
            fill="#101b2d",
            outline="#39577c",
            width=1,
        )

        compact = card_width < 190.0
        pad = 8.0 if compact else 12.0
        title_size = 8 if compact else 11
        body_font = 7 if compact else 8
        heading_font = 8 if compact else 9

        canvas.create_text(
            card_left + pad,
            card_top + 10,
            text="AGP QUICK GUIDE",
            anchor="nw",
            fill="#f5f8ff",
            font=("Segoe UI Semibold", title_size),
        )
        canvas.create_text(
            card_left + pad,
            card_top + 28,
            text=f"CURRENT: {'NAV' if mode == 'navigation' else 'RADIO'}",
            anchor="nw",
            fill="#5aa9ff" if mode == "radio" else "#54d69f",
            font=("Segoe UI Semibold", 7 if compact else 8),
        )

        y = card_top + 48.0
        inner_left = card_left + pad
        wrap = max(88.0, card_width - pad * 2.0)

        def section(title: str, body: str, *, active: bool = False) -> None:
            nonlocal y
            if y > card_bottom - 26:
                return
            canvas.create_text(
                inner_left,
                y,
                text=title,
                anchor="nw",
                fill="#ffd166" if active else "#8fbdf2",
                font=("Segoe UI Semibold", heading_font),
            )
            y += 15.0
            item = canvas.create_text(
                inner_left,
                y,
                text=body,
                anchor="nw",
                justify="left",
                width=wrap,
                fill="#c6d2e6",
                font=("Segoe UI", body_font),
            )
            try:
                box = canvas.bbox(item)
            except Exception:
                box = None
            if box:
                y = float(box[3]) + 8.0
            else:
                y += max(30.0, 12.0 * (body.count("\n") + 1))

        section(
            "MODE",
            "TERR ON ND\n"
            "RADIO <-> NAV\n"
            "Only TERR changes mode.",
        )
        section(
            "RADIO",
            "GPS / INT / SET\n"
            "= VHF1 / VHF2 / VHF3\n"
            "CHR turn = coarse tune\n"
            "RST turn = fine tune\n"
            "RST push = ACTIVE/STBY\n"
            "CHR push = user remap",
            active=mode == "radio",
        )
        section(
            "ATC / SQUAWK",
            "SET long = edit / next digit\n"
            "Flashing digit = selected\n"
            "SET turn = change digit\n"
            "SET tap = finish / stop flash\n"
            "RUN = STBY\n"
            "STP = ALT OFF\n"
            "RST spring = ALT ON > TA > TA/RA\n"
            "Mode shows 1.5s, then squawk.",
            active=mode == "radio",
        )
        section(
            "NAV",
            "RST turn = SPEED\n"
            "CHR turn = ALTITUDE\n"
            "SET turn = HEADING\n"
            "TERR returns to RADIO.",
            active=mode == "navigation",
        )
        section(
            "PANEL",
            "GEAR UP / DOWN\n"
            "BRK FAN ON / OFF\n"
            "AUTO BRK LO / MED / MAX\n"
            "A/SKID ON / OFF",
        )

    def _live_control_active(self, key: str) -> bool:
        """Read the bridge-held physical state instead of the diagnostic ring.

        The diagnostics list is intentionally bounded to 100 records and is a
        useful event log, not a state transport.  HardwareLab.inputs is the
        authoritative latest state and therefore keeps a control visibly alive
        even if several other panels generated enough events to evict its log
        record before Studio's next poll.
        """

        device = str(self._selected_device or "")
        if not device or not key:
            return False
        source = self._learned_source(key) or key
        kind = self._control_kinds.get(device, {}).get(
            source,
            self._control_kinds.get(device, {}).get(key, ""),
        )
        return physical_input_active(
            self._lab, device, source, kind=kind, now_wall=time.time()
        )

    def _control_color(self, key: str) -> str:
        if self._flash_until.get(key, 0.0) > time.monotonic():
            return "#00ffd1"
        live_active = (
            self._live_control_active(key)
            if hasattr(self, "_live_control_active")
            else False
        )
        if live_active:
            return "#35e7cf"
        if key == self._selected_visual:
            return "#ffd166"
        if self._learned_source(key):
            return BLUE
        return "#50617e"

    def _control_fill(self, key: str, default: str = "#202e49") -> str:
        """Return an unambiguous live/selected faceplate state colour."""

        if self._flash_until.get(key, 0.0) > time.monotonic():
            return "#087f76"
        live_active = (
            self._live_control_active(key)
            if hasattr(self, "_live_control_active")
            else False
        )
        if live_active:
            return "#0a655e"
        if key == self._selected_visual:
            return "#4c3915"
        return default

    def _highlight_ring(self, canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, key: str, *, radius: float = 7) -> None:
        if (
            key != self._selected_visual
            and self._flash_until.get(key, 0.0) <= time.monotonic()
            and not (
                self._live_control_active(key)
                if hasattr(self, "_live_control_active")
                else False
            )
        ):
            return
        ring = canvas.create_round_rect(
            x1 - 4, y1 - 4, x2 + 4, y2 + 4, radius=radius + 3,
            fill="", outline=self._control_color(key), width=3,
        )
        self._tag(canvas, ring, key)

    def _tag(self, canvas: tk.Canvas, item: int, key: str) -> None:
        canvas.addtag_withtag(f"control:{key}", item)

    def _tag_capture(self, canvas: tk.Canvas, item: int, target: str) -> None:
        """Mark a panel location that needs one real-input capture first."""

        canvas.addtag_withtag(f"capture:{target}", item)

    def _draw_capture_button(
        self, canvas: tk.Canvas, x: float, y: float, label: str, target: str, *, width: int = 72,
    ) -> None:
        """Draw an unverified AGP location without presenting it as mapped."""

        color = self._control_color(target)
        self._highlight_ring(canvas, x - width / 2, y - 16, x + width / 2, y + 16, target, radius=6)
        item = canvas.create_round_rect(
            x - width / 2, y - 16, x + width / 2, y + 16, radius=6,
            fill=self._control_fill(target, "#202936"), outline=color,
            width=3 if target == self._selected_visual else 2,
        )
        text = canvas.create_text(x, y - 2, text=label, fill=INK, font=("Segoe UI Semibold", 7))
        detail = canvas.create_text(x, y + 10, text="CAPTURE" if not self._learned_source(target) else "RAW MAPPED", fill=color, font=("Segoe UI", 6))
        for token in (item, text, detail):
            self._tag_capture(canvas, token, target)

    def _draw_button(self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, *, width: int = 72) -> None:
        color = self._control_color(key)
        self._highlight_ring(canvas, x - width / 2, y - 19, x + width / 2, y + 19, key)
        item = canvas.create_round_rect(x - width / 2, y - 19, x + width / 2, y + 19, radius=7, fill=self._control_fill(key), outline=color, width=3 if key == self._selected_visual else 2)
        self._tag(canvas, item, key)
        text = canvas.create_text(x, y, text=label, fill=INK, font=("Segoe UI Semibold", 9))
        self._tag(canvas, text, key)

    def _draw_mini_button(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, *,
        width: int = 54, half_height: int = 10, font_size: int = 7,
        layout_tag: str = "",
    ) -> None:
        """Dense selectable detent used where the real EFIS has a selector."""

        color = self._control_color(key)
        self._highlight_ring(canvas, x - width / 2, y - half_height, x + width / 2, y + half_height, key, radius=4)
        item = canvas.create_round_rect(x - width / 2, y - half_height, x + width / 2, y + half_height, radius=4, fill=self._control_fill(key), outline=color, width=2 if key == self._selected_visual else 1)
        self._tag(canvas, item, key)
        text = canvas.create_text(x, y, text=label, fill=INK, font=("Segoe UI Semibold", font_size))
        self._tag(canvas, text, key)
        if layout_tag:
            canvas.addtag_withtag(layout_tag, item)
            canvas.addtag_withtag(layout_tag, text)

    def _draw_knob(self, canvas: tk.Canvas, x: float, y: float, label: str, value: str, group: str, *, compact: bool = False) -> None:
        radius = 29 if compact else 42
        core_radius = 20 if compact else 29
        label_offset = 43 if compact else 60
        value_offset = 58 if compact else 79
        for key, extent, start in ((f"{group}_dec", 130, 205), (f"{group}_inc", 130, 25)):
            item = canvas.create_arc(x - radius, y - radius, x + radius, y + radius, start=start, extent=extent, style="arc", outline=self._control_color(key), width=7 if compact else 10)
            self._tag(canvas, item, key)
        self._highlight_ring(canvas, x - core_radius, y - core_radius, x + core_radius, y + core_radius, f"{group}_push", radius=core_radius)
        core = canvas.create_oval(x - core_radius, y - core_radius, x + core_radius, y + core_radius, fill=self._control_fill(f"{group}_push", "#111a2b"), outline=self._control_color(f"{group}_push"), width=3 if f"{group}_push" == self._selected_visual else 2)
        self._tag(canvas, core, f"{group}_push")
        dot_y = y - core_radius + 7
        dot = canvas.create_oval(x - 3, dot_y, x + 3, dot_y + 6, fill=ACCENT, outline="")
        self._tag(canvas, dot, f"{group}_push")
        text = canvas.create_text(x, y + label_offset, text=label, fill=MUTED, font=("Segoe UI Semibold", 9 if compact else 10))
        self._tag(canvas, text, f"{group}_push")
        if compact:
            canvas.addtag_withtag("fcu-knob-labels", text)
        if value:
            display = canvas.create_text(x, y + value_offset, text=value, fill="#b9f7df", font=("Consolas", 11 if compact else 14, "bold"))
            self._tag(canvas, display, f"{group}_push")

    def _efis_state(self, values: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        """Combine confirmed practice values with the live BA01 faceplate cache."""

        stored = self._fcu_efis_visual[prefix]
        buttons = dict(stored["buttons"])
        for button in buttons:
            key = f"{prefix}_{button}"
            if key in values:
                buttons[button] = self._number(values, key, 0.0) >= 0.5
        state: Dict[str, Any] = {
            "unit": stored["unit"], "std": bool(stored["std"]),
            "mode": stored["mode"], "range": stored["range"],
            "nav1": stored["nav1"], "nav2": stored["nav2"], "buttons": buttons,
        }
        if f"{prefix}_baro_inhg" in values:
            state["unit"] = "inhg" if self._number(values, f"{prefix}_baro_inhg", 1.0) >= 0.5 else "hpa"
        if f"{prefix}_baro_std" in values:
            state["std"] = self._number(values, f"{prefix}_baro_std", 0.0) >= 0.5
        for field in ("mode", "nav1", "nav2"):
            candidate = str(values.get(f"{prefix}_{field}") or "").lower()
            if candidate:
                state[field] = candidate
        if f"{prefix}_range" in values:
            state["range"] = round(self._number(values, f"{prefix}_range", stored["range"]))
        return state

    def _draw_efis_toggle(self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, active: bool) -> None:
        """A labelled on/off switch with a dot that travels along its track."""

        track_left, track_right = x - 3, x + 27
        color = self._control_color(key)
        label_item = canvas.create_text(x - 14, y, text=label, anchor="e", fill=INK, font=("Segoe UI Semibold", 8))
        self._tag(canvas, label_item, key)
        hit = canvas.create_rectangle(x - 38, y - 10, x + 31, y + 10, outline="", fill="")
        self._tag(canvas, hit, key)
        line = canvas.create_line(track_left, y, track_right, y, fill="#50617e", width=3, capstyle="round")
        self._tag(canvas, line, key)
        dot_x = track_right if active else track_left
        dot_color = "#00ffd1" if self._flash_until.get(key, 0.0) > time.monotonic() else ("#ffd166" if key == self._selected_visual else ACCENT)
        dot = canvas.create_oval(dot_x - 4, y - 4, dot_x + 4, y + 4, fill=dot_color, outline=color, width=1)
        self._tag(canvas, dot, key)

    def _draw_efis_selector(
        self, canvas: tk.Canvas, x: float, y: float, options: tuple[tuple[str, str], ...], active: str, *,
        width: float = 144, font_size: int = 6, label_offset: int = 11,
        layout_tag: str = "",
    ) -> None:
        """A multi-position EFIS selector: the dot moves to the chosen detent."""

        if not options:
            return
        start, end = x - width / 2, x + width / 2
        baseline = canvas.create_line(start, y, end, y, fill="#50617e", width=2, capstyle="round")
        if layout_tag:
            canvas.addtag_withtag(f"{layout_tag}:line", baseline)
        count = max(1, len(options) - 1)
        active_key = options[0][1]
        active_position = start
        for index, (label, key) in enumerate(options):
            position = start + (end - start) * index / count
            tick = canvas.create_line(position, y - 4, position, y + 4, fill=self._control_color(key), width=1)
            self._tag(canvas, tick, key)
            text = canvas.create_text(position, y + label_offset, text=label, fill=INK if key.endswith(active) else MUTED, font=("Segoe UI Semibold", font_size))
            self._tag(canvas, text, key)
            if layout_tag:
                canvas.addtag_withtag(f"{layout_tag}:labels", text)
            hit = canvas.create_rectangle(position - 13, y - 9, position + 13, y + label_offset + 9, outline="", fill="")
            self._tag(canvas, hit, key)
            if key.endswith(active):
                active_key = key
                active_position = position
        dot_color = "#00ffd1" if self._flash_until.get(active_key, 0.0) > time.monotonic() else ("#ffd166" if active_key == self._selected_visual else ACCENT)
        dot = canvas.create_oval(active_position - 4, y - 4, active_position + 4, y + 4, fill=dot_color, outline="#d9fff8")
        self._tag(canvas, dot, active_key)

    def _draw_efis_unit_arc(self, canvas: tk.Canvas, x: float, y: float, prefix: str, unit: str) -> None:
        """BARO unit switch with a moving dot at either end of the arc."""

        left_key, right_key = f"{prefix}_inhg", f"{prefix}_hpa"
        arc = canvas.create_arc(x - 46, y - 24, x + 46, y + 24, start=198, extent=144, style="arc", outline="#50617e", width=3)
        canvas.addtag_withtag("fcu-baro-unit-arc", arc)
        positions = ((x - 44, "inHg", left_key, "inhg"), (x + 44, "hPa", right_key, "hpa"))
        active_key = left_key if unit == "inhg" else right_key
        for position, label, key, value in positions:
            text = canvas.create_text(position, y + 22, text=label, fill=INK if value == unit else MUTED, font=("Segoe UI Semibold", 8))
            self._tag(canvas, text, key)
            canvas.addtag_withtag("fcu-baro-unit-labels", text)
            hit = canvas.create_rectangle(position - 20, y - 14, position + 20, y + 29, outline="", fill="")
            self._tag(canvas, hit, key)
        dot_x = x - 44 if unit == "inhg" else x + 44
        dot_color = "#00ffd1" if self._flash_until.get(active_key, 0.0) > time.monotonic() else ("#ffd166" if active_key == self._selected_visual else ACCENT)
        dot = canvas.create_oval(dot_x - 5, y - 11, dot_x + 5, y - 1, fill=dot_color, outline="#d9fff8")
        self._tag(canvas, dot, active_key)

    def _draw_fcu(self, canvas: tk.Canvas, width: int, height: int) -> None:
        mirror = self._device_mirror("fcu_32_efis")
        values = dict(mirror.get("values") or {})
        fallback = self._fcu_values
        speed = self._number(values, "speed", fallback["speed"])
        speed_is_mach = self._number(values, "speed_is_mach", 0.0) >= 0.5
        heading = self._number(values, "heading", fallback["heading"])
        altitude = self._number(values, "altitude", fallback["altitude"])
        vertical_speed = self._number(values, "vertical_speed", fallback["vs"])
        margin = 30
        panel_y = 80
        # The FCU is a four-column strip.  Keep the EFIS wings narrow enough
        # to give every LCD and rotary its own footprint, even on a compact
        # Studio window.
        panel_h = min(height - 110, 500)
        side_width = max(168, min(184, (width - 2 * margin) * 0.22))
        side_half = side_width / 2
        left_efis_x = margin + side_half
        right_efis_x = width - margin - side_half
        fcu_left = margin + side_width + 16
        fcu_right = width - margin - side_width - 16
        if fcu_right - fcu_left < 380:
            # Preserve four non-overlapping columns before sacrificing the
            # side-panel width on unusually small windows.
            side_width = max(148, (width - 2 * margin - 412) / 2)
            side_half = side_width / 2
            left_efis_x = margin + side_half
            right_efis_x = width - margin - side_half
            fcu_left = margin + side_width + 10
            fcu_right = width - margin - side_width - 10
        canvas.create_rectangle(margin, panel_y, width - margin, panel_y + panel_h, fill="#111a2c", outline="#344664", width=2)
        canvas.create_text(margin + 22, panel_y + 20, text="AIRBUS-STYLE FCU / EFIS VISUAL STUDIO", anchor="w", fill=MUTED, font=("Segoe UI Semibold", 12))
        canvas.create_text(width - margin - 22, panel_y + 20, state="hidden", text="Blue = mapped/default  •  gold = selected  •  teal = live press", anchor="e", fill=MUTED, font=("Segoe UI", 10))

        # The centre follows the FCU's physical grouping.  Each of the four
        # displays has a fixed compact column: no shared window, knob arc, or
        # row of buttons can occupy another control's hit target.
        fcu_top, fcu_bottom = panel_y + 76, panel_y + 338
        canvas.create_round_rect(fcu_left, fcu_top, fcu_right, fcu_bottom, radius=16, fill="#1b273e", outline="#425675", width=2)
        canvas.create_text(fcu_left + 18, fcu_top + 20, text="FLIGHT CONTROL UNIT", anchor="w", fill=INK, font=("Segoe UI Semibold", 12))
        column_width = (fcu_right - fcu_left) / 4
        centers = (
            (fcu_left + column_width * .5, "speed", "SPEED", f"M{speed:.2f}" if speed_is_mach else f"{round(speed):03d}"),
            (fcu_left + column_width * 1.5, "heading", "HDG", f"{round(heading) % 360:03d}"),
            (fcu_left + column_width * 2.5, "altitude", "ALT", f"{round(altitude):05d}"),
            (fcu_left + column_width * 3.5, "vs", "V/S", f"{round(vertical_speed):+05d}"),
        )
        for x, group, label, value in centers:
            display_half = min(47, max(38, column_width / 2 - 7))
            canvas.create_round_rect(x - display_half, fcu_top + 40, x + display_half, fcu_top + 72, radius=4, fill="#07100e", outline="#5a705f")
            canvas.create_text(x, fcu_top + 56, text=value, fill="#b9f7df", font=("Consolas", 15, "bold"))
            self._draw_knob(canvas, x, fcu_top + 119, label, "", group, compact=True)
            self._draw_mini_button(
                canvas, x, fcu_top + 185, "PULL", f"{group}_pull",
                width=48, half_height=11, font_size=8, layout_tag="fcu-pull-row",
            )
        for row, keys in enumerate((("mach", "loc", "trk", "ap1", "ap2", "athr"), ("exped", "metric", "appr", "altitude_step_100", "altitude_step_1000"))):
            step = (fcu_right - fcu_left - 60) / max(1, len(keys) - 1)
            for index, key in enumerate(keys):
                info = self._fcu_controls()[key]
                self._draw_mini_button(
                    canvas, fcu_left + 30 + index * step, fcu_top + 214 + row * 27,
                    str(info["label"]), key, width=64, half_height=11,
                    font_size=8, layout_tag=f"fcu-button-row-{row + 1}",
                )

        # EFIS wings make captain/first-officer controls separately mappable.
        for side, x, prefix in (("CAPTAIN EFIS", left_efis_x, "left"), ("FIRST-OFFICER EFIS", right_efis_x, "right")):
            canvas.create_round_rect(x - side_half, panel_y + 54, x + side_half, panel_y + panel_h - 10, radius=14, fill="#1b273e", outline="#425675", width=2)
            canvas.create_text(x, panel_y + 76, text=side, fill=INK, font=("Segoe UI Semibold", 10, "bold"))
            state = self._efis_state(values, prefix)
            baro_std = bool(state["std"])
            baro_inhg = state["unit"] == "inhg"
            baro_value = self._number(values, f"{prefix}_baro", 29.92)
            baro_text = "STD" if baro_std else (f"{baro_value * 100:04.0f}" if baro_inhg else f"{baro_value * 33.8639:04.0f}")
            canvas.create_round_rect(x - side_half + 12, panel_y + 87, x + side_half - 12, panel_y + 121, radius=4, fill="#07100e", outline="#5a705f")
            canvas.create_text(x, panel_y + 104, text=f"BARO  {baro_text}", fill="#b9f7df", font=("Consolas", 13, "bold"), width=158)
            for index, suffix in enumerate(("fd", "ls", "cstr", "wpt", "vord", "ndb", "arpt")):
                row, column = divmod(index, 2)
                key = f"{prefix}_{suffix}"
                self._draw_efis_toggle(
                    canvas, x - 42 + column * 84, panel_y + 141 + row * 22,
                    suffix.upper(), key, bool(state["buttons"].get(suffix)),
                )
            # The physical BARO push/pull changes between STD and QNH.  The
            # two labelled endpoints are selectable and the dot makes that
            # current simulated position immediately obvious.
            self._draw_efis_selector(
                canvas, x, panel_y + 218,
                (("STD", f"{prefix}_std_push"), ("QNH", f"{prefix}_std_pull")),
                "std_push" if baro_std else "std_pull", width=92,
                font_size=8, label_offset=13, layout_tag=f"fcu-{prefix}-std",
            )
            for key, start in ((f"{prefix}_baro_dec", 205), (f"{prefix}_baro_inc", 25)):
                item = canvas.create_arc(x - 24, panel_y + 245, x + 24, panel_y + 285, start=start, extent=130, style="arc", outline=self._control_color(key), width=6)
                self._tag(canvas, item, key)
                canvas.addtag_withtag(f"fcu-{prefix}-baro-arc", item)
            canvas.create_text(x, panel_y + 265, text="BARO", fill=MUTED, font=("Segoe UI Semibold", 9))
            self._draw_efis_unit_arc(canvas, x, panel_y + 313, prefix, str(state["unit"]))
            canvas.create_text(x, panel_y + 350, text="MAP MODE", fill=MUTED, font=("Segoe UI Semibold", 8), tags=(f"fcu-{prefix}-map-heading",))
            self._draw_efis_selector(
                canvas, x, panel_y + 364,
                (("LS", f"{prefix}_mode_ls"), ("VOR", f"{prefix}_mode_vor"), ("NAV", f"{prefix}_mode_nav"), ("ARC", f"{prefix}_mode_arc"), ("PLAN", f"{prefix}_mode_plan")),
                str(state["mode"]), width=142, font_size=8, label_offset=13,
                layout_tag=f"fcu-{prefix}-map",
            )
            canvas.create_text(x, panel_y + 391, text="RANGE", fill=MUTED, font=("Segoe UI Semibold", 8), tags=(f"fcu-{prefix}-range-heading",))
            self._draw_efis_selector(
                canvas, x, panel_y + 405,
                (("10", f"{prefix}_range_10"), ("20", f"{prefix}_range_20"), ("40", f"{prefix}_range_40"), ("80", f"{prefix}_range_80"), ("160", f"{prefix}_range_160"), ("320", f"{prefix}_range_320")),
                str(state["range"]), width=146, font_size=8, label_offset=13,
                layout_tag=f"fcu-{prefix}-range",
            )
            canvas.create_text(x - side_half + 14, panel_y + 438, text="1", fill=MUTED, font=("Segoe UI Semibold", 8))
            self._draw_efis_selector(
                canvas, x + 8, panel_y + 438,
                (("ADF", f"{prefix}_nav1_adf"), ("OFF", f"{prefix}_nav1_off"), ("VOR", f"{prefix}_nav1_vor")),
                str(state["nav1"]), width=106, font_size=8, label_offset=13,
                layout_tag=f"fcu-{prefix}-nav1",
            )
            canvas.create_text(x - side_half + 14, panel_y + 468, text="2", fill=MUTED, font=("Segoe UI Semibold", 8))
            self._draw_efis_selector(
                canvas, x + 8, panel_y + 468,
                (("ADF", f"{prefix}_nav2_adf"), ("OFF", f"{prefix}_nav2_off"), ("VOR", f"{prefix}_nav2_vor")),
                str(state["nav2"]), width=106, font_size=8, label_offset=13,
                layout_tag=f"fcu-{prefix}-nav2",
            )

        if not self._detected.get("fcu_32_efis"):
            canvas.create_rectangle(margin, panel_y + panel_h - 48, width - margin, panel_y + panel_h, fill="#352735", outline="")
            canvas.create_text(width / 2, panel_y + panel_h - 24, text="FCU/EFIS is not currently detected.", fill="#ffd4ec", font=("Segoe UI", 10))

    def _device_mirror(self, device_key: str) -> Dict[str, Any]:
        # MUSLIMSIM_PRACTICE_DATA_PLANE_V4
        # Keep three independent truths:
        #   1) the device manager's raw live mirror;
        #   2) the bridge-owned Practice preview;
        #   3) HardwareLab physical inputs / actual outputs.
        # Practice is an overlay, never a replacement for physical truth.
        state = dict(self._device_states.get(device_key, {}) or {})
        preview = None
        if self.practice_mode.get():
            candidate = self._preview_snapshot.get(device_key)
            if isinstance(candidate, dict):
                preview = dict(candidate)
        return compose_live_mirror(
            device_key,
            state,
            getattr(self, "_lab", {}),
            practice_preview=preview,
        )

    @staticmethod
    def _number(values: Dict[str, Any], key: str, fallback: float) -> float:
        try:
            return float(values.get(key, fallback))
        except (TypeError, ValueError):
            return float(fallback)

    def _draw_window(self, canvas: tk.Canvas, x: float, y: float, label: str, value: str, *, width: int = 106) -> None:
        canvas.create_round_rect(x - width / 2, y - 22, x + width / 2, y + 22, radius=5, fill="#06100e", outline="#5a705f")
        canvas.create_text(x - width / 2 + 7, y - 14, text=label, anchor="w", fill="#688e82", font=("Segoe UI Semibold", 7))
        canvas.create_text(x, y + 5, text=value, fill="#bcf9dc", font=("Consolas", 14, "bold"))

    def _draw_rotary(self, canvas: tk.Canvas, x: float, y: float, label: str, value: str, *, dec: str, inc: str, width: int = 82) -> None:
        radius = 31
        for key, start in ((dec, 205), (inc, 25)):
            item = canvas.create_arc(x - radius, y - radius, x + radius, y + radius, start=start, extent=130, style="arc", outline=self._control_color(key), width=8)
            self._tag(canvas, item, key)
        live_checker = getattr(self, "_live_control_active", lambda _key: False)
        dec_live = live_checker(dec)
        inc_live = live_checker(inc)
        active_key = dec if (dec == self._selected_visual or self._flash_until.get(dec, 0.0) > time.monotonic() or dec_live) else inc
        if (
            active_key == inc
            and inc != self._selected_visual
            and self._flash_until.get(inc, 0.0) <= time.monotonic()
            and not inc_live
        ):
            active_key = ""
        if active_key:
            self._highlight_ring(canvas, x - 20, y - 20, x + 20, y + 20, active_key, radius=20)
        canvas.create_oval(x - 20, y - 20, x + 20, y + 20, fill=self._control_fill(active_key, "#101a2b"), outline=self._control_color(active_key) if active_key else "#7a89a8", width=3 if active_key else 2)
        # Relative encoders have no absolute shaft angle.  Show a truthful
        # direction tick while a recent physical pulse is active rather than
        # pretending the knob has a stored position.
        if dec_live or inc_live:
            direction = -1 if dec_live and not inc_live else 1
            canvas.create_line(
                x, y - 3, x + direction * 12, y - 13,
                fill="#35e7cf", width=3, capstyle="round",
            )
        canvas.create_text(x, y + 43, text=label, fill=MUTED, font=("Segoe UI Semibold", 8), width=width)
        canvas.create_text(x, y + 57, text=value, fill="#bcf9dc", font=("Consolas", 10, "bold"))

    def _draw_agp_press_rotary(
        self, canvas: tk.Canvas, x: float, y: float, label: str, raw_value: int,
        *, dec: str, press: str, inc: str,
    ) -> None:
        """Draw one verified AGP push encoder, including its live raw count."""

        radius = 39
        for key, start in ((dec, 205), (inc, 25)):
            arc = canvas.create_arc(
                x - radius, y - radius, x + radius, y + radius,
                start=start, extent=130, style="arc",
                outline=self._control_color(key), width=8,
            )
            self._tag(canvas, arc, key)
        for key, x1, x2 in ((dec, x - 58, x - 18), (inc, x + 18, x + 58)):
            hit = canvas.create_rectangle(x1, y - 37, x2, y + 25, fill="", outline="")
            self._tag(canvas, hit, key)
        active_key = next(
            (key for key in (press, dec, inc) if key == self._selected_visual or self._flash_until.get(key, 0.0) > time.monotonic()),
            "",
        )
        if active_key:
            self._highlight_ring(canvas, x - 23, y - 23, x + 23, y + 23, active_key, radius=22)
        centre = canvas.create_oval(
            x - 22, y - 22, x + 22, y + 22,
            fill=self._control_fill(press if active_key == press else "", "#253348"),
            outline=self._control_color(press), width=3 if press == self._selected_visual else 2,
        )
        self._tag(canvas, centre, press)
        # The counter is signed and continuous, so this short tick only shows
        # a recent turning pose; it does not claim an unsupported end-stop.
        tick = (int(raw_value) % 13) - 6
        pointer = canvas.create_line(x, y, x + tick * 2, y - 14, fill="#e0e8f6", width=3, capstyle="round")
        self._tag(canvas, pointer, press)
        title = canvas.create_text(x, y + 54, text=label, fill=INK, font=("Segoe UI Semibold", 9))
        raw = canvas.create_text(x, y + 70, text=f"RAW {int(raw_value):+06d}", fill="#bcf9dc", font=("Consolas", 8, "bold"))
        hint = canvas.create_text(x, y + 84, text="CCW    PUSH    CW", fill=MUTED, font=("Segoe UI", 6))
        self._tag(canvas, title, press)
        self._tag(canvas, raw, press)
        self._tag(canvas, hint, press)

    def _draw_agp_three_way_selector(
        self, canvas: tk.Canvas, x: float, y: float, title: str,
        options: tuple[tuple[str, str], ...], active_key: str,
    ) -> None:
        """Draw a physical three-position AGP clock selector with detents."""

        if len(options) != 3:
            return
        positions = ((x - 30, y + 13), (x, y - 28), (x + 30, y + 13))
        canvas.create_text(x, y - 52, text=title, fill="#f2d7a1", font=("Segoe UI Semibold", 8))
        bezel = canvas.create_oval(x - 28, y - 28, x + 28, y + 28, fill="#0b121e", outline="#71829a", width=2)
        self._tag(canvas, bezel, active_key)
        selected = next((index for index, (_label, key) in enumerate(options) if key == active_key), 1)
        px, py = positions[selected]
        pointer = canvas.create_line(x, y, px, py, fill="#dbe6f8", width=4, capstyle="round")
        self._tag(canvas, pointer, active_key)
        for index, ((label, key), (dot_x, dot_y)) in enumerate(zip(options, positions)):
            active = key == active_key
            dot = canvas.create_oval(dot_x - 5, dot_y - 5, dot_x + 5, dot_y + 5, fill=ACCENT if active else "#26364d", outline=self._control_color(key))
            self._tag(canvas, dot, key)
            label_y = y + 45 if index != 1 else y - 43
            label_item = canvas.create_text(dot_x, label_y, text=label, fill=self._control_color(key), font=("Segoe UI Semibold", 7))
            hit = canvas.create_rectangle(dot_x - 26, label_y - 12, dot_x + 26, label_y + 10, fill="", outline="")
            self._tag(canvas, label_item, key)
            self._tag(canvas, hit, key)

    def _draw_agp_flip_toggle(
        self, canvas: tk.Canvas, x: float, y: float, title: str,
        *, on_key: str, off_key: str, active: bool,
    ) -> None:
        """Draw an AGP two-position lever with a visible moving detent ball."""

        canvas.create_text(x, y - 39, text=title, fill=INK, font=("Segoe UI Semibold", 8))
        rail = canvas.create_line(x - 37, y, x + 37, y, fill="#596c84", width=5, capstyle="round")
        self._tag(canvas, rail, on_key)
        self._tag(canvas, rail, off_key)
        for dot_x, key, label in ((x - 34, on_key, "ON"), (x + 34, off_key, "OFF")):
            detent = canvas.create_oval(
                dot_x - 8, y - 8, dot_x + 8, y + 8,
                fill="#0b121e", outline=self._control_color(key), width=2,
            )
            text = canvas.create_text(dot_x, y + 22, text=label, fill=self._control_color(key), font=("Segoe UI Semibold", 7))
            hit = canvas.create_rectangle(dot_x - 25, y - 17, dot_x + 25, y + 33, fill="", outline="")
            self._tag(canvas, detent, key)
            self._tag(canvas, text, key)
            self._tag(canvas, hit, key)
        ball_x = x - 34 if active else x + 34
        active_key = on_key if active else off_key
        lever = canvas.create_line(x, y - 18, ball_x, y, fill="#dce8f7", width=5, capstyle="round")
        ball = canvas.create_oval(
            ball_x - 10, y - 10, ball_x + 10, y + 10,
            fill=ACCENT if active else "#9aa9bb", outline=self._control_color(active_key), width=3,
        )
        self._tag(canvas, lever, active_key)
        self._tag(canvas, ball, active_key)

    def _draw_agp_square_switch(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str,
        *, active: bool = False,
    ) -> None:
        """Draw the AGP's square, back-lit push-switch face without latching a press."""

        pressed = key == self._selected_visual or self._flash_until.get(key, 0.0) > time.monotonic()
        face_fill = "#195253" if active else self._control_fill(key, "#1a2432")
        face_outline = ACCENT if active else self._control_color(key)
        self._highlight_ring(canvas, x - 26, y - 26, x + 26, y + 26, key, radius=6)
        bezel = canvas.create_round_rect(x - 25, y - 25, x + 25, y + 25, radius=5, fill="#090f18", outline="#8190a6", width=2)
        face = canvas.create_round_rect(
            x - 20, y - 20, x + 20, y + 20, radius=4, fill=face_fill,
            outline=face_outline, width=3 if active or pressed else 2,
        )
        text = canvas.create_text(x, y, text=label, fill=INK, font=("Segoe UI Semibold", 7), justify="center", width=38)
        hit = canvas.create_rectangle(x - 28, y - 28, x + 28, y + 28, fill="", outline="")
        self._tag(canvas, bezel, key)
        self._tag(canvas, face, key)
        self._tag(canvas, text, key)
        self._tag(canvas, hit, key)

    def _draw_switch(self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, active: bool) -> None:
        color = ACCENT if active else self._control_color(key)
        self._highlight_ring(canvas, x - 31, y - 15, x + 31, y + 15, key, radius=5)
        item = canvas.create_round_rect(x - 31, y - 15, x + 31, y + 15, radius=5, fill="#234f50" if active else self._control_fill(key), outline=color, width=3 if key == self._selected_visual else 2)
        self._tag(canvas, item, key)
        text = canvas.create_text(x, y, text=label, fill=INK, font=("Segoe UI Semibold", 8))
        self._tag(canvas, text, key)

    def _pu_input_value(self, key: str, fallback: float = 0.0) -> float:
        """Read one verified PU input without treating a missing report as OFF."""

        inputs = self._lab.get("inputs")
        pu_inputs = dict(inputs.get("pu_overhead") or {}) if isinstance(inputs, dict) else {}
        item = pu_inputs.get(key)
        if isinstance(item, dict):
            return self._number(item, "value", fallback)
        return fallback

    def _pu_choice_index(self, key: str, fallback: int, choices: tuple[str, ...]) -> int:
        value = int(round(self._pu_input_value(key, float(fallback))))
        return max(0, min(max(0, len(choices) - 1), value))

    def _set_pu_visual_input(self, key: str, value: int | float, phase: str) -> None:
        """Make a test click feel immediate while the bridge confirms it."""

        inputs = self._lab.setdefault("inputs", {})
        pu_inputs = inputs.setdefault("pu_overhead", {})
        if isinstance(pu_inputs, dict):
            pu_inputs[key] = {"value": value, "phase": phase, "source": "virtual"}

    def _device_input_value(self, device: str, key: str, fallback: float = 0.0) -> float:
        """Read the last lab value for any captured physical input."""

        inputs = self._lab.get("inputs")
        device_inputs = dict(inputs.get(device) or {}) if isinstance(inputs, dict) else {}
        item = device_inputs.get(key)
        return self._number(item, "value", fallback) if isinstance(item, dict) else fallback

    def _set_device_visual_input(self, device: str, key: str, value: int | float, phase: str = "change") -> None:
        """Show an axis move immediately, before the bridge status round-trip."""

        inputs = self._lab.setdefault("inputs", {})
        device_inputs = inputs.setdefault(device, {})
        if isinstance(device_inputs, dict):
            device_inputs[key] = {"value": value, "phase": phase, "source": "virtual"}

    @staticmethod
    def _axis_fraction(value: float) -> float:
        """Normalize SDL, HID-word and already-normalized values for a lever pose."""

        if value > 1.001:
            value /= 65535.0
        elif value < -0.001:
            value = (value + 1.0) / 2.0
        return max(0.0, min(1.0, value))

    def _throttle_axis_fraction(self, key: str) -> float:
        return self._axis_fraction(self._device_input_value("winctrl_throttle", key, 0.0))

    def _throttle_output_value(self, key: str, fallback: int = 0) -> int:
        """Read a bridge-confirmed B930 output without blocking the UI."""

        outputs = self._lab.get("outputs")
        device_outputs = dict(outputs.get("winctrl_throttle") or {}) if isinstance(outputs, dict) else {}
        item = device_outputs.get(key)
        if isinstance(item, dict):
            return max(0, min(255, int(round(self._number(item, "value", fallback)))) )
        state = self._device_states.get("winctrl_throttle", {})
        mirror = state.get("mirror", {}) if isinstance(state, dict) else {}
        values = dict(mirror.get("values") or {}) if isinstance(mirror, dict) else {}
        return max(0, min(255, int(round(self._number(values, key, fallback)))))

    def _set_throttle_output_visual(self, key: str, value: int) -> None:
        """Update a test tile immediately; the bridge remains authoritative."""

        outputs = self._lab.setdefault("outputs", {})
        throttle_outputs = outputs.setdefault("winctrl_throttle", {})
        if isinstance(throttle_outputs, dict):
            throttle_outputs[key] = {
                "value": max(0, min(255, int(value))),
                "source": "virtual",
                "updated": time.time(),
            }

    def _queue_throttle_output(self, key: str, value: int) -> None:
        """Send one safe captured B930 channel through the loopback worker."""

        self._set_throttle_output_visual(key, value)
        self._request(
            "lab_output", device="winctrl_throttle", control=key, value=value,
            done=lambda _result: None,
        )

    def _activate_throttle_output(self, key: str) -> None:
        """Operate a visible throttle test output; motors always self-clear."""

        if key not in WINCTRL_THROTTLE_OUTPUT_KEYS:
            return
        current = self._throttle_output_value(key, WINCTRL_THROTTLE_OUTPUT_DEFAULTS.get(key, 0))
        if key.startswith("vibration_motor_"):
            # The capture proves a 0..255 intensity byte, not duration or
            # force settings.  A short fixed practice pulse makes the motor
            # test useful and guarantees it returns to its safe, off state.
            self._queue_throttle_output(key, 220 if current == 0 else 0)
            if current == 0:
                self.after(350, lambda output=key: self._queue_throttle_output(output, 0))
            return
        if key.endswith("backlight"):
            self._queue_throttle_output(key, 0 if current > 0 else 255)
            return
        self._queue_throttle_output(key, 0 if current > 0 else 1)

    def _pedal_axis_value(self, key: str) -> float:
        value = self._device_input_value("winctrl_pedals", key, 0.0)
        if key == "rudder":
            if abs(value) > 1.001:
                return max(-1.0, min(1.0, value / 32767.5 - 1.0))
            return max(-1.0, min(1.0, value))
        return self._axis_fraction(value)

    def _virtual_axis_input(self, key: str) -> tuple[float, str]:
        """Give the clickable 2D axes a useful, bounded practice movement."""

        device = self._selected_device
        if device == "winctrl_throttle":
            current = self._throttle_axis_fraction(key)
            value = 0.0 if current >= .95 else round(current + .10, 2)
        elif device == "winctrl_pedals" and key == "rudder":
            current = self._pedal_axis_value(key)
            value = -1.0 if current >= .95 else round(current + .20, 2)
        else:
            current = self._pedal_axis_value(key)
            value = 0.0 if current >= .95 else round(current + .10, 2)
        self._set_device_visual_input(device, key, value)
        return value, "change"

    def _apply_throttle_trim_visual(self, key: str) -> None:
        """Animate the captured B930 trim contacts without fabricating input readback.

        The HID input report does not expose the trim number.  In Test mode
        the bridge mirrors its own verified numeric display write; this local
        value makes virtual clicks feel immediate before that status arrives.
        """

        mode = self._throttle_trim_mode
        if mode not in self._throttle_trim_values:
            return
        if mode == "STAB":
            # The rocker's real wiring has no centre command for electric
            # pitch trim, so RESET stays a no-op here exactly as it is live.
            if key == "rudder_trim_left":
                self._throttle_trim_values[mode] = max(0.0, round(self._throttle_trim_values[mode] - 0.1, 1))
            elif key == "rudder_trim_right":
                self._throttle_trim_values[mode] = min(19.9, round(self._throttle_trim_values[mode] + 0.1, 1))
            return
        if key == "rudder_trim_reset":
            self._throttle_trim_values[mode] = 0.0
        elif key == "rudder_trim_left":
            self._throttle_trim_values[mode] = max(-10.0, round(self._throttle_trim_values[mode] - 0.1, 1))
        elif key == "rudder_trim_right":
            self._throttle_trim_values[mode] = min(10.0, round(self._throttle_trim_values[mode] + 0.1, 1))

    def _set_throttle_trim_selector(self, key: str) -> None:
        """Reflect the real MODE detent - CRANK/NORM/IGN-START = pitch/rudder/aileron."""

        roles: Dict[str, Optional[str]] = {
            "trim_mode_crank": "STAB",
            "trim_mode_norm": "RUDDER",
            "trim_mode_ign_start": "AILERON",
        }
        if key in roles:
            changed = key != self._throttle_trim_selector
            self._throttle_trim_selector = key
            self._throttle_trim_mode = roles[key]
            if changed:
                self._throttle_trim_label_until = time.monotonic() + 1.0
                self._throttle_trim_request_frame()

    def _throttle_trim_request_frame(self) -> None:
        """Force one redraw once the mode-name announcement window ends."""

        def _frame() -> None:
            if self._selected_device == "winctrl_throttle":
                self._draw_faceplate()

        try:
            self.after(1050, _frame)
        except Exception:
            pass

    def _throttle_trim_display_value(self, mode: Optional[str], fallback: float) -> float:
        """Use the bridge-confirmed numeric window for the selected trim role."""

        if mode not in self._throttle_trim_values:
            return 0.0
        state = self._device_states.get("winctrl_throttle", {})
        mirror = state.get("mirror", {}) if isinstance(state, dict) else {}
        values = dict(mirror.get("values") or {}) if isinstance(mirror, dict) else {}
        bridge_role = str(values.get("trim_role") or "").upper()
        # The bridge status always reports the one physical window's last
        # confirmed value under "rudder_trim_display", whichever channel
        # (signed rudder/aileron or unsigned STAB units) actually wrote it -
        # there is no separate mirror key for the STAB scale.
        if bridge_role == mode:
            return self._number(values, "rudder_trim_display", fallback)
        return fallback

    def _pu_virtual_input(self, key: str) -> tuple[int | float, str]:
        """Produce one real PU decoder value for a Studio test interaction."""

        if key == "battery_on":
            self._pu_battery_on = not self._pu_battery_on
            return int(self._pu_battery_on), "press" if self._pu_battery_on else "release"
        if key in PU_TOGGLE_KEYS:
            current = self._pu_input_value(key, 0.0)
            value = 0 if current >= .5 else 1
            return value, "press" if value else "release"
        values = PU_SELECTOR_VALUES.get(key)
        if values:
            current = int(round(self._pu_input_value(key, values[0])))
            try:
                index = values.index(current)
            except ValueError:
                index = -1
            return values[(index + 1) % len(values)], "change"
        return 1, "press"

    def _pu_output_value(self, key: str, fallback: str = "-----") -> str:
        """Show laboratory display tests when the real overhead has no mirror."""

        outputs = self._lab.get("outputs")
        pu_outputs = dict(outputs.get("pu_overhead") or {}) if isinstance(outputs, dict) else {}
        item = pu_outputs.get(key)
        if isinstance(item, dict) and item.get("value") not in {None, ""}:
            return str(item["value"])[:8]
        state = self._device_states.get("pu_overhead", {})
        mirror = state.get("mirror", {}) if isinstance(state, dict) else {}
        values = dict(mirror.get("values") or {}) if isinstance(mirror, dict) else {}
        if key in values and values[key] not in {None, ""}:
            value = values[key]
            try:
                return f"{round(float(value)):05d}"
            except (TypeError, ValueError):
                return str(value)[:8]
        return fallback

    def _pu_light_mask(self) -> int:
        """Return the real P7 lamp word, or an explicit lab light test word."""

        outputs = self._lab.get("outputs")
        pu_outputs = dict(outputs.get("pu_overhead") or {}) if isinstance(outputs, dict) else {}
        tested_bits = [bit for bit in range(32) if isinstance(pu_outputs.get(f"lamp_{bit}"), dict)]
        if tested_bits:
            mask = 0
            for bit in tested_bits:
                item = dict(pu_outputs.get(f"lamp_{bit}") or {})
                if self._number(item, "value", 0.0) >= .5:
                    mask |= 1 << bit
            return mask
        state = self._device_states.get("pu_overhead", {})
        mirror = state.get("mirror", {}) if isinstance(state, dict) else {}
        try:
            return int(dict(mirror).get("light_mask", 0)) & 0xFFFFFFFF
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _pu_axis_fraction(value: float) -> float:
        """Accept either SDL's -1..1 axis form or an already-normalized value."""

        if -1.001 <= value <= 1.001:
            value = (value + 1.0) / 2.0
        return max(0.0, min(1.0, value))

    def _draw_pu_static_toggle(
        self, canvas: tk.Canvas, x: float, y: float, label: str, *, key: Optional[str] = None,
        on: bool = False, compact: bool = False, scale: float = 1.0,
    ) -> None:
        """A photographed PU toggle, selectable only when its source is captured."""

        radius = (10 if compact else 13) * scale
        shaft = (18 if compact else 24) * scale
        color = self._control_color(key) if key else "#897e69"
        if key:
            self._highlight_ring(canvas, x - radius, y - radius, x + radius, y + radius, key, radius=radius)
        label_item = canvas.create_text(x, y - shaft - 13 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(5, int((7 if compact else 9) * scale))), width=max(40, int(82 * scale)))
        base = canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#06080c", outline=color, width=2 if key == self._selected_visual else 1)
        dy = -shaft if on else shaft
        lever = canvas.create_line(x, y, x + 4 * scale, y + dy, fill="#d3d3d8" if on else "#8b8d95", width=max(2, radius), capstyle="round")
        pivot = canvas.create_oval(x - 3 * scale, y - 3 * scale, x + 3 * scale, y + 3 * scale, fill="#3b3b44", outline="#0a0b0e")
        state = canvas.create_text(x, y + shaft + 12 * scale, text="ON" if on else "OFF", fill="#b9f7df" if on else "#cdbf9d", font=("Segoe UI Semibold", max(5, int((7 if compact else 8) * scale))))
        if key:
            for item in (label_item, base, lever, pivot, state):
                self._tag(canvas, item, key)

    def _draw_pu_action_button(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, *, scale: float,
    ) -> None:
        """A clear spring-endpoint control for the generator/electrical bank."""

        half_w = max(19.0, 25.0 * scale)
        half_h = max(11.0, 14.0 * scale)
        color = self._control_color(key)
        self._highlight_ring(canvas, x - half_w, y - half_h, x + half_w, y + half_h, key, radius=5)
        body = canvas.create_round_rect(
            x - half_w, y - half_h, x + half_w, y + half_h, radius=5,
            fill=self._control_fill(key, "#1a2130"), outline=color,
            width=3 if key == self._selected_visual else 2,
        )
        text = canvas.create_text(
            x, y, text=label, fill=INK,
            font=("Segoe UI Semibold", max(6, int(7 * scale))), justify="center",
        )
        self._tag(canvas, body, key)
        self._tag(canvas, text, key)

    def _pu_input_record(self, key: str) -> Dict[str, Any]:
        """Return one recorded PU input without treating absence as OFF."""

        inputs = self._lab.get("inputs")
        pu_inputs = dict(inputs.get("pu_overhead") or {}) if isinstance(inputs, dict) else {}
        item = pu_inputs.get(key)
        return dict(item) if isinstance(item, dict) else {}

    def _draw_pu_spring_toggle(
        self, canvas: tk.Canvas, x: float, y: float, label: str, off_key: str, on_key: str, *, scale: float,
    ) -> None:
        """A centre-return OFF/ON lever with separately mappable directions.

        GPU, GEN 1/2 and APU GEN 1/2 have captured individual OFF and ON
        contacts, but the owner confirmed both directions are spring-loaded.
        The visual lever therefore returns to its centre after a press; it is
        never shown as a maintained switch position.
        """

        half_w = max(15.0, 19.0 * scale)
        half_h = max(25.0, 33.0 * scale)
        now = time.monotonic()
        # Selection is intentionally separate from motion: selecting the
        # endpoint for mapping must not leave a spring-loaded lever visibly
        # held.  Real HardwareLab press state is authoritative; the old flash
        # remains a fallback/acknowledgement for a just-seen event.
        off_live = self._live_control_active(off_key)
        on_live = self._live_control_active(on_key)
        pressed_key = (
            off_key if off_live or self._flash_until.get(off_key, 0.0) > now else
            on_key if on_live or self._flash_until.get(on_key, 0.0) > now else ""
        )
        selected_key = self._selected_visual if self._selected_visual in {off_key, on_key} else ""
        focus_key = pressed_key or selected_key
        active_key = focus_key or on_key
        self._highlight_ring(canvas, x - half_w, y - half_h, x + half_w, y + half_h, focus_key, radius=max(4, 5 * scale))
        body = canvas.create_round_rect(
            x - half_w, y - half_h, x + half_w, y + half_h,
            radius=max(4, 5 * scale), fill="#11151d", outline=self._control_color(focus_key) if focus_key else "#647186",
            width=3 if focus_key else 2,
        )
        self._tag(canvas, body, active_key)
        title = canvas.create_text(x, y - half_h - 12 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(6, int(7 * scale))), width=max(42, int(70 * scale)))
        self._tag(canvas, title, active_key)
        on_y, off_y = y - half_h * .53, y + half_h * .53
        for position_y, text, key in ((on_y, "OFF", off_key), (off_y, "ON", on_key)):
            item = canvas.create_text(x + half_w + 7 * scale, position_y, text=text, anchor="w", fill=INK if key == pressed_key else "#ffd166" if key == selected_key else MUTED, font=("Segoe UI Semibold", max(5, int(6 * scale))))
            hit = canvas.create_round_rect(x - half_w + 2 * scale, position_y - 8 * scale, x + half_w - 2 * scale, position_y + 8 * scale, radius=3, fill="", outline="")
            self._tag(canvas, item, key)
            self._tag(canvas, hit, key)
        pivot_y = y
        lever_end_y = (
            y - half_h + 10 * scale if pressed_key == off_key else
            y + half_h - 10 * scale if pressed_key == on_key else y - 2 * scale
        )
        lever = canvas.create_line(x, pivot_y, x + 3 * scale, lever_end_y, fill="#d3d3d8" if pressed_key else "#b8bac1", width=max(3, int(7 * scale)), capstyle="round")
        pivot = canvas.create_oval(x - 4 * scale, pivot_y - 4 * scale, x + 4 * scale, pivot_y + 4 * scale, fill="#303944", outline="#0a0b0e")
        self._tag(canvas, lever, active_key)
        self._tag(canvas, pivot, active_key)

    def _draw_pu_detent(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, choices: tuple[str, ...], active_index: int, *, scale: float,
    ) -> None:
        """Compact linear selector used for packs, wiper and cabin systems."""

        if not choices:
            return
        half = max(24.0, 34.0 * scale)
        active = max(0, min(len(choices) - 1, int(active_index)))
        color = self._control_color(key)
        self._highlight_ring(canvas, x - half, y - 6 * scale, x + half, y + 6 * scale, key, radius=max(3, 4 * scale))
        track = canvas.create_line(x - half, y, x + half, y, fill="#5a6578", width=max(2, int(3 * scale)), capstyle="round")
        self._tag(canvas, track, key)
        span = half * 2
        position = x - half + span * active / max(1, len(choices) - 1)
        for index, choice in enumerate(choices):
            tick_x = x - half + span * index / max(1, len(choices) - 1)
            tick = canvas.create_line(tick_x, y - 4 * scale, tick_x, y + 4 * scale, fill=color, width=1)
            self._tag(canvas, tick, key)
            item = canvas.create_text(tick_x, y + 13 * scale, text=choice, fill=INK if index == active else MUTED, font=("Segoe UI Semibold", max(6, int(7 * scale))))
            self._tag(canvas, item, key)
        dot = canvas.create_oval(position - 4 * scale, y - 4 * scale, position + 4 * scale, y + 4 * scale, fill="#00ffd1" if self._flash_until.get(key, 0.0) > time.monotonic() else ACCENT, outline=color)
        self._tag(canvas, dot, key)
        title = canvas.create_text(x, y - 15 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        self._tag(canvas, title, key)

    def _draw_pu_toggle_selector(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, *,
        choices: tuple[str, ...], active_index: int, scale: float,
    ) -> None:
        """Draw a moving-lever switch, never a round knob.

        The PU NO SMOKING and FASTEN BELTS controls are switches.  Their
        choice labels sit beside a vertical travel path and the teal/gold dot
        moves to the exact selected contact, matching the physical intent.
        """

        if not choices:
            return
        half = max(20.0, 31.0 * scale)
        active = max(0, min(len(choices) - 1, int(active_index)))
        color = self._control_color(key)
        self._highlight_ring(canvas, x - 20 * scale, y - half - 6 * scale, x + 35 * scale, y + half + 8 * scale, key, radius=5)
        title = canvas.create_text(x, y - half - 17 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        self._tag(canvas, title, key)
        track = canvas.create_line(x, y - half, x, y + half, fill="#596478", width=max(2, int(3 * scale)), capstyle="round")
        self._tag(canvas, track, key)
        for index, choice in enumerate(choices):
            marker_y = y - half + (half * 2) * index / max(1, len(choices) - 1)
            tick = canvas.create_line(x - 6 * scale, marker_y, x + 6 * scale, marker_y, fill=color, width=1)
            text = canvas.create_text(x + 13 * scale, marker_y, text=choice, anchor="w", fill=INK if index == active else MUTED, font=("Segoe UI Semibold", max(6, int(7 * scale))))
            self._tag(canvas, tick, key)
            self._tag(canvas, text, key)
        marker_y = y - half + (half * 2) * active / max(1, len(choices) - 1)
        base = canvas.create_oval(x - 7 * scale, marker_y - 7 * scale, x + 7 * scale, marker_y + 7 * scale, fill="#11151d", outline=color, width=2)
        dot = canvas.create_oval(x - 3 * scale, marker_y - 3 * scale, x + 3 * scale, marker_y + 3 * scale, fill="#00ffd1" if self._flash_until.get(key, 0.0) > time.monotonic() else ACCENT, outline=color)
        self._tag(canvas, base, key)
        self._tag(canvas, dot, key)

    def _draw_pu_axis_knob(self, canvas: tk.Canvas, x: float, y: float, key: str, value: float, *, scale: float) -> None:
        """Draw the panel-brightness axis as the physical-style rotary knob."""

        import math

        radius = max(20.0, 29.0 * scale)
        fraction = self._pu_axis_fraction(value)
        color = self._control_color(key)
        self._highlight_ring(canvas, x - radius, y - radius, x + radius, y + radius, key, radius=radius)
        body = canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=self._control_fill(key, "#151822"), outline=color, width=3 if key == self._selected_visual else 2)
        self._tag(canvas, body, key)
        for index in range(7):
            angle = math.radians(140 - index * 280 / 6)
            inner, outer = radius - 5 * scale, radius + 2 * scale
            tick = canvas.create_line(x + inner * math.cos(angle), y - inner * math.sin(angle), x + outer * math.cos(angle), y - outer * math.sin(angle), fill="#8593a9", width=1)
            self._tag(canvas, tick, key)
        angle = math.radians(140 - fraction * 280)
        pointer = canvas.create_line(x, y, x + (radius - 7 * scale) * math.cos(angle), y - (radius - 7 * scale) * math.sin(angle), fill="#e8dbc0", width=max(2, int(3 * scale)))
        label = canvas.create_text(x, y + radius + 13 * scale, text="PANEL BRIGHT", fill="#e7d9b5", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        minimum = canvas.create_text(x - radius - 5 * scale, y + radius + 1 * scale, text="DIM", anchor="e", fill=MUTED, font=("Segoe UI", max(5, int(6 * scale))))
        maximum = canvas.create_text(x + radius + 5 * scale, y + radius + 1 * scale, text="BRT", anchor="w", fill=MUTED, font=("Segoe UI", max(5, int(6 * scale))))
        for item in (pointer, label, minimum, maximum):
            self._tag(canvas, item, key)

    def _draw_pu_annunciator(
        self, canvas: tk.Canvas, x: float, y: float, label: str, tone: str, active: bool, *, width: float, height: float,
    ) -> None:
        """Draw the PU's recessed rectangular P7 annunciator lenses."""

        palette = {
            "red": ("#ff493d", "#5a181b", "#1a0a0d"),
            "green": ("#36ff7d", "#15572e", "#07150d"),
            "blue": ("#9cc8ff", "#1a3f76", "#08101c"),
            "white": ("#e8f4ff", "#465d75", "#10151b"),
        }
        lit_text, unlit_text, unlit_fill = palette.get(tone, palette["white"])
        x1, y1, x2, y2 = x - width / 2, y - height / 2, x + width / 2, y + height / 2
        canvas.create_round_rect(x1 - 1, y1 - 1, x2 + 1, y2 + 1, radius=max(2, height * .18), fill="#07090d", outline="#414852", width=1)
        canvas.create_round_rect(x1, y1, x2, y2, radius=max(2, height * .16), fill=("#20242b" if active else unlit_fill), outline=(lit_text if active else "#171c25"), width=1)
        canvas.create_text(
            x, y, text=label, fill=(lit_text if active else unlit_text),
            font=("Segoe UI Semibold", max(4, int(height * .34))), justify="center", width=max(16, width - 3),
        )

    def _draw_pu_rotary(
        self, canvas: tk.Canvas, x: float, y: float, label: str, value: str, *, dec: str, inc: str, scale: float,
    ) -> None:
        """A real two-direction PU encoder: each arc has its own remappable source."""

        radius = max(15.0, 23.0 * scale)
        core = max(10.0, radius * .62)
        for key, start in ((dec, 205), (inc, 25)):
            item = canvas.create_arc(x - radius, y - radius, x + radius, y + radius, start=start, extent=130, style="arc", outline=self._control_color(key), width=max(3, int(5 * scale)))
            self._tag(canvas, item, key)
        canvas.create_oval(x - core, y - core, x + core, y + core, fill="#151822", outline="#9d998c", width=1)
        canvas.create_line(x, y, x, y - core + 3, fill="#d8cba9", width=max(1, int(2 * scale)))
        canvas.create_text(x, y + radius + 8 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(5, int(6 * scale))))
        canvas.create_text(x, y + radius + 18 * scale, text=value, fill="#b9f7df", font=("Consolas", max(6, int(7 * scale)), "bold"))

    def _draw_pu_selector(
        self, canvas: tk.Canvas, x: float, y: float, label: str, key: str, *,
        choices: tuple[str, ...], active_index: int, scale: float,
    ) -> None:
        """A captured multi-position selector with an explicit current detent."""

        radius = max(17.0, 23.0 * scale)
        color = self._control_color(key)
        self._highlight_ring(canvas, x - radius, y - radius, x + radius, y + radius, key, radius=radius)
        item = canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=self._control_fill(key, "#151822"), outline=color, width=3 if key == self._selected_visual else 2)
        self._tag(canvas, item, key)
        index = max(0, min(len(choices) - 1, int(active_index))) if choices else 0
        if len(choices) == 4:
            angles = (-132, -42, 42, 132)
        elif len(choices) == 3:
            angles = (-90, 0, 90)
        elif len(choices) == 2:
            angles = (-100, 80)
        else:
            angles = (-90,)
        # Each real detent is printed beside the knob.  Showing just the
        # current word made it impossible to tell what a rotary could select.
        import math
        for choice, choice_angle in zip(choices, angles):
            label_radius = radius + max(13.0, 17.0 * scale)
            label_x = x + label_radius * math.cos(math.radians(choice_angle))
            label_y = y + label_radius * math.sin(math.radians(choice_angle))
            anchor = "w" if math.cos(math.radians(choice_angle)) > .30 else "e" if math.cos(math.radians(choice_angle)) < -.30 else "center"
            detent = canvas.create_text(label_x, label_y, text=choice, anchor=anchor, fill=INK if choices.index(choice) == index else MUTED, font=("Segoe UI Semibold", max(5, int(6 * scale))))
            self._tag(canvas, detent, key)
        angle = angles[index]
        end_x = x + (radius - 4) * math.cos(math.radians(angle))
        end_y = y + (radius - 4) * math.sin(math.radians(angle))
        pointer = canvas.create_line(x, y, end_x, end_y, fill="#e8dbc0", width=max(2, int(3 * scale)))
        self._tag(canvas, pointer, key)
        text = canvas.create_text(x, y + radius + 11 * scale, text=label, fill="#e7d9b5", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        self._tag(canvas, text, key)
        current = choices[index] if choices else "—"
        subtext = canvas.create_text(x, y + radius + 22 * scale, text=current, fill="#b9f7df", font=("Segoe UI Semibold", max(6, int(7 * scale))))
        self._tag(canvas, subtext, key)

    def _draw_pu_battery(self, canvas: tk.Canvas, x: float, y: float, active: bool, *, scale: float) -> None:
        """The user-proven SDL 43 DC/BAT switch, at its photographed location."""

        key = "battery_on"
        half_w, half_h = 22 * scale, 29 * scale
        color = "#00ffd1" if active else self._control_color(key)
        self._highlight_ring(canvas, x - half_w, y - half_h, x + half_w, y + half_h, key, radius=max(5, 7 * scale))
        body = canvas.create_round_rect(x - half_w, y - half_h, x + half_w, y + half_h, radius=max(5, 6 * scale), fill="#1b202a" if not active else "#174447", outline=color, width=3 if key == self._selected_visual else 2)
        self._tag(canvas, body, key)
        pivot = canvas.create_oval(x - 5 * scale, y - 5 * scale, x + 5 * scale, y + 5 * scale, fill="#080a0f", outline="#a9a29a")
        self._tag(canvas, pivot, key)
        end_y = y - 17 * scale if active else y + 17 * scale
        lever = canvas.create_line(x, y, x + 4 * scale, end_y, fill="#c7c8ce", width=max(5, int(8 * scale)), capstyle="round")
        self._tag(canvas, lever, key)
        state = canvas.create_text(x + 28 * scale, y - 13 * scale, text="ON" if active else "OFF", anchor="w", fill="#b9f7df" if active else "#d5c7a7", font=("Segoe UI Semibold", max(6, int(7 * scale))))
        self._tag(canvas, state, key)
        label = canvas.create_text(x, y + 39 * scale, text="DC / BAT", fill="#f2e6c5", font=("Segoe UI Semibold", max(6, int(7 * scale))))
        self._tag(canvas, label, key)

    def _draw_pu_overhead_photographed_reference(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Original photograph-proportional study retained for design reference."""

        image_ratio = 3375 / 1921
        panel_width = min(width - 38, (height - 86) * image_ratio)
        panel_height = panel_width / image_ratio
        left = (width - panel_width) / 2
        top = max(49.0, (height - panel_height) / 2 + 20)
        scale = max(.55, min(1.45, panel_width / 1540))

        def pt(x: float, y: float) -> tuple[float, float]:
            return left + panel_width * x / 100, top + panel_height * y / 100

        def block(x: float, y: float, w: float, h: float, label: str) -> tuple[float, float, float, float]:
            x1, y1 = pt(x, y)
            x2, y2 = pt(x + w, y + h)
            canvas.create_round_rect(x1, y1, x2, y2, radius=max(5, 8 * scale), fill="#292b31", outline="#727985", width=max(1, int(2 * scale)))
            canvas.create_text((x1 + x2) / 2, y1 + 10 * scale, text=label, fill="#eee2c7", font=("Segoe UI Semibold", max(5, int(7 * scale))))
            return x1, y1, x2, y2

        canvas.create_text(left, top - 27, text="PU OVERHEAD — 2D HARDWARE STUDIO", anchor="w", fill=INK, font=("Segoe UI Semibold", 13))
        canvas.create_text(left + panel_width, top - 27, state="hidden", text="Blue = mapped/default  •  gold = selected  •  teal = live press", anchor="e", fill=MUTED, font=("Segoe UI", 9))
        canvas.create_round_rect(left, top, left + panel_width, top + panel_height, radius=max(9, 14 * scale), fill="#111317", outline="#5b6473", width=2)

        # The layout follows the owner's photo: framed black/metal panels
        # first, then the captured switch/rotary elements on top.
        block(1.2, 7.0, 22.5, 18.0, "IRS / NAV")
        block(25.0, 6.5, 22.5, 19.0, "ELECTRICAL")
        block(48.8, 6.5, 24.2, 28.7, "ICE PROTECTION")
        block(75.0, 6.5, 23.8, 29.5, "BLEED AIR")
        block(1.2, 29.0, 22.5, 42.0, "FUEL PUMPS")
        block(24.8, 29.0, 23.4, 24.0, "GENERATOR / APU")
        block(49.5, 38.2, 23.0, 26.5, "CABIN / PANEL")
        block(74.3, 38.0, 24.7, 30.0, "PRESSURIZATION")
        block(1.2, 74.0, 97.7, 22.5, "EXTERIOR LIGHTS / APU / ENGINE START")

        # Each P7 bit is now a photographed recessed annunciator: its lens
        # keeps the correct red/green/blue/white identity while the current
        # bridge P7 mask (or an explicit laboratory light test) controls its
        # brightness.  This is deliberately indication feedback, never a
        # guessed switch-position lamp.
        light_mask = self._pu_light_mask()
        for bit, label, x_percent, y_percent, w_percent, h_percent, tone in PU_ANNUNCIATOR_LAYOUT:
            x, y = pt(x_percent, y_percent)
            self._draw_pu_annunciator(
                canvas, x, y, label, tone, bool(light_mask & (1 << bit)),
                width=panel_width * w_percent / 100,
                height=panel_height * h_percent / 100,
            )

        # IRS and electrical upper-left groups.  Every visible handle below
        # has a verified PU source, so a real movement and a Studio test move
        # the same simulated handle and open the same mapping inspector.
        irs_choices = ("OFF", "ALIGN", "NAV", "ATT")
        self._draw_pu_selector(
            canvas, *pt(7.0, 16.0), "L IRS", "irs_left", choices=irs_choices,
            active_index=self._pu_choice_index("irs_left", 2, irs_choices), scale=scale,
        )
        self._draw_pu_selector(
            canvas, *pt(17.3, 16.0), "R IRS", "irs_right", choices=irs_choices,
            active_index=self._pu_choice_index("irs_right", 2, irs_choices), scale=scale,
        )
        self._draw_pu_static_toggle(canvas, *pt(30.0, 16.0), "YAW DAMP", key="yaw_damper", on=self._pu_input_value("yaw_damper", 1) >= .5, compact=True)
        self._draw_pu_static_toggle(canvas, *pt(38.4, 16.0), "GRD PWR ON", key="ground_power_on", on=False, compact=True)

        # Window heat / packs / anti-ice silhouettes retain the panel's real
        # visual hierarchy but stay deliberately non-remappable until captured.
        for x, y, label, key in (
            (53.0, 15.0, "L SIDE", "window_heat_l_side"), (58.6, 15.0, "L FWD", "window_heat_l_fwd"),
            (65.0, 15.0, "R FWD", "window_heat_r_fwd"), (70.0, 15.0, "R SIDE", "window_heat_r_side"),
            (52.5, 26.0, "PROBE L", "probe_heat_capt"), (58.0, 26.0, "PROBE R", "probe_heat_fo"),
            (64.5, 26.0, "WING A/I", "wing_anti_ice"), (69.0, 26.0, "ENG 1 A/I", "eng1_anti_ice"),
            (72.0, 26.0, "ENG 2 A/I", "eng2_anti_ice"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True)
        for x, y, label, key, choices in (
            (79.5, 15.0, "L PACK", "l_pack", ("OFF", "AUTO", "HIGH")),
            (87.4, 18.0, "ISOLATION", "isolation_valve", ("CLOSE", "AUTO", "OPEN")),
            (95.0, 15.0, "R PACK", "r_pack", ("OFF", "AUTO", "HIGH")),
        ):
            self._draw_pu_detent(
                canvas, *pt(x, y), label, key, choices,
                self._pu_choice_index(key, 1, choices), scale=scale,
            )
        for x, y, label, key in (
            (79.5, 27.5, "BLEED 1", "bleed_air_1"), (87.5, 27.5, "APU BLEED", "bleed_air_apu"), (95.5, 27.5, "BLEED 2", "bleed_air_2"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 0) >= .5, compact=True)

        # Fuel, generator and hydraulic visual groups (shown, but no semantic
        # claim is made for the yet-uncaptured individual source bits).
        for x, y, label, key in (
            (7.4, 43.0, "CTR L", "fuel_ctr_l"), (13.0, 43.0, "CTR R", "fuel_ctr_r"), (6.0, 62.0, "1 AFT", "fuel_l_aft"),
            (11.5, 62.0, "1 FWD", "fuel_l_fwd"), (17.0, 62.0, "2 FWD", "fuel_r_fwd"), (21.0, 62.0, "2 AFT", "fuel_r_aft"),
            (29.0, 43.0, "GEN 1 ON", "gen1_on"), (35.2, 43.0, "APU GEN 1", "apu_gen1_on"), (42.5, 43.0, "GEN 2 ON", "gen2_on"),
            (53.5, 48.0, "ENG 1", "hyd_eng1"), (59.0, 48.0, "ELEC 2", "hyd_elec2"), (64.0, 48.0, "ELEC 1", "hyd_elec1"), (69.4, 48.0, "ENG 2", "hyd_eng2"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1 if key.startswith(("fuel", "hyd")) else 0) >= .5, compact=True)

        # These are real output instruments, not virtual switches.  Their
        # values come from the same bridge cache written to COM5, or a lab
        # output test, so the visual faceplate cannot disagree with hardware.
        egt_x, egt_y = pt(37.0, 62.0)
        egt_value = self._number({"value": self._pu_output_value("apu_egt", "0")}, "value", 0.0)
        egt_radius = max(17, 25 * scale)
        canvas.create_oval(egt_x - egt_radius, egt_y - egt_radius, egt_x + egt_radius, egt_y + egt_radius, fill="#080a0e", outline="#9c927d", width=2)
        canvas.create_text(egt_x, egt_y - 5 * scale, text="APU EGT", fill="#eadfc4", font=("Segoe UI Semibold", max(5, int(6 * scale))))
        canvas.create_text(egt_x, egt_y + 8 * scale, text=f"{round(egt_value):03d}", fill="#ffbf69", font=("Consolas", max(6, int(8 * scale)), "bold"))
        self._draw_pu_detent(
            canvas, *pt(43.5, 62.0), "WIPER", "wiper_selector", ("PARK", "INT", "LOW", "HIGH"),
            self._pu_choice_index("wiper_selector", 0, ("PARK", "INT", "LOW", "HIGH")), scale=scale,
        )

        # Cabin panel: the exact owner-provided BAT/ON location is a real
        # selectable control (SDL 43) with its physical state reflected.
        battery_value = self._pu_input_value("battery_on", 1.0 if self._pu_battery_on else 0.0)
        battery_on = battery_value >= .5
        self._pu_battery_on = battery_on
        self._draw_pu_battery(canvas, *pt(58.3, 59.1), battery_on, scale=scale)
        self._draw_pu_selector(
            canvas, *pt(52.8, 59.0), "NO SMOKE", "no_smoking", choices=("OFF", "ON"),
            active_index=0 if self._pu_input_value("no_smoking", 2) < 1 else 1, scale=scale,
        )
        self._draw_pu_selector(
            canvas, *pt(65.3, 59.0), "SEAT BELTS", "fasten_belts", choices=("OFF", "AUTO", "ON"),
            active_index=self._pu_choice_index("fasten_belts", 1, ("OFF", "AUTO", "ON")), scale=scale,
        )

        brightness_x, brightness_y = pt(68.3, 58.0)
        brightness = self._pu_axis_fraction(self._pu_input_value("panel_brightness", 0.0))
        key = "panel_brightness"
        color = self._control_color(key)
        self._highlight_ring(canvas, brightness_x - 26 * scale, brightness_y - 12 * scale, brightness_x + 26 * scale, brightness_y + 12 * scale, key, radius=max(4, 5 * scale))
        slider = canvas.create_line(brightness_x - 20 * scale, brightness_y, brightness_x + 20 * scale, brightness_y, fill="#596478", width=max(2, int(3 * scale)), capstyle="round")
        self._tag(canvas, slider, key)
        knob_x = brightness_x - 20 * scale + 40 * scale * brightness
        knob = canvas.create_oval(knob_x - 5 * scale, brightness_y - 5 * scale, knob_x + 5 * scale, brightness_y + 5 * scale, fill=ACCENT, outline=color)
        self._tag(canvas, knob, key)
        label = canvas.create_text(brightness_x, brightness_y + 14 * scale, text="PANEL BRIGHT", fill="#e7d9b5", font=("Segoe UI Semibold", max(5, int(6 * scale))))
        self._tag(canvas, label, key)

        # The flight/landing altitude wheels are source-verified directional
        # pulses.  Separate arcs keep clockwise and counter-clockwise mapping
        # unmistakable, even though their physical numerical displays are
        # outputs rather than synthetic simulator values.
        for x_percent, y_percent, title, display_key, dec, inc in (
            (83.7, 51.0, "FLT ALT", "flt_altitude", "flt_alt_ccw", "flt_alt_cw"),
            (83.7, 64.0, "LAND ALT", "land_altitude", "land_alt_ccw", "land_alt_cw"),
        ):
            x, y = pt(x_percent, y_percent)
            self._draw_window(canvas, x, y - 8 * scale, title, self._pu_output_value(display_key), width=max(68, int(96 * scale)))
            self._draw_pu_rotary(canvas, x, y + 27 * scale, title, "CCW / CW", dec=dec, inc=inc, scale=scale)

        # Lower strip gives the user the familiar operational scan path.
        for x, label, key in (
            (5.3, "LANDING L", "landing_light_left"), (12.4, "LANDING R", "landing_light_right"),
            (20.4, "TAXI", "taxi_light"), (74.6, "LOGO", "logo_light"),
            (88.1, "ANTI COLL", "beacon_light"), (95.2, "WING", "wing_light"),
        ):
            on = self._pu_input_value(key, 0) >= .5
            self._draw_pu_static_toggle(canvas, *pt(x, 86.5), label, key=key, on=on, compact=True)
        self._draw_pu_detent(
            canvas, *pt(29.0, 86.5), "APU", "apu_start", ("OFF", "ON", "START"),
            self._pu_choice_index("apu_start", 0, ("OFF", "ON", "START")), scale=scale,
        )
        position_values = (-1, 0, 1)
        position_current = int(round(self._pu_input_value("position_lights", 0)))
        self._draw_pu_detent(
            canvas, *pt(81.7, 86.5), "POSITION", "position_lights", ("STEADY", "OFF", "STROBE"),
            max(0, min(2, position_values.index(position_current) if position_current in position_values else 1)), scale=scale,
        )
        eng_choices = ("GRD", "OFF", "CONT", "FLT")
        self._draw_pu_selector(
            canvas, *pt(47.2, 86.2), "ENG START 1", "engine_start_1", choices=eng_choices,
            active_index=self._pu_choice_index("engine_start_1", 1, eng_choices), scale=scale,
        )
        ignition_values = (-1, 0, 1)
        ignition_current = int(round(self._pu_input_value("ignition_source", 0)))
        self._draw_pu_detent(
            canvas, *pt(55.8, 86.3), "IGNITION", "ignition_source", ("IGN L", "BOTH", "IGN R"),
            ignition_values.index(ignition_current) if ignition_current in ignition_values else 1, scale=scale,
        )
        self._draw_pu_selector(
            canvas, *pt(64.5, 86.2), "ENG START 2", "engine_start_2", choices=eng_choices,
            active_index=self._pu_choice_index("engine_start_2", 1, eng_choices), scale=scale,
        )

        footer_y = top + panel_height + 17
        canvas.create_text(
            width / 2, footer_y,
            state="hidden", text="BAT (SDL 43), altitude wheel directions, panel-brightness axis and both engine-start selectors are live/remappable.  The P7 annunciators mirror the confirmed 32-bit lamp mask and preserve their actual lens colours.",
            fill=MUTED, font=("Segoe UI", 8), width=max(420, int(panel_width - 20)),
        )

    def _draw_pu_overhead_compact_legacy(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw the PU as a readable operating layout, not a scaled photograph.

        The real unit is intentionally compact, but copying its pixel geometry
        made the Studio version hard to operate.  This layout preserves the
        overhead's system groups and every verified source while giving each
        switch, selector and output enough breathing room to be configured.
        """

        design_width, design_height = 1120.0, 630.0
        scale = min((width - 24) / design_width, (height - 22) / design_height)
        scale = max(.62, min(1.12, scale))
        panel_width, panel_height = design_width * scale, design_height * scale
        left = (width - panel_width) / 2
        top = max(8.0, (height - panel_height) / 2)

        def pt(x: float, y: float) -> tuple[float, float]:
            return left + x * scale, top + y * scale

        def card(x: float, y: float, w: float, h: float, title: str) -> None:
            x1, y1 = pt(x, y)
            x2, y2 = pt(x + w, y + h)
            canvas.create_round_rect(
                x1, y1, x2, y2, radius=max(7, 10 * scale),
                fill="#1b202a", outline="#647186", width=2,
            )
            canvas.create_text(
                (x1 + x2) / 2, y1 + 13 * scale, text=title,
                fill="#eadfc4", font=("Segoe UI Semibold", max(8, int(10 * scale))),
            )

        x1, y1 = pt(0, 0)
        x2, y2 = pt(design_width, design_height)
        canvas.create_round_rect(x1, y1, x2, y2, radius=max(10, 14 * scale), fill="#10151e", outline="#758197", width=2)
        canvas.create_text(*pt(16, 18), text="PU OVERHEAD — WORKING HARDWARE PANEL", anchor="w", fill=INK, font=("Segoe UI Semibold", max(13, int(16 * scale))))
        try:
            wake_test = bool(object.__getattribute__(self, "pu_wake_test").get())
        except AttributeError:  # headless faceplate regression harness
            wake_test = False
        wake_state = "OUTPUT TEST ACTIVE" if wake_test else "OUTPUT TEST STANDBY"
        canvas.create_text(*pt(1102, 18), text=wake_state, anchor="e", fill="#5ff5c2" if wake_test else MUTED, font=("Segoe UI Semibold", max(8, int(10 * scale))))
        canvas.create_text(*pt(16, 35), state="hidden", text="Click a control to map it. Physical movement is teal; selection is gold.", anchor="w", fill=MUTED, font=("Segoe UI", max(7, int(9 * scale))))

        # P7 is one real 32-bit output field.  Keeping its lamps in an aligned
        # strip makes the output test readable and prevents them from being
        # mistaken for switch-position indicators.
        strip_x1, strip_y1 = pt(14, 46)
        strip_x2, strip_y2 = pt(1106, 86)
        canvas.create_round_rect(strip_x1, strip_y1, strip_x2, strip_y2, radius=max(5, 7 * scale), fill="#0b0f16", outline="#394354", width=1)
        canvas.create_text(*pt(24, 53), text="P7 ANNUNCIATOR OUTPUTS", anchor="w", fill="#aebbd2", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        light_mask = self._pu_light_mask()
        for bit, label, _x, _y, _w, _h, tone in PU_ANNUNCIATOR_LAYOUT:
            lamp_x = 40 + bit * 32 + (bit // 8) * 9
            self._draw_pu_annunciator(
                canvas, *pt(lamp_x, 70), label, tone, bool(light_mask & (1 << bit)),
                width=29 * scale, height=22 * scale,
            )

        card(10, 100, 220, 155, "IRS / NAV")
        card(240, 100, 260, 155, "ELECTRICAL")
        card(510, 100, 320, 155, "ICE PROTECTION")
        card(840, 100, 270, 155, "BLEED AIR")
        card(10, 265, 220, 165, "FUEL PUMPS")
        card(240, 265, 260, 165, "GENERATOR / APU")
        card(510, 265, 320, 165, "HYDRAULICS / CABIN")
        card(840, 265, 270, 165, "PRESSURIZATION")
        card(10, 440, 1100, 175, "EXTERIOR LIGHTS / APU / ENGINE START")

        irs_choices = ("OFF", "ALIGN", "NAV", "ATT")
        self._draw_pu_selector(canvas, *pt(76, 170), "LEFT IRS", "irs_left", choices=irs_choices, active_index=self._pu_choice_index("irs_left", 2, irs_choices), scale=scale)
        self._draw_pu_selector(canvas, *pt(170, 170), "RIGHT IRS", "irs_right", choices=irs_choices, active_index=self._pu_choice_index("irs_right", 2, irs_choices), scale=scale)

        self._draw_pu_static_toggle(canvas, *pt(274, 171), "YAW\nDAMP", key="yaw_damper", on=self._pu_input_value("yaw_damper", 1) >= .5, compact=True)
        for x, label, key in (
            (338, "GPU\nOFF", "ground_power_off"), (394, "GPU\nON", "ground_power_on"),
            (450, "GEN 1\nOFF", "gen1_off"), (338, "GEN 1\nON", "gen1_on"),
            (394, "GEN 2\nOFF", "gen2_off"), (450, "GEN 2\nON", "gen2_on"),
        ):
            y = 145 if x in {338, 394, 450} and key in {"ground_power_off", "ground_power_on", "gen1_off"} else 195
            self._draw_pu_action_button(canvas, *pt(x, y), label, key, scale=scale)

        ice_controls = (
            (544, 157, "L SIDE", "window_heat_l_side"), (604, 157, "L FWD", "window_heat_l_fwd"),
            (664, 157, "R FWD", "window_heat_r_fwd"), (724, 157, "R SIDE", "window_heat_r_side"),
            (784, 157, "PROBE\nCAPT", "probe_heat_capt"), (570, 221, "PROBE\nFO", "probe_heat_fo"),
            (640, 221, "WING\nA/ICE", "wing_anti_ice"), (710, 221, "ENG 1\nA/ICE", "eng1_anti_ice"),
            (780, 221, "ENG 2\nA/ICE", "eng2_anti_ice"),
        )
        for x, y, label, key in ice_controls:
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True)

        for x, y, label, key, choices in (
            (884, 160, "L PACK", "l_pack", ("OFF", "AUTO", "HIGH")),
            (974, 160, "ISOLATION", "isolation_valve", ("CLOSE", "AUTO", "OPEN")),
            (1062, 160, "R PACK", "r_pack", ("OFF", "AUTO", "HIGH")),
        ):
            self._draw_pu_detent(canvas, *pt(x, y), label, key, choices, self._pu_choice_index(key, 1, choices), scale=scale)
        for x, label, key in ((885, "BLEED 1", "bleed_air_1"), (975, "APU\nBLEED", "bleed_air_apu"), (1065, "BLEED 2", "bleed_air_2")):
            self._draw_pu_static_toggle(canvas, *pt(x, 221), label, key=key, on=self._pu_input_value(key, 0) >= .5, compact=True)

        fuel_controls = (
            (55, 325, "CTR L", "fuel_ctr_l"), (120, 325, "CTR R", "fuel_ctr_r"), (185, 325, "1 FWD", "fuel_l_fwd"),
            (55, 395, "1 AFT", "fuel_l_aft"), (120, 395, "2 FWD", "fuel_r_fwd"), (185, 395, "2 AFT", "fuel_r_aft"),
        )
        for x, y, label, key in fuel_controls:
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True)

        generator_controls = (
            (275, 320, "APU 1\nOFF", "apu_gen1_off"), (340, 320, "APU 1\nON", "apu_gen1_on"),
            (405, 320, "APU 2\nOFF", "apu_gen2_off"), (470, 320, "APU 2\nON", "apu_gen2_on"),
        )
        for x, y, label, key in generator_controls:
            self._draw_pu_action_button(canvas, *pt(x, y), label, key, scale=scale)
        egt_x, egt_y = pt(300, 390)
        egt_value = self._number({"value": self._pu_output_value("apu_egt", "0")}, "value", 0.0)
        radius = max(20, 27 * scale)
        canvas.create_oval(egt_x - radius, egt_y - radius, egt_x + radius, egt_y + radius, fill="#080a0e", outline="#a99d83", width=2)
        canvas.create_text(egt_x, egt_y - 6 * scale, text="APU EGT", fill="#eadfc4", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        canvas.create_text(egt_x, egt_y + 10 * scale, text=f"{round(egt_value):03d}", fill="#ffbf69", font=("Consolas", max(8, int(10 * scale)), "bold"))
        self._draw_pu_detent(canvas, *pt(420, 388), "WIPER", "wiper_selector", ("PARK", "INT", "LOW", "HIGH"), self._pu_choice_index("wiper_selector", 0, ("PARK", "INT", "LOW", "HIGH")), scale=scale)

        for x, label, key in ((548, "ENG 1", "hyd_eng1"), (620, "ELEC 2", "hyd_elec2"), (692, "ELEC 1", "hyd_elec1"), (764, "ENG 2", "hyd_eng2")):
            self._draw_pu_static_toggle(canvas, *pt(x, 321), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True)
        battery_on = self._pu_input_value("battery_on", 1.0 if self._pu_battery_on else 0.0) >= .5
        self._pu_battery_on = battery_on
        self._draw_pu_battery(canvas, *pt(552, 383), battery_on, scale=scale)
        self._draw_pu_selector(canvas, *pt(648, 376), "NO SMOKE", "no_smoking", choices=("OFF", "ON"), active_index=0 if self._pu_input_value("no_smoking", 2) < 1 else 1, scale=scale)
        self._draw_pu_selector(canvas, *pt(735, 376), "SEAT BELTS", "fasten_belts", choices=("OFF", "AUTO", "ON"), active_index=self._pu_choice_index("fasten_belts", 1, ("OFF", "AUTO", "ON")), scale=scale)
        brightness_x, brightness_y = pt(800, 390)
        brightness = self._pu_axis_fraction(self._pu_input_value("panel_brightness", 0.0))
        self._highlight_ring(canvas, brightness_x - 24 * scale, brightness_y - 10 * scale, brightness_x + 24 * scale, brightness_y + 10 * scale, "panel_brightness", radius=4)
        rail = canvas.create_line(brightness_x - 20 * scale, brightness_y, brightness_x + 20 * scale, brightness_y, fill="#596478", width=max(2, int(3 * scale)), capstyle="round")
        self._tag(canvas, rail, "panel_brightness")
        knob_x = brightness_x - 20 * scale + 40 * scale * brightness
        knob = canvas.create_oval(knob_x - 5 * scale, brightness_y - 5 * scale, knob_x + 5 * scale, brightness_y + 5 * scale, fill=ACCENT, outline=self._control_color("panel_brightness"))
        self._tag(canvas, knob, "panel_brightness")
        label = canvas.create_text(brightness_x, brightness_y + 15 * scale, text="PANEL BRIGHT", fill="#e7d9b5", font=("Segoe UI Semibold", max(7, int(8 * scale))))
        self._tag(canvas, label, "panel_brightness")

        for x, title, display_key, dec, inc in (
            (907, "FLT ALT", "flt_altitude", "flt_alt_ccw", "flt_alt_cw"),
            (1043, "LAND ALT", "land_altitude", "land_alt_ccw", "land_alt_cw"),
        ):
            px, py = pt(x, 310)
            self._draw_window(canvas, px, py, title, self._pu_output_value(display_key), width=max(88, int(105 * scale)))
            self._draw_pu_rotary(canvas, *pt(x, 378), title, "CCW / CW", dec=dec, inc=inc, scale=scale)

        for x, label, key in (
            (50, "LAND L", "landing_light_left"), (110, "LAND R", "landing_light_right"),
            (170, "TURN L", "runway_turnoff_left"), (230, "TURN R", "runway_turnoff_right"), (290, "TAXI", "taxi_light"),
            (878, "LOGO", "logo_light"), (1032, "BEACON", "beacon_light"), (1090, "WING", "wing_light"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, 527), label, key=key, on=self._pu_input_value(key, 0) >= .5, compact=True)
        self._draw_pu_detent(canvas, *pt(395, 520), "APU", "apu_start", ("OFF", "ON", "START"), self._pu_choice_index("apu_start", 0, ("OFF", "ON", "START")), scale=scale)
        eng_choices = ("GRD", "OFF", "CONT", "FLT")
        self._draw_pu_selector(canvas, *pt(545, 520), "ENG START 1", "engine_start_1", choices=eng_choices, active_index=self._pu_choice_index("engine_start_1", 1, eng_choices), scale=scale)
        ignition_values = (-1, 0, 1)
        ignition_current = int(round(self._pu_input_value("ignition_source", 0)))
        self._draw_pu_detent(canvas, *pt(675, 520), "IGNITION", "ignition_source", ("IGN L", "BOTH", "IGN R"), ignition_values.index(ignition_current) if ignition_current in ignition_values else 1, scale=scale)
        self._draw_pu_selector(canvas, *pt(775, 520), "ENG START 2", "engine_start_2", choices=eng_choices, active_index=self._pu_choice_index("engine_start_2", 1, eng_choices), scale=scale)
        position_values = (-1, 0, 1)
        position_current = int(round(self._pu_input_value("position_lights", 0)))
        self._draw_pu_detent(canvas, *pt(950, 520), "POSITION", "position_lights", ("STEADY", "OFF", "STROBE"), max(0, min(2, position_values.index(position_current) if position_current in position_values else 1)), scale=scale)

        canvas.create_text(*pt(560, 604), state="hidden", text="All controls shown have a verified PU source. Output test never drives the engine-start solenoid; P7 lamps are outputs only, not guessed switch feedback.", fill=MUTED, font=("Segoe UI", max(7, int(8 * scale))), width=int(1040 * scale))

    def _draw_pu_overhead(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw the PU as a spaced operating panel rather than a packed grid.

        This view keeps the overhead's natural systems scan while reserving
        clear room for the actual choices around each rotary and switch.  It
        intentionally uses no photographic texture: a Studio user needs
        readable interactions and remapping targets first.
        """

        design_width, design_height = 1240.0, 650.0
        scale = min((width - 24) / design_width, (height - 22) / design_height)
        # This is the only faceplate that benefits from filling the large
        # Studio workspace.  A 1.10 cap left a third of the available panel
        # blank on a normal 1080p display and made every real handle tiny.
        scale = max(.50, min(1.35, scale))
        panel_width, panel_height = design_width * scale, design_height * scale
        left = (width - panel_width) / 2
        top = max(7.0, (height - panel_height) / 2)

        def pt(x: float, y: float) -> tuple[float, float]:
            return left + x * scale, top + y * scale

        def card(x: float, y: float, w: float, h: float, title: str) -> None:
            x1, y1 = pt(x, y)
            x2, y2 = pt(x + w, y + h)
            canvas.create_round_rect(x1, y1, x2, y2, radius=max(7, 10 * scale), fill="#1b202a", outline="#647186", width=2)
            canvas.create_text((x1 + x2) / 2, y1 + 15 * scale, text=title, fill="#eadfc4", font=("Segoe UI Semibold", max(7, int(10 * scale))))

        x1, y1 = pt(0, 0)
        x2, y2 = pt(design_width, design_height)
        canvas.create_round_rect(x1, y1, x2, y2, radius=max(10, 14 * scale), fill="#10151e", outline="#758197", width=2)
        canvas.create_text(*pt(16, 19), text="PU OVERHEAD — HARDWARE / PRACTICE PANEL", anchor="w", fill=INK, font=("Segoe UI Semibold", max(12, int(16 * scale))))
        try:
            wake_test = bool(object.__getattribute__(self, "pu_wake_test").get())
        except AttributeError:  # Headless faceplate test harness.
            wake_test = False
        canvas.create_text(*pt(1222, 19), text="SAFE OUTPUT TEST ACTIVE" if wake_test else "SAFE OUTPUT TEST STANDBY", anchor="e", fill="#5ff5c2" if wake_test else MUTED, font=("Segoe UI Semibold", max(7, int(9 * scale))))
        canvas.create_text(*pt(16, 38), state="hidden", text="Click a control to select/map it; Practice also operates it. Teal = live physical input; gold = selected.", anchor="w", fill=MUTED, font=("Segoe UI", max(6, int(8 * scale))))

        card(10, 54, 200, 145, "P7 ANNUNCIATORS — OUTPUTS")
        card(222, 54, 180, 145, "IRS / NAV")
        card(414, 54, 230, 145, "ELECTRICAL")
        card(656, 54, 300, 145, "ICE PROTECTION")
        card(968, 54, 262, 145, "BLEED AIR")
        card(10, 211, 260, 190, "FUEL PUMPS")
        card(282, 211, 270, 190, "GENERATOR / APU")
        card(564, 211, 326, 190, "HYDRAULICS / CABIN")
        card(902, 211, 328, 190, "PRESSURIZATION")
        card(10, 413, 1220, 220, "EXTERIOR LIGHTS / APU / ENGINE START")

        # The P7 field is 32 actual output bits, grouped four rows by eight
        # here only to keep its output lenses readable without crowding the
        # control surfaces.  They never claim switch-state feedback.
        light_mask = self._pu_light_mask()
        for bit, label, _x, _y, _w, _h, tone in PU_ANNUNCIATOR_LAYOUT:
            lamp_x = 24 + (bit % 8) * 23
            lamp_y = 100 + (bit // 8) * 24
            self._draw_pu_annunciator(canvas, *pt(lamp_x, lamp_y), label, tone, bool(light_mask & (1 << bit)), width=24 * scale, height=18 * scale)

        irs_choices = ("OFF", "ALIGN", "NAV", "ATT")
        self._draw_pu_selector(canvas, *pt(274, 128), "LEFT IRS", "irs_left", choices=irs_choices, active_index=self._pu_choice_index("irs_left", 2, irs_choices), scale=scale)
        self._draw_pu_selector(canvas, *pt(350, 128), "RIGHT IRS", "irs_right", choices=irs_choices, active_index=self._pu_choice_index("irs_right", 2, irs_choices), scale=scale)

        # Electrical and generator controls are momentary centre-return
        # levers. Each endpoint stays separately selectable because the PU
        # reader has confirmed separate OFF and ON contacts.
        self._draw_pu_static_toggle(canvas, *pt(440, 139), "YAW\nDAMP", key="yaw_damper", on=self._pu_input_value("yaw_damper", 1) >= .5, compact=True, scale=scale)
        for x, label, off_key, on_key in (
            (505, "GPU", "ground_power_off", "ground_power_on"),
            (565, "GEN 1", "gen1_off", "gen1_on"),
            (620, "GEN 2", "gen2_off", "gen2_on"),
        ):
            self._draw_pu_spring_toggle(canvas, *pt(x, 139), label, off_key, on_key, scale=scale)

        for x, y, label, key in (
            (680, 123, "L SIDE", "window_heat_l_side"), (735, 123, "L FWD", "window_heat_l_fwd"),
            (790, 123, "R FWD", "window_heat_r_fwd"), (845, 123, "R SIDE", "window_heat_r_side"),
            (692, 177, "PROBE L", "probe_heat_capt"), (748, 177, "PROBE R", "probe_heat_fo"),
            (804, 177, "WING A/I", "wing_anti_ice"), (860, 177, "ENG 1 A/I", "eng1_anti_ice"), (916, 177, "ENG 2 A/I", "eng2_anti_ice"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True, scale=scale)

        for x, label, key, choices in (
            (1006, "L PACK", "l_pack", ("OFF", "AUTO", "HIGH")),
            (1099, "ISOLATION", "isolation_valve", ("CLOSE", "AUTO", "OPEN")),
            (1192, "R PACK", "r_pack", ("OFF", "AUTO", "HIGH")),
        ):
            self._draw_pu_detent(canvas, *pt(x, 122), label, key, choices, self._pu_choice_index(key, 1, choices), scale=scale)
        for x, label, key in ((1006, "BLEED 1", "bleed_air_1"), (1099, "APU BLEED", "bleed_air_apu"), (1192, "BLEED 2", "bleed_air_2")):
            self._draw_pu_static_toggle(canvas, *pt(x, 177), label, key=key, on=self._pu_input_value(key, 0) >= .5, compact=True, scale=scale)

        for x, y, label, key in (
            (63, 286, "CTR L", "fuel_ctr_l"), (138, 286, "CTR R", "fuel_ctr_r"), (213, 286, "1 FWD", "fuel_l_fwd"),
            (63, 367, "1 AFT", "fuel_l_aft"), (138, 367, "2 FWD", "fuel_r_fwd"), (213, 367, "2 AFT", "fuel_r_aft"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, y), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True, scale=scale)

        for x, label, off_key, on_key in (
            (330, "APU GEN 1", "apu_gen1_off", "apu_gen1_on"),
            (435, "APU GEN 2", "apu_gen2_off", "apu_gen2_on"),
        ):
            self._draw_pu_spring_toggle(canvas, *pt(x, 288), label, off_key, on_key, scale=scale)
        egt_x, egt_y = pt(360, 357)
        egt_value = self._number({"value": self._pu_output_value("apu_egt", "0")}, "value", 0.0)
        egt_radius = max(19, 27 * scale)
        canvas.create_oval(egt_x - egt_radius, egt_y - egt_radius, egt_x + egt_radius, egt_y + egt_radius, fill="#080a0e", outline="#a99d83", width=2, tags="pu_egt_test")
        canvas.create_text(egt_x, egt_y - 6 * scale, text="APU EGT", fill="#eadfc4", font=("Segoe UI Semibold", max(6, int(8 * scale))), tags="pu_egt_test")
        canvas.create_text(egt_x, egt_y + 10 * scale, text=f"{round(egt_value):03d}", fill="#ffbf69", font=("Consolas", max(7, int(10 * scale)), "bold"), tags="pu_egt_test")
        self._draw_pu_selector(canvas, *pt(495, 354), "WIPER", "wiper_selector", choices=("PARK", "INT", "LOW", "HIGH"), active_index=self._pu_choice_index("wiper_selector", 0, ("PARK", "INT", "LOW", "HIGH")), scale=scale)

        for x, label, key in ((603, "ENG 1", "hyd_eng1"), (665, "ELEC 2", "hyd_elec2"), (727, "ELEC 1", "hyd_elec1"), (789, "ENG 2", "hyd_eng2")):
            self._draw_pu_static_toggle(canvas, *pt(x, 278), label, key=key, on=self._pu_input_value(key, 1) >= .5, compact=True, scale=scale)
        battery_on = self._pu_input_value("battery_on", 1.0 if self._pu_battery_on else 0.0) >= .5
        self._pu_battery_on = battery_on
        self._draw_pu_battery(canvas, *pt(604, 353), battery_on, scale=scale)
        self._draw_pu_toggle_selector(canvas, *pt(685, 351), "NO SMOKE", "no_smoking", choices=("OFF", "ON"), active_index=0 if self._pu_input_value("no_smoking", 2) < 1 else 1, scale=scale)
        self._draw_pu_toggle_selector(canvas, *pt(770, 351), "SEAT BELTS", "fasten_belts", choices=("OFF", "AUTO", "ON"), active_index=self._pu_choice_index("fasten_belts", 1, ("OFF", "AUTO", "ON")), scale=scale)
        self._draw_pu_axis_knob(canvas, *pt(850, 349), "panel_brightness", self._pu_input_value("panel_brightness", 0.0), scale=scale)

        for x, title, display_key, dec, inc in (
            (983, "FLT ALT", "flt_altitude", "flt_alt_ccw", "flt_alt_cw"),
            (1148, "LAND ALT", "land_altitude", "land_alt_ccw", "land_alt_cw"),
        ):
            px, py = pt(x, 275)
            self._draw_window(canvas, px, py, title, self._pu_output_value(display_key), width=max(90, int(118 * scale)))
            self._draw_pu_rotary(canvas, *pt(x, 350), title, "CCW / CW", dec=dec, inc=inc, scale=scale)

        for x, label, key in (
            (62, "LAND L", "landing_light_left"), (132, "LAND R", "landing_light_right"),
            (202, "TURN L", "runway_turnoff_left"), (272, "TURN R", "runway_turnoff_right"), (342, "TAXI", "taxi_light"),
            (1018, "LOGO", "logo_light"), (1090, "BEACON", "beacon_light"), (1162, "WING", "wing_light"),
        ):
            self._draw_pu_static_toggle(canvas, *pt(x, 503), label, key=key, on=self._pu_input_value(key, 0) >= .5, compact=True, scale=scale)
        self._draw_pu_detent(canvas, *pt(425, 505), "APU", "apu_start", ("OFF", "ON", "START"), self._pu_choice_index("apu_start", 0, ("OFF", "ON", "START")), scale=scale)
        engine_choices = ("GRD", "OFF", "CONT", "FLT")
        self._draw_pu_selector(canvas, *pt(555, 520), "ENG START 1", "engine_start_1", choices=engine_choices, active_index=self._pu_choice_index("engine_start_1", 1, engine_choices), scale=scale)
        ignition_values = (-1, 0, 1)
        ignition = int(round(self._pu_input_value("ignition_source", 0)))
        self._draw_pu_detent(canvas, *pt(695, 505), "IGNITION", "ignition_source", ("IGN L", "BOTH", "IGN R"), ignition_values.index(ignition) if ignition in ignition_values else 1, scale=scale)
        self._draw_pu_selector(canvas, *pt(825, 520), "ENG START 2", "engine_start_2", choices=engine_choices, active_index=self._pu_choice_index("engine_start_2", 1, engine_choices), scale=scale)
        position_values = (-1, 0, 1)
        position = int(round(self._pu_input_value("position_lights", 0)))
        self._draw_pu_detent(canvas, *pt(935, 505), "POSITION", "position_lights", ("STEADY", "OFF", "STROBE"), position_values.index(position) if position in position_values else 1, scale=scale)

        canvas.create_text(*pt(620, 614), state="hidden", text="Practice APU START animates the confirmed EGT output. Engine START GRD uses only the documented short P1 return-to-OFF pulse — no force, endpoint, or motor setting is invented.", fill=MUTED, font=("Segoe UI", max(6, int(8 * scale))), width=max(500, int(1110 * scale)))

    def _draw_pap3(self, canvas: tk.Canvas, width: int, height: int) -> None:
        mirror = self._device_mirror("pap3_mag")
        values = dict(mirror.get("values") or {})
        panel_left, panel_right = 32, width - 32
        canvas.create_round_rect(panel_left, 45, panel_right, height - 30, radius=16, fill="#111a2c", outline="#445673", width=2)
        canvas.create_text(panel_left + 22, 68, text="PAP3 MAG — LIVE MCP TWIN", anchor="w", fill=INK, font=("Segoe UI Semibold", 13))
        canvas.create_text(panel_right - 22, 68, state="hidden", text="Six MCP windows • original Zibo roles are active until remapped", anchor="e", fill=MUTED, font=("Segoe UI", 9))

        fallback = self._pap3_values
        speed = self._number(values, "speed", fallback["speed"])
        if self._number(values, "speed_is_mach", 0.0) >= 0.5:
            speed_text = f"M{speed:.2f}"
        else:
            speed_text = f"{round(speed):03d}"
        fields = (
            ("CRS CAPT", f"{round(self._number(values, 'course_capt', fallback['course_capt'])) % 360:03d}"),
            ("SPD", speed_text),
            ("HDG", f"{round(self._number(values, 'heading', fallback['heading'])) % 360:03d}"),
            ("ALT", f"{round(self._number(values, 'altitude', fallback['altitude'])):05d}"),
            ("V/S", f"{round(self._number(values, 'vertical_speed', fallback['vertical_speed'])):+05d}"),
            ("CRS FO", f"{round(self._number(values, 'course_fo', fallback['course_fo'])) % 360:03d}"),
        )
        display_y = 116
        for index, (label, value) in enumerate(fields):
            x = panel_left + 100 + index * ((panel_right - panel_left - 200) / 5)
            self._draw_window(canvas, x, display_y, label, value, width=116)

        knobs = (
            ("CRS CAPT", "course_capt_dec", "course_capt_inc", fields[0][1]),
            ("SPEED", "speed_dec", "speed_inc", fields[1][1]),
            ("HEADING", "heading_dec", "heading_inc", fields[2][1]),
            ("ALTITUDE", "altitude_dec", "altitude_inc", fields[3][1]),
            ("V/S", "vs_dec", "vs_inc", fields[4][1]),
            ("CRS FO", "course_fo_dec", "course_fo_inc", fields[5][1]),
        )
        for index, (label, dec, inc, value) in enumerate(knobs):
            x = panel_left + 100 + index * ((panel_right - panel_left - 200) / 5)
            self._draw_rotary(canvas, x, 216, label, value, dec=dec, inc=inc)

        rows = (
            ("n1", "speed", "vnav", "lvl_chg", "hdg_sel", "lnav", "vorloc", "app", "alt_hld", "vs"),
            ("cmd_a", "cws_a", "cmd_b", "cws_b", "change_over", "spd_intv", "alt_intv"),
        )
        for row, keys in enumerate(rows):
            step = (panel_right - panel_left - 130) / max(1, len(keys) - 1)
            for index, key in enumerate(keys):
                info = self._visual_controls().get(key, {"label": key})
                self._draw_button(canvas, panel_left + 65 + index * step, 315 + row * 48, str(info["label"]), key, width=76)

        toggles = (
            ("fd_capt", "FD CAPT", "fd_capt"), ("fd_fo", "FD FO", "fd_fo"),
            ("ap_disconnect", "A/P DISC", "ap_disconnect"), ("at_arm", "A/T ARM", "at_arm"),
            ("bank_angle", "BANK ANGLE", "bank_angle"),
        )
        for index, (key, label, value_key) in enumerate(toggles):
            active = bool(round(self._number(values, value_key, 0.0)))
            self._draw_switch(canvas, panel_left + 115 + index * ((panel_right - panel_left - 230) / 4), 430, label, key, active)

        canvas.create_text(width / 2, height - 55, state="hidden", text="Touch any physical button, dial direction or switch: it lights here immediately. Click it once to inspect its original role or replace that role in this profile.", fill=MUTED, font=("Segoe UI", 9))

    def _draw_agp(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw a full-width AGP faceplate from the verified contact map."""

        is_toliss = self._is_toliss_throttle_workspace()
        mirror = self._device_mirror("agp_bb80")
        shown = list(mirror.get("values") or ())
        if len(shown) != 3:
            shown = ["----", "------", "----"]
        page = str(mirror.get("page") or self._agp_page).upper()
        live_controls = dict(mirror.get("controls") or {})
        if live_controls:
            self._agp_brake_fan = bool(live_controls.get("brake_fan", self._agp_brake_fan))
            self._agp_autobrake = str(live_controls.get("autobrake", self._agp_autobrake))
            self._agp_anti_skid = bool(live_controls.get("anti_skid", self._agp_anti_skid))
            self._agp_terrain = (
                bool(live_controls.get("terrain", self._agp_terrain))
                if is_toliss else page == "NAVIGATION"
            )
            self._agp_gear = str(live_controls.get("gear", self._agp_gear))
            self._agp_elapsed_running = bool(live_controls.get("elapsed_running", self._agp_elapsed_running))
        reported_raw = dict(mirror.get("rotary_raw") or {})
        for name in self._agp_rotary_raw:
            if name in reported_raw:
                self._agp_rotary_raw[name] = int(self._number(reported_raw, name, self._agp_rotary_raw[name]))

        panel_left, panel_right = 24, width - 24
        panel_top, panel_bottom = 26, height - 24
        canvas.create_round_rect(panel_left, panel_top, panel_right, panel_bottom, radius=22, fill="#25303d", outline="#8a97aa", width=3)
        canvas.create_round_rect(panel_left + 16, panel_top + 16, panel_right - 16, panel_bottom - 16, radius=16, fill="#1b2532", outline="#57677c", width=2)
        canvas.create_text(panel_left + 28, panel_top + 34, text="32 AGP METAL — LIVE CONTROL PANEL", anchor="w", fill="#f5f8ff", font=("Segoe UI Semibold", 14))
        canvas.create_text(panel_right - 28, panel_top + 34, text=f"Live page: {page}  •  raw encoders verified", anchor="e", fill="#c3cad7", font=("Segoe UI", 9))

        top = panel_top + 63
        top_bottom = min(top + 210, panel_bottom - 250)
        inner_left, inner_right = panel_left + 30, panel_right - 30
        gap = 14
        gear_right = inner_left + (inner_right - inner_left) * .28
        brake_right = gear_right + gap + (inner_right - inner_left) * .37
        sections = (
            (inner_left, gear_right, "LANDING GEAR"),
            (gear_right + gap, brake_right, "BRAKE / AUTOBRAKE"),
            (brake_right + gap, inner_right, "BRAKE FAN / STEERING / TERRAIN"),
        )
        for x1, x2, title in sections:
            canvas.create_round_rect(x1, top, x2, top_bottom, radius=12, fill="#121c29", outline="#56687f", width=2)
            canvas.create_text((x1 + x2) / 2, top + 17, text=title, fill="#f2d7a1", font=("Segoe UI Semibold", 9))

        gear_center = (inner_left + gear_right) / 2
        gear_arrow_color = "#ff514e" if self._agp_gear == "UP" else "#40db9a"
        gear_lamp_outline = "#ae4c50" if self._agp_gear == "UP" else "#6b8376"
        for index in range(3):
            x = gear_center - 62 + index * 62
            lamp = canvas.create_round_rect(x - 22, top + 31, x + 22, top + 75, radius=4, fill="#160b0d" if self._agp_gear == "UP" else "#07100e", outline=gear_lamp_outline, width=2)
            canvas.create_text(x, top + 52, text="▼", fill=gear_arrow_color, font=("Segoe UI", 22, "bold"))
            self._tag(canvas, lamp, "gear_down")
        lever_y = top + 112 if self._agp_gear == "UP" else top_bottom - 60
        rail = canvas.create_line(gear_center, top + 102, gear_center, top_bottom - 58, fill="#6d8097", width=6)
        self._tag(canvas, rail, "gear_up")
        self._tag(canvas, rail, "gear_down")
        lever_key = "gear_up" if self._agp_gear == "UP" else "gear_down"
        self._highlight_ring(canvas, gear_center - 27, lever_y - 15, gear_center + 27, lever_y + 15, lever_key, radius=9)
        handle = canvas.create_round_rect(gear_center - 25, lever_y - 13, gear_center + 25, lever_y + 13, radius=7, fill="#3c5068", outline=self._control_color(lever_key), width=3)
        self._tag(canvas, handle, lever_key)
        self._draw_mini_button(canvas, gear_center - 48, top_bottom - 24, "UP", "gear_up", width=50)
        self._draw_mini_button(canvas, gear_center + 48, top_bottom - 24, "DOWN", "gear_down", width=58)

        brake_center = (gear_right + gap + brake_right) / 2
        canvas.create_text(brake_center, top + 44, text="AUTO BRK", fill=INK, font=("Segoe UI Semibold", 10))
        for index, (label, key) in enumerate((("LOW", "autobrake_low"), ("MED", "autobrake_med"), ("MAX", "autobrake_max"))):
            self._draw_button(canvas, brake_center - 76 + index * 76, top + 76, label, key, width=62)
        canvas.create_text(brake_center, top + 123, text=f"SELECTED  {self._agp_autobrake}", fill=ACCENT if self._agp_autobrake != "OFF" else MUTED, font=("Consolas", 8, "bold"))

        steer_center = (brake_right + gap + inner_right) / 2
        self._draw_agp_flip_toggle(
            canvas, steer_center, top + 80, "A/SKID & N/W STRG",
            on_key="anti_skid_on", off_key="anti_skid_off", active=self._agp_anti_skid,
        )
        switch_y = top + 169
        fan_x, terrain_x = steer_center - 49, steer_center + 49
        fan_key = "brake_fan_off" if self._agp_brake_fan else "brake_fan_on"
        canvas.create_text(fan_x, switch_y - 42, text="BRK FAN", fill="#f5f8ff", font=("Segoe UI Semibold", 8, "bold"))
        canvas.create_text(terrain_x, switch_y - 42, text="TERR ON ND", fill="#f5f8ff", font=("Segoe UI Semibold", 8, "bold"))
        self._draw_agp_square_switch(canvas, fan_x, switch_y, "BRK\nFAN", fan_key, active=self._agp_brake_fan)
        self._draw_agp_square_switch(canvas, terrain_x, switch_y, "TERR\nON ND", "terr_on_nd")
        canvas.create_text(fan_x, switch_y + 39, text="LATCHED  ON" if self._agp_brake_fan else "LATCHED  OFF", fill=ACCENT if self._agp_brake_fan else "#d6e0ee", font=("Consolas", 7, "bold"))
        canvas.create_text(
            terrain_x, switch_y + 39,
            text=(
                "TERRAIN ON" if self._agp_terrain else "TERRAIN OFF"
            ) if is_toliss else (
                "NAV MODE" if self._agp_terrain else "RADIO MODE"
            ),
            fill=ACCENT if self._agp_terrain else "#d6e0ee", font=("Consolas", 7, "bold"),
        )

        clock_top, clock_bottom = top_bottom + 17, panel_bottom - 34
        clock_left, clock_right = inner_left, inner_right
        canvas.create_round_rect(clock_left, clock_top, clock_right, clock_bottom, radius=14, fill="#101923", outline="#65758a", width=2)
        canvas.create_text(
            clock_left + 20, clock_top + 19,
            text=(
                "AGP — CLOCK / RADIO / CTRL"
                if is_toliss else "AGP FALLBACK — RADIO / NAV"
            ),
            anchor="w", fill="#f2d7a1",
            font=("Segoe UI Semibold", 10),
        )
        canvas.create_text(clock_right - 20, clock_top + 19, text="Turn the three encoders or press their centres — each raw count is live", anchor="e", fill=MUTED, font=("Segoe UI", 7))
        display_y = clock_top + 60
        clock_w = clock_right - clock_left
        display_positions = (
            clock_left + clock_w * .38,
            clock_left + clock_w * .54,
            clock_left + clock_w * .70,
        )
        if is_toliss and page == "CLOCK":
            window_labels = ("CHR", "UTC", "ET")
        elif page in {"CTL", "NAVIGATION"}:
            window_labels = ("SPD", "ALT", "HDG")
        else:
            window_labels = ("RADIO", "FREQ", "ATC")
        for x, label, value, window_w in zip(
            display_positions, window_labels, shown, (118, 142, 118)
        ):
            self._draw_window(canvas, x, display_y, label, str(value), width=window_w)

        encoder_y = min(clock_bottom - 92, display_y + 102)
        if is_toliss and page == "CLOCK":
            roles = ("RST", "CHR", "DATE")
        elif page in {"CTL", "NAVIGATION"}:
            roles = ("RST / SPD", "CHR / ALT", "SET / HDG")
        else:
            roles = ("RST / FINE", "CHR / COARSE", "SET / ATC")
        self._draw_agp_press_rotary(
            canvas, display_positions[0], encoder_y, roles[0],
            self._agp_rotary_raw["rst"], dec="rst_ccw", press="rst", inc="rst_cw",
        )
        self._draw_agp_press_rotary(
            canvas, display_positions[1], encoder_y, roles[1],
            self._agp_rotary_raw["chr"], dec="chr_left", press="chr_press", inc="chr_right",
        )
        self._draw_agp_press_rotary(
            canvas, display_positions[2], encoder_y, roles[2],
            self._agp_rotary_raw["date"], dec="date_ccw", press="date_press", inc="date_cw",
        )

        selector_y = min(clock_bottom - 62, display_y + 92)
        try:
            mirror_vhf = int(mirror.get("vhf", 1) or 1)
        except Exception:
            mirror_vhf = 1
        self._draw_agp_three_way_selector(
            canvas, clock_left + clock_w * .14, selector_y, "VHF SELECT",
            (("1", "utc_gps"), ("2", "utc_int"), ("3", "utc_set")),
            {1: "utc_gps", 2: "utc_int", 3: "utc_set"}.get(mirror_vhf, "utc_gps"),
        )
        timer_active = "timer_run" if self._agp_elapsed_running else "timer_stop"
        if self._flash_until.get("timer_reset", 0.0) > time.monotonic():
            timer_active = "timer_reset"
        self._draw_agp_three_way_selector(
            canvas, clock_left + clock_w * .88, selector_y, "ATC MODE (RADIO)",
            (("RUN", "timer_run"), ("STP", "timer_stop"), ("RST", "timer_reset")), timer_active,
        )
        canvas.create_text(width / 2, panel_bottom - 16, text="Blue = original mapping • gold = selected for remapping • teal = live physical contact • RAW values are captured hardware counters, not invented axis ranges.", fill=MUTED, font=("Segoe UI", 8))

    def _draw_pdc_efis(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw the BB62 only from its captured input-bit map.

        The unit's output frame is known but its display/LED selectors are
        not.  The panel deliberately does not pretend to be an illuminated
        display: every visible, selectable item below has a captured BB62
        input bit and can therefore be remapped safely.
        """

        left, right = 30, width - 30
        top, bottom = 34, height - 28
        canvas.create_round_rect(left, top, right, bottom, radius=16, fill="#182237", outline="#4b607f", width=2)
        side = self._cockpit_sides.get(self._selected_device, CAPTAIN_SIDE)
        canvas.create_text(
            left + 22, top + 25,
            text=f"WINCTRL 3N PDC / AIRBUS EFIS — {side.upper()} — CAPTURED 2D PANEL",
            anchor="w", fill=INK, font=("Segoe UI Semibold", 13),
        )
        canvas.create_text(right - 22, top + 25, state="hidden", text="Blue = mapped/default  •  gold = selected  •  teal = live press", anchor="e", fill=MUTED, font=("Segoe UI", 9))

        # BB62's output packet framing is documented but no display selector
        # meaning is captured.  It remains a clearly-labelled blank window,
        # not a fake screen that a user could mistake for a real mirror.
        display_left, display_right = left + 28, right - 28
        canvas.create_round_rect(display_left, top + 54, display_right, top + 100, radius=6, fill="#08110f", outline="#596e67", width=2)
        canvas.create_text(width / 2, top + 70, text="PDC OUTPUT MIRROR", fill="#6f998c", font=("Segoe UI Semibold", 8))
        canvas.create_text(width / 2, top + 86, text="Not drawn: BB62 display / LED selector meaning has not been captured", fill="#c4d0df", font=("Segoe UI", 9))

        group_top = top + 125
        group_w = (right - left - 80) / 3
        groups = (
            (left + 24, "DISPLAY OVERLAYS", (
                ("FPV", "fpv"), ("MTRS", "mtrs"), ("WXR", "wxr"),
                ("STA", "sta"), ("WPT", "wpt"), ("ARPT", "arpt"),
                ("DATA", "data"), ("POS", "pos"), ("TERR", "terr"),
            )),
            (left + 40 + group_w, "MODE / RANGE", (
                ("APP", "mode_app"), ("VOR", "mode_vor"), ("MAP", "mode_map"), ("PLAN", "mode_plan"),
                ("5", "range_5"), ("10", "range_10"), ("20", "range_20"), ("40", "range_40"),
                ("80", "range_80"), ("160", "range_160"), ("320", "range_320"),
            )),
            (right - 24 - group_w, "AUXILIARY", (
                ("TFC", "tfc"), ("MINS RST", "mins_reset"), ("BARO STD", "baro_std"),
                ("RADIO", "mins_mode_radio"), ("BARO", "mins_mode_baro"),
                ("IN Hg", "baro_mode_in"), ("hPa", "baro_mode_hpa"),
            )),
        )
        for x, title, buttons in groups:
            canvas.create_round_rect(x, group_top, x + group_w, group_top + 190, radius=10, fill="#111b2e", outline="#3e526f", width=2)
            canvas.create_text(x + group_w / 2, group_top + 16, text=title, fill="#f2d7a1", font=("Segoe UI Semibold", 9))
            columns = 3 if len(buttons) > 8 else 2
            for index, (label, key) in enumerate(buttons):
                row, column = divmod(index, columns)
                columns_used = min(columns, len(buttons) - row * columns)
                cell = (group_w - 30) / max(1, columns)
                xpos = x + 15 + cell * (column + .5)
                ypos = group_top + 48 + row * 34
                self._draw_button(canvas, xpos, ypos, label, key, width=max(54, min(82, int(cell - 7))))

        lower_top = group_top + 214
        lower_bottom = min(bottom - 20, lower_top + 125)
        canvas.create_round_rect(left + 24, lower_top, right - 24, lower_bottom, radius=10, fill="#111b2e", outline="#3e526f", width=2)
        canvas.create_text(left + 44, lower_top + 17, text="VOR / ADF RECEIVERS", anchor="w", fill="#f2d7a1", font=("Segoe UI Semibold", 9))
        for receiver, base_x in (("1", width * .30), ("2", width * .55)):
            canvas.create_text(base_x, lower_top + 43, text=f"VOR / ADF {receiver}", fill=INK, font=("Segoe UI Semibold", 9))
            for index, (label, suffix) in enumerate((("VOR", "vor"), ("OFF", "off"), ("ADF", "adf"))):
                self._draw_button(canvas, base_x - 72 + index * 72, lower_top + 72, label, f"vor_adf_{receiver}_{suffix}", width=60)
        self._draw_rotary(canvas, width * .76, lower_top + 55, "MINS", "CCW / CW", dec="mins_knob_ccw", inc="mins_knob_cw", width=96)
        self._draw_rotary(canvas, width * .89, lower_top + 55, "BARO", "CCW / CW", dec="baro_knob_ccw", inc="baro_knob_cw", width=96)
        canvas.create_text(width / 2, bottom - 12, state="hidden", text=f"{side} virtual view • every blue control is a captured input and can be remapped. The blank mirror is intentional until the real display/LED selectors are learned.", fill=MUTED, font=("Segoe UI", 9))

    def _draw_winctrl_linear_axis(
        self, canvas: tk.Canvas, x1: float, x2: float, y: float, label: str,
        key: str, value: float, detents: tuple[tuple[float, str], ...], *,
        state: str = "", detent_font_size: int = 7,
        detent_label_offset: int = 24,
    ) -> None:
        """One horizontal Studio slider with labelled physical detents."""

        x1, x2 = float(x1), float(x2)
        canvas.create_text(x1, y - 21, text=label, anchor="w", fill=INK, font=("Segoe UI Semibold", 9))
        if state:
            canvas.create_text(x2, y - 21, text=state, anchor="e", fill="#b9f7df", font=("Consolas", 9, "bold"))
        track = canvas.create_round_rect(x1, y - 7, x2, y + 7, radius=6, fill="#07101c", outline="#52657d", width=2)
        self._tag(canvas, track, key)
        detent_count = len(detents)
        for index, (position, text_value) in enumerate(detents):
            x = x1 + max(0.0, min(1.0, position)) * (x2 - x1)
            tick = canvas.create_line(x, y - 13, x, y + 13, fill="#dca14b", width=2)
            text_x = x
            text_anchor = "center"
            if index == 0:
                text_x, text_anchor = x + 3, "w"
            elif index == detent_count - 1:
                text_x, text_anchor = x - 3, "e"
            elif detent_count == 6 and index == 1:
                # REV IDLE and IDLE are physically close. Put their text on
                # opposite sides of the ticks instead of shrinking it until
                # neither label can be read.
                text_x, text_anchor = x - 4, "e"
            elif detent_count == 6 and index == 2:
                text_x, text_anchor = x + 4, "w"
            self._tag(canvas, tick, key)
            if text_value:
                text = canvas.create_text(
                    text_x, y + detent_label_offset,
                    text=text_value, anchor=text_anchor, justify="center",
                    fill="#d7b57a",
                    font=("Segoe UI Semibold", detent_font_size),
                )
                self._tag(canvas, text, key)
        x = x1 + max(0.0, min(1.0, value)) * (x2 - x1)
        self._highlight_ring(canvas, x - 13, y - 13, x + 13, y + 13, key, radius=12)
        marker = canvas.create_oval(x - 10, y - 10, x + 10, y + 10, fill=self._control_fill(key, "#41536b"), outline=self._control_color(key), width=3 if key == self._selected_visual else 2)
        stem = canvas.create_line(x, y - 22, x, y + 22, fill="#c7d3e4", width=3)
        self._tag(canvas, marker, key)
        self._tag(canvas, stem, key)

    def _draw_winctrl_engine_toggle(
        self, canvas: tk.Canvas, x: float, y: float, title: str, idle_key: str, cutoff_key: str,
    ) -> None:
        """A two-end engine lever that only moves on its captured contacts."""

        now = time.monotonic()
        idle_live = self._flash_until.get(idle_key, 0.0) > now
        cutoff_live = self._flash_until.get(cutoff_key, 0.0) > now
        live_key = idle_key if idle_live else (cutoff_key if cutoff_live else "")
        handle_y = y - 25 if idle_live else (y + 25 if cutoff_live else y)
        canvas.create_text(x, y - 54, text=title, fill=INK, font=("Segoe UI Semibold", 9))
        slot = canvas.create_round_rect(x - 18, y - 36, x + 18, y + 36, radius=12, fill="#07101c", outline="#52657d", width=2)
        self._tag(canvas, slot, idle_key)
        self._tag(canvas, slot, cutoff_key)
        for offset, text_value, key in ((-38, "IDLE", idle_key), (38, "CUTOFF", cutoff_key)):
            item = canvas.create_text(x + 33, y + offset, text=text_value, anchor="w", fill=self._control_color(key), font=("Segoe UI Semibold", 8))
            hit = canvas.create_rectangle(x - 30, y + offset - 11, x + 78, y + offset + 11, outline="", fill="")
            self._tag(canvas, item, key)
            self._tag(canvas, hit, key)
        key = live_key or (self._selected_visual if self._selected_visual in {idle_key, cutoff_key} else idle_key)
        handle = canvas.create_round_rect(x - 24, handle_y - 11, x + 24, handle_y + 11, radius=6, fill=self._control_fill(key, "#3d4d64"), outline=self._control_color(key), width=3 if key == self._selected_visual else 2)
        self._tag(canvas, handle, key)

    def _draw_winctrl_output_tile(
        self, canvas: tk.Canvas, x: float, y: float, width: float, label: str, key: str,
    ) -> None:
        """Compact, clickable B930 output test tile for the live quadrant."""

        value = self._throttle_output_value(key, WINCTRL_THROTTLE_OUTPUT_DEFAULTS.get(key, 0))
        active = value > 0
        if "fire" in key:
            on_fill, on_outline = "#6b292c", DANGER
        elif "fault" in key:
            on_fill, on_outline = "#654c1e", WARN
        elif "vibration" in key:
            on_fill, on_outline = "#493c73", "#caa7ff"
        else:
            on_fill, on_outline = "#175462", ACCENT
        fill = on_fill if active else "#172336"
        outline = on_outline if active else "#566982"
        self._highlight_ring(canvas, x - width / 2 - 2, y - 21, x + width / 2 + 2, y + 21, key, radius=7)
        tile = canvas.create_round_rect(
            x - width / 2, y - 19, x + width / 2, y + 19,
            radius=6, fill=fill, outline=outline,
            width=3 if active or key == self._selected_visual else 2,
        )
        title = canvas.create_text(x, y - 3, text=label, fill=INK, font=("Segoe UI Semibold", 8), justify="center")
        state_text = (
            f"{value}" if key.startswith("vibration") else
            ("ON" if active else "OFF")
        )
        state = canvas.create_text(x, y + 11, text=state_text, fill=on_outline if active else MUTED, font=("Consolas", 8, "bold"))
        for item in (tile, title, state):
            self._tag(canvas, item, key)

    def _is_toliss_throttle_workspace(self) -> bool:
        return (
            self.simulator_mode.get() == SIMULATOR_XPLANE
            and self.xplane_aircraft.get() == AIRCRAFT_TOLISS
        )

    def _toliss_throttle_calibration(self) -> Dict[str, Any]:
        """Read the active ToLiss raw gates without borrowing Boeing values."""

        state = dict(self._device_states.get("winctrl_throttle") or {})
        candidates: List[Any] = [state.get("raw_calibration")]
        active = self._profile.get("active_profile")
        active_profile = (
            self._profile.get("profiles", {}).get(active, {}) if active else {}
        )
        candidates.append(
            dict(active_profile.get("calibration") or {}).get(
                "winctrl_throttle"
            )
        )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                return normalise_toliss_throttle_calibration(candidate)
            except ValueError:
                continue
        return default_toliss_throttle_calibration()

    def _toliss_throttle_probe_note(self, probe: Dict[str, Any]) -> str:
        error = str(probe.get("error") or "").strip()
        if error:
            return error
        if bool(probe.get("active")):
            next_gates = dict(probe.get("next") or {})
            progress = dict(probe.get("progress") or {})
            settling = dict(probe.get("settling") or {})
            details = []
            for side, title in (("left", "ENG 1"), ("right", "ENG 2")):
                gate = next_gates.get(side)
                label = (
                    TOLISS_THROTTLE_DETENT_LABELS.get(str(gate), str(gate))
                    if gate else "DONE"
                )
                active_settle = settling.get(side)
                if (
                    isinstance(active_settle, dict)
                    and active_settle.get("gate") == gate
                ):
                    remaining = max(
                        0, int(active_settle.get("remaining_ms", 0))
                    )
                    details.append(
                        f"{title}: HOLD {label} STEADY "
                        f"{remaining / 1000.0:.1f}s "
                        f"({int(progress.get(side, 0))}/6)"
                    )
                else:
                    details.append(
                        f"{title}: {label} "
                        f"({int(progress.get(side, 0))}/6)"
                    )
            return "CALIBRATING — " + "  •  ".join(details)
        if bool(probe.get("completed")) and bool(probe.get("saved")):
            return (
                "SAVED — ToLiss detent translation is active; safe pickup armed"
            )
        return (
            "READY — Set both levers to FULL REV, then select CALIBRATE DETENTS"
        )

    def _draw_winctrl_throttle(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Wide, readable URSA Minor panel based on captured controls only."""

        left, right = 30, width - 30
        top, bottom = 28, height - 26
        is_toliss = self._is_toliss_throttle_workspace()
        throttle_state = dict(
            self._device_states.get("winctrl_throttle") or {}
        )
        probe = dict(throttle_state.get("calibration_probe") or {})
        canvas.create_round_rect(left, top, right, bottom, radius=18, fill="#17243a", outline="#52647d", width=2)
        header = (
            "WINCTRL URSA MINOR — TOLISS A320/A321 THROTTLE"
            if is_toliss else
            "WINCTRL URSA MINOR THROTTLE — LIVE QUADRANT"
        )
        canvas.create_text(left + 24, top + 24, text=header, anchor="w", fill=INK, font=("Segoe UI Semibold", 14))
        if is_toliss:
            calibration_key = (
                "toliss_throttle_calibration_cancel"
                if bool(probe.get("active")) else
                "toliss_throttle_calibration_start"
            )
            calibration_label = (
                "CANCEL" if bool(probe.get("active")) else "CALIBRATE DETENTS"
            )
            self._draw_mini_button(
                canvas, right - 88, top + 24, calibration_label,
                calibration_key, width=142, half_height=13, font_size=9,
            )
            probe_note = self._toliss_throttle_probe_note(probe)
            calibration_source = str(
                throttle_state.get("calibration_source") or ""
            ).strip()
            show_source = bool(
                calibration_source
                and not probe.get("active")
                and not probe.get("error")
                and not (probe.get("completed") and probe.get("saved"))
            )
            status_left, status_right = left + 24, right - 24
            status_top, status_bottom = top + 43, top + 75
            canvas.create_round_rect(
                status_left, status_top, status_right, status_bottom,
                radius=8, fill="#0d1828", outline="#40546f", width=1,
            )
            source_width = 188 if show_source else 0
            canvas.create_text(
                status_left + 12, (status_top + status_bottom) / 2,
                text=probe_note,
                anchor="w", fill=WARN if probe.get("error") else MUTED,
                font=("Segoe UI Semibold", 9),
                width=status_right - status_left - 24 - source_width,
                justify="left",
            )
            if show_source:
                canvas.create_text(
                    status_right - 12, (status_top + status_bottom) / 2,
                    text=calibration_source.upper(), anchor="e",
                    fill="#b9f7df", font=("Segoe UI Semibold", 8),
                )
        else:
            canvas.create_text(right - 24, top + 24, state="hidden", text="Top sliders show the physical position • blue items are remappable", anchor="e", fill=MUTED, font=("Segoe UI", 9))

        thrust_left = left + 26
        thrust_right = right - 26
        if is_toliss:
            thrust_card_top, thrust_card_bottom = top + 80, top + 216
            slider_top, slider_step = top + 110, 59
            output_card_top, output_card_bottom = top + 220, top + 286
            output_title_y, output_tile_y = top + 232, top + 264
            lower_top = top + 300
        else:
            thrust_card_top, thrust_card_bottom = top + 48, top + 178
            slider_top, slider_step = top + 74, 54
            output_top = top + 196
            output_card_top, output_card_bottom = output_top - 22, output_top + 26
            output_title_y, output_tile_y = output_top - 12, output_top + 7
            lower_top = top + 262
        canvas.create_round_rect(
            thrust_left, thrust_card_top, thrust_right, thrust_card_bottom,
            radius=12, fill="#101a2c", outline="#425675", width=2,
        )
        toliss_calibration = (
            self._toliss_throttle_calibration() if is_toliss else None
        )
        boeing_detents = (
            (0.000, "FULL REV 0.0"), (0.215, "REV IDLE 21.5"),
            (0.308, "IDLE 30.8"), (0.692, "CL 69.2"),
            (0.846, "FLX/MCT 84.6"), (1.000, "TO/GA 100"),
        )
        for row, (key, title, side) in enumerate((
            ("left_thrust", "ENG 1 THRUST", "left"),
            ("right_thrust", "ENG 2 THRUST", "right"),
        )):
            fraction = self._axis_ease("winctrl_throttle", key, self._throttle_axis_fraction(key))
            if toliss_calibration is not None:
                gates = toliss_calibration[side]
                short_labels = {
                    "full_reverse": "FULL REV",
                    "reverse_idle": "REV IDLE",
                    "idle": "IDLE",
                    "climb": "CL",
                    "flex_mct": "FLEX/MCT",
                    "toga": "TOGA",
                }
                detents = tuple(
                    (
                        int(gates[gate]) / float(TOLISS_THROTTLE_RAW_AXIS_MAX),
                        f"{short_labels[gate]}\n{int(gates[gate]):05d}",
                    )
                    for gate in TOLISS_THROTTLE_DETENT_ORDER
                )
                state_text = f"RAW {int(round(fraction * TOLISS_THROTTLE_RAW_AXIS_MAX)):05d}"
            else:
                detents = boeing_detents
                state_text = f"{fraction * 100:05.1f}%"
            self._draw_winctrl_linear_axis(
                canvas, thrust_left + 42, thrust_right - 42,
                slider_top + row * slider_step,
                title, key, fraction, detents, state=state_text,
                detent_font_size=8 if is_toliss else 7,
                detent_label_offset=25 if is_toliss else 24,
            )

        canvas.create_round_rect(
            thrust_left, output_card_top, thrust_right, output_card_bottom,
            radius=9, fill="#0f1a2b", outline="#40546f", width=1,
        )
        canvas.create_text(
            thrust_left + 12, output_title_y, text="OUTPUT TESTS",
            anchor="w", fill="#f2d7a1",
            font=("Segoe UI Semibold", 9),
        )
        output_tiles = (
            ("THR\nBKL", "throttle_backlight"),
            ("PAC\nBKL", "flaps_airbrake_backlight"),
            ("TRIM\nBKL", "trim_display_backlight"),
            ("ENG 1\nFAULT", "engine_1_fault_light"),
            ("ENG 1\nFIRE", "engine_1_fire_light"),
            ("ENG 2\nFAULT", "engine_2_fault_light"),
            ("ENG 2\nFIRE", "engine_2_fire_light"),
            ("VIB\n1", "vibration_motor_1"),
            ("VIB\n2", "vibration_motor_2"),
        )
        tile_step = (thrust_right - thrust_left - 80) / max(1, len(output_tiles) - 1)
        for index, (label, key) in enumerate(output_tiles):
            self._draw_winctrl_output_tile(
                canvas, thrust_left + 40 + index * tile_step,
                output_tile_y, 66, label, key,
            )

        lower_bottom = bottom - 24
        usable_w = right - left - 76
        left_panel = left + 26
        centre_panel = left_panel + usable_w * .35 + 12
        right_panel = centre_panel + usable_w * .31 + 12
        panel_defs = (
            (left_panel, centre_panel - 12, "SPOILERS / FLAPS"),
            (centre_panel, right_panel - 12, "ENGINE / TRIM"),
            (right_panel, right - 26, "PARKING / DISCONNECT"),
        )
        for x1, x2, title in panel_defs:
            canvas.create_round_rect(x1, lower_top, x2, lower_bottom, radius=12, fill="#101a2c", outline="#425675", width=2)
            canvas.create_text((x1 + x2) / 2, lower_top + 17, text=title, fill="#f2d7a1", font=("Segoe UI Semibold", 10))

        spoiler = self._axis_ease("winctrl_throttle", "speedbrake", self._throttle_axis_fraction("speedbrake"))
        spoiler_state = (
            "DOWN" if spoiler <= .025 else
            "ARMED" if abs(spoiler - .0889) <= .025 else
            "HALF" if abs(spoiler - .5000) <= .05 else
            "UP" if spoiler >= .96 else "DEPLOY"
        )
        self._draw_winctrl_linear_axis(
            canvas, left_panel + 32, centre_panel - 44, lower_top + 63,
            "SPEEDBRAKE", "speedbrake", spoiler,
            ((0.0, ""), (.0889, "ARM"), (.50, "HALF"), (1.0, "UP")),
            state=spoiler_state, detent_font_size=8,
        )
        flap = self._axis_ease("winctrl_throttle", "flap_axis", self._throttle_axis_fraction("flap_axis"))
        self._draw_winctrl_linear_axis(
            canvas, left_panel + 32, centre_panel - 44, lower_top + 152,
            "FLAP LEVER", "flap_axis", flap,
            ((0.0, "0"), (.25, "5"), (.50, "15"), (.75, "25"), (1.0, "30")),
            state=f"{flap * 100:05.1f}%", detent_font_size=8,
        )
        canvas.create_text((left_panel + centre_panel - 12) / 2, lower_top + 202, text="FLAP DETENTS", fill=MUTED, font=("Segoe UI Semibold", 9))
        flap_keys = (("0", "flaps_0"), ("5", "flaps_5"), ("15", "flaps_15"), ("25", "flaps_25"), ("30", "flaps_30"))
        flap_span = (centre_panel - left_panel - 90) / 4
        for index, (label, key) in enumerate(flap_keys):
            self._draw_mini_button(
                canvas, left_panel + 45 + flap_span * index,
                lower_top + 228, label, key, width=46, font_size=8,
            )
        canvas.create_text((left_panel + centre_panel - 12) / 2, lower_top + 261, text="AUXILIARY BUTTONS", fill=MUTED, font=("Segoe UI Semibold", 9))
        self._draw_mini_button(canvas, (left_panel + centre_panel - 58) / 2, lower_top + 284, "AUX 1", "aux_button_1", width=66, font_size=8)
        self._draw_mini_button(canvas, (left_panel + centre_panel + 58) / 2, lower_top + 284, "AUX 2", "aux_button_2", width=66, font_size=8)

        engine_mid = (centre_panel + right_panel - 12) / 2
        self._draw_winctrl_engine_toggle(canvas, engine_mid - 62, lower_top + 90, "ENG 1", "engine_1_idle", "engine_1_cutoff")
        self._draw_winctrl_engine_toggle(canvas, engine_mid + 62, lower_top + 90, "ENG 2", "engine_2_idle", "engine_2_cutoff")
        trim_top = lower_top + 152
        canvas.create_round_rect(centre_panel + 20, trim_top, right_panel - 32, lower_bottom - 12, radius=9, fill="#18263b", outline="#52657d", width=2)
        throttle_mirror = dict(throttle_state.get("mirror") or {})
        throttle_values = dict(throttle_mirror.get("values") or {})
        bridge_trim_mode = str(throttle_values.get("trim_role") or "").upper()
        trim_mode = (
            bridge_trim_mode
            if is_toliss and bridge_trim_mode in self._throttle_trim_values
            else self._throttle_trim_mode
        )
        fallback_trim_value = self._throttle_trim_values.get(trim_mode or "", 0.0)
        trim_value = self._throttle_trim_display_value(trim_mode, fallback_trim_value)
        # STAB is shown to the owner as PITCH - the label they asked for -
        # even though it reuses the "STAB" value/channel internally.
        mode_label = "PITCH" if trim_mode == "STAB" else trim_mode
        trim_title = f"{mode_label} TRIM" if trim_mode else "TRIM ROLE — NEUTRAL"
        canvas.create_text(engine_mid, trim_top + 14, text=trim_title, fill=INK, font=("Segoe UI Semibold", 9))
        canvas.create_round_rect(centre_panel + 34, trim_top + 28, engine_mid + 10, trim_top + 58, radius=4, fill="#07100e", outline="#5a705f")
        announcing_mode = time.monotonic() < self._throttle_trim_label_until
        if announcing_mode:
            lcd_text = mode_label or "----"
        elif trim_mode == "STAB":
            lcd_text = f"{trim_value:05.1f}"
        else:
            lcd_text = f"{trim_value:+05.1f}"
        canvas.create_text((centre_panel + 34 + engine_mid + 10) / 2, trim_top + 43, text=lcd_text, fill="#b9f7df", font=("Consolas", 11, "bold"))
        canvas.create_oval(engine_mid + 27, trim_top + 25, engine_mid + 70, trim_top + 68, fill="#2f3e54", outline="#8596ad", width=2)
        pointer_angle = trim_value * 0.62
        canvas.create_line(engine_mid + 49, trim_top + 47, engine_mid + 49 + 16 * pointer_angle, trim_top + 35, fill="#d8e1ef", width=3)
        self._draw_mini_button(canvas, centre_panel + 52, trim_top + 77, "◀", "rudder_trim_left", width=34, font_size=8)
        self._draw_mini_button(canvas, engine_mid + 2, trim_top + 77, "RESET", "rudder_trim_reset", width=62, font_size=8)
        self._draw_mini_button(canvas, right_panel - 58, trim_top + 77, "▶", "rudder_trim_right", width=34, font_size=8)
        selector_active = (
            str(throttle_values.get("trim_selector") or "trim_mode_norm")
            if is_toliss else self._throttle_trim_selector
        )
        if is_toliss:
            self._draw_mini_button(
                canvas, engine_mid, trim_top + 103,
                "PUSH KNOB • NEXT TRIM", "trim_mode_cycle",
                width=138, half_height=10, font_size=8,
            )
            selector_y = trim_top + 132
            selector_options = (
                ("CRANK", "trim_mode_crank"),
                ("NORM", "trim_mode_norm"),
                ("IGN/START", "trim_mode_ign_start"),
            )
        else:
            canvas.create_text(engine_mid, trim_top + 99, text="SELECTOR / TRIM ROLE", fill=MUTED, font=("Segoe UI Semibold", 8))
            selector_y = trim_top + 108
            selector_options = (
                ("CRANK\nPITCH", "trim_mode_crank"),
                ("NORM\nRUD", "trim_mode_norm"),
                ("IGN/START\nAIL", "trim_mode_ign_start"),
            )
        self._draw_efis_selector(
            canvas, engine_mid, selector_y, selector_options,
            selector_active, width=160, font_size=8,
        )

        parking_x = (right_panel + right - 26) / 2
        canvas.create_text(parking_x, lower_top + 42, text="PARKING BRAKE", fill=INK, font=("Segoe UI Semibold", 10))
        parking_top = lower_top + 63
        canvas.create_round_rect(parking_x - 72, parking_top, parking_x + 72, parking_top + 42, radius=18, fill="#07101c", outline="#52657d", width=2)
        for offset, label, key in ((-48, "RELEASE", "parking_brake_off"), (48, "SET", "parking_brake_on")):
            x = parking_x + offset
            self._highlight_ring(canvas, x - 14, parking_top + 7, x + 14, parking_top + 35, key, radius=12)
            handle = canvas.create_oval(x - 12, parking_top + 9, x + 12, parking_top + 33, fill=self._control_fill(key, "#43536a"), outline=self._control_color(key), width=3 if key == self._selected_visual else 2)
            text = canvas.create_text(x, parking_top + 57, text=label, fill=self._control_color(key), font=("Segoe UI Semibold", 8))
            self._tag(canvas, handle, key)
            self._tag(canvas, text, key)
        canvas.create_text(parking_x, parking_top + 82, text="A/T DISCONNECT", fill=MUTED, font=("Segoe UI Semibold", 8))
        self._draw_button(canvas, parking_x - 46, parking_top + 111, "LEFT", "at_disconnect_left", width=66)
        self._draw_button(canvas, parking_x + 46, parking_top + 111, "RIGHT", "at_disconnect_right", width=66)
        canvas.create_text(width / 2, bottom - 10, state="hidden", text="LIVE HARDWARE OVERRIDES STUDIO PRACTICE CONTROLS", fill=MUTED, font=("Segoe UI Semibold", 9))

    def _draw_winctrl_pedals(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Live rudder and independently animated toe-brake faceplate."""

        left, right = 34, width - 34
        top, bottom = 34, height - 28
        canvas.create_round_rect(left, top, right, bottom, radius=18, fill="#1a2639", outline="#52647d", width=2)
        canvas.create_text(left + 24, top + 25, text="WINCTRL ORION RUDDER PEDALS — LIVE 2D", anchor="w", fill=INK, font=("Segoe UI Semibold", 14))
        canvas.create_text(right - 24, top + 25, state="hidden", text="Rudder and each toe brake are separate, remappable axes", anchor="e", fill=MUTED, font=("Segoe UI", 9))

        rudder = self._pedal_axis_value("rudder")
        left_brake = self._pedal_axis_value("left_toe_brake")
        right_brake = self._pedal_axis_value("right_toe_brake")
        centre = width / 2
        track_y = top + 150
        track_left, track_right = centre - 270, centre + 270
        canvas.create_round_rect(track_left, track_y, track_right, track_y + 44, radius=20, fill="#07101c", outline="#53667e", width=2)
        for fraction, label in ((0.0, "LEFT"), (.5, "CENTRE"), (1.0, "RIGHT")):
            x = track_left + fraction * (track_right - track_left)
            canvas.create_line(x, track_y + 7, x, track_y + 37, fill="#516078", width=2)
            canvas.create_text(x, track_y - 13, text=label, fill=MUTED, font=("Segoe UI Semibold", 8))
        carriage_x = centre + rudder * 210
        self._highlight_ring(canvas, carriage_x - 34, track_y + 5, carriage_x + 34, track_y + 39, "rudder", radius=12)
        carriage = canvas.create_round_rect(carriage_x - 32, track_y + 7, carriage_x + 32, track_y + 37, radius=10, fill=self._control_fill("rudder", "#35435a"), outline=self._control_color("rudder"), width=3 if self._selected_visual == "rudder" else 2)
        self._tag(canvas, carriage, "rudder")
        canvas.create_text(centre, top + 105, text=f"RUDDER  {rudder:+.3f}", fill="#b9f7df", font=("Consolas", 14, "bold"))

        # Each pedal is its own mechanical foot plate.  The lateral offset is
        # shared by both plates (rudder movement); the upper section pivots
        # forward independently for left/right toe brake pressure.
        base_y = track_y + 90
        for direction, key, title, brake, default_x in (
            (-1, "left_toe_brake", "LEFT TOE BRAKE", left_brake, centre - 188),
            (1, "right_toe_brake", "RIGHT TOE BRAKE", right_brake, centre + 188),
        ):
            x = default_x + rudder * 50
            frame = canvas.create_round_rect(x - 108, base_y, x + 108, bottom - 58, radius=16, fill="#101a2b", outline="#475d78", width=2)
            canvas.create_text(x, base_y + 18, text=title, fill="#f2d7a1", font=("Segoe UI Semibold", 10))
            plate_top = base_y + 70 - brake * 38
            plate = canvas.create_polygon(
                x - 78, plate_top + 25, x - 55, plate_top - 14,
                x + 55, plate_top - 14, x + 78, plate_top + 25,
                x + 60, plate_top + 95, x - 60, plate_top + 95,
                fill=self._control_fill(key, "#3a485d"), outline=self._control_color(key), width=3 if self._selected_visual == key else 2,
            )
            grooves = []
            for groove in range(4):
                gx = x - 38 + groove * 26
                grooves.append(canvas.create_line(gx, plate_top + 7, gx - 8, plate_top + 76, fill="#8493a8", width=3))
            pressure = canvas.create_text(x, bottom - 82, text=f"{brake * 100:05.1f}%", fill="#b9f7df", font=("Consolas", 13, "bold"))
            note = canvas.create_text(x, bottom - 59, state="hidden", text="press plate forward", fill=MUTED, font=("Segoe UI", 8))
            self._tag(canvas, frame, key)
            self._tag(canvas, plate, key)
            self._tag(canvas, pressure, key)
            self._tag(canvas, note, key)
            for groove in grooves:
                self._tag(canvas, groove, key)
        canvas.create_text(width / 2, bottom - 22, state="hidden", text="Click a blue axis in Practice mode to move it in safe steps. Real pedal movement always takes priority and is shown immediately.", fill=MUTED, font=("Segoe UI", 9))

    def _ecam_face_label(self, key: str, native_label: str) -> str:
        """Keep the Airbus legend until this profile deliberately remaps it."""

        active = self._profile.get("active_profile")
        active_profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        custom = active_profile.get("labels", {}).get("ecam32", {}).get(key)
        if custom:
            return str(custom)[:16]
        source = self._learned_source(key)
        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        binding = dict(profile.get("bindings", {}).get(f"ecam32.{source}", {}) or {}) if source else {}
        if not binding or str(binding.get("kind")) == "disabled":
            return native_label
        target = str(binding.get("target") or "").strip()
        if not target:
            return native_label
        reminder = target.rsplit("/", 1)[-1].replace("_", " ").replace("-", " ").upper()
        return reminder[:16] if reminder else native_label

    def _draw_ecam32(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw the physical ECAM32 in its native A320-style arrangement."""

        panel_w = min(width - 90, 1020)
        panel_h = min(height - 120, 610)
        left = (width - panel_w) / 2
        right = left + panel_w
        top = max(62, (height - panel_h) / 2 - 16)
        bottom = top + panel_h
        mirror = self._device_mirror("ecam32")
        reported = dict(mirror or {})
        device_state = dict(self._device_states.get("ecam32") or {})
        reader_state = str(device_state.get("state") or reported.get("status") or "waiting")
        contacts = list(reported.get("contacts_seen") or ())
        active_lamps = {
            int(index, 16) for index, value in dict(reported.get("lamps") or {}).items()
            if int(value or 0) > 0
        }
        yellow_backlight = max(
            int(dict(reported.get("lamps") or {}).get("00", 0) or 0),
            int(dict(reported.get("lamps") or {}).get("01", 0) or 0),
        )
        wake_state = bool(reported.get("wake_enabled"))

        canvas.create_text(left, top - 29, text="WINCTRL 32 ECAM — A320 CONTROL PANEL", anchor="w", fill=INK, font=("Segoe UI Semibold", 15))
        canvas.create_text(
            right, top - 29,
            state="hidden", text="A320 labels stay native until you save a remap",
            anchor="e", fill=MUTED, font=("Segoe UI", 9),
        )
        canvas.create_round_rect(left, top, right, bottom, radius=20, fill="#48515d", outline="#9eaab8", width=3)
        canvas.create_round_rect(left + 14, top + 14, right - 14, bottom - 14, radius=14, fill="#3b4551", outline="#222b37", width=2)

        status_fill = "#18c98b" if reader_state == "running" else "#ffbf69"
        canvas.create_oval(left + 35, top + 32, left + 49, top + 46, fill=status_fill, outline="#0b1119")
        awake = self._ecam_awake or wake_state
        canvas.create_text(left + 58, top + 39, text="ECAM PANEL AWAKE" if awake else "ECAM PANEL STANDBY", anchor="w", fill="#f5f8ff", font=("Segoe UI Semibold", 9, "bold"))
        backlight_text = f"YELLOW {yellow_backlight}/255" if yellow_backlight else "YELLOW OFF"
        canvas.create_text(right - 28, top + 39, text=f"BB70 {reader_state.upper()}  •  WAKE {'ON' if wake_state else 'OFF'}  •  {backlight_text}  •  {len(contacts)} CONTACTS", anchor="e", fill="#e8edf6", font=("Consolas", 8, "bold"))

        bay_left, bay_right = left + 38, right - 38
        bay_top, bay_bottom = top + 70, bottom - 56
        canvas.create_round_rect(bay_left, bay_top, bay_right, bay_bottom, radius=13, fill="#3a3931" if yellow_backlight else "#26303b", outline="#d6a34d" if yellow_backlight else "#778493", width=2)
        canvas.create_text((bay_left + bay_right) / 2, bay_top + 21, text="ELECTRONIC CENTRALIZED AIRCRAFT MONITOR", fill="#ffd166" if yellow_backlight else "#f0bd64", font=("Segoe UI Semibold", 10, "bold"))

        # The actual hardware is an Airbus ECP key matrix.  The supplied
        # capture covers each of these eighteen button contacts once; Learn
        # can still replace one local physical source without changing its
        # native Airbus legend.
        grid = (
            ("ecam_eng", "ecam_bleed", "ecam_press"),
            ("ecam_elec", "ecam_hyd", "ecam_fuel"),
            ("ecam_apu", "ecam_cond", "ecam_door"),
            ("ecam_wheel", "ecam_fctl", "ecam_all"),
            ("ecam_clr_left", "ecam_sts", "ecam_rcl"),
            # The two blank keycaps confirmed by "Ecam Blank.pcapng" fill
            # what used to be empty filler cells. _ECAM32_OFF_PANEL_BLANKS
            # below lists the remaining two - the "Other physical contact"
            # picker in the inspector reaches those instead.
            ("ecam_clr_right", "ecam_blank_1", "ecam_blank_2"),
        )
        details = {key: (label, role) for key, label, role in ECAM32_A320_CONTROLS}
        grid_x = (bay_left + bay_right) / 2 + 70
        col_step = 135
        row_step = 59
        first_y = bay_top + 80

        def draw_button(x: float, y: float, key: str, *, emergency: bool = False) -> None:
            native, _role = details[key]
            label = self._ecam_face_label(key, native)
            source = self._learned_source(key)
            active = key == self._ecam_active_page
            flashing = self._flash_until.get(key, 0.0) > time.monotonic()
            physical = self._live_control_active(key)
            lamp_index = ECAM32_CAPTURED_CONTACT_LED_INDEX.get(source)
            physical_lit = lamp_index in active_lamps if lamp_index is not None else False
            face = "#6a251f" if emergency else ("#17463f" if physical else ("#726019" if active or physical_lit else "#121a24"))
            outline = "#ff6d63" if emergency else ("#00ffd1" if physical else ("#ffd166" if active or physical_lit else (ACCENT if flashing else (BLUE if source else "#aab5c1"))))
            bezel = canvas.create_round_rect(x - 51, y - 21, x + 51, y + 21, radius=5, fill="#111720", outline="#9ba7b4", width=2)
            keycap = canvas.create_round_rect(x - 45, y - 16, x + 45, y + 16, radius=4, fill=face, outline=outline, width=3 if active or flashing else 2)
            text = canvas.create_text(x, y, text=label, fill="#fff4db" if active or emergency else "#f0f4fb", font=("Segoe UI Semibold", 8, "bold"), justify="center", width=84)
            state_text = "LIT" if physical_lit else ("MAPPED" if source else "CAPTURE")
            state = canvas.create_text(x, y + 30, text=state_text, fill="#ffd166" if physical_lit else (ACCENT if source else "#c8d2df"), font=("Consolas", 6, "bold"))
            token = self._tag if source else self._tag_capture
            for item in (bezel, keycap, text, state):
                token(canvas, item, key)

        for row, keys in enumerate(grid):
            for column, key in enumerate(keys):
                x = grid_x + (column - 1) * col_step
                y = first_y + row * row_step
                if key:
                    draw_button(x, y, key)
                else:
                    canvas.create_round_rect(x - 48, y - 19, x + 48, y + 19, radius=5, fill="#313b46", outline="#596673", width=1)

        special_x = bay_left + 145
        canvas.create_text(special_x, first_y - 45, text="ECAM ALERTS", fill="#f0bd64", font=("Segoe UI Semibold", 9, "bold"))
        draw_button(special_x, first_y + 55, "ecam_to_config")
        # The guard keeps the real panel's emergency control easy to identify
        # without claiming a mechanical guard position in the BB70 report.
        canvas.create_round_rect(special_x - 66, first_y + 126, special_x + 66, first_y + 198, radius=9, fill="#711f25", outline="#f0a0a0", width=3)
        draw_button(special_x, first_y + 162, "ecam_emer_canc", emergency=True)

        # Keep the sixth button row clear.  This guidance belongs beneath the
        # physical panel in the unused dark-blue canvas, not over CLR or its
        # click target.  The colour legend moves into the panel's lower trim.
        canvas.create_text(
            width / 2, bottom - 27,
            state="hidden", text="Amber = selected / physical lamp  •  teal = live physical press  •  blue = measured and ready to map  •  CAPTURE = not assigned yet",
            fill=MUTED, font=("Segoe UI", 8), tags=("ecam-state-legend",),
        )
        guidance_top = bottom + 7
        guidance_bottom = min(height - 4, bottom + 58)
        canvas.create_round_rect(
            bay_left + 58, guidance_top, bay_right - 58, guidance_bottom,
            radius=8, fill="#17212c", outline="#647384", width=2,
            tags=("ecam-measured-status",),
        )
        captured_count = sum(1 for key, _label, _role in ECAM32_A320_CONTROLS if self._learned_source(key))
        canvas.create_text(
            (bay_left + bay_right) / 2, guidance_top + 18,
            text=f"MEASURED BUTTON NAMES: {captured_count} / {len(ECAM32_A320_CONTROLS)}",
            fill="#eef3fb", font=("Segoe UI Semibold", 8, "bold"),
            tags=("ecam-measured-status",),
        )
        canvas.create_text(
            (bay_left + bay_right) / 2, guidance_top + 37,
            state="hidden", text="No packet-order guess is used. Only the exact physical button you assigned can activate each ECAM name.",
            fill=MUTED, font=("Segoe UI", 8), tags=("ecam-measured-status",),
        )







    def _draw_pdc_animated_asset_v2(self, canvas: tk.Canvas, width: int, height: int, device: str) -> None:
        """Animated, image-layer PDC model with invisible hit zones.

        MUSLIMSIM_PDC_ANIMATED_ASSET_MODEL_V2
        """
        import json
        import math
        import time as _pdc_time
        from pathlib import Path

        try:
            from PIL import Image, ImageTk, ImageEnhance
        except Exception:
            # Preserve the pre-V2 renderer if Pillow is unavailable.
            return self._draw_fixed_pdc_pre_anim_v2(canvas, width, height)

        side_folder = "bb61" if device == "pdc_bb61_left" else "bb52"
        asset_root = Path(__file__).resolve().parents[1] / "assets" / "pdc_animated_v2" / side_folder
        manifest_path = asset_root / "manifest.json"
        if not manifest_path.is_file():
            return self._draw_fixed_pdc_pre_anim_v2(canvas, width, height)

        if not hasattr(self, "_pdc_anim_v2_state"):
            self._pdc_anim_v2_state = {}
        state = self._pdc_anim_v2_state.setdefault(device, {
            "angles": {}, "positions": {}, "pulse_seen": {}, "relative": {},
        })
        if not hasattr(self, "_pdc_anim_v2_scaled"):
            self._pdc_anim_v2_scaled = {}
        if not hasattr(self, "_pdc_anim_v2_sources"):
            self._pdc_anim_v2_sources = {}
        if not hasattr(self, "_pdc_anim_v2_frame_scheduled"):
            self._pdc_anim_v2_frame_scheduled = False
        self._pdc_anim_v2_photo_refs = []

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return self._draw_fixed_pdc_pre_anim_v2(canvas, width, height)

        src_w, src_h = (float(x) for x in manifest.get("source_size", [1448,1086]))
        avail_w = max(200.0, float(width) - 24.0)
        avail_h = max(160.0, float(height) - 24.0)
        scale = min(avail_w/src_w, avail_h/src_h)
        draw_w = int(round(src_w*scale)); draw_h = int(round(src_h*scale))
        ox = (float(width)-draw_w)/2.0; oy=(float(height)-draw_h)/2.0

        def get_source(name):
            key=(device,name)
            src=self._pdc_anim_v2_sources.get(key)
            if src is None:
                src=Image.open(asset_root/name).convert("RGBA")
                self._pdc_anim_v2_sources[key]=src
            return src

        def scaled(name):
            src=get_source(name)
            key=(device,name,round(scale,4))
            out=self._pdc_anim_v2_scaled.get(key)
            if out is None:
                size=(max(1,int(round(src.width*scale))),max(1,int(round(src.height*scale))))
                out=src.resize(size,Image.Resampling.LANCZOS)
                self._pdc_anim_v2_scaled[key]=out
            return out

        def photo(image):
            p=ImageTk.PhotoImage(image)
            self._pdc_anim_v2_photo_refs.append(p)
            return p

        # Base art. Dynamic pieces below cover the static controls completely.
        base=scaled("base.png")
        canvas.create_image(ox,oy,image=photo(base),anchor="nw")

        # MUSLIMSIM_PRACTICE_DATA_PLANE_V4
        # The common composer has already joined live mirror, Practice preview,
        # persistent physical inputs and actual lab outputs. Do not overwrite
        # that result with a second raw-device merge.
        mirror=self._device_mirror(device)
        if not isinstance(mirror,dict): mirror={}
        sr=self._device_states.get(device,{})

        lab=getattr(self,"_lab",{})
        lab_inputs={}
        if isinstance(lab,dict):
            inputs=lab.get("inputs",{})
            if isinstance(inputs,dict):
                lab_inputs=inputs.get(device,{}) or {}

        def n(key,default=-1):
            try: return int(round(float(mirror.get(key,default))))
            except Exception: return int(default)

        def pulse(key,delta,relname):
            rec=lab_inputs.get(key,{}) if isinstance(lab_inputs,dict) else {}
            stamp=0.0
            try: stamp=max(stamp,float(self._flash_until.get(key,0.0)))
            except Exception: pass
            try:
                if isinstance(rec,dict) and str(rec.get("phase") or "") in {"press","change"} and float(rec.get("value",0.0))!=0.0:
                    stamp=max(stamp,float(rec.get("updated",0.0)))
            except Exception: pass
            seen=state["pulse_seen"].get(key,0.0)
            if stamp>seen:
                state["pulse_seen"][key]=stamp
                state["relative"][relname]=(float(state["relative"].get(relname,0.0))+delta)%360.0

        pulse("mins_inc",18.0,"mins_trim"); pulse("mins_dec",-18.0,"mins_trim")
        pulse("baro_inc",18.0,"baro_trim"); pulse("baro_dec",-18.0,"baro_trim")
        if device=="pdc_bb52_right":
            pulse("range_inc",18.0,"range_trim"); pulse("range_dec",-18.0,"range_trim")

        angles=manifest.get("angles",{})
        mins_idx=max(0,min(1,n("mins_mode",0))); baro_idx=max(0,min(1,n("baro_unit",0)))
        mins_target=float(angles.get("mins_mode",[-28,28])[mins_idx])+float(state["relative"].get("mins_trim",0.0))
        baro_target=float(angles.get("baro_unit",[-28,28])[baro_idx])+float(state["relative"].get("baro_trim",0.0))
        mode_idx=max(0,min(3,n("map_mode",2))); mode_target=float(angles.get("map_mode",[-48,-16,16,48])[mode_idx])
        if device=="pdc_bb61_left":
            range_idx=max(0,min(7,n("map_range",0))); range_target=float(angles.get("map_range",[-82,-58,-34,-10,14,38,62,86])[range_idx])
        else:
            range_target=float(state["relative"].get("range_trim",0.0))

        moving=False
        def ease(name,target,factor=0.28):
            nonlocal moving
            current=float(state["angles"].get(name,target))
            # shortest angular path
            diff=((target-current+180.0)%360.0)-180.0
            if abs(diff)>0.35:
                current=(current+diff*factor)%360.0; moving=True
            else:
                current=target%360.0
            state["angles"][name]=current
            return current

        mins_angle=ease("mins",mins_target); baro_angle=ease("baro",baro_target)
        mode_angle=ease("mode",mode_target); range_angle=ease("range",range_target)

        comps=manifest.get("components",{})
        def draw_asset(name,center,angle=0.0,key=None,pressed=False):
            im=scaled(name)
            if abs(angle)>0.01:
                im=im.rotate(-angle,resample=Image.Resampling.BICUBIC,expand=True)
            if pressed:
                im=ImageEnhance.Brightness(im).enhance(0.72)
            px=ox+float(center[0])*scale; py=oy+float(center[1])*scale
            item=canvas.create_image(px,py,image=photo(im),anchor="center")
            if key: self._tag(canvas,item,key)
            return item

        now=_pdc_time.monotonic()
        def active(key):
            return (
                key==self._selected_visual
                or self._flash_until.get(key,0.0)>now
                or self._live_control_active(key)
            )
        def halo(cx,cy,rx,ry,key,oval=True):
            if not active(key): return
            live = self._live_control_active(key)
            color="#00ffd1" if (self._flash_until.get(key,0.0)>now or live) else "#ffd166"
            x1=ox+(cx-rx)*scale; y1=oy+(cy-ry)*scale; x2=ox+(cx+rx)*scale; y2=oy+(cy+ry)*scale
            if oval: item=canvas.create_oval(x1,y1,x2,y2,fill="",outline=color,width=2)
            else: item=canvas.create_round_rect(x1,y1,x2,y2,radius=max(3,int(8*scale)),fill="",outline=color,width=2)
            self._tag(canvas,item,key)

        # Rotating outer rings + fixed center pushbuttons.
        draw_asset("mins_outer.png",comps["mins_outer"]["center"],mins_angle,"mins_mode")
        draw_asset("mins_center.png",comps["mins_center"]["center"],0,"mins_rst",active("mins_rst"))
        draw_asset("baro_outer.png",comps["baro_outer"]["center"],baro_angle,"baro_unit")
        draw_asset("baro_center.png",comps["baro_center"]["center"],0,"baro_std",active("baro_std"))
        draw_asset("mode_outer.png",comps["mode_outer"]["center"],mode_angle,"map_mode")
        draw_asset("mode_center.png",comps["mode_center"]["center"],0,"ctr",active("ctr"))
        draw_asset("range_outer.png",comps["range_outer"]["center"],range_angle,None)
        draw_asset("range_center.png",comps["range_center"]["center"],0,"tfc",active("tfc"))
        draw_asset("fpv.png",comps["fpv"]["center"],0,"fpv",active("fpv"))
        draw_asset("mtrs.png",comps["mtrs"]["center"],0,"mtrs",active("mtrs"))
        if device=="pdc_bb52_right" and "vsd" in comps:
            draw_asset("vsd.png",comps["vsd"]["center"],0,"vsd",active("vsd"))

        # Right RANGE: invisible half-zone images, not visible rectangles.
        if device=="pdc_bb52_right":
            hit=scaled("transparent_hit.png")
            for key,box in manifest.get("range_zones",{}).items():
                x1,y1,x2,y2=(float(v) for v in box)
                zone=hit.resize((max(1,int((x2-x1)*scale)),max(1,int((y2-y1)*scale))))
                item=canvas.create_image(ox+x1*scale,oy+y1*scale,image=photo(zone),anchor="nw")
                self._tag(canvas,item,key)
                halo((x1+x2)/2,(y1+y2)/2,(x2-x1)/2,(y2-y1)/2,key,False)
        else:
            # Entire fixed-range knob selects map_range.
            hit=scaled("transparent_hit.png")
            c=comps["range_outer"]["center"]; size=comps["range_outer"]["size"]
            zone=hit.resize((max(1,int(size[0]*scale)),max(1,int(size[1]*scale))))
            item=canvas.create_image(ox+c[0]*scale,oy+c[1]*scale,image=photo(zone),anchor="center")
            self._tag(canvas,item,"map_range")

        # VOR flip switches: hide the frozen handle, then move the two-ball handle.
        toggle=scaled("toggle_handle.png")
        for key in ("vor1","vor2"):
            g=manifest["switches"][key]; x=float(g["x"]); top=float(g["top"]); bottom=float(g["bottom"])
            value=max(0,min(2,n(key,1)))
            targets=[top+24.0,(top+bottom)/2.0,bottom-24.0]
            ytarget=targets[value]
            current=float(state["positions"].get(key,ytarget))
            diff=ytarget-current
            if abs(diff)>0.45:
                current += diff*0.32; moving=True
            else: current=ytarget
            state["positions"][key]=current
            # dark clean slot completely covers the static rendered lever
            canvas.create_round_rect(ox+(x-30)*scale,oy+(top-12)*scale,ox+(x+30)*scale,oy+(bottom+12)*scale,
                                     radius=max(6,int(20*scale)),fill="#0b141d",outline="#9ca9b4",width=2)
            canvas.create_line(ox+x*scale,oy+(top+8)*scale,ox+x*scale,oy+(bottom-8)*scale,fill="#5f6b74",width=max(2,int(4*scale)))
            item=canvas.create_image(ox+x*scale,oy+current*scale,image=photo(toggle),anchor="center")
            self._tag(canvas,item,key)
            # invisible full travel hit zone
            hit=scaled("transparent_hit.png").resize((max(1,int(76*scale)),max(1,int((bottom-top+36)*scale))))
            hititem=canvas.create_image(ox+x*scale,oy+((top+bottom)/2)*scale,image=photo(hit),anchor="center")
            self._tag(canvas,hititem,key)
            halo(x,(top+bottom)/2,38,(bottom-top+36)/2,key,False)

        # Bottom buttons, exact visible assets; no permanent outlines.
        for key in ("wxr","sta","wpt","arpt","data","pos","terr"):
            c=comps[key]["center"]
            draw_asset(key+".png",c,0,key,active(key))
            halo(c[0],c[1],comps[key]["size"][0]/2+3,comps[key]["size"][1]/2+3,key,False)

        # Subtle halos only for the active/selected controls.
        for key,name in (("mins_mode","mins_outer"),("mins_rst","mins_center"),("baro_unit","baro_outer"),("baro_std","baro_center"),
                         ("map_mode","mode_outer"),("ctr","mode_center"),("tfc","range_center"),("fpv","fpv"),("mtrs","mtrs")):
            c=comps[name]["center"]; s=comps[name]["size"]
            halo(c[0],c[1],s[0]/2+3,s[1]/2+3,key,True)
        if device=="pdc_bb52_right" and "vsd" in comps:
            c=comps["vsd"]["center"]; s=comps["vsd"]["size"]; halo(c[0],c[1],s[0]/2+3,s[1]/2+3,"vsd",False)
        if device=="pdc_bb61_left":
            c=comps["range_outer"]["center"]; s=comps["range_outer"]["size"]; halo(c[0],c[1],s[0]/2+3,s[1]/2+3,"map_range",True)

        # Truthful offline status without changing the art itself.
        service_state=str(sr.get("state") or "").strip().lower() if isinstance(sr,dict) else ""
        if self._detected.get(device) is None or service_state in {"disconnected","offline","waiting-for-usb","reconnecting","stopped"} or service_state.startswith("waiting"):
            canvas.create_round_rect(ox+draw_w*0.75,oy+draw_h*0.026,ox+draw_w*0.965,oy+draw_h*0.084,
                                     radius=max(4,int(8*scale)),fill="#40230d",outline="#ffb95c",width=2)
            canvas.create_text(ox+draw_w*0.857,oy+draw_h*0.055,text="USB NOT CONNECTED",fill="#ffd49b",font=("Segoe UI",10,"bold"))

        if moving and not self._pdc_anim_v2_frame_scheduled:
            self._pdc_anim_v2_frame_scheduled=True
            def _next_pdc_frame():
                self._pdc_anim_v2_frame_scheduled=False
                if self._selected_device in {"pdc_bb61_left","pdc_bb52_right"}:
                    self._draw_faceplate()
            self.after(16,_next_pdc_frame)






    def _pdc_flat_request_frame(self) -> None:
        if getattr(self, "_pdc_flat_frame_pending", False):
            return
        self._pdc_flat_frame_pending = True
        def _frame() -> None:
            self._pdc_flat_frame_pending = False
            if self._selected_device in {"pdc_bb61_left", "pdc_bb52_right", "pdc_bb62"}:
                self._draw_faceplate()
        try:
            self.after(16, _frame)
        except Exception:
            self._pdc_flat_frame_pending = False

    def _pdc_flat_animate(self, key: str, target: float, speed: float = 0.28) -> float:
        if not hasattr(self, "_pdc_flat_anim"):
            self._pdc_flat_anim = {}
        current = float(self._pdc_flat_anim.get(key, target))
        delta = float(target) - current
        if abs(delta) < 0.20:
            current = float(target)
        else:
            current += delta * max(0.05, min(0.75, float(speed)))
            self._pdc_flat_request_frame()
        self._pdc_flat_anim[key] = current
        return current

    def _axis_ease_request_frame(self, device: str) -> None:
        """Keep one device's continuous axes animating at ~60fps between polls.

        Real hardware position only arrives as often as the status poll runs
        (about 10Hz) - fine for a switch, not for a lever the owner watches
        move, which otherwise appears to hop once per poll. Mirrors
        ``_moza_yoke_request_frame`` but keyed by device name so the same
        helper serves the WinCtrl throttle, the TCA quadrant and the AB6.
        """

        if not hasattr(self, "_axis_ease_frame_pending"):
            self._axis_ease_frame_pending: Dict[str, bool] = {}
        if self._axis_ease_frame_pending.get(device):
            return
        self._axis_ease_frame_pending[device] = True

        def _frame() -> None:
            self._axis_ease_frame_pending[device] = False
            if self._selected_device == device:
                self._draw_faceplate()

        try:
            self.after(16, _frame)
        except Exception:
            self._axis_ease_frame_pending[device] = False

    def _axis_ease(self, device: str, key: str, target: float, speed: float = 0.30) -> float:
        """Smooth a 0..1 (or -1..1) axis fraction between the polls that feed it.

        ``_pdc_flat_animate``'s snap-to-target threshold (0.20) is tuned for
        degree/percentage-scale values; a raw fraction is scaled up before
        easing and back down after so the same threshold stays negligible.
        """

        eased = self._pdc_flat_animate(f"{device}:{key}", float(target) * 100.0, speed) / 100.0
        if abs(eased - target) > 1e-4:
            self._axis_ease_request_frame(device)
        return eased

    # The right PDC's RANGE is an endless rotary, not the left one's eight-way
    # switch, so its knob should keep turning for as long as the owner keeps
    # turning it rather than nudging and springing back to centre.  One detent
    # is 24 degrees, matching the tick marks drawn around the knob.
    PDC_RANGE_DETENT_DEGREES = 24.0

    def _pdc_range_turn_angle(self, device: str, mirror: Dict[str, Any]) -> float:
        """Accumulated RANGE rotation for an endless encoder.

        Each new pulse from ``range_inc`` / ``range_dec`` adds one detent in
        that direction.  The total is never wrapped for drawing - sine and
        cosine are periodic, so the knob simply keeps going round - but it is
        folded back toward zero once it grows large, together with the
        animation's own stored value so the eased position never jumps.
        """

        if not hasattr(self, "_pdc_range_turn"):
            self._pdc_range_turn: Dict[str, Dict[str, Any]] = {}
        state = self._pdc_range_turn.setdefault(device, {"angle": 0.0, "seen": {}})

        records = mirror.get("lab_inputs")
        if not isinstance(records, dict):
            records = {}

        def _mark(control: str) -> Optional[float]:
            record = records.get(control)
            if not isinstance(record, dict):
                return None
            # ``sequence`` counts every physical pulse; ``updated`` is the
            # fallback when the platform journal is not in the payload.
            for field in ("sequence", "updated"):
                if field in record:
                    try:
                        return float(record[field])
                    except (TypeError, ValueError):
                        continue
            return None

        for control, direction in (("range_inc", 1.0), ("range_dec", -1.0)):
            mark = _mark(control)
            if mark is None:
                continue
            previous = state["seen"].get(control)
            state["seen"][control] = mark
            if previous is None or mark <= previous:
                # First sight, or the bridge restarted its counter: adopt the
                # new mark without inventing a turn that never happened.
                continue
            state["angle"] += direction * self.PDC_RANGE_DETENT_DEGREES

        angle = float(state["angle"])
        if abs(angle) > 3600.0:
            # Fold both the target and the eased value by the same whole number
            # of turns, so the knob's drawn position is unchanged.
            # int() truncates toward zero; math is imported only inside the
            # draw method, not at module scope.
            shift = int(angle / 360.0) * 360.0
            angle -= shift
            state["angle"] = angle
            store = getattr(self, "_pdc_flat_anim", None)
            key = f"{device}:range_turn"
            if isinstance(store, dict) and key in store:
                store[key] = float(store[key]) - shift
        return angle

    def _draw_fixed_pdc(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """MUSLIMSIM_PDC_CLEAN_FLAT_RENDERER_V1
        MUSLIMSIM_PDC_CLEAN_REPAIR_V1"""
        import math
        import time

        device = self._selected_device
        if device not in {"pdc_bb61_left", "pdc_bb52_right", "pdc_bb62"}:
            self._draw_device_surface(canvas, width, height)
            return

        from muslimsim.gui.pdc_faceplate import control_keys, selector_value, recent_input, rotary_angle
        from ..hardware.discovery import hardware_presence
        is_bb62 = device == "pdc_bb62"
        is_left = device == "pdc_bb61_left"
        detected = self._detected.get(device) or {}
        state_record = self._device_states.get(device) or {}
        panel_name = str(detected.get("product") or state_record.get("detail") or
                         ("WINWING 3N PDC R" if is_bb62 else "WINWING PDC"))
        side_name = str(self._cockpit_sides.get(device, "Captain" if is_left else "First Officer")).upper()
        pid = detected.get("product_id") or state_record.get("pid")
        pid_name = f"4098:{int(pid):04X}" if pid else ""
        cyclic_3m = is_left and (pid == 0xBB51 or "3M PDC" in panel_name.upper())
        detented_range = is_bb62 or (is_left and not cyclic_3m)
        # Owner-facing brand/model, independent of firmware's old product string.
        panel_name = "WINCTRL 3M PDC" if cyclic_3m or device == "pdc_bb52_right" else "WINCTRL 3N PDC"
        keys = lambda key: control_keys(device, key)
        if not hasattr(self, "_pdc_rotary_feedback"):
            self._pdc_rotary_feedback = {}

        BASE_W, BASE_H = 1120.0, 720.0
        scale = min(float(width) / BASE_W, float(height) / BASE_H)
        ox = (float(width) - BASE_W * scale) / 2.0
        oy = (float(height) - BASE_H * scale) / 2.0
        X = lambda v: ox + v * scale
        Y = lambda v: oy + v * scale
        S = lambda v: v * scale
        def F(size, bold=False):
            return ("Segoe UI Semibold" if bold else "Segoe UI", max(8, int(round(size * scale))), "bold" if bold else "normal")

        state_record = self._device_states.get(device, {})
        if not isinstance(state_record, dict):
            state_record = {}
        # MUSLIMSIM_PRACTICE_DATA_PLANE_V4
        # _device_mirror() is already the fully composed physical + Practice
        # picture. Re-applying state_record["mirror"] here used to overwrite
        # the physical overlay and freeze selectors back at stale positions.
        mirror = self._device_mirror(device)
        if not isinstance(mirror, dict):
            mirror = {}
        def num(key, default):
            try:
                return selector_value(device, mirror, key, default, self._learned())
            except Exception:
                return int(default)

        service_state = str(state_record.get("state") or "").strip().lower()
        offline = not detected or hardware_presence(state_record) is False
        now = time.monotonic()
        def flashed(key):
            # Diagnostics are a bounded event log, not a state transport.
            # A held physical contact must stay visibly live even after its
            # diagnostic entry rolls out of the ring.
            active = (
                any(self._flash_until.get(source, 0.0) > now or self._live_control_active(source)
                    or recent_input(mirror, self._learned_source(source) or source, time.time())
                    for source in keys(key))
            )
            if active:
                self._pdc_flat_request_frame()
            return active
        def selected(key): return self._selected_visual in keys(key)
        def accent(key):
            return "#39d7c5" if flashed(key) else "#f2b84d" if selected(key) else "#657789"
        def fill(key, normal="#1c2a38"):
            return "#17463f" if flashed(key) else "#4a391b" if selected(key) else normal
        def tag(item, key): self._tag(canvas, item, keys(key)[0]); return item
        def hit_rect(x1,y1,x2,y2,key):
            choices = keys(key)
            for index, source in enumerate(choices):
                # Separate hit areas retain BB62's existing per-position keys.
                vertical = key in {"vor1", "vor2"}
                xa, xb = (x1, x2) if vertical else (x1+(x2-x1)*index/len(choices), x1+(x2-x1)*(index+1)/len(choices))
                ya, yb = (y1+(y2-y1)*index/len(choices), y1+(y2-y1)*(index+1)/len(choices)) if vertical else (y1,y2)
                self._tag(canvas, canvas.create_rectangle(X(xa),Y(ya),X(xb),Y(yb),fill="",outline="",width=0),source)
        def hit_oval(x1,y1,x2,y2,key):
            if len(keys(key)) > 1:
                hit_rect(x1,y1,x2,y2,key)
            else:
                tag(canvas.create_oval(X(x1),Y(y1),X(x2),Y(y2),fill="",outline="",width=0),key)

        TEXT="#f1f5f8"; MUTED="#a8b4bf"; PANEL="#172432"; PANEL2="#101a26"; KNOB="#d7dce0"; INNER="#202c37"; SLOT="#0c151f"
        canvas.create_round_rect(X(18),Y(16),X(1102),Y(704),radius=S(18),fill=PANEL2,outline="#6f7f8d",width=max(1,int(S(2))))
        canvas.create_round_rect(X(28),Y(26),X(1092),Y(694),radius=S(14),fill=PANEL,outline="#344758",width=max(1,int(S(2))))
        canvas.create_text(X(50),Y(53),text=f"{panel_name}  —  {side_name}  —  {pid_name}",anchor="w",fill=TEXT,font=F(14,True))
        canvas.create_text(X(1070),Y(53),text="USB NOT CONNECTED" if offline else "CONNECTED • LIVE",anchor="e",fill="#ffb75e" if offline else "#38d9a5",font=F(11,True))
        canvas.create_line(X(48),Y(78),X(1072),Y(78),fill="#445869",width=max(1,int(S(1))))

        def push(cx,cy,label,key,w=112,h=56):
            canvas.create_round_rect(X(cx-w/2),Y(cy-h/2),X(cx+w/2),Y(cy+h/2),radius=S(8),fill=fill(key),outline=accent(key),width=max(1,int(S(2))))
            canvas.create_text(X(cx),Y(cy),text=label,fill=TEXT,font=F(13,True))
            hit_rect(cx-w/2,cy-h/2,cx+w/2,cy+h/2,key)

        def round_button(cx,cy,label,key):
            canvas.create_text(X(cx),Y(cy-49),text=label,fill=TEXT,font=F(12,True))
            canvas.create_oval(X(cx-34),Y(cy-34),X(cx+34),Y(cy+34),fill=fill(key,"#18232e"),outline=accent(key),width=max(1,int(S(2))))
            canvas.create_oval(X(cx-25),Y(cy-25),X(cx+25),Y(cy+25),fill="#0f1821",outline="#596a79",width=max(1,int(S(1))))
            hit_oval(cx-38,cy-38,cx+38,cy+38,key)

        def selector_knob(cx,cy,heading,left_label,right_label,key,value,center_label,center_key):
            canvas.create_text(X(cx),Y(cy-96),text=heading,fill=TEXT,font=F(15,True))
            canvas.create_text(X(cx-72),Y(cy-69),text=left_label,fill=TEXT,font=F(10,True))
            canvas.create_text(X(cx+72),Y(cy-69),text=right_label,fill=TEXT,font=F(10,True))
            canvas.create_line(X(cx-44),Y(cy-53),X(cx-33),Y(cy-40),fill=TEXT,width=max(1,int(S(3))))
            canvas.create_line(X(cx+44),Y(cy-53),X(cx+33),Y(cy-40),fill=TEXT,width=max(1,int(S(3))))
            target=-42.0 if value==0 else 42.0 if value==1 else 0.0
            angle=self._pdc_flat_animate(f"{device}:{key}:angle",target)
            canvas.create_oval(X(cx-73),Y(cy-73),X(cx+73),Y(cy+73),fill=KNOB,outline=accent(key),width=max(1,int(S(2))))
            canvas.create_oval(X(cx-51),Y(cy-51),X(cx+51),Y(cy+51),fill=INNER,outline="#6b7b88",width=max(1,int(S(2))))
            r=math.radians(angle)
            canvas.create_line(X(cx+math.sin(r)*49),Y(cy-math.cos(r)*49),X(cx+math.sin(r)*67),Y(cy-math.cos(r)*67),fill="#24303a",width=max(3,int(S(6))))
            canvas.create_oval(X(cx-35),Y(cy-35),X(cx+35),Y(cy+35),fill=fill(center_key,"#17212c"),outline=accent(center_key),width=max(1,int(S(2))))
            canvas.create_text(X(cx),Y(cy),text=center_label,fill=TEXT,font=F(16,True))
            hit_oval(cx-75,cy-75,cx+75,cy+75,key)
            prefix = "mins" if key == "mins_mode" else "baro"
            dec, inc = prefix + "_dec", prefix + "_inc"
            state = self._pdc_rotary_feedback.setdefault(f"{device}:{prefix}", {})
            angle = rotary_angle(state, mirror, self._learned_source(keys(dec)[0]) or keys(dec)[0],
                                 self._learned_source(keys(inc)[0]) or keys(inc)[0])
            r = math.radians(angle)
            canvas.create_line(X(cx+math.sin(r)*37),Y(cy-math.cos(r)*37),
                               X(cx+math.sin(r)*49),Y(cy-math.cos(r)*49),
                               fill="#39d7c5" if flashed(dec) or flashed(inc) else "#d7dce0",
                               width=max(2,int(S(4))), tags=(f"pdc-rotation:{prefix}",))
            for source, dx, symbol in ((dec,-103,"−"),(inc,103,"+")):
                canvas.create_text(X(cx+dx),Y(cy+28),text=symbol,fill=accent(source),font=F(20,True))
                hit_rect(cx+dx-23,cy+3,cx+dx+23,cy+53,source)
            hit_oval(cx-37,cy-37,cx+37,cy+37,center_key)

        def vor_switch(cx,cy,key,title,adf_label,value,off_side):
            canvas.create_text(X(cx),Y(cy-104),text=title,fill=TEXT,font=F(12,True))
            t,b=cy-72,cy+72
            canvas.create_round_rect(X(cx-24),Y(t),X(cx+24),Y(b),radius=S(20),fill=SLOT,outline=accent(key),width=max(1,int(S(2))))
            canvas.create_line(X(cx),Y(t+18),X(cx),Y(b-18),fill="#81909c",width=max(2,int(S(4))))
            target=t+24 if value==0 else cy if value==1 else b-24 if value==2 else cy
            by=self._pdc_flat_animate(f"{device}:{key}:ball",float(target),0.34)
            canvas.create_oval(X(cx-13),Y(by-13),X(cx+13),Y(by+13),fill="#dde2e5",outline="#202a32",width=max(1,int(S(2))))
            canvas.create_oval(X(cx-6),Y(by-7),X(cx+2),Y(by+1),fill="#ffffff",outline="")
            offx=cx+56 if off_side=="right" else cx-56
            canvas.create_text(X(offx),Y(cy),text="OFF",fill=TEXT,font=F(11,True))
            canvas.create_text(X(cx),Y(cy+103),text=adf_label,fill=TEXT,font=F(11,True))
            hit_rect(cx-32,t-6,cx+32,b+6,key)

        def mode_knob(cx,cy,value):
            angles=[-52.0,-18.0,18.0,52.0]; angle=self._pdc_flat_animate(f"{device}:mode",angles[value] if value in range(4) else 0.0)
            positions={"APP":(cx-89,cy-61),"VOR":(cx-45,cy-91),"MAP":(cx+44,cy-91),"PLN":(cx+91,cy-61)}
            for label,a in zip(("APP","VOR","MAP","PLN"),angles):
                lx,ly=positions[label]; canvas.create_text(X(lx),Y(ly),text=label,fill=TEXT,font=F(10,True)); r=math.radians(a)
                canvas.create_line(X(cx+math.sin(r)*69),Y(cy-math.cos(r)*69),X(cx+math.sin(r)*81),Y(cy-math.cos(r)*81),fill=TEXT,width=max(1,int(S(3))))
            canvas.create_oval(X(cx-65),Y(cy-65),X(cx+65),Y(cy+65),fill=KNOB,outline=accent("map_mode"),width=max(1,int(S(2))))
            canvas.create_oval(X(cx-41),Y(cy-41),X(cx+41),Y(cy+41),fill=INNER,outline="#6b7b88",width=max(1,int(S(2))))
            r=math.radians(angle); canvas.create_line(X(cx+math.sin(r)*43),Y(cy-math.cos(r)*43),X(cx+math.sin(r)*61),Y(cy-math.cos(r)*61),fill="#24303a",width=max(3,int(S(6))))
            canvas.create_oval(X(cx-29),Y(cy-29),X(cx+29),Y(cy+29),fill=fill("ctr","#17212c"),outline=accent("ctr"),width=max(1,int(S(2))))
            canvas.create_text(X(cx),Y(cy),text="CTR",fill=TEXT,font=F(14,True)); hit_oval(cx-67,cy-67,cx+67,cy+67,"map_mode"); hit_oval(cx-31,cy-31,cx+31,cy+31,"ctr")

        def range_left(cx,cy,value):
            vals=("5","10","20","40","80","160","320","640"); ang=(-67,-48,-29,-10,10,29,48,67); angle=self._pdc_flat_animate(f"{device}:range",ang[value] if value in range(8) else 0.0)
            canvas.create_text(X(cx),Y(cy-108),text="RANGE",fill=TEXT,font=F(12,True))
            for label,a in zip(vals,ang):
                r=math.radians(a); tx=cx+math.sin(r)*102; ty=cy-math.cos(r)*102; canvas.create_text(X(tx),Y(ty),text=label,fill=TEXT,font=F(9,True)); canvas.create_line(X(cx+math.sin(r)*70),Y(cy-math.cos(r)*70),X(cx+math.sin(r)*81),Y(cy-math.cos(r)*81),fill=TEXT,width=max(1,int(S(3))))
            canvas.create_oval(X(cx-65),Y(cy-65),X(cx+65),Y(cy+65),fill=KNOB,outline=accent("map_range"),width=max(1,int(S(2))))
            canvas.create_oval(X(cx-41),Y(cy-41),X(cx+41),Y(cy+41),fill=INNER,outline="#6b7b88",width=max(1,int(S(2))))
            r=math.radians(angle); canvas.create_line(X(cx+math.sin(r)*43),Y(cy-math.cos(r)*43),X(cx+math.sin(r)*61),Y(cy-math.cos(r)*61),fill="#24303a",width=max(3,int(S(6))))
            canvas.create_oval(X(cx-29),Y(cy-29),X(cx+29),Y(cy+29),fill=fill("tfc","#17212c"),outline=accent("tfc"),width=max(1,int(S(2))))
            canvas.create_text(X(cx),Y(cy),text="TFC",fill=TEXT,font=F(14,True)); hit_oval(cx-67,cy-67,cx+67,cy+67,"map_range"); hit_oval(cx-31,cy-31,cx+31,cy+31,"tfc")

        def range_right(cx,cy):
            canvas.create_text(X(cx),Y(cy-108),text="RANGE",fill=TEXT,font=F(12,True))
            for a in (-48,-24,0,24,48):
                r=math.radians(a); canvas.create_line(X(cx+math.sin(r)*72),Y(cy-math.cos(r)*72),X(cx+math.sin(r)*83),Y(cy-math.cos(r)*83),fill=TEXT,width=max(1,int(S(3))))
            # An endless encoder: keep turning while the owner keeps turning,
            # instead of nudging 18 degrees and springing back to centre.
            if cyclic_3m:
                # Verified BB51 has relative contacts 21/22, not map_range.
                # Keep complete taps visible even when release arrives first.
                state = self._pdc_rotary_feedback.setdefault(f"{device}:range", {})
                target = rotary_angle(state, mirror,
                                      self._learned_source("range_dec") or "range_dec",
                                      self._learned_source("range_inc") or "range_inc")
                # Draw the observed relative angle directly so wrapping at 360
                # cannot animate a long reverse turn between adjacent detents.
            else:
                target = self._pdc_range_turn_angle(device,mirror)
            angle=target if cyclic_3m else self._pdc_flat_animate(f"{device}:range_turn",target,0.40)
            canvas.create_oval(X(cx-65),Y(cy-65),X(cx+65),Y(cy+65),fill=KNOB,outline=accent("range_inc"),width=max(1,int(S(2))))
            canvas.create_oval(X(cx-41),Y(cy-41),X(cx+41),Y(cy+41),fill=INNER,outline="#6b7b88",width=max(1,int(S(2))))
            r=math.radians(angle); canvas.create_line(X(cx+math.sin(r)*43),Y(cy-math.cos(r)*43),X(cx+math.sin(r)*61),Y(cy-math.cos(r)*61),fill="#24303a",width=max(3,int(S(6))))
            canvas.create_oval(X(cx-29),Y(cy-29),X(cx+29),Y(cy+29),fill=fill("tfc","#17212c"),outline=accent("tfc"),width=max(1,int(S(2))))
            canvas.create_text(X(cx),Y(cy),text="TFC",fill=TEXT,font=F(14,True)); canvas.create_text(X(cx-105),Y(cy),text="−",fill=TEXT,font=F(22,True)); canvas.create_text(X(cx+105),Y(cy),text="+",fill=TEXT,font=F(22,True))
            hit_rect(cx-132,cy-34,cx-78,cy+34,"range_dec")
            hit_rect(cx+78,cy-34,cx+132,cy+34,"range_inc")
            if cyclic_3m:
                hit_rect(cx-65,cy-65,cx,cy+65,"range_dec")
                hit_rect(cx,cy-65,cx+65,cy+65,"range_inc")
            hit_oval(cx-31,cy-31,cx+31,cy+31,"tfc")

        mins_mode=num("mins_mode",-1); baro_unit=num("baro_unit",-1); vor1=num("vor1",-1); vor2=num("vor2",-1); map_mode=num("map_mode",-1); map_range=num("map_range",-1)
        # Missing positions await the next status delta; they must not create
        # an unbounded chain of repaint timers while a contact is unavailable.
        selector_knob(210,215,"MINS","RADIO","BARO","mins_mode",mins_mode,"RST","mins_rst")
        selector_knob(910,215,"BARO","IN","HPA","baro_unit",baro_unit,"STD","baro_std")
        round_button(490,178,"FPV","fpv"); round_button(630,178,"MTRS","mtrs")
        if cyclic_3m or device == "pdc_bb52_right": push(560,275,"VSD","vsd",84,64)
        vor_switch(150,445,"vor1","VOR 1","ADF 1",vor1,"right"); vor_switch(970,445,"vor2","VOR 2","ADF 2",vor2,"left")
        mode_knob(430,450,map_mode)
        range_left(690,450,map_range) if detented_range else range_right(690,450)
        for i,(key,label) in enumerate((("wxr","WXR"),("sta","STA"),("wpt","WPT"),("arpt","ARPT"),("data","DATA"),("pos","POS"),("terr","TERR"))): push(115+i*148,630,label,key,112,56)
        canvas.create_text(X(560),Y(680),state="hidden", text="Select a control to assign it. Physical feedback works without the simulator.",fill=MUTED,font=F(8))

    def _draw_fmc_keypad(self, canvas: tk.Canvas, width: int, height: int) -> None:
        device = self._selected_device
        label = "PFP3N" if device == "pfp3n_bb35" else "MCDU32"
        mirror = self._device_mirror(device)

        detected = self._detected.get(device)
        state_record = self._device_states.get(device, {})
        if not isinstance(state_record, dict):
            state_record = {}
        service_state = str(state_record.get("state") or "").strip().lower()

        # MUSLIMSIM_BB36_COMPLETE_LIFECYCLE_V2_STUDIO
        offline_states = {
            "pfp3n_bb35": {
                "disconnected",
                "offline",
                "waiting-for-pfp3n",
                "reconnecting",
                "stopped",
            },
            "mcdu32_bb36": {
                "disconnected",
                "offline",
                "waiting-for-bb36",
                "reconnecting",
                "stopped",
            },
        }
        physical_panel_offline = bool(
            device in offline_states
            and (
                detected is None
                or (
                    detected.get("source") == "bridge"
                    and service_state in offline_states[device]
                )
            )
        )

        if physical_panel_offline:
            # Never let stale simulator telemetry masquerade as a disconnected
            # physical screen.
            if device == "pfp3n_bb35":
                offline_lines = [
                    "PFP3N  OFFLINE",
                    "",
                    "Physical WINCTRL 3N PFP CAPTAIN is disconnected.",
                    "Waiting for USB 4098:BB35...",
                ]
            else:
                offline_lines = [
                    "MCDU32  OFFLINE",
                    "",
                    "Physical WINCTRL 32 MCDU CAPTAIN is disconnected.",
                    "Waiting for USB 4098:BB36...",
                ]
            mirror = {
                "state": "offline",
                "lines": offline_lines,
            }

        controls = self._visual_controls()
        panel_left, panel_right = 24, width - 24
        canvas.create_round_rect(panel_left, 25, panel_right, height - 20, radius=16, fill="#151a25", outline="#4d5a6e", width=2)
        side = self._cockpit_sides.get(device, CAPTAIN_SIDE)
        panel_state_label = (
            "OFFLINE"
            if physical_panel_offline
            else "LIVE SCREEN AND KEYPAD"
        )
        canvas.create_text(
            panel_left + 20,
            48,
            text=f"{label} — {side.upper()} — {panel_state_label}",
            anchor="w",
            fill=INK,
            font=("Segoe UI Semibold", 13),
        )
        original = "Original hardware key roles are active until you change one."
        canvas.create_text(panel_right - 20, 48, text=original, anchor="e", fill=MUTED, font=("Segoe UI", 9))

        screen_left, screen_right = max(175, width * .24), min(width - 175, width * .76)
        screen_top, screen_bottom = 82, min(360, height * .48)
        canvas.create_rectangle(screen_left, screen_top, screen_right, screen_bottom, fill="#06100e", outline="#678178", width=2)
        lines = list(mirror.get("lines") or ())
        if not lines and mirror.get("state") == "pfd":
            pfd = dict(mirror.get("pfd") or {})
            pfd_values = dict(pfd.get("values") or {})
            lines = [
                f"{label}  {str(pfd.get('page') or 'PFD').upper()} LIVE",
                "",
                f" IAS {pfd_values.get('ias', '---')}    HDG {pfd_values.get('heading', '---')}",
                f" ALT {pfd_values.get('altitude', '---')}    VS  {pfd_values.get('vertical_speed', '---')}",
                "",
                "This is the same read-only PFD telemetry sent to the physical screen.",
            ]
        if not lines:
            lines = ["MUSLIMSIM STUDIO", "", "Waiting for the physical display stream…"]
        line_height = max(10, min(16, (screen_bottom - screen_top - 18) / max(1, len(lines))))
        for row, text in enumerate(lines[:14]):
            canvas.create_text(screen_left + 12, screen_top + 12 + row * line_height, text=str(text)[:42], anchor="nw", fill="#b9f7df", font=("Consolas", max(7, int(line_height - 2))))

        # Six LSKs on each side mirror their physical positions beside the display.
        for index in range(6):
            for key_index, x in ((index, screen_left - 62), (index + 6, screen_right + 62)):
                key = f"key_{key_index}"
                info = controls.get(key)
                if info:
                    self._draw_button(canvas, x, screen_top + 28 + index * ((screen_bottom - screen_top - 56) / 5), str(info["label"]), key, width=86)

        remainder = [key for key in sorted(controls, key=lambda item: int(item.partition("_")[2]) if item.partition("_")[2].isdigit() else 999) if key not in {f"key_{index}" for index in range(12)}]
        columns = 9
        rows = max(1, (len(remainder) + columns - 1) // columns)
        gap_y = max(28, min(42, (height - screen_bottom - 38) / rows))
        gap_x = (panel_right - panel_left - 100) / max(1, columns - 1)
        for index, key in enumerate(remainder):
            row, column = divmod(index, columns)
            x = panel_left + 50 + column * gap_x
            y = screen_bottom + 30 + row * gap_y
            self._draw_button(canvas, x, y, str(controls[key]["label"]), key, width=88)

    def _moza_calibration_values(self, device: Optional[str] = None) -> Dict[str, Any]:
        """Read the current profile's complete, capture-derived Moza values."""

        selected = device or self._selected_device
        active = str(self._profile.get("active_profile") or "Default")
        profiles = dict(self._profile.get("profiles") or {})
        profile = dict(profiles.get(active) or {})
        calibration = dict(profile.get("calibration") or {})
        return effective_moza_calibration(selected, dict(calibration.get(selected) or {}))

    def _moza_live_axes(self, device: str) -> tuple[Dict[str, float], bool]:
        """Use bridge-held HID readings without making Tk open the device.

        MUSLIMSIM_MOZA_AB6_CAPTURE_V1: this was hard-wired to ``moza_a210``,
        written when the AB6 had no captured report and so had nothing live to
        show.  On the AB6 page it returned the A210's own fallback with
        ``seen=False``, leaving the AB6 at a dead centre pose whatever the
        physical base did.  The AB6 now has its own capture-proven reader.
        """

        # Fill in whatever this device's stored pose is missing rather than
        # trusting its shape.  The AB6's seed carried only X/Y/Z from its
        # preset days, so the first live report - which publishes all eight
        # axes at once - raised KeyError here and blanked the entire panel.
        stored = self._moza_practice_axes.setdefault(str(device), {})
        for key in MOZA_AXIS_KEYS:
            stored.setdefault(key, .5)
        fallback = dict(stored)
        if self._selected_device != device:
            return fallback, False
        inputs = self._lab.get("inputs")
        device_inputs = dict(inputs.get(device) or {}) if isinstance(inputs, dict) else {}
        seen = False
        for key in MOZA_AXIS_KEYS:
            item = device_inputs.get(key)
            if not isinstance(item, dict) or "value" not in item:
                continue
            fallback[key] = self._axis_fraction(
                self._number(item, "value", fallback.get(key, .5))
            )
            seen = True
        return fallback, seen

    def _moza_a210_live_axes(self) -> tuple[Dict[str, float], bool]:
        """Preserved entry point; the A210 behaves exactly as it did before."""

        return self._moza_live_axes("moza_a210")

    @staticmethod
    def _moza_button_key(number: int) -> str:
        return f"button_{int(number):03d}"

    def _moza_pressed(self, key: str, device: str = "moza_a210") -> bool:
        # MUSLIMSIM_MOZA_AB6_CAPTURE_V1: the default preserves the A210.
        return self._device_input_value(str(device), key, 0.0) > .5

    def _draw_moza_push(self, canvas: tk.Canvas, x: float, y: float, label: str, number: int, *, width: int = 44, height: int = 34, enabled: bool = True, device: str = "moza_a210") -> None:
        """A physical-looking square contact, labelled only - no raw HID number."""

        key = self._moza_button_key(number)
        active = self._moza_pressed(key, device) if enabled else False
        if enabled:
            fill = "#10615b" if active else self._control_fill(key, "#1a2a40")
            outline = ACCENT if active else self._control_color(key)
        else:
            fill, outline = "#18243a", "#44546c"
        face = canvas.create_round_rect(
            x - width / 2, y - height / 2, x + width / 2, y + height / 2,
            radius=6, fill=fill, outline=outline, width=3 if active else 2,
        )
        cap = canvas.create_round_rect(
            x - width / 2 + 5, y - height / 2 + 5, x + width / 2 - 5, y + height / 2 - 5,
            radius=4, fill="#0d1728", outline="#627795",
        )
        text = canvas.create_text(
            x, y, text=label, fill="#eafffa" if active else "#d8e4f3",
            font=("Segoe UI", 7, "bold"), width=width - 8, justify="center",
        )
        if enabled:
            for item in (face, cap, text):
                self._tag(canvas, item, key)
        else:
            canvas.create_text(x, y + height / 2 + 13, text="CAPTURE", fill=MUTED, font=("Consolas", 6, "bold"))

    def _draw_moza_rotary_pair(self, canvas: tk.Canvas, x: float, y: float, label: str, first: int, second: int, *, enabled: bool = True) -> None:
        """Draw a labelled two-contact rotary without guessing its direction map."""

        canvas.create_text(
            x, y - 39, text=label, fill="#dce8f7", font=("Segoe UI", 7, "bold"),
            width=78, justify="center",
        )
        canvas.create_oval(x - 19, y - 19, x + 19, y + 19, fill="#0b1424", outline="#617894", width=2)
        canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill="#334a65", outline="#91a9c8")
        for offset, number, arrow in ((-27, first, "‹"), (27, second, "›")):
            key = self._moza_button_key(number)
            active = self._moza_pressed(key) if enabled else False
            control = canvas.create_oval(
                x + offset - 10, y - 10, x + offset + 10, y + 10,
                fill="#10615b" if active else "#1b2b43",
                outline=ACCENT if active else (self._control_color(key) if enabled else "#4d5b70"), width=2,
            )
            glyph = canvas.create_text(x + offset, y - 1, text=arrow, fill="#edfff9" if active else "#cdd9eb", font=("Segoe UI", 12, "bold"))
            if enabled:
                self._tag(canvas, control, key)
                self._tag(canvas, glyph, key)
        canvas.create_text(x, y + 34, text="ROTATE", fill=MUTED, font=("Segoe UI", 6, "bold"))

    def _draw_moza_rocker(self, canvas: tk.Canvas, x: float, y: float, label: str, numbers: tuple[int, int, int], *, enabled: bool = True) -> None:
        """Three-position hardware rocker used on the A210 base reference."""

        canvas.create_text(x, y - 52, text=label, fill="#dce8f7", font=("Segoe UI", 7, "bold"), width=78, justify="center")
        canvas.create_round_rect(x - 22, y - 37, x + 22, y + 37, radius=8, fill="#0a1424", outline="#5a708e", width=2)
        positions = ((-20, "UP"), (0, "MID"), (20, "DOWN"))
        for (offset, caption), number in zip(positions, numbers):
            key = self._moza_button_key(number)
            active = self._moza_pressed(key) if enabled else False
            item = canvas.create_round_rect(
                x - 15, y + offset - 7, x + 15, y + offset + 7, radius=4,
                fill="#10615b" if active else "#263951",
                outline=ACCENT if active else (self._control_color(key) if enabled else "#4d5b70"), width=2,
            )
            text = canvas.create_text(x, y + offset, text=caption, fill="#edfff9" if active else "#c9d6e8", font=("Segoe UI", 5, "bold"))
            if enabled:
                self._tag(canvas, item, key)
                self._tag(canvas, text, key)

    def _draw_moza_dpad(self, canvas: tk.Canvas, x: float, y: float, label: str, numbers: tuple[int, int, int, int, int], *, enabled: bool = True) -> None:
        """Five-way physical pad; each contact stays individually remappable."""

        canvas.create_text(x, y - 49, text=label, fill="#dce8f7", font=("Segoe UI", 7, "bold"), width=110, justify="center")
        positions = ((0, -22, "▲"), (-22, 0, "◀"), (0, 0, "●"), (22, 0, "▶"), (0, 22, "▼"))
        for (dx, dy, glyph), number in zip(positions, numbers):
            key = self._moza_button_key(number)
            active = self._moza_pressed(key) if enabled else False
            item = canvas.create_oval(
                x + dx - 10, y + dy - 10, x + dx + 10, y + dy + 10,
                fill="#10615b" if active else "#20334d",
                outline=ACCENT if active else (self._control_color(key) if enabled else "#4d5b70"), width=2,
            )
            text = canvas.create_text(x + dx, y + dy - 1, text=glyph, fill="#edfff9" if active else "#d5e1f1", font=("Segoe UI", 8, "bold"))
            if enabled:
                self._tag(canvas, item, key)
                self._tag(canvas, text, key)

    def _draw_moza_layout_nav(self, canvas: tk.Canvas, left: float, y: float, pages: tuple[tuple[str, str], ...], selected: str) -> None:
        """A stable page rail keeps detailed faceplates apart instead of shrinking them."""

        x = left
        for page, caption in pages:
            active = page == selected
            width = max(96, len(caption) * 7 + 26)
            key = f"moza_view:{page}"
            pill = canvas.create_round_rect(
                x, y - 13, x + width, y + 13, radius=12,
                fill="#175b57" if active else "#1a2941",
                outline=ACCENT if active else "#506987", width=2,
            )
            text = canvas.create_text(x + width / 2, y, text=caption, fill="#effff9" if active else "#c6d5e9", font=("Segoe UI", 7, "bold"), width=width - 12)
            self._tag(canvas, pill, key)
            self._tag(canvas, text, key)
            x += width + 10

    def _draw_moza_a210_base_layout(self, canvas: tk.Canvas, left: float, top: float, right: float, bottom: float) -> None:
        """Use the owner-supplied AY210 visual map for the captured A210 contacts."""

        canvas.create_round_rect(left + 18, top + 5, right - 18, bottom - 8, radius=18, fill="#111d31", outline="#516783", width=2)
        canvas.create_text((left + right) / 2, top + 25, text="A210 BASE — SWITCHES, ROTARIES AND TRIM", fill="#f2d7a1", font=("Segoe UI", 9, "bold"), width=right - left - 70)
        canvas.create_text((left + right) / 2, top + 42, text="Live teal shows the exact captured contact.", fill=MUTED, font=("Segoe UI", 7), width=right - left - 70)
        xs = (left + 104, left + 218, left + 332)
        for x, label, first, second in zip(xs, ("NAV", "BEACON", "STROBE"), (65, 67, 69), (64, 66, 68)):
            self._draw_moza_rotary_pair(canvas, x, top + 110, label, first, second)
        for x, label, first, second in zip(xs, ("BAT", "FUEL PUMP", "PITOT"), (71, 73, 75), (70, 72, 74)):
            self._draw_moza_rotary_pair(canvas, x, top + 246, label, first, second)
        canvas.create_text(left + 450, top + 65, text="AUXILIARY\nPUSH SWITCHES", fill="#dce8f7", font=("Segoe UI", 7, "bold"), justify="center", width=84)
        for y, label, number in ((top + 112, "AUX 1", 49), (top + 160, "AUX 2", 50), (top + 208, "AUX 3", 51), (top + 256, "AUX 4", 52)):
            self._draw_moza_push(canvas, left + 450, y, label, number, width=58, height=32)
        self._draw_moza_rocker(canvas, left + 510, top + 134, "TRIM\nROCKER", (60, 59, 58))
        self._draw_moza_dpad(canvas, left + 450, top + 333, "HAT / TRIM", (55, 54, 57, 56, 53))
        self._draw_moza_push(canvas, left + 518, top + 310, "AUX 5", 62, width=46, height=30)
        self._draw_moza_push(canvas, left + 518, top + 359, "AUX 6", 63, width=46, height=30)
        self._draw_moza_push(canvas, left + 518, top + 408, "AUX 7", 77, width=46, height=30)
        self._draw_moza_push(canvas, left + 450, top + 418, "PUSH", 76, width=58, height=30)

    # MUSLIMSIM_MOZA_YOKE_SILHOUETTE_V2
    #
    # V1 fixed the shape (a flat sliding bar became a swept "gull-wing" yoke)
    # but got two things wrong that only showed up once the owner actually
    # watched it move: the grips were mounted below the hub - upside down
    # against the real MFY yoke's own product photography, where the grips
    # are above the hub and the hub sits low, over the column - and pitch was
    # drawn as the hub itself sliding up and down on a visible connecting
    # rod. The owner's fix is more correct than V1 was: the axle is a single
    # fixed point, nothing about its position ever moves, and every axis is
    # expressed as a transform of the yoke *around* that fixed point - roll
    # rotates it up to 90 degrees either way, pitch scales it larger or
    # smaller. No rod, because a fixed axle does not need one drawn.
    #
    # Every point below is defined once in a LOCAL frame - the axle at the
    # origin, grips above (negative y), hub below (positive y), shape
    # unrotated - then carried through one shared rigid-body transform so the
    # horns, the grips, the hub badge and every button mounted on them move
    # together as one object, the way they are actually bolted together.
    MOZA_YOKE_MAX_ROLL_DEGREES = 90.0
    # Push = zoom in (larger), pull = zoom out (smaller), per the owner's own
    # description of the feel they want. This assumes a higher raw axis_y
    # reading is "push" - that direction was not re-verified against a fresh
    # capture for this change, so it is the one thing worth confirming
    # against the real yoke. If push and pull read backwards, this is the
    # only line to change: flip the "+" to a "-" where scale_target is built.
    MOZA_YOKE_PITCH_SCALE_RANGE = 0.16
    # "move the entire yoke down about 3 cm" asked for ~113 px at a common
    # 96 DPI desktop scaling. That does not fit: at full zoom-in (push,
    # scale 1.16), the grip capsule alone - unchanged, existing geometry,
    # nothing to do with this request - already needs 227 px of clearance
    # below the pivot, and shifting the full 113 px down would leave only
    # 207 px there. The cap is about 77 px (roughly 2 cm) before that
    # capsule starts drawing off the bottom of its own panel at full zoom;
    # checked directly by computing every drawn element's true worst-case
    # reach from the pivot, not estimated. Getting the full 3 cm would mean
    # shrinking geometry nobody asked to change, so this is the largest
    # shift that still keeps everything on-panel at every roll and pitch
    # extreme (see the faceplate test's panel-fit sweep).
    MOZA_YOKE_VERTICAL_SHIFT = 70.0

    @staticmethod
    def _moza_yoke_point(local_x: float, local_y: float, cx: float, cy: float, roll_degrees: float, scale: float) -> tuple[float, float]:
        """One local point, carried through the yoke's rigid-body transform."""

        import math

        radians = math.radians(roll_degrees)
        cos_a, sin_a = math.cos(radians), math.sin(radians)
        rotated_x = local_x * cos_a - local_y * sin_a
        rotated_y = local_x * sin_a + local_y * cos_a
        return cx + rotated_x * scale, cy + rotated_y * scale

    def _moza_yoke_capsule(self, canvas: tk.Canvas, local_cx: float, local_cy: float, half_w: float, half_h: float, *, cx: float, cy: float, roll_degrees: float, scale: float, **kwargs: Any) -> int:
        """A grip or hub, drawn as a rotated capsule so it turns as one piece.

        Four corners of the unrotated rectangle, each carried through the same
        transform every other point on the yoke uses, then joined with
        ``smooth=True`` - Tk's spline through four points alone gives exactly
        the rounded, pill-like corners a real yoke's moulded grip has, with no
        separate radius parameter to keep in step with the rotation.
        """

        corners = (
            (local_cx - half_w, local_cy - half_h), (local_cx + half_w, local_cy - half_h),
            (local_cx + half_w, local_cy + half_h), (local_cx - half_w, local_cy + half_h),
        )
        points: list[float] = []
        for lx, ly in corners:
            px, py = self._moza_yoke_point(lx, ly, cx, cy, roll_degrees, scale)
            points.extend((px, py))
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _moza_yoke_request_frame(self) -> None:
        """Keep the yoke animating at ~60 fps between real telemetry replies.

        Physical status only arrives ten times a second - fine for a switch,
        not for something the owner watches turn continuously. Reusing the
        PDC panel's own eased-animation store rather than a second one: it is
        a plain key/value smoother with no PDC-specific behaviour in it, and
        every key here is namespaced ``moza_a210:...`` so it cannot collide
        with a PDC key.
        """

        if getattr(self, "_moza_yoke_frame_pending", False):
            return
        self._moza_yoke_frame_pending = True

        def _frame() -> None:
            self._moza_yoke_frame_pending = False
            if self._selected_device == "moza_a210" and self._moza_layout_page.get("moza_a210") == "yoke":
                self._draw_faceplate()

        try:
            self.after(16, _frame)
        except Exception:
            self._moza_yoke_frame_pending = False

    def _moza_yoke_ease(self, key: str, target: float) -> float:
        eased = self._pdc_flat_animate(f"moza_a210:{key}", target, 0.30)
        if abs(eased - target) > 1e-6:
            self._moza_yoke_request_frame()
        return eased

    # Every numbered contact the flat layout used, drawn clean: a live dot or
    # button that lights up when pressed and nothing else printed on it. A
    # raw HID contact number is not a function, and printing it as though it
    # were one is what the owner is objecting to - the number is still there
    # for calibration, on the tag Practice mode already uses to pick a
    # contact, it is simply not written across the hardware's own face.

    def _draw_moza_yoke_dot(self, canvas: tk.Canvas, x: float, y: float, number: int, *, radius: float = 9.0, scale: float = 1.0) -> None:
        # x and y already carry the scale - the position of a point away from
        # the pivot naturally grows or shrinks with it. The radius does not:
        # it is applied in absolute screen pixels after that transform, so it
        # has to be scaled here explicitly, or a "bigger" yoke would still be
        # drawn with identically-sized buttons on it.
        radius *= scale
        key = self._moza_button_key(number)
        active = self._moza_pressed(key)
        item = canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="#10615b" if active else "#1b2b43",
            outline=ACCENT if active else self._control_color(key),
            width=3 if active else 2,
        )
        self._tag(canvas, item, key)

    def _draw_moza_yoke_ring(self, canvas: tk.Canvas, x: float, y: float, label: str, numbers: tuple[int, ...], *, label_dx: float = 0.0, label_dy: float = -34.0, roll_degrees: float = 0.0, scale: float = 1.0, housing: str = "circle") -> None:
        """A cluster of genuinely distinct contacts, drawn as a ring of plain dots.

        MUSLIMSIM_MOZA_YOKE_CAPTURE_V1: how many dots to draw, and which HID
        numbers light each one, both come from ``yoke.pcapng`` - each number
        here was pressed on its own and produced exactly one clean edge, with
        no other number changing at the same instant, which is what tells a
        genuine multi-contact cluster (a hat, a selector ring) apart from a
        single switch reported on more than one bit (see
        ``_draw_moza_yoke_rocker`` for that case). Evenly spaced starting
        from the top and going clockwise - the real layout of eight detents
        around a ring is not something a HID capture can reveal, so this is
        a legible arrangement, not a claim about which physical position is
        which number.

        The dots are mounted on the grip, so they turn with it: their offsets
        from the ring's own centre are rotated by the same roll angle as
        everything else, not left screen-locked while the centre they sit on
        moves out from under them. The caption's offset is given explicitly
        by the caller rather than always sitting above - a cluster at the
        edge of the yoke reads better with its label to the outer side than
        floating over the horn next to it.
        """

        import math

        canvas.create_text(x + label_dx, y + label_dy, text=label, fill="#a9bbd3", font=("Segoe UI", 6, "bold"), width=90, justify="center")
        if housing == "rounded_rect":
            # The four corners of an unrotated square, each carried through
            # the same rigid-body transform every other point on the yoke
            # uses - exactly how _moza_yoke_capsule builds a grip or the hub,
            # reused here because a rounded-rectangle pad is the same shape.
            half = 22.0
            corners = ((-half, -half), (half, -half), (half, half), (-half, half))
            points: list[float] = []
            for lx, ly in corners:
                px, py = self._moza_yoke_point(lx, ly, x, y, roll_degrees, scale)
                points.extend((px, py))
            canvas.create_polygon(points, smooth=True, fill="#0b1424", outline="#43597a", width=2)
        else:
            ring_radius = 22.0 * scale
            canvas.create_oval(x - ring_radius, y - ring_radius, x + ring_radius, y + ring_radius, fill="#0b1424", outline="#43597a", width=2)
        count = len(numbers)
        spread = 15.0
        for index, number in enumerate(numbers):
            angle = math.radians(-90.0 + 360.0 * index / count)
            dx, dy = spread * math.cos(angle), spread * math.sin(angle)
            px, py = self._moza_yoke_point(dx, dy, x, y, roll_degrees, scale)
            self._draw_moza_yoke_dot(canvas, px, py, number, radius=6.5, scale=scale)

    def _draw_moza_yoke_rocker(self, canvas: tk.Canvas, x: float, y: float, numbers: tuple[int, ...], *, radius: float = 20.0, scale: float = 1.0) -> None:
        """One physical switch that reports on more than one HID contact.

        MUSLIMSIM_MOZA_YOKE_CAPTURE_V1: ``yoke.pcapng`` caught the right-hand
        one of these being pressed - contacts 24 and 25 asserted together for
        the whole ~0.9 s of the press, across several hundred consecutive
        reports, and released together - a single mechanism read on two
        bits, not two buttons that happened to be tapped at once. That is
        exactly "one button you can tap from multiple angles": the angle
        decides which bit (or bits) it reports, but there is one switch
        under the finger, so it is drawn as one circle, lit if any of its
        bits are active, rather than as a ring of separate contacts.

        ``numbers`` may be empty - the left-hand rocker was never pressed in
        the capture, so its own bits are not proven. Drawn in a dashed,
        inert style rather than guessing a number for it: a wrong guess would
        light up on a press that has nothing to do with it, which is worse
        than admitting it is not wired up yet.
        """

        radius *= scale
        if not numbers:
            canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill="#141f30", outline="#4a5a72", width=2, dash=(4, 3),
            )
            return
        active = any(self._moza_pressed(self._moza_button_key(number)) for number in numbers)
        colors = [self._control_color(self._moza_button_key(number)) for number in numbers]
        outline = ACCENT if active else (colors[0] if colors else "#617894")
        item = canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="#10615b" if active else "#1b2b43",
            outline=outline, width=3 if active else 2,
        )
        for number in numbers:
            self._tag(canvas, item, self._moza_button_key(number))

    def _draw_moza_yoke_button(self, canvas: tk.Canvas, x: float, y: float, number: int, *, radius: float = 13.0, scale: float = 1.0) -> None:
        """One plain round button - live colour is the only information it carries."""

        radius *= scale

        key = self._moza_button_key(number)
        active = self._moza_pressed(key)
        item = canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="#10615b" if active else self._control_fill(key, "#1a2a40"),
            outline=ACCENT if active else self._control_color(key),
            width=3 if active else 2,
        )
        self._tag(canvas, item, key)

    def _draw_moza_a210_yoke_layout(self, canvas: tk.Canvas, left: float, top: float, right: float, bottom: float, axes: Dict[str, float], live: bool) -> None:
        """Draw the detachable yoke, shaped and moving like the real MFY yoke."""

        canvas.create_round_rect(left + 18, top + 5, right - 18, bottom - 8, radius=18, fill="#111d31", outline="#516783", width=2)
        canvas.create_text((left + right) / 2, top + 24, text="DETACHABLE YOKE — LIVE HID SURFACE", fill="#f2d7a1", font=("Segoe UI", 9, "bold"))
        canvas.create_text((left + right) / 2, top + 41, state="hidden", text="The yoke and base remain one A210 device when fitted or removed.", fill=MUTED, font=("Segoe UI", 7), width=right - left - 62)

        # Native X-Plane axis assignment (--moza-yoke) auto-detects which
        # joystick-axis slot is roll/pitch; this opens the correction dialog
        # for when that detection gets stuck or picks the wrong slot.
        axis_btn = canvas.create_round_rect(
            right - 170, top + 6, right - 26, top + 28, radius=7,
            fill="#28466b", outline="#7085a3", width=1,
        )
        axis_btn_label = canvas.create_text(
            (right - 170 + right - 26) / 2, top + 17,
            text="AXIS ASSIGNMENT", fill="#dbe7fb", font=("Segoe UI Semibold", 8),
        )
        for item in (axis_btn, axis_btn_label):
            canvas.tag_bind(item, "<Button-1>", lambda _e: self._open_moza_axis_assignment_dialog())
            canvas.tag_bind(item, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(item, "<Leave>", lambda _e: canvas.configure(cursor=""))

        # The axle: a single fixed point, centred in the available drawing
        # area. Nothing about its position ever changes - only the shape
        # drawn around it rotates and scales - which is the owner's own
        # description of how this should behave and also the simplest way to
        # guarantee the whole yoke stays on the visible panel at any angle:
        # every point below is proven to keep a constant distance from this
        # one fixed centre (see the faceplate test), so keeping that centre
        # comfortably clear of every edge is all the fitting this needs.
        # Shifted down from panel-centre by request: "move the entire yoke
        # down about 3 cm" (MOZA_YOKE_VERTICAL_SHIFT, defined with the
        # other tunable constants above).
        cx = (left + right) / 2
        cy = (top + bottom) / 2 + self.MOZA_YOKE_VERTICAL_SHIFT

        roll_target = (axes.get("axis_x", .5) - .5) * 2.0 * self.MOZA_YOKE_MAX_ROLL_DEGREES
        scale_target = 1.0 + (axes.get("axis_y", .5) - .5) * 2.0 * self.MOZA_YOKE_PITCH_SCALE_RANGE
        roll_degrees = self._moza_yoke_ease("roll", roll_target)
        scale = self._moza_yoke_ease("scale", scale_target)

        def moza_point(local_x: float, local_y: float) -> tuple[float, float]:
            return self._moza_yoke_point(local_x, local_y, cx, cy, roll_degrees, scale)

        def moza_capsule(local_cx: float, local_cy: float, half_w: float, half_h: float, **kwargs: Any) -> int:
            return self._moza_yoke_capsule(canvas, local_cx, local_cy, half_w, half_h, cx=cx, cy=cy, roll_degrees=roll_degrees, scale=scale, **kwargs)

        # Two horns, swept up and outward from the hub to each grip, matching
        # the real yoke's own photography: grips above, hub below. Tk has no
        # native curve primitive; a smoothed line through the same waypoints
        # the shape was proven against gives the same sweep.
        for side in (-1.0, 1.0):
            local_waypoints = (
                (side * 18.0, 5.0), (side * 44.0, -7.0), (side * 70.0, -27.0),
                (side * 94.0, -52.0), (side * 112.0, -80.0),
            )
            outline_points: list[float] = []
            for lx, ly in local_waypoints:
                px, py = moza_point(lx, ly)
                outline_points.extend((px, py))
            canvas.create_line(outline_points, fill="#1b2c44", width=34, capstyle="round", joinstyle="round", smooth=True)
            canvas.create_line(outline_points, fill="#0a1424", width=20, capstyle="round", joinstyle="round", smooth=True)

        # The hub badge, low, where the column would attach - rotating with
        # the rest of the assembly. Tk 8.6 can rotate text directly, so the
        # nameplate turns the way a real badge mounted to a turning wheel
        # would.
        moza_capsule(0.0, 4.0, 37.0, 32.0, fill="#1a2a40", outline="#7085a3", width=3)
        label_x, label_y = moza_point(0.0, 4.0)
        canvas.create_text(label_x, label_y, text="MOZA", fill="#f2d7a1", font=("Segoe UI Semibold", 9, "bold"), angle=-roll_degrees)

        # Each grip: the capsule the pilot's hand actually wraps around.
        #
        # MUSLIMSIM_MOZA_YOKE_CAPTURE_V1: every number below was proven, or
        # proven absent, against ``yoke.pcapng`` - the previous five-a-side
        # guess included three numbers (13, 18, and the whole of the old
        # "LEFT UPPER" set) that never moved once in 91.5 seconds of the
        # owner actually working every control, and two more (31, 32) that
        # read as permanently pressed for the entire capture, which is a
        # firmware idle pattern, not a button. The right-hand rocker is
        # proven live: contacts 24 and 25 assert together for the whole
        # press. The left-hand rocker was never pressed in this capture, so
        # it is drawn - deliberately - with no numbers bound to it yet; see
        # ``_draw_moza_yoke_rocker``.
        grip_specs = (
            (-1.0, (), "LEFT GRIP", (19, 20, 21, 22)),
            (1.0, (24, 25), "RIGHT GRIP", (14, 15, 16, 17)),
        )
        for side, upper_numbers, grip_label, grip_numbers in grip_specs:
            grip_local_x = side * 112.0
            moza_capsule(grip_local_x, -80.0, 17.0, 56.0, fill="#1b2c44", outline="#7085a3", width=3)
            upper_x, upper_y = moza_point(grip_local_x, -108.0)
            self._draw_moza_yoke_rocker(canvas, upper_x, upper_y, upper_numbers, scale=scale)
            # Moved above the rocker (-108) with clear separation, and
            # reshaped from a round ring to a rounded rectangle, per direct
            # request. Kept close enough to fit alongside the 3 cm downward
            # shift below without drawing off the panel at full zoom - see
            # MOZA_YOKE_VERTICAL_SHIFT for the arithmetic. Still carried
            # through the same rotating transform as every other contact -
            # these are real contacts mounted on the grip, not panel
            # furniture, so they turn with the wheel the way select and the
            # rocker already do.
            pad_x, pad_y = moza_point(grip_local_x, -128.0)
            # "on the side": the caption sits outward from the yoke's own
            # centreline - further left for the left grip, further right for
            # the right - rather than floating above the cluster and reading
            # as attached to whichever horn happens to pass nearby.
            self._draw_moza_yoke_ring(
                canvas, pad_x, pad_y, grip_label, grip_numbers,
                label_dx=side * 44.0, label_dy=0.0, housing="rounded_rect",
                roll_degrees=roll_degrees, scale=scale,
            )

        # Select, split across the two sides where the axis sliders used to
        # be: "the select button they should be located on the side in the
        # place of those two slides in the corner". Eight distinct contacts,
        # not the five the old guess drew - the owner's own diagnosis was
        # "select buttons missing too many", and the capture backs it up
        # exactly: 5 through 12 each produced one clean edge on its own, in
        # one continuous run, with nothing else moving alongside it.
        #
        # Kept part of the yoke's own rotation (computed through moza_point,
        # like everything else) rather than pinned to the panel the way the
        # sliders were: select is mounted on the crossbar, so it turns with
        # the wheel when the owner rolls it, the same as every other contact
        # here - a raw panel position would have quietly undone that.
        select_groups = ((-1.0, (5, 6, 7, 8)), (1.0, (9, 10, 11, 12)))
        for side, numbers in select_groups:
            select_x, select_y = moza_point(side * 172.0, 0.0)
            self._draw_moza_yoke_ring(
                canvas, select_x, select_y, "SELECT", numbers,
                label_dx=side * 40.0, label_dy=0.0,
                roll_degrees=roll_degrees, scale=scale,
            )

        # The four corner contacts near where each horn meets the hub - the
        # one cluster the capture confirmed unchanged: 1, 2, 3 and 4 each
        # produced one clean edge, individually, in their own test pass.
        # Moved further from the hub than before and given more room between
        # them, since the owner reported these as not registering at all -
        # not proven wrong by the capture, but worth being easy to hit and
        # to tell apart rather than crowding the hub's own edge.
        for local_x, local_y, number in (
            (-52.0, -14.0, 3), (52.0, -14.0, 1),
            (-84.0, -40.0, 2), (84.0, -40.0, 4),
        ):
            px, py = moza_point(local_x, local_y)
            self._draw_moza_yoke_button(canvas, px, py, number, radius=15.0, scale=scale)

        # MUSLIMSIM_MOZA_YOKE_CAPTURE_V1: the two sliders that used to sit
        # here (axis_z, axis_dial) are gone, not merely relocated. Checked
        # against the same capture before removing either: axis_z stayed
        # pinned at the exact value 32767 for all 76,345 reports - the same
        # idle pattern already documented for the AB6's Z axis, now confirmed
        # on the A210 too, and the reason it never looked like it was giving
        # feedback is that it genuinely was not. axis_dial is not idle -
        # it swept its full 0..65535 range in this same capture - so it was
        # a real, working control being removed to make room for select, not
        # a second dead one. If that axis is wanted back, it belongs
        # somewhere its own on this panel; it was never proven broken.

    def _draw_moza_max3_layout(self, canvas: tk.Canvas, left: float, top: float, right: float, bottom: float, device: str = "moza_a210") -> None:
        """Visual MAX3 grip reference, reading the base it is mounted on.

        MUSLIMSIM_MOZA_AB6_CAPTURE_V1: this read the A210 contact pool while
        being drawn on the AB6 page, because at the time the AB6 had no
        captured report to read.  The AB6 capture then observed contacts 1
        and 10 closing - this grip's own TRIGGER and TOP - so its presses
        arrive on the base it is fitted to, and that is what it now shows.
        """

        canvas.create_round_rect(left + 18, top + 5, right - 18, bottom - 8, radius=18, fill="#111d31", outline="#516783", width=2)
        canvas.create_text((left + right) / 2, top + 24, text="MAX3 GRIP — LIVE HID", fill="#f2d7a1", font=("Segoe UI", 9, "bold"))
        canvas.create_text((left + right) / 2, top + 42, state="hidden", text="Rendered from your MAX3 layout.  Its contacts arrive on the base it is mounted on; no separate MAX3 USB protocol is assumed.", fill=MUTED, font=("Segoe UI", 7), width=right - left - 64)
        cx = (left + right) / 2
        canvas.create_round_rect(cx - 88, top + 100, cx + 88, bottom - 56, radius=36, fill="#1b2d45", outline="#647b99", width=3)
        canvas.create_oval(cx - 39, top + 119, cx + 39, top + 197, fill="#142237", outline="#8298b5", width=3)
        canvas.create_line(cx - 35, top + 199, cx - 82, bottom - 104, fill="#536a87", width=14)
        canvas.create_line(cx + 35, top + 199, cx + 82, bottom - 104, fill="#536a87", width=14)
        self._draw_moza_push(canvas, cx - 94, top + 277, "TRIGGER", 1, width=62, height=32, device=device)
        self._draw_moza_push(canvas, cx + 94, top + 145, "TOP", 10, width=54, height=32, device=device)
        canvas.create_text(cx, bottom - 34, state="hidden", text="Only B001 and B010 are placed from this reference.  Other MAX3 contacts appear live when you press them.", fill="#c3d1e4", font=("Segoe UI", 7), width=right - left - 76)

    def _draw_moza_ab6_layout(self, canvas: tk.Canvas, left: float, top: float, right: float, bottom: float, axes: Dict[str, float]) -> None:
        """Draw the AB6 from its own capture-proven live HID report.

        MUSLIMSIM_MOZA_AB6_CAPTURE_V1: this used to be a reference drawing
        that said so - the contacts were drawn ``enabled=False`` and the
        caption asked for a capture that had not happened.  It has now
        happened, the base streams report 01, and the panel shows what the
        hardware is really doing.
        """

        canvas.create_round_rect(left + 18, top + 5, right - 18, bottom - 8, radius=18, fill="#111d31", outline="#516783", width=2)
        canvas.create_text((left + right) / 2, top + 24, text="AB6 BASE — LIVE HID", fill="#f2d7a1", font=("Segoe UI", 9, "bold"))
        canvas.create_text((left + right) / 2, top + 42, state="hidden", text="Captured from the base: report 01, eight axes, hat and 128 contacts.  The base prints no button names, so assign functions to the numbered contacts here.", fill=MUTED, font=("Segoe UI", 7), width=right - left - 64)
        cx = (left + right) / 2
        console_top, console_bottom = top + 72, bottom - 56
        canvas.create_round_rect(cx - 116, console_top, cx + 116, console_bottom, radius=24, fill="#172941", outline="#607895", width=3)
        stick_x_fraction = self._axis_ease("moza_ab6", "axis_x", float(axes.get("axis_x", .5)))
        stick_y_fraction = self._axis_ease("moza_ab6", "axis_y", float(axes.get("axis_y", .5)))
        stick_x = cx + (stick_x_fraction - .5) * 86
        stick_y = console_top + 136 + (stick_y_fraction - .5) * 70
        canvas.create_oval(cx - 62, console_top + 56, cx + 62, console_top + 180, fill="#0c1728", outline="#617997", width=3)
        arm = canvas.create_line(cx, console_top + 145, stick_x, stick_y, fill="#d9e5f6", width=9)
        cap = canvas.create_oval(stick_x - 17, stick_y - 17, stick_x + 17, stick_y + 17, fill="#415a77", outline=BLUE, width=3)
        self._tag(canvas, arm, "axis_y")
        self._tag(canvas, cap, "axis_x")
        # Observed closing during the capture, matching the reference
        # drawing's own numbering, so they read live rather than dead.
        for x, numbers in ((cx - 93, (49, 50, 51, 52)), (cx + 93, (53, 54, 55, 56))):
            for index, number in enumerate(numbers):
                self._draw_moza_push(
                    canvas, x, console_top + 43 + index * 45, "", number,
                    width=31, height=29, device="moza_ab6",
                )
        # SLIDER and DIAL each swept the full 0..65535 range during the
        # capture, so they are axes.  They were drawn as three guessed
        # contacts each - exactly the invention the capture removes.
        for x, caption, key in ((cx - 165, "SLIDER", "axis_slider"), (cx + 165, "DIAL", "axis_dial")):
            fraction = self._axis_ease("moza_ab6", key, max(0.0, min(1.0, float(axes.get(key, .5)))))
            track_top, track_bottom = console_top + 90, console_bottom - 46
            canvas.create_text(x, console_top + 72, text=caption, fill="#dce8f7", font=("Segoe UI", 7, "bold"))
            canvas.create_line(x, track_top, x, track_bottom, fill="#2c4258", width=7)
            marker = track_bottom - (track_bottom - track_top) * fraction
            canvas.create_line(x, marker, x, track_bottom, fill="#4fd1c5", width=7)
            knob = canvas.create_oval(x - 9, marker - 9, x + 9, marker + 9, fill="#415a77", outline=BLUE, width=3)
            self._tag(canvas, knob, key)
            canvas.create_text(
                x + (-27 if x < cx else 27), marker,
                text=f"{fraction * 100:.0f}%", fill="#a9bbd3",
                font=("Consolas", 6, "bold"),
            )
        canvas.create_text(cx, bottom - 30, state="hidden", text="Z, Rx, Ry and Rz are declared by the report but stayed idle through a full-travel exercise.  No force-feedback output protocol exists, so nothing is ever sent to this base.", fill="#c3d1e4", font=("Segoe UI", 7), width=right - left - 76)

    def _draw_moza_hat(self, canvas: tk.Canvas, x: float, y: float, device: str = "moza_a210") -> None:
        """Render the capture-proven 8-way HID hat with a visible detent."""

        value = int(round(self._device_input_value(str(device), "hat", 8.0)))
        active = value if 0 <= value <= 7 else None
        canvas.create_text(x, y - 37, text="HAT SWITCH", fill=INK, font=("Segoe UI Semibold", 8, "bold"))
        canvas.create_oval(x - 27, y - 27, x + 27, y + 27, fill="#07101c", outline="#52657d", width=2)
        points = ((0, -18), (13, -13), (18, 0), (13, 13), (0, 18), (-13, 13), (-18, 0), (-13, -13))
        for index, (dx, dy) in enumerate(points):
            selected = active == index
            dot = canvas.create_oval(x + dx - 5, y + dy - 5, x + dx + 5, y + dy + 5, fill=ACCENT if selected else "#344864", outline=ACCENT if selected else "#7893b7")
            self._tag(canvas, dot, "hat")
        core = canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill="#1c2a43", outline=self._control_color("hat"), width=2)
        self._tag(canvas, core, "hat")
        canvas.create_text(x, y + 37, text="LIVE" if active is not None else "CENTRE", fill="#b9f7df", font=("Consolas", 7, "bold"))

    def _draw_moza_setting(self, canvas: tk.Canvas, x: float, y: float, width: float, label: str, key: str, value: Any) -> None:
        """A compact setting card with its label and value on separate lines."""

        is_toggle = isinstance(value, bool)
        canvas.create_round_rect(x, y, x + width, y + 41, radius=7, fill="#18263b", outline="#445a76", width=1)
        canvas.create_text(
            x + width / 2, y + 9, text=label, fill="#d9e5f6", font=("Segoe UI Semibold", 6, "bold"),
            width=max(42, width - 10), justify="center",
        )
        if is_toggle:
            active = bool(value)
            fill, outline = ("#145c5a", ACCENT) if active else ("#202c40", "#5c6b82")
            button = canvas.create_round_rect(x + width / 2 - 24, y + 19, x + width / 2 + 24, y + 36, radius=9, fill=fill, outline=outline, width=2)
            text = canvas.create_text(x + width / 2, y + 27, text="ON" if active else "OFF", fill="#eafffa" if active else MUTED, font=("Segoe UI", 6, "bold"))
            self._tag(canvas, button, f"moza_toggle:{key}")
            self._tag(canvas, text, f"moza_toggle:{key}")
            return
        centre = x + width / 2
        minus = canvas.create_round_rect(centre - 44, y + 19, centre - 26, y + 36, radius=4, fill="#243651", outline="#57749b")
        value_tile = canvas.create_round_rect(centre - 23, y + 19, centre + 23, y + 36, radius=4, fill="#06100e", outline="#5a705f")
        plus = canvas.create_round_rect(centre + 26, y + 19, centre + 44, y + 36, radius=4, fill="#243651", outline="#57749b")
        minus_text = canvas.create_text(centre - 35, y + 27, text="−", fill=INK, font=("Segoe UI", 8, "bold"))
        value_text = canvas.create_text(centre, y + 27, text=f"{int(value):03d}", fill="#b9f7df", font=("Consolas", 7, "bold"))
        plus_text = canvas.create_text(centre + 35, y + 27, text="+", fill=INK, font=("Segoe UI", 8, "bold"))
        for item in (minus, minus_text):
            self._tag(canvas, item, f"moza_adjust:{key}:-10")
        for item in (plus, plus_text):
            self._tag(canvas, item, f"moza_adjust:{key}:10")
        self._tag(canvas, value_tile, f"moza_adjust:{key}:0")
        self._tag(canvas, value_text, f"moza_adjust:{key}:0")

    def _draw_moza_ffb_physics_row(
        self, canvas: tk.Canvas, x: float, y: float, width: float, label: str, field: str, value: int, *, live: bool,
    ) -> None:
        """One full-width physics row: label, a filled progress track (the
        same visual language as MOZA Cockpit's own sliders), -/+ steppers,
        and a live NN% readout. Unlike _draw_moza_setting's cramped 3-column
        tiles, this is real: every click reaches the AY210 FFB engine (see
        _moza_ffb_physics_command()), not just a locally-saved profile."""

        row_height = 30
        canvas.create_text(x, y + row_height / 2, text=label, anchor="w", fill="#d9e5f6", font=("Segoe UI Semibold", 9))
        step_w = 22
        readout_w = 46
        track_right = x + width - (step_w * 2 + readout_w + 16)
        track_left = max(x + 210, track_right - 160)
        track_top, track_bottom = y + row_height / 2 - 7, y + row_height / 2 + 7
        canvas.create_round_rect(track_left, track_top, track_right, track_bottom, radius=7, fill="#0c1524", outline="#3c5170", width=1)
        fraction = max(0.0, min(1.0, value / 100.0))
        fill_color = ACCENT if live else "#5c6b82"
        if fraction > 0.0:
            canvas.create_round_rect(track_left, track_top, track_left + (track_right - track_left) * fraction, track_bottom, radius=7, fill=fill_color, outline="")
        minus_x = track_right + 8
        plus_x = minus_x + step_w + readout_w + 8
        minus = canvas.create_round_rect(minus_x, y + 2, minus_x + step_w, y + row_height - 2, radius=5, fill="#243651", outline="#57749b")
        minus_text = canvas.create_text(minus_x + step_w / 2, y + row_height / 2, text="−", fill=INK, font=("Segoe UI", 9, "bold"))
        readout = canvas.create_text(minus_x + step_w + readout_w / 2, y + row_height / 2, text=f"{value:d}%", fill="#b9f7df" if live else MUTED, font=("Consolas", 9, "bold"))
        plus = canvas.create_round_rect(plus_x, y + 2, plus_x + step_w, y + row_height - 2, radius=5, fill="#243651", outline="#57749b")
        plus_text = canvas.create_text(plus_x + step_w / 2, y + row_height / 2, text="+", fill=INK, font=("Segoe UI", 9, "bold"))
        for item in (minus, minus_text):
            self._tag(canvas, item, f"moza_ffb_adjust:{field}:-5")
        for item in (plus, plus_text):
            self._tag(canvas, item, f"moza_ffb_adjust:{field}:5")
        self._tag(canvas, readout, f"moza_ffb_adjust:{field}:0")

    def _draw_moza_ffb_effect_gain_row(
        self, canvas: tk.Canvas, x: float, y: float, width: float,
        effect_id: str, live_value: Optional[float], gain_percent: int, *, live: bool,
    ) -> None:
        """One compact per-effect row: its id, the profile curve's own live
        computed strength (read-only, informational), and a 0-200% gain
        stepper - set_effect_gain_override() scales that curve's result
        without touching the .mslm file, the same live-tuning idea as
        _draw_moza_ffb_physics_row but for an individual effect's felt
        strength instead of a physics gain parameter."""

        row_height = 22
        mid = y + row_height / 2
        canvas.create_text(x, mid, text=effect_id, anchor="w", fill="#d9e5f6", font=("Consolas", 8, "bold"))
        value_text = f"{live_value:+.2f}" if live_value is not None else "—"
        canvas.create_text(x + 138, mid, text=value_text, anchor="w", fill="#8fa0ae", font=("Consolas", 8))
        step_w = 18
        readout_w = 40
        plus_x = x + width - step_w
        readout_x = plus_x - step_w - readout_w
        minus_x = readout_x - step_w
        minus = canvas.create_round_rect(minus_x, y + 1, minus_x + step_w, y + row_height - 1, radius=4, fill="#243651", outline="#57749b")
        minus_text = canvas.create_text(minus_x + step_w / 2, mid, text="−", fill=INK, font=("Segoe UI", 8, "bold"))
        readout = canvas.create_text(readout_x + readout_w / 2, mid, text=f"{gain_percent:d}%", fill="#b9f7df" if live else MUTED, font=("Consolas", 8, "bold"))
        plus = canvas.create_round_rect(plus_x, y + 1, plus_x + step_w, y + row_height - 1, radius=4, fill="#243651", outline="#57749b")
        plus_text = canvas.create_text(plus_x + step_w / 2, mid, text="+", fill=INK, font=("Segoe UI", 8, "bold"))
        for item in (minus, minus_text):
            self._tag(canvas, item, f"moza_ffb_effect_adjust:{effect_id}:-10")
        for item in (plus, plus_text):
            self._tag(canvas, item, f"moza_ffb_effect_adjust:{effect_id}:10")
        self._tag(canvas, readout, f"moza_ffb_effect_adjust:{effect_id}:0")

    def _draw_moza_calibration(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Interactive profile editor drawn only from the supplied Moza presets."""

        device = self._selected_device
        is_ab6 = device == "moza_ab6"
        values = self._moza_calibration_values(device)
        axes, live_axes = self._moza_live_axes(device)
        title = "MOZA AB6 — BASE CALIBRATION" if is_ab6 else "MOZA A210 — BASE / YOKE CONTROL STUDIO"
        left, right = 18, width - 18
        top, bottom = 18, height - 18
        canvas.create_round_rect(left, top, right, bottom, radius=18, fill="#17243a", outline="#52647d", width=2)
        canvas.create_text(left + 22, top + 20, text=title, anchor="w", fill=INK, font=("Segoe UI Semibold", 12))
        canvas.create_text(
            right - 22, top + 20,
            text=("LIVE HID" if live_axes else "REFERENCE / PRACTICE"),
            anchor="e", fill="#b9f7df" if live_axes else MUTED,
            font=("Segoe UI", 7, "bold"), width=270, justify="right",
        )

        card_top = top + 38
        self._draw_moza_ffb_preset_bar(canvas, left + 24, card_top, right - 24, card_top + 48)

        main_top = card_top + 63
        left_panel, centre_split = left + 16, width * .62
        visual_right = centre_split - 8
        canvas.create_round_rect(left_panel, main_top, visual_right, bottom - 34, radius=13, fill="#101a2c", outline="#40546f", width=2)
        if is_ab6:
            # MAX3 grip moved here from the A210 tab set: it mounts on the
            # AB6 base on this rig, not the A210 yoke base. The faceplate
            # itself, and the A210 HID contact pool it reads live presses
            # from, are unchanged - only which screen surfaces the tab.
            page = self._moza_layout_page.get("moza_ab6", "base")
            self._draw_moza_layout_nav(
                canvas, left_panel + 18, main_top + 21,
                (("base", "AB6 BASE"), ("max3", "MAX3 GRIP")), page,
            )
            if page == "max3":
                self._draw_moza_max3_layout(canvas, left_panel, main_top + 42, visual_right, bottom - 38, device="moza_ab6")
            else:
                self._draw_moza_ab6_layout(canvas, left_panel, main_top + 42, visual_right, bottom - 38, axes)
        else:
            page = self._moza_layout_page.get("moza_a210", "base")
            self._draw_moza_layout_nav(
                canvas, left_panel + 18, main_top + 21,
                (("base", "A210 BASE"), ("yoke", "DETACHABLE YOKE")), page,
            )
            if page == "yoke":
                self._draw_moza_a210_yoke_layout(canvas, left_panel, main_top + 42, visual_right, bottom - 38, axes, live_axes)
            else:
                self._draw_moza_a210_base_layout(canvas, left_panel, main_top + 42, visual_right, bottom - 38)

        settings_left, settings_right = centre_split + 6, right - 24
        canvas.create_round_rect(settings_left, main_top, settings_right, bottom - 35, radius=13, fill="#101a2c", outline="#40546f", width=2)
        button = canvas.create_round_rect(settings_left + 18, main_top + 6, settings_right - 18, main_top + 36,
                                          radius=8, fill="#1d594f", outline=ACCENT, width=2)
        label = canvas.create_text((settings_left + settings_right) / 2, main_top + 21,
                                   text="FEEDBACK & TESTS — ROLL / PITCH / VIBRATION", fill=INK, font=("Segoe UI", 9, "bold"))
        for item in (button, label):
            self._tag(canvas, item, "moza_feedback_window")
        if is_ab6:
            self._draw_moza_ab6_saved_calibration(canvas, settings_left, settings_right, main_top + 42, bottom, width, values)
        else:
            self._draw_moza_ffb_panel(canvas, settings_left, settings_right, main_top + 42, bottom, width)
        # Both bases share the picker, with independent lists and selections.
        if self._moza_ffb_picker()["open"]:
            self._draw_moza_ffb_preset_dropdown_overlay(canvas, left + 24, card_top + 48, right - 24)

    def _draw_moza_ab6_saved_calibration(
        self, canvas: tk.Canvas, settings_left: float, settings_right: float,
        main_top: float, bottom: float, width: float, values: Dict[str, Any],
    ) -> None:
        """AB6's legacy calibration UI, unchanged: local-only, saved to this
        MuslimSim profile, never sent to hardware - see moza_presets.py's
        own docstring. The AY210's own panel (_draw_moza_ffb_panel) has
        moved on to real, wired sliders; AB6's own real protocol mapping is
        a separate, not-yet-done follow-up (see
        moza_ab6_calibration_notes.md)."""

        canvas.create_text(settings_left + 18, main_top + 19, text="SAVED CALIBRATION", anchor="w", fill="#f2d7a1", font=("Segoe UI Semibold", 10, "bold"))
        canvas.create_text(settings_right - 18, main_top + 19, text="click − / + or ON / OFF", anchor="e", fill=MUTED, font=("Segoe UI", 7))
        setting_width = (settings_right - settings_left - 54) / 3
        force_fields = (
            ("OVERALL", "overall_strength"), ("MAX TORQUE", "max_torque"), ("GAME FFB", "game_force_feedback"),
            ("DAMPER", "damper"), ("FRICTION", "friction"), ("INERTIA", "inertia"),
            ("SPRING", "spring"), ("ADVANCED", "advanced_force"),
        )
        for index, (label, key) in enumerate(force_fields):
            row, column = divmod(index, 3)
            self._draw_moza_setting(canvas, settings_left + 18 + column * (setting_width + 9), main_top + 43 + row * 52, setting_width, label, key, values.get(key, 0))
        axis_top = main_top + 194
        canvas.create_text(settings_left + 18, axis_top, text="AXIS SETUP", anchor="w", fill="#c6d5e9", font=("Segoe UI Semibold", 8, "bold"))
        axis_fields = (
            ("X INVERT", "axis_range_x_reversal"), ("Y INVERT", "axis_range_y_reversal"), ("Z INVERT", "axis_range_z_reversal"),
            ("X DEADZONE", "axis_x_deadzone"), ("Y DEADZONE", "axis_y_deadzone"), ("Z DEADZONE", "axis_z_deadzone"),
        )
        for index, (label, key) in enumerate(axis_fields):
            row, column = divmod(index, 3)
            raw_value = values.get(key, 0)
            value = bool(raw_value) if key.endswith("reversal") else raw_value
            self._draw_moza_setting(canvas, settings_left + 18 + column * (setting_width + 9), axis_top + 12 + row * 52, setting_width, label, key, value)
        effects_top = axis_top + 130
        canvas.create_text(settings_left + 18, effects_top, text="FLIGHT EFFECTS", anchor="w", fill="#c6d5e9", font=("Segoe UI Semibold", 8, "bold"))
        effect_fields = (
            ("G FORCE", "g_force_enabled"), ("STALL BUFFET", "stall_buffet_enabled"), ("RUNWAY", "runway_rumble_enabled"),
            ("GEAR", "gear_motion_enabled"), ("FLAPS", "flaps_motion_enabled"), ("JET RUMBLE", "jet_rumble_enabled"),
            ("TURBULENCE", "turbulence_enabled"), ("SPEEDBRAKE", "speedbrake_buffet_enabled"),
        )
        for index, (label, key) in enumerate(effect_fields):
            row, column = divmod(index, 3)
            self._draw_moza_setting(canvas, settings_left + 18 + column * (setting_width + 9), effects_top + 12 + row * 44, setting_width, label, key, bool(values.get(key, False)))
        canvas.create_text((settings_left + settings_right) / 2, bottom - 52, state="hidden", text="Preset values are saved to this MuslimSim profile. No Moza output protocol was present in these files, so Studio does not send unknown force-feedback commands.", fill=MUTED, font=("Segoe UI", 7), width=settings_right - settings_left - 40)
        canvas.create_text(width / 2, bottom - 13, state="hidden", text="Blue = profile setting • teal = selected preset • the A210 yoke stays one device when removed or refitted", fill=MUTED, font=("Segoe UI", 8))

    def _draw_moza_ffb_panel(
        self, canvas: tk.Canvas, settings_left: float, settings_right: float,
        main_top: float, bottom: float, width: float,
    ) -> None:
        """The AY210's real, wired force-feedback panel - every physics row
        here reaches the live MozaAy210FfbEngine over the same
        "device_command" RPC the axis-assignment dialog uses (see
        _moza_ffb_physics_command()), unlike moza_presets.py's older
        local-only calibration UI (still used for AB6 - see
        _draw_moza_ab6_saved_calibration)."""

        diagnostics = self._moza_ffb_diagnostics()
        engine_running = bool(diagnostics.get("connected") and diagnostics.get("last_tick"))
        # server.py's _device_statuses() folds status_snapshot()'s own fields
        # (including "active_profile") straight onto this dict alongside
        # "diagnostics" - there is no nested "state" wrapper to unpack.
        device_state = self._device_states.get("moza_a210_ffb", {})
        active_profile_name = device_state.get("active_profile") if isinstance(device_state, dict) else None

        canvas.create_text(settings_left + 18, main_top + 19, text="FORCE FEEDBACK — PHYSICS MODEL", anchor="w", fill="#f2d7a1", font=("Segoe UI Semibold", 10, "bold"))
        canvas.create_text(
            settings_right - 18, main_top + 19,
            text=(("LIVE — writing to hardware" if engine_running else "FFB INACTIVE")),
            anchor="e", fill="#b9f7df" if engine_running else MUTED, font=("Segoe UI", 7, "bold"),
        )

        physics_top = main_top + 40
        for index, (label, field) in enumerate(MOZA_FFB_PHYSICS_FIELDS):
            value = self._moza_ffb_physics_value(field)
            self._draw_moza_ffb_physics_row(
                canvas, settings_left + 18, physics_top + index * 32, settings_right - settings_left - 36,
                label, field, value, live=engine_running,
            )

        effects_top = physics_top + len(MOZA_FFB_PHYSICS_FIELDS) * 32 + 14
        canvas.create_text(settings_left + 18, effects_top, text="ACTIVE PROFILE EFFECTS", anchor="w", fill="#c6d5e9", font=("Segoe UI Semibold", 8, "bold"))
        # On its own line below the title, not squeezed onto the same one -
        # a long profile name (e.g. a saved "... - roll fix" copy) has
        # nowhere else to go without overlapping the title text.
        canvas.create_text(
            settings_left + 18, effects_top + 14, anchor="w",
            text=(active_profile_name or "(none selected)"), fill="#b9f7df" if active_profile_name else MUTED,
            font=("Segoe UI", 7, "bold"), width=settings_right - settings_left - 36,
        )
        last_effect_values = diagnostics.get("last_effect_values") if isinstance(diagnostics, dict) else None
        rows_top = effects_top + 30
        if isinstance(last_effect_values, dict) and last_effect_values:
            row_y = rows_top
            for effect_id in sorted(last_effect_values):
                effect_value = last_effect_values.get(effect_id)
                gain_percent = self._moza_ffb_effect_gain_value(effect_id)
                self._draw_moza_ffb_effect_gain_row(
                    canvas, settings_left + 18, row_y, settings_right - settings_left - 36,
                    effect_id, effect_value if isinstance(effect_value, (int, float)) else None,
                    gain_percent, live=engine_running,
                )
                row_y += 22
                if row_y > bottom - 46:
                    break
        else:
            canvas.create_text(
                settings_left + 18, rows_top, anchor="w",
                text="No effects reporting yet.",
                fill=MUTED, font=("Segoe UI", 7), width=settings_right - settings_left - 36,
            )

        canvas.create_text(width / 2, bottom - 13, state="hidden", text="Click − / + on any effect above to scale how strong it feels (0-200%) - a live override, same as the physics rows, never written to the .mslm file itself.", fill=MUTED, font=("Segoe UI", 8), width=width - 80)

    def _draw_moza_ffb_preset_bar(
        self, canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
    ) -> None:
        """A dropdown, not a fixed row of cards: real .mslm profiles accumulate
        (bundled Tony-derived presets, drop-ins, and anything saved from
        "+ New Preset"), so this list has no natural fixed width."""

        if not self._moza_ffb_picker()["names"]:
            self._moza_ffb_list_profiles()

        device_state = self._device_states.get(self._moza_ffb_picker_device() + "_ffb", {})
        active_name = device_state.get("active_profile") if isinstance(device_state, dict) else None
        active_name = active_name or self._moza_ffb_picker()["active"]
        open_now = self._moza_ffb_picker()["open"]

        bar = canvas.create_round_rect(
            x1, y1, x2, y2, radius=9,
            fill="#1d594f" if open_now else "#1a2940",
            outline=ACCENT if open_now else "#486481", width=2,
        )
        label = canvas.create_text(
            x1 + 14, (y1 + y2) / 2, anchor="w",
            text=f"PRESET: {active_name}" if active_name else "PRESET: (none selected)",
            fill=INK, font=("Segoe UI Semibold", 9, "bold"), width=(x2 - x1) - 60,
        )
        chevron = canvas.create_text(
            x2 - 16, (y1 + y2) / 2, anchor="e", text="▴" if open_now else "▾",
            fill=INK, font=("Segoe UI", 11, "bold"),
        )
        for item in (bar, label, chevron):
            self._tag(canvas, item, "moza_ffb_preset_toggle")

    def _draw_moza_ffb_preset_dropdown_overlay(
        self, canvas: tk.Canvas, x1: float, y1: float, x2: float,
    ) -> None:
        """The expanded list, drawn last so it sits on top of every panel
        beneath it - the same one-canvas overlay idiom as a selection ring."""

        device_state = self._device_states.get(self._moza_ffb_picker_device() + "_ffb", {})
        active_name = device_state.get("active_profile") if isinstance(device_state, dict) else None
        active_name = active_name or self._moza_ffb_picker()["active"]

        rows = list(self._moza_ffb_picker()["names"])
        row_height = 30
        list_height = max(1, len(rows)) * row_height if rows else row_height
        legacy = moza_presets_for_device("moza_ab6") if self._moza_ffb_picker_device() == "moza_ab6" else []
        new_preset_top = y1 + list_height + len(legacy) * row_height
        panel_bottom = new_preset_top + 2 * row_height

        canvas.create_round_rect(
            x1, y1, x2, panel_bottom, radius=9,
            fill="#0e1826", outline=ACCENT, width=2,
        )
        if rows:
            for index, name in enumerate(rows):
                row_top = y1 + index * row_height
                row_bottom = row_top + row_height
                selected = name == active_name
                if selected:
                    canvas.create_rectangle(x1 + 2, row_top, x2 - 2, row_bottom, fill="#1d594f", outline="")
                text = canvas.create_text(
                    x1 + 14, (row_top + row_bottom) / 2, anchor="w", text=name,
                    fill="#b9f7df" if selected else INK, font=("Segoe UI", 9, "bold" if selected else "normal"),
                    width=(x2 - x1) - 28,
                )
                self._tag(canvas, text, f"moza_ffb_preset_select:{name}")
                hit = canvas.create_rectangle(x1 + 2, row_top, x2 - 2, row_bottom, fill="", outline="")
                self._tag(canvas, hit, f"moza_ffb_preset_select:{name}")
        else:
            canvas.create_text(
                x1 + 14, y1 + row_height / 2, anchor="w",
                text=self._moza_ffb_picker()["error"] or "No .mslm presets in this device folder.",
                fill=MUTED, font=("Segoe UI", 8),
            )

        # Preserve the existing AB6 reference-calibration choices in the same menu.
        for index, preset in enumerate(legacy):
            preset_id = next(key for key, value in MOZA_UI_PRESETS.items() if value is preset)
            row_top = y1 + list_height + index * row_height
            label = canvas.create_text(x1 + 14, row_top + row_height / 2, anchor="w",
                                       text=str(preset.get("title") or "Reference preset") + " (calibration)",
                                       fill=INK, font=("Segoe UI", 9), width=(x2 - x1) - 28)
            hit = canvas.create_rectangle(x1 + 2, row_top, x2 - 2, row_top + row_height, fill="", outline="")
            for item in (label, hit):
                self._tag(canvas, item, f"moza_preset:{preset_id}")
        browse_row = canvas.create_rectangle(x1 + 2, new_preset_top, x2 - 2, new_preset_top + row_height, fill="#20344f", outline="")
        browse_text = canvas.create_text(x1 + 14, new_preset_top + row_height / 2,
                                        anchor="w", text="Browse… (.mslm)", fill=INK, font=("Segoe UI", 9, "bold"))
        for item in (browse_row, browse_text):
            self._tag(canvas, item, "moza_ffb_browse")
        new_preset_top += row_height
        if self._moza_ffb_picker_device() + "_ffb" not in self._device_states:
            return
        new_row = canvas.create_rectangle(x1 + 2, new_preset_top, x2 - 2, panel_bottom, fill="#20344f", outline="")
        new_text = canvas.create_text(
            x1 + 14, (new_preset_top + panel_bottom) / 2, anchor="w",
            text="+ New Preset…", fill="#f2d7a1", font=("Segoe UI Semibold", 9, "bold"),
        )
        for item in (new_row, new_text):
            self._tag(canvas, item, "moza_ffb_new_preset")

    def _draw_tca_boeing_combined(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw the TCA Boeing quadrant as the single physical unit it is.

        MUSLIMSIM_TCA_BOEING_2D_FACEPLATE_V3

        V2 drew two side-by-side bank cards with three unlabelled lanes each,
        every handle pinned to mid-travel, and no ``_tag`` call anywhere -- so
        nothing on it could be clicked and "Choose simulator function" could
        never enable.  Its "AXIS 0/1/2" captions were loop ordinals that
        matched no hardware: the three levers are SDL axes 3, 4 and 5.

        This draws one quadrant, laid out like the real unit, with every
        control from the 2026-08-31 capture in its physical place, animated
        from the live bridge mirror and individually selectable.
        """
        detected = self._detected.get("tca_boeing") or {}
        mirror = self._device_mirror("tca_boeing")
        product = str(detected.get("product") or "")
        product_norm = " ".join(product.casefold().split())
        bank = "34" if "3&4" in product_norm else "12"
        bank_label = "3&4" if bank == "34" else "1&2"
        connected = bool(detected.get("connected", product != ""))

        panel = "#15212d"
        card = "#1d2b39"
        metal = "#243343"
        slot = "#0e1720"
        edge = "#4f6273"
        live = "#36d8c4"
        text = "#f3f6f8"
        muted = "#8fa0ae"
        amber = "#e9b958"

        def key_for(kind: str, index: int) -> str:
            return "bank%s_%s_%d" % (bank, kind, index)

        def axis_value(index: int) -> float:
            raw = mirror.get(key_for("axis", index))
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return 1.0
            return max(-1.0, min(1.0, value))

        def button_on(index: int) -> bool:
            return bool(mirror.get(key_for("button", index)))

        def known(key: str) -> bool:
            """Whether this control is captured, so the Studio may bind it."""
            return key in self._visual_controls()

        canvas.create_rectangle(
            18, 18, max(40, width - 18), max(40, height - 18),
            fill=panel, outline=edge, width=2,
        )
        canvas.create_text(
            44, 44, text="THRUSTMASTER TCA BOEING QUADRANT",
            anchor="w", fill=text, font=("Segoe UI", 16, "bold"),
        )
        canvas.create_text(
            max(60, width - 44), 44,
            text=("ENGINE BANK " + bank_label) if connected else "WAITING FOR TCA",
            anchor="e", fill=live if connected else amber,
            font=("Segoe UI", 12, "bold"),
        )
        canvas.create_text(
            44, 68,
            state="hidden", text=(
                "One physical unit  \u2022  the 1&2 / 3&4 selector is read when USB "
                "enumerates  \u2022  click any control to map it"
            ),
            anchor="w", fill=muted, font=("Segoe UI", 9),
        )

        body_left = 40.0
        body_right = max(body_left + 620.0, float(width) - 40.0)
        body_top = 92.0
        body_bottom = max(body_top + 400.0, float(height) - 44.0)
        canvas.create_round_rect(
            body_left, body_top, body_right, body_bottom,
            radius=18, fill=card, outline=edge, width=2,
        )

        # ---- side buttons, down the captain-side edge of the chassis ----
        # Captured order: the owner's side button 1..5 are SDL 9, 6, 7, 8, 10.
        side_indices = (9, 6, 7, 8, 10)
        side_x1 = body_left + 22.0
        side_x2 = side_x1 + 74.0
        side_top = body_top + 46.0
        canvas.create_text(
            (side_x1 + side_x2) / 2.0, body_top + 28.0, text="SIDE",
            fill=muted, font=("Segoe UI", 8, "bold"),
        )
        for position, index in enumerate(side_indices):
            key = key_for("button", index)
            y1 = side_top + position * 42.0
            y2 = y1 + 32.0
            self._highlight_ring(canvas, side_x1, y1, side_x2, y2, key, radius=6)
            item = canvas.create_round_rect(
                side_x1, y1, side_x2, y2, radius=6,
                fill=live if button_on(index) else self._control_fill(key, metal),
                outline=self._control_color(key),
                width=3 if key == self._selected_visual else 2,
            )
            self._tag(canvas, item, key)
            label = canvas.create_text(
                (side_x1 + side_x2) / 2.0, (y1 + y2) / 2.0,
                text="S%d" % (position + 1),
                fill="#0e1720" if button_on(index) else text,
                font=("Segoe UI", 9, "bold"),
            )
            self._tag(canvas, label, key)

        # ---- the three levers ----
        lever_left = side_x2 + 40.0
        knob_width = 150.0
        lever_right = body_right - knob_width - 46.0
        lane_span = (lever_right - lever_left) / 3.0
        track_top = body_top + 62.0
        track_bottom = body_bottom - 92.0

        levers = (
            (3, "LEFT", "AIRBRAKE", None, None),
            (4, "MIDDLE", "THRUST", 4, 1),
            (5, "RIGHT", "FLAPS", 5, 2),
        )
        for position, (axis_index, name, role, rev_index, btn_index) in enumerate(levers):
            axis_key = key_for("axis", axis_index)
            cx = lever_left + lane_span * (position + 0.5)

            canvas.create_text(
                cx, track_top - 26.0, text=name,
                fill=text if known(axis_key) else muted,
                font=("Segoe UI", 10, "bold"),
            )
            canvas.create_text(
                cx, track_top - 11.0, text=role,
                fill=live if known(axis_key) else muted, font=("Segoe UI", 8),
            )

            # Slot.  Rest (+1.0) sits at the bottom and full travel (-1.0) at
            # the top, which is the same direction the binding uses: rest maps
            # to 0.0, meaning idle thrust, speedbrake in, flaps up.
            self._highlight_ring(
                canvas, cx - 15, track_top, cx + 15, track_bottom, axis_key, radius=9,
            )
            canvas.create_round_rect(
                cx - 15, track_top, cx + 15, track_bottom, radius=9,
                fill=slot, outline=self._control_color(axis_key),
                width=3 if axis_key == self._selected_visual else 1,
            )
            for tick in range(0, 5):
                ty = track_top + (track_bottom - track_top) * tick / 4.0
                canvas.create_line(cx - 24, ty, cx - 17, ty, fill=edge)
                canvas.create_line(cx + 17, ty, cx + 24, ty, fill=edge)

            travel = (1.0 - axis_value(axis_index)) / 2.0
            handle_y = track_bottom - (track_bottom - track_top) * travel
            handle = canvas.create_round_rect(
                cx - 27, handle_y - 15, cx + 27, handle_y + 15, radius=7,
                fill=self._control_fill(axis_key, "#3a4a5e"),
                outline=self._control_color(axis_key),
                width=3 if axis_key == self._selected_visual else 2,
            )
            self._tag(canvas, handle, axis_key)
            grip = canvas.create_line(
                cx - 18, handle_y, cx + 18, handle_y, fill=live if connected else muted, width=2,
            )
            self._tag(canvas, grip, axis_key)

            # Reverse lever, drawn on the handle of the two slides that carry
            # one.  The owner confirmed these are the middle and right slides.
            if rev_index is not None:
                rev_key = key_for("button", rev_index)
                self._highlight_ring(
                    canvas, cx - 27, handle_y - 34, cx + 27, handle_y - 18, rev_key, radius=5,
                )
                rev = canvas.create_round_rect(
                    cx - 27, handle_y - 34, cx + 27, handle_y - 18, radius=5,
                    fill=amber if button_on(rev_index) else self._control_fill(rev_key, "#5a3a2c"),
                    outline=self._control_color(rev_key),
                    width=3 if rev_key == self._selected_visual else 2,
                )
                self._tag(canvas, rev, rev_key)
                rev_text = canvas.create_text(
                    cx, handle_y - 26, text="REV",
                    fill="#0e1720" if button_on(rev_index) else text,
                    font=("Segoe UI", 7, "bold"),
                )
                self._tag(canvas, rev_text, rev_key)

            # Button on the slide handle.  It sits beside the handle rather
            # than below it: below collides with the caption once the lever
            # reaches its bottom stop, which is where a throttle rests.
            if btn_index is not None:
                btn_key = key_for("button", btn_index)
                bx = cx + 42.0
                self._highlight_ring(
                    canvas, bx - 11, handle_y - 11, bx + 11, handle_y + 11, btn_key, radius=5,
                )
                dot = canvas.create_oval(
                    bx - 11, handle_y - 11, bx + 11, handle_y + 11,
                    fill=live if button_on(btn_index) else self._control_fill(btn_key, metal),
                    outline=self._control_color(btn_key),
                    width=3 if btn_key == self._selected_visual else 2,
                )
                self._tag(canvas, dot, btn_key)

            canvas.create_text(
                cx, track_bottom + 20.0,
                text="axis %d" % axis_index, fill=muted, font=("Segoe UI", 8),
            )

        # ---- the two knobs, on the first-officer side of the chassis ----
        knob_x1 = lever_right + 26.0
        knob_x2 = body_right - 22.0
        knob_cx = (knob_x1 + knob_x2) / 2.0
        canvas.create_round_rect(
            knob_x1, body_top + 26.0, knob_x2, body_bottom - 26.0,
            radius=12, fill=metal, outline=edge, width=1,
        )

        # Continuous encoder: one contact per direction, no end stops.
        enc_cy = body_top + 104.0
        canvas.create_text(
            knob_cx, body_top + 48.0, text="TOP KNOB",
            fill=text, font=("Segoe UI", 9, "bold"),
        )
        canvas.create_text(
            knob_cx, body_top + 63.0, text="turns without end",
            fill=muted, font=("Segoe UI", 7),
        )
        canvas.create_oval(
            knob_cx - 34, enc_cy - 34, knob_cx + 34, enc_cy + 34,
            fill="#1a2634", outline=edge, width=2,
        )
        for direction, index, angle_text, dx in (("CCW", 14, "\u25c0", -1), ("CW", 15, "\u25b6", 1)):
            key = key_for("button", index)
            x1 = knob_cx + dx * 14 - 15
            x2 = knob_cx + dx * 14 + 15
            self._highlight_ring(canvas, x1, enc_cy - 15, x2, enc_cy + 15, key, radius=5)
            arc = canvas.create_round_rect(
                x1, enc_cy - 15, x2, enc_cy + 15, radius=5,
                fill=live if button_on(index) else self._control_fill(key, "#2c3d50"),
                outline=self._control_color(key),
                width=3 if key == self._selected_visual else 1,
            )
            self._tag(canvas, arc, key)
            glyph = canvas.create_text(
                knob_cx + dx * 14, enc_cy,
                text=angle_text, fill="#0e1720" if button_on(index) else text,
                font=("Segoe UI", 9, "bold"),
            )
            self._tag(canvas, glyph, key)

        # Knob pushbutton: engages whatever the select window is showing.
        push_key = key_for("button", 16)
        push_y = enc_cy + 56.0
        self._highlight_ring(canvas, knob_cx - 40, push_y - 13, knob_cx + 40, push_y + 13, push_key, radius=6)
        push = canvas.create_round_rect(
            knob_cx - 40, push_y - 13, knob_cx + 40, push_y + 13, radius=6,
            fill=live if button_on(16) else self._control_fill(push_key, "#2c3d50"),
            outline=self._control_color(push_key),
            width=3 if push_key == self._selected_visual else 2,
        )
        self._tag(canvas, push, push_key)
        push_text = canvas.create_text(
            knob_cx, push_y, text="PUSH / SELECT",
            fill="#0e1720" if button_on(16) else text, font=("Segoe UI", 8, "bold"),
        )
        self._tag(canvas, push_text, push_key)

        # Three-position select knob.  It names what the top knob adjusts.
        sel_top = push_y + 40.0
        canvas.create_text(
            knob_cx, sel_top, text="SELECT",
            fill=text, font=("Segoe UI", 9, "bold"),
        )
        for position, (index, label) in enumerate(
            ((11, "IAS / MACH"), (12, "HDG / TRK"), (13, "ALTITUDE"))
        ):
            key = key_for("button", index)
            y1 = sel_top + 18.0 + position * 34.0
            y2 = y1 + 26.0
            selected_detent = button_on(index)
            self._highlight_ring(canvas, knob_cx - 60, y1, knob_cx + 60, y2, key, radius=6)
            item = canvas.create_round_rect(
                knob_cx - 60, y1, knob_cx + 60, y2, radius=6,
                fill=live if selected_detent else self._control_fill(key, "#2c3d50"),
                outline=self._control_color(key),
                width=3 if key == self._selected_visual else 1,
            )
            self._tag(canvas, item, key)
            caption = canvas.create_text(
                knob_cx, (y1 + y2) / 2.0, text=label,
                fill="#0e1720" if selected_detent else text,
                font=("Segoe UI", 8, "bold"),
            )
            self._tag(canvas, caption, key)

        footer = (
            "Windows/SDL: %s" % (product or "not detected")
        )
        if bank == "34":
            footer += "  \u2022  bank 3&4 was not captured; run tools/capture_tca_boeing_one_unit_both_banks.py"
        canvas.create_text(
            (body_left + body_right) / 2.0, body_bottom + 16.0,
            text=footer, fill=muted, font=("Segoe UI", 8),
        )

    # Full-set Practice surface.  The V3 single-unit drawing above is retained
    # as a reference for the known-good live geometry; this version composes
    # one or two of the same physical units without touching their input path.
    _TCA_UNITS = (("12", "1&2", "CAPTAIN SIDE"), ("34", "3&4", "FIRST OFFICER SIDE"))
    _TCA_FULL_SET_ROLES = {
        ("12", 3): "AIRBRAKE",
        ("12", 4): "THRUST 1",
        ("12", 5): "THRUST 2",
        ("34", 3): "THRUST 3",
        ("34", 4): "THRUST 4",
        ("34", 5): "FLAPS",
    }
    _TCA_SINGLE_ROLES = {3: "AIRBRAKE", 4: "THRUST (ALL)", 5: "FLAPS"}
    _TCA_SIDE_BUTTONS = (9, 6, 7, 8, 10)
    _TCA_SELECT_DETENTS = ((11, "IAS / MACH"), (12, "HDG / TRK"), (13, "ALTITUDE"))
    _TCA_HANDLE_CONTACTS = {3: (3, 0), 4: (4, 1), 5: (5, 2)}
    _TCA_AXIS_DEADBAND = 0.0015
    _TCA_AXIS_INTERVAL = 0.015

    def _tca_axis_value(self, mirror: Dict[str, Any], bank: str, index: int) -> float:
        """Read exactly the raw value used by the working physical faceplate."""

        key = f"bank{bank}_axis_{index}"
        source: Any
        if self.practice_mode.get():
            source = self._tca_practice_axes.get(key, 1.0)
        else:
            source = mirror.get(key, 1.0)
        try:
            return max(-1.0, min(1.0, float(source)))
        except (TypeError, ValueError):
            return 1.0

    def _draw_tca_boeing_set(self, canvas: tk.Canvas, width: int, height: int) -> None:
        """Draw one real quadrant or the complete two-quadrant Practice set."""

        mirror = self._device_mirror("tca_boeing")
        detected = self._detected.get("tca_boeing") or {}
        product = str(mirror.get("product") or detected.get("product") or "")
        active = str(mirror.get("active_bank") or mirror.get("bank") or "")
        if active not in {"1&2", "3&4"}:
            normalized = " ".join(product.casefold().split())
            active = "3&4" if "3&4" in normalized else "1&2" if "1&2" in normalized else ""
        active_code = "34" if active == "3&4" else "12" if active == "1&2" else ""
        bank_connected = {
            "12": bool(mirror.get("bank12_connected")),
            "34": bool(mirror.get("bank34_connected")),
        }
        if active_code and bool(mirror.get("connected", detected.get("connected", False))):
            bank_connected[active_code] = True
        practice = bool(self.practice_mode.get())
        full_set = practice or all(bank_connected.values())

        panel, card, metal = "#15212d", "#1d2b39", "#243343"
        slot, edge, live = "#0e1720", "#4f6273", "#36d8c4"
        text, muted, amber, ghost = "#f3f6f8", "#8fa0ae", "#e9b958", "#33414f"

        canvas.create_rectangle(14, 14, width - 14, height - 14, fill=panel, outline=edge, width=2)
        canvas.create_text(
            38, 38, text="THRUSTMASTER TCA BOEING QUADRANT",
            anchor="w", fill=text, font=("Segoe UI", 15, "bold"),
        )
        state_text = (
            "PRACTICE — FULL SET"
            if practice else "FULL PHYSICAL SET"
            if all(bank_connected.values()) else f"ENGINE BANK {active}"
            if active else "WAITING FOR TCA"
        )
        canvas.create_text(
            width - 38, 38, text=state_text, anchor="e",
            fill=amber if practice else live if active else amber,
            font=("Segoe UI", 11, "bold"),
        )
        canvas.create_text(
            38, 60,
            text=(
                ("AIRBRAKE  •  THRUST 1  •  THRUST 2  •  THRUST 3  •  THRUST 4  •  FLAPS" if full_set else "AIRBRAKE  •  THRUST  •  FLAPS")
            ),
            anchor="w", fill=muted, font=("Segoe UI", 8),
        )

        self._tca_axis_tracks.clear()
        units = self._TCA_UNITS if full_set else (
            (active_code or "12", active or "1&2", ""),
        )
        outer_left = 30.0
        outer_right = float(width) - 30.0
        top = 78.0
        bottom = float(height) - 34.0
        gap = 16.0
        unit_width = (outer_right - outer_left - gap * (len(units) - 1)) / len(units)
        colours = (card, metal, slot, edge, live, text, muted, amber, ghost)
        for position, (bank, label, side) in enumerate(units):
            left = outer_left + position * (unit_width + gap)
            self._draw_tca_unit(
                canvas,
                mirror,
                bank,
                label,
                side,
                left,
                top,
                left + unit_width,
                bottom,
                full_set=full_set,
                physically_connected=bank_connected.get(bank, False),
                virtual_available=practice,
                colours=colours,
            )
        footer = (
            "Practice: drag any handle or click anywhere in its slot. Only the newest continuous value is posted."
            if practice else
            f"Windows/SDL: {product or 'not detected'}  •  physical polling remains on the original reader"
        )
        canvas.create_text(
            (outer_left + outer_right) / 2.0, bottom + 14.0,
            text=footer, fill=muted, font=("Segoe UI", 8),
        )

    def _draw_tca_unit(
        self,
        canvas: tk.Canvas,
        mirror: Dict[str, Any],
        bank: str,
        bank_label: str,
        side_label: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        full_set: bool,
        physically_connected: bool,
        virtual_available: bool,
        colours: tuple[str, ...],
    ) -> None:
        """Draw the three working lever axes and all 17 button identities."""

        card, metal, slot, edge, live, text, muted, amber, ghost = colours
        known = self._visual_controls()
        available = physically_connected or virtual_available

        def key_for(kind: str, index: int) -> str:
            return f"bank{bank}_{kind}_{index}"

        def on(index: int) -> bool:
            return bool(mirror.get(key_for("button", index)))

        def usable(key: str) -> bool:
            return key in known

        outline = live if physically_connected else amber if virtual_available else ghost
        canvas.create_round_rect(x1, y1, x2, y2, radius=14, fill=card, outline=outline, width=2)
        canvas.create_text(
            (x1 + x2) / 2.0, y1 + 18.0, text=f"ENGINE BANK {bank_label}",
            fill=text if available else muted, font=("Segoe UI", 11, "bold"),
        )
        if side_label:
            canvas.create_text(
                (x1 + x2) / 2.0, y1 + 34.0,
                text=side_label + ("  •  VIRTUAL" if virtual_available and not physically_connected else ""),
                fill=live if physically_connected else amber if virtual_available else muted,
                font=("Segoe UI", 7, "bold"),
            )

        # Five side buttons.
        sx1, sx2 = x1 + 14.0, x1 + 54.0
        side_top = y1 + 54.0
        canvas.create_text((sx1 + sx2) / 2.0, side_top - 12.0, text="SIDE", fill=muted, font=("Segoe UI", 7, "bold"))
        for position, index in enumerate(self._TCA_SIDE_BUTTONS):
            key = key_for("button", index)
            by1, by2 = side_top + position * 32.0, side_top + position * 32.0 + 24.0
            self._highlight_ring(canvas, sx1, by1, sx2, by2, key, radius=5)
            item = canvas.create_round_rect(
                sx1, by1, sx2, by2, radius=5,
                fill=live if on(index) else self._control_fill(key, metal if usable(key) else ghost),
                outline=self._control_color(key), width=3 if key == self._selected_visual else 1,
            )
            label = canvas.create_text(
                (sx1 + sx2) / 2.0, (by1 + by2) / 2.0, text=f"S{position + 1}",
                fill="#0e1720" if on(index) else text, font=("Segoe UI", 8, "bold"),
            )
            self._tag(canvas, item, key)
            self._tag(canvas, label, key)

        # Knob column: encoder directions, pushbutton, and three select detents.
        kx2, kx1 = x2 - 12.0, x2 - 116.0
        kcx = (kx1 + kx2) / 2.0
        canvas.create_round_rect(kx1, y1 + 46.0, kx2, y2 - 22.0, radius=10, fill=metal, outline=edge, width=1)
        encoder_y = y1 + 92.0
        canvas.create_text(kcx, y1 + 60.0, text="TOP KNOB", fill=text, font=("Segoe UI", 8, "bold"))
        canvas.create_oval(kcx - 26, encoder_y - 22, kcx + 26, encoder_y + 22, fill=slot, outline=edge, width=1)
        for glyph, index, direction in (("◀", 14, -1), ("▶", 15, 1)):
            key = key_for("button", index)
            cx = kcx + direction * 12.0
            item = canvas.create_round_rect(
                cx - 12, encoder_y - 12, cx + 12, encoder_y + 12, radius=4,
                fill=live if on(index) else self._control_fill(key, "#2c3d50"),
                outline=self._control_color(key), width=3 if key == self._selected_visual else 1,
            )
            mark = canvas.create_text(cx, encoder_y, text=glyph, fill="#0e1720" if on(index) else text, font=("Segoe UI", 8, "bold"))
            self._tag(canvas, item, key)
            self._tag(canvas, mark, key)
        push_key = key_for("button", 16)
        push_y = encoder_y + 40.0
        push = canvas.create_round_rect(
            kcx - 44, push_y - 11, kcx + 44, push_y + 11, radius=5,
            fill=live if on(16) else self._control_fill(push_key, "#2c3d50"),
            outline=self._control_color(push_key), width=3 if push_key == self._selected_visual else 1,
        )
        push_text = canvas.create_text(kcx, push_y, text="PUSH / SELECT", fill="#0e1720" if on(16) else text, font=("Segoe UI", 7, "bold"))
        self._tag(canvas, push, push_key)
        self._tag(canvas, push_text, push_key)
        select_top = push_y + 26.0
        canvas.create_text(kcx, select_top, text="SELECT", fill=text, font=("Segoe UI", 8, "bold"))
        for position, (index, caption) in enumerate(self._TCA_SELECT_DETENTS):
            key = key_for("button", index)
            dy1 = select_top + 14.0 + position * 28.0
            dy2 = dy1 + 22.0
            item = canvas.create_round_rect(
                kcx - 46, dy1, kcx + 46, dy2, radius=5,
                fill=live if on(index) else self._control_fill(key, "#2c3d50"),
                outline=self._control_color(key), width=3 if key == self._selected_visual else 1,
            )
            label = canvas.create_text(kcx, (dy1 + dy2) / 2.0, text=caption, fill="#0e1720" if on(index) else text, font=("Segoe UI", 7, "bold"))
            self._tag(canvas, item, key)
            self._tag(canvas, label, key)

        # Three continuous lever tracks. Every moving accessory shares one
        # movement tag, so pointer motion changes only this handle group.
        lane_left, lane_right = sx2 + 24.0, kx1 - 18.0
        lane_span = (lane_right - lane_left) / 3.0
        track_top, track_bottom = y1 + 74.0, y2 - 52.0
        for position, axis_index in enumerate((3, 4, 5)):
            axis_key = key_for("axis", axis_index)
            cx = lane_left + lane_span * (position + 0.5)
            role = self._TCA_FULL_SET_ROLES[(bank, axis_index)] if full_set else self._TCA_SINGLE_ROLES[axis_index]
            reserved = role in {"AIRBRAKE", "FLAPS"}
            canvas.create_text(cx, track_top - 24.0, text=("LEFT", "MIDDLE", "RIGHT")[position], fill=text, font=("Segoe UI", 8, "bold"))
            canvas.create_text(cx, track_top - 11.0, text=role, fill=amber if reserved else live, font=("Segoe UI", 7, "bold"))
            self._highlight_ring(canvas, cx - 13, track_top, cx + 13, track_bottom, axis_key, radius=8)
            track = canvas.create_round_rect(
                cx - 13, track_top, cx + 13, track_bottom, radius=8,
                fill=slot, outline=self._control_color(axis_key),
                width=3 if axis_key == self._selected_visual else 1,
            )
            self._tag(canvas, track, axis_key)
            raw_value = self._tca_axis_value(mirror, bank, axis_index)
            dragging_this_axis = self._selected_device == "tca_boeing" and self._tca_drag_axis == axis_key
            if not dragging_this_axis:
                raw_value = self._axis_ease("tca_boeing", axis_key, raw_value)
            travel = (1.0 - raw_value) / 2.0
            handle_y = track_bottom - (track_bottom - track_top) * travel
            move_tag = f"tca-handle:{axis_key}"
            handle = canvas.create_round_rect(
                cx - 23, handle_y - 13, cx + 23, handle_y + 13, radius=6,
                fill=self._control_fill(axis_key, "#3a4a5e"),
                outline=self._control_color(axis_key), width=3 if axis_key == self._selected_visual else 2,
            )
            grip = canvas.create_line(cx - 15, handle_y, cx + 15, handle_y, fill=amber if reserved else live, width=2)
            for item in (handle, grip):
                self._tag(canvas, item, axis_key)
                canvas.addtag_withtag(move_tag, item)
            rev_index, button_index = self._TCA_HANDLE_CONTACTS[axis_index]
            rev_key = key_for("button", rev_index)
            reverse = canvas.create_round_rect(
                cx - 23, handle_y - 30, cx + 23, handle_y - 16, radius=4,
                fill=amber if on(rev_index) else self._control_fill(rev_key, "#5a3a2c"),
                outline=self._control_color(rev_key), width=3 if rev_key == self._selected_visual else 1,
            )
            reverse_text = canvas.create_text(cx, handle_y - 23, text="REV", fill="#0e1720" if on(rev_index) else text, font=("Segoe UI", 6, "bold"))
            for item in (reverse, reverse_text):
                self._tag(canvas, item, rev_key)
                canvas.addtag_withtag(move_tag, item)
            button_key = key_for("button", button_index)
            button_x = cx + 34.0
            button = canvas.create_oval(
                button_x - 9, handle_y - 9, button_x + 9, handle_y + 9,
                fill=live if on(button_index) else self._control_fill(button_key, metal),
                outline=self._control_color(button_key), width=3 if button_key == self._selected_visual else 1,
            )
            self._tag(canvas, button, button_key)
            canvas.addtag_withtag(move_tag, button)
            canvas.create_text(cx, track_bottom + 13.0, text=f"axis {axis_index}", fill=muted, font=("Segoe UI", 7))
            self._tca_axis_tracks[axis_key] = {
                "top": track_top,
                "bottom": track_bottom,
                "current_y": handle_y,
                "move_tag": move_tag,
            }

    def _draw_device_surface(self, canvas: tk.Canvas, width: int, height: int) -> None:
        spec = self._catalog.get(self._selected_device, {})
        detected = self._detected.get(self._selected_device, {})
        title = spec.get("title") or detected.get("product") or detected.get("title") or "Unidentified USB device"
        if not self._selected_device:
            canvas.create_text(width / 2, height / 2, text="No connected hardware", fill=MUTED, font=("Segoe UI", 16))
            return
        canvas.create_text(width / 2, 95, text=title, fill=INK, font=("Segoe UI Semibold", 18))
        notes = spec.get("notes", "")
        canvas.create_text(width / 2, 128, state="hidden", text=notes or "A visual mapping surface is ready when a driver/control map is captured.", fill=MUTED, font=("Segoe UI", 10), width=width - 100)
        controls = [item for item in spec.get("controls", []) if item.get("status") == "implemented" and item.get("direction") in {"input", "bidirectional"}]
        if not controls:
            canvas.create_text(width / 2, height / 2, text="No verified control map is available for this device yet.", fill=WARN, font=("Segoe UI", 13), justify="center")
            return
        shown = controls
        columns = 6
        rows = max(1, (len(shown) + columns - 1) // columns)
        row_step = max(42, min(72, (height - 245) / rows))
        for index, control in enumerate(shown):
            row, column = divmod(index, columns)
            x = 100 + column * max(105, (width - 200) / max(1, columns - 1))
            y = 200 + row * row_step
            key = control["key"]
            label = control["label"][:15]
            if control["kind"] in {"rotary", "axis"}:
                self._highlight_ring(canvas, x - 24, y - 24, x + 24, y + 24, key, radius=24)
                item = canvas.create_oval(x - 24, y - 24, x + 24, y + 24, fill=self._control_fill(key, "#1c2a43"), outline=self._control_color(key), width=4 if key == self._selected_visual else 3)
                self._tag(canvas, item, key)
            else:
                self._draw_button(canvas, x, y, label, key, width=90)
                continue
            text = canvas.create_text(x, y + 38, text=label, fill=INK, font=("Segoe UI", 8), width=100)
            self._tag(canvas, text, key)
        canvas.create_text(width / 2, height - 34, state="hidden", text="Every captured control is selectable here. The original bridge function stays active until you save an override in the current profile.", fill=MUTED, font=("Segoe UI", 9))

    # ----- selection, learning, binding ---------------------------------------

    def _visual_controls(self) -> Dict[str, Dict[str, Any]]:
        if self._selected_device == "fcu_32_efis":
            controls = self._fcu_controls()
            spec = self._catalog.get("fcu_32_efis", {})
            for item in spec.get("controls", []):
                key = str(item.get("key") or "")
                if key in controls:
                    controls[key]["default_role"] = item.get("default_role", "")
            return controls
        if self._selected_device == "ecam32":
            return {
                key: {"label": label, "kind": "button", "default_role": role}
                for key, label, role in ECAM32_A320_CONTROLS
            }
        # MUSLIMSIM_MOZA_AB6_CAPTURE_V1
        # The AB6 used to return three hard-coded "visual practice pose"
        # axes here, because its catalogue held nothing else. Its eight
        # axes, hat and 128 contacts are now captured from the base, so it
        # reads its own catalogue exactly as the A210 does - without which
        # none of its controls could be selected or assigned a function.
        if self._selected_device in {"moza_a210", "moza_ab6"}:
            spec = self._catalog.get(self._selected_device, {})
            return {
                str(control["key"]): {
                    "label": str(control["label"]), "kind": str(control["kind"]),
                    "default_role": str(control.get("default_role") or ""),
                }
                for control in spec.get("controls", [])
                if control.get("status") == "implemented" and control.get("direction") in {"input", "bidirectional"}
            }
        spec = self._catalog.get(self._selected_device, {})
        device = self._selected_device
        allowed_status = (
            {"implemented", "unknown", "unimplemented"}
            if device in _EXPOSE_UNVERIFIED_CONTROLS else {"implemented"}
        )
        controls = {
            control["key"]: {
                "label": control["label"],
                "kind": control["kind"],
                "default_role": control.get("default_role", ""),
                "status": control.get("status", "implemented"),
            }
            for control in spec.get("controls", [])
            if control.get("status") in allowed_status
            and control.get("direction") in {"input", "bidirectional"}
            and (device, control["key"]) not in _LEGACY_SUPERSEDED_CONTROLS
        }
        if device == "pdc_bb61_left":
            detected = getattr(self, "_detected", {}).get(device) or {}
            state = getattr(self, "_device_states", {}).get(device) or {}
            pid = detected.get("product_id") or state.get("pid")
            product = str(detected.get("product") or state.get("detail") or "")
            if pid == 0xBB51 or "3M PDC" in product.upper():
                controls.pop("map_range", None)  # Saved legacy binding remains intact.
            elif pid == 0xBB61 or "3N PDC" in product.upper():
                for key in ("vsd", "range_dec", "range_inc"):
                    controls.pop(key, None)
        if device == "pdc_bb62":
            from muslimsim.gui.pdc_faceplate import BB62_UNCAPTURED
            for key, label in BB62_UNCAPTURED.items():
                controls.setdefault(key, {"label": label, "kind": "button", "default_role": "", "status": "unknown"})
        return controls

    def _learned(self) -> Dict[str, str]:
        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        return dict(profile.get("learned", {}).get(self._selected_device, {}) or {})

    def _custom_label(self, visual_key: str) -> str:
        """An owner-typed display name for one control, if one was saved."""

        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        labels = profile.get("labels", {}).get(self._selected_device, {}) or {}
        return str(labels.get(visual_key, "") or "")

    def _rename_selected(self) -> None:
        if not self._selected_visual:
            self.footer.set("Choose a visual control first.")
            return
        current = self._custom_label(self._selected_visual)
        chosen = simpledialog.askstring(
            "Name this control",
            "Type the name Studio should show for this control (leave blank to use its original name):",
            initialvalue=current, parent=self,
        )
        if chosen is None:
            return
        device, visual = self._selected_device, self._selected_visual

        def applied(_result: Dict[str, Any]) -> None:
            self._show_selection()
            self._draw_faceplate()
            self.footer.set(
                f"Renamed to \"{chosen.strip()}\"." if chosen.strip() else "Restored the original name."
            )

        self._request("label_set", device=device, visual=visual, label=chosen, done=applied)

    def _learned_source(self, visual_key: str) -> str:
        learned = self._learned().get(visual_key, "")
        if learned:
            return learned
        if self._selected_device == "pdc_bb62":
            from muslimsim.gui.pdc_faceplate import BB62_UNCAPTURED
            if visual_key in BB62_UNCAPTURED:
                return ""  # No guessed bit for a new faceplate location.
        if self._selected_device in {"moza_a210", "moza_ab6"}:
            # Both bases now have a capture-proven HID report, read from
            # the hardware. Generic contact numbers stay names rather than
            # guessed physical legends, but they are safe mapping sources.
            # The AB6 branch used to return "" - correct while it had only
            # a preset, and the reason nothing on it could be assigned.
            return visual_key if visual_key in self._visual_controls() else ""
        if self._selected_device == "ecam32":
            # A BB70 report bit has no trustworthy Airbus label until the
            # owner records that exact physical press.  Never fall back to a
            # same-named semantic key or to the old packet-order guess.
            return self._learned().get(visual_key, "")
        if self._selected_device == "fcu_32_efis":
            # BA01 now has a direct physical identity. Older profiles may
            # still retain a migrated Learn assignment, but all known visual
            # controls point to themselves without requiring a Learn step.
            return visual_key if visual_key in self._visual_controls() else self._learned().get(visual_key, "")
        # A named faceplate location may deliberately learn a different raw
        # control (e.g. an older saved profile's migrated Learn assignment).
        # Prefer that stored relation; every other captured control - known
        # or still-unverified, see _EXPOSE_UNVERIFIED_CONTROLS - keeps its
        # own physical identity and needs no separate Learn step.
        learned = self._learned().get(visual_key, "")
        return learned or (visual_key if visual_key in self._visual_controls() else "")

    def _cancel_tca_practice_routes(self) -> None:
        """Invalidate queued virtual positions before leaving Practice."""

        with self._tca_route_lock:
            self._tca_route_epoch += 1
            self._tca_route_latest.clear()
            # An older worker observes the epoch mismatch and exits.  Clearing
            # this flag lets the first sample in the new Test session start a
            # fresh worker without waiting for a Tk completion callback.
            self._tca_route_worker_running = False

    def _drain_tca_practice_routes(self, client: Any, epoch: int) -> Dict[str, Any]:
        """Coalesce high-rate pointer samples without touching the Tk thread."""

        sent: Dict[str, int] = {}
        delivered = 0
        last_send = 0.0
        try:
            while True:
                with self._tca_route_lock:
                    if epoch != self._tca_route_epoch:
                        return {"sent": delivered, "cancelled": True}
                    pending = [
                        (entry[0], key)
                        for key, entry in self._tca_route_latest.items()
                        if entry[3] == epoch and entry[0] > sent.get(key, -1)
                    ]
                    if not pending:
                        self._tca_route_worker_running = False
                        return {"sent": delivered, "cancelled": False}
                    _sequence, key = min(pending)

                delay = self._TCA_AXIS_INTERVAL - (time.monotonic() - last_send)
                if delay > 0.0:
                    time.sleep(delay)

                # Re-read after pacing: all intermediate samples for this
                # lever collapse into the newest one before the socket write.
                with self._tca_route_lock:
                    if epoch != self._tca_route_epoch:
                        return {"sent": delivered, "cancelled": True}
                    sequence, value, phase, item_epoch = self._tca_route_latest[key]
                    if item_epoch != epoch:
                        continue
                client.request(
                    "lab_input",
                    device="tca_boeing",
                    control=key,
                    value=value,
                    phase=phase,
                    practice_only=True,
                )
                sent[key] = sequence
                delivered += 1
                last_send = time.monotonic()
        finally:
            with self._tca_route_lock:
                # A newer epoch may already have started its own worker.
                if epoch == self._tca_route_epoch:
                    self._tca_route_worker_running = False

    def _queue_tca_practice_route(self, visual_key: str, value: float, *, final: bool) -> None:
        """Keep one newest continuous value and start one ordered sender."""

        client = self.supervisor.client
        if client is None or str(self._lab.get("mode") or "") != "test":
            return
        with self._tca_route_lock:
            previous = self._tca_route_latest.get(visual_key)
            if (
                not final
                and previous is not None
                and abs(float(value) - float(previous[1])) < self._TCA_AXIS_DEADBAND
            ):
                return
            self._tca_route_sequence += 1
            epoch = self._tca_route_epoch
            self._tca_route_latest[visual_key] = (
                self._tca_route_sequence,
                float(value),
                "change",
                epoch,
            )
            if self._tca_route_worker_running:
                return
            self._tca_route_worker_running = True
        future = self._workers.submit(self._drain_tca_practice_routes, client, epoch)
        self._collect_future(future, lambda _result: None)

    def _set_tca_practice_axis(self, visual_key: str, event_y: float, *, final: bool = False) -> bool:
        """Move one handle immediately and post its exact continuous raw value."""

        if (
            not self.practice_mode.get()
            or self._selected_device != "tca_boeing"
            or visual_key not in self._tca_axis_tracks
        ):
            return False
        track = self._tca_axis_tracks[visual_key]
        top = float(track["top"])
        bottom = float(track["bottom"])
        y = max(top, min(bottom, float(event_y)))
        current_y = float(track["current_y"])
        delta = y - current_y
        if abs(delta) > 0.0001:
            self.faceplate.move(str(track["move_tag"]), 0.0, delta)
            track["current_y"] = y
        span = max(1.0, bottom - top)
        # Exact inverse of the working live display: top=-1, bottom=+1.
        raw_value = -1.0 + 2.0 * ((y - top) / span)
        self._tca_practice_axes[visual_key] = raw_value
        selected_changed = self._selected_visual != visual_key
        self._selected_visual = visual_key
        if selected_changed:
            self._show_selection()
            self.footer.set(
                "TCA Practice lever follows the pointer continuously; the aircraft remains isolated in Test mode."
            )
        self._queue_tca_practice_route(visual_key, raw_value, final=final)
        return True

    def _faceplate_drag(self, event: tk.Event[Any]) -> Optional[str]:
        visual_key = self._tca_drag_axis
        if visual_key and self._set_tca_practice_axis(visual_key, float(event.y)):
            return "break"
        return None

    def _faceplate_release(self, event: tk.Event[Any]) -> Optional[str]:
        visual_key = self._tca_drag_axis
        self._tca_drag_axis = None
        if visual_key and self._set_tca_practice_axis(visual_key, float(event.y), final=True):
            # One release redraw refreshes selection outlines and button poses;
            # no full-canvas redraw occurs during pointer motion.
            self._draw_faceplate()
            return "break"
        return None

    # Tapping the APU EGT gauge drives the real P4 field of the COM5 OVHD
    # frame, so the gauge can be proven to move at all.  ``lab_output`` writes
    # exactly one control; ``lab_output_test`` with action "values" would zero
    # every output missing from the payload and blank the altitude windows,
    # lamps and backlight along with it.
    PU_EGT_TEST_STEPS = (0.0, 25.0, 50.0, 75.0, 100.0)

    def _pu_egt_test_step(self) -> str:
        """Send the next APU EGT test value to the physical gauge."""

        if not self.practice_mode.get():
            self.footer.set(
                "Turn Practice on to drive the physical APU EGT gauge from this tap."
            )
            return "break"
        steps = self.PU_EGT_TEST_STEPS
        index = (getattr(self, "_pu_egt_test_index", -1) + 1) % len(steps)
        self._pu_egt_test_index = index
        value = steps[index]
        # Above 1.0 the bridge treats the number as an explicit APU
        # temperature; egt-mid-temp defaults to 50, so 50 is a settled EGT
        # and 100 is around the start peak.
        self.footer.set(f"APU EGT test: sending {value:g} to the panel…")
        self._request(
            "lab_output",
            device="pu_overhead",
            control="apu_egt",
            value=value,
            done=lambda _result, sent=value: self.footer.set(
                f"APU EGT test: sent {sent:g} (OVHD field P4). Tap the gauge again for the next step."
            ),
        )
        return "break"

    def _faceplate_click(self, _event: tk.Event[Any]) -> Optional[str]:
        if self._selected_device == "tca_boeing":
            self._tca_drag_axis = None
        current = self.faceplate.find_withtag("current")
        for item in current:
            for tag in self.faceplate.gettags(item):
                if tag == "pu_egt_test":
                    return self._pu_egt_test_step()
                if tag.startswith("capture:"):
                    target = tag.partition(":")[2]
                    if self.practice_mode.get() and self._learned_source(target):
                        self._activate_visual(target, physical=False)
                    elif self._selected_device in _CAPTURE_LIVE_DISCOVERY_DEVICES:
                        # Always arm capture on click — re-assigns a previously
                        # captured button just as easily as a fresh one.
                        self._start_live_capture(target)
                    else:
                        self._selected_visual = target
                        self._show_selection()
                        self._draw_faceplate()
                    return
                if tag.startswith("control:"):
                    visual_key = tag.partition(":")[2]
                    if (
                        self.practice_mode.get()
                        and self._selected_device == "tca_boeing"
                        and visual_key in self._tca_axis_tracks
                    ):
                        self._tca_drag_axis = visual_key
                        self._set_tca_practice_axis(visual_key, float(_event.y), final=True)
                        return "break"
                    # TERR ON ND is the one dedicated AGP RADIO/NAV mode
                    # switch. In Live, a software click requests the same
                    # bridge-owned mode used by the physical TERR contact.
                    # It is the only Live faceplate control that operates
                    # immediately; every other Live click remains selection-only.
                    if (
                        not self.practice_mode.get()
                        and self._selected_device == "agp_bb80"
                        and visual_key == "terr_on_nd"
                    ):
                        mirror = self._device_mirror("agp_bb80")
                        current_mode = str(
                            mirror.get("page") or "radio"
                        ).strip().lower()
                        wanted = (
                            "navigation"
                            if current_mode != "navigation"
                            else "radio"
                        )
                        self.footer.set(
                            f"AGP mode request: {wanted.upper()}…"
                        )
                        self._request(
                            "lab_output",
                            device="agp_bb80",
                            control="display_mode",
                            value=wanted,
                            done=lambda _result, mode=wanted: self.footer.set(
                                f"AGP mode: {mode.upper()} — TERR ON ND is the only mode selector."
                            ),
                        )
                        return "break"

                    # In Practice mode the faceplate is an operating panel:
                    # a click both selects and moves the virtual control.
                    # Other Live controls remain selection-only so a mapping
                    # review cannot accidentally change a real aircraft. The
                    # Moza A210/AB6 calibration panel is exempt from that
                    # restriction: its controls (physics gain sliders, base/
                    # yoke tab, preset selection) tune the yoke's own force-
                    # feedback hardware, not an aircraft system, and
                    # _activate_moza_visual() already sends every one of them
                    # through the real bridge regardless of mode - proven live
                    # this session via moza_ay210_ffb_engine.py's physics
                    # override path, which has no mode gate of its own.
                    # The ToLiss calibration button is likewise a guarded
                    # device-configuration action, not an aircraft control;
                    # its bridge path freezes thrust and re-arms pickup.
                    if (
                        self.practice_mode.get()
                        or self._selected_device in {"moza_a210", "moza_ab6"}
                        or (
                            self._selected_device == "winctrl_throttle"
                            and visual_key.startswith(
                                "toliss_throttle_calibration_"
                            )
                        )
                    ):
                        self._activate_visual(visual_key, physical=False)
                    else:
                        self._selected_visual = visual_key
                        self._show_selection()
                        self._draw_faceplate()
                    return None
        return None

    def _refresh_spare_controls(self) -> None:
        """Populate the "other physical contact" picker for the current device."""

        device = self._selected_device
        if device in _EXPOSE_UNVERIFIED_CONTROLS:
            entries = sorted(
                (key, str(info.get("label") or key))
                for key, info in self._visual_controls().items()
                if str(info.get("status", "implemented")) != "implemented"
            )
        elif device == "ecam32":
            entries = sorted(
                (key, str(info.get("label") or key))
                for key, info in self._visual_controls().items()
                if key in _ECAM32_OFF_PANEL_CONTROLS
            )
        else:
            entries = []
        if not entries:
            self._spare_control_by_display = {}
            self.spare_control_name.set("")
            self.spare_control_picker.configure(values=(), state="disabled")
            self.spare_control_label.configure(
                text="This device has no unidentified physical contacts left."
            )
            return
        self._spare_control_by_display = {f"{label}  ({key})": key for key, label in entries}
        display_values = tuple(self._spare_control_by_display)
        self.spare_control_picker.configure(values=display_values, state="readonly")
        self.spare_control_label.configure(
            text=f"Other physical contacts with no confirmed legend yet ({len(entries)}):"
        )
        if self.spare_control_name.get() not in display_values:
            self.spare_control_name.set("")

    def _select_spare_control(self, _event: object = None) -> None:
        key = self._spare_control_by_display.get(self.spare_control_name.get())
        if not key:
            return
        self._selected_visual = key
        self._show_selection()
        self._draw_faceplate()

    def _show_selection(self) -> None:
        # Only AGP retains the small explanatory control-setup caption.
        note_label = getattr(self, "selection_note_label", None)
        if note_label is not None:
            if self._selected_device == "agp_bb80":
                note_label.pack(anchor="w", pady=(10, 16), before=self.device_activation_button.master)
            else:
                note_label.pack_forget()

        self._refresh_spare_controls()
        if not self._selected_visual:
            self.capture_button.state(("disabled",))
            self.selection_title.set("Select a control on the panel")
            self.selection_source.set("")
            self.selection_note.set("Click a button, switch or knob on the visual panel to configure it.")
            return
        if (
            self._selected_device in {"moza_a210", "moza_ab6"}
            and self._selected_visual not in self._visual_controls()
        ):
            selected = self._selected_visual
            if selected.startswith("moza_view:"):
                page = selected.partition(":")[2]
                label = {
                    "base": "A210 base layout",
                    "yoke": "Detachable yoke layout",
                    "max3": "MAX3 grip reference",
                }.get(page, "Moza reference layout")
                note = "This changes only the 2D faceplate view. It does not create an unverified hardware mapping."
            elif selected.startswith("moza_preset:"):
                preset_id = selected.partition(":")[2]
                label = str(MOZA_UI_PRESETS.get(preset_id, {}).get("title") or "Captured Moza preset")
                note = "This owner-supplied Moza preset is selected and saved in the current MuslimSim profile."
            elif selected.startswith("moza_axis:"):
                axis = selected.split(":", 2)[1].upper()
                label = f"{axis} visual practice pose"
                note = "This moves the 2D calibration pose only. Map the live captured axis of the same name instead; it is listed as a normal control on this device."
            elif selected.startswith("moza_toggle:") or selected.startswith("moza_adjust:"):
                parts = selected.split(":")
                key = parts[1] if len(parts) > 1 else "setting"
                label = key.replace("_", " ").upper()
                note = "This captured-preset setting is saved per MuslimSim profile. Studio does not send an unverified Moza motor command."
            elif selected in self._visual_controls():
                # MUSLIMSIM_MOZA_AB6_CAPTURE_V1: this was A210-only, so an
                # AB6 contact fell through to "Moza visual calibration
                # control" and never said it could be mapped. Both bases
                # now have a capture-proven report.
                info = self._visual_controls()[selected]
                label = str(info.get("label") or selected)
                if selected.startswith("button_"):
                    note = "This is a live, capture-proven HID button contact. Its physical legend has not been guessed; choose any simulator role to map it."
                elif selected == "hat":
                    note = "This live, capture-proven HID hat switch is ready to map. Its selected detent is shown in the 2D panel."
                else:
                    note = "This live, capture-proven HID axis is shown in the 2D panel and is ready to map."
            else:
                label = selected.replace("_", " ").upper()
                note = "Moza visual calibration control."
            self.capture_button.state(("disabled",))
            self.selection_title.set(label)
            self.selection_source.set(
                f"Physical source: {selected}" if self._selected_device == "moza_a210" and selected in self._visual_controls()
                else "Source: owner-supplied Moza .preset"
            )
            self.selection_note.set(note)
            return
        info = self._visual_controls().get(
            self._selected_visual, {"label": self._selected_visual},
        )
        source = self._learned_source(self._selected_visual)
        # Every input faceplate can learn a new physical source. Device-specific
        # calibration widgets and outputs are not input faceplate locations.
        capturable = self._selected_visual in self._visual_controls()
        self.capture_button.state(("!disabled",) if capturable else ("disabled",))
        self.capture_button.configure(text="Assign hardware button")
        original_label = str(info.get("label", self._selected_visual))
        custom_label = self._custom_label(self._selected_visual)
        self.selection_title.set(custom_label or original_label)
        self.selection_source.set(
            (f"Physical source: {source}" if source else "Physical source: unavailable")
            + (f"  •  original name: {original_label}" if custom_label else "")
        )
        if not source:
            if capturable:
                note = "Click Assign hardware button, then press or move the physical control before choosing its simulator function."
            else:
                note = "This visual element has no verified hardware source yet, so MuslimSim will not assign it a simulator role."
        else:
            active = self._profile.get("active_profile")
            profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
            custom = dict(profile.get("bindings", {}).get(f"{self._selected_device}.{source}", {}) or {})
            # X-Plane defaults are never shown as an MSFS suggestion. The
            # MSFS workspace starts from the imported aircraft catalogue and
            # only shows a role after the owner saves one there.
            original = (
                str(info.get("default_role") or "")
                if (
                    self.simulator_mode.get() == SIMULATOR_XPLANE
                    and self.xplane_aircraft.get() == AIRCRAFT_ZIBO
                )
                else ""
            )
            if custom:
                if str(custom.get("kind")) == "disabled":
                    note = "This control is disabled in the active profile. Restore the profile to return to the original bridge role."
                else:
                    mechanical = str(custom.get("mechanical") or "standard")
                    suffix = " It uses the confirmed spring return." if mechanical == "spring_return" else ""
                    note = f"Custom role: {custom.get('target') or custom.get('kind')}.{suffix} Choose a new function whenever you like."
            elif original:
                note = f"Original role: {original}. Choose simulator action only if you want this profile to replace it."
            elif str(info.get("status", "implemented")) != "implemented":
                note = "This hardware position has a fixed identity but no confirmed real-world legend yet. Choose a simulator function, then press the matching physical control and watch it light up here to confirm you picked the right one."
            else:
                note = (
                    "This visual control animates with its learned hardware input. Choose an imported MSFS 2024 function when you are ready."
                    if self.simulator_mode.get() == SIMULATOR_MSFS24 else
                    "This visual control animates with its learned hardware input. You can remap it whenever you like."
                )
        self.selection_note.set(note)
        self._update_reset_button_visibility()

    def _begin_learn(self) -> None:
        if not self._selected_visual:
            self.footer.set("Choose a control on the panel first.")
            return
        if self._selected_visual in self._visual_controls():
            self._start_live_capture(self._selected_visual)
            return
        self.footer.set("Select a control and press its physical button to assign it.")

    def _start_live_capture(self, target: str) -> None:
        """Assign one input location from the existing physical event stream."""
        if self.practice_mode.get():
            self.footer.set("Switch to Live to save a hardware assignment.")
            return

        info = self._visual_controls().get(target)
        if info is None:
            return
        device = self._selected_device
        label = info.get("label", target)
        self._selected_visual = target
        self._capture_target = target
        self._capture_device = device
        self._capture_started = time.time()
        self.footer.set(
            f"Capture armed for {label} — press or move its physical control once to assign it."
        )
        self._show_selection()
        self._draw_faceplate()

    def _map_selected(self) -> None:
        if not self._selected_visual:
            self.footer.set("Choose a visual control first.")
            return
        source = self._learned_source(self._selected_visual)
        if not source:
            self.footer.set("This visual item has no verified physical input and cannot be mapped yet.")
            return
        self._open_mapping_dialog(source)

    def _test_selected(self) -> None:
        if not self._selected_visual:
            self.footer.set("Choose a visual control first.")
            return
        self._activate_visual(self._selected_visual, physical=False)

    def _queue_ecam_output(self, control: str, value: int) -> None:
        """Send a capture-proven ECAM output without blocking the Tk loop."""

        self._request(
            "lab_output", device="ecam32", control=control, value=value,
            done=lambda _result: None,
        )

    def _save_moza_calibration(self, values: Dict[str, Any], message: str) -> None:
        """Persist a validated captured-preset calibration through loopback."""

        device = self._selected_device
        active = str(self._profile.get("active_profile") or "Default")
        profiles = self._profile.setdefault("profiles", {})
        profile = profiles.setdefault(active, {}) if isinstance(profiles, dict) else {}
        if isinstance(profile, dict):
            profile.setdefault("calibration", {})[device] = dict(values)
        self._request("calibration_set", device=device, values=values, done=lambda _result: None)
        self.footer.set(message)

    def _activate_moza_visual(self, visual_key: str, *, physical: bool) -> bool:
        """Operate the Moza calibration page without inventing a HID path."""

        if physical:
            return True
        device = self._selected_device
        values = self._moza_calibration_values(device)
        if visual_key.startswith("moza_view:"):
            page = visual_key.partition(":")[2]
            # MAX3 lives under the AB6 tab set now (it mounts on the AB6
            # base on this rig); A210 keeps its own base/yoke pages.
            valid_pages = {
                "moza_a210": {"base", "yoke"},
                "moza_ab6": {"base", "max3"},
            }.get(device)
            if valid_pages is None or page not in valid_pages:
                return True
            self._moza_layout_page[device] = page
            self.footer.set({
                "base": "AB6 base faceplate shown." if device == "moza_ab6" else "A210 base faceplate shown.",
                "yoke": "Detachable yoke faceplate shown.",
                "max3": "MAX3 grip reference shown; no separate USB protocol has been assumed.",
            }[page])
            return True
        if visual_key.startswith("moza_preset:"):
            self._moza_ffb_picker()["open"] = False
            preset_id = visual_key.partition(":")[2]
            try:
                values = effective_moza_calibration(device, {"preset_id": preset_id})
            except ValueError:
                self.footer.set("That preset does not belong to this Moza base.")
                return True
            self._save_moza_calibration(values, "Captured Moza preset selected and saved to this profile.")
            # This preset card is also one of the two real, reinterpreted
            # .mslm profiles built from the same owner-supplied preset (see
            # MOZA_FFB_PRESET_ID_TO_MSLM) - ask the live FFB engine to load
            # it too, not just the local reference copy.
            mslm_name = MOZA_FFB_PRESET_ID_TO_MSLM.get(preset_id)
            if device == "moza_a210" and mslm_name:
                self._moza_ffb_select_profile(mslm_name)
            return True
        if visual_key == "moza_restore":
            values = effective_moza_calibration(device, {"preset_id": str(values.get("preset_id") or "")})
            self._save_moza_calibration(values, "Moza settings restored to the selected captured preset.")
            return True
        if visual_key.startswith("moza_axis:"):
            _prefix, axis, raw_direction = visual_key.split(":", 2)
            try:
                direction = int(raw_direction)
            except ValueError:
                direction = 0
            state = self._moza_practice_axes.setdefault(device, {"axis_x": .5, "axis_y": .5, "axis_z": .5})
            if axis in state:
                state[axis] = max(0.0, min(1.0, round(float(state[axis]) + direction * .10, 2)))
            self.footer.set("Moza 2D practice pose moved. It is not presented as a physical HID reading.")
            return True
        if visual_key.startswith("moza_toggle:"):
            key = visual_key.partition(":")[2]
            if key not in values:
                return True
            values[key] = not bool(values[key])
            self._save_moza_calibration(values, f"{key.replace('_', ' ').title()} saved for this profile.")
            return True
        if visual_key.startswith("moza_adjust:"):
            _prefix, key, raw_delta = visual_key.split(":", 2)
            if key not in values:
                return True
            try:
                delta = int(raw_delta)
            except ValueError:
                delta = 0
            values[key] = max(0, min(100, int(values[key]) + delta))
            self._save_moza_calibration(values, f"{key.replace('_', ' ').title()} saved for this profile.")
            return True
        if visual_key.startswith("moza_ffb_adjust:"):
            _prefix, field, raw_delta = visual_key.split(":", 2)
            if field not in {f for _, f in MOZA_FFB_PHYSICS_FIELDS}:
                return True
            try:
                delta = int(raw_delta)
            except ValueError:
                delta = 0
            new_value = self._moza_ffb_physics_value(field) + delta
            self._moza_ffb_physics_command(field, new_value)
            return True
        if visual_key.startswith("moza_ffb_effect_adjust:"):
            _prefix, effect_id, raw_delta = visual_key.split(":", 2)
            try:
                delta = int(raw_delta)
            except ValueError:
                delta = 0
            new_value = self._moza_ffb_effect_gain_value(effect_id) + delta
            self._moza_ffb_effect_gain_command(effect_id, new_value)
            return True
        if visual_key == "moza_ffb_preset_toggle":
            self._moza_ffb_picker()["open"] = not self._moza_ffb_picker()["open"]
            if self._moza_ffb_picker()["open"]:
                self._moza_ffb_list_profiles()
            return True
        if visual_key.startswith("moza_ffb_preset_select:"):
            name = visual_key.partition(":")[2]
            self._moza_ffb_picker()["open"] = False
            self._moza_ffb_select_profile(name)
            return True
        if visual_key == "moza_feedback_window":
            from .moza_feedback_window import FeedbackWindow
            windows = getattr(self, "_moza_feedback_windows", {})
            window = windows.get(device)
            if window is not None and window.winfo_exists():
                window.lift()
            else:
                windows[device] = FeedbackWindow(self, device)
                self._moza_feedback_windows = windows
            return True
        if visual_key == "moza_ffb_browse":
            self._moza_ffb_picker()["open"] = False
            self._moza_ffb_browse_profile()
            return True
        if visual_key == "moza_ffb_new_preset":
            self._moza_ffb_picker()["open"] = False
            self._open_moza_ffb_new_preset_dialog()
            return True
        return False

    def _activate_visual(self, visual_key: str, *, physical: bool) -> None:
        # Physical and virtual input both choose the exact faceplate item.  A
        # bright live flash identifies the press, while the gold selection
        # remains until another control is chosen for mapping.
        self._selected_visual = visual_key
        self._flash_until[visual_key] = time.monotonic() + 1.10
        if self._selected_device in {"moza_a210", "moza_ab6"}:
            if self._activate_moza_visual(visual_key, physical=physical):
                self._show_selection()
                self._draw_faceplate()
                return
        if (
            self._selected_device == "winctrl_throttle"
            and visual_key in {
                "toliss_throttle_calibration_start",
                "toliss_throttle_calibration_cancel",
            }
            and not physical
        ):
            action = (
                "start_toliss_throttle_calibration"
                if visual_key.endswith("start") else
                "cancel_toliss_throttle_calibration"
            )

            def calibration_result(result: Dict[str, Any]) -> None:
                if self._device_command_ok(result):
                    self.footer.set(
                        "Calibration started: sweep both levers from FULL REV "
                        "through REV IDLE, IDLE, CL, FLEX/MCT, and TOGA."
                        if action.startswith("start") else
                        "ToLiss throttle calibration cancelled; the previous "
                        "saved gates remain active."
                    )
                else:
                    self.footer.set(
                        "ToLiss throttle calibration failed: "
                        + self._device_command_error(result)
                    )
                self._redraw_pending = True

            self._request(
                "device_command", device="winctrl_throttle", action=action,
                payload={}, done=calibration_result,
            )
            self._draw_faceplate()
            return
        if (
            self._selected_device == "winctrl_throttle"
            and visual_key in WINCTRL_THROTTLE_OUTPUT_KEYS
            and not physical
        ):
            # Output tiles are a safe laboratory surface, not mapping
            # sources.  Do not fall through to lab_input or offer a guessed
            # simulator command for a lamp, backlight, or vibration motor.
            self._activate_throttle_output(visual_key)
            self.footer.set("Throttle output test sent through the bridge; the tile reflects the confirmed test state.")
            self._show_selection()
            self._draw_faceplate()
            return
        info = self._visual_controls().get(visual_key, {})
        if self.practice_mode.get():
            self._preview.activate(
                self._selected_device, visual_key, str(info.get("label") or ""),
            )
            self._preview_snapshot = dict(self._preview.snapshot())
            self._practice_outputs_dirty = True
        if self._selected_device == "fcu_32_efis":
            self._apply_fcu_efis_visual(visual_key)
        if self._selected_device == "fcu_32_efis" and info.get("kind") == "knob":
            group = str(info.get("group") or "")
            delta = int(info.get("delta") or 0)
            if group and delta:
                self._fcu_values[group] = max(0, self._fcu_values[group] + delta)
        elif self._selected_device == "pap3_mag":
            increments = {
                "course_capt_dec": ("course_capt", -1), "course_capt_inc": ("course_capt", 1),
                "speed_dec": ("speed", -1), "speed_inc": ("speed", 1),
                "heading_dec": ("heading", -1), "heading_inc": ("heading", 1),
                "altitude_dec": ("altitude", -100), "altitude_inc": ("altitude", 100),
                "vs_dec": ("vertical_speed", -100), "vs_inc": ("vertical_speed", 100),
                "course_fo_dec": ("course_fo", -1), "course_fo_inc": ("course_fo", 1),
            }
            item = increments.get(visual_key)
            if item:
                field, delta = item
                self._pap3_values[field] += delta
                if field in {"course_capt", "heading", "course_fo"}:
                    self._pap3_values[field] %= 360
                elif field == "speed":
                    self._pap3_values[field] = max(100, min(400, self._pap3_values[field]))
                elif field == "altitude":
                    self._pap3_values[field] = max(0, self._pap3_values[field])
        elif self._selected_device == "winctrl_throttle":
            if self._is_toliss_throttle_workspace() and visual_key == "trim_mode_cycle":
                roles = ("STAB", "RUDDER")
                try:
                    role_index = roles.index(self._throttle_trim_mode or "")
                except ValueError:
                    role_index = -1
                self._throttle_trim_mode = roles[(role_index + 1) % len(roles)]
                self._throttle_trim_label_until = time.monotonic() + 1.0
                self._throttle_trim_request_frame()
            elif (
                self._is_toliss_throttle_workspace()
                and visual_key in {
                    "trim_mode_crank", "trim_mode_norm", "trim_mode_ign_start",
                }
            ):
                # These are real Airbus engine-mode detents in the ToLiss
                # workspace; they must not silently change the trim role.
                self._throttle_trim_selector = visual_key
            elif visual_key in {"trim_mode_crank", "trim_mode_norm", "trim_mode_ign_start"}:
                self._set_throttle_trim_selector(visual_key)
            elif visual_key in {"rudder_trim_left", "rudder_trim_right", "rudder_trim_reset"}:
                self._apply_throttle_trim_visual(visual_key)
        elif self._selected_device == "ecam32":
            # The capture verifies the BB70 wake heartbeat.  For a learned
            # contact with a recorded lamp address, Studio also mirrors the
            # selected page to that individual real lamp.  An unrecorded
            # contact never receives a guessed LED selector.
            was_awake = self._ecam_awake
            self._ecam_awake = True
            if not was_awake:
                self._queue_ecam_output("panel_wake", 1)
            old_page = self._ecam_active_page
            if visual_key in ECAM32_A320_PAGE_KEYS:
                self._ecam_active_page = "" if self._ecam_active_page == visual_key else visual_key
                if old_page and old_page != self._ecam_active_page:
                    old_source = self._learned_source(old_page)
                    old_lamp = ECAM32_CAPTURED_CONTACT_LED_INDEX.get(old_source)
                    if old_lamp is not None:
                        self._queue_ecam_output(f"led_{old_lamp:02x}", 0)
                source = self._learned_source(visual_key)
                lamp_index = ECAM32_CAPTURED_CONTACT_LED_INDEX.get(source)
                if lamp_index is not None:
                    self._queue_ecam_output(f"led_{lamp_index:02x}", 1 if self._ecam_active_page else 0)
        elif self._selected_device == "agp_bb80":
            # RADIO/NAV display/mode behavior is owned by VirtualZibo in
            # Practice and by the bridge in Live. Keep only simple local
            # mechanical/lamp poses here; no clock/date/page fallback remains.
            if visual_key == "brake_fan_on":
                self._agp_brake_fan = True
            elif visual_key == "brake_fan_off":
                self._agp_brake_fan = False
            elif visual_key == "anti_skid_on":
                self._agp_anti_skid = True
            elif visual_key == "anti_skid_off":
                self._agp_anti_skid = False
            elif visual_key == "gear_up":
                self._agp_gear = "UP"
            elif visual_key == "gear_down":
                self._agp_gear = "DOWN"
            elif visual_key.startswith("autobrake_"):
                self._agp_autobrake = visual_key.removeprefix("autobrake_").upper()
        pu_value: int | float = 1
        pu_phase = "press"
        axis_value: int | float = 1
        axis_phase = "press"
        if self._selected_device == "pu_overhead" and not physical:
            # A visual interaction cycles/toggles using the exact same stable
            # values that the physical PU decoder emits.  The local pose is
            # updated immediately, then the bridge becomes authoritative on
            # its next fast status response.
            pu_value, pu_phase = self._pu_virtual_input(visual_key)
            self._set_pu_visual_input(visual_key, pu_value, pu_phase)
        elif (
            self._selected_device == "winctrl_throttle"
            and visual_key in {"left_thrust", "right_thrust", "speedbrake", "flap_axis"}
            and not physical
        ):
            axis_value, axis_phase = self._virtual_axis_input(visual_key)
        elif (
            self._selected_device == "winctrl_pedals"
            and visual_key in {"rudder", "left_toe_brake", "right_toe_brake"}
            and not physical
        ):
            axis_value, axis_phase = self._virtual_axis_input(visual_key)
        source = self._learned_source(visual_key)
        if source and not physical:
            value: int | float = 1
            phase = "press"
            if self._selected_device == "pu_overhead":
                value, phase = pu_value, pu_phase
            elif self._selected_device in {"winctrl_throttle", "winctrl_pedals"} and source == visual_key and info.get("kind") == "axis":
                value, phase = axis_value, axis_phase
            self._request(
                "lab_input", device=self._selected_device, control=source,
                value=value, phase=phase,
                practice_only=self._selected_device == "tca_boeing",
                done=lambda _result: None,
            )
        elif not physical:
            self.footer.set("This visual control is not identified yet. Use Identify to connect it to the real hardware.")
        self._show_selection()
        self._draw_faceplate()

    def _open_mapping_dialog(self, source: str) -> None:
        is_msfs = self.simulator_mode.get() == SIMULATOR_MSFS24
        xplane_aircraft = self.xplane_aircraft.get()
        xplane_title = xplane_aircraft_title(xplane_aircraft)
        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        current = dict(profile.get("bindings", {}).get(f"{self._selected_device}.{source}", {}) or {})
        dialog = tk.Toplevel(self)
        dialog.title("Choose MSFS 2024 function" if is_msfs else "Choose X-Plane function")
        dialog.configure(bg=PANEL)
        dialog.geometry("860x620")
        dialog.minsize(760, 520)
        dialog.transient(self)
        dialog.grab_set()
        visual_key = self._selected_visual or ""
        label = self._custom_label(visual_key) or self._visual_controls().get(visual_key, {}).get("label") or source
        source_spec = next(
            (item for item in self._catalog.get(self._selected_device, {}).get("controls", []) if item.get("key") == source),
            {},
        )
        is_axis = str(source_spec.get("kind") or "") == "axis"
        required_kind = "dataref" if is_axis else "command"
        type_label = "axis" if is_axis else "switch, button, knob or selector"
        detents = tuple(str(item) for item in source_spec.get("choices") or ())
        is_safe_spring_selector = (self._selected_device, source) in {
            ("pu_overhead", "engine_start_1"),
            ("pu_overhead", "engine_start_2"),
        }

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(3, weight=1)
        ttk.Label(dialog, text=f"{label}", style="Panel.TLabel", font=("Segoe UI Semibold", 14)).grid(row=0, column=0, padx=18, pady=(16, 2), sticky="w")
        if self._selected_device == "agp_bb80":
            ttk.Label(
                dialog,
                text=(
                    f"Physical {type_label}  •  choose its MSFS 2024 function below. Saved MSFS mappings stay separate from X-Plane."
                    if is_msfs else
                    f"Physical {type_label}  •  choose its new {xplane_title} function below. The original device role stays active until you save."
                ),
                style="PanelMuted.TLabel",
            ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")

        tools = ttk.Frame(dialog, style="Panel.TFrame")
        tools.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="ew")
        tools.columnconfigure(1, weight=1)
        ttk.Label(tools, text="Find function", style="Panel.TLabel").grid(row=0, column=0, padx=(0, 8), pady=3)
        search = tk.StringVar()
        search_box = ttk.Entry(tools, textvariable=search)
        search_box.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(tools, text="System", style="Panel.TLabel").grid(row=0, column=2, padx=(12, 6), pady=3)
        category = tk.StringVar(value="All systems")
        category_picker = ttk.Combobox(tools, textvariable=category, state="readonly", width=26)
        category_picker.grid(row=0, column=3, pady=3)
        msfs_family = msfs24_family(self.msfs_aircraft.get()) if is_msfs else None
        msfs_title = msfs24_aircraft_title(self.msfs_aircraft.get()) if is_msfs else ""
        if is_msfs and msfs_family:
            msfs_count = sum(
                1 for item in offline_msfs24_functions()
                if str(item.get("aircraft") or "") == msfs_family
            )
            msfs_note = (
                f"{msfs_title} — {msfs_count} imported {msfs_family} functions. "
                "Dispatch is not enabled yet."
            )
        else:
            msfs_note = (
                f"{msfs_title} — the imported catalogue has no functions for this "
                "aircraft yet, so nothing is listed here. Its commands have to be "
                "imported before it can be mapped."
            )
        library_note = tk.StringVar(value=(
            msfs_note
            if is_msfs else
            f"{xplane_title} catalogue — its functions and mapping profile stay inside the X-Plane workspace."
        ))
        ttk.Label(tools, textvariable=library_note, style="PanelMuted.TLabel").grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="w")

        browser = ttk.Frame(dialog, style="Panel.TFrame")
        browser.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="nsew")
        browser.columnconfigure(0, weight=1)
        browser.rowconfigure(0, weight=1)
        tree = ttk.Treeview(browser, columns=("function", "system"), show="headings", selectmode="browse")
        tree.heading("function", text="Function")
        tree.heading("system", text="Aircraft system")
        tree.column("function", width=380, anchor="w")
        tree.column("system", width=285, anchor="w")
        scrollbar = ttk.Scrollbar(browser, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        selected_note = tk.StringVar(value="Select a function from the library.")
        ttk.Label(dialog, textvariable=selected_note, style="PanelMuted.TLabel", wraplength=800).grid(row=4, column=0, padx=18, pady=(0, 8), sticky="w")

        selector_frame = ttk.Frame(dialog, style="Panel.TFrame")
        selector_frame.grid(row=5, column=0, padx=18, pady=(0, 5), sticky="ew")
        selector_frame.columnconfigure(3, weight=1)
        trigger_choice = tk.StringVar(value="")
        if detents:
            previous_trigger = current.get("trigger_value")
            try:
                trigger_choice.set(detents[int(float(previous_trigger))]) if previous_trigger is not None else trigger_choice.set(detents[0])
            except (IndexError, TypeError, ValueError):
                trigger_choice.set(detents[0])
            ttk.Label(selector_frame, text="Activate at", style="Panel.TLabel").grid(row=0, column=0, padx=(0, 8), pady=4)
            ttk.Combobox(selector_frame, textvariable=trigger_choice, values=detents, state="readonly", width=13).grid(row=0, column=1, pady=4, sticky="w")
            if self._selected_device == "agp_bb80":
                ttk.Label(selector_frame, text="Only this physical selector position sends the chosen function.", style="PanelMuted.TLabel").grid(row=0, column=2, padx=(12, 0), pady=4, sticky="w")

        spring_return = tk.BooleanVar(value=str(current.get("mechanical") or "") == "spring_return")
        if is_safe_spring_selector:
            ttk.Checkbutton(
                selector_frame,
                text="Use confirmed automatic spring return after GRD / START",
                variable=spring_return,
                command=lambda: trigger_choice.set("GRD") if spring_return.get() else None,
            ).grid(row=1, column=0, columnspan=3, pady=(2, 4), sticky="w")
            if self._selected_device == "agp_bb80":
                ttk.Label(
                    selector_frame,
                    text="This uses only the existing PU start-selector return pulse; no motor strength, direction, or endpoint is exposed.",
                    style="PanelMuted.TLabel",
                ).grid(row=2, column=0, columnspan=4, pady=(0, 3), sticky="w")

        if is_msfs:
            # Only the selected airframe's catalogue family. A PMDG command can
            # never be offered while a Fenix workspace is open, and an aircraft
            # with no imported functions lists nothing rather than everything.
            library = [
                item for item in offline_msfs24_functions(include_axes=is_axis)
                if str(item.get("kind")) == required_kind
                and msfs_family is not None
                and str(item.get("aircraft") or "") == msfs_family
            ]
        else:
            library = [
                item for item in offline_xplane_functions(xplane_aircraft, include_axes=is_axis)
                if str(item.get("kind")) == required_kind
            ]
        visible: dict[str, dict[str, Any]] = {}

        def refresh_categories() -> None:
            values = ["All systems"] + sorted({str(item.get("category") or "Other") for item in library})
            category_picker.configure(values=values)
            if category.get() not in values:
                category.set("All systems")

        def populate() -> None:
            visible.clear()
            for item_id in tree.get_children():
                tree.delete(item_id)
            query = search.get().strip()
            system = category.get()
            items = (
                search_msfs24_functions(library, query, limit=1000)
                if is_msfs else search_xplane_functions(library, query, limit=1000)
            )
            if system != "All systems":
                items = [item for item in items if str(item.get("category") or "Other") == system]
            for index, item in enumerate(items):
                row_id = f"function-{index}"
                visible[row_id] = item
                tree.insert("", "end", iid=row_id, values=(item.get("label") or "Unnamed function", item.get("category") or "Other"))
            if not items:
                selected_note.set(
                    "No matching MSFS 2024 function. Try the aircraft, system, switch or action name."
                    if is_msfs else
                    "No matching function. Try a broader word, or start the simulator and refresh its aircraft library."
                )

        def chosen(_event: object = None) -> None:
            picked = tree.selection()
            item = visible.get(picked[0]) if picked else None
            if not item:
                return
            description = str(item.get("description") or "")
            selected_note.set(f"Selected: {item.get('label')} — {description}")

        def receive_library(response: Dict[str, Any]) -> None:
            if not dialog.winfo_exists():
                return
            response_items = response.get("functions") if isinstance(response, dict) else None
            loaded = [
                dict(item) for item in list(response_items or ()) if isinstance(item, dict)
                and str(item.get("kind")) == required_kind
            ]
            if loaded:
                library[:] = loaded
                refresh_categories()
                populate()
            source_name = str(response.get("source") or "built-in") if isinstance(response, dict) else "built-in"
            total = int(response.get("total") or len(library)) if isinstance(response, dict) else len(library)
            if source_name == "catalogue-msfs24":
                library_note.set(f"MSFS 2024 catalogue • {total} imported functions. They can be saved now; aircraft dispatch is not enabled yet.")
            elif source_name == "live-x-plane":
                library_note.set(f"Live {xplane_title} library • {total} functions available. Search by cockpit system, switch, or action.")
            elif source_name == "installed-zibo":
                library_note.set(f"Installed Zibo command library • {total} functions available without starting X-Plane.")
            elif source_name == "catalogue-xplane-zibo":
                library_note.set(f"Zibo X-Plane catalogue • {total} documented and installed choices. Start Zibo to load its live command library.")
            elif source_name == "catalogue-xplane-toliss":
                library_note.set(f"ToLiss X-Plane catalogue • {total} verified command choices. It is never shown in MSFS 2024.")
            elif source_name == "catalogue-xplane-levelup":
                library_note.set(f"LevelUp X-Plane compatibility catalogue • {total} choices. Verify against the installed LevelUp variant before live use.")
            elif source_name == "catalogue-xplane-c172ng":
                library_note.set(
                    f"AirfoilLabs C172 NG Digital catalogue • {total} installed X-Plane and G1000 commands. "
                    "Start the C172 to include any aircraft plugin commands registered live."
                )
            elif not is_msfs:
                library_note.set(f"{xplane_title} catalogue • {total} choices. Start the matching aircraft to load its live command library.")

        fetch_after: Optional[str] = None

        def request_live_library(*_args: object) -> None:
            nonlocal fetch_after
            if fetch_after is not None:
                dialog.after_cancel(fetch_after)
            def fetch() -> None:
                nonlocal fetch_after
                fetch_after = None
                self._request(
                    "function_catalog", query=search.get().strip(), limit=1000,
                    aircraft="" if is_msfs else xplane_aircraft, done=receive_library,
                )
            fetch_after = dialog.after(260, fetch)
            populate()

        search.trace_add("write", request_live_library)
        category_picker.bind("<<ComboboxSelected>>", lambda _event: populate())
        tree.bind("<<TreeviewSelect>>", chosen)
        refresh_categories()
        populate()
        search_box.focus_set()
        self._request(
            "function_catalog", query="", limit=1000,
            aircraft="" if is_msfs else xplane_aircraft, done=receive_library,
        )

        actions = ttk.Frame(dialog, style="Panel.TFrame")
        actions.grid(row=6, column=0, padx=18, pady=(5, 16), sticky="ew")

        def save() -> None:
            picked = tree.selection()
            function = visible.get(picked[0]) if picked else None
            if function is None:
                messagebox.showinfo("Choose a function", "Select one function from the library first.", parent=dialog)
                return
            payload: Dict[str, Any] = {
                "kind": required_kind,
                "target": str(function.get("target") or ""),
                "simulator": SIMULATOR_MSFS24 if is_msfs else SIMULATOR_XPLANE,
                "protocol": str(function.get("protocol") or ("xplane" if not is_msfs else "")),
            }
            if not payload["target"]:
                messagebox.showerror("Unavailable function", "The selected library item has no usable simulator target.", parent=dialog)
                return
            if detents:
                selected_detent = "GRD" if spring_return.get() and "GRD" in detents else trigger_choice.get()
                payload["trigger_value"] = float(detents.index(selected_detent))
            if spring_return.get():
                payload["mechanical"] = "spring_return"
            self._request(
                "binding_set", device=self._selected_device, control=source, binding=payload,
                done=lambda _result: (dialog.destroy(), self._refresh_profile_status("Simulator function saved.")),
            )

        def restore_original() -> None:
            self._request(
                "binding_set", device=self._selected_device, control=source, binding={"kind": "disabled"},
                done=lambda _result: (dialog.destroy(), self._refresh_profile_status("Original device function restored.")),
            )

        ttk.Button(actions, text="Clear saved mapping" if is_msfs else "Restore original device role", command=restore_original).pack(side="left")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(actions, text="Save selected function", style="Accent.TButton", command=save).pack(side="right", padx=(0, 8))

    @staticmethod
    def _device_command_ok(result: Any) -> bool:
        """"device_command"'s own action result, not the RPC's own "ok".

        server.py's device_command handler always returns the top-level
        {"ok": True, "result": entry.command(...)} once the device exists and
        accepts commands - the action's real success/failure lives one level
        down, in "result". Checking the outer "ok" alone reports success even
        when the action itself failed.
        """

        inner = result.get("result") if isinstance(result, dict) else None
        return isinstance(inner, dict) and bool(inner.get("ok"))

    @staticmethod
    def _device_command_error(result: Any) -> str:
        inner = result.get("result") if isinstance(result, dict) else None
        return str(inner.get("error") or "unknown error") if isinstance(inner, dict) else "unknown error"

    def _moza_axis_command(self, action: str, axis: str, slot_text: Optional[str] = None) -> None:
        """Send a MOZA A210 axis-assignment correction to the bridge.

        Zibo only respects X-Plane's native joystick-axis assignment, so the
        bridge auto-detects which global joystick_axis_values slot is the
        MOZA A210's roll/pitch by watching for movement (see
        MUSLIMSIM MOZA A210 NATIVE AXIS-ASSIGNMENT V1 in bridge/final.py).
        This is the correction path for when that detection gets stuck
        (ambiguous) or picks the wrong slot - set one manually, clear a bad
        assignment, or ask the bridge to try detecting again.
        """

        payload: Dict[str, Any] = {"axis": axis}
        if action == "manual":
            try:
                payload["slot"] = int(str(slot_text).strip())
            except (TypeError, ValueError):
                self.footer.set("Enter a whole number axis slot first.")
                return
        self._request(
            "device_command", device="moza_a210", action=action, payload=payload,
            done=lambda result: self.footer.set(
                "MOZA A210 axis updated."
                if self._device_command_ok(result)
                else f"MOZA A210 axis command failed: {self._device_command_error(result)}"
            ),
        )

    def _moza_ffb_diagnostics(self) -> Dict[str, Any]:
        """The live AY210 FFB engine's own diagnostics_snapshot(), if the
        bridge has --moza-ffb enabled and it reached this poll cycle -
        `control/server.py` folds a DeviceRegistration's diagnostics()
        straight into its status entry, so no separate RPC is needed."""

        state = dict(self._device_states.get("moza_a210_ffb") or {})
        diagnostics = state.get("diagnostics")
        return dict(diagnostics) if isinstance(diagnostics, dict) else {}

    def _moza_ffb_physics_value(self, field: str) -> int:
        """0-100 - the value a physics slider should currently show: the
        owner's own last click first (never waits a poll cycle to reflect
        its own action), else the live engine's last-sent byte, else the
        field's schema default."""

        if field in self._moza_ffb_physics_local:
            return self._moza_ffb_physics_local[field]
        sent = self._moza_ffb_diagnostics().get("physics_sent")
        if isinstance(sent, dict) and isinstance(sent.get(field), (int, float)):
            return int(sent[field])
        from ..hardware.ffb_profiles import PHYSICS_FIELD_DEFAULTS
        return int(round(PHYSICS_FIELD_DEFAULTS.get(field, 0.0) * 100))

    def _moza_ffb_physics_command(self, field: str, value: int) -> None:
        """Push one live physics override to the real AY210 FFB engine -
        never written back to any `.mslm` file (those stay user-authored),
        session-only, exactly like moza_ay210_ffb_engine.py's
        set_physics_override() itself promises."""

        value = max(0, min(100, int(value)))
        self._moza_ffb_physics_local[field] = value
        self._request(
            "device_command", device="moza_a210_ffb", action="set_physics",
            payload={"overrides": {field: value / 100.0}},
            done=lambda result: self.footer.set(
                f"{field.replace('_', ' ').title()} set to {value}%."
                if self._device_command_ok(result)
                else f"MOZA AY210 FFB command failed: {self._device_command_error(result)}"
            ),
        )

    def _moza_ffb_effect_gain_value(self, effect_id: str) -> int:
        """0-200 - the gain percentage an effect's row should currently
        show: the owner's own last click first, else the live engine's
        reported override, else 100% (the profile's own curve, unmodified)."""

        if effect_id in self._moza_ffb_effect_gain_local:
            return self._moza_ffb_effect_gain_local[effect_id]
        overrides = self._moza_ffb_diagnostics().get("effect_gain_overrides")
        if isinstance(overrides, dict) and isinstance(overrides.get(effect_id), (int, float)):
            return int(round(float(overrides[effect_id]) * 100))
        return 100

    def _moza_ffb_effect_gain_command(self, effect_id: str, value: int) -> None:
        """Push one live per-effect gain override to the real AY210 FFB
        engine - never written back to any `.mslm` file, session-only, same
        promise as set_physics_override()/_moza_ffb_physics_command()."""

        value = max(0, min(200, int(value)))
        self._moza_ffb_effect_gain_local[effect_id] = value
        self._request(
            "device_command", device="moza_a210_ffb", action="set_effect_gain",
            payload={"overrides": {effect_id: value / 100.0}},
            done=lambda result: self.footer.set(
                f"{effect_id.replace('_', ' ').title()} gain set to {value}%."
                if self._device_command_ok(result)
                else f"MOZA AY210 FFB command failed: {self._device_command_error(result)}"
            ),
        )

    def _moza_ffb_picker_device(self, device: Optional[str] = None) -> str:
        return "moza_ab6" if (device or self._selected_device) == "moza_ab6" else "moza_a210"

    def _moza_ffb_picker(self, device: Optional[str] = None) -> Dict[str, Any]:
        return self._moza_ffb_pickers[self._moza_ffb_picker_device(device)]

    def _moza_ffb_select_profile(self, mslm_name: str, *, device: Optional[str] = None) -> None:
        device = self._moza_ffb_picker_device(device)
        def selected(result: Any) -> None:
            if self._device_command_ok(result):
                self._moza_ffb_picker(device)["active"] = mslm_name
                if device == "moza_a210":
                    self._moza_ffb_physics_local.clear()
                self.footer.set(f"MOZA preset {mslm_name!r} selected.")
                self._draw_faceplate()
            else:
                self.footer.set(f"Preset selection failed: {self._device_command_error(result)}")
        self._request("device_command", device=device + "_ffb", action="select_profile",
                      payload={"name": mslm_name}, done=selected)

    def _moza_ffb_browse_profile(self) -> None:
        from tkinter import filedialog
        from ..hardware.ffb_profiles import default_ffb_profile_dir
        device = self._moza_ffb_picker_device()
        directory = default_ffb_profile_dir(device)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.footer.set(f"Could not open the preset folder: {exc}")
            return
        path = filedialog.askopenfilename(parent=self, title="Load MOZA .mslm preset",
                                          initialdir=str(directory),
                                          filetypes=[("MuslimSim preset", "*.mslm")])
        if not path:
            return
        def imported(result: Any) -> None:
            if not self._device_command_ok(result):
                self.footer.set(f"Preset could not be loaded: {self._device_command_error(result)}")
                return
            name = str(result["result"]["name"])
            self._moza_ffb_list_profiles(force=True, device=device)
            self._moza_ffb_select_profile(name, device=device)
        self._request("device_command", device=device + "_ffb", action="import_profile",
                      payload={"path": path}, done=imported)

    _MOZA_FFB_PROFILES_RETRY_SECONDS = 2.0

    def _moza_ffb_list_profiles(self, *, force: bool = False, device: Optional[str] = None) -> None:
        device = self._moza_ffb_picker_device(device)
        picker = self._moza_ffb_picker(device)
        now = time.monotonic()
        if not force and now - picker["fetch_at"] < self._MOZA_FFB_PROFILES_RETRY_SECONDS:
            return
        picker["fetch_at"] = now
        self._request("device_command", device=device + "_ffb", action="list_profiles",
                      payload={}, done=lambda result: self._receive_moza_ffb_profiles(result, device=device))

    def _receive_moza_ffb_profiles(self, result: Any, *, device: Optional[str] = None) -> None:
        picker = self._moza_ffb_picker(device)
        inner = result.get("result") if isinstance(result, dict) else None
        names = inner.get("profiles") if isinstance(inner, dict) else None
        if isinstance(names, list):
            picker["names"] = [str(item) for item in names]
            if "active_profile" in inner:
                picker["active"] = inner["active_profile"]
            picker["error"] = "Some preset files could not be read." if inner.get("errors") else ""
            self._draw_faceplate()

    _AIRCRAFT_DISPLAY_NAMES: Dict[str, str] = {
        AIRCRAFT_ZIBO: "Zibo 737", AIRCRAFT_LEVELUP: "LevelUp 737",
        AIRCRAFT_TOLISS: "ToLiss Airbus", AIRCRAFT_C172_NG: "C172 NG Digital",
    }

    def _moza_ffb_current_aircraft_display_name(self) -> str:
        raw = str(
            (self.msfs_aircraft if self.simulator_mode.get() == SIMULATOR_MSFS24 else self.xplane_aircraft).get() or ""
        ).strip()
        if not raw:
            return ""
        return self._AIRCRAFT_DISPLAY_NAMES.get(raw, raw.replace("_", " ").replace("-", " ").title())

    def _open_moza_ffb_new_preset_dialog(self) -> None:
        """Freeze the panel's current live physics feel into a new, named
        .mslm profile - the owner's own request to save a preset "named
        after the aircraft am running now", the same way MOZA Cockpit lets
        you save a tuning as a named profile."""

        dialog = tk.Toplevel(self)
        device = self._moza_ffb_picker_device()
        dialog.title("New MOZA AB6 FFB Preset" if device == "moza_ab6" else "New MOZA AY210 FFB Preset")
        dialog.configure(bg=PANEL)
        dialog.geometry("420x160")
        dialog.minsize(400, 150)
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(
            dialog, text="Save the current physics settings as a new preset",
            style="Panel.TLabel", font=("Segoe UI Semibold", 11),
        ).pack(padx=18, pady=(16, 4), anchor="w")
        if self._selected_device == "agp_bb80":
            ttk.Label(
                dialog,
                text="Every Spring/Damper/Inertia/... value currently shown is frozen into this preset. Effects (rumble/spring curves) start empty and can be hand-authored later.",
                style="PanelMuted.TLabel", wraplength=380, justify="left",
            ).pack(padx=18, pady=(0, 10), anchor="w")

        name_var = tk.StringVar(value=self._moza_ffb_current_aircraft_display_name())
        entry_row = ttk.Frame(dialog, style="Panel.TFrame")
        entry_row.pack(padx=18, fill="x")
        ttk.Label(entry_row, text="Name:", style="Panel.TLabel").pack(side="left")
        entry = ttk.Entry(entry_row, textvariable=name_var)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        entry.focus_set()
        entry.select_range(0, "end")

        status_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status_var, style="PanelMuted.TLabel").pack(padx=18, pady=(8, 0), anchor="w")

        button_row = ttk.Frame(dialog, style="Panel.TFrame")
        button_row.pack(padx=18, pady=(14, 16), fill="x")

        def save() -> None:
            name = name_var.get().strip()
            if not name:
                status_var.set("Enter a name first.")
                return
            status_var.set("Saving…")
            self._moza_ffb_save_new_preset(
                name, device=device,
                done=lambda ok, message: (dialog.destroy() if ok else status_var.set(message)),
            )

        ttk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(button_row, text="Save Preset", command=save).pack(side="right", padx=(0, 8))
        dialog.bind("<Return>", lambda _e: save())

    def _moza_ffb_save_new_preset(self, name: str, *, done: Callable[[bool, str], None], device: Optional[str] = None) -> None:
        device = self._moza_ffb_picker_device(device)
        self._request(
            "device_command", device=device + "_ffb", action="save_profile",
            payload={"name": name},
            done=lambda result: self._finish_moza_ffb_save_new_preset(result, name, done, device=device),
        )

    def _finish_moza_ffb_save_new_preset(self, result: Any, name: str, done: Callable[[bool, str], None], *, device: Optional[str] = None) -> None:
        device = self._moza_ffb_picker_device(device)
        ok = self._device_command_ok(result)
        if ok:
            if device == "moza_a210":
                self._moza_ffb_physics_local.clear()
            self._moza_ffb_picker(device)["active"] = name
            self._moza_ffb_list_profiles(force=True, device=device)
            self.footer.set(f"MOZA preset {name!r} saved and selected.")
        message = "" if ok else f"Save failed: {self._device_command_error(result)}"
        done(ok, message)

    def _open_moza_axis_assignment_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("MOZA A210 Axis Assignment")
        dialog.configure(bg=PANEL)
        dialog.geometry("560x380")
        dialog.minsize(520, 340)
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(
            dialog, text="MOZA A210 native axis assignment", style="Panel.TLabel",
            font=("Segoe UI Semibold", 13),
        ).pack(padx=18, pady=(16, 4), anchor="w")
        if self._selected_device == "agp_bb80":
            ttk.Label(
                dialog,
                text=(
                    "The bridge watches for movement to auto-detect which X-Plane "
                    "joystick axis slot is roll and which is pitch - the only way "
                    "Zibo actually respects a physical yoke. If detection gets "
                    "stuck or picks the wrong slot, correct it below."
                ),
                style="PanelMuted.TLabel", wraplength=510, justify="left",
            ).pack(padx=18, pady=(0, 12), anchor="w")

        rows = ttk.Frame(dialog, style="Panel.TFrame")
        rows.pack(padx=18, pady=(0, 8), fill="x")

        status_vars: Dict[str, tk.StringVar] = {}
        slot_vars: Dict[str, tk.StringVar] = {}

        def build_row(row: int, axis: str, title: str) -> None:
            base = row * 3
            ttk.Label(rows, text=title, style="Panel.TLabel", font=("Segoe UI Semibold", 10)).grid(
                row=base, column=0, columnspan=5, sticky="w", pady=(10 if row else 0, 2),
            )
            status_var = tk.StringVar(value="Loading...")
            status_vars[axis] = status_var
            ttk.Label(rows, textvariable=status_var, style="PanelMuted.TLabel", wraplength=500, justify="left").grid(
                row=base + 1, column=0, columnspan=5, sticky="w",
            )
            slot_var = tk.StringVar()
            slot_vars[axis] = slot_var
            ttk.Label(rows, text="Manual slot:", style="Panel.TLabel").grid(row=base + 2, column=0, sticky="w", pady=(4, 0))
            ttk.Entry(rows, textvariable=slot_var, width=8).grid(row=base + 2, column=1, sticky="w", pady=(4, 0), padx=(6, 12))
            ttk.Button(rows, text="Set", command=lambda a=axis: self._moza_axis_command("manual", a, slot_vars[a].get())).grid(
                row=base + 2, column=2, sticky="w", pady=(4, 0), padx=(0, 6),
            )
            ttk.Button(rows, text="Clear", command=lambda a=axis: self._moza_axis_command("clear", a)).grid(
                row=base + 2, column=3, sticky="w", pady=(4, 0), padx=(0, 6),
            )
            ttk.Button(rows, text="Redetect", command=lambda a=axis: self._moza_axis_command("redetect", a)).grid(
                row=base + 2, column=4, sticky="w", pady=(4, 0),
            )

        build_row(0, "roll", "ROLL — turn the yoke left/right")
        build_row(1, "pitch", "PITCH — push/pull the yoke")

        close_row = ttk.Frame(dialog, style="Panel.TFrame")
        close_row.pack(padx=18, pady=(16, 16), fill="x")
        ttk.Button(close_row, text="Close", command=dialog.destroy).pack(side="right")

        def refresh() -> None:
            if not dialog.winfo_exists():
                return
            state = self._device_states.get("moza_a210", {})
            assignment = state.get("axis_assignment", {}) if isinstance(state, dict) else {}
            for axis, label in (("roll", "roll"), ("pitch", "pitch")):
                info = assignment.get(axis, {}) if isinstance(assignment, dict) else {}
                status = info.get("status", "idle")
                slot = info.get("slot")
                manual = info.get("manual")
                candidates = info.get("candidate_count")
                if status == "assigned":
                    text = f"Assigned: X-Plane joystick axis slot {slot}. X-Plane now reads this axis directly."
                elif status == "detected":
                    origin = "Manually set" if manual else "Detected"
                    text = f"{origin}: slot {slot} — move {label} through its current simulator position to finish taking over."
                elif status == "detecting":
                    remaining = candidates if candidates is not None else "several"
                    text = f"Detecting… {remaining} candidate axis slot(s) remain. Keep moving {label}."
                elif status == "ambiguous":
                    text = "Lost track — no single slot matched every observed movement. Set it manually below, or move the axis through its full range again."
                elif status == "failed":
                    text = "The assignment write failed — check the bridge console for the error."
                else:
                    text = "Idle — move the yoke to start automatic detection, or set a slot manually below."
                status_vars[axis].set(text)
            dialog.after(500, refresh)

        refresh()

    # ----- status / profiles ---------------------------------------------------

    def _switch_profile(self, _event: object) -> None:
        name = self.profile_name.get().strip()
        if name:
            self._request("profile_select", name=name, done=lambda _result: self._refresh_profile_status(f"Profile: {name}"))

    def _new_profile(self) -> None:
        name = simpledialog.askstring("New profile", "Name for the new visual mapping profile:", parent=self)
        if name and name.strip():
            self._request("profile_create", name=name.strip(), copy_active=True, done=lambda _result: self._refresh_profile_status("New profile created."))

    def _device_has_custom_bindings(self, device: str) -> bool:
        """Return True if any non-disabled custom binding exists for *device*."""
        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        prefix = f"{device}."
        return any(
            str(b.get("kind") or "") not in ("disabled", "")
            for key, b in dict(profile.get("bindings") or {}).items()
            if key.startswith(prefix) and isinstance(b, dict)
        )

    def _update_reset_button_visibility(self) -> None:
        """Show the per-device reset button only when custom bindings exist."""
        try:
            if self._selected_device and self._device_has_custom_bindings(self._selected_device):
                self.device_reset_button.pack(fill="x", pady=(0, 6), after=self._test_button)
            else:
                self.device_reset_button.pack_forget()
        except tk.TclError:
            pass

    def _reset_device_bindings(self) -> None:
        """Clear all custom bindings for the current device, restoring built-in defaults."""
        device = self._selected_device
        if not device:
            return
        active = self._profile.get("active_profile")
        profile = self._profile.get("profiles", {}).get(active, {}) if active else {}
        prefix = f"{device}."
        to_clear = [
            key[len(prefix):]
            for key, b in dict(profile.get("bindings") or {}).items()
            if key.startswith(prefix) and isinstance(b, dict)
            and str(b.get("kind") or "") not in ("disabled", "")
        ]
        if not to_clear:
            self._update_reset_button_visibility()
            return
        remaining = [len(to_clear)]

        def on_done(result: Dict[str, Any]) -> None:
            updated = result.get("profile")
            if isinstance(updated, dict):
                self._profile = updated
            remaining[0] -= 1
            if remaining[0] <= 0:
                title = (self._catalog.get(device) or {}).get("title") or device
                self._refresh_profile_status(f"{title} reset to built-in defaults.")
                self._update_reset_button_visibility()
                self._show_selection()

        for control in to_clear:
            self._request(
                "binding_set", device=device, control=control,
                binding={"kind": "disabled"}, done=on_done,
            )

    def _restore_profile(self) -> None:
        if messagebox.askyesno("Restore profile", "Remove this profile's mappings, learned controls, safe calibration, and restore every device to running?", parent=self):
            self._request("restore_defaults", done=lambda _result: self._refresh_profile_status("Profile restored."))

    def _refresh_profile_status(self, message: str) -> None:
        self.footer.set(message)
        self._request("status", done=self._receive_status)

    def _clear_connection_banner(self) -> None:
        """Take down a control-channel banner, and only that.

        A real message the owner still needs - an output test result, a mapping
        confirmation, a panel fault location - must survive an unrelated status
        poll recovering, so only the transient banners are replaced.
        """

        try:
            if self.footer.get() in CONNECTION_BANNERS:
                self.footer.set(CONNECTION_RECOVERED_FOOTER)
        except tk.TclError:
            pass

    def _receive_status(self, response: Dict[str, Any]) -> None:
        self._status_pending = False
        # MUSLIMSIM_CONNECTION_BANNER_V1
        # Resetting the counter was never enough: the banner those
        # failures raised is footer text and stayed up for the rest of the
        # session. A working poll retires its own complaint.
        if self._control_failures:
            self._clear_connection_banner()
        self._control_failures = 0
        # The bridge includes this short-lived read-only snapshot with every
        # status reply.  This is the reliable fallback when the UI Python has
        # no HID library or the first explicit scan raced bridge startup.
        hardware_inventory = response.get("hardware_discovery")
        if isinstance(hardware_inventory, dict):
            self._receive_bridge_discovery(hardware_inventory)
        self._device_states = {
            str(key): dict(value)
            for key, value in dict(response.get("devices") or {}).items()
            if isinstance(value, dict)
        }
        self._bridge_detected_at = time.monotonic()
        absent_devices: set[str] = set()
        bridge_detected: Dict[str, Dict[str, Any]] = {}
        for key, state in self._device_states.items():
            if hardware_presence(state) is False:
                absent_devices.add(key)
            spec = self._catalog.get(key)
            if spec is None or hardware_presence(state) is not True:
                continue
            bridge_detected[key] = {
                "key": key, "title": str(spec.get("title") or key),
                "product": str(spec.get("identity") or "Bridge-observed hardware"),
                "serial": "bridge", "firmware": "—", "source": "bridge", "connected": True,
            }
        if bridge_detected != self._bridge_detected or absent_devices != getattr(self, "_absent_device_keys", set()):
            self._bridge_detected = bridge_detected
            self._absent_device_keys = absent_devices
            self._merge_detected_devices()
        lab = dict(response.get("lab") or {})
        self._lab = lab
        self._sync_live_selector_poses(lab)
        # The private bridge reads X-Plane's active .acf path. Once that
        # identity is confirmed, switch profiles exactly once so LevelUp,
        # ToLiss, and the AirfoilLabs C172 never inherit Zibo assignments.
        if self._auto_select_loaded_xplane_aircraft(lab):
            return
        self._sync_tca_practice_axes(lab)
        reported_enabled = lab.get("device_enabled")
        if isinstance(reported_enabled, dict):
            enabled = {str(key): bool(value) for key, value in reported_enabled.items()}
            if enabled != self._device_enabled:
                self._device_enabled = enabled
                self._refresh_detected_devices()
        bridge_preview = lab.get("practice_preview")
        if (
            str(lab.get("mode") or "") == "test"
            and lab.get("practice_preview_owner") == "bridge"
            and isinstance(bridge_preview, dict)
        ):
            # Physical controls reach the bridge before the UI.  Reflect its
            # authoritative practice model, not a delayed UI-side copy.
            self._preview_snapshot = {
                str(key): dict(value)
                for key, value in bridge_preview.items()
                if isinstance(value, dict)
            }
        profile = lab.get("profile")
        if isinstance(profile, dict):
            self._profile = profile
            profiles = profile.get("profiles") or {}
            active = str(profile.get("active_profile") or "Default")
            self.profile_picker.configure(values=tuple(str(item) for item in profiles))
            if self.profile_name.get() != active:
                self.profile_name.set(active)
            self._update_reset_button_visibility()
        mode = str(lab.get("mode") or "live")
        if self.simulator_mode.get() == SIMULATOR_MSFS24:
            simulator = "MSFS 2024 catalogue / Practice workspace"
        else:
            aircraft_name = xplane_aircraft_title(self.xplane_aircraft.get())
            simulator = (
                f"{aircraft_name} connected"
                if lab.get("simulator_connected")
                else (f"{aircraft_name} practice cockpit" if mode == "test" else f"{aircraft_name} not running")
            )
        if not self._mode_initialised:
            self._mode_initialised = True
            if self.practice_mode.get() and mode != "test":
                self._set_practice_mode()
        elif self.practice_mode.get() != (mode == "test"):
            self.practice_mode.set(mode == "test")
        self._refresh_practice_mode_switch()
        # MUSLIMSIM_PHYSICAL_TELEMETRY_V6
        telemetry = dict(lab.get("physical_telemetry") or {})
        telemetry_devices = dict(telemetry.get("devices") or {})
        try:
            telemetry_count = sum(max(0, int(value)) for value in telemetry_devices.values())
        except (TypeError, ValueError):
            telemetry_count = 0
        try:
            telemetry_sequence = max(0, int(telemetry.get("sequence", 0)))
        except (TypeError, ValueError):
            telemetry_sequence = 0
        # The physical counters used to be appended to the header, but this
        # line is rewritten on every 10 Hz status reply and the incrementing
        # sequence number made it flicker constantly.  The numbers are kept on
        # the instance for diagnostics; the header now shows only the two facts
        # that change when something actually happens.
        self._physical_telemetry_online = bool(telemetry)
        self._physical_telemetry_count = telemetry_count
        self._physical_telemetry_sequence = telemetry_sequence
        self._status_seen = True
        self._set_connection_text(f"{simulator}  •  {mode.title()} mode")
        self._process_physical_events(lab)
        self._refresh_device_activation()
        self._show_selection()
        # A status reply arrives ten times a second whether or not anything the
        # panel draws has moved.  Repainting on every one rebuilt several
        # hundred canvas items to show an identical picture.  Repaint only when
        # the drawn state actually differs; a physical input still appears on
        # the very next reply, because that is exactly when it differs.
        if not (self._selected_device == "tca_boeing" and self._tca_drag_axis):
            if self._faceplate_signature() != self._painted_signature:
                self._redraw_pending = True

    def _set_connection_text(self, text: str) -> None:
        """Write the header only when it actually changes.

        Tk re-renders the label on every ``StringVar.set``, even with an
        identical string, so setting it on each 70 ms tick made the header
        visibly flicker.
        """

        if self.connection_text.get() != text:
            self.connection_text.set(text)

    def _faceplate_signature(self) -> tuple:
        """Everything the current faceplate draws from, cheaply comparable.

        Deliberately generous: a false "unchanged" would freeze the panel,
        which is the failure this project keeps having, so the device mirror,
        its bridge state, the practice preview and the selection are all in it.
        Comparing these costs far less than rebuilding several hundred canvas
        items.
        """

        device = self._selected_device
        try:
            mirror = self._device_mirror(device)
        except Exception:
            # A mirror that cannot be composed must never suppress a repaint.
            return ("mirror-error", time.monotonic())
        return (
            device,
            self._selected_visual,
            repr(sorted(mirror.items(), key=lambda item: item[0])),
            repr(self._device_states.get(device)),
            repr(self._preview_snapshot.get(device)),
            bool(self.practice_mode.get()),
            tuple(sorted(self._flash_until)),
        )

    def _set_practice_mode(self) -> None:
        requested = "test" if self.practice_mode.get() else "live"
        self._cancel_tca_practice_routes()
        if requested == "live":
            self._tca_drag_axis = None
        self._refresh_practice_mode_switch()
        if requested == "test":
            self._preview_output_signature = ""
            self._practice_outputs_dirty = True
        self._request(
            "lab_mode", mode=requested,
            done=lambda _result: self.footer.set(
                (
                    "MSFS 2024 Practice mode is active. The visual panel can be used safely; no aircraft dispatch is enabled."
                    if self.simulator_mode.get() == SIMULATOR_MSFS24 else
                    "Practice mode is active. Physical telemetry is live; verified panel outputs follow the common aircraft-power gate."
                )
                if requested == "test" else
                (
                    "MSFS 2024 live mode is selected. Saved mappings remain inactive until the MSFS connector is installed."
                    if self.simulator_mode.get() == SIMULATOR_MSFS24 else
                    "Live simulator mode is active for your saved mappings."
                )
            ),
        )

    def _sync_tca_practice_axes(self, lab: Dict[str, Any]) -> None:
        """Let real lever travel replace only its matching virtual pose."""

        if not self.practice_mode.get():
            return
        inputs = lab.get("inputs") if isinstance(lab, dict) else None
        tca_inputs = inputs.get("tca_boeing") if isinstance(inputs, dict) else None
        if not isinstance(tca_inputs, dict):
            return
        for bank in ("12", "34"):
            for axis in (3, 4, 5):
                key = f"bank{bank}_axis_{axis}"
                if key == self._tca_drag_axis:
                    continue
                item = tca_inputs.get(key)
                if not isinstance(item, dict):
                    continue
                if str(item.get("source") or "") not in {"physical", "baseline"}:
                    continue
                try:
                    self._tca_practice_axes[key] = max(
                        -1.0, min(1.0, float(item.get("value"))),
                    )
                except (TypeError, ValueError):
                    continue

    def _practice_page_wake(self, *, immediate: bool = False) -> None:
        """Compatibility no-op: V5's bridge owns Practice output authority.

        # MUSLIMSIM_FINAL_COCKPIT_STATE_V5
        Older Studio generations tried to keep only the selected panel awake by
        sending a ``practice_wake`` command.  That split the product across two
        incompatible control-channel generations and made Practice depend on
        which page happened to be open.  V5 starts/releases the entire verified
        Practice output group in the bridge from one aircraft-power gate.
        Physical input telemetry remains independent and is always rendered.
        """
        self._practice_wake_device = None
        return

    def _sync_practice_outputs(self) -> None:
        """Mirror the virtual values without starving live control feedback."""

        # Current bridges own the simulator-down cockpit model themselves.
        # They update supported physical displays from the same HID input
        # event that changed the model, so the visual UI cannot become a
        # single point of failure for hardware feedback.
        if self._lab.get("practice_preview_owner") == "bridge":
            return
        # Wait until the bridge has accepted test mode.  This prevents a
        # startup race where a real device could receive preview values while
        # the lab is still in live-routing mode.
        if (
            not self.practice_mode.get()
            or self._lab.get("mode") != "test"
            or self.supervisor.client is None
        ):
            return
        # The animated Studio faceplate is intentionally independent from
        # device writes.  Real panels receive a new test frame at startup and
        # after a user action, not a continuous stream merely because the
        # software preview is breathing/moving.
        if not self._practice_outputs_dirty:
            return
        fcu = self._preview_snapshot.get("fcu_32_efis", {})
        pap = self._preview_snapshot.get("pap3_mag", {})
        agp = self._preview_snapshot.get("agp_bb80", {})
        fcu_values = dict(fcu.get("values") or {})
        pap_values = dict(pap.get("values") or {})
        agp_values = tuple(str(value) for value in list(agp.get("values") or ())[:3])
        pfp_lines = list((self._preview_snapshot.get("pfp3n_bb35") or {}).get("lines") or ())
        mcdu_lines = list((self._preview_snapshot.get("mcdu32_bb36") or {}).get("lines") or ())
        if len(agp_values) != 3:
            return
        signature = repr((fcu_values, pap_values, agp_values, pfp_lines, mcdu_lines))
        if signature == self._preview_output_signature:
            self._practice_outputs_dirty = False
            return
        # A practice preview can change several display fields at once.  The
        # older implementation submitted every HID-facing update separately
        # on every animation step, which could fill the same worker queue used
        # for physical status polling.  Keep only the newest picture while a
        # single ordered batch is being sent.
        if self._output_sync_pending:
            self._output_sync_dirty = True
            return
        self._preview_output_signature = signature
        self._practice_outputs_dirty = False
        updates: list[tuple[str, str, Any]] = [
            ("fcu_32_efis", "fcu_windows", fcu_values),
            ("fcu_32_efis", "backlight", 180),
            ("pap3_mag", "lcd", pap_values),
            ("pap3_mag", "backlight", 1),
        ]
        for control, value in zip(("chr", "utc", "et"), agp_values):
            updates.append(("agp_bb80", control, value))
        # F2 is the exact character-page protocol already used by the BB35
        # and BB36 live FMC paths.  No arbitrary graphics plane is exposed.
        for device, lines in (("pfp3n_bb35", pfp_lines), ("mcdu32_bb36", mcdu_lines)):
            if len(lines) == 14:
                updates.append((device, "screen", {"lines": lines}))
        client = self.supervisor.client
        if client is None:
            return
        self._output_sync_pending = True
        self._output_sync_dirty = False

        def write_batch() -> Dict[str, Any]:
            failures: list[str] = []
            sent = 0
            for device, control, value in updates:
                try:
                    client.request("lab_output", device=device, control=control, value=value)
                    sent += 1
                except Exception as exc:
                    failures.append(str(exc))
            return {"sent": sent, "failures": failures}

        def complete(result: Dict[str, Any]) -> None:
            self._output_sync_pending = False
            if self._output_sync_dirty:
                # The latest snapshot replaces any one that changed while the
                # device was writing; it will be scheduled on the next tick.
                self._preview_output_signature = ""
                self._practice_outputs_dirty = True
            failures = list(result.get("failures") or {})
            if failures:
                self.footer.set("Display update is retrying; physical controls are still live.")

        self._submit_output(write_batch, complete)

    def _sync_live_selector_poses(self, lab: Dict[str, Any]) -> None:
        """Recover maintained visual poses directly from HardwareLab state.

        Event diagnostics remain useful for learning and the bright movement
        flash, but they are a bounded history.  Maintained FCU/EFIS selectors
        must not depend on a particular event still being present in that ring.
        Only idempotent selector positions are synchronized here; momentary
        push buttons keep their established simulator/mirror indication.
        """

        inputs = lab.get("inputs")
        fcu = dict(inputs.get("fcu_32_efis") or {}) if isinstance(inputs, dict) else {}
        if not fcu:
            return
        selector_prefixes = (
            "left_inhg", "left_hpa", "right_inhg", "right_hpa",
            "left_mode_", "right_mode_", "left_range_", "right_range_",
            "left_nav1_", "left_nav2_", "right_nav1_", "right_nav2_",
        )
        for key, item in fcu.items():
            if not isinstance(item, dict):
                continue
            if str(item.get("source") or "").casefold() != "physical":
                continue
            if str(item.get("phase") or "").casefold() == "release":
                continue
            try:
                asserted = abs(float(item.get("value", 0.0))) > 0.5
            except (TypeError, ValueError):
                asserted = False
            if not asserted or not str(key).startswith(selector_prefixes):
                continue
            self._apply_fcu_efis_visual(str(key))

    @staticmethod
    def _capture_input_is_assignable(device: str, raw: str, pattern: Any) -> bool:
        # ECAM discovers report contacts dynamically; all other drivers already
        # publish catalogued keys. Never open a second reader or invent an input.
        if pattern is not None and not pattern.fullmatch(raw):
            return False
        control = runtime_control_by_key(device, raw)
        return bool(control and control.is_input and control.remappable
                    and control.status == "implemented")

    def _process_physical_events(self, lab: Dict[str, Any]) -> None:
        events = list(lab.get("diagnostics") or [])
        newest = self._latest_diagnostic
        for event in events:
            timestamp = float(event.get("time") or 0.0)
            if timestamp <= self._latest_diagnostic:
                continue
            newest = max(newest, timestamp)
            if event.get("event") != "input":
                continue
            detail = dict(event.get("detail") or {})
            if detail.get("source") != "physical":
                continue
            raw = str(detail.get("control") or "")
            event_device = str(event.get("device") or "")
            # Maintained switches publish their final position as either a
            # release or a selector change.  The faceplate reads that value
            # continuously, while press/change is also allowed to create the
            # short teal live acknowledgement for the control just moved.
            if detail.get("phase") not in {"press", "change"}:
                continue
            capture_pattern = _CAPTURE_RAW_PATTERN.get(event_device)
            if (
                self._capture_target is not None
                and event_device == self._capture_device
                and timestamp >= self._capture_started
                and event_device == self._selected_device
                and not self.practice_mode.get()
                and self._capture_input_is_assignable(event_device, raw, capture_pattern)
            ):
                target = self._capture_target
                self._capture_target = None
                self._capture_device = None
                self._request(
                    "learn_set", device=event_device, visual=target,
                    raw_control=raw,
                    done=lambda _result, v=target, r=raw: self._learn_complete(v, r),
                )
                continue
            if event_device == self._selected_device:
                assigned_visual = next(
                    (visual for visual, source in self._learned().items() if source == raw), "",
                )
                if assigned_visual:
                    self._activate_visual(assigned_visual, physical=True)
                    continue
            if event_device != "fcu_32_efis":
                # A device with a live-discovery pattern (see
                # _CAPTURE_RAW_PATTERN) only earns a labelled location on its
                # faceplate after the owner explicitly assigns that exact
                # observed report bit above - an unrelated raw change must
                # never select a button on its own. Every other device's raw
                # contacts already have a fixed identity (see
                # _EXPOSE_UNVERIFIED_CONTROLS) and are safe to highlight the
                # moment they appear in _visual_controls().
                if capture_pattern is not None and capture_pattern.fullmatch(raw):
                    continue
                visual = raw if raw in self._visual_controls() else next(
                    (candidate for candidate, source in self._learned().items() if source == raw),
                    "",
                )
                if event_device == self._selected_device and visual:
                    self._activate_visual(visual, physical=True)
                elif self.practice_mode.get() and event_device in {"pap3_mag", "agp_bb80"}:
                    self._preview.activate(event_device, raw)
                    self._preview_snapshot = dict(self._preview.snapshot())
                    self._practice_outputs_dirty = True
                continue
            if event_device == self._selected_device and raw in self._visual_controls():
                self._activate_visual(raw, physical=True)
                continue
            if self._learning is not None and timestamp >= self._learning_started:
                visual = self._learning
                self._learning = None
                self._request("learn_set", device="fcu_32_efis", visual=visual, raw_control=raw, done=lambda _result, v=visual, r=raw: self._learn_complete(v, r))
                continue
            for visual, source in self._learned().items():
                if source == raw:
                    self._activate_visual(visual, physical=True)
        self._latest_diagnostic = newest

    def _learn_complete(self, visual: str, raw: str) -> None:
        label = self._visual_controls().get(visual, {}).get("label") or visual
        self.footer.set(f"Captured {label} from {raw}. Choose its simulator action next.")
        self._refresh_profile_status(self.footer.get())

    @staticmethod
    def _panel_fault_location(exc: BaseException) -> str:
        """Describe a swallowed panel fault well enough to fix it."""

        detail = f"{type(exc).__name__}: {exc}".strip()
        try:
            frames = traceback.extract_tb(exc.__traceback__)
            mine = [f for f in frames if f.filename.endswith("studio.py")]
            frame = (mine or frames)[-1]
            name = _FaultPath(frame.filename).name
            return f"{detail}  [{name}:{frame.lineno} in {frame.name}]"
        except Exception:
            return detail

    def _record_panel_fault(self, exc: BaseException) -> None:
        """Keep one full traceback per distinct fault, not one per tick.

        A draw that fails once fails every 70 ms, so an unthrottled log would
        be both useless and enormous.  The first occurrence of each distinct
        location is the one that matters.
        """

        try:
            signature = self._panel_fault_location(exc)
            seen = getattr(self, "_panel_faults_logged", None)
            if seen is None:
                seen = set()
                self._panel_faults_logged = seen
            if signature in seen:
                return
            seen.add(signature)
            target = _FaultPath(__file__).resolve().parents[2] / "logs"
            target.mkdir(parents=True, exist_ok=True)
            with (target / "studio_panel_faults.log").open(
                "a", encoding="utf-8",
            ) as handle:
                handle.write(
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"device={self._selected_device} {signature}\n"
                )
                handle.write(
                    "".join(traceback.format_exception(
                        type(exc), exc, exc.__traceback__,
                    ))
                )
                handle.write("\n")
        except Exception:
            # Diagnostics must never become the reason the panel stops.
            pass

    def _tick(self) -> None:
        """Keep the live bridge/UI pulse alive after an isolated panel fault."""

        try:
            self._tick_once()
        except Exception as exc:
            # Tk otherwise drops an ``after`` callback permanently when a
            # single draw/status payload is unexpected.  The window then
            # remains clickable but stops reflecting every real device.  Show
            # a concise recovery state in Studio and always arm the next
            # pulse; detailed device diagnostics remain in the bridge.
            self._status_pending = False
            # MUSLIMSIM_PANEL_FAULT_LOCATION_V1
            # The exception class alone cannot be acted on: a swallowed
            # KeyError from a faceplate draw reads identically to one from
            # a status payload, and all the owner sees is a panel that
            # stops updating.  Name the deepest frame in Studio's own code
            # and keep the whole traceback on disk.
            self.footer.set(
                f"Panel update recovered: {self._panel_fault_location(exc)}"
            )
            self._record_panel_fault(exc)
        finally:
            try:
                if self.winfo_exists():
                    self.after(70, self._tick)
            except tk.TclError:
                pass

    def _tick_once(self) -> None:
        # The Platform V7 Studio hook is installed inside a bare except that
        # stores the error and continues.  It merges the bridge telemetry that
        # drives live physical feedback, so a failed install silently reduces
        # the panel to whatever the plain mirror carries.  Say so once, rather
        # than leaving the owner to wonder why controls stopped animating.
        if not getattr(self, "_platform_v7_install_reported", False):
            self._platform_v7_install_reported = True
            if _MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR is not None:
                self.footer.set(
                    "Platform V7 telemetry hook did not install "
                    f"({type(_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR).__name__}: "
                    f"{_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR}). "
                    "Live physical feedback will be reduced."
                )
        if self.practice_mode.get() and self._preview.step():
            self._preview_snapshot = dict(self._preview.snapshot())
            if not (self._selected_device == "tca_boeing" and self._tca_drag_axis):
                self._redraw_pending = True
        self._practice_page_wake()
        self._sync_practice_outputs()
        self._service_gaze_focus()
        for line in self.supervisor.drain_output():
            # The child process stays hidden.  Surface only a concise state
            # line rather than a terminal-like log stream.
            if line.startswith("WARNING:"):
                self.footer.set(line.removeprefix("WARNING:").strip())
        while True:
            try:
                done, value, error, health_check = self._results.get_nowait()
            except queue.Empty:
                break
            if error is not None:
                if isinstance(error, ControlClientError):
                    self.footer.set(BANNER_WAITING_UPDATE)
                    if health_check:
                        self._control_failures += 1
                        # A delayed status snapshot is not evidence that the
                        # hardware service stopped.  The previous three-strike
                        # recovery policy killed a healthy bridge while it was
                        # handing devices from the practice preview to X-Plane,
                        # then replayed all their startup output in a loop.
                        # Only a process that actually exits is restarted by
                        # the normal ``supervisor.running`` path below.
                        if not self.supervisor.running:
                            self.footer.set(BANNER_SERVICE_STOPPED)
                        elif self._control_failures >= 3:
                            self.footer.set(BANNER_STILL_CONNECTED)
                else:
                    self.footer.set(str(error))
                self._status_pending = False
            else:
                done(value)
        client = self.supervisor.client
        now = time.monotonic()
        if client is not None and not self._status_pending and now >= self._next_status_poll:
            self._status_pending = True
            self._next_status_poll = now + 0.10
            if not self._request("status", done=self._receive_status, health_check=True):
                # A workspace change tears the bridge down on its own thread, so
                # the client can become None between the check above and this
                # submit.  Nothing will ever answer that poll, and leaving the
                # latch set stopped Studio polling for the rest of the session -
                # live feedback died until Studio was closed and reopened.
                self._status_pending = False
        elif getattr(self.supervisor, "recovering", False):
            self._set_connection_text("Restoring private hardware service…")
        elif self.supervisor.running and not self._status_seen:
            # Only before the first reply. This branch is also reached whenever
            # a poll is simply in flight or not yet due - most ticks on a
            # healthy bridge - and writing "Starting..." then made the header
            # alternate with the real status line about fourteen times a second.
            self._set_connection_text("Starting private hardware service…")
        else:
            # A bridge can exit after a USB-driver or device disconnect while
            # the visual application remains perfectly healthy.  Restarting
            # our own child lets the panels reconnect without asking the user
            # to close and reopen Studio.
            self._start_bridge()
        had_live_flash = bool(self._flash_until)
        now = time.monotonic()
        self._flash_until = {key: until for key, until in self._flash_until.items() if until > now}
        if (
            (self._flash_until or had_live_flash)
            and not (self._selected_device == "tca_boeing" and self._tca_drag_axis)
        ):
            self._redraw_pending = True

        # One paint per tick, after every source has had its say.
        if self._redraw_pending:
            self._redraw_pending = False
            self._draw_faceplate()
            try:
                self._painted_signature = self._faceplate_signature()
            except Exception:
                self._painted_signature = None

    # ---- eye focus ----------------------------------------------------
    #
    # Holds the pointer still while the owner is looking at one thing, and lets
    # go the moment they look somewhere else. Entirely optional: with the
    # toggle off, or no tracker present, nothing here runs and Studio behaves
    # exactly as it did before.

    def _gaze_focus_service(self):
        """Build the service on first use, never at startup."""

        if self._gaze_service is None:
            from ..platform.gaze_service import GazeFocusService

            self._gaze_service = GazeFocusService()
        return self._gaze_service

    def _toggle_gaze_focus(self) -> None:
        if not self.gaze_focus_enabled.get():
            service = self._gaze_service
            if service is not None:
                service.stop()
            self._set_gaze_label("Eye focus")
            self.footer.set("Eye focus off.")
            return

        try:
            service = self._gaze_focus_service()
        except Exception as exc:
            self.gaze_focus_enabled.set(False)
            self._set_gaze_label("Eye focus")
            self.footer.set(f"Eye focus unavailable: {type(exc).__name__}: {exc}")
            return

        ready, detail = service.availability()
        if not ready:
            # Put the toggle back rather than leaving it looking enabled while
            # nothing is running.
            self.gaze_focus_enabled.set(False)
            self._set_gaze_label("Eye focus")
            self.footer.set(f"Eye focus unavailable: {detail}")
            return

        try:
            service.start()
        except Exception as exc:
            self.gaze_focus_enabled.set(False)
            self._set_gaze_label("Eye focus")
            self.footer.set(f"Eye focus could not start: {exc}")
            return

        self._set_gaze_label(service.summary())
        self.footer.set(
            "Eye focus on. Moving the mouse always takes the pointer back."
        )

    def _set_gaze_label(self, text: str) -> None:
        # Written only when it actually changes. A label in the toolbar that is
        # rewritten on every tick is the flicker the owner asked to be rid of.
        if text != self._gaze_label_shown:
            self._gaze_label_shown = text
            self.gaze_focus_label.set(text)

    def _service_gaze_focus(self) -> None:
        """Called from the tick: feed it hardware activity and read its state."""

        service = self._gaze_service
        if service is None or not service.running:
            return
        # Somebody part way through turning a knob is not trying to look
        # elsewhere, so any new physical input holds the focus lock open. The
        # telemetry sequence is one number that advances whenever any control
        # anywhere reports, which keeps this O(1) however many panels are added.
        sequence = getattr(self, "_physical_telemetry_sequence", 0)
        if sequence != self._gaze_telemetry_seen:
            self._gaze_telemetry_seen = sequence
            service.note_control_activity()
        self._set_gaze_label(service.summary())

    def _close(self) -> None:
        self._cancel_tca_practice_routes()
        service = self._gaze_service
        if service is not None:
            service.stop()
        self.supervisor.stop()
        self._workers.shutdown(wait=False, cancel_futures=True)
        self._output_workers.shutdown(wait=False, cancel_futures=True)
        self.destroy()


def _rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, radius: float, **kwargs: Any) -> int:
    radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    return canvas.create_polygon(
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        smooth=True, **kwargs,
    )


# Tk Canvas has no native rounded rectangle.  Attaching it once keeps all
# faceplate drawing declarative and avoids any image asset requirement.
if not hasattr(tk.Canvas, "create_round_rect"):
    setattr(tk.Canvas, "create_round_rect", _rounded_rect)


# >>> MUSLIMSIM_PLATFORM_V7_STUDIO_HOOK >>>
# Patch the completed Studio class after its definition. The hook only merges
# bridge-published telemetry and adds the Device Manager shortcut; Studio never
# opens a hardware handle.
_MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR = None
try:
    from muslimsim.platform.studio_hooks import auto_install as _muslimsim_platform_v7_auto_install
    _MUSLIMSIM_PLATFORM_V7_STUDIO_CLASSES = (
        _muslimsim_platform_v7_auto_install(globals())
    )
except Exception as _muslimsim_platform_v7_studio_error:
    _MUSLIMSIM_PLATFORM_V7_STUDIO_CLASSES = 0
    _MUSLIMSIM_PLATFORM_V7_STUDIO_ERROR = _muslimsim_platform_v7_studio_error
# <<< MUSLIMSIM_PLATFORM_V7_STUDIO_HOOK <<<

__all__ = ("MuslimSimStudio",)

# MUSLIMSIM_AGP_RADIO_NAV_V2_STUDIO

# MUSLIMSIM_AGP_RADIO_NAV_V2_4_QUICK_GUIDE
# MUSLIMSIM_AGP_STUDIO_GUIDE_LEFT_V2_5

# MUSLIMSIM_FMC_AUTHORED_FACEPLATES_V1_STUDIO

# MUSLIMSIM_STUDIO_LIVE_FEEDBACK_V1
