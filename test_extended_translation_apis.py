import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import semantic_review as api
import audio_translation as local

class ExtendedApiTests(unittest.TestCase):
 def test_gemini_native_json_request_and_thoughts_excluded(self):
  calls=[];report={'needs_review':False,'issues':[],'corrected_translation':'Olá'}
  def opener(request,timeout):
   calls.append(request)
   return io.BytesIO(json.dumps({'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'private reasoning'},{'text':json.dumps(report)}]}}]}).encode())
  result=api.request_report('Gemini — API','System','Prompt',{**api.DEFAULTS,'gemini_model':'models/gemini-test'},'private-test',lambda:False,opener)
  request=calls[0];payload=json.loads(request.data)
  self.assertTrue(request.full_url.endswith('/models/gemini-test:generateContent'));self.assertNotIn('private-test',request.full_url)
  self.assertEqual(request.get_header('X-goog-api-key'),'private-test');self.assertEqual(payload['systemInstruction']['parts'][0]['text'],'System')
  self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json');self.assertEqual(result,report)
 def test_gemini_truncation_and_blocked_responses_rejected(self):
  for result in ({'candidates':[]},{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'{}'}]}}]}):
   with self.assertRaisesRegex(RuntimeError,'incompleta'):api.request_report('Gemini','S','P',{**api.DEFAULTS,'gemini_model':'test'},'private',lambda:False,lambda *a,**k:io.BytesIO(json.dumps(result).encode()))
 def test_all_new_translators_use_indexed_validation_and_context(self):
  for code,provider in api.TRANSLATION_PROVIDERS.items():
   with self.subTest(provider=provider):
    config={**api.DEFAULTS,'openai_model':'gpt-test','codex_model':'codex-test','claude_model':'claude-test','gemini_model':'gemini-test'}
    def request(p,system,prompt,settings,key,cancel):
     self.assertEqual(p,provider);self.assertIn('My Game',system);self.assertEqual(json.loads(prompt)['items'][0]['source'],'<b>Hello</b>')
     return {'items':[{'index':0,'text':'<b>Olá</b>'}]}
    with patch('semantic_review.settings',return_value=config),patch('semantic_review.load_key',return_value='private'),patch('semantic_review.request_report',side_effect=request):
     self.assertEqual(api.translate('<b>Hello</b>','pt',code,lambda x:None,lambda:False,{'title':'My Game'}),'<b>Olá</b>')
 def test_invalid_provider_output_is_not_published(self):
  with patch('semantic_review.settings',return_value={**api.DEFAULTS,'gemini_model':'test'}),patch('semantic_review.load_key',return_value='private'),patch('semantic_review.request_report',return_value={'items':[{'index':0,'text':'Here is the translation: Olá'}]}):
   with self.assertRaisesRegex(RuntimeError,'comentários'):api.translate('Hello','pt','gemini-api',lambda x:None,lambda:False)
 def test_gemini_key_protected_and_separate(self):
  with tempfile.TemporaryDirectory() as directory,patch('semantic_review.runtime_root',return_value=Path(directory)),patch('transcription_backend.crypt_key',side_effect=lambda raw,protect:b'protected-'+raw if protect else raw.removeprefix(b'protected-')):
   api.save_settings({**api.DEFAULTS,'gemini_model':'test'},'openai-test','claude-test','gemini-secret')
   self.assertEqual(api.load_key('Gemini'),'gemini-secret');self.assertEqual(api.load_key('Claude'),'claude-test')
   self.assertNotIn('gemini-secret',(Path(directory)/'semantic-review.json').read_text())
 def test_extended_api_dubbing_uses_native_translator(self):
  for code in api.TRANSLATION_PROVIDERS:
   with tempfile.TemporaryDirectory() as directory,patch('semantic_review.ready',return_value=True),patch('transcription_backend.run_local',return_value={'transcript':'Hello','source_language':'en'}),patch('semantic_review.translate',return_value='Olá') as translate:
    root=Path(directory);target=root/'TXT TEXTO PORTUGUES'/'scene.txt'
    self.assertEqual(local.generate_text('source.wav',target,root,'scene',{'translator':code},lambda x:None)[0],'Olá')
    self.assertEqual(translate.call_args.args[2],code)
if __name__=='__main__':unittest.main()
