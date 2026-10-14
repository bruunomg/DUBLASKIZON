@echo off
setlocal
cd /d "%~dp0"

echo ================================================================
echo        BUILD DUBLASKIZON.EXE
echo ================================================================
echo.

echo [1/3] Verificando Python...
python --version
if errorlevel 1 (
    echo ERRO: Python nao foi encontrado no PATH.
    echo Instale Python oficial 3.12 ou 3.13 e marque "Add Python to PATH".
    pause
    exit /b 1
)

echo.
echo [2/3] Instalando/atualizando PyInstaller...
python -m pip install --index-url https://pypi.org/simple -r requirements.txt
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar o PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/3] Gerando Dublaskizon.exe...
echo Conferindo as dependencias de audio antes de compilar...
python -c "import sys; sys.path.insert(0,'build_vendor'); import audioop; import pydub; import numpy; assert audioop.rms(b'\x01\x00' * 8, 2) == 1; print('Dependencias de audio OK')"
if errorlevel 1 (
    echo ERRO: audioop, pydub ou numpy nao podem ser usados neste Python.
    echo Execute python -m pip install -r requirements.txt e tente novamente.
    pause
    exit /b 1
)

python -m PyInstaller --paths build_vendor --hidden-import pydub --hidden-import audioop --hidden-import numpy --hidden-import project_trash --hidden-import audio_versions --hidden-import repetition_prosody --onefile --windowed --clean --noconfirm --name Dublaskizon --icon "Dublaskizon.ico" --exclude-module scipy --exclude-module librosa --exclude-module sklearn --exclude-module numba --exclude-module llvmlite --exclude-module qwen_tts --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module transformers --exclude-module diffusers --exclude-module gradio --exclude-module pandas --exclude-module pyarrow --exclude-module matplotlib --exclude-module bitsandbytes --hidden-import fish_backend --hidden-import warm_inference --hidden-import speech_completeness --hidden-import voice_reference --hidden-import qwen_backend --hidden-import native_emotions --hidden-import emotional_speech --hidden-import text_to_speech_tab --hidden-import audio_frequency_separator_tab --hidden-import batch_tab --hidden-import review_tab --hidden-import duration_converter_tab --hidden-import format_converter_tab --hidden-import video_converter_tab --hidden-import video_preview --hidden-import video_audio_swap_tab --hidden-import wem_filter_tab --hidden-import voice_clone_tab --hidden-import personalized_dubbing_tab --hidden-import audio_clone_preprocessor --hidden-import main --hidden-import audio_player --hidden-import audio_clip_timeline --hidden-import scene_parts --hidden-import find_panel --hidden-import dependency_setup --hidden-import generation_progress --hidden-import f5_backend --hidden-import directml_backend --hidden-import audio_translation --hidden-import voice_character --hidden-import ui_theme --hidden-import i18n --hidden-import tkinterdnd2 --collect-all tkinterdnd2 --add-data "emotional_voices;emotional_voices" --add-data "Dublaskizon.ico;." --add-data "Dublaskizon_TUTORIAL.pdf;." Dublaskizon.py
if errorlevel 1 (
    echo ERRO: a compilacao falhou.
    pause
    exit /b 1
)
powershell -NoProfile -Command "$p=Get-Item -LiteralPath 'dist\Dublaskizon.exe'; Write-Host ('Tamanho do EXE: {0:N1} MB' -f ($p.Length/1MB)); if($p.Length -gt 125829120){exit 2}"
if errorlevel 1 (
    echo ERRO: o EXE ultrapassou 120 MB. O build incorporou bibliotecas externas indevidas e foi rejeitado.
    pause
    exit /b 1
)
python verify_frozen_build.py "dist\Dublaskizon.exe"
if errorlevel 1 (
    echo ERRO: a auditoria interna do EXE encontrou modulo ausente ou biblioteca indevida.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo BUILD CONCLUIDO
echo ================================================================
echo O executavel foi criado em:
echo %~dp0dist\Dublaskizon.exe
echo.
echo Copie esse arquivo para a pasta raiz de cada projeto, ao lado de:
echo   WAV ORIGINAIS\
echo   TXT TEXTO PORTUGUES\
echo   TXT TEXTO ORIGINAL\
echo   TXT TEXTO do WAV TRANSCRITO e TRADUZIDO\
echo   OUTRAS TRADUCOES\
echo   dublado\
echo   revisoes\
echo.
pause
endlocal







