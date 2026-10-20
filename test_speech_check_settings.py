import json
import tempfile
import unittest
from pathlib import Path
from speech_completeness import BATCH_DEFAULTS,load_batch_settings,save_batch_settings,verified_command
import test_speech_completeness as worker_fixtures


class SettingsTests(unittest.TestCase):
    def test_defaults_and_storage_preserve_legacy_flags(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(load_batch_settings(root),BATCH_DEFAULTS)
            path=Path(root)/'Dublaskizon_conferencia_fala.json'
            self.assertFalse(path.exists())
            path.write_text(json.dumps({'enabled':True,'other':'kept'}),encoding='utf-8')
            chosen=dict(BATCH_DEFAULTS,attempts=4,base_steps=48,recover_smaller=True)
            save_batch_settings(root,chosen)
            self.assertEqual(load_batch_settings(root),chosen)
            self.assertEqual(json.loads(path.read_text())['other'],'kept')
            with self.assertRaises(ValueError):save_batch_settings(root,dict(chosen,attempts=0))
            self.assertEqual(load_batch_settings(root),chosen)

    def test_selected_attempts_and_steps_reach_worker(self):
        with tempfile.TemporaryDirectory() as root:
            model,imports=worker_fixtures.CompletenessTests()._worker(root,['Venha aqui']*3+['Venha aqui agora'])
            model.verification_namespace.update(BATCH_VERIFICATION_BUDGET=True,BATCH_CHECK_SETTINGS=dict(BATCH_DEFAULTS,attempts=4,base_steps=40,step_increment=8))
            with imports:model.generate(text='Venha aqui agora',language='pt')
            self.assertEqual([c['num_step'] for c in model.calls],[40,48,56,64])
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_batch_defaults_preserve_two_attempts_and_review(self):
        with tempfile.TemporaryDirectory() as root:
            model,imports=worker_fixtures.CompletenessTests()._worker(root,['Venha aqui']*2,save_unconfirmed=True)
            model.verification_namespace.update(BATCH_VERIFICATION_BUDGET=True,BATCH_CHECK_SETTINGS=dict(BATCH_DEFAULTS))
            with imports:model.generate(text='Venha aqui agora',language='pt')
            self.assertEqual([c['num_step'] for c in model.calls],[32,48])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_config_applies_to_batch_command_only(self):
        with tempfile.TemporaryDirectory() as root:
            save_batch_settings(root,dict(BATCH_DEFAULTS,attempts=5))
            command=['python','-u','-c','print(1)','--model','edwixx/omnivoice-brpt-v15']
            batch=verified_command(command,'edwixx/omnivoice-brpt-v15',root,batch_budget=True)
            manual=verified_command(command,'edwixx/omnivoice-brpt-v15',root)
            self.assertIn("'attempts': 5",batch[3])
            self.assertIn('BATCH_CHECK_SETTINGS={}\n',manual[3])
            self.assertEqual(verified_command(command,'Qwen/Qwen3-TTS',root),command)

if __name__=='__main__':unittest.main()
