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
python -m pip install --upgrade --index-url https://pypi.org/simple -r requirements.txt
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar o PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/3] Gerando Dublaskizon.exe...
python -m PyInstaller --onefile --windowed --clean --noconfirm --name Dublaskizon --icon "Dublaskizon.ico" --hidden-import batch_tab --hidden-import review_tab --hidden-import duration_converter_tab --hidden-import format_converter_tab --hidden-import video_converter_tab --hidden-import video_preview --hidden-import video_audio_swap_tab --hidden-import wem_filter_tab --hidden-import voice_clone_tab --hidden-import audio_clone_preprocessor --hidden-import audio_player --hidden-import audio_clip_timeline --hidden-import scene_parts --hidden-import find_panel --hidden-import dependency_setup --hidden-import generation_progress --hidden-import f5_backend --hidden-import audio_translation --hidden-import ui_theme --hidden-import i18n --hidden-import tkinterdnd2 --add-data "Dublaskizon.ico;." --add-data "Dublaskizon_TUTORIAL.pdf;." Dublaskizon.py
if errorlevel 1 (
    echo ERRO: a compilacao falhou.
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
