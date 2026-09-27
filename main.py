"""CLI do pré-processador de áudio para clonagem de voz."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from audio_clone_preprocessor import AudioCloneProcessor, AudioProcessingError, format_bytes, format_seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Corta, junta, normaliza e prepara áudios para clonagem de voz.")
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="Um ou mais arquivos de áudio de entrada.")
    parser.add_argument("--target", required=True, choices=("omnivoice", "eleven_instant", "eleven_pro"), help="Plataforma/modo de destino.")
    parser.add_argument("--output", type=Path, default=Path("REDIMENSIONAR ÁUDIO PARA CLONAR"), help="Pasta raiz dos resultados (padrão: REDIMENSIONAR ÁUDIO PARA CLONAR).")
    parser.add_argument("--format", choices=("wav", "mp3", "flac", "ogg", "aiff", "m4a"), default="wav", help="Formato de saída: wav, mp3, flac, ogg, aiff ou m4a (padrão: wav).")
    parser.add_argument("--bitrate", default="256k", help="Bitrate do MP3, quando aplicável (padrão: 256k).")
    parser.add_argument("--channels", type=int, choices=(1, 2), default=1, help="Canais da saída: 1 mono ou 2 estéreo (padrão: 1).")
    parser.add_argument("--silence-db", type=int, default=-35, help="Limiar de silêncio usado para encontrar cortes (padrão: -35 dB).")
    parser.add_argument("--silence-seconds", type=float, default=0.20, help="Duração mínima de silêncio para ser um limite (padrão: 0.20 s).")
    parser.add_argument("--omnivoice-seconds", type=float, default=10.0, help="Duração alvo no modo OmniVoice (5–25 s).")
    parser.add_argument("--block-minutes", type=float, default=30.0, help="Duração alvo de cada bloco Professional (30–45 min).")
    parser.add_argument("--no-normalize", action="store_true", help="Não aplicar normalização de pico para -1 dBFS.")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório completo em JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        processor = AudioCloneProcessor(silence_db=args.silence_db, silence_seconds=args.silence_seconds)
        report = processor.process(
            args.input,
            args.target,
            output_root=args.output,
            output_format=args.format,
            bitrate=args.bitrate,
            channels=args.channels,
            normalize=not args.no_normalize,
            omnivoice_seconds=args.omnivoice_seconds,
            block_minutes=args.block_minutes,
        )
    except AudioProcessingError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"Modo: {report.target}")
    print(f"Duração de entrada: {format_seconds(report.input_duration)}")
    print(f"Duração de saída: {format_seconds(report.output_duration)}")
    for path in report.outputs:
        print(f"Saída: {path} ({format_bytes(path.stat().st_size)})")
    for warning in report.warnings:
        print(f"AVISO: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
