import io,sys,tempfile,time,unittest,subprocess
from unittest.mock import patch
from warm_inference import ReviewMemoryCache,SERVER_CODE,WarmInference
from test_warm_inference import FAKE_ENGINE

class ReviewCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache=ReviewMemoryCache();self.addCleanup(self.cache.shutdown)
        for p in [patch('warm_inference.SERVER_CODE',FAKE_ENGINE+SERVER_CODE),
                  patch.object(WarmInference,'eligible',return_value=True),
                  patch('warm_inference.available_memory',return_value=(8*1024**3,16*1024**3))]:
            p.start();self.addCleanup(p.stop)
    def command(self,text):
        return [sys.executable,'-u','-c',"from omnivoice.models.omnivoice import OmniVoice;import sys;m=OmniVoice.from_pretrained('same');print(m.generate(sys.argv[1]),flush=True)",text]
    def run_scene(self,text):
        with tempfile.TemporaryFile('w+b') as output:
            scene=self.cache.start(self.command(text),stdout=output,text=True)
            self.assertEqual(scene.wait(timeout=15),0)
            output.seek(0);return scene,output.read().decode('utf-8')
    def test_two_manual_scenes_share_worker_binary_progress_and_not_text(self):
        self.cache.set_enabled(True)
        first,a=self.run_scene('Primeira fala.')
        second,b=self.run_scene('Segunda fala.')
        self.assertEqual(first.pid,second.pid)
        self.assertIn('LOAD_MODEL',a);self.assertNotIn('LOAD_MODEL',b)
        self.assertIn('Segunda fala.',b);self.assertNotIn('Primeira fala.',b)
        process=self.cache.pool.process
        self.cache.set_enabled(False)
        for _ in range(100):
            if process.poll() is not None:break
            time.sleep(.02)
        self.assertIsNotNone(process.poll())
    def test_disabled_and_low_memory_keep_original_runner(self):
        command=self.command('fala')
        with patch('warm_inference.subprocess.Popen') as popen:
            self.cache.start(command,stdout=io.BytesIO())
            popen.assert_called_once()
        self.cache.set_enabled(True)
        with patch('warm_inference.available_memory',return_value=(200*1024**2,16*1024**3)),patch('warm_inference.subprocess.Popen') as popen:
            self.cache.start(command,stdout=io.BytesIO())
            popen.assert_called_once()
    def test_turn_off_during_scene_does_not_cancel_it(self):
        self.cache.set_enabled(True)
        command=[sys.executable,'-u','-c',"import time;print('começou',flush=True);time.sleep(.3);print('terminou',flush=True)"]
        with tempfile.TemporaryFile('w+b') as output:
            scene=self.cache.start(command,stdout=output,text=True)
            self.cache.set_enabled(False)
            with self.assertRaises(RuntimeError):self.cache.start(command,stdout=output,text=True)
            self.assertEqual(scene.wait(timeout=15),0)
            output.seek(0);self.assertIn('terminou',output.read().decode())
    def test_cancellation_clears_worker_for_next_scene(self):
        self.cache.set_enabled(True)
        with tempfile.TemporaryFile('w+b') as output:
            scene=self.cache.start([sys.executable,'-u','-c','import time;time.sleep(30)'],stdout=output,text=True)
            scene.terminate();self.assertNotEqual(scene.wait(timeout=15),0)
        second,_=self.run_scene('recuperou');self.assertNotEqual(scene.pid,second.pid)

    def test_real_review_runner_and_binary_progress_log(self):
        from types import SimpleNamespace
        from review_tab import ReviewApp
        from generation_progress import run_observed
        self.cache.set_enabled(True)
        app=SimpleNamespace(regen_cancel_requested=False)
        with patch('warm_inference.review_memory_cache',self.cache):
            result=run_observed(self.command('teste integrado'),lambda *_:None,
                runner=lambda command,**kwargs:ReviewApp._run_cancellable_generation(app,command,**kwargs),text=True)
        self.assertEqual(result.returncode,0)
        self.assertIn('teste integrado',result.stdout)
        self.assertIn('LOAD_MODEL',result.stdout)

    def test_header_switch_is_off_by_default_and_controls_cache(self):
        import tkinter as tk
        import textwrap
        from pathlib import Path
        from types import SimpleNamespace
        root=tk.Tk();root.withdraw()
        self.addCleanup(root.destroy)
        from review_memory_ui import mount_controls
        panel=tk.Frame(root)
        refresh=tk.Button(panel,text='ATUALIZAR TELA');refresh.pack(side='left')
        app=SimpleNamespace(root=root,refresh_screen_button=refresh,current_tab_key=lambda:'clone')
        frame=mount_controls(app,panel,self.cache)
        self.assertEqual(panel.pack_slaves()[:2],[frame,refresh])
        self.assertFalse(app.review_memory_var.get())
        app.review_memory_button.invoke();self.assertTrue(self.cache.enabled)
        app.review_memory_button.invoke();self.assertFalse(self.cache.enabled)

    def test_review_context_keeps_loaded_worker_past_idle_timeout(self):
        self.cache.set_enabled(True);self.cache.set_review_context(True)
        scene,_=self.run_scene('carregado')
        state=self.cache.snapshot()
        self.assertEqual(state['pid'],scene.pid)
        self.assertTrue(state['model_ready']);self.assertFalse(state['asr_ready'])
        self.cache.config['idle_minutes']=10
        self.cache.last_used=time.monotonic()-10000
        self.cache.check_retention();self.assertEqual(self.cache.pool.process.pid,scene.pid)
        self.cache.set_review_context(False);self.cache.check_retention()
        self.assertIsNone(self.cache.pool.process)

    def test_translation_releases_worker_then_synthesis_restarts(self):
        self.cache.set_enabled(True)
        before,_=self.run_scene('antes')
        with self.cache.translation_session():
            self.assertIsNone(self.cache.pool.process)
            self.assertTrue(self.cache.snapshot()['preparing'])
            with self.assertRaises(RuntimeError):self.cache.start(self.command('concorrente'),stdout=io.BytesIO())
        self.assertFalse(self.cache.snapshot()['preparing'])
        self.assertTrue(self.cache.enabled)
        after,_=self.run_scene('depois');self.assertNotEqual(before.pid,after.pid)

    def test_saved_thresholds_and_immediate_review_detection(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'memory.json';self.cache.settings_path=path
            self.cache.configure(dict(idle_minutes=0,min_scenes=4,keep_while_review=True,reserve_mb=1024))
            other=ReviewMemoryCache(path)
            try:
                self.assertEqual(other.config['min_scenes'],4)
                self.assertFalse(other.enabled)
            finally:other.shutdown()
        self.cache.set_enabled(True)
        self.run_scene('primeira fora');self.assertIsNone(self.cache.pool.process)
        self.cache.set_review_context(True)
        self.run_scene('na revisão');self.assertIsNotNone(self.cache.pool.process)

    def test_ready_profile_ignores_brief_ram_drop_but_releases_critical_pressure(self):
        self.cache.set_enabled(True);self.run_scene('pronto')
        self.assertEqual(self.cache.config['idle_minutes'],0)
        with patch('warm_inference.available_memory',return_value=(900*1024**2,16*1024**3)):
            self.cache.check_retention();self.assertIsNotNone(self.cache.pool.process)
        self.cache.check_retention();self.assertIsNone(self.cache.low_ram_since)
        with patch('warm_inference.available_memory',return_value=(200*1024**2,16*1024**3)):
            self.cache.check_retention();self.assertIsNone(self.cache.pool.process)

    def test_preload_prepares_worker_without_counting_or_generating_speech(self):
        self.cache.set_enabled(True)
        with patch('warm_inference.preload_command',return_value=self.command('preparado')):
            self.cache.preload('omnivoice')
            self.assertTrue(self.cache.preload_done.wait(15))
        state=self.cache.snapshot()
        self.assertTrue(state['model_ready']);self.assertFalse(state['preloading'])
        self.assertEqual(state['completed'],0)
        scene,_=self.run_scene('nova fala');self.assertEqual(scene.pid,state['pid'])

    def test_turning_off_cancels_preload_without_waiting_for_a_scene(self):
        self.cache.set_enabled(True)
        with patch('warm_inference.preload_command',return_value=[sys.executable,'-u','-c','import time;time.sleep(30)']):
            self.cache.preload('omnivoice')
            for _ in range(100):
                if self.cache.preload_process is not None:break
                time.sleep(.01)
            self.cache.set_enabled(False)
            self.assertTrue(self.cache.preload_done.wait(15))
        self.assertIsNone(self.cache.pool.process)

if __name__=='__main__':unittest.main()
