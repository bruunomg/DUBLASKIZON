from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import ast
import review_tab
import personalized_dubbing_tab as custom
from audio_player import AudioPlayerManager

class Root:
    def __init__(self): self.callbacks=[]
    def after(self, delay, callback): self.callbacks.append(callback)

player=AudioPlayerManager.__new__(AudioPlayerManager)
player.theme={'mode':'claro','surface':'#FFFFFF','text':'#123456'}
player.window=None
player.dubbed_folder_name='dublado'
player._project_audio_index={}
player.apply_theme({'input':'#EEEEEE'})
normal=dict(player.theme)
player.set_dubbed_folder_name('dublados personalizados')
assert player.theme['surface']=='#450F18'
player.apply_theme({'surface':'#101010'})
assert player.theme['surface']=='#450F18'
player.set_dubbed_folder_name('dublado')
assert player.theme['surface']=='#101010'
assert player.theme['text']==normal['text']

with tempfile.TemporaryDirectory() as tmp:
    project=Path(tmp)
    review_tab.configure_project_root(project)
    custom.configure_project_root(project)
    target=project/'dublados personalizados'/'CAP01'/'cena.wav'
    original=project/'WAV ORIGINAIS'/'CAP01'/'cena.wav'
    for p in (target,original):
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(b'old')
    app=review_tab.ReviewApp.__new__(review_tab.ReviewApp)
    app.root=Root()
    app.append_regen_log=lambda text:None
    app.config={'model':'test','language':'pt','instruct':'test'}
    app.audio_by_stem={'CAP01/cena':original}
    app.audio_source_mode='normal' # destination captured before changing source
    events=[]
    app._generation_done=lambda *args:events.append(('done',args))
    app._generation_failed=lambda *args:events.append(('failed',args))
    def synth(command,**kwargs):
        Path(command[command.index('--output')+1]).write_bytes(b'new')
        return SimpleNamespace(returncode=0,stdout='')
    def expression(source,reference,dest):
        assert reference==original
        dest.write_bytes(source.read_bytes()+b'-expression')
    with patch.object(review_tab,'find_omnivoice_command',return_value=['infer']), patch.object(review_tab.subprocess,'run',side_effect=synth), patch.object(custom,'match_original_expression',side_effect=expression), patch.object(custom.os,'replace',side_effect=PermissionError('rename blocked')):
        app._run_generation('CAP01/cena','texto',target,target,original)
    for cb in app.root.callbacks: cb()
    assert target.read_bytes()==b'new-expression'
    assert events[0][0]=='done'
    assert (project/'revisoes/CAP01/cena_v01.wav').read_bytes()==b'old'
    app.root=Root()
    app.append_regen_log=lambda text:None; events.clear()
    with patch.object(review_tab,'find_omnivoice_command',return_value=['infer']), patch.object(review_tab.subprocess,'run',side_effect=RuntimeError('synthesis failed')):
        app._run_generation('CAP01/cena','texto',target,target,original)
    for cb in app.root.callbacks: cb()
    assert events[0][0]=='failed' and 'synthesis failed' in events[0][1][1]
    app.root=Root()
    app.append_regen_log=lambda text:None;events.clear()
    with patch.object(review_tab,'find_omnivoice_command',return_value=['infer']), patch.object(review_tab.subprocess,'run',side_effect=synth), patch.object(custom,'match_original_expression',side_effect=expression), patch.object(custom,'_safe_replace_file',side_effect=PermissionError('write blocked')):
        app._run_generation('CAP01/cena','texto',target,target,original)
    for cb in app.root.callbacks: cb()
    assert events[0][0]=='failed'
    assert (project/'revisoes/CAP01/cena_v02.wav').exists()
    c=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
    c.running=False;c.review_app=None;c.audio_by_stem={'CAP01/cena':original};c.text_by_stem={'CAP01/cena':Path('text')}
    calls=[]
    c.start_generation=lambda **kwargs:calls.append(kwargs)
    with patch.object(custom,'custom_model_for_stem',return_value=original):
        c.redub_personalized_scene('CAP01/cena')
    assert calls==[{'stems_override':['CAP01/cena'],'model_override':original}]
for name in ('review_tab.py','personalized_dubbing_tab.py','audio_player.py'):
    ast.parse((Path(__file__).parent/name).read_text(encoding='utf-8'))
print('v5: theme restore, selected-scene redub, expression, rename fallback, delayed failure callback, backup retention: OK')
