import tempfile
import wave
from pathlib import Path
import tkinter as tk
import duration_converter_tab as converter


def wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(b'\0\0' * 1200)


class Value:
    def __init__(self): self.value = ''
    def set(self, value): self.value = value
    def get(self): return self.value

class Listbox:
    def delete(self, *args): pass
    def insert(self, *args): pass

class Button:
    def __init__(self, app): self.app = app
    def invoke(self):
        return self.app.project_actions.get('load_converter_from_personalized', self.app.load_from_personalized)()


def make_app(project):
    app = converter.DurationConverterApp.__new__(converter.DurationConverterApp)
    app.project_root = project
    app.running = False
    app.project_actions = {}
    app.original_files = []
    app.dubbed_files = []
    app.original_base_dir = project
    app.dubbed_base_dir = project
    for name in ('original_dir_var', 'dubbed_dir_var', 'count_var', 'status_var'):
        setattr(app, name, Value())
    app.panel_title_vars = {'original': Value(), 'dubbed': Value()}
    app.original_listbox = Listbox()
    app.dubbed_listbox = Listbox()
    app.append_log = lambda text: None
    app.load_personalized_button = Button(app)
    return app

with tempfile.TemporaryDirectory() as tmp:
    project = Path(tmp)
    for chapter in ('CAP01', 'CAP02'):
        wav(project / 'WAV ORIGINAIS' / chapter / 'cena.wav')
        wav(project / 'dublados personalizados' / chapter / 'cena.wav')
    wav(project / 'dublado' / 'outra.wav')
    wav(project / 'WAV ORIGINAIS' / 'outra.wav')
    wav(project / 'dublados personalizados' / '.cena.__sintese.wav')
    wav(project / 'dublados personalizados' / '_BACKUP_OMNIVOICE' / 'backup.wav')
    app = make_app(project)
    app.load_personalized_button.invoke()
    assert set(app.original_by_stem) == {'CAP01/cena', 'CAP02/cena'}
    assert set(app.dubbed_by_stem) == {'CAP01/cena', 'CAP02/cena'}
    assert len(app.pair_items()) == 2
    assert all('dublados personalizados' in str(p) for p in app.dubbed_files)
    app.running = True
    wav(project / 'dublados personalizados' / 'sem_original.wav')
    app.load_personalized_button.invoke()
    assert len(app.dubbed_files) == 2
    app.running = False
    app.load_personalized_button.invoke()
    assert len(app.dubbed_files) == 3
    assert '1 dublado(s) sem original' in app.status_var.get()
    calls = []
    app.project_actions['load_converter_from_personalized'] = lambda: calls.append(True)
    app.load_personalized_button.invoke()
    assert calls == [True]
    app.project_root = project / 'outro_projeto'
    app.load_from_personalized()
    assert not app.original_files and not app.dubbed_files
    assert 'Nenhum áudio' in app.status_var.get()
    app.project_root = project
    app.load_from_review()
    assert set(app.dubbed_by_stem) == {'outra'}
    app.load_from_batch()
    assert set(app.dubbed_by_stem) == {'outra'}
print('personalized_duration_loading_ok')
