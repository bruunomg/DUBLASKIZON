import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from repetition_prosody import reference_repetition_profile


class OriginalProsodyTests(unittest.TestCase):
    def test_original_accents_change_profile_without_randomness(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'original.wav'
            samples=[]
            for duration,gain,pause in ((.1,.15,.12),(.2,.3,.2),(.15,.2,.05)):
                t=np.arange(round(16000*duration))/16000
                samples.extend(gain*np.sin(2*np.pi*200*t))
                samples.extend(np.zeros(round(16000*pause)))
            with wave.open(str(target),'wb') as output:
                output.setparams((1,2,16000,0,'NONE','not compressed'))
                output.writeframes((np.array(samples)*32767).astype('<i2').tobytes())
            # Test the same reader contract without requiring a managed engine.
            import sys,types
            from unittest.mock import patch
            reader=types.SimpleNamespace(read=lambda *a,**k:(np.array(samples,dtype='float32')[:,None],16000))
            with patch.dict(sys.modules,{'soundfile':reader}):
                profile=reference_repetition_profile(target,14)
                self.assertEqual(profile,reference_repetition_profile(target,14))
            self.assertEqual(len(profile),14)
            self.assertGreater(max(p['gain'] for p in profile)-min(p['gain'] for p in profile),.2)
            self.assertGreater(max(p['pause'] for p in profile)-min(p['pause'] for p in profile),.05)
            self.assertTrue(all(.8<=p['rate']<=1.25 for p in profile))

    def test_absent_reference_preserves_count_with_neutral_profile(self):
        profile=reference_repetition_profile(None,7)
        self.assertEqual(len(profile),7)
        self.assertTrue(all(p=={'gain':1.,'rate':1.,'pause':.15} for p in profile))

if __name__=='__main__':unittest.main()
