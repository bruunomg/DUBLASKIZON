"""Collapsible scene list using the existing Review controller and actions."""
import tkinter as tk
from tkinter import ttk
import threading
from pathlib import Path

class SceneReviewDrawer:
    def __init__(self,player,controller,parent):
        self.player,self.controller=player,controller
        self.expanded=False;self.rows_token=None;self.syncing=False;self.tree_mode=False;self.tree_indices={};self.drawer_width=290
        bg=player.theme.get('surface','#FFFFFF');fg=player.theme.get('text','#111827')
        self.host=tk.Frame(parent,bg=bg);self.host.pack(side='left',fill='both',expand=True)
        self.edge=tk.Frame(self.host,bg=player.theme.get('border','#475569'),width=22)
        self.edge.pack(side='left',fill='y');self.edge.pack_propagate(False)
        self.arrow=tk.Button(self.edge,text='▶',command=self.toggle,relief='flat',bg='#C49A18',font=('Segoe UI',9,'bold'),padx=0,pady=7)
        self.arrow.pack(fill='x',pady=4)
        tk.Label(self.edge,text='R\nE\nV\nI\nS\nÃ\nO',bg=player.theme.get('border','#475569'),fg=fg,font=('Segoe UI',7,'bold')).pack(pady=5)
        self.panes=tk.PanedWindow(self.host,orient='horizontal',sashwidth=7,sashrelief='raised',opaqueresize=True,bg=bg,bd=0)
        self.panes.pack(side='left',fill='both',expand=True)
        self.panel=tk.Frame(self.panes,bg=bg,width=290);self.panel.pack_propagate(False)
        top=tk.Frame(self.panel,bg=bg);top.pack(fill='x',padx=5,pady=5)
        self.source=ttk.Combobox(top,textvariable=controller.audio_source_var,values=('Dublados','Dublados personalizados'),state='readonly')
        self.source.pack(fill='x',pady=(0,4));self.source.bind('<<ComboboxSelected>>',self.change_source)
        self.sort=ttk.Combobox(top,textvariable=controller.scene_sort_var,values=('Padrão','Avaliar primeiro','Aprovadas primeiro','Rejeitadas primeiro','Aprovadas e rejeitadas primeiro'),state='readonly')
        self.sort.pack(fill='x',pady=(0,4));self.sort.bind('<<ComboboxSelected>>',self.change_sort)
        ttk.Button(top,text='ORGANIZAR LISTA SOMENTE OS ÁUDIOS',command=lambda:self.set_mode(False)).pack(fill='x',pady=1)
        ttk.Button(top,text='ORGANIZAR LISTA POR ÁRVORE',command=lambda:self.set_mode(True)).pack(fill='x',pady=(1,4))
        tk.Label(top,textvariable=controller.scene_count_var,wraplength=275,bg=bg,fg=fg,font=('Segoe UI',9,'bold')).pack(fill='x')
        tk.Label(top,text='Organizar DUBLADOS',bg=bg,fg=fg,font=('Segoe UI',8,'bold')).pack(anchor='w')
        listing=tk.Frame(self.panel,bg=bg);listing.pack(fill='both',expand=True,padx=5)
        self.list=tk.Listbox(listing,exportselection=False,selectmode='extended',bg=player.theme.get('input','#FFFFFF'),fg=fg,selectbackground=player.theme.get('select','#2563EB'),font=('Segoe UI',9))
        self.listing=listing
        self.tree=ttk.Treeview(listing,show='tree',selectmode='extended')
        self.tree.column('#0',width=520,minwidth=120,stretch=False)
        self.tree.tag_configure('approved',foreground='#15803D');self.tree.tag_configure('rejected',foreground='#DC2626');self.tree.tag_configure('evaluate',foreground='#B7791F')
        self.vscroll=ttk.Scrollbar(listing,orient='vertical',command=self.scroll)
        self.hscroll=ttk.Scrollbar(listing,orient='horizontal',command=self.scroll_horizontal)
        for widget in (self.list,self.tree):widget.configure(yscrollcommand=self.vscroll.set,xscrollcommand=self.hscroll.set)
        listing.rowconfigure(0,weight=1);listing.columnconfigure(0,weight=1)
        self.vscroll.grid(row=0,column=1,sticky='ns');self.hscroll.grid(row=1,column=0,sticky='ew')
        self.list.grid(row=0,column=0,sticky='nsew')
        self.list.bind('<Button-3>',self.context_menu)
        self.tree.bind('<Button-3>',self.context_menu)
        self.tree.bind('<<TreeviewSelect>>',self.select)
        self.tree.bind('<Double-Button-1>',self.tree_double_click)
        self.list.bind('<<ListboxSelect>>',self.select)
        self.list.bind('<Double-Button-1>',lambda event:self.listen())
        self.list.bind('<MouseWheel>',lambda event:player.parent.after_idle(self.paint_visible),add='+')
        self.selection=tk.StringVar(player.window,value='0 selecionados')
        tk.Label(self.panel,textvariable=self.selection,bg=bg,fg=fg,anchor='w',font=('Segoe UI',8)).pack(fill='x',padx=5)
        tk.Label(self.panel,textvariable=controller.review_totals_var,bg=bg,fg=fg,wraplength=275,font=('Segoe UI',8,'bold')).pack(fill='x',padx=5,pady=4)
        buttons=tk.Frame(self.panel,bg=bg);buttons.pack(fill='x',padx=5,pady=4)
        for label,command in [('▶ OUVIR CENA',self.listen),('▶ OUVIR TODOS',self.listen_all)]:
            tk.Button(buttons,text=label,command=command,bg='#0F766E',fg='white',relief='flat',font=('Segoe UI',8,'bold')).pack(side='left',fill='x',expand=True,padx=1)
        rejected=tk.Frame(self.panel,bg=bg);rejected.pack(fill='x',padx=5,pady=3)
        ttk.Button(rejected,text='REDUBLAR REJEITADOS [REFAZER]',command=controller.redub_all_rejected).pack(side='left',fill='x',expand=True)
        ttk.Button(rejected,text='⚙',width=3,command=controller.configure_rejected_batch).pack(side='right')
        for label,command in [('CORTAR SILÊNCIO INÍCIO/FIM — TODOS',lambda:controller.finish_all_audio(trim=True)),
                              ('VOLUME MÁXIMO SEGURO — TODOS',lambda:controller.finish_all_audio(max_volume=True))]:
            ttk.Button(self.panel,text=label,command=command).pack(fill='x',padx=5,pady=2)
        self.progress=ttk.Progressbar(self.panel,maximum=100);self.progress.pack(fill='x',padx=5,pady=2)
        ttk.Button(self.panel,text='PARAR AJUSTES',command=lambda:getattr(controller,'finishing_cancel',threading.Event()).set()).pack(fill='x',padx=5,pady=(0,5))
        self.main=tk.Frame(self.panes,bg=bg);self.panes.add(self.main,minsize=300,stretch='always')
        self.job=player.parent.after(400,self.poll)
        if getattr(player,'_review_drawer_expanded',False):self.toggle()

    def close(self):
        if self.job:
            try:self.player.parent.after_cancel(self.job)
            except tk.TclError:pass
            self.job=None

    def toggle(self):
        self.expanded=not self.expanded
        self.player._review_drawer_expanded=self.expanded
        if self.expanded:
            self.panes.add(self.panel,before=self.main,minsize=170,width=self.drawer_width,stretch='never');self.arrow.configure(text='◀');self.refresh()
        else:
            self.drawer_width=max(170,self.panel.winfo_width());self.panes.forget(self.panel);self.arrow.configure(text='▶')

    def scroll(self,*args):
        (self.tree if self.tree_mode else self.list).yview(*args);self.paint_visible()

    def scroll_horizontal(self,*args):
        (self.tree if self.tree_mode else self.list).xview(*args)

    def selected_indices(self):
        if not self.tree_mode:return list(self.list.curselection())
        selected=set()
        def collect(item):
            if item in self.tree_indices:selected.add(self.tree_indices[item])
            for child in self.tree.get_children(item):collect(child)
        for item in self.tree.selection():collect(item)
        return sorted(selected)

    def set_mode(self,tree):
        selected=self.selected_indices();self.syncing=True
        try:
            self.tree_mode=tree
            if tree:
                self.list.grid_remove();self.tree.grid(row=0,column=0,sticky='nsew')
                self.tree.selection_set([f'a{i}' for i in selected if self.tree.exists(f'a{i}')])
            else:
                self.tree.grid_remove();self.list.grid(row=0,column=0,sticky='nsew')
                self.list.selection_clear(0,'end')
                for i in selected:self.list.selection_set(i)
        finally:self.syncing=False
        self.refresh()

    def tree_double_click(self,event):
        item=self.tree.identify_row(event.y)
        if item in self.tree_indices:self.listen();return 'break'

    def context_menu(self,event):
        if self.tree_mode:
            item=self.tree.identify_row(event.y)
            index=self.tree_indices.get(item)
            if index is None:return 'break'
            if item not in self.tree.selection():self.tree.selection_set(item)
            self.tree.focus(item)
        else:
            index=self.list.nearest(event.y);bounds=self.list.bbox(index)
            if not bounds or not bounds[1]<=event.y<bounds[1]+bounds[3]:return 'break'
            if index not in self.list.curselection():self.list.selection_clear(0,'end');self.list.selection_set(index)
            self.list.activate(index)
        self.select()
        return self.controller.show_scene_context_menu(event,stem=self.controller.stems[index])

    def rebuild_tree(self,values):
        self.tree.delete(*self.tree.get_children());self.tree_indices={};folders={}
        max_width=520
        for index,key in enumerate(self.controller.stems):
            parts=Path(key).parts;parent=''
            for depth,part in enumerate(parts[:-1]):
                folder=parts[:depth+1]
                if folder not in folders:
                    folders[folder]=self.tree.insert(parent,'end',text=part,open=True)
                parent=folders[folder]
            value=values[index] if index<len(values) else ''
            marker=value[:value.index(']')+1] if value.startswith('[') and ']' in value else ''
            label=f'{marker} {parts[-1]}'
            tag={'[OK]':'approved','[REFAZER]':'rejected','[AVALIAR]':'evaluate'}.get(marker,'')
            item=self.tree.insert(parent,'end',iid=f'a{index}',text=label,tags=(tag,) if tag else ())
            self.tree_indices[item]=index;max_width=max(max_width,30*len(parts)+len(label)*8)
        self.tree.column('#0',width=max_width)

    def paint_visible(self):
        rows=getattr(self.controller,'_scene_rows',None) or []
        if not rows or not self.list.winfo_ismapped():return
        first=self.list.nearest(0);last=self.list.nearest(self.list.winfo_height())
        rgb=self.list.winfo_rgb(self.list.cget('bg'));light=sum(rgb)>3*32767
        colors={'[OK]':'#0057B8' if light else '#60A5FA','[REFAZER]':'#C00000' if light else '#F87171','[AVALIAR]':'#9A6700' if light else '#FBBF24'}
        for index in range(first,min(last+2,len(rows))):
            marker=rows[index][0].split(' ',1)[0]
            self.list.itemconfigure(index,foreground=colors.get(marker,self.list.cget('fg')))

    def refresh(self):
        c=self.controller;p=self.player
        rows=getattr(c,'_scene_rows',None)
        token=id(rows) if rows is not None else (id(c.stems),len(c.stems))
        if token!=self.rows_token:
            self.list.delete(0,'end')
            values=[row[0] for row in rows] if rows is not None else c.scene_list.get(0,'end')
            self.rebuild_tree(values)
            values=[(value[:value.index(']')+1]+' ' if value.startswith('[') and ']' in value else '')+Path(key).name for value,key in zip(values,c.stems)]
            for start in range(0,len(values),1000):self.list.insert('end',*values[start:start+1000])
            self.rows_token=token
        key=p._scene_text_key()
        if key in c.stems:
            index=c.stems.index(key)
            if index not in self.selected_indices():
                if self.tree_mode:
                    self.tree.selection_set(f'a{index}');self.tree.focus(f'a{index}');self.tree.see(f'a{index}')
                else:
                    self.list.selection_clear(0,'end');self.list.selection_set(index);self.list.activate(index);self.list.see(index)
        self.selection.set(f'{len(self.selected_indices())} selecionados')
        try:self.progress['value']=c.finishing_progress['value']
        except (AttributeError,tk.TclError):pass
        self.paint_visible()

    def poll(self):
        self.job=None
        try:
            if self.player.window is None or not self.host.winfo_exists():return
            if self.expanded:self.refresh()
            self.job=self.player.parent.after(400,self.poll)
        except tk.TclError:return

    def follow(self):
        c=self.controller;p=self.player;stem=c.current_stem()
        if stem is not None:
            p.set_dubbed_folder_name('dublados personalizados' if c.audio_source_mode=='custom' else 'dublado')
            p.follow_scene_selection(stem,[c.current_output_dir()/f'{key}.wav' for key in c.stems],c.stems)
        self.refresh()

    def resolve_pair(self,path):
        c=self.controller
        try:
            key=Path(path).resolve().relative_to(c.current_output_dir().resolve()).with_suffix('').as_posix()
        except ValueError:return None
        original=c.audio_by_stem.get(key)
        target=c.current_output_dir()/f'{key}.wav'
        return (original if original and original.is_file() else None,target if target.is_file() else None)

    def change_source(self,_event=None):
        c=self.controller
        if getattr(c,'busy',False) or not self.player._prepare_audio_edit_scene_change():
            c.audio_source_var.set('Dublados personalizados' if c.audio_source_mode=='custom' else 'Dublados');return
        c._on_audio_source_selected();self.follow()

    def change_sort(self,_event=None):
        self.controller._on_scene_sort_selected();self.follow()

    def select(self,_event=None):
        selected=self.selected_indices()
        self.selection.set(f'{len(selected)} selecionados')
        if not selected or self.syncing:return
        if not self.player._prepare_audio_edit_scene_change():return
        c=self.controller
        self.syncing=True
        try:
            c.scene_list.selection_clear(0,'end')
            for index in selected:c.scene_list.selection_set(index)
            active=self.tree_indices.get(self.tree.focus(),-1) if self.tree_mode else self.list.index('active');index=active if active in selected else selected[0]
            c.select_scene(index,preserve_selection=True);self.follow()
        finally:self.syncing=False

    def listen(self):
        self.select();self.player.start_pending()

    def listen_all(self):
        c=self.controller
        pairs=[(key,c.current_scene_playback_path(key)) for key in c.stems]
        pairs=[(key,path) for key,path in pairs if path is not None]
        self.player.play_all([path for key,path in pairs],'OUVIR TODOS — CENAS',scene_keys=[key for key,path in pairs])
