import io,json,tempfile,unittest,os,sys,types,urllib.error
from pathlib import Path
from unittest.mock import patch
import transcription_backend as backend
import audio_translation

class BackendTests(unittest.TestCase):
 def test_protected_key_round_trip_not_in_public_config(self):
  if os.name!='nt':self.skipTest('DPAPI requer Windows')
  with tempfile.TemporaryDirectory() as folder,patch('transcription_backend.runtime_root',return_value=Path(folder)),patch.dict(os.environ,{'OPENAI_API_KEY':''}):
   secret='test-credential-only';backend.save_api(backend.API_DEFAULTS,secret)
   self.assertEqual(backend.load_key(),secret)
   self.assertNotIn(secret,(Path(folder)/'translation-api.json').read_text())
   self.assertNotIn(secret.encode(),(Path(folder)/'translation-api-key.bin').read_bytes())
   backend.save_api(backend.API_DEFAULTS,'');self.assertFalse(backend.load_key())
 def test_env_import_has_only_supported_fields(self):
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'.env';file.write_text('OPENAI_API_KEY=test-value\nOTHER_SECRET=omit\nLUNA_TRANSLATION_MODEL=custom-luna\n',encoding='utf-8')
   self.assertEqual(backend.import_env(file),{'key':'test-value','luna_model':'custom-luna'})
 def test_api_requires_all_indexes_and_preserves_tags(self):
  def api(model,system,records,*args):return {'items':[{'index':r['index'],'text':r['source'].replace('Hello','Olá')} for r in records]}
  checkpoints=[]
  with patch('transcription_backend.request_json',side_effect=api) as calls:
   source='\n'.join('[alegre] Hello {name} '+str(i) for i in range(17))
   value=backend.translate_api(source,'Português',backend.API_DEFAULTS,'test',lambda *a:None,lambda:False,checkpoint=checkpoints.append)
   self.assertEqual(value.count('Olá'),17);self.assertEqual(calls.call_count,3);self.assertEqual(len(checkpoints),3)
   self.assertEqual(calls.call_args.args[0],backend.API_DEFAULTS['luna_model'])
 def test_api_rejects_duplicate_indexes_and_missing_tags(self):
  for response in ({'items':[{'index':0,'text':'Olá'},{'index':0,'text':'Oi'}]},{'items':[{'index':0,'text':'Olá'},{'index':1,'text':'Oi'}]}):
   with self.subTest(response=response),patch('transcription_backend.request_json',return_value=response),self.assertRaises(RuntimeError):
    backend.translate_api('[alegre] Hello\nHello','pt',backend.API_DEFAULTS,'test',lambda *a:None,lambda:False)
 def test_review_uses_sol_and_keeps_translation_separate(self):
  source='Hello {player}';draft='Olá {player}'
  with patch('transcription_backend.request_json',return_value={'items':[{'index':0,'text':'Oi {player}'}]}) as api:
   result=backend.translate_api(source,'Português',backend.API_DEFAULTS,'test',lambda *a:None,lambda:False,draft=draft)
  self.assertEqual(result,'Oi {player}');self.assertEqual(api.call_args.args[0],backend.API_DEFAULTS['sol_model']);self.assertEqual(draft,'Olá {player}')
 def test_http_error_does_not_echo_server_body_or_key(self):
  def opener(*args,**kwargs):raise urllib.error.HTTPError('https://api.openai.com/v1/chat/completions',401,'bad',{},io.BytesIO(b'private-test-secret'))
  with self.assertRaises(RuntimeError) as error:backend.request_json('model','system',[],backend.API_DEFAULTS,'private-test-secret',lambda:False,opener)
  self.assertNotIn('private-test-secret',str(error.exception));self.assertIn('401',str(error.exception))
 def test_model_check_uses_get_without_translation(self):
  requests=[]
  def opener(request,timeout):
   requests.append(request)
   return io.BytesIO(b'{"id":"custom-model"}')
  backend.check_models(backend.API_DEFAULTS,'fake',opener)
  self.assertEqual(len(requests),2)
  self.assertTrue(all(request.get_method()=='GET' and request.data is None for request in requests))
 def test_cancel_before_api_call_sends_nothing(self):
  with self.assertRaisesRegex(RuntimeError,'cancelada'),patch('transcription_backend.request_json') as request:
   backend.translate_api('Hello','pt',backend.API_DEFAULTS,'fake',lambda *a:None,lambda:True)
  request.assert_not_called()

 def test_translate_only_worker_never_loads_whisper(self):
  with tempfile.TemporaryDirectory() as folder:
   request=Path(folder)/'request.json';result=Path(folder)/'result.json';config=audio_translation.settings({'source':'en','language':'Inglês'})
   request.write_text(json.dumps({'settings':config,'audio':'unused.wav','text':'Hello there','transcribe_only':False}))
   with patch.object(sys,'argv',['worker',str(request),str(result)]),patch.dict('sys.modules',{'faster_whisper':None,'whisper':None}):exec(compile(audio_translation.WORKER,'worker','exec'),{'__name__':'__main__'})
   self.assertEqual(json.loads(result.read_text())['translation'],'Hello there')
 def test_transcribe_only_worker_skips_translator(self):
  model=types.SimpleNamespace(transcribe=lambda *a,**k:(iter([types.SimpleNamespace(text='Hello there',end=1)]),types.SimpleNamespace(language='en',duration=1)))
  with tempfile.TemporaryDirectory() as folder:
   request=Path(folder)/'request.json';result=Path(folder)/'result.json'
   request.write_text(json.dumps({'settings':audio_translation.settings({'source':'en'}),'audio':'unchanged.wav','text':None,'transcribe_only':True}))
   with patch.object(sys,'argv',['worker',str(request),str(result)]),patch.dict('sys.modules',{'faster_whisper':types.SimpleNamespace(WhisperModel=lambda *a,**k:model),'argostranslate':None}):
    with self.assertRaises(SystemExit) as stop:exec(compile(audio_translation.WORKER,'worker','exec'),{'__name__':'__main__'})
    self.assertEqual(stop.exception.code,0)
   data=json.loads(result.read_text());self.assertEqual(data['transcript'],'Hello there');self.assertEqual(data['translation'],'')
 def test_worker_uses_managed_command_without_modifying_input(self):
  from contextlib import nullcontext
  with tempfile.TemporaryDirectory() as folder:
   original=Path(folder)/'original.wav';original.write_bytes(b'original')
   fake="import sys,json;print('Transcrevendo',flush=True);d=json.load(open(sys.argv[1]));json.dump({'transcript':'teste','translation':''},open(sys.argv[2],'w'))"
   with patch('audio_translation.translation_python',return_value=sys.executable),patch('audio_translation.WORKER',fake),patch('batch_tab.find_ffmpeg_directory',return_value=None),patch('warm_inference.review_memory_cache.translation_session',side_effect=lambda *a:nullcontext()):
    data=backend.run_local(original,None,{},True,lambda *a:None,lambda:False)
   self.assertEqual(data['transcript'],'teste');self.assertEqual(original.read_bytes(),b'original')
