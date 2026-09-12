"""Shared, explicit file editor and timed hardware tests for both MOZA bases."""
from __future__ import annotations
import copy
import json
import math
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from ..hardware.ffb_profiles import default_ffb_profile_dir, PHYSICS_FIELD_DEFAULTS


class FeedbackWindow(tk.Toplevel):
    def __init__(self, studio, device):
        super().__init__(studio)
        self.studio, self.device = studio, device
        self.alive = True
        self.action_error = ""
        self.document = None
        self.loading = False
        self.pending = None
        self.active_test = None
        self.physics_vars = {}
        self.effect_index = None
        self.title(('MOZA AB6' if device=='moza_ab6' else 'MOZA A210')+' — Feedback & Tests')
        self.geometry('880x730');self.minsize(760,650)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.status_text=tk.StringVar(value='Loading preset…')
        self.source_text=tk.StringVar()
        self.name=tk.StringVar()
        top=ttk.Frame(self,padding=12);top.pack(fill='x')
        self.presets=ttk.Combobox(top,textvariable=self.name,state='readonly',width=39)
        self.presets.pack(side='left',fill='x',expand=True)
        self.presets.bind('<<ComboboxSelected>>',lambda e:self.select())
        for label,cmd in [('New…',self.new_preset),('Browse…',self.browse),('Save',self.save),('Save As…',lambda:self.save(True))]:
            ttk.Button(top,text=label,command=cmd).pack(side='left',padx=4)
        ttk.Label(self,textvariable=self.source_text,wraplength=840).pack(fill='x',padx=12)
        actions=ttk.Frame(self,padding=12);actions.pack(fill='x')
        self.master_enabled=tk.BooleanVar(value=True)
        ttk.Checkbutton(actions,text='Preset flight feedback enabled',variable=self.master_enabled).pack(side='left')
        ttk.Button(actions,text='Apply changes',command=self.apply).pack(side='left',padx=8)
        ttk.Button(actions,text='Enable flight feedback',command=self.enable).pack(side='left',padx=8)
        tk.Button(actions,text='STOP ALL FEEDBACK',command=self.stop,bg='#a52b32',fg='white',font=('Segoe UI',10,'bold')).pack(side='right')
        notebook=ttk.Notebook(self);notebook.pack(fill='both',expand=True,padx=12,pady=8)
        self.effect_tab=ttk.Frame(notebook,padding=12)
        self.physics_tab=ttk.Frame(notebook,padding=12)
        self.test_tab=ttk.Frame(notebook,padding=12)
        self.advanced_tab=ttk.Frame(notebook,padding=12)
        self.test_resistance_tab=ttk.Frame(notebook,padding=12)
        for tab,title in [(self.effect_tab,'Flight effects'),(self.physics_tab,'Resistance'),(self.test_tab,'Hardware tests'),(self.test_resistance_tab,'Test resistance'),(self.advanced_tab,'Full preset')]:
            notebook.add(tab,text=title)
        from ..hardware.moza_feedback_profiles import effect_templates
        add_row=ttk.Frame(self.effect_tab);add_row.pack(fill='x',pady=(0,8))
        self.add_effect_name=tk.StringVar(value='Road bumps')
        ttk.Combobox(add_row,textvariable=self.add_effect_name,values=list(effect_templates()),state='readonly',width=27).pack(side='left')
        ttk.Button(add_row,text='Add effect',command=self.add_effect).pack(side='left',padx=8)
        ttk.Button(add_row,text='Remove selected effect',command=self.remove_effect).pack(side='left')
        self.effects=ttk.Treeview(self.effect_tab,columns=('kind','enabled'),show='tree headings',height=10,selectmode='browse')
        self.effects.heading('#0',text='Effect');self.effects.heading('kind',text='Type');self.effects.heading('enabled',text='Enabled')
        self.effects.column('#0',width=270);self.effects.column('kind',width=100);self.effects.column('enabled',width=70)
        self.effects.pack(fill='x');self.effects.bind('<<TreeviewSelect>>',self.choose_effect)
        self.effect_enabled=tk.BooleanVar(value=True)
        self.effect_strength=tk.DoubleVar(value=100)
        self.effect_texture=tk.StringVar()
        row=ttk.Frame(self.effect_tab);row.pack(fill='x',pady=8)
        ttk.Checkbutton(row,text='Effect enabled',variable=self.effect_enabled,command=self.flush_effect).pack(side='left')
        self.texture=ttk.Combobox(row,textvariable=self.effect_texture,state='readonly',width=25)
        self.texture.pack(side='right');self.texture.bind('<<ComboboxSelected>>',lambda e:self.flush_effect())
        self.slider(self.effect_tab,'Effect strength',self.effect_strength,0,200,lambda v:self.flush_effect())
        ttk.Label(self.effect_tab,text='Vibration texture selects a captured shaking pattern. Save stores these choices in the .mslm file.',wraplength=800).pack(anchor='w',pady=8)
        self.advanced=tk.Text(self.advanced_tab,wrap='none',font=('Consolas',10),undo=True)
        self.advanced.pack(fill='both',expand=True)
        ttk.Button(self.advanced_tab,text='Use edited preset',command=self.use_json).pack(anchor='e',pady=8)
        self.roll=tk.DoubleVar(value=0);self.pitch=tk.DoubleVar(value=0)
        self.force=tk.DoubleVar(value=0);self.test_strength=tk.DoubleVar(value=100);self.vibration=tk.DoubleVar(value=100)
        self.duration=tk.DoubleVar(value=3);self.test_texture=tk.StringVar(value='runway_rumble')
        self.use_preset_resistance=tk.BooleanVar(value=False)
        self.test_physics={}
        for field,label in [('spring_gain','Built-in centering spring'),('damper','Damper'),('friction','Friction'),('inertia','Inertia')]:
            var=tk.DoubleVar(value=100);self.test_physics[field]=var
            self.slider(self.test_resistance_tab,label,var,0,100,self.changed_test)
            kind={'spring_gain':'spring','damper':'damping','friction':'friction','inertia':'inertia'}[field]
            ttk.Button(self.test_resistance_tab,text='Test '+label.lower(),command=lambda kind=kind:self.start_test(kind)).pack(anchor='e')
        ttk.Label(self.test_resistance_tab,text='Preset resistance overrides these controls when selected.',wraplength=760).pack(anchor='w',pady=12)
        ttk.Checkbutton(self.test_tab,text='Use fixed preset settings for resistance tests',variable=self.use_preset_resistance,command=self.changed_test).pack(anchor='w',pady=5)
        self.slider(self.test_tab,'Roll target: left / right',self.roll,-100,100,self.changed_test)
        self.slider(self.test_tab,'Pitch target: forward / back',self.pitch,-100,100,self.changed_test)
        self.slider(self.test_tab,'Movement strength',self.test_strength,0,100,self.changed_test)
        row=ttk.Frame(self.test_tab);row.pack(fill='x',pady=8)
        ttk.Button(row,text='Test roll',command=lambda:self.start_test('roll')).pack(side='left')
        ttk.Button(row,text='Test pitch',command=lambda:self.start_test('pitch')).pack(side='left',padx=4)
        ttk.Button(row,text='Test diagonal',command=lambda:self.start_test('movement')).pack(side='left',padx=4)
        ttk.Button(row,text='Return to centre',command=self.centre).pack(side='left',padx=8)
        ttk.Label(row,text='Seconds (max 5)').pack(side='left',padx=8)
        ttk.Spinbox(row,from_=.2,to=5,increment=.2,textvariable=self.duration,width=5).pack(side='left')
        self.slider(self.test_tab,'Vibration strength',self.vibration,0,100,self.changed_test)
        row=ttk.Frame(self.test_tab);row.pack(fill='x',pady=8)
        self.test_patterns=ttk.Combobox(row,textvariable=self.test_texture,state='readonly',width=28)
        self.test_patterns.pack(side='left')
        ttk.Button(row,text='Test vibration',command=lambda:self.start_test('vibration')).pack(side='left',padx=8)
        self.slider(self.test_tab,'Constant push (independent strength)',self.force,-100,100,self.changed_test)
        ttk.Button(self.test_tab,text='Test constant push separately',command=lambda:self.start_test('constant_force')).pack(anchor='w')
        grip='yoke' if device=='moza_a210' else 'control stick'
        self.constant_warning_text=f'WARNING: The first push can be strong. Keep your hands on the {grip} throughout the test.'
        self.constant_warning=tk.StringVar(value=self.constant_warning_text+' Starts after a 3-second countdown.')
        ttk.Label(self.test_tab,textvariable=self.constant_warning,foreground='#ffb020',font=('Segoe UI',10,'bold'),wraplength=780).pack(anchor='w',pady=(8,0))
        ttk.Label(self.test_tab,text='Targets span full tested travel, not measured degrees. Resistance and constant push reach 32,000. Tests stop automatically and restore original base settings.',wraplength=810).pack(anchor='w',pady=12)
        ttk.Label(self,textvariable=self.status_text,wraplength=840).pack(fill='x',padx=12,pady=10)
        self.refresh()
        self.after(400,self.poll)

    def slider(self,parent,label,var,low,high,command):
        row=ttk.Frame(parent);row.pack(fill='x',pady=5)
        ttk.Label(row,text=label,width=31).pack(side='left')
        value=ttk.Label(row,width=7);value.pack(side='right')
        def update(v):
            value.configure(text=f'{float(v):.0f}%')
            command(v)
        scale=ttk.Scale(row,from_=low,to=high,variable=var,command=update)
        scale.pack(side='left',fill='x',expand=True,padx=8)
        value.configure(text=f'{var.get():.0f}%')

    def send(self,action,payload=None,done=None):
        if action != 'test_heartbeat':self.action_error=''
        def received(response):
            if not self.alive:return
            inner=response.get('result',{})
            if not inner.get('ok'):
                self.action_error=inner.get('error') or response.get('error') or 'Feedback request failed'
                self.status_text.set(self.action_error)
                return
            if done:done(inner)
        sent=self.studio._request('device_command',device=self.device+'_ffb',action=action,payload=payload or {},done=received)
        if sent is False:
            self.active_test=None
            self.status_text.set('Hardware service is starting or disconnected. Wait for Studio to reconnect, then retry.')

    def refresh(self):
        self.send('list_profiles',done=lambda r:self.presets.configure(values=r['profiles']))
        self.send('get_profile',done=self.loaded)

    def loaded(self,result):
        self.loading=True
        self.document=result.get('document')
        self.physics_fields=result.get('physics_fields',[])
        self.texture.configure(values=result.get('textures',[]))
        self.test_patterns.configure(values=result.get('textures',[]))
        self.source_text.set(result.get('source_file') or 'No preset file selected')
        if self.document:
            self.name.set(self.document['name'])
            self.master_enabled.set(self.document.get('tuning',{}).get('enabled',True))
            test=self.document.get('tuning',{}).get('test',{})
            for key,var,scale in [('roll',self.roll,100),('pitch',self.pitch,100),('strength',self.test_strength,100),('vibration',self.vibration,100),('seconds',self.duration,1)]:
                if key in test:var.set(float(test[key])*scale)
            self.test_strength.set(min(100,self.test_strength.get()))
            self.test_texture.set(test.get('texture','runway_rumble'))
            self.use_preset_resistance.set(test.get('use_preset_resistance',False))
            for field,var in self.test_physics.items():var.set(float(test.get('physics',{}).get(field,1))*100)
        self.rebuild_effects();self.rebuild_physics();self.show_json()
        self.loading=False
        self.status_text.set('Loaded. Tests work without the simulator; Apply uses edits and Save writes the preset.')

    def new_preset(self):
        from ..hardware.moza_feedback_profiles import starter_document
        aircraft=self.studio._moza_ffb_current_aircraft_display_name()
        name=simpledialog.askstring('New preset','Preset name:',initialvalue=aircraft or 'My MOZA preset',parent=self)
        if not name:return
        airbus='toliss' in aircraft.lower() or 'airbus' in aircraft.lower() or self.device=='moza_ab6'
        raw=starter_document(self.device,name.strip(),airbus)
        self.stop()
        self.send('save_document',{'document':raw,'save_as':True},lambda r:self.refresh())

    def add_effect(self):
        if self.document is None:
            self.status_text.set('Create or load a preset first.');return
        from ..hardware.moza_feedback_profiles import effect_templates
        effect=effect_templates()[self.add_effect_name.get()]
        if any(e.get('id')==effect['id'] for e in self.document['effects']):
            self.status_text.set('That effect is already in this preset.');return
        self.document['effects'].append(effect)
        self.document.setdefault('tuning',{}).setdefault('effects',{})[effect['id']]={'enabled':True,'strength':.15 if effect['kind']=='rumble' else .5}
        self.rebuild_effects();self.show_json()

    def remove_effect(self):
        if self.document is None or self.effect_index is None:return
        effect=self.document['effects'].pop(self.effect_index)
        self.document.get('tuning',{}).get('effects',{}).pop(effect.get('id'),None)
        self.rebuild_effects();self.show_json()

    def select(self):
        self.stop()
        self.send('select_profile',{'name':self.name.get()},lambda r:self.refresh())

    def browse(self):
        directory=default_ffb_profile_dir(self.device);directory.mkdir(parents=True,exist_ok=True)
        path=filedialog.askopenfilename(parent=self,initialdir=str(directory),filetypes=[('MuslimSim preset','*.mslm')])
        if path:
            self.stop()
            self.send('import_profile',{'path':path},lambda r:self.send('select_profile',{'name':r['name']},lambda result:self.refresh()))

    def rebuild_effects(self):
        self.effect_index=None
        self.effects.delete(*self.effects.get_children())
        for i,effect in enumerate((self.document or {}).get('effects',[])):
            key=effect.get('id') or f"{effect['kind']}_{i+1}"
            settings=self.document.get('tuning',{}).get('effects',{}).get(key,{})
            self.effects.insert('', 'end',iid=str(i),text=key.replace('_',' ').title(),values=(effect['kind'],'Yes' if settings.get('enabled',True) else 'No'))

    def choose_effect(self,event=None):
        rows=self.effects.selection()
        if not rows or not self.document:return
        self.loading=True
        self.effect_index=int(rows[0]);effect=self.document['effects'][self.effect_index]
        key=effect.get('id') or f"{effect['kind']}_{self.effect_index+1}"
        settings=self.document.get('tuning',{}).get('effects',{}).get(key,{})
        self.effect_enabled.set(settings.get('enabled',True));self.effect_strength.set(settings.get('strength',1)*100)
        self.effect_texture.set(settings.get('texture',effect.get('preset','')))
        self.texture.configure(state='readonly' if effect['kind']=='rumble' else 'disabled')
        self.loading=False

    def flush_effect(self):
        if self.loading or self.document is None or self.effect_index is None:return
        effect=self.document['effects'][self.effect_index]
        key=effect.get('id') or f"{effect['kind']}_{self.effect_index+1}"
        setting={'enabled':self.effect_enabled.get(),'strength':self.effect_strength.get()/100}
        if effect['kind']=='rumble':setting['texture']=self.effect_texture.get()
        self.document.setdefault('tuning',{}).setdefault('effects',{})[key]=setting
        self.effects.item(str(self.effect_index),values=(effect['kind'],'Yes' if setting['enabled'] else 'No'))

    def rebuild_physics(self):
        for child in self.physics_tab.winfo_children():child.destroy()
        self.physics_vars={}
        raw=(self.document or {}).get('physics',{})
        for field,default in PHYSICS_FIELD_DEFAULTS.items():
            setting=raw.get(field,default)
            if field not in self.physics_fields:
                ttk.Label(self.physics_tab,text=field.replace('_',' ').title()+' — not confirmed for this base').pack(anchor='w',pady=8)
                continue
            fixed=tk.BooleanVar(value=not isinstance(setting,dict))
            value=tk.DoubleVar(value=(setting if isinstance(setting,(int,float)) else 0)*100)
            self.physics_vars[field]=(fixed,value)
            ttk.Checkbutton(self.physics_tab,text='Use fixed '+field.replace('_',' '),variable=fixed).pack(anchor='w')
            self.slider(self.physics_tab,field.replace('_',' ').title(),value,0,100,self.changed_test)
        ttk.Label(self.physics_tab,text='Leaving a dynamic setting unchecked preserves its original aircraft-driven curve. The Full preset tab exposes every curve and trigger.',wraplength=810).pack(anchor='w',pady=12)

    def controls(self):
        controls={'roll':self.roll.get()/100,'pitch':self.pitch.get()/100,'force':self.force.get()/100,
                  'strength':self.test_strength.get()/100,'vibration':self.vibration.get()/100,
                  'seconds':self.duration.get(),'texture':self.test_texture.get(),
                  'use_preset_resistance':self.use_preset_resistance.get(),
                  'physics':{field:var.get()/100 for field,var in self.test_physics.items()}}
        if self.use_preset_resistance.get():
            controls['physics'].update({field:value.get()/100 for field,(fixed,value) in self.physics_vars.items() if fixed.get()})
        return controls

    def collect(self):
        if self.document is None:
            self.document={'schema':1,'name':'New preset','device':self.device,'physics':{},'effects':[]}
        self.flush_effect()
        self.document.setdefault('tuning',{})['enabled']=self.master_enabled.get()
        self.document['tuning']['test']=self.controls()
        for field,(fixed,value) in self.physics_vars.items():
            if fixed.get():self.document.setdefault('physics',{})[field]=value.get()/100
        return copy.deepcopy(self.document)

    def apply(self,done=None):
        try:raw=self.collect()
        except Exception as exc:self.status_text.set(str(exc));return
        self.send('update_profile',{'document':raw},lambda r:(self.status_text.set('Applied. Save to keep these settings in the .mslm file.'),done() if done else None))
        self.show_json()

    def save(self,save_as=False):
        raw=self.collect()
        if save_as or not self.source_text.get() or self.source_text.get()=='No preset file selected':
            name=simpledialog.askstring('Save preset','Preset name:',initialvalue=raw['name'],parent=self)
            if not name:return
            raw['name']=name.strip();save_as=True
        self.send('save_document',{'document':raw,'save_as':save_as},lambda r:self.refresh())

    def show_json(self):
        self.advanced.delete('1.0','end')
        self.advanced.insert('1.0',json.dumps(self.document or {},indent=2))

    def use_json(self):
        try:raw=json.loads(self.advanced.get('1.0','end'))
        except Exception as exc:self.status_text.set(str(exc));return
        self.send('update_profile',{'document':raw},lambda r:self.send('get_profile',done=self.loaded))

    def enable(self):self.apply(lambda:self.send('enable_live'))

    def start_test(self,kind):
        try:controls=self.controls()
        except Exception as exc:self.status_text.set(str(exc));return
        self.active_test=kind
        if kind=='constant_force':
            self.constant_warning.set(self.constant_warning_text+' Starting in 3 seconds…')
        self.send('test_start',{'kind':kind,'controls':controls})

    def changed_test(self,value=None):
        if self.loading or self.active_test is None:return
        if self.pending:self.after_cancel(self.pending)
        self.pending=self.after(90,self.update_test)

    def update_test(self):
        self.pending=None
        if self.active_test:
            self.send('test_update',{'kind':self.active_test,'controls':self.controls()})

    def centre(self):
        self.roll.set(0);self.pitch.set(0)
        if self.active_test in ('movement','roll','pitch'):self.update_test()
        else:self.start_test('movement')

    def stop(self):
        self.active_test=None
        if self.pending:self.after_cancel(self.pending);self.pending=None
        self.send('stop')

    def poll(self):
        if not self.alive:return
        def received(r):
            state=r.get('status',{})
            if state.get('mode')!='test':self.active_test=None
            status=state.get('last_error') or (
                f"{state.get('mode','stopped').title()} | " +
                ('hardware connected' if state.get('connected') else (f"waiting {state['reconnect_remaining']:.1f}s for base reconnect" if state.get('mode')=='test' and state.get('reconnect_remaining',0)>0 else ('waiting for aircraft power / telemetry' if state.get('waiting_for_power') else 'connecting to hardware' if state.get('mode')=='test' else 'hardware output inactive'))) +
                (f" | {state.get('test_remaining',0):.1f}s remaining" if state.get('mode')=='test' else ''))
            countdown=state.get('test_countdown',0)
            if countdown>0:
                remaining=math.ceil(countdown)
                self.constant_warning.set(self.constant_warning_text+f' Starting in {remaining}…')
                status=f'Constant push starts in {remaining}… Keep your hands on the control. STOP cancels.'
            else:
                self.constant_warning.set(self.constant_warning_text+' Starts after a 3-second countdown.')
            if state.get('mode')=='stopped' and state.get('test_result'):
                status=state.get('last_error') or state['test_result']
            if state.get('unsupported_effects'):
                status+=' | Not yet verified on this base: '+', '.join(state['unsupported_effects'])
            self.status_text.set(self.action_error or status)
        self.send('test_heartbeat',done=received)
        self.after(500,self.poll)

    def close(self):
        if self.pending:self.after_cancel(self.pending)
        self.send('stop_test')
        self.alive=False
        self.destroy()
