import tempfile
import wave
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk

import batch_tab
import review_tab


def make_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * 240)


class FakeMenu:
    instances = []

    def __init__(self, *_args, **_kwargs):
        self.commands = []
        self.__class__.instances.append(self)

    def add_command(self, **kwargs):
        self.commands.append(kwargs)

    def add_separator(self):
        return None

    def tk_popup(self, *_args):
        return None

    def grab_release(self):
        return None


def event_for(listbox):
    box = listbox.bbox(0)
    assert box
    return SimpleNamespace(y=box[1] + 1, x_root=20, y_root=20)


def assert_menu_labels(menu):
    assert [item["label"] for item in menu.commands] == [
        "ABRIR LOCAL DO ÁUDIO DUBLADO",
        "ABRIR LOCAL DO ÁUDIO ORIGINAL",
        "COPIAR NOME DO ÁUDIO",
        "COPIAR LOCAL DO ÁUDIO DUBLADO",
        "COPIAR LOCAL DO ÁUDIO ORIGINAL",
    ], menu.commands


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original = project / "WAV ORIGINAIS" / "CAP02" / "cena.wav"
    text = project / "TXT TEXTO PORTUGUES" / "CAP02" / "cena.txt"
    dubbed = project / "dublado" / "CAP02" / "cena.wav"
    make_wav(original)
    make_wav(dubbed)
    text.parent.mkdir(parents=True, exist_ok=True)
    text.write_text("Texto", encoding="utf-8")

    batch_tab.configure_project_root(project)
    old_batch_menu = batch_tab.Menu
    root = tk.Tk()
    root.withdraw()
    try:
        batch_tab.Menu = FakeMenu
        app = batch_tab.BatchApp(root, embedded=False)
        root.update_idletasks()
        captured = []
        old_reveal = batch_tab.reveal_in_file_manager
        batch_tab.reveal_in_file_manager = lambda path: captured.append(Path(path)) or True
        assert app.show_scene_context_menu(event_for(app.queue_list)) == "break"
        menu = FakeMenu.instances[-1]
        assert_menu_labels(menu)
        menu.commands[0]["command"]()
        menu.commands[1]["command"]()
        menu.commands[2]["command"]()
        assert root.clipboard_get() == "cena.wav"
        menu.commands[3]["command"]()
        assert root.clipboard_get() == str(dubbed.parent.resolve())
        menu.commands[4]["command"]()
        assert root.clipboard_get() == str(original.parent.resolve())
        assert captured == [dubbed.resolve(), original.resolve()]
        batch_tab.reveal_in_file_manager = old_reveal
    finally:
        batch_tab.Menu = old_batch_menu
        root.destroy()

    review_tab.configure_project_root(project)
    old_review_menu = review_tab.Menu
    root = tk.Tk()
    root.withdraw()
    try:
        review_tab.Menu = FakeMenu
        app = review_tab.ReviewApp(root, embedded=False)
        root.update_idletasks()
        captured = []
        old_reveal = review_tab.reveal_in_file_manager
        review_tab.reveal_in_file_manager = lambda path: captured.append(Path(path)) or True
        assert app.show_scene_context_menu(event_for(app.scene_list)) == "break"
        menu = FakeMenu.instances[-1]
        assert_menu_labels(menu)
        menu.commands[0]["command"]()
        menu.commands[1]["command"]()
        menu.commands[2]["command"]()
        assert root.clipboard_get() == "cena.wav"
        menu.commands[3]["command"]()
        assert root.clipboard_get() == str(dubbed.parent.resolve())
        menu.commands[4]["command"]()
        assert root.clipboard_get() == str(original.parent.resolve())
        assert captured == [dubbed.resolve(), original.resolve()]
        review_tab.reveal_in_file_manager = old_reveal
    finally:
        review_tab.Menu = old_review_menu
        root.destroy()

print("audio_location_context_menu_ok")
