@echo off
setlocal enableDelayedExpansion

:: --- CONFIGURAÇÕES ---
set "MOD_PATH=%~dp0"
set "FFMPEG=%MOD_PATH%ferramentas\ffmpeg.exe"
set "AUDIO_DIR=%MOD_PATH%audios"
set "BACKUP_DIR=%MOD_PATH%backup_AUDIOS-dos-videos"
set "TEMP_DIR=%MOD_PATH%temp"

:: CAMINHO ONDE ESTÃO OS VÍDEOS
set "VIDEO_DIR=%MOD_PATH%Videos Originais"

if not exist "%FFMPEG%" (
    echo ERRO: ffmpeg.exe nao encontrado em ferramentas.
    pause
    exit /b
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"
if not exist "%VIDEO_DIR%" mkdir "%VIDEO_DIR%"

echo =====================================================
echo    INJETOR DE DUBLAGEM - MOHAB (CORRECAO V4)
echo =====================================================
echo.
echo Diretorio de Videos: "%VIDEO_DIR%"
echo.

if not exist "%VIDEO_DIR%" (
    echo [!] AVISO: O diretorio de videos acima nao foi encontrado.
    set /p VIDEO_DIR="Por favor, cole o caminho da pasta onde estao os videos (.mov): "
)

for %%f in ("%AUDIO_DIR%\*.wav") do (
    set "NAME=%%~nf"
    set "AUDIO_IN=%%f"
    
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
        echo [+] Processando: !NAME!!EXT!
        
        :: Backup do audio original
        if not exist "%BACKUP_DIR%\!NAME!.wav" (
            echo     - Fazendo backup do audio original...
            "%FFMPEG%" -i "!VIDEO_TARGET!" -map 0:a:0 -c:a pcm_s16le "%BACKUP_DIR%\!NAME!.wav" -y > nul 2>&1
        )

        :: Criar video novo (Usando a extensao correta para o temporario)
        echo     - Injetando nova dublagem...
        "%FFMPEG%" -i "!VIDEO_TARGET!" -i "!AUDIO_IN!" -c:v copy -map 0:v:0 -map 1:a:0 "%TEMP_DIR%\!NAME!!EXT!" -y

        if exist "%TEMP_DIR%\!NAME!!EXT!" (
            move /y "%TEMP_DIR%\!NAME!!EXT!" "!VIDEO_TARGET!" > nul
            echo     [OK] Dublagem aplicada com sucesso.
        ) else (
            echo.
            echo [ERRO] Falha ao processar !NAME!. 
            echo O FFmpeg nao conseguiu criar o arquivo. Verifique se o video nao esta aberto em outro programa.
        )
    ) else (
        echo [!] Ignorado: !NAME! (Video original nao encontrado na pasta do jogo)
    )
    echo.
)

echo.
echo Processo Concluido.
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
pause
