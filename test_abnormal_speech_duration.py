import unittest
from speech_completeness import recover_abnormal_duration
from voice_reference import WORKER_CODE

class DurationGuardTests(unittest.TestCase):
 def test_extreme_duration_recovers_before_synthesis(self):
  text='Este é o set de filmagem de Medal of Honor Airborne.'
  self.assertLess(recover_abnormal_duration(text,87.2),6)
  self.assertIsNone(recover_abnormal_duration(text,5.8))
 def test_reference_requires_speech_density_and_variety(self):
  start=WORKER_CODE.index('def reference_has_speech');end=WORKER_CODE.index('def _complete_prompt')
  namespace={};exec(WORKER_CODE[start:end],namespace);valid=namespace['reference_has_speech']
  self.assertFalse(valid('This',8))
  self.assertFalse(valid('Música '*20,8))
  self.assertTrue(valid('This is the filming set for the game.',8))

class UnspacedSpeechTests(unittest.TestCase):
 def validator(self):
  start=WORKER_CODE.index('def reference_has_speech');end=WORKER_CODE.index('def _complete_prompt')
  namespace={};exec(WORKER_CODE[start:end],namespace);return namespace['reference_has_speech']
 def test_chinese_dialogue_is_not_counted_as_one_latin_word(self):
  valid=self.validator()
  self.assertTrue(valid('星星偷走了太阳，世界就要崩溃了，我们该怎么办？',8))
  self.assertTrue(valid('これは本当に危険です。今すぐここから逃げましょう。',8))
 def test_sparse_or_repetitive_output_still_rejected(self):
  valid=self.validator()
  self.assertFalse(valid('太阳',8));self.assertFalse(valid('哈'*40,8));self.assertFalse(valid('',8));self.assertFalse(valid('This',8));self.assertFalse(valid('Música '*20,8))
