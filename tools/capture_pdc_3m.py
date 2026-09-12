"""Guided BB51 recapture using only the running bridge's existing HID owner.

Writes labelled evidence under captures; never edits profiles or device maps.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.control.client import ControlClient
DEVICE='pdc_bb61_left'


def capture_steps():
    steps=[]
    def add(key,label,kind,action): steps.append(dict(key=key,label=label,kind=kind,action=action))
    for key,label in [('wxr','WXR'),('sta','STA'),('wpt','WPT'),('arpt','ARPT'),('data','DATA'),('pos','POS'),('terr','TERR'),('fpv','FPV'),('mtrs','MTRS'),('vsd','VSD'),('mins_rst','MINS RST'),('baro_std','BARO STD'),('ctr','CTR'),('tfc','TFC')]:
        add(key,label,'button','Press and hold this button for about 1 second, then release it. Repeat twice. Leave other controls still.')
    for group,choices in [('mins_mode',['RADIO','BARO']),('baro_unit',['IN','HPA']),('vor1',['VOR','OFF','ADF 1']),('vor2',['VOR','OFF','ADF 2']),('map_mode',['APP','VOR','MAP','PLN'])]:
        for i,label in enumerate(choices):
            add(f'{group}:{i}',f'{group.replace("_"," ").upper()} — {label}','selector',f'Move this selector to {label} and leave it there until recording finishes. Leave other controls still.')
    for direction,label in [('inc','clockwise'),('dec','counter-clockwise')]:
        add('range_'+direction,'RANGE — '+label,'encoder',f'Turn RANGE slowly {label} through several clicks. Pause briefly between clicks. Keep turning only in that direction.')
    for group in ['mins','baro']:
        for direction,label in [('dec','left / decrease'),('inc','right / increase')]:
            add(f'{group}_{direction}',f'{group.upper()} — one notch {label}','detent',f'Move the inner {group.upper()} knob to its FIRST notch {label}, hold for a second, then release. Repeat twice. Do not push past the notch.')
            add(f'{group}_{direction}_fast',f'{group.upper()} — past the notch {label}','fast',f'Move the inner {group.upper()} knob PAST the first notch {label}, hold for two seconds, then release. Repeat once.')
    return steps


def locate_bridge():
    ps=r'''$ErrorActionPreference='Stop'; $bridgeRows=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'MuslimSim[\\/]launch(?:_msfs24)?\.py' }; @($bridgeRows | ForEach-Object { $entry=$_; $ports=@(Get-NetTCPConnection -State Listen -OwningProcess $entry.ProcessId -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort); [pscustomobject]@{command=$entry.CommandLine;ports=$ports} }) | ConvertTo-Json -Depth 4 -Compress'''
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise RuntimeError('Cannot find the running Studio service.')
    rows=json.loads(result.stdout or '[]'); rows=rows if isinstance(rows,list) else [rows]
    found=[]
    for row in rows:
        match=re.search(r'--control-token=([^\s"]+)',row.get('command',''))
        if not match: continue
        for port in row.get('ports',[]):
            client=ControlClient(port,match.group(1),timeout=2)
            try:
                reply=client.request('device_diagnostics',device=DEVICE)
            except Exception: continue
            diag=reply.get('diagnostics') or {}
            if str(diag.get('pid','')).upper()=='BB51' and diag.get('raw_hex'):
                found.append(client)
    if len(found)!=1:
        raise RuntimeError('Close and reopen Studio, select Practice, and leave the 3M PDC connected. Then click Connect again.')
    return found[0]


def read_sample(client, expected_serial=None):
    reply=client.request('device_diagnostics',device=DEVICE)
    diag=reply.get('diagnostics') or {}
    if reply.get('mode')!='test': raise RuntimeError('Select Practice in Studio before recording.')
    if str(diag.get('pid','')).upper()!='BB51' or diag.get('state')!='connected':
        raise RuntimeError('The 3M BB51 is disconnected. Reconnect it before recording.')
    if expected_serial is not None and diag.get('serial','')!=expected_serial:
        raise RuntimeError('The physical PDC changed. Reconnect the original 3M.')
    raw=bytes.fromhex(diag.get('raw_hex') or '')
    if len(raw)<17 or raw[0]!=1: raise RuntimeError('Waiting for a valid 3M input report.')
    return {'time':time.time(),'raw_hex':raw.hex(),'buttons':diag.get('buttons',[]),'serial':diag.get('serial','')}


def validate_samples(step,samples):
    if not samples: return False,'No input reports received.'
    states={x['raw_hex'] for x in samples}
    buttons=[set(x['buttons']) for x in samples]
    changed=set.union(*buttons)-set.intersection(*buttons)
    if step['kind']=='selector':
        # A selector may already be in the requested position. Cross-position
        # comparison is deliberately left to the completed-map review.
        tail=[set(x['buttons']) for x in samples if x['time']>=samples[-1]['time']-1]
        if not tail or any(x!=tail[-1] for x in tail): return False,'Let the selector settle and retry.'
        return True,'Selector position recorded.'
    if not changed: return False,'No button contacts changed. Try again, or mark this control as not present.'
    if len(changed)>8: return False,'Several controls changed together. Leave other controls still and retry.'
    return True,'Control movement recorded.'


class CaptureWindow:
    def __init__(self):
        self.root=tk.Tk(); self.root.title('MuslimSim — Full 3M PDC capture')
        self.root.geometry('820x580');self.root.minsize(720,500)
        self.steps=capture_steps();self.index=0;self.records=[];self.client=None;self.serial=None
        self.busy=False;self.pending=None;self.stopped=threading.Event()
        self.path=ROOT/'captures'/('PDC_3M_BB51_GUIDED_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
        frame=ttk.Frame(self.root,padding=24);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Capture every 3M PDC control',font=('Segoe UI',22,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Your saved simulator assignments stay intact.',font=('Segoe UI',12)).pack(anchor='w',pady=(7,20))
        self.progress=ttk.Label(frame,font=('Segoe UI',11));self.progress.pack(anchor='w')
        self.title=ttk.Label(frame,font=('Segoe UI',20,'bold'));self.title.pack(anchor='w',pady=(12,8))
        self.instructions=ttk.Label(frame,wraplength=735,font=('Segoe UI',13));self.instructions.pack(anchor='w',fill='x')
        self.status=ttk.Label(frame,text='Close and reopen Studio, select Practice, then click Connect.',wraplength=735,font=('Segoe UI',12));self.status.pack(anchor='w',pady=22)
        buttons=ttk.Frame(frame);buttons.pack(anchor='w',pady=12)
        self.connect=ttk.Button(buttons,text='Connect',command=self.connect_click);self.connect.pack(side='left',padx=(0,10))
        self.record=ttk.Button(buttons,text='Record this control',command=self.record_click,state='disabled');self.record.pack(side='left',padx=(0,10))
        self.accept=ttk.Button(buttons,text='Keep and continue',command=self.accept_click,state='disabled');self.accept.pack(side='left',padx=(0,10))
        self.skip=ttk.Button(frame,text='This control is not on my panel',command=self.skip_click,state='disabled');self.skip.pack(anchor='w',pady=10)
        ttk.Label(frame,text='Nothing is applied automatically. Each recording is saved for verification.',wraplength=735).pack(anchor='w',pady=12)
        self.root.protocol('WM_DELETE_WINDOW',self.close);self.show_step()
    def ui(self,fn):
        if not self.stopped.is_set(): self.root.after(0,fn)
    def save(self,complete=False):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={'schema':1,'pid':'BB51','device':DEVICE,'serial':self.serial,'complete':complete,'step_count':len(self.steps),'records':self.records}
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(self.path)
    def show_step(self):
        if self.index==len(self.steps):
            self.save(True);self.title.configure(text='All controls recorded');self.progress.configure(text='Capture complete')
            self.instructions.configure(text='Return to the conversation and say “capture finished”. The recordings will be checked before applying your 3M map.')
            self.status.configure(text='Saved: '+self.path.name)
            for button in (self.record,self.accept,self.skip,self.connect):button.configure(state='disabled')
            return
        step=self.steps[self.index];self.progress.configure(text=f'Control {self.index+1} of {len(self.steps)}')
        self.title.configure(text=step['label']);self.instructions.configure(text=step['action'])
    def connect_click(self):
        if self.busy:return
        self.busy=True;self.connect.configure(state='disabled');self.status.configure(text='Connecting to the existing Studio service…')
        def worker():
            try:
                self.client=locate_bridge();sample=read_sample(self.client);self.serial=sample['serial']
                self.ui(lambda:self.connected())
            except Exception as exc:
                message=str(exc);self.ui(lambda:self.failed(message))
        threading.Thread(target=worker,daemon=True).start()
    def connected(self):
        self.busy=False;self.connect.configure(state='normal');self.record.configure(state='normal');self.skip.configure(state='normal')
        self.status.configure(text='3M connected. Click Record, keep your hands off for the countdown, then follow the instruction.')
    def failed(self,message):
        self.busy=False;self.status.configure(text=message);self.connect.configure(state='normal')
        self.record.configure(state='normal' if self.client else 'disabled');self.skip.configure(state='normal' if self.client else 'disabled')
    def record_click(self):
        if self.busy or not self.client:return
        self.busy=True;self.pending=None
        for b in (self.record,self.accept,self.skip,self.connect):b.configure(state='disabled')
        step=self.steps[self.index]
        def worker():
            try:
                self.ui(lambda:self.status.configure(text='Keep all controls still for 2 seconds…'))
                samples=[];start=time.monotonic();last=None;announced=False
                while time.monotonic()-start<11:
                    if self.stopped.is_set():return
                    sample=read_sample(self.client,self.serial)
                    # Save transitions and a small heartbeat for stable selector
                    # validation. No unbounded capture or idle polling.
                    now=time.monotonic()
                    if sample['raw_hex']!=last or not samples or sample['time']-samples[-1]['time']>=0.25:
                        samples.append(sample);last=sample['raw_hex']
                    if now-start>=2 and not announced:
                        announced=True;self.ui(lambda:self.status.configure(text='NOW operate the named control. Recording for 9 seconds…'))
                    time.sleep(0.025)
                valid,message=validate_samples(step,samples)
                self.pending={'step':step,'samples':samples,'valid':valid,'message':message}
                self.ui(lambda:self.recorded(valid,message))
            except Exception as exc:
                message=str(exc);self.ui(lambda:self.failed(message))
        threading.Thread(target=worker,daemon=True).start()
    def recorded(self,valid,message):
        self.busy=False;self.record.configure(state='normal');self.skip.configure(state='normal');self.connect.configure(state='normal')
        self.accept.configure(state='normal' if valid else 'disabled')
        self.status.configure(text=message+(' Click Keep and continue if you operated the named control; otherwise record it again.' if valid else ''))
    def accept_click(self):
        if self.busy or not self.pending or not self.pending['valid']:return
        self.records.append(self.pending);self.save();self.pending=None;self.index+=1;self.accept.configure(state='disabled');self.show_step()
        if self.index<len(self.steps):self.status.configure(text='Ready for the next control.')
    def skip_click(self):
        if self.busy:return
        self.records.append({'step':self.steps[self.index],'absent':True});self.save();self.index+=1;self.accept.configure(state='disabled');self.show_step()
    def close(self):
        self.stopped.set()
        if self.records:self.save(self.index==len(self.steps))
        self.root.destroy()
    def run(self):self.root.mainloop()

if __name__=='__main__':CaptureWindow().run()
