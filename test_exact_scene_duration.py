import unittest
from unittest.mock import patch
from audio_player import process_exact_original_duration
from audio_clip_timeline import AudioClip
class DurationTests(unittest.TestCase):
 def test_short_audio_is_padded_without_changing_voice(self):
  data=b'\x01\x00'*100
  track=dict(frames=data,sample_rate=1000,sample_width=2,channels=1)
  with patch('audio_player.process_scene_audio') as processor:raw,clips=process_exact_original_duration(track,None,.2)
  processor.assert_not_called();self.assertEqual(raw,data+b'\x00'*200)
 def test_long_audio_uses_same_duration_processor(self):
  track=dict(frames=b'\x01\x00'*1000,sample_rate=1000,sample_width=2,channels=1)
  def process(track,root,factor,preserve_clips):
   data=b'\x01\x00'*round(len(track['frames'])/2*factor)
   return data,(AudioClip(1,0,data),)
  with patch('audio_player.process_scene_audio',side_effect=process) as processor:raw,clips=process_exact_original_duration(track,None,.25)
  self.assertEqual(len(raw),500);self.assertEqual(processor.call_count,2)
if __name__=='__main__':unittest.main()
