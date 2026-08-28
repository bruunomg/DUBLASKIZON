from pathlib import Path
import os
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE
BUILD = PROJECT / "unified_build" if (PROJECT / "unified_build").is_dir() else PROJECT
sys.path.insert(0, str(HERE))
os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(PROJECT)

import Dublaskizon
import batch_tab
import review_tab
import format_converter_tab

with tempfile.TemporaryDirectory() as cache_raw:
    cache_root = Path(cache_raw)
    (cache_root / "models--acme--voice").mkdir(parents=True)
    previous_cache = os.environ.get("HUGGINGFACE_HUB_CACHE")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(cache_root)
    try:
        assert "acme/voice" in batch_tab.cached_model_ids()
        assert any(model_id == "acme/voice" for _label, model_id in batch_tab.discover_model_choices())
    finally:
        if previous_cache is None:
            os.environ.pop("HUGGINGFACE_HUB_CACHE", None)
        else:
            os.environ["HUGGINGFACE_HUB_CACHE"] = previous_cache

with tempfile.TemporaryDirectory() as raw:
    selected = Path(raw) / "PROJETO_TESTE"
    batch_tab.configure_project_root(selected)
    review_tab.configure_project_root(selected)
    assert batch_tab.ROOT == selected.resolve()
    assert review_tab.ROOT == selected.resolve()
    other_dir = selected / "OUTRAS TRADUÇÕES"
    other_dir.mkdir(parents=True)
    english_dir = other_dir / "INGLES"
    spanish_dir = other_dir / "ESPANHOL"
    english_dir.mkdir()
    spanish_dir.mkdir()
    matching = english_dir / "cena_001.txt"
    matching.write_text("Texto alternativo da cena", encoding="utf-8")
    mapping = review_tab.other_translation_text_files(english_dir)
    assert mapping["cena_001"] == matching
    assert [path.name for path in review_tab.other_translation_folders(other_dir)] == ["ESPANHOL", "INGLES"]
    assert review_tab.DEFAULT_CONFIG["other_translation_dir"] == ""
    assert review_tab.DEFAULT_CONFIG["other_translation_root_dir"] == ""

assert "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO" in Dublaskizon.PROJECT_FOLDERS
assert "OUTRAS TRADUÇÕES" in Dublaskizon.PROJECT_FOLDERS
assert "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO" in review_tab.TRANSCRIBED_TRANSLATED_TEXT_DIR.name
assert review_tab.OTHER_TRANSLATIONS_DIR.name == "OUTRAS TRADUÇÕES"
assert Dublaskizon.TUTORIAL_FILENAME == "Dublaskizon_TUTORIAL.pdf"
assert (BUILD / "Dublaskizon.ico").is_file()
assert (BUILD / "i18n.py").is_file()
build_source = (BUILD / "build_exe.bat").read_text(encoding="utf-8")
portable_build_source = (BUILD / "build_exe_portatil_sem_python.bat").read_text(encoding="utf-8")
assert '--icon "Dublaskizon.ico"' in build_source
assert "Dublaskizon_Portatil" in portable_build_source
assert "--collect-all tkinterdnd2" in portable_build_source
assert "--hidden-import i18n" in portable_build_source
assert "build_exe_portatil_sem_python.bat" not in build_source
assert Dublaskizon.INTERFACE_CONFIG_PATH.name == "Dublaskizon_interface.json"
assert set(("claro", "escuro")) <= set(Dublaskizon.THEMES)
main_source = (HERE / "Dublaskizon.py").read_text(encoding="utf-8")
assert "change_scale(-5)" in main_source and "change_scale(5)" in main_source
assert "APARÊNCIA: CLARA" in main_source and "def toggle_theme" in main_source
assert "COMANDOS" in main_source
assert "ATUALIZAR TELA" in main_source
assert "language_combo" in main_source
assert "on_language_selected" in main_source
assert "def refresh_screen" in main_source
assert "help_button" in main_source
assert "ContextHelpManager" in main_source
assert "ABRIR PASSO A PASSO DA ABA ATUAL" in (HERE / "i18n.py").read_text(encoding="utf-8")
assert "TerminalApp" in main_source
assert "if create_structure:" in main_source
batch_source = (HERE / "batch_tab.py").read_text(encoding="utf-8")
assert "#F8FAFC" in batch_source and "neutral_fgs" in batch_source
assert "alguns Labels permaneciam quase brancos" in batch_source
assert "light_texts" in main_source
assert "help_manager.refresh" in main_source
app_init_source = main_source[main_source.index("class DublaskizonApp"):main_source.index("    def load_scale_percent")]
assert "self.ensure_project_structure()" not in app_init_source
assert main_source.index('text="CONVERTER FORMATOS"') < main_source.index('text="COMANDOS"')
assert 'for path in (INTERFACE_CONFIG_PATH,):' in main_source
assert main_source.count('for path in (INTERFACE_CONFIG_PATH,)') == 2
batch_source = (HERE / "batch_tab.py").read_text(encoding="utf-8")
assert "root_backgrounds" in batch_source
assert "surface_backgrounds" in batch_source
assert "footer_backgrounds" in batch_source
assert "DEFAULT_MODEL_CHOICES" in batch_source
assert "model_cache_roots" in batch_source
assert "cached_model_ids" in batch_source
assert "discover_model_choices" in batch_source
assert "refresh_model_choices" in batch_source
review_source = (HERE / "review_tab.py").read_text(encoding="utf-8")
assert "REVISIONS_DIR.mkdir(parents=True, exist_ok=True)\n        self.config" not in review_source
assert "save_json(CONFIG_FILE, self.config)" not in review_source[review_source.index("    def __init__"):review_source.index("    def build_ui")]
assert "refresh_other_translation_folder_buttons" in review_source
assert "select_other_translation_subfolder" in review_source
assert "self.other_translation_folders_bar" in review_source
assert 'text="SELECIONAR PASTA"' not in review_source
assert 'self.text_box = Text(text_frame, height=8' in review_source
assert 'background="#E8F5E9"' in review_source
assert 'self.other_translation_box = Text(other_panel, height=8' in review_source
assert 'self.other_translation_box = Text(other_panel, height=8, wrap="word", state="disabled", font=("Segoe UI", 11)' in review_source
assert 'self.transcribed_text_box = Text(transcribed_text_frame, height=8' in review_source
assert 'self.original_text_box = Text(original_text_frame, height=8' in review_source
assert 'self.text_columns.add(left_column, weight=2)' in review_source
assert 'self.text_columns.add(right_column, weight=1)' in review_source
assert 'self.script_pane' not in review_source
assert 'self.reference_pane' not in review_source
assert 'background="#E8F5E9"' in review_source
assert 'self.other_translation_status_label = ttk.Label(other_meta' in review_source
assert review_source.index('self.other_translation_check = ttk.Checkbutton(other_meta') < review_source.index('self.other_translation_box = Text(other_panel')
assert review_source.index('self.other_translation_status_label = ttk.Label(other_meta') < review_source.index('self.other_translation_box = Text(other_panel')
assert 'textvariable=self.other_translation_var' not in review_source
assert "max(25" in main_source and "min(200" in main_source
assert "scale_slider" not in main_source
assert (BUILD / Dublaskizon.TUTORIAL_FILENAME).is_file()
assert "Ir para revisão" not in main_source
assert "Ir para clonagem + dublagem" not in main_source
assert "duration_converter_tab" in main_source
assert "voice_clone_tab" in main_source
assert "REDIMENSIONAR ÁUDIO PARA CLONAR" in main_source
assert (HERE / "voice_clone_tab.py").is_file()
assert (HERE / "audio_clone_preprocessor.py").is_file()
assert (HERE / "main.py").is_file()
assert (HERE / "requirements_voice_clone.txt").is_file()
assert (HERE / "INSTALAR_DEPENDENCIAS_CLONAGEM.bat").is_file()
assert "voice_clone_tab" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
assert "audio_clone_preprocessor" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
converter_source = (HERE / "duration_converter_tab.py").read_text(encoding="utf-8")
assert '"ÁUDIOS ORIGINAIS"' in converter_source
assert '"ÁUDIOS DUBLADOS"' in converter_source
assert "BAIXAR / PREPARAR FERRAMENTAS" in converter_source
assert "TOOLS_HELP_TEXT" in converter_source
assert "tools_help_button" in converter_source
assert "silence_controls" in converter_source
assert "padx=(0, 38)" in converter_source
assert "FFMPEG_WINDOWS_URL" in converter_source
assert "SOX_WINDOWS_URL" in converter_source
assert "CONVERTER DURAÇÃO" in main_source
assert "load_converter_from_review" in main_source
assert "load_converter_from_batch" in main_source
assert "duration_converter_tab" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
assert "audio_player" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
assert "format_converter_tab" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
assert "i18n" in (HERE / "build_exe.bat").read_text(encoding="utf-8") or "import i18n" in main_source
assert "Nenhum par de wav + txt encontrado." in (HERE / "i18n.py").read_text(encoding="utf-8")
assert "Conversão de formato: aguardando" in (HERE / "i18n.py").read_text(encoding="utf-8")
assert (HERE / "audio_player.py").is_file()
assert (HERE / "format_converter_tab.py").is_file()
audio_player_source = (HERE / "audio_player.py").read_text(encoding="utf-8")
assert "AudioPlayerManager" in audio_player_source
assert "▶  INICIAR" in audio_player_source
assert "def start_pending" in audio_player_source
assert "pending_paths" in audio_player_source
assert "previous_button" in audio_player_source
assert "next_button" in audio_player_source
assert "def navigate" in audio_player_source
format_source = (HERE / "format_converter_tab.py").read_text(encoding="utf-8")
assert "class FormatConverterApp" in format_source
assert "CONVERTER FORMATOS DE ÁUDIO" in format_source
assert "CONVERTER FORMATOS" in format_source
assert "FORMAT_CHOICES" in format_source
assert "BAIXAR / PREPARAR FERRAMENTAS" in format_source
assert "TOOLS_HELP_TEXT" in format_source
assert "tools_help_button" in format_source
assert "load_review_button" in format_source
assert "load_batch_button" in format_source
assert "def load_from_review" in format_source
assert "def load_from_batch" in format_source
assert "def start_tool_alert" in format_source
duration_source = (HERE / "duration_converter_tab.py").read_text(encoding="utf-8")
assert "self.missing_tools()" in duration_source
assert "def start_tool_alert" in format_source
assert "tkinterdnd2" in (HERE / "build_exe.bat").read_text(encoding="utf-8")
print("project_flow_ok")
