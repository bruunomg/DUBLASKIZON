@echo off
setlocal
chcp 65001 >nul

echo ================================================================
echo Dependências da ferramenta REDIMENSIONAR ÁUDIO PARA CLONAR
echo ================================================================
python -m pip install --upgrade pydub ffmpeg-python numpy scipy
if errorlevel 1 (
    echo ERRO: não foi possível instalar as dependências Python.
    pause
    exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo AVISO: FFmpeg não foi encontrado no PATH.
    echo Instale FFmpeg e adicione a pasta bin ao PATH do Windows.
) else (
    echo FFmpeg encontrado.
)

where ffprobe >nul 2>nul
if errorlevel 1 (
    echo AVISO: FFprobe não foi encontrado no PATH.
) else (
    echo FFprobe encontrado.
)

echo.
echo Dependências Python instaladas. Pressione uma tecla para sair.
pause >nul
