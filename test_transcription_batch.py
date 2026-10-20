import json,tempfile,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
import audio_translation as local
import transcription_backend as backend

class BatchTests(unittest.TestCase):
 def test_batch_reuses_model_and_continues_after_bad_file(self):
  loads=[];segments=[]
  def model(*args,**kwargs):
   loads.append(args)
   def transcribe(path,**kwargs):
    segments.append(path)
    if 'bad' in path:raise RuntimeError('Invalid audio test')
    return [types.SimpleNamespace(text='A complete sentence.',end=1.,avg_logprob=-.2)],types.SimpleNamespace(language='en',duration=1.)
   return types.SimpleNamespace(transcribe=transcribe)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);request=root/'request.json';result=root/'result.json'
   request.write_text(json.dumps({'batch_paths':['first.wav','bad.wav','last.wav'],'settings':local.settings(),'worker':local.WORKER}),encoding='utf-8')
   with patch.dict(sys.modules,{'faster_whisper':types.SimpleNamespace(WhisperModel=model)}),patch.object(sys,'argv',['batch',str(request),str(result)]),patch('builtins.print'):
    exec(compile(backend.BATCH_ASR_CODE,'batch_worker','exec'),{})
   data=json.loads(result.read_text())['items']
  self.assertEqual(len(loads),1);self.assertEqual(len(segments),3);self.assertIn('error',data[1]);self.assertEqual(data[2]['transcript'],'A complete sentence.')
 def test_review_signals_and_normal_completion(self):
  good={'transcript':'Das ist gut.','translation':'Isso é bom.','source_language':'de'}
  self.assertEqual(backend.assess_text_result(good,Path('name__DE.wav'),translated=True),[])
  bad={**good,'source_language':'en','translation':''}
  warnings=backend.assess_text_result(bad,Path('name__DE.wav'),translated=True)
  self.assertTrue(any('Idioma' in warning for warning in warnings));self.assertIn('Tradução vazia.',warnings)
