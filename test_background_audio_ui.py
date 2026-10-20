import sys
from pathlib import Path
sys.path.insert(0,str(Path('build_vendor').resolve()))
import unittest
from unittest.mock import patch
from test_audio_player_live_follow import LiveFollowTests,make_audio
from background_audio import BackgroundEditor

class BackgroundUI(unittest.TestCase):
    setUp=LiveFollowTests.setUp
    def test_apply_preserves_original_and_archives_dub(self):
        target=self.project/'dublado'/(self.keys[0]+'.wav');make_audio(target)
        original_before=self.originals[0].read_bytes();dub_before=target.read_bytes()
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update()
        editor=BackgroundEditor(self.manager,-20);self.root.update()
        self.assertEqual(len(editor.canvases),3)
        editor.selection=(100,300);editor.edit('mute');editor.undo_edit();editor.redo_edit()
        with patch('background_audio.messagebox.showerror') as error:
            editor.apply();self.root.update();error.assert_not_called()
        self.assertEqual(self.originals[0].read_bytes(),original_before)
        self.assertNotEqual(target.read_bytes(),dub_before)
        reopened=BackgroundEditor(self.manager,-5);self.root.update()
        self.assertEqual(reopened.dub.raw_data,editor.dub.raw_data)
        self.assertEqual(reopened.gain.get(),-20)
        reopened.close()
        from audio_versions import switch
        switch(target,self.project)
        self.assertEqual(target.read_bytes(),dub_before)
    def test_changed_scene_is_blocked(self):
        target=self.project/'dublado'/(self.keys[0]+'.wav');make_audio(target)
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update();editor=BackgroundEditor(self.manager);self.root.update()
        self.manager.navigate(1)
        with patch('background_audio.messagebox.showerror') as error:
            editor.apply();error.assert_called_once()
        editor.close()

    def test_full_editor_and_visible_play_controls(self):
        target=self.project/'dublado'/(self.keys[0]+'.wav');make_audio(target)
        self.manager.play_one(self.originals[0],playlist=self.originals,index=0,scene_key=self.keys[0],scene_keys=self.keys)
        self.root.update();editor=BackgroundEditor(self.manager);self.root.update()
        editor.window.geometry('900x740');self.root.update()
        import tkinter as tk
        def buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child,tk.Button):yield child
                yield from buttons(child)
        for button in buttons(editor.window):
            self.assertTrue(button.winfo_ismapped(),button.cget('text'))
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),editor.window.winfo_rootx()+editor.window.winfo_width(),button.cget('text'))
        self.assertLessEqual(abs(editor.mix_button.winfo_width()-editor.play_buttons[0].winfo_width()),2)
        self.assertLess(editor.apply_button.winfo_rooty(),editor.canvases[0].winfo_rooty())
        import time
        with patch.object(self.manager,'_start_paths'):
            editor.play_selected('background')
            self.manager.waveform_active_path=Path(editor.temp.name)/'preview.wav'
            self.manager.waveform_active_started_at=time.monotonic()-.2
            time.sleep(.07);self.root.update()
            self.assertTrue(editor.canvases[1].find_withtag('play_cursor'))
            self.assertFalse(editor.canvases[0].find_withtag('play_cursor'))
            self.assertFalse(editor.canvases[2].find_withtag('play_cursor'))
            editor.play_mix()
            self.manager.waveform_active_path=Path(editor.temp.name)/'preview.wav'
            self.manager.waveform_active_started_at=time.monotonic()-.2
            time.sleep(.07);self.root.update()
            for wave in editor.canvases:self.assertTrue(wave.find_withtag('play_cursor'))
        editor.stop_preview()
        with patch('background_audio.messagebox.showerror') as error:
            editor.advanced_edit();self.root.update();error.assert_not_called()
        child=editor.advanced
        self.assertNotEqual(child._current_audio_path('dubbed'),self.originals[0])
        child.window.geometry('1000x850');self.root.update()
        self.assertEqual(set(child.waveform_canvases),{'original','dubbed','dry_dub'})
        self.assertGreater(child.waveform_canvases['dry_dub'].winfo_rooty(),child.waveform_canvases['dubbed'].winfo_rooty())
        controls=editor.advanced_play_buttons+[editor.advanced_mix_button,editor.advanced_stop_button,editor.advanced_apply_button]
        for button in controls:
            self.assertTrue(button.winfo_ismapped(),button.cget('text'))
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),child.window.winfo_rootx()+child.window.winfo_width(),button.cget('text'))
        self.assertGreaterEqual(editor.advanced_mix_button.winfo_height(),sum(b.winfo_height() for b in editor.advanced_play_buttons))
        self.assertLessEqual(abs(editor.advanced_mix_button.winfo_width()-editor.advanced_play_buttons[0].winfo_width()),2)
        # Save synchronizes the other editor without closing the complete editor.
        track=child.audio_edit_working['dubbed']
        child._set_edit_frames('dubbed',track,track['frames'][:len(track['frames'])//2])
        child.audio_save_button.invoke();self.root.update()
        self.assertEqual(len(editor.background),500)
        self.assertEqual(child.waveform_data['dubbed']['duration'],.5)
        # dB affects the display only; repeated redraws never alter the raw audio.
        before=editor.background.raw_data
        def height(canvas,tag):
            coords=canvas.coords(canvas.find_withtag(tag)[10]);return abs(coords[3]-coords[1])
        editor.gain.set(0);self.root.update()
        loud=height(child.waveform_canvases['dubbed'],'waveform')
        editor.gain.set(-20);self.root.update()
        quiet=height(child.waveform_canvases['dubbed'],'waveform')
        self.assertAlmostEqual(loud/quiet,10,places=3)
        self.assertEqual(editor.background.raw_data,before)
        # Exercise the real progress scheduler without launching a player.
        with patch.object(child,'_start_paths'):
            editor.play_advanced(child,'mix')
        child.stop_event.clear()
        child._begin_waveform_progress('dubbed',Path(editor.temp.name)/'advanced_preview.wav',child.playback_id)
        import time
        child.waveform_active_started_at=time.monotonic()-.2
        child._poll_waveform_progress()
        for wave in child.waveform_canvases.values():
            self.assertTrue(wave.find_withtag('background_cursor'))
        child.stop(announce=False)
        accept=child.review_action_buttons[0][0]
        self.assertEqual(accept.cget('text'),'USAR FUNDO EDITADO')
        accept.invoke();self.root.update()
        self.assertIsNone(child.window)
        editor.close()

if __name__=='__main__':
    unittest.main(defaultTest='BackgroundUI')
