"""Preset discovery/selection without simulator, hardware or real user-profile writes."""
from pathlib import Path
import ast
import json
import os
import sys
import tempfile
import time
import types
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))

def check():
    from muslimsim.hardware import ffb_profiles as f
    from muslimsim.control.server import ControlServer, DeviceRegistration
    with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,APPDATA=td):
        original={}
        for device in f.ALLOWED_DEVICES:
            directory=f.default_ffb_profile_dir(device)
            directory.mkdir(parents=True)
            p=directory/'Flight.mslm'
            p.write_text(json.dumps({'schema':1,'name':'Flight','device':device,'effects':[]}),encoding='utf-8')
            original[p]=p.read_bytes()
        (f.default_ffb_profile_dir()/'bad.mslm').write_text('{',encoding='utf-8')
        server=ControlServer(types.SimpleNamespace(mode='live',device_enabled=lambda key:True,set_device_status=lambda *a:None),token='fixture')
        def request(device,action,**payload):
            return server.handle(dict(cmd='device_command',token='fixture',device=device+'_ffb',action=action,payload=payload))
        for device in f.ALLOWED_DEVICES:
            listed=request(device,'list_profiles')['result']
            assert 'Flight' in listed['profiles']
            assert request(device,'select_profile',name='Flight')['result']['ok']
            assert f.load_active_profile_name(f.default_active_profile_path(device))=='Flight'
        assert request('moza_a210','list_profiles')['result']['errors']
        external=Path(td)/'Downloads'
        external.mkdir()
        for device in f.ALLOWED_DEVICES:
            source=external/(device+'.mslm')
            source.write_text(json.dumps({'schema':1,'name':'Flight','device':device,'effects':[], 'physics':{}}),encoding='utf-8')
            before=source.read_bytes()
            result=request(device,'import_profile',path=str(source))['result']
            assert result['ok'], result
            assert result['name']=='Flight (2)'
            assert request(device,'import_profile',path=str(source))['result']['ok']
            assert source.read_bytes()==before
            assert request(device,'select_profile',name=result['name'])['result']['ok']
            other='moza_ab6' if device=='moza_a210' else 'moza_a210'
            assert not request(other,'import_profile',path=str(source))['result']['ok']
        source=external/'broken.mslm';source.write_text('{',encoding='utf-8')
        active_before=f.default_active_profile_path().read_bytes()
        assert not request('moza_a210','import_profile',path=str(source))['result']['ok']
        assert f.default_active_profile_path().read_bytes()==active_before
        assert all(p.read_bytes()==b for p,b in original.items())
        a210_active=f.default_active_profile_path().read_bytes()
        assert not request('moza_ab6','select_profile',name='missing')['result']['ok']
        assert f.default_active_profile_path().read_bytes()==a210_active
        assert all(p.read_bytes()==b for p,b in original.items())
        assert not server.handle(dict(cmd='device_command',token='wrong',device='moza_a210_ffb',action='list_profiles'))['ok']
        live=[]
        server.register(DeviceRegistration('moza_a210_ffb',command=lambda a,p: live.append((a,p)) or {'ok':True,'profiles':['Live']}))
        assert request('moza_a210','list_profiles')['result']['profiles']==['Live']
        assert live==[('list_profiles',{})]
        assert not request('moza_ab6','set_physics',overrides={'spring':50})['ok']

    tree=ast.parse((PROJECT/'muslimsim/gui/studio.py').read_text(encoding='utf-8'))
    methods={n.name:n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef)}
    wanted=['_moza_ffb_browse_profile','_moza_ffb_picker_device','_moza_ffb_picker','_moza_ffb_list_profiles','_receive_moza_ffb_profiles','_moza_ffb_select_profile','_draw_moza_ffb_preset_bar','_draw_moza_ffb_preset_dropdown_overlay']
    mod=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+[methods[n] for n in wanted],type_ignores=[])
    ns=dict(__package__='muslimsim.gui',time=time,INK='white',MUTED='grey',ACCENT='green',moza_presets_for_device=lambda d:[],MOZA_UI_PRESETS={})
    exec(compile(ast.fix_missing_locations(mod),'<actual Studio picker methods>','exec'),ns)
    ui=types.SimpleNamespace(_selected_device='moza_a210',_device_states={},_moza_ffb_physics_local={'spring':12},_MOZA_FFB_PROFILES_RETRY_SECONDS=2.0)
    ui._moza_ffb_pickers={d:dict(names=[],open=False,fetch_at=0.0,active=None,error='') for d in f.ALLOWED_DEVICES}
    for name in wanted:setattr(ui,name,types.MethodType(ns[name],ui))
    queued=[]
    ui._request=lambda cmd,**kw:queued.append((cmd,kw))
    ui._draw_faceplate=lambda:None
    ui.footer=types.SimpleNamespace(set=lambda text:None)
    ui._device_command_ok=lambda res:res.get('result',{}).get('ok',False)
    ui._device_command_error=lambda res:'fixture error'
    ui._moza_ffb_list_profiles()
    ui._selected_device='moza_ab6'
    ui._moza_ffb_list_profiles()
    queued[0][1]['done']({'result':{'profiles':['A210 flight'],'active_profile':'A210 flight'}})
    queued[1][1]['done']({'result':{'profiles':['AB6 flight'],'active_profile':'AB6 flight'}})
    assert ui._moza_ffb_picker()['names']==['AB6 flight']
    assert ui._moza_ffb_picker('moza_a210')['names']==['A210 flight']
    ui._moza_ffb_select_profile('AB6 flight')
    assert queued[-1][1]['device']=='moza_ab6_ffb'
    ui._selected_device='moza_a210'
    queued[-1][1]['done']({'result':{'ok':True}})
    assert ui._moza_ffb_physics_local=={'spring':12}
    assert ui._moza_ffb_picker()['active']=='A210 flight'
    # Native chooser cancellation has no side effect; a delayed import retains its base.
    chooser=types.SimpleNamespace(askopenfilename=lambda **kw: '')
    with tempfile.TemporaryDirectory() as picker_dir, patch.dict(os.environ,APPDATA=picker_dir), patch.dict(sys.modules, {'tkinter':types.SimpleNamespace(filedialog=chooser)}):
        count=len(queued)
        ui._moza_ffb_browse_profile()
        assert len(queued)==count
        opened=[]
        chooser.askopenfilename=lambda **kw: opened.append(kw) or '/chosen/Flight.mslm'
        ui._selected_device='moza_ab6'
        ui._moza_ffb_browse_profile()
        assert opened[-1]['initialdir']==str(f.default_ffb_profile_dir('moza_ab6'))
        assert Path(opened[-1]['initialdir']).is_dir()
        imported=queued[-1][1]
        assert imported['device']=='moza_ab6_ffb' and imported['action']=='import_profile'
        ui._selected_device='moza_a210'
        imported['done']({'result':{'ok':True,'name':'AB6 flight'}})
        assert queued[-1][1]['device']=='moza_ab6_ffb' and queued[-1][1]['action']=='select_profile'
        ui._moza_ffb_browse_profile()
        assert opened[-1]['initialdir']==str(f.default_ffb_profile_dir('moza_a210'))
    class Canvas:
        def __init__(self):self.text=[];self.tags=[];self.count=0
        def create_text(self,*a,**kw):self.text.append(kw.get('text'));self.count+=1;return self.count
        def create_round_rect(self,*a,**kw):self.count+=1;return self.count
        create_rectangle=create_round_rect
    ui._tag=lambda canvas,item,tag:canvas.tags.append(tag)
    for device,title in [('moza_a210','A210 flight'),('moza_ab6','AB6 flight')]:
        ui._selected_device=device
        canvas=Canvas()
        ui._draw_moza_ffb_preset_bar(canvas,0,0,400,48)
        ui._draw_moza_ffb_preset_dropdown_overlay(canvas,0,48,400)
        assert 'PRESET: '+title in canvas.text
        assert 'moza_ffb_preset_toggle' in canvas.tags
        assert 'moza_ffb_browse' in canvas.tags
        assert 'moza_ffb_preset_select:'+title in canvas.tags
    print('MOZA preset picker: offline listing/selection, files unchanged, auth, live route, per-base callbacks and click targets PASS')

if __name__=='__main__':check()
