import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave
import audacity_openvino as ov

def wav(path,seconds=1):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as stream:
        stream.setparams((1,2,8000,0,'NONE','not compressed'))
        stream.writeframes(b'\x01\x10'*(8000*seconds))

class SafetyTests(unittest.TestCase):
    def test_results_follow_original_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'original.wav';wav(original)
            target=ov.scene_directory(root,original);wav(target/'vocals.wav')
            self.assertEqual(set(ov.outputs(root,original)),{'vocals'})
            wav(original,2)
            self.assertEqual(ov.outputs(root,original),{})
    def test_running_audacity_is_never_opened_or_terminated(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/'original.wav';wav(original)
            with patch.object(ov,'audacity_running',return_value=True),patch.object(ov.subprocess,'Popen') as launch:
                with self.assertRaisesRegex(RuntimeError,'Salve e feche'):
                    ov.process_original(temp,original)
                launch.assert_not_called()
            self.assertFalse(ov._LOCK.locked())
    def test_failure_does_not_publish_partial_results_or_replace_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'original.wav';wav(original)
            digest=hashlib.sha256(original.read_bytes()).digest()
            (root/'Portable Settings').mkdir()
            (root/'Portable Settings/audacity.cfg').write_text('[Directories]\nTempDir=unused\n[GUI]\nShowSplashScreen=0\n')
            folder=ov.scene_directory(root,original);wav(folder/'vocals.wav')
            saved=(folder/'vocals.wav').read_bytes()
            commands=[]
            class FakePipe:
                def __init__(self,*a):pass
                def command(self,command):
                    commands.append(command)
                    if command.startswith('OpenvinoMusic'):raise RuntimeError('efeito falhou')
                def close(self):pass
            with patch.object(ov,'audacity_running',return_value=False),patch.object(ov,'prepare_bridge',return_value=root),patch.object(ov,'configure_session'),patch.object(ov,'wait_engine'),patch.object(ov,'Pipe',FakePipe),patch.object(ov.subprocess,'Popen') as launch:
                launch.return_value.poll.return_value=None
                with self.assertRaisesRegex(RuntimeError,'efeito falhou'):ov.process_original(root,original,True)
                launch.return_value.terminate.assert_called_once()
            self.assertEqual(saved,(folder/'vocals.wav').read_bytes())
            self.assertEqual(digest,hashlib.sha256(original.read_bytes()).digest())
            self.assertFalse(ov._LOCK.locked())
    def test_cancellation_is_bounded(self):
        from types import SimpleNamespace
        pipe=object.__new__(ov.Pipe);pipe.cancel=threading.Event();pipe.cancel.set()
        pipe.process=SimpleNamespace(poll=lambda:None);pipe.deadline=float('inf')
        with self.assertRaisesRegex(RuntimeError,'cancelado'):pipe.check()

class SceneTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from audio_player import AudioPlayerManager
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name);self.original=self.project/'WAV ORIGINAIS/scene.wav';wav(self.original)
        self.root=tk.Tk();self.root.withdraw();self.addCleanup(self.root.destroy)
        self.player=AudioPlayerManager(self.root,self.project);self.addCleanup(self.player.close_window)
        self.player.play_one(self.original,scene_key='scene');self.root.update()
        self.ui=self.player.audacity_ui
    def test_new_tracks_visibility_reference_choices_and_original_unchanged(self):
        before=self.original.read_bytes()
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,self.original)/(kind+'.wav'))
        self.player._refresh_waveforms();self.root.update()
        self.assertEqual(set(self.ui.paths),set(ov.KINDS))
        for kind in ov.KINDS:
            self.assertTrue(self.ui.rows[kind].winfo_ismapped())
            self.assertEqual(self.player._current_audio_path(kind),self.ui.paths[kind])
            self.assertEqual(self.player.waveform_data[kind]['duration'],1)
        self.ui.visible['vocals'].set(False);self.ui.reflow();self.root.update()
        self.assertFalse(self.ui.rows['vocals'].winfo_ismapped())
        self.assertTrue(self.ui.rows['suppression'].winfo_ismapped())
        self.ui.all_visible.set(False);self.ui.reflow();self.root.update()
        self.assertTrue(all(not row.winfo_ismapped() for row in self.ui.rows.values()))
        self.assertEqual(before,self.original.read_bytes())
    def test_choose_vocals_and_cancel(self):
        import tkinter as tk
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,self.original)/(kind+'.wav'))
        def choose(label):
            def visit(widget):
                for child in widget.winfo_children():
                    if isinstance(child,tk.Button) and child.cget('text')==label:child.invoke();return True
                    if visit(child):return True
                return False
            visit(self.player.window)
        self.root.after(50,lambda:choose('DUBLAR COM\n'+ov.LABELS['vocals']))
        confirmed,path=self.ui.choose_reference(self.original)
        self.assertTrue(confirmed);self.assertEqual(path.name,'vocals.wav')
        self.root.after(50,lambda:choose('Não'))
        confirmed,path=self.ui.choose_reference(self.original)
        self.assertFalse(confirmed);self.assertEqual(path,self.original)
    def test_close_cancels_treatment(self):
        self.player.close_window();self.assertTrue(self.ui.cancel.is_set())

    def test_buttons_confirm_only_when_enabled_and_do_not_process_on_refresh(self):
        import tkinter as tk
        self.assertTrue(all(isinstance(b,tk.Button) for b in self.ui.effect_buttons))
        with patch('audacity_scene_ui.messagebox.askyesno',return_value=False) as ask,patch.object(self.ui,'start') as start:
            self.ui.effect_buttons[0].invoke();ask.assert_called_once();start.assert_not_called()
        self.ui.confirm_effect.set(False)
        with patch('audacity_scene_ui.messagebox.askyesno') as ask,patch.object(self.ui,'start') as start:
            self.ui.effect_buttons[1].invoke();ask.assert_not_called();start.assert_called_once_with(True)
            self.ui.refresh();self.root.update();start.assert_called_once()

    def test_processed_tracks_are_after_dubbed_wave_and_scrollbar(self):
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,self.original)/(kind+'.wav'))
        self.player._refresh_waveforms();self.root.update()
        self.assertGreater(self.ui.container.winfo_y(),self.player.waveform_scrollbar.winfo_y())
        self.assertGreater(self.player.waveform_scrollbar.winfo_y(),self.player.waveform_canvases['dubbed'].master.winfo_y())
