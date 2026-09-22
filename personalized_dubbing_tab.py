#!/usr/bin/env python3
"""Dublagem personalizada com voz-modelo e expressão aproximada da cena original.

O OmniVoice expõe uma única referência de áudio (``--ref_audio``). Portanto ele
não separa, de forma nativa, "identidade/timbre" e "prosódia/expressão" em dois
arquivos independentes. Esta aba usa o áudio-modelo como referência de voz e,
após a síntese, aproxima ritmo, pausas e dinâmica do WAV original. Isso preserva
melhor a identidade do modelo sem prometer transferência exata de entonação.
"""
from __future__ import annotations

import json
from generation_progress import GenerationProgress
import os
import queue
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import END, Button, Listbox, StringVar, filedialog, messagebox, simpledialog, ttk

try:
    from . import batch_tab
    from .audio_player import AudioPlayerManager, reveal_in_file_manager
    from .ui_theme import apply_button_style, apply_button_style_to_tree
except ImportError:
    import batch_tab
    from audio_player import AudioPlayerManager, reveal_in_file_manager
    from ui_theme import apply_button_style, apply_button_style_to_tree

ROOT = Path(os.environ.get("DUBLASKIZON_PROJECT_ROOT", Path(__file__).resolve().parent)).resolve()
AUDIO_DIR = ROOT / "WAV ORIGINAIS"
TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
CUSTOM_DIR = ROOT / "dublados personalizados"
MODEL_DIR = ROOT / "MODELOS DE VOZ PERSONALIZADOS"
CONFIG_FILE = ROOT / "Dublaskizon_dublagem_personalizada.json"
MANIFEST_FILE = CUSTOM_DIR / "_manifesto_personalizado.json"
AUDIO_EXTENSIONS = batch_tab.AUDIO_EXTENSIONS


def configure_project_root(project_root: Path) -> None:
    global ROOT, AUDIO_DIR, TEXT_DIR, CUSTOM_DIR, MODEL_DIR, CONFIG_FILE, MANIFEST_FILE
    ROOT = Path(project_root).expanduser().resolve()
    AUDIO_DIR = ROOT / "WAV ORIGINAIS"
    TEXT_DIR = ROOT / "TXT TEXTO PORTUGUES"
    CUSTOM_DIR = ROOT / "dublados personalizados"
    MODEL_DIR = ROOT / "MODELOS DE VOZ PERSONALIZADOS"
    CONFIG_FILE = ROOT / "Dublaskizon_dublagem_personalizada.json"
    MANIFEST_FILE = CUSTOM_DIR / "_manifesto_personalizado.json"


def _load_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_custom_manifest() -> dict[str, dict]:
    data = _load_json(MANIFEST_FILE, {})
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def custom_model_for_stem(stem: str) -> Path | None:
    record = load_custom_manifest().get(stem, {})
    raw = str(record.get("voice_model", "")).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve() if path.is_file() else None


def _ffmpeg_path() -> str | None:
    try:
        return batch_tab.executable_path("ffmpeg", ROOT)
    except Exception:
        return shutil.which("ffmpeg")


def _audio_duration(path: Path) -> float:
    try:
        from pydub import AudioSegment
        return max(0.001, len(AudioSegment.from_file(path)) / 1000.0)
    except Exception:
        return 0.0


def _atempo_chain(speed: float) -> str:
    """Monta filtros atempo (0.5..2.0 cada) para qualquer fator positivo."""
    speed = max(0.05, float(speed))
    factors: list[float] = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.8f}" for factor in factors)


def _safe_replace_file(source: Path, target: Path, retries: int = 18, delay: float = 0.18) -> None:
    """Finaliza um WAV no Windows mesmo quando rename/replace é bloqueado.

    Alguns ambientes permitem criar/gravar o WAV temporário, mas bloqueiam os.replace()
    dentro da mesma pasta. Nesses casos fazemos fallback para cópia direta dos bytes
    ao arquivo final e só depois removemos o temporário.
    """
    source = Path(source)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            if target.exists():
                try:
                    os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass
                try:
                    target.unlink()
                except OSError:
                    pass

            # Caminho rápido/atômico.
            try:
                os.replace(source, target)
                return
            except (PermissionError, OSError) as exc:
                last_error = exc

            # Fallback importante para Windows: evita depender de rename.
            # O temporário já está fechado neste ponto (ffmpeg/subprocess terminou).
            with source.open('rb') as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                try:
                    os.fsync(dst.fileno())
                except OSError:
                    pass
            try:
                shutil.copystat(source, target)
            except OSError:
                pass
            try:
                source.unlink()
            except OSError:
                pass
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(delay)
    raise PermissionError(
        f"Não foi possível gravar {target.name} na pasta de dublados personalizados. "
        f"O áudio chegou a ser gerado, mas o Windows bloqueou a gravação final. "
        f"Erro: {last_error}"
    )


def match_original_expression(generated: Path, original: Path, target: Path, progress_callback=None) -> None:
    """Aproxima duração, pausas e envelope de intensidade do original.

    A entonação/pitch exata não é transferida, pois o OmniVoice atual não expõe
    condicionamento separado de prosódia. O pós-processamento é deliberadamente
    conservador para não destruir o timbre clonado.
    """
    report = progress_callback or (lambda value: None)
    report(1)
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        shutil.copy2(generated, target)
        return

    original_duration = _audio_duration(original)
    generated_duration = _audio_duration(generated)
    if original_duration <= 0 or generated_duration <= 0:
        shutil.copy2(generated, target)
        return

    report(15)
    speed = generated_duration / original_duration  # >1 acelera; <1 desacelera
    timed = target.with_name(f".{target.stem}.__tempo.wav")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(generated),
        "-af", _atempo_chain(speed), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(timed),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **batch_tab.hidden_process_kwargs())
    if result.returncode != 0 or not timed.is_file():
        shutil.copy2(generated, target)
        return

    report(40)
    # Copia o contorno de intensidade/pausas em janelas curtas. Se numpy/pydub
    # não estiverem disponíveis, o WAV apenas fica com a duração sincronizada.
    try:
        import numpy as np
        from pydub import AudioSegment

        src = AudioSegment.from_file(original).set_frame_rate(24000).set_channels(1).set_sample_width(2)
        dub = AudioSegment.from_file(timed).set_frame_rate(24000).set_channels(1).set_sample_width(2)
        n = min(len(src.raw_data), len(dub.raw_data)) // 2
        src_arr = np.frombuffer(src.raw_data[: n * 2], dtype=np.int16).astype(np.float32)
        dub_arr = np.frombuffer(dub.raw_data[: n * 2], dtype=np.int16).astype(np.float32)
        if len(src_arr) < 400 or len(dub_arr) < 400:
            _safe_replace_file(timed, target)
            return
        window = 960  # 40 ms a 24 kHz
        gains = np.ones((len(dub_arr) + window - 1) // window, dtype=np.float32)
        src_rms_all = []
        dub_rms_all = []
        eps = 30.0
        for i in range(len(gains)):
            a, b = i * window, min((i + 1) * window, len(dub_arr))
            src_chunk = src_arr[a:b]
            dub_chunk = dub_arr[a:b]
            src_rms_all.append(float(np.sqrt(np.mean(src_chunk * src_chunk) + eps)))
            dub_rms_all.append(float(np.sqrt(np.mean(dub_chunk * dub_chunk) + eps)))
        report(65)
        src_med = max(eps, float(np.median([x for x in src_rms_all if x > eps] or [eps])))
        dub_med = max(eps, float(np.median([x for x in dub_rms_all if x > eps] or [eps])))
        for i, (sr, dr) in enumerate(zip(src_rms_all, dub_rms_all)):
            # Relação relativa: segue reações/pausas do original sem copiar volume absoluto.
            wanted = sr / src_med
            current = dr / dub_med
            gain = wanted / max(0.10, current)
            if sr < src_med * 0.08:  # pausa/silêncio do original
                gain = min(gain, 0.08)
            gains[i] = float(np.clip(gain, 0.08, 1.8))
        if len(gains) >= 5:
            gains = np.convolve(gains, np.ones(5, dtype=np.float32) / 5.0, mode="same")
        out = dub_arr.copy()
        for i, gain in enumerate(gains):
            a, b = i * window, min((i + 1) * window, len(out))
            out[a:b] *= gain
        out = np.clip(out, -32768, 32767).astype(np.int16)
        final = AudioSegment(
            data=out.tobytes(), sample_width=2, frame_rate=24000, channels=1
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        report(90)
        final.export(target, format="wav", parameters=["-acodec", "pcm_s16le"])
        timed.unlink(missing_ok=True)
    except Exception:
        _safe_replace_file(timed, target)


def prepare_voice_model_audio(source: Path, destination_dir: Path) -> Path:
    """Copia/converte o modelo para WAV PCM 16-bit, 24 kHz, mono."""
    source = Path(source).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source.stem}.wav"
    if destination.resolve() == source:
        return source
    index = 2
    while destination.exists() and destination.resolve() != source:
        # Se o mesmo conteúdo/nome já estiver no projeto, reutiliza o arquivo.
        try:
            if source.stat().st_size == destination.stat().st_size and source.suffix.casefold() == ".wav":
                return destination.resolve()
        except OSError:
            pass
        destination = destination_dir / f"{source.stem}_{index}.wav"
        index += 1
    ffmpeg = _ffmpeg_path()
    if ffmpeg:
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(destination)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **batch_tab.hidden_process_kwargs())
        if result.returncode == 0 and destination.is_file():
            return destination.resolve()
    if source.suffix.casefold() in {".wav", ".wave", ".waw"}:
        if destination.resolve() != source:
            shutil.copy2(source, destination)
        return destination.resolve()
    raise RuntimeError("FFmpeg é necessário para preparar este formato de áudio modelo.")


def filter_personalized_scenes(stems, folders=(), names=()):
    """Filter relative scene keys; compare whole folder components, never filenames."""
    prefixes=[tuple(part.casefold() for part in Path(folder).parts) for folder in folders]
    wanted={name.strip().casefold() for name in names if name.strip()}
    if not prefixes and not wanted:return list(stems)
    result=[]
    for stem in stems:
        parts=tuple(part.casefold() for part in Path(stem).parent.parts)
        if any(parts[:len(prefix)]==prefix for prefix in prefixes) or wanted.intersection(parts):result.append(stem)
    return result


def choose_personalized_voice(parent, theme, project_root, library=None):
    """Modal voice library picker. Cancel never starts generation."""
    configure_project_root(project_root)
    window=tk.Toplevel(parent)
    window.title("ÁUDIOS MODELO DE VOZ — ALTERAR PERSONAGEM")
    window.geometry("850x300");window.minsize(650,300)
    window.transient(parent.winfo_toplevel())
    bg=theme.get('surface',theme.get('root','#FFFFFF'));fg=theme.get('text','#111827')
    window.configure(bg=bg)
    if library is None:
        library=PersonalizedDubbingApp.__new__(PersonalizedDubbingApp)
        library.root=window;library.models=[]
        library.active_model_var=StringVar(master=window,value='')
        library.status_var=StringVar(master=window,value='Selecione o personagem para esta cena.')
        library._load_settings()
    tk.Label(window,text="ÁUDIOS MODELO DE VOZ — prefira fala limpa, sem música/efeitos",bg=bg,fg=fg,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=12,pady=12)
    combo=ttk.Combobox(window,textvariable=library.active_model_var,state='readonly',values=[str(p) for p in library.models])
    combo.pack(fill='x',padx=12,pady=4)
    if not hasattr(library,'model_combo'):library.model_combo=combo
    combo.bind('<<ComboboxSelected>>',lambda _event:library._save_settings())
    preview=AudioPlayerManager(window,project_root,status_callback=library.status_var.set)
    preview.theme=theme
    result=[None]
    def close():
        preview.stop(announce=False)
        window.destroy()
    def refresh(action):
        action()
        combo.configure(values=[str(p) for p in library.models])
    def listen():
        raw=library.active_model_var.get().strip()
        if raw and Path(raw).is_file():
            preview.stop(announce=False);preview._start_paths([Path(raw)],'modelo')
        else:messagebox.showwarning('Áudio modelo','Selecione um modelo disponível.',parent=window)
    def confirm():
        raw=library.active_model_var.get().strip()
        path=Path(raw).expanduser() if raw else None
        if path is None or not path.is_file():
            messagebox.showwarning('Áudio modelo','Adicione e selecione um modelo antes de continuar.',parent=window);return
        library._save_settings();result[0]=path.resolve();close()
    row=tk.Frame(window,bg=bg);row.pack(fill='x',padx=12,pady=8)
    for label,command,role in [('+ ADICIONAR MODELO',lambda:refresh(lambda:library.add_models(dialog_parent=window)),'primary'),('REMOVER MODELO',lambda:refresh(library.remove_model),'danger'),('▶ OUVIR MODELO',listen,'teal'),('PARAR',lambda:preview.stop(announce=False),'secondary')]:
        button=Button(row,text=label,command=command,relief='flat',padx=8,pady=6)
        apply_button_style(button,theme,role);button.pack(side='left',padx=(0,6))
    tk.Label(window,textvariable=library.status_var,bg=bg,fg=fg,anchor='w',wraplength=800).pack(fill='x',padx=12,pady=4)
    footer=tk.Frame(window,bg=bg);footer.pack(side='bottom',fill='x',padx=12,pady=12)
    for label,command,role in [('CANCELAR',close,'secondary'),('USAR MODELO E CONTINUAR',confirm,'success')]:
        button=Button(footer,text=label,command=command,relief='flat',padx=12,pady=7)
        apply_button_style(button,theme,role);button.pack(side='right',padx=4)
    window.protocol('WM_DELETE_WINDOW',close);window.bind('<Escape>',lambda _e:close())
    window.grab_set();combo.focus_set();window.wait_window()
    return result[0]


class PersonalizedDubbingApp:
    def __init__(self, root, embedded=False, project_root: Path | None = None, project_actions=None, review_app=None):
        self.root = root
        self.embedded = embedded
        self.project_actions = project_actions or {}
        self.review_app = review_app
        if review_app is not None:
            review_app.voice_model_picker = lambda parent: choose_personalized_voice(parent,self.theme,ROOT,self)
        self.scene_review = None
        if project_root is not None:
            configure_project_root(project_root)
        self.theme = {"mode": "claro", "input": "#FFFFFF", "input_text": "#1F2937", "select": "#DBEAFE"}
        self.audio_by_stem = batch_tab.find_audio_by_stem()
        self.text_by_stem = batch_tab.find_text_by_stem()
        self.stems = sorted(set(self.audio_by_stem) & set(self.text_by_stem), key=str.casefold)
        self.scope_folders=set();self.scope_names=set()
        self.completed_stems = set(batch_tab.find_audio_by_stem(CUSTOM_DIR))
        self.selected_stems = set(self.stems) - self.completed_stems
        self.models: list[Path] = []
        self.active_model_var = StringVar(value="")
        self.r_pronunciation_var = StringVar(value=batch_tab.R_PRONUNCIATION_CHOICES[0][0])
        self.status_var = StringVar(value="Pronto")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.clone_stage_var = tk.DoubleVar(value=0.0)
        self.dub_stage_var = tk.DoubleVar(value=0.0)
        self.original_stage_var = tk.DoubleVar(value=0.0)
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.auto_translation_var = StringVar(value='0')
        self.align_audio_var = StringVar(value='0')
        self.auto_translation_settings = {}
        self.align_audio_settings = {'pauses':False, 'max_change':25}
        self.cancel_requested = False
        self.current_process = None
        self.audio_player = AudioPlayerManager(root, ROOT, status_callback=self.status_var.set)
        self.audio_player.set_dubbed_folder_name("dublados personalizados")
        self.audio_player.part_context_provider = self.part_generation_context
        self.audio_player.set_scene_integration(review_actions={"redub_personalized": self.redub_personalized_scene})
        self._load_settings()
        self.build_ui()
        self.populate_scenes()
        self.root.after(120, self.poll_messages)

    def part_generation_context(self, stem):
        controller = self._ensure_scene_review()
        model = custom_model_for_stem(stem)
        if model is None:
            raw = self.active_model_var.get().strip()
            model = Path(raw).expanduser() if raw else None
        context=controller.part_generation_context(stem)
        context['reference']=model
        return context

    def _load_settings(self):
        data = _load_json(CONFIG_FILE, {})
        self.auto_translation_settings = dict(data.get('auto_translation_settings', {}))
        self.align_audio_settings = {'pauses':False, 'max_change':25, **data.get('align_audio_settings', {})}
        raw_models = data.get("models", []) if isinstance(data, dict) else []
        for raw in raw_models if isinstance(raw_models, list) else []:
            path = Path(str(raw)).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            if path.is_file() and path.suffix.casefold() in AUDIO_EXTENSIONS:
                self.models.append(path.resolve())
        active = str(data.get("active_model", "")) if isinstance(data, dict) else ""
        if active:
            candidate = Path(active).expanduser()
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            if candidate.is_file() and candidate.resolve() not in self.models:
                self.models.append(candidate.resolve())
        if self.models:
            chosen = self.models[0]
            if active:
                active_path = Path(active).expanduser()
                if not active_path.is_absolute():
                    active_path = ROOT / active_path
                try:
                    active_path = active_path.resolve()
                    chosen = next((p for p in self.models if p.resolve() == active_path), self.models[0])
                except OSError:
                    pass
            self.active_model_var.set(str(chosen))

    def _save_settings(self):
        def rel(path: Path) -> str:
            try:
                return path.relative_to(ROOT).as_posix()
            except ValueError:
                return str(path)
        active = Path(self.active_model_var.get()).expanduser() if self.active_model_var.get() else None
        _save_json(CONFIG_FILE, {
            "models": [rel(path) for path in self.models],
            "auto_translation_settings": self.auto_translation_settings,
            "align_audio_settings": self.align_audio_settings,
            "active_model": rel(active.resolve()) if active and active.is_file() else "",
        })

    def build_ui(self):
        header = ttk.Frame(self.root, padding=(12, 8, 12, 5))
        header.pack(fill="x")
        ttk.Label(header, text="DUBLAGEM PERSONALIZADA", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text=("Usa o ÁUDIO MODELO para a identidade/timbre da voz e o áudio ORIGINAL da cena para aproximar duração, pausas e intensidade. "
                  "A entonação exata do original não pode ser separada pelo OmniVoice atual."),
            wraplength=1350,
        ).pack(anchor="w", pady=(2, 0))

        model_box = ttk.LabelFrame(self.root, text="1. ÁUDIOS MODELO DE VOZ — prefira fala limpa, sem música/efeitos", padding=8)
        model_box.pack(fill="x", padx=12, pady=(2, 6))
        row = ttk.Frame(model_box); row.pack(fill="x")
        self.model_combo = ttk.Combobox(row, textvariable=self.active_model_var, state="readonly", values=[str(p) for p in self.models])
        self.model_combo.pack(side="left", fill="x", expand=True)
        self.add_model_button = Button(row, text="+ ADICIONAR MODELO", command=self.add_models, relief="flat", cursor="hand2")
        self.add_model_button.pack(side="left", padx=(6, 0))
        self.remove_model_button = Button(row, text="REMOVER MODELO", command=self.remove_model, relief="flat", cursor="hand2")
        self.remove_model_button.pack(side="left", padx=(6, 0))
        self.listen_model_button = Button(row, text="▶ OUVIR MODELO", command=self.listen_model, relief="flat", cursor="hand2")
        self.listen_model_button.pack(side="left", padx=(6, 0))
        self.model_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_settings())

        scenes = ttk.LabelFrame(self.root, text="2. CENAS QUE SERÃO DUBLADAS", padding=8)
        scenes.pack(fill="both", expand=True, padx=12, pady=6)
        scope_bar=ttk.Frame(scenes);scope_bar.pack(fill='x',pady=(0,5))
        self.scope_buttons=[]
        for label,command in [('ADICIONAR PASTA',self.add_scene_folder),('ADICIONAR TODAS DO PERSONAGEM',self.add_character_folders),('MOSTRAR TODAS AS CENAS',self.clear_scene_scope)]:
            button=Button(scope_bar,text=label,command=command,relief='flat',font=('Segoe UI',8,'bold'),padx=7,pady=4)
            button.pack(side='left',padx=(0,5));self.scope_buttons.append(button)
        self.scope_status=StringVar(value='Todas as pastas do projeto')
        ttk.Label(scenes,textvariable=self.scope_status,wraplength=950).pack(anchor='w',pady=(0,5))
        scene_view = ttk.Frame(scenes)
        scene_view.pack(fill="both", expand=True)
        self.scene_list = Listbox(scene_view, selectmode="extended", exportselection=False, height=16)
        self.scene_scrollbar = ttk.Scrollbar(scene_view, orient="vertical", command=self.scene_list.yview)
        self.scene_scrollbar.pack(side="right", fill="y")
        self.scene_list.configure(yscrollcommand=self.scene_scrollbar.set)
        self.scene_list.pack(side="left", fill="both", expand=True)
        self.scene_list.bind("<MouseWheel>", self.scroll_scene_list)
        self.scene_list.bind("<Button-4>", self.scroll_scene_list)
        self.scene_list.bind("<Button-5>", self.scroll_scene_list)
        self.scene_list.bind("<Double-Button-1>", self.listen_selected_scene)
        self.scene_list.bind("<Button-3>", self.show_scene_context_menu)
        bar = ttk.Frame(scenes); bar.pack(fill="x", pady=(6, 0))
        self.select_all_button = Button(bar, text="SELECIONAR TODOS", command=lambda: self.scene_list.selection_set(0, END), relief="flat", cursor="hand2")
        self.select_all_button.pack(side="left")
        self.clear_button = Button(bar, text="LIMPAR SELEÇÃO", command=lambda: self.scene_list.selection_clear(0, END), relief="flat", cursor="hand2")
        self.clear_button.pack(side="left", padx=(6, 0))
        self.reload_button = Button(bar, text="ATUALIZAR CENAS", command=self.reload_scenes, relief="flat", cursor="hand2")
        self.reload_button.pack(side="left", padx=(6, 0))
        self.listen_scene_button = Button(bar, text="▶ OUVIR ORIGINAL", command=self.listen_selected_original, relief="flat", cursor="hand2")
        self.listen_scene_button.pack(side="left", padx=(6, 0))

        action = ttk.LabelFrame(self.root, text="3. GERAR", padding=8)
        action.pack(fill="x", padx=12, pady=(6, 10))
        pronunciation = ttk.Frame(action)
        pronunciation.pack(fill="x", pady=(0, 8))
        ttk.Label(pronunciation, text="PRONÚNCIA DO R").pack(side="left", padx=(0, 8))
        self.r_pronunciation_combo = ttk.Combobox(
            pronunciation, textvariable=self.r_pronunciation_var,
            values=[label for label, _mode in batch_tab.R_PRONUNCIATION_CHOICES],
            state="readonly", width=18)
        self.r_pronunciation_combo.pack(side="left")
        self.r_pronunciation_combo.bind("<MouseWheel>", lambda _event: "break")
        stages = ttk.Frame(action)
        stages.pack(fill="x", pady=(0, 6))
        for index, (label, variable) in enumerate((("Clonagem / voz-modelo", self.clone_stage_var),
                                ("Dublagem / síntese", self.dub_stage_var),
                                ("Ritmo / pausas do original", self.original_stage_var))):
            stages.columnconfigure(index, weight=1, uniform="personalized_stages")
            column = ttk.Frame(stages)
            column.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            ttk.Label(column, text=label).pack(anchor="w")
            ttk.Progressbar(column, variable=variable, maximum=100, mode="determinate").pack(fill="x", pady=(2,4))
        ttk.Label(action, text="Total de cenas processadas").pack(anchor="w")
        self.progress = ttk.Progressbar(action, variable=self.progress_var, maximum=100, style="PersonalizedTotal.Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(action, textvariable=self.status_var)
        self.status_label.pack(anchor="w", pady=(4, 6))
        buttons = ttk.Frame(action); buttons.pack(fill="x")
        self.generate_button = Button(buttons, text="DUBLAR PERSONALIZADOS", command=self.start_generation, relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"))
        self.generate_button.pack(side="left", fill="x", expand=True)
        self.cancel_button = Button(buttons, text="PARAR", command=self.cancel_generation, relief="flat", cursor="hand2", state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.open_output_button = Button(buttons, text="ABRIR DUBLADOS PERSONALIZADOS", command=self.open_output, relief="flat", cursor="hand2")
        self.open_output_button.pack(side="left", padx=(8, 0))
        options = ttk.Frame(action)
        options.pack(fill='x', pady=5)
        for column in range(2): options.columnconfigure(column, weight=1)
        ttk.Checkbutton(options,text='ALINHAR RITMO E DURAÇÃO AO ORIGINAL',variable=self.align_audio_var,onvalue='1',offvalue='0').grid(row=0,column=0,sticky='w')
        ttk.Button(options,text='CONFIGURAR ALINHAMENTO',command=self.configure_alignment).grid(row=1,column=0,sticky='ew',padx=(0,6))
        ttk.Checkbutton(options,text='TRANSCREVER E TRADUZIR QUANDO FALTAR TXT',variable=self.auto_translation_var,onvalue='1',offvalue='0',command=self.toggle_translation).grid(row=0,column=1,sticky='w')
        ttk.Button(options,text='CONFIGURAR TRANSCRIÇÃO / TRADUÇÃO',command=self.configure_translation).grid(row=1,column=1,sticky='ew')
        self.log = tk.Text(action, height=7, state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(8, 0))
        self.apply_theme(self.theme)

    def scroll_scene_list(self, event):
        number = getattr(event, "num", None)
        delta = getattr(event, "delta", 0)
        if number in (4, 5):
            steps = -3 if number == 4 else 3
        elif delta:
            steps = (-1 if delta > 0 else 1) * max(1, int(abs(delta) / 120)) * 3
        else:
            steps = 0
        if steps:
            self.scene_list.yview_scroll(steps, "units")
        return "break"

    def apply_theme(self, theme: dict):
        self.theme = theme or self.theme
        self.audio_player.apply_theme(self.theme)
        if self.scene_review is not None:
            self.scene_review.apply_theme(self.theme)
        try:
            ttk.Style(self.root).configure("PersonalizedTotal.Horizontal.TProgressbar",
                                           background="#800020", lightcolor="#800020", darkcolor="#800020",
                                           troughcolor=self.theme.get("border", "#CBD5E1"), bordercolor="#800020")
            for widget in (self.scene_list, self.log):
                widget.configure(bg=self.theme.get("input", "#FFFFFF"), fg=self.theme.get("input_text", "#1F2937"), selectbackground=self.theme.get("select", "#DBEAFE"))
            for button, role in ((self.add_model_button, "primary"), (self.remove_model_button, "danger"), (self.listen_model_button, "teal"), (self.select_all_button, "secondary"), (self.clear_button, "secondary"), (self.reload_button, "secondary"), (self.listen_scene_button, "teal"), (self.generate_button, "success"), (self.cancel_button, "danger"), (self.open_output_button, "accent")):
                apply_button_style(button, self.theme, role)
            for button in getattr(self,"scope_buttons",[]):apply_button_style(button,self.theme,"secondary")
            apply_button_style_to_tree(self.root, self.theme)
        except Exception:
            pass

    def apply_language(self, _language_code: str):
        # Esta funcionalidade nova é originalmente em PT; o mecanismo global ainda
        # pode traduzir widgets conhecidos sem impedir o uso.
        return

    def refresh_for_project(self):
        self.reload_scenes()

    def _apply_scene_scope(self,select_all=False):
        enabled = getattr(self, 'auto_translation_var', None)
        all_stems=sorted(set(self.audio_by_stem) if enabled is not None and enabled.get()=='1' else set(self.audio_by_stem)&set(self.text_by_stem),key=str.casefold)
        self.stems=filter_personalized_scenes(all_stems,getattr(self,'scope_folders',()),getattr(self,'scope_names',()))
        self.populate_scenes()
        if select_all and self.stems:
            self.scene_list.selection_clear(0,END)
            for i, stem in enumerate(self.stems):
                if stem not in getattr(self,'completed_stems',set()): self.scene_list.selection_set(i)
        status=getattr(self,'scope_status',None)
        if status is not None:
            choices=[str(p) for p in sorted(getattr(self,'scope_folders',()))]+['Personagem: '+n for n in sorted(getattr(self,'scope_names',()))]
            status.set((' + '.join(choices) if choices else 'Todas as pastas do projeto')+f' — {len(self.stems)} cenas com áudio + TXT')

    def add_scene_folder(self):
        if self.busy:return
        raw=filedialog.askdirectory(parent=self.root,title='Adicionar pasta de cenas dentro de WAV ORIGINAIS',initialdir=str(AUDIO_DIR))
        if not raw:return
        try:relative=Path(raw).resolve().relative_to(AUDIO_DIR.resolve())
        except ValueError:
            messagebox.showwarning('Pasta de cenas','Escolha uma pasta dentro de WAV ORIGINAIS deste projeto, para manter a correspondência com os TXT.',parent=self.root);return
        self.scope_folders.add(relative.as_posix())
        self._apply_scene_scope(select_all=True)

    def add_character_folders(self):
        if self.busy:return
        all_stems=sorted(set(self.audio_by_stem)&set(self.text_by_stem),key=str.casefold)
        folders=set()
        for stem in self.audio_by_stem:
            parent=Path(stem).parent
            while parent!=Path('.'):
                folders.add(parent);parent=parent.parent
        window=tk.Toplevel(self.root);window.title('SELECIONAR PASTA DO PERSONAGEM')
        window.geometry('760x540');window.minsize(620,400);window.transient(self.root.winfo_toplevel())
        bg=self.theme.get('surface','#FFFFFF');fg=self.theme.get('text','#111827');window.configure(bg=bg)
        tk.Label(window,text='Abra os capítulos e selecione a pasta do personagem. Somente pastas são mostradas.',bg=bg,fg=fg,anchor='w',wraplength=710).pack(fill='x',padx=12,pady=10)
        footer=tk.Frame(window,bg=bg);footer.pack(side='bottom',fill='x',padx=12,pady=12)
        info=StringVar(master=window,value='Selecione uma pasta. Ex.: Alexandria → DARYL.')
        tk.Label(window,textvariable=info,bg=bg,fg=fg,anchor='w',wraplength=710).pack(side='bottom',fill='x',padx=12,pady=5)
        panel=tk.Frame(window,bg=bg);panel.pack(fill='both',expand=True,padx=12)
        tree=ttk.Treeview(panel,show='tree',selectmode='browse')
        scroll=ttk.Scrollbar(panel,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');tree.pack(side='left',fill='both',expand=True)
        style=ttk.Style(window);style.configure('CharacterFolders.Treeview',background=self.theme.get('input',bg),fieldbackground=self.theme.get('input',bg),foreground=self.theme.get('input_text',fg),rowheight=25)
        style.map('CharacterFolders.Treeview',background=[('selected','#2563EB')],foreground=[('selected','#FFFFFF')]);tree.configure(style='CharacterFolders.Treeview')
        tree.insert('','end',iid='root',text='WAV ORIGINAIS',open=True)
        paths={}
        for folder in sorted(folders,key=lambda p:(len(p.parts),p.as_posix().casefold())):
            identity='folder:'+folder.as_posix();parent='folder:'+folder.parent.as_posix() if folder.parent!=Path('.') else 'root'
            tree.insert(parent,'end',iid=identity,text=folder.name,open=False);paths[identity]=folder
        def chosen():
            selection=tree.selection();return paths.get(selection[0]) if selection else None
        def update(_event=None):
            folder=chosen()
            if folder is None:
                info.set('Selecione a pasta de um personagem abaixo de WAV ORIGINAIS.');return
            count=len(filter_personalized_scenes(all_stems,names=[folder.name]))
            same=sum(p.name.casefold()==folder.name.casefold() for p in folders)
            info.set(f'{folder.as_posix()} — {same} pasta(s) com o nome {folder.name}; {count} cenas com áudio + TXT no projeto.')
        def confirm(all_named):
            if self.busy:return
            folder=chosen()
            if folder is None:info.set('Selecione uma pasta na árvore.');return
            matching=filter_personalized_scenes(all_stems,names=[folder.name]) if all_named else filter_personalized_scenes(all_stems,folders=[folder.as_posix()])
            if not matching:info.set('Nenhuma cena com áudio e TXT correspondente nesta seleção.');return
            if all_named:self.scope_names.add(folder.name)
            else:self.scope_folders.add(folder.as_posix())
            self._apply_scene_scope(select_all=True);window.destroy()
        for label,command,role in [('CANCELAR',window.destroy,'secondary'),('ADICIONAR TODAS COM ESTE NOME',lambda:confirm(True),'success'),('SOMENTE ESTA PASTA',lambda:confirm(False),'primary')]:
            button=Button(footer,text=label,command=command,relief='flat',font=('Segoe UI',8,'bold'),padx=8,pady=6)
            apply_button_style(button,self.theme,role);button.pack(side='right',padx=4)
        tree.bind('<<TreeviewSelect>>',update)
        tree.bind('<Return>',lambda _e:confirm(True))
        window.bind('<Escape>',lambda _e:window.destroy())
        window.grab_set();tree.focus_set()

    def clear_scene_scope(self):
        if self.busy:return
        self.scope_folders=set();self.scope_names=set()
        self._apply_scene_scope(select_all=True)

    def populate_scenes(self):
        previous=getattr(self,'_displayed_stems',None)
        if previous==self.stems:return
        selected={previous[int(i)] for i in self.scene_list.curselection() if previous and int(i)<len(previous)}
        self.scene_list.delete(0,END)
        finished=getattr(self,'completed_stems',set())
        if self.stems:self.scene_list.insert(END,*[("[OK] " if stem in finished else "")+stem for stem in self.stems])
        if previous is None and self.stems:
            for i,stem in enumerate(self.stems):
                if stem not in finished:self.scene_list.selection_set(i)
        else:
            for i,stem in enumerate(self.stems):
                if stem in selected:self.scene_list.selection_set(i)
        self._displayed_stems=list(self.stems)
        self.status_var.set(f"{len(self.stems)} cena(s) disponíveis.")

    def reload_scenes(self):
        if getattr(self,'_scan_running',False) or self.busy:return
        self._scan_running=True
        project=ROOT;audio_dir=AUDIO_DIR;text_dir=TEXT_DIR;result={};done=threading.Event()
        def worker():
            try:
                result['index']=(batch_tab.find_audio_by_stem(audio_dir),batch_tab.find_text_by_stem(text_dir))
                result['completed']=set(batch_tab.find_audio_by_stem(project / 'dublados personalizados'))
            except Exception as exc:result['error']=str(exc)
            finally:done.set()
        def finish():
            if not self.root.winfo_exists():return
            if not done.is_set():self.root.after(60,finish);return
            self._scan_running=False
            if project!=ROOT:return
            if self.busy:self.root.after(100,self.reload_scenes);return
            if 'error' in result:self.status_var.set('Falha ao atualizar cenas: '+result['error']);return
            self.audio_by_stem,self.text_by_stem=result['index']
            completed=result.get('completed',set())
            if completed!=getattr(self,'completed_stems',set()):self._displayed_stems=None
            self.completed_stems=completed
            self._apply_scene_scope()
        threading.Thread(target=worker,daemon=True).start()
        self.root.after(60,finish)

    def add_models(self, dialog_parent=None):
        paths = filedialog.askopenfilenames(parent=dialog_parent or self.root, title="Selecionar áudios modelo", filetypes=[("Áudios", "*.wav *.wave *.waw *.mp3 *.flac *.m4a *.ogg *.aac"), ("Todos", "*.*")])
        if not paths:
            return
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        added = []
        for raw in paths:
            src = Path(raw).expanduser().resolve()
            if not src.is_file() or src.suffix.casefold() not in AUDIO_EXTENSIONS:
                continue
            try:
                dest = prepare_voice_model_audio(src, MODEL_DIR)
            except Exception as exc:
                messagebox.showerror("Áudio modelo", f"Não foi possível preparar {src.name}:\n{exc}", parent=self.root)
                continue
            if dest not in self.models:
                self.models.append(dest); added.append(dest)
        self.model_combo.configure(values=[str(p) for p in self.models])
        if added:
            self.active_model_var.set(str(added[-1]))
            self._save_settings()
            self.status_var.set(f"{len(added)} modelo(s) adicionado(s).")

    def remove_model(self):
        raw = self.active_model_var.get().strip()
        if not raw:
            return
        target = Path(raw).expanduser().resolve()
        self.models = [p for p in self.models if p.resolve() != target]
        self.active_model_var.set(str(self.models[0]) if self.models else "")
        self.model_combo.configure(values=[str(p) for p in self.models])
        self._save_settings()

    def listen_model(self):
        raw = self.active_model_var.get().strip()
        if raw and Path(raw).is_file():
            self.audio_player.play_one(Path(raw), "OUVIR ÁUDIO MODELO")

    @property
    def busy(self):
        return self.running or bool(self.scene_review is not None and self.scene_review.busy)

    def _ensure_scene_review(self):
        """Controlador independente: mantém fonte, seleção e progresso personalizados."""
        if self.scene_review is not None:
            return self.scene_review
        try:
            from . import review_tab
        except ImportError:
            import review_tab
        review_tab.configure_project_root(ROOT)
        # Reutiliza as ações completas da Revisão sem exibir outra aba ou janela.
        self.scene_review_frame = ttk.Frame(self.root)
        controller = review_tab.ReviewApp(self.scene_review_frame, embedded=True,
                                         project_actions=self.project_actions, prompt_missing_text=False,
                                         scene_index=(self.audio_by_stem,self.text_by_stem))
        self.scene_review = controller
        controller.audio_player = self.audio_player
        self.audio_player.translation_controller = controller
        controller.voice_model_picker = lambda parent: choose_personalized_voice(parent,self.theme,ROOT,self)
        controller.audio_source_mode = "custom"
        controller.audio_source_var.set("Dublados personalizados")
        self.audio_player.set_dubbed_folder_name("dublados personalizados")
        actions = {name: (lambda stem, action=name: self._run_personalized_review_action(stem, action))
                   for name in ("open_audacity", "approve", "reject", "redub_other")}
        actions["redub_personalized"] = lambda stem: self._run_personalized_review_action(stem, "redub")
        self.audio_player.set_scene_integration(self._sync_personalized_scene, actions)
        self.audio_player.set_scene_text_integration(controller.load_scene_text_for_player,
                                                     controller.save_scene_text_from_player)
        self.audio_player.set_review_snapshot_provider(self.player_progress_snapshot)
        self.audio_player.set_review_preferences({
            "auto_open_var": controller.auto_open_var,
            "auto_open_command": controller.toggle_auto_open,
            "request_character_var": getattr(controller,"request_character_var",None),
            "request_translation_var": getattr(controller,"request_translation_var",None),
            "align_original_var": getattr(controller,'align_original_var',None),
            "translate_missing_var": getattr(controller,'translate_missing_var',None),
            "request_r_var": controller.request_r_var,
            "request_r_command": controller.toggle_r_request,
        })
        controller.set_fixed_r_pronunciation_provider(self.selected_r_pronunciation_id)
        if self.review_app is not None:
            controller.translation_settings_provider=getattr(self.review_app,"translation_settings_provider",None)
            controller.speech_language_provider=lambda: self.auto_translation_settings.get('language','Português (Brasil)')
            controller.voice_model_provider=lambda: self.selected_voice_engine()
            controller.alignment_settings_provider=getattr(self.review_app,'alignment_settings_provider',None)
        controller.set_player_refresh_callback(self._personalized_review_finished)
        controller.set_regeneration_progress_callback(self._review_stage_progress)
        controller.apply_theme(self.theme)
        return controller

    def _sync_personalized_scene(self, stem, index=0):
        controller = self._ensure_scene_review()
        # O worker continua associado à sua cena até finalizar.
        if controller.busy:
            return
        controller.audio_by_stem = dict(self.audio_by_stem)
        controller.text_by_stem = dict(self.text_by_stem)
        controller.default_stems = list(self.stems)
        controller.stems = list(self.stems)
        controller.audio_source_mode = "custom"
        if self.review_app is not None:
            controller.state.update(self.review_app.state)
        controller.refresh_scene_list(stem)
        if stem in controller.stems:
            controller.select_scene(controller.stems.index(stem))

    def _review_stage_progress(self, stem, clone, dub, phase, done=False, success=False):
        self.clone_stage_var.set(clone)
        self.dub_stage_var.set(dub)
        self.original_stage_var.set(100 if done and success else 1 if 'ritmo' in phase.lower() else 0)
        self.status_var.set(f"{stem}: {phase}")

    def mark_completed(self, stem):
        if not hasattr(self, 'completed_stems'): self.completed_stems=set()
        self.completed_stems.add(stem)
        if stem in self.stems:
            index=self.stems.index(stem)
            self.scene_list.delete(index)
            self.scene_list.insert(index, "[OK] " + stem)
            self.scene_list.selection_clear(index)

    def player_progress_snapshot(self, stem=None):
        if self.running:
            return {"clone_progress":self.clone_stage_var.get(), "dub_progress":self.dub_stage_var.get(),
                    "phase":self.status_var.get(), "regen":"Progresso por etapas; aguardando o gerador quando não há percentual."}
        return self._ensure_scene_review().player_review_snapshot(stem)

    def _personalized_review_finished(self, stem):
        self.mark_completed(stem)
        self.status_var.set(f"Áudio personalizado atualizado: {stem}")
        if self.review_app is not None and not self.review_app.busy:
            self.review_app.state.update(self.scene_review.state)
            self.review_app.refresh_scene_list()
            if self.review_app.audio_source_mode == "custom":
                self.review_app.audio_player.refresh_current_scene(stem)

    def _run_personalized_review_action(self, stem, action):
        controller = self._ensure_scene_review()
        if self.running or controller.busy or (self.review_app is not None and self.review_app.busy):
            self.status_var.set("Aguarde a dublagem atual terminar.")
            return
        if stem not in self.stems:
            return
        self._sync_personalized_scene(stem)
        if action in {"redub", "redub_other"}:
            box = self.audio_player.scene_text_box
            saved = controller.load_scene_text_for_player(stem)["text"]
            translation_requested=getattr(controller,"request_translation_var",None)
            if not getattr(self.audio_player, 'show_original_text', False) and not (translation_requested is not None and translation_requested.get()=="1") and box is not None and box.get("1.0", "end-1c").strip() != saved.strip():
                if not messagebox.askyesno("Texto não salvo", "Salvar a edição do TXT antes de redublar?",
                                          parent=self.audio_player.window or self.root):
                    return
                success, message = controller.save_scene_text_from_player(stem, box.get("1.0", "end-1c"))
                if not success:
                    self.status_var.set(message)
                    return
            if action == "redub" and custom_model_for_stem(stem) is None and not (getattr(controller,"request_character_var",None) is not None and controller.request_character_var.get()=="1"):
                raw = self.active_model_var.get().strip()
                model = Path(raw) if raw else None
                if model is None or not model.is_file():
                    messagebox.showwarning("Áudio modelo", "Selecione um modelo de voz para redublar esta cena.", parent=self.audio_player.window or self.root)
                    return
                controller.alternate_reference_audio = model
        controller.run_audio_review_action(stem, action)
        if self.review_app is not None:
            self.review_app.state.update(controller.state)
            if not self.review_app.busy:
                self.review_app.refresh_scene_list()

    def show_scene_context_menu(self, event):
        index = self.scene_list.nearest(event.y)
        bounds = self.scene_list.bbox(index)
        if bounds is None or not bounds[1] <= event.y < bounds[1]+bounds[3] or not 0 <= index < len(self.stems):
            return "break"
        if index not in self.scene_list.curselection():
            self.scene_list.selection_clear(0, END)
            self.scene_list.selection_set(index)
        self.scene_list.activate(index)
        self.scene_list.focus_set()
        stem = self.stems[index]
        original = self.audio_by_stem.get(stem)
        dubbed = CUSTOM_DIR / f"{stem}.wav"
        def open_audio(path):
            if path is None or not path.is_file():
                self.status_var.set("Áudio não encontrado para esta cena.")
                return
            if not reveal_in_file_manager(path):
                self.status_var.set(f"Não foi possível abrir o local de {path.name}.")
        def copy(value):
            self.root.clipboard_clear();self.root.clipboard_append(str(value))
            self.status_var.set(f"Copiado: {value}")
        theme=self.theme
        menu=tk.Menu(self.root,tearoff=0,bg=theme.get("input","#FFFFFF"),fg=theme.get("input_text","#111827"),activebackground=theme.get("select","#DBEAFE"),activeforeground=theme.get("input_text","#111827"))
        menu.add_command(label="OUVIR CENA",command=lambda:self.listen_selected_scene(event))
        menu.add_separator()
        menu.add_command(label="ABRIR LOCAL DO ÁUDIO DUBLADO",command=lambda:open_audio(dubbed))
        menu.add_command(label="ABRIR LOCAL DO ÁUDIO ORIGINAL",command=lambda:open_audio(original))
        menu.add_separator()
        menu.add_command(label="COPIAR NOME DO ÁUDIO",command=lambda:copy(dubbed.name))
        menu.add_command(label="COPIAR LOCAL DO ÁUDIO DUBLADO",command=lambda:copy(dubbed.parent))
        menu.add_command(label="COPIAR LOCAL DO ÁUDIO ORIGINAL",command=lambda:copy(original.parent) if original else self.status_var.set("Original não encontrado."))
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
        return "break"

    def listen_selected_scene(self, event=None):
        if event is not None:
            index = self.scene_list.nearest(event.y)
            box = self.scene_list.bbox(index)
            if box is None or not box[1] <= event.y < box[1] + box[3]:
                return "break"
        else:
            selection = self.scene_list.curselection()
            if not selection:
                return
            index = int(selection[0])
        if not 0 <= index < len(self.stems):
            return "break"
        stem = self.stems[index]
        personalized = CUSTOM_DIR / f"{stem}.wav"
        original = self.audio_by_stem.get(stem)
        path = personalized if personalized.is_file() else original
        if path is None or not path.is_file():
            self.status_var.set(f"Áudio não encontrado: {stem}")
            return "break"
        self._ensure_scene_review()
        self._sync_personalized_scene(stem, index)
        self.audio_player.set_dubbed_folder_name("dublados personalizados")
        playlist = [self.audio_by_stem[key] for key in self.stems]
        self.audio_player.play_one(path, f"OUVIR CENA — {stem}", playlist=playlist,
                                   index=index, scene_key=stem, scene_keys=self.stems)
        return "break"

    def listen_selected_original(self):
        selection = self.scene_list.curselection()
        if not selection:
            return
        stem = self.stems[int(selection[0])]
        path = self.audio_by_stem.get(stem)
        if path:
            self._ensure_scene_review()
            self._sync_personalized_scene(stem)
            self.audio_player.play_one(path, f"OUVIR ORIGINAL — {stem}", scene_key=stem)

    def open_output(self):
        CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt": os.startfile(str(CUSTOM_DIR))  # type: ignore[attr-defined]
            elif sys.platform == "darwin": subprocess.Popen(["open", str(CUSTOM_DIR)])
            else: subprocess.Popen(["xdg-open", str(CUSTOM_DIR)])
        except Exception as exc:
            messagebox.showerror("Pasta", str(exc), parent=self.root)

    def append_log(self, text: str):
        self.log.configure(state="normal"); self.log.insert(END, text + "\n"); self.log.see(END); self.log.configure(state="disabled")

    def redub_personalized_scene(self, stem):
        if self.running or (self.review_app is not None and getattr(self.review_app, "busy", False)):
            self.status_var.set("Aguarde a dublagem atual terminar antes de redublar.")
            return
        if stem not in self.audio_by_stem or stem not in self.text_by_stem:
            self.status_var.set("Original ou texto da cena não encontrado.")
            return
        model = custom_model_for_stem(stem)
        self.start_generation(stems_override=[stem], model_override=model)

    def selected_r_pronunciation_id(self):
        variable=getattr(self,"r_pronunciation_var",None)
        raw=variable.get() if variable is not None else "unchanged"
        return next((mode for label,mode in batch_tab.R_PRONUNCIATION_CHOICES if raw in (label,mode)),"unchanged")

    def toggle_translation(self):
        if self.busy:
            self.auto_translation_var.set('1' if getattr(self,'run_translation_settings',None) is not None else '0')
            return
        self._apply_scene_scope(select_all=True)

    def configure_translation(self):
        if self.busy:return
        from audio_translation import choose_settings
        selected=choose_settings(self.root,self.auto_translation_settings)
        if selected is not None:
            self.auto_translation_settings=selected
            self._save_settings()

    def configure_alignment(self):
        if self.busy:return
        from types import SimpleNamespace
        proxy=SimpleNamespace(root=self.root,theme=self.theme,align_audio_settings=dict(self.align_audio_settings),
            dependencies_button=SimpleNamespace(invoke=lambda:self.project_actions.get('prepare_audio_tools',lambda:None)()))
        def save():
            self.align_audio_settings=dict(proxy.align_audio_settings)
            self._save_settings()
        proxy.save_voice_settings=save
        batch_tab.BatchApp.configure_audio_alignment(proxy)

    def start_generation(self, stems_override=None, model_override=None):
        if self.busy or (self.review_app is not None and self.review_app.busy):
            return
        model_raw = self.active_model_var.get().strip()
        model = model_override or (Path(model_raw).expanduser() if model_raw else None)
        if model is None or not model.is_file():
            messagebox.showwarning("Áudio modelo", "Adicione e selecione um áudio modelo antes de dublar.", parent=self.root); return
        indices = list(self.scene_list.curselection())
        if not indices and not stems_override:
            messagebox.showwarning("Cenas", "Selecione pelo menos uma cena.", parent=self.root); return
        self.run_voice_model=self.selected_voice_engine()
        try:infer_prefix = batch_tab.find_voice_command(self.run_voice_model)
        except Exception as exc:
            messagebox.showerror('Modelo de voz', str(exc), parent=self.root);return
        if not infer_prefix:
            messagebox.showerror("OmniVoice", "OmniVoice não foi encontrado. Prepare/instale as ferramentas de clonagem primeiro.", parent=self.root); return
        stems = list(stems_override) if stems_override else [self.stems[int(i)] for i in indices]
        if stems_override is None:
            pending=[]
            for stem in stems:
                target=CUSTOM_DIR / f"{stem}.wav"
                if target.is_file() and target.stat().st_size>44:
                    self.mark_completed(stem)
                    self.append_log(f"PULADO: {stem} já tem dublagem personalizada.")
                else: pending.append(stem)
            stems=pending
            if not stems:
                self.status_var.set("Todas as cenas selecionadas já estão dubladas. Use REDUBLAR para refazer uma cena.")
                return
        # Libera possíveis handles de WAV antes de sobrescrever personalizados.
        try:
            self.audio_player.stop(announce=False)
        except Exception:
            pass
        if self.review_app is not None:
            try:
                self.review_app.audio_player.stop(announce=False)
            except Exception:
                pass
        self.stop_after_current = False
        self.run_alignment_settings = dict(self.align_audio_settings) if self.align_audio_var.get()=='1' else None
        self.run_translation_settings = dict(self.auto_translation_settings) if self.auto_translation_var.get()=='1' else None
        from audio_translation import settings
        self.run_speech_language=settings(self.auto_translation_settings)['tts_language']
        from f5_backend import MODEL as F5_MODEL, validate
        if self.run_voice_model == F5_MODEL:
            try:validate(self.run_speech_language)
            except ValueError as exc:
                messagebox.showerror('F5-TTS Russian',str(exc),parent=self.root);return
        self.append_log('Gerador: '+self.run_voice_model)
        if self.run_translation_settings is not None:
            from audio_translation import translation_python
            try:translation_python()
            except Exception as exc:
                messagebox.showerror('Transcrição / tradução',str(exc),parent=self.root);return
        self.running = True; self.cancel_requested = False; self.progress_var.set(0); self.generate_button.configure(state="disabled"); self.cancel_button.configure(state="normal")
        self.append_log(f"Modelo de voz: {model.name}")
        self.append_log(f"Cenas selecionadas: {len(stems)}")
        r_mode=self.selected_r_pronunciation_id()
        self.append_log("Pronúncia do R: " + next(label for label,mode in batch_tab.R_PRONUNCIATION_CHOICES if mode==r_mode))
        threading.Thread(target=self._worker, args=(stems, model.resolve(), infer_prefix, stems_override is not None, r_mode), daemon=True).start()

    def selected_voice_engine(self):
        provider=getattr(self.review_app,'voice_model_provider',None)
        return provider() if callable(provider) else batch_tab.MODEL

    def cancel_generation(self):
        self.cancel_requested = True
        process = self.current_process
        if process is not None and process.poll() is None:
            try: process.terminate()
            except OSError: pass
        self.status_var.set("Cancelamento solicitado...")

    def _worker(self, stems: list[str], model: Path, infer_prefix: list[str], force=False, r_mode="unchanged"):
        manifest = load_custom_manifest()
        total = len(stems)
        completed = 0
        for number, stem in enumerate(stems, 1):
            if self.cancel_requested or getattr(self, 'stop_after_current', False): break
            existing = CUSTOM_DIR / f"{stem}.wav"
            if not force and existing.is_file() and existing.stat().st_size>44:
                self.queue.put(("refresh_scene",stem))
                self.queue.put(("log",f"PULADO: {stem} já foi dublado."))
                self.queue.put(("progress",number/total*100.0))
                continue
            self.queue.put(("stage",0,0,0,"Preparando voz-modelo: " + stem))
            original = self.audio_by_stem[stem]
            text_file = self.text_by_stem.get(stem, ROOT / 'TXT TEXTO PORTUGUES' / (stem+'.txt'))
            try:
                language = getattr(self,'run_speech_language',batch_tab.LANGUAGE)
                text = text_file.read_text(encoding="utf-8-sig").strip() if text_file.is_file() else ''
                if not text and getattr(self,'run_translation_settings',None) is not None:
                    from audio_translation import generate_text
                    text,language=generate_text(original,text_file,ROOT,stem,self.run_translation_settings,
                        lambda value:self.queue.put(('log',value)),cancelled=lambda:self.cancel_requested,
                        on_result=lambda value,path:self.queue.put(('generated_text',stem,text_file if text_file.is_file() else path)))
                if not text:
                    raise RuntimeError("TXT em português está vazio")
                target = CUSTOM_DIR / f"{stem}.wav"; target.parent.mkdir(parents=True, exist_ok=True)
                work_dir=ROOT / "revisoes" / "_intermediarios" / "personalizados" / Path(stem).parent
                work_dir.mkdir(parents=True,exist_ok=True)
                temp = work_dir / f".{target.stem}_{os.getpid()}_{time.time_ns()}.__sintese.wav"
                finalized=temp.with_name(temp.stem+".__expressao.wav")
                from audio_translation import synthesis_settings
                voice_model,instruction=synthesis_settings(language,getattr(self,'run_voice_model',batch_tab.MODEL),batch_tab.INSTRUCT)
                command = [*infer_prefix, "--model", voice_model, "--text", batch_tab.apply_r_pronunciation(text, r_mode if language in ('pt','Portuguese') else 'unchanged'), "--language", language, "--instruct", instruction, "--ref_audio", str(model), "--output", str(temp)]
                self.queue.put(("status", f"[{number}/{total}] Clonando voz-modelo e dublando: {stem}"))
                self.queue.put(("log", f"[{number}/{total}] {stem}"))
                self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **batch_tab.hidden_process_kwargs())
                observer=GenerationProgress(lambda clone,dub,phase:self.queue.put(("stage",clone,dub,0,stem+": "+phase)))
                lines=[]
                for line in self.current_process.stdout:
                    observer.feed(line)
                    lines.append(line)
                    if len(lines)>100:lines.pop(0)
                self.current_process.wait()
                stdout=''.join(lines)
                rc = self.current_process.returncode
                self.current_process = None
                if self.cancel_requested: break
                if rc != 0 or not temp.is_file():
                    raise RuntimeError((stdout or f"OmniVoice terminou com código {rc}")[-1600:])
                self.queue.put(("status", f"[{number}/{total}] Aplicando ritmo/pausas/intensidade do original: {stem}"))
                self.queue.put(("stage",100,100,1,"Aplicando ritmo / pausas do original: "+stem))
                if getattr(self,'run_alignment_settings',None):
                    batch_tab.BatchApp.align_generated_audio(self,temp,original)
                    shutil.copy2(temp,finalized)
                else:
                    match_original_expression(temp, original, finalized, progress_callback=lambda value:self.queue.put(("stage",100,100,value,"Aplicando ritmo / pausas do original: "+stem)))
                if self.cancel_requested: break
                _safe_replace_file(finalized,target)
                temp.unlink(missing_ok=True)
                try: rel_model = model.relative_to(ROOT).as_posix()
                except ValueError: rel_model = str(model)
                manifest[stem] = {"voice_model": rel_model, "original": str(original), "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "expression_transfer": "duration_pauses_dynamics_approximation"}
                _save_json(MANIFEST_FILE, manifest)
                completed += 1
                self.queue.put(("stage",100,100,100,"Concluído: "+stem))
                self.queue.put(("refresh_scene", stem))
                self.queue.put(("log", f"OK: {target.relative_to(ROOT)}"))
            except Exception as exc:
                self.queue.put(("log", f"FALHA em {stem}: {exc}"))
            self.queue.put(("progress", number / total * 100.0))
        self.queue.put(("done", completed, total, self.cancel_requested))

    def poll_messages(self):
        try:
            while True:
                item = self.queue.get_nowait(); kind = item[0]
                if kind == "status": self.status_var.set(item[1])
                elif kind == 'generated_text': self.text_by_stem[item[1]]=item[2]
                elif kind == "log": self.append_log(item[1])
                elif kind == "stage":
                    self.clone_stage_var.set(item[1]);self.dub_stage_var.set(item[2]);self.original_stage_var.set(item[3])
                    self.status_var.set(item[4])
                elif kind == "refresh_scene":
                    self.mark_completed(item[1])
                    callback = self.project_actions.get('scene_completed')
                    if callback:
                        callback(item[1], self.audio_by_stem[item[1]], self.text_by_stem[item[1]], 'custom')
                    self.audio_player.refresh_current_scene(item[1])
                elif kind == "progress": self.progress_var.set(float(item[1]))
                elif kind == "done":
                    completed, total, cancelled = item[1], item[2], item[3]
                    self.running = False; self.generate_button.configure(state="normal"); self.cancel_button.configure(state="disabled")
                    self.status_var.set(("Parado" if cancelled else "Concluído") + f": {completed}/{total} personalizados gerados.")
                    # Each published scene was registered incrementally above.
                    # Do not switch source or reload an editor at the end of a batch.
        except queue.Empty:
            pass
        try: self.root.after(120, self.poll_messages)
        except Exception: pass
