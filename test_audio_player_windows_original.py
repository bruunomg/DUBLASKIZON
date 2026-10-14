import sys
import tempfile
import time
import wave
from pathlib import Path

import tkinter as tk

import audio_player


def make_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * 240)


root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original = project / "WAV ORIGINAIS" / "CAP02" / "cena.wav"
    dubbed = project / "dublado" / "CAP02" / "cena.wav"
    make_wav(original)
    make_wav(dubbed)

    manager = audio_player.AudioPlayerManager(root, project)
    manager.set_playback_mode("windows")
    captured = []
    old_platform = audio_player.sys.platform
    had_startfile = hasattr(audio_player.os, "startfile")
    old_startfile = getattr(audio_player.os, "startfile", None)
    audio_player.sys.platform = "win32"
    audio_player.os.startfile = lambda value: captured.append(Path(value).resolve())
    try:
        manager.play_one(dubbed, "OUVIR CENA", playlist=[dubbed], index=0)
        root.update_idletasks()
        assert manager.window is not None
        assert manager.original_button.cget("state") == "normal"
        assert manager.start_button.cget("state") == "normal"

        manager.original_button.invoke()
        deadline = time.monotonic() + 2
        while manager.thread is not None and manager.thread.is_alive() and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert captured == [original.resolve()], captured
        for _ in range(20):
            root.update()
            if manager.start_button.cget("state") == "normal":
                break
            time.sleep(0.01)
        assert manager.start_button.cget("state") == "normal"

        manager.start_button.invoke()
        deadline = time.monotonic() + 2
        while manager.thread is not None and manager.thread.is_alive() and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert captured == [original.resolve(), dubbed.resolve()], captured
        manager.close_window()
    finally:
        audio_player.sys.platform = old_platform
        if had_startfile:
            audio_player.os.startfile = old_startfile
        else:
            delattr(audio_player.os, "startfile")
        root.destroy()

print("audio_player_windows_original_ok")
