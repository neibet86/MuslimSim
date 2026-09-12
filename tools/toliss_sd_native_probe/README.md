# Read-only ToLiss SD native probe

Status: compiled and tested offline, **installed with operator approval, not yet live-tested**. This is
a diagnostic, not a replacement telemetry provider. See
`../../docs/TOLISS_BLEED_SOURCE_RESEARCH.md` for evidence and interpretation.

Installed September 10, 2026 after verifying X-Plane was closed, into
`Resources/plugins/MuslimSimSDProbe/64/win.xpl` in the active simulator.
Installed SHA256 matches the tested build:
`73D0CAC9115914576F159882C0A4B8D481D68A7C65A14A36B9E763B31B7CBCD0`.
No existing plugin or ToLiss file was overwritten. Next step is the ground test.

It compares native XPLMGetDatab reads using 36-, 40- and 256-byte requests.
It logs SD page, seven colour rows, pressure and PackTemp pointer ratios to
X-Plane's Log.txt under `MS-SD-PROBE`. NULs are preserved as hex, not discarded.
Three samples are taken, five seconds apart after an initial ten-second delay.
After those samples no more reads are scheduled. Unready-aircraft retries are
bounded. It has no dataref setters, aircraft commands, sockets or HID access.
No display or light is driven, regardless of aircraft power state.

## Safe live test, only after operator approval

1. Finish the flight and close X-Plane normally. Do not hot-inject this plugin.
2. Copy only `win.xpl` into a new
   `Resources/plugins/MuslimSimSDProbe/64/` folder in the active X-Plane install.
   Do not overwrite an existing plugin or alter ToLiss files.
3. Start a safe on-ground session. Select BLEED on native ECAM. If initial
   sampling completed before selection, disable/re-enable only this diagnostic
   in Plugin Admin to collect another bounded set.
4. Compare `MS-SD-PROBE` log rows with simultaneous REST byte values.
5. Close X-Plane normally, then move the diagnostic folder back out of the
   plugins directory. Leave the log available for analysis.

The probe accepts the installed path containing `ToLissA321`; a differently
named aircraft folder is deliberately not assumed to be the same aircraft.
Any plugin can expose provider defects; this is why installation waits for a
safe session. No live result has been claimed from the synthetic tests.

## Offline build

In an x64 Visual Studio developer command prompt in this folder:

```text
cl /nologo /std:c++17 /EHsc /W4 /MT /LD probe.cpp /Fe:win.xpl /link /INCREMENTAL:NO
cl /nologo /std:c++17 /EHsc /W4 /MT test_probe.cpp /Fe:test_probe.exe /link /INCREMENTAL:NO
test_probe.exe
dumpbin /exports win.xpl
```

The Windows SDK is used for module lookup; no downloaded SDK library or third-
party executable is loaded. XPLM functions are resolved from the module already
loaded by X-Plane, using the documented C ABI.
