import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from review_tab import ReviewApp,DEFAULT_CONFIG

class RejectedTests(unittest.TestCase):
    def test_evaluate_first_preserves_other_scenes(self):
        app=SimpleNamespace(stems=['a','b','c'], default_stems=['a','b','c'],
                            scene_sort_mode='evaluate_first',
                            state={'a':{'status':'aprovada'},'b':{'status':'avaliar'}},
                            review_state_key=lambda stem:stem)
        self.assertEqual(ReviewApp._ordered_scene_stems(app), ['b','c','a'])

    def test_only_rejected_scenes_are_enqueued_in_list_order(self):
        jobs=[]
        app=SimpleNamespace(busy=False,stems=['a','b','c'],state={'a':{'status':'rejeitada'},'b':{'status':'aprovada'},'c':{'status':'rejeitada'}},
            review_state_key=lambda stem:stem,root=SimpleNamespace(),_next_rejected=Mock())
        app.config={}
        for key in ('auto_open_var','request_r_var','align_original_var','preserve_original_voice_var','request_character_var','request_translation_var','translate_missing_var'):
            setattr(app,key,SimpleNamespace(get=lambda:'0'))
        with patch('review_tab.messagebox.askyesno',return_value=True):ReviewApp.redub_all_rejected(app)
        self.assertEqual(app._rejected_queue,['a','c'])
        app._next_rejected.assert_called_once()

    def test_next_scene_waits_for_running_scene(self):
        app=SimpleNamespace(busy=True,_rejected_queue=['b'],root=SimpleNamespace(after=Mock()),_next_rejected=Mock())
        ReviewApp._next_rejected(app)
        self.assertEqual(app._rejected_queue,['b'])
        app.root.after.assert_called_once()

    def test_completed_rejected_scene_becomes_evaluate(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'scene.wav'
            app=SimpleNamespace(busy=True,_rejected_active='scene',current_output_dir=lambda:Path(folder),
                append_regen_log=Mock(),finish_regen_clock=Mock(),update_record=Mock(),status_var=SimpleNamespace(set=Mock()),
                audio_player=SimpleNamespace(refresh_current_scene=Mock()),set_action_state=Mock(),update_details=Mock(),config={'auto_open_after_generate':False})
            ReviewApp._generation_done(app,'scene',target)
            self.assertFalse(app.busy)
            self.assertEqual(app.update_record.call_args.args[:2],('scene','avaliar'))

    def test_default_auto_open_and_r_prompt_disabled(self):
        self.assertFalse(DEFAULT_CONFIG['auto_open_after_generate'])
        self.assertFalse(DEFAULT_CONFIG['ask_r_pronunciation'])
