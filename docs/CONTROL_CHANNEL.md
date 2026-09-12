# The control channel

How the control panel reaches into a running bridge to stop, start or reset a
single device — and why that is the whole reason it exists.

---

## Why

Before this, the only granularity available was Ctrl+C. Recovering one wedged
MCDU display restarted the throttle, the pedals, the MCP and the overhead with
it.

The device managers already supported better than that — each one owns its own
HID handle and has `start()` and `stop()` — so all that was missing was a way
to reach them from outside the process. That is all this is.

---

## Shape

A loopback TCP server inside the bridge, one JSON object per line in each
direction.

Line-delimited JSON rather than anything cleverer because the point of this
channel is to be debuggable by hand: you can drive it from a terminal with a
socket and read what comes back.

```
panel                                   bridge
  |                                       |
  |-- {"cmd":"restart","device":"mcdu"} ->|  mcdu.stop(); mcdu.start()
  |<- {"ok":true,"state":"running"} ------|
```

### Security

- Bound to `127.0.0.1` only. Never a routable address.
- Carries a **per-run token**, generated fresh each start, so another process
  on the machine cannot reach in and start moving the aircraft's controls.
- A caller with the wrong token gets `Not authorised` — the same answer
  whether the token is absent or wrong, so probing reveals nothing.
- `--control-port` is **off unless the panel passes it**. Nothing changes for
  anyone starting the bridge from a terminal.

---

## Commands

| Command | Fields | Returns |
| --- | --- | --- |
| `ping` | — | `ok`, protocol version, registered device keys |
| `status` | — | every device's state and its manager's own words |
| `start` / `stop` / `restart` | `device` | `ok` and the new state |
| `telemetry` | — | what each panel is currently drawing |
| `shutdown` | — | begins a graceful stop |

Device states: `running`, `stopped`, `disabled`, `error`, `unsupported`. A
manager that reports its own trouble (the PAP3 and PDC both do) overrides the
coarse view — `reconnect`, `error` or `unavailable` in its status text is
promoted to `error`.

---

## It opens before the wait for X-Plane

This was got wrong first, and the correction matters.

The first version registered the channel where all the device managers exist —
after the bridge had connected to the simulator. It **never came up**, because
the bridge blocks in `Waiting for X-Plane Web API` long before that point.

So with the simulator down there was no per-device control at all, which is
exactly the moment the panels are powered and may already need resetting.

Now:

- the channel is **created and started before** the X-Plane wait;
- the wait loop checks a stop event, so the panel's Stop button has something
  to act on even if the simulator never appears;
- the device managers are **registered later**, as they are created, and until
  then the channel still answers `status`, `telemetry` and `shutdown`.

Measured result: Stop went from a Ctrl+Break kill (exit `0xC000013A`) to a
clean unwind in **1.9 s, exit code 0**, which lets the shutdown path restore
the panels to their WinCtrl state.

---

## Defensiveness

A control channel that can crash the bridge is worse than no control channel.

- Every registered callback runs inside `try/except`; a failure is reported to
  the caller, never raised into the bridge's own threads.
- The whole startup block is wrapped: if the channel cannot bind, the bridge
  prints a warning and flies anyway.
- The server thread and every connection thread are daemons with timeouts.

---

## The panel's side

`muslimsim/gui/supervisor.py` owns the bridge as a **child process**. The panel
never runs bridge code in its own interpreter: the bridge opens serial ports,
HID handles and SDL and blocks forever, so a GUI hosting it would freeze on the
first hardware stall and die with it on every crash.

The supervisor:

- builds the command line from saved settings;
- starts the process in its own group, so Ctrl+C in a console does not also
  interrupt it;
- pumps its output into a queue the UI drains on a timer, so no UI thread ever
  blocks on a pipe;
- watches that output for the two banner lines the bridge prints:

  ```
  CONTROL CHANNEL PORT 50366
  CONTROL CHANNEL TOKEN z8GS9UCIBtC7SWOLKtn4drN0
  ```

  and attaches a client when it has both;
- stops it politely (control channel), then firmly (`CTRL_BREAK_EVENT`), then
  finally (`terminate`, `kill`), and never leaves an orphan behind.

Each client call opens a connection, sends one line, reads one line and
closes. Slower than holding a socket open, and the right trade: the GUI polls
a few times a second, and a short-lived connection cannot wedge the bridge's
control thread if the panel is killed mid-request.

Nothing raises on a dead bridge. A panel whose bridge has stopped is an
ordinary state, so `ping` returns False and the device shows as offline.

---

## Frozen builds

A built exe has no interpreter to start the bridge with, so it re-runs
**itself** with `--run-bridge`, and everything after that flag is the bridge's
own command line. `muslimsim/gui/paths.py` decides which form to use.

The control port is passed as `--control-port=N` in `=` form deliberately:
argparse would read a bare negative value as a flag.

---

## Testing

`muslimsim/gui/selftest.py` exercises the whole round trip against a stub
device — ping, restart ordering (`stop` then `start`), unknown device
refused, bad token refused, and that a rejected caller never reached the
device. Run with `MuslimSim.exe --check`.

**Not yet verified:** the same path against the *real* device managers, which
needs the bridge past the X-Plane wait.

---

## Files

| File | Role |
| --- | --- |
| `muslimsim/control/protocol.py` | Wire format, commands, token, `DeviceState` |
| `muslimsim/control/server.py` | Runs inside the bridge; holds the registry |
| `muslimsim/control/client.py` | The panel's side |
| `muslimsim/gui/supervisor.py` | Owns the process, attaches the client |
| `bridge/final.py` | `--control-port` / `--control-token`, startup, registration, shutdown |
