"""Busca incremental não modal nos controles visíveis da janela atual."""
import unicodedata
import tkinter as tk
from tkinter import ttk

SEARCHABLE={'Listbox','Treeview','Tree','Text','ScrolledText','Entry','TEntry','Combobox','TCombobox'}

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold()) if not unicodedata.combining(c))

def visible_targets(top):
    candidates=[]
    def visit(widget):
        for child in widget.winfo_children():
            if child.winfo_class()=='Toplevel':continue
            if child.winfo_ismapped():
                if child.winfo_class() in SEARCHABLE:candidates.append(child)
                visit(child)
    visit(top)
    return candidates

def choose_target(focused,top):
    candidates=visible_targets(top)
    if focused in candidates:return focused
    for group in ({'Listbox','Treeview','Tree'},{'Text','ScrolledText'},{'Entry','TEntry','Combobox','TCombobox'}):
        for widget in candidates:
            if widget.winfo_class() in group:return widget
    return None

def target_label(widget,index):
    parent=widget.master
    while parent is not None:
        try:
            title=str(parent.cget('text')).strip()
            if title:return f'{index+1}. {title}'
        except tk.TclError:pass
        parent=getattr(parent,'master',None)
    return f'{index+1}. Lista de arquivos'


class FindPanel:
    def __init__(self,root,theme):
        self.root=root;self.theme=theme;self.window=None;self.target=None
        self.matches=[];self.position=-1;self.token=0;self.pending=None;self.searching=False
        self.highlight=None

    def show(self,focused):
        if self.window is not None and self.window.winfo_exists() and focused.winfo_toplevel() is self.window:
            self.entry.focus_set();self.entry.selection_range(0,'end');return
        top=focused.winfo_toplevel()
        target=choose_target(focused,top)
        if target is None:
            from tkinter import messagebox
            messagebox.showinfo('Localizar','Clique numa lista de áudios ou num campo de texto e use Ctrl+F.',parent=top)
            return
        previous=self.query.get() if self.window is not None and self.window.winfo_exists() else ''
        self.close()
        self.target=target;self.kind=target.winfo_class()
        self.window=tk.Toplevel(top);self.window.title('LOCALIZAR — lista ou texto atual');self.window.transient(top)
        self.window.resizable(True,False);self.window.geometry('560x190');self.window.minsize(420,190)
        surface=self.theme.get('surface','#FFFFFF');fg=self.theme.get('text','#111827');self.window.configure(bg=surface)
        self.scopes=[w for w in visible_targets(top) if w.winfo_class() in {'Listbox','Treeview','Tree'}]
        if target not in self.scopes:self.scopes.insert(0,target)
        labels=[target_label(w,i) for i,w in enumerate(self.scopes)]
        self.scope=ttk.Combobox(self.window,state='readonly',values=labels)
        self.scope.pack(fill='x',padx=12,pady=(8,0));self.scope.current(self.scopes.index(target))
        self.scope.bind('<<ComboboxSelected>>',self.change_scope)
        self.query=tk.StringVar(value=previous)
        self.entry=tk.Entry(self.window,textvariable=self.query,font=('Segoe UI',11),bg=self.theme.get('input',surface),fg=self.theme.get('input_text',fg),insertbackground=fg)
        self.entry.pack(fill='x',padx=12,pady=(12,6))
        row=tk.Frame(self.window,bg=surface);row.pack(fill='x',padx=12)
        for label,command in [('ANTERIOR',lambda:self.move(-1)),('PRÓXIMO',lambda:self.move(1)),('FECHAR',self.close)]:
            ttk.Button(row,text=label,command=command).pack(side='left',padx=(0,6))
        self.status=tk.StringVar(value='Digite para buscar. Enter/F3: próximo; Shift+Enter/F3: anterior.')
        tk.Label(self.window,textvariable=self.status,bg=surface,fg=fg,anchor='w',wraplength=490).pack(fill='x',padx=12,pady=7)
        self.query.trace_add('write',lambda *_:self.schedule())
        self.entry.bind('<Return>',lambda _e:self.move(1))
        self.entry.bind('<Shift-Return>',lambda _e:self.move(-1))
        self.window.bind('<F3>',lambda _e:self.move(1))
        self.window.bind('<Shift-F3>',lambda _e:self.move(-1))
        self.window.bind('<Escape>',lambda _e:self.close())
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.entry.focus_set();self.entry.selection_range(0,'end')
        if previous:self.schedule()

    def change_scope(self,_event=None):
        self.clear_highlight()
        if self.kind in {'Text','ScrolledText'}:
            try:self.target.tag_remove('ctrl_f_match','1.0','end')
            except tk.TclError:pass
        self.target=self.scopes[self.scope.current()];self.kind=self.target.winfo_class()
        self.schedule()
        self.entry.focus_set()

    def clear_highlight(self):
        mark=self.highlight
        self.highlight=None
        if mark is None:return
        widget,identity,value,options=mark
        try:
            # Do not restore row colors onto a different file after a list refresh.
            if widget.winfo_exists() and widget.get(identity)==value:widget.itemconfigure(identity,**options)
        except (tk.TclError,IndexError):pass

    def highlight_selection(self,identity,value):
        # Native Windows controls can hide selection while the search owns focus.
        # A row background also keeps the current result visible in that state.
        if self.kind=='Listbox':
            self.target.configure(exportselection=False)
            options={key:self.target.itemcget(identity,key) for key in ('background','foreground','selectbackground','selectforeground')}
            self.highlight=(self.target,identity,value,options)
            self.target.itemconfigure(identity,background='#2563EB',foreground='#FFFFFF',selectbackground='#2563EB',selectforeground='#FFFFFF')
        elif self.kind in {'Treeview','Tree'}:
            style=ttk.Style(self.target)
            base=self.target.cget('style') or 'Treeview'
            name=base if base.startswith('FindSelected.') else 'FindSelected.'+base
            style.map(name,background=[('selected','#2563EB')]+[states for states in style.map(base,'background') if 'selected' not in states[:-1]],
                      foreground=[('selected','#FFFFFF')]+[states for states in style.map(base,'foreground') if 'selected' not in states[:-1]])
            self.target.configure(style=name)

    def close(self):
        self.clear_highlight()
        self.token+=1
        if self.pending is not None:
            try:self.root.after_cancel(self.pending)
            except tk.TclError:pass
            self.pending=None
        if self.target is not None and self.target.winfo_exists() and self.target.winfo_class() in {'Text','ScrolledText'}:
            self.target.tag_remove('ctrl_f_match','1.0','end')
        if self.window is not None and self.window.winfo_exists():self.window.destroy()
        self.window=None
        return 'break'

    def schedule(self):
        self.clear_highlight()
        self.token+=1;token=self.token
        if self.pending is not None:
            try:self.root.after_cancel(self.pending)
            except tk.TclError:pass
        self.matches=[];self.position=-1;self.searching=False
        self.pending=self.root.after(120,lambda:self.search(token))

    def search(self,token):
        if token!=self.token or self.window is None or not self.window.winfo_exists():return
        self.pending=None
        if not self.target.winfo_exists():self.status.set('A lista ou janela foi fechada. Abra Ctrl+F novamente.');return
        query=self.query.get().strip()
        self.matches=[];self.position=-1
        if self.kind in {'Text','ScrolledText'}:self.target.tag_remove('ctrl_f_match','1.0','end')
        if not query:self.status.set('Digite para localizar.');return
        self.searching=True
        self.status.set('Buscando…')
        terms=normalized(query).split()
        def items():
            if self.kind=='Listbox':
                for index,value in enumerate(self.target.get(0,'end')):yield index,str(value)
            elif self.kind in {'Treeview','Tree'}:
                stack=list(reversed(self.target.get_children('')))
                while stack:
                    item=stack.pop();data=self.target.item(item)
                    yield item,str(data.get('text',''))+' '+' '.join(map(str,data.get('values',())))
                    stack.extend(reversed(self.target.get_children(item)))
            elif self.kind in {'Text','ScrolledText'}:
                index='1.0';count=tk.IntVar(master=self.target)
                while True:
                    index=self.target.search(query,index,nocase=True,stopindex='end',count=count)
                    if not index:break
                    end=f'{index}+{max(1,count.get())}c'
                    yield (index,end),None
                    index=end
            else:
                value=self.target.get();start=0
                while True:
                    index=value.lower().find(query.lower(),start)
                    if index<0:break
                    yield (index,index+len(query)),None
                    start=index+max(1,len(query))
        iterator=items()
        def chunk():
            if token!=self.token or self.window is None or not self.window.winfo_exists():return
            self.pending=None
            try:
                for _ in range(300):
                    identity,value=next(iterator)
                    if value is None or all(term in normalized(value) for term in terms):self.matches.append((identity,value))
            except StopIteration:
                self.searching=False
                if self.matches:self.position=0;self.apply_match()
                else:self.status.set('Nenhum resultado nesta lista ou texto.')
                return
            except (tk.TclError,RuntimeError):
                self.searching=False
                self.status.set('A lista mudou. Digite novamente para atualizar a busca.');return
            self.pending=self.root.after(1,chunk)
        chunk()

    def move(self,step):
        if self.searching:return 'break'
        if self.matches:
            self.position=(self.position+step)%len(self.matches);self.apply_match()
        elif self.pending is not None:
            self.root.after_cancel(self.pending);self.pending=None;self.search(self.token)
        return 'break'

    def apply_match(self):
        self.clear_highlight()
        try:
            identity,value=self.matches[self.position]
            if self.kind=='Listbox':
                if self.target.get(identity)!=value:self.schedule();return
                self.target.selection_clear(0,'end');self.target.selection_set(identity);self.target.activate(identity);self.target.see(identity)
                self.target.event_generate('<<ListboxSelect>>')
                if self.target.get(identity)==value:self.highlight_selection(identity,value)
            elif self.kind in {'Treeview','Tree'}:
                if not self.target.exists(identity):self.schedule();return
                ancestor=self.target.parent(identity)
                while ancestor:self.target.item(ancestor,open=True);ancestor=self.target.parent(ancestor)
                self.target.selection_set(identity);self.target.focus(identity);self.target.see(identity)
                self.highlight_selection(identity,value)
                self.target.event_generate('<<TreeviewSelect>>')
            elif self.kind in {'Text','ScrolledText'}:
                start,end=identity
                self.target.tag_remove('ctrl_f_match','1.0','end');self.target.tag_add('ctrl_f_match',start,end)
                self.target.tag_configure('ctrl_f_match',background='#FDE68A',foreground='#111827');self.target.mark_set('insert',end);self.target.see(start)
            else:
                start,end=identity;self.target.selection_range(start,end);self.target.icursor(end)
            self.status.set(f'{self.position+1} de {len(self.matches)} resultados — Enter/F3: próximo')
        except (tk.TclError,IndexError):self.status.set('O conteúdo mudou. Digite novamente para atualizar.')
