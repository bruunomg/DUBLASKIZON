import unittest,tempfile,os,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import component_uninstall as c

class Removal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
        env=patch.dict(os.environ,{'LOCALAPPDATA':str(self.home),'HF_HOME':str(self.home/'hf'),'XDG_DATA_HOME':str(self.home/'.local/share'),'ARGOS_PACKAGES_DIR':str(self.home/'argos')})
        env.start();self.addCleanup(env.stop)
        home=patch.object(Path,'home',return_value=self.home);home.start();self.addCleanup(home.stop)
        from dependency_setup import runtime_root
        self.runtime=runtime_root();self.runtime.mkdir(parents=True)
    def file(self,path):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test');return path
    def test_selective_removal_keeps_other_tools_keys_and_project(self):
        self.file(self.runtime/'env-1/python.exe');translation=self.file(self.runtime/'translation-1/python.exe')
        key=self.file(self.runtime/'semantic-openai-key.bin');settings=self.file(self.runtime/'translation-last-settings.json')
        project=self.home/'project';audio=self.file(project/'WAV ORIGINAIS/a.wav');txt=self.file(project/'TXT TEXTO PORTUGUES/a.txt')
        self.file(self.home/'argos/en_pt/model.bin');self.file(self.home/'.cache/whisper/large-v3.pt')
        self.file(self.home/'hf/hub/models--Systran--faster-whisper-large-v3/snapshots/1/model.bin')
        items=c.catalog(self.home,project,include_ollama=False,include_system=False)
        selected=[i for i in items if i['label'].startswith('Transcrição / tradução')]
        self.assertEqual(len(selected),1)
        removed,failures,notices=c.remove_selected(selected)
        self.assertGreater(removed,0);self.assertFalse(failures);self.assertFalse(translation.exists())
        for path in (key,settings,audio,txt,self.runtime/'env-1/python.exe'):self.assertTrue(path.exists(),str(path))
        self.assertTrue(any('Argos' in i['label'] for i in items));self.assertTrue(any('Whisper' in i['label'] for i in items))
    def test_overlapping_selected_paths_only_removed_once(self):
        parent=self.home/'a';child=parent/'child';self.file(child/'test.bin')
        self.assertEqual(c.unique_paths([child,parent,parent]),[parent])
    def test_ollama_removes_only_named_model_with_api(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        item=dict(label='Qwen',kind='ollama',model='qwen2.5:7b',paths=[],size=10)
        with patch('audio_translation.ensure_ollama'),patch('component_uninstall.urllib.request.urlopen',return_value=response) as request:
            removed,failures,notices=c.remove_selected([item])
        self.assertFalse(failures);self.assertTrue(notices)
        req=request.call_args.args[0];self.assertEqual(req.get_method(),'DELETE');self.assertEqual(json.loads(req.data),{'model':'qwen2.5:7b'})

class MemoryUI(unittest.TestCase):
    def test_both_controls_share_state_without_duplicate_preload(self):
        import tkinter as tk
        import review_memory_ui as ui
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
        app=SimpleNamespace(root=root,batch_app=SimpleNamespace(selected_model_id=lambda:'test/model'),current_tab_key=lambda:'review')
        root._dublaskizon_app=app
        parent=tk.Frame(root);parent.pack();app.refresh_screen_button=tk.Button(parent,text='Refresh');app.refresh_screen_button.pack()
        cache=Mock();cache.enabled=False
        cache.snapshot=lambda:dict(enabled=cache.enabled,active=False,preparing=False,reason='desligado',preloading=False)
        cache.set_enabled=lambda value:setattr(cache,'enabled',value)
        with patch('warm_inference.review_memory_cache',cache):
            main=ui.mount_controls(app,parent,cache)
            scene_parent=tk.Frame(root);scene_parent.pack()
            scene=ui.mount_scene_controls(SimpleNamespace(parent=root),scene_parent)
            self.assertEqual(str(main.memory_button.cget('variable')),str(scene.memory_button.cget('variable')))
            main.memory_button.invoke();self.assertTrue(cache.enabled);self.assertTrue(scene.memory_button.getvar(scene.memory_button.cget('variable')))
            scene.memory_button.invoke();self.assertFalse(cache.enabled);self.assertFalse(app.review_memory_var.get())
            cache.preload.assert_called_once_with('test/model')
