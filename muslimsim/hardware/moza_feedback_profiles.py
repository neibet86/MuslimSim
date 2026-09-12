"""File-backed MOZA calibration documents, preserving user-authored curves."""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid
import re
from . import ffb_profiles as profiles
from . import moza_ay210_ffb_protocol as protocol


def unit(value, label, low=0.0, high=1.0):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def validate(document, device):
    raw = copy.deepcopy(document)
    if raw.get('device') != device:
        raise ValueError('This preset belongs to a different MOZA base.')
    profiles.build_profile(raw)
    tuning = raw.setdefault('tuning', {})
    if not isinstance(tuning, dict):
        raise ValueError('tuning must be an object')
    if type(tuning.setdefault('enabled', True)) is not bool:
        raise ValueError('Feedback enabled must be true or false')
    effects = tuning.setdefault('effects', {})
    if not isinstance(effects, dict):
        raise ValueError('Effect tuning must be an object')
    known = {e.get('id') or f"{e['kind']}_{i+1}": e for i, e in enumerate(raw['effects'])}
    if len(known) != len(raw['effects']):
        raise ValueError('Effect names must be unique')
    if set(effects) - set(known):
        raise ValueError('Tuning references an unknown effect')
    for key, setting in effects.items():
        if not isinstance(setting, dict) or type(setting.get('enabled', True)) is not bool:
            raise ValueError('Effect enabled must be true or false')
        unit(setting.get('strength', 1), key, 0, 2)
        if 'texture' in setting and (known[key]['kind'] != 'rumble' or setting['texture'] not in protocol.RUMBLE_PRESETS):
            raise ValueError('Choose a captured vibration texture')
    test = tuning.setdefault('test', {})
    for key, default in [('strength', .15), ('vibration', .15), ('roll', 0), ('pitch', 0), ('force', 0)]:
        unit(test.get(key, default), key, -1 if key in ('roll', 'pitch', 'force') else 0, 1)
    physics=test.get('physics',{})
    confirmed=protocol.AB6_PROFILE.confirmed_physics_fields if device=='moza_ab6' else profiles.PHYSICS_FIELD_DEFAULTS
    if not isinstance(physics,dict) or set(physics)-set(confirmed):
        raise ValueError('Unknown test resistance field for this base')
    for field,value in physics.items():unit(value,field)
    unit(test.get('seconds', 3), 'Test duration', .2, 5)
    if test.get('texture', 'runway_rumble') not in protocol.RUMBLE_PRESETS:
        raise ValueError('Unknown vibration texture')
    return raw


def compile_document(document, device):
    raw = validate(document, device)
    tune = raw['tuning']
    if not tune['enabled']:
        raw['effects'] = []
        raw['physics'] = {field: 0.0 for field in profiles.PHYSICS_FIELD_DEFAULTS}
    else:
        effects = []
        for i, effect in enumerate(raw['effects']):
            key = effect.get('id') or f"{effect['kind']}_{i+1}"
            effect['id'] = key
            setting = tune['effects'].get(key, {})
            if not setting.get('enabled', True):
                continue
            strength = float(setting.get('strength', 1))
            effect['curve'] = list(effect.get('curve') or []) + [
                {'kind': 'scale', 'options': {'in_min': -1, 'in_max': 1,
                 'out_min': -strength, 'out_max': strength, 'clamp': False}}]
            if effect['kind'] == 'rumble' and setting.get('texture'):
                effect['preset'] = setting['texture']
            effects.append(effect)
        raw['effects'] = effects
    return profiles.build_profile(raw)


class Repository:
    def __init__(self, device):
        if device not in profiles.ALLOWED_DEVICES:
            raise ValueError('Unknown MOZA base')
        self.device = device
        self.directory = profiles.default_ffb_profile_dir(device)
        self.active_path = profiles.default_active_profile_path(device)

    def entries(self):
        store = profiles.FfbProfileStore(self.directory)
        store.discover()
        return {k: p for k, p in store.profiles.items() if p.device == self.device}, store.errors

    def load(self, name):
        entries, errors = self.entries()
        # Files always win over old built-in names and aliases.
        if name in entries:
            path = entries[name].source_path
            return validate(json.loads(path.read_text(encoding='utf-8')), self.device), path
        if self.device == 'moza_a210':
            for slug, raw in profiles.PRESETS.items():
                if name in (slug, raw['name']):
                    return self.save(validate(raw, self.device), create=True)
        raise ValueError(f'Preset {name!r} was not found')

    def save(self, document, path=None, *, create=False):
        raw = validate(document, self.device)
        self.directory.mkdir(parents=True, exist_ok=True)
        if create or path is None:
            names, _ = self.entries()
            if raw['name'] in names:
                raise ValueError('A preset with that name already exists. Choose another name.')
            filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(raw['name'])).strip(' .') or 'Preset'
            path = self.directory / (filename + '.mslm')
            index = 2
            while path.exists():
                path = self.directory / (filename + f' ({index}).mslm')
                index += 1
        path = Path(path).resolve()
        if path.parent != self.directory.resolve():
            raise ValueError('Import the preset before saving changes')
        if path.exists():
            backups = self.directory.parent / 'ffb_backups' / self.device
            backups.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backups / (path.stem + '_' + str(time.time_ns()) + '.mslm'))
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(raw, indent=2) + '\n', encoding='utf-8')
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return raw, path

    def select(self, name):
        profiles.save_active_profile_name(self.active_path, name)
        if profiles.load_active_profile_name(self.active_path) != name:
            raise ValueError('Could not save preset selection')


def test_profile(device, controls, kind='movement'):
    strength = unit(controls.get('strength', .15), 'Strength')
    effects = []
    if kind == 'movement':
        cap=1.0
        for axis in ('roll', 'pitch'):
            unit(controls.get(axis, 0), axis, -1, 1)
            effects.extend([
                {'kind': 'spring', 'id': axis+'_spring', 'axis': axis, 'deadband': 0.0, 'dataref': 'test.strength',
                 'curve': [{'kind':'scale','options':{'in_max':cap,'out_min':0,'out_max':cap}}]},
                {'kind': 'trim', 'id': axis+'_position', 'axis': axis, 'dataref': 'test.'+axis,
                 'curve': [{'kind':'scale','options':{'in_min':-1,'in_max':1,'out_min':-1,'out_max':1}}]},
            ])
    elif kind == 'vibration':
        texture = controls.get('texture', 'runway_rumble')
        supported=protocol.AB6_RUMBLE_PRESETS if device=='moza_ab6' else protocol.RUMBLE_PRESETS
        if texture not in supported:
            raise ValueError('Unknown captured vibration texture')
        gain = unit(controls.get('vibration', .15), 'Vibration')
        effects = [{'kind':'rumble','id':'test_vibration','dataref':'test.vibration','preset':texture,
                    'curve':[{'kind':'scale','options':{'out_min':0,'out_max':1}}]}]
    elif kind == 'constant_force':
        # Its signed channel competes with spring/trim; test it in isolation.
        gain = unit(controls.get('force', 0), 'Force', -1, 1) * strength
        effects = [{'kind':'constant_force','id':'test_force','dataref':'test.force_gain','max_magnitude':32000,
                    'curve':[{'kind':'scale','options':{'in_min':-1,'in_max':1,'out_min':-1,'out_max':1}}]}]
    else:
        raise ValueError('Unknown test type')
    confirmed = protocol.AB6_PROFILE.confirmed_physics_fields if device == 'moza_ab6' else tuple(profiles.PHYSICS_FIELD_DEFAULTS)
    overrides = controls.get('physics', {})
    if not isinstance(overrides, dict) or set(overrides) - set(confirmed):
        raise ValueError('Only confirmed resistance fields may be tested on this base')
    for field,value in overrides.items():unit(value,field)
    physics = {field:{'dataref':'test.physics.'+field,'curve':[{'kind':'scale','options':{'out_min':0,'out_max':1}}]} for field in confirmed}
    return profiles.build_profile({'schema':1,'device':device,'name':'Timed hardware test',
                                   'physics':physics,'effects':effects})


def effect_templates():
    def scale(a,b,c,d):
        return [{'kind':'scale','options':{'in_min':a,'in_max':b,'out_min':c,'out_max':d}}]
    def when(key,a,b):return {'kind':'when','options':{'key':key,'min':a,'max':b}}
    speed='sim/flightmodel/position/indicated_airspeed'
    ground='sim/flightmodel/failures/onground_any'
    engine='sim/cockpit2/engine/indicators/N1_percent'
    result={}
    for axis in ('roll','pitch'):
        result[axis.title()+' centering']={'kind':'spring','id':axis+'_spring','axis':axis,
            'dataref':speed,'curve':scale(0,250,.2,.8)}
        result[axis.title()+' trim']={'kind':'trim','id':axis+'_trim','axis':axis,
            'dataref':'sim/cockpit2/controls/'+('aileron_trim' if axis=='roll' else 'elevator_trim'),
            'curve':scale(-1,1,-.25,.25)}
    result['Road bumps']={'kind':'rumble','id':'road_bumps','preset':'runway_rumble',
        'dataref':'sim/flightmodel/position/groundspeed','curve':scale(0,30,0,1),
        'gate':[when(ground,.5,1.5)]}
    for index in (0,1):
        result[f'Engine {index+1} rumble']={'kind':'rumble','id':f'engine_{index+1}','preset':'engine_rumble',
            'dataref':engine+f'[{index}]','curve':scale(0,100,0,1)}
    result['Gear buffet']={'kind':'rumble','id':'gear_buffet','preset':'gear_buffet',
        'dataref':speed,'curve':scale(80,250,0,1),
        'gate':[when(ground,-.1,.1),when('sim/cockpit2/controls/gear_handle_down',.5,1.5)]}
    result['Flap buffet']={'kind':'rumble','id':'flap_buffet','preset':'flap_buffet',
        'dataref':'sim/cockpit2/controls/flap_ratio','curve':scale(0,1,0,1),
        'gate':[when(speed,100,999)]}
    result['Spoiler buffet']={'kind':'rumble','id':'spoiler_buffet','preset':'spoiler_buffet',
        'dataref':'sim/cockpit2/controls/speedbrake_ratio','curve':scale(0,1,0,1),
        'gate':[when(speed,100,999),when(ground,-.1,.1)]}
    result['Stall buffet']={'kind':'rumble','id':'stall_buffet','preset':'stall_buffet',
        'dataref':'sim/cockpit2/annunciators/stall_warning','curve':scale(0,1,0,1)}
    result['Constant force']={'kind':'constant_force','id':'constant_force','dataref':speed,'curve':scale(0,250,0,.2)}
    return result


def starter_document(device, name, airbus=False):
    templates=effect_templates()
    keys=['Pitch centering','Roll centering','Road bumps','Engine 1 rumble','Engine 2 rumble',
          'Gear buffet','Flap buffet','Spoiler buffet','Stall buffet']
    if not airbus:keys.append('Pitch trim')
    effects=[templates[key] for key in keys]
    return validate({'schema':1,'device':device,'name':name,'effects':effects,
        'power_dataref':'AirbusFBW/DCBusVoltages[0]' if airbus else 'sim/cockpit2/electrical/bus_volts[0]',
        'physics':{'spring_gain':.35,'damper':.15,'inertia':.05,'friction':.02,
                   'overall_intensity':.5,'max_torque':.5},
        'tuning':{'enabled':True,'effects':{e['id']:{'enabled':True,'strength':.15 if e['kind']=='rumble' else .5} for e in effects},
                  'test':{'roll':0,'pitch':0,'strength':.15,'vibration':.15,'seconds':3,'texture':'runway_rumble'}},
        'validation_note':'Conservative starter. Verify aircraft signals and tune on the actual base. Airbus has no automatic trim-follow effect.'},device)
