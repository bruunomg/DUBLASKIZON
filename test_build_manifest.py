import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED_MODULES = {
    'warm_inference', 'speech_completeness', 'voice_reference', 'fish_backend', 'qwen_backend', 'native_emotions', 'emotional_speech', 'text_to_speech_tab', 'audio_frequency_separator_tab', 'batch_tab', 'review_tab', 'duration_converter_tab',
    'format_converter_tab', 'video_converter_tab', 'video_preview', 'video_audio_swap_tab',
    'wem_filter_tab', 'voice_clone_tab', 'personalized_dubbing_tab', 'audio_clone_preprocessor',
    'main', 'audio_player', 'audio_clip_timeline', 'scene_parts', 'find_panel', 'dependency_setup',
    'generation_progress', 'f5_backend', 'directml_backend', 'audio_translation',
    'voice_character', 'ui_theme', 'i18n', 'tkinterdnd2',
}
HEAVY_EXTERNAL_MODULES = {
    'scipy', 'librosa', 'sklearn', 'numba', 'llvmlite', 'torch', 'torchvision',
    'torchaudio', 'transformers', 'diffusers', 'gradio', 'pandas', 'pyarrow',
    'matplotlib', 'qwen_tts', 'bitsandbytes',
}


class BuildManifestTests(unittest.TestCase):
    def test_both_windows_build_scripts_include_app_modules_and_exclude_external_runtimes(self):
        for filename in ('build_exe.bat', 'build_exe_portatil_sem_python.bat'):
            text = (ROOT / filename).read_text(encoding='utf-8')
            with self.subTest(filename=filename):
                for module in REQUIRED_MODULES:
                    self.assertIn('--hidden-import ' + module, text)
                for module in HEAVY_EXTERNAL_MODULES:
                    self.assertIn('--exclude-module ' + module, text)
                self.assertIn('EXE ultrapassou 120 MB', text)
                self.assertIn('verify_frozen_build.py', text)

    def test_spec_matches_the_supported_build_manifest(self):
        text = (ROOT / 'Dublaskizon.spec').read_text(encoding='utf-8')
        tree = ast.parse(text)
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try: assignments[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError): pass
        self.assertTrue(REQUIRED_MODULES <= set(assignments['hiddenimports']))
        self.assertTrue(HEAVY_EXTERNAL_MODULES <= set(assignments['excluded_heavy_runtime']))
        self.assertIn('excludes=excluded_heavy_runtime', text)

    def test_frozen_auditor_detects_missing_and_accidentally_embedded_modules(self):
        import verify_frozen_build as verifier
        good = sorted(verifier.REQUIRED)
        self.assertEqual(verifier.verify_entries(good), ([], []))
        missing, heavy = verifier.verify_entries([entry for entry in good if entry != 'Dublaskizon'] + ['torch', 'torch.cuda'])
        self.assertEqual(missing, ['Dublaskizon'])
        self.assertEqual(heavy, ['torch'])


if __name__ == '__main__':
    unittest.main()
