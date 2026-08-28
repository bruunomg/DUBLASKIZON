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
    echo Instale Python 3.12 e marque "Add Python to PATH".
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
python -m pip install --upgrade pyinstaller tkinterdnd2 pydub ffmpeg-python numpy
if errorlevel 1 (
    echo ERRO: nao foi possivel instalar PyInstaller/tkinterdnd2.
    pause
    exit /b 1
)

echo.
echo [2/3] Gerando o EXE com Python incorporado...
python -m PyInstaller --onefile --windowed --clean --noconfirm --name Dublaskizon_Portatil --icon "Dublaskizon.ico" --hidden-import batch_tab --hidden-import review_tab --hidden-import duration_converter_tab --hidden-import format_converter_tab --hidden-import wem_filter_tab --hidden-import voice_clone_tab --hidden-import audio_clone_preprocessor --hidden-import main --hidden-import audio_player --hidden-import ui_theme --hidden-import i18n --hidden-import tkinterdnd2 --collect-all tkinterdnd2 --add-data "Dublaskizon.ico;." --add-data "Dublaskizon_TUTORIAL.pdf;." Dublaskizon.py
if errorlevel 1 (
    echo ERRO: a compilacao do EXE portatil falhou.
    pause
    exit /b 1
)

echo.
echo [3/3] Conferindo o resultado...
if not exist "dist\Dublaskizon_Portatil.exe" (
    echo ERRO: o EXE nao foi encontrado na pasta dist.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo BUILD PORTATIL CONCLUIDO
echo ================================================================
echo EXE criado em:
echo %~dp0dist\Dublaskizon_Portatil.exe
echo.
echo Esse EXE pode ser levado para outro Windows sem Python instalado.
echo No primeiro uso, clique em BAIXAR / PREPARAR FERRAMENTAS para
 echo obter FFmpeg, FFprobe, FFplay e SoX fora do EXE, quando necessario.
echo.
pause
endlocal
