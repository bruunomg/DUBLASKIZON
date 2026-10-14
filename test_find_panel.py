from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import tempfile
from find_panel import FindPanel,choose_target,normalized
import personalized_dubbing_tab as custom
class Var:
 def __init__(self,v=''):self.v=v
 def get(self):return self.v
 def set(self,v):self.v=v
class Widget:
 def __init__(self,kind='Listbox',values=(),children=(),mapped=True):self.kind=kind;self.values=list(values);self.children=children;self.mapped=mapped;self.events=[];self.selected=();self.options={};self.row_options={}
 def winfo_class(self):return self.kind
 def winfo_children(self):return self.children
 def winfo_ismapped(self):return self.mapped
 def winfo_exists(self):return True
 def get(self,i,end=None):return tuple(self.values) if end else self.values[i]
 def selection_clear(self,*a):self.selected=()
 def selection_set(self,i):self.selected=(i,)
 def curselection(self):return self.selected
 def activate(self,i):self.active=i
 def see(self,i):self.visible=i
 def event_generate(self,e):self.events.append(e)
 def configure(self,**kw):self.options.update(kw)
 def itemcget(self,i,key):return self.row_options.get(i,{}).get(key,'')
 def itemconfigure(self,i,**kw):self.row_options.setdefault(i,{}).update(kw)
 def focus_set(self):pass
 def nearest(self,y):return y//20
 def bbox(self,i):return (0,i*20,100,20) if i<len(self.values) else None
class Root:
 def __init__(self):self.jobs={};self.serial=0
 def after(self,delay,fn):self.serial+=1;self.jobs[self.serial]=fn;return self.serial
 def after_cancel(self,i):self.jobs.pop(i,None)
 def flush(self):
  while self.jobs:
   i=next(iter(self.jobs));self.jobs.pop(i)()
 def clipboard_clear(self):self.clip=''
 def clipboard_append(self,v):self.clip+=v
root=Root();target=Widget(values=['cena antiga']*1000+['AÇÃO nova.wav','nova ação 2.wav'])
p=FindPanel(root,{});p.window=Widget();p.target=target;p.kind='Listbox';p.query=Var('antiga');p.status=Var()
p.search(0);assert p.searching and len(p.matches)==300
p.query.set('acao nova');p.schedule();root.flush()
assert len(p.matches)==2 and target.selected==(1000,)
p.move(1);assert target.selected==(1001,)
assert target.row_options[1001]['background']=='#2563EB' and target.row_options[1000]['background']==''
assert target.options['exportselection'] is False
p.move(1);assert target.selected==(1000,)
p.move(-1);assert target.selected==(1001,)
assert target.events[-1]=='<<ListboxSelect>>'
p.query.set('inexistente');p.schedule();root.flush();assert not p.matches and 'Nenhum' in p.status.get()
p.query.set('');p.schedule();root.flush();assert not p.searching
hidden=Widget(values=['hidden'],mapped=False);button=Widget('TButton');top=Widget('Tk',children=[hidden,button,target])
assert choose_target(button,top) is target
assert choose_target(hidden,top) is target
assert normalized('DUBLAGEM ÁÇÃO')=='dublagem acao'
class Menu:
 def __init__(self,*a,**k):self.commands={};menus.append(self)
 def add_command(self,**k):self.commands[k['label']]=k['command']
 def add_separator(self):pass
 def tk_popup(self,*a):pass
 def grab_release(self):self.released=True
menus=[]
with tempfile.TemporaryDirectory() as directory:
 custom.configure_project_root(Path(directory));stem='CAP01/cena';original=Path(directory)/'originais/cena.wav';original.parent.mkdir();original.write_bytes(b'original')
 dubbed=custom.CUSTOM_DIR/f'{stem}.wav';dubbed.parent.mkdir(parents=True);dubbed.write_bytes(b'custom')
 app=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp)
 app.scene_list=Widget(values=[stem]);app.stems=[stem];app.audio_by_stem={stem:original};app.root=root;app.theme={};app.status_var=Var();played=[];opened=[]
 app.listen_selected_scene=lambda event:played.append(event.y)
 with patch.object(custom.tk,'Menu',Menu),patch.object(custom,'reveal_in_file_manager',lambda path:opened.append(path) or True):
  assert app.show_scene_context_menu(SimpleNamespace(y=5,x_root=0,y_root=0))=='break'
  commands=menus[-1].commands
  commands['ABRIR LOCAL DO ÁUDIO DUBLADO']();commands['ABRIR LOCAL DO ÁUDIO ORIGINAL']();assert opened==[dubbed,original]
  commands['COPIAR LOCAL DO ÁUDIO DUBLADO']();assert root.clip==str(dubbed.parent)
  commands['COPIAR NOME DO ÁUDIO']();assert root.clip=='cena.wav'
  commands['OUVIR CENA']();assert played==[5]
  assert app.scene_list.selected==(0,) and menus[-1].released
  app.show_scene_context_menu(SimpleNamespace(y=500,x_root=0,y_root=0));assert len(menus)==1
print('find_panel_and_personalized_menu_ok')

# Switching between two visible lists restores old colors and navigates the new list.
other=Widget(values=['nova ação outro.wav','nova ação final.wav'])
p.scopes=[target,other];p.scope=SimpleNamespace(current=lambda:1);p.entry=Widget('Entry')
p.query.set('nova');p.change_scope();root.flush()
assert p.target is other and other.selected==(0,)
p.move(1);assert other.selected==(1,) and other.row_options[1]['background']=='#2563EB'
p.clear_highlight();assert other.row_options[1]['background']==''
# Restore is guarded against a refreshed list assigning the index to another file.
p.apply_match();other.values[1]='replacement.wav';p.clear_highlight()
assert other.row_options[1]['background']=='#2563EB'
print('persistent_selection_scope_switch_and_stale_focus_ok')

class Tree(Widget):
 def __init__(self):super().__init__('Treeview');self.opened=[]
 def get_children(self,parent):return ['a','b'] if not parent else []
 def item(self,item,**kw):
  if kw:self.opened.append(item)
  return {'text':'cena '+item,'values':['audio.wav']}
 def exists(self,item):return item in ('a','b')
 def parent(self,item):return ''
 def focus(self,item):self.active=item
 def cget(self,key):return self.options.get(key,'VoiceClone.Treeview')
class Style:
 def __init__(self,*a):pass
 def map(self,name,option=None,**kw):
  if kw:style_maps[name]=kw;return
  return [('selected','!focus','#AAAAAA'),('disabled','#999999')]
style_maps={};tree=Tree();p.clear_highlight();p.target=tree;p.kind='Treeview';p.query.set('audio');p.schedule()
with patch('find_panel.ttk.Style',Style):
 root.flush();assert tree.selected==('a',)
 p.move(1);assert tree.selected==('b',) and tree.visible=='b'
 p.move(-1);assert tree.selected==('a',)
assert tree.options['style']=='FindSelected.VoiceClone.Treeview'
assert style_maps[tree.options['style']]['background'][0]==('selected','#2563EB')
assert tree.events[-1]=='<<TreeviewSelect>>'
print('tree_selection_without_keyboard_focus_ok')
