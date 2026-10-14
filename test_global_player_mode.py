import os
import tempfile
from pathlib import Path

import tkinter as tk

import Dublaskizon

root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder) / "PROJETO_PLAYER"
    project.mkdir()
    old_app_dir = Dublaskizon.APP_DIR
    old_config = Dublaskizon.INTERFACE_CONFIG_PATH
    old_env = os.environ.get("DUBLASKIZON_PROJECT_ROOT")
    try:
        os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(project)
        Dublaskizon.APP_DIR = project
        Dublaskizon.INTERFACE_CONFIG_PATH = project / "Dublaskizon_interface.json"
        app = Dublaskizon.DublaskizonApp(root)
        root.update_idletasks()
        assert app.player_mode == "ffplay"
        assert app.player_mode_button.cget("text") == "OUVIR: FFPLAY"
        players = [
            app.batch_app.audio_player,
            app.review_app.audio_player,
            app.converter_app.audio_player,
            app.format_app.audio_player,
            app.voice_clone_app.audio_player,
        ]
        assert all(player.playback_mode == "ffplay" for player in players)

        app.toggle_player_mode()
        root.update_idletasks()
        assert app.player_mode == "windows"
        assert app.player_mode_button.cget("text") == "OUVIR: WINDOWS"
        assert all(player.playback_mode == "windows" for player in players)
        saved = Dublaskizon.INTERFACE_CONFIG_PATH.read_text(encoding="utf-8")
        assert '"player_mode": "windows"' in saved

        app.apply_language("en", save=False)
        assert app.player_mode_button.cget("text") == "PLAY: WINDOWS"
        app.toggle_player_mode()
        app.apply_language("pt", save=False)
        assert app.player_mode_button.cget("text") == "OUVIR: FFPLAY"
    finally:
        Dublaskizon.APP_DIR = old_app_dir
        Dublaskizon.INTERFACE_CONFIG_PATH = old_config
        if old_env is None:
            os.environ.pop("DUBLASKIZON_PROJECT_ROOT", None)
        else:
            os.environ["DUBLASKIZON_PROJECT_ROOT"] = old_env
        root.destroy()

print("global_player_mode_ok")
