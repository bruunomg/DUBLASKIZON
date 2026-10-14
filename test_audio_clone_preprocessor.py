import json
import subprocess
import tempfile
import wave
from pathlib import Path

from audio_clone_preprocessor import AudioCloneProcessor, format_bytes, format_seconds


def make_wav(path: Path, seconds: float, sample_rate: int = 8000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b'\x00\x00' * frames)


with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    source = root / 'voz_teste.wav'
    make_wav(source, 12)
    processor = AudioCloneProcessor(silence_seconds=0.10)
    info = processor.probe(source)
    assert 11.9 <= info.duration <= 12.1
    assert info.channels == 1
    assert format_seconds(info.duration) == '00:00:12'
    assert format_bytes(info.size_bytes).endswith(('KB', 'MB'))
    progress_values = []
    report = processor.process([source], 'omnivoice', output_root=root / 'output', output_format='wav', channels=1, progress_callback=lambda percent, stage: progress_values.append((percent, stage)))
    assert report.outputs and report.outputs[0].parent.name == 'omnivoice'
    assert progress_values and progress_values[-1][0] == 100.0
    assert [value for value, _stage in progress_values] == sorted(value for value, _stage in progress_values)
    assert report.outputs[0].exists()
    assert 5.0 <= report.output_duration <= 25.0
    assert report.segments[0].end <= 12.1
    source2 = root / 'voz_teste_2.wav'
    make_wav(source2, 15)
    joined = processor.process([source, source2], 'omnivoice', output_root=root / 'output', output_format='mp3', channels=1, normalize=False)
    assert joined.outputs and joined.outputs[0].exists()
    assert joined.input_duration >= 26.9
    assert 24.5 <= joined.output_duration <= 25.5
    assert any('excedia' in warning for warning in joined.warnings)
    instant = processor.process([source], 'eleven_instant', output_root=root / 'output', output_format='mp3', channels=1, normalize=False)
    assert instant.outputs and instant.outputs[0].parent.name == 'elevenlabs_instant'
    assert any('mínimo' in warning or 'recomenda' in warning for warning in instant.warnings)
    professional = processor.process([source], 'eleven_pro', output_root=root / 'output', output_format='wav', channels=1, normalize=False, block_minutes=30)
    assert professional.outputs and professional.outputs[0].parent.name == 'elevenlabs_pro'
    assert professional.segments[0].duration > 0
    blocks = processor.choose_blocks(3700, 1800, [], 2700)
    assert len(blocks) == 2
    assert sum(item.duration for item in blocks) >= 3699
    cli_output = root / 'cli-output'
    completed = subprocess.run([
        'python3', 'main.py', '--input', str(source), '--target', 'omnivoice', '--output', str(cli_output), '--format', 'mp3', '--json', '--no-normalize'
    ], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data['target'] == 'omnivoice'
    assert Path(data['outputs'][0]).exists()
print('audio_clone_preprocessor_ok')
