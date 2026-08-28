import tempfile
import tkinter as tk
from pathlib import Path

import audio_player


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        dubbed_dir = project / "dublado"
        original_dir = project / "WAV ORIGINAIS"
        dubbed_dir.mkdir()
        original_dir.mkdir()
        dubbed_one = dubbed_dir / "cena_001.wav"
        dubbed_two = dubbed_dir / "cena_002.wav"
        original_one = original_dir / dubbed_one.name
        original_two = original_dir / dubbed_two.name
        for path in (dubbed_one, dubbed_two, original_one, original_two):
            path.write_bytes(b"RIFF-test")
        manager = audio_player.AudioPlayerManager(root, project)
        manager.play_one(dubbed_one, "OUVIR CENA — cena_001", playlist=[dubbed_one, dubbed_two], index=0)
        root.update_idletasks()
        assert manager.previous_button.cget("state") == "disabled"
        assert manager.next_button.cget("state") == "normal"
        assert manager.start_button.cget("text") == "▶  INICIAR DUBLADO"
        assert manager.original_button.cget("text") == "▶  INICIAR ORIGINAL"
        assert manager.original_button.cget("state") == "normal"
        assert manager.original_pending_paths == [original_one.resolve()]
        manager.navigate(1)
        root.update_idletasks()
        assert manager.pending_paths == [dubbed_two.resolve()]
        assert manager.original_pending_paths == [original_two.resolve()]
        assert manager.previous_button.cget("state") == "normal"
        assert manager.next_button.cget("state") == "disabled"
        manager.close_window()

        deep_dir = project
        for index in range(12):
            deep_dir = deep_dir / (f"pasta_com_endereco_muito_comprido_{index:02d}")
        deep_dir.mkdir(parents=True)
        long_dubbed = deep_dir / "cena_com_endereco_longo.wav"
        long_original = original_dir / long_dubbed.name
        long_dubbed.write_bytes(b"RIFF-long")
        long_original.write_bytes(b"RIFF-long-original")
        manager.play_one(long_dubbed, "OUVIR CENA — caminho longo", playlist=[long_dubbed], index=0)
        root.update_idletasks()
        window_top = manager.window.winfo_rooty()
        window_bottom = window_top + manager.window.winfo_height()
        for button in (manager.previous_button, manager.next_button, manager.original_button, manager.start_button, manager.stop_button, manager.close_button):
            assert button.winfo_rooty() + button.winfo_height() <= window_bottom, (button, window_bottom)
            assert button.winfo_rootx() >= manager.window.winfo_rootx()
        assert len(manager._compact_path(long_dubbed)) <= 82
        manager.close_window()
    root.destroy()


if __name__ == "__main__":
    main()
    print("audio_player_modes_ok")
