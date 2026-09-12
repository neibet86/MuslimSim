"""MuslimSim timed force tests, authored from owner USB/HID captures and bench tests.

No vendor SDK dependency. This session is owned by FeedbackService, never by
the GUI or an additional input reader. Live aircraft effects keep their owner.
"""
from __future__ import annotations
import time
from . import moza_ay210_ffb_protocol as wire
from .moza_feedback_profiles import unit

FIELDS = {'spring': 175, 'damping': 176, 'inertia': 177, 'friction': 178}
PHYSICS = {'spring': 'spring_gain', 'damping': 'damper', 'inertia': 'inertia', 'friction': 'friction'}
MOVEMENT = ('movement', 'roll', 'pitch')
KINDS = (*MOVEMENT, 'vibration', 'constant_force', *FIELDS)


def packet(body):
    return bytes([*body, (sum(body) + 13) & 255])


def validate_controls(device, controls, kind):
    if device not in ('moza_a210', 'moza_ab6') or kind not in KINDS:
        raise ValueError('Unknown hardware test')
    if not isinstance(controls, dict):
        raise ValueError('Test controls must be an object')
    controls = dict(controls)
    for key in ('roll', 'pitch', 'force'):
        controls[key] = unit(controls.get(key, 0), key, -1, 1)
    for key in ('strength', 'vibration'):
        controls[key] = unit(controls.get(key, 1), key)
    controls['seconds'] = unit(controls.get('seconds', 3), 'Test duration', .2, 5)
    physics = controls.get('physics', {})
    confirmed = wire.AB6_PROFILE.confirmed_physics_fields if device == 'moza_ab6' else (
        'spring_gain', 'damper', 'friction', 'inertia', 'overall_intensity', 'max_torque', 'friction_compensation')
    if not isinstance(physics, dict) or set(physics) - set(confirmed):
        raise ValueError('Unknown test resistance field for this base')
    controls['physics'] = {key: unit(value, key) for key, value in physics.items()}
    if kind == 'vibration':
        textures = wire.AB6_RUMBLE_PRESETS if device == 'moza_ab6' else wire.RUMBLE_PRESETS
        if controls.get('texture', 'runway_rumble') not in textures:
            raise ValueError('Choose a verified vibration pattern for this base')
    return controls


def effect_plan(device, kind, controls):
    """Fresh effect blocks: the same definitions and scaling tested on the bench."""
    controls = validate_controls(device, controls, kind)
    setup, updates, channels = [], [], []
    if kind == 'vibration':
        ab6 = device == 'moza_ab6'
        texture = controls.get('texture', 'runway_rumble')
        definition = (wire.AB6_RUMBLE_PRESETS if ab6 else wire.RUMBLE_PRESETS)[texture]
        for index, (reference_channel, frequency) in enumerate(definition['channels'], 1):
            arms = list(wire.AB6_RUMBLE_ARM if ab6 else wire.RUMBLE_CHANNEL_ARM[reference_channel])
            if ab6 and texture == 'gear_bumps':
                arms[-1] = '110404ff7f000000000000ffff04e457000000000000'
            setup.append(('feature', bytes([33, bytes.fromhex(arms[0])[2], 0, 0])))
            for raw in arms:
                frame = bytearray.fromhex(raw)
                frame[1] = index
                setup.append(('hid', bytes(frame)))
            updates.append(wire.build_set_periodic(index, round(definition['reference_magnitude'] * controls.get('vibration', 1)), frequency))
            channels.append(index)
    elif kind in ('damping', 'friction', 'inertia'):
        prefix, effect_type = {'damping': ('110409', 9), 'friction': ('11050b', 11), 'inertia': ('11060a', 10)}[kind]
        reference = next(raw for _, method, raw in wire.CONNECTION_SETUP_SEQUENCE if method == 'hid' and raw.startswith(prefix))
        definition = bytearray.fromhex(reference)
        definition[1] = 1
        setup = [('feature', bytes([33, effect_type, 0, 0])), ('hid', bytes(definition))]
        coefficient = round(32000 * resistance_strength(controls, kind))
        updates = [wire.build_set_condition(1, axis, 0, coefficient, coefficient, 32000, 32000, 0) for axis in (0, 1)]
        channels = [1]
    elif kind == 'constant_force':
        setup = [('feature', bytes.fromhex('21010000')), ('hid', bytes.fromhex('110101ff7f000000000000ffff040000000000000000'))]
        updates = [wire.build_constant_force(round(32000 * controls.get('force', 0)))]
        channels = [1]
    return setup, updates, channels


def resistance_strength(controls, kind):
    return controls.get('physics', {}).get(PHYSICS[kind], controls.get('strength', 1))


class ForceTestSession:
    def __init__(self, device, controls, kind, cancelled, *, clock=time.monotonic,
                 serial_factory=None, ports=None, hid_factory=None):
        controls = validate_controls(device, controls, kind)
        self.device, self.kind, self.controls = device, kind, dict(controls)
        self.cancelled, self.clock = cancelled, clock
        self.serial_factory, self.ports, self.hid_factory = serial_factory, ports, hid_factory
        self.serial = self.hid = None
        self.original, self.changed = {}, []
        self.armed = self.connected = False
        self.deadline = self.heartbeat = self.effect_tick = 0
        self.last_values = None
        self.channels = []
        self.cleanup_errors = []
        self.axes = (0, 1) if kind == 'movement' else (0,) if kind == 'roll' else (1,)

    def _check(self):
        if self.cancelled() or (self.deadline and self.clock() >= self.deadline):
            raise RuntimeError('Test ended or cancelled; output is off.')

    def _read(self, address, sub=0, axis=None, *, cleanup=False):
        if not cleanup:
            self._check()
        short = address == 225 and axis is None
        body = [126, 2, 30, 18, address, sub] if short else [126, 3, 30, 18, address, sub, axis or 0]
        self.serial.write(packet(body))
        end, buf = self.clock() + .35, bytearray()
        while self.clock() < end:
            if not cleanup:
                self._check()
            buf.extend(self.serial.read(4096))
            while len(buf) >= 5:
                if buf[0] != 126:
                    del buf[0]
                    continue
                size = buf[1] + 5
                if len(buf) < size:
                    break
                frame = bytes(buf[:size])
                del buf[:size]
                if packet(list(frame[:-1])) != frame or frame[2] != 158 or frame[4] != address:
                    continue
                if address == 225 and (frame[5] != sub or (axis is not None and (len(frame) != 9 or frame[6] != axis))):
                    continue
                if len(frame) != (9 if axis is not None else 8):
                    continue
                return frame[7] if axis is not None else frame[6]
        raise TimeoutError(f'Hardware setting {address:02x}/{sub:02x} did not reply')

    def _remember(self, address, sub=0, axis=None):
        key = (address, sub, axis)
        value = self._read(*key)
        if not 0 <= value <= 100:
            raise RuntimeError('Unexpected original hardware setting; test cancelled')
        self.original[key] = value
        return value

    def _set(self, address, value, sub=0, axis=None, *, cleanup=False):
        key = (address, sub, axis)
        if not cleanup:
            self._check()
            if key not in self.original:
                raise RuntimeError('Cannot change a setting without its original readback')
            if key not in self.changed:
                self.changed.append(key)  # restore even if the write/readback fails
        body = [126, 3, 31, 18, address, sub, value] if axis is None else [126, 4, 31, 18, address, sub, axis, value]
        self.serial.write(packet(body))
        if self._read(*key, cleanup=cleanup) != value:
            raise RuntimeError(f'Hardware setting {address:02x}/{sub:02x} did not read back {value}')

    def _hid(self, frame, feature=False):
        self._check()
        written = self.hid.send_feature_report(frame) if feature else self.hid.write(frame)
        # Windows HIDAPI may report the padded output-report size. A larger
        # count is a successful write, not a truncated command.
        if not isinstance(written, int) or written < len(frame):
            raise IOError(f'Force report 0x{frame[0]:02x} failed: requested {len(frame)} bytes, transport returned {written!r}')

    def start(self):
        try:
            if self.serial_factory is None:
                import serial
                self.serial_factory = serial.Serial
            if self.ports is None:
                from serial.tools import list_ports
                self.ports = list_ports.comports
            pid = 4097 if self.device == 'moza_a210' else 4098
            candidates = [p.device for p in self.ports() if p.vid == 13422 and p.pid == pid]
            if len(candidates) != 1:
                raise RuntimeError('Connect exactly one matching base before testing')
            self._check()
            self.serial = self.serial_factory(candidates[0], 115200, timeout=.02, write_timeout=.3)
            self.serial.reset_input_buffer()
            if self._read(153) != 0 or self._read(225, 7) != 0:
                raise RuntimeError('Another output session is active. Close the other hardware owner first.')
            if self.kind in MOVEMENT:
                if self._read(225, 6) != 1:
                    raise RuntimeError('Position-follow is not enabled on this base; no settings changed')
                for axis in self.axes:
                    self._remember(225, 10, axis)
                    self._remember(225, 9, axis)
                self._remember(175)
            else:
                if self._remember(133) not in (0, 1, 2):
                    raise RuntimeError('Unexpected base mode; test cancelled')
                for address in FIELDS.values():
                    self._remember(address)
                if self.kind in ('damping', 'friction', 'inertia'):
                    self._remember(174)
            self.hid = (self.hid_factory or wire.open_ay210)(vid=13422, pid=pid)
            self._hid(bytes.fromhex('1c03'))
            if self.kind in MOVEMENT:
                for axis in self.axes:
                    self._set(225, round(100 * self.controls.get('strength', 1)), 10, axis)
                self._set(175, 100)
                for axis in self.axes:
                    self._set(225, 100, 9, axis)
                self._check()
                self.armed = True  # cleanup required even after a partial activation write
                self.serial.write(bytes.fromhex('7e041f12e1000bb864'))
                self.serial.write(bytes.fromhex('7e031f12e10701a8'))
                self._targets()
            else:
                setup, updates, self.channels = effect_plan(self.device, self.kind, self.controls)
                if self.kind in ('damping', 'friction', 'inertia'):
                    self._set(174, 100)  # AB6 capture AE=100; bench-confirmed stronger resistance
                for name, address in FIELDS.items():
                    self._set(address, round(100 * resistance_strength(self.controls, name)) if name == self.kind else 0)
                if setup:
                    self._set(133, 1)
                for method, frame in setup:
                    self._hid(frame, method == 'feature')
                    time.sleep(.015)  # capture-tested allocation pacing, setup only
                for frame in updates:
                    self._hid(frame)
                if setup:
                    self._hid(bytes.fromhex('1df2'))
                self._check()
                self.armed = True
                self.serial.write(bytes.fromhex('7e041f12e1000bb864'))
            self._check()
            self.serial.write(bytes.fromhex('7e031f12990064bc'))
            self.deadline = self.clock() + self.controls.get('seconds', 3)
            self.connected = True
            self.last_values = self._values()
        except Exception:
            self.stop()
            raise

    def _targets(self):
        frames = []
        for axis in self.axes:
            target = self.controls.get(('roll', 'pitch')[axis], 0)
            position = round(32767 + target * (32768 if target >= 0 else 32767))
            frames.append(packet([126, 6, 31, 18, 225, 12, axis, position >> 8, position & 255, 20]))
        self._check()
        self.serial.write(b''.join(frames))  # both diagonal targets before gain-on

    def _values(self):
        if self.kind in MOVEMENT:
            return tuple(self.controls.get(('roll', 'pitch')[axis], 0) for axis in self.axes) + (self.controls.get('strength', 1),)
        if self.kind in FIELDS:
            return (resistance_strength(self.controls, self.kind),)
        if self.kind == 'vibration':
            return (self.controls.get('vibration', 1),)
        return (self.controls.get('force', 0),)

    def update(self, controls):
        controls = validate_controls(self.device, controls, self.kind)
        if controls.get('texture') != self.controls.get('texture'):
            raise ValueError('Stop before changing the vibration pattern')
        self.controls = dict(controls)

    def tick(self, read=None):
        self._check()
        values = self._values()
        if values != self.last_values:
            if self.kind in MOVEMENT:
                if values[-1] != self.last_values[-1]:
                    for axis in self.axes:
                        self._set(225, round(values[-1] * 100), 10, axis)
                self._targets()
            else:
                if self.kind in FIELDS:
                    self._set(FIELDS[self.kind], round(values[0] * 100))
                _, updates, _ = effect_plan(self.device, self.kind, self.controls)
                for frame in updates:
                    self._hid(frame)
            self.last_values = values
        now = self.clock()
        if now >= self.heartbeat:
            self.serial.write(bytes.fromhex('7e041f12e1000bb864'))
            self.heartbeat = now + 1
        if self.channels and now >= self.effect_tick:
            self._hid(bytes.fromhex('1df2'))
            for channel in self.channels:
                self._hid(bytes([26, channel, 1, 1]))
            self.effect_tick = now + .25
        # Drain command replies on this same owner, never consume joystick HID input.
        if getattr(self.serial, 'in_waiting', 0):
            self.serial.read(min(4096, self.serial.in_waiting))

    def stop(self):
        errors = []
        def attempt(fn):
            try:
                fn()
            except Exception as exc:
                errors.append(str(exc))
        if self.serial:
            if self.armed:
                frames = ['7e031f1299000058']
                if self.kind in MOVEMENT:
                    frames += ['7e031f12e10700a7', '7e021f12e10dac']
                for raw in frames:
                    attempt(lambda raw=raw: self.serial.write(bytes.fromhex(raw)))
            if self.hid:
                attempt(lambda: self.hid.write(bytes.fromhex('1c03')))
            for key in reversed(self.changed):
                attempt(lambda key=key: self._set(key[0], self.original[key], key[1], key[2], cleanup=True))
            if self.armed:
                def verify_off():
                    if self._read(153, cleanup=True) != 0:
                        raise RuntimeError('Motor gain did not read back zero')
                attempt(verify_off)
            attempt(self.serial.close)
        if self.hid:
            attempt(self.hid.close)
        self.serial = self.hid = None
        self.connected = self.armed = False
        self.changed.clear()
        self.cleanup_errors.extend(errors)
        if errors:
            raise RuntimeError('Output cleanup needs attention: ' + '; '.join(errors))

    def status_snapshot(self):
        return {'running': self.connected, 'connected': self.connected, 'test_path': 'MuslimSim capture-tested output'}

    def diagnostics_snapshot(self):
        return {'test_kind': self.kind, 'cleanup_errors': list(self.cleanup_errors), 'unsupported_effects': [],
                'requested_constant_force': round(32000 * self.controls.get('force', 0)) if self.kind == 'constant_force' else None}
