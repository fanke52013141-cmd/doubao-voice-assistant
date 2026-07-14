import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import client


class PlatformCompatibilityTests(unittest.TestCase):
    def test_paste_hotkey_uses_command_on_macos(self):
        with patch("client.sys.platform", "darwin"):
            self.assertEqual(client.paste_hotkey(), ("command", "v"))

    def test_paste_hotkey_uses_control_on_windows(self):
        with patch("client.sys.platform", "win32"):
            self.assertEqual(client.paste_hotkey(), ("ctrl", "v"))

    def test_macos_bundle_is_derived_from_executable_path(self):
        app_path = os.path.abspath(
            os.path.join(
                os.sep,
                "Applications",
                "语音输入助手.app",
                "Contents",
                "MacOS",
                "VoiceInputAssistant",
            )
        )
        expected_suffix = os.path.join("Applications", "语音输入助手.app")
        self.assertTrue(client.macos_app_bundle_path(app_path).endswith(expected_suffix))

    def test_macos_login_startup_plist_can_be_enabled_and_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plist_path = os.path.join(temp_dir, "com.fanke.voiceinputassistant.plist")
            startup_args = ["/usr/bin/open", "-g", "/Applications/语音输入助手.app"]
            with patch("client.sys.platform", "darwin"), patch(
                "client.macos_launch_agent_path", return_value=plist_path
            ), patch("client.macos_startup_arguments", return_value=startup_args):
                client.set_startup_enabled(True)
                self.assertTrue(client.is_startup_enabled())
                client.set_startup_enabled(False)
                self.assertFalse(os.path.exists(plist_path))


if __name__ == "__main__":
    unittest.main()
