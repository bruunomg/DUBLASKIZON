import tkinter as tk
import tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
from audio_player import AudioPlayerManager
class SimpleEditorTests(unittest.TestCase):
 def test_switch_preserves_scene_and_both_views(self):
  root=tk.Tk();root.withdraw()
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);audio=p/'scene.wav'
   with wave.open(str(audio),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0\0'*2400)
   original=audio.read_bytes();player=AudioPlayerManager(root,p)
   try:
    player.pending_paths=[audio];player.dubbed_pending_paths=[audio]
    player.pending_title='TESTE';player.show_window('TESTE','');root.update()
    self.assertIsNotNone(player.audacity_ui)
    player.set_editor_mode('simple');root.update()
    self.assertIsNone(player.audacity_ui)
    self.assertEqual(set(player.waveform_canvases),{'original','dubbed'})
    self.assertEqual(len(player.part_action_buttons),2)
    for button in player.part_action_buttons:
     self.assertTrue(button.winfo_ismapped())
     self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),player.window.winfo_rooty()+player.window.winfo_height())
    self.assertEqual(set(player.editor_mode_buttons),{'simple','advanced'})
    self.assertEqual(player.dubbed_pending_paths,[audio])
    player.audio_edit_mode=True;player.audio_edit_dirty=True
    with patch('audio_player.messagebox.askyesno',return_value=False):player.set_editor_mode('advanced')
    self.assertEqual(player.editor_mode,'simple')
    player.audio_edit_dirty=False;player.set_editor_mode('advanced');root.update()
    self.assertIsNotNone(player.audacity_ui)
    self.assertEqual(audio.read_bytes(),original)
   finally:player.close_window();root.destroy()
if __name__=='__main__':unittest.main()
