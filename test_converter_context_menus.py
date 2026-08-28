import tempfile
import wave
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk

import duration_converter_tab
import format_converter_tab


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


def check_menu(menu):
    assert [item["label"] for item in menu.commands] == [
        "ABRIR LOCAL DO ÁUDIO DUBLADO",
        "ABRIR LOCAL DO ÁUDIO ORIGINAL",
        "COPIAR NOME DO ÁUDIO",
        "COPIAR LOCAL DO ÁUDIO DUBLADO",
        "COPIAR LOCAL DO ÁUDIO ORIGINAL",
    ]


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original = project / "WAV ORIGINAIS" / "CAP01" / "cena.wav"
    dubbed = project / "dublado" / "CAP01" / "cena.wav"
    make_wav(original)
    make_wav(dubbed)

    root = tk.Tk()
    root.withdraw()
    try:
        duration_converter_tab.configure_project_root(project)
        old_menu = duration_converter_tab.Menu
        old_reveal = duration_converter_tab.reveal_in_file_manager
        duration_converter_tab.Menu = FakeMenu
        captured = []
        duration_converter_tab.reveal_in_file_manager = lambda path: captured.append(Path(path)) or True
        duration = duration_converter_tab.DurationConverterApp(root, embedded=False, project_root=project)
        duration.load_project_defaults("TESTE")
        assert duration.show_audio_context_menu(event_for(duration.original_listbox), "original") == "break"
        menu = FakeMenu.instances[-1]
        check_menu(menu)
        for command in menu.commands:
            command["command"]()
        assert captured == [dubbed.resolve(), original.resolve()]
        assert root.clipboard_get() == str(original.parent.resolve())
        duration_converter_tab.Menu = old_menu
        duration_converter_tab.reveal_in_file_manager = old_reveal

        old_menu = format_converter_tab.Menu
        old_reveal = format_converter_tab.reveal_in_file_manager
        format_converter_tab.Menu = FakeMenu
        captured = []
        format_converter_tab.reveal_in_file_manager = lambda path: captured.append(Path(path)) or True
        converter = format_converter_tab.FormatConverterApp(root, embedded=False, project_root=project)
        converter.load_project_defaults("TESTE")
        assert converter.show_context_menu(event_for(converter.listbox)) == "break"
        menu = FakeMenu.instances[-1]
        check_menu(menu)
        for command in menu.commands:
            command["command"]()
        assert captured == [dubbed.resolve(), original.resolve()]
        assert root.clipboard_get() == str(original.parent.resolve())
        format_converter_tab.Menu = old_menu
        format_converter_tab.reveal_in_file_manager = old_reveal
    finally:
        try:
            duration_converter_tab.Menu = old_menu
            duration_converter_tab.reveal_in_file_manager = old_reveal
        except NameError:
            pass
        root.destroy()

print("converter_context_menus_ok")
