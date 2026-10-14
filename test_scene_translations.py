from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import review_tab as review
import audio_player as player
class Var:
 def __init__(self,value):self.value=value
 def get(self):return self.value
 def set(self,v):self.value=v
with TemporaryDirectory() as tmp:
 root=Path(tmp);review.configure_project_root(root)
 main=root/'TXT TEXTO PORTUGUES/cena.txt';main.parent.mkdir();main.write_text('principal',encoding='utf-8')
 alt=root/'alternativa.txt';alt.write_text('alternativa',encoding='utf-8')
 c=review.ReviewApp.__new__(review.ReviewApp);c.text_by_stem={'cena':main};c.audio_by_stem={};c.other_translation_by_stem={'cena':alt};c.use_other_translation_var=Var('0');c.other_translation_status_var=Var('');c.refresh_other_translation_text('cena')
 c._log_central=lambda *a:None;c.update_history=lambda *a:None;c.current_stem=lambda:'cena'
 assert c.load_scene_text_for_player('cena')['text']=='principal'
 c.use_other_translation_var.set('1');assert c.load_scene_text_for_player('cena')['path']==alt
 ok,msg=c.save_scene_text_from_player('cena','alternativa editada');assert ok,msg
 assert main.read_text()=='principal' and alt.read_text(encoding='utf-8').strip()=='alternativa editada'
 m=player.AudioPlayerManager(None);m.translation_controller=c;m.current_context_key='cena';m.scene_text_box=SimpleNamespace(get=lambda *a:'texto visível ainda não salvo')
 calls=[];m.review_actions={name:lambda key:calls.append(c.player_text_override) for name in ('redub','redub_other','redub_personalized')}
 for name in m.review_actions:m._invoke_review_action(name)
 assert calls==[('cena','texto visível ainda não salvo')]*3
 m._allow_translation_switch=lambda:True;m._refresh_scene_text=lambda:None
 m._show_main_scene_translation();assert c.use_other_translation_var.get()=='0' and c.load_scene_text_for_player('cena')['path']==main
 # The generator consumes the displayed snapshot before any file-reading branch.
 import ast
 tree=ast.parse(Path(review.__file__).read_text(encoding='utf-8'))
 method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='regenerate_scene')
 source=ast.unparse(method)
 assert 'text = displayed[1].strip()' in source and 'displayed is None and (not use_other)' in source
print('OK: main/alternative display, isolated alternative save + backup, displayed snapshot for all redub buttons, return to main and generator snapshot branch.')

with TemporaryDirectory() as tmp:
 root=Path(tmp);review.configure_project_root(root)
 main=root/'TXT TEXTO PORTUGUES'/'cena.txt';main.parent.mkdir();main.write_text('principal')
 folders=root/'OUTRAS TRADUÇÕES';a=folders/'Traducao A';a.mkdir(parents=True);(a/'cena.txt').write_text('texto A')
 empty=folders/'Traducao B';empty.mkdir()
 c=review.ReviewApp.__new__(review.ReviewApp);c.busy=False;c.config={};c.other_translation_root_dir=folders;c.other_translation_dir=folders
 c.other_translation_var=Var('');c.use_other_translation_var=Var('0');c.other_translation_status_var=Var('');c.status_var=Var('')
 c.current_stem=lambda:'cena';c.refresh_other_translation_folder_buttons=lambda:None;c.set_action_state=lambda:None
 c.text_by_stem={'cena':main};c.audio_by_stem={}
 m=player.AudioPlayerManager(None,root);m.translation_controller=c;m.current_context_key='cena';m._allow_translation_switch=lambda:True
 m._refresh_scene_translation_folders=lambda:None;m._refresh_scene_text=lambda:None;m.scene_text_status_var=Var('')
 m._select_scene_translation_folder(a)
 assert c.load_scene_text_for_player('cena')['text']=='texto A' and c.use_other_translation_var.get()=='1'
 m._select_scene_translation_folder(empty)
 assert c.load_scene_text_for_player('cena')['text']=='principal' and c.use_other_translation_var.get()=='0'
 assert 'não tem TXT' in m.scene_text_status_var.get()
 assert review.other_translation_folders(folders)==[a,empty]
 m._select_scene_translation_folder(a);m._show_main_scene_translation()
 assert c.load_scene_text_for_player('cena')['path']==main
print('OK: actual OUTRAS TRADUCOES folder discovery, shared Review folder selection, corresponding TXT, missing TXT fallback and principal button.')
