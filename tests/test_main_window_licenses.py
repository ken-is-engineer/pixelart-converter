"""Headless test for Help → Third-party licenses (T6-1)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pixelart_converter.ui.main_window import MainWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MainWindowLicensesMenuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _ensure_app()

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.close()

    def test_help_menu_has_third_party_licenses_action(self) -> None:
        licenses_action = self.window.third_party_licenses_action
        self.assertIsNotNone(licenses_action)
        self.assertEqual(licenses_action.objectName(), "thirdPartyLicensesAction")
        self.assertIn("Third-party licenses", licenses_action.text())

    def test_third_party_licenses_action_is_in_help_menu(self) -> None:
        menubar = self.window.menuBar()
        help_menu = None
        for action in menubar.actions():
            if action.text() == "Help":
                help_menu = action.menu()
                break
        self.assertIsNotNone(help_menu)
        action_texts = [action.text() for action in help_menu.actions()]
        self.assertIn("Third-party licenses", action_texts)


if __name__ == "__main__":
    unittest.main()
