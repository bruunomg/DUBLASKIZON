import tempfile
import unittest
import wave
from pathlib import Path
from audio_versions import archive, switch


def wav(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,24000,0,'NONE','not compressed'))
        output.writeframes(value.to_bytes(2,'little',signed=True)*2400)
    return path.read_bytes()


class RecoveryTests(unittest.TestCase):
    def test_external_output_keeps_its_exact_location(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'project';root.mkdir()
            target=base/'external/scene.wav'
            previous=wav(target,10);archive(target,root);latest=wav(target,20)
            switch(target,root);self.assertEqual(target.read_bytes(),previous)
            switch(target,root,latest=True);self.assertEqual(target.read_bytes(),latest)

    def test_round_trip_same_path_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'dublados personalizados/Deadpool/123.wav'
            previous=wav(target,10);archive(target,root);latest=wav(target,20)
            self.assertEqual(switch(target,root),target)
            self.assertEqual(target.read_bytes(),previous)
            # No UI session state is needed to undo the recovery.
            switch(target,root,latest=True)
            self.assertEqual(target.read_bytes(),latest)

    def test_existing_legacy_revision_and_scene_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'dublado/A/123.wav'
            previous=wav(root/'revisoes/A/123_v01.wav',10)
            wav(root/'revisoes/B/123_v99.wav',99)
            latest=wav(target,20)
            switch(target,root);self.assertEqual(target.read_bytes(),previous)
            switch(target,root,latest=True);self.assertEqual(target.read_bytes(),latest)

    def test_new_generation_is_not_overwritten_by_stale_undo(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'dublado/123.wav'
            wav(target,10);archive(target,root);wav(target,20);switch(target,root)
            newest=wav(target,30)
            with self.assertRaises(ValueError):switch(target,root,latest=True)
            self.assertEqual(target.read_bytes(),newest)

    def test_repeated_recovery_does_not_erase_latest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'dublado/123.wav'
            wav(target,10);archive(target,root);latest=wav(target,20)
            switch(target,root)
            with self.assertRaises(ValueError):switch(target,root)
            switch(target,root,latest=True)
            self.assertEqual(target.read_bytes(),latest)

    def test_missing_or_corrupt_backup_preserves_current(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'dublado/123.wav';current=wav(target,20)
            with self.assertRaises(ValueError):switch(target,root)
            bad=root/'revisoes/123_v01.wav';bad.parent.mkdir(exist_ok=True);bad.write_bytes(b'invalid')
            with self.assertRaises((ValueError,wave.Error,EOFError)):switch(target,root)
            self.assertEqual(target.read_bytes(),current)

    def test_original_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'WAV ORIGINAIS/123.wav';before=wav(target,10)
            with self.assertRaises(ValueError):switch(target,root)
            self.assertEqual(target.read_bytes(),before)

if __name__=='__main__':unittest.main()
