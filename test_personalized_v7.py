import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ast
import personalized_dubbing_tab as custom
import review_tab as review

class Player:
    window=None
    scene_text_box=None
    def set_dubbed_folder_name(self,name): self.folder=name
    def set_scene_integration(self,selection,actions): self.selection=selection;self.actions=actions
    def set_scene_text_integration(self,loader,saver): self.loader=loader;self.saver=saver
    def set_review_snapshot_provider(self,provider): self.provider=provider
    def set_review_preferences(self,prefs): self.prefs=prefs
class Var:
    def set(self,value): self.value=value
    def get(self): return getattr(self,'value','')

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    custom.configure_project_root(root)
    review.configure_project_root(root)
    text=root/'TXT TEXTO PORTUGUES/CAP01/cena.txt';text.parent.mkdir(parents=True);text.write_text('texto original',encoding='utf-8')
    audio=root/'WAV ORIGINAIS/CAP01/cena.wav';audio.parent.mkdir(parents=True);audio.write_bytes(b'audio')
    controller=review.ReviewApp.__new__(review.ReviewApp)
    controller.busy=False;controller.audio_source_var=Var();controller.state={}
    controller.auto_open_var=Var();controller.request_r_var=Var()
    controller.toggle_auto_open=lambda:None;controller.toggle_r_request=lambda:None
    controller.apply_theme=lambda theme:None
    controller._log_central=lambda *args:None
    controller.update_history=lambda *args:None
    controller.refresh_scene_list=lambda *args:None
    controller.select_scene=lambda i:setattr(controller,'current_index',i)
    controller.current_index=0
    controller.run_audio_review_action=lambda stem,action:actions.append((stem,action,controller.current_output(stem)))
    original=SimpleNamespace(busy=False,state={'normal':{'status':'aprovada'}},audio_source_mode='normal',refresh_scene_list=lambda:None,_fixed_r_pronunciation=lambda:'unchanged')
    app=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
    app.root=object();app.scene_review=None;app.review_app=original;app.project_actions={};app.audio_player=Player();app.theme={};app.running=False
    app.stems=['CAP01/cena'];app.audio_by_stem={'CAP01/cena':audio};app.text_by_stem={'CAP01/cena':text};app.status_var=Var()
    actions=[]
    with patch.object(custom.ttk,'Frame',return_value=object()),patch.object(review,'ReviewApp',return_value=controller):
        app._ensure_scene_review()
    assert set(app.audio_player.actions)=={'open_audacity','approve','reject','redub_other','redub_personalized'}
    assert app.audio_player.folder=='dublados personalizados'
    app.audio_player.selection('CAP01/cena',0)
    assert app.audio_player.loader('CAP01/cena')['text']=='texto original'
    ok,message=app.audio_player.saver('CAP01/cena','texto editado')
    assert ok,message
    assert text.read_text(encoding='utf-8').strip()=='texto editado'
    assert any((root/'revisoes/CAP01').glob('cena_texto_v*.txt'))
    for action in ('open_audacity','approve','reject'):
        app.audio_player.actions[action]('CAP01/cena')
    assert all(row[2]==root/'dublados personalizados/CAP01/cena.wav' for row in actions)
    assert original.audio_source_mode=='normal'
    with patch.object(custom,'custom_model_for_stem',return_value=audio):
        app.audio_player.actions['redub_personalized']('CAP01/cena')
    assert actions[-1][1]=='redub'
    assert callable(app.audio_player.provider)
    assert app.audio_player.prefs['auto_open_var'] is controller.auto_open_var
    # Persisting a custom status must retain existing normal review records.
    controller.refresh_scene_list=lambda:None
    review.save_json(review.STATE_FILE,{'normal':{'status':'aprovada'}})
    controller.update_record('CAP01/cena','rejeitada','test')
    state=review.load_json(review.STATE_FILE,{})
    assert state['normal']['status']=='aprovada'
    assert state['personalizado::CAP01/cena']['status']=='rejeitada'
for path in Path(__file__).parent.glob('*.py'):
    ast.parse(path.read_text(encoding='utf-8-sig'))
print('v7 OK: full action wiring, editable TXT/save/backup, custom destination, independent source, preferences, status preservation and syntax')
