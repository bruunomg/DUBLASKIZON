"""Explicit, non-destructive selection of scene audio sources."""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from audacity_openvino import outputs, LABELS

LABELS = {'original':'ORIGINAL', **LABELS, 'dubbed':'DUBLADO'}

def sources(root, original, dubbed=None):
    result={'original':Path(original)}
    if root: result.update(outputs(root, Path(original)))
    if dubbed is not None: result['dubbed']=Path(dubbed)
    return result

def choose(parent, options, title, defaults=('original', 'dubbed')):
    win=tk.Toplevel(parent); win.title(title); win.configure(bg='#202B3B')
    win.transient(parent); win.resizable(False,False)
    tk.Label(win,text='Selecione uma ou várias faixas:',bg='#202B3B',fg='white',font=('Segoe UI',11,'bold')).pack(anchor='w',padx=16,pady=12)
    variables={}; result=None
    for key,label in LABELS.items():
        if key=='dubbed' and key not in options: continue
        available=key in options and Path(options[key]).is_file()
        variable=tk.BooleanVar(win,value=available and key in defaults); variables[key]=variable
        tk.Checkbutton(win,text=label+('' if available else ' — indisponível'),variable=variable,
            state='normal' if available else 'disabled',bg='#202B3B',fg='white',selectcolor='#374151',
            activebackground='#202B3B',activeforeground='white').pack(anchor='w',padx=16,pady=5)
    def accept():
        nonlocal result
        selected=[(key,Path(options[key])) for key,var in variables.items() if var.get() and key in options and Path(options[key]).is_file()]
        if not selected:
            messagebox.showwarning(title,'Selecione ao menos uma faixa.',parent=win); return
        result=selected; win.destroy()
    row=tk.Frame(win,bg='#202B3B');row.pack(fill='x',padx=16,pady=14)
    tk.Button(row,text='USAR FAIXAS SELECIONADAS',command=accept,bg='#4ADE80',padx=12,pady=7).pack(side='left')
    tk.Button(row,text='CANCELAR',command=win.destroy,padx=12,pady=7).pack(side='right',padx=8)
    win.protocol('WM_DELETE_WINDOW',win.destroy);win.grab_set();win.wait_window()
    return result


def choose_one(parent,options,title='Dublar parte do áudio original'):
    """Choose a single source to copy into the crop editor, including simple view."""
    win=tk.Toplevel(parent);win.title(title);win.configure(bg='#202B3B')
    win.transient(parent);win.resizable(False,False)
    tk.Label(win,text='Qual áudio deseja recortar e dublar?',bg='#202B3B',fg='white',font=('Segoe UI',11,'bold')).pack(anchor='w',padx=16,pady=12)
    tk.Label(win,text='A edição será feita em uma cópia. As faixas de origem serão preservadas.',bg='#202B3B',fg='white').pack(anchor='w',padx=16,pady=(0,8))
    selected=tk.StringVar(win,value='original');result=None
    for key in ('original','instrumental','vocals','suppression'):
        available=key in options and Path(options[key]).is_file()
        tk.Radiobutton(win,text=LABELS[key]+('' if available else ' — processe este efeito primeiro'),variable=selected,value=key,state='normal' if available else 'disabled',bg='#202B3B',fg='white',selectcolor='#374151',activebackground='#202B3B',activeforeground='white').pack(anchor='w',padx=16,pady=5)
    def accept():
        nonlocal result
        key=selected.get();path=options.get(key)
        if path is None or not Path(path).is_file():
            messagebox.showwarning(title,'A faixa escolhida não está disponível.',parent=win);return
        result=(key,Path(path));win.destroy()
    row=tk.Frame(win,bg='#202B3B');row.pack(fill='x',padx=16,pady=14)
    tk.Button(row,text='ABRIR RECORTE DESTA FAIXA',command=accept,bg='#4ADE80',padx=12,pady=7).pack(side='left')
    tk.Button(row,text='CANCELAR',command=win.destroy,padx=12,pady=7).pack(side='right',padx=8)
    win.protocol('WM_DELETE_WINDOW',win.destroy);win.grab_set();win.wait_window()
    return result
