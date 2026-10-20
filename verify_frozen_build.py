"""Audit a PyInstaller EXE before it is accepted as a Dublaskizon release."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REQUIRED = {'component_uninstall', 'simple_scene_editor', 'shared_audio_tools', 'voice_requirements', 'audacity_setup', 'waveform_navigation', 'scene_audio_choices', 'scene_review_drawer', 'audacity_openvino', 'audacity_scene_ui', 'batch_text_preparation', 'app_version','transcription_scene_editor','theme_web_sources','theme_research','api_configuration','api_settings_ui','translation_output','semantic_review','translation_context','transcription_tab','transcription_backend','review_memory_ui', 'background_audio', 'project_trash', 'audio_versions', 'pydub', 'audioop', 'numpy', 'repetition_prosody',
    'Dublaskizon', 'warm_inference', 'speech_completeness', 'voice_reference', 'fish_backend', 'qwen_backend', 'native_emotions', 'emotional_speech', 'text_to_speech_tab', 'audio_frequency_separator_tab', 'batch_tab', 'review_tab',
    'duration_converter_tab', 'format_converter_tab', 'video_converter_tab',
    'video_preview', 'video_audio_swap_tab', 'wem_filter_tab', 'voice_clone_tab',
    'personalized_dubbing_tab', 'audio_clone_preprocessor', 'main', 'audio_player',
    'audio_clip_timeline', 'scene_parts', 'find_panel', 'dependency_setup',
    'generation_progress', 'f5_backend', 'directml_backend', 'audio_translation',
    'voice_character', 'ui_theme', 'i18n',
}
HEAVY_EXTERNAL = {
    'scipy', 'librosa', 'sklearn', 'numba', 'llvmlite', 'torch', 'torchvision',
    'torchaudio', 'transformers', 'diffusers', 'gradio', 'pandas', 'pyarrow',
    'matplotlib', 'qwen_tts', 'bitsandbytes',
}
MAX_EXE_BYTES = 120 * 1024 * 1024


def verify_entries(lines):
    entries = {line.strip() for line in lines if line.strip()}
    # Extension modules are stored as binary filenames rather than PYZ names.
    # Python 3.12 has audioop.pyd; newer builds may have an ABI-tagged filename.
    for item in tuple(entries):
        filename = item.replace('\\', '/')
        if '/' not in filename and filename.lower().endswith(('.pyd', '.so')):
            entries.add(filename.split('.', 1)[0])
    missing = sorted(REQUIRED - entries)
    embedded_heavy = sorted(module for module in HEAVY_EXTERNAL if any(item == module or item.startswith(module + '.') for item in entries))
    return missing, embedded_heavy


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print('Uso: python verify_frozen_build.py caminho-do-exe', file=sys.stderr);return 2
    executable = Path(args[0]).resolve()
    if not executable.is_file():
        print(f'ERRO: EXE não encontrado: {executable}', file=sys.stderr);return 2
    if executable.stat().st_size > MAX_EXE_BYTES:
        print(f'ERRO: EXE acima de 120 MB: {executable.stat().st_size} bytes', file=sys.stderr);return 3
    command=[sys.executable,'-m','PyInstaller.utils.cliutils.archive_viewer','-r','-b',str(executable)]
    result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace')
    if result.returncode:
        print('ERRO: não foi possível ler o conteúdo congelado.\n'+result.stderr,file=sys.stderr);return 4
    missing,embedded_heavy=verify_entries(result.stdout.splitlines())
    if missing:
        print('ERRO: módulos do Dublaskizon ausentes do EXE: '+', '.join(missing),file=sys.stderr);return 5
    if embedded_heavy:
        print('ERRO: bibliotecas externas pesadas incorporadas ao EXE: '+', '.join(embedded_heavy),file=sys.stderr);return 6
    print(f'AUDITORIA OK: {len(REQUIRED)} módulos do aplicativo presentes; bibliotecas pesadas externas ausentes; {executable.stat().st_size/1048576:.2f} MB.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


