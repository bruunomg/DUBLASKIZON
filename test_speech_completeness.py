import json
from pathlib import Path
import tempfile
import unittest
from speech_completeness import compare_speech, split_speech, verified_command


class CompletenessTests(unittest.TestCase):
    def test_context_interval_excludes_auxiliary_and_extra_words(self):
        from speech_completeness import matched_text_interval
        chunks=[{'text':'Ai','timestamp':(0,.2)}, {'text':'Mas','timestamp':(.3,.5)},
                {'text':'quando','timestamp':(.5,.8)}, {'text':'tento','timestamp':(.8,1.1)},
                {'text':'me','timestamp':(1.1,1.2)}, {'text':'lembrar','timestamp':(1.2,1.6)}]
        interval=matched_text_interval('Mas quando tento me lembrar',chunks,2)
        self.assertAlmostEqual(interval[0],.275)
        self.assertAlmostEqual(interval[1],1.625)
        chunks[3]['text']='tenta'
        self.assertIsNone(matched_text_interval('Mas quando tento me lembrar',chunks,2))

    def test_repetitions_preserve_count_and_surrounding_text(self):
        from speech_completeness import repetition_plan
        self.assertEqual(repetition_plan('Mas eu, eu, eu, eu.'), [('text','Mas',1),('repeat','eu',4)])
        self.assertEqual(repetition_plan('não, não, não. Pare!'), [('repeat','não',3),('text','Pare!',1)])
        self.assertEqual(repetition_plan('Eu quero falar.'), [])

    def test_repetition_word_is_isolated_without_carrier_words(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports=self._worker(folder, [])
            model._asr_pipe=lambda *args,**kwargs:{'text':'Eu estou aqui para conversar com você.', 'chunks':[
                {'text':'Eu','timestamp':(0,.002)}, {'text':'estou','timestamp':(.004,.006)}]}
            with imports:result=model.generate(text='eu, eu, eu.',language='pt')
            self.assertEqual(len(model.calls),2)
            self.assertEqual(len(result[0]),3*96+2*3600)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_repetition_discards_extra_leading_word(self):
        with tempfile.TemporaryDirectory() as folder:
            model,imports=self._worker(folder,[])
            model._asr_pipe=lambda *args,**kwargs:{'text':'Pai eu estou aqui', 'chunks':[
                {'text':'Pai','timestamp':(0,.002)}, {'text':'eu','timestamp':(.002,.004)},
                {'text':'estou','timestamp':(.004,.006)}]}
            with imports:result=model.generate(text='eu, eu, eu.',language='pt')
            self.assertEqual(len(result[0]),3*48+2*3600)
            self.assertGreaterEqual(model.calls[0]['duration'],3)

    def test_too_short_incomplete_audio_gets_duration_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            model,imports=self._worker(folder,['Nada','Eu preciso falar com você agora.'])
            with imports:model.generate(text='Eu preciso falar com você agora.',language='pt')
            self.assertGreaterEqual(model.calls[1]['duration'],1)

    def test_short_phrases_keep_context_without_losing_text(self):
        from speech_completeness import contextual_parts
        text='Coronel Scott Webb, relatório pós-operação. 27 de março de 1945. A guerra terminou.'
        self.assertEqual(contextual_parts(split_speech(text)), [text])

    def test_normal_review_prepares_reference_once(self):
        with tempfile.TemporaryDirectory() as folder:
            command=['python','-u','-c','print(1)']
            result=verified_command(command,'edwixx/omnivoice-brpt-v15',folder)
            self.assertIn('OmniVoice.create_voice_clone_prompt = _complete_prompt',result[3])
            from voice_reference import protect_reference_command
            result=verified_command(protect_reference_command(command,'edwixx/omnivoice-brpt-v15'),'edwixx/omnivoice-brpt-v15',folder)
            self.assertEqual(result[3].count('OmniVoice.create_voice_clone_prompt = _complete_prompt'),1)

    def test_extra_cut_only_isolated_timestamped_insertions(self):
        from speech_completeness import extra_word_intervals
        chunks = [{'text':'Olá','timestamp':(0,.3)},
                  {'text':'Change','timestamp':(.4,.7)},
                  {'text':'amigo','timestamp':(.8,1.2)}]
        self.assertEqual(extra_word_intervals('Olá amigo', chunks), [(.4,.7)])
        self.assertEqual(extra_word_intervals('Olá querido amigo', chunks), [])
        chunks[1]['timestamp']=(.2,.7)
        self.assertEqual(extra_word_intervals('Olá amigo', chunks), [])

    def test_worker_cuts_extra_and_rechecks_audio(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, [])
            replies=iter([{'text':'Olá Change amigo'},
                          {'text':'Olá Change amigo','chunks':[
                              {'text':'Olá','timestamp':(0,.002)},
                              {'text':'Change','timestamp':(.003,.005)},
                              {'text':'amigo','timestamp':(.006,.01)}]},
                          {'text':'Olá amigo'}])
            model._asr_pipe=lambda *args, **kwargs:next(replies)
            with imports:
                result=model.generate(text='Olá amigo',language='pt')
            self.assertEqual(len(result[0]),240-48)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])
            self.assertEqual(len(model.calls),1)

    def test_inserted_words_are_not_complete(self):
        for heard in ('Change Olá amigo', 'Olá Change amigo', 'Olá amigo the end'):
            verdict = compare_speech('Olá amigo', heard)
            self.assertNotEqual(verdict['status'], 'complete')
            self.assertTrue(verdict['extra'])

    def test_extra_words_retry_and_keep_clean_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Change Olá amigo', 'Olá amigo'], save_unconfirmed=True)
            with imports:
                model.generate(text='Olá amigo', language='pt')
            self.assertEqual(len(model.calls), 2)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_extra_words_save_valid_audio_for_review_after_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Olá amigo the end'] * 3, save_unconfirmed=True)
            with imports:
                result = model.generate(text='Olá amigo', language='pt')
            self.assertEqual(len(result[0]), 240)
            self.assertEqual(len(model.calls), 3)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])
            reports = list(Path(folder).glob('*.json'))
            self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8'))['result']['extra'], ['the', 'end'])

    def test_extra_words_still_fail_when_all_audio_is_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, [], audios=[None, [], None], save_unconfirmed=True)
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text='Olá amigo', language='pt')
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])

    def test_alignment_warning_keeps_existing_review_notes(self):
        from speech_completeness import mark_pending_review, publish_review_report, review_report_path, needs_review
        with tempfile.TemporaryDirectory() as root:
            project=Path(root); temporary=project/'dublado/temp.wav'; target=project/'dublado/final.wav'
            mark_pending_review(temporary,project,'duração não validada')
            mark_pending_review(temporary,project,'segunda observação')
            publish_review_report(temporary,target)
            self.assertTrue(needs_review(target))
            self.assertEqual(len(json.loads(review_report_path(target).read_text(encoding='utf-8'))['notes']),2)

    def test_batch_budget_stops_recursive_regeneration(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Legenda por Sônia', 'Legenda por Sônia'], save_unconfirmed=True)
            model.verification_namespace['BATCH_VERIFICATION_BUDGET'] = True
            with imports:
                model.generate(text='Preciso lembrar que você está aqui para melhorar a experiência.', language='pt')
            self.assertEqual(len(model.calls), 2)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_long_audio_verification_uses_short_windows(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Olá', 'amigo'], audios=[np.ones(31*16000,dtype=np.float32)])
            with imports:
                model.generate(text='Olá amigo',language='pt',duration=31)
            self.assertEqual(len(model.calls),1)

    def test_abnormal_estimate_is_corrected_before_model_generates(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            model,imports=self._worker(folder,['Venha aqui agora'])
            model.audio_tokenizer=SimpleNamespace(config=SimpleNamespace(frame_rate=50))
            model._estimate_target_tokens=lambda *a,**k:4360
            prompt=SimpleNamespace(ref_text='This',ref_audio_tokens=SimpleNamespace(shape=(8,400)))
            with imports:model.generate(text='Venha aqui agora',language='pt',voice_clone_prompt=prompt)
            self.assertEqual(len(model.calls),1)
            self.assertEqual(model.calls[0]['duration'],1.5)

    def test_abnormal_audio_retries_without_transcribing_it(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model,imports=self._worker(folder,['Olá amigo'],audios=[np.ones(31*24000,dtype=np.float32),np.ones(240,dtype=np.float32)])
            with imports:model.generate(text='Olá amigo',language='pt')
            self.assertEqual(len(model.calls),2)
            self.assertEqual(model.calls[-1]['duration'],1.5)

    def test_personalized_ellipsis_preserves_words_and_pauses(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Max', 'Ou Max', 'Você está certo'])
            model.verification_namespace['PERSONALIZED_TEXT_PAUSES'] = True
            with imports:
                result = model.generate(text='Max... Ou Max… Você está certo!', language='pt')
            self.assertEqual([call['text'] for call in model.calls],
                             ['Max', 'Ou Max', 'Você está certo!'])
            self.assertEqual(len(result[0]), 3 * 240 + 2 * round(24000 * .45))

    def test_complete_and_accents(self):
        self.assertEqual(compare_speech('André, venha aqui!', 'andre venha aqui')['status'], 'complete')

    def test_missing_last_word(self):
        result = compare_speech('Eu preciso falar com você agora.', 'Eu preciso falar com você')
        self.assertEqual(result['status'], 'suspect')
        self.assertEqual(result['missing'], ['agora'])

    def test_missing_middle_and_repeated_word(self):
        self.assertEqual(compare_speech('venha venha aqui', 'venha aqui')['missing'], ['venha'])
        self.assertEqual(compare_speech('Eu quero conversar com você.', 'Eu quero com você')['missing'], ['conversar'])

    def test_wrong_recognition_is_uncertain(self):
        self.assertEqual(compare_speech('Nanoo nanoo shazbot', 'Não não Chazbot')['status'], 'uncertain')
        self.assertEqual(compare_speech('Olá', '')['status'], 'uncertain')

    def test_cut_word_is_not_accepted(self):
        self.assertNotEqual(compare_speech('Ele saiu da casa', 'Ele saiu da cas')['status'], 'complete')

    def test_contraction_equivalent(self):
        self.assertEqual(compare_speech('Vem pra cá', 'Vem para cá')['status'], 'complete')

    def test_nonverbal_tags_are_not_spoken_words(self):
        self.assertEqual(compare_speech('[laughter] Venha aqui', 'Venha aqui')['status'], 'complete')

    def _worker(self, folder, transcripts, audios=None, save_unconfirmed=False):
        import types
        from unittest.mock import patch
        import numpy as np
        from speech_completeness import WORKER_CODE
        class Model:
            sampling_rate = 24000
            def __init__(self):
                self.calls = []
                self.audio_values = iter(audios) if audios is not None else None
                values = iter(transcripts)
                self._asr_pipe = lambda *_args, **_kwargs: ({'text':'', 'chunks':[]} if _kwargs.get('return_timestamps') else {'text': next(values)})
            def generate(self, **kwargs):
                self.calls.append(kwargs)
                return [next(self.audio_values) if self.audio_values is not None else np.ones(240, dtype=np.float32)]
        modules = {
            'soundfile': types.SimpleNamespace(write=lambda path, *_args: Path(path).write_bytes(b'audio')),
            'librosa': types.SimpleNamespace(resample=lambda pcm, **_kwargs: pcm),
            'omnivoice.models.omnivoice': types.SimpleNamespace(OmniVoice=Model),
        }
        with patch.dict('sys.modules', modules):
            namespace = {'COMPLETENESS_REVIEW_DIR': folder, 'SAVE_UNCONFIRMED': save_unconfirmed}
            exec(WORKER_CODE, namespace)
            model = Model()
            model.verification_namespace = namespace
            return model, patch.dict('sys.modules', modules)

    def test_worker_retries_then_accepts(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Venha aqui', 'Venha aqui agora'])
            with imports:
                result = model.generate(text='Venha aqui agora', language='pt')
            self.assertEqual([call['num_step'] for call in model.calls], [32, 48])
            self.assertEqual(len(result), 1)
            self.assertFalse(list(Path(folder).iterdir()))

    def test_recovery_preserves_requested_speaking_rate(self):
        for speed in (1.0, 1.15):
            with self.subTest(speed=speed), tempfile.TemporaryDirectory() as folder:
                model, imports = self._worker(folder, ['Venha aqui', 'Venha aqui', 'Venha aqui agora'])
                with imports:
                    model.generate(text='Venha aqui agora', language='pt', speed=speed)
                self.assertEqual([call['speed'] for call in model.calls], [speed] * 3)
                self.assertEqual([call['num_step'] for call in model.calls], [32, 48, 64])

    def test_empty_generation_retries_without_calling_asr_on_empty(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Venha aqui agora'], [[], np.ones(240)])
            with imports:
                result = model.generate(text='Venha aqui agora', language='pt')
            self.assertEqual(len(model.calls), 2)
            self.assertEqual(len(result[0]), 240)

    def test_all_empty_reports_review_without_crash_or_fake_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = Path(folder) / 'anterior.wav'
            previous.write_bytes(b'original intacto')
            model, imports = self._worker(folder, [], [None, [], None])
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text='Venha aqui agora', language='pt')
            self.assertEqual(len(model.calls), 3)
            self.assertEqual(previous.read_bytes(), b'original intacto')
            self.assertFalse(list(Path(folder).glob('fala_*.wav')))
            self.assertEqual(len(list(Path(folder).glob('fala_*.json'))), 1)

    def test_silence_and_invalid_samples_are_retried(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Venha aqui agora'], [np.zeros(240), [float('nan')], np.ones(240)])
            with imports:
                model.generate(text='Venha aqui agora', language='pt')
            self.assertEqual(len(model.calls), 3)

    def test_empty_long_phrase_uses_adaptive_recovery(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Ele precisa destruir', 'todos os caminhões'],
                                          [[], [], [], np.ones(240), np.ones(240)])
            with imports:
                result = model.generate(text='Ele precisa destruir todos os caminhões', language='pt')
            self.assertEqual(len(model.calls), 5)
            self.assertGreater(len(result[0]), 480)

    def test_recovery_avoids_hanging_article_and_preserves_words(self):
        from speech_completeness import recovery_parts
        text = 'Eles estão carregando a água pesada no depósito.'
        parts = recovery_parts(text)
        self.assertEqual(' '.join(parts), text)
        self.assertEqual(parts, ['Eles estão carregando', 'a água pesada no depósito.'])
        self.assertIsNone(recovery_parts('Vem aqui agora.'))

    def test_worker_stops_and_retains_review_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Venha aqui'] * 3)
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text='Venha aqui agora', language='pt')
            self.assertEqual(len(model.calls), 3)
            reports = list(Path(folder).glob('*.json'))
            self.assertEqual(len(reports), 1)
            self.assertEqual(json.loads(reports[0].read_text(encoding='utf-8'))['result']['missing'], ['agora'])

    def test_unconfirmed_name_saves_best_audio_with_review_not_confirmation(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['É hora de cavar Matias', 'hora de cavar', 'É hora de cavar Matias'],
                [np.full(240, .1), np.full(240, .2), np.full(240, .3)], save_unconfirmed=True)
            with imports:
                result = model.generate(text='É hora de cavar Mathias', language='pt')
            np.testing.assert_allclose(result[0], .1)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_even_save_policy_cannot_publish_all_empty_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, [], [None, [], None], save_unconfirmed=True)
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text='Venha aqui agora', language='pt')
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])

    def test_valid_parent_is_not_split_into_tiny_fragments(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['transcricao incerta'] * 3,
                [np.ones(240)] * 3 + [None, []], save_unconfirmed=True)
            with imports:
                result = model.generate(text='Eles precisam destruir todos os caminhões', language='pt')
            self.assertEqual(len(result[0]), 240)
            self.assertEqual(len(model.calls), 3)
            self.assertTrue(model.verification_namespace['_DUBLASKIZON_TEXT_AVAILABLE'])
            self.assertFalse(model.verification_namespace['_DUBLASKIZON_TEXT_COMPLETE'])

    def test_review_report_follows_output_and_next_confirmed_generation_clears_it(self):
        from speech_completeness import publish_review_report, needs_review
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'temporary.wav', Path(folder) / 'final.wav'
            source.with_suffix('.conferencia.json').write_text('{"needs_review":true}')
            self.assertTrue(publish_review_report(source, target))
            self.assertTrue(needs_review(target))
            source.with_suffix('.conferencia.json').write_text('{"needs_review":false}')
            self.assertFalse(publish_review_report(source, target))

    def test_reports_stay_out_of_audio_folders_and_preserve_hierarchy(self):
        from speech_completeness import publish_review_report, review_report_path, needs_review
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            temporary = project / 'revisoes' / '_intermediarios' / 'temporary.wav'
            target = project / 'dublados personalizados' / 'chapter' / '100097641.wav'
            assessment = review_report_path(temporary, pending=True)
            assessment.parent.mkdir(parents=True)
            assessment.write_text('{"needs_review":true}')
            target.parent.mkdir(parents=True)
            target.write_bytes(b'unchanged audio')
            self.assertTrue(publish_review_report(temporary, target))
            expected = project / 'revisoes/_conferencia_fala/relatorios/dublados personalizados/chapter/100097641.conferencia.json'
            self.assertEqual(review_report_path(target), expected)
            self.assertTrue(expected.is_file())
            self.assertFalse(target.with_suffix('.conferencia.json').exists())
            self.assertEqual(target.read_bytes(), b'unchanged audio')
            self.assertTrue(needs_review(target))

    def test_legacy_report_moves_on_read_without_changing_wav(self):
        from speech_completeness import needs_review, review_report_path
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'dublado' / 'chapter' / 'scene.wav'
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b'audio')
            old = audio.with_suffix('.conferencia.json')
            old.write_text('{"needs_review":true}')
            self.assertTrue(needs_review(audio))
            self.assertFalse(old.exists())
            self.assertTrue(review_report_path(audio).exists())
            self.assertEqual(audio.read_bytes(), b'audio')

    def test_compound_word_spacing_without_accepting_omission(self):
        self.assertEqual(compare_speech('para a casamata', 'para a casa mata')['status'], 'complete')
        result = compare_speech('deve ter mais agua pesada sendo transportada para a casamata',
                                'Deve sendo transportada para Casa Mata')
        self.assertNotEqual(result['status'], 'complete')
        self.assertIn('pesada', result['missing'])
        self.assertIn('a', result['missing'])

    def test_adaptive_recovery_does_not_drop_words(self):
        text = 'deve ter mais agua pesada sendo transportada para a casamata'
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['deve sendo transportada'] * 3 + ['deve ter mais agua pesada', 'sendo transportada para a casa mata'])
            with imports:
                result = model.generate(text=text, language='pt')
            self.assertEqual(len(model.calls), 5)
            self.assertEqual(' '.join(call['text'] for call in model.calls[3:]), text)
            self.assertGreater(len(result[0]), 480)

    def test_recovery_still_rejects_incomplete_children(self):
        text = 'deve ter mais agua pesada sendo transportada para a casamata'
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['deve sendo transportada'] * 3 + ['deve ter mais'] * 2)
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text=text, language='pt')
            self.assertEqual(len(model.calls), 5)

    def test_friendly_error_preserves_unrelated_errors(self):
        from speech_completeness import friendly_error
        self.assertEqual(friendly_error('CUDA indisponível'), 'CUDA indisponível')
        self.assertEqual(friendly_error('Traceback\nRuntimeError: DUBLASKIZON_NEEDS_REVIEW: Confira a amostra: teste.wav'), 'Confira a amostra: teste.wav')

    def test_worker_long_text_keeps_every_segment(self):
        text = ' '.join('palavra' + str(index) for index in range(80))
        parts = split_speech(text)
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, parts)
            with imports:
                result = model.generate(text=text, language='pt', duration=9)
            self.assertEqual([call['text'] for call in model.calls], parts)
            self.assertAlmostEqual(sum(call['duration'] for call in model.calls), 9)
            self.assertEqual(len(result[0]), 240 * len(parts))

    def test_split_does_not_drop_words(self):
        text = ' '.join('palavra' + str(index) for index in range(117))
        parts = split_speech(text)
        self.assertEqual(' '.join(parts), text)
        self.assertTrue(all(len(part.split()) <= 35 for part in parts))
        self.assertEqual(split_speech(''), [])

    def test_short_sentences_are_checked_separately(self):
        text = 'Eles chegaram agora. Precisamos sair daqui.'
        self.assertEqual(split_speech(text), ['Eles chegaram agora.', 'Precisamos sair daqui.'])

    def test_short_final_command_retains_portuguese_context(self):
        text = 'Eles irão procurar por nós. Prepare-se.'
        self.assertEqual(split_speech(text), [text])

    def test_quiet_endings_are_not_trimmed_or_faded_for_100ms(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            model, imports = self._worker(folder, ['Droga mãe agora'])
            model.config = SimpleNamespace(_name_or_path='edwixx/omnivoice-brpt-v15')
            with imports:
                model.generate(text='Droga! Mãe, agora!', language='pt', instruct='portuguese accent')
            options = model.calls[0]
            self.assertFalse(options['postprocess_output'])
            self.assertEqual(options['fade_duration'], .005)
            self.assertEqual(options['instruct'], 'portuguese accent')
            self.assertEqual(options['speed'], 1.0)

    def test_later_partial_sentence_is_retried_without_regenerating_first(self):
        with tempfile.TemporaryDirectory() as folder:
            first='Eles chegaram agora com todos os caminhões.'
            second='Precisamos sair daqui antes que eles voltem.'
            model, imports = self._worker(folder, [first, 'Precisamos sair daqui antes que eles', second])
            with imports:
                result = model.generate(text=first+' '+second, language='pt')
            self.assertEqual([call['text'] for call in model.calls],
                             [first, second, second])
            self.assertEqual(len(result[0]), 240 * 2 + 2400)

    def test_failure_in_second_sentence_does_not_return_first_as_final(self):
        with tempfile.TemporaryDirectory() as folder:
            first='Eles chegaram agora com todos os caminhões.'
            second='Precisamos sair daqui antes que eles voltem.'
            model, imports = self._worker(folder, [first] + ['Precisamos sair'] * 3)
            with imports, self.assertRaisesRegex(RuntimeError, 'DUBLASKIZON_NEEDS_REVIEW'):
                model.generate(text=first+' '+second, language='pt')
            self.assertEqual(len(model.calls), 4)

    def test_managed_omni_checks_even_with_legacy_disabled_setting(self):
        command = ['python', '-u', '-c', 'print(1)', '--text', 'Oi']
        with tempfile.TemporaryDirectory() as folder:
            result = verified_command(command, 'edwixx/omnivoice-brpt-v15', folder)
            compile(result[3], '<worker>', 'exec')
            self.assertEqual(result[4:], command[4:])
            self.assertEqual(command[3], 'print(1)')
            self.assertEqual(verified_command(command, 'Qwen/Qwen3-TTS', folder), command)
            self.assertEqual(verified_command(['omnivoice-infer'], 'k2-fsa/OmniVoice', folder), ['omnivoice-infer'])
            (Path(folder) / 'Dublaskizon_conferencia_fala.json').write_text(json.dumps({'enabled': False}))
            self.assertNotEqual(verified_command(command, 'edwixx/omnivoice-brpt-v15', folder), command)
            self.assertEqual(verified_command(command, 'edwixx/omnivoice-brpt-v15', folder, require_complete=False), command)


if __name__ == '__main__':
    unittest.main()
