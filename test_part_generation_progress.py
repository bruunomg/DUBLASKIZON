import sys,threading,unittest
from scene_parts import run_command

class ProgressTests(unittest.TestCase):
    def test_real_process_output_updates_both_stages(self):
        states=[]
        run_command([sys.executable,'-u','-c',"print('Loading model');print('Generating audio');print('CONFERÊNCIA: conferindo palavras');print('Saved to result.wav')"],threading.Event(),lambda *state:states.append(state))
        self.assertTrue(any(clone==100 and dub>=90 for clone,dub,phase in states))
        self.assertTrue(any(dub==99 for clone,dub,phase in states))
