"""
AI wake-word support for the desktop client.

The phone page only sends LAN text. API keys and model settings stay on the PC.
"""
import json
import hashlib
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime


AI_SETTINGS_FILE = "ai-settings.json"
AI_LOG_FILE = "ai-assistant.log"
AI_PROVIDER_PRESETS = {
    "custom": {
        "label": "自定义/中转站",
        "base_url": "",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
    },
    "xai": {
        "label": "xAI Grok",
        "base_url": "https://api.x.ai/v1",
    },
    "together": {
        "label": "Together.ai",
        "base_url": "https://api.together.xyz/v1",
    },
    "perplexity": {
        "label": "Perplexity",
        "base_url": "https://api.perplexity.ai",
    },
    "azure_openai": {
        "label": "Azure OpenAI",
        "base_url": "",
    },
    "anthropic_gateway": {
        "label": "Anthropic 兼容网关",
        "base_url": "",
    },
    "gemini_gateway": {
        "label": "Gemini 兼容网关",
        "base_url": "",
    },
    "zhipu": {
        "label": "智谱 BigModel",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
    },
    "qwen": {
        "label": "通义千问 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "doubao": {
        "label": "火山方舟/豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    "moonshot": {
        "label": "Moonshot/Kimi",
        "base_url": "https://api.moonshot.cn/v1",
    },
    "baidu": {
        "label": "百度千帆",
        "base_url": "https://qianfan.baidubce.com/v2",
    },
    "tencent": {
        "label": "腾讯混元",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
    },
    "stepfun": {
        "label": "阶跃星辰",
        "base_url": "https://api.stepfun.com/v1",
    },
    "baichuan": {
        "label": "百川智能",
        "base_url": "https://api.baichuan-ai.com/v1",
    },
    "siliconflow": {
        "label": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
    },
    "aihubmix": {
        "label": "AiHubMix 中转",
        "base_url": "https://aihubmix.com/v1",
    },
    "oneapi": {
        "label": "OneAPI/NewAPI 中转",
        "base_url": "",
    },
}


DEFAULT_AI_SETTINGS = {
    "api": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "",
    },
    "rules": [
        {
            "enabled": True,
            "id": "",
            "wake_word": "土豆",
            "match_mode": "contains",
            "button_enabled": True,
            "button_label": "土豆",
            "system_prompt": "你是一个语音输入文本处理助手。请根据用户内容进行二次处理，让输出更适合直接粘贴或发送。请直接输出最终文本，不要输出思考过程。",
            "output_action": "follow",
        }
    ],
    "behavior": {
        "show_processing_title": True,
        "save_ai_history": True,
    },
}


def runtime_data_dir():
    """Use AppData for writable files in the packaged app."""
    if getattr(sys, "frozen", False):
        path = os.path.join(
            os.environ.get("APPDATA", os.path.dirname(sys.executable)),
            "VoiceInputAssistant",
        )
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def ai_settings_file_path():
    return os.path.join(runtime_data_dir(), AI_SETTINGS_FILE)


def ai_log_file_path():
    return os.path.join(runtime_data_dir(), AI_LOG_FILE)


def log_ai_event(event, details=None):
    """Append AI diagnostics without writing secrets."""
    payload = details if isinstance(details, dict) else {}
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key not in ("api_key", "authorization", "Authorization")
    }
    line = json.dumps(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            **safe_payload,
        },
        ensure_ascii=False,
    )
    try:
        with open(ai_log_file_path(), "a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except Exception:
        pass


def copy_settings(settings):
    return json.loads(json.dumps(settings, ensure_ascii=False))


def detect_provider_from_base_url(base_url):
    url = (base_url or "").strip().lower()
    for provider_id, preset in AI_PROVIDER_PRESETS.items():
        preset_url = preset.get("base_url", "").strip().lower().rstrip("/")
        if provider_id == "custom" or not preset_url:
            continue
        if url.rstrip("/").startswith(preset_url):
            return provider_id
    return "custom" if url else "openai"


def make_rule_id(rule, index):
    """Create a stable id for old settings that do not have one yet."""
    existing = str(rule.get("id", "")).strip() if isinstance(rule, dict) else ""
    if re.fullmatch(r"[A-Za-z0-9_-]{6,64}", existing):
        return existing
    source = json.dumps(
        {
            "index": index,
            "wake_word": rule.get("wake_word", "") if isinstance(rule, dict) else "",
            "system_prompt": rule.get("system_prompt", "") if isinstance(rule, dict) else "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "rule-" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def normalize_ai_settings(settings):
    """Merge persisted settings with defaults and sanitize rule fields."""
    if not isinstance(settings, dict):
        settings = {}

    normalized = copy_settings(DEFAULT_AI_SETTINGS)

    api = settings.get("api") if isinstance(settings.get("api"), dict) else {}
    provider = str(api.get("provider", "")).strip()
    if not provider:
        provider = detect_provider_from_base_url(api.get("base_url"))
    if provider not in AI_PROVIDER_PRESETS:
        provider = detect_provider_from_base_url(api.get("base_url"))
    normalized["api"]["provider"] = provider
    for key in ("base_url", "api_key", "model"):
        value = api.get(key)
        if isinstance(value, str):
            normalized["api"][key] = value.strip()

    behavior = settings.get("behavior") if isinstance(settings.get("behavior"), dict) else {}
    normalized["behavior"]["show_processing_title"] = bool(
        behavior.get("show_processing_title", normalized["behavior"]["show_processing_title"])
    )
    normalized["behavior"]["save_ai_history"] = bool(
        behavior.get("save_ai_history", normalized["behavior"]["save_ai_history"])
    )

    rules = settings.get("rules")
    normalized_rules = []
    if isinstance(rules, list):
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            wake_word = str(rule.get("wake_word", "")).strip()
            system_prompt = str(rule.get("system_prompt", "")).strip()
            if not wake_word:
                continue
            match_mode = rule.get("match_mode", "contains")
            if match_mode not in ("contains", "prefix"):
                match_mode = "contains"
            output_action = rule.get("output_action", "follow")
            if output_action not in ("follow", "paste", "send"):
                output_action = "follow"
            button_label = str(rule.get("button_label", "")).strip() or wake_word
            normalized_rules.append(
                {
                    "enabled": bool(rule.get("enabled", True)),
                    "id": make_rule_id(rule, index),
                    "wake_word": wake_word,
                    "match_mode": match_mode,
                    "button_enabled": bool(rule.get("button_enabled", True)),
                    "button_label": button_label[:16],
                    "system_prompt": system_prompt,
                    "output_action": output_action,
                }
            )
    if normalized_rules:
        normalized["rules"] = normalized_rules

    return normalized


def public_ai_buttons(settings):
    """Return button metadata safe for the phone page."""
    normalized = normalize_ai_settings(settings)
    api = normalized.get("api", {})
    if not (api.get("api_key") and api.get("model")):
        return []
    buttons = []
    for rule in normalized.get("rules", []):
        if not rule.get("enabled") or not rule.get("button_enabled"):
            continue
        buttons.append(
            {
                "id": rule.get("id", ""),
                "label": rule.get("button_label") or rule.get("wake_word", ""),
                "wake_word": rule.get("wake_word", ""),
            }
        )
    return buttons


def load_ai_settings():
    path = ai_settings_file_path()
    if not os.path.exists(path):
        return normalize_ai_settings(DEFAULT_AI_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as settings_file:
            return normalize_ai_settings(json.load(settings_file))
    except Exception:
        return normalize_ai_settings(DEFAULT_AI_SETTINGS)


def save_ai_settings(settings):
    normalized = normalize_ai_settings(settings)
    path = ai_settings_file_path()
    with open(path, "w", encoding="utf-8") as settings_file:
        json.dump(normalized, settings_file, ensure_ascii=False, indent=2)
    return normalized


def clean_text_after_wake(text):
    """Remove punctuation and spacing between the wake word and the real prompt."""
    return re.sub(r"^[\s,，.。:：;；!！?？、\-—|/\\]+", "", text or "").strip()


def find_wake_rule(text, settings):
    """Return the first matching enabled wake-word rule and prompt text."""
    if not text:
        return None
    for rule in normalize_ai_settings(settings).get("rules", []):
        if not rule.get("enabled"):
            continue
        wake_word = rule.get("wake_word", "")
        if not wake_word:
            continue
        source = text.lstrip() if rule.get("match_mode") == "prefix" else text
        index = source.find(wake_word)
        if index < 0:
            continue
        if rule.get("match_mode") == "prefix" and index != 0:
            continue
        prompt_text = clean_text_after_wake(source[index + len(wake_word):])
        if not prompt_text:
            continue
        return {
            "rule": rule,
            "prompt_text": prompt_text,
        }
    return None


def find_rule_by_id(rule_id, text, settings):
    """Return a rule selected explicitly by the phone UI."""
    selected_id = str(rule_id or "").strip()
    if not selected_id or not text:
        return None
    for rule in normalize_ai_settings(settings).get("rules", []):
        if not rule.get("enabled"):
            continue
        if rule.get("id") != selected_id:
            continue
        return {
            "rule": rule,
            "prompt_text": clean_text_after_wake(text),
            "source": "button",
        }
    return None


def chat_completions_url(base_url):
    base = (base_url or DEFAULT_AI_SETTINGS["api"]["base_url"]).strip().rstrip("/")
    if not base:
        base = DEFAULT_AI_SETTINGS["api"]["base_url"]
    path, separator, query = base.partition("?")
    path = path.rstrip("/")
    query_suffix = f"{separator}{query}" if separator else ""
    if re.search(r"/(?:chat/)?completions$", path):
        return base
    if re.search(r"/(?:v\d+|paas/v\d+|coding/paas/v\d+|api/v\d+)$", path):
        return f"{path}/chat/completions{query_suffix}"
    if re.search(r"/openai/deployments/[^/]+$", path):
        return f"{path}/chat/completions{query_suffix}"
    return f"{path}/v1/chat/completions{query_suffix}"


def anthropic_messages_url(base_url):
    base = (base_url or AI_PROVIDER_PRESETS["anthropic"]["base_url"]).strip().rstrip("/")
    if not base:
        base = AI_PROVIDER_PRESETS["anthropic"]["base_url"]
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def build_system_prompt(system_prompt):
    return (system_prompt or "").strip()


def strip_thinking_text(text):
    """Remove common visible thinking blocks while keeping the final answer."""
    value = str(text or "")
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<thinking>.*?</thinking>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<reasoning>.*?</reasoning>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"^\s*(?:思考|推理|Reasoning|Thinking)\s*[:：].*?(?=\n\s*(?:答案|回答|Answer|Final)\s*[:：]|\Z)", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"^\s*(?:答案|回答|Answer|Final)\s*[:：]\s*", "", value, flags=re.IGNORECASE)
    return value.strip()


def message_content_to_text(content):
    """Normalize OpenAI-compatible message content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return "\n".join(part for part in parts if part)
    return str(content)


def extract_message_text(message):
    if not isinstance(message, dict):
        return ""
    content_text = message_content_to_text(message.get("content"))
    if not content_text and isinstance(message.get("text"), str):
        content_text = message["text"]
    return strip_thinking_text(content_text)


def call_chat_completion_message(
    api_settings,
    system_prompt,
    user_text,
    max_tokens=None,
):
    """Call an OpenAI-compatible chat completions endpoint and return raw message text."""
    api = api_settings or {}
    api_key = (api.get("api_key") or "").strip()
    model = (api.get("model") or "").strip()
    provider = (api.get("provider") or detect_provider_from_base_url(api.get("base_url"))).strip()
    if not api_key:
        raise ValueError("请先在设置中填写 API Key")
    if not model:
        raise ValueError("请先在设置中填写 model")
    if provider == "anthropic":
        return call_anthropic_messages(api, system_prompt, user_text, max_tokens=max_tokens)

    url = chat_completions_url(api.get("base_url"))
    payload = {
        "messages": [
            {
                "role": "system",
                "content": build_system_prompt(system_prompt),
            },
            {"role": "user", "content": user_text or ""},
        ],
        "stream": False,
    }
    is_azure = provider == "azure_openai" or ".openai.azure.com/" in url.lower()
    if not is_azure:
        payload["model"] = model
    if max_tokens:
        payload["max_tokens"] = max_tokens
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if is_azure:
        headers["api-key"] = api_key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")

    log_ai_event(
        "request",
        {
            "url": url,
            "model": model,
            "system_prompt_chars": len(system_prompt or ""),
            "user_text_chars": len(user_text or ""),
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        log_ai_event(
            "http_error",
            {
                "url": url,
                "model": model,
                "status": exc.code,
                "detail": detail[:1000],
            },
        )
        raise ValueError(f"AI 接口返回错误 {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        log_ai_event(
            "network_error",
            {
                "url": url,
                "model": model,
                "error": str(exc),
            },
        )
        raise ValueError(f"AI 接口连接失败: {exc}") from exc

    try:
        data = json.loads(response_body)
        message = data["choices"][0]["message"]
        model_message = extract_message_text(message)
    except Exception as exc:
        log_ai_event(
            "bad_response_shape",
            {
                "url": url,
                "model": model,
                "response": response_body[:1000],
            },
        )
        raise ValueError("AI 接口响应不是兼容的 chat/completions 结构") from exc

    log_ai_event(
        "response",
        {
            "url": url,
            "model": model,
            "message_chars": len(model_message or ""),
            "message_preview": (model_message or "")[:300],
        },
    )
    return model_message


def call_anthropic_messages(api_settings, system_prompt, user_text, max_tokens=None):
    api = api_settings or {}
    api_key = (api.get("api_key") or "").strip()
    model = (api.get("model") or "").strip()
    if not api_key:
        raise ValueError("请先在设置中填写 API Key")
    if not model:
        raise ValueError("请先在设置中填写 model")

    url = anthropic_messages_url(api.get("base_url"))
    payload = {
        "model": model,
        "max_tokens": max_tokens or 2048,
        "messages": [{"role": "user", "content": user_text or ""}],
    }
    system = build_system_prompt(system_prompt)
    if system:
        payload["system"] = system
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    log_ai_event(
        "request",
        {
            "url": url,
            "model": model,
            "system_prompt_chars": len(system_prompt or ""),
            "user_text_chars": len(user_text or ""),
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        log_ai_event(
            "http_error",
            {
                "url": url,
                "model": model,
                "status": exc.code,
                "detail": detail[:1000],
            },
        )
        raise ValueError(f"AI 接口返回错误 {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        log_ai_event(
            "network_error",
            {
                "url": url,
                "model": model,
                "error": str(exc),
            },
        )
        raise ValueError(f"AI 接口连接失败: {exc}") from exc

    try:
        data = json.loads(response_body)
        model_message = strip_thinking_text(message_content_to_text(data.get("content")))
    except Exception as exc:
        log_ai_event(
            "bad_response_shape",
            {
                "url": url,
                "model": model,
                "response": response_body[:1000],
            },
        )
        raise ValueError("AI 接口响应不是兼容的 Anthropic messages 结构") from exc

    log_ai_event(
        "response",
        {
            "url": url,
            "model": model,
            "message_chars": len(model_message or ""),
            "message_preview": (model_message or "")[:300],
        },
    )
    return model_message


def call_openai_compatible(api_settings, system_prompt, user_text):
    """Call an OpenAI-compatible chat completions endpoint and return final text."""
    return call_chat_completion_message(api_settings, system_prompt, user_text)


def test_openai_compatible(api_settings):
    """Test connectivity without requiring the model to return JSON."""
    return call_chat_completion_message(
        api_settings,
        "你是接口连通性测试助手，请用一句中文短句回复测试成功。",
        "请回复：测试成功",
        max_tokens=128,
    )
