import time,tempfile,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import batch_tab,review_tab,personalized_dubbing_tab as custom
from audio_player import AudioPlayerManager
class Var:
 def __init__(self,value=''):self.value=value
 def get(self):return self.value
 def set(self,v):self.value=v
class List:
 def __init__(self):self.rows=[];self.selected=set();self.mutations=0
 def delete(self,index,end=None):
  self.mutations+=1
  if end is not None:self.rows=[];self.selected=set()
  else:self.rows.pop(index)
 def insert(self,index,*values):
  self.mutations+=1
  if index=='end':self.rows.extend(values)
  else:self.rows[index:index]=values
 def itemconfig(self,*a,**kw):self.mutations+=1
 def selection_set(self,index,end=None):self.selected=set(range(len(self.rows))) if end else {index}
 def curselection(self):return tuple(sorted(self.selected))
 def see(self,index):pass
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);a=root/'WAV ORIGINAIS';t=root/'TXT TEXTO PORTUGUES';a.mkdir();t.mkdir()
 for i in range(5000):
  (a/f'cena{i:05}.wav').write_bytes(b'RIFF');(t/f'cena{i:05}.txt').write_text('texto')
 start=time.perf_counter();audio=batch_tab.find_audio_by_stem(a);texts=batch_tab.find_text_by_stem(t);elapsed=time.perf_counter()-start
 assert len(audio)==len(texts)==5000
 print(f'5000 pares: indice em {elapsed:.3f}s (disco de teste local).')
 r=review_tab.ReviewApp.__new__(review_tab.ReviewApp);r.stems=sorted(audio);r.default_stems=r.stems;r.current_index=15;r.state={};r.theme={};r.audio_by_stem=audio;r.audio_source_mode='normal';r.scene_count_var=Var();r.audio_source_var=Var('Dublados');r.scene_list=List()
 r.refresh_scene_list();r.scene_list.mutations=0;r.refresh_scene_list();assert r.scene_list.mutations==0
 r.state[r.stems[15]]={'status':'aprovada'};r.refresh_scene_list();assert r.scene_list.mutations==3
 c=custom.PersonalizedDubbingApp.__new__(custom.PersonalizedDubbingApp);c.stems=sorted(audio);c.scene_list=List();c.status_var=Var();c.populate_scenes();c.scene_list.selection_set(15);c.scene_list.mutations=0;c.populate_scenes();assert c.scene_list.mutations==0 and c.scene_list.curselection()==(15,)
 custom.configure_project_root(root);c.running=False;c.scene_review=None;jobs=[];c.root=SimpleNamespace(winfo_exists=lambda:True,after=lambda ms,fn:jobs.append(fn))
 release=threading.Event();entered=threading.Event()
 def scan(directory):
  if Path(directory).name=="dublados personalizados":return {}
  entered.set();release.wait(5);return audio
 with patch.object(batch_tab,'find_audio_by_stem',scan),patch.object(batch_tab,'find_text_by_stem',return_value=texts):
  c.reload_scenes();assert c._scan_running and entered.wait(1)
  assert c.scene_list.mutations==0
  c.reload_scenes();assert len(jobs)==1
  release.set();deadline=time.monotonic()+5
  while jobs:
   assert time.monotonic()<deadline;time.sleep(.005);jobs.pop(0)()
 assert c.scene_list.mutations==0 and c.scene_list.curselection()==(15,)
 m=AudioPlayerManager(None,root);m.stop=lambda **kw:None;m.show_window=lambda *a:None
 calls=[];resolve=Path.resolve
 def count(path,*args,**kwargs):calls.append(path);return resolve(path,*args,**kwargs)
 with patch.object(Path,'resolve',count):m.play_one(audio['cena00015'],playlist=list(audio.values()),index=15)
 assert len(calls)<25,len(calls)
 assert len(m.navigation_paths)==5000 and m._resolved_pair_indices=={15}
 print(f'Playlist 5000: {len(calls)} resolucoes de caminho; apenas cena atual resolvida.')
print('OK: unchanged lists not rebuilt; single status updates one row; asynchronous scan returns while worker waits; selection survives; overlapping scans prevented.')

# Tool discovery never recursively scans the project audio tree.
import duration_converter_tab as duration
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);tools=root/'tools'/'ffmpeg'/'bin';tools.mkdir(parents=True);exe=tools/'ffmpeg.exe';exe.write_bytes(b'tool')
 visited=[];rglob=Path.rglob
 def guarded(path,pattern):
  visited.append(path)
  assert path.name.lower() in {'tools','sox',duration.TOOLS_DIR_NAME.lower()},path
  return rglob(path,pattern)
 with patch.object(duration.shutil,'which',return_value=None),patch.object(Path,'rglob',guarded):
  assert duration.executable_path('ffmpeg',root)==str(exe)
 print('OK: nested portable tools still found without recursive project traversal.')
