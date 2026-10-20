import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from speech_presence import SpeechDetector, speech_preflight_batch

class PresenceTests(unittest.TestCase):
    def detector(self,response):
        detector=SpeechDetector()
        detector.process=SimpleNamespace(stdin=Mock())
        detector.responses.put(response)
        return detector

    def test_absent_and_present_speech_protocol(self):
        for expected in (False,True):
            detector=self.detector(json.dumps({'speech':expected}))
            self.assertEqual(detector.detect('original.wav'),expected)
            detector.process.stdin.write.assert_called_once()

    def test_detection_error_is_not_no_speech(self):
        detector=self.detector(json.dumps({'error':'decoder error'}))
        with self.assertRaisesRegex(RuntimeError,'decoder error'):
            detector.detect('original.wav')

    def test_cancel_does_not_wait_for_response(self):
        detector=self.detector(None)
        with self.assertRaisesRegex(RuntimeError,'cancelada'):
            detector.detect('original.wav',lambda:True)

    def test_detector_is_closed_even_if_batch_fails(self):
        app=SimpleNamespace()
        closed=[]
        @speech_preflight_batch
        def worker(self):
            self._speech_detector.close=lambda:closed.append(True)
            raise ValueError('failed')
        with self.assertRaises(ValueError): worker(app)
        self.assertEqual(closed,[True])
        self.assertIsNone(app._speech_detector)
