import io,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import api_configuration as config
import semantic_review as api
import transcription_backend as backend

class ConfigurationTests(unittest.TestCase):
 def test_env_matches_fields_aliases_quotes_and_does_not_change_source(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'.env';content='export OPENAI_API_KEY="test-secret" # comment\nOPENAI_BASE_URL=https://api.openai.com/v1\nOPENAI_MODEL=gpt-4.1-mini\nOPENAI_CODEX_MODEL=gpt-5-codex\nANTHROPIC_API_KEY=claude-secret\nANTHROPIC_MODEL=claude-test\nGOOGLE_API_KEY=gemini-secret\nGEMINI_MODEL=gemini-test\nUNRELATED_PASSWORD=ignored\n'
   path.write_text(content,encoding='utf-8');values=config.import_env(path)
   self.assertEqual(values['openai_key'],'test-secret');self.assertEqual(values['codex_model'],'gpt-5-codex');self.assertEqual(values['openai_model'],'gpt-4.1-mini')
   self.assertEqual(values['claude_key'],'claude-secret');self.assertEqual(values['gemini_key'],'gemini-secret');self.assertNotIn('UNRELATED_PASSWORD',values);self.assertEqual(path.read_text(),content)
 def test_env_existing_luna_sol_and_empty_variables(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'.env';path.write_text('OPENAI_API_KEY=\nLUNA_TRANSLATION_MODEL=luna-test\nSOL_REVIEW_MODEL=sol-test\n',encoding='utf-8')
   result=config.import_env(path);self.assertNotIn('openai_key',result);self.assertEqual(result,{'openai_model':'luna-test','codex_model':'sol-test'})
 def test_env_generic_values_apply_only_to_selected_provider(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'.env';path.write_text('API_KEY=test-secret\nMODEL=claude-test\nBASE_URL=https://api.anthropic.com/v1\n')
   values=config.import_env(path,'Claude');self.assertEqual(values['claude_model'],'claude-test');self.assertNotIn('openai_key',values)
 def test_random_identifier_and_secret_cannot_be_used_as_model(self):
  for model,key in [('AbCdEfGhIjKlMnOp','secret'),('sk-test-secret','other'),('copied-secret','copied-secret')]:
   with self.subTest(model=model),self.assertRaises(ValueError) as error:config.validate_model(model,key)
   self.assertNotIn(model,str(error.exception))
  self.assertEqual(config.validate_model('gpt-4.1-mini'),'gpt-4.1-mini');self.assertEqual(config.validate_model('o3'),'o3')
  self.assertEqual(config.validate_model('AbCdEfGhIjKlMnOp',official=False),'AbCdEfGhIjKlMnOp')
 def test_readonly_list_and_model_test_never_call_generation(self):
  calls=[]
  def opener(request,timeout):
   calls.append(request)
   payload={'data':[{'id':'gpt-4.1-mini'},{'id':'gpt-5-codex'}]} if request.full_url.endswith('/models') else {'id':'gpt-4.1-mini'}
   return io.BytesIO(json.dumps(payload).encode())
  result=config.list_models('OpenAI','https://api.openai.com/v1','test-secret',opener)
  self.assertIn('gpt-4.1-mini',result['models']);self.assertIn('Consulta aceita',config.test_model('OpenAI','https://api.openai.com/v1','test-secret','gpt-4.1-mini',opener))
  self.assertTrue(all(call.get_method()=='GET' and call.data is None for call in calls));self.assertTrue(all('test-secret' not in call.full_url for call in calls))
 def test_authentication_and_model_errors_are_distinct_and_redacted(self):
  for code in (401,404):
   def opener(*args,**kwargs):raise urllib.error.HTTPError('https://example.test',code,'private-secret',{},io.BytesIO(b'private-secret'))
   with self.assertRaises(RuntimeError) as error:config.list_models('OpenAI','https://api.openai.com/v1','private-secret',opener)
   self.assertIn('HTTP '+str(code),str(error.exception));self.assertNotIn('private-secret',str(error.exception))
   self.assertIn('chave secreta' if code==401 else 'modelo',str(error.exception))
 def test_normalizes_endpoint_and_rejects_registration_site(self):
  self.assertEqual(config.normalize_base('openai','https://api.openai.com/v1/responses'),'https://api.openai.com/v1')
  with self.assertRaises(ValueError):config.normalize_base('openai','https://platform.openai.com/api-keys')
 def test_bad_model_is_stopped_before_http_and_logging(self):
  values={**api.DEFAULTS,'codex_model':'AbCdEfGhIjKlMnOp'}
  with patch('urllib.request.urlopen') as request:
   with self.assertRaises(ValueError):api.request_report('OpenAI / Codex','S','P',values,'test-secret',lambda:False)
   request.assert_not_called()
  logs=[]
  with self.assertRaises(ValueError):backend.translate_api('Hello','pt',{'luna_model':'sk-test-secret','base_url':'https://api.openai.com/v1'},'other-secret',logs.append,lambda:False)
  self.assertEqual(logs,[])
 def test_saved_provider_does_not_become_ready_with_key_id_in_model(self):
  values={**api.DEFAULTS,'codex_model':'AbCdEfGhIjKlMnOp'}
  with patch('semantic_review.load_key',return_value='test-secret'):
   self.assertFalse(api.ready('OpenAI / Codex',values));self.assertIn('identificador',api.configuration_problem('OpenAI / Codex',values))
class ParameterTests(unittest.TestCase):
 def test_export_provider_parameters_round_trip_without_secret(self):
  values={**api.DEFAULTS,'openai_key':'DO-NOT-EXPORT','openai_model':'gpt-4.1-mini','codex_model':'gpt-5-codex','claude_model':'claude-test','gemini_model':'gemini-test','batch_size':3,'max_batches':0,'max_retries':1,'request_timeout':120}
  for provider,key in [('OpenAI','OPENAI_API_KEY'),('Claude','ANTHROPIC_API_KEY'),('Gemini','GEMINI_API_KEY')]:
   content=config.export_env(values,provider);self.assertNotIn('DO-NOT-EXPORT',content);self.assertIn(key+'=',content)
   with tempfile.TemporaryDirectory() as folder:
    file=Path(folder)/'settings.env';file.write_text(content);data=config.import_env(file,provider)
   self.assertEqual(config.execution_parameters(data),{'batch_size':3,'max_batches':0,'max_retries':1,'request_timeout':120})
 def test_batch_size_used_and_limit_rejects_before_any_request(self):
  calls=[]
  def transport(model,system,items,*args):calls.append(items);return {'items':[{'index':item['index'],'text':'Olá'} for item in items]}
  values={'luna_model':'gpt-test','batch_size':2,'max_batches':0}
  backend.translate_api('One\nTwo\nThree','pt',values,'secret',lambda x:None,lambda:False,transport=transport)
  self.assertEqual([len(items) for items in calls],[2,1]);calls.clear()
  with self.assertRaisesRegex(RuntimeError,'MAX_BATCHES'):backend.translate_api('One\nTwo\nThree','pt',{**values,'max_batches':1},'secret',lambda x:None,lambda:False,transport=transport)
  self.assertEqual(calls,[])
 def test_timeout_and_bounded_retry_applied(self):
  calls=[]
  def opener(request,timeout):
   calls.append(timeout)
   if len(calls)==1:raise urllib.error.HTTPError('https://example.test',503,'unavailable',{},None)
   return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"items":[]}'}]}]}).encode())
  api.request_report('OpenAI','system','text',{**api.DEFAULTS,'openai_model':'gpt-test','request_timeout':123,'max_retries':1},'secret',lambda:False,opener)
  self.assertEqual(calls,[123,123])
if __name__=='__main__':unittest.main()
