from __future__ import annotations

import tempfile
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
        nested_target = app.output_target(nested_source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert nested_target == root / "out" / "CAP01" / "fala.mp3"
        target = app.output_target(source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert target.name == "voice.mp3"
        (root / "out").mkdir()
        target.touch()
        next_target = app.output_target(source, root / "out", "MP3 — 320 kbps — 48 kHz — estéreo")
        assert next_target.name == "voice_convertido.mp3"


if __name__ == "__main__":
    main()
    print("format_converter_ok")
