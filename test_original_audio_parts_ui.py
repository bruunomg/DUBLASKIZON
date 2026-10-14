import tkinter as tk
import tempfile,wave,unittest
from pathlib import Path
from audio_player import AudioPlayerManager
from scene_parts import ScenePartsUI

class EditorTests(unittest.TestCase):
    def test_editor_saves_only_private_original_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=tk.Tk();root.withdraw()
            project=Path(directory);original=project/'original.wav'
            with wave.open(str(original),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
                wav.writeframes(b'\x01\x01'*24000)
            before=original.read_bytes()
            player=AudioPlayerManager(root,project);player.window=root
            player.scene_text_box=tk.Text(root);player.scene_text_box.insert('1.0','Texto da parte.')
            ui=ScenePartsUI(player)
            ui.context=lambda:{'root':project,'source':'dublado','scene':'cena','original':original,'config':{'model':'fake','language':'pt','instruct':''}}
            try:
                ui.composer_original()
                self.assertEqual(len(ui.children),1)
                child=ui.children[0]
                self.assertTrue(child.audio_edit_mode)
                self.assertIn('PARTE DO RECORTE',child.start_button.cget('text'))
                self.assertIn(child.start_button.cget('background'),('#F59E0B','#D97706'))
                self.assertIsNotNone(child.review_clone_var)
                self.assertIsNotNone(child.review_dub_var)
                action=next(button for button,role in child.review_action_buttons if 'SALVAR E DUBLAR' in button.cget('text'))
                self.assertIn(action.cget('background'),('#F59E0B','#D97706'))
                self.assertNotEqual(child.part_file,original)
                track=child.audio_edit_working['dubbed']
                child._set_edit_frames('dubbed',track,track['frames'][:24000])
                child._save_audio_edit()
                self.assertFalse(child.audio_edit_dirty)
                self.assertEqual(original.read_bytes(),before)
                self.assertNotEqual(child.part_file.read_bytes(),before)
            finally:
                for child in ui.children:child.close_window()
                root.update_idletasks();root.destroy()
