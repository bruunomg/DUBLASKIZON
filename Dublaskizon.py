#!/usr/bin/env python3
"""Dublaskizon — interface única portátil para dublagem e revisão."""

from __future__ import annotations

import json
import os
import queue
from datetime import datetime
import shlex
import subprocess
import sys
import threading
import shutil
import webbrowser
from pathlib import Path

try:
    from ui_theme import BUTTON_PALETTES, apply_button_style, apply_button_style_to_tree, button_style, configure_ttk_button_styles, surface_color
except ImportError:
    from .ui_theme import BUTTON_PALETTES, apply_button_style, apply_button_style_to_tree, button_style, configure_ttk_button_styles, surface_color


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
TUTORIAL_FILENAME = "Dublaskizon_TUTORIAL.pdf"
TUTORIAL_PATH = RESOURCE_DIR / TUTORIAL_FILENAME
ICON_FILENAME = "Dublaskizon.ico"
ICON_PATH = RESOURCE_DIR / ICON_FILENAME
INTERFACE_CONFIG_PATH = APP_DIR / "Dublaskizon_interface.json"
BASE_WINDOW_WIDTH = 1440
BASE_WINDOW_HEIGHT = 980
BASE_MIN_WIDTH = 1160
BASE_MIN_HEIGHT = 760
PROJECT_FOLDERS = ("WAV ORIGINAIS", "TXT TEXTO PORTUGUES", "TXT TEXTO ORIGINAL", "TXT TEXTO do WAV TRANSCRITO e TRADUZIDO", "OUTRAS TRADUÇÕES", "dublado", "dublados personalizados", "MODELOS DE VOZ PERSONALIZADOS", "revisoes", "REDIMENSIONAR ÁUDIO PARA CLONAR")
THEMES = {
    "claro": {
        "mode": "claro", "root": "#F5F6FA", "surface": "#FFFFFF", "panel": "#FFFFFF", "text": "#1F2937",
        "muted": "#64748B", "input": "#FFFFFF", "input_text": "#1F2937", "border": "#CBD5E1",
        "header": "#172033", "tabs": "#E2E8F0", "footer": "#EEF2F7", "select": "#DBEAFE",
        "buttons": BUTTON_PALETTES["claro"],
    },
    "medio": {
        "mode": "medio", "root": "#334155", "surface": "#3F4D5F", "panel": "#475569", "text": "#F8FAFC",
        "muted": "#D6DEE8", "input": "#526174", "input_text": "#FFFFFF", "border": "#718096",
        "header": "#263445", "tabs": "#44546A", "footer": "#3B4A5E", "select": "#2563EB",
        "buttons": BUTTON_PALETTES["medio"],
    },
    "escuro": {
        "mode": "escuro", "root": "#202938", "surface": "#2A3546", "panel": "#314055", "text": "#F8FAFC",
        "muted": "#CBD5E1", "input": "#35445A", "input_text": "#FFFFFF", "border": "#52627A",
        "header": "#182230", "tabs": "#2A374A", "footer": "#253246", "select": "#2563EB",
        "buttons": BUTTON_PALETTES["escuro"],
    },
}
# DUBLASKIZON_PROJECT_ROOT só é definido quando o usuário escolhe uma pasta ou quando
# um processo externo realmente o fornece. Não o preencher com APP_DIR aqui: em um
# build PyInstaller instalado em ...\\dist isso faria a saída cair indevidamente em dist.
os.environ.setdefault("DUBLASKIZON_APP_DIR", str(APP_DIR))


def configure_windows_app_identity() -> None:
    """Evita que o Windows agrupe a janela como um aplicativo genérico do Tk."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dublaskizon.Software.Dublagem")
    except Exception:
        pass


def apply_window_icon(root) -> None:
    """Aplica o ICO à janela e, no Windows, também ao botão da barra de tarefas."""
    candidates = (ICON_PATH, APP_DIR / ICON_FILENAME, Path(__file__).resolve().parent / ICON_FILENAME)
    icon_file = next((path for path in candidates if path.is_file()), None)
    if icon_file is None:
        return
    try:
        root.iconbitmap(default=str(icon_file))
    except Exception:
        try:
            root.wm_iconbitmap(str(icon_file))
        except Exception:
            pass

try:
    from tkinter import Tk, filedialog, messagebox, StringVar, simpledialog, ttk
    import tkinter as tk
    from tkinter import font as tkfont
except ModuleNotFoundError as exc:
    Tk = None  # type: ignore
    filedialog = None  # type: ignore
    messagebox = None  # type: ignore
    StringVar = None  # type: ignore
    simpledialog = None  # type: ignore
    ttk = None  # type: ignore
    tk = None  # type: ignore
    tkfont = None  # type: ignore
    TK_IMPORT_ERROR = str(exc)

try:
    import i18n  # type: ignore
except ImportError:
    from . import i18n  # type: ignore

if messagebox is not None:
    _raw_messagebox = messagebox

    class _LocalizedMessageBox:
        def __getattr__(self, name):
            method = getattr(_raw_messagebox, name)
            if name not in {"showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askretrycancel"}:
                return method
            def localized(title, message, *args, **kwargs):
                return method(i18n.tr(title), i18n.tr(message), *args, **kwargs)
            return localized

    messagebox = _LocalizedMessageBox()

try:
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore
    except ImportError:
        TkinterDnD = None  # type: ignore
except Exception:
    TkinterDnD = None  # type: ignore

try:
    import batch_tab  # type: ignore
    import review_tab  # type: ignore
    import duration_converter_tab  # type: ignore
    import format_converter_tab  # type: ignore
    import wem_filter_tab  # type: ignore
    import voice_clone_tab  # type: ignore
    import personalized_dubbing_tab  # type: ignore
    import video_converter_tab
    import video_audio_swap_tab
except ImportError:
    from . import batch_tab, review_tab, duration_converter_tab, format_converter_tab, wem_filter_tab, voice_clone_tab, personalized_dubbing_tab, video_converter_tab, video_audio_swap_tab


if tk is not None:
    class ScrollableFrame(tk.Frame):
        def __init__(self, parent, background="#F5F6FA"):
            super().__init__(parent, bg=background)
            self.canvas = tk.Canvas(self, bg=background, highlightthickness=0, borderwidth=0)
            self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self._on_scroll)
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar_visible = False
            self.inner = tk.Frame(self.canvas, bg=background)
            self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
            self.inner.bind("<Configure>", self._on_inner_configure)
            self.canvas.bind("<Configure>", self._on_canvas_configure)
            self.canvas.bind("<Enter>", self._bind_mousewheel)
            self.canvas.bind("<Leave>", self._unbind_mousewheel)

        def _on_inner_configure(self, _event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.after_idle(self._update_scrollbar)

        def _on_canvas_configure(self, event):
            self.canvas.itemconfigure(self.window_id, width=event.width)
            self.after_idle(self._update_scrollbar)

        def _on_scroll(self, first, last):
            if self.scrollbar_visible:
                self.scrollbar.set(first, last)

        def _update_scrollbar(self):
            try:
                if not self.winfo_exists():
                    return
                self.update_idletasks()
                bbox = self.canvas.bbox("all")
            except tk.TclError:
                return
            if not bbox:
                return
            content_height = max(0, bbox[3] - bbox[1])
            viewport_height = max(1, self.canvas.winfo_height())
            should_show = content_height > viewport_height + 18
            if should_show and not self.scrollbar_visible:
                self.scrollbar.pack(side="right", fill="y")
                self.scrollbar_visible = True
                self.after_idle(self._update_scrollbar)
            elif not should_show and self.scrollbar_visible:
                self.scrollbar.pack_forget()
                self.scrollbar_visible = False
                self.canvas.yview_moveto(0)
                self.after_idle(self._update_scrollbar)
            if should_show:
                first, last = self.canvas.yview()
                self.scrollbar.set(first, last)

        def set_background(self, background):
            try:
                self.configure(bg=background)
                self.canvas.configure(bg=background)
                self.inner.configure(bg=background)
            except tk.TclError:
                pass

        def refresh_layout(self):
            try:
                if not self.winfo_exists():
                    return
                self.update_idletasks()
                self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 0, 0))
                self._update_scrollbar()
                self.after(80, self._update_scrollbar)
            except tk.TclError:
                return

        def _bind_mousewheel(self, _event=None):
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        def _unbind_mousewheel(self, _event=None):
            self.canvas.unbind_all("<MouseWheel>")

        def _on_mousewheel(self, event):
            if not self.scrollbar_visible:
                return "break"
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
else:
    class ScrollableFrame:
        pass


class TerminalApp:
    """Painel portátil de comandos úteis para diagnosticar e executar o OmniVoice."""

    def __init__(self, parent, root_window, theme, global_log_queue=None, central_log_callback=None):
        self.parent = parent
        self.root = root_window
        self.theme = theme
        self.global_log_queue = global_log_queue or queue.Queue()
        self.central_log_callback = central_log_callback
        self.process = None
        self.worker_thread = None
        self.output_queue = queue.Queue()
        self.command_var = tk.StringVar(value="python -m omnivoice.cli.infer --help")
        self.build_ui()
        self.refresh_for_project()
        self.root.after(100, self.poll_output)

    def build_ui(self):
        theme = self.theme
        self.parent.configure(bg=theme["root"])
        title = tk.Label(self.parent, text="COMANDOS DO TERMINAL", bg=theme["root"], fg=theme["text"], font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", padx=18, pady=(16, 4))
        tk.Label(self.parent, text="Execute diagnósticos do Python, OmniVoice e ambiente sem abrir uma janela externa.", bg=theme["root"], fg=theme["muted"], font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 12))

        project_box = tk.Frame(self.parent, bg=theme["surface"], bd=1, relief="solid")
        project_box.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(project_box, text="Projeto ativo", bg=theme["surface"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        self.project_label = tk.Label(project_box, text="", bg=theme["surface"], fg=theme["muted"], anchor="w", justify="left", font=("Consolas", 10))
        self.project_label.pack(fill="x", padx=12, pady=(0, 10))

        command_box = tk.Frame(self.parent, bg=theme["surface"], bd=1, relief="solid")
        command_box.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(command_box, text="Comando", bg=theme["surface"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 3))
        row = tk.Frame(command_box, bg=theme["surface"])
        row.pack(fill="x", padx=12, pady=(0, 10))
        self.command_entry = tk.Entry(row, textvariable=self.command_var, bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"], relief="solid", bd=1, font=("Consolas", 10))
        self.command_entry.pack(side="left", fill="x", expand=True)
        tk.Button(row, text="EXECUTAR", command=self.run_command, bg="#2563EB", activebackground="#1D4ED8", fg="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=5, cursor="hand2").pack(side="left", padx=(8, 0))
        tk.Button(row, text="LIMPAR", command=self.clear_output, bg="#64748B", activebackground="#475569", fg="white", relief="flat", padx=10, pady=5, cursor="hand2").pack(side="left", padx=(6, 0))

        presets = tk.Frame(self.parent, bg=theme["root"])
        presets.pack(fill="x", padx=18, pady=(0, 10))
        for label, command in (
            ("OmniVoice --help", "python -m omnivoice.cli.infer --help"),
            ("Python", "python --version"),
            ("OmniVoice instalado", "python -m pip show omnivoice"),
            ("Localizar OmniVoice", "where omnivoice-infer"),
        ):
            tk.Button(presets, text=label, command=lambda value=command: self.command_var.set(value), bg="#475569", activebackground="#334155", fg="white", relief="flat", padx=8, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))

        tk.Label(self.parent, text="Histórico global dos processos", bg=theme["root"], fg=theme["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18)
        global_frame = tk.Frame(self.parent, bg=theme["surface"], bd=1, relief="solid")
        global_frame.pack(fill="x", padx=18, pady=(4, 10))
        self.global_log_box = tk.Text(global_frame, height=8, wrap="word", state="disabled", bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"], selectbackground=theme["select"], selectforeground="#FFFFFF", font=("Consolas", 9), relief="flat", bd=0)
        global_scroll = ttk.Scrollbar(global_frame, orient="vertical", command=self.global_log_box.yview)
        self.global_log_box.configure(yscrollcommand=global_scroll.set)
        self.global_log_box.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        global_scroll.pack(side="right", fill="y", pady=8)

        tk.Label(self.parent, text="Saída do terminal", bg=theme["root"], fg=theme["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18)
        output_frame = tk.Frame(self.parent, bg=theme["surface"], bd=1, relief="solid")
        output_frame.pack(fill="both", expand=True, padx=18, pady=(4, 18))
        self.output_box = tk.Text(output_frame, wrap="word", state="disabled", bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"], font=("Consolas", 10), relief="flat", bd=0)
        output_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_box.yview)
        self.output_box.configure(yscrollcommand=output_scroll.set)
        self.output_box.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        output_scroll.pack(side="right", fill="y", pady=8)

    def refresh_for_project(self):
        if hasattr(self, "project_label"):
            self.project_label.configure(text=str(getattr(self.root, "project_root", APP_DIR)))

    def append_output(self, text):
        try:
            if not self.parent.winfo_exists() or not self.output_box.winfo_exists():
                return
            self.output_box.configure(state="normal")
            self.output_box.insert("end", text)
            self.output_box.see("end")
            self.output_box.configure(state="disabled")
        except tk.TclError:
            return

    def clear_output(self):
        for widget in (self.output_box, getattr(self, "global_log_box", None)):
            if widget is None:
                continue
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")
        try:
            while True:
                self.global_log_queue.get_nowait()
        except queue.Empty:
            pass

    def append_global_log(self, source, text, tag="normal"):
        try:
            if not self.parent.winfo_exists() or not self.global_log_box.winfo_exists():
                return
            stamp = datetime.now().strftime("%H:%M:%S")
            line = f"[{stamp}] [{source}] {str(text).rstrip()}\n"
            self.global_log_box.configure(state="normal")
            self.global_log_box.insert("end", line)
            self.global_log_box.see("end")
            self.global_log_box.configure(state="disabled")
        except tk.TclError:
            return

    def log_central(self, text, tag="normal", source="COMANDOS"):
        callback = self.central_log_callback
        if callable(callback):
            try:
                callback(source, str(text), tag)
            except Exception:
                pass

    def run_command(self):
        if self.process is not None and self.process.poll() is None:
            self.append_output("\n[AVISO] Já existe um comando em execução.\\n")
            return
        command_text = self.command_var.get().strip()
        if not command_text:
            return
        self.append_output(f"\\n$ {command_text}\\n")
        self.log_central(f"$ {command_text}", "info")
        self.worker_thread = threading.Thread(target=self._run_command, args=(command_text,), daemon=True)
        self.worker_thread.start()

    def _run_command(self, command_text):
        try:
            self.process = subprocess.Popen(command_text, shell=True, cwd=str(getattr(self.root, "project_root", APP_DIR)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, **batch_tab.hidden_process_kwargs())
            if self.process.stdout:
                for line in self.process.stdout:
                    self.output_queue.put(line)
                    self.log_central(line.rstrip(), "normal")
            code = self.process.wait()
            message = f"[processo terminou com código {code}]"
            self.output_queue.put(f"\\n{message}\\n")
            self.log_central(message, "ok" if code == 0 else "error")
        except Exception as exc:
            message = f"[ERRO] {exc}"
            self.output_queue.put(f"\\n{message}\\n")
            self.log_central(message, "error")
        finally:
            self.process = None

    def poll_output(self):
        try:
            if not self.parent.winfo_exists():
                return
            while True:
                self.append_global_log(*self.global_log_queue.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                self.append_output(self.output_queue.get_nowait())
        except queue.Empty:
            pass
        except tk.TclError:
            return
        try:
            if self.root.winfo_exists() and self.parent.winfo_exists():
                self.root.after(100, self.poll_output)
        except tk.TclError:
            pass

    def apply_theme(self, theme):
        self.theme = theme
        if hasattr(self, "parent"):
            self.parent.configure(bg=theme["root"])
            for widget in self.parent.winfo_children():
                self._apply_theme_widget(widget, theme)

    def _apply_theme_widget(self, widget, theme):
        try:
            if isinstance(widget, tk.Label):
                current_fg = str(widget.cget("fg"))
                light_texts = {"#F8FAFC", "#FFFFFF", "white"}
                light_muted = {"#CBD5E1", "#94A3B8"}
                dark_texts = {"#1F2937", "#334155", "#374151", "#475569", "#3B2500"}
                dark_muted = {"#64748B", "#6B7280"}
                if current_fg in light_texts or current_fg in dark_texts:
                    widget.configure(fg=theme["text"])
                elif current_fg in light_muted:
                    widget.configure(fg=theme["muted"])
                elif current_fg in dark_muted or current_fg in light_muted:
                    widget.configure(fg=theme["muted"])
                widget.configure(bg=theme["surface"] if widget.master is not self.parent else theme["root"])
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=theme["surface"] if widget is not self.parent else theme["root"])
            elif isinstance(widget, tk.Text):
                widget.configure(bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"])
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"])
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._apply_theme_widget(child, theme)


class ContextHelpManager:
    """Ajuda contextual global, não modal e reconstruível junto com as abas."""

    def __init__(self, app):
        self.app = app
        self.markers = []
        self.tooltip_window = None
        self.center_window = None
        self.center_message = None
        self.center_step_button = None
        self.center_disable_button = None
        self.steps_window = None
        self.steps_body = None

    def _theme(self):
        return self.app.current_theme()

    def _tab_key(self):
        return self.app.current_tab_key()

    def _targets(self):
        targets = [
            (getattr(self.app, "clone_tab_button", None), "Alterna entre as abas principais do aplicativo."),
            (getattr(self.app, "review_tab_button", None), "Alterna entre as abas principais do aplicativo."),
            (getattr(self.app, "converter_tab_button", None), "Alterna entre as abas principais do aplicativo."),
            (getattr(self.app, "format_tab_button", None), "Alterna entre as abas principais do aplicativo."),
            (getattr(self.app, "wem_filter_tab_button", None), "Abre o filtro inteligente para renomear arquivos de qualquer extensão com pré-visualização e segurança."),
            (getattr(self.app, "voice_clone_tab_button", None), "Abre a ferramenta para cortar, juntar e preparar áudios para clonagem de voz."),
            (getattr(self.app, "commands_tab_button", None), "Alterna entre as abas principais do aplicativo."),
            (getattr(self.app, "language_combo", None), "Escolha o idioma da interface. Caminhos, arquivos e dados do usuário não são modificados."),
            (getattr(self.app, "theme_button", None), "Alterna entre os temas claro e escuro."),
            (getattr(self.app, "refresh_screen_button", None), "Reconstrói a interface e recarrega as abas sem fechar o aplicativo."),
            (getattr(self.app, "scale_minus_button", None), "Reduz o tamanho visual da interface em 5%."),
            (getattr(self.app, "scale_plus_button", None), "Aumenta o tamanho visual da interface em 5%."),
            (getattr(self.app, "player_mode_button", None), "Alterna entre o FFplay interno e o reprodutor padrão do Windows ao abrir um áudio."),
        ]
        batch = getattr(self.app, "batch_app", None)
        targets.extend([
            (getattr(batch, "model_combo", None), "Escolha o modelo de geração disponível para a fila."),
            (getattr(batch, "mode_combo", None), "Escolha o modo de geração: clonagem, design ou voz automática."),
            (getattr(batch, "instruct_entry", None), "Digite a descrição usada pelo modo Voice Design."),
            (getattr(batch, "r_pronunciation_combo", None), "Escolha SEM ALTERAÇÃO, R SUAVE, R NORMAL ou R FORTE; a opção fixa atua por transformação ortográfica segura do texto e não envia frases livres inválidas ao OmniVoice."),
            (getattr(batch, "queue_list", None), "Lista as cenas e os pares WAV + TXT encontrados no projeto; também aceita arquivos de áudio arrastados."),
            (getattr(batch, "dependencies_button", None), "Prepara FFmpeg, FFprobe e FFplay na pasta portátil compartilhada."),
            (getattr(batch, "tools_help_button", None), "Explica qual ferramenta é usada para conversão, diagnóstico e reprodução."),
            (getattr(batch, "audio_count_label", None), "Mostra quantos áudios foram encontrados e quantas cenas possuem TXT correspondente."),
            (getattr(batch, "start_button", None), "Inicia a fila de clonagem e dublagem."),
            (getattr(batch, "log_box", None), "Mostra o andamento, avisos e erros da fila."),
        ])
        review = getattr(self.app, "review_app", None)
        targets.extend([
            (getattr(review, "scene_list", None), "Lista as cenas disponíveis para revisão."),
            (getattr(review, "text_box", None), "Edite o texto em português antes de salvar ou refazer uma cena."),
            (getattr(review, "approve_button", None), "Use Aprovar, Rejeitar ou REFAZER CENA conforme o resultado."),
            (getattr(review, "regenerate_button", None), "Use Aprovar, Rejeitar ou REFAZER CENA conforme o resultado."),
            (getattr(review, "regenerate_other_audio_button", None), "Abre uma janela com os WAVs originais e permite escolher também um áudio externo para usar como referência na redublagem."),
            (getattr(review, "auto_open_check", None), "Quando ativado, abre o Audacity automaticamente depois que a redublagem terminar."),
            (getattr(review, "request_r_check", None), "Quando ativado, pergunta o ajuste do R somente nesta ação de REDUBLAR ou REDUBLAR COM OUTRO ÁUDIO; não altera a escolha fixa da aba CLONAGEM + DUBLAGEM."),
        ])
        converter = getattr(self.app, "converter_app", None)
        targets.extend([
            (getattr(converter, "original_listbox", None), "Lista os áudios originais carregados para comparar duração."),
            (getattr(converter, "dubbed_listbox", None), "Lista os áudios dublados carregados para converter."),
            (getattr(converter, "format_combo", None), "Escolha o formato final do áudio."),
            (getattr(converter, "dependencies_button", None), "Prepara FFmpeg, FFprobe, FFplay e SoX na pasta portátil."),
            (getattr(converter, "convert_button", None), "Inicia a conversão de duração dos áudios."),
        ])
        format_app = getattr(self.app, "format_app", None)
        targets.extend([
            (getattr(format_app, "listbox", None), "Lista os arquivos carregados para converter."),
            (getattr(format_app, "format_combo", None), "Escolha o formato final do áudio."),
            (getattr(format_app, "output_entry", None), "Escolha onde os arquivos convertidos serão gravados."),
            (getattr(format_app, "load_review_button", None), "Carrega os áudios reais do projeto a partir da aba Revisão."),
            (getattr(format_app, "load_batch_button", None), "Carrega os áudios reais do projeto a partir da aba Clonagem + Dublagem."),
            (getattr(format_app, "dependencies_button", None), "Prepara FFmpeg, FFprobe, FFplay e SoX na pasta portátil."),
            (getattr(format_app, "convert_button", None), "Inicia a conversão somente de formato, sem ajustar a duração."),
        ])
        terminal = getattr(self.app, "terminal_app", None)
        targets.extend([
            (getattr(terminal, "command_entry", None), "Digite ou escolha um comando de diagnóstico."),
            (getattr(terminal, "output_box", None), "Mostra a saída dos comandos executados no projeto."),
        ])
        wem_filter = getattr(self.app, "wem_filter_app", None)
        targets.extend([
            (getattr(wem_filter, "file_list", None), "Lista arquivos de qualquer extensão para renomeação, sem copiar, mover ou converter. Também aceita arquivos e pastas arrastados."),
            (getattr(wem_filter, "add_files_button", None), "Abre arquivos individuais de qualquer extensão para a lista."),
            (getattr(wem_filter, "choose_folder_button", None), "Abre uma pasta e carrega seus arquivos para a lista."),
            (getattr(wem_filter, "generate_txt_button", None), "Gera um TXT com ID, nome base, arquivo, extensão e caminho relativo."),
            (getattr(wem_filter, "clear_button", None), "Remove somente os arquivos da lista e da prévia; não apaga arquivos do disco nem o histórico de renomeações."),
            (getattr(wem_filter, "rule_combo", None), "Escolha a regra inteligente: IDs, padrões Wwise, sufixos ou nome base."),
            (getattr(wem_filter, "id_plus_one_button", None), "Aumenta todos os IDs encontrados em 1 e atualiza somente a prévia."),
            (getattr(wem_filter, "id_plus_ten_button", None), "Aumenta todos os IDs encontrados em 10 e atualiza somente a prévia."),
            (getattr(wem_filter, "id_minus_one_button", None), "Diminui todos os IDs encontrados em 1 e atualiza somente a prévia."),
            (getattr(wem_filter, "id_minus_ten_button", None), "Diminui todos os IDs encontrados em 10 e atualiza somente a prévia."),
            (getattr(wem_filter, "id_custom_button", None), "Permite digitar qualquer valor positivo ou negativo para ajustar os IDs na prévia."),
            (getattr(wem_filter, "load_map_button", None), "Carrega um ou dois TXT do Wwise e relaciona nomes de narração aos seus IDs."),
            (getattr(wem_filter, "process_all_button", None), "Executa o fluxo completo: prévia, TXT de IDs e nomes e renomeação segura."),
            (getattr(wem_filter, "rename_button", None), "Aplica somente renomeações seguras no mesmo diretório."),
            (getattr(wem_filter, "undo_button", None), "Desfaz a última operação de renomeação realizada nesta sessão."),
            (getattr(wem_filter, "save_renamed_button", None), "Salva a lista completa dos arquivos renomeados, com nome anterior, nome novo e ID final."),
            (getattr(wem_filter, "preview_tree", None), "Mostra o nome atual, o novo nome, a regra usada e os conflitos detectados."),
        ])
        return targets

    def _destroy_markers(self):
        for marker in self.markers:
            try:
                marker.destroy()
            except Exception:
                pass
        self.markers = []

    def _show_tooltip(self, event, source_text):
        self._hide_tooltip()
        try:
            theme = self._theme()
            window = tk.Toplevel(self.app.root)
            window.wm_overrideredirect(True)
            window.attributes("-topmost", True)
            bg = theme.get("surface", "#FFFFFF")
            fg = theme.get("text", "#1F2937")
            tk.Label(window, text=i18n.tr(source_text), justify="left", wraplength=360, bg=bg, fg=fg, relief="solid", bd=1, padx=8, pady=6, font=("Segoe UI", 9)).pack()
            window.update_idletasks()
            x = int(getattr(event, "x_root", self.app.root.winfo_pointerx()))
            y = int(getattr(event, "y_root", self.app.root.winfo_pointery())) - window.winfo_reqheight() - 10
            if y < 4:
                y = int(getattr(event, "y_root", self.app.root.winfo_pointery())) + 16
            window.geometry(f"+{max(4, x - 370)}+{max(4, y)}")
            self.tooltip_window = window
        except Exception:
            self.tooltip_window = None

    def _hide_tooltip(self, _event=None):
        if self.tooltip_window is not None:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None

    def _create_marker(self, widget, source_text):
        try:
            if not widget.winfo_exists() or widget.master is None:
                return
            theme = self._theme()
            marker = tk.Label(widget.master, text="?", bg="#F59E0B", fg="#111827", relief="solid", bd=1, width=1, height=1, font=("Segoe UI", 7, "bold"), cursor="question_arrow")
            marker.place(in_=widget, relx=1.0, rely=0.0, x=-2, y=2, anchor="ne")
            marker.lift()
            marker.bind("<Enter>", lambda event, text=source_text: self._show_tooltip(event, text), add="+")
            marker.bind("<Leave>", self._hide_tooltip, add="+")
            marker.bind("<Button-1>", lambda _event: self.open_center(), add="+")
            self.markers.append(marker)
        except Exception:
            return

    def refresh(self):
        self._destroy_markers()
        if not self.app.help_active:
            self.update_windows()
            return
        for widget, source_text in self._targets():
            if widget is not None:
                self._create_marker(widget, source_text)
        self.update_windows()

    def update_windows(self):
        try:
            if self.center_window is not None and self.center_window.winfo_exists():
                self.center_window.title(i18n.tr("AJUDA CONTEXTUAL"))
                self.center_message.configure(text=i18n.tr("A ajuda contextual está ativa. Passe o mouse sobre os marcadores ? para ver uma explicação."))
                self.center_step_button.configure(text=i18n.tr("ABRIR PASSO A PASSO DA ABA ATUAL"))
                self.center_disable_button.configure(text=i18n.tr("DESATIVAR AJUDA"))
        except Exception:
            pass
        self.update_steps_window()

    def open_center(self):
        if self.center_window is not None and self.center_window.winfo_exists():
            self.center_window.lift()
            return
        theme = self._theme()
        self.center_window = tk.Toplevel(self.app.root)
        self.center_window.title(i18n.tr("AJUDA CONTEXTUAL"))
        self.center_window.geometry("510x180")
        self.center_window.minsize(420, 160)
        self.center_window.transient(self.app.root)
        self.center_window.protocol("WM_DELETE_WINDOW", self.close_center)
        self.center_window.configure(bg=theme.get("surface", "#FFFFFF"))
        self.center_message = tk.Label(self.center_window, text=i18n.tr("A ajuda contextual está ativa. Passe o mouse sobre os marcadores ? para ver uma explicação."), justify="left", wraplength=470, bg=theme.get("surface", "#FFFFFF"), fg=theme.get("text", "#1F2937"), font=("Segoe UI", 10), padx=14, pady=14)
        self.center_message.pack(fill="both", expand=True)
        actions = tk.Frame(self.center_window, bg=theme.get("surface", "#FFFFFF"))
        actions.pack(fill="x", padx=14, pady=(0, 14))
        self.center_step_button = tk.Button(actions, text=i18n.tr("ABRIR PASSO A PASSO DA ABA ATUAL"), command=self.show_steps, relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5)
        apply_button_style(self.center_step_button, theme, "warning")
        self.center_step_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.center_disable_button = tk.Button(actions, text=i18n.tr("DESATIVAR AJUDA"), command=self.deactivate, relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=5)
        apply_button_style(self.center_disable_button, theme, "danger")
        self.center_disable_button.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.center_window.lift()

    def close_center(self):
        if self.center_window is not None:
            try:
                self.center_window.destroy()
            except Exception:
                pass
        self.center_window = None
        self.center_message = None
        self.center_step_button = None
        self.center_disable_button = None

    def show_steps(self):
        if self.steps_window is not None and self.steps_window.winfo_exists():
            self.steps_window.lift()
            self.update_steps_window()
            return
        theme = self._theme()
        self.steps_window = tk.Toplevel(self.app.root)
        self.steps_window.title(i18n.tr("Passo a passo — ") + i18n.help_tab_label(self._tab_key()))
        self.steps_window.geometry("690x300")
        self.steps_window.minsize(500, 230)
        self.steps_window.transient(self.app.root)
        self.steps_window.protocol("WM_DELETE_WINDOW", self.close_steps)
        self.steps_window.configure(bg=theme.get("surface", "#FFFFFF"))
        self.steps_body = tk.Label(self.steps_window, justify="left", anchor="nw", wraplength=640, bg=theme.get("surface", "#FFFFFF"), fg=theme.get("text", "#1F2937"), font=("Segoe UI", 10), padx=16, pady=16)
        self.steps_body.pack(fill="both", expand=True)
        self.update_steps_window()
        self.steps_window.lift()

    def update_steps_window(self):
        try:
            if self.steps_window is not None and self.steps_window.winfo_exists() and self.steps_body is not None:
                self.steps_window.title(i18n.tr("Passo a passo — ") + i18n.help_tab_label(self._tab_key()))
                self.steps_body.configure(text="\n".join(i18n.help_steps(self._tab_key())))
        except Exception:
            pass

    def close_steps(self):
        if self.steps_window is not None:
            try:
                self.steps_window.destroy()
            except Exception:
                pass
        self.steps_window = None
        self.steps_body = None

    def update_tab(self):
        self.update_steps_window()

    def update_language(self):
        self.update_windows()

    def apply_theme(self):
        theme = self._theme()
        for window, body in ((self.center_window, self.center_message), (self.steps_window, self.steps_body)):
            try:
                if window is not None and window.winfo_exists():
                    window.configure(bg=theme.get("surface", "#FFFFFF"))
                    if body is not None:
                        body.configure(bg=theme.get("surface", "#FFFFFF"), fg=theme.get("text", "#1F2937"))
            except Exception:
                pass
        for widget, role in ((self.center_step_button, "warning"), (self.center_disable_button, "danger")):
            try:
                if widget is not None and widget.winfo_exists():
                    apply_button_style(widget, theme, role)
            except Exception:
                pass
        warning_style = button_style(theme, "warning")
        for marker in tuple(self.markers):
            try:
                if marker.winfo_exists():
                    marker.configure(bg=warning_style["bg"], fg=warning_style["fg"])
            except Exception:
                pass
        # Apenas atualiza textos e cores; não destrói/recria marcadores nem janelas.
        self.update_windows()

    def activate(self):
        self.app.help_active = True
        self.app.update_help_button()
        self.refresh()
        self.open_center()

    def deactivate(self):
        self.app.help_active = False
        self._hide_tooltip()
        self._destroy_markers()
        self.close_center()
        self.close_steps()
        self.app.update_help_button()

    def toggle(self):
        if self.app.help_active:
            self.deactivate()
        else:
            self.activate()

    def close(self):
        self._hide_tooltip()
        self._destroy_markers()
        self.close_center()
        self.close_steps()


class DublaskizonApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Dublaskizon")
        apply_window_icon(self.root)
        self.root.geometry(f"{BASE_WINDOW_WIDTH}x{BASE_WINDOW_HEIGHT}")
        self.root.minsize(BASE_MIN_WIDTH, BASE_MIN_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._install_global_shortcuts()
        configured_root = os.environ.get("DUBLASKIZON_PROJECT_ROOT")
        if configured_root:
            configured_path = Path(configured_root).expanduser().resolve()
            # A pasta escolhida/configurada é a raiz dos dados. Quando ela é
            # justamente a pasta dist do EXE, as saídas ficam ali por decisão
            # explícita do usuário: <diretório do EXE>\\REDIMENSIONAR ÁUDIO PARA CLONAR.
            self.project_root = configured_path
        else:
            self.project_root = self.detect_default_project_root()
        self.root.project_root = self.project_root
        self.base_tk_scaling = float(self.root.tk.call("tk", "scaling"))
        self._scaling_in_progress = False
        self._scale_font_targets = {}
        self._scale_padding_targets = {}
        self.theme_mode = self.load_theme_mode()
        self.scale_percent = self.load_scale_percent()
        self.language_code = self.load_language()
        self.player_mode = self.load_player_mode()
        i18n.set_current_language(self.language_code)
        self.apply_scale(self.scale_percent, resize_window=True, save=False)
        self.active_scroll = None
        self.clone_scroll = None
        self.review_scroll = None
        self.personalized_scroll = None
        self.terminal_scroll = None
        self.converter_scroll = None
        self.format_scroll = None
        self.video_scroll = None
        self.swap_scroll = None
        self.batch_app = None
        self.review_app = None
        self.personalized_app = None
        self.terminal_app = None
        self.converter_app = None
        self.format_app = None
        self.video_app = None
        self.swap_app = None
        self.wem_filter_app = None
        self.wem_filter_scroll = None
        self.wem_filter_frame = None
        self.voice_clone_app = None
        self.voice_clone_scroll = None
        self.voice_clone_frame = None
        self.help_active = False
        self.central_log_queue = queue.Queue()
        self.help_manager = ContextHelpManager(self)

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            try:
                style.theme_use("vista")
            except Exception:
                pass

        header = tk.Frame(root, bg="#172033")
        self.header = header
        header.pack(fill="x")
        brand_line = tk.Frame(header, bg="#172033")
        self.brand_line = brand_line
        brand_line.pack(fill="x", padx=20, pady=(6, 8))
        tk.Label(brand_line, text="DUBLASKIZON", bg="#172033", fg="white", font=("Segoe UI", 22, "bold")).pack(side="left")
        tk.Label(brand_line, text="OmniVoice + Audacity — dublagem e revisão em um único aplicativo", bg="#172033", fg="#CBD5E1", font=("Segoe UI", 11)).pack(side="left", padx=(18, 0), pady=(5, 0))

        tabs_shell = tk.Frame(root, bg="#E2E8F0")
        tabs_shell.pack(fill="x", padx=10, pady=(8, 0))
        self.tabs_canvas = tk.Canvas(tabs_shell, bg="#E2E8F0", height=54, highlightthickness=0)
        self.tabs_canvas.pack(fill="x")
        tab_scroll = ttk.Scrollbar(tabs_shell, orient="horizontal", command=self.tabs_canvas.xview)
        tab_scroll.pack(fill="x")
        self.tabs_canvas.configure(xscrollcommand=tab_scroll.set)
        tabs_bar = tk.Frame(self.tabs_canvas, bg="#E2E8F0")
        self.tabs_bar = tabs_bar
        self.tabs_canvas.create_window((0, 0), window=tabs_bar, anchor="nw")
        tabs_bar.bind("<Configure>", lambda event: self.tabs_canvas.configure(scrollregion=self.tabs_canvas.bbox("all"), height=tabs_bar.winfo_reqheight()))
        self.clone_tab_button = tk.Button(tabs_bar, text="CLONAGEM + DUBLAGEM", command=lambda: self.select_tab(self.clone_scroll), bg="#2563EB", activebackground="#1D4ED8", fg="white", activeforeground="white", relief="sunken", font=("Segoe UI", 10, "bold"), padx=11, pady=6, width=21, cursor="hand2")
        self.clone_tab_button.pack(side="left", padx=(0, 4))
        self.review_tab_button = tk.Button(tabs_bar, text="REVISÃO", command=lambda: self.select_tab(self.review_scroll), bg="#C4B5FD", activebackground="#A78BFA", fg="#24134D", activeforeground="#24134D", relief="raised", font=("Segoe UI", 10, "bold"), padx=11, pady=6, width=21, cursor="hand2")
        self.review_tab_button.pack(side="left", padx=(4, 0))
        self.personalized_tab_button = tk.Button(tabs_bar, text="DUBLAGEM PERSONALIZADA", command=lambda: self.select_tab(self.personalized_scroll), bg="#8B5CF6", activebackground="#7C3AED", fg="white", activeforeground="white", relief="raised", font=("Segoe UI", 8, "bold"), padx=9, pady=0, width=16, height=2, wraplength=120, justify="center", cursor="hand2")
        self.personalized_tab_button.pack(side="left", padx=(4, 0))
        self.converter_tab_button = tk.Button(tabs_bar, text="CONVERTER\nDURAÇÃO", command=lambda: self.select_tab(self.converter_scroll), bg="#F97316", activebackground="#EA580C", fg="white", activeforeground="white", relief="raised", font=("Segoe UI", 10, "bold"), padx=11, pady=6, width=21, cursor="hand2")
        self.converter_tab_button.pack(side="left", padx=(4, 0))
        self.format_tab_button = tk.Button(tabs_bar, text="CONVERTER\nFORMATOS", command=lambda: self.select_tab(self.format_scroll), bg="#14B8A6", activebackground="#0F766E", fg="white", activeforeground="white", relief="raised", font=("Segoe UI", 10, "bold"), padx=11, pady=6, width=21, cursor="hand2")
        self.format_tab_button.pack(side="left", padx=(4, 0))
        self.wem_filter_tab_button = tk.Button(tabs_bar, text="FILTRO RENOMEAR .WEM", command=lambda: self.select_tab(self.wem_filter_scroll), bg="#7C3AED", activebackground="#6D28D9", fg="white", activeforeground="white", relief="raised", font=("Segoe UI", 10, "bold"), padx=11, pady=6, width=21, cursor="hand2")
        self.wem_filter_tab_button.pack(side="left", padx=(4, 0))
        tools_bar = tabs_bar
        self.tools_tabs_bar = tabs_bar
        self.voice_clone_tab_button = tk.Button(tools_bar, text="REDIMENSIONAR ÁUDIO PARA CLONAR", command=lambda: self.select_tab(self.voice_clone_scroll), bg="#0F766E", fg="white", font=("Segoe UI", 8, "bold"), padx=8, pady=5, width=25, wraplength=170, cursor="hand2")
        self.voice_clone_tab_button.pack(side="left", padx=(0, 4))
        self.video_tab_button = tk.Button(tools_bar, text="COMPACTAR / CONVERTER VÍDEOS", command=lambda: self.select_tab(self.video_scroll), bg="#0F766E", fg="white", font=("Segoe UI", 8, "bold"), padx=8, pady=5, width=25, wraplength=170, cursor="hand2")
        self.video_tab_button.pack(side="left", padx=(0, 4))
        self.swap_tab_button = tk.Button(tools_bar, text="TROCAR AUDIO DO VÍDEO", command=lambda: self.select_tab(self.swap_scroll), bg="#7C3AED", fg="white", font=("Segoe UI", 8, "bold"), padx=8, pady=5, width=25, wraplength=170, cursor="hand2")
        self.swap_tab_button.pack(side="left", padx=(0, 4))
        self.commands_tab_button = tk.Button(tools_bar, text="COMANDOS", command=lambda: self.select_tab(self.terminal_scroll), bg="#F59E0B", fg="#3B2500", font=("Segoe UI", 8, "bold"), padx=8, pady=5, width=18, cursor="hand2")
        self.commands_tab_button.pack(side="left")

        scale_panel = tk.Frame(brand_line, bg="#172033")
        self.scale_panel = scale_panel
        scale_panel.pack(side="right", padx=(8, 0), pady=(0, 0))
        self.refresh_screen_button = tk.Button(scale_panel, text="ATUALIZAR TELA", command=self.refresh_screen, bg="#0F766E", activebackground="#115E59", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.refresh_screen_button.pack(side="left", padx=(0, 5))
        self.help_button = tk.Button(scale_panel, text="? AJUDA", command=self.toggle_help, bg="#D97706", activebackground="#B45309", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.help_button.pack(side="left", padx=(0, 5))
        self.requirements_button = tk.Button(scale_panel, text="REQUISITOS", command=self.show_dependency_assistant, bg="#0F766E", activebackground="#115E59", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.requirements_button.pack(side="left", padx=(0, 5))
        self.language_label = tk.Label(scale_panel, text="IDIOMA:", bg="#E2E8F0", fg="#1F2937", font=("Segoe UI", 8, "bold"))
        self.language_label.pack(side="left", padx=(0, 3))
        self.language_var = tk.StringVar(value=i18n.LANGUAGE_LABELS.get(self.language_code, "Português"))
        self.language_combo = ttk.Combobox(scale_panel, textvariable=self.language_var, values=list(i18n.LANGUAGE_LABELS.values()), state="readonly", width=11)
        self.language_combo.pack(side="left", padx=(0, 6))
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_selected)
        self.theme_button = tk.Button(scale_panel, text="APARÊNCIA: CLARA", command=self.toggle_theme, bg="#334155", activebackground="#1E293B", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.theme_button.pack(side="left", padx=(0, 5))
        self.scale_minus_button = tk.Button(scale_panel, text="−", command=lambda: self.change_scale(-5), bg="#64748B", activebackground="#475569", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"), width=2, padx=0, pady=1, cursor="hand2")
        self.scale_minus_button.pack(side="left", padx=(0, 3))
        self.scale_percent_button = tk.Button(scale_panel, text=f"ESCALA DA TELA: {self.scale_percent}%", command=lambda: self.set_scale_percent(100), bg="#334155", activebackground="#1E293B", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.scale_percent_button.pack(side="left", padx=2)
        self.scale_plus_button = tk.Button(scale_panel, text="+", command=lambda: self.change_scale(5), bg="#64748B", activebackground="#475569", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"), width=2, padx=0, pady=1, cursor="hand2")
        self.scale_plus_button.pack(side="left", padx=(3, 0))
        self.player_mode_button = tk.Button(scale_panel, command=self.toggle_player_mode, bg="#7C3AED", activebackground="#6D28D9", fg="white", activeforeground="white", relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        self.player_mode_button.pack(side="left", padx=(6, 0))
        self.update_player_mode_button()

        self.content = tk.Frame(root, bg="#F5F6FA")
        self.content.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        footer = tk.Frame(root, bg="#EEF2F7")
        self.footer = footer
        footer.pack(fill="x")
        self.footer_label = tk.Label(footer, text="Projeto atual:", bg="#EEF2F7", fg="#475569", font=("Segoe UI", 8, "bold"))
        self.footer_label.pack(side="left", padx=(12, 4), pady=4)
        self.project_footer_entry = tk.Entry(footer, font=("Segoe UI", 8), relief="flat", bd=0, readonlybackground="#EEF2F7", fg="#475569", width=150)
        self.project_footer_entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=4)
        self.project_footer_entry.configure(state="readonly")

        # A estrutura só é criada por uma ação explícita do usuário.
        self.rebuild_views()
        self.apply_scale(self.scale_percent, resize_window=True, save=False)
        self.apply_language(self.language_code, save=False)
        self.help_manager.refresh()
        self.root.after(350, self._language_refresh_tick)
        if self.should_show_dependency_assistant():
            self.root.after(900, self.show_dependency_assistant)

    def _install_global_shortcuts(self) -> None:
        """Registra atalhos para todas as abas e Toplevels desta aplicação."""
        self.root.bind_all("<Control-KeyPress-a>", self._shortcut_select_all, add="+")
        self.root.bind_all("<Control-KeyPress-f>", self._shortcut_find, add="+")

    @staticmethod
    def _widget_state(widget) -> str:
        try:
            return str(widget.cget("state"))
        except (AttributeError, tk.TclError):
            return "normal"

    def _shortcut_select_all(self, event=None):
        widget = getattr(event, "widget", None) if event is not None else self.root.focus_get()
        if widget is None:
            return "break"
        try:
            widget_class = widget.winfo_class()
            if self._widget_state(widget) == "disabled":
                return "break"
            if widget_class in {"Entry", "TEntry", "Spinbox", "TSpinbox", "Combobox", "TCombobox"}:
                widget.selection_range(0, "end")
                widget.icursor("end")
                return "break"
            if widget_class in {"Text", "ScrolledText"}:
                widget.tag_add("sel", "1.0", "end-1c")
                widget.mark_set("insert", "end-1c")
                widget.see("end")
                return "break"
            if widget_class == "Listbox":
                last = widget.size() - 1
                if last >= 0:
                    widget.selection_clear(0, "end")
                    widget.selection_set(0, last)
                    widget.activate(0)
                    widget.see(0)
                return "break"
            if widget_class in {"Treeview", "Tree"}:
                items = widget.get_children("")
                if items:
                    widget.selection_set(items)
                return "break"
        except (AttributeError, tk.TclError):
            pass
        return "break"

    def _shortcut_find(self, event=None):
        widget = getattr(event, "widget", None) if event is not None else self.root.focus_get()
        widget = widget or self.root
        try:
            from .find_panel import FindPanel
        except ImportError:
            from find_panel import FindPanel
        if not hasattr(self, "find_panel"):
            self.find_panel = FindPanel(self.root, self.current_theme())
        self.find_panel.theme = self.current_theme()
        self.find_panel.show(widget)
        return "break"

    def _find_in_widget(self, widget, query: str) -> bool:
        query = str(query).casefold()
        if not query:
            return False
        try:
            widget_class = widget.winfo_class()
            if widget_class in {"Entry", "TEntry", "Spinbox", "TSpinbox", "Combobox", "TCombobox"}:
                value = str(widget.get())
                start = value.casefold().find(query)
                if start >= 0:
                    widget.selection_range(start, start + len(query))
                    widget.icursor(start + len(query))
                    return True
                return False
            if widget_class in {"Text", "ScrolledText"}:
                start_index = "1.0"
                try:
                    insert_index = widget.index("insert")
                    if widget.compare(insert_index, "<", "end-1c"):
                        start_index = insert_index
                except (AttributeError, tk.TclError):
                    pass
                index = widget.search(query, start_index, nocase=True, stopindex="end")
                if not index and start_index != "1.0":
                    index = widget.search(query, "1.0", nocase=True, stopindex="end")
                if index:
                    end_index = f"{index}+{len(query)}c"
                    widget.tag_remove("ctrl_f_match", "1.0", "end")
                    widget.tag_add("ctrl_f_match", index, end_index)
                    widget.tag_configure("ctrl_f_match", background="#FDE68A", foreground="#111827")
                    widget.mark_set("insert", end_index)
                    widget.see(index)
                    return True
                return False
            if widget_class == "Listbox":
                for index, value in enumerate(widget.get(0, "end")):
                    if query in str(value).casefold():
                        widget.selection_clear(0, "end")
                        widget.selection_set(index)
                        widget.activate(index)
                        widget.see(index)
                        return True
                return False
            if widget_class in {"Treeview", "Tree"}:
                def walk(parent_item=""):
                    for item in widget.get_children(parent_item):
                        values = " ".join(str(value) for value in widget.item(item, "values"))
                        text = f"{widget.item(item, 'text')} {values}"
                        if query in text.casefold():
                            return item
                        found = walk(item)
                        if found:
                            return found
                    return None
                item = walk()
                if item:
                    widget.selection_set(item)
                    widget.focus(item)
                    widget.see(item)
                    return True
                return False
        except (AttributeError, tk.TclError, TypeError, ValueError):
            return False
        return False

    def should_show_dependency_assistant(self) -> bool:
        try:
            data = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8"))
            return bool(data.get("show_dependency_assistant", True))
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return True

    def save_dependency_assistant_preference(self, show_again: bool) -> None:
        try:
            data = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8")) if INTERFACE_CONFIG_PATH.is_file() else {}
            if not isinstance(data, dict):
                data = {}
            data["show_dependency_assistant"] = bool(show_again)
            INTERFACE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            INTERFACE_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    def dependency_python_command(self) -> list[str] | None:
        if not getattr(sys, "frozen", False):
            return [sys.executable]
        if sys.platform.startswith("win") and shutil.which("py"):
            return [shutil.which("py"), "-3.12"]
        for name in ("python", "python3"):
            found = shutil.which(name)
            if found:
                return [found]
        return None

    def voice_studio_installed(self) -> bool:
        candidates = []
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "APPDATA"):
            value = os.environ.get(variable)
            if value:
                base = Path(value)
                candidates.extend((base / "VoiceStudio", base / "Programs" / "VoiceStudio", base / "OmniVoiceStudio"))
        return any(path.exists() for path in candidates)

    def show_dependency_assistant(self) -> None:
        from dependency_setup import show_assistant
        show_assistant(self)

    def load_player_mode(self) -> str:
        try:
            data = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8"))
            mode = str(data.get("player_mode", "ffplay")).casefold()
            return mode if mode in {"ffplay", "windows"} else "ffplay"
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return "ffplay"

    def save_player_mode(self) -> None:
        try:
            existing = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8")) if INTERFACE_CONFIG_PATH.is_file() else {}
            if not isinstance(existing, dict):
                existing = {}
            existing["player_mode"] = self.player_mode
            INTERFACE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            INTERFACE_CONFIG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    def apply_player_mode(self) -> None:
        for app in (self.batch_app, self.review_app, self.personalized_app, self.converter_app, self.format_app, self.voice_clone_app):
            player = getattr(app, "audio_player", None)
            if player is not None and hasattr(player, "set_playback_mode"):
                player.set_playback_mode(self.player_mode)

    def update_player_mode_button(self) -> None:
        if hasattr(self, "player_mode_button"):
            label = "OUVIR: FFPLAY" if self.player_mode == "ffplay" else "OUVIR: WINDOWS"
            self.player_mode_button.configure(text=i18n.tr(label))

    def toggle_player_mode(self) -> None:
        self.player_mode = "windows" if self.player_mode == "ffplay" else "ffplay"
        self.central_log("COMANDOS", f"Modo de reprodução alterado para: {self.player_mode}.", "info")
        self.apply_player_mode()
        self.update_player_mode_button()
        self.save_player_mode()

    def load_language(self) -> str:
        try:
            data = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8"))
            language = str(data.get("language", "pt"))
            return language if language in i18n.LANGUAGE_LABELS else "pt"
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return "pt"

    def save_language(self) -> None:
        try:
            existing = json.loads(INTERFACE_CONFIG_PATH.read_text(encoding="utf-8")) if INTERFACE_CONFIG_PATH.is_file() else {}
            if not isinstance(existing, dict):
                existing = {}
            existing["language"] = self.language_code
            INTERFACE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            INTERFACE_CONFIG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    def apply_language(self, language: str, save: bool = True) -> None:
        self.language_code = i18n.set_current_language(language)
        if hasattr(self, "language_var"):
            self.language_var.set(i18n.LANGUAGE_LABELS[self.language_code])
        if getattr(self, "wem_filter_app", None) is not None and hasattr(self.wem_filter_app, "apply_language"):
            self.wem_filter_app.apply_language(self.language_code)
        if getattr(self, "batch_app", None) is not None and hasattr(self.batch_app, "apply_language"):
            self.batch_app.apply_language(self.language_code)
        if getattr(self, "voice_clone_app", None) is not None and hasattr(self.voice_clone_app, "apply_language"):
            self.voice_clone_app.apply_language(self.language_code)
        if getattr(self, "personalized_app", None) is not None and hasattr(self.personalized_app, "apply_language"):
            self.personalized_app.apply_language(self.language_code)
        i18n.translate_widget_tree(self.root, self.language_code)
        self.update_theme_button()
        self.update_player_mode_button()
        if hasattr(self, "help_manager"):
            self.help_manager.update_language()
        if hasattr(self, "scale_percent_button"):
            self.scale_percent_button.configure(text=f"{i18n.tr('ESCALA DA TELA')}: {self.scale_percent}%")
        self.root.title(f"{i18n.tr('Dublaskizon')} — {self.project_root.name}")
        if save:
            self.save_language()

    def on_language_selected(self, _event=None) -> None:
        selected = self.language_var.get()
        language = i18n.LANGUAGE_CODES.get(selected, "pt")
        self.apply_language(language)

    def _language_refresh_tick(self) -> None:
        try:
            if self.root.winfo_exists():
                i18n.translate_widget_tree(self.root, self.language_code)
                self.root.after(350, self._language_refresh_tick)
        except tk.TclError:
            return

    def refresh_screen(self) -> None:
        apps = (getattr(self, name, None) for name in (
            'batch_app', 'personalized_app', 'review_app', 'converter_app',
            'format_app', 'video_app', 'swap_app', 'voice_clone_app'))
        if any(getattr(app, flag, False) for app in apps
               for flag in ('running', 'busy', 'dependencies_running')):
            # Rebuilding widgets destroys queues, editors and active job controllers.
            # Only refresh the review index while any worker is active.
            self.refresh_review()
            return
        active_name = self.current_tab_key()
        if active_name == "wem_filter":
            # A aba de renomeação mantém seus arquivos, mapas, ajuste numérico,
            # divisor e colunas. Apenas repinta o tema/idioma e recalcula a prévia.
            self.wem_filter_app.refresh_for_project()
            self.wem_filter_app.apply_theme(self.current_theme())
            self.wem_filter_app.apply_language(self.language_code)
            self.wem_filter_app.generate_preview()
            self.update_tab_buttons()
            self.status_refresh_message()
            if hasattr(self, "help_manager"):
                self.help_manager.refresh()
            self.root.update_idletasks()
            return
        self.rebuild_views()
        self.apply_language(self.language_code, save=False)
        target = {"clone": self.clone_scroll, "review": self.review_scroll, "personalized": self.personalized_scroll, "terminal": self.terminal_scroll, "converter": self.converter_scroll, "format": self.format_scroll, "video": self.video_scroll, "swap": self.swap_scroll, "wem_filter": self.wem_filter_scroll, "voice_clone": self.voice_clone_scroll}[active_name]
        self.select_tab(target)
        self.status_refresh_message()
        if hasattr(self, "help_manager"):
            self.help_manager.refresh()

    def status_refresh_message(self) -> None:
        if hasattr(self, "footer_label"):
            self.footer_label.configure(text=i18n.tr("Projeto atual:"))

    def detect_default_project_root(self) -> Path:
        """Usa o diretório do executável como raiz padrão das saídas."""
        # Em um pacote PyInstaller, APP_DIR é exatamente a pasta que contém o
        # EXE. Não usar cwd nem a pasta pai evita criar dist\\output ou espalhar
        # os resultados em outro local.
        return APP_DIR.resolve()

    def load_scale_percent(self) -> int:
        candidates = [INTERFACE_CONFIG_PATH, self.project_root / "revisoes" / "Dublaskizon_interface.json"]
        for path in candidates:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                value = int(data.get("scale_percent", 100))
                return max(25, min(200, value))
            except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return 100

    def save_scale_percent(self) -> None:
        data = {"scale_percent": int(self.scale_percent)}
        for path in (INTERFACE_CONFIG_PATH,):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                if not isinstance(existing, dict):
                    existing = {}
                existing.update(data)
                path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                return
            except (OSError, json.JSONDecodeError):
                continue

    def load_theme_mode(self) -> str:
        candidates = [INTERFACE_CONFIG_PATH, self.project_root / "revisoes" / "Dublaskizon_interface.json"]
        for path in candidates:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if int(data.get("theme_schema_version", 0)) < 3:
                    return "escuro"
                mode = str(data.get("theme", "escuro")).lower()
                return mode if mode in THEMES else "escuro"
            except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return "escuro"

    def save_theme_mode(self) -> None:
        data = {"theme": self.theme_mode, "theme_schema_version": 3}
        for path in (INTERFACE_CONFIG_PATH,):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                if not isinstance(existing, dict):
                    existing = {}
                existing.update(data)
                path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                return
            except (OSError, json.JSONDecodeError):
                continue

    def current_theme(self) -> dict:
        return THEMES.get(self.theme_mode, THEMES["escuro"])

    def toggle_theme(self) -> None:
        order = ("escuro", "medio", "claro")
        self.theme_mode = order[(order.index(self.theme_mode) + 1) % len(order)] if self.theme_mode in order else "escuro"
        self.apply_theme()
        self.save_theme_mode()
        self.update_theme_button()

    def update_theme_button(self) -> None:
        if hasattr(self, "theme_button"):
            self.theme_button.configure(text=f"TEMA: {self.theme_mode.upper()}")

    def update_help_button(self) -> None:
        if hasattr(self, "help_button"):
            self.help_button.configure(text=i18n.tr("? AJUDA: ATIVA" if self.help_active else "? AJUDA"))

    def toggle_help(self) -> None:
        if hasattr(self, "help_manager"):
            self.help_manager.toggle()

    def current_tab_key(self) -> str:
        mapping = (
            (self.clone_scroll, "clone"),
            (self.review_scroll, "review"),
            (self.personalized_scroll, "personalized"),
            (self.converter_scroll, "converter"),
            (self.format_scroll, "format"),
            (self.video_scroll, "video"),
            (self.swap_scroll, "swap"),
            (self.wem_filter_scroll, "wem_filter"),
            (self.voice_clone_scroll, "voice_clone"),
            (self.terminal_scroll, "terminal"),
        )
        for view, key in mapping:
            if self.active_scroll is view:
                return key
        return "clone"

    def apply_theme(self) -> None:
        theme = self.current_theme()
        try:
            style = ttk.Style(self.root)
            ttk_button = button_style(theme, "secondary")
            neutral_button_bg = ttk_button["bg"]
            neutral_button_active = ttk_button["activebackground"]
            neutral_button_fg = ttk_button["fg"]
            style.configure("TFrame", background=theme["surface"])
            style.configure("TLabel", background=theme["surface"], foreground=theme["text"])
            style.configure("TLabelframe", background=theme["surface"], foreground=theme["text"])
            style.configure("TLabelframe.Label", background=theme["surface"], foreground=theme["text"])
            style.configure("TCheckbutton", background=theme["surface"], foreground=theme["text"])
            style.map("TCheckbutton", background=[("active", theme["surface"])], foreground=[("disabled", theme["muted"]), ("active", theme["text"])])
            style.configure("TButton", background=neutral_button_bg, foreground=neutral_button_fg)
            style.map("TButton", background=[("active", neutral_button_active), ("pressed", theme["select"])], foreground=[("disabled", theme["muted"]), ("active", neutral_button_fg), ("pressed", theme["text"])])
            configure_ttk_button_styles(style, theme)
            style.configure("TScrollbar", background=neutral_button_bg, troughcolor=theme["input"], arrowcolor=theme["text"], borderwidth=0)
            style.configure("Vertical.TScrollbar", background=neutral_button_bg, troughcolor=theme["input"], arrowcolor=theme["text"], borderwidth=0)
            style.configure("Horizontal.TScrollbar", background=neutral_button_bg, troughcolor=theme["input"], arrowcolor=theme["text"], borderwidth=0)
            style.configure("TSeparator", background=theme["border"])
            style.configure("TEntry", fieldbackground=theme["input"], foreground=theme["input_text"], insertcolor=theme["input_text"])
            style.map("TEntry", fieldbackground=[("readonly", theme["input"]), ("disabled", theme["surface"])], foreground=[("readonly", theme["input_text"]), ("disabled", theme["muted"])])
            style.configure("TPanedwindow", background=theme["surface"])
            style.configure("TProgressbar", troughcolor=theme["border"], background=surface_color(theme, "progress_clone", theme["select"]), lightcolor=surface_color(theme, "progress_clone", theme["select"]), darkcolor=surface_color(theme, "progress_clone", theme["select"]))
            style.configure("TCombobox", fieldbackground=theme["input"], background=theme["input"], foreground=theme["input_text"], arrowcolor=theme["input_text"])
            style.map("TCombobox", fieldbackground=[("readonly", theme["input"])], foreground=[("readonly", theme["input_text"])], selectbackground=[("readonly", theme["select"])], selectforeground=[("readonly", theme["input_text"])])
            self.root.option_add("*TCombobox*Listbox.background", theme["input"])
            self.root.option_add("*TCombobox*Listbox.foreground", theme["input_text"])
            self.root.option_add("*TCombobox*Listbox.selectBackground", theme["select"])
            self.root.configure(bg=theme["root"])
            for widget in (getattr(self, "header", None), getattr(self, "brand_line", None)):
                if widget is not None and widget.winfo_exists():
                    widget.configure(bg=theme["header"])
            if getattr(self, "tabs_bar", None) is not None:
                self.tabs_bar.configure(bg=theme["tabs"])
                self.tools_tabs_bar.configure(bg=theme["tabs"])
                self.tabs_canvas.configure(bg=theme["tabs"])
            if getattr(self, "scale_panel", None) is not None:
                self.scale_panel.configure(bg=theme["header"])
                if getattr(self, "language_label", None) is not None:
                    self.language_label.configure(bg=theme["header"])
                if getattr(self, "language_combo", None) is not None:
                    self.language_combo.configure(background=theme["input"], foreground=theme["input_text"])
            if getattr(self, "footer_label", None) is not None:
                self.footer_label.configure(bg=theme["footer"], fg=theme["muted"])
            if getattr(self, "project_footer_entry", None) is not None:
                self.project_footer_entry.configure(readonlybackground=theme["footer"], fg=theme["muted"])
            if getattr(self, "content", None) is not None:
                self.content.configure(bg=theme["root"])
            if getattr(self, "footer", None) is not None:
                self.footer.configure(bg=theme["footer"])
            self.update_theme_button()
            self.update_player_mode_button()
            for widget, role in (
                (getattr(self, "refresh_screen_button", None), "teal"),
                (getattr(self, "help_button", None), "warning"),
                (getattr(self, "requirements_button", None), "teal"),
                (getattr(self, "theme_button", None), "accent"),
                (getattr(self, "scale_minus_button", None), "neutral"),
                (getattr(self, "scale_percent_button", None), "secondary"),
                (getattr(self, "scale_plus_button", None), "neutral"),
                (getattr(self, "player_mode_button", None), "accent"),
            ):
                if widget is not None and widget.winfo_exists():
                    apply_button_style(widget, theme, role)
            self.update_tab_buttons()
            apply_button_style_to_tree(self.root, theme)
            for app in (getattr(self, "batch_app", None), getattr(self, "review_app", None), getattr(self, "personalized_app", None), getattr(self, "terminal_app", None), getattr(self, "converter_app", None), getattr(self, "format_app", None), getattr(self, "video_app", None), getattr(self, "swap_app", None), getattr(self, "wem_filter_app", None), getattr(self, "voice_clone_app", None)):
                if app is not None and hasattr(app, "apply_theme"):
                    app.apply_theme(theme)
            for scroll in (getattr(self, "clone_scroll", None), getattr(self, "review_scroll", None), getattr(self, "personalized_scroll", None), getattr(self, "terminal_scroll", None), getattr(self, "converter_scroll", None), getattr(self, "format_scroll", None), getattr(self, "video_scroll", None), getattr(self, "swap_scroll", None), getattr(self, "wem_filter_scroll", None), getattr(self, "voice_clone_scroll", None)):
                if scroll is not None and scroll.winfo_exists():
                    scroll.set_background(theme["root"])
            if hasattr(self, "help_manager"):
                self.help_manager.apply_theme()
            self.ensure_control_contrast(self.root)
            self.root.update_idletasks()
        except tk.TclError:
            pass

    def ensure_control_contrast(self, container) -> None:
        """Garante contraste legível para controles Tk com cores personalizadas."""
        def contrast_for(widget, background: str) -> str:
            try:
                red, green, blue = widget.winfo_rgb(background)
                luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 65535.0
                return "#1F2937" if luminance >= 0.58 else "#FFFFFF"
            except Exception:
                return self.current_theme()["text"]

        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls in {"Button", "Label", "Checkbutton", "Radiobutton"}:
                    background = str(widget.cget("background"))
                    foreground = contrast_for(widget, background)
                    widget.configure(foreground=foreground)
                    if cls == "Button":
                        widget.configure(activeforeground=contrast_for(widget, str(widget.cget("activebackground"))))
                elif cls in {"Entry", "Text", "Listbox", "Spinbox"}:
                    background = str(widget.cget("background"))
                    if cls == "Entry" and str(widget.cget("state")) == "readonly":
                        try:
                            background = str(widget.cget("readonlybackground"))
                        except Exception:
                            pass
                    foreground = contrast_for(widget, background)
                    options = {"foreground": foreground}
                    if cls in {"Entry", "Text", "Spinbox"}:
                        options["insertbackground"] = foreground
                    widget.configure(**options)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    visit(child)
            except Exception:
                pass
        visit(container)

    def capture_scale_targets(self) -> None:
        if tkfont is None:
            return
        def visit(widget):
            key = str(widget)
            if key not in self._scale_font_targets or self._scale_font_targets[key][0] is not widget:
                try:
                    font_value = widget.cget("font")
                    if font_value:
                        font_obj = tkfont.Font(root=self.root, font=font_value)
                        self._scale_font_targets[key] = (widget, font_obj.cget("family"), int(font_obj.cget("size")), font_obj.cget("weight"), font_obj.cget("slant"), int(font_obj.cget("underline")), int(font_obj.cget("overstrike")))
                except (tk.TclError, TypeError, ValueError):
                    pass
            if key not in self._scale_padding_targets or self._scale_padding_targets[key][0] is not widget:
                values = {}
                for option in ("padx", "pady", "width", "height"):
                    try:
                        raw = widget.cget(option)
                        if isinstance(raw, (int, float)):
                            values[option] = float(raw)
                    except (tk.TclError, TypeError, ValueError):
                        pass
                if values:
                    self._scale_padding_targets[key] = (widget, values)
            try:
                children = widget.winfo_children()
            except tk.TclError:
                children = []
            for child in children:
                visit(child)
        visit(self.root)

    def apply_widget_scale(self) -> None:
        raw_factor = self.scale_percent / 100.0
        # Em níveis baixos a fonte reduz pouco; em níveis altos cresce de forma proporcional.
        font_factor = max(0.86, raw_factor)
        # O espaço é o principal elemento compactado para manter mais conteúdo visível.
        layout_factor = max(0.55, min(2.0, raw_factor))
        dead = []
        for key, target in self._scale_font_targets.items():
            widget, family, size, weight, slant, underline, overstrike = target
            try:
                if not widget.winfo_exists():
                    dead.append(key)
                    continue
                scaled_size = max(9, int(round(size * font_factor)))
                widget.configure(font=(family, scaled_size, weight, slant, underline, overstrike))
            except (tk.TclError, TypeError, ValueError):
                pass
        for key, target in self._scale_padding_targets.items():
            widget, values = target
            try:
                if not widget.winfo_exists():
                    dead.append(key)
                    continue
                for option, base_value in values.items():
                    widget.configure(**{option: max(0, int(round(base_value * layout_factor)))})
            except (tk.TclError, TypeError, ValueError):
                pass
        for key in dead:
            self._scale_font_targets.pop(key, None)
            self._scale_padding_targets.pop(key, None)

        # Uma única linha: dimensões idênticas para todas as abas, inclusive em outras escalas.
        for name in ("clone", "review", "personalized", "converter", "format", "wem_filter", "voice_clone", "video", "swap", "commands"):
            button = getattr(self, name + "_tab_button", None)
            if button is not None:
                button.configure(font=("Segoe UI", max(8, round(9 * self.scale_percent / 100)), "bold"),
                                 width=19, height=2, padx=10, pady=7, wraplength=max(100, round(136 * self.scale_percent / 100)))
                button.pack_configure(padx=(0, 6))
        self.root.update_idletasks()

    def resize_window_to_scale(self) -> None:
        # Em níveis baixos preserva uma janela utilizável e compacta o conteúdo;
        # em níveis altos amplia a janela gradualmente para acompanhar o zoom.
        if self.scale_percent <= 100:
            window_factor = 1.0
        else:
            window_factor = 1.0 + ((self.scale_percent - 100) / 100.0) * 0.45
        width = max(1000, int(round(BASE_WINDOW_WIDTH * window_factor)))
        height = max(680, int(round(BASE_WINDOW_HEIGHT * window_factor)))
        min_width = max(900, int(round(BASE_MIN_WIDTH * window_factor)))
        min_height = max(620, int(round(BASE_MIN_HEIGHT * window_factor)))
        self.root.minsize(min_width, min_height)
        try:
            x = max(0, int(self.root.winfo_x()))
            y = max(0, int(self.root.winfo_y()))
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            self.root.geometry(f"{width}x{height}")

    def apply_scale(self, percent: int, resize_window: bool = True, save: bool = True) -> None:
        if self._scaling_in_progress:
            return
        self._scaling_in_progress = True
        try:
            self.scale_percent = max(25, min(200, int(round(percent / 5) * 5)))
            # Mantém a escala nativa do Tk constante para que fontes padrão também não encolham.
            self.root.tk.call("tk", "scaling", self.base_tk_scaling)
            self.capture_scale_targets()
            self.apply_widget_scale()
            if resize_window:
                self.resize_window_to_scale()
            if hasattr(self, "scale_percent_button"):
                self.scale_percent_button.configure(text=f"{i18n.tr('ESCALA DA TELA')}: {self.scale_percent}%")
            self.refresh_scrollbars()
            if hasattr(self, "help_manager"):
                self.help_manager.refresh()
            self.root.after(80, self.refresh_scrollbars)
            self.root.after(220, self.refresh_scrollbars)
            if save:
                self.save_scale_percent()
        finally:
            self._scaling_in_progress = False

    def refresh_scrollbars(self):
        for scroll_frame in (getattr(self, "clone_scroll", None), getattr(self, "review_scroll", None), getattr(self, "converter_scroll", None), getattr(self, "format_scroll", None), getattr(self, "video_scroll", None), getattr(self, "swap_scroll", None), getattr(self, "wem_filter_scroll", None), getattr(self, "voice_clone_scroll", None)):
            if scroll_frame is not None and scroll_frame.winfo_exists():
                scroll_frame.refresh_layout()

    def change_scale(self, delta: int) -> None:
        self.apply_scale(self.scale_percent + delta)

    def set_scale_percent(self, percent: int) -> None:
        self.apply_scale(percent)

    def central_log(self, source, text, tag="normal") -> None:
        """Recebe eventos das abas sem tocar em widgets fora da thread Tk."""
        try:
            self.central_log_queue.put((str(source), str(text), str(tag)))
        except Exception:
            pass

    def project_callbacks(self):
        return {
            "central_log": self.central_log,
            "prepare_video_tools": self.prepare_shared_audio_tools,
            "select_project": self.choose_project_folder,
            "use_exe_folder": self.use_exe_folder,
            "tutorial": self.open_tutorial,
            "load_converter_from_review": self.load_converter_from_review,
            "load_converter_from_batch": self.load_converter_from_batch,
            "load_converter_from_personalized": self.load_converter_from_personalized,
            "load_voice_clone_from_format": self.load_voice_clone_from_format,
            "get_format_audio_files": self.get_format_audio_files,
            "refresh_review": self.refresh_review,
            "control_dubbing": self.control_dubbing,
            "scene_completed": self.scene_completed,
            "prepare_audio_tools": self.prepare_shared_audio_tools,
        }

    def scene_completed(self, stem, original, text, source):
        if getattr(self, '_review_refresh_running', False):
            self._review_completed_during_scan.append((stem, original, text, source))
        review = getattr(self, 'review_app', None)
        if review is not None:
            review.register_completed_scene(stem, original, text, source)

    def control_dubbing(self, source, after_scene):
        app = self.personalized_app if source == 'custom' else self.batch_app
        if not getattr(app, 'running', False):
            return
        if source == 'custom':
            if after_scene:
                app.stop_after_current = True
                app.status_var.set('A cena atual será concluída e a fila será encerrada.')
            else:
                app.cancel_generation()
        elif after_scene:
            app.stop_after_scene()
        else:
            app.cancel_run()

    def refresh_review(self):
        review = getattr(self, "review_app", None)
        if review is None or getattr(self, '_review_refresh_running', False):
            return
        self._review_refresh_running = True
        self._review_completed_during_scan = []
        project = self.project_root
        results = queue.Queue()
        audio_dir, text_dir = review_tab.AUDIO_DIR, review_tab.TEXT_DIR
        original_dir = getattr(review, 'original_text_dir', review_tab.ORIGINAL_TEXT_DIR)
        other_dir = review.other_translation_dir
        review.status_var.set('Atualizando cenas disponíveis; a dublagem continua…')
        def scan():
            try:
                results.put((True, (
                    batch_tab.find_audio_by_stem(audio_dir),
                    batch_tab.find_text_by_stem(text_dir),
                    review_tab.original_text_files(original_dir),
                    review_tab.other_translation_text_files(other_dir),
                    batch_tab.find_audio_by_stem(project / 'dublados personalizados'),
                )))
            except Exception as exc:
                results.put((False, str(exc)))
        def finish():
            if review is not getattr(self, 'review_app', None) or project != self.project_root:
                self._review_refresh_running = False
                return
            try:
                ok, data = results.get_nowait()
            except queue.Empty:
                self.root.after(100, finish)
                return
            self._review_refresh_running = False
            if not ok:
                review.status_var.set('Não foi possível atualizar a Revisão: ' + data)
                return
            previous = review.current_stem()
            audio, texts, originals, alternatives, custom = data
            review.audio_by_stem = audio
            review.text_by_stem = texts
            if original_dir == getattr(review, 'original_text_dir', review_tab.ORIGINAL_TEXT_DIR):
                review.original_text_by_stem = originals
            if other_dir == review.other_translation_dir:
                review.other_translation_by_stem = alternatives
            available = set(audio) & set(texts)
            if getattr(review, 'audio_source_mode', 'normal') == 'custom':
                available &= set(custom)
            review.default_stems = sorted(available, key=str.casefold)
            review.refresh_scene_list(preserve_stem=previous)
            # Do not reload the current editor/player: it may contain unsaved edits.
            if previous is None and review.stems and not getattr(review, 'busy', False):
                review.select_scene(0)
            review.refresh_original_folder_buttons()
            review.refresh_other_translation_folder_buttons()
            for event in self._review_completed_during_scan:
                review.register_completed_scene(*event)
            self._review_completed_during_scan = []
            review.status_var.set('Revisão atualizada. Cenas disponíveis para revisar; processamento preservado.')
        threading.Thread(target=scan, daemon=True).start()
        self.root.after(100, finish)

    def load_converter_from_review(self):
        if self.converter_app is not None:
            self.converter_app.load_from_review()
            self.select_tab(self.converter_scroll)

    def load_converter_from_batch(self):
        if self.converter_app is not None:
            self.converter_app.load_from_batch()
            self.select_tab(self.converter_scroll)

    def load_converter_from_personalized(self):
        if self.converter_app is not None:
            self.select_tab(self.converter_scroll)
            self.converter_app.load_from_personalized()

    def get_format_audio_files(self):
        """Retorna a fila atual da aba Converter Formatos sem abrir outra janela."""
        return list(getattr(self.format_app, "files", []) or [])

    def load_voice_clone_from_format(self):
        if self.voice_clone_app is not None:
            self.voice_clone_app.load_from_format_conversion(self.get_format_audio_files())
            self.select_tab(self.voice_clone_scroll)

    def ensure_project_structure(self):
        try:
            for folder_name in PROJECT_FOLDERS:
                (self.project_root / folder_name).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showwarning("Pastas do projeto", f"Não foi possível criar todas as pastas do projeto:\n{exc}", parent=self.root)

    def rebuild_views(self):
        if getattr(self.swap_app, "running", False):
            return
        if self.swap_app is not None:
            self.swap_app.close_previews()
        if getattr(self.video_app, "running", False) or getattr(self.swap_app, "running", False):
            return
        if self.video_app is not None:
            self.video_app.close_previews()
        if getattr(getattr(self, "personalized_app", None), "busy", False):
            return
        if (self.batch_app is not None and getattr(self.batch_app, "running", False)) or (self.converter_app is not None and getattr(self.converter_app, "running", False)) or (self.format_app is not None and getattr(self.format_app, "running", False)):
            return
        for old_view in (self.clone_scroll, self.review_scroll, self.personalized_scroll, self.terminal_scroll, self.converter_scroll, self.format_scroll, self.video_scroll, self.swap_scroll, self.wem_filter_scroll, self.voice_clone_scroll):
            if old_view is not None:
                old_view.destroy()

        batch_tab.configure_project_root(self.project_root)
        review_tab.configure_project_root(self.project_root)
        personalized_dubbing_tab.configure_project_root(self.project_root)
        # Corrige nomes legados antes de instanciar a Revisão, que também lê WAV ORIGINAIS.
        batch_tab.migrate_legacy_converted_wavs()
        # Não criar diretórios ao trocar/abrir o projeto; apenas atualizar as listas.
        theme = self.current_theme()
        self.clone_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.review_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.personalized_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.terminal_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.converter_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.format_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.video_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.swap_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.wem_filter_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.voice_clone_scroll = ScrollableFrame(self.content, background=theme["root"])
        self.clone_frame = self.clone_scroll.inner
        self.review_frame = self.review_scroll.inner
        self.personalized_frame = self.personalized_scroll.inner
        self.terminal_frame = self.terminal_scroll.inner
        self.converter_frame = self.converter_scroll.inner
        self.format_frame = self.format_scroll.inner
        self.video_frame = self.video_scroll.inner
        self.swap_frame = self.swap_scroll.inner
        self.wem_filter_frame = self.wem_filter_scroll.inner
        self.voice_clone_frame = self.voice_clone_scroll.inner
        self.clone_scroll.pack(fill="both", expand=True)
        self.active_scroll = self.clone_scroll
        callbacks = self.project_callbacks()
        # O BatchApp converte formatos não-WAV antes de a Revisão montar sua lista.
        # Assim, as duas abas passam a enxergar os WAVs com exatamente os mesmos stems dos TXT.
        self.batch_app = batch_tab.BatchApp(self.clone_frame, embedded=True, project_actions=callbacks)
        self.review_app = review_tab.ReviewApp(self.review_frame, embedded=True, project_actions=callbacks)
        self.personalized_app = personalized_dubbing_tab.PersonalizedDubbingApp(self.personalized_frame, embedded=True, project_root=self.project_root, project_actions=callbacks, review_app=self.review_app)
        self.batch_app.set_review_audio_target(self.review_app)
        self.terminal_app = TerminalApp(self.terminal_frame, self.root, theme, global_log_queue=self.central_log_queue, central_log_callback=self.central_log)
        duration_converter_tab.configure_project_root(self.project_root)
        self.converter_app = duration_converter_tab.DurationConverterApp(self.converter_frame, embedded=True, project_root=self.project_root, project_actions=callbacks)
        self.format_app = format_converter_tab.FormatConverterApp(self.format_frame, embedded=True, project_root=self.project_root, project_actions=callbacks)
        self.video_app = video_converter_tab.VideoConverterApp(self.video_frame, project_root=self.project_root, project_actions=callbacks)
        self.swap_app = video_audio_swap_tab.VideoAudioSwapApp(self.swap_frame, project_root=self.project_root, project_actions=callbacks)
        self.wem_filter_app = wem_filter_tab.WemFilterApp(self.wem_filter_frame, embedded=True, project_root=self.project_root, project_actions=callbacks)
        self.voice_clone_app = voice_clone_tab.VoiceClonePreprocessorApp(self.voice_clone_frame, embedded=True, project_root=self.project_root, project_actions=callbacks)
        self.apply_player_mode()
        # As três abas compartilham a mesma pasta de ferramentas e o mesmo download.
        self.converter_app.dependencies_button.configure(command=self.prepare_shared_audio_tools)
        self.format_app.dependencies_button.configure(command=self.prepare_shared_audio_tools)
        self.voice_clone_app.dependencies_button.configure(command=self.prepare_shared_audio_tools)
        self.batch_app.dependencies_button.configure(command=self.prepare_shared_audio_tools)
        self.update_project_display()
        self.update_tab_buttons()
        if not getattr(self,"_activity_timer",None):
            self._activity_timer=self.root.after(750,self.poll_tab_activity)
        self.apply_theme()
        self.apply_scale(self.scale_percent, resize_window=False, save=False)
        if hasattr(self, "language_code"):
            self.apply_language(self.language_code, save=False)

    def prepare_shared_audio_tools(self) -> None:
        apps = (self.converter_app, self.format_app, self.voice_clone_app, self.batch_app, self.video_app, self.swap_app)
        if any(getattr(app, "running", False) for app in apps):
            self.central_log("COMANDOS", "Preparação das ferramentas bloqueada: há um processamento em andamento.", "info")
            messagebox.showwarning("Ferramentas", "Aguarde o processamento atual terminar antes de preparar as ferramentas.", parent=self.root)
            return
        if any(getattr(app, "dependencies_running", False) for app in apps):
            self.central_log("COMANDOS", "Preparação das ferramentas já está em andamento.", "info")
            return
        for app in (self.format_app, self.voice_clone_app, self.batch_app):
            app.dependencies_running = True
            app.dependencies_button.configure(state="disabled")
            app.download_progress.stop()
            app.download_progress.configure(mode="determinate", value=0)
            app.download_status_var.set("Preparando ferramentas compartilhadas...")
        self.central_log("COMANDOS", "Iniciada a preparação compartilhada de FFmpeg, FFprobe e FFplay.", "info")
        self.converter_app.start_dependency_setup()
        self.sync_shared_tool_progress()

    def sync_shared_tool_progress(self) -> None:
        duration_app = self.converter_app
        shared_apps = (self.format_app, self.voice_clone_app, self.batch_app)
        try:
            status = duration_app.download_status_var.get()
            value = float(duration_app.download_progress.cget("value"))
            for app in shared_apps:
                app.download_status_var.set(status)
                try:
                    current = float(app.download_progress.cget("value"))
                except (TypeError, ValueError, tk.TclError):
                    current = 0.0
                app.download_progress.stop()
                app.download_progress.configure(mode="determinate", value=max(current, value))
            if duration_app.dependencies_running:
                self.root.after(150, self.sync_shared_tool_progress)
                return
            for app in shared_apps:
                app.dependencies_running = False
                app.dependencies_button.configure(state="normal")
            duration_app.dependencies_button.configure(state="normal")
            missing = duration_app.missing_tools()
            if not missing:
                self.central_log("COMANDOS", "Ferramentas compartilhadas preparadas com sucesso: FFmpeg, FFprobe e FFplay.", "ok")
                for app in shared_apps:
                    app.stop_tool_alert()
                    app.download_progress.stop()
                    app.download_progress.configure(mode="determinate", value=100)
                    app.download_status_var.set("Ferramentas compartilhadas prontas: FFmpeg, FFprobe e FFplay.")
                    app.status_var.set("Ferramentas prontas para usar nesta aba.")
                self.batch_app.retry_pending_audio_conversion()
            else:
                self.central_log("COMANDOS", "Falha na preparação compartilhada; ferramentas ausentes: " + ", ".join(missing), "error")
                for app in shared_apps:
                    app.start_tool_alert()
                    app.download_status_var.set("Não foi possível preparar todas as ferramentas.")
        except Exception as exc:
            self.central_log("COMANDOS", f"Erro ao sincronizar a preparação compartilhada: {exc}", "error")
            for app in (getattr(self, "format_app", None), getattr(self, "voice_clone_app", None), getattr(self, "batch_app", None)):
                if app is None:
                    continue
                app.dependencies_running = False
                try:
                    app.dependencies_button.configure(state="normal")
                except Exception:
                    pass

    def update_project_display(self):
        for entry in (getattr(self.batch_app, "project_entry", None), getattr(self.review_app, "project_entry", None), self.project_footer_entry):
            if entry is None:
                continue
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(self.project_root))
            entry.configure(state="readonly")

    def choose_project_folder(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(i18n.tr("Selecionar pasta PROJETO_DUBLAGEM"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        theme = self.current_theme()
        root_bg = theme["root"]
        dialog.configure(bg=root_bg)
        tk.Label(dialog, text=i18n.tr("Escolha a pasta que será usada como PROJETO_DUBLAGEM"), bg=root_bg, fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(14, 5))
        tk.Label(dialog, text=i18n.tr("O nome da pasta pode ser qualquer um. Depois use o botão azul para criar a estrutura."), bg=root_bg, fg=theme["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 10))
        path_var = tk.StringVar(value=str(self.project_root))
        path_row = tk.Frame(dialog, bg=root_bg)
        path_row.pack(fill="x", padx=16)
        path_entry = tk.Entry(path_row, textvariable=path_var, width=70, font=("Segoe UI", 9), bg=theme["input"], fg=theme["input_text"], insertbackground=theme["input_text"], relief="solid", bd=1)
        path_entry.pack(side="left", fill="x", expand=True)
        def browse():
            selected = filedialog.askdirectory(parent=dialog, title=i18n.tr("Escolher pasta do projeto"))
            if selected:
                path_var.set(selected)
        browse_button = tk.Button(path_row, text="Procurar...", command=browse, relief="flat", padx=9, pady=4, cursor="hand2")
        apply_button_style(browse_button, theme, "secondary")
        browse_button.pack(side="left", padx=(6, 0))
        tk.Label(dialog, text="Pastas que serão criadas: WAV ORIGINAIS, TXT TEXTO PORTUGUES, TXT TEXTO ORIGINAL, TXT TEXTO do WAV TRANSCRITO e TRADUZIDO, dublado, revisoes e REDIMENSIONAR ÁUDIO PARA CLONAR.", bg=root_bg, fg=theme["muted"], justify="left", wraplength=620, font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(8, 12))
        actions = tk.Frame(dialog, bg=root_bg)
        actions.pack(fill="x", padx=16, pady=(0, 14))
        def selected_path():
            selected = path_var.get().strip()
            if not selected:
                messagebox.showwarning("Projeto", "Informe ou procure uma pasta antes de continuar.", parent=dialog)
                return None
            return Path(selected).expanduser()
        def create_here():
            selected = selected_path()
            if selected is None:
                return
            dialog.destroy()
            self.set_project_root(selected, create_structure=True)
        def select_here():
            selected = selected_path()
            if selected is None:
                return
            dialog.destroy()
            self.set_project_root(selected, create_structure=False)
        create_button = tk.Button(actions, text="GERAR AS PASTAS DO PROJETO AQUI", command=create_here, relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=7, cursor="hand2")
        apply_button_style(create_button, theme, "primary")
        create_button.pack(side="left")
        select_button = tk.Button(actions, text="SELECIONAR ESTA PASTA", command=select_here, relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=7, cursor="hand2")
        apply_button_style(select_button, theme, "teal")
        select_button.pack(side="left", padx=(8, 0))
        cancel_button = tk.Button(actions, text="CANCELAR", command=dialog.destroy, relief="flat", padx=12, pady=7, cursor="hand2")
        apply_button_style(cancel_button, theme, "secondary")
        cancel_button.pack(side="right")
        path_entry.focus_set()
        self.root.wait_window(dialog)

    def use_exe_folder(self):
        self.set_project_root(APP_DIR, create_structure=True)

    def set_project_root(self, project_root: Path, create_structure: bool = True):
        if getattr(self.video_app, "running", False) or getattr(self.swap_app, "running", False):
            messagebox.showwarning("Vídeo em execução", "Aguarde ou cancele a conversão antes de trocar o projeto.", parent=self.root)
            return
        if getattr(getattr(self, "personalized_app", None), "busy", False):
            messagebox.showwarning("Dublagem em execução", "Aguarde a dublagem personalizada terminar antes de trocar o projeto.", parent=self.root)
            return
        if self.batch_app is not None and getattr(self.batch_app, "running", False):
            messagebox.showwarning("Dublagem em execução", "Aguarde ou cancele a fila antes de trocar a pasta do projeto.", parent=self.root)
            return
        self.project_root = Path(project_root).expanduser().resolve()
        self.root.project_root = self.project_root
        os.environ["DUBLASKIZON_PROJECT_ROOT"] = str(self.project_root)
        if create_structure:
            self.ensure_project_structure()
        self.rebuild_views()
        self.root.title(f"{i18n.tr('Dublaskizon')} — {self.project_root.name}")

    def open_tutorial(self):
        if not TUTORIAL_PATH.is_file():
            messagebox.showwarning("Tutorial", f"Não encontrei o tutorial PDF em:\n{TUTORIAL_PATH}", parent=self.root)
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(TUTORIAL_PATH))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(TUTORIAL_PATH)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(TUTORIAL_PATH)])
        except Exception as exc:
            messagebox.showerror("Tutorial", f"Não foi possível abrir o tutorial PDF:\n{exc}", parent=self.root)

    def select_tab(self, scroll_frame):
        if scroll_frame is self.active_scroll:
            self.update_tab_buttons()
            if hasattr(self, "help_manager"):
                self.help_manager.update_tab()
            return
        self.active_scroll.pack_forget()
        scroll_frame.pack(fill="both", expand=True)
        self.active_scroll = scroll_frame
        self.update_tab_buttons()
        if scroll_frame is self.review_scroll:
            self.review_app.refresh_scene_list()
            # A largura real da aba só existe depois do pack; centraliza a divisória
            # após a interface e a escala visual terminarem de se acomodar.
            self.root.after(50, self.review_app.schedule_initial_text_divider)
        elif scroll_frame is self.personalized_scroll:
            self.personalized_app.refresh_for_project()
        elif scroll_frame is self.terminal_scroll:
            self.terminal_app.refresh_for_project()
        elif scroll_frame is self.converter_scroll:
            self.converter_app.refresh_for_project()
        elif scroll_frame is self.swap_scroll:
            self.swap_app.refresh_for_project()
        elif scroll_frame is self.video_scroll:
            self.video_app.refresh_for_project()
        elif scroll_frame is self.format_scroll:
            self.format_app.refresh_for_project()
        elif scroll_frame is self.wem_filter_scroll:
            self.wem_filter_app.refresh_for_project()
        elif scroll_frame is self.voice_clone_scroll:
            self.voice_clone_app.refresh_for_project()
        if hasattr(self, "help_manager"):
            self.help_manager.update_tab()

    def poll_tab_activity(self):
        if not self.root.winfo_exists(): return
        self._activity_blink = not getattr(self, '_activity_blink', False)
        self.update_tab_buttons()
        for name, app_name in (("clone","batch_app"),("review","review_app"),("personalized","personalized_app"),
                               ("converter","converter_app"),("format","format_app"),("video","video_app"),
                               ("swap","swap_app"),("wem_filter","wem_filter_app"),("voice_clone","voice_clone_app")):
            app=getattr(self,app_name,None)
            active=any(bool(getattr(app,flag,False)) for flag in ('running','busy','dependencies_running','_scan_running'))
            if active and self.active_scroll is not getattr(self,name+'_scroll',None) and self._activity_blink:
                button=getattr(self,name+'_tab_button',None)
                if button is not None:button.configure(bg='#FBBF24',fg='#111827')
        process=getattr(getattr(self,'terminal_app',None),'process',None)
        if process is not None and process.poll() is None and self.active_scroll is not self.terminal_scroll and self._activity_blink:
            self.commands_tab_button.configure(bg='#FBBF24',fg='#111827')
        self._activity_timer=self.root.after(750,self.poll_tab_activity)

    def update_tab_buttons(self):
        theme = self.current_theme()
        tab_states = (
            (self.clone_tab_button, self.active_scroll is self.clone_scroll),
            (self.review_tab_button, self.active_scroll is self.review_scroll),
            (self.personalized_tab_button, self.active_scroll is self.personalized_scroll),
            (self.converter_tab_button, self.active_scroll is self.converter_scroll),
            (self.format_tab_button, self.active_scroll is self.format_scroll),
            (self.video_tab_button, self.active_scroll is self.video_scroll),
            (self.swap_tab_button, self.active_scroll is self.swap_scroll),
            (self.wem_filter_tab_button, self.active_scroll is self.wem_filter_scroll),
            (self.voice_clone_tab_button, self.active_scroll is self.voice_clone_scroll),
            (self.commands_tab_button, self.active_scroll is self.terminal_scroll),
        )
        for widget, selected in tab_states:
            apply_button_style(widget, theme, "tab_active" if selected else "tab_inactive")
            widget.configure(relief="sunken" if selected else "raised")

    def close(self):
        if getattr(self.swap_app, "running", False):
            if messagebox.askyesno("Troca de áudio", "Cancelar a operação? Aguarde o cancelamento e feche novamente.", parent=self.root):
                self.swap_app.cancel_run()
            return
        if self.swap_app is not None:
            self.swap_app.close_previews()
        if getattr(self.video_app, "running", False) or getattr(self.swap_app, "running", False):
            if messagebox.askyesno("Conversão de vídeo", "Cancelar a conversão? Aguarde a conclusão do cancelamento e feche novamente.", parent=self.root):
                self.video_app.cancel_run()
            return
        if self.video_app is not None:
            self.video_app.close_previews()
        if hasattr(self, "help_manager"):
            self.help_manager.close()
        batch_running = getattr(self.batch_app, "running", False)
        converter_running = getattr(self.converter_app, "running", False)
        format_running = getattr(self.format_app, "running", False)
        if batch_running or converter_running or format_running:
            activity = "dublagem" if batch_running else ("conversão de duração" if converter_running else "conversão de formatos")
            answer = messagebox.askyesno("Sair", f"A {activity} ainda está em execução. Cancelar e fechar?", parent=self.root)
            if not answer:
                return
            if batch_running:
                self.batch_app.cancel_run()
            if converter_running:
                self.converter_app.cancel_run()
            if format_running:
                self.format_app.cancel_run()
            self.root.after(500, self.root.destroy)
            return
        self.root.destroy()


def main() -> int:
    if not batch_tab.TK_AVAILABLE or not review_tab.TK_AVAILABLE or not duration_converter_tab.TK_AVAILABLE or not format_converter_tab.TK_AVAILABLE or Tk is None:
        print("ERRO: Tkinter não está disponível neste Python.")
        return 2
    configure_windows_app_identity()
    root = TkinterDnD.Tk() if TkinterDnD is not None else Tk()
    apply_window_icon(root)
    DublaskizonApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
