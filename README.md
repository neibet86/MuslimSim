# MuslimSim

Windows desktop cockpit-hardware integration and practice workspace.

## Start

Use the configured Python environment on the cockpit PC to run
`MuslimSim Studio.pyw`. The bridge owns the hardware readers; do not start a
second bridge or USB reader while Studio is running.

- `muslimsim/`: device drivers, control service, hardware catalog, and Studio.
- `bridge/`: simulator integration.
- `tools/`: diagnostics, capture tools, and offline regression checks.
- `PNG/` and `assets/`: authored display and faceplate resources.
- `DEVICE_REFERENCE.md`: hardware identities and verified behavior.
- `AGENTS.md`: preservation, ownership, and output-power rules.

## Verify

Run `python -B tools/test_known_regressions.py` in the configured environment.
The verified 3M PDC capture fixture is included for its full decoder replay.
Tk drawing checks can be run with
`python -B tools/test_pdc_shared_faceplate.py --render`.

## Local-only material

Raw packet captures, backup trees, generated builds, diagnostic logs and
scratch files remain on the cockpit PC and are excluded from this source
repository. Saved user simulator profiles remain in the local application
settings folder; this upload does not change their assignments.


GitHub source upload: the modified `tools/XTextureExtractor-trial` source is
included directly, with its existing third-party attribution and license.
Local nested Git metadata, historical archives and compiled temporary products
are excluded. The verified 3M guided capture remains included for offline tests.
