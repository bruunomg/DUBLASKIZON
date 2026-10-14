import tempfile
import time
import wave
from pathlib import Path

import tkinter as tk

from audio_player import AudioPlayerManager


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
    original = project / "WAV ORIGINAIS" / "CAP15" / "cena_1500.wav"
    dubbed = project / "dublado" / "CAP15" / "cena_1500.wav"
    make_wav(original)
    make_wav(dubbed)
    playlist = [project / "dublado" / f"CAP{index // 100:02d}" / f"cena_{index:04d}.wav" for index in range(3000)]
    playlist[1500] = dubbed
    manager = AudioPlayerManager(root, project)
    started = time.monotonic()
    manager.play_one(dubbed, "OUVIR CENA", playlist=playlist, index=1500)
    elapsed = time.monotonic() - started
    assert elapsed < 1.0, elapsed
    assert manager.current_index == 1500
    assert manager._resolved_pair_indices == {1500}, manager._resolved_pair_indices
    assert manager.original_pending_paths == [original.resolve()]
    assert manager.dubbed_pending_paths == [dubbed.resolve()]
    manager.close_window()
    root.update()
root.destroy()
print(f"audio_player_lazy_playlist_ok: {elapsed:.3f}s")
