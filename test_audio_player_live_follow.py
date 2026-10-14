from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import wave

from audio_player import AudioPlayerManager


def make_audio(path, seconds=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
        stream.writeframes(b'\x01\x10' * (8000 * seconds))


class LiveFollowTests(unittest.TestCase):
    def test_recovery_round_trip_refreshes_wave_and_keeps_buttons_visible(self):
        from audio_versions import archive
        target=self.project/'dublado'/(self.keys[0]+'.wav')
        make_audio(target,1);archive(target,self.project);make_audio(target,2)
        self.manager.set_scene_integration(review_actions={name:lambda *_:None for name in ('open_audacity','approve','reject','redub','redub_personalized','redub_other')})
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update()
        self.manager.audio_restore_previous_button.invoke();self.root.update()
        self.assertEqual(self.manager.waveform_data['dubbed']['duration'],1)
        self.manager.audio_restore_latest_button.invoke();self.root.update()
        self.assertEqual(self.manager.waveform_data['dubbed']['duration'],2)
        for width in (1300,900):
            self.manager.window.geometry(f'{width}x900')
            self.root.update()
            for name in ('audio_restore_previous_button','audio_restore_latest_button','audio_exact_duration_button','project_trash_button'):
                button=getattr(self.manager,name)
                self.assertTrue(button.winfo_ismapped(),str((width,button.master.master.pack_info(),button.master.master.winfo_width())))
                if name.startswith('audio_restore'):self.assertEqual(button.master.cget('bg'),'#DC2626')
                self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),self.manager.window.winfo_rootx()+self.manager.window.winfo_width())
            for button,role in self.manager.review_action_buttons:
                self.assertGreaterEqual(button.winfo_height(),button.winfo_reqheight())
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),self.manager.window.winfo_rootx()+self.manager.window.winfo_width())

    def test_trash_confirmation_cancel_and_disabled_confirmation(self):
        from unittest.mock import patch
        target=self.project/'dublado'/(self.keys[0]+'.wav');make_audio(target)
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update()
        self.assertEqual(self.manager.trash_confirm_var.get(),'1')
        with patch('audio_player.messagebox.askyesno',return_value=False) as confirm:
            self.manager._trash_current_scene()
            confirm.assert_called_once()
        self.assertTrue(target.is_file());self.assertTrue(self.originals[0].is_file())
        self.manager.trash_confirm_var.set('0');self.manager._save_trash_preference()
        with patch('audio_player.messagebox.askyesno') as confirm:
            self.manager._trash_current_scene()
            confirm.assert_not_called()
        self.assertFalse(target.exists());self.assertFalse(self.originals[0].exists())
        self.assertTrue(self.originals[1].is_file())
        self.assertTrue((self.project/'lixeira do projeto/dublado'/(self.keys[0]+'.wav')).is_file())

    def test_all_scene_preferences_use_two_rows(self):
        names=('auto_open_var','request_r_var','request_character_var','request_translation_var',
               'align_original_var','translate_missing_var','preserve_original_voice_var')
        variables={name:tk.StringVar(self.root,value='0') for name in names}
        self.manager.set_review_preferences(variables)
        self.manager.set_scene_integration(review_actions={'redub':lambda *_:None})
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update()
        widgets=self.manager.review_preference_widgets
        self.assertEqual(len(widgets),7)
        self.assertEqual({int(widget.grid_info()['row']) for widget in widgets},{0,1})
        for widget in widgets:
            self.assertLessEqual(widget.winfo_x()+widget.winfo_width(),widget.master.winfo_width()+2)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.root = tk.Tk(); self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.manager = AudioPlayerManager(self.root, self.project)
        self.addCleanup(self.manager.close_window)
        self.keys = ['chapter/first', 'chapter/second']
        self.originals = [self.project/'WAV ORIGINAIS'/(key+'.wav') for key in self.keys]
        for path in self.originals: make_audio(path)

    def test_revisit_discovers_newly_generated_normal_and_custom_audio(self):
        for folder in ('dublado', 'dublados personalizados'):
            self.manager.set_dubbed_folder_name(folder)
            self.manager.play_one(self.originals[0], playlist=self.originals, index=0,
                                  scene_key=self.keys[0], scene_keys=self.keys)
            self.manager.navigate(1)
            self.assertEqual(self.manager.dubbed_pending_paths, [])
            self.manager.navigate(-1)
            dubbed = self.project/folder/(self.keys[1]+'.wav')
            make_audio(dubbed, 2)
            self.manager.navigate(1)
            self.assertEqual(self.manager.dubbed_pending_paths, [dubbed.resolve()])
            self.assertEqual(self.manager.waveform_data['dubbed']['duration'], 2)
            self.assertEqual(self.manager.start_button.cget('state'), 'normal')
            self.manager.close_window()

    def test_list_selection_follows_same_window_without_callback_loop(self):
        self.manager.play_one(self.originals[0], playlist=self.originals, index=0,
                              scene_key=self.keys[0], scene_keys=self.keys)
        window = self.manager.window
        notifications = []
        def callback(key, index):
            notifications.append(key)
            self.manager.follow_scene_selection(key, self.originals, self.keys)
        self.manager.set_scene_integration(callback)
        self.manager.follow_scene_selection(self.keys[1], self.originals, self.keys)
        self.assertIs(self.manager.window, window)
        self.assertEqual(self.manager.current_context_key, self.keys[1])
        self.assertEqual(self.manager.original_pending_paths, [self.originals[1].resolve()])
        self.assertEqual(notifications, [self.keys[1]])

    def test_selection_does_not_open_closed_window(self):
        self.manager.follow_scene_selection(self.keys[1], self.originals, self.keys)
        self.assertIsNone(self.manager.window)

    def test_duration_controls_inside_opening_window(self):
        self.manager.play_one(self.originals[0], playlist=self.originals, index=0,
                              scene_key=self.keys[0], scene_keys=self.keys)
        self.root.update()
        window = self.manager.window
        self.assertGreaterEqual(window.winfo_height(), min(760, window.winfo_screenheight()-100))
        for name in ('audio_duration_minus_button', 'audio_duration_plus_button', 'audio_internal_silence_button'):
            button = getattr(self.manager, name)
            self.assertGreater(button.winfo_width(), 1)
            self.assertGreaterEqual(button.winfo_rootx(), window.winfo_rootx())
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(), window.winfo_rootx()+window.winfo_width())

    def test_requirements_footer_visible_on_open(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import dependency_setup
        self.root.deiconify()
        app = SimpleNamespace(root=self.root, current_theme=lambda: dict(root='#202838', text='#FFFFFF'),
                              should_show_dependency_assistant=lambda: True, ensure_control_contrast=lambda window: None)
        with patch.object(dependency_setup, 'detect_processing', return_value={'variant':'cpu','cpu':'test','gpu':'test'}):
            dependency_setup.show_assistant(app)
            self.addCleanup(app.dependency_window.destroy)
            self.root.update()
        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)
        buttons = [widget for widget in children(app.dependency_window) if widget.winfo_class()=='TButton' and widget.cget('text') in ('CONTINUAR','1. INSTALAR / REPARAR')]
        self.assertEqual(len(buttons), 2)
        for button in buttons:
            self.assertGreater(button.winfo_height(), 1)
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), app.dependency_window.winfo_rooty()+app.dependency_window.winfo_height())


if __name__ == '__main__':
    unittest.main()
