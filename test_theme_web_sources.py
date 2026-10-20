import io,unittest
from unittest.mock import patch
import theme_web_sources as web
class WebSourcesTests(unittest.TestCase):
 def test_non_wikipedia_sources_attributed_and_bounded(self):
  rss=b'<rss><channel><item><title>Moss official guide</title><link>https://example.com/moss</link><description>Moss Crystal is an item in this fantasy game. Context and terminology guide.</description></item></channel></rss>'
  documents,errors=web.search('Moss',lambda *a,**k:io.BytesIO(rss))
  self.assertEqual(len(documents),1);self.assertIn('https://example.com/moss',documents[0]);self.assertIn('Resumo do mecanismo',documents[0])
 def test_partial_web_failure_keeps_wikipedia_and_no_rules_invented(self):
  with patch('theme_web_sources.search',return_value=([],['Busca indisponível'])),patch('translation_context.research_theme',return_value='Wikipedia references'):
   result=web.collect('Moss');self.assertIn('Wikipedia references',result);self.assertIn('Limitações',result)
 def test_cancel_stops_source_collection(self):
  with self.assertRaises(RuntimeError):web.search('Moss',cancelled=lambda:True)
class RelevanceTests(unittest.TestCase):
 def test_rejects_generic_walking_results(self):
  self.assertFalse(web.relevant('The Walking Dead Onslaught','Walking exercise and walking benefits'))
  self.assertTrue(web.relevant('The Walking Dead Onslaught','The Walking Dead Onslaught combat dialogue'))
 def test_article_excludes_script_and_navigation(self):
  parser=web.ArticleText();parser.feed('<nav>Menu</nav><p>Actual dialogue</p><script>ignore()</script>')
  self.assertEqual(parser.parts,['Actual dialogue'])
 def test_page_failure_keeps_original_attributed_summary(self):
  document='Game\nhttps://example.test/game\n[Resumo do mecanismo] Game summary'
  with patch('theme_web_sources.public_url',side_effect=ValueError('blocked')):
   self.assertEqual(web.read_documents('Game',[document],lambda:False,lambda x:None),[document])
if __name__=='__main__':unittest.main()
