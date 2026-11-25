import os
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from client import DoubleClickButton


class RestartButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.button = DoubleClickButton("重启")
        self.button.resize(84, 52)
        self.button.show()
        self.app.processEvents()

    def tearDown(self):
        self.button.close()

    def wait_for_click_resolution(self):
        """Allow headless macOS runners enough time to deliver the Qt timer."""
        QTest.qWait(self.app.doubleClickInterval() + 300)

    def test_single_click_only_emits_hint_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.mouseClick(self.button, Qt.LeftButton)
        self.wait_for_click_resolution()

        self.assertEqual(events, ["single"])

    def test_double_click_only_emits_restart_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.mouseDClick(self.button, Qt.LeftButton)
        self.wait_for_click_resolution()

        self.assertEqual(events, ["double"])

    def test_single_keyboard_activation_only_emits_hint_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.keyClick(self.button, Qt.Key_Return)
        self.wait_for_click_resolution()

        self.assertEqual(events, ["single"])

    def test_double_keyboard_activation_emits_restart_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.keyClick(self.button, Qt.Key_Return)
        QTest.keyClick(self.button, Qt.Key_Return)
        self.wait_for_click_resolution()

        self.assertEqual(events, ["double"])


if __name__ == "__main__":
    unittest.main()
