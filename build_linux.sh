#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec > >(tee build-linux.log) 2>&1
trap 'printf "\nFALHA na linha %s. Consulte: %s/build-linux.log\n" "$LINENO" "$PWD" >&2' ERR

PYTHON_BIN="${PYTHON_BIN:-python3}"
APPIMAGE_TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
command -v "$PYTHON_BIN" >/dev/null || fail "python3 não encontrado. Instale Python 3.12/3.13, python3-venv e python3-tk."
command -v ffmpeg >/dev/null || fail "FFmpeg não encontrado. Instale ffmpeg antes da compilação."
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] not in ((3,12),(3,13)):
    raise SystemExit('Use Python 3.12 ou 3.13 para gerar o pacote Linux.')
import tkinter
print('Python/Tk:',sys.version.split()[0],tkinter.TkVersion)
PY

printf '[1/5] Criando ambiente de compilação isolado...\n'
"$PYTHON_BIN" -m venv .build-linux-venv
BUILD_PY="$PWD/.build-linux-venv/bin/python"
"$BUILD_PY" -m pip install --upgrade --index-url https://pypi.org/simple pip
"$BUILD_PY" -m pip install --index-url https://pypi.org/simple -r requirements-build-linux.txt

printf '[2/5] Gerando executável Linux portátil com PyInstaller...\n'
rm -rf build/linux dist/Dublaskizon_Linux Dublaskizon.AppDir dist/Dublaskizon-x86_64.AppImage
"$BUILD_PY" -m PyInstaller --onedir --windowed --clean --noconfirm \
  --exclude-module qwen_tts --exclude-module torch --exclude-module transformers \
  --name Dublaskizon_Linux --distpath dist --workpath build/linux \
  --hidden-import fish_backend --hidden-import qwen_backend --hidden-import native_emotions --hidden-import emotional_speech --hidden-import text_to_speech_tab --hidden-import batch_tab --hidden-import review_tab --hidden-import personalized_dubbing_tab \
  --hidden-import duration_converter_tab --hidden-import format_converter_tab --hidden-import video_converter_tab \
  --hidden-import video_preview --hidden-import video_audio_swap_tab --hidden-import wem_filter_tab \
  --hidden-import voice_clone_tab --hidden-import audio_clone_preprocessor --hidden-import audio_player \
  --hidden-import audio_clip_timeline --hidden-import scene_parts --hidden-import find_panel \
  --hidden-import dependency_setup --hidden-import generation_progress --hidden-import f5_backend --hidden-import directml_backend \
  --hidden-import audio_translation --hidden-import ui_theme --hidden-import i18n \
  --hidden-import tkinterdnd2 --collect-all tkinterdnd2 \
  --add-data "emotional_voices:emotional_voices" --add-data "Dublaskizon.ico:." --add-data "Dublaskizon.svg:." \
  --add-data "Dublaskizon_TUTORIAL.pdf:." --add-data "LEIA-ME-LINUX.md:." Dublaskizon.py
test -x dist/Dublaskizon_Linux/Dublaskizon_Linux || fail "PyInstaller não criou o executável esperado."

printf '[3/5] Montando estrutura AppDir...\n'
mkdir -p Dublaskizon.AppDir/usr/bin
cp -a dist/Dublaskizon_Linux Dublaskizon.AppDir/usr/bin/Dublaskizon
cp Dublaskizon.desktop Dublaskizon.AppDir/
cp Dublaskizon.svg Dublaskizon.AppDir/
cat > Dublaskizon.AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export DUBLASKIZON_APP_DIR="${DUBLASKIZON_APP_DIR:-$PWD}"
exec "$HERE/usr/bin/Dublaskizon/Dublaskizon_Linux" "$@"
EOF
chmod +x Dublaskizon.AppDir/AppRun
ln -sfn Dublaskizon.svg Dublaskizon.AppDir/.DirIcon

printf '[4/5] Obtendo appimagetool oficial do projeto AppImage...\n'
mkdir -p .build-tools
if [ ! -s .build-tools/appimagetool-x86_64.AppImage ]; then
  command -v curl >/dev/null || fail "curl não encontrado."
  curl --fail --location --retry 3 "$APPIMAGE_TOOL_URL" -o .build-tools/appimagetool-x86_64.AppImage
fi
chmod +x .build-tools/appimagetool-x86_64.AppImage

printf '[5/5] Gerando e conferindo AppImage...\n'
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 .build-tools/appimagetool-x86_64.AppImage Dublaskizon.AppDir dist/Dublaskizon-x86_64.AppImage
chmod +x dist/Dublaskizon-x86_64.AppImage
test -s dist/Dublaskizon-x86_64.AppImage || fail "AppImage não foi criado."
printf '\nCONCLUÍDO:\n  %s\n  %s\n' "$PWD/dist/Dublaskizon-x86_64.AppImage" "$PWD/dist/Dublaskizon_Linux/Dublaskizon_Linux"
