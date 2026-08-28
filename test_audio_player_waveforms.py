from pathlib import Path
import tempfile
import wave

from audio_player import AudioPlayerManager


def write_pcm24(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for value in (0, 1_000_000, -1_000_000, 0):
        if value < 0:
            value += 1 << 24
        frames.append(int(value).to_bytes(3, "little", signed=False))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(3)
        wav_file.setframerate(8000)
        wav_file.writeframes(b"".join(frames))


with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    wav_path = root / "pcm24.wav"
    write_pcm24(wav_path)
    data = AudioPlayerManager._read_waveform(wav_path)
    assert data is not None
    assert data["channels"] == 1
    assert data["sample_rate"] == 8000
    assert data["duration"] == 4 / 8000
    assert max(data["samples"]) > 0.1

    assert AudioPlayerManager._read_waveform(root / "missing.wav") is None
    invalid_path = root / "invalid.wav"
    invalid_path.write_bytes(b"not a wav")
    assert AudioPlayerManager._read_waveform(invalid_path) is None
    empty_path = root / "empty.wav"
    with wave.open(str(empty_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
    empty_data = AudioPlayerManager._read_waveform(empty_path)
    assert empty_data is not None
    assert empty_data["samples"] == []

assert AudioPlayerManager._format_wave_duration(0) == "00:00.00"
assert AudioPlayerManager._format_wave_duration(65.432) == "01:05.43"
print("audio_player_waveforms_ok")
