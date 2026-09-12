# ToLiss BLEED telemetry investigation

## Finding

There is not yet a verified replacement source for the six missing BLEED temperatures in the running installation. The old SD-column mapping is traceable to real XHSI source code, but the corresponding datarefs currently return empty byte arrays through X-Plane's web API. That mapping cannot be treated as working merely because an older integration used it.

Two concrete paths remain: test those datarefs through the native SDK, then, if native reads are also empty, investigate extraction of ToLiss's live ECAM image or obtain a supported export from ToLiss. A bounded native diagnostic has been built and tested offline. It is not installed and has not run inside X-Plane.

## Installed environment and observed evidence

Read-only inspection on September 10, 2026 established:

| Item | Evidence |
|---|---|
| Simulator | Installed Log.txt: X-Plane 12.4.3-r2, build 124311, Vulkan, Windows |
| Aircraft path | REST reports `Aircraft/Laminar Research/ToLissA321_V1p8/a321.acf` |
| Version indication | The aircraft's A321_changelog.txt begins with V1.9.1, Build 1696; the folder name is not reliable version evidence |
| Published catalog | 16,711 entries returned in the current API catalog; searched for bleed, pack/duct/compressor temperatures, ATA21/ATA36 and SD text |
| Selected page | `AirbusFBW/SDPage = 1`; the operator independently confirmed native BLEED was selected |
| Missing readings | `SDline2g`, `SDline5g`, `SDline13g`, and checked amber row 2 returned 36 NUL bytes each |
| Working scalar | A repeated sample of `LeftBleedPress` returned 65.344177; it is not an empty feed |
| Non-temperature scalar | `Pack1Temp` returned approximately 0.27783, consistent with the existing pointer-ratio interpretation, not a degree-Celsius reading |
| Installed panel texture | PNG header reports 4096 × 4096 |

The observed numbers are diagnostic samples, not display defaults. These observations do not prove the native SDK also returns zeros, that every version of ToLiss lacks these values, or that an undocumented export cannot exist. They do rule out native BLEED selection as a sufficient fix for this session.

Local evidence locations: `D:/SteamLibrary/steamapps/common/X-Plane 12/Log.txt`; `Aircraft/Laminar Research/ToLissA321_V1p8/A321_changelog.txt`, `smartcopilot.cfg`, and `cockpit_3d/-PANELS-/Panel_Airliner.png` under that simulator installation. Measurements were read through localhost port 8086. No simulator commands were sent.

## What the GitHub implementations actually do

### XHSI: a real historical mapping, not an independent sensor feed

XHSI's QPAC branch gates the extraction on SD page 1 and reads green SD rows through `XPLMGetDatab` into a 40-byte buffer. It parses the following zero-based columns. Its Java temperature getters ultimately consume those packets; they do not reveal a separate direct ToLiss temperature dataref. [XHSI packets source](https://github.com/annerajb/XHSI/blob/master/XHSI_plugin/packets.c), [XHSI aircraft getters](https://github.com/annerajb/XHSI/blob/master/XHSI_app/src/net/sourceforge/xhsi/model/xplane/XPlaneAircraft.java).

| Quantity | Historical source | Left columns | Right columns |
|---|---|---|---|
| Pack outlet | SDline2g | 4–6 | 26–28 intended |
| Compressor outlet | SDline5g | 4–6 | 26–28 |
| Bleed duct | SDline13g | 5–7 | 27–29 |

The inspected right-pack-outlet expression repeats column 27 for its final digit; copying that expression would introduce another bug. The same packet file has JAR-specific numeric temperature sources, but those belong to another aircraft and are not substitutes for ToLiss. [XHSI packets source](https://github.com/annerajb/XHSI/blob/master/XHSI_plugin/packets.c).

**Conclusion:** installing XHSI alone is not an established fix. Its underlying SD byte reads must first succeed on this aircraft. The mapping is historical QPAC evidence, not current A321 compatibility certification.

### Other dataref lists and integrations

The public ToLiss dataref list inspected includes Pack1Temp/Pack2Temp and the familiar bleed indication names. It is a different-aircraft community inventory, not authoritative unit documentation for this A321. The live catalog is the stronger availability check. [Community dataref inventory](https://github.com/dualznz/toliss-a430-datarefs/blob/main/datarefs.txt).

The installed SmartCopilot configuration contains pack and bleed switches, but the searched ATA21/ATA36 sections did not reveal the missing engineering temperatures. A switch synchronization mapping does not expose every internal simulation state. Other integrations also explicitly document missing ToLiss feedback for some features; that is evidence of limitations, not proof about BLEED specifically. [xp_streamdeck profile documentation](https://github.com/rwellinger/xp_streamdeck/blob/main/streamdeck-profiles/README.md).

No verified, independent six-temperature mapping or specific current-A321 fix was found in the searched GitHub issues and indexed forum discussions. This is a bounded negative finding, not a claim to have searched every private repository or unindexed forum post.

## Native SDK test: the immediate next step

The SDK documents byte-array reads with an offset and requested maximum length, and explicitly states that provider plugins implement the array behavior. Consequently, a native/web discrepancy or buffer-length sensitivity is a testable hypothesis, not something to dismiss or assume. [Laminar Research: XPLMGetDatab](https://developer.x-plane.com/sdk/XPLMGetDatab/).

The prepared probe reads seven SD colour rows at requested sizes 36, 40 and 256, logging reported size, returned length, changed bytes, a guard-region check, raw hex and a printable representation. It also logs page ID, aircraft path, pressure and pointer-ratio scalars. It takes three samples five seconds apart after its initial delay, then stops scheduling reads. Aircraft-not-ready retries are bounded. Lookups and reads occur in the SDK flight-loop callback, not an arbitrary worker thread. [Laminar Research: flight-loop registration](https://developer.x-plane.com/sdk/XPLMRegisterFlightLoopCallback/).

| Native result | Interpretation and next action |
|---|---|
| Digits at all sizes while REST stays empty | Investigate the web transport/provider interaction; implement a narrowly scoped native export only after simultaneous comparison |
| Digits only at a larger request size | Investigate a provider byte-buffer contract discrepancy; retain raw evidence and validate all six fields before shipping an adapter |
| All NUL at all sizes | Current native export is also unusable in that state; pursue ToLiss support or live texture extraction |
| Values returned on a different native page | Establish page identity and prevent stale/cross-page numbers before any display integration |

The compiled diagnostic is not a fix and does not establish any of these outcomes. It resolves only read functions, logging and callback lifecycle functions from X-Plane's already loaded XPLM module. It does not load another DLL, patch ToLiss memory, send commands, write datarefs, open hardware, or illuminate displays. Loading any new plugin still requires a safe simulator session and operator agreement.

## Live display extraction: a credible fallback with important constraints

XTextureExtractor extracts rendered instrument textures and can send them over TCP port 52500. Its network path encodes PNG frames; GPU readback can reduce performance. This is live aircraft imagery, not invented engineering telemetry. Its A321 definition explicitly names ECAM1 and ECAM2. [Project README](https://github.com/waynepiekarski/XTextureExtractor/blob/master/README), [network implementation](https://github.com/waynepiekarski/XTextureExtractor/blob/master/XTextureExtractorNetwork.cpp), [A321 definition](https://github.com/waynepiekarski/XTextureExtractor/blob/master/XTextureExtractor-Data/a321.acf.tex).

The inspected A321 definition targets 2048 × 2048, while this installation's panel file is 4096 × 4096. A ToLiss A319 issue documents that exact class of header mismatch causing definition rejection. The correct A321 regions must therefore be measured from the current live texture; blindly copying the old definition or doubling all coordinates is not validated. [A319 texture-size issue #26](https://github.com/waynepiekarski/XTextureExtractor/issues/26).

This option has three integration limits:

- The current BB35/BB36 path uses native drawing commands, not an established video framebuffer. A PC popout working does not prove a fast LCD raster-upload path.
- One lower ECAM texture normally reflects the page ToLiss is rendering. Independent, simultaneous lower-page imagery must not be promised without proving separate render surfaces.
- Extracting numbers from the image would be image-derived telemetry. It would need page recognition, validity/confidence checks, stale-frame rejection and exact digit tests before populating the existing native renderer.

Those are engineering feasibility checks, not reasons to replace missing temperatures with arbitrary values.

## Forums and vendor-supported options

In the home-cockpit discussion, ToLiss's developer recommends popout windows, saving their positions in the ISCS and restoring them using a command. The developer also says panels.txt does not configure these displays. A cockpit builder describes using popouts behind HTML panels. These approaches support faithful visual reuse, but do not demonstrate numerical BLEED exports. [ToLiss home-cockpit discussion](https://forums.x-plane.org/forums/topic/303273-homecockpit-possible-on-the-toliss-a320-x-plane/).

The official A321 changelog shows the product has changed across versions; it is not a specification of the six exports at issue. There is no verified basis here for saying an update alone fixes them. [A321 changelog](https://toliss.com/pages/a321-change-log).

If native reads remain empty, a precise vendor question is preferable to a broad request for “all datarefs.” ToLiss identifies its forums as the primary support channel. [Official support](https://toliss.com/pages/support).

Suggested support question, not posted:

> On Windows/X-Plane 12.4.3-r2, with an A321 installation whose changelog identifies V1.9.1 Build 1696, native BLEED is selected and SDPage is 1. The web API returns 36 NUL bytes for SDline2g, SDline5g and SDline13g while pressure and Pack1Temp are numeric. Are the historical SDline engineering-text exports still maintained? Is an export option required, or are there supported datarefs for left/right pack outlet, compressor outlet and bleed duct temperatures? A direct SDK comparison at several buffer sizes can be supplied separately.

## Delivery and acceptance

Prepared locally: `tools/toliss_sd_native_probe/probe.cpp`, `test_probe.cpp`, `win.xpl` and its README. The x64 plugin builds successfully and exports all five required plugin lifecycle functions. Offline tests passed for byte preservation, the synthetic buffer-size distinction, three-sample scheduling and unregister behavior. The project's mandatory known-regression suite also passed. None of this is live-aircraft acceptance.

The next gate is an approved, on-ground native probe run, with native BLEED visible and a simultaneous web-API read. A production fix is accepted only when all six values match ToLiss and update across changing aircraft states, invalid data stays invalid, and the existing power-off, FCU and hardware ownership behavior remains unchanged.

## Source inventory

Sources inspected September 10, 2026; GitHub master branches are mutable and historical QPAC code is not assumed current-A321 behavior.

1. XHSI contributors, [packets.c](https://github.com/annerajb/XHSI/blob/master/XHSI_plugin/packets.c): actual temperature extraction.
2. XHSI contributors, [XPlaneAircraft.java](https://github.com/annerajb/XHSI/blob/master/XHSI_app/src/net/sourceforge/xhsi/model/xplane/XPlaneAircraft.java): consumer-side getters.
3. XHSI contributors, [datarefs_qpac.c](https://github.com/annerajb/XHSI/blob/master/XHSI_plugin/datarefs_qpac.c): reference resolution.
4. dualznz, [ToLiss dataref inventory](https://github.com/dualznz/toliss-a430-datarefs/blob/main/datarefs.txt): candidate names, different-aircraft caveat.
5. rwellinger and contributors, [Stream Deck profile documentation](https://github.com/rwellinger/xp_streamdeck/blob/main/streamdeck-profiles/README.md): integration limitations.
6. Laminar Research, [XPLMGetDatab](https://developer.x-plane.com/sdk/XPLMGetDatab/) and [flight-loop registration](https://developer.x-plane.com/sdk/XPLMRegisterFlightLoopCallback/): native diagnostic contract.
7. Wayne Piekarski, [XTextureExtractor README](https://github.com/waynepiekarski/XTextureExtractor/blob/master/README), [network code](https://github.com/waynepiekarski/XTextureExtractor/blob/master/XTextureExtractorNetwork.cpp), and [A321 definition](https://github.com/waynepiekarski/XTextureExtractor/blob/master/XTextureExtractor-Data/a321.acf.tex): live-image route.
8. schenlap, [XTextureExtractor issue #26](https://github.com/waynepiekarski/XTextureExtractor/issues/26), December 7, 2024: A319 resolution mismatch report.
9. GlidingKiwi and cockpit builders, [home-cockpit forum discussion](https://forums.x-plane.org/forums/topic/303273-homecockpit-possible-on-the-toliss-a320-x-plane/), March 2024: popout workflow.
10. ToLiss, [A321 changelog](https://toliss.com/pages/a321-change-log) and [support](https://toliss.com/pages/support): version context and vendor escalation.
