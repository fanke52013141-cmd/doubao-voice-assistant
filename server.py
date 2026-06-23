"""
Voice Sync 服务器
实现手机端与电脑端的实时文本同步
"""
import os
import sys
from flask import Flask, render_template, send_file, jsonify
from flask_socketio import SocketIO, emit

from ai_assistant import load_ai_settings, public_ai_buttons
from network_utils import get_local_ip, get_local_ip_candidates


def configure_text_streams():
    """Keep logging from crashing when text contains emoji or rare Unicode."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configure_text_streams()


def resource_path(relative_path):
    """Return a bundled resource path when running from PyInstaller."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


app = Flask(__name__, template_folder=resource_path("templates"))
app.config['SECRET_KEY'] = 'voice-sync-secret-key'
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    max_http_buffer_size=50 * 1024 * 1024,
)

@app.route('/')
def sender():
    """手机端发送页面"""
    return render_template('sender.html')


@app.route('/favicon.ico')
def favicon():
    """浏览器标签页图标"""
    icon_path = resource_path("语音输入助手.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("icon.ico")
    return send_file(icon_path, mimetype="image/x-icon")


@app.route('/ai-buttons')
def ai_buttons():
    """Expose safe AI button metadata to the phone page."""
    return jsonify({"buttons": public_ai_buttons(load_ai_settings())})


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print('客户端已连接', flush=True)


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print('客户端已断开', flush=True)


@socketio.on('send_text')
def handle_send_text(data):
    """接收并广播文本"""
    text = data.get('text', '')
    action = data.get('action', 'paste')  # 默认为粘贴
    ai_rule_id = str(data.get('ai_rule_id') or '').strip()
    image_paste_mode = 'safe' if data.get('image_paste_mode') == 'safe' else 'fast'
    images = data.get('images') or []
    images = [image for image in images if isinstance(image, dict) and image.get('data')]
    image_delay_ms = 0
    if images:
        try:
            image_delay_ms = int(data.get('image_delay_ms', 10000))
        except (TypeError, ValueError):
            image_delay_ms = 10000
        image_delay_ms = max(0, min(image_delay_ms, 60000))
    if text or images:
        print(
            f'收到文本: {text} (action: {action}, images: {len(images)}, '
            f'delay: {image_delay_ms}ms, paste_mode: {image_paste_mode})',
            flush=True,
        )
        # 广播给所有客户端（包含 action）
        emit(
            'receive_text',
            {
                'text': text,
                'action': action,
                'ai_rule_id': ai_rule_id,
                'images': images,
                'image_delay_ms': image_delay_ms,
                'image_paste_mode': image_paste_mode,
            },
            broadcast=True,
        )
        return {'ok': True, 'images': len(images)}
    return {'ok': False, 'error': 'empty payload'}


def main():
    local_ip = get_local_ip()
    lan_ips = get_local_ip_candidates()
    port = 56789
    print("\n" + "=" * 50)
    print("  Voice Sync Server Started")
    print("=" * 50)
    print(f"\n  [Mobile]  http://{local_ip}:{port}")
    if lan_ips:
        print(f"  [LAN IPs] {', '.join(lan_ips)}")
    print(f"  [Local]   http://localhost:{port}")
    print("\n  Press Ctrl+C to stop")
    print("=" * 50 + "\n")
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
    except OSError as e:
        if "Address already in use" in str(e) or "[WinError 10048]" in str(e):
            print(f"\nError: Port {port} is already in use!")
            print(f"   请检查是否有其他程序占用了 {port} 端口。")
            print("   正在尝试清理端口...")
            import os
            os.system(f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr ":{port}" ^| findstr "LISTENING"\') do taskkill /F /PID %a')
            return 1
        else:
            print(f"\nError: {e}")
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
