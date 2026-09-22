from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,shutil
import personalized_dubbing_tab as custom
import review_tab as review
class Widget:
 all=[];during_wait=None
 def __init__(self,*args,**kw):self.kw=kw;self.value=kw.get('value','');Widget.all.append(self)
 def pack(self,**kw):pass
 def configure(self,**kw):self.kw.update(kw)
 def get(self):return self.value
 def set(self,v):self.value=v
 def title(self,*a):pass
 def geometry(self,*a):pass
 def minsize(self,*a):pass
 def transient(self,*a):pass
 def winfo_toplevel(self):return self
 def bind(self,*a):pass
 def protocol(self,*a):pass
 def grab_set(self):pass
 def focus_set(self):pass
 def destroy(self):pass
 def wait_window(self):Widget.during_wait()
class Preview:
 def __init__(self,*a,**kw):pass
 def stop(self,**kw):heard.append('stop')
 def _start_paths(self,paths,kind):heard.append(paths[0])
def button(label):return next(w for w in reversed(Widget.all) if w.kw.get('text')==label)
with TemporaryDirectory() as tmp:
 root=Path(tmp);model=root/'model.wav';model.write_bytes(b'model');heard=[]
 custom.configure_project_root(root);custom._save_json(custom.CONFIG_FILE,{'models':['model.wav'],'active_model':'model.wav'})
 with patch.multiple(custom.tk,Toplevel=Widget,Label=Widget,Frame=Widget),patch.multiple(custom,Button=Widget,StringVar=Widget,AudioPlayerManager=Preview,apply_button_style=lambda *a:None),patch.object(custom.ttk,'Combobox',Widget):
  def confirm():
   for name in ('+ ADICIONAR MODELO','REMOVER MODELO','▶ OUVIR MODELO','PARAR','CANCELAR','USAR MODELO E CONTINUAR'):assert button(name)
   button('▶ OUVIR MODELO').kw['command']();button('USAR MODELO E CONTINUAR').kw['command']()
  Widget.during_wait=confirm
  assert custom.choose_personalized_voice(Widget(),{},root)==model
  assert model in heard
  Widget.during_wait=lambda:button('CANCELAR').kw['command']()
  assert custom.choose_personalized_voice(Widget(),{},root) is None
 app=review.ReviewApp.__new__(review.ReviewApp);app.busy=False;app.root=Widget();app.request_character_var=Widget(value='1')
 calls=[];app._choose_r_override=lambda parent:'unchanged';app.voice_model_picker=lambda parent:model
 app.regenerate_scene=lambda:calls.append(app.alternate_reference_audio)
 app._redub_with_r_request();assert calls==[model] and app.alternate_reference_audio is None
 app.voice_model_picker=lambda parent:None;app._redub_with_r_request();assert calls==[model] and app.alternate_reference_audio is None
 app.request_character_var.set('0');app._redub_with_r_request();assert calls==[model,None]
 # Real worker destination/manifest logic, fake synthesis only.
 review.configure_project_root(root);custom.configure_project_root(root)
 target=custom.CUSTOM_DIR/'scene.wav';target.parent.mkdir();target.write_bytes(b'old')
 original=root/'original.wav';original.write_bytes(b'original');app.audio_by_stem={'scene':original}
 app.config={'model':'omni','language':'pt','instruct':''};jobs=[];app.root=SimpleNamespace(after=lambda delay,fn:jobs.append(fn))
 def synth(cmd,**kw):
  assert Path(cmd[cmd.index('--ref_audio')+1])==model
  assert Path(cmd[cmd.index('--output')+1]).is_relative_to(root/'revisoes'/'_intermediarios')
  Path(cmd[cmd.index('--output')+1]).write_bytes(b'new');return SimpleNamespace(returncode=0,stdout='')
 with patch.object(review,'find_omnivoice_command',return_value=['omni']),patch.object(review.ReviewApp,'_run_cancellable_generation',staticmethod(synth)),patch.object(custom,'match_original_expression',lambda src,orig,out:shutil.copy2(src,out)):
  app._run_generation('scene','texto',target,target,model)
 assert target.read_bytes()==b'new' and original.read_bytes()==b'original'
 assert json.loads(custom.MANIFEST_FILE.read_text(encoding='utf-8'))['scene']['voice_model']=='model.wav'
 assert len(jobs)==1
print('OK: model dialog controls, audible preview callback, confirm/cancel, optional redub routing, reference passed to synthesis, custom destination and saved identity; UI/synthesis mocked.')
