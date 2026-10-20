import unittest,tempfile,zipfile,threading
from pathlib import Path
from unittest.mock import Mock,patch
import audacity_setup as a

class Preparation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'Audacity'
        self.job=Mock();self.job.cancel=threading.Event()
    def ready(self,root):
        for name in ['Audacity.exe','modules/mod-openvino.dll','modules/mod-script-pipe.dll','openvino-models/htdemucs_v4.xml','openvino-models/htdemucs_v4.bin','openvino-models/noise-suppression-denseunet-ll-0001.xml','openvino-models/noise-suppression-denseunet-ll-0001.bin']:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test')
        (root/'openvino-models/deepfilternet3').mkdir(parents=True,exist_ok=True)
    def test_complete_existing_install_is_reused(self):
        self.ready(self.root)
        with patch.object(a,'installations',return_value=[self.root]),patch.object(a,'download') as download:
            self.assertEqual(a.prepare(self.job),self.root);download.assert_not_called()
    def test_models_are_required_not_only_plugin_dll(self):
        self.ready(self.root);(self.root/'openvino-models/htdemucs_v4.bin').unlink()
        self.assertIn('openvino-models/htdemucs_v4.bin',a.missing(self.root))
    def test_fresh_pair_targets_same_directory_with_required_components(self):
        archive=Path(self.temp.name)/'source.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('Audacity.exe',b'test');z.writestr('modules/mod-script-pipe.dll',b'test')
        def download(job,url,target,size):return archive if url==a.AUDACITY_URL else Path(self.temp.name)/'plugin.exe'
        def install(job,exe,directory):self.assertEqual(directory,self.root);self.ready(directory)
        with patch.object(a,'installations',return_value=[]),patch.object(a,'managed_directory',return_value=self.root),patch('audacity_openvino.audacity_running',return_value=False),patch.object(a,'download',side_effect=download),patch.object(a,'run_plugin_installer',side_effect=install) as run:
            self.assertEqual(a.prepare(self.job),self.root);run.assert_called_once()
        self.assertIn('music_sep',a.COMPONENTS);self.assertIn(r'noise_sup\denseunet',a.COMPONENTS)
    def test_no_changes_when_audacity_is_running(self):
        with patch.object(a,'installations',return_value=[]),patch('audacity_openvino.audacity_running',return_value=True),patch.object(a,'download') as download:
            with self.assertRaisesRegex(RuntimeError,'feche'):a.prepare(self.job)
            download.assert_not_called()
    def test_empty_selection_does_nothing(self):
        with patch.object(a,'download') as download:a.prepare(self.job,False,False);download.assert_not_called()

class RequirementsUI(unittest.TestCase):
    def test_defaults_blue_steps_and_scrollable_settings(self):
        import tkinter as tk
        import dependency_setup as setup
        from types import SimpleNamespace
        root=tk.Tk();self.addCleanup(root.destroy)
        root.geometry('400x200')
        app=SimpleNamespace(root=root,dependency_window=None,current_theme=lambda:{'root':'#202B3B','text':'white','input':'#334155','input_text':'white'},should_show_dependency_assistant=lambda:True,save_dependency_assistant_preference=lambda value:None,ensure_control_contrast=lambda w:None,prepare_shared_audio_tools=lambda:None)
        with patch.object(setup,'detect_processing',return_value={'variant':'cpu','cpu':'Teste','gpu':'CPU'}):
            setup.show_assistant(app);root.update()
        window=app.dependency_window;self.addCleanup(lambda:window.destroy() if window.winfo_exists() else None)
        window.geometry('900x650');root.update()
        self.assertTrue(all(var.get() for var in app.dependency_audacity_options))
        found={}
        def walk(widget):
            for child in widget.winfo_children():
                try:found[child.cget('text')]=child
                except tk.TclError:pass
                walk(child)
        walk(window)
        for text in ('1. INSTALAR / REPARAR','2. BAIXAR MODELOS','4. TESTAR MODELO'):
            self.assertEqual(found[text].cget('bg'),'#00FFFF')
            self.assertTrue(found[text].winfo_ismapped())
        self.assertTrue(found['CONTINUAR'].winfo_ismapped())
        canvas=app.dependency_body_canvas
        self.assertGreater(canvas.bbox('all')[3],canvas.winfo_height())
        canvas.yview_moveto(1);self.assertGreater(canvas.yview()[0],0)
        self.assertLess(found['CONTINUAR'].winfo_rooty()+found['CONTINUAR'].winfo_height(),window.winfo_rooty()+window.winfo_height()+1)
