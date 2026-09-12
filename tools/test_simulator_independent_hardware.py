"""Physical feedback and virtual Practice must work with no simulator."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def check():
    from muslimsim.hardware.catalog import catalogue_snapshot
    from muslimsim.hardware.lab import HardwareLab
    from muslimsim.hardware.profiles import HardwareProfileStore
    from muslimsim.gui.live_feedback import compose_live_mirror

    devices = catalogue_snapshot()['devices']
    counts = {}
    with TemporaryDirectory(prefix="muslimsim-no-simulator-") as directory:
        for mode in ('live', 'test'):
            store = HardwareProfileStore(Path(directory) / (mode + ".json"))
            store.load()
            lab = HardwareLab(store)
            try:
                lab.set_simulator_connected(False)
                lab.set_mode(mode)
                exercised = 0
                for device in devices:
                    controls = [c for c in device['controls'] if c['direction'] in {'input', 'bidirectional'}
                                and c['status'] == 'implemented']
                    if not controls:
                        continue
                    control = controls[0]['key']
                    key = device['key']
                    for value in (0.0, 1.0):
                        lab.input(key, control, value, source='physical', route=False)
                        snapshot = lab.snapshot()
                        assert not snapshot['simulator_connected']
                        mirror = compose_live_mirror(key, {'state': 'waiting-for-simulator', 'connected': False}, snapshot)
                        assert mirror['input_values'][control] == value, (mode, key)
                    exercised += 1
                assert exercised >= 17, exercised
                counts[mode] = exercised
                # Explicit analog travel in Live and Practice, with simulator disconnected.
                for key, controls in {'winctrl_throttle': ('left_thrust', 'right_thrust'),
                                      'winctrl_pedals': ('rudder', 'left_toe_brake', 'right_toe_brake')}.items():
                    for control in controls:
                        for value in (0.125, 0.875):
                            lab.input(key, control, value, source='physical', route=False)
                            mirror = compose_live_mirror(key, {}, lab.snapshot())
                            assert mirror['input_values'][control] == value, (mode, key, control)
                        if mode == 'test':
                            lab.practice_input(key, control, 0.5)
                            assert lab.snapshot()['inputs'][key][control]['value'] == 0.5
            finally:
                from muslimsim.platform.bootstrap import runtime_for
                runtime = runtime_for(lab, create=False)
                if runtime is not None:
                    runtime.close()
    print(f'  [ok] BUG-61 simulator-off physical feedback: {counts}; throttle/pedal analog travel and Practice input')


if __name__ == '__main__':
    check()
