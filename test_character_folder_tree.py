from unittest.mock import patch
from types import SimpleNamespace
import personalized_dubbing_tab as module
class Widget:
 all=[]
 def __init__(self,*a,**kw):self.kw=kw;self.rows={};self.selected=();self.value=kw.get('value','');Widget.all.append(self)
 def pack(self,**kw):pass
 def configure(self,*a,**kw):pass
 def map(self,*a,**kw):pass
 def title(self,*a):pass
 def geometry(self,*a):pass
 def minsize(self,*a):pass
 def transient(self,*a):pass
 def winfo_toplevel(self):return self
 def yview(self,*a):pass
 def set(self,v,*a):self.value=v
 def insert(self,parent,index,iid,**kw):
  assert iid not in self.rows
  assert not parent or parent in self.rows
  self.rows[iid]=(parent,kw['text'])
 def selection(self):return self.selected
 def bind(self,*a):pass
 def grab_set(self):pass
 def focus_set(self):pass
 def destroy(self):pass
app=module.PersonalizedDubbingApp.__new__(module.PersonalizedDubbingApp)
app.root=Widget();app.theme={};app.running=False;app.scene_review=None
keys=['Alexandria/DARYL/a','CAP02/DARYL/a','CAP03/RICK/b','root/DARYL/c']
app.audio_by_stem=dict.fromkeys(keys);app.text_by_stem=dict.fromkeys(keys);app.scope_names=set();app.scope_folders=set();calls=[];app._apply_scene_scope=lambda **kw:calls.append(kw)
with patch.multiple(module.tk,Toplevel=Widget,Frame=Widget,Label=Widget),patch.multiple(module.ttk,Treeview=Widget,Scrollbar=Widget,Style=Widget),patch.multiple(module,Button=Widget,StringVar=Widget,apply_button_style=lambda *a:None):
 app.add_character_folders()
 tree=next(w for w in Widget.all if w.kw.get('show')=='tree')
 assert tree.rows['folder:Alexandria/DARYL']==('folder:Alexandria','DARYL')
 assert all(label not in ('a','b','c') for parent,label in tree.rows.values())
 tree.selected=('folder:Alexandria/DARYL',)
 button=next(w for w in Widget.all if w.kw.get('text')=='ADICIONAR TODAS COM ESTE NOME');button.kw['command']()
 assert app.scope_names=={'DARYL'} and calls
 button=next(w for w in Widget.all if w.kw.get('text')=='SOMENTE ESTA PASTA');button.kw['command']()
 assert app.scope_folders=={'Alexandria/DARYL'}
print('OK: folders-only tree, nested hierarchy, repeated names, root-name collision, all-name and single-folder confirmation callbacks.')
