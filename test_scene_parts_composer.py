from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import tkinter as tk
from tkinter import filedialog,messagebox
import scene_parts

class Widget:
 all=[]
 def __init__(self,parent=None,**kw):self.kw=kw;self.value=kw.get('value','');self.exists=True;self.grid_args={};self.weights={};Widget.all.append(self)
 def configure(self,**kw):self.kw.update(kw)
 def cget(self,key):return self.kw.get(key,'')
 def grid(self,**kw):self.grid_args=kw
 def pack(self,**kw):raise AssertionError('Composer must reserve footer space with grid')
 def grid_rowconfigure(self,index,**kw):self.weights[index]=kw
 def grid_columnconfigure(self,*a,**kw):pass
 def title(self,*a):pass
 def geometry(self,value):self.size=value
 def minsize(self,*a):pass
 def bind(self,*a):pass
 def protocol(self,*a):pass
 def get(self,*a):return self.value
 def set(self,value):self.value=value
 def insert(self,index,text):self.value=text
 def delete(self,*a):self.value=''
 def yview(self,*a):pass
 def focus_set(self):pass
 def winfo_exists(self):return self.exists
 def destroy(self):self.exists=False
class ImmediateThread:
 def __init__(self,target,**kw):self.target=target
 def start(self):self.target()

def button(label):return next(w for w in reversed(Widget.all) if w.kw.get('text')==label)
def editor():return next(w for w in reversed(Widget.all) if w.kw.get('undo') is True)

with TemporaryDirectory() as directory:
 root=Path(directory);ref=root/'ref.wav';ref.write_bytes(b'reference');other=root/'other.wav';other.write_bytes(b'other')
 original=root/'principal.txt';original.write_text('Texto completo original.',encoding='utf-8')
 queue=[];calls=[];opened=[]
 player=SimpleNamespace(theme={},window=None,scene_text_box=SimpleNamespace(get=lambda *args:original.read_text(encoding='utf-8')),parent=SimpleNamespace(after=lambda delay,callback:queue.append(callback)))
 ui=scene_parts.ScenePartsUI(player)
 context={'root':root,'source':'dublado','scene':'cena','reference':ref,'config':{}}
 ui.context=lambda:dict(context);ui.refresh=lambda **kw:None;ui.open_part=lambda part,ctx:opened.append(part)
 def generate(ctx,text,reference,cancel):calls.append((text,reference));return {'number':len(calls)}
 with patch.multiple(tk,Toplevel=Widget,Frame=Widget,Label=Widget,Text=Widget,Scrollbar=Widget,StringVar=Widget,Button=Widget),patch.object(scene_parts.threading,'Thread',ImmediateThread),patch.object(scene_parts,'generate_part',generate),patch.object(filedialog,'askopenfilename',return_value=str(other)),patch.object(messagebox,'showerror',side_effect=AssertionError):
  ui.composer()
  assert all(button(label).grid_args['row']==0 for label in ('SALVAR ALTERAÇÃO','REDUBLAR','REDUBLAR COM OUTRO ÁUDIO'))
  editor().value='Somente uma parte.'
  button('SALVAR ALTERAÇÃO').kw['command']()
  draft=scene_parts.scene_parts_dir(root,'dublado','cena')/'rascunho.txt'
  assert draft.read_text(encoding='utf-8').strip()=='Somente uma parte.'
  assert original.read_text(encoding='utf-8')=='Texto completo original.'
  ui.composer();assert editor().value.strip()=='Somente uma parte.'
  button('REDUBLAR').kw['command']();queue.pop(0)()
  assert calls[-1]==('Somente uma parte.',ref) and opened[-1]['number']==1
  ui.composer();button('CARREGAR TXT PRINCIPAL').kw['command']()
  assert editor().value=='Texto completo original.'
  editor().value='Segunda parte.'
  button('REDUBLAR COM OUTRO ÁUDIO').kw['command']();queue.pop(0)()
  assert calls[-1]==('Segunda parte.',other) and opened[-1]['number']==2
print('OK: reserved footer layout, three button callbacks, draft save/reopen, main TXT preserved, restore main text, both generation references. Widget layer mocked.')
