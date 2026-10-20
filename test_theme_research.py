import unittest
from unittest.mock import patch
import theme_research as research
import semantic_review as api
import translation_context as context
class ThemeResearchTests(unittest.TestCase):
 def setUp(self):
  self.sources='Game\\nhttps://en.wikipedia.org/wiki/Game\\nThe Crystal guards the gate. Cristal is the Portuguese name.'
  self.data={'facts':[{'text':'A crystal guards the gate.','url':'https://en.wikipedia.org/wiki/Game','quote':'The Crystal guards the gate.'}],'instructions':'Preserve o tom de fantasia.','terms':[{'source':'Crystal','preferred':'Cristal','status':'official','reason':'Item de fantasia.','url':'https://en.wikipedia.org/wiki/Game','quote':'The Crystal guards the gate. Cristal is the Portuguese name.'}],'asr_hints':['Crystal','invented'],'uncertainties':[]}
 def test_evidence_and_asr_hints_validated(self):
  result=research.validate(self.data,self.sources);self.assertEqual(len(result['terms']),1);self.assertEqual(result['asr_hints'],['Crystal']);self.assertEqual(result['terms'][0]['status'],'official')
 def test_false_citation_and_official_claim_rejected_or_downgraded(self):
  self.data['terms'][0]['preferred']='Pedra';result=research.validate(self.data,self.sources);self.assertEqual(result['terms'][0]['status'],'proposed')
  self.data['terms'][0]['url']='https://fake.test';self.assertEqual(research.validate(self.data,self.sources)['terms'],[])
 def test_api_providers_use_shared_credentials_and_native_request(self):
  for provider in research.PROVIDERS[:4]:
   with patch('semantic_review.settings',return_value=api.DEFAULTS),patch('semantic_review.load_key',return_value='test'),patch('semantic_review.configuration_problem',return_value=''),patch('semantic_review.request_report',return_value=self.data) as request:
    result=research.analyze('Game','Jogo',self.sources,provider,lambda x:None,lambda:False)
   self.assertEqual(request.call_args.args[0],provider);self.assertEqual(len(result['terms']),1)
 def test_luna_and_sol_use_configured_models(self):
  for provider,expected in [('Luna — API','luna-test'),('Sol — API','sol-test')]:
   with patch('transcription_backend.api_settings',return_value={'luna_model':'luna-test','sol_model':'sol-test'}),patch('transcription_backend.load_key',return_value='test'),patch('transcription_backend.request_json',return_value=self.data) as request:
    research.analyze('Game','Jogo',self.sources,provider,lambda x:None,lambda:False)
   self.assertEqual(request.call_args.args[0],expected)
 def test_other_adaptation_terms_are_not_applied(self):
  self.data['terms'][0]['relevance']='other_adaptation'
  self.assertEqual(research.validate(self.data,self.sources)['terms'],[])
 def test_adaptive_queries_are_bounded_and_used(self):
  self.data['research_queries']=['subtitles recurring enemies terminology']*9
  result=research.validate(self.data,self.sources)
  self.assertEqual(len(result['research_queries']),5)
  sources='Page\nhttps://example.test/a\nCrystal is an item in the game.'
  with patch('theme_web_sources.collect_deep',side_effect=[sources,sources]) as collect,patch('theme_research.analyze',return_value=result):
   research.deep_research('Game','Jogo','Claude',lambda x:None,lambda:False)
  self.assertIn('subtitles recurring enemies terminology',collect.call_args.kwargs['focus'])
 def test_transcript_enrichment_preserves_manual_rules(self):
  profile={'title':'Game','domain':'Jogo','glossary':'Crystal => Minha escolha','instructions':'Minha regra','asr_hints':'Old','research_provider':'Claude — API'}
  result=research.validate(self.data,self.sources)
  with patch('theme_research.deep_research',return_value=(self.sources,result)) as run:
   updated=research.enrich_from_transcripts(profile,'The Crystal guards the gate.',lambda x:None,lambda:False)
  self.assertIn('Crystal => Minha escolha',updated['glossary']);self.assertIn('The Crystal guards the gate.',run.call_args.args[-1]);self.assertIn('Minha regra',updated['instructions'])
 def test_contextual_terms_require_literal_dialogue_and_high_confidence(self):
  data={'instructions':'Natural','contextual_terms':[{'source':'walker','preferred':'morto-vivo','scope':'agressor no diálogo','category':'Inimigo','reason':'Cena de ataque','confidence':'high','relevance':'target','quote':"Walker's got me!"}]}
  result=research.validate(data,'',"Walker's got me!")
  self.assertEqual(result['terms'][0]['origin'],'ai');self.assertIn('IA —',research.glossary_text(result))
  self.assertEqual(research.validate(data,'','Other dialogue')['terms'],[])
  data['contextual_terms'][0]['confidence']='low';self.assertEqual(research.validate(data,'',"Walker's got me!")['terms'],[])
 def test_provenance_manual_changes_and_unknown_legacy(self):
  old='# IA — proposta contextual\ncrystal => Cristal'
  updated=research.mark_manual_changes(old.replace('Cristal','Pedra'),{'crystal => Cristal'})
  self.assertIn('USUÁRIO —',updated);self.assertNotIn('# IA —',updated)
  self.assertIn('ORIGEM ANTERIOR',research.annotate_existing('glass => Vidro'))
 def test_cancelled_does_not_call_api(self):
  with patch('semantic_review.request_report') as request:
   with self.assertRaises(RuntimeError):research.analyze('Game','Jogo',self.sources,'Claude',lambda x:None,lambda:True)
   request.assert_not_called()
 def test_provider_persists_and_context_flows_to_translation(self):
  profile=context.normalized_context({'title':'Game','research_provider':'Claude — API','instructions':'Preserve o tom de fantasia.','glossary':'Crystal => Cristal','asr_hints':'Crystal','research':self.sources})
  self.assertEqual(profile['research_provider'],'Claude — API');self.assertIn('Crystal => Cristal',context.context_instruction(profile));self.assertEqual(context.transcription_hint(profile),'Crystal')
class DeepResearchTests(unittest.TestCase):
 def result(self,terms):return {'facts':[],'instructions':'Contexto específico','terms':[{'source':x,'preferred':'PT '+x,'reason':'Objeto da obra','category':'Objeto','scope':'Somente item do jogo','url':'https://example.test','quote':x+' is an item in the game.'} for x in terms],'asr_hints':terms,'uncertainties':[]}
 def test_merge_keeps_distinct_terms_and_excludes_conflicts(self):
  first=self.result(['Crystal','Sword']);second=self.result(['Crystal','Shield']);second['terms'][0]['preferred']='Outra tradução'
  merged=research.merge_results([first,second]);self.assertEqual({x['source'] for x in merged['terms']},{'Sword','Shield'});self.assertTrue(any('conflitantes' in note for note in merged['uncertainties']))
  self.assertIn('Somente item do jogo',research.glossary_text(merged))
 def test_deep_pipeline_refines_sparse_output(self):
  sources='Theme\n\nPage\nhttps://example.test/a\nCrystal is an item in the game.'
  extra='Theme\n\nOther\nhttps://example.test/b\nSword is an item in the game.'
  with patch('theme_web_sources.collect_deep',side_effect=[sources,extra]) as collect,patch('theme_research.analyze',side_effect=[self.result(['Crystal']),self.result(['Sword'])]) as analyze:
   returned,result=research.deep_research('Game','Jogo','Claude — API',lambda x:None,lambda:False)
  self.assertEqual(collect.call_count,2);self.assertEqual(analyze.call_count,2);self.assertEqual(len(result['terms']),2);self.assertIn('https://example.test/b',returned)
 def test_deep_results_not_padded_to_target_count(self):
  result=research.merge_results([self.result(['Crystal'])]);self.assertEqual(len(result['terms']),1);self.assertTrue(any('poucos termos' in note for note in result['uncertainties']))
if __name__=='__main__':unittest.main()
