import ast
import sys
import unittest
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock, patch
from pathlib import Path
import audio_translation as translation
import batch_tab
import i18n


class RussianSupport(unittest.TestCase):
    def test_russian_complement_is_language_not_english_accent(self):
        self.assertEqual(translation.synthesis_settings('Russian',batch_tab.MODEL,'Russian accent, deep voice'),('k2-fsa/OmniVoice','deep voice'))
        self.assertEqual(translation.synthesis_settings('Russian',batch_tab.MODEL,'Russo'),('k2-fsa/OmniVoice',''))

    def test_return_to_brpt_resets_language_and_translation(self):
        class Var:
            def __init__(self,value):self.value=value
            def get(self):return self.value
            def set(self,value):self.value=value
        app=SimpleNamespace(selected_model_id=lambda:batch_tab.MODEL,speech_language_var=Var('Russo'),instruct_var=Var('Russo'),
                            auto_translation_settings={'language':'Russo'},update_model_info=Mock(),save_voice_settings=Mock())
        batch_tab.BatchApp.on_model_changed(app)
        self.assertEqual(i18n.source_text(app.speech_language_var.get()),'Português (Brasil)')
        self.assertEqual(app.auto_translation_settings['language'],'Português (Brasil)')
        self.assertEqual(app.instruct_var.get(),'portuguese accent')

    def test_complement_russian_selects_visible_multilingual_model(self):
        app=SimpleNamespace(instruct_var=SimpleNamespace(get=lambda:'Russo'),speech_language_var=Mock(),
                            auto_translation_settings={},selected_model_id=lambda:batch_tab.MODEL,
                            model_choices=batch_tab.DEFAULT_MODEL_CHOICES,model_var=Mock(),display_model=lambda label,model:model,
                            update_model_info=Mock(),save_voice_settings=Mock())
        batch_tab.BatchApp.on_voice_complement_changed(app)
        self.assertEqual(app.auto_translation_settings['language'],'Russo')
        app.model_var.set.assert_called_once_with('k2-fsa/OmniVoice')

    def test_localized_language_round_trip(self):
        for locale in ('en','ru','es'):
            for label in translation.LANGUAGES:
                config=translation.settings({'language':i18n.tr(label,locale)})
                self.assertEqual(config['language'],label)
        self.assertEqual(translation.settings({'language':'Русский'})['target'],'ru')

    def test_russian_model_and_instruction(self):
        model,instruction=translation.synthesis_settings('Russian',batch_tab.MODEL,'portuguese accent, deep voice, clear Brazilian Portuguese')
        self.assertEqual(model,'k2-fsa/OmniVoice')
        self.assertEqual(instruction,'deep voice')
        self.assertEqual(translation.synthesis_settings('Portuguese',batch_tab.MODEL,'portuguese accent'),(batch_tab.MODEL,'portuguese accent'))

    def test_russian_batch_command(self):
        app=SimpleNamespace(scene_translation_language='Russian',selected_r_pronunciation='unchanged',
            infer_prefix=['omni'],selected_model=batch_tab.MODEL,selected_mode='clone',
            selected_instruct='portuguese accent',audio_by_stem={'scene':Path('ref.wav')})
        command=batch_tab.BatchApp.build_infer_command(app,'scene','Привет, мир!',Path('out.wav'))
        self.assertEqual(command[command.index('--model')+1],'k2-fsa/OmniVoice')
        self.assertEqual(command[command.index('--language')+1],'Russian')
        self.assertNotIn('--instruct',command)

    def test_argos_auto_russian_installs_target_once(self):
        installed=[]
        package=SimpleNamespace(update_package_index=Mock())
        model=SimpleNamespace(from_code='en',to_code='ru',download=Mock(return_value=Path('official.argosmodel')))
        package.get_available_packages=lambda:[model]
        package.install_from_path=lambda path:installed.append(path)
        english=SimpleNamespace(code='en',get_translation=lambda target:object() if installed else None)
        russian=SimpleNamespace(code='ru')
        translate=SimpleNamespace(get_installed_languages=lambda:[english,russian] if installed else [])
        module=ModuleType('argostranslate');module.package=package;module.translate=translate
        tree=ast.parse(translation.PREPARE_WORKER)
        branch=next(node for node in tree.body if isinstance(node,ast.If) and ast.unparse(node.test)=="c['translator'] == 'argos'")
        code=compile(ast.Module(body=[branch],type_ignores=[]),'<prepare-argos>','exec')
        scope={'c':translation.settings({'language':'Russo','source':'auto'}),'available':lambda value:None,'print':lambda *args,**kwargs:None}
        with patch.dict(sys.modules,{'argostranslate':module}):
            exec(code,scope);exec(code,scope)
        self.assertEqual(installed,[Path('official.argosmodel')])
        model.download.assert_called_once()

    def test_official_model_selection_in_localized_ui(self):
        label, model=batch_tab.DEFAULT_MODEL_CHOICES[1]
        for language in ('ru','en','es'):
            app=SimpleNamespace(model_var=SimpleNamespace(get=lambda:i18n.tr(label,language)+' [cache local]'),model_choices=batch_tab.DEFAULT_MODEL_CHOICES)
            self.assertEqual(batch_tab.BatchApp.selected_model_id(app),model)

if __name__=='__main__':unittest.main()
