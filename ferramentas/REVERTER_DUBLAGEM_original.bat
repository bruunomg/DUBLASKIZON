@echo off
setlocal enableDelayedExpansion

:: --- CONFIGURAÇÕES ---
set "MOD_PATH=%~dp0"
set "FFMPEG=%MOD_PATH%ferramentas\ffmpeg.exe"
set "BACKUP_DIR=%MOD_PATH%backup_AUDIOS-dos-videos"
set "TEMP_DIR=%MOD_PATH%temp"

:: CAMINHO ONDE ESTÃO OS VÍDEOS
set "VIDEO_DIR=%MOD_PATH%Videos Originais"

if not exist "%BACKUP_DIR%" (
    echo ERRO: Pasta de backup nao encontrada. Nada para restaurar.
    pause
    exit /b
)

if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

echo =====================================================
echo    REVERSOR DE DUBLAGEM - MOHAB (CORRECAO V4)
echo =====================================================
echo.
echo Diretorio de Videos: "%VIDEO_DIR%"
echo.

if not exist "%VIDEO_DIR%" (
    echo [!] AVISO: O diretorio de videos nao foi encontrado.
    set /p VIDEO_DIR="Por favor, cole o caminho da pasta onde estao os videos (.mov): "
)

for %%f in ("%BACKUP_DIR%\*.wav") do (
    set "NAME=%%~nf"
    set "AUDIO_BACKUP=%%f"
    
    set "VIDEO_TARGET="
    set "EXT="
    if exist "%VIDEO_DIR%\!NAME!.mov" (
        set "VIDEO_TARGET=%VIDEO_DIR%\!NAME!.mov"
        set "EXT=.mov"
    ) else if exist "%VIDEO_DIR%\!NAME!.mp4" (
        set "VIDEO_TARGET=%VIDEO_DIR%\!NAME!.mp4"
        set "EXT=.mp4"
    )

    if defined VIDEO_TARGET (
        echo [+] Restaurando original: !NAME!!EXT!
        
        :: Injetar o audio original de volta (Usando extensao correta no temporario)
        "%FFMPEG%" -i "!VIDEO_TARGET!" -i "!AUDIO_BACKUP!" -c:v copy -map 0:v:0 -map 1:a:0 "%TEMP_DIR%\!NAME!!EXT!" -y > nul 2>&1

        if exist "%TEMP_DIR%\!NAME!!EXT!" (
            move /y "%TEMP_DIR%\!NAME!!EXT!" "!VIDEO_TARGET!" > nul
            echo     [OK] Audio original restaurado.
        ) else (
            echo     [ERRO] Falha ao restaurar !NAME!.
        )
    ) else (
        echo [!] Ignorado: !NAME! (Video nao encontrado na pasta do jogo)
    )
)

echo.
echo Processo Concluido.
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
pause
