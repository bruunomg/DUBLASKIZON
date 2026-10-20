"""Shared text view for the transcription tab's scene player."""
import tkinter as tk
from tkinter import ttk

class SceneTexts:
    def __init__(self,app,parent):
        self.app=app;self.path=None;self.updating=False;self.texts={}
        self.frame=ttk.Frame(parent);self.frame.pack(fill='both',expand=True,padx=8,pady=5)
        ttk.Label(self.frame,text='TEXTOS — EDITÁVEIS',font=('Segoe UI',9,'bold')).pack(anchor='w')
        self.caption=tk.StringVar(parent,value='');ttk.Label(self.frame,textvariable=self.caption).pack(anchor='w')
        self.notebook=ttk.Notebook(self.frame);self.notebook.pack(fill='both',expand=True)
        for key,label in [('source','TRANSCRIÇÃO'),('translation','TRADUÇÃO'),('revision','REVISÃO')]:
            page=ttk.Frame(self.notebook);self.notebook.add(page,text=label)
            app.button(page,'SALVAR EDIÇÃO',lambda name=key:app.save_scene_editor(name),'primary').pack(side='bottom',anchor='e')
            box=tk.Text(page,wrap='word',height=3,undo=True,bg=app.theme.get('input','#172231'),fg=app.theme.get('input_text',app.theme.get('text','#F8FAFC')),insertbackground=app.theme.get('text','#F8FAFC'))
            bar=ttk.Scrollbar(page,command=box.yview);box.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');box.pack(fill='both',expand=True)
            self.texts[key]=box;box.edit_modified(False);box.bind('<<Modified>>',lambda event,name=key:self.changed(name))
    def exists(self):
        try:return bool(self.frame.winfo_exists())
        except tk.TclError:return False
    def changed(self,name):
        box=self.texts[name]
        if not box.edit_modified():return
        box.edit_modified(False)
        if self.updating or self.path is None or self.app.running:return
        self.app.scene_editor_changed(self.path,name,box.get('1.0','end-1c'))
    def show(self,path,values):
        if not self.exists():return
        self.updating=True;self.path=path;self.caption.set(path.name if path else 'Nenhum áudio selecionado')
        for name,box in self.texts.items():
            value=values.get(name,'');box.configure(state='normal')
            if box.get('1.0','end-1c')!=value:box.delete('1.0','end');box.insert('1.0',value)
            box.edit_modified(False)
            if self.app.running:box.configure(state='disabled')
        self.updating=False
