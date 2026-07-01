"""
语音输入助手 - 桌面客户端
PyQt5 实现的接收端窗口，默认置顶，精简布局
支持自动输入到光标所在位置
"""
import sys
import os
import base64
import time
import subprocess
import json
import ctypes
import socketio
import pyperclip
import pyautogui


def configure_qt_plugin_paths():
    """Point Qt at PyQt5's bundled plugins when running from a local venv."""
    candidates = [
        os.path.abspath(
            os.path.join(
                os.path.dirname(sys.executable),
                "..",
                "Lib",
                "site-packages",
                "PyQt5",
                "Qt5",
                "plugins",
            )
        ),
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".venv",
            "Lib",
            "site-packages",
            "PyQt5",
            "Qt5",
            "plugins",
        ),
    ]
    for plugin_root in candidates:
        platform_dir = os.path.join(plugin_root, "platforms")
        if os.path.exists(os.path.join(platform_dir, "qwindows.dll")):
            os.environ.setdefault("QT_PLUGIN_PATH", plugin_root)
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", platform_dir)
            break


configure_qt_plugin_paths()

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QDialog, QScrollArea, QMenu, QFrame,
    QLineEdit, QCheckBox, QComboBox, QListWidget, QFormLayout,
    QDialogButtonBox, QGroupBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMimeData, QByteArray, QSize
from PyQt5.QtGui import QIcon, QImage, QPixmap, QFont, QFontMetrics, QPainter
from PyQt5.QtSvg import QSvgRenderer

from ai_assistant import (
    AI_PROVIDER_PRESETS,
    DEFAULT_AI_SETTINGS,
    ai_log_file_path,
    call_openai_compatible,
    copy_settings,
    find_rule_by_id,
    find_wake_rule,
    load_ai_settings,
    normalize_ai_settings,
    save_ai_settings,
    test_openai_compatible,
)
from network_utils import get_local_ip

# 配置 pyautogui
pyautogui.FAILSAFE = False  # 禁用安全角落
pyautogui.PAUSE = 0.05  # 减少间隔提高速度

DEFAULT_IMAGE_SEND_DELAY_MS = 10000
MAX_IMAGE_SEND_DELAY_MS = 60000
IMAGE_PASTE_SETTLE_SECONDS = 1.2
IMAGE_MULTI_PASTE_SETTLE_SECONDS = 3.0
IMAGE_PASTE_BATCH_SIZE = 3
IMAGE_PASTE_BATCH_PAUSE_SECONDS = 6.0
IMAGE_PASTE_MODE_FAST = "fast"
IMAGE_PASTE_MODE_SAFE = "safe"
IMAGE_TEXT_PASTE_DELAY_MS = 1000
TEXT_PASTE_SETTLE_SECONDS = 0.05
WINDOW_TITLE = "语音输入助手"
APP_USER_MODEL_ID = "DoubaoVoiceAssistant.VoiceInputAssistant"
HISTORY_LIMIT = 20
PC_UI_SETTINGS_FILE = "pc-ui-settings.json"
PC_CLIENT_LOG_FILE = "voice-input-client.log"
DEFAULT_PC_FONT_SIZE = 23
MIN_PC_FONT_SIZE = 18
MAX_PC_FONT_SIZE = 36
STARTUP_VALUE_NAME = "VoiceInputAssistant"
STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

UI_COLORS = {
    "brand": "#5b4bff",
    "brand_hover": "#4f46e5",
    "brand_soft": "#f1efff",
    "accent": "#ff671d",
    "success": "#19b866",
    "success_soft": "#ecfdf3",
    "ink": "#11182d",
    "muted": "#788197",
    "line": "#e1e5ef",
    "surface": "#ffffff",
    "page": "#f7f8fc",
}

LUCIDE_ICON_PATHS = {
    "rotate": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "pin": '<path d="M12 17v5"/><path d="M5 3l14 14"/><path d="M8 4h8l-1 6 4 4H9"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "settings": '<path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    "download": '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "trash": '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 15H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>',
}


def lucide_icon(name, color=None, size=22):
    """Render a bundled Lucide-style line icon without external assets."""
    paths = LUCIDE_ICON_PATHS.get(name)
    if not paths:
        return QIcon()
    stroke = color or UI_COLORS["brand"]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def resource_path(relative_path):
    """Return bundled resources from PyInstaller's temp dir when packaged."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


def app_icon_path():
    """Find the app icon in source, packaged resources, or next to the exe."""
    candidates = [
        resource_path("voice-assistant-v2.ico"),
        resource_path("语音输入助手.ico"),
        resource_path("icon.ico"),
    ]
    if getattr(sys, "frozen", False):
        executable_dir = os.path.dirname(sys.executable)
        candidates.extend([
            os.path.join(executable_dir, "voice-assistant-v2.ico"),
            os.path.join(executable_dir, "语音输入助手.ico"),
            os.path.join(executable_dir, "icon.ico"),
        ])
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return ""


def set_windows_app_user_model_id():
    """Give Windows taskbar a stable identity instead of grouping under pythonw."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def runtime_data_dir():
    """Use AppData for writable files in the packaged app."""
    if getattr(sys, "frozen", False):
        path = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "VoiceInputAssistant")
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def pc_client_log_file_path():
    return os.path.join(runtime_data_dir(), PC_CLIENT_LOG_FILE)


def log_client_event(message):
    """Write lightweight desktop-side diagnostics for image paste issues."""
    try:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        with open(pc_client_log_file_path(), "a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except Exception:
        pass


def clamp_pc_font_size(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = DEFAULT_PC_FONT_SIZE
    return max(MIN_PC_FONT_SIZE, min(size, MAX_PC_FONT_SIZE))


def pc_ui_settings_file_path():
    return os.path.join(runtime_data_dir(), PC_UI_SETTINGS_FILE)


def load_pc_ui_settings():
    path = pc_ui_settings_file_path()
    if not os.path.exists(path):
        return {"font_size": DEFAULT_PC_FONT_SIZE}
    try:
        with open(path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
        if isinstance(settings, dict):
            return {"font_size": clamp_pc_font_size(settings.get("font_size"))}
    except Exception:
        pass
    return {"font_size": DEFAULT_PC_FONT_SIZE}


def save_pc_ui_settings(settings):
    normalized = {
        "font_size": clamp_pc_font_size(
            settings.get("font_size") if isinstance(settings, dict) else DEFAULT_PC_FONT_SIZE
        )
    }
    with open(pc_ui_settings_file_path(), "w", encoding="utf-8") as settings_file:
        json.dump(normalized, settings_file, ensure_ascii=False, indent=2)
    return normalized


def bundled_pythonw_executable(base_dir):
    venv_config = os.path.join(base_dir, ".venv", "pyvenv.cfg")
    try:
        with open(venv_config, "r", encoding="utf-8") as config:
            for line in config:
                key, _, value = line.partition("=")
                if key.strip().lower() == "home":
                    pythonw = os.path.join(value.strip(), "pythonw.exe")
                    if os.path.exists(pythonw):
                        return pythonw
    except Exception:
        pass

    candidates = [
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        sys.executable,
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return sys.executable


def wscript_executable():
    system_wscript = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "wscript.exe")
    if os.path.exists(system_wscript):
        return system_wscript
    return "wscript.exe"


def launch_command():
    if getattr(sys, "frozen", False):
        return [sys.executable]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    launcher_path = os.path.join(base_dir, "launcher.py")
    script_path = launcher_path if os.path.exists(launcher_path) else os.path.abspath(__file__)
    runner_path = os.path.join(base_dir, "hidden_runner.pyw")
    if os.path.exists(runner_path):
        return [bundled_pythonw_executable(base_dir), runner_path, script_path]
    hidden_script = os.path.join(base_dir, "start_hidden.vbs")
    if os.path.exists(hidden_script):
        return [wscript_executable(), "//B", "//Nologo", hidden_script]
    return [bundled_pythonw_executable(base_dir), script_path]


def launch_working_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def startup_command_line():
    return subprocess.list2cmdline(launch_command())


def startup_registry_value():
    if os.name != "nt":
        return ""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
            return str(value)
    except FileNotFoundError:
        return ""
    except OSError:
        return ""


def is_startup_enabled():
    value = startup_registry_value().strip()
    return bool(value) and value.lower() == startup_command_line().strip().lower()


def set_startup_enabled(enabled):
    if os.name != "nt":
        raise RuntimeError("开机自启只支持 Windows")
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, startup_command_line())
            return
        try:
            winreg.DeleteValue(key, STARTUP_VALUE_NAME)
        except FileNotFoundError:
            pass

class SocketIOThread(QThread):
    """WebSocket 连接线程"""
    text_received = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    
    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url
        self.sio = socketio.Client()
        self.running = True
        
        @self.sio.event
        def connect():
            self.connection_changed.emit(True)
        
        @self.sio.event
        def disconnect():
            self.connection_changed.emit(False)
        
        @self.sio.on('receive_text')
        def on_receive_text(data):
            text = data.get('text', '')
            action = data.get('action', 'paste')  # paste=传递, send=发送
            images = data.get('images') or []
            if text or images:
                self.text_received.emit({
                    'action': action,
                    'text': text,
                    'ai_rule_id': data.get('ai_rule_id', ''),
                    'images': images,
                    'image_delay_ms': data.get('image_delay_ms', DEFAULT_IMAGE_SEND_DELAY_MS),
                    'image_paste_mode': data.get('image_paste_mode', IMAGE_PASTE_MODE_FAST),
                })
    
    def run(self):
        try:
            self.sio.connect(self.server_url)
            self.sio.wait()
        except Exception as e:
            print(f"Connection failed: {e}")
    
    def stop(self):
        self.running = False
        if self.sio.connected:
            self.sio.disconnect()


class AiProcessThread(QThread):
    """Run AI processing away from the PyQt UI thread."""
    ai_finished = pyqtSignal(object)

    def __init__(self, settings, rule, prompt_text, original_text):
        super().__init__()
        normalized = normalize_ai_settings(settings)
        self.api_settings = normalized.get("api", {})
        self.rule = dict(rule or {})
        self.prompt_text = prompt_text
        self.original_text = original_text

    def run(self):
        try:
            ai_text = call_openai_compatible(
                self.api_settings,
                self.rule.get("system_prompt", ""),
                self.prompt_text,
            )
            self.ai_finished.emit({
                "ok": True,
                "text": ai_text,
                "rule": self.rule,
                "prompt_text": self.prompt_text,
                "original_text": self.original_text,
            })
        except Exception as e:
            self.ai_finished.emit({
                "ok": False,
                "error": str(e),
                "rule": self.rule,
                "prompt_text": self.prompt_text,
                "original_text": self.original_text,
            })


class AiTestThread(QThread):
    """Test API connectivity away from the settings dialog thread."""
    test_finished = pyqtSignal(object)

    def __init__(self, api_settings):
        super().__init__()
        self.api_settings = dict(api_settings or {})

    def run(self):
        try:
            message = test_openai_compatible(self.api_settings)
            self.test_finished.emit({
                "ok": True,
                "message": message,
            })
        except Exception as e:
            self.test_finished.emit({
                "ok": False,
                "error": str(e),
            })


class ImageThumbLabel(QLabel):
    clicked = pyqtSignal(int)
    copy_requested = pyqtSignal(int)
    
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)
    
    def show_menu(self, position):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #fffdf7;
                color: #111827;
                border: 2px solid #111827;
                border-radius: 6px;
                font-size: 18px;
                padding: 6px;
            }
            QMenu::item {
                color: #111827;
                padding: 8px 18px;
                background: transparent;
            }
            QMenu::item:selected {
                color: #111827;
                background: #fef3c7;
            }
        """)
        copy_action = menu.addAction("复制这张图片")
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            self.copy_requested.emit(self.index)


class AiSettingsDialog(QDialog):
    """Settings dialog for API credentials and wake-word rules."""

    def __init__(self, settings, parent=None, font_size=DEFAULT_PC_FONT_SIZE):
        super().__init__(parent)
        self.settings = normalize_ai_settings(copy_settings(settings))
        self.font_size = clamp_pc_font_size(font_size)
        self.saved_font_size = self.font_size
        self.current_rule_index = -1
        self.test_worker = None
        self.init_ui()
        self.load_api_fields()
        self.refresh_rule_list()
        if self.settings.get("rules"):
            self.rule_list.setCurrentRow(0)

    def control_height(self):
        return max(38, self.font_size + 20)

    def init_ui(self):
        self.setWindowTitle("AI 设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        icon_path = app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.resize(max(1450, self.font_size * 58), max(980, self.font_size * 38))
        self.setMinimumSize(max(1100, self.font_size * 44), max(760, self.font_size * 30))
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.font_decrease_btn = QPushButton("A-")
        self.font_decrease_btn.setObjectName("compactButton")
        self.font_decrease_btn.clicked.connect(lambda: self.change_font_size(-1))
        self.font_size_label = QLabel("")
        self.font_size_label.setAlignment(Qt.AlignCenter)
        self.font_increase_btn = QPushButton("A+")
        self.font_increase_btn.setObjectName("compactButton")
        self.font_increase_btn.clicked.connect(lambda: self.change_font_size(1))

        api_group = QGroupBox("AI 接入配置")
        api_form = QFormLayout(api_group)
        api_form.setLabelAlignment(Qt.AlignRight)
        api_form.setVerticalSpacing(8)
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumHeight(self.control_height())
        for provider_id, preset in AI_PROVIDER_PRESETS.items():
            self.provider_combo.addItem(preset["label"], provider_id)
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_toggle_action = self.api_key_input.addAction(
            lucide_icon("eye", UI_COLORS["muted"], 18),
            QLineEdit.TrailingPosition,
        )
        self.api_key_toggle_action.triggered.connect(self.toggle_api_key_visibility)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("模型名")
        for input_widget in (self.base_url_input, self.api_key_input, self.model_input):
            input_widget.setMinimumHeight(self.control_height())
        api_form.addRow("Provider", self.provider_combo)
        api_form.addRow("Base URL", self.base_url_input)
        api_form.addRow("API Key", self.api_key_input)
        api_form.addRow("Model", self.model_input)

        api_actions = QHBoxLayout()
        self.test_api_btn = QPushButton("测试连接")
        self.test_api_btn.setObjectName("primaryButton")
        self.test_api_btn.setIcon(lucide_icon("link", "#ffffff", 18))
        self.test_api_btn.clicked.connect(self.test_api_connection)
        self.open_log_btn = QPushButton("打开日志")
        self.open_log_btn.setIcon(lucide_icon("file", UI_COLORS["ink"], 18))
        self.open_log_btn.clicked.connect(self.open_ai_log)
        self.test_status_label = QLabel("日志会记录到 ai-assistant.log")
        self.test_status_label.setWordWrap(True)
        api_actions.addWidget(self.test_api_btn)
        api_actions.addWidget(self.open_log_btn)
        api_actions.addWidget(self.test_status_label, 1)
        api_form.addRow("", api_actions)
        layout.addWidget(api_group)

        behavior_group = QGroupBox("运行偏好")
        behavior_layout = QHBoxLayout(behavior_group)
        self.show_title_check = QCheckBox("AI 处理中显示窗口标题")
        self.save_history_check = QCheckBox("记录原始文本和 AI 结果")
        self.startup_check = QCheckBox("开机自动启动")
        
        font_container = QWidget()
        font_layout = QHBoxLayout(font_container)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.setSpacing(6)
        
        font_title = QLabel("字体大小")
        font_title.setObjectName("fontTitle")
        font_layout.addWidget(font_title)
        font_layout.addWidget(self.font_decrease_btn)
        font_layout.addWidget(self.font_size_label)
        font_layout.addWidget(self.font_increase_btn)
        
        behavior_layout.addWidget(self.show_title_check, 1)
        behavior_layout.addWidget(self.save_history_check, 1)
        behavior_layout.addWidget(self.startup_check, 1)
        behavior_layout.addWidget(font_container, 1)
        layout.addWidget(behavior_group)

        rules_group = QGroupBox("唤醒规则")
        rules_layout = QHBoxLayout(rules_group)
        rules_layout.setSpacing(12)

        rules_left = QVBoxLayout()
        self.rule_list = QListWidget()
        self.rule_list.setMinimumWidth(260)
        self.rule_list.currentRowChanged.connect(self.on_rule_selection_changed)
        rules_left.addWidget(self.rule_list, 1)

        rule_buttons = QHBoxLayout()
        add_rule_btn = QPushButton("新增")
        add_rule_btn.setIcon(lucide_icon("plus", UI_COLORS["ink"], 18))
        add_rule_btn.clicked.connect(self.add_rule)
        delete_rule_btn = QPushButton("删除")
        delete_rule_btn.setIcon(lucide_icon("trash", UI_COLORS["ink"], 18))
        delete_rule_btn.clicked.connect(self.delete_rule)
        rule_buttons.addWidget(add_rule_btn)
        rule_buttons.addWidget(delete_rule_btn)
        rules_left.addLayout(rule_buttons)
        rules_layout.addLayout(rules_left, 1)

        rule_form = QFormLayout()
        rule_form.setLabelAlignment(Qt.AlignRight)
        rule_form.setVerticalSpacing(8)
        self.rule_enabled_check = QCheckBox("启用")
        self.button_enabled_check = QCheckBox("显示为手机按钮")
        rule_checks_layout = QHBoxLayout()
        rule_checks_layout.addWidget(self.rule_enabled_check)
        rule_checks_layout.addWidget(self.button_enabled_check)
        rule_checks_layout.addStretch()
        
        self.wake_word_input = QLineEdit()
        self.wake_word_input.setMinimumHeight(self.control_height())
        self.button_label_input = QLineEdit()
        self.button_label_input.setMinimumHeight(self.control_height())
        self.button_label_input.setPlaceholderText("手机按钮名称，留空则使用唤醒词")
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.setMinimumHeight(self.control_height())
        self.match_mode_combo.addItem("包含唤醒词", "contains")
        self.match_mode_combo.addItem("以唤醒词开头", "prefix")
        self.output_action_combo = QComboBox()
        self.output_action_combo.setMinimumHeight(self.control_height())
        self.output_action_combo.addItem("跟随手机按钮", "follow")
        self.output_action_combo.addItem("强制传递", "paste")
        self.output_action_combo.addItem("强制发送", "send")
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setFixedHeight(self.prompt_input_height())
        self.system_prompt_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.system_prompt_input.setPlaceholderText("系统提示词")
        rule_form.addRow("", rule_checks_layout)
        rule_form.addRow("唤醒词", self.wake_word_input)
        rule_form.addRow("按钮名称", self.button_label_input)
        rule_form.addRow("匹配方式", self.match_mode_combo)
        rule_form.addRow("输出动作", self.output_action_combo)
        rule_form.addRow("系统提示词", self.system_prompt_input)
        rules_layout.addLayout(rule_form, 2)
        layout.addWidget(rules_group, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self.accept_settings)
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        self.restore_defaults_btn = QPushButton("恢复默认设置")
        self.restore_defaults_btn.setIcon(lucide_icon("rotate", UI_COLORS["ink"], 18))
        self.restore_defaults_btn.clicked.connect(self.restore_default_settings)
        footer.addWidget(self.restore_defaults_btn)
        footer.addStretch()
        footer.addWidget(buttons)
        layout.addLayout(footer)

        self.apply_dialog_style()
        self.update_font_size_label()

    def apply_dialog_style(self):
        self.provider_combo.setMinimumHeight(self.control_height())
        for input_widget in (self.base_url_input, self.api_key_input, self.model_input):
            input_widget.setMinimumHeight(self.control_height())
        for input_widget in (self.wake_word_input, self.button_label_input):
            input_widget.setMinimumHeight(self.control_height())
        for combo in (self.match_mode_combo, self.output_action_combo):
            combo.setMinimumHeight(self.control_height())
        self.system_prompt_input.setFixedHeight(self.prompt_input_height())
        self.resize(max(1450, self.font_size * 58), max(980, self.font_size * 38))
        self.setMinimumSize(max(1100, self.font_size * 44), max(760, self.font_size * 30))
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background: {UI_COLORS['page']};
                color: {UI_COLORS['ink']};
                font-family: 'Microsoft YaHei UI';
                font-size: {self.font_size}px;
            }}
            QLabel, QCheckBox {{ background: transparent; }}
            QGroupBox {{
                background: {UI_COLORS['surface']};
                border: 1px solid {UI_COLORS['line']};
                border-radius: 14px;
                margin-top: 16px;
                padding: 16px 14px 14px;
                font-weight: 800;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: {UI_COLORS['ink']};
            }}
            QLineEdit, QTextEdit, QListWidget, QComboBox {{
                background: #ffffff;
                color: {UI_COLORS['ink']};
                border: 1px solid {UI_COLORS['line']};
                border-radius: 8px;
                padding: 7px 10px;
                selection-background-color: {UI_COLORS['brand']};
                font-size: {self.font_size}px;
            }}
            QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QComboBox:focus {{
                border: 1px solid {UI_COLORS['brand']};
            }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QListWidget::item {{
                min-height: {self.font_size + 14}px;
                padding: 6px 8px;
                border-radius: 7px;
            }}
            QListWidget::item:selected {{
                color: {UI_COLORS['brand']};
                background: {UI_COLORS['brand_soft']};
            }}
            QCheckBox {{ spacing: 9px; }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border-color: {UI_COLORS['brand']};
            }}
            QCheckBox::indicator:checked {{
                border-color: {UI_COLORS['brand']};
                background-color: {UI_COLORS['brand']};
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZmZmZmZmIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBvbHlsaW5lIHBvaW50cz0iMjAgNiA5IDE3IDQgMTIiLz48L3N2Zz4=);
            }}
            QCheckBox::indicator:disabled {{
                background-color: #f2f4f8;
                border-color: #cbd5e1;
            }}
            QPushButton {{
                background: #ffffff;
                color: {UI_COLORS['ink']};
                border: 1px solid {UI_COLORS['line']};
                border-radius: 9px;
                min-height: 34px;
                padding: 6px 14px;
                font-size: {self.font_size}px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #f5f4ff; border-color: #cbc7ff; }}
            QPushButton#primaryButton {{
                color: #ffffff;
                background: {UI_COLORS['brand']};
                border-color: {UI_COLORS['brand']};
            }}
            QPushButton#primaryButton:hover {{ background: {UI_COLORS['brand_hover']}; }}
            QPushButton#compactButton {{ min-width: 44px; max-width: 56px; padding: 4px 8px; }}
            QPushButton:disabled {{ color: #a2a8b6; background: #f2f4f8; }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: #cfd4e2; border-radius: 5px; min-height: 28px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def prompt_input_height(self):
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(self.font_size)
        line_height = QFontMetrics(font).lineSpacing()
        return max(64, line_height * 2 + 22)

    def update_font_size_label(self):
        self.font_size_label.setText(f"{self.font_size}px")
        self.font_decrease_btn.setEnabled(self.font_size > MIN_PC_FONT_SIZE)
        self.font_increase_btn.setEnabled(self.font_size < MAX_PC_FONT_SIZE)

    def change_font_size(self, delta):
        self.font_size = clamp_pc_font_size(self.font_size + delta)
        self.update_font_size_label()
        self.apply_dialog_style()

    def toggle_api_key_visibility(self):
        visible = self.api_key_input.echoMode() == QLineEdit.Normal
        self.api_key_input.setEchoMode(QLineEdit.Password if visible else QLineEdit.Normal)

    def restore_default_settings(self):
        """Restore defaults in the dialog; changes are persisted only after Save."""
        self.settings = normalize_ai_settings(copy_settings(DEFAULT_AI_SETTINGS))
        self.current_rule_index = -1
        self.load_api_fields()
        self.refresh_rule_list()
        if self.settings.get("rules"):
            self.rule_list.setCurrentRow(0)
        self.test_status_label.setText("已恢复默认值，点击保存后生效。")

    def load_api_fields(self):
        api = self.settings.get("api", {})
        behavior = self.settings.get("behavior", {})
        self.set_combo_value(self.provider_combo, api.get("provider", "openai"))
        self.base_url_input.setText(api.get("base_url", ""))
        self.api_key_input.setText(api.get("api_key", ""))
        self.model_input.setText(api.get("model", ""))
        self.show_title_check.setChecked(bool(behavior.get("show_processing_title", True)))
        self.save_history_check.setChecked(bool(behavior.get("save_ai_history", True)))
        self.startup_check.setChecked(is_startup_enabled())

    def current_api_settings(self):
        return {
            "provider": self.provider_combo.currentData(),
            "base_url": self.base_url_input.text().strip(),
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_input.text().strip(),
        }

    def on_provider_changed(self):
        provider_id = self.provider_combo.currentData()
        preset = AI_PROVIDER_PRESETS.get(provider_id, {})
        base_url = preset.get("base_url", "")
        if base_url:
            self.base_url_input.setText(base_url)

    def test_api_connection(self):
        if self.test_worker and self.test_worker.isRunning():
            return
        self.test_api_btn.setEnabled(False)
        self.test_status_label.setText("测试中...")
        self.test_worker = AiTestThread(self.current_api_settings())
        self.test_worker.test_finished.connect(self.on_api_test_finished)
        self.test_worker.finished.connect(lambda: self.test_api_btn.setEnabled(True))
        self.test_worker.start()

    def on_api_test_finished(self, result):
        if result.get("ok"):
            message = (result.get("message") or "").strip().replace("\n", " ")
            self.test_status_label.setText(f"测试成功：{message[:80]}")
        else:
            error = str(result.get("error", "未知错误")).replace("\n", " ")
            self.test_status_label.setText(f"测试失败：{error[:140]}")

    def open_ai_log(self):
        path = ai_log_file_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8"):
                    pass
            os.startfile(path)
        except Exception as e:
            self.test_status_label.setText(f"打开日志失败：{e}")

    def refresh_rule_list(self):
        self.rule_list.blockSignals(True)
        self.rule_list.clear()
        for rule in self.settings.get("rules", []):
            enabled = "☑" if rule.get("enabled") else "☐"
            button = "按钮" if rule.get("button_enabled") else "无按钮"
            mode = "包含" if rule.get("match_mode") == "contains" else "开头"
            self.rule_list.addItem(f"{enabled} {rule.get('wake_word', '')} · {button} · {mode}")
        self.rule_list.blockSignals(False)

    def on_rule_selection_changed(self, row):
        self.save_current_rule()
        self.current_rule_index = row
        self.load_rule_into_form(row)

    def load_rule_into_form(self, row):
        rules = self.settings.get("rules", [])
        enabled = 0 <= row < len(rules)
        for widget in (
            self.rule_enabled_check,
            self.button_enabled_check,
            self.wake_word_input,
            self.button_label_input,
            self.match_mode_combo,
            self.output_action_combo,
            self.system_prompt_input,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.rule_enabled_check.setChecked(False)
            self.button_enabled_check.setChecked(False)
            self.wake_word_input.clear()
            self.button_label_input.clear()
            self.system_prompt_input.clear()
            return

        rule = rules[row]
        self.rule_enabled_check.setChecked(bool(rule.get("enabled", True)))
        self.button_enabled_check.setChecked(bool(rule.get("button_enabled", True)))
        self.wake_word_input.setText(rule.get("wake_word", ""))
        self.button_label_input.setText(rule.get("button_label", ""))
        self.set_combo_value(self.match_mode_combo, rule.get("match_mode", "contains"))
        self.set_combo_value(self.output_action_combo, rule.get("output_action", "follow"))
        self.system_prompt_input.setPlainText(rule.get("system_prompt", ""))

    def save_current_rule(self):
        rules = self.settings.get("rules", [])
        row = self.current_rule_index
        if row < 0 or row >= len(rules):
            return
        rules[row] = {
            "id": rules[row].get("id", ""),
            "enabled": self.rule_enabled_check.isChecked(),
            "button_enabled": self.button_enabled_check.isChecked(),
            "wake_word": self.wake_word_input.text().strip(),
            "button_label": self.button_label_input.text().strip(),
            "match_mode": self.match_mode_combo.currentData(),
            "output_action": self.output_action_combo.currentData(),
            "system_prompt": self.system_prompt_input.toPlainText().strip(),
        }

    def set_combo_value(self, combo, value):
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def add_rule(self):
        self.save_current_rule()
        rules = self.settings.setdefault("rules", [])
        rules.append({
            "enabled": True,
            "button_enabled": True,
            "wake_word": f"唤醒词{len(rules) + 1}",
            "button_label": f"按钮{len(rules) + 1}",
            "match_mode": "contains",
            "system_prompt": "请处理用户输入，并直接输出最终文本，不要输出思考过程。",
            "output_action": "follow",
        })
        self.refresh_rule_list()
        self.rule_list.setCurrentRow(len(rules) - 1)

    def delete_rule(self):
        rules = self.settings.get("rules", [])
        row = self.rule_list.currentRow()
        if len(rules) <= 1 or row < 0 or row >= len(rules):
            return
        del rules[row]
        self.current_rule_index = -1
        self.refresh_rule_list()
        self.rule_list.setCurrentRow(min(row, len(rules) - 1))

    def accept_settings(self):
        self.save_current_rule()
        try:
            set_startup_enabled(self.startup_check.isChecked())
        except Exception as e:
            self.test_status_label.setText(f"开机自启设置失败：{e}")
            return
        settings = {
            "api": {
                "provider": self.provider_combo.currentData(),
                "base_url": self.base_url_input.text().strip(),
                "api_key": self.api_key_input.text().strip(),
                "model": self.model_input.text().strip(),
            },
            "rules": self.settings.get("rules", []),
            "behavior": {
                "show_processing_title": self.show_title_check.isChecked(),
                "save_ai_history": self.save_history_check.isChecked(),
            },
        }
        self.settings = normalize_ai_settings(settings)
        self.saved_font_size = save_pc_ui_settings({"font_size": self.font_size})["font_size"]
        self.accept()

    def result_settings(self):
        return self.settings


class VoiceInputWindow(QMainWindow):
    """主窗口 - 精简版"""
    
    def __init__(self):
        super().__init__()
        self.is_pinned = True
        self.is_connected = False
        self.auto_input_mode = True
        self.received_images = []
        self.history_records = self.load_history()
        self.history_expanded = False
        self.ai_settings = load_ai_settings()
        self.pc_ui_settings = load_pc_ui_settings()
        self.ui_font_size = self.pc_ui_settings["font_size"]
        self.ai_workers = []
        self.init_ui()
        self.show_startup_warning()
        self.init_socket()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(self.main_window_width())
        self.collapsed_height = self.collapsed_window_height()
        self.expanded_height = self.expanded_window_height()
        self.setFixedSize(self.main_window_width(), self.collapsed_height)
        
        # 设置图标
        icon_path = app_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 默认置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # 中央部件
        central = QWidget()
        central.setObjectName("mainSurface")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(16)
        
        # 顶部栏：状态点 + 手机地址
        self.address_card = QFrame()
        self.address_card.setObjectName("addressCard")
        address_bar = QHBoxLayout(self.address_card)
        address_bar.setContentsMargins(18, 10, 14, 10)
        address_bar.setSpacing(12)
        
        # 状态指示（小圆点）
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(24)
        self.status_dot.setStyleSheet("color: #ef4444; font-size: 24px; border: none;")
        address_bar.addWidget(self.status_dot)
        self.status_text = QLabel("未连接")
        self.status_text.setObjectName("statusText")
        address_bar.addWidget(self.status_text)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setObjectName("addressDivider")
        address_bar.addWidget(divider)
        
        # 显示手机端访问地址
        local_ip = get_local_ip()
        self.access_url = f"http://{local_ip}:56789"
        self.ip_label = QLabel(f"地址：{self.access_url}")
        self.ip_label.setMinimumWidth(780)
        self.ip_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-family: 'Microsoft YaHei UI';
                font-size: 28px;
                font-weight: 700;
                border: none;
            }
        """)
        self.ip_label.setToolTip("点击复制手机访问地址")
        self.ip_label.setCursor(Qt.PointingHandCursor)
        self.ip_label.mousePressEvent = lambda e: self.copy_ip(local_ip)
        address_bar.addWidget(self.ip_label, 1)

        self.copy_address_btn = QPushButton()
        self.copy_address_btn.setObjectName("iconButton")
        self.copy_address_btn.setIcon(lucide_icon("copy", UI_COLORS["brand"], 22))
        self.copy_address_btn.setIconSize(QSize(22, 22))
        self.copy_address_btn.setToolTip("复制手机访问地址")
        self.copy_address_btn.clicked.connect(lambda: self.copy_ip(local_ip))
        address_bar.addWidget(self.copy_address_btn)
        layout.addWidget(self.address_card)
        
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)
        
        # 文本显示区域（低高度状态预览）
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setPlaceholderText("等待接收...")
        self.text_display.setFixedHeight(52)
        self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_display.setStyleSheet("""
            QTextEdit {
                background: #fffdf7;
                border: 2px solid #111827;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 22px;
                color: #334155;
            }
        """)
        control_bar.addWidget(self.text_display, 1)

        self.restart_btn = QPushButton("重启")
        self.restart_btn.setIcon(lucide_icon("rotate", UI_COLORS["brand"], 21))
        self.restart_btn.setIconSize(QSize(21, 21))
        self.restart_btn.setFixedSize(84, 52)
        self.restart_btn.setToolTip("重启语音输入助手")
        self.restart_btn.clicked.connect(self.restart_app)
        self.restart_btn.setStyleSheet("""
            QPushButton {
                background: #fff7ed;
                color: #111827;
                border: 2px solid #111827;
                border-radius: 12px;
                font-size: 21px;
                font-weight: 700;
            }
            QPushButton:hover { background: #fed7aa; }
            QPushButton:disabled { color: #9ca3af; background: #f3f4f6; }
        """)
        control_bar.addWidget(self.restart_btn)
        
        # 置顶按钮
        self.pin_btn = QPushButton("置顶")
        self.pin_btn.setIcon(lucide_icon("pin", UI_COLORS["brand"], 21))
        self.pin_btn.setIconSize(QSize(21, 21))
        self.pin_btn.setFixedSize(130, 52)
        self.pin_btn.setToolTip("取消置顶")
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.update_pin_style()
        control_bar.addWidget(self.pin_btn)
        
        self.history_btn = QPushButton("记录")
        self.history_btn.setIcon(lucide_icon("clock", UI_COLORS["success"], 21))
        self.history_btn.setIconSize(QSize(21, 21))
        self.history_btn.setFixedSize(84, 52)
        self.history_btn.setToolTip("展开最近记录")
        self.history_btn.clicked.connect(self.toggle_history_panel)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background: #ecfccb;
                color: #111827;
                border: 2px solid #111827;
                border-radius: 12px;
                font-size: 21px;
                font-weight: 700;
            }
            QPushButton:hover { background: #d9f99d; }
        """)
        control_bar.addWidget(self.history_btn)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setIcon(lucide_icon("settings", UI_COLORS["brand"], 21))
        self.settings_btn.setIconSize(QSize(21, 21))
        self.settings_btn.setFixedSize(84, 52)
        self.settings_btn.setToolTip("打开 AI 设置")
        self.settings_btn.clicked.connect(self.open_ai_settings)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: #e0f2fe;
                color: #111827;
                border: 2px solid #111827;
                border-radius: 12px;
                font-size: 21px;
                font-weight: 700;
            }
            QPushButton:hover { background: #bae6fd; }
        """)
        control_bar.addWidget(self.settings_btn)
        layout.addLayout(control_bar)
        
        self.history_panel = QWidget()
        self.history_panel.setVisible(False)
        history_panel_layout = QVBoxLayout(self.history_panel)
        history_panel_layout.setContentsMargins(0, 0, 0, 0)
        history_panel_layout.setSpacing(8)
        
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFixedHeight(520)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_scroll.setStyleSheet("""
            QScrollArea {
                background: #ffffff;
                border: 1px solid #e1e5ef;
                border-radius: 14px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #cfd4e2;
                border-radius: 5px;
            }
        """)
        self.history_container = QWidget()
        self.history_list_layout = QVBoxLayout(self.history_container)
        self.history_list_layout.setContentsMargins(12, 12, 12, 12)
        self.history_list_layout.setSpacing(12)
        self.history_scroll.setWidget(self.history_container)
        history_panel_layout.addWidget(self.history_scroll)
        layout.addWidget(self.history_panel)
        
        self.setStyleSheet(f"""
            QMainWindow {{ background: {UI_COLORS['page']}; }}
            QWidget#mainSurface {{
                background: {UI_COLORS['page']};
                color: {UI_COLORS['ink']};
                font-family: 'Microsoft YaHei UI';
            }}
            QFrame#addressCard {{
                background: #ffffff;
                border: 1px solid {UI_COLORS['line']};
                border-radius: 14px;
            }}
            QLabel#statusText {{
                color: {UI_COLORS['success']};
                background: transparent;
                border: none;
                font-weight: 800;
            }}
            QFrame#addressDivider {{ color: {UI_COLORS['line']}; background: {UI_COLORS['line']}; max-width: 1px; }}
            QPushButton#iconButton {{
                min-width: 46px;
                max-width: 46px;
                min-height: 42px;
                max-height: 42px;
                background: #fbfcff;
                border: 1px solid {UI_COLORS['line']};
                border-radius: 10px;
            }}
            QPushButton#iconButton:hover {{ background: {UI_COLORS['brand_soft']}; }}
        """)
        self.apply_pc_font_size_styles()
    
    def font_px(self, offset=0):
        return max(12, self.ui_font_size + offset)

    def control_button_size(self):
        height = max(52, self.font_px(0) + 32)
        width = max(84, self.font_px(0) * 3 + 18)
        pin_width = max(130, self.font_px(0) * 4 + 58)
        return width, height, pin_width

    def main_window_width(self):
        return max(900, self.font_px(0) * 20 + 420)

    def collapsed_window_height(self):
        return max(170, self.font_px(0) * 5 + 62)

    def expanded_window_height(self):
        return max(720, self.collapsed_window_height() + 570)

    def button_style(self, background, hover, disabled=False):
        disabled_style = ""
        if disabled:
            disabled_style = "QPushButton:disabled { color: #9ca3af; background: #f3f4f8; }"
        return f"""
            QPushButton {{
                background: {background};
                color: {UI_COLORS['ink']};
                border: 1px solid {UI_COLORS['line']};
                border-radius: 12px;
                font-size: {self.font_px(-1)}px;
                font-weight: 700;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background: {hover}; border-color: #cbc7ff; }}
            {disabled_style}
        """

    def apply_connection_style(self):
        color = "#22c55e" if self.is_connected else "#ef4444"
        self.status_dot.setStyleSheet(
            f"color: {color}; font-size: {self.font_px(2)}px; border: none;"
        )
        self.status_dot.setToolTip("已连接" if self.is_connected else "未连接")
        self.status_text.setText("已连接" if self.is_connected else "未连接")
        self.status_text.setStyleSheet(
            f"color: {color}; font-size: {self.font_px(1)}px; font-weight: 800; border: none;"
        )

    def apply_pc_font_size_styles(self):
        button_width, button_height, pin_width = self.control_button_size()
        self.collapsed_height = self.collapsed_window_height()
        self.expanded_height = self.expanded_window_height()
        self.setMinimumWidth(self.main_window_width())

        self.status_dot.setFixedWidth(max(24, self.font_px(4)))
        self.apply_connection_style()

        self.ip_label.setMinimumWidth(max(560, self.font_px(0) * 22))
        self.ip_label.setStyleSheet(f"""
            QLabel {{
                color: #334155;
                font-family: 'Microsoft YaHei UI';
                font-size: {self.font_px(1)}px;
                font-weight: 600;
                border: none;
                background: transparent;
            }}
        """)

        self.text_display.setFixedHeight(max(52, self.font_px(2) + 32))
        self.text_display.setStyleSheet(f"""
            QTextEdit {{
                background: #ffffff;
                border: 1px solid #8f87ff;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: {self.font_px(2)}px;
                color: #334155;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: #cfd4e2;
                border-radius: 5px;
            }}
        """)

        self.restart_btn.setFixedSize(button_width, button_height)
        self.restart_btn.setStyleSheet(self.button_style("#ffffff", "#f1efff", disabled=True))
        self.pin_btn.setFixedSize(pin_width, button_height)
        self.update_pin_style()
        self.history_btn.setFixedSize(button_width, button_height)
        self.history_btn.setStyleSheet(self.button_style(UI_COLORS["success_soft"], "#dcfce7"))
        self.settings_btn.setFixedSize(button_width, button_height)
        self.settings_btn.setStyleSheet(self.button_style("#ffffff", "#f1efff"))

        self.history_scroll.setFixedHeight(max(520, self.font_px(0) * 15))
        window_height = self.expanded_height if self.history_expanded else self.collapsed_height
        self.setFixedSize(self.main_window_width(), window_height)
        if self.history_expanded:
            self.refresh_history_panel()

    def update_pin_style(self):
        """更新置顶按钮样式"""
        if self.is_pinned:
            self.pin_btn.setStyleSheet(self.button_style("#ffffff", "#f1efff"))
            self.pin_btn.setText("取消置顶")
        else:
            self.pin_btn.setStyleSheet(self.button_style("#ffffff", "#f1efff"))
            self.pin_btn.setText("置顶")
    
    def init_socket(self):
        """初始化 Socket 连接"""
        self.socket_thread = SocketIOThread("http://localhost:56789")
        self.socket_thread.text_received.connect(self.on_text_received)
        self.socket_thread.connection_changed.connect(self.on_connection_changed)
        self.socket_thread.start()

    def open_ai_settings(self):
        """Open AI settings and persist changes."""
        dialog = AiSettingsDialog(self.ai_settings, self, self.ui_font_size)
        if dialog.exec_() != QDialog.Accepted:
            return
        try:
            self.ai_settings = save_ai_settings(dialog.result_settings())
            self.pc_ui_settings = load_pc_ui_settings()
            self.ui_font_size = self.pc_ui_settings["font_size"]
            self.apply_pc_font_size_styles()
            self.show_temporary_title("AI 设置已保存")
        except Exception as e:
            self.text_display.setText(f"保存 AI 设置失败：{e}")
    
    def on_text_received(self, data):
        """收到手机端内容，支持旧文本格式和新的图片+文本格式。"""
        if isinstance(data, dict):
            action = data.get('action', 'paste')
            text = data.get('text', '')
            ai_rule_id = data.get('ai_rule_id', '')
            images = data.get('images') or []
            image_delay_ms = self.normalize_image_delay_ms(
                data.get('image_delay_ms', DEFAULT_IMAGE_SEND_DELAY_MS)
            )
            image_paste_mode = self.normalize_image_paste_mode(
                data.get('image_paste_mode', IMAGE_PASTE_MODE_FAST)
            )
        elif '|' in data:
            action, text = data.split('|', 1)
            ai_rule_id = ''
            images = []
            image_delay_ms = DEFAULT_IMAGE_SEND_DELAY_MS
            image_paste_mode = IMAGE_PASTE_MODE_FAST
        else:
            action, text = 'paste', data
            ai_rule_id = ''
            images = []
            image_delay_ms = DEFAULT_IMAGE_SEND_DELAY_MS
            image_paste_mode = IMAGE_PASTE_MODE_FAST
        
        self.set_received_images(images)

        wake_match = find_rule_by_id(ai_rule_id, text, self.ai_settings)
        if not wake_match:
            wake_match = find_wake_rule(text, self.ai_settings)
        if wake_match:
            self.start_ai_processing(action, text, images, image_delay_ms, image_paste_mode, wake_match)
            return

        self.handle_processed_text(
            action,
            text,
            images,
            image_delay_ms,
            image_paste_mode,
            original_text=text,
        )

    def start_ai_processing(self, action, original_text, images, image_delay_ms, image_paste_mode, wake_match):
        rule = wake_match.get("rule", {})
        prompt_text = wake_match.get("prompt_text", "")
        wake_word = rule.get("button_label") or rule.get("wake_word", "AI")
        if self.ai_settings.get("behavior", {}).get("show_processing_title", True):
            self.setWindowTitle(f"AI处理中：{wake_word}")
        self.text_display.setText(f"AI处理中：{wake_word}\n{prompt_text}")

        worker = AiProcessThread(self.ai_settings, rule, prompt_text, original_text)
        self.ai_workers.append(worker)
        worker.ai_finished.connect(
            lambda result, worker=worker, action=action, images=images,
                   image_delay_ms=image_delay_ms, image_paste_mode=image_paste_mode:
                self.on_ai_processing_finished(result, action, images, image_delay_ms, image_paste_mode, worker)
        )
        worker.finished.connect(lambda worker=worker: self.cleanup_ai_worker(worker))
        worker.start()

    def on_ai_processing_finished(self, result, action, images, image_delay_ms, image_paste_mode, worker):
        rule = result.get("rule", {})
        wake_word = rule.get("wake_word", "")
        original_text = result.get("original_text", "")

        if result.get("ok"):
            final_action = self.resolve_ai_action(action, rule)
            self.handle_processed_text(
                final_action,
                result.get("text", ""),
                images,
                image_delay_ms,
                image_paste_mode,
                original_text=original_text,
                ai_rule=wake_word,
            )
        else:
            error = result.get("error", "AI 处理失败")
            print(f"AI 处理失败，已原样传递: {error}")
            self.handle_processed_text(
                action,
                original_text,
                images,
                image_delay_ms,
                image_paste_mode,
                original_text=original_text,
                ai_rule=wake_word,
                ai_error=error,
            )
        self.cleanup_ai_worker(worker)

    def cleanup_ai_worker(self, worker):
        if worker in self.ai_workers:
            self.ai_workers.remove(worker)

    def resolve_ai_action(self, original_action, rule):
        output_action = rule.get("output_action", "follow")
        if output_action in ("paste", "send"):
            return output_action
        return original_action

    def handle_processed_text(
        self,
        action,
        text,
        images,
        image_delay_ms,
        image_paste_mode=IMAGE_PASTE_MODE_FAST,
        original_text=None,
        ai_rule=None,
        ai_error=None,
    ):
        self.add_history_record(
            action,
            text,
            images,
            original_text=original_text,
            ai_rule=ai_rule,
            ai_error=ai_error,
        )

        if self.auto_input_mode:
            try:
                pasted_images = 0
                clean_images = self.clone_image_payloads(images)
                total_images = len(clean_images)
                image_paste_mode = self.normalize_image_paste_mode(image_paste_mode)
                log_client_event(
                    f"auto input start action={action} text_len={len(text or '')} "
                    f"images={total_images} image_delay_ms={image_delay_ms} "
                    f"image_paste_mode={image_paste_mode}"
                )
                for index, image in enumerate(clean_images, start=1):
                    paste_delay = self.image_paste_settle_seconds(total_images, image_paste_mode)
                    if self.paste_image(image, index=index, total=total_images, delay_seconds=paste_delay):
                        pasted_images += 1
                    if (
                        image_paste_mode == IMAGE_PASTE_MODE_SAFE
                        and
                        total_images > IMAGE_PASTE_BATCH_SIZE
                        and index < total_images
                        and index % IMAGE_PASTE_BATCH_SIZE == 0
                    ):
                        self.setWindowTitle(
                            f"等待目标应用处理图片 {index}/{total_images}"
                        )
                        QApplication.processEvents()
                        log_client_event(
                            f"batch pause after image {index}/{total_images} "
                            f"seconds={IMAGE_PASTE_BATCH_PAUSE_SECONDS}"
                        )
                        time.sleep(IMAGE_PASTE_BATCH_PAUSE_SECONDS)
                log_client_event(
                    f"auto input pasted images={pasted_images}/{total_images} action={action} "
                    f"image_paste_mode={image_paste_mode}"
                )
                
                if action == 'send':
                    if pasted_images:
                        delay_seconds = image_delay_ms // 1000
                        self.setWindowTitle(f"等待图片上传 {delay_seconds} 秒")
                        QTimer.singleShot(
                            image_delay_ms,
                            lambda text=text: self.finish_image_send(text),
                        )
                    else:
                        if text:
                            self.paste_text(text)
                        time.sleep(TEXT_PASTE_SETTLE_SECONDS)
                        pyautogui.press('enter')
                        self.show_temporary_title("✅ 已发送")
                else:
                    if pasted_images and text:
                        self.setWindowTitle("等待图片粘贴")
                        QTimer.singleShot(
                            IMAGE_TEXT_PASTE_DELAY_MS,
                            lambda text=text: self.finish_image_paste(text),
                        )
                    elif pasted_images:
                        QTimer.singleShot(
                            IMAGE_TEXT_PASTE_DELAY_MS,
                            lambda: self.show_temporary_title("📋 已传递"),
                        )
                    else:
                        if text:
                            self.paste_text(text)
                        self.show_temporary_title("📋 已传递")
            except Exception as e:
                log_client_event(f"auto input failed error={e}")
                print(f"自动输入失败: {e}")
                self.text_display.setText(self.format_display_text(text, images))
        else:
            display_text = self.format_display_text(text, images)
            current = self.text_display.toPlainText()
            if current:
                self.text_display.setText(current + "\n" + display_text)
            else:
                self.text_display.setText(display_text)
    
    def image_paste_settle_seconds(self, total_images, image_paste_mode=IMAGE_PASTE_MODE_FAST):
        """Use a slower cadence for multi-image paste targets such as MasterGo."""
        if image_paste_mode == IMAGE_PASTE_MODE_SAFE and total_images and total_images > 1:
            return IMAGE_MULTI_PASTE_SETTLE_SECONDS
        return IMAGE_PASTE_SETTLE_SECONDS
    
    def paste_image(self, image, index=None, total=None, delay_seconds=None):
        """把图片放入系统剪贴板并粘贴到当前光标位置。"""
        qimage = self.image_to_qimage(image)
        delay_seconds = (
            self.image_paste_settle_seconds(total)
            if delay_seconds is None
            else delay_seconds
        )

        if total and total > 1 and index:
            self.setWindowTitle(f"粘贴图片 {index}/{total}")
            QApplication.processEvents()
        log_client_event(
            f"paste image {index or 1}/{total or 1} "
            f"name={image.get('name', '')} data_chars={len(image.get('data', '') or '')} "
            f"settle_seconds={delay_seconds}"
        )
        QApplication.clipboard().setImage(qimage)
        QApplication.processEvents()
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(delay_seconds)
        return True
    
    def image_to_qimage(self, image):
        """把手机端 data URL 图片转成 QImage。"""
        data_url = image.get('data', '')
        if not data_url:
            raise ValueError("image data missing")
        
        if ',' in data_url:
            data_url = data_url.split(',', 1)[1]
        image_bytes = base64.b64decode(data_url)
        
        qimage = QImage()
        if not qimage.loadFromData(image_bytes):
            raise ValueError("image decode failed")
        return qimage
    
    def set_received_images(self, images):
        """在 PC 端保留最近一次收到的图片，供复制和预览。"""
        self.received_images = [
            image for image in images
            if isinstance(image, dict) and image.get('data')
        ]
        if self.history_expanded:
            self.refresh_history_panel()
    
    def copy_image_by_index(self, index):
        if index < 0 or index >= len(self.received_images):
            return
        self.copy_image_object(self.received_images[index])
    
    def copy_all_images(self):
        if not self.received_images:
            return
        self.copy_images_to_clipboard(self.received_images)
    
    def preview_image(self, index):
        if index < 0 or index >= len(self.received_images):
            return
        try:
            qimage = self.image_to_qimage(self.received_images[index])
        except Exception as e:
            self.text_display.setText(f"预览图片失败：{e}")
            return
        self.preview_qimage(qimage)
    
    def preview_qimage(self, qimage):
        dialog = QDialog(self)
        dialog.setWindowTitle("图片预览")
        icon_path = app_icon_path()
        if icon_path:
            dialog.setWindowIcon(QIcon(icon_path))
        dialog.resize(1000, 760)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(22, 18, 22, 22)
        dialog_layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_icon = QLabel()
        title_icon.setPixmap(lucide_icon("image", UI_COLORS["brand"], 24).pixmap(24, 24))
        title = QLabel("图片预览")
        title.setObjectName("previewTitle")
        close_btn = QPushButton()
        close_btn.setObjectName("previewClose")
        close_btn.setIcon(lucide_icon("x", UI_COLORS["ink"], 22))
        close_btn.setIconSize(QSize(22, 22))
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(title_icon)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        dialog_layout.addLayout(header)
        
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setToolTip("右键复制图片")
        label.setContextMenuPolicy(Qt.CustomContextMenu)
        label.customContextMenuRequested.connect(
            lambda position: self.show_preview_image_menu(label, position, qimage, dialog)
        )
        pixmap = QPixmap.fromImage(qimage)
        scaled = pixmap.scaled(940, 590, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled)
        label.setObjectName("previewImage")
        
        scroll = QScrollArea()
        scroll.setObjectName("previewScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        scroll.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
        scroll.viewport().customContextMenuRequested.connect(
            lambda position: self.show_preview_image_menu(scroll.viewport(), position, qimage, dialog)
        )
        dialog_layout.addWidget(scroll)

        footer = QHBoxLayout()
        footer.addStretch()
        download_btn = QPushButton("下载")
        download_btn.setObjectName("previewDownload")
        download_btn.setIcon(lucide_icon("download", UI_COLORS["brand"], 20))
        download_btn.setIconSize(QSize(20, 20))
        download_btn.clicked.connect(lambda: self.save_preview_image(qimage, dialog))
        footer.addWidget(download_btn)
        dialog_layout.addLayout(footer)

        dialog.setStyleSheet(f"""
            QDialog {{ background: {UI_COLORS['page']}; }}
            QLabel {{ background: transparent; color: {UI_COLORS['ink']}; font-family: 'Microsoft YaHei UI'; }}
            QLabel#previewTitle {{ font-size: 22px; font-weight: 800; }}
            QScrollArea#previewScroll {{
                background: #ffffff;
                border: 1px solid {UI_COLORS['line']};
                border-radius: 14px;
            }}
            QLabel#previewImage {{ background: #ffffff; padding: 10px; }}
            QPushButton {{
                min-height: 42px;
                padding: 0 18px;
                color: {UI_COLORS['ink']};
                background: #ffffff;
                border: 1px solid {UI_COLORS['line']};
                border-radius: 10px;
                font-size: 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {UI_COLORS['brand_soft']}; border-color: #cbc7ff; }}
            QPushButton#previewClose {{ min-width: 42px; max-width: 42px; padding: 0; }}
            QPushButton#previewDownload {{ color: {UI_COLORS['brand']}; }}
        """)
        dialog.exec_()

    def save_preview_image(self, qimage, dialog):
        path, _ = QFileDialog.getSaveFileName(
            dialog,
            "保存图片",
            "图片.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;所有文件 (*.*)",
        )
        if not path:
            return
        if qimage.save(path):
            self.show_temporary_title("图片已保存")
        else:
            self.text_display.setText("保存图片失败，请检查目标目录权限。")

    def show_preview_image_menu(self, owner, position, qimage, dialog):
        menu = QMenu(owner)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                color: #111827;
                border: 1px solid #e1e5ef;
                border-radius: 8px;
                font-size: 18px;
                padding: 6px;
            }
            QMenu::item {
                color: #111827;
                padding: 8px 18px;
                background: transparent;
            }
            QMenu::item:selected {
                color: #111827;
                background: #f1efff;
            }
        """)
        copy_action = menu.addAction("复制这张图片")
        action = menu.exec_(owner.mapToGlobal(position))
        if action == copy_action and self.copy_qimage_to_clipboard(qimage):
            dialog.accept()

    def copy_qimage_to_clipboard(self, qimage):
        try:
            QApplication.clipboard().setImage(qimage)
            self.show_temporary_title("已复制图片")
            return True
        except Exception as e:
            self.text_display.setText(f"复制图片失败：{e}")
            return False
    
    def copy_image_object(self, image):
        try:
            qimage = self.image_to_qimage(image)
        except Exception as e:
            self.text_display.setText(f"复制图片失败：{e}")
            return
        self.copy_qimage_to_clipboard(qimage)
    
    def copy_images_to_clipboard(self, images):
        images = self.clone_image_payloads(images)
        if not images:
            return
        try:
            mime = QMimeData()
            html_images = []
            for image in images:
                data = image.get('data', '')
                if data:
                    html_images.append(f'<img src="{data}">')
            if html_images:
                mime.setHtml("<br>".join(html_images))
            mime.setImageData(self.image_to_qimage(images[0]))
            QApplication.clipboard().setMimeData(mime)
            self.show_temporary_title("已复制全部图片")
        except Exception as e:
            self.text_display.setText(f"复制图片失败：{e}")
    
    def make_history_button(self, text, callback, width=132):
        button = QPushButton(text)
        dynamic_width = max(width, self.font_px(-2) * len(text) + 36)
        button.setFixedSize(dynamic_width, max(40, self.font_px(-2) + 22))
        button.clicked.connect(callback)
        button.setStyleSheet(f"""
            QPushButton {{
                background: #ffffff;
                color: {UI_COLORS['brand']};
                border: 1px solid {UI_COLORS['line']};
                border-radius: 8px;
                font-size: {self.font_px(-2)}px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {UI_COLORS['brand_soft']}; border-color: #cbc7ff; }}
        """)
        return button
    
    def toggle_history_panel(self):
        self.history_expanded = not self.history_expanded
        self.history_panel.setVisible(self.history_expanded)
        self.history_btn.setText("收起" if self.history_expanded else "记录")
        self.setFixedSize(
            self.main_window_width(),
            self.expanded_height if self.history_expanded else self.collapsed_height,
        )
        if self.history_expanded:
            self.refresh_history_panel()
    
    def refresh_history_panel(self):
        while self.history_list_layout.count():
            item = self.history_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if not self.history_records:
            empty = QLabel("还没有记录")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"""
                QLabel {{
                    background: #ffffff;
                    color: #6b7280;
                    border: 1px dashed #cfd4e2;
                    border-radius: 10px;
                    font-size: {self.font_px(0)}px;
                    padding: 40px;
                }}
            """)
            self.history_list_layout.addWidget(empty)
        else:
            for record in self.history_records:
                self.history_list_layout.addWidget(self.create_history_item(record))
            self.history_list_layout.addStretch()
    
    def create_history_item(self, record):
        meta_font = QFont("SimHei")
        meta_font.setPixelSize(self.font_px(4))
        meta_font.setBold(True)
        text_font = QFont("SimHei")
        text_font.setPixelSize(self.font_px(4))
        text_font.setBold(True)
        text_lines = 4 if record.get("ai_rule") else 2
        text_height = QFontMetrics(text_font).lineSpacing() * text_lines + 8
        meta_height = QFontMetrics(meta_font).lineSpacing() + 4
        content_height = max(50 if record.get("images") else 42, self.font_px(-2) + 22)

        item = QFrame()
        item.setObjectName("historyCard")
        item.setFixedHeight(meta_height + text_height + content_height + 34)
        item.setStyleSheet("""
            QFrame#historyCard {
                background: #ffffff;
                border: 1px solid #e1e5ef;
                border-radius: 14px;
            }
        """)
        layout = QVBoxLayout(item)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        
        meta = QLabel(self.format_history_meta(record))
        meta.setFont(meta_font)
        meta.setFixedHeight(meta_height)
        meta.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        meta.setStyleSheet("color: #111827; border: none;")
        layout.addWidget(meta)
        
        text = QTextEdit()
        text.setFont(text_font)
        text.setPlainText(self.format_history_text(record))
        text.setReadOnly(True)
        text.setFocusPolicy(Qt.NoFocus)
        text.setFrameShape(QFrame.NoFrame)
        text.setLineWrapMode(QTextEdit.WidgetWidth)
        text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text.setFixedHeight(text_height)
        text.document().setDocumentMargin(0)
        text.setViewportMargins(0, 0, 0, 0)
        text.setStyleSheet("""
            QTextEdit {
                color: #111827;
                border: none;
                background: transparent;
                padding: 0;
            }
        """)
        layout.addWidget(text)
        
        images = self.clone_image_payloads(record.get("images", []))
        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        if images:
            image_row = QHBoxLayout()
            image_row.setSpacing(5)
            for image in images:
                try:
                    qimage = self.image_to_qimage(image)
                except Exception:
                    continue
                pixmap = QPixmap.fromImage(qimage).scaled(
                    44,
                    44,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                thumb = ImageThumbLabel(0)
                thumb.setFixedSize(50, 46)
                thumb.setAlignment(Qt.AlignCenter)
                thumb.setPixmap(pixmap)
                thumb.setToolTip("左键预览，右键复制")
                thumb.setStyleSheet("""
                    QLabel {
                        background: #ffffff;
                        border: 1px solid #e1e5ef;
                        border-radius: 8px;
                    }
                """)
                thumb.clicked.connect(lambda _index, img=image: self.preview_qimage(self.image_to_qimage(img)))
                thumb.copy_requested.connect(lambda _index, img=image: self.copy_image_object(img))
                image_row.addWidget(thumb)
            content_row.addLayout(image_row)
        
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        if record.get("text"):
            action_row.addWidget(
                self.make_history_button(
                    "复制结果" if record.get("ai_rule") and not record.get("ai_error") else "复制文本",
                    lambda _checked=False, text=record.get("text", ""): pyperclip.copy(text),
                )
            )
        original_text = record.get("original_text", "")
        if original_text and original_text != record.get("text", ""):
            action_row.addWidget(
                self.make_history_button(
                    "复制原文",
                    lambda _checked=False, text=original_text: pyperclip.copy(text),
                )
            )
        if images:
            action_row.addWidget(
                self.make_history_button(
                    "复制全部图片",
                    lambda _checked=False, imgs=images: self.copy_images_to_clipboard(imgs),
                    width=166,
                )
            )
        action_row.addStretch()
        content_row.addLayout(action_row)
        content_row.addStretch()
        layout.addLayout(content_row)
        return item

    def format_history_text(self, record):
        if record.get("ai_rule"):
            original_text = record.get("original_text", "")
            if record.get("ai_error"):
                return f"原文：{original_text}\nAI失败：{record.get('ai_error')}\n已原样处理：{record.get('text', '')}"
            return f"原文：{original_text}\nAI结果：{record.get('ai_text') or record.get('text', '')}"
        return record.get("text") or ("[仅图片]" if record.get("images") else "[空]")
    
    def format_history_meta(self, record):
        label = "发送" if record.get("action") == "send" else "传递"
        if record.get("ai_rule"):
            prefix = "AI失败" if record.get("ai_error") else f"AI·{record.get('ai_rule')}"
            label = f"{prefix} {label}"
        timestamp = time.localtime(record.get("time", time.time()))
        time_text = time.strftime("%H:%M:%S", timestamp)
        image_count = len(record.get("images") or [])
        return f"{label}  {time_text}  图片 {image_count}"
        
    def paste_text(self, text):
        """把文字放入系统剪贴板并粘贴到当前光标位置。"""
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(TEXT_PASTE_SETTLE_SECONDS)
    
    def normalize_image_delay_ms(self, value):
        """限制图片发送等待时间，避免异常值造成过长等待。"""
        try:
            delay_ms = int(value)
        except (TypeError, ValueError):
            delay_ms = DEFAULT_IMAGE_SEND_DELAY_MS
        return max(0, min(delay_ms, MAX_IMAGE_SEND_DELAY_MS))
    
    def normalize_image_paste_mode(self, value):
        """规范化手机端传来的图片粘贴速度模式。"""
        return IMAGE_PASTE_MODE_SAFE if value == IMAGE_PASTE_MODE_SAFE else IMAGE_PASTE_MODE_FAST
    
    def finish_image_send(self, text):
        """图片等待完成后，粘贴文字并回车发送。"""
        try:
            if text:
                self.paste_text(text)
            pyautogui.press('enter')
            self.show_temporary_title("✅ 已发送")
        except Exception as e:
            print(f"图片发送完成阶段失败: {e}")
            if text:
                self.text_display.setText(text)
    
    def finish_image_paste(self, text):
        """图片粘贴稳定后，再粘贴文字。"""
        try:
            if text:
                self.paste_text(text)
            self.show_temporary_title("📋 已传递")
        except Exception as e:
            print(f"图片传递完成阶段失败: {e}")
            if text:
                self.text_display.setText(text)
    
    def show_temporary_title(self, title):
        """短暂显示操作反馈。"""
        self.setWindowTitle(title)
        QTimer.singleShot(800, lambda: self.setWindowTitle(WINDOW_TITLE))
    
    def format_display_text(self, text, images):
        parts = []
        if images:
            parts.append(f"[图片 {len(images)} 张]")
        if text:
            parts.append(text)
        return "\n".join(parts)
    
    def on_connection_changed(self, connected):
        """连接状态变化"""
        self.is_connected = connected
        self.apply_connection_style()
    
    def show_startup_warning(self):
        warning = os.environ.get("VOICE_ASSISTANT_FIREWALL_WARNING")
        if not warning:
            return
        self.text_display.setText(warning)
        self.text_display.setToolTip(warning)
    
    def history_file_path(self):
        return os.path.join(runtime_data_dir(), "pc-history.json")
    
    def load_history(self):
        path = self.history_file_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as history_file:
                records = json.load(history_file)
            if isinstance(records, list):
                return records[:HISTORY_LIMIT]
        except Exception:
            pass
        return []
    
    def save_history(self):
        path = self.history_file_path()
        try:
            with open(path, "w", encoding="utf-8") as history_file:
                json.dump(self.history_records[:HISTORY_LIMIT], history_file, ensure_ascii=False)
        except Exception as e:
            self.text_display.setText(f"保存记录失败：{e}")
    
    def clone_image_payloads(self, images):
        return [
            {
                "name": image.get("name", ""),
                "type": image.get("type", ""),
                "data": image.get("data", ""),
            }
            for image in images
            if isinstance(image, dict) and image.get("data")
        ]
    
    def add_history_record(self, action, text, images, original_text=None, ai_rule=None, ai_error=None):
        clean_images = self.clone_image_payloads(images)
        if not (text or clean_images or original_text):
            return
        record = {
            "time": time.time(),
            "action": action,
            "text": text or "",
            "images": clean_images,
        }
        if ai_rule and self.ai_settings.get("behavior", {}).get("save_ai_history", True):
            record["ai_rule"] = ai_rule
            record["original_text"] = original_text or ""
            if ai_error:
                record["ai_error"] = ai_error
            else:
                record["ai_text"] = text or ""
        self.history_records.insert(0, record)
        self.history_records = self.history_records[:HISTORY_LIMIT]
        self.save_history()
        if self.history_expanded:
            self.refresh_history_panel()
    
    def restart_app(self):
        """重新启动完整助手进程。"""
        base_dir = launch_working_dir()
        command = launch_command()
        
        self.restart_btn.setEnabled(False)
        self.restart_btn.setText("重启中")
        QApplication.processEvents()
        
        try:
            subprocess.Popen(
                command,
                cwd=base_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            QTimer.singleShot(250, QApplication.instance().quit)
        except Exception as e:
            self.restart_btn.setEnabled(True)
            self.restart_btn.setText("重启")
            self.text_display.setText(f"重启失败：{e}")
    
    def toggle_pin(self):
        """切换置顶状态"""
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.pin_btn.setToolTip("取消置顶")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.pin_btn.setToolTip("置顶")
        self.update_pin_style()
        self.show()
    
    def copy_ip(self, ip):
        """复制IP地址"""
        url = f"http://{ip}:56789"
        QApplication.clipboard().setText(url)
        self.ip_label.setText("已复制!")
        QTimer.singleShot(1000, lambda: self.ip_label.setText(f"地址: {url}"))
    
    def closeEvent(self, event):
        """关闭事件"""
        self.socket_thread.stop()
        self.socket_thread.wait(1000)
        event.accept()


def main():
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    icon_path = app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = VoiceInputWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
