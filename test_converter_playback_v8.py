from pathlib import Path
import tempfile
import ast
from audio_player import AudioPlayerManager
from duration_converter_tab import DurationConverterApp
from format_converter_tab import FormatConverterApp

def player(root):
 p=AudioPlayerManager.__new__(AudioPlayerManager)
 p.theme={"surface":"#FFFFFF","text":"#1F2937","mode":"claro"};p.window=None;p._project_audio_index={}
 p.project_root=root;p.dubbed_folder_name='dublado';p._resolved_pair_indices=set()
 return p
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)
 originals=[];custom=[];normal=[]
 for chapter in ('A','B'):
  for folder,collection in [('WAV ORIGINAIS',originals),('dublados personalizados',custom),('dublado',normal)]:
   path=root/folder/chapter/'same.wav';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(folder.encode());collection.append(path)
 app=DurationConverterApp.__new__(DurationConverterApp)
 app.original_files=originals;app.dubbed_files=custom
 app.original_base_dir=root/'WAV ORIGINAIS';app.dubbed_base_dir=root/'dublados personalizados'
 app.original_by_stem=dict(zip(('A/same','B/same'),originals));app.dubbed_by_stem=dict(zip(('A/same','B/same'),custom))
 app.audio_player=player(root)
 for kind,paths in [('original',originals),('dubbed',custom)]:
  app._prepare_loaded_playback(kind)
  assert app.audio_player.theme["surface"]=="#450F18"
  app.audio_player.navigation_paths=paths
  assert app.audio_player._originals_for_navigation()==originals
  assert app.audio_player._dubbed_for_navigation()==custom
  app.audio_player.original_navigation_paths=[None]*2;app.audio_player.dubbed_navigation_paths=[None]*2
  app.audio_player._resolve_navigation_pair(1)
  assert app.audio_player.dubbed_navigation_paths[1]==custom[1]
 form=FormatConverterApp.__new__(FormatConverterApp)
 form.project_root=root;form.file_source_by_path={};form.audio_player=player(root)
 for files in (custom, originals+custom, normal, originals+normal):
  form.files=files;form._prepare_loaded_playback()
  assert form.audio_player.theme["surface"] == ("#450F18" if any(p in custom for p in files) else "#FFFFFF")
  for path in files:
   if path in originals: continue
   assert form.audio_player._find_dubbed_audio(path)==path
  if files==custom:
   assert form.audio_player._find_original_audio(custom[0]) is None
   assert form.audio_player._find_dubbed_audio(normal[0]) is None
 external=root/'external/same.wav';external.parent.mkdir();external.write_bytes(b'external')
 form.files=[external];form._prepare_loaded_playback()
 assert form.audio_player._find_dubbed_audio(external)==external
for name in ('audio_player.py','duration_converter_tab.py','format_converter_tab.py'):
 ast.parse((Path(__file__).parent/name).read_text(encoding='utf-8'))
print('v8 OK: exact loaded files, same-name normal/custom pairs, nested scenes, both duration panels, all/navigation, external files, reload source')
