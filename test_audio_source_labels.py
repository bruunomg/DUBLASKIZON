import tempfile
import tkinter as tk
from pathlib import Path

import duration_converter_tab
import format_converter_tab


class PlayerCapture:
    def __init__(self):
        self.calls = []

    def play_all(self, files, title):
        self.calls.append((list(files), title))


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        project = Path(temp_dir)
        original_dir = project / "WAV ORIGINAIS"
        dubbed_dir = project / "dublado"
        original_dir.mkdir()
        dubbed_dir.mkdir()
        original = original_dir / "cena_001.wav"
        dubbed = dubbed_dir / "cena_001.wav"
        original.write_bytes(b"RIFF-original")
        dubbed.write_bytes(b"RIFF-dubbed")

        root = tk.Tk()
        root.withdraw()
        root.project_root = project
        app = format_converter_tab.FormatConverterApp(root, embedded=True, project_root=project)
        app.load_from_review()
        root.update_idletasks()
        rows = app.listbox.get(0, "end")
        assert any("cena_001.wav [ORIGINAL]" == row for row in rows), rows
        assert any("cena_001.wav [DUBLADO]" == row for row in rows), rows
        app.load_from_batch()
        root.update_idletasks()
        rows = app.listbox.get(0, "end")
        assert any("[ORIGINAL]" in row for row in rows)
        assert any("[DUBLADO]" in row for row in rows)
        root.destroy()

    duration_app = duration_converter_tab.DurationConverterApp.__new__(duration_converter_tab.DurationConverterApp)
    duration_app.original_files = [Path("original_001.wav"), Path("original_002.wav")]
    duration_app.dubbed_files = [Path("dubbed_001.wav")]
    duration_app.audio_player = PlayerCapture()
    duration_app.play_all_kind("original")
    duration_app.play_all_kind("dubbed")
    assert duration_app.audio_player.calls[0][1] == "ÁUDIOS ORIGINAIS (2)"
    assert duration_app.audio_player.calls[1][1] == "ÁUDIOS DUBLADOS (1)"


if __name__ == "__main__":
    main()
    print("audio_source_labels_ok")
