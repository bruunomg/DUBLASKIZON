"""Conservative transfer of the original voice's spectral coloration.

This does not copy speech or pitch from the source.  It measures broad frequency
bands and applies a small corrective EQ to the generated voice.  Radio/robot
voices usually keep more of their narrow, metallic bandwidth this way without
adding synthetic noise to ordinary dialogue.
"""
from __future__ import annotations

import math
import os
import subprocess
import wave
from pathlib import Path


_BANDS = ((90, 250), (250, 700), (700, 1800), (1800, 4000), (4000, 9000))


def _mono_samples(path: Path, seconds: float = 12.0):
    import numpy as np
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frames = source.readframes(min(source.getnframes(), int(rate * seconds)))
    if width == 1:
        data = np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0
    elif width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float64)
    elif width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        values = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        data = ((values ^ 0x800000) - 0x800000).astype(np.float64)
    elif width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float64)
    else:
        raise ValueError(f"PCM de {width * 8} bits não suportado")
    if channels > 1:
        data = data[: len(data) - len(data) % channels].reshape(-1, channels).mean(axis=1)
    data -= data.mean() if data.size else 0.0
    return rate, data


def spectral_profile(path: Path) -> dict:
    """Return normalized broad-band energy and conservative speech cutoffs."""
    import numpy as np
    rate, samples = _mono_samples(Path(path))
    if samples.size < 256 or not np.any(samples):
        raise ValueError("áudio sem amostras suficientes")
    window = np.hanning(samples.size)
    power = np.abs(np.fft.rfft(samples * window)) ** 2
    frequencies = np.fft.rfftfreq(samples.size, 1.0 / rate)
    useful = (frequencies >= 60) & (frequencies <= min(10000, rate * 0.48))
    total = float(power[useful].sum()) or 1.0
    bands = []
    for low, high in _BANDS:
        mask = (frequencies >= low) & (frequencies < min(high, rate * 0.48))
        bands.append(float(power[mask].sum()) / total)
    selected_f = frequencies[useful]
    cumulative = np.cumsum(power[useful]) / total
    low_cut = float(selected_f[min(int(np.searchsorted(cumulative, 0.01)), len(selected_f) - 1)])
    high_cut = float(selected_f[min(int(np.searchsorted(cumulative, 0.99)), len(selected_f) - 1)])
    return {"rate": rate, "bands": bands, "low_cut": low_cut, "high_cut": high_cut}


def build_filter(original: Path, generated: Path) -> tuple[str, str]:
    """Build a restrained FFmpeg filter and a human-readable detection summary."""
    source = spectral_profile(original)
    voice = spectral_profile(generated)
    filters: list[str] = []
    gains = []
    for (low, high), src_energy, gen_energy in zip(_BANDS, source["bands"], voice["bands"]):
        gain = 10.0 * math.log10(max(src_energy, 1e-8) / max(gen_energy, 1e-8))
        gain = max(-4.5, min(4.5, gain * 0.55))
        gains.append(gain)
        if abs(gain) >= 0.7:
            center = math.sqrt(low * high)
            width = max(100.0, high - low)
            filters.append(f"equalizer=f={center:.0f}:width_type=h:width={width:.0f}:g={gain:.2f}")
    # Apply narrow-band limits only when they are strong enough to indicate a
    # telephone/radio/robot treatment; ordinary speech remains full-band.
    narrow_low = source["low_cut"] >= 170
    narrow_high = source["high_cut"] <= 6200
    if narrow_low:
        filters.insert(0, f"highpass=f={max(80, min(320, source['low_cut'] * 0.75)):.0f}")
    if narrow_high:
        filters.append(f"lowpass=f={max(3200, source['high_cut'] * 1.08):.0f}")
    summary = "perfil eletrônico/rádio detectado" if narrow_low or narrow_high else "coloração natural preservada"
    return ",".join(filters), summary


def preserve_original_voice(generated: Path, original: Path, ffmpeg: str) -> str:
    """Apply the measured profile in-place; leave the generated WAV intact on failure."""
    generated, original = Path(generated), Path(original)
    filters, summary = build_filter(original, generated)
    if not filters:
        return "perfil já semelhante ao original"
    temporary = generated.with_name(f".{generated.stem}.__voz_original.wav")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(generated),
               "-af", filters, "-c:a", "pcm_s16le", str(temporary)]
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
    if result.returncode or not temporary.is_file() or temporary.stat().st_size <= 44:
        temporary.unlink(missing_ok=True)
        raise RuntimeError((result.stdout or "FFmpeg não gerou o áudio tratado")[-800:])
    os.replace(temporary, generated)
    return summary
