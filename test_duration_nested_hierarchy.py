import tempfile
import time
import wave
from pathlib import Path

import tkinter as tk

import duration_converter_tab


def make_wav(path: Path, seconds: float = 0.05) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * max(1, int(24000 * seconds)))


root = tk.Tk()
root.withdraw()
with tempfile.TemporaryDirectory() as folder:
    project = Path(folder)
    original_dir = project / "WAV ORIGINAIS"
    dubbed_dir = project / "dublado"
    for chapter in ("CAP01", "CAP02"):
        make_wav(original_dir / chapter / "cena.wav")
        make_wav(dubbed_dir / chapter / "cena.wav")
    backup = original_dir / "_BACKUP_OMNIVOICE" / "CAP01" / "cena.wav"
    make_wav(backup)

    listed = duration_converter_tab.list_audio_files(original_dir)
    assert len(listed) == 2, listed
    app = duration_converter_tab.DurationConverterApp(root, embedded=False, project_root=project)
    app.load_project_defaults("TESTE")
    expected = {"CAP01/cena", "CAP02/cena"}
    assert set(app.original_by_stem) == expected, app.original_by_stem
    assert set(app.dubbed_by_stem) == expected, app.dubbed_by_stem
    pairs = app.pair_items()
    assert [item[0] for item in pairs] == ["CAP01/cena", "CAP02/cena"]

    output_root = project / "AUDIOS com DURAÇAO CONVERTIDAS"
    app.get_duration = lambda _path: 1.0
    app.convert_equal = lambda _source, target, _duration, _format: (target.parent.mkdir(parents=True, exist_ok=True), target.write_bytes(b"ok"))
    app.conversion_worker(pairs, duration_converter_tab.DEFAULT_FORMAT, duration_converter_tab.OUTPUT_MODE_CHOICES[0], str(output_root), False)
    equal_dir = output_root / "AUDIO CONVERTIDO ..IGUAL.. DURAÇÃO"
    assert (equal_dir / "CAP01" / "cena.wav").is_file()
    assert (equal_dir / "CAP02" / "cena.wav").is_file()
    assert not (equal_dir / "cena.wav").exists()
    root.update()
    root.destroy()

print("duration_nested_hierarchy_ok")
