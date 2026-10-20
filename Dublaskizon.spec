# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import runpy
runpy.run_path("write_version_info.py")
APP_VERSION=runpy.run_path("app_version.py")["APP_VERSION"]

datas = [('emotional_voices', 'emotional_voices'), ('Dublaskizon.ico', '.'), ('Dublaskizon_TUTORIAL.pdf', '.')]
binaries = []
hiddenimports = ['component_uninstall', 'simple_scene_editor', 'shared_audio_tools', 'voice_requirements', 'audacity_setup', 'waveform_navigation', 'scene_audio_choices', 'scene_review_drawer', 'audacity_openvino', 'audacity_scene_ui', 'batch_text_preparation', 'app_version','transcription_scene_editor','theme_web_sources','theme_research','api_configuration','api_settings_ui','translation_output','semantic_review','translation_context','transcription_tab','transcription_backend','review_memory_ui', 'background_audio', 'project_trash', 'audio_versions', 'pydub', 'audioop', 'numpy', 'repetition_prosody', 'fish_backend', 'warm_inference', 'speech_completeness', 'voice_reference', 'qwen_backend', 'native_emotions', 'emotional_speech', 'text_to_speech_tab', 'audio_frequency_separator_tab', 'batch_tab', 'review_tab', 'duration_converter_tab', 'format_converter_tab', 'video_converter_tab', 'video_preview', 'video_audio_swap_tab', 'wem_filter_tab', 'voice_clone_tab', 'personalized_dubbing_tab', 'audio_clone_preprocessor', 'main', 'audio_player', 'audio_clip_timeline', 'scene_parts', 'find_panel', 'dependency_setup', 'generation_progress', 'f5_backend', 'directml_backend', 'audio_translation', 'voice_character', 'ui_theme', 'i18n', 'tkinterdnd2']
excluded_heavy_runtime = ['scipy', 'librosa', 'sklearn', 'numba', 'llvmlite', 'torch', 'torchvision', 'torchaudio', 'transformers', 'diffusers', 'gradio', 'pandas', 'pyarrow', 'matplotlib', 'qwen_tts', 'bitsandbytes']
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['Dublaskizon.py'],
    pathex=['build_vendor'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_heavy_runtime,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'Dublaskizon V{APP_VERSION}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Dublaskizon.ico'],
    version='version_info.txt',
)


