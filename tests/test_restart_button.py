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

    def test_single_click_only_emits_hint_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.mouseClick(self.button, Qt.LeftButton)
        QTest.qWait(self.app.doubleClickInterval() + 50)

        self.assertEqual(events, ["single"])

    def test_double_click_only_emits_restart_signal(self):
        events = []
        self.button.singleClicked.connect(lambda: events.append("single"))
        self.button.doubleClicked.connect(lambda: events.append("double"))

        QTest.mouseDClick(self.button, Qt.LeftButton)
        QTest.qWait(self.app.doubleClickInterval() + 50)

        self.assertEqual(events, ["double"])


if __name__ == "__main__":
    unittest.main()
