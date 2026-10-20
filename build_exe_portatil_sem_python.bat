@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ================================================================
echo   BUILD DUBLASKIZON - EXE PORTATIL SEM PYTHON NO DESTINO
echo ================================================================
echo.
echo Este script precisa de Python apenas no computador que COMPILA.
echo O EXE gerado levara o interpretador Python e as bibliotecas do app.
echo FFmpeg, FFprobe, FFplay e SoX continuam fora do EXE e sao baixados
 echo pelo botao BAIXAR / PREPARAR FERRAMENTAS quando necessario.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao foi encontrado no computador de compilacao.
    echo Instale Python oficial 3.12 ou 3.13 e marque "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "Dublaskizon.py" (
    echo ERRO: Dublaskizon.py nao foi encontrado nesta pasta.
    pause
    exit /b 1
)

if not exist "Dublaskizon_TUTORIAL.pdf" (
    echo ERRO: Dublaskizon_TUTORIAL.pdf nao foi encontrado.
    pause
    exit /b 1
)

echo [1/3] Instalando o compilador e o suporte de arrastar-e-soltar...
python -m pip install --index-url https://pypi.org/simple -r requirements.txt
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar PyInstaller/tkinterdnd2.
    pause
    exit /b 1
)

echo.
echo [2/3] Gerando o EXE com Python incorporado...
echo Conferindo as dependencias de audio antes de compilar...
python -c "import sys; sys.path.insert(0,'build_vendor'); import audioop; import pydub; import numpy; assert audioop.rms(b'\x01\x00' * 8, 2) == 1; print('Dependencias de audio OK')"
if errorlevel 1 (
    echo ERRO: audioop, pydub ou numpy nao podem ser usados neste Python.
    echo Execute python -m pip install -r requirements.txt e tente novamente.
    pause
    exit /b 1
)

python write_version_info.py
for /f %%v in ('python -c "from app_version import APP_VERSION; print(APP_VERSION)"') do set "DUBLASKIZON_VERSION=%%v"
python -m PyInstaller --paths build_vendor --hidden-import pydub --hidden-import audioop --hidden-import numpy --version-file version_info.txt --hidden-import app_version --hidden-import transcription_scene_editor --hidden-import theme_web_sources --hidden-import theme_research --hidden-import api_configuration --hidden-import api_settings_ui --hidden-import translation_output --hidden-import semantic_review --hidden-import translation_context --hidden-import transcription_tab --hidden-import transcription_backend --hidden-import review_memory_ui --hidden-import background_audio --hidden-import project_trash --hidden-import audio_versions --hidden-import repetition_prosody --onefile --windowed --clean --noconfirm --name "Dublaskizon_Portatil V%DUBLASKIZON_VERSION%" --icon "Dublaskizon.ico" --exclude-module scipy --exclude-module librosa --exclude-module sklearn --exclude-module numba --exclude-module llvmlite --exclude-module qwen_tts --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module transformers --exclude-module diffusers --exclude-module gradio --exclude-module pandas --exclude-module pyarrow --exclude-module matplotlib --exclude-module bitsandbytes --hidden-import fish_backend --hidden-import warm_inference --hidden-import speech_completeness --hidden-import voice_reference --hidden-import qwen_backend --hidden-import native_emotions --hidden-import emotional_speech --hidden-import text_to_speech_tab --hidden-import audio_frequency_separator_tab --hidden-import batch_tab --hidden-import review_tab --hidden-import duration_converter_tab --hidden-import format_converter_tab --hidden-import video_converter_tab --hidden-import video_preview --hidden-import video_audio_swap_tab --hidden-import wem_filter_tab --hidden-import voice_clone_tab --hidden-import personalized_dubbing_tab --hidden-import audio_clone_preprocessor --hidden-import main --hidden-import audio_player --hidden-import audio_clip_timeline --hidden-import scene_parts --hidden-import find_panel --hidden-import dependency_setup --hidden-import generation_progress --hidden-import f5_backend --hidden-import directml_backend --hidden-import audio_translation --hidden-import voice_character --hidden-import ui_theme --hidden-import i18n --hidden-import tkinterdnd2 --collect-all tkinterdnd2 --add-data "emotional_voices;emotional_voices" --add-data "Dublaskizon.ico;." --add-data "Dublaskizon_TUTORIAL.pdf;." Dublaskizon.py
if errorlevel 1 (
    echo ERRO: a compilacao do EXE portatil falhou.
    pause
    exit /b 1
)

echo.
echo [3/3] Conferindo o resultado...
if not exist "dist\Dublaskizon_Portatil V%DUBLASKIZON_VERSION%.exe" (
    echo ERRO: o EXE nao foi encontrado na pasta dist.
    pause
    exit /b 1
)
powershell -NoProfile -Command "$p=Get-Item -LiteralPath 'dist\Dublaskizon_Portatil V%DUBLASKIZON_VERSION%.exe'; Write-Host ('Tamanho do EXE: {0:N1} MB' -f ($p.Length/1MB)); if($p.Length -gt 125829120){exit 2}"
if errorlevel 1 (
    echo ERRO: o EXE ultrapassou 120 MB. O build incorporou bibliotecas externas indevidas e foi rejeitado.
    pause
    exit /b 1
)
python verify_frozen_build.py "dist\Dublaskizon_Portatil V%DUBLASKIZON_VERSION%.exe"
if errorlevel 1 (
    echo ERRO: a auditoria interna do EXE encontrou modulo ausente ou biblioteca indevida.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo BUILD PORTATIL CONCLUIDO
echo ================================================================
echo EXE criado em:
echo %~dp0dist\Dublaskizon_Portatil V%DUBLASKIZON_VERSION%.exe
echo.
echo Esse EXE pode ser levado para outro Windows sem Python instalado.
echo No primeiro uso, clique em BAIXAR / PREPARAR FERRAMENTAS para
 echo obter FFmpeg, FFprobe, FFplay e SoX fora do EXE, quando necessario.
echo.
pause
endlocal







