import tempfile
import unittest
import wave
from pathlib import Path

from emotional_speech import (
    ExpressiveSpeechError, SegmentGenerationError, VoiceProfile,
    generate_expressive_speech, parse_emotion_tags,
)


def write_wav(path, *, rate=1000, width=2, frames=100, value=1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(bytes([value]) * width * frames)


class RecordingEngine:
    def __init__(self, fail_at=None, width=2, mismatch=False):
        self.calls = []
        self.fail_at, self.width, self.mismatch = fail_at, width, mismatch

    def synthesize(self, text, ref_audio_path, output_path):
        self.calls.append((text, ref_audio_path, output_path))
        write_wav(output_path, width=self.width,
                  rate=2000 if self.mismatch and len(self.calls) == 2 else 1000)
        if len(self.calls) == self.fail_at:
            raise RuntimeError("Falha simulada")


class EmotionalSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.neutral = self.root / "neutro.wav"
        self.happy = self.root / "alegre.wav"
        write_wav(self.neutral)
        write_wav(self.happy)
        self.profile = VoiceProfile({"neutro": self.neutral, "alegre": self.happy})
        self.output = self.root / "resultado.wav"

    def test_parser_user_example_and_neutral_prefix(self):
        self.assertEqual(parse_emotion_tags("Oi. [alegre] Olá tudo bem? [sussurro] Segredo nosso."), [
            {"emocao": "neutro", "texto_limpo": "Oi."},
            {"emocao": "alegre", "texto_limpo": "Olá tudo bem?"},
            {"emocao": "sussurro", "texto_limpo": "Segredo nosso."},
        ])

    def test_consecutive_tags_accents_and_legacy_markers(self):
        self.assertEqual(parse_emotion_tags("[RAÍVA][alegre] Olá [[EXPRESSAO:sussurro]] André!"), [
            {"emocao": "alegre", "texto_limpo": "Olá"},
            {"emocao": "sussurro", "texto_limpo": "André!"},
        ])

    def test_empty_text_and_tags_only_do_not_call_engine(self):
        for text in ("", "  ", "[alegre] [neutro]"):
            engine = RecordingEngine()
            with self.assertRaises(ExpressiveSpeechError):
                generate_expressive_speech(text, self.profile, engine, self.output)
            self.assertEqual(engine.calls, [])

    def test_unknown_and_missing_reference_fall_back(self):
        profile = VoiceProfile({"neutro": self.neutral, "grito": self.root / "missing.wav"})
        for emotion in ("grito", "desconhecida"):
            choice = profile.select_reference(emotion)
            self.assertEqual(choice.used_emotion, "neutro")
            self.assertEqual(choice.path, self.neutral)

    def test_neutral_reference_is_required(self):
        with self.assertRaises(ExpressiveSpeechError):
            VoiceProfile({"alegre": self.happy})
        self.neutral.unlink()
        with self.assertRaises(ExpressiveSpeechError):
            self.profile.select_reference("triste")

    def test_correct_reference_clean_text_pause_and_cleanup(self):
        engine, events = RecordingEngine(), []
        result = generate_expressive_speech(
            "[alegre] Olá! [sussurro] Vem cá.", self.profile, engine, self.output,
            on_progress=events.append,
        )
        self.assertEqual([(c[0], c[1]) for c in engine.calls],
                         [("Olá!", self.happy), ("Vem cá.", self.neutral)])
        self.assertEqual(result.references[1].used_emotion, "neutro")
        self.assertEqual([e.stage for e in events], ["generating", "completed"] * 2)
        with wave.open(str(self.output), "rb") as wav:
            self.assertEqual(wav.getnframes(), 350)  # 100 + 150 ms + 100
            audio = wav.readframes(350)
            self.assertEqual(audio[200:500], b"\x00" * 300)
        self.assertFalse(list(self.root.glob("dublaskizon_emotions_*")))
        self.assertTrue(all(not c[2].exists() for c in engine.calls))

    def test_eight_bit_silence_is_unsigned(self):
        generate_expressive_speech("Um [alegre] Dois", self.profile,
                                  RecordingEngine(width=1), self.output, pause_ms=10)
        with wave.open(str(self.output), "rb") as wav:
            data = wav.readframes(210)
            self.assertEqual(data[100:110], b"\x80" * 10)

    def test_segment_failure_preserves_old_output_and_cleans(self):
        self.output.write_bytes(b"saida anterior")
        with self.assertRaises(SegmentGenerationError) as error:
            generate_expressive_speech("Um [alegre] Dois", self.profile,
                                      RecordingEngine(fail_at=2), self.output)
        self.assertEqual(error.exception.index, 2)
        self.assertEqual(self.output.read_bytes(), b"saida anterior")
        self.assertFalse(list(self.root.glob("dublaskizon_emotions_*")))

    def test_mismatched_formats_do_not_corrupt_existing_output(self):
        self.output.write_bytes(b"saida anterior")
        with self.assertRaisesRegex(ExpressiveSpeechError, "formatos WAV diferentes"):
            generate_expressive_speech("Um [alegre] Dois", self.profile,
                                      RecordingEngine(mismatch=True), self.output)
        self.assertEqual(self.output.read_bytes(), b"saida anterior")
        self.assertFalse(list(self.root.glob("dublaskizon_emotions_*")))

    def test_normalizer_hook_resolves_format_difference(self):
        def normalize(source, destination):
            write_wav(destination)
        generate_expressive_speech("Um [alegre] Dois", self.profile,
                                  RecordingEngine(mismatch=True), self.output,
                                  normalizer=normalize, pause_ms=0)
        with wave.open(str(self.output), "rb") as wav:
            self.assertEqual(wav.getnframes(), 200)

    def test_output_cannot_replace_any_reference(self):
        with self.assertRaises(ExpressiveSpeechError):
            generate_expressive_speech("Oi", self.profile, RecordingEngine(), self.happy)

    def test_no_output_from_engine_is_recoverable(self):
        class EmptyEngine:
            def synthesize(self, text, ref_audio_path, output_path):
                pass
        with self.assertRaisesRegex(SegmentGenerationError, "não produziu"):
            generate_expressive_speech("Oi", self.profile, EmptyEngine(), self.output)

    def test_truncated_wav_is_rejected(self):
        class TruncatedEngine:
            def synthesize(self, text, ref_audio_path, output_path):
                write_wav(output_path)
                data = output_path.read_bytes()
                output_path.write_bytes(data[:-50])
        with self.assertRaisesRegex(ExpressiveSpeechError, "incompleto"):
            generate_expressive_speech("Oi", self.profile, TruncatedEngine(), self.output)
        self.assertFalse(self.output.exists())

    def test_invalid_pause_is_rejected(self):
        for pause in (-1, float("nan"), float("inf")):
            with self.assertRaises(ExpressiveSpeechError):
                generate_expressive_speech("Oi", self.profile, RecordingEngine(),
                                          self.output, pause_ms=pause)


if __name__ == "__main__":
    unittest.main()
