import io,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import semantic_review as semantic
import transcription_backend as backend

class SemanticTests(unittest.TestCase):
 def verdict(self):return {'needs_review':True,'issues':['Expressão imperativa excessivamente literal.'],'corrected_translation':'Abaixe a cabeça, porra!'}
 def test_user_example_is_flagged_by_semantic_verdict(self):
  result=semantic.validate_report(self.verdict(),'Kopf runter, verdammt!','Cabeça para baixo, puta merda!')
  self.assertTrue(result['needs_review']);self.assertEqual(result['corrected_translation'],'Abaixe a cabeça, porra!')
 def test_changed_text_cannot_be_silently_approved(self):
  data={**self.verdict(),'needs_review':False,'issues':[]}
  self.assertTrue(semantic.validate_report(data,'Original','Outro texto')['needs_review'])
 def test_missing_verdict_empty_text_or_changed_tags_rejected(self):
  for data in ({'corrected_translation':'Texto'},{'needs_review':'false','issues':[],'corrected_translation':'Texto'},{'needs_review':False,'issues':[],'corrected_translation':''},{'needs_review':False,'issues':[],'corrected_translation':'Sem tag'}):
   with self.assertRaises(RuntimeError):semantic.validate_report(data,'<b>Source</b>','<b>Texto</b>')
 def test_embedded_translation_explanation_is_a_warning(self):
  record={'transcript':'Kopf runter, verdammt!','translation':'"Kopf runter, verdammt!" translates to "Cabeça para baixo, puta merda!"'}
  self.assertTrue(any('apresentação' in reason for reason in backend.assess_text_result(record,None,translated=True)))
 def test_openai_responses_and_codex_use_configured_model(self):
  for provider,field in [('OpenAI / ChatGPT — API','openai_model'),('OpenAI / Codex — API','codex_model')]:
   calls=[]
   def opener(request,timeout):
    calls.append(request);return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(self.verdict())}]}]}).encode())
   config={**semantic.DEFAULTS,field:'account-model-id'}
   result=semantic.request_report(provider,'System','Prompt',config,'secret-test',lambda:False,opener)
   payload=json.loads(calls[0].data);self.assertEqual(payload['model'],'account-model-id');self.assertFalse(payload['store']);self.assertTrue(calls[0].full_url.endswith('/responses'));self.assertEqual(result,self.verdict())
 def test_claude_messages_headers_and_system(self):
  calls=[]
  def opener(request,timeout):calls.append(request);return io.BytesIO(json.dumps({'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(self.verdict())}]}).encode())
  result=semantic.request_report('Claude — API','System','Prompt',{**semantic.DEFAULTS,'claude_model':'my-claude-model'},'secret-test',lambda:False,opener)
  request=calls[0];self.assertTrue(request.full_url.endswith('/messages'));self.assertEqual(request.get_header('X-api-key'),'secret-test');self.assertEqual(json.loads(request.data)['system'],'System');self.assertEqual(result,self.verdict())
 def test_incomplete_response_and_http_error_never_pass(self):
  with self.assertRaisesRegex(RuntimeError,'incompleto'):semantic.request_report('OpenAI','S','P',{**semantic.DEFAULTS,'openai_model':'test'},'hidden',lambda:False,lambda *a,**k:io.BytesIO(b'{"status":"incomplete"}'))
  def opener(*args,**kwargs):raise urllib.error.HTTPError('https://example.test',401,'hidden',None,None)
  with self.assertRaises(RuntimeError) as error:semantic.request_report('OpenAI','S','P',{**semantic.DEFAULTS,'openai_model':'test'},'hidden',lambda:False,opener)
  self.assertNotIn('hidden',str(error.exception))
 def test_keys_are_protected_outside_public_settings(self):
  with tempfile.TemporaryDirectory() as directory,patch('semantic_review.runtime_root',return_value=Path(directory)),patch('transcription_backend.crypt_key',side_effect=lambda raw,protect:b'protected' if protect else b'private-key'):
   semantic.save_settings({**semantic.DEFAULTS,'openai_model':'some-model'},'private-key','claude-key')
   raw=(Path(directory)/'semantic-review.json').read_text();self.assertNotIn('private-key',raw);self.assertNotIn('claude-key',raw)
   self.assertEqual(semantic.load_key('OpenAI'),'private-key')
