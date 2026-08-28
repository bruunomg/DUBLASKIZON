"""Filtro universal de renomeação para qualquer tipo de arquivo.

A aba somente renomeia arquivos no mesmo diretório. Ela não copia, move,
converte nem cria diretórios. As regras incorporam os padrões encontrados nos
scripts fornecidos: IDs entre parênteses, IDs após '#', arquivos Wwise
'123_convertido_HASH', sufixos '.created'/'_dublado' e mapas Wwise
Name -> ID.
"""
from __future__ import annotations

import os
import re
import subprocess
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from tkinter import END, StringVar, Text, filedialog, messagebox, simpledialog, ttk
from tkinter import Button, Checkbutton, Entry, Frame, Label, Listbox, Scrollbar

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = "DND_Files"

try:
    from ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles
except ImportError:
    from .ui_theme import apply_button_style, apply_button_style_to_tree, configure_ttk_button_styles

try:
    import i18n
except ImportError:
    from . import i18n

messagebox = i18n.localized_messagebox(messagebox)
simpledialog = i18n.localized_simpledialog(simpledialog)


TITLE = "FILTRO de RENOMEAR ARQUIVOS .WEM"
RULE_CHOICES = (
    "Inteligente (IDs + Wwise + mapa)",
    "Extrair ID: (123), #123 ou [123]",
    "Wwise pós-processado: 123_convertido_HASH",
    "Remover sufixos Wwise: .created / _dublado",
    "Usar nome base sem sufixos",
)
PADDING_CHOICES = ("0", "1", "2", "3", "4", "5")
Wwise_SUFFIX_RE = re.compile(r"(?:\.created|_dublado|_dubbed)$", re.IGNORECASE)
Wwise_CONVERTED_RE = re.compile(r"^(\d+)_convertido_([0-9a-f]+)$", re.IGNORECASE)


@dataclass
class RenamePlan:
    source: Path
    target: Path
    status: str
    reason: str



def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def read_text_flexibly(path: Path) -> str:
    raw = path.read_bytes()
    candidates: list[tuple[int, str]] = []
    encodings = ("utf-16", "utf-8-sig", "utf-8", "latin-1")
    for encoding in encodings:
        try:
            decoded = raw.decode(encoding).replace("\x00", "")
        except UnicodeDecodeError:
            continue
        score = 0
        if "Streamed Audio" in decoded:
            score += 100
        if "ID" in decoded and "Name" in decoded:
            score += 50
        if "\t" in decoded:
            score += 10
        score += sum(1 for char in decoded if char.isprintable() or char in "\n\r\t") // 100
        candidates.append((score, decoded))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return raw.decode("utf-8", errors="replace")


def parse_wwise_name_id_map(path: Path) -> dict[str, str]:
    """Lê tabelas Wwise com colunas ID/Name em UTF-16, UTF-8 ou Latin-1."""
    content = read_text_flexibly(path)
    relevant = content.split("Streamed Audio", 1)[-1] if "Streamed Audio" in content else content
    mapping: dict[str, str] = {}
    for line in relevant.splitlines():
        if not line.strip() or "ID" in line and "Name" in line:
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 2:
            parts = [part.strip() for part in re.split(r"\s{2,}", line) if part.strip()]
        if len(parts) < 2:
            continue
        numeric_index = next((index for index, part in enumerate(parts[:3]) if part.isdigit()), None)
        if numeric_index is None or numeric_index + 1 >= len(parts):
            continue
        audio_id = parts[numeric_index]
        name = parts[numeric_index + 1]
        if name:
            mapping[normalize_key(name)] = audio_id
    return mapping


def extract_id(stem: str) -> tuple[str | None, str]:
    """Retorna ID e explicação, priorizando padrões Wwise mais confiáveis."""
    match = Wwise_CONVERTED_RE.fullmatch(stem)
    if match:
        return match.group(1), "padrão Wwise pós-processado"
    for pattern, description in (
        (r"\((\d+)\)", "ID entre parênteses"),
        (r"#(\d+)(?:$|[^0-9])", "ID após #"),
        (r"\[(\d+)\]", "ID entre colchetes"),
        (r"(?:^|[_\-\s])id[_\-\s]*(\d+)(?:$|[_\-\s])", "ID identificado pelo rótulo"),
    ):
        match = re.search(pattern, stem, re.IGNORECASE)
        if match:
            return match.group(1), description
    if stem.isdigit():
        return stem, "nome já composto apenas por ID"
    trailing = re.search(r"(?:^|[^0-9])(\d+)$", stem)
    if trailing:
        return trailing.group(1), "número final do nome"
    return None, "nenhum ID confiável encontrado"


def strip_wwise_suffix(stem: str) -> str:
    return Wwise_SUFFIX_RE.sub("", stem)


def parse_drop_paths(raw: str, tk_root=None) -> list[Path]:
    if not raw:
        return []
    try:
        values = list(tk_root.tk.splitlist(raw)) if tk_root is not None else [raw]
    except Exception:
        values = [raw]
    paths: list[Path] = []
    for value in values:
        cleaned = str(value).strip().strip('"')
        if cleaned:
            paths.append(Path(cleaned).expanduser())
    return paths


class WemFilterApp:
    TITLE = TITLE

    def __init__(self, root, embedded=True, project_root: Path | None = None, project_actions=None):
        self.root = root
        self.embedded = embedded
        self.project_actions = project_actions or {}
        self.central_log_callback = self.project_actions.get("central_log")
        self.project_root = Path(project_root or getattr(root, "project_root", Path.cwd())).expanduser().resolve()
        self.theme = {
            "mode": "claro", "root": "#F5F6FA", "surface": "#FFFFFF", "text": "#1F2937",
            "muted": "#64748B", "input": "#FFFFFF", "input_text": "#1F2937", "select": "#DBEAFE",
        }
        self.files: list[Path] = []
        self.plan: list[RenamePlan] = []
        self.last_changes: list[tuple[Path, Path]] = []
        self.rename_history: list[tuple[Path, Path]] = []
        self.name_id_map: dict[str, str] = {}
        self.pcvr_to_standalone: dict[str, str] = {}
        self.loaded_map_files: list[Path] = []
        self.id_offset = 0
        self.operation_scope_paths: set[Path] = set()
        self.preview_flash_after_id = None
        self.preview_header_drag = None
        self.source_dir: Path = self.project_root
        self.source_var = StringVar(value=str(self.source_dir))
        self.rule_var = StringVar(value=RULE_CHOICES[0])
        self.padding_var = StringVar(value="0")
        self.recursive_var = StringVar(value="0")
        self.selected_only_var = StringVar(value="0")
        self.strip_suffix_var = StringVar(value="1")
        self.use_map_var = StringVar(value="1")
        self.id_adjust_var = StringVar(value="Ajuste atual do ID: 0")
        self.map_var = StringVar(value="Nenhum mapa Wwise carregado")
        self.status_var = StringVar(value="Escolha uma pasta ou adicione arquivos de qualquer extensão.")
        self.summary_var = StringVar(value="Arquivos: 0 | Prontos: 0 | Conflitos: 0 | Sem alteração: 0")
        self.build_ui()
        self.refresh_for_project()

    def apply_language(self, language: str | None = None):
        """Atualiza textos próprios da aba sem traduzir nomes de arquivos ou ConversionMap.txt."""
        language = i18n.set_current_language(language or i18n.CURRENT_LANGUAGE)
        heading_sources = {"status": "Estado", "old": "Nome atual", "new": "Novo nome", "reason": "Inteligência aplicada"}
        for column, source in heading_sources.items():
            self.preview_tree.heading(column, text=i18n.tr(source, language))
        if hasattr(self, "preview_title_label"):
            title = i18n.tr("PRÉ-VISUALIZAÇÃO", language) + "  |  " + "  |  ".join(i18n.tr(source, language) for source in heading_sources.values())
            self.preview_title_label.configure(text=title)
        self._update_id_adjust_label()
        self.generate_preview()

    def build_ui(self):
        header = Frame(self.root, bg="#F5F6FA")
        header.pack(fill="x", padx=16, pady=(8, 3))
        Label(header, text=self.TITLE, bg="#F5F6FA", fg="#1F2937", font=("Segoe UI", 14, "bold")).pack(side="left")
        Label(header, text="  Renomeação segura e inteligente para qualquer arquivo", bg="#F5F6FA", fg="#64748B", font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))

        source_panel = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        source_panel.pack(fill="x", padx=16, pady=(0, 7))
        Label(source_panel, text="LOCAL DA PASTA DE ORIGEM — usado para ABRIR PASTA e salvar ConversionMap.txt", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        self.source_entry = Entry(source_panel, textvariable=self.source_var, state="readonly", readonlybackground="#FFFFFF", fg="#64748B", relief="flat", font=("Segoe UI", 8))
        self.source_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=(10, 6), pady=(0, 7))
        self.choose_folder_button = Button(source_panel, text="ABRIR PASTA", command=self.choose_folder, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.choose_folder_button, self.theme, "primary")
        self.choose_folder_button.grid(row=0, column=3, rowspan=2, padx=(0, 4), pady=7)
        self.add_files_button = Button(source_panel, text="ABRIR ARQUIVOS", command=self.add_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.add_files_button, self.theme, "secondary")
        self.add_files_button.grid(row=0, column=4, rowspan=2, padx=4, pady=7)
        self.load_project_button = Button(source_panel, text="CARREGAR PROJETO", command=self.load_project_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.load_project_button, self.theme, "teal")
        self.load_project_button.grid(row=0, column=5, rowspan=2, padx=4, pady=7)
        self.generate_txt_button = Button(source_panel, text="GERAR TXT IDs + NOMES", command=self.generate_names_txt, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.generate_txt_button, self.theme, "warning")
        self.generate_txt_button.grid(row=0, column=6, rowspan=2, padx=4, pady=7)
        self.clear_button = Button(source_panel, text="LIMPAR ARQUIVOS CARREGADOS", command=self.clear_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=9, pady=4, cursor="hand2")
        apply_button_style(self.clear_button, self.theme, "danger")
        self.clear_button.grid(row=0, column=7, rowspan=2, padx=(4, 10), pady=7)
        self.drop_hint = Label(source_panel, text="Você também pode arrastar arquivos ou pastas para esta área.", bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w")
        self.drop_hint.grid(row=2, column=0, columnspan=8, sticky="w", padx=10, pady=(0, 7))
        source_panel.grid_columnconfigure(0, weight=1)
        source_panel.grid_columnconfigure(1, weight=1)
        source_panel.grid_columnconfigure(2, weight=1)

        options = Frame(self.root, bg="#FFFFFF", bd=1, relief="solid")
        options.pack(fill="x", padx=16, pady=(0, 7))
        Label(options, text="Inteligência de renomeação", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=(8, 2))
        self.rule_combo = ttk.Combobox(options, textvariable=self.rule_var, values=list(RULE_CHOICES), state="readonly", width=46)
        self.rule_combo.grid(row=1, column=0, sticky="ew", padx=(10, 6), pady=(0, 8))
        self.rule_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_rule_changed())
        Label(options, text="Largura do ID (0 = original)", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6, pady=(8, 2))
        self.padding_combo = ttk.Combobox(options, textvariable=self.padding_var, values=list(PADDING_CHOICES), state="readonly", width=12)
        self.padding_combo.grid(row=1, column=1, sticky="w", padx=6, pady=(0, 8))
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(2, weight=1)
        options.grid_columnconfigure(4, weight=0)
        self.recursive_check = ttk.Checkbutton(options, text="Incluir subpastas", variable=self.recursive_var, onvalue="1", offvalue="0", command=self.on_scope_changed)
        self.recursive_check.grid(row=1, column=2, sticky="w", padx=6, pady=(0, 8))
        self.selected_only_check = ttk.Checkbutton(options, text="Renomear somente selecionados", variable=self.selected_only_var, onvalue="1", offvalue="0", command=self.generate_preview)
        self.selected_only_check.grid(row=1, column=3, sticky="w", padx=6, pady=(0, 8))
        self.strip_suffix_check = ttk.Checkbutton(options, text="Limpar sufixos Wwise", variable=self.strip_suffix_var, onvalue="1", offvalue="0", command=self.generate_preview)
        self.strip_suffix_check.grid(row=2, column=0, columnspan=2, sticky="w", padx=(10, 6), pady=(0, 8))
        self.use_map_check = ttk.Checkbutton(options, text="Usar mapa Name → ID", variable=self.use_map_var, onvalue="1", offvalue="0", command=self.generate_preview)
        self.use_map_check.grid(row=2, column=2, sticky="w", padx=6, pady=(0, 8))
        self.load_map_button = Button(options, text="CARREGAR MAPA(S) WWISE", command=self.load_mapping, relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=3, cursor="hand2")
        apply_button_style(self.load_map_button, self.theme, "warning")
        self.load_map_button.grid(row=2, column=3, sticky="e", padx=(6, 4), pady=(0, 8))
        self.clear_map_button = Button(options, text="LIMPAR MAPA", command=self.clear_mapping, relief="flat", font=("Segoe UI", 8, "bold"), padx=7, pady=3, cursor="hand2")
        apply_button_style(self.clear_map_button, self.theme, "secondary")
        self.clear_map_button.grid(row=2, column=4, sticky="e", padx=(0, 10), pady=(0, 8))
        Label(options, text="Ajuste numérico dos IDs", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold"), anchor="w").grid(row=3, column=0, sticky="w", padx=(10, 6), pady=(0, 3))
        adjust_buttons = Frame(options, bg="#FFFFFF")
        adjust_buttons.grid(row=4, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 5))
        # Ordem padronizada por sinal: reduções vermelhas, aumentos azuis,
        # seguidos pelo valor personalizado em cinza.
        self.id_minus_ten_button = Button(adjust_buttons, text="−10", command=lambda: self.apply_id_offset(-10), relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2")
        apply_button_style(self.id_minus_ten_button, self.theme, "danger")
        self.id_minus_ten_button.pack(side="left", padx=(0, 5))
        self.id_minus_one_button = Button(adjust_buttons, text="−1", command=lambda: self.apply_id_offset(-1), relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2")
        apply_button_style(self.id_minus_one_button, self.theme, "danger")
        self.id_minus_one_button.pack(side="left", padx=5)
        self.id_plus_one_button = Button(adjust_buttons, text="+1", command=lambda: self.apply_id_offset(1), relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2")
        apply_button_style(self.id_plus_one_button, self.theme, "primary")
        self.id_plus_one_button.pack(side="left", padx=5)
        self.id_plus_ten_button = Button(adjust_buttons, text="+10", command=lambda: self.apply_id_offset(10), relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2")
        apply_button_style(self.id_plus_ten_button, self.theme, "primary")
        self.id_plus_ten_button.pack(side="left", padx=5)
        self.id_custom_button = Button(adjust_buttons, text="VALOR PERSONALIZADO", command=self.choose_custom_id_offset, relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2")
        apply_button_style(self.id_custom_button, self.theme, "secondary")
        self.id_custom_button.pack(side="left", padx=5)
        Label(options, textvariable=self.id_adjust_var, bg="#FFFFFF", fg="#475569", font=("Segoe UI", 8, "bold"), anchor="w").grid(row=5, column=0, columnspan=5, sticky="w", padx=10, pady=(0, 3))
        Label(options, textvariable=self.map_var, bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8), anchor="w").grid(row=6, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 7))

        lists = Frame(self.root, bg="#F5F6FA")
        lists.pack(fill="both", expand=True, padx=16, pady=(0, 7))
        self.panel_split = ttk.Panedwindow(lists, orient="horizontal")
        self.panel_split.pack(fill="both", expand=True)
        left = Frame(self.panel_split, bg="#FFFFFF", bd=1, relief="solid")
        self.panel_split.add(left, weight=1)
        Label(left, text="Arquivos carregados — qualquer extensão", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=10, pady=(8, 4))
        file_list_frame = Frame(left, bg="#FFFFFF")
        file_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.file_list = Listbox(file_list_frame, selectmode="extended", activestyle="none", exportselection=False, bg="#FFFFFF", fg="#1F2937", selectbackground="#DBEAFE", selectforeground="#1F2937", font=("Segoe UI", 9))
        file_scroll = Scrollbar(file_list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=file_scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        file_scroll.pack(side="right", fill="y")
        self.file_list.bind("<<ListboxSelect>>", lambda _event: self.generate_preview())
        self.enable_drag_drop(self.file_list)

        right = Frame(self.panel_split, bg="#FFFFFF", bd=1, relief="solid")
        self.panel_split.add(right, weight=1)
        self.preview_title_label = Label(right, text="PRÉ-VISUALIZAÇÃO  |  Estado  |  Nome atual  |  Novo nome  |  Inteligência aplicada", bg="#FFFFFF", fg="#1F2937", font=("Segoe UI", 9, "bold"), anchor="w")
        self.preview_title_label.pack(fill="x", padx=10, pady=(8, 4))
        tree_frame = Frame(right, bg="#FFFFFF")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        columns = ("status", "old", "new", "reason")
        self.preview_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        headings = {"status": "Estado", "old": "Nome atual", "new": "Novo nome", "reason": "Inteligência aplicada"}
        widths = {"status": 92, "old": 190, "new": 190, "reason": 215}
        for column in columns:
            self.preview_tree.heading(column, text=headings[column])
            self.preview_tree.column(column, width=widths[column], minwidth=70, anchor="w")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=tree_scroll.set)
        self.preview_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.preview_tree.tag_configure("ok", foreground="#15803D")
        self.preview_tree.tag_configure("new_flash", foreground="#FFFFFF", background="#16A34A")
        self.preview_tree.tag_configure("renamed", foreground="#FFFFFF", background="#15803A")
        self.preview_tree.tag_configure("conflict", foreground="#B91C1C")
        self.preview_tree.tag_configure("skip", foreground="#64748B")
        self.enable_drag_drop(self.preview_tree)

        actions = Frame(self.root, bg="#F5F6FA")
        actions.pack(fill="x", padx=16, pady=(0, 5))
        self.process_all_button = Button(actions, text="GERAR ConversionMap.txt", command=self.generate_conversion_map_txt, relief="flat", font=("Segoe UI", 8, "bold"), padx=12, pady=5, cursor="hand2")
        apply_button_style(self.process_all_button, self.theme, "accent")
        self.process_all_button.pack(side="left", padx=(0, 5))
        self.rename_button = Button(actions, text="RENOMEAR COM SEGURANÇA", command=self.rename_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=10, pady=5, cursor="hand2")
        apply_button_style(self.rename_button, self.theme, "success")
        self.rename_button.pack(side="left", padx=5)
        self.undo_button = Button(actions, text="DESFAZER ÚLTIMA RENOMEAÇÃO", command=self.undo_last, relief="flat", font=("Segoe UI", 8, "bold"), padx=10, pady=5, cursor="hand2")
        apply_button_style(self.undo_button, self.theme, "warning")
        self.undo_button.pack(side="left", padx=5)
        self.save_renamed_button = Button(actions, text="SALVAR RENOMEADOS", command=self.save_renamed_files, relief="flat", font=("Segoe UI", 8, "bold"), padx=10, pady=5, cursor="hand2")
        apply_button_style(self.save_renamed_button, self.theme, "secondary")
        self.save_renamed_button.pack(side="left", padx=5)
        self.open_folder_button = Button(actions, text="ABRIR PASTA", command=self.open_source_folder, relief="flat", font=("Segoe UI", 8, "bold"), padx=10, pady=5, cursor="hand2")
        apply_button_style(self.open_folder_button, self.theme, "teal")
        self.open_folder_button.pack(side="right")

        Label(self.root, textvariable=self.summary_var, bg="#F5F6FA", fg="#475569", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=16)
        Label(self.root, textvariable=self.status_var, bg="#F5F6FA", fg="#64748B", anchor="w").pack(fill="x", padx=16, pady=(2, 2))
        self.log_box = Text(self.root, height=5, wrap="word", state="disabled", font=("Consolas", 8), background="#111827", foreground="#E5E7EB")
        self.log_box.pack(fill="x", padx=16, pady=(0, 10))
        self.enable_drag_drop(self.root)

    def apply_theme(self, theme):
        self.theme = {**self.theme, **theme}
        root_bg = self.theme.get("root", "#F5F6FA")
        surface = self.theme.get("surface", "#FFFFFF")
        text = self.theme.get("text", "#1F2937")
        input_bg = self.theme.get("input", surface)
        input_fg = self.theme.get("input_text", text)
        select = self.theme.get("select", "#DBEAFE")
        try:
            style = ttk.Style(self.root)
            configure_ttk_button_styles(style, self.theme)
            style.configure("TFrame", background=surface)
            style.configure("TLabel", background=surface, foreground=text)
            style.configure("TCheckbutton", background=surface, foreground=text)
            style.map("TCheckbutton", background=[("active", surface)], foreground=[("disabled", self.theme.get("muted", "#64748B")), ("active", text)])
            style.configure("TCombobox", fieldbackground=input_bg, background=input_bg, foreground=input_fg, arrowcolor=input_fg)
            style.map("TCombobox", fieldbackground=[("readonly", input_bg)], foreground=[("readonly", input_fg)], selectbackground=[("readonly", select)], selectforeground=[("readonly", input_fg)])
            style.configure("Filter.Treeview", background=input_bg, fieldbackground=input_bg, foreground=input_fg, rowheight=25, borderwidth=0)
            style.map("Filter.Treeview", background=[("selected", select)], foreground=[("selected", input_fg)])
            style.configure("Filter.Treeview.Heading", background=self.theme.get("border", "#CBD5E1"), foreground=text, relief="flat", padding=(6, 5))
            style.map("Filter.Treeview.Heading", background=[("active", self.theme.get("border", "#CBD5E1"))])
            self.preview_tree.configure(style="Filter.Treeview")
        except Exception:
            pass

        def visit(widget):
            try:
                cls = widget.winfo_class()
                if cls == "Frame":
                    widget.configure(bg=surface)
                elif cls == "Label":
                    widget.configure(bg=surface, fg=text)
                elif cls == "Entry":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg, readonlybackground=input_bg)
                elif cls == "Listbox":
                    widget.configure(bg=input_bg, fg=input_fg, selectbackground=select, selectforeground=input_fg)
                elif cls == "Text":
                    widget.configure(bg=input_bg, fg=input_fg, insertbackground=input_fg)
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    visit(child)
            except Exception:
                pass
        visit(self.root)
        apply_button_style_to_tree(self.root, self.theme)
        self.preview_tree.tag_configure("ok", foreground=self.theme.get("success_text", self.theme.get("text", "#15803D")))
        self.preview_tree.tag_configure("conflict", foreground=self.theme.get("danger_text", "#B91C1C"))
        self.preview_tree.tag_configure("skip", foreground=self.theme.get("muted", "#64748B"))

    def refresh_for_project(self):
        new_root = Path(getattr(self.root, "project_root", self.project_root)).expanduser().resolve()
        self.project_root = new_root
        if not self.files:
            self.source_dir = new_root
            self.source_var.set(str(self.source_dir))
        self.status_var.set("Escolha uma pasta ou adicione arquivos de qualquer extensão.")

    def on_scope_changed(self):
        if self.files and self.source_var.get():
            source = Path(self.source_var.get())
            if source.is_dir():
                self.set_files(self.collect_files(source), str(source))
        self.generate_preview()

    def collect_files(self, folder: Path) -> list[Path]:
        iterator = folder.rglob("*") if self.recursive_var.get() == "1" else folder.iterdir()
        return sorted((path for path in iterator if path.is_file()), key=lambda path: str(path).casefold())

    def choose_folder(self):
        selected = filedialog.askdirectory(parent=self.root, title="Escolher pasta com arquivos para renomear")
        if selected:
            folder = Path(selected).expanduser().resolve()
            self.set_files(self.collect_files(folder), str(folder))

    def load_project_files(self):
        folder = self.project_root
        if not folder.is_dir():
            messagebox.showwarning("Projeto", f"A pasta do projeto não existe:\n{folder}", parent=self.root)
            return
        self.set_files(self.collect_files(folder), str(folder))

    def add_files(self):
        selected = filedialog.askopenfilenames(parent=self.root, title="Adicionar arquivos de qualquer extensão", filetypes=[("Todos os arquivos", "*.*")])
        if selected:
            current = list(self.files)
            seen = {str(path.resolve()).casefold() for path in current}
            for raw in selected:
                path = Path(raw).expanduser().resolve()
                if path.is_file() and str(path).casefold() not in seen:
                    current.append(path)
                    seen.add(str(path).casefold())
            self.set_files(current, "Arquivos selecionados")
            self._select_loaded_paths([Path(raw).expanduser().resolve() for raw in selected])
            self.generate_preview()

    def enable_drag_drop(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda event: self.handle_drop(event.data))
            return True
        except Exception:
            return False

    def _select_loaded_paths(self, paths: list[Path]) -> None:
        selected_keys = {str(Path(path).expanduser().resolve()).casefold() for path in paths}
        self.file_list.selection_clear(0, END)
        for index, loaded in enumerate(self.files):
            if str(loaded.resolve()).casefold() in selected_keys:
                self.file_list.selection_set(index)
        self.operation_scope_paths = {path for path in self.files if str(path.resolve()).casefold() in selected_keys}
        if selected_keys:
            self.selected_only_var.set("1")

    def handle_drop(self, raw: str):
        found: list[Path] = []
        dropped_folders: list[Path] = []
        for path in parse_drop_paths(raw, self.root):
            path = path.expanduser().resolve()
            if path.is_dir():
                dropped_folders.append(path)
                found.extend(self.collect_files(path))
            elif path.is_file():
                found.append(path)
        if not found:
            self.status_var.set("Nenhum arquivo válido foi encontrado no item arrastado.")
            return
        current = list(self.files)
        seen = {str(path).casefold() for path in current}
        for path in found:
            key = str(path).casefold()
            if key not in seen:
                current.append(path)
                seen.add(key)
        source_label = str(dropped_folders[0]) if len(dropped_folders) == 1 and not self.files else "Itens arrastados"
        self.set_files(current, source_label)
        # Arquivos recém-arrastados ficam selecionados e entram no modo seguro;
        # itens que já estavam na lista não participam por acidente.
        self._select_loaded_paths(found)
        self.generate_preview()
        self.status_var.set(f"{len(found)} arquivo(s) encontrado(s) por arrastar-e-soltar; somente os recém-selecionados serão tratados.")

    def infer_source_dir(self, files: list[Path], source_label: str) -> Path:
        """Determina a pasta real para abrir e salvar saídas, nunca um rótulo textual."""
        labeled = Path(source_label).expanduser()
        if labeled.is_dir():
            return labeled.resolve()
        parents = [path.parent.resolve() for path in files if path.is_file()]
        if not parents:
            return self.source_dir if self.source_dir.is_dir() else self.project_root
        try:
            common = Path(os.path.commonpath([str(parent) for parent in parents]))
            return common if common.is_dir() else parents[0]
        except (ValueError, OSError):
            return parents[0]

    def set_files(self, files: list[Path], source_label: str):
        self.files = []
        seen: set[str] = set()
        for raw in files:
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                continue
            key = str(path).casefold()
            if key not in seen:
                self.files.append(path)
                seen.add(key)
        self.files.sort(key=lambda path: str(path).casefold())
        self.operation_scope_paths = set(self.files)
        self.source_dir = self.infer_source_dir(self.files, source_label)
        self.source_var.set(str(self.source_dir))
        self.file_list.delete(0, END)
        base = self.source_dir if self.source_dir.is_dir() else None
        for path in self.files:
            # A lista mostra somente o nome; a pasta real fica no campo superior.
            self.file_list.insert(END, path.name)
        self.generate_preview()

    def clear_files(self):
        self.files = []
        self.plan = []
        self.operation_scope_paths = set()
        self.selected_only_var.set("0")
        self.file_list.delete(0, END)
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.summary_var.set("Arquivos: 0 | Prontos: 0 | Conflitos: 0 | Sem alteração: 0")
        self.status_var.set("Arquivos carregados removidos da lista. Nenhum arquivo do disco foi alterado.")

    def generate_conversion_map_txt(self) -> bool:
        """Trata os nomes e gera um único ConversionMap.txt com os IDs tratados.

        Qualquer extensão é aceita. Para cada arquivo, a função aplica a regra
        atual ao nome e usa o nome tratado previsto, mesmo que a renomeação
        ainda não tenha sido confirmada. O arquivo mantém o padrão original:
        somente IDs tratados, um por linha, sem cabeçalho, extensão ou caminho.
        """
        source = self.source_dir if self.source_dir.is_dir() else Path(self.source_var.get()).expanduser()
        if not self.files:
            if source.is_dir():
                self.set_files(self.collect_files(source), str(source))
            else:
                messagebox.showinfo("ConversionMap.txt", "Escolha uma pasta ou abra arquivos primeiro.", parent=self.root)
                return False

        # Recalcula os alvos para que o mapa reflita os nomes que serão usados
        # mesmo antes de clicar em RENOMEAR COM SEGURANÇA.
        self.generate_preview()
        planned_by_source = {item.source: item for item in self.plan}
        ids: list[str] = []
        without_id: list[str] = []
        for path in self.files:
            item = planned_by_source.get(path)
            final_stem = item.target.stem if item is not None else path.stem
            final_id, _reason = extract_id(final_stem)
            if final_id:
                ids.append(final_id)
            else:
                without_id.append(path.name)

        if not ids:
            messagebox.showinfo("ConversionMap.txt", "Nenhum ID foi encontrado nos arquivos carregados ou nos nomes finais previstos.", parent=self.root)
            self.status_var.set("ConversionMap.txt não gerado: nenhum ID encontrado.")
            return False

        output_dir = self.source_dir if self.source_dir.is_dir() else self.files[0].parent
        output_path = output_dir / "ConversionMap.txt"
        content = "\n".join(ids) + "\n"
        try:
            output_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("ConversionMap.txt", f"Não foi possível gerar o arquivo:\n{exc}", parent=self.root)
            return False
        detail = f" {len(without_id)} arquivo(s) sem ID foram ignorados." if without_id else ""
        self.append_log(f"ConversionMap.txt tratado gerado: {len(ids)} ID(s).{detail}")
        self.status_var.set(f"ConversionMap.txt tratado gerado com {len(ids)} ID(s): {output_path}{detail}")
        messagebox.showinfo("ConversionMap.txt", f"Arquivo único gerado com {len(ids)} ID(s) tratados:\n{output_path}{detail}", parent=self.root)
        return True

    def generate_names_txt(self, output_path: Path | None = None) -> bool:
        if not self.files:
            self.status_var.set("Adicione arquivos antes de gerar o TXT de IDs e nomes.")
            return False
        if output_path is None:
            base = Path(self.source_var.get())
            initial_dir = str(base if base.is_dir() else self.project_root)
            selected = filedialog.asksaveasfilename(
                parent=self.root,
                title="Salvar TXT com IDs e nomes",
                initialdir=initial_dir,
                initialfile="ConversionMap.txt",
                defaultextension=".txt",
                filetypes=[("Arquivo TXT", "*.txt"), ("Todos os arquivos", "*.*")],
            )
            if not selected:
                return False
            output_path = Path(selected).expanduser().resolve()
        rows = ["ID\tNOME_BASE\tARQUIVO\tEXTENSÃO\tCAMINHO_RELATIVO"]
        for path in self.files:
            extracted, _reason = extract_id(path.stem)
            try:
                relative = str(path.relative_to(Path(self.source_var.get())))
            except (ValueError, OSError):
                relative = str(path)
            rows.append("\t".join((extracted or "", path.stem, path.name, path.suffix or "(sem extensão)", relative)))
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")
        except OSError as exc:
            messagebox.showerror("Gerar TXT", f"Não foi possível salvar o TXT:\n{exc}", parent=self.root)
            return False
        self.append_log(f"TXT de IDs e nomes gerado: {output_path.name} ({len(self.files)} arquivo(s)).")
        self.status_var.set(f"TXT gerado com {len(self.files)} arquivo(s): {output_path}")
        return True

    def on_rule_changed(self):
        self.generate_preview()

    def _update_id_adjust_label(self):
        value = f"{self.id_offset:+d}" if self.id_offset else "0"
        self.id_adjust_var.set(i18n.tr(f"Ajuste atual do ID: {value}"))

    def apply_id_offset(self, amount: int):
        """Acumula um passo predefinido e recalcula a prévia imediatamente."""
        self.id_offset += int(amount)
        self._update_id_adjust_label()
        value = f"{self.id_offset:+d}" if self.id_offset else "0"
        self.status_var.set(i18n.tr(f"Ajuste de ID {value} aplicado somente na prévia. Nada foi renomeado."))
        self.append_log(f"Ajuste numérico acumulado: {value}; aplicado somente na prévia.")
        self.generate_preview()

    def set_id_offset(self, value: int):
        """Define exatamente o ajuste digitado no valor personalizado."""
        self.id_offset = int(value)
        self._update_id_adjust_label()
        current = f"{self.id_offset:+d}" if self.id_offset else "0"
        self.status_var.set(i18n.tr(f"Ajuste de ID {current} aplicado somente na prévia. Nada foi renomeado."))
        self.append_log(f"Ajuste numérico personalizado: {current}; aplicado somente na prévia.")
        self.generate_preview()

    def choose_custom_id_offset(self):
        value = simpledialog.askinteger(
            "Ajuste personalizado",
            "Digite o valor do ajuste. Use número positivo para aumentar ou negativo para diminuir:",
            initialvalue=self.id_offset,
            parent=self.root,
        )
        if value is not None:
            self.set_id_offset(value)

    def map_id_for_stem(self, stem: str) -> tuple[str | None, str]:
        """Busca o ID usando nome exato e versões limpas de IDs/sufixos do arquivo."""
        candidates = [stem, strip_wwise_suffix(stem)]
        for pattern in (r"\s*\(\d+\)\s*$", r"\s*#\d+\s*$", r"\s*\[\d+\]\s*$", r"[_\- ]+\d+\s*$"):
            candidates.append(re.sub(pattern, "", stem, flags=re.IGNORECASE))
        for candidate in candidates:
            key = normalize_key(candidate)
            if key in self.pcvr_to_standalone:
                return self.pcvr_to_standalone[key], "mapa Wwise PCVR → Standalone"
            if key in self.name_id_map:
                return self.name_id_map[key], "mapa Wwise Name → ID"
        return None, ""

    def load_mapping(self):
        selected = filedialog.askopenfilenames(parent=self.root, title="Carregar um ou dois mapas Name → ID do Wwise", filetypes=[("Arquivos TXT", "*.txt"), ("Todos os arquivos", "*.*")])
        if not selected:
            return
        paths = [Path(item).expanduser().resolve() for item in selected]
        parsed: list[tuple[Path, dict[str, str]]] = []
        invalid: list[str] = []
        for path in paths:
            try:
                mapping = parse_wwise_name_id_map(path)
            except OSError:
                mapping = {}
            if mapping:
                parsed.append((path, mapping))
            else:
                invalid.append(path.name)
        if not parsed:
            self.map_var.set("Nenhum ID e nome reconhecível foi encontrado nos TXT selecionados.")
            self.append_log("Mapa Wwise ignorado: nenhum registro ID/Name reconhecido.")
            messagebox.showwarning("Mapa Wwise", "Os arquivos foram lidos, mas não encontrei linhas com ID e Name.\n\nConfira se o TXT contém uma tabela do Wwise com essas colunas.", parent=self.root)
            return
        self.loaded_map_files = [path for path, _mapping in parsed]
        self.pcvr_to_standalone = {}
        if len(parsed) >= 2:
            pcvr_path, pcvr_map = next((item for item in parsed if "pcvr" in item[0].name.casefold()), parsed[0])
            standalone_path, standalone_map = next((item for item in parsed if any(token in item[0].name.casefold() for token in ("standalone", "satand", "stand")) and item[0] != pcvr_path), parsed[1])
            pcvr_id_to_name = {audio_id: name_key for name_key, audio_id in pcvr_map.items()}
            for pcvr_id, narration_key in pcvr_id_to_name.items():
                standalone_id = standalone_map.get(narration_key)
                if standalone_id:
                    self.pcvr_to_standalone[normalize_key(pcvr_id)] = standalone_id
            self.name_id_map = standalone_map
            self.map_var.set(f"2 mapas ativos: {len(self.pcvr_to_standalone)} conversões PCVR → Standalone; {len(standalone_map)} nomes no Standalone")
            self.append_log(f"Mapas Wwise relacionados: {len(self.pcvr_to_standalone)} conversões PCVR → Standalone.")
        else:
            path, mapping = parsed[0]
            self.name_id_map = mapping
            self.map_var.set(f"1 mapa ativo: {path.name} — {len(mapping)} nomes Name → ID")
            self.append_log(f"Mapa Wwise ativo: {path.name}; {len(mapping)} nomes Name → ID.")
        if invalid:
            self.append_log(f"Arquivos sem registros reconhecíveis: {', '.join(invalid)}")
        self.generate_preview()

    def clear_mapping(self):
        """Remove todos os mapas da memória e força a prévia a ignorá-los."""
        self.name_id_map.clear()
        self.pcvr_to_standalone.clear()
        self.loaded_map_files.clear()
        self.use_map_var.set("0")
        self.map_var.set("Nenhum mapa Wwise carregado; a prévia usa apenas regras internas.")
        self.status_var.set("Mapa Wwise limpo. A prévia agora usa apenas as regras internas.")
        self.append_log("Todos os mapas Wwise foram removidos da sessão; o uso de mapa foi desativado.")
        self.generate_preview()

    def relative_name(self, path: Path) -> str:
        base = Path(self.source_var.get())
        try:
            return str(path.relative_to(base)) if base.is_dir() else str(path)
        except ValueError:
            return str(path)

    def adjust_id_value(self, value: str, padding: int, reason: str) -> tuple[str | None, str]:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return None, reason
        if self.id_offset:
            adjusted = numeric + self.id_offset
            if adjusted < 0:
                return None, "ajuste produziria ID negativo"
            value = str(adjusted)
            reason = f"{reason}; ajuste de ID {self.id_offset:+d}"
        return (value.zfill(padding) if padding else value), reason

    def target_name_for(self, path: Path) -> tuple[str, str]:
        stem = path.stem
        suffix = path.suffix
        rule = i18n.source_text(self.rule_var.get())
        clean_stem = strip_wwise_suffix(stem) if self.strip_suffix_var.get() == "1" else stem
        padding = int(self.padding_var.get() or "0")

        if rule == RULE_CHOICES[3]:
            if clean_stem != stem:
                return clean_stem + suffix, "sufixo Wwise removido"
            return path.name, "nenhum sufixo Wwise encontrado"
        if rule == RULE_CHOICES[4]:
            return clean_stem + suffix, "nome base normalizado"
        if self.use_map_var.get() == "1":
            mapped_id, map_reason = self.map_id_for_stem(clean_stem)
            if mapped_id:
                adjusted_id, adjusted_reason = self.adjust_id_value(mapped_id, padding, map_reason)
                if adjusted_id is None:
                    return path.name, adjusted_reason
                return adjusted_id + suffix, adjusted_reason

        extracted, reason = extract_id(stem)
        if rule == RULE_CHOICES[2] and not Wwise_CONVERTED_RE.fullmatch(stem):
            return path.name, "padrão Wwise pós-processado não encontrado"
        if rule in (RULE_CHOICES[0], RULE_CHOICES[1], RULE_CHOICES[2]) and extracted:
            value, adjusted_reason = self.adjust_id_value(extracted, padding, reason)
            if value is None:
                return path.name, adjusted_reason
            return value + suffix, adjusted_reason
        if rule == RULE_CHOICES[0] and clean_stem != stem:
            return clean_stem + suffix, "sufixo Wwise removido sem ID confiável"
        return path.name, reason

    def _cancel_preview_flash(self):
        if self.preview_flash_after_id is not None:
            try:
                self.root.after_cancel(self.preview_flash_after_id)
            except Exception:
                pass
            self.preview_flash_after_id = None

    def _flash_new_name_rows(self, item_ids: list[str]):
        self._cancel_preview_flash()
        if not item_ids:
            return

        def pulse(step: int = 0):
            if not self.preview_tree.winfo_exists():
                self.preview_flash_after_id = None
                return
            tag = "new_flash" if step % 2 == 0 else "ok"
            for item_id in item_ids:
                if self.preview_tree.exists(item_id):
                    self.preview_tree.item(item_id, tags=(tag,))
            if step < 5:
                self.preview_flash_after_id = self.root.after(180, lambda: pulse(step + 1))
            else:
                self.preview_flash_after_id = None

        pulse()

    def generate_preview(self):
        self._cancel_preview_flash()
        self.preview_tree.delete(*self.preview_tree.get_children())
        if not self.files:
            self.plan = []
            self.summary_var.set("Arquivos: 0 | Prontos: 0 | Conflitos: 0 | Sem alteração: 0")
            return
        selected_indices = set(self.file_list.curselection())
        # A seleção guardada controla a operação, mas nunca oculta linhas da
        # prévia. Assim, todos os arquivos carregados continuam visíveis.
        if selected_indices:
            self.operation_scope_paths = {self.files[index] for index in selected_indices if 0 <= index < len(self.files)}
        elif self.selected_only_var.get() == "1":
            self.operation_scope_paths &= set(self.files)
        else:
            self.operation_scope_paths = set(self.files)
        scope_paths = self.operation_scope_paths or set(self.files)
        self.plan = []
        for path in self.files:
            if path not in scope_paths:
                self.plan.append(RenamePlan(path, path, "SEM ALTERAÇÃO", "arquivo carregado, mas não selecionado para esta operação"))
                continue
            new_name, reason = self.target_name_for(path)
            target = path.with_name(new_name)
            status = "OK" if new_name != path.name else "SEM ALTERAÇÃO"
            self.plan.append(RenamePlan(path, target, status, reason))
        self.validate_plan()
        counts = {"OK": 0, "CONFLITO": 0, "SEM ALTERAÇÃO": 0}
        new_name_rows: list[str] = []
        for item in self.plan:
            counts[item.status] = counts.get(item.status, 0) + 1
            tag = "renamed" if item.status == "RENOMEADO" else "ok" if item.status == "OK" else "conflict" if item.status == "CONFLITO" else "skip"
            row_id = self.preview_tree.insert("", END, values=(i18n.tr(item.status), item.source.name, item.target.name, item.reason), tags=(tag,))
            if item.status == "OK":
                new_name_rows.append(row_id)
        self.summary_var.set(f"Arquivos: {len(self.plan)} | Prontos: {counts.get('OK', 0)} | Conflitos: {counts.get('CONFLITO', 0)} | Sem alteração: {counts.get('SEM ALTERAÇÃO', 0)}")
        self.status_var.set(i18n.tr("Prévia automática atualizada. Os novos nomes piscam em verde; revise antes de confirmar."))
        if new_name_rows:
            self.preview_tree.selection_set(new_name_rows[0])
            self.preview_tree.see(new_name_rows[0])
        elif self.plan:
            first_row = self.preview_tree.get_children()[0]
            self.preview_tree.selection_set(first_row)
            self.preview_tree.see(first_row)
        self.root.update_idletasks()
        self._flash_new_name_rows(new_name_rows)

    def validate_plan(self):
        source_keys = {str(item.source).casefold() for item in self.plan}
        target_groups: dict[str, list[RenamePlan]] = {}
        for item in self.plan:
            if item.status == "SEM ALTERAÇÃO":
                continue
            target_groups.setdefault(str(item.target).casefold(), []).append(item)
        for item in self.plan:
            if item.status == "SEM ALTERAÇÃO":
                continue
            key = str(item.target).casefold()
            if len(target_groups.get(key, [])) > 1:
                item.status = "CONFLITO"
                item.reason = "dois ou mais arquivos receberiam o mesmo nome"
            elif item.target.exists() and str(item.target).casefold() not in source_keys:
                item.status = "CONFLITO"
                item.reason = "o nome de destino já existe"

    def process_all(self):
        """Executa carregamento implícito, prévia, TXT e renomeação em uma sequência confirmada."""
        if not self.files:
            source = Path(self.source_var.get())
            if source.is_dir():
                self.set_files(self.collect_files(source), str(source))
            else:
                messagebox.showinfo("Processar tudo", "Escolha uma pasta ou abra arquivos primeiro.", parent=self.root)
                return
        self.selected_only_var.set("0")
        self.operation_scope_paths = set(self.files)
        self.file_list.selection_clear(0, END)
        self.generate_preview()
        conflicts = [item for item in self.plan if item.status == "CONFLITO"]
        changes = [(item.source, item.target) for item in self.plan if item.status == "OK"]
        if conflicts:
            messagebox.showwarning("Processar tudo", "Há conflitos na prévia. Corrija a regra ou os nomes antes de continuar.", parent=self.root)
            return
        if not messagebox.askyesno("Processar tudo", f"O fluxo irá gerar o TXT de IDs + nomes e renomear {len(changes)} arquivo(s) com segurança.\n\nContinuar?", parent=self.root):
            return
        if not self.generate_names_txt():
            if not messagebox.askyesno("TXT não gerado", "O TXT não foi salvo. Deseja continuar somente com a renomeação?", parent=self.root):
                return
        if changes:
            if self._apply_changes(changes):
                self.status_var.set(f"Processamento completo concluído: TXT gerado e {len(changes)} arquivo(s) renomeado(s).")
        else:
            self.status_var.set("Processamento completo concluído: TXT gerado; nenhum nome precisou mudar.")

    def rename_files(self):
        if not self.files:
            messagebox.showinfo("Renomeação", "Adicione arquivos ou escolha uma pasta primeiro.", parent=self.root)
            return
        # Recalcula sempre antes da confirmação para respeitar a seleção mais
        # recente da lista e não reutilizar um plano de outra seleção.
        self.generate_preview()
        conflicts = [item for item in self.plan if item.status == "CONFLITO"]
        scope_paths = self.operation_scope_paths or set(self.files)
        changes = [item for item in self.plan if item.status == "OK" and item.source in scope_paths]
        if conflicts:
            conflicts = [item for item in conflicts if item.source in scope_paths]
        if conflicts:
            messagebox.showwarning("Conflitos", "Corrija os conflitos destacados na prévia antes de renomear.", parent=self.root)
            return
        if not changes:
            messagebox.showinfo("Renomeação", "Nenhum arquivo tem uma alteração segura para aplicar.", parent=self.root)
            return
        if not messagebox.askyesno("Confirmar renomeação", f"Renomear {len(changes)} arquivo(s)?\n\nA operação somente altera os nomes no mesmo diretório; não copia nem move arquivos.", parent=self.root):
            return
        scoped_changes = [(item.source, item.target) for item in changes if item.source in self.files]
        if len(scoped_changes) != len(changes):
            self.status_var.set("Renomeação interrompida: o plano continha arquivo fora da lista carregada.")
            self.append_log("Renomeação bloqueada por segurança: somente arquivos carregados podem ser alterados.")
            return
        self._apply_changes(scoped_changes)
        self.status_var.set(f"Renomeação concluída. {len(scoped_changes)} arquivo(s) alterado(s). Use DESFAZER se necessário.")

    def _mark_renamed_preview(self, applied: list[tuple[Path, Path]]):
        """Marca na prévia os destinos que foram efetivamente confirmados."""
        renamed_targets = {str(target.resolve()).casefold() for _source, target in applied}
        for item in self.plan:
            if str(item.source.resolve()).casefold() in renamed_targets:
                item.status = "RENOMEADO"
                item.reason = "renomeação confirmada nesta sessão"
        for row_id, item in zip(self.preview_tree.get_children(), self.plan):
            if item.status == "RENOMEADO":
                self.preview_tree.item(row_id, values=(i18n.tr(item.status), item.source.name, item.target.name, item.reason), tags=("renamed",))
        renamed_count = sum(item.status == "RENOMEADO" for item in self.plan)
        if renamed_count:
            self.status_var.set(i18n.tr(f"Renomeação concluída. {renamed_count} arquivo(s) marcado(s) como RENOMEADO."))

    def _replace_loaded_paths(self, replacements: list[tuple[Path, Path]]) -> None:
        """Atualiza a lista carregada sem redescobrir nem adicionar arquivos da pasta."""
        replacement_map = {source.resolve(): target.resolve() for source, target in replacements}
        updated = [replacement_map.get(path.resolve(), path.resolve()) for path in self.files]
        old_scope = {path.resolve() for path in self.operation_scope_paths}
        self.set_files(updated, str(self.source_dir))
        self.operation_scope_paths = {replacement_map.get(path, path) for path in old_scope if path in replacement_map or path in {item.resolve() for item in self.files}}
        self.file_list.selection_clear(0, END)
        if self.selected_only_var.get() == "1":
            for index, path in enumerate(self.files):
                if path.resolve() in self.operation_scope_paths:
                    self.file_list.selection_set(index)
        self.generate_preview()

    def _apply_changes(self, changes: list[tuple[Path, Path]]):
        try:
            self._execute_safe(changes)
        except OSError as exc:
            messagebox.showerror("Renomeação", f"A operação foi interrompida e revertida quando possível:\n{exc}", parent=self.root)
            return False
        applied = list(changes)
        self.last_changes = applied
        self.rename_history.extend(applied)
        self.append_log(f"Renomeação concluída: {len(applied)} arquivo(s).")
        self._replace_loaded_paths(applied)
        self._mark_renamed_preview(applied)
        return True

    def save_renamed_files(self) -> bool:
        """Salva todos os pares renomeados nesta sessão sem repetir a operação."""
        if not self.rename_history:
            messagebox.showinfo("Salvar renomeados", "Ainda não há arquivos renomeados nesta sessão.", parent=self.root)
            return False
        source = Path(self.source_var.get()).expanduser()
        initial_dir = str(source if source.is_dir() else self.project_root)
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar lista de arquivos renomeados",
            initialdir=initial_dir,
            initialfile="ArquivosRenomeados.txt",
            defaultextension=".txt",
            filetypes=[("Arquivo TXT", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return False
        output_path = Path(selected).expanduser().resolve()
        rows = ["NOME ANTERIOR\tNOME NOVO\tID FINAL"]
        for old_path, new_path in self.rename_history:
            final_id, _reason = extract_id(new_path.stem)
            rows.append("\t".join((old_path.name, new_path.name, final_id or "")))
        try:
            output_path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")
        except OSError as exc:
            messagebox.showerror("Salvar renomeados", f"Não foi possível salvar a lista:\n{exc}", parent=self.root)
            return False
        self.append_log(f"Lista de renomeados salva: {output_path.name} ({len(self.rename_history)} arquivo(s)).")
        self.status_var.set(f"Lista de renomeados salva: {output_path}")
        messagebox.showinfo("Salvar renomeados", f"Lista salva com {len(self.rename_history)} arquivo(s):\n{output_path}", parent=self.root)
        return True

    def _execute_safe(self, changes: list[tuple[Path, Path]]):
        token = uuid.uuid4().hex
        staged: list[tuple[Path, Path, Path]] = []
        try:
            for index, (source, target) in enumerate(changes):
                temporary = source.with_name(f".__dublaskizon_rename_{token}_{index}.tmp")
                source.rename(temporary)
                staged.append((source, temporary, target))
            for source, temporary, target in staged:
                temporary.rename(target)
        except Exception:
            for source, temporary, target in reversed(staged):
                try:
                    if temporary.exists():
                        temporary.rename(source)
                    elif target.exists() and not source.exists():
                        target.rename(source)
                except Exception:
                    pass
            raise

    def undo_last(self):
        if not self.last_changes:
            messagebox.showinfo("Desfazer", "Ainda não há uma renomeação recente para desfazer.", parent=self.root)
            return
        # O desfazer usa exclusivamente o lote guardado pela última operação;
        # nunca redescobre arquivos na pasta de origem.
        inverse = [(new, old) for old, new in self.last_changes]
        if any(not source.exists() for source, _ in inverse):
            messagebox.showwarning("Desfazer", "Algum arquivo renomeado não está mais no local esperado.", parent=self.root)
            return
        if not messagebox.askyesno("Desfazer renomeação", f"Restaurar {len(inverse)} nome(s) anteriores?", parent=self.root):
            return
        try:
            self._execute_safe(inverse)
        except OSError as exc:
            messagebox.showerror("Desfazer", f"Não foi possível desfazer a operação:\n{exc}", parent=self.root)
            return
        restored = [(old, new) for old, new in self.last_changes]
        for change in reversed(restored):
            for index in range(len(self.rename_history) - 1, -1, -1):
                if self.rename_history[index] == change:
                    self.rename_history.pop(index)
                    break
        self.last_changes = []
        self.append_log(f"Desfeito: {len(restored)} arquivo(s) restaurado(s).")
        self._replace_loaded_paths([(new, old) for old, new in restored])
        self.status_var.set("Última renomeação desfeita com segurança.")

    def open_source_folder(self):
        folder = self.source_dir.expanduser().resolve() if self.source_dir else None
        if folder is None or not folder.is_dir():
            existing_parent = next((path.parent for path in self.files if path.exists()), None)
            folder = existing_parent.resolve() if existing_parent is not None else None
        if folder is None or not folder.is_dir():
            messagebox.showwarning("Pasta", "A pasta de origem dos arquivos carregados não existe mais.", parent=self.root)
            return
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            messagebox.showerror("Pasta", f"Não foi possível abrir a pasta:\n{exc}", parent=self.root)

    def _log_central(self, text, tag="normal") -> None:
        callback = getattr(self, "central_log_callback", None)
        if callable(callback):
            try:
                callback("FILTRO RENOMEAR .WEM", str(text), tag)
            except Exception:
                pass

    def append_log(self, text: str):
        self._log_central(text, "error" if str(text).startswith("ERRO") else "normal")
        self.log_box.configure(state="normal")
        self.log_box.insert(END, text + "\n")
        self.log_box.see(END)
        self.log_box.configure(state="disabled")


if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    root.title(TITLE)
    root.geometry("1280x860")
    WemFilterApp(root, embedded=False)
    root.mainloop()
