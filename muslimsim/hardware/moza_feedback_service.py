"""One bounded FFB worker per base, usable before and during simulator connection."""
from __future__ import annotations
import copy
import threading
import time
from . import ffb_profiles as profiles
from . import moza_ay210_ffb_protocol as protocol
from .moza_ay210_ffb_engine import MozaAy210FfbEngine
from .moza_feedback_profiles import Repository, validate, compile_document, unit
from .force_test_session import ForceTestSession, validate_controls


class FeedbackService:
    def __init__(self, device, read_dataref, online, *, auto_live=False, engine_factory=MozaAy210FfbEngine, clock=time.monotonic, reconnect_delay=6.0, test_factory=ForceTestSession):
        self.device = device
        self.repository = Repository(device)
        self.protocol = protocol.AB6_PROFILE if device == 'moza_ab6' else protocol.AY210_PROFILE
        self.read_dataref, self.online = read_dataref, online
        self.clock, self.engine_factory = clock, engine_factory
        self.test_factory = test_factory
        self.reconnect_delay = reconnect_delay
        self.reconnect_after = clock() + reconnect_delay
        self.lock = threading.RLock()
        self.shutdown = threading.Event()
        self.wake = threading.Event()
        self.mode = 'live' if auto_live else 'stopped'
        self.revision = 0
        self.document = None
        self.path = None
        self.dirty = False
        self.error = ''
        self.test = {}
        self.test_kind = 'movement'
        self.test_result = ''
        self.test_seconds = 3.0
        self.lease = 0.0
        self.test_deadline = 0.0
        self.test_requested = 0.0
        self.test_not_before = 0.0
        self.engine_status = {}
        self.engine_diagnostics = {}
        self.last_tick = 0.0
        self.tick_count = 0
        self.missing = []
        self.thread = None
        name = profiles.load_active_profile_name(self.repository.active_path)
        if name:
            try:
                self.document, self.path = self.repository.load(name)
            except Exception as exc:
                self.error = str(exc)

    def start_worker(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name='MuslimSim-FFB-'+self.device, daemon=True)
            self.thread.start()

    def close(self):
        self.shutdown.set()
        self.wake.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=4)

    def status(self):
        with self.lock:
            return dict(self.engine_status, mode=self.mode,
                        active_profile=self.document.get('name') if self.document else None,
                        source_file=str(self.path) if self.path else None, dirty=self.dirty,
                        last_error=self.error, last_tick=self.last_tick,
                        test_countdown=max(0,self.test_not_before-self.clock()) if self.mode=='test' else 0,
                        test_result=self.test_result, requested_constant_force=self.engine_diagnostics.get('requested_constant_force'), tick_count=self.tick_count, test_remaining=max(0,self.test_deadline-self.clock()),
                        missing_datarefs=list(self.missing), output_owner='managed-feedback',
                        reconnect_remaining=max(0,self.reconnect_after-self.clock()),
                        unsupported_effects=list(self.engine_diagnostics.get('unsupported_effects',[])))

    def diagnostics(self):
        with self.lock:
            return dict(self.engine_diagnostics, **self.status())

    def command(self, action, payload):
        try:
            return self._command(action, payload)
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def _command(self, action, payload):
        action = str(action).strip().lower()
        if action == 'list_profiles':
            entries, errors = self.repository.entries()
            names = set(entries)
            if self.device == 'moza_a210':
                names.update(raw['name'] for raw in profiles.PRESETS.values())
            return {'ok':True,'profiles':sorted(names),'errors':errors,'active_profile':self.status()['active_profile']}
        if action == 'select_profile':
            raw, path = self.repository.load(str(payload.get('name','')))
            self.repository.select(raw['name'])
            with self.lock:
                self.document, self.path, self.dirty = raw, path, False
                self.revision += 1
                self.error = ''
                if self.mode == 'test': self.mode = 'stopped'
            self.wake.set()
            return {'ok':True}
        if action == 'get_profile':
            with self.lock:
                fields = self.protocol.confirmed_physics_fields or tuple(profiles.PHYSICS_FIELD_DEFAULTS)
                return {'ok':True, 'document':copy.deepcopy(self.document), 'source_file':str(self.path) if self.path else None,
                        'textures':sorted(protocol.AB6_RUMBLE_PRESETS if self.device=='moza_ab6' else protocol.RUMBLE_PRESETS), 'physics_fields':list(fields), 'status':self.status()}
        if action in ('update_profile','save_document'):
            raw = validate(payload.get('document'), self.device)
            # Validate compiled curves, not just the editable document.
            compile_document(raw,self.device)
            with self.lock:
                path = self.path
            if action == 'save_document':
                raw,path=self.repository.save(raw,path,create=bool(payload.get('save_as')))
                self.repository.select(raw['name'])
            with self.lock:
                self.document, self.path = raw,path
                self.dirty = action == 'update_profile'
                self.revision += 1
                if self.mode == 'test':self.mode='stopped'
                self.error=''
            self.wake.set()
            return {'ok':True, 'path':str(path) if path else None}
        if action == 'save_profile':
            # Legacy New Preset button now retains the complete current document.
            with self.lock:
                raw=copy.deepcopy(self.document) if self.document else {'schema':1,'device':self.device,'physics':{},'effects':[]}
            raw['name']=str(payload.get('name','')).strip()
            if not raw['name']:raise ValueError('Enter a preset name')
            return self._command('save_document',{'document':raw,'save_as':True})
        if action in ('stop','stop_test'):
            with self.lock:
                if action == 'stop_test' and self.mode != 'test':return {'ok':True}
                if self.mode=='test':self.test_result='Test stopped.'
                self.mode='stopped';self.test_deadline=0;self.revision+=1
            self.wake.set()
            return {'ok':True}
        if action == 'enable_live':
            with self.lock:
                if not self.document:raise ValueError('Load a preset first')
                if not self.document.get('tuning',{}).get('enabled',True):raise ValueError('Enable feedback in the preset first')
                self.mode='live';self.revision+=1;self.error=''
            self.wake.set()
            return {'ok':True}
        if action == 'test_heartbeat':
            with self.lock:self.lease=self.clock()
            return {'ok':True,'status':self.status()}
        if action in ('test_start','test_update'):
            controls=copy.deepcopy(payload.get('controls') or {})
            kind=str(payload.get('kind','movement'))
            controls=validate_controls(self.device,controls,kind)  # validate everything before activation
            seconds=unit(controls.get('seconds',3),'Test duration',.2,5)
            with self.lock:
                if action == 'test_update' and self.mode != 'test':
                    return {'ok':True, 'inactive':True}
                if action == 'test_update' and kind != self.test_kind:
                    raise ValueError('Stop before changing the test type')
                if action == 'test_update' and controls.get('texture') != self.test.get('texture'):
                    raise ValueError('Stop before changing the vibration texture')
                self.test=controls
                self.lease=self.clock()
                if action == 'test_start':
                    self.mode='test';self.test_kind=kind;self.test_seconds=seconds
                    self.test_requested=self.clock();self.test_deadline=0;self.test_result=''
                    self.test_not_before=self.test_requested+3.0 if kind=='constant_force' else 0.0
                    self.revision+=1;self.error=''
            self.wake.set()
            return {'ok':True}
        if action in ('set_physics','set_effect_gain'):
            # Compatibility controls are edits to the draft, no hidden overrides.
            with self.lock:raw=copy.deepcopy(self.document)
            if raw is None:raise ValueError('Load a preset first')
            overrides=payload.get('overrides') or {}
            if action == 'set_physics':
                for key,value in overrides.items():
                    if key not in (self.protocol.confirmed_physics_fields or profiles.PHYSICS_FIELD_DEFAULTS):
                        raise ValueError('That physics field is not confirmed for this base')
                    raw.setdefault('physics',{})[key]=unit(value,key)
            else:
                for key,value in overrides.items():
                    raw.setdefault('tuning',{}).setdefault('effects',{}).setdefault(key,{})['strength']=unit(value,key,0,2)
            return self._command('update_profile',{'document':raw})
        raise ValueError('Unsupported feedback action')

    def _expired(self, now):
        return self.mode=='test' and (now-self.lease>1.5 or
            (self.test_deadline and now>=self.test_deadline) or now-self.test_requested>15)

    def _expiry_result(self, now):
        if self.test_deadline and now>=self.test_deadline:
            return 'Timed test finished. Output is off.'
        if now-self.lease>1.5:
            return 'Test stopped: contact with the test window was lost.'
        return 'Test could not connect. Output is off.'

    def _run(self):
        engine=None;applied=-1
        try:
            while not self.shutdown.is_set():
                now=self.clock()
                with self.lock:
                    if self._expired(now):
                        self.test_result=self._expiry_result(now)
                        if not self.test_deadline and now-self.test_requested>15:
                            self.error='MOZA output connection timed out before the test started. Check base power and close MOZA Cockpit, then retry.'
                        self.mode='stopped';self.revision+=1
                    mode,revision=self.mode,self.revision
                    document=copy.deepcopy(self.document) if revision!=applied else None
                    controls=dict(self.test)
                    kind=self.test_kind
                    enabled=bool(self.document and self.document.get('tuning',{}).get('enabled',True))
                    power_ref=(self.document or {}).get('power_dataref','sim/cockpit2/electrical/bus_volts')
                wanted=mode=='test' or (mode=='live' and enabled and self.online())
                if engine is not None and (not wanted or applied!=revision):
                    retiring,engine=engine,None
                    try:
                        retiring.stop()
                    except Exception as exc:
                        with self.lock:
                            self.error=str(exc);self.mode='stopped';self.revision+=1
                        wanted=False
                    self.reconnect_after=self.clock()+self.reconnect_delay
                    with self.lock:self.engine_status={'running':False,'connected':False}
                if not wanted:
                    self.wake.wait(.1);self.wake.clear();continue
                # A constant push can begin sharply. The bridge enforces the
                # preparation interval, so delayed/repeated UI messages cannot
                # bypass it. Stop, a replacement test or a lost UI lease cancels it.
                if mode=='test' and self.clock()<self.test_not_before:
                    with self.lock:self.engine_status={'running':False,'connected':False}
                    self.wake.wait(.05);self.wake.clear();continue
                try:
                    cache={};missing=set()
                    def read(ref):
                        if not self.online():return None
                        if ref not in cache:
                            try:cache[ref]=self.read_dataref(ref)
                            except Exception:cache[ref]=None
                            if cache[ref] is None:missing.add(ref)
                        return cache[ref]
                    # Master power gate is separate from effect gates. No telemetry -> no output.
                    if mode=='live':
                        power=read(power_ref)
                        if power is None or power<1:
                            if engine is not None:
                                engine.stop();engine=None
                                self.reconnect_after=self.clock()+self.reconnect_delay
                            with self.lock:
                                self.engine_status={'running':False,'connected':False,'waiting_for_power':True}
                                self.missing=sorted(missing)
                            self.wake.wait(.2);self.wake.clear();continue
                    if engine is None:
                        # Full feedback sessions need longer than idle polls to
                        # finish disconnecting. A quick reopen otherwise preserves
                        # the old connection and never emits a fresh Connected.
                        if self.clock()<self.reconnect_after:
                            self.wake.wait(.1);self.wake.clear();continue
                        if document is None:
                            with self.lock:document=copy.deepcopy(self.document)
                        if mode=='test':
                            def cancelled(expected=revision):
                                with self.lock:
                                    return (self.shutdown.is_set() or self.mode!='test' or
                                            self.revision!=expected or self._expired(self.clock()))
                            engine=self.test_factory(self.device,controls,kind,cancelled,clock=self.clock)
                        else:
                            engine=self.engine_factory(device_profile=self.protocol)
                            engine.set_active_profile(compile_document(document,self.device))
                        engine.start()
                        applied=revision
                        if mode=='test':
                            with self.lock:
                                if self.mode==mode and self.revision==revision:
                                    self.test_deadline=engine.deadline
                    with self.lock:
                        if self.shutdown.is_set() or self.mode != mode or self.revision != revision:
                            continue
                        if self._expired(self.clock()):
                            self.test_result=self._expiry_result(self.clock())
                            if not self.test_deadline and self.clock()-self.test_requested>15:
                                self.error='MOZA output connection timed out before the test started. Check base power and close MOZA Cockpit, then retry.'
                            self.mode='stopped';self.revision+=1
                            continue
                    if mode=='test':engine.update(controls)
                    engine.tick(read)
                    snapshot=engine.status_snapshot()
                    diagnostics=engine.diagnostics_snapshot()
                    with self.lock:
                        self.engine_status=snapshot;self.engine_diagnostics=diagnostics
                        self.last_tick=self.clock();self.tick_count+=1;self.missing=sorted(missing)
                        if mode=='test' and snapshot.get('connected') and not self.test_deadline:
                            self.test_deadline=self.clock()+self.test_seconds
                except Exception as exc:
                    engine_cleanup_error=''
                    if engine is not None:
                        try:engine.stop()
                        except Exception as cleanup_exc:engine_cleanup_error=str(cleanup_exc)
                        if not engine_cleanup_error and getattr(engine,'cleanup_errors',None):
                            engine_cleanup_error='Output cleanup needs attention: '+'; '.join(engine.cleanup_errors)
                    engine=None
                    self.reconnect_after=self.clock()+self.reconnect_delay
                    with self.lock:
                        if self.revision==revision:
                            if mode=='test' and self._expired(self.clock()) and not engine_cleanup_error:
                                self.test_result=self._expiry_result(self.clock())
                            else:
                                self.error=str(exc)+(('; '+engine_cleanup_error) if engine_cleanup_error else '')
                            self.mode='stopped'
                        elif engine_cleanup_error:
                            self.error=engine_cleanup_error;self.mode='stopped';self.revision+=1
                        self.engine_status={'running':False,'connected':False}
                self.wake.wait(.03);self.wake.clear()
        finally:
            if engine is not None:
                try:engine.stop()
                except Exception as exc:
                    with self.lock:self.error=str(exc)
            with self.lock:self.engine_status={'running':False,'connected':False}


def install(server, read_dataref, online, *, auto_a210=False, auto_ab6=False):
    from ..control.server import DeviceRegistration
    services=[]
    for device,auto in [('moza_a210',auto_a210),('moza_ab6',auto_ab6)]:
        service=FeedbackService(device,read_dataref,online,auto_live=auto)
        server.register(DeviceRegistration(device+'_ffb',start=lambda s=service:s.command('enable_live',{}),
            stop=lambda s=service:s.command('stop',{}),status=service.status,
            diagnostics=service.diagnostics,command=service.command))
        service.start_worker();services.append(service)
    server._moza_feedback_services=services
    return services
