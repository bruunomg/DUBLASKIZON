import unittest
from unittest.mock import Mock, patch

import batch_tab
import directml_backend as dml
import dependency_setup as setup


class DirectMLBackendTests(unittest.TestCase):
    def test_portuguese_voice_cloning_is_accepted(self):
        for language in ('pt', 'pt-BR', 'Portuguese', 'Português (Brasil)'):
            dml.validate(language)

    def test_other_languages_and_design_mode_are_rejected(self):
        with self.assertRaises(ValueError):
            dml.validate('Russian')
        with self.assertRaises(ValueError):
            dml.validate('pt', 'design')

    def test_model_routes_to_isolated_directml_command(self):
        with patch.object(dml, 'inference_command', return_value=['dml-python']):
            # find_voice_command imports the function during this call.
            self.assertEqual(batch_tab.find_voice_command(dml.MODEL), ['dml-python'])

    def test_worker_has_directml_and_cpu_fallback(self):
        self.assertIn('torch_directml.device()', dml.WORKER)
        self.assertIn("device='cpu'", dml.WORKER)
        self.assertIn('Repetindo esta cena na CPU', dml.WORKER)
        self.assertIn('_torchcodec_available=False', dml.WORKER)

    def test_rx580_is_selected_before_cpu(self):
        with patch.object(setup, '_windows_display_names', return_value=['AMD Radeon RX 580']), \
             patch.object(setup.shutil, 'which', return_value=None), \
             patch.object(setup.subprocess, 'run', return_value=Mock(returncode=1,stdout='')):
            detected=setup.detect_processing()
        self.assertEqual(detected['variant'], 'directml')
        self.assertIn('RX 580', detected['gpu'])


if __name__ == '__main__':
    unittest.main()
