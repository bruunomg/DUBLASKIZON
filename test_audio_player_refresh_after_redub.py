from pathlib import Path
import tempfile
import tkinter as tk
import wave

from audio_player import AudioPlayerManager


def make_wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(8000 * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes((b"\x00\x00\x00\x20" * max(1, frames // 2)))


with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original = project / "WAV ORIGINAIS" / "CAP01" / "cena.wav"
    dubbed = project / "dublado" / "CAP01" / "cena.wav"
    make_wav(original, 2.0)

    root = tk.Tk()
    root.withdraw()
    manager = AudioPlayerManager(root, project)
    manager.play_one(original, "OUVIR CENA", playlist=[original], index=0, scene_key="CAP01/cena", scene_keys=["CAP01/cena"])
    root.update_idletasks()
    assert manager.original_pending_paths == [original.resolve()]
    assert manager.dubbed_pending_paths == []
    assert manager.start_button.cget("state") == "disabled"
    assert manager.waveform_data["dubbed"] is None

    make_wav(dubbed, 1.0)
    manager.refresh_current_scene("CAP01/cena")
    root.update_idletasks()
    assert manager.dubbed_pending_paths == [dubbed.resolve()]
    assert manager.start_button.cget("state") == "normal"
    assert manager.waveform_data["dubbed"] is not None
    assert manager.waveform_duration_vars["original"].get().startswith("Duração: 00:02.00")
    assert manager.waveform_duration_vars["dubbed"].get().startswith("Duração: 00:01.00")
    assert manager._waveform_plot_width("dubbed", 800) < manager._waveform_plot_width("original", 800)
    manager.close_window()
    root.destroy()

print("audio_player_refresh_after_redub_ok")
