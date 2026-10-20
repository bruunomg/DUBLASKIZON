import unittest
from unittest.mock import patch
from background_audio import combine_sources
from test_background_audio import audio
from test_audacity_openvino import SceneTests, wav, ov
class Mixing(unittest.TestCase):
    def test_simultaneous_tracks(self):
        a=audio(26000,ms=1000);b=audio(26000,ms=500);before=a.raw_data
        mixed=combine_sources([a,b],a)
        self.assertEqual(len(mixed),1000);self.assertEqual(a.raw_data,before)
        self.assertLessEqual(mixed.max,26000)
        self.assertGreater(mixed[:400].rms,mixed[600:].rms)
class Cursor(SceneTests):
    def test_all_button_indicators(self):
        import io,threading
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,self.original)/(kind+'.wav'))
        self.player._refresh_waveforms();self.root.update()
        target=self.project/'dubbed.wav';wav(target);self.player.dubbed_pending_paths=[target];self.player.dubbed_navigation_paths=[target]
        self.player.waveform_data['dubbed']=dict(self.player.waveform_data['original'])
        class Process:
            def __init__(self,*a,**kw):self.done=threading.Event();self.stderr=io.BytesIO()
            def poll(self):return 0 if self.done.is_set() else None
            def wait(self,*a,**kw):self.done.wait(1);return 0
            def terminate(self):self.done.set()
            kill=terminate
        failures=[]
        with patch('audio_player.find_ffplay',return_value='fake'),patch('audio_player.subprocess.Popen',Process):
            for kind in ['original','dubbed',*ov.KINDS]:
                self.player.playback_mode='ffplay'
                if kind=='dubbed':self.player.start_pending()
                elif kind=='original':self.player.start_original_pending()
                else:self.ui.play(kind)
                def check(k=kind):
                    try:
                        self.assertEqual(self.player.waveform_active_kind,k)
                        self.assertTrue(self.player.waveform_canvases[k].find_withtag('progress'))
                    except Exception as exc:failures.append(exc)
                    finally:self.player.stop(announce=False);self.root.quit()
                self.root.after(200,check);self.root.mainloop()
        if failures:raise failures[0]

class Selection(SceneTests):
    def test_multiple_selection_and_cancel(self):
        import tkinter as tk
        from scene_audio_choices import choose,sources
        for kind in ov.KINDS:wav(ov.scene_directory(self.project,self.original)/(kind+'.wav'))
        options=sources(self.project,self.original)
        def accept():
            def walk(w):
                for child in w.winfo_children():
                    if isinstance(child,tk.Checkbutton) and 'sample-instrumental' in child.cget('text'):child.invoke()
                    if isinstance(child,tk.Button) and child.cget('text')=='USAR FAIXAS SELECIONADAS':child.invoke();return
                    walk(child)
            walk(self.player.window)
        self.root.after(50,accept)
        result=choose(self.player.window,options,'Teste',('vocals',))
        self.assertEqual([key for key,_ in result],['instrumental','vocals'])
        before=self.original.read_bytes()
        from background_audio import BackgroundEditor
        target=self.project/'dub.wav';wav(target)
        self.player.dubbed_pending_paths=[target];self.player.dubbed_navigation_paths=[target]
        editor=BackgroundEditor(self.player);self.root.update()
        with patch('scene_audio_choices.choose',return_value=result):editor.select_sources()
        self.assertEqual(editor.background_source_keys,('instrumental','vocals'))
        editor.undo_edit();self.assertEqual(editor.background_source_keys,('original',))
        editor.redo_edit();self.assertEqual(editor.background_source_keys,('instrumental','vocals'))
        self.assertEqual(self.original.read_bytes(),before);editor.close()

