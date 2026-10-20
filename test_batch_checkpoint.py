import tempfile
import unittest
from pathlib import Path
from batch_checkpoint import load_checkpoint, record_checkpoint, plan_batch

class CheckpointTests(unittest.TestCase):
    def test_selected_queue_survives_restart_and_resumes_current(self):
        from batch_checkpoint import save_session, save_cursor, remaining_session
        with tempfile.TemporaryDirectory() as root:
            save_session(root,['b','d','f'])
            save_cursor(root,1)
            self.assertEqual(remaining_session(root),['d','f'])
            save_cursor(root,3)
            self.assertEqual(remaining_session(root),[])

    def test_restart_and_corrupt_last_line(self):
        with tempfile.TemporaryDirectory() as root:
            record_checkpoint(root, 'personagem/a', 'error')
            record_checkpoint(root, 'personagem/a', 'success')
            file=Path(root)/'revisoes/_controle_lote/clonagem.jsonl'
            with file.open('a') as stream: stream.write('{incomplete')
            self.assertEqual(load_checkpoint(root), {'personagem/a':'success'})

    def test_resume_selection_errors_and_missing_output(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root); (folder/'done.wav').write_bytes(b'x'*100)
            (folder/'empty.wav').write_bytes(b'')
            records={'bad':'error','missing':'success'}
            self.assertEqual(plan_batch(['done','bad','empty','missing'], records, folder,
                                       resume=True,ignore_errors=True), ['empty','missing'])
            self.assertEqual(plan_batch(['bad'], records, folder), ['bad'])
