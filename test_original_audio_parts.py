import tempfile, threading, wave, unittest
from pathlib import Path
from scene_parts import generate_part, list_parts

class OriginalPartsTests(unittest.TestCase):
    def test_original_copy_is_published_with_generated_part(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);reference=root/'recorte.wav'
            with wave.open(str(reference),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
                wav.writeframes(b'\x01\x01'*2400)
            before=reference.read_bytes()
            context={'root':root,'source':'dublado','scene':'cena','kind':'original',
                     'config':{'model':'fake','language':'pt','instruct':''},'infer_prefix':['fake']}
            def runner(command,cancel):
                self.assertEqual(command[command.index('--ref_audio')+1],str(reference))
                Path(command[command.index('--output')+1]).write_bytes(before)
            result=generate_part(context,'Somente esta parte.',reference,threading.Event(),runner)
            self.assertEqual(reference.read_bytes(),before)
            self.assertEqual(result['reference'].read_bytes(),before)
            self.assertEqual(list_parts(result['audio'].parent.parent)[0]['kind'],'original')
