# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('emotional_voices', 'emotional_voices'), ('Dublaskizon.ico', '.'), ('Dublaskizon_TUTORIAL.pdf', '.')]
binaries = []
hiddenimports = ['project_trash', 'audio_versions', 'pydub', 'audioop', 'numpy', 'repetition_prosody', 'fish_backend', 'warm_inference', 'speech_completeness', 'voice_reference', 'qwen_backend', 'native_emotions', 'emotional_speech', 'text_to_speech_tab', 'audio_frequency_separator_tab', 'batch_tab', 'review_tab', 'duration_converter_tab', 'format_converter_tab', 'video_converter_tab', 'video_preview', 'video_audio_swap_tab', 'wem_filter_tab', 'voice_clone_tab', 'personalized_dubbing_tab', 'audio_clone_preprocessor', 'main', 'audio_player', 'audio_clip_timeline', 'scene_parts', 'find_panel', 'dependency_setup', 'generation_progress', 'f5_backend', 'directml_backend', 'audio_translation', 'voice_character', 'ui_theme', 'i18n', 'tkinterdnd2']
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
    name='Dublaskizon',
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
)
