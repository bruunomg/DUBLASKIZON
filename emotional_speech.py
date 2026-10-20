"""Tags emocionais por troca de referência; não injeta tags no texto falado.

Sem dependências de IA no processo da interface. Os motores podem executar em
outro processo por CommandSpeechEngine ou ser adaptados ao protocolo SpeechEngine.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence, TypedDict


class EmotionSegment(TypedDict):
    emocao: str
    texto_limpo: str


class ExpressiveSpeechError(RuntimeError):
    """Erro recuperável: a interface deve mostrá-lo sem encerrar a aplicação."""


class SegmentGenerationError(ExpressiveSpeechError):
    def __init__(self, index: int, emotion: str, detail: str):
        self.index = index
        self.emotion = emotion
        super().__init__(f"Falha no trecho {index} ({emotion}): {detail}")


def _emotion_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.strip().casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[\s-]+", "_", value)


# Reconhece também os marcadores antigos do Dublaskizon. Tags consecutivas
# mudam a referência, mas não criam trechos vazios nem são pronunciadas.
_TAG = re.compile(r"\[\[EXPRESSAO:([^\[\]\r\n]+)\]\]|\[([^\[\]\r\n]+)\]", re.I)


def parse_emotion_tags(text: str) -> list[EmotionSegment]:
    """Divide texto; a emoção permanece até a próxima tag. Prefixo é neutro."""
    if not isinstance(text, str):
        raise TypeError("O texto deve ser uma string.")
    result: list[EmotionSegment] = []
    emotion, start = "neutro", 0
    for match in _TAG.finditer(text):
        clean = text[start:match.start()].strip()
        if clean:
            result.append({"emocao": emotion, "texto_limpo": clean})
        emotion = _emotion_name(match.group(1) or match.group(2)) or "neutro"
        start = match.end()
    clean = text[start:].strip()
    if clean:
        result.append({"emocao": emotion, "texto_limpo": clean})
    return result


@dataclass(frozen=True)
class ReferenceChoice:
    requested_emotion: str
    used_emotion: str
    path: Path


@dataclass
class VoiceProfile:
    """Referências do MESMO personagem; referências opcionais ausentes usam neutro."""
    references: Mapping[str, str | Path]
    name: str = "Personagem"

    def __post_init__(self) -> None:
        self.references = {
            _emotion_name(key): Path(value).expanduser().resolve()
            for key, value in self.references.items()
        }
        neutral = self.references.get("neutro")
        if neutral is None or not self._available(neutral):
            raise ExpressiveSpeechError("Configure um WAV neutro existente para o personagem.")

    @staticmethod
    def _available(path: Path) -> bool:
        return path.suffix.casefold() == ".wav" and path.is_file() and path.stat().st_size > 0

    def select_reference(self, emotion: str) -> ReferenceChoice:
        requested = _emotion_name(emotion)
        candidate = self.references.get(requested)
        if candidate is not None and self._available(candidate):
            return ReferenceChoice(requested, requested, candidate)
        neutral = self.references["neutro"]
        if not self._available(neutral):
            raise ExpressiveSpeechError("A referência neutra foi removida ou está vazia.")
        return ReferenceChoice(requested, "neutro", neutral)


class SpeechEngine(Protocol):
    def synthesize(self, text: str, ref_audio_path: Path, output_path: Path) -> None:
        """Gera um WAV completo no destino; levanta exceção em caso de falha."""
        ...


def _hidden_process_options() -> dict[str, object]:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


@dataclass
class CommandSpeechEngine:
    """Adaptador dos comandos F5/OmniVoice existentes no Dublaskizon.

    O comando é uma lista de argumentos, nunca código shell. Não baixa modelos.
    Use somente um modelo que suporte o idioma escolhido.
    """
    command: Sequence[str]
    model: str
    language: str = "Portuguese"
    environment: Mapping[str, str] | None = None
    timeout_seconds: float = 600

    def synthesize(self, text: str, ref_audio_path: Path, output_path: Path) -> None:
        if not self.command:
            raise ExpressiveSpeechError("Motor de fala não configurado.")
        args = [*self.command, "--model", self.model, "--text", text,
                "--language", self.language, "--ref_audio", str(ref_audio_path),
                "--output", str(output_path)]
        result = subprocess.run(
            args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", timeout=self.timeout_seconds,
            env=dict(self.environment) if self.environment is not None else None,
            **_hidden_process_options(),
        )
        if result.returncode:
            raise ExpressiveSpeechError(
                f"Motor terminou com código {result.returncode}.\n{result.stdout[-4000:]}"
            )


@dataclass
class FFmpegNormalizer:
    """Opcional: converte WAV float/formatos diferentes para PCM comum.

    Não altera duração, velocidade ou tom. PCM 24-bit evita redução desnecessária
    para 16-bit. Usa o FFmpeg já instalado pela ferramenta.
    """
    executable: str
    sample_rate: int = 24000
    channels: int = 1
    timeout_seconds: float = 120

    def __call__(self, source: Path, destination: Path) -> None:
        result = subprocess.run(
            [self.executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(source), "-ar", str(self.sample_rate), "-ac", str(self.channels),
             "-c:a", "pcm_s24le", str(destination)],
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", timeout=self.timeout_seconds,
            **_hidden_process_options(),
        )
        if result.returncode:
            raise ExpressiveSpeechError(f"Falha ao preparar WAV: {result.stdout[-2000:]}")


def _join_pcm_wavs(paths: Sequence[Path], output: Path, pause_ms: float) -> None:
    """Concatena em blocos pequenos: não carrega o áudio inteiro na memória."""
    expected: tuple[int, int, int] | None = None
    with wave.open(str(output), "wb") as destination:
        for index, path in enumerate(paths):
            with wave.open(str(path), "rb") as source:
                fmt = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                if source.getcomptype() != "NONE" or source.getnframes() == 0:
                    raise ExpressiveSpeechError(f"WAV vazio ou comprimido: {path.name}")
                if expected is None:
                    expected = fmt
                    destination.setnchannels(fmt[0])
                    destination.setsampwidth(fmt[1])
                    destination.setframerate(fmt[2])
                elif fmt != expected:
                    raise ExpressiveSpeechError(
                        "Os trechos têm formatos WAV diferentes. Configure FFmpegNormalizer."
                    )
                if index:
                    # PCM 8-bit é sem sinal: o silêncio é 128, não zero.
                    sample = b"\x80" if fmt[1] == 1 else b"\x00" * fmt[1]
                    frames_left = round(fmt[2] * pause_ms / 1000)
                    while frames_left:
                        count = min(frames_left, 16384)
                        destination.writeframesraw(sample * fmt[0] * count)
                        frames_left -= count
                bytes_read = 0
                while data := source.readframes(16384):
                    destination.writeframesraw(data)
                    bytes_read += len(data)
                if bytes_read != source.getnframes() * fmt[0] * fmt[1]:
                    raise ExpressiveSpeechError(f"WAV incompleto: {path.name}")


@dataclass(frozen=True)
class SegmentProgress:
    index: int
    total: int
    stage: str  # generating / completed
    reference: ReferenceChoice


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    segments: tuple[EmotionSegment, ...]
    references: tuple[ReferenceChoice, ...]


def generate_expressive_speech(
    text: str,
    profile: VoiceProfile,
    engine: SpeechEngine,
    output_path: str | Path,
    *,
    pause_ms: float = 150,
    normalizer: Callable[[Path, Path], None] | None = None,
    on_progress: Callable[[SegmentProgress], None] | None = None,
) -> GenerationResult:
    """Gera todos os trechos ou preserva a saída anterior se qualquer um falhar.

    Execute numa thread de trabalho. on_progress pode alimentar uma Queue para
    a interface Tk; não atualize widgets diretamente a partir dessa thread.
    Temporários são removidos também quando o motor/concatenação falha.
    """
    segments = parse_emotion_tags(text)
    if not segments:
        raise ExpressiveSpeechError("Digite um texto com palavras para gerar a fala.")
    if not math.isfinite(pause_ms) or not 0 <= pause_ms <= 60000:
        raise ExpressiveSpeechError("A pausa deve estar entre 0 e 60000 ms.")
    output = Path(output_path).expanduser().resolve()
    if output.suffix.casefold() != ".wav":
        raise ExpressiveSpeechError("O arquivo final deve ter extensão .wav.")
    choices = tuple(profile.select_reference(s["emocao"]) for s in segments)
    if output in profile.references.values():
        raise ExpressiveSpeechError("A saída não pode substituir uma referência do personagem.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dublaskizon_emotions_", dir=output.parent) as directory:
        folder = Path(directory)
        generated: list[Path] = []
        for index, (segment, choice) in enumerate(zip(segments, choices), 1):
            try:
                if on_progress:
                    on_progress(SegmentProgress(index, len(segments), "generating", choice))
                raw = folder / f"{index:05d}_raw.wav"
                engine.synthesize(segment["texto_limpo"], choice.path, raw)
                if not raw.is_file() or raw.stat().st_size == 0:
                    raise ExpressiveSpeechError("O motor não produziu um WAV.")
                prepared = folder / f"{index:05d}_pcm.wav" if normalizer else raw
                if normalizer:
                    normalizer(raw, prepared)
                # Detecta uma saída inválida antes de iniciar o próximo trecho.
                with wave.open(str(prepared), "rb") as check:
                    if check.getnframes() == 0:
                        raise ExpressiveSpeechError("O motor produziu um áudio vazio.")
                generated.append(prepared)
                if on_progress:
                    on_progress(SegmentProgress(index, len(segments), "completed", choice))
            except Exception as error:
                raise SegmentGenerationError(index, choice.requested_emotion, str(error)) from error
        final = folder / "final.wav"
        try:
            _join_pcm_wavs(generated, final, pause_ms)
            # Substitui somente depois da geração completa; mesmo volume/disco.
            os.replace(final, output)
        except Exception as error:
            raise ExpressiveSpeechError(f"Não foi possível finalizar o áudio: {error}") from error
    return GenerationResult(output, tuple(segments), choices)
