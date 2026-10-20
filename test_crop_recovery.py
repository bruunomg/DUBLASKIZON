import tempfile, threading, wave, unittest
from pathlib import Path
from unittest.mock import patch
from scene_parts import generate_part, run_command

class CropRecoveryTests(unittest.TestCase):
    def test_native_failure_retries_once_without_touching_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); ref=root/'original.wav'
            with wave.open(str(ref),'wb') as w:
                w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\x01\x01'*2400)
            original=ref.read_bytes(); calls=[]
            context={'root':root,'source':'dublado','scene':'test','kind':'original','config':{'model':'omnivoice-test','language':'pt','instruct':''},'infer_prefix':['python','-u','-c','pass']}
            def runner(cmd,cancel):
                calls.append(cmd)
                if len(calls)==1:raise RuntimeError('0xC0000005')
                self.assertIn('DUBLASKIZON_ASR_CPU_RECOVERY',cmd[3])
                Path(cmd[cmd.index('--output')+1]).write_bytes(original)
            with patch('voice_reference.protect_reference_command',side_effect=lambda c,m:c),patch('speech_completeness.verified_command',side_effect=lambda c,m,r:c):
                result=generate_part(context,'Uma frase completa.',ref,threading.Event(),runner)
            self.assertEqual(len(calls),2);self.assertEqual(ref.read_bytes(),original)
            self.assertTrue(result['audio'].is_file())
            self.assertIn('DUBLASKIZON_SAFE_REFERENCE',calls[0][3])

    def test_failure_saves_report_outside_temporary_output(self):
        import sys
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'.gerando_test'/'gerado.wav';output.parent.mkdir()
            with self.assertRaisesRegex(RuntimeError,'Relatório completo'):
                run_command([sys.executable,'-c',"print('diagnostico');raise SystemExit(4)",'--output',str(output)],threading.Event())
            reports=list((Path(folder)/'logs').glob('*.log'))
            self.assertEqual(len(reports),1)
            self.assertIn('diagnostico',reports[0].read_text())
