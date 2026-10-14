import ast
import tempfile
from pathlib import Path
from types import SimpleNamespace
import audio_player
import format_converter_tab as formats

base = Path(__file__).parent
source = ast.parse((base/'personalized_dubbing_tab.py').read_text(encoding='utf-8'))
method = next(n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'listen_selected_scene')
class Value:
    def set(self, value): self.value=value
class Player:
    def set_project_root(self, value): self.root=value
    def set_dubbed_folder_name(self, value): self.folder=value
    def play_one(self, path, title, **kwargs): self.play=(path,title,kwargs)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    for folder in ('WAV ORIGINAIS', 'dublados personalizados', 'dublado'):
        for chapter in ('A', 'B'):
            p=root/folder/chapter/'cena.wav'
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b'test')
    ns={'CUSTOM_DIR':root/'dublados personalizados'}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<scene>','exec'),ns)
    app=SimpleNamespace(stems=['A/cena','B/cena'],audio_by_stem={key:root/'WAV ORIGINAIS'/f'{key}.wav' for key in ('A/cena','B/cena')},audio_player=Player(),status_var=Value(),scene_list=SimpleNamespace(nearest=lambda y:1,bbox=lambda i:(0,20,100,20),curselection=lambda:(0,)))
    app._ensure_scene_review=lambda: None
    app._sync_personalized_scene=lambda *args: None
    ns['listen_selected_scene'](app,SimpleNamespace(y=25))
    assert app.audio_player.play[0] == root/'dublados personalizados/B/cena.wav'
    assert app.audio_player.play[2]['index']==1
    assert app.audio_player.folder=='dublados personalizados'
    player=audio_player.AudioPlayerManager.__new__(audio_player.AudioPlayerManager)
    player.project_root=root
    player.dubbed_folder_name='dublados personalizados'
    for chapter in ('A','B'):
        original=root/'WAV ORIGINAIS'/chapter/'cena.wav'
        dubbed=root/'dublados personalizados'/chapter/'cena.wav'
        assert player._find_original_audio(dubbed)==original.resolve()
        assert player._find_dubbed_audio(original)==dubbed.resolve()
        assert player._find_dubbed_audio(dubbed)==dubbed.resolve()
    (root/'dublados personalizados/B/cena.wav').unlink()
    app._ensure_scene_review=lambda: None
    app._sync_personalized_scene=lambda *args: None
    ns['listen_selected_scene'](app,SimpleNamespace(y=25))
    assert app.audio_player.play[0]==root/'WAV ORIGINAIS/B/cena.wav'
    assert player._find_dubbed_audio(root/'WAV ORIGINAIS/B/cena.wav') is None
    (root/'dublados personalizados/.cena.__sintese.wav').write_bytes(b'temp')
    loaded=[]
    form=formats.FormatConverterApp.__new__(formats.FormatConverterApp)
    form.running=False
    form.root=SimpleNamespace()
    form.project_root=root
    form.audio_player=Player()
    form.status_var=Value()
    form.set_files=lambda files,label,source_labels=None:loaded.append(files)
    form.append_log=lambda message:None
    form.load_from_personalized()
    assert loaded[-1]==[root/'dublados personalizados/A/cena.wav']
    form.running=True
    form.load_from_personalized()
    assert len(loaded)==1
    form.running=False
    form.project_root=root/'empty'
    form.load_from_personalized()
    assert loaded[-1]==[]
    assert 'Nenhum áudio' in form.status_var.value
for name in ('Dublaskizon.py','audio_player.py','personalized_dubbing_tab.py','duration_converter_tab.py','format_converter_tab.py','i18n.py'):
    ast.parse((base/name).read_text(encoding='utf-8-sig'))
assert 'bind("<Double-Button-1>", self.listen_selected_scene)' in (base/'personalized_dubbing_tab.py').read_text(encoding='utf-8')
for name in ('duration_converter_tab.py','format_converter_tab.py'):
    assert 'CARREGAR DA ABA DUBLAGEM PERSONALIZADA' in (base/name).read_text(encoding='utf-8')
print('Personalized scene pairing, double-click selection, missing dub, format loading, busy/empty states and syntax: OK')
