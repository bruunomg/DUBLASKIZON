import unittest
from translation_output import normalize_translation_output as clean
import semantic_review
class OutputTests(unittest.TestCase):
 def test_wrapper(self):
  result,warnings=clean('Kopf runter, verdammt!','"Kopf runter, verdammt!" translates to "Cabeça para baixo, puta merda!"')
  self.assertEqual(result,'Cabeça para baixo, puta merda!');self.assertTrue(warnings)
 def test_mismatch(self):
  with self.assertRaises(RuntimeError):clean('Other','"Source" translates to "Alvo"')
 def test_ambiguous(self):
  with self.assertRaises(RuntimeError):clean('Source','Here is the translation: Alvo')
 def test_inner_quotes(self):
  self.assertEqual(clean('Say hello','"Say hello" translates to "Diga "olá" agora!"')[0],'Diga "olá" agora!')
 def test_dialogue(self):
  self.assertEqual(clean('He said hello','Ele disse "olá".')[0],'Ele disse "olá".')
 def test_semantic_guard(self):
  report=semantic_review.validate_report({'needs_review':False,'issues':[],'corrected_translation':'"Hello" translates to "Olá"'},'Hello','Oi')
  self.assertEqual(report['corrected_translation'],'Olá');self.assertTrue(report['needs_review'])
if __name__=='__main__':unittest.main()
