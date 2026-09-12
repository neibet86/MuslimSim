# The display mirror, and a restart that is really a restart

Two things the control panel does with the PFP 3N (BB35) and the MCDU 32
(BB36): show what is actually on the glass, and restart the panel for real.

---

## Part 1 — the mirror

### What it is

Not an illustration of what the panel *should* show. The same renderer the
bridge draws with, fed the same values the bridge drew its last frame from.

If the glass is wrong, the mirror is wrong in the same way. That is the only
kind of mirror worth having: one that quietly flattered the hardware would
send you hunting for faults that are not there.

Rendered at about **12 ms per frame** (~80 fps) — far more than a live view
needs.

### Where the values come from

The bridge records them. `bridge/final.py` gained
`_muslimsim_record_display_telemetry`, called at the one point in the display
worker where both value paths converge:

```python
live = _pfp_pfd_has_primary_flight_data(pfd_values)

# Both the WebSocket and REST paths have set pfd_values by here,
# so this is the one place that sees every frame.
_muslimsim_record_display_telemetry(
    device_label, requested_page, pfd_values, last_standby_reason, source,
)
```

Each entry carries the page (`pfd` / `nd` / `eng_pri` / `mfd`), the values,
the standby reason if any, and the data source (`WS+INTERP` or
`REST-FALLBACK`). It is served over the control channel by the `telemetry`
command.

### Why not just read the datarefs again

Because it would lie.

The display worker smooths, interpolates, falls back to REST when the
WebSocket is unhealthy, and substitutes a MuslimSim standby card when the
simulator goes away or the aircraft's displays lose power. A second reader in
the panel would show live numbers while the panel showed standby — the
plausible-but-false picture this project has lost the most time to.

So the mirror is fed from where the renderer is fed.

### How it draws

`muslimsim/hardware/displays.py` imports the renderer package (`pfp_renderer`,
`nd_renderer`), which is pure and cheap, plus the offline frame emulator from
`tools/render_pfp_frame_png.py` — a canvas that accepts the same command set as
the real display and paints onto a PIL image.

`bridge/final.py` is imported for exactly one thing: `_McduPfdFittedCanvas`,
the MCDU's vertical viewport. Reimplementing that geometry would let the mirror
drift away from the panel the first time someone tuned one and not the other.

Two details that were bugs first:

- The mirror frame needs an `identifier`; the MCDU's viewport wrapper reads it
  from the canvas it wraps, and a frame without one cannot be fitted. The MCDU
  mirror sets `0x32`, the PFP `0x31`.
- The frame starts filled with the panel's own background `(6, 7, 13)`, not
  PIL's black, so unpainted area matches the glass rather than looking like a
  hole.

Render failures are **recorded, not swallowed** (`render_error()`), so a blank
mirror can say why instead of leaving you to guess.

### What the tab shows

Both panels side by side, each with its picture, a live/standby/not-running
lamp, and a line reading e.g.

```
Showing PFD  -  data via WS+INTERP
```

Standby is shown as standby, with the reason, rather than as a frozen last
frame.

---

## Part 2 — a real restart

### Redrawing is not restarting

Blanking a panel and redrawing it leaves the controller in whatever state it
was already in — which is no use when that state is the fault. The MCDU
investigation established that only a power cycle reliably recovers this
hardware.

A **real** restart is a USB re-enumeration: the device drops off the bus, its
firmware starts again, and the WinCtrl logo appears on the way up, exactly as
when the cable is pulled.

The Displays tab therefore has two buttons per panel:

| Button | What it does |
| --- | --- |
| **Redraw** | Restarts that device's manager inside the running bridge — the soft path |
| **Restart screen** | Re-enumerates the device on the USB bus — the real one |

### The trap: `pnputil` lies without elevation

`pnputil /restart-device` **exits 0 when not elevated and does nothing at
all.**

Measured: after a reset that reported `Power-cycled 1 instance`, the bus was
polled at 50 ms for 3.5 s — **0 absent samples out of 80**. The device never
left the bus.

Reporting that as success would have been the worst possible failure here: you
would believe a display had been power-cycled when it had not, and go looking
for the fault somewhere else entirely.

So the reset now:

1. **Checks for Administrator up front** and refuses with a message that says
   so, because it has been measured that the operation cannot work without it.
2. **Targets the `USB\` parent node**, not the `HID\` child. Each panel appears
   twice on the PnP tree; restarting the child only rebinds the driver and
   leaves the device's own state untouched.
3. **Verifies afterwards** — waits up to 4 s for the device to leave the bus,
   then up to 15 s for it to come back, and reports failure if either does not
   happen:

   ```
   Windows reported success but the device never left the USB bus,
   so it was not restarted.
   ```

This is why the application ships with an administrator manifest
(`uac_admin=True`): it is what makes the Restart button honest. Without
elevation the button is disabled and says why, rather than appearing to work.

A self-test check asserts that an unelevated power cycle never claims success.

### PnP nodes

```
USB\VID_4098&PID_BB36\2565D1217760606282261023   <- restarted (the parent)
HID\VID_4098&PID_BB36\7&37834E8C&0&0000          <- ignored (the child)
```

---

## Files

| File | Role |
| --- | --- |
| `muslimsim/hardware/displays.py` | Rendering, telemetry matching, `reboot()`, `can_reboot()` |
| `muslimsim/hardware/usb.py` | Presence, PnP enumeration, verified `reset_device()` |
| `muslimsim/gui/displayview.py` | The two mirrors and their buttons |
| `bridge/final.py` | `_muslimsim_record_display_telemetry`, `muslimsim_display_telemetry` |
| `muslimsim/control/*` | Carries the telemetry to the panel |

## Related

- The MCDU speckle investigation, and why no fix was applied, is in
  [CONTROL_PANEL_BUILD.md §7.1](CONTROL_PANEL_BUILD.md#71-the-mcdu-speckles-are-not-in-the-rendering).
- The panel-side hardware notes are in
  [../MCDU_BB36_INVESTIGATION.md](../MCDU_BB36_INVESTIGATION.md).
