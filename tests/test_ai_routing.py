import unittest
from unittest.mock import patch

from ai_assistant import (
    anthropic_messages_url,
    call_chat_completion_message,
    call_openai_compatible,
    chat_completions_url,
    find_rule_by_id,
    find_wake_rule,
    normalize_ai_settings,
    public_ai_buttons,
    strip_thinking_text,
)
from client import DEFAULT_IMAGE_SEND_DELAY_MS, VoiceInputWindow
from server import app, socketio


def sample_settings():
    return normalize_ai_settings(
        {
            "api": {
                "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                "api_key": "test-key",
                "model": "glm-5.1",
            },
            "rules": [
                {
                    "enabled": True,
                    "wake_word": "td_translate",
                    "match_mode": "prefix",
                    "button_enabled": True,
                    "button_label": "translate",
                    "system_prompt": "translate",
                    "output_action": "follow",
                },
                {
                    "enabled": True,
                    "wake_word": "td_search",
                    "match_mode": "contains",
                    "button_enabled": False,
                    "button_label": "search",
                    "system_prompt": "search",
                    "output_action": "send",
                },
            ],
        }
    )


class FakeWindow:
    def __init__(self, settings):
        self.ai_settings = settings
        self.calls = []

    def normalize_image_delay_ms(self, value):
        return DEFAULT_IMAGE_SEND_DELAY_MS

    def normalize_image_paste_mode(self, value):
        return value if value == "safe" else "fast"

    def set_received_images(self, images):
        self.calls.append(("images", len(images)))

    def start_ai_processing(self, action, text, images, delay, image_paste_mode, wake_match):
        rule = wake_match["rule"]
        self.calls.append(
            (
                "ai",
                action,
                rule.get("button_label") or rule.get("wake_word"),
                wake_match.get("prompt_text"),
            )
        )

    def handle_processed_text(self, action, text, images, delay, image_paste_mode="fast", original_text=None):
        self.calls.append(("plain", action, text, original_text))


class AiRoutingTests(unittest.TestCase):
    def test_provider_detection_and_zhipu_url(self):
        settings = sample_settings()
        self.assertEqual(settings["api"]["provider"], "zhipu")
        self.assertEqual(
            chat_completions_url(settings["api"]["base_url"]),
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://relay.example.com/v1/chat/completions"),
            "https://relay.example.com/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://relay.example.com/v1/chat/completions?api-version=2024-10-21"),
            "https://relay.example.com/v1/chat/completions?api-version=2024-10-21",
        )
        self.assertEqual(
            chat_completions_url("https://relay.example.com/api/v3"),
            "https://relay.example.com/api/v3/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("https://example.openai.azure.com/openai/deployments/my-model?api-version=2024-10-21"),
            "https://example.openai.azure.com/openai/deployments/my-model/chat/completions?api-version=2024-10-21",
        )
        self.assertEqual(
            anthropic_messages_url("https://api.anthropic.com/v1"),
            "https://api.anthropic.com/v1/messages",
        )

    def test_public_buttons_require_api_and_model(self):
        settings = sample_settings()
        buttons = public_ai_buttons(settings)
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0]["label"], "translate")

        hidden = public_ai_buttons({"api": {"model": "glm-5.1"}, "rules": settings["rules"]})
        self.assertEqual(hidden, [])

    def test_button_route_then_keyword_then_plain(self):
        settings = sample_settings()
        button_id = public_ai_buttons(settings)[0]["id"]

        button_match = find_rule_by_id(button_id, "hello world", settings)
        self.assertEqual(button_match["rule"]["button_label"], "translate")
        self.assertEqual(button_match["prompt_text"], "hello world")

        keyword_match = find_wake_rule("please td_search today news", settings)
        self.assertEqual(keyword_match["rule"]["button_label"], "search")
        self.assertEqual(keyword_match["prompt_text"], "today news")

        self.assertIsNone(find_wake_rule("ordinary text", settings))

    def test_desktop_receive_priority(self):
        settings = sample_settings()
        button_id = public_ai_buttons(settings)[0]["id"]

        fake = FakeWindow(settings)
        VoiceInputWindow.on_text_received(
            fake,
            {"action": "paste", "text": "hello", "ai_rule_id": button_id, "images": []},
        )
        self.assertIn(("ai", "paste", "translate", "hello"), fake.calls)

        fake = FakeWindow(settings)
        VoiceInputWindow.on_text_received(
            fake,
            {"action": "send", "text": "please td_search today news", "images": []},
        )
        self.assertIn(("ai", "send", "search", "today news"), fake.calls)

        fake = FakeWindow(settings)
        VoiceInputWindow.on_text_received(
            fake,
            {"action": "paste", "text": "ordinary text", "images": []},
        )
        self.assertIn(("plain", "paste", "ordinary text", "ordinary text"), fake.calls)

    def test_server_forwards_ai_rule_id(self):
        sender = socketio.test_client(app)
        receiver = socketio.test_client(app)
        try:
            sender.emit(
                "send_text",
                {"text": "hello", "action": "paste", "ai_rule_id": "rule-test", "images": []},
            )
            events = [item for item in receiver.get_received() if item["name"] == "receive_text"]
            self.assertTrue(events)
            data = events[-1]["args"][0]
            self.assertEqual(data["ai_rule_id"], "rule-test")
            self.assertEqual(data["text"], "hello")
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_direct_output_without_json_content_extraction(self):
        with patch(
            "ai_assistant.call_chat_completion_message",
            return_value='{"content":"不要再解析这个 JSON"}',
        ):
            self.assertEqual(
                call_openai_compatible(
                    {"api_key": "test", "model": "gpt-test"},
                    "直接润色文本",
                    "hello",
                ),
                '{"content":"不要再解析这个 JSON"}',
            )

    def test_thinking_text_is_removed_from_visible_output(self):
        self.assertEqual(strip_thinking_text("<think>先分析</think>\n最终结果"), "最终结果")
        self.assertEqual(strip_thinking_text("思考：先分析\n答案：最终结果"), "最终结果")

    def test_chat_payload_allows_thinking_models(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"choices":[{"message":{"reasoning_content":"hidden","content":"<think>hidden</think>final"}}]}'

        def fake_urlopen(request):
            import json

            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            result = call_chat_completion_message(
                {"base_url": "https://api.example.com/v1", "api_key": "test", "model": "glm-5.1"},
                "直接输出最终文本",
                "hello",
            )

        self.assertEqual(result, "final")
        self.assertNotIn("thinking", captured["body"])
        self.assertNotIn("JSON", captured["body"]["messages"][0]["content"])

    def test_azure_openai_sends_api_key_header(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'

        def fake_urlopen(request):
            import json

            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            result = call_chat_completion_message(
                {
                    "provider": "azure_openai",
                    "base_url": "https://example.openai.azure.com/openai/deployments/test?api-version=2024-10-21",
                    "api_key": "azure-key",
                    "model": "ignored-by-azure-url",
                },
                "system",
                "hello",
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["headers"].get("Api-key"), "azure-key")
        self.assertNotIn("model", captured["body"])

    def test_anthropic_provider_uses_messages_api(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"content":[{"type":"text","text":"<think>hidden</think>claude final"}]}'

        def fake_urlopen(request):
            import json

            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            result = call_chat_completion_message(
                {
                    "provider": "anthropic",
                    "base_url": "https://api.anthropic.com/v1",
                    "api_key": "anthropic-key",
                    "model": "claude-sonnet-4-5",
                },
                "system prompt",
                "hello",
            )

        self.assertEqual(result, "claude final")
        self.assertEqual(captured["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(captured["headers"].get("X-api-key"), "anthropic-key")
        self.assertEqual(captured["body"]["system"], "system prompt")


if __name__ == "__main__":
    unittest.main()
