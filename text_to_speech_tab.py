"""Editor independente de texto para fala usando o runtime OmniVoice gerenciado."""
from __future__ import annotations

import os
import json
import queue
import re
import shutil
import subprocess
import threading
import time
import hashlib
import tempfile
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # permite testes sem Tk funcional
    tk = None

import batch_tab
from ui_theme import apply_button_style
from emotional_speech import VoiceProfile, FFmpegNormalizer, parse_emotion_tags, generate_expressive_speech
from warm_inference import warm_batch, WarmInference


AUDIO_EXTENSIONS = batch_tab.AUDIO_EXTENSIONS
MICROPHONE_CODE = r'''
import sys,json
import sounddevice as sd
if len(sys.argv)==1:
    devices=sd.query_devices();default=sd.default.device[0];hosts=sd.query_hostapis()
    print('DUBLASKIZON_MIC '+json.dumps([{'id':i,'name':d['name'],'rate':int(d['default_samplerate']),'default':i==default,'api':hosts[d['hostapi']]['name']} for i,d in enumerate(devices) if d['max_input_channels']>0]))
else:
    import numpy as np,wave
    device=int(sys.argv[1]);seconds=float(sys.argv[2]);rate=int(sd.query_devices(device,'input')['default_samplerate'])
    if not 3<=seconds<=10:raise ValueError('Grave entre 3 e 10 segundos.')
    pcm=sd.rec(round(seconds*rate),samplerate=rate,channels=1,dtype='float32',device=device)
    sd.wait()
    if not np.isfinite(pcm).all() or np.max(np.abs(pcm))<.001:raise ValueError('Gravação silenciosa; confira o microfone.')
    with wave.open(sys.argv[3],'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(rate)
        output.writeframes((np.clip(pcm,-1,1)*32767).astype(np.int16).tobytes())
'''


def microphone_command(*args):
    from dependency_setup import managed_python
    python=managed_python()
    if not python:raise RuntimeError('Prepare TEXTO PARA FALA no botão 1 dos Requisitos.')
    return [str(python),'-u','-c',MICROPHONE_CODE,*map(str,args)]


def ensure_microphone_runtime():
    """Install only capture dependencies if the active environment predates recording."""
    python=microphone_command()[0]
    options=dict(capture_output=True,text=True,encoding='utf-8',errors='replace',**batch_tab.hidden_process_kwargs())
    check=subprocess.run([python,'-c','import sounddevice;print(sounddevice.__version__)'],timeout=30,**options)
    if check.returncode:
        install=subprocess.run([python,'-m','pip','install','--index-url','https://pypi.org/simple',
                                '--retries','3','--timeout','30','sounddevice>=0.5,<0.6'],timeout=300,**options)
        if install.returncode:
            raise RuntimeError('Não foi possível preparar a captura de microfone: '+install.stderr[-1200:])

MARKER_RE = re.compile(r"\[\[(EXPRESSAO|VOZ):([^\]]+)\]\]", re.IGNORECASE)

# Apenas sussurro possui um atributo de estilo. Sons não verbais têm tags
# oficiais; altura da voz não deve ser confundida com emoção.
EXPRESSIONS = (
    ("ALEGRE 😄", "alegre", ""),
    ("RINDO 😆", "rindo", ""),
    ("TRISTE 😢", "triste", ""),
    ("SUSSURRO 🤫", "sussurro", "whisper"),
    ("SUSPIRO 😮‍💨", "suspiro", ""),
    ("SURPRESO 😮", "surpreso", ""),
    ("DÚVIDA 🤔", "duvida", ""),
    ("DESCONTENTE 😒", "descontente", ""),
)
NONVERBAL_TAGS = {"rindo":"[laughter]", "suspiro":"[sigh]", "surpreso":"[surprise-oh]",
                 "duvida":"[question-oh]", "descontente":"[dissatisfaction-hnn]"}
NATIVE_NONVERBAL_SOUNDS = {'rindo','suspiro','duvida'}
EXTRA_EXPRESSIONS = (
    ("GRITO 😠", "grito"), ("GRITO FORTE 😱", "grito_forte"),
    ("CHORO 😢 · som", "choro"), ("CHORO INTENSO 😭 · som", "choro_intenso"),
    ("RAIVA 😡", "raiva"), ("MEDO 😨", "medo"), ("ANIMADO 🤩", "animado"),
    ("VOZ SUAVE 🙂", "suave"), ("NERVOSO 😬", "nervoso"), ("CALMO 😌", "calmo"),
    ("SARCÁSTICO 😏", "sarcastico"), ("OFEGANTE 😮‍💨 · som", "ofegante"),
)

# Only expose reactions backed by a bundled, verified audio reference.
# Legacy/custom tags are still parsed, but missing references block UI generation.
AVAILABLE_EXPRESSIONS = (
    ('NEUTRO 🙂','neutro'), ('ALEGRE 😄','alegre'), ('TRISTE 😢','triste'),
    ('RAIVA 😡','raiva'), ('SUSSURRO 🤫','sussurro'), ('SURPRESO 😮','surpreso'),
)


def unavailable_emotions(source: str, references: dict, native_keys=(), *, allow_nonverbal=False) -> list[str]:
    supported={'neutro',*native_keys}
    supported.update(key for key,value in references.items()
                     if Path(value).is_file() and Path(value).suffix.casefold() in AUDIO_EXTENSIONS)
    if allow_nonverbal:supported.update(NATIVE_NONVERBAL_SOUNDS)
    return sorted({part['emocao'] for part in parse_emotion_tags(source)}-supported)

def generation_error(report, code):
    """Resumo legível; o relatório completo permanece no quadro de mensagens."""
    if 'DUBLASKIZON_NEEDS_REVIEW:' in str(report):
        from speech_completeness import friendly_error
        return friendly_error(report) + '\n\nDetalhes em PROCESSOS E MENSAGENS.'
    for line in reversed(str(report).splitlines()):
        if re.match(r'^(RuntimeError|ValueError|OSError|FileNotFoundError|ImportError|ModuleNotFoundError):',line.strip()):
            return line.split(':',1)[1].strip()+"\n\nDetalhes em PROCESSOS E MENSAGENS."
    return f"O motor não concluiu a geração (código {code}). Consulte PROCESSOS E MENSAGENS."
OUTPUT_FOLDERS = {"project":"WAV ORIGINAIS TEXTO para FALA", "original":"ÁUDIO ORIGINAL TEXTO para FALA",
                  "personal":"VOZ MODELO TEXTO para FALA", "system":"DO SISTEMA TEXTO para FALA"}


def output_location(project_root, mode, reference=None, voice_name="fala"):
    root=Path(project_root).resolve()
    source=Path(reference).resolve() if reference else None
    category=mode
    safe_voice_name=re.sub(r'[<>:"/\\|?*]', '_', str(voice_name))
    relative=Path((source.stem if source else safe_voice_name)+".wav")
    if mode=="original" and source:
        try:
            relative=source.relative_to(root/"WAV ORIGINAIS").with_suffix(".wav")
            category="project"
        except ValueError:pass
    destination=root/"TEXTO PARA FALA"/OUTPUT_FOLDERS[category]/relative
    counter=2
    while destination.exists():
        destination=destination.with_name(relative.stem+f"_{counter}.wav");counter+=1
    return destination

SYSTEM_VOICES = (
    ("Mulher jovem", "female, young adult, moderate pitch"),
    ("Mulher adulta grave", "female, middle-aged, low pitch"),
    ("Homem jovem", "male, young adult, moderate pitch"),
    ("Homem adulto grave", "male, middle-aged, low pitch"),
    ("Narrador idoso", "male, elderly, low pitch"),
    ("Criança — menina", "female, child, high pitch"),
    ("Criança — menino", "male, child, high pitch"),
    ("Sussurro", "whisper, moderate pitch"),
)


def render_expression_text(source: str) -> tuple[str, list[str]]:
    """Remove marcadores da fala e retorna apenas instruções OmniVoice válidas."""
    instructions: list[str] = []
    by_key = {key: instruction for _label, key, instruction in EXPRESSIONS}
    def replace(match):
        if match.group(1).casefold() == "expressao":
            instruction = by_key.get(match.group(2).strip().casefold(), "")
            if instruction and instruction not in instructions:
                instructions.append(instruction)
        return NONVERBAL_TAGS.get(match.group(2).strip().casefold(), "") if match.group(1).casefold()=="expressao" else ""
    text = MARKER_RE.sub(replace, str(source or ""))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()
    return text, instructions


class TextToSpeechApp:
    def __init__(self, parent, project_root, project_actions=None, theme=None):
        if tk is None:
            raise RuntimeError("Tkinter indisponível")
        self.parent = parent
        self.project_root = Path(project_root).resolve()
        self.project_actions = project_actions or {}
        self.theme = theme or self._theme()
        self.running = False
        self.process = None
        self.events = queue.Queue()
        self.originals: list[Path] = []
        self.personal: list[Path] = []
        self.system_audio: list[Path] = []
        self.cancel_event = threading.Event()
        self.native_automatic = tk.BooleanVar(value=True)
        self.native_voice = tk.StringVar(value='masculina')
        self.preview_expressions = tk.BooleanVar(value=False)
        self.reference_mode = tk.StringVar(value="original")
        from qwen_backend import MODEL as QWEN_MODEL
        self.engine = tk.StringVar(value="Qwen3-TTS — clonagem / vozes com instruções" if batch_tab.MODEL==QWEN_MODEL else "OmniVoice / F5 — referências emocionais")
        self.reference_text = tk.StringVar()
        self.status = tk.StringVar(value="Pronto. Selecione uma voz, escreva o texto e clique em DUBLAR.")
        self.output_path: Path | None = None
        self.results=[]
        from audio_player import AudioPlayerManager
        self.audio_player=AudioPlayerManager(parent, self.project_root)
        self.audio_player.set_scene_text_integration(self._load_result_text,self._save_result_text)
        self._build_ui()
        self.refresh_for_project()
        self._style_trees()
        self.parent.after(120, self._poll)

    def _theme(self):
        root = self.parent.winfo_toplevel()
        app = getattr(root, "dublaskizon_app", None)
        if app and hasattr(app, "current_theme"):
            return app.current_theme()
        return {"root":"#202938","surface":"#2A3546","panel":"#314055","text":"#F8FAFC","muted":"#CBD5E1","input":"#35445A","input_text":"#FFFFFF","border":"#52627A","select":"#2563EB","buttons":{}}

    def _button(self, parent, text, command, role="secondary", **kwargs):
        button = tk.Button(parent, text=text, command=command, relief="flat", cursor="hand2", **kwargs)
        button._dublaskizon_role = role
        apply_button_style(button, self.theme, role)
        return button

    def _build_ui(self):
        t = self.theme
        # The main application already provides a ScrollableFrame for this tab.
        # A nested Canvas reduces its requested height and creates two scrollbars.
        root = tk.Frame(self.parent, bg=t["root"])
        root.pack(fill="both",expand=True,padx=8,pady=5)
        engine_row=tk.Frame(root,bg=t["root"]);engine_row.pack(fill="x",pady=(0,4))
        tk.Label(engine_row, text="TEXTO PARA FALA", bg=t["root"], fg=t["text"], font=("Segoe UI", 18, "bold")).pack(side="left",padx=(0,14))
        tk.Label(engine_row,text="MOTOR",bg=t["root"],fg=t["text"]).pack(side="left")
        self.engine_choice=ttk.Combobox(engine_row,textvariable=self.engine,state="readonly",values=("OmniVoice / F5 — referências emocionais", "Qwen3-TTS — clonagem / vozes com instruções"),width=36)
        self.engine_choice.pack(side="left",padx=6,fill="x",expand=True)
        self.engine.trace_add("write",lambda *_:self._refresh_system_voices())
        self._button(engine_row,"REQUISITOS",self.open_requirements,"primary",padx=10,pady=4).pack(side="left")
        from speech_completeness import mount_controls
        mount_controls(root, self.project_root)
        libraries = tk.PanedWindow(root, orient="horizontal", sashwidth=5, bg=t["border"], bd=0)
        libraries.pack(fill="both", expand=True)
        left = self._library_panel(libraries,"ÁUDIOS ORIGINAIS / NORMAIS")
        middle = self._library_panel(libraries,"VOZES DO SISTEMA")
        right = self._library_panel(libraries,"ESCOLHIDAS POR MIM")
        self.voice_panels={'original':left[0],'system':middle[0],'personal':right[0]}
        libraries.add(left[0], stretch="always"); libraries.add(middle[0], stretch="always"); libraries.add(right[0], stretch="always")
        self.original_tree, self.system_tree, self.personal_tree = left[1], middle[1], right[1]
        # Keep each action beside its requested title, without an extra toolbar.
        self.load_originals_button=self._button(left[0]._library_header,"CARREGAR DA PASTA WAV ORIGINAIS",self.load_project_originals,"primary",font=("Segoe UI",8,"bold"),padx=3,pady=2)
        self.load_originals_button.pack(side="right",padx=3)
        self.add_original_button=self._button(middle[0]._library_header,"ADICIONAR ÁUDIO ORIGINAL",self.add_original,"teal",font=("Segoe UI",8,"bold"),padx=3,pady=2)
        self.add_original_button.pack(side="right",padx=3)
        self.add_voice_button=self._button(right[0]._library_header,"ADICIONAR VOZ MODELO",self.add_personal_voice,"accent",font=("Segoe UI",8,"bold"),padx=3,pady=2)
        self.add_voice_button.pack(side="right",padx=3)
        self._button(middle[0],"ADICIONAR ÁUDIO DO SISTEMA",self.add_system_voice,"teal",pady=2).pack(fill="x",padx=5,pady=2)
        for mode,tree in (("original",self.original_tree),("system",self.system_tree),("personal",self.personal_tree)):
            tree.bind("<<TreeviewSelect>>",lambda _e,m=mode,tr=tree:self.reference_mode.set(m) if tr.selection() else None)
        self.system_tree.bind("<Double-1>",lambda _e:self.listen_selected("system"))
        self.original_tree.bind("<Double-1>", lambda _e:self.listen_selected("original"))
        self.personal_tree.bind("<Double-1>", lambda _e:self.listen_selected("personal"))
        for name, instruction in SYSTEM_VOICES:
            self.system_tree.insert("", "end", iid=name, text=name, values=(instruction,))

        self._refresh_system_voices()
        editor_shell=tk.Frame(root,bg=t["root"]);editor_shell.pack(fill="both",expand=True,pady=(4,0))
        result_panel,result_tree=self._library_panel(editor_shell,"ÁUDIOS DUBLADOS — modo selecionado")
        result_panel.pack(side="right",fill="both",padx=(10,0));result_panel.configure(width=300)
        self.result_tree=result_tree
        result_tree.bind("<Double-1>",lambda _e:self.listen_output())
        self._button(result_panel,"OUVIR CENA",self.listen_output,"teal",pady=6).pack(fill="x",padx=5,pady=5)
        self._button(result_panel,"ABRIR PASTA DE SAÍDA",self.open_output_folder,"secondary",pady=6).pack(fill="x",padx=5,pady=5)
        self._button(result_panel,"ATUALIZAR RESULTADOS",self.refresh_results,"secondary",pady=6).pack(fill="x",padx=5,pady=5)
        root=tk.Frame(editor_shell,bg=t["root"]);root.pack(side="left",fill="both",expand=True)
        expression = tk.LabelFrame(root,text="EXPRESSÕES — clique para inserir no ponto do cursor",bg=t["panel"],fg=t["text"],font=("Segoe UI",9,"bold"),bd=1,relief="solid")
        expression.pack(fill="x",pady=(0,3))
        self.expression_panel=expression
        self.expression_buttons=[]
        all_expressions=self._available_expressions()
        for index,(label,key) in enumerate(all_expressions):
            label=label.replace(' · som','')
            button=self._button(expression,label,lambda k=key:self.expression_action(k),"secondary",font=("Segoe UI Emoji",8,"bold"),padx=1,pady=1,height=1,wraplength=0)
            button.grid(row=index//6,column=index%6,sticky="nsew",padx=1,pady=1)
            expression.columnconfigure(index%6,weight=1,uniform="expression")
            self.expression_buttons.append(button)
        self.preview_button=tk.Checkbutton(expression,text='OUVIR EXPRESSÕES',variable=self.preview_expressions,bg=t['panel'],fg=t['text'],selectcolor=t['input'],activebackground=t['panel'],activeforeground=t['text'],font=('Segoe UI',9,'bold'))
        self.preview_button.grid(row=(len(all_expressions)+5)//6,column=0,columnspan=6,sticky='e',padx=1,pady=2)
        native=tk.Frame(root,bg=t['root']);native.pack(fill='x',pady=2)
        tk.Checkbutton(native,text='REAÇÕES NATIVAS AUTOMÁTICAS',variable=self.native_automatic,bg=t['root'],fg=t['text'],selectcolor=t['input'],activebackground=t['root'],activeforeground=t['text']).pack(side='left')
        self.native_voice_choice=ttk.Combobox(native,textvariable=self.native_voice,values=('masculina','feminina'),state='readonly',width=14,font=('Segoe UI',13,'bold'))
        self.native_voice_choice.pack(side='left',padx=6)
        self.prepare_native_button=self._button(native,'PREPARAR REAÇÕES NATIVAS',self.prepare_native_emotions,'teal',pady=5,padx=6)
        self.prepare_native_button.pack(side='left',padx=3)
        self._button(native,'PREPARAR NOVAS REAÇÕES (QWEN)',self.prepare_qwen_emotions,'accent',pady=5,padx=6).pack(side='left',padx=3)
        self.native_voice.trace_add('write',lambda *_:self._refresh_expression_buttons())
        self._native_blink=False
        self.parent.after(650,self._blink_native_preparation)
        self.custom_expression_panel=tk.Frame(root,bg=t['root'])
        self.custom_expression_panel.pack(fill='x',pady=2)
        self.custom_expression_buttons=[]
        self._button(self.custom_expression_panel,"REFERÊNCIAS PRÓPRIAS (OPCIONAL)",self.configure_emotional_voice,"accent",font=('Segoe UI',8,'bold'),padx=3,pady=1).grid(row=0,column=0,sticky='w',padx=(0,8))
        tk.Label(root,text="Todos os botões têm referência para ouvir. Seed-VC aproxima o timbre; emoção e sotaque podem variar. Tags sem suporte são avisadas antes de gerar.",wraplength=950,bg=t["root"],fg=t["muted"]).pack(anchor="w")
        self.reference_mode.trace_add("write",lambda *_:self.refresh_results())
        self.reference_mode.trace_add('write',lambda *_:self._refresh_custom_expression_buttons())

        modes=tk.Frame(root,bg=t["root"]);modes.pack(fill="x")
        self.mode_buttons={}
        for label,value,color in (("ORIGINAL","original","#2563EB"),("DO SISTEMA","system","#D97706"),("ESCOLHIDO POR MIM","personal","#7C3AED")):
            button=tk.Radiobutton(modes,text=label,value=value,variable=self.reference_mode,indicatoron=False,selectcolor=color,bg=t["panel"],fg=t["text"],activebackground=color,activeforeground="white",font=("Segoe UI",9,"bold"),relief="flat",pady=6)
            button.pack(side="left",fill="x",expand=True,padx=2)
            self.mode_buttons[value]=button
        tk.Label(root,text="TEXTO EDITÁVEL",bg=t["root"],fg=t["text"],font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(7,2))
        self.text=tk.Text(root,height=5,wrap="word",undo=True,bg=t["input"],fg=t["input_text"],insertbackground=t["input_text"],selectbackground=t["select"],font=("Segoe UI",11),bd=1,relief="solid")
        self.text.pack(fill="x")
        tk.Label(root,text="Transcrição da referência (OPCIONAL — deixe vazio para reconhecer automaticamente)",bg=t["root"],fg=t["text"]).pack(anchor="w",pady=(4,0))
        self.ref_entry=tk.Entry(root,textvariable=self.reference_text,bg=t["input"],fg=t["input_text"],insertbackground=t["input_text"])
        self.ref_entry.pack(fill="x")
        self.text.insert("1.0","Digite aqui o texto que será transformado em fala.")
        bottom=tk.Frame(root,bg=t["root"]);bottom.pack(fill="x",pady=(8,0))
        self.generate_button=self._button(bottom,"DUBLAR",self.start_generation,"success",font=("Segoe UI",11,"bold"),padx=35,pady=8);self.generate_button.pack(side="left")
        self.listen_button=self._button(bottom,"OUVIR RESULTADO",self.listen_output,"teal",padx=16,pady=8);self.listen_button.pack(side="left",padx=6)
        self.cancel_button=self._button(bottom,"CANCELAR",self.cancel,"danger",padx=16,pady=8);self.cancel_button.pack(side="left");self.cancel_button.configure(state="disabled")
        self.progress=ttk.Progressbar(bottom,mode="indeterminate",length=220)
        self.progress.pack(side="right",padx=(8,0))
        tk.Label(root,textvariable=self.status,bg=t["root"],fg=t["muted"],anchor="w").pack(fill="x",pady=(5,0))
        log_frame=tk.LabelFrame(root,text="PROCESSOS E MENSAGENS",bg=t["panel"],fg=t["text"],font=("Segoe UI",9,"bold"))
        log_frame.pack(fill="both",expand=True,pady=(7,0))
        self.process_log=tk.Text(log_frame,height=4,wrap="word",state="disabled",font=("Consolas",9),bg=t["input"],fg=t["input_text"])
        log_scroll=ttk.Scrollbar(log_frame,command=self.process_log.yview)
        self.process_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right",fill="y");self.process_log.pack(fill="both",expand=True)


    def _append_log(self,message):
        self.process_log.configure(state="normal")
        self.process_log.insert("end",str(message)+"\n")
        if int(self.process_log.index("end-1c").split('.')[0])>1500:self.process_log.delete("1.0","300.0")
        self.process_log.see("end");self.process_log.configure(state="disabled")

    def _refresh_system_voices(self):
        if not hasattr(self,"system_tree"):return
        self.system_tree.delete(*self.system_tree.get_children())
        voices=SYSTEM_VOICES if not self.engine.get().startswith('Qwen') else (
            ('QWEN_SPEAKER:Ryan','QWEN_SPEAKER:Ryan'),('QWEN_SPEAKER:Vivian','QWEN_SPEAKER:Vivian'))
        for name,instruction in voices:
            label={'QWEN_SPEAKER:Ryan':'Ryan — voz masculina Qwen','QWEN_SPEAKER:Vivian':'Vivian — voz feminina Qwen'}.get(name,name)
            self.system_tree.insert("","end",iid=name,text=label,values=(instruction,))
        for index,path in enumerate(self.system_audio):
            self.system_tree.insert("","end",iid=f"audio:{index}",text=path.name,values=(str(path),))
        for voice in ('masculina','feminina'):
            self.system_tree.insert('','end',iid='nativa:'+voice,text='Voz brasileira '+voice+' — banco nativo')

    def _library_panel(self,parent,title):
        t=self.theme;frame=tk.Frame(parent,bg=t["panel"],bd=1,relief="solid")
        header=tk.Frame(frame,bg=t["panel"]);header.pack(fill="x",padx=3,pady=3)
        frame._library_header=header
        tk.Label(header,text=title,bg=t["panel"],fg=t["text"],font=("Segoe UI",9,"bold")).pack(side="left")
        tree=ttk.Treeview(frame,columns=("detail",),show="tree",height=5,selectmode="browse",style="DublaskizonTTS.Treeview")
        scroll=ttk.Scrollbar(frame,orient="vertical",command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y");tree.pack(fill="both",expand=True,padx=(5,0),pady=(0,5))
        return frame,tree

    def _style_trees(self):
        t=self.theme;style=ttk.Style(self.parent)
        style.configure("DublaskizonTTS.Treeview",background=t["input"],fieldbackground=t["input"],foreground=t["input_text"])
        style.map("DublaskizonTTS.Treeview",background=[("selected",t["select"])],foreground=[("selected","#FFFFFF")])
        self._color_voice_panels()

    def apply_theme(self,theme):
        self.theme=theme
        self._style_trees()

    def _color_voice_panels(self):
        palette={'original':('#2563EB','#172E56'),'system':('#D97706','#54330E'),'personal':('#7C3AED','#332253')}
        style=ttk.Style(self.parent)
        for mode,(color,field) in palette.items():
            panel=self.voice_panels[mode]
            def paint(widget):
                if isinstance(widget,(tk.Frame,tk.Label,tk.Button)):
                    options={'bg':color}
                    if isinstance(widget,(tk.Label,tk.Button)):options['fg']='white'
                    if isinstance(widget,tk.Button):options.update(activebackground=field,activeforeground='white')
                    widget.configure(**options)
                for child in widget.winfo_children():paint(child)
            paint(panel)
            tree={'original':self.original_tree,'system':self.system_tree,'personal':self.personal_tree}[mode]
            name=f'DublaskizonTTS.{mode}.Treeview'
            style.configure(name,background=field,fieldbackground=field,foreground='white')
            style.map(name,background=[('selected',color)],foreground=[('selected','white')])
            tree.configure(style=name)
            self.mode_buttons[mode].configure(bg=color,fg='white',selectcolor=field,activebackground=field,activeforeground='white')

    def _blink_native_preparation(self):
        try:
            if not self.parent.winfo_exists():return
            import native_emotions
            pending=self.parent.winfo_ismapped() and not self.running and not native_emotions.prepared()
            self._native_blink=not self._native_blink if pending else False
            self.prepare_native_button.configure(bg='#FBBF24' if self._native_blink else '#14B8A6',fg='#111827',activebackground='#2DD4BF')
            self.parent.after(650,self._blink_native_preparation)
        except tk.TclError:pass

    def _set_paths(self, tree, paths):
        tree.delete(*tree.get_children())
        for index,path in enumerate(paths):
            tree.insert("","end",iid=str(index),text=path.name,values=(str(path),))

    def load_project_originals(self):
        folder=self.project_root/"WAV ORIGINAIS"
        self.originals=sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.casefold() in AUDIO_EXTENSIONS),key=lambda p:str(p).casefold()) if folder.is_dir() else []
        self._set_paths(self.original_tree,self.originals)
        self.status.set(f"{len(self.originals)} áudio(s) carregado(s) de WAV ORIGINAIS.")

    def add_original(self):
        values=filedialog.askopenfilenames(parent=self.parent,title="Adicionar áudio original",filetypes=(("Áudios","*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.opus"),("Todos","*.*")))
        for value in values:
            path=Path(value).resolve()
            if path not in self.originals:self.originals.append(path)
        self._set_paths(self.original_tree,self.originals)

    def add_personal_voice(self):
        values=filedialog.askopenfilenames(parent=self.parent,title="Adicionar voz modelo",filetypes=(("Áudios","*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.opus"),("Todos","*.*")))
        library=self.project_root/"MODELOS DE VOZ PERSONALIZADOS";library.mkdir(parents=True,exist_ok=True)
        for value in values:
            source=Path(value).resolve();destination=library/source.name
            if source != destination:
                counter=2
                while destination.exists() and destination.resolve()!=source:destination=library/f"{source.stem}_{counter}{source.suffix}";counter+=1
                if not destination.exists():shutil.copy2(source,destination)
            if destination not in self.personal:self.personal.append(destination)
        self._set_paths(self.personal_tree,self.personal)

    def open_requirements(self):
        app=getattr(self.parent.winfo_toplevel(),"dublaskizon_app",None)
        if app:
            import dependency_setup
            dependency_setup.show_assistant(app)
        else:messagebox.showinfo("Requisitos","Abra REQUISITOS no cabeçalho do Dublaskizon.",parent=self.parent)

    def insert_expression(self,key):
        tag=f"[{key}]"
        self.text.insert("insert",tag+" ");self.text.focus_set()

    def expression_action(self,key):
        if not self.preview_expressions.get():
            self.insert_expression(key);return
        try:
            import native_emotions
            mode=self.reference_mode.get();selected,instruction=self._selection()
            samples=self._emotional_references(mode,selected,instruction)
            reference=samples.get(key)
            if reference:
                reference=Path(reference)
                self.status.set('Prévia da referência própria: '+key)
                self._open_audio(reference)
                return
            samples=native_emotions.native_references(self.native_voice.get())
            reference=samples.get(key)
            if not reference:
                self.status.set('Sem prévia gravada para esta expressão. Nenhum texto foi inserido.')
                return
            # Audition the bundled interpretation, not an expensive synthesis.
            # This is the donor voice, not a promise of the selected voice's result.
            self.status.set('Prévia da referência '+key+' — voz do banco nativo; o resultado com sua voz pode variar.')
            if reference.name.startswith('thorsten_'):
                self.status.set('Prévia de '+key+' — gravação em alemão; ouça a interpretação. A síntese permanece em português.')
            from audio_player import play_wav_with_winsound
            if not play_wav_with_winsound(reference):self._open_audio(reference)
        except (OSError,ValueError,RuntimeError) as exc:
            self.status.set('Não foi possível ouvir a expressão: '+str(exc))

    def add_system_voice(self):
        values=filedialog.askopenfilenames(parent=self.parent,title="Adicionar referência do sistema",filetypes=(("Áudios","*.wav *.mp3 *.flac *.ogg *.m4a *.opus"),))
        folder=self.project_root/"TEXTO PARA FALA"/"VOZES DO SISTEMA";folder.mkdir(parents=True,exist_ok=True)
        for value in values:
            source=Path(value).resolve();destination=folder/source.name
            if destination.resolve()!=source:
                counter=2
                while destination.exists():destination=folder/f"{source.stem}_{counter}{source.suffix}";counter+=1
                shutil.copy2(source,destination)
            if destination not in self.system_audio:self.system_audio.append(destination)
        self._refresh_system_voices()

    def _refresh_custom_expression_buttons(self):
        for button in self.custom_expression_buttons:button.destroy()
        self.custom_expression_buttons=[]
        reference,instruction=self._selection()
        try:
            refs=self._emotional_references(self.reference_mode.get(),reference,instruction)
        except (OSError,ValueError,TypeError):
            refs={}
        labels={key:label for label,key,_ in EXPRESSIONS}
        labels.update({key:label for label,key in EXTRA_EXPRESSIONS})
        for index,key in enumerate(refs):
            if not Path(refs[key]).is_file():continue
            button=self._button(self.custom_expression_panel,labels.get(key,key.upper()),lambda k=key:self.expression_action(k),'accent',font=('Segoe UI Emoji',8,'bold'),padx=3,pady=1)
            button.grid(row=index//5,column=index%5+1,sticky='w',padx=2,pady=1)
            self.custom_expression_buttons.append(button)

    def _available_expressions(self):
        from qwen_backend import emotional_references,NEW_EXPRESSIONS
        refs=emotional_references(self.native_voice.get())
        return AVAILABLE_EXPRESSIONS+tuple((label,key) for label,key in NEW_EXPRESSIONS if key in refs)

    def _refresh_expression_buttons(self):
        for index in range(6):
            self.expression_panel.columnconfigure(index,weight=0)
        for button in self.expression_buttons:button.destroy()
        self.expression_buttons=[]
        expressions=self._available_expressions()
        for index,(label,key) in enumerate(expressions):
            button=self._button(self.expression_panel,label,lambda k=key:self.expression_action(k),'secondary',font=('Segoe UI Emoji',8,'bold'),padx=1,pady=1,height=1)
            button.grid(row=index//6,column=index%6,sticky='nsew',padx=1,pady=1)
            self.expression_panel.columnconfigure(index%6,weight=1,uniform='expression')
            self.expression_buttons.append(button)
        self.preview_button.grid_configure(row=(len(expressions)+5)//6,columnspan=6)

    def prepare_qwen_emotions(self):
        if self.running:return
        if not messagebox.askyesno('Novas reações Qwen','Instalar o ambiente Qwen e baixar os modelos oficiais? São aproximadamente 10,7 GB de modelos, mais as dependências. As amostras serão geradas em português; ouça para avaliar a interpretação.',parent=self.parent):return
        self.running=True;self.cancel_event.clear()
        self.generate_button.configure(state='disabled');self.engine_choice.configure(state='disabled');self.cancel_button.configure(state='normal');self.progress.start(12)
        self.status.set('Preparando novas referências emocionais Qwen…')
        def worker():
            try:
                from dependency_setup import SetupJob,detect_processing
                import qwen_backend
                job=SetupJob(lambda message:self.events.put(('log',message)),self.cancel_event,transfer=lambda data:self.events.put(('download',data)))
                self.events.put(('log','Relatório Qwen: '+str(job.log)))
                variant=detect_processing()['variant']
                qwen_backend.install(job,variant);qwen_backend.download(job);qwen_backend.prepare_emotions(job)
                self.events.put(('qwen_ready',None))
            except Exception as error:self.events.put(('error',str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def prepare_native_emotions(self):
        if self.running:return
        self.running=True;self.cancel_event.clear()
        self.generate_button.configure(state='disabled');self.engine_choice.configure(state='disabled');self.cancel_button.configure(state='normal');self.progress.start(12)
        self.status.set('Preparando as reações nativas…')
        def worker():
            try:
                self._prepare_native_runtime()
                self.events.put(('native_ready',None))
            except Exception as error:self.events.put(('error',str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def _prepare_native_runtime(self):
        from dependency_setup import SetupJob
        import native_emotions
        job=SetupJob(lambda message:self.events.put(('log',message)),self.cancel_event,
                     transfer=lambda data:self.events.put(('download',data)))
        self.events.put(('log','Relatório das reações nativas: '+str(job.log)))
        native_emotions.install(job)
        native_emotions.download(job)

    def _profile_file(self,mode,reference,system_instruction):
        identity=json.dumps([mode,str(reference.resolve()) if reference else system_instruction],ensure_ascii=False)
        key=hashlib.sha256(identity.encode('utf-8')).hexdigest()
        return self.project_root/"TEXTO PARA FALA"/"PERFIS EMOCIONAIS"/(key+'.json')

    def _emotional_references(self,mode,reference,system_instruction):
        path=self._profile_file(mode,reference,system_instruction)
        data=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        refs=data.get('references',{})
        if not isinstance(refs,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in refs.items()):
            raise ValueError("Perfil emocional inválido. Configure novamente as reações da voz.")
        shared=self.project_root/'TEXTO PARA FALA'/'EXPRESSOES COMPARTILHADAS'/'references.json'
        if refs and not shared.is_file():
            for key,value in refs.items():
                if key!='neutro' and Path(value).is_file():self._share_emotion(key,value)
        if shared.is_file():
            for key,item in json.loads(shared.read_text(encoding='utf-8')).get('references',{}).items():
                if mode in item.get('modes',['original','system','personal']):
                    refs[key]=item['path']
        return refs

    def _share_emotion(self,key,value,modes=('original','system','personal')):
        source=Path(value).resolve()
        if not source.is_file() or source.suffix.casefold() not in AUDIO_EXTENSIONS:
            raise ValueError('Referência inexistente ou formato de áudio não aceito: '+str(source))
        folder=self.project_root/'TEXTO PARA FALA'/'EXPRESSOES COMPARTILHADAS'
        folder.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()[:20]
        stored=folder/(key+'_'+digest+source.suffix.lower())
        if source!=stored and not stored.is_file():shutil.copy2(source,stored)
        index=folder/'references.json'
        data=json.loads(index.read_text(encoding='utf-8')) if index.is_file() else {'references':{}}
        previous=data['references'].get(key,{})
        data['references'][key]={'path':str(stored),'modes':sorted(set(previous.get('modes',[]))|set(modes))}
        pending=index.with_suffix('.pending.json')
        pending.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(index)
        return stored

    def share_expression(self,key,value,mode):
        try:
            self._share_emotion(key,value,(mode,))
            self._refresh_custom_expression_buttons()
            self.status.set('Expressão '+key+' disponível para qualquer voz da categoria escolhida; a voz selecionada foi mantida.')
        except (OSError,ValueError) as error:messagebox.showerror('Compartilhar expressão',str(error),parent=self.parent)

    def configure_emotional_voice(self):
        if self.running:return
        mode=self.reference_mode.get();reference,instruction=self._selection()
        if not reference and not instruction:
            messagebox.showwarning("Reações da voz","Selecione primeiro uma voz em uma das três listas.",parent=self.parent);return
        try:references=self._emotional_references(mode,reference,instruction)
        except Exception as error:
            messagebox.showerror("Reações da voz",str(error),parent=self.parent);return
        dialog=tk.Toplevel(self.parent);dialog.title("Reações da voz — "+(reference.name if reference else "Voz do sistema"));dialog.configure(bg=self.theme['panel'])
        dialog.geometry(f"{min(1150,dialog.winfo_screenwidth()-60)}x{min(960,dialog.winfo_screenheight()-100)}+30+40");dialog.transient(self.parent.winfo_toplevel())
        footer=tk.Frame(dialog,bg=self.theme['panel']);footer.pack(side='bottom',fill='x')
        tk.Label(dialog,text="Importe ou grave expressões. Salvar disponibiliza essas expressões para qualquer voz das três categorias.\nUSAR EM compartilha na categoria escolhida sem trocar a voz principal. O timbre final é convertido para a voz selecionada.",bg=self.theme['panel'],fg=self.theme['text'],justify='left').pack(fill='x',padx=12,pady=10)
        tk.Label(dialog,text="Neutro: "+(str(reference) if reference else "gerado pela voz do sistema"),bg=self.theme['panel'],fg=self.theme['text'],wraplength=720).pack(fill='x',padx=12)
        body=tk.Frame(dialog,bg=self.theme['panel']);body.pack(fill='both',expand=True,padx=12,pady=8)
        canvas=tk.Canvas(body,bg=self.theme['panel'],highlightthickness=0)
        scroll=ttk.Scrollbar(body,command=canvas.yview);canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        rows=tk.Frame(canvas,bg=self.theme['panel']);window=canvas.create_window((0,0),window=rows,anchor='nw')
        rows.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        canvas.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
        entries={}
        for index,(label,key) in enumerate([(label,key) for label,key,_ in EXPRESSIONS]+list(EXTRA_EXPRESSIONS)):
            cell=tk.Frame(rows,bg=self.theme['panel'])
            cell.grid(row=index,column=0,sticky='ew',padx=5,pady=2)
            cell.columnconfigure(1,weight=1)
            row_index=0
            host=cell
            tk.Label(host,text=label,bg=self.theme['panel'],fg=self.theme['text'],anchor='w',font=('Segoe UI Emoji',8,'bold')).grid(row=row_index,column=0,sticky='w',pady=2)
            variable=tk.StringVar(value=references.get(key,''));entries[key]=variable
            entry=tk.Entry(host,textvariable=variable,width=12,bg=self.theme['input'],fg=self.theme['input_text'],insertbackground=self.theme['input_text'])
            entry.grid(row=row_index,column=1,sticky='ew',padx=3)
            def choose(v=variable):
                chosen=filedialog.askopenfilename(parent=dialog,title="Importar gravação expressiva (inclusive exportada)",filetypes=(("Áudios",' '.join('*'+suffix for suffix in sorted(AUDIO_EXTENSIONS))),("Todos os arquivos","*.*")))
                if chosen:v.set(chosen)
            self._button(host,'ESCOLHER',choose,'primary',padx=2,pady=1,font=('Segoe UI',8)).grid(row=0,column=2)
            self._button(host,'LIMPAR',lambda v=variable:v.set(''),'secondary',padx=2,pady=1,font=('Segoe UI',8)).grid(row=0,column=3,padx=2)
            self._button(host,'🎙',lambda v=variable,k=key:self.record_expression(dialog,k,v),'success',padx=3,pady=1).grid(row=0,column=4,padx=2)
            self._button(host,'EXPORTAR',lambda v=variable:self.export_reference_audio(v.get()),'secondary',padx=3,pady=1,font=('Segoe UI',8)).grid(row=0,column=5,padx=2)
            use=tk.Menubutton(host,text='USAR EM ▾',relief='raised',font=('Segoe UI',8))
            menu=tk.Menu(use,tearoff=False)
            for label,mode in [('Originais','original'),('Vozes do sistema','system'),('Escolhidas por mim','personal')]:
                menu.add_command(label=label,command=lambda m=mode,v=variable,k=key:self.share_expression(k,v.get(),m))
            use.configure(menu=menu);use.grid(row=0,column=6,padx=2)
        rows.columnconfigure(0,weight=1)
        def save():
            refs={key:var.get().strip() for key,var in entries.items() if var.get().strip()}
            invalid=[path for path in refs.values() if not Path(path).is_file() or Path(path).suffix.casefold() not in AUDIO_EXTENSIONS]
            if invalid:
                messagebox.showerror('Reações da voz','Áudio não encontrado ou formato inválido: '+invalid[0],parent=dialog);return
            try:
                refs={key:str(self._share_emotion(key,value)) for key,value in refs.items()}
                path=self._profile_file(mode,reference,instruction);path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps({'references':refs},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:
                messagebox.showerror('Reações da voz',str(error),parent=dialog);return
            self.status.set('Reações salvas para a voz selecionada.');dialog.destroy()
            self._refresh_custom_expression_buttons()
        self._button(footer,'SALVAR REAÇÕES',save,'success',pady=7).pack(fill='x',padx=12,pady=10)

    def export_reference_audio(self,value):
        path=Path(value) if value else None
        if not path or not path.is_file():
            messagebox.showwarning('Exportar referência','Escolha ou confirme uma gravação primeiro.',parent=self.parent);return
        selected=filedialog.asksaveasfilename(parent=self.parent,title='Exportar referência',initialfile=path.name,defaultextension=path.suffix,filetypes=(('Áudio original','*'+path.suffix),))
        if selected:
            try:
                if Path(selected).resolve()!=path.resolve():shutil.copy2(path,selected)
                self.status.set('Referência exportada: '+selected)
            except OSError as error:messagebox.showerror('Exportar referência',str(error),parent=self.parent)

    def use_reference_audio(self,value,mode):
        path=Path(value).resolve() if value else None
        if not path or not path.is_file():
            messagebox.showwarning('Usar referência','Escolha ou confirme uma gravação primeiro.',parent=self.parent);return
        paths={'original':self.originals,'system':self.system_audio,'personal':self.personal}[mode]
        if path not in paths:paths.append(path)
        if mode=='system':
            self._refresh_system_voices();tree=self.system_tree;iid='audio:'+str(paths.index(path))
        else:
            tree=self.original_tree if mode=='original' else self.personal_tree
            self._set_paths(tree,paths);iid=str(paths.index(path))
        tree.selection_set(iid);tree.focus(iid);tree.see(iid)
        self.reference_mode.set(mode)
        self.status.set('Referência adicionada e selecionada: '+path.name)

    def record_expression(self,parent,key,variable):
        from audio_player import AudioPlayerManager
        dialog=tk.Toplevel(parent);dialog.title('Gravar expressão — '+key)
        dialog.geometry('760x360');dialog.transient(parent);dialog.configure(bg=self.theme['panel'])
        status=tk.StringVar(value='Preparando captura e detectando microfones de entrada…')
        ttk.Label(dialog,textvariable=status,wraplength=720).pack(fill='x',padx=12,pady=8)
        selected=tk.StringVar();choice=ttk.Combobox(dialog,textvariable=selected,state='readonly');choice.pack(fill='x',padx=12)
        duration=tk.StringVar(value='6')
        ttk.Label(dialog,text='Duração: 3 a 10 segundos. Fale uma frase clara com a expressão; evite silêncio e ruído.').pack(anchor='w',padx=12,pady=6)
        ttk.Spinbox(dialog,from_=3,to=10,textvariable=duration,width=8).pack(anchor='w',padx=12)
        canvas=tk.Canvas(dialog,height=100,bg=self.theme['input'],highlightthickness=0);canvas.pack(fill='x',padx=12,pady=8)
        controls=ttk.Frame(dialog);controls.pack(fill='x',padx=12,pady=8)
        folder=tempfile.TemporaryDirectory(prefix='dublaskizon-microfone-');pending=Path(folder.name)/'gravacao.wav'
        state={'devices':{},'busy':False,'ready':False,'closed':False,'process':None}
        events=queue.Queue()
        def run(args):
            process=subprocess.Popen(microphone_command(*args),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',**batch_tab.hidden_process_kwargs())
            state['process']=process
            if state['closed']:process.terminate()
            try:
                stdout,stderr=process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill();process.communicate()
                raise RuntimeError('Microfone não respondeu em 30 segundos; tente outro dispositivo.')
            if process.returncode:raise RuntimeError(stderr[-1200:] or 'Falha na captura. Prepare TEXTO PARA FALA no botão 1 dos Requisitos.')
            return stdout
        def discover():
            try:
                ensure_microphone_runtime()
                output=run([])
                line=next(line for line in output.splitlines() if line.startswith('DUBLASKIZON_MIC '))
                events.put(('devices',json.loads(line.split(' ',1)[1])))
            except Exception as error:events.put(('error',str(error)))
        def record():
            if state['busy']:return
            try:
                seconds=float(duration.get());device=state['devices'][selected.get()]
                if not 3<=seconds<=10:raise ValueError()
            except (ValueError,KeyError):status.set('Selecione um microfone e uma duração entre 3 e 10 segundos.');return
            state['busy']=True;state['ready']=False;update_buttons();canvas.delete('all')
            status.set(f'Gravando por {seconds:g} segundos…')
            def work():
                try:run([device['id'],seconds,pending]);events.put(('recorded',None))
                except Exception as error:events.put(('error',str(error)))
                finally:
                    if state['closed']:folder.cleanup()
            threading.Thread(target=work,daemon=True).start()
        def eliminate():
            pending.unlink(missing_ok=True);state['ready']=False;canvas.delete('all');status.set('Gravação eliminada.');update_buttons()
        def close():
            state['closed']=True
            process=state['process']
            if process and process.poll() is None:process.terminate()
            if not state['busy']:folder.cleanup()
            dialog.destroy()
        def confirm():
            if not state['ready']:return
            destination=self.project_root/'TEXTO PARA FALA'/'GRAVACOES DE EXPRESSOES'
            try:
                destination.mkdir(parents=True,exist_ok=True)
                path=destination/f'{key}_{time.time_ns()}.wav';shutil.copy2(pending,path)
            except OSError as error:
                status.set('Não foi possível salvar a gravação: '+str(error));return
            variable.set(str(path));close()
        buttons={}
        def refresh_devices():
            if state['busy']:return
            state['busy']=True;update_buttons();status.set('Atualizando microfones conectados…')
            threading.Thread(target=discover,daemon=True).start()
        for label,command in [('ATUALIZAR MIC',refresh_devices),('🎙 GRAVAR',record),('REFAZER',record),('OUVIR',lambda:self._open_audio(pending)),('CONFIRMAR',confirm),('ELIMINAR',eliminate),('FECHAR',close)]:
            buttons[label]=ttk.Button(controls,text=label,command=command);buttons[label].pack(side='left',padx=3)
        def update_buttons():
            for label,button in buttons.items():
                enabled=label=='FECHAR' or (not state['busy'] and (True if label=='ATUALIZAR MIC' else bool(state['devices']) if label in ('🎙 GRAVAR','REFAZER') else state['ready']))
                button.configure(state='normal' if enabled else 'disabled')
        def poll():
            if state['closed']:return
            while not events.empty():
                kind,data=events.get();state['busy']=False
                if kind=='devices':
                    state['devices']={f"{d['id']} — {d['name']} [{d.get('api','áudio')}]"+(' (padrão)' if d['default'] else ''):d for d in data}
                    choice.configure(values=list(state['devices']))
                    if data:selected.set(next((label for label,d in state['devices'].items() if d['default']),next(iter(state['devices']))))
                    status.set('Selecione o microfone interno ou USB pelo nome.' if data else 'Nenhum microfone de entrada encontrado.')
                elif kind=='recorded':
                    wave_data=AudioPlayerManager._read_waveform(pending)
                    if not wave_data:status.set('Gravação inválida; refaça.');continue
                    state['ready']=True;status.set('Gravação pronta. Ouça e confirme, elimine ou refaça.')
                    canvas.update_idletasks();width=max(1,canvas.winfo_width());peaks=wave_data['samples']
                    for index,peak in enumerate(peaks):
                        x=index*width/max(1,len(peaks));canvas.create_line(x,50-45*peak,x,50+45*peak,fill='#4ADE80')
                else:status.set('Falha: '+str(data))
                update_buttons()
            dialog.after(100,poll)
        dialog.protocol('WM_DELETE_WINDOW',close);update_buttons();poll()
        refresh_devices()

    def _start_emotional_generation(self):
        source=self.text.get('1.0','end-1c')
        # Marcadores antigos de voz não são comandos emocionais.
        source=re.sub(r'\[\[VOZ:[^\]]+\]\]','',source,flags=re.I)
        if not parse_emotion_tags(source):
            messagebox.showwarning('Texto para fala','Digite o texto que será dublado.',parent=self.parent);return
        mode=self.reference_mode.get();reference,instruction=self._selection()
        if not reference and not instruction:
            messagebox.showwarning('Texto para fala','Selecione uma voz em uma das três listas.',parent=self.parent);return
        from qwen_backend import MODEL as QWEN_MODEL
        model=QWEN_MODEL if self.engine.get().startswith("Qwen") else batch_tab.MODEL
        if not self.engine.get().startswith('Qwen') and model==QWEN_MODEL:
            model='edwixx/omnivoice-brpt-v15'
        from f5_backend import MODEL as russian_model
        if model==russian_model:
            messagebox.showwarning('Texto para fala','O F5 Russian não suporta português. Selecione OmniVoice BR-PT ou F5 compatível com português em Ferramenta / modelo.',parent=self.parent);return
        try:command=batch_tab.find_voice_command(model)
        except RuntimeError as error:
            messagebox.showerror('Motor indisponível',str(error),parent=self.parent);return
        if not command:
            messagebox.showerror('Texto para fala','Prepare o motor selecionado em REQUISITOS.',parent=self.parent);return
        try:references=self._emotional_references(mode,reference,instruction)
        except Exception as error:
            messagebox.showerror('Reações da voz',str(error),parent=self.parent);return
        from directml_backend import MODEL as f5_portuguese
        native_keys=()
        if self.native_automatic.get():
            import native_emotions
            try:native_keys=native_emotions.native_references(self.native_voice.get()).keys()
            except (OSError,ValueError,RuntimeError) as error:
                messagebox.showerror('Reações nativas',str(error),parent=self.parent);return
        missing=unavailable_emotions(source,references,native_keys,allow_nonverbal=model not in (f5_portuguese,QWEN_MODEL))
        if missing:
            messagebox.showwarning('Expressões indisponíveis','Estas tags não têm referência ou suporte para a configuração atual: '+', '.join(missing)+'.\n\nRemova-as, ative REAÇÕES NATIVAS AUTOMÁTICAS para as reações do banco ou cadastre referências próprias. Nenhum áudio foi gerado.',parent=self.parent)
            return
        output=output_location(self.project_root,mode,reference,self.system_tree.selection()[0] if self.system_tree.selection() else 'fala')
        self.pending_metadata={'engine':'emotional_references','model':model,'mode':mode,'reference':str(reference) if reference else None,'text':source,'needs_review':False,'reference_text':self.reference_text.get().strip() if reference else ''}
        self.generation_warning=False;self.cancel_event.clear()
        self._append_log('Iniciando geração por referências emocionais — '+model)
        self.running=True;self.generate_button.configure(state='disabled');self.cancel_button.configure(state='normal');self.engine_choice.configure(state='disabled');self.progress.start(12)
        self.status.set('Preparando a voz selecionada…')
        threading.Thread(target=self._emotional_worker,args=(source,reference,instruction,references,command,model,output,self.native_automatic.get(),self.native_voice.get()),daemon=True).start()

    def _run_emotional_command(self,args):
        if self.cancel_event.is_set():raise RuntimeError('Geração cancelada.')
        from dependency_setup import official_environment
        env=official_environment();ffdir=batch_tab.find_ffmpeg_directory()
        if ffdir:env['PATH']=str(ffdir)+os.pathsep+env.get('PATH','')
        pool=getattr(self,'_warm_inference',None)
        warm=pool is not None and WarmInference.eligible(args)
        if pool is not None and not warm:
            # Voice conversion needs the GPU memory occupied by synthesis.
            pool.close()
        runner=pool.start if warm else subprocess.Popen
        process=runner(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,**batch_tab.hidden_process_kwargs())
        self.process=process
        captured=[]
        def read():
            for line in process.stdout:
                if line.strip():self.events.put(('log',line.strip()))
                captured.append(line)
                if len(captured)>100:del captured[:50]
        reader=threading.Thread(target=read,daemon=True);reader.start()
        try:
            # Polling also handles cancel clicked just before Popen was assigned.
            deadline=time.monotonic()+1800
            while process.poll() is None:
                if self.cancel_event.is_set():process.terminate();break
                if time.monotonic()>deadline:raise RuntimeError('Tempo limite de geração excedido.')
                time.sleep(.1)
            if warm:process.wait()
            else:process.wait(timeout=5)
            reader.join(timeout=3)
            if self.cancel_event.is_set():raise RuntimeError('Geração cancelada.')
            if process.returncode:raise RuntimeError(generation_error(''.join(captured),process.returncode))
        finally:
            if process.poll() is None:process.kill();process.wait()
            reader.join(timeout=3)
            if process.stdout:process.stdout.close()
            self.process=None

    @warm_batch
    def _emotional_worker(self,source,reference,instruction,references,command,model,output,auto_native=False,native_voice='masculina'):
        try:
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='dublaskizon_voice_',dir=output.parent) as directory:
                folder=Path(directory);ffdir=batch_tab.find_ffmpeg_directory()
                normalizer=FFmpegNormalizer(str(Path(ffdir)/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg'))) if ffdir else None
                if reference is None:
                    # A fixed neutral reference avoids changing the system voice between segments.
                    reference=folder/'system_neutral.wav'
                    self.events.put(('log','Criando referência fixa da voz do sistema…'))
                    self._run_emotional_command([*command,'--model',model,'--text','Olá, esta é a minha voz. Vamos conversar com calma.','--language','Portuguese','--instruct',instruction,'--output',str(reference)])
                    self.pending_metadata['reference']=None
                prepared={'neutro':reference}
                wanted={segment['emocao'] for segment in parse_emotion_tags(source)}
                own_refs={emotion:Path(path) for emotion,path in references.items() if emotion in wanted and emotion!='neutro' and Path(path).is_file()}
                if own_refs:
                    import native_emotions
                    if not native_emotions.prepared():
                        self.events.put(('log','Preparando conversão de timbre das referências próprias para a voz selecionada…'))
                        self._prepare_native_runtime()
                        self.events.put(('synthesis_start',None))
                    prepared.update(own_refs)
                    self.pending_metadata['own_expression_method']='synthesize_expression_then_convert_voice'
                if auto_native:
                    import native_emotions
                    available=native_emotions.native_references(native_voice)
                    # As vozes brasileiras já fornecem suas próprias interpretações.
                    for bank in ('masculina','feminina'):
                        native_refs=native_emotions.native_references(bank)
                        if reference.resolve()==native_refs['neutro'].resolve():
                            prepared.update({emotion:path for emotion,path in native_refs.items()
                                             if emotion in wanted and emotion not in prepared and not path.name.startswith('thorsten_')})
                            native_voice=bank;available=native_refs;break
                    required=[emotion for emotion in wanted if emotion not in prepared and emotion in available and emotion not in NATIVE_NONVERBAL_SOUNDS]
                    if required and not native_emotions.prepared():
                        self.events.put(('log','Preparando automaticamente o conversor e os modelos das reações nativas…'))
                        self._prepare_native_runtime()
                        self.events.put(('synthesis_start',None))
                    for emotion in sorted(required):
                        self.events.put(('log','Adaptando referência nativa de '+emotion+' à voz selecionada…'))
                        adapted=native_emotions.converted_reference(emotion,reference,self._run_emotional_command,voice=native_voice)
                        if adapted:prepared[emotion]=adapted
                    self.pending_metadata['native_emotions']=True
                    self.pending_metadata['native_bank']=native_voice
                if normalizer:
                    for index,(emotion,path) in enumerate(list(prepared.items())):
                        destination=folder/f'reference_{index}.wav';normalizer(path,destination);prepared[emotion]=destination
                app=self
                current_emotion=['neutro']
                class Engine:
                    def synthesize(self,text,ref_audio_path,output_path):
                        emotion=current_emotion[0]
                        final_output=output_path
                        if emotion in own_refs:
                            output_path=Path(output_path).with_name(Path(output_path).stem+'.expressive.wav')
                        # Sons não verbais documentados pelo OmniVoice, com a voz escolhida.
                        from directml_backend import MODEL as f5_portuguese
                        from qwen_backend import MODEL as QWEN_MODEL
                        if model not in (f5_portuguese,QWEN_MODEL) and current_emotion[0] in NATIVE_NONVERBAL_SOUNDS:
                            text=NONVERBAL_TAGS[current_emotion[0]]+' '+text
                        args=[*command,'--model',model,'--text',text,'--language','Portuguese','--ref_audio',str(ref_audio_path),'--output',str(output_path)]
                        if model==QWEN_MODEL:
                            if current_emotion[0]=='neutro' and app.pending_metadata.get('reference_text'):
                                args.extend(['--ref_text',app.pending_metadata['reference_text']])
                            elif current_emotion[0] not in references:
                                from qwen_backend import emotional_references
                                if current_emotion[0] in emotional_references(native_voice):
                                    args.extend(['--ref_text','André, venha aqui. Eu preciso conversar com você agora.'])
                        from speech_completeness import verified_command
                        app._run_emotional_command(verified_command(args, model, getattr(app, 'project_root', output.parent)))
                        if emotion in own_refs:
                            import native_emotions
                            app.events.put(('log','Convertendo timbre do trecho expressivo '+emotion+' para a voz selecionada: '+reference.name))
                            converted=native_emotions.converted_reference(emotion,reference,app._run_emotional_command,donor=Path(output_path))
                            if not converted:raise RuntimeError('Conversão da voz do trecho expressivo falhou; nenhum doador será publicado como resultado.')
                            shutil.copy2(converted,final_output)
                            Path(output_path).unlink(missing_ok=True)
                def progress(event):
                    if self.cancel_event.is_set():raise RuntimeError('Geração cancelada.')
                    choice=event.reference
                    if event.stage=='generating':
                        current_emotion[0]=choice.requested_emotion
                        self.events.put(('log',f'Trecho {event.index}/{event.total} — {choice.requested_emotion}; referência: {choice.used_emotion}'))
                        if choice.requested_emotion in NATIVE_NONVERBAL_SOUNDS:
                            self.events.put(('log','Som não verbal solicitado: '+choice.requested_emotion+'; depende do suporte do motor.'))
                        elif choice.requested_emotion!=choice.used_emotion:
                            self.events.put(('log',f'AVISO: sem referência para {choice.requested_emotion}; usando a voz neutra selecionada.'))
                result=generate_expressive_speech(source,VoiceProfile(prepared),Engine(),output,normalizer=normalizer,on_progress=progress)
                self.pending_metadata['segments']=[{'emotion':s['emocao'],'text':s['texto_limpo'],'used_emotion':c.used_emotion} for s,c in zip(result.segments,result.references)]
                self.pending_metadata['emotional_references']=references
            output.with_suffix('.txt').write_text(source,encoding='utf-8')
            output.with_suffix('.json').write_text(json.dumps(self.pending_metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            self.events.put(('done',output))
        except Exception as error:self.events.put(('error',str(error)))

    def _selected_path(self,tree,paths):
        selected=tree.selection()
        if not selected:return None
        try:return paths[int(selected[0])]
        except (ValueError,IndexError):return None

    def _selection(self):
        mode=self.reference_mode.get()
        if mode=="original":return self._selected_path(self.original_tree,self.originals),""
        if mode=="personal":return self._selected_path(self.personal_tree,self.personal),""
        selected=self.system_tree.selection()
        if not selected:return None,""
        if selected[0].startswith("audio:"):
            try:return self.system_audio[int(selected[0].split(':')[1])],""
            except (ValueError,IndexError):return None,""
        if selected[0].startswith('nativa:'):
            import native_emotions
            return native_emotions.native_references(selected[0].split(':')[1])['neutro'],''
        if selected[0].startswith("QWEN_SPEAKER:"):return None,selected[0]
        return None,dict(SYSTEM_VOICES).get(selected[0],"")

    def start_generation(self):
        if self.running:return
        self._start_emotional_generation()

    def _worker(self,args,output):
        temporary=output.with_name('.'+output.stem+'.pending.wav')
        try:
            args=list(args)
            if '--output' in args:args[args.index('--output')+1]=str(temporary)
            from dependency_setup import official_environment
            env=official_environment();ffdir=batch_tab.find_ffmpeg_directory()
            if ffdir:env["PATH"]=str(ffdir)+os.pathsep+env.get("PATH","")
            self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",env=env,**batch_tab.hidden_process_kwargs())
            captured_lines=[];review_warnings=[]
            process=self.process
            def read_log():
                for line in process.stdout:
                    if "AVISO: verificação inconclusiva" in line and line.strip() not in review_warnings:review_warnings.append(line.strip())
                    captured_lines.append(line)
                    if len(captured_lines)>100:del captured_lines[:50]
                    if line.strip():self.events.put(("log",line.strip()))
            reader=threading.Thread(target=read_log,daemon=True);reader.start()
            try:process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                process.kill();process.wait();reader.join(timeout=3)
                raise RuntimeError("Tempo limite de geração excedido. "+''.join(captured_lines)[-1200:])
            reader.join(timeout=3);captured=''.join(captured_lines)
            code=self.process.returncode
            if code or not temporary.is_file():raise RuntimeError(generation_error(captured,code))
            os.replace(temporary,output)
            self.pending_metadata["needs_review"]=bool(review_warnings)
            self.pending_metadata["verification_warnings"]=review_warnings
            output.with_suffix(".txt").write_text(self.pending_metadata["text"],encoding="utf-8")
            output.with_suffix(".json").write_text(json.dumps(self.pending_metadata,ensure_ascii=False,indent=2),encoding="utf-8")
            self.events.put(("done",output))
        except Exception as exc:self.events.put(("error",str(exc)))
        finally:
            self.process=None
            try:temporary.unlink(missing_ok=True)
            except OSError:pass

    def _poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=="log":
                    if "AVISO: verificação inconclusiva" in value:self.generation_warning=True
                    self._append_log(value);self.status.set(value[-180:]);continue
                if kind=='download':
                    total=value.get('total',0);current=value.get('current',0)
                    if total:
                        self.progress.stop();self.progress.configure(mode='determinate',maximum=100,value=min(100,current*100/total))
                        self.status.set(f"{value.get('name','Download')}: {current/1_000_000:.1f} / {total/1_000_000:.1f} MB")
                    continue
                if kind=='synthesis_start':
                    self.progress.stop();self.progress.configure(mode='indeterminate',value=0);self.progress.start(12);continue
                if kind in ('native_ready','qwen_ready'):
                    self.running=False;self.engine_choice.configure(state='readonly');self.generate_button.configure(state='normal');self.cancel_button.configure(state='disabled');self.progress.stop();self.progress.configure(mode='indeterminate',value=0)
                    if kind=='qwen_ready':self._refresh_expression_buttons()
                    self.status.set('Reações nativas preparadas. Selecione a voz e clique em DUBLAR.');self._append_log(self.status.get());continue
                self._append_log(("Fala salva: " if kind=="done" else "ERRO: ")+str(value))
                self.running=False;self.engine_choice.configure(state="readonly");self.progress.stop();self.progress.configure(mode='indeterminate',value=0);self.generate_button.configure(state="normal");self.cancel_button.configure(state="disabled")
                if kind=="done":
                    self.output_path=value;self.status.set(("Fala salva — confira o trecho indicado no aviso: " if getattr(self,"generation_warning",False) else "Fala criada: ")+str(value));self.refresh_results()
                    if value in self.results:self.result_tree.selection_set(str(self.results.index(value)))
                else:self.status.set("Falha ao gerar a fala.");messagebox.showerror("Texto para fala",value,parent=self.parent)
        except queue.Empty:pass
        try:self.parent.after(120,self._poll)
        except tk.TclError:pass

    def cancel(self):
        self.cancel_event.set()
        if self.process and self.process.poll() is None:
            try:self.process.terminate()
            except OSError:pass
        self.status.set("Cancelamento solicitado…")

    def listen_selected(self,mode):
        path=self._selection()[0] if mode=="system" else (self._selected_path(self.original_tree,self.originals) if mode=="original" else self._selected_path(self.personal_tree,self.personal))
        if path:self._open_audio(path)
    def listen_output(self):
        selected=self._selected_path(self.result_tree,self.results)
        if selected is None and self.results:selected=self.results[-1]
        if not selected:return
        pairs={}
        for path in self.results:
            try:metadata=json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            except (OSError,ValueError):metadata={}
            reference=Path(metadata["reference"]) if metadata.get("reference") else None
            pairs[path]=(reference if reference and reference.is_file() else None,path)
        self.audio_player.set_loaded_audio_pairs(pairs)
        self.audio_player.play_one(selected,"OUVIR CENA — "+selected.stem,playlist=self.results,index=self.results.index(selected),scene_keys=[str(p) for p in self.results])

    def _load_result_text(self,key):
        path=Path(key).with_suffix(".txt")
        return {"text":path.read_text(encoding="utf-8") if path.is_file() else "", "path":path}

    def _save_result_text(self,key,text):
        path=Path(key).with_suffix(".txt");path.write_text(text,encoding="utf-8")
        return path

    def refresh_results(self):
        mode=self.reference_mode.get()
        folders=[OUTPUT_FOLDERS[mode]]
        if mode=="original":folders.insert(0,OUTPUT_FOLDERS["project"])
        base=self.project_root/"TEXTO PARA FALA"
        self.results=sorted((p for name in folders for p in (base/name).rglob("*.wav") if p.is_file() and not p.name.startswith('.')),key=lambda p:str(p).casefold())
        self.result_tree.delete(*self.result_tree.get_children())
        for index,path in enumerate(self.results):
            try:review=json.loads(path.with_suffix(".json").read_text(encoding="utf-8")).get("needs_review",False)
            except (OSError,ValueError):review=False
            self.result_tree.insert("","end",iid=str(index),text=("[CONFERIR] " if review else "")+path.name,values=(str(path),))
    def _open_audio(self,path):
        try:os.startfile(str(path))
        except Exception as exc:messagebox.showerror("Ouvir áudio",str(exc),parent=self.parent)
    def open_output_folder(self):
        folder=self.project_root/"TEXTO PARA FALA";folder.mkdir(parents=True,exist_ok=True)
        try:os.startfile(str(folder))
        except Exception as exc:messagebox.showerror("Pasta de saída",str(exc),parent=self.parent)

    def refresh_for_project(self):
        self.project_root=Path(os.environ.get("DUBLASKIZON_PROJECT_ROOT",self.project_root)).resolve()
        library=self.project_root/"MODELOS DE VOZ PERSONALIZADOS"
        self.personal=sorted((p for p in library.rglob("*") if p.is_file() and p.suffix.casefold() in AUDIO_EXTENSIONS),key=lambda p:str(p).casefold()) if library.is_dir() else []
        self._set_paths(self.personal_tree,self.personal);self.load_project_originals()
        system=self.project_root/"TEXTO PARA FALA"/"VOZES DO SISTEMA"
        self.system_audio=sorted(p for p in system.rglob('*') if p.is_file() and p.suffix.casefold() in AUDIO_EXTENSIONS) if system.is_dir() else []
        self._refresh_system_voices()
        self.refresh_results()

    def apply_theme(self,theme=None):
        if theme:self.theme=theme
        self._style_trees()
        self.audio_player.apply_theme(self.theme)
        t=self.theme
        def repaint(widget):
            try:
                if isinstance(widget,tk.Text):widget.configure(bg=t["input"],fg=t["input_text"],insertbackground=t["input_text"],selectbackground=t["select"])
                elif isinstance(widget,tk.Entry):widget.configure(bg=t["input"],fg=t["input_text"],insertbackground=t["input_text"])
                elif isinstance(widget,tk.Canvas):widget.configure(bg=t["root"])
                elif isinstance(widget,tk.LabelFrame):widget.configure(bg=t["panel"],fg=t["text"])
                elif isinstance(widget,tk.Label):widget.configure(bg=t["root"] if widget.master is self.parent or widget.master.cget("bg")==t.get("root") else t["panel"],fg=t["text"])
                elif isinstance(widget,tk.Frame):widget.configure(bg=t["root"] if widget.master is self.parent else t["panel"])
                elif isinstance(widget,tk.Button):apply_button_style(widget,t,getattr(widget,"_dublaskizon_role","secondary"))
            except (tk.TclError,KeyError):pass
            for child in widget.winfo_children():repaint(child)
        repaint(self.parent)
