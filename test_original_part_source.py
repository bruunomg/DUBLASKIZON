import tkinter as tk
import tempfile,wave,unittest
from pathlib import Path
from unittest.mock import patch
from audio_player import AudioPlayerManager
from scene_parts import ScenePartsUI
from scene_audio_choices import sources,choose_one
from audacity_openvino import scene_directory
class OriginalSourceTests(unittest.TestCase):
 def test_all_sources_in_both_modes_are_private_copies(self):
  with tempfile.TemporaryDirectory() as directory:
   root=tk.Tk();root.withdraw();project=Path(directory);original=project/'original.wav'
   def wav(path,value):
    with wave.open(str(path),'wb') as w:
     w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(bytes([value,0])*2400)
   wav(original,1);folder=scene_directory(project,original);folder.mkdir(parents=True)
   for index,kind in enumerate(('instrumental','vocals','suppression'),2):wav(folder/(kind+'.wav'),index)
   options=sources(project,original);before={key:path.read_bytes() for key,path in options.items()}
   player=AudioPlayerManager(root,project);player.window=root;ui=ScenePartsUI(player)
   ui.context=lambda:{'root':project,'source':'dublado','scene':'scene','original':original,'config':{'model':'fake','language':'pt','instruct':''}}
   try:
    for mode in ('simple','advanced'):
     player.editor_mode=mode
     root._dublaskizon_playback_mode='windows' if mode=='simple' else 'ffplay'
     for kind,path in options.items():
      with self.subTest(mode=mode,kind=kind),patch('scene_audio_choices.choose_one',return_value=(kind,path)) as choice:
       ui.composer_original();child=ui.children[-1]
       self.assertEqual(child.part_file.read_bytes(),before[kind]);self.assertNotEqual(child.part_file,path)
       self.assertEqual(child._current_audio_path('original'),path.resolve())
       self.assertEqual(set(choice.call_args.args[1]),set(options))
       child.close_window()
    count=len(ui.children)
    with patch('scene_audio_choices.choose_one',return_value=None):ui.composer_original()
    self.assertEqual(len(ui.children),count)
    for key,path in options.items():self.assertEqual(path.read_bytes(),before[key])
   finally:
    for child in ui.children:child.close_window()
    root.destroy()
 def test_picker_has_four_choices_and_disables_missing(self):
  with tempfile.TemporaryDirectory() as directory:
   root=tk.Tk();root.withdraw();path=Path(directory)/'original.wav';path.write_bytes(b'audio');observed=[]
   def select():
    win=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
    radios=[w for w in win.winfo_children() if w.winfo_class()=='Radiobutton']
    observed.append([str(r.cget('state')) for r in radios])
    frame=next(w for w in win.winfo_children() if w.winfo_class()=='Frame')
    next(w for w in frame.winfo_children() if str(w.cget('text')).startswith('ABRIR')).invoke()
   root.after(100,select)
   self.assertEqual(choose_one(root,{'original':path}),('original',path))
   self.assertEqual(observed,[['normal','disabled','disabled','disabled']]);root.destroy()
if __name__=='__main__':unittest.main()
