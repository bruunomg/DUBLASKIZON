import unittest
from verify_frozen_build import REQUIRED, verify_entries


class FrozenAuditTests(unittest.TestCase):
    def test_audioop_extension_layouts(self):
        for filename in ('audioop.pyd', 'audioop.cp312-win_amd64.pyd',
                         'audioop.cpython-312-x86_64-linux-gnu.so'):
            with self.subTest(filename=filename):
                missing,heavy=verify_entries((REQUIRED-{'audioop'})|{filename})
                self.assertEqual(missing,[])
                self.assertEqual(heavy,[])

    def test_missing_audioop_is_still_rejected(self):
        for other in ('_audioop.pyd','audioop_lts.pyd','audioop/other.pyd'):
            missing,_=verify_entries((REQUIRED-{'audioop'})|{other})
            self.assertEqual(missing,['audioop'])

    def test_external_heavy_extension_is_still_rejected(self):
        _,heavy=verify_entries(REQUIRED|{'torch.cp312-win_amd64.pyd'})
        self.assertIn('torch',heavy)

if __name__=='__main__':unittest.main()
