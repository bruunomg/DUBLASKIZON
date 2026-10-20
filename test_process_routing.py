import unittest,sys,threading,queue,types,subprocess
from unittest.mock import patch
from generation_progress import configure_process_sink,run_observed
from scene_parts import run_command
from warm_inference import SERVER_CODE

class ProcessRoutingTests(unittest.TestCase):
 def tearDown(self):configure_process_sink(None)
 def test_parts_stream_lines_to_shared_sink(self):
  lines=[];configure_process_sink(lambda source,text:lines.append((source,text)))
  run_command([sys.executable,'-u','-c',"print('CONFERÊNCIA: trecho 2/4')"],threading.Event())
  self.assertTrue(any('trecho 2/4' in text for _,text in lines))
  self.assertTrue(any('finalizado' in text for _,text in lines))
 def test_review_runner_streams_lines_and_reports_completion(self):
  lines=[];configure_process_sink(lambda source,text:lines.append((source,text)))
  result=run_observed([sys.executable,'-u','-c',"print('TEMPO: síntese 1.5 s')"],lambda *args:None,subprocess.run)
  self.assertEqual(result.returncode,0)
  self.assertTrue(any('síntese 1.5' in text for _,text in lines))
 def test_central_fanout_does_not_relay_batch_back_to_itself(self):
  from Dublaskizon import DublaskizonApp
  app=DublaskizonApp.__new__(DublaskizonApp);app.central_log_queue=queue.Queue();app.batch_app=types.SimpleNamespace(message_queue=queue.Queue())
  app.central_log('GERAÇÃO — cena','trecho 3/4')
  self.assertEqual(app.batch_app.message_queue.get()[0],'external_log')
  app.central_log('CLONAGEM + DUBLAGEM','mensagem nativa')
  self.assertTrue(app.batch_app.message_queue.empty())
 def test_review_uses_isolated_worker_with_cache_disabled(self):
  import tempfile
  import warm_inference
  from review_tab import ReviewApp
  from test_warm_inference import FAKE_ENGINE
  cache=types.SimpleNamespace(preloading=False,enabled=False,evict_idle=lambda *a:None)
  with tempfile.TemporaryFile('w+b') as log,patch('warm_inference.review_memory_cache',cache),patch('warm_inference.SERVER_CODE',FAKE_ENGINE+SERVER_CODE),patch.object(warm_inference.WarmInference,'eligible',return_value=True):
   result=ReviewApp._run_cancellable_generation(types.SimpleNamespace(regen_cancel_requested=False),[sys.executable,'-u','-c',"print('geracao isolada pronta',flush=True)"],stdout=log)
   self.assertEqual(result.returncode,0);log.seek(0)
   self.assertIn(b'geracao isolada pronta',log.read())

 def test_gpu_asr_requires_free_memory(self):
  code=SERVER_CODE[SERVER_CODE.index('def gpu_asr_has_headroom'):SERVER_CODE.index('def limited_vram')]
  cuda=types.SimpleNamespace(is_available=lambda:True,mem_get_info=lambda:(4*1024**3,8*1024**3))
  ns={'torch':types.SimpleNamespace(cuda=cuda)};exec(code,ns)
  self.assertTrue(ns['gpu_asr_has_headroom']())
  cuda.mem_get_info=lambda:(2*1024**3,8*1024**3)
  self.assertFalse(ns['gpu_asr_has_headroom']())
  cuda.mem_get_info=lambda:(4*1024**3,6*1024**3)
  self.assertFalse(ns['gpu_asr_has_headroom']())
