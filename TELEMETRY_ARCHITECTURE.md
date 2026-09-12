# MuslimSim shared X-Plane telemetry architecture

## Purpose

Simulator state is read once and distributed many times.

Before this layer, independent device workers could issue their own REST
`GET /datarefs/<id>/value` calls for the same or neighboring aircraft state.
With PU, AGP, FCU/EFIS, throttle feedback, HOWALT and display helpers active,
that created hundreds of local HTTP reads per second.

The shared telemetry layer removes simulator reads from the device ownership
model:

```text
X-Plane Web API
      |
      | one read-only WebSocket
      v
SharedXPlaneTelemetryHub
      |
      +-- latest whole-DataRef values
      +-- group registry
      +-- scalar/index extraction
      +-- reconnect generation
      +-- metrics
      +-- bounded REST fallback broker
      |
      +--> PU
      +--> AGP
      +--> FCU / EFIS
      +--> WinCtrl throttle feedback
      +--> pedals/startup reconciliation
      +--> HOWALT and other legacy read_dataref callers
      +--> PFD support data
```

Hardware writers remain completely separate.

## Ownership boundary

`muslimsim/simulator/xplane_telemetry.py` may:

- subscribe to X-Plane DataRefs;
- cache values;
- distribute read-only values;
- cache session-scoped DataRef/command IDs;
- report diagnostics.

It must not:

- open HID/serial/SDL hardware;
- call `set_dataref`;
- activate commands;
- own a simulator control;
- decide an aircraft mapping;
- decide panel power/output state.

The existing bridge/device owners keep all writes.

## WebSocket policy

The hub uses X-Plane's additive `dataref_subscribe_values` operation.

Whole DataRefs are subscribed, including arrays. Array consumers extract their
index from the shared whole-array value. This deliberately avoids sparse-index
subscription ordering and lets multiple consumers share the same array.

Normal subscription messages contain up to 64 DataRef IDs. X-Plane documents
that a failed subscription request fails the whole request, so if a normal
batch is rejected MuslimSim retries that batch as isolated one-ID
subscriptions. A single bad optional DataRef is quarantined instead of
starving the rest of the group.

## Consumer groups

Current diagnostic namespaces:

- `pu.core`
- `pu.annunciators`
- `power.authority`
- `startup.safety`
- `fcu_efis.display`
- `winctrl.controls`
- `winctrl.throttle.feedback`
- `pedals.controls`
- `agp.radio_nav`
- `pfd.shared_inputs`
- `dynamic.legacy`
- `dynamic.array`

`dynamic.*` is the compatibility path. Existing modules that still call the
bridge's normal `read_dataref()` API automatically use the shared hub without
being rewritten. As a device receives a dedicated adapter later, its IDs
should be registered under a named group.

## Read contract

Existing callers keep:

```python
read_dataref(api_version, dataref_id)
read_dataref_index(api_version, dataref_id, index)
```

The bridge now performs:

1. request/ensure that DataRef in the shared hub;
2. return the streamed cached value when available;
3. briefly wait for the first value after a new subscription;
4. use the bounded REST fallback broker only if needed.

This means device code does not need to know whether data arrived by WebSocket
or REST.

## REST fallback safety

WebSocket failure must not turn into another request storm.

Fallback is therefore:

- single-flight per `(DataRef ID, optional index)`;
- reused for 1.0 second;
- no more than one new request per key inside the bounded request interval;
- fail-fast when another request would exceed the bound.

Simulator writes are not subject to this broker.

## DataRef/command ID registry

Successful name-to-ID resolutions are cached in
`XPlaneSessionResourceCache`.

The cache is positive for the current bridge/X-Plane generation. A failed
plugin resource lookup receives exponential bounded retry spacing instead of
being searched repeatedly during aircraft load.

Existing code paths that explicitly recover a known stale ID call
`refresh=True`, which invalidates that one cached name before resolving it.

## Freshness

X-Plane sends the full current value after a new subscription, then sends a
DataRef only when it changes. Therefore an individual cached value does not
expire merely because its value has been unchanged for a long time.

A cache becomes invalid when the telemetry WebSocket generation disconnects.
Values are cleared on disconnect/reconnect; no previous-aircraft value is
served as live state.

## Diagnostics

Run the bridge with:

```text
--diagnose-telemetry
```

Every 30 seconds it reports:

- connected state;
- subscribed/desired DataRefs;
- cached values;
- cache reads;
- REST fallbacks;
- cache hit rate;
- resource-ID cache hits;
- actual resource REST resolutions.

`SharedXPlaneTelemetryHub.status()` also exposes group counts, rejected
subscriptions and fallback metrics for future Studio diagnostics.

## Current phase boundary

Performance Phase A centralizes normal bridge `read_dataref` and
`read_dataref_index` consumers.

The existing BB35/BB36 `_SmoothTelemetryHub` graphical-display sampler and the
PU physical-authority WebSocket remain separate for now. They are already
streaming rather than high-frequency REST clients, and changing their timing
belongs in a later Phase B after Phase A is live-proven.

## Performance Phase B — shared graphical display telemetry

BB35 and BB36 no longer create one `_SmoothTelemetryHub` X-Plane subscription
per physical display. Their physical HID/output workers remain separate, but
they acquire one ref-counted smoothing/distribution instance:

```text
Phase-A SharedXPlaneTelemetryHub
        |
        +-- pfd.graphical.shared (PFD + ND + ENG + MFD + HYD raw values)
        |        |
        |        v
        |   one _SmoothTelemetryHub
        |        |
        |        +--> BB35 renderer / independent HID owner
        |        +--> BB36 renderer / independent HID owner
        |
        +-- bb36.fmc          -> BB36 graphical FMC text
        +-- pfd.nd.route      -> FMC route arrays/string
        +-- pfd.nd.traffic    -> TCAS arrays
        +-- pfd.text          -> NAV identifier/string
```

The smoothing instance is reference-counted. Restarting or unplugging one
physical display releases only that display's reference; the other display
continues consuming the same telemetry state. The smoother is destroyed only
when the final graphical display consumer releases it.

The Phase-A telemetry hub now exposes read-only update listeners. Listener
callbacks run outside the central cache lock. This lets the one smoothing
instance receive only changed X-Plane values without opening another socket or
polling the cache every render frame.

### Generation safety

The smoother tracks the central telemetry generation. A simulator reconnect
clears the old smoothed signals before the new connection is considered live,
so a previous-aircraft IAS/heading/etc. cannot briefly reappear on the new
session.

The bridge watchdog also advances `XPlaneSessionResourceCache` on a real
simulator-disconnect edge because X-Plane DataRef/command IDs are session
scoped.

### Display-side raw data

The ND route, TCAS arrays, NAV identifier, and BB36 graphical FMC strings are
not numeric smoothing inputs. They now consume the Phase-A raw cache directly.
When the shared telemetry service exists, these helpers do not issue their old
periodic direct REST reads; they wait for the stream. Their old REST/WebSocket
implementations remain only as compatibility fallback when the shared service
is genuinely unavailable.

### Connection reduction

With both graphical panels and BB36 graphical FMC active, the previous layout
could create:

- one Phase-A bridge-wide telemetry WebSocket;
- one smooth PFD/ND/etc. WebSocket for BB35;
- one smooth PFD/ND/etc. WebSocket for BB36;
- one BB36 graphical-FMC WebSocket.

Phase B carries those display data paths on the one Phase-A telemetry
connection. PU physical authority and other intentionally independent
streaming owners are unchanged.
