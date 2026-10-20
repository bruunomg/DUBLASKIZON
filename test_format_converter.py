from __future__ import annotations

import tempfile
import threading
import queue
from pathlib import Path

import format_converter_tab


def main() -> None:
    assert format_converter_tab.TITLE if hasattr(format_converter_tab, "TITLE") else True
    assert any(name.startswith("WAV PCM 16-bit") for name in format_converter_tab.FORMAT_CHOICES)
    assert "MP3 — 320 kbps — 48 kHz — estéreo" in format_converter_tab.FORMAT_CHOICES
    assert format_converter_tab.is_audio_file(Path("voice.wav")) is False

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        original_dir = root / "WAV ORIGINAIS"
        dubbed_dir = root / "dublado"
        original_dir.mkdir()
        dubbed_dir.mkdir()
        (original_dir / "cena_001.wav").write_bytes(b"RIFF")
        (dubbed_dir / "cena_001.wav").write_bytes(b"RIFF")
        originals, dubbed = format_converter_tab.project_audio_files(root)
        assert [path.name for path in originals] == ["cena_001.wav"]
        assert [path.name for path in dubbed] == ["cena_001.wav"]
        assert not (root / "revisoes").exists()
        source = root / "voice.wav"
        second = root / "other.mp3"
        ignored = root / "notes.txt"
        source.write_bytes(b"source")
        second.write_bytes(b"second")
        ignored.write_text("not audio", encoding="utf-8")
        listed = format_converter_tab.list_audio_files(root)
        assert set(listed) == {original_dir / "cena_001.wav", dubbed_dir / "cena_001.wav", second, source}
        nested_source = original_dir / "CAP01" / "fala.wav"
        nested_source.parent.mkdir()
        nested_source.write_bytes(b"nested")
        originals, dubbed = format_converter_tab.project_audio_files(root)
        assert nested_source in originals
        assert dubbed == [dubbed_dir / "cena_001.wav"]
        app = format_converter_tab.FormatConverterApp.__new__(format_converter_tab.FormatConverterApp)
        app.project_root = root
        app.file_relative_by_path = {}
        nested_target = app.output_target(nested_source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert nested_target == root / "out" / "WAV ORIGINAIS" / "CAP01" / "fala.mp3"
        target = app.output_target(source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert target == root / "out" / root.name / "voice.mp3"
        target.parent.mkdir(parents=True)
        target.touch()
        next_target = app.output_target(source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert next_target == target
        assert "_convertido" not in next_target.name

        dragged = root / "PERSONAGEM" / "CAP02" / "linha.wav"
        dragged.parent.mkdir(parents=True)
        dragged.write_bytes(b"RIFF")
        key = format_converter_tab.os.path.normcase(str(dragged.resolve()))
        app.file_relative_by_path[key] = Path("PERSONAGEM") / "CAP02" / "linha.wav"
        dragged_target = app.output_target(dragged, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert dragged_target == root / "out" / "PERSONAGEM" / "CAP02" / "linha.mp3"

        # O lote publica somente os convertidos, preservando cada hierarquia e
        # substituindo uma conversão anterior sem acrescentar _convertido.
        other = root / "OUTRO" / "CAP02" / "linha.wav"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"RIFF")
        other_key = format_converter_tab.os.path.normcase(str(other.resolve()))
        app.file_relative_by_path[other_key] = Path("OUTRO") / "CAP02" / "linha.wav"
        app.cancel_event = threading.Event()
        app.queue = queue.Queue()
        app.append_log = lambda _text: None
        app._log_central = lambda _text, _level: None
        app.run_ffmpeg = lambda _source, destination, _format: destination.write_bytes(b"CONVERTED")
        output = root / format_converter_tab.FORMAT_OUTPUT_FOLDER_NAME
        app.conversion_worker([dragged, other], "MP3 — 320 kbps — 48 kHz — estéreo", output)
        assert (output / "PERSONAGEM" / "CAP02" / "linha.mp3").read_bytes() == b"CONVERTED"
        assert (output / "OUTRO" / "CAP02" / "linha.mp3").read_bytes() == b"CONVERTED"
        assert not list(output.rglob("*_convertido*"))
        assert not list(output.rglob("*.wav"))


if __name__ == "__main__":
    main()
    print("format_converter_ok")
