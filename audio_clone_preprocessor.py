"""Pré-processamento de áudio para OmniVoice e ElevenLabs.

O módulo usa FFmpeg/FFprobe por subprocesso para não depender de um backend
Python específico. Ele aceita vários arquivos, normaliza cada entrada, junta
as entradas em uma linha contínua e encontra limites de corte próximos a
silêncios. Os limites são conservadores e configuráveis; a plataforma final
continua sendo a autoridade sobre os requisitos de upload.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

SUPPORTED_INPUT_EXTENSIONS = {".mp3", ".wav", ".wave", ".flac", ".m4a", ".ogg", ".aac"}
CLONE_OUTPUT_FOLDER_NAME = "REDIMENSIONAR ÁUDIO PARA CLONAR"
MODE_OUTPUT_DIRS = {
    "omnivoice": "omnivoice",
    "eleven_instant": "elevenlabs_instant",
    "eleven_pro": "elevenlabs_pro",
}
def hidden_process_kwargs() -> dict:
    """Executa FFmpeg/FFprobe sem abrir uma janela de console no Windows."""
    if not sys.platform.startswith("win"):
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
    }


MODE_LABELS = {
    "omnivoice": "OmniVoice VoiceStudio",
    "eleven_instant": "ElevenLabs Instant",
    "eleven_pro": "ElevenLabs Professional",
}


@dataclass(frozen=True)
class AudioMode:
    key: str
    label: str
    minimum_seconds: float
    recommended_seconds: float
    maximum_seconds: float
    maximum_bytes: int | None = None
    block_minimum_seconds: float | None = None
    block_recommended_seconds: float | None = None
    block_maximum_seconds: float | None = None


MODES = {
    "omnivoice": AudioMode(
        "omnivoice", MODE_LABELS["omnivoice"], 5.0, 10.0, 25.0,
    ),
    "eleven_instant": AudioMode(
        "eleven_instant", MODE_LABELS["eleven_instant"], 60.0, 120.0, 180.0,
        maximum_bytes=400 * 1024 * 1024,
    ),
    "eleven_pro": AudioMode(
        "eleven_pro", MODE_LABELS["eleven_pro"], 30 * 60.0, 30 * 60.0, 180 * 60.0,
        maximum_bytes=450 * 1024 * 1024,
        block_minimum_seconds=30 * 60.0,
        block_recommended_seconds=30 * 60.0,
        block_maximum_seconds=45 * 60.0,
    ),
}


@dataclass
class AudioInfo:
    path: Path
    duration: float
    size_bytes: int
    format_name: str = ""
    codec: str = ""
    sample_rate: int | None = None
    channels: int | None = None
    bitrate: int | None = None

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass
class Segment:
    start: float
    end: float
    source_index: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class ProcessingReport:
    target: str
    output_dir: Path
    outputs: list[Path] = field(default_factory=list)
    input_duration: float = 0.0
    output_duration: float = 0.0
    warnings: list[str] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "output_dir": str(self.output_dir),
            "outputs": [str(path) for path in self.outputs],
            "input_duration": round(self.input_duration, 3),
            "output_duration": round(self.output_duration, 3),
            "warnings": list(self.warnings),
            "segments": [{"start": round(item.start, 3), "end": round(item.end, 3), "duration": round(item.duration, 3)} for item in self.segments],
        }


class AudioProcessingError(RuntimeError):
    """Erro recuperável mostrado pela interface ou CLI."""


class AudioCloneProcessor:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None, silence_db: int = -35, silence_seconds: float = 0.20):
        self.ffmpeg = ffmpeg or "ffmpeg"
        self.ffprobe = ffprobe or "ffprobe"
        self.silence_db = int(silence_db)
        self.silence_seconds = max(0.05, float(silence_seconds))

    def _run(self, args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(args, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None, check=False, **hidden_process_kwargs())
        except OSError as exc:
            raise AudioProcessingError(f"Não foi possível executar {args[0]}: {exc}") from exc
        if completed.returncode != 0:
            details = (completed.stderr or "").strip().splitlines()
            detail = details[-1] if details else "sem detalhes do FFmpeg"
            raise AudioProcessingError(f"Falha no processamento de áudio: {detail}")
        return completed

    def check_tools(self) -> None:
        self._run([self.ffmpeg, "-version"])
        self._run([self.ffprobe, "-version"])

    def probe(self, path: Path) -> AudioInfo:
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise AudioProcessingError(f"Arquivo não encontrado: {path}")
        result = self._run([
            self.ffprobe, "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,sample_rate,channels:format=duration,size,format_name,bit_rate",
            "-of", "json", str(path),
        ])
        try:
            data = json.loads(result.stdout or "{}")
            format_data = data.get("format", {})
            stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), {})
            duration = float(format_data.get("duration") or 0.0)
            size = int(format_data.get("size") or path.stat().st_size)
            sample_rate = int(stream["sample_rate"]) if stream.get("sample_rate") else None
            channels = int(stream["channels"]) if stream.get("channels") else None
            bitrate = int(format_data["bit_rate"]) if format_data.get("bit_rate") else None
        except (ValueError, TypeError, KeyError, OSError, StopIteration) as exc:
            raise AudioProcessingError(f"Não foi possível ler os metadados de {path.name}.") from exc
        if duration <= 0:
            raise AudioProcessingError(f"A duração de {path.name} não pôde ser determinada.")
        return AudioInfo(path, duration, size, str(format_data.get("format_name") or ""), str(stream.get("codec_name") or ""), sample_rate, channels, bitrate)

    def peak_db(self, path: Path) -> float | None:
        result = self._run([self.ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"], capture=True)
        match = re.search(r"max_volume:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*dB", result.stderr or "")
        return float(match.group(1)) if match else None

    def normalize_gain_db(self, path: Path, target_peak_db: float = -1.0) -> float:
        peak = self.peak_db(path)
        if peak is None or not math.isfinite(peak):
            return 0.0
        return round(float(target_peak_db) - peak, 4)

    def silence_intervals(self, path: Path) -> list[tuple[float, float]]:
        result = self._run([
            self.ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
            "-af", f"silencedetect=noise={self.silence_db}dB:d={self.silence_seconds}",
            "-f", "null", "-",
        ], capture=True)
        starts: list[float] = []
        intervals: list[tuple[float, float]] = []
        for line in (result.stderr or "").splitlines():
            start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
            end_match = re.search(r"silence_end:\s*([0-9.]+)", line)
            if start_match:
                starts.append(float(start_match.group(1)))
            if end_match and starts:
                intervals.append((starts.pop(0), float(end_match.group(1))))
        return intervals

    @staticmethod
    def _boundary_points(duration: float, intervals: Iterable[tuple[float, float]]) -> list[float]:
        points = {0.0, max(0.0, duration)}
        for start, end in intervals:
            points.add(max(0.0, min(duration, start)))
            points.add(max(0.0, min(duration, end)))
        return sorted(points)

    def choose_segment(self, duration: float, minimum: float, recommended: float, maximum: float, intervals: list[tuple[float, float]]) -> Segment:
        if duration <= maximum:
            return Segment(0.0, duration)
        points = self._boundary_points(duration, intervals)
        target = min(max(recommended, minimum), maximum)
        candidates: list[tuple[float, float, float]] = []
        for start in points:
            for end in points:
                length = end - start
                if minimum <= length <= maximum:
                    edge_penalty = 0.0
                    if start not in (0.0, duration):
                        edge_penalty += 0.05
                    if end not in (0.0, duration):
                        edge_penalty += 0.05
                    candidates.append((abs(length - target) + edge_penalty, start, end))
        if candidates:
            _, start, end = min(candidates, key=lambda item: item[0])
            return Segment(start, end)
        start = max(0.0, min(duration - minimum, (duration - target) / 2))
        return Segment(start, min(duration, start + min(maximum, max(minimum, target))))

    def choose_blocks(self, duration: float, block_seconds: float, intervals: list[tuple[float, float]], maximum_seconds: float) -> list[Segment]:
        if duration <= 0:
            return []
        points = self._boundary_points(duration, intervals)
        blocks: list[Segment] = []
        start = 0.0
        while start < duration - 0.05:
            desired_end = min(duration, start + block_seconds)
            candidates = [point for point in points if start + 30.0 <= point <= min(duration, start + maximum_seconds)]
            end = min(candidates, key=lambda point: abs(point - desired_end)) if candidates else desired_end
            if end <= start:
                end = min(duration, start + block_seconds)
            blocks.append(Segment(start, end, len(blocks)))
            start = end
        return blocks

    @staticmethod
    def _safe_stem(path: Path) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-")
        return value or "audio"

    def _transcode_to_wav(self, source: Path, destination: Path, channels: int, normalize: bool) -> None:
        filters: list[str] = []
        if normalize:
            filters.append(f"volume={self.normalize_gain_db(source):.4f}dB")
        args = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
        if filters:
            args += ["-af", ",".join(filters)]
        args += ["-ar", "44100", "-ac", str(channels), "-c:a", "pcm_s16le", str(destination)]
        self._run(args)

    def _concat_inputs(self, paths: list[Path], workspace: Path, channels: int, normalize: bool) -> Path:
        normalized: list[Path] = []
        for index, source in enumerate(paths):
            destination = workspace / f"normalized_{index:04d}.wav"
            self._transcode_to_wav(source, destination, channels, normalize)
            normalized.append(destination)
        concat_file = workspace / "concat.txt"
        concat_file.write_text("\n".join(f"file '{path.as_posix().replace("'", "'\\''")}'" for path in normalized) + "\n", encoding="utf-8")
        joined = workspace / "joined.wav"
        self._run([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(joined)])
        return joined

    def _export(self, source: Path, destination: Path, segment: Segment, output_format: str, bitrate: str, channels: int, normalize: bool) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        filters: list[str] = []
        if normalize:
            filters.append(f"volume={self.normalize_gain_db(source):.4f}dB")
        args = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{segment.start:.3f}", "-i", str(source), "-t", f"{segment.duration:.3f}"]
        if filters:
            args += ["-af", ",".join(filters)]
        args += ["-ar", "44100", "-ac", str(channels)]
        output_format = output_format.casefold().lstrip(".")
        if output_format == "mp3":
            args += ["-c:a", "libmp3lame", "-b:a", bitrate]
        elif output_format == "flac":
            args += ["-c:a", "flac"]
        elif output_format == "ogg":
            args += ["-c:a", "libvorbis", "-q:a", "6"]
        elif output_format == "aiff":
            args += ["-c:a", "pcm_s16be"]
        elif output_format == "m4a":
            args += ["-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart"]
        else:
            args += ["-c:a", "pcm_s16le"]
        args.append(str(destination))
        self._run(args)
        return destination

    def process(self, paths: Iterable[Path], target: str, output_root: Path = Path(CLONE_OUTPUT_FOLDER_NAME), output_format: str = "wav", bitrate: str = "256k", channels: int = 1, normalize: bool = True, omnivoice_seconds: float | None = None, block_minutes: float = 30.0, progress_callback: Callable[[float, str], None] | None = None) -> ProcessingReport:
        target = str(target).lower()
        if target not in MODES:
            raise AudioProcessingError(f"Modo desconhecido: {target}")
        source_paths = [Path(item).expanduser().resolve() for item in paths]
        if not source_paths:
            raise AudioProcessingError("Nenhum áudio foi carregado.")
        output_format = str(output_format).casefold().lstrip(".")
        if output_format not in {"wav", "mp3", "flac", "ogg", "aiff", "m4a"}:
            raise AudioProcessingError("O formato de saída deve ser WAV, MP3, FLAC, OGG, AIFF ou M4A.")
        if channels not in {1, 2}:
            raise AudioProcessingError("A quantidade de canais deve ser 1 ou 2.")
        def report_progress(percent: float, stage: str) -> None:
            if progress_callback is not None:
                progress_callback(max(0.0, min(100.0, float(percent))), stage)

        infos: list[AudioInfo] = []
        for index, path in enumerate(source_paths, start=1):
            infos.append(self.probe(path))
            report_progress(10.0 * index / max(1, len(source_paths)), f"Lendo áudio {index}/{len(source_paths)}")
        mode = MODES[target]
        output_dir = Path(output_root).expanduser().resolve() / MODE_OUTPUT_DIRS[target]
        report = ProcessingReport(target, output_dir, input_duration=sum(item.duration for item in infos))
        with tempfile.TemporaryDirectory(prefix="dublaskizon_voice_") as temporary:
            workspace = Path(temporary)
            report_progress(15.0, f"Juntando e normalizando {len(source_paths)} áudio(s)")
            joined = self._concat_inputs(source_paths, workspace, channels, normalize)
            report_progress(48.0, "Junção e normalização concluídas")
            joined_info = self.probe(joined)
            report_progress(56.0, "Analisando duração do áudio unido")
            intervals = self.silence_intervals(joined)
            report_progress(64.0, "Localizando pausas seguras para o corte")
            if target == "omnivoice":
                recommended = float(omnivoice_seconds or mode.recommended_seconds)
                recommended = max(mode.minimum_seconds, min(mode.maximum_seconds, recommended))
                if joined_info.duration < mode.minimum_seconds:
                    report.warnings.append(f"O áudio tem {joined_info.duration:.1f}s; o mínimo configurado para OmniVoice é {mode.minimum_seconds:.0f}s.")
                segment = self.choose_segment(joined_info.duration, mode.minimum_seconds, recommended, mode.maximum_seconds, intervals)
                if joined_info.duration > mode.maximum_seconds:
                    report.warnings.append(f"O conjunto unido excedia {mode.maximum_seconds:.0f}s; o excedente foi cortado no final.")
                    segment = Segment(0.0, mode.maximum_seconds)
                report.segments = [segment]
            elif target == "eleven_instant":
                if joined_info.duration < mode.minimum_seconds:
                    report.warnings.append(f"O áudio tem {joined_info.duration:.1f}s; o Instant recomenda pelo menos {mode.minimum_seconds:.0f}s.")
                segment = self.choose_segment(joined_info.duration, mode.minimum_seconds, mode.recommended_seconds, mode.maximum_seconds, intervals)
                if joined_info.duration > mode.maximum_seconds:
                    report.warnings.append(f"O conjunto unido excedia {mode.maximum_seconds:.0f}s; o excedente foi cortado no final.")
                    segment = Segment(0.0, mode.maximum_seconds)
                report.segments = [segment]
            else:
                if joined_info.duration < mode.minimum_seconds:
                    report.warnings.append("O total ficou abaixo de 30 minutos; o arquivo será processado mesmo assim para permitir revisão.")
                if joined_info.duration > mode.maximum_seconds:
                    report.warnings.append("O total excedia 180 minutos; o processamento foi limitado aos primeiros 180 minutos, cortando o excedente no final.")
                    joined_duration = mode.maximum_seconds
                else:
                    joined_duration = joined_info.duration
                block_seconds = max(mode.block_minimum_seconds or 1800.0, min(mode.block_maximum_seconds or 2700.0, float(block_minutes) * 60.0))
                report.segments = self.choose_blocks(joined_duration, block_seconds, intervals, mode.block_maximum_seconds or 2700.0)
            report_progress(72.0, f"Plano pronto: {len(report.segments)} saída(s)")
            stem = self._safe_stem(source_paths[0])
            total_segments = max(1, len(report.segments))
            for index, segment in enumerate(report.segments, 1):
                suffix = f"_{index:02d}" if target == "eleven_pro" else ""
                extension = {"wav": ".wav", "mp3": ".mp3", "flac": ".flac", "ogg": ".ogg", "aiff": ".aiff", "m4a": ".m4a"}[output_format]
                destination = output_dir / f"{stem}_{target}{suffix}{extension}"
                self._export(joined, destination, segment, output_format, bitrate, channels, normalize)
                report_progress(72.0 + 20.0 * index / total_segments, f"Exportando saída {index}/{total_segments}")
                if mode.maximum_bytes is not None and destination.stat().st_size > mode.maximum_bytes:
                    if output_format != "mp3":
                        report.warnings.append(f"{destination.name} excedeu o limite conservador; foi reexportado em mono MP3 256 kbps.")
                        destination.unlink(missing_ok=True)
                        destination = destination.with_suffix(".mp3")
                        self._export(joined, destination, segment, "mp3", "256k", 1, normalize)
                    if destination.stat().st_size > mode.maximum_bytes:
                        raise AudioProcessingError(f"Não foi possível manter {destination.name} abaixo do limite de tamanho configurado.")
                report.outputs.append(destination)
                report.output_duration += segment.duration
                report_progress(72.0 + 28.0 * index / total_segments, f"Saída {index}/{total_segments} concluída")
        report_progress(100.0, "Processamento concluído")
        return report


def format_seconds(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
