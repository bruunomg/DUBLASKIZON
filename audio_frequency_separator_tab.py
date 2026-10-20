from __future__ import annotations

import os
import atexit
import importlib
import json
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Button, Entry, Frame, Label, StringVar, Text, Toplevel, filedialog, messagebox, ttk

from ui_theme import apply_button_style, apply_button_style_to_tree

SAMPLE_RATE = 22050
N_MFCC = 20
AUDIO_EXTENSIONS = {'.wav', '.ogg', '.mp3', '.flac', '.m4a', '.aac', '.wma', '.opus'}
_FEATURE_CLIENT = None

FEATURE_WORKER = r'''import json,sys
import numba
def _without_cache(function):
    def wrapper(*args,**kwargs):
        kwargs['cache']=False
        return function(*args,**kwargs)
    return wrapper
numba.jit=_without_cache(numba.jit)
numba.vectorize=_without_cache(numba.vectorize)
numba.guvectorize=_without_cache(numba.guvectorize)
import librosa
import numpy as np
for line in sys.stdin:
    try:
        path=json.loads(line)
        audio,rate=librosa.load(path,sr=22050,mono=True)
        duration=float(librosa.get_duration(y=audio,sr=rate))
        mfcc=librosa.feature.mfcc(y=audio,sr=rate,n_mfcc=20)
        fingerprint=np.mean(mfcc,axis=1).astype(float)
        norm=float(np.linalg.norm(fingerprint))
        if not norm: raise ValueError('audio sem conteudo suficiente')
        print(json.dumps({'ok':True,'feature':(fingerprint/norm).tolist(),'duration':duration}),flush=True)
    except Exception as exc:
        print(json.dumps({'ok':False,'error':str(exc)}),flush=True)
'''


class ManagedFeatureClient:
    def __init__(self):
        from dependency_setup import managed_python
        python = managed_python()
        if not python:
            raise RuntimeError('Analise MFCC nao instalada. Abra REQUISITOS, mantenha Incluir analise MFCC ativado e use 1. INSTALAR / REPARAR.')
        self.lock = threading.Lock()
        worker_env = os.environ.copy()
        worker_env['PYTHONUTF8'] = '1'
        worker_env['PYTHONIOENCODING'] = 'utf-8'
        worker_env.setdefault('NUMBA_DISABLE_JIT', '1')
        worker_env.setdefault('NUMBA_CACHE_DIR', str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Dublaskizon' / 'runtime' / 'numba-cache'))
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        self.process = subprocess.Popen([str(python), '-X', 'utf8', '-u', '-c', FEATURE_WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', env=worker_env,
                                        creationflags=creationflags)

    def get(self, path: Path):
        with self.lock:
            if self.process.poll() is not None:
                raise RuntimeError('O analisador MFCC foi encerrado inesperadamente. Repare-o em REQUISITOS.')
            self.process.stdin.write(json.dumps(str(path), ensure_ascii=False) + '\n'); self.process.stdin.flush()
            response = self.process.stdout.readline()
        if not response: raise RuntimeError('O analisador MFCC nao retornou resultado.')
        data = json.loads(response)
        if not data.get('ok'): raise RuntimeError(data.get('error') or 'Falha na analise MFCC.')
        return data['feature'], float(data['duration'])

    def close(self):
        try:self.process.terminate()
        except Exception:pass


def _managed_features(path: Path):
    global _FEATURE_CLIENT
    if _FEATURE_CLIENT is None:
        _FEATURE_CLIENT = ManagedFeatureClient()
        atexit.register(_FEATURE_CLIENT.close)
    return _FEATURE_CLIENT.get(path)


def cosine_similarity(left, right):
    return float(sum(float(a) * float(b) for a, b in zip(left, right)))


def open_path(path: Path):
    if sys.platform.startswith('win'):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


class Cancelled(Exception):
    pass


class ScreenSafeTooltip:
    def __init__(self,widget,text):
        self.widget=widget;self.text=text;self.window=None;self.after_id=None
        widget.bind('<Enter>',self.schedule,add='+');widget.bind('<Leave>',self.hide,add='+');widget.bind('<ButtonPress>',self.hide,add='+')

    def schedule(self,_event=None):
        self.hide();self.after_id=self.widget.after(250,self.show)

    def show(self):
        self.after_id=None
        if self.window:return
        tip=Toplevel(self.widget);tip.wm_overrideredirect(True);tip.attributes('-topmost',True)
        label=Label(tip,text=self.text,justify='left',wraplength=430,bg='#FFF7CC',fg='#111827',relief='solid',bd=1,padx=9,pady=7,font=('Segoe UI',9));label.pack()
        tip.update_idletasks();width=tip.winfo_reqwidth();height=tip.winfo_reqheight();screen_w=self.widget.winfo_screenwidth();screen_h=self.widget.winfo_screenheight()
        x=self.widget.winfo_rootx()+self.widget.winfo_width()+8;y=self.widget.winfo_rooty()
        if x+width>screen_w-8:x=self.widget.winfo_rootx()-width-8
        x=max(8,min(x,screen_w-width-8));y=max(8,min(y,screen_h-height-8));tip.geometry(f'+{x}+{y}');self.window=tip

    def hide(self,_event=None):
        if self.after_id:
            try:self.widget.after_cancel(self.after_id)
            except Exception:pass
            self.after_id=None
        if self.window:
            try:self.window.destroy()
            except Exception:pass
            self.window=None


def audio_features(path: Path):
    if getattr(sys, 'frozen', False):
        return _managed_features(path)
    librosa = importlib.import_module('lib' + 'rosa')
    np = importlib.import_module('num' + 'py')
    audio, rate = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    duration = float(librosa.get_duration(y=audio, sr=rate))
    mfcc = librosa.feature.mfcc(y=audio, sr=rate, n_mfcc=N_MFCC)
    fingerprint = np.mean(mfcc, axis=1).astype(np.float64)
    norm = float(np.linalg.norm(fingerprint))
    if not norm:
        raise ValueError('áudio sem conteúdo suficiente')
    return fingerprint / norm, duration


def collect_files(root: Path, suffix: str) -> list[Path]:
    return sorted((path for path in root.rglob('*') if path.is_file() and path.suffix.casefold() == suffix), key=lambda p: str(p).casefold())


def unique_destination(folder: Path, filename: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if not target.exists(): return target
    source = Path(filename)
    for number in range(2, 1001):
        candidate = folder / f'{source.stem}_{number}{source.suffix}'
        if not candidate.exists(): return candidate
    raise RuntimeError(f'Limite de colisões atingido para {filename}')


def organize_audio_in_named_folders(root: Path, *, progress=None, log=None, cancelled=None):
    """Move every audio into a sibling folder named after its own stem."""
    progress=progress or (lambda value,text='':None);log=log or (lambda text:None);cancelled=cancelled or (lambda:False)
    files=sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.casefold() in AUDIO_EXTENSIONS),key=lambda p:str(p).casefold())
    if not files:raise RuntimeError('Nenhum arquivo de áudio foi encontrado na pasta da etapa 1.')
    moved=already=0
    for index,source in enumerate(files,1):
        if cancelled():raise Cancelled('Processo cancelado.')
        if source.parent.name.casefold()==source.stem.casefold():
            already+=1;log(f'JÁ ORGANIZADO: {source}');progress(index*100/len(files),f'Organizando áudio {index}/{len(files)}');continue
        folder=source.parent/source.stem;target=unique_destination(folder,source.name)
        shutil.move(str(source),str(target));moved+=1;log(f'ORGANIZADO: {source.name} → {folder.name}\\{target.name}')
        progress(index*100/len(files),f'Organizando áudio {index}/{len(files)}')
    return {'moved':moved,'already':already}


def _pair_pt_wavs_with_oggs(wavs,oggs):
    by_stem={}
    for ogg in oggs:by_stem.setdefault(ogg.stem.casefold(),[]).append(ogg)
    used=set();pairs=[];unmatched=[]
    for wav in wavs:
        choices=[ogg for ogg in by_stem.get(wav.stem.casefold(),[]) if ogg not in used]
        if choices:used.add(choices[0]);pairs.append((wav,choices[0]))
        else:unmatched.append(wav)
    remaining=[ogg for ogg in oggs if ogg not in used]
    if len(unmatched)==len(remaining):pairs.extend(zip(unmatched,remaining));unmatched=[]
    return pairs,unmatched


def restore_dubbed_audio_positions(root: Path, *, progress=None, log=None, cancelled=None):
    """Move WAV PT-BR two levels up, rename from OGG, then remove completed scene folders."""
    progress=progress or (lambda value,text='':None);log=log or (lambda text:None);cancelled=cancelled or (lambda:False)
    pt_folders=sorted((p for p in root.rglob('*') if p.is_dir() and p.name.casefold()=='wav pt-br'),key=lambda p:str(p).casefold())
    if not pt_folders:raise RuntimeError('Nenhuma pasta WAV PT-BR foi encontrada na pasta da etapa 3.')
    moved=skipped=removed=0
    for index,pt_folder in enumerate(pt_folders,1):
        if cancelled():raise Cancelled('Processo cancelado.')
        scene=pt_folder.parent;destination=scene.parent
        wavs=sorted((p for p in pt_folder.iterdir() if p.is_file() and p.suffix.casefold()=='.wav'),key=lambda p:p.name.casefold())
        oggs=sorted((p for p in scene.iterdir() if p.is_file() and p.suffix.casefold()=='.ogg'),key=lambda p:p.name.casefold())
        pairs,unmatched=_pair_pt_wavs_with_oggs(wavs,oggs)
        complete=bool(wavs) and not unmatched and len(pairs)==len(wavs)
        for wav,ogg in pairs:
            target=destination/f'{ogg.stem}.wav'
            if target.exists():skipped+=1;complete=False;log(f'IGNORADO — destino já existe: {target}');continue
            shutil.move(str(wav),str(target));moved+=1;log(f'RESTAURADO: {wav.name} → {target}')
        for wav in unmatched:skipped+=1;complete=False;log(f'IGNORADO — sem OGG correspondente: {wav}')
        if complete and scene.exists():
            shutil.rmtree(scene);removed+=1;log(f'PASTA DA CENA REMOVIDA: {scene}')
        elif not wavs:log(f'IGNORADO — WAV PT-BR vazio: {pt_folder}')
        progress(index*100/len(pt_folders),f'Restaurando pasta {index}/{len(pt_folders)}')
    return {'moved':moved,'skipped':skipped,'removed':removed}


def paired_scene_folders(root: Path):
    paired=set()
    for folder in (root,*sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:str(p).casefold())):
        try:names={p.name.casefold() for p in folder.iterdir() if p.is_dir()}
        except OSError:continue
        if {'wav ingles','wav pt-br'} <= names:paired.add(folder)
    return paired


def copy_unpaired_results(root: Path, destination: Path, *, progress=None, log=None, cancelled=None):
    """Copy files outside paired scene folders while preserving their relative hierarchy."""
    progress=progress or (lambda value,text='':None);log=log or (lambda text:None);cancelled=cancelled or (lambda:False)
    root=root.resolve();destination=destination.resolve()
    if destination==root or root in destination.parents:raise RuntimeError('Escolha uma pasta de destino fora da pasta de resultados.')
    protected=paired_scene_folders(root);files=sorted((p for p in root.rglob('*') if p.is_file()),key=lambda p:str(p).casefold())
    unpaired=[p for p in files if not any(scene==p.parent or scene in p.parents for scene in protected)]
    if not unpaired:raise RuntimeError('Não foram encontrados arquivos sem par para copiar.')
    copied=0
    for index,source in enumerate(unpaired,1):
        if cancelled():raise Cancelled('Processo cancelado.')
        target=destination/source.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():target=unique_destination(target.parent,target.name)
        shutil.copy2(source,target);copied+=1;log(f'COPIADO SEM PAR: {source.relative_to(root)}')
        progress(index*100/len(unpaired),f'Copiando sem pares {index}/{len(unpaired)}')
    return {'copied':copied,'protected':len(protected),'destination':str(destination)}


def remove_unpaired_results(root: Path, *, progress=None, log=None, cancelled=None):
    """Delete only files outside paired scenes and remove directories left empty."""
    progress=progress or (lambda value,text='':None);log=log or (lambda text:None);cancelled=cancelled or (lambda:False)
    root=root.resolve();protected=paired_scene_folders(root)
    files=sorted((p for p in root.rglob('*') if p.is_file()),key=lambda p:str(p).casefold())
    removable=[p for p in files if not any(scene==p.parent or scene in p.parents for scene in protected)]
    for index,path in enumerate(removable,1):
        if cancelled():raise Cancelled('Processo cancelado.')
        path.unlink();log(f'EXCLUÍDO SEM PAR: {path.relative_to(root)}');progress(index*90/max(1,len(removable)),f'Excluindo sem pares {index}/{len(removable)}')
    removed_dirs=0
    protected_and_ancestors=set(protected)
    for scene in protected:
        protected_and_ancestors.update(parent for parent in scene.parents if parent==root or root in parent.parents)
    directories=sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda p:(len(p.parts),str(p).casefold()),reverse=True)
    for folder in directories:
        if folder in protected_and_ancestors:continue
        try:
            if not any(folder.iterdir()):folder.rmdir();removed_dirs+=1
        except OSError:pass
    progress(100,'Limpeza dos resultados sem par concluída')
    return {'deleted':len(removable),'removed_dirs':removed_dirs,'protected':len(protected)}


def run_matching_pass(wav_en_root: Path, wav_pt_root: Path, ogg_root: Path, *,
                      similarity_threshold=.95, duration_tolerance=.1, require_duration=True,
                      progress=None, log=None, cancelled=None):
    """Move matched EN/PT pairs beside their OGG reference, preserving the proven workflow."""
    progress = progress or (lambda value, text='': None)
    log = log or (lambda text: None)
    cancelled = cancelled or (lambda: False)
    oggs = collect_files(ogg_root, '.ogg')
    wavs = collect_files(wav_en_root, '.wav')
    pts = {path.relative_to(wav_pt_root).as_posix(): path for path in collect_files(wav_pt_root, '.wav')}
    if not oggs: raise RuntimeError('Nenhum OGG foi encontrado na janela 3.')
    if not wavs: raise RuntimeError('Nenhum WAV em inglês foi encontrado na janela 1.')
    log(f'Indexando {len(oggs)} OGG e comparando {len(wavs)} WAV em inglês.')
    reference_paths, reference_features, reference_durations = [], [], []
    total_work = len(oggs) + len(wavs)
    for index, path in enumerate(oggs, 1):
        if cancelled(): raise Cancelled('Processo cancelado.')
        try:
            fingerprint, duration = audio_features(path)
            reference_paths.append(path); reference_features.append(fingerprint); reference_durations.append(duration)
        except Exception as exc: log(f'OGG ignorado: {path.name}: {exc}')
        progress(index * 45 / max(1, total_work), f'Indexando OGG {index}/{len(oggs)}')
    if not reference_features: raise RuntimeError('Nenhum OGG pôde ser analisado.')
    moved_en = moved_pt = 0; matches = []
    for index, source in enumerate(wavs, 1):
        if cancelled(): raise Cancelled('Processo cancelado.')
        relative = source.relative_to(wav_en_root).as_posix()
        try:
            fingerprint, duration = audio_features(source)
            similarities = [cosine_similarity(reference_feature, fingerprint) for reference_feature in reference_features]
            best = max(range(len(similarities)), key=similarities.__getitem__); similarity = similarities[best]
            reference = reference_paths[best]
            difference = abs(duration - float(reference_durations[best]))
            accepted = similarity >= similarity_threshold and (not require_duration or difference <= duration_tolerance)
            if accepted:
                target_en = unique_destination(reference.parent / 'WAV INGLES', source.name)
                shutil.move(str(source), str(target_en)); moved_en += 1
                pt_source = pts.pop(relative, None)
                target_pt = None
                if pt_source is not None and pt_source.is_file():
                    target_pt = unique_destination(reference.parent / 'WAV PT-BR', source.name)
                    shutil.move(str(pt_source), str(target_pt)); moved_pt += 1
                matches.append((source, reference, target_en, target_pt, similarity, difference))
                log(f'CORRESPONDÊNCIA: {source.name} → {reference.name} | MFCC {similarity:.4f}' + (f' | diferença {difference:.3f}s' if require_duration else ' | segunda passagem'))
            elif similarity >= similarity_threshold and require_duration:
                log(f'DURAÇÃO DIFERENTE: {source.name} / {reference.name} | MFCC {similarity:.4f} | diferença {difference:.3f}s')
        except Exception as exc: log(f'WAV ignorado: {source.name}: {exc}')
        progress(45 + index * 55 / max(1, len(wavs)), f'Comparando WAV {index}/{len(wavs)}')
    return {'moved_en': moved_en, 'moved_pt': moved_pt, 'matches': matches, 'remaining': len(wavs)-moved_en}


def filter_final_results(ogg_root: Path, *, progress=None, log=None, cancelled=None):
    """Keep the closest English WAV for each OGG and remove its losing PT pairs."""
    progress = progress or (lambda value, text='': None)
    log = log or (lambda text: None)
    cancelled = cancelled or (lambda: False)
    groups = []
    for folder in sorted({path.parent for path in collect_files(ogg_root, '.ogg')}, key=lambda p: str(p).casefold()):
        en_folder, pt_folder = folder / 'WAV INGLES', folder / 'WAV PT-BR'
        oggs = sorted((path for path in folder.iterdir() if path.is_file() and path.suffix.casefold() == '.ogg'), key=lambda p:p.name.casefold())
        wavs = collect_files(en_folder, '.wav') if en_folder.is_dir() else []
        if oggs and wavs:
            groups.append((folder, oggs, wavs, pt_folder))
    if not groups:
        raise RuntimeError('Não encontrei resultados WAV INGLES junto dos OGG na janela 3.')
    deleted_en = deleted_pt = kept = 0
    for group_index, (folder, oggs, wavs, pt_folder) in enumerate(groups, 1):
        if cancelled(): raise Cancelled('Processo cancelado.')
        references = []
        for ogg in oggs:
            try: references.append((ogg, audio_features(ogg)[0]))
            except Exception as exc: log(f'OGG ignorado no filtro: {ogg.name}: {exc}')
        candidates = []
        for wav in wavs:
            if cancelled(): raise Cancelled('Processo cancelado.')
            try:
                feature = audio_features(wav)[0]
                if references:
                    ref, score = max(((ref, cosine_similarity(feature, ref_feature)) for ref, ref_feature in references), key=lambda item: item[1])
                    candidates.append((ref, score, wav))
            except Exception as exc: log(f'WAV ignorado no filtro: {wav.name}: {exc}')
        by_reference = {}
        for ref, score, wav in candidates:
            by_reference.setdefault(ref, []).append((score, wav))
        winners = set()
        for ref, choices in by_reference.items():
            score, winner = sorted(choices, key=lambda item: (-item[0], item[1].name.casefold()))[0]
            winners.add(winner); kept += 1
            log(f'MANTIDO: {winner.name} → {ref.name} | MFCC {score:.4f}')
        for _ref, _score, wav in candidates:
            if wav in winners: continue
            wav.unlink(); deleted_en += 1
            pt = pt_folder / wav.name
            if pt.is_file(): pt.unlink(); deleted_pt += 1
            log(f'REPETIDO EXCLUÍDO: {wav.name}')
        progress(group_index * 100 / len(groups), f'Filtrando pasta {group_index}/{len(groups)}')
    return {'kept': kept, 'deleted_en': deleted_en, 'deleted_pt': deleted_pt}


def remove_mismatched_results(ogg_root: Path, similarity_threshold=.95, *, progress=None, log=None, cancelled=None):
    """Remove EN WAVs below the best OGG similarity and their same-name PT pair."""
    progress=progress or (lambda value,text='':None);log=log or (lambda text:None);cancelled=cancelled or (lambda:False)
    groups=[]
    for folder in sorted({path.parent for path in collect_files(ogg_root,'.ogg')},key=lambda p:str(p).casefold()):
        oggs=sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.casefold()=='.ogg'),key=lambda p:p.name.casefold())
        en_folder,pt_folder=folder/'WAV INGLES',folder/'WAV PT-BR';wavs=collect_files(en_folder,'.wav') if en_folder.is_dir() else []
        if oggs and wavs:groups.append((oggs,wavs,pt_folder))
    if not groups:raise RuntimeError('Não encontrei WAV INGLES junto dos OGG na janela 3.')
    kept=deleted_en=deleted_pt=0
    for group_index,(oggs,wavs,pt_folder) in enumerate(groups,1):
        references=[]
        for ogg in oggs:
            if cancelled():raise Cancelled('Processo cancelado.')
            try:references.append((ogg,audio_features(ogg)[0]))
            except Exception as exc:log(f'OGG ignorado na verificação final: {ogg.name}: {exc}')
        for wav in wavs:
            if cancelled():raise Cancelled('Processo cancelado.')
            try:
                feature=audio_features(wav)[0]
                reference,score=max(((ogg,cosine_similarity(feature,ref_feature)) for ogg,ref_feature in references),key=lambda item:item[1])
                if score>=similarity_threshold:
                    kept+=1;log(f'APROVADO: {wav.name} corresponde a {reference.name} | MFCC {score:.4f}')
                else:
                    wav.unlink();deleted_en+=1;pt=pt_folder/wav.name
                    if pt.is_file():pt.unlink();deleted_pt+=1
                    log(f'NÃO CORRESPONDE — EXCLUÍDO: {wav.name} / {reference.name} | MFCC {score:.4f}')
            except Exception as exc:log(f'WAV preservado porque não pôde ser verificado: {wav.name}: {exc}')
        progress(group_index*100/len(groups),f'Verificando resultado {group_index}/{len(groups)}')
    return {'kept':kept,'deleted_en':deleted_en,'deleted_pt':deleted_pt}


class AudioFrequencySeparatorApp:
    def __init__(self, root, project_root=None, project_actions=None):
        self.root = root; self.project_root = Path(project_root or Path.cwd())
        self.project_actions = project_actions or {}; self.theme = {}
        self.paths = [None, None, None]; self.trees = []; self.stage_paths=[None,None];self.stage_trees=[];self.running = False
        self.first_pass_completed = False; self.cancel_event = threading.Event(); self.events = queue.Queue()
        self.status_var = StringVar(value='Arraste uma pasta para cada janela.')
        self.progress_var = StringVar(value='0')
        self.first_similarity_var=StringVar(value='0.95');self.second_similarity_var=StringVar(value='0.95')
        self.final_similarity_var=StringVar(value='0.95');self.duration_var=StringVar(value='0.10')
        self.build_ui(); self.root.after(100, self.poll_events)

    def build_ui(self):
        header=Frame(self.root,bg='#F5F6FA');header.pack(fill=X,padx=14,pady=(10,6))
        Label(header,text='SEPARAR ÁUDIO IGUAL POR FREQUÊNCIA IDÊNTICA',bg='#F5F6FA',fg='#172033',font=('Segoe UI',15,'bold')).pack(side=LEFT)
        stage_top=Frame(self.root,bg='#F5F6FA');stage_top.pack(fill=X,padx=14,pady=(0,6));self.stage_color_frames=[]
        stage_specs=(('ETAPA 1 — PREPARAR PASTAS','#2563EB','#DCEEFF','COLOCAR TODOS OS ÁUDIOS EM UMA PASTA COM SEU PRÓPRIO NOME',self.start_stage_one,'Arraste aqui a pasta que receberá a dublagem.'),('ETAPA 3 — DEVOLVER DUBLADOS','#B7791F','#FFF2BF','VOLTAR ÁUDIOS DUBLADOS PARA POSIÇÃO DOS ÁUDIOS ORIGINAIS',self.start_stage_three,'Arraste aqui a pasta do resultado da janela 3 da etapa 2 para voltar os áudios à posição normal antes de reempacotar e colocar no jogo.'))
        for index,(title,color,light,button_text,command,help_text) in enumerate(stage_specs):
            panel=Frame(stage_top,bg=light,bd=1,relief='solid');panel.grid(row=0,column=index,sticky='nsew',padx=(0 if index==0 else 6,0));stage_top.columnconfigure(index,weight=1,uniform='stage13');self.stage_color_frames.append((panel,light))
            Label(panel,text=title,bg=color,fg='white',font=('Segoe UI',10,'bold'),pady=4).pack(fill=X)
            help_row=Frame(panel,bg=light);help_row.pack(fill=X,padx=6,pady=(3,0));help_button=Button(help_row,text='?',width=3,font=('Segoe UI',9,'bold'),relief='flat',cursor='question_arrow');help_button.pack(side=RIGHT);ScreenSafeTooltip(help_button,help_text)
            bar=Frame(panel,bg=light);bar.pack(fill=X,padx=6,pady=4)
            choose=Button(bar,text='ADICIONAR PASTA',command=lambda i=index:self.choose_stage_folder(i),relief='flat',cursor='hand2');choose.pack(side=LEFT,fill=X,expand=True)
            clear=Button(bar,text='LIMPAR',command=lambda i=index:self.set_stage_folder(i,None),relief='flat',cursor='hand2');clear.pack(side=LEFT,padx=(5,0))
            tree_frame=Frame(panel,bg=light);tree_frame.pack(fill=BOTH,expand=True,padx=6)
            tree=ttk.Treeview(tree_frame,columns=('path',),displaycolumns=(),show='tree',height=6,selectmode='browse',style='Frequency.Treeview')
            scroll=ttk.Scrollbar(tree_frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
            tree.pack(side=LEFT,fill=BOTH,expand=True);scroll.pack(side=RIGHT,fill=Y)
            tree.bind('<<TreeviewOpen>>',lambda event,t=tree:self.expand_tree(t));tree.bind('<Double-Button-1>',lambda event,t=tree:self.open_tree_item(t))
            self.enable_stage_drop(tree,index);self.stage_trees.append(tree)
            action=Button(panel,text=button_text,command=command,relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');action.pack(fill=X,padx=6,pady=5)
            if index==0:self.stage_one_button=action
            else:self.stage_three_button=action
            choose._role='primary';clear._role='secondary'
        stage_two=Frame(self.root,bg='#DDF3DF',bd=1,relief='solid');stage_two.pack(fill=BOTH,expand=True,padx=14,pady=(2,8));self.stage_color_frames.append((stage_two,'#DDF3DF'))
        Label(stage_two,text='ETAPA 2 — COMPARAR, SEPARAR E FILTRAR',bg='#DDF3DF',fg='#172033',font=('Segoe UI',11,'bold'),anchor='w').pack(fill=X,padx=8,pady=(5,0))
        panes=ttk.PanedWindow(stage_two,orient='horizontal');panes.pack(fill=BOTH,expand=True,padx=8,pady=6)
        titles=('JANELA 1 — WAV INGLÊS','JANELA 2 — WAV PORTUGUÊS','JANELA 3 — OGG / RESULTADO FINAL')
        colors=('#2563EB','#16A34A','#7C3AED')
        help_texts=('Arraste aqui a pasta do jogo de PC original em que está a dublagem original do jogo.','Arraste aqui a pasta que contém os áudios dublados por fãs ou uma atualização de dublagem oficial.','Arraste aqui a pasta de destino para a qual a dublagem será portada; normalmente é a mesma pasta usada na etapa 1.')
        for index,(title,color) in enumerate(zip(titles,colors)):
            panel=Frame(panes,bg='white',bd=1,relief='solid');panes.add(panel,weight=1)
            Label(panel,text=title,bg=color,fg='white',font=('Segoe UI',10,'bold'),pady=6).pack(fill=X)
            help_row=Frame(panel,bg='white');help_row.pack(fill=X,padx=6,pady=(3,0));help_button=Button(help_row,text='?',width=3,font=('Segoe UI',9,'bold'),relief='flat',cursor='question_arrow');help_button.pack(side=RIGHT);ScreenSafeTooltip(help_button,help_texts[index])
            bar=Frame(panel,bg='white');bar.pack(fill=X,padx=6,pady=5)
            choose=Button(bar,text='ADICIONAR PASTA',command=lambda i=index:self.choose_folder(i),relief='flat',cursor='hand2');choose.pack(side=LEFT,fill=X,expand=True)
            clear=Button(bar,text='LIMPAR',command=lambda i=index:self.set_folder(i,None),relief='flat',cursor='hand2');clear.pack(side=LEFT,padx=(5,0))
            tree=ttk.Treeview(panel,columns=('path',),displaycolumns=(),show='tree',selectmode='browse',style='Frequency.Treeview')
            scroll=ttk.Scrollbar(panel,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
            tree.pack(side=LEFT,fill=BOTH,expand=True,padx=(6,0),pady=(0,6));scroll.pack(side=RIGHT,fill=Y,padx=(0,6),pady=(0,6))
            tree.bind('<<TreeviewOpen>>',lambda event,t=tree:self.expand_tree(t))
            tree.bind('<Double-Button-1>',lambda event,t=tree:self.open_tree_item(t))
            self.enable_drop(tree,index);self.trees.append(tree)
            choose._role='primary';clear._role='secondary'
        controls=Frame(stage_two,bg='#DDF3DF');controls.pack(fill=X,padx=8,pady=(4,4));self.config_panels=[]
        config_specs=(('#86D9A1','1ª PASSAGEM',(('MFCC',self.first_similarity_var),('Duração',self.duration_var))),('#CBBBF7','2ª PASSAGEM',(('MFCC',self.second_similarity_var),)),('#F7D57C','3ª — REPETIDOS / DIFERENTES',(('Critério','mais próximo'),)),('#85CEBF','4ª — RESULTADO FINAL',(('MFCC mínimo',self.final_similarity_var),)),('#F3B4CF','5ª — ÁUDIOS SEM PARES',(('Ação','copiar / conferir'),)))
        action_help=(
            'A primeira passagem analisa os WAV originais da janela 1 e os compara de forma robusta com os OGG originais da janela 3, usando semelhança MFCC e duração. Quando encontra um par, move o WAV inglês da janela 1 e o WAV dublado correspondente da janela 2 para as pastas WAV INGLES e WAV PT-BR ao lado do OGG na janela 3.',
            'A segunda passagem refina o que restou da primeira. Ela compara novamente os WAV originais restantes da janela 1 com os OGG da janela 3, usando a semelhança MFCC sem bloquear pela diferença de duração. Para cada correspondência, move juntos o WAV inglês da janela 1 e o WAV dublado correspondente da janela 2 para a janela 3.',
            'Esta filtragem examina os candidatos produzidos pelas passagens 1 e 2. Para cada OGG da janela 3, mantém somente o WAV INGLES mais próximo e o WAV PT-BR de mesmo nome, removendo os candidatos repetidos ou menos semelhantes.',
            'A filtragem final refaz a comparação entre cada arquivo de WAV INGLES e os OGG da janela 3. Remove o WAV inglês que ficar abaixo do MFCC mínimo e também remove o WAV PT-BR de mesmo nome. Arquivos que não puderem ser analisados são preservados para conferência.',
            'Salva, na pasta escolhida por você e mantendo a hierarquia, uma cópia dos arquivos que ficaram sem pares. Depois da cópia, você pode apagar esses itens da janela 3 e conservar somente as cenas que possuem WAV INGLES e WAV PT-BR. Em seguida, arraste o resultado para a etapa 3 para devolver os áudios dublados às posições normais.'
        )
        self.config_panel_colors=[spec[0] for spec in config_specs]
        for index,(color,title,fields) in enumerate(config_specs):
            box=Frame(controls,bg=color,padx=6,pady=4);box.grid(row=0,column=index,sticky='nsew',padx=(0 if index==0 else 3,0));controls.columnconfigure(index,weight=1,uniform='frequency_actions');self.config_panels.append(box)
            title_row=Frame(box,bg=color);title_row.pack(fill=X)
            Label(title_row,text=title,bg=color,fg='#111827',font=('Segoe UI',8,'bold')).pack(side=LEFT)
            help_button=Button(title_row,text='?',width=2,font=('Segoe UI',8,'bold'),relief='flat',cursor='question_arrow');help_button.pack(side=RIGHT);ScreenSafeTooltip(help_button,action_help[index])
            line=Frame(box,bg=color);line.pack(fill=X)
            for field,value in fields:
                Label(line,text=field+':',bg=color,fg='#111827').pack(side=LEFT,padx=(0,3))
                if isinstance(value,StringVar):Entry(line,textvariable=value,width=10,font=('Segoe UI',10),justify='center').pack(side=LEFT,padx=(0,7),ipady=3)
                else:Label(line,text=value,bg=color,fg='#111827',font=('Segoe UI',8,'bold')).pack(side=LEFT,padx=(0,7))
        self.first_button=Button(controls,text='1ª — EXECUTAR PRIMEIRA PASSAGEM',command=lambda:self.start_pass(True),relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');self.first_button.grid(row=1,column=0,sticky='nsew',pady=(2,0))
        self.second_button=Button(controls,text='2ª — EXECUTAR SEGUNDA PASSAGEM',command=lambda:self.start_pass(False),relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');self.second_button.grid(row=1,column=1,sticky='nsew',padx=(3,0),pady=(2,0))
        self.filter_button=Button(controls,text='3ª — FILTRAR REPETIDOS OU DIFERENTES',command=self.start_filter,relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');self.filter_button.grid(row=1,column=2,sticky='nsew',padx=(3,0),pady=(2,0))
        self.final_filter_button=Button(controls,text='4ª — FILTRAR RESULTADO FINAL',command=self.start_final_filter,relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');self.final_filter_button.grid(row=1,column=3,sticky='nsew',padx=(3,0),pady=(2,0))
        self.unpaired_button=Button(controls,text='5ª — SALVAR ÁUDIOS SEM PARES',command=self.start_unpaired_copy,relief='flat',font=('Segoe UI',9,'bold'),height=2,cursor='hand2');self.unpaired_button.grid(row=1,column=4,sticky='nsew',padx=(3,0),pady=(2,0))
        self.progress=ttk.Progressbar(stage_two,maximum=100,mode='determinate');self.progress.pack(fill=X,padx=8)
        Label(stage_two,textvariable=self.status_var,bg='#DDF3DF',anchor='w').pack(fill=X,padx=8,pady=(3,4))
        logframe=Frame(stage_two,bg='#DDF3DF');logframe.pack(fill=BOTH,expand=False,padx=8,pady=(0,4))
        self.log=Text(logframe,height=7,wrap='word',state='disabled',font=('Consolas',8));self.log.pack(fill=BOTH,expand=True)
        utility=Frame(stage_two,bg='#DDF3DF');utility.pack(fill=X,padx=8,pady=(0,7))
        self.cancel_button=Button(utility,text='CANCELAR',command=self.cancel,relief='flat',cursor='hand2',state='disabled');self.cancel_button.pack(side=LEFT,fill=X,expand=True)
        self.open_button=Button(utility,text='ABRIR RESULTADO',command=self.open_result,relief='flat',cursor='hand2');self.open_button.pack(side=LEFT,fill=X,expand=True,padx=(6,0))

    def enable_drop(self,widget,index):
        try:
            widget.drop_target_register('DND_Files')
            widget.dnd_bind('<<Drop>>',lambda event,i=index:self.on_drop(event,i))
        except Exception: pass

    def enable_stage_drop(self,widget,index):
        try:
            widget.drop_target_register('DND_Files');widget.dnd_bind('<<Drop>>',lambda event,i=index:self.on_stage_drop(event,i))
        except Exception:pass

    def on_stage_drop(self,event,index):
        try:items=self.root.winfo_toplevel().tk.splitlist(event.data)
        except Exception:items=[str(getattr(event,'data','')).strip('{}"')]
        path=next((Path(item) for item in items if Path(item).is_dir()),None)
        if path:self.set_stage_folder(index,path)
        else:self.status_var.set('Arraste uma pasta válida.')
        return 'break'

    def choose_stage_folder(self,index):
        value=filedialog.askdirectory(parent=self.root,title=('Etapa 1 — pasta com os áudios','Etapa 3 — pasta processada')[index])
        if value:self.set_stage_folder(index,Path(value))

    def set_stage_folder(self,index,path):
        self.stage_paths[index]=Path(path).resolve() if path else None;tree=self.stage_trees[index];tree.delete(*tree.get_children())
        if self.stage_paths[index]:
            root=self.stage_paths[index];node=tree.insert('',END,text=root.name or str(root),values=(str(root),),open=True);self.populate_node(tree,node,root)

    def on_drop(self,event,index):
        try: items=self.root.winfo_toplevel().tk.splitlist(event.data)
        except Exception: items=[str(getattr(event,'data','')).strip('{}"')]
        path=next((Path(item) for item in items if Path(item).is_dir()),None)
        if path:self.set_folder(index,path)
        else:self.status_var.set('Arraste uma pasta válida.')
        return 'break'

    def choose_folder(self,index):
        value=filedialog.askdirectory(parent=self.root,title=('WAV inglês','WAV português','Referências OGG / resultado')[index])
        if value:self.set_folder(index,Path(value))

    def set_folder(self,index,path):
        self.paths[index]=Path(path).resolve() if path else None;self.reset_tree(index)
        self.first_pass_completed=False;self.second_button.configure(state='normal')

    def reset_tree(self,index):
        tree=self.trees[index];tree.delete(*tree.get_children())
        path=self.paths[index]
        if not path:return
        node=tree.insert('',END,text=path.name or str(path),values=(str(path),),open=True)
        self.populate_node(tree,node,path)

    def populate_node(self,tree,node,path):
        tree.delete(*tree.get_children(node))
        try:children=sorted(path.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold()))
        except OSError:return
        for child in children:
            if child.is_file() and child.suffix.casefold() not in AUDIO_EXTENSIONS:continue
            item=tree.insert(node,END,text=('📁 ' if child.is_dir() else '♫ ')+child.name,values=(str(child),))
            if child.is_dir():tree.insert(item,END,text='…',values=('',))

    def expand_tree(self,tree):
        item=tree.focus();values=tree.item(item,'values')
        if not values:return
        path=Path(values[0]);children=tree.get_children(item)
        if path.is_dir() and len(children)==1 and tree.item(children[0],'values')==('',):self.populate_node(tree,item,path)

    def open_tree_item(self,tree):
        item=tree.focus();values=tree.item(item,'values')
        if values and Path(values[0]).exists():open_path(Path(values[0]) if Path(values[0]).is_dir() else Path(values[0]).parent)

    def append_log(self,text):
        self.log.configure(state='normal');self.log.insert(END,str(text)+'\n');self.log.see(END);self.log.configure(state='disabled')

    def set_process_buttons(self,state):
        for button in (self.stage_one_button,self.stage_three_button,self.first_button,self.second_button,self.filter_button,self.final_filter_button,self.unpaired_button):button.configure(state=state)

    def start_stage_one(self):
        root=self.stage_paths[0]
        if self.running:return
        if not root or not root.is_dir():messagebox.showwarning('Etapa 1','Arraste ou adicione a pasta com os áudios na janela da etapa 1.',parent=self.root);return
        if not messagebox.askyesno('Etapa 1',f'Criar uma pasta com o nome de cada áudio e mover o próprio áudio para dentro?\n\nPasta: {root}',parent=self.root):return
        self.running=True;self.cancel_event.clear();self.set_process_buttons('disabled');self.cancel_button.configure(state='normal');self.progress.configure(value=0);self.status_var.set('Etapa 1: organizando áudios…')
        def worker():
            try:
                result=organize_audio_in_named_folders(root,progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('stage_one_done',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_stage_three(self):
        root=self.stage_paths[1]
        if self.running:return
        if not root or not root.is_dir():messagebox.showwarning('Etapa 3','Arraste ou adicione a pasta processada na janela da etapa 3.',parent=self.root);return
        question=('Mover os áudios de WAV PT-BR para a posição dos originais, renomeando-os pelo OGG?\n\n'
                  'Depois que todos os WAV PT-BR de uma cena forem movidos, a pasta dessa cena será apagada com o OGG e WAV INGLES. '
                  'Pastas com colisão, erro ou correspondência incompleta serão preservadas.\n\nEsta operação não pode ser desfeita.')
        if not messagebox.askyesno('Etapa 3 — voltar áudios dublados',question,parent=self.root):return
        self.running=True;self.cancel_event.clear();self.set_process_buttons('disabled');self.cancel_button.configure(state='normal');self.progress.configure(value=0);self.status_var.set('Etapa 3: devolvendo áudios dublados…')
        def worker():
            try:
                result=restore_dubbed_audio_positions(root,progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('stage_three_done',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_unpaired_copy(self):
        if self.running:return
        root=self.paths[2]
        if not root or not root.is_dir():messagebox.showwarning('Etapa 2 — sem pares','Informe na janela 3 a pasta dos OGG e resultados.',parent=self.root);return
        value=filedialog.askdirectory(parent=self.root,title='Salvar cópia dos áudios sem pares em…')
        if not value:return
        destination=Path(value)
        self.running=True;self.cancel_event.clear();self.set_process_buttons('disabled');self.cancel_button.configure(state='normal');self.progress.configure(value=0);self.status_var.set('Copiando arquivos sem pares com sua hierarquia…')
        def worker():
            try:
                result=copy_unpaired_results(root,destination,progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('unpaired_copied',(root,result)))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_unpaired_cleanup(self,root):
        self.cancel_event.clear();self.progress.configure(value=0);self.status_var.set('Removendo da origem somente os arquivos sem pares…')
        def worker():
            try:
                result=remove_unpaired_results(root,progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('unpaired_cleaned',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_pass(self,strict):
        if self.running:return
        if not all(path and path.is_dir() for path in self.paths):messagebox.showwarning('Pastas necessárias','Informe as três pastas: WAV inglês, WAV português e referências OGG.',parent=self.root);return
        try:
            threshold=float((self.first_similarity_var if strict else self.second_similarity_var).get().replace(',','.'))
            tolerance=float(self.duration_var.get().replace(',','.'))
        except ValueError:messagebox.showwarning('Configuração','Use números válidos para MFCC e duração.',parent=self.root);return
        if not 0 <= threshold <= 1 or tolerance < 0:
            messagebox.showwarning('Configuração','MFCC deve ficar entre 0 e 1 e a duração não pode ser negativa.',parent=self.root);return
        label='primeira' if strict else 'segunda'
        if not messagebox.askyesno('Mover arquivos',f'Executar a {label} passagem?\n\nOs WAVs correspondentes serão movidos para WAV INGLES e WAV PT-BR junto dos OGG.',parent=self.root):return
        self.running=True;self.cancel_event.clear();self.set_process_buttons('disabled');self.cancel_button.configure(state='normal');self.progress.configure(value=0)
        self.status_var.set(f'Executando {label} passagem…')
        def worker():
            try:
                result=run_matching_pass(*self.paths,similarity_threshold=threshold,duration_tolerance=tolerance,require_duration=strict,
                    progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('done',(strict,result)))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def cancel(self):self.cancel_event.set();self.status_var.set('Cancelamento solicitado…')

    def cancel_run(self):
        self.cancel()

    def start_filter(self):
        if self.running:return
        if not self.paths[2] or not self.paths[2].is_dir():
            messagebox.showwarning('Resultado necessário','Informe na janela 3 a pasta dos OGG e resultados.',parent=self.root);return
        if not messagebox.askyesno('Filtrar repetidos ou diferentes','Manter somente o WAV INGLÊS mais próximo de cada OGG e excluir os outros candidatos, junto do WAV PT-BR correspondente?\n\nEsta exclusão não pode ser desfeita.',parent=self.root):return
        self.running=True;self.cancel_event.clear();self.set_process_buttons('disabled');self.cancel_button.configure(state='normal');self.progress.configure(value=0)
        self.status_var.set('Filtrando repetidos ou diferentes…')
        def worker():
            try:
                result=filter_final_results(self.paths[2],progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('filtered',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_final_filter(self):
        if self.running:return
        if not self.paths[2] or not self.paths[2].is_dir():
            messagebox.showwarning('Resultado necessário','Informe na janela 3 a pasta dos OGG e resultados.',parent=self.root);return
        try:threshold=float(self.final_similarity_var.get().replace(',','.'))
        except ValueError:messagebox.showwarning('Configuração','Use um número válido para o MFCC mínimo.',parent=self.root);return
        if not 0 <= threshold <= 1:
            messagebox.showwarning('Configuração','O MFCC mínimo deve ficar entre 0 e 1.',parent=self.root);return
        question=(f'Comparar somente cada WAV INGLES com os áudios OGG e remover os que não correspondem '
                  f'ao MFCC mínimo {threshold:.2f}?\n\nPara cada WAV INGLES rejeitado, o WAV PT-BR de mesmo nome '
                  'também será removido. Esta exclusão não pode ser desfeita.')
        if not messagebox.askyesno('Filtrar resultado final',question,parent=self.root):return
        self.running=True;self.cancel_event.clear()
        self.set_process_buttons('disabled')
        self.cancel_button.configure(state='normal');self.progress.configure(value=0);self.status_var.set('Verificando WAV INGLES contra os OGG…')
        def worker():
            try:
                result=remove_mismatched_results(self.paths[2],similarity_threshold=threshold,
                    progress=lambda value,text:self.events.put(('progress',(value,text))),log=lambda text:self.events.put(('log',text)),cancelled=self.cancel_event.is_set)
                self.events.put(('final_filtered',result))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll_events(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='log':self.append_log(payload)
                elif kind=='progress':self.progress.configure(value=payload[0]);self.status_var.set(payload[1])
                elif kind=='done':
                    strict,result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    if strict:self.first_pass_completed=True
                    self.second_button.configure(state='normal')
                    self.status_var.set(f"Concluído: {result['moved_en']} WAV inglês e {result['moved_pt']} WAV português movidos; {result['remaining']} restantes.")
                    for index in range(3):self.reset_tree(index)
                elif kind=='filtered':
                    result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    self.status_var.set(f"Filtro concluído: {result['kept']} mantidos; {result['deleted_en']} WAV inglês e {result['deleted_pt']} WAV português repetidos excluídos.")
                    self.reset_tree(2)
                elif kind=='final_filtered':
                    result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    self.status_var.set(f"Verificação concluída: {result['kept']} correspondentes mantidos; {result['deleted_en']} WAV inglês e {result['deleted_pt']} WAV português não correspondentes removidos.")
                    self.reset_tree(2)
                elif kind=='stage_one_done':
                    result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    self.status_var.set(f"Etapa 1 concluída: {result['moved']} áudios organizados; {result['already']} já estavam em pasta própria.");self.set_stage_folder(0,self.stage_paths[0])
                elif kind=='stage_three_done':
                    result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    self.status_var.set(f"Etapa 3 concluída: {result['moved']} WAV movidos; {result['removed']} pastas concluídas removidas; {result['skipped']} itens preservados.");self.set_stage_folder(1,self.stage_paths[1])
                elif kind=='unpaired_copied':
                    root,result=payload;self.progress.configure(value=100)
                    question=(f"Cópia concluída: {result['copied']} arquivos sem pares foram salvos em:\n{result['destination']}\n\n"
                              'Deseja manter na origem somente as cenas que possuem WAV INGLES e WAV PT-BR? '
                              'Os demais arquivos serão excluídos e as pastas vazias removidas. As cenas com as duas pastas serão preservadas.')
                    if messagebox.askyesno('Cópia concluída — limpar origem?',question,parent=self.root):self.start_unpaired_cleanup(root)
                    else:
                        self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.status_var.set(f"Cópia concluída: {result['copied']} arquivos sem pares salvos; origem preservada.")
                elif kind=='unpaired_cleaned':
                    result=payload;self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.progress.configure(value=100)
                    self.status_var.set(f"Limpeza concluída: {result['deleted']} arquivos sem pares e {result['removed_dirs']} pastas vazias removidos; {result['protected']} cenas com os dois pares preservadas.");self.reset_tree(2)
                elif kind=='error':
                    self.running=False;self.cancel_button.configure(state='disabled');self.set_process_buttons('normal');self.status_var.set(payload);self.append_log('ERRO: '+payload)
        except queue.Empty:pass
        try:self.root.after(100,self.poll_events)
        except Exception:pass

    def open_result(self):
        if self.paths[2] and self.paths[2].is_dir():open_path(self.paths[2])

    def refresh_for_project(self):
        for index in range(3):self.reset_tree(index)

    def apply_theme(self,theme):
        self.theme=dict(theme or {});apply_button_style_to_tree(self.root,self.theme)
        surface=self.theme.get('surface','#FFFFFF');root_bg=self.theme.get('root','#F5F6FA');text=self.theme.get('text','#1F2937');input_bg=self.theme.get('input',surface);input_text=self.theme.get('input_text',text);border=self.theme.get('border','#CBD5E1');select=self.theme.get('select','#DBEAFE')
        style=ttk.Style(self.root)
        style.configure('Frequency.Treeview',background=input_bg,fieldbackground=input_bg,foreground=input_text,bordercolor=border,rowheight=23)
        style.map('Frequency.Treeview',background=[('selected',select)],foreground=[('selected',input_text)])
        def recolor(widget):
            try:
                cls=widget.winfo_class()
                if cls=='Frame':widget.configure(bg=root_bg if widget is self.root else surface)
                elif cls=='Label' and str(widget.cget('bg')).upper() in {'#F5F6FA','#FFFFFF','#202938','#2A3546','#334155','#3F4D5F'}:widget.configure(bg=surface,fg=text)
                elif cls in {'Entry','Text'}:widget.configure(bg=input_bg,fg=input_text,insertbackground=input_text,highlightbackground=border)
                for child in widget.winfo_children():recolor(child)
            except Exception:pass
        recolor(self.root)
        for stage_frame,stage_bg in self.stage_color_frames:
            def recolor_stage_frames(widget):
                try:
                    if widget.winfo_class()=='Frame':widget.configure(bg=stage_bg)
                    for child in widget.winfo_children():recolor_stage_frames(child)
                except Exception:pass
            recolor_stage_frames(stage_frame)
        for panel,bg in zip(self.config_panels,self.config_panel_colors):
            fg='#111827'
            def recolor_panel(widget):
                try:
                    if widget.winfo_class()=='Frame':widget.configure(bg=bg)
                    elif widget.winfo_class()=='Label':widget.configure(bg=bg,fg=fg)
                    for child in widget.winfo_children():recolor_panel(child)
                except Exception:pass
            recolor_panel(panel)
        for button,role in ((self.stage_one_button,'primary'),(self.stage_three_button,'teal'),(self.first_button,'success'),(self.second_button,'accent'),(self.filter_button,'warning'),(self.final_filter_button,'teal'),(self.unpaired_button,'danger'),(self.cancel_button,'danger'),(self.open_button,'teal')):apply_button_style(button,self.theme,role)

