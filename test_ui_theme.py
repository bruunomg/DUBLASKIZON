import unittest

from ui_theme import BUTTON_PALETTES, apply_button_style, button_style, resolve_theme_mode


class FakeButton:
    def __init__(self, bg="#2563EB"):
        self.options = {"bg": bg}

    def cget(self, key):
        return self.options[key]

    def configure(self, **kwargs):
        self.options.update(kwargs)


class UiThemeTests(unittest.TestCase):
    def test_all_theme_roles_are_complete(self):
        expected = {"bg", "activebackground", "fg", "activeforeground"}
        for mode, palette in BUTTON_PALETTES.items():
            self.assertGreaterEqual(len(palette), 10, mode)
            for role, colors in palette.items():
                self.assertTrue(expected.issubset(colors), f"{mode}/{role}")

    def test_mode_resolution(self):
        self.assertEqual(resolve_theme_mode({"mode": "claro"}), "claro")
        self.assertEqual(resolve_theme_mode({"root": "#334155"}), "medio")
        self.assertEqual(resolve_theme_mode({"root": "#202938"}), "escuro")

    def test_button_style_changes_between_themes(self):
        light = button_style({"mode": "claro"}, "primary")
        dark = button_style({"mode": "escuro"}, "primary")
        self.assertNotEqual(light, dark)

    def test_legacy_button_gets_role_and_theme_colors(self):
        button = FakeButton("#DC2626")
        apply_button_style(button, {"mode": "escuro"})
        self.assertEqual(button._dublaskizon_button_role, "danger")
        self.assertEqual(button.options["bg"], button_style({"mode": "escuro"}, "danger")["bg"])
        self.assertIn("activebackground", button.options)


if __name__ == "__main__":
    unittest.main()
