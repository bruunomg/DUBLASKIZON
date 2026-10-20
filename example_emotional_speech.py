"""Exemplo de integração com os comandos já gerenciados pelo Dublaskizon.

Importar este arquivo não inicia downloads nem geração. Chame a função numa
thread de trabalho e envie o resultado/erro à interface por Queue + root.after.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from emotional_speech import (
    CommandSpeechEngine, ExpressiveSpeechError, FFmpegNormalizer,
    GenerationResult, SegmentProgress, VoiceProfile, generate_expressive_speech,
)


def generate_with_dublaskizon(
    text: str,
    profile: VoiceProfile,
    output_path: str | Path,
    model: str,
    *,
    language: str = "Portuguese",
    pause_ms: float = 150,
    on_progress: Callable[[SegmentProgress], None] | None = None,
) -> GenerationResult:
    # Imports locais: o módulo principal continua independente de Tk e de IA.
    import batch_tab
    import dependency_setup
    from f5_backend import MODEL as F5_RUSSIAN_MODEL

    if model == F5_RUSSIAN_MODEL and language.casefold() not in {
        "ru", "russian", "en", "english"
    }:
        raise ExpressiveSpeechError(
            "Esse F5-TTS Russian suporta russo/inglês. Para português, selecione "
            "OmniVoice BR-PT ou o motor F5 compatível com português."
        )
    command = batch_tab.find_voice_command(model)
    if not command:
        raise ExpressiveSpeechError("Prepare o motor selecionado na janela Requisitos.")
    environment = dict(dependency_setup.official_environment())
    ffmpeg_folder = batch_tab.find_ffmpeg_directory()
    normalizer = None
    if ffmpeg_folder:
        environment["PATH"] = str(ffmpeg_folder) + os.pathsep + environment.get("PATH", "")
        executable = Path(ffmpeg_folder) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if executable.is_file():
            normalizer = FFmpegNormalizer(str(executable))
    engine = CommandSpeechEngine(command, model, language, environment)
    return generate_expressive_speech(
        text, profile, engine, output_path,
        pause_ms=pause_ms, normalizer=normalizer, on_progress=on_progress,
    )


# Dentro do worker do botão DUBLAR:
#
# profile = VoiceProfile({
#     "neutro": r"C:\Vozes\Andre\neutro.wav",
#     "alegre": r"C:\Vozes\Andre\alegre.wav",
#     "sussurro": r"C:\Vozes\Andre\sussurro.wav",
#     "raiva": r"C:\Vozes\Andre\raiva.wav",
#     "triste": r"C:\Vozes\Andre\triste.wav",
#     "grito": r"C:\Vozes\Andre\grito.wav",
# }, name="André")
# try:
#     result = generate_with_dublaskizon(
#         "[alegre] Olá! [sussurro] Vem cá, não conte a ninguém.",
#         profile, r"C:\Saida\Andre.wav", batch_tab.MODEL,
#         on_progress=lambda event: ui_queue.put(("progresso", event)),
#     )
#     ui_queue.put(("concluido", result))
# except Exception as error:
#     # O worker termina; a aplicação continua aberta.
#     ui_queue.put(("erro", str(error)))
