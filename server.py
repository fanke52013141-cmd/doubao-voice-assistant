"""
Voice Sync 服务器
实现手机端与电脑端的实时文本同步
"""
import os
import sys
import time
import uuid
from pathlib import Path
from flask import Flask, render_template, send_file, jsonify
from flask import request
from flask_socketio import SocketIO, emit

from ai_assistant import load_ai_settings, public_ai_button_groups
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
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
UPLOAD_TTL_SECONDS = 24 * 60 * 60
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.m4v'}


def upload_dir():
    root = Path(os.environ.get('APPDATA', os.path.dirname(os.path.abspath(__file__)))) / 'VoiceInputAssistant' / 'uploads'
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_uploads():
    cutoff = time.time() - UPLOAD_TTL_SECONDS
    for path in upload_dir().iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass
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
    icon_path = resource_path("voice-assistant-v2.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("语音输入助手.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("icon.ico")
    return send_file(icon_path, mimetype="image/x-icon")


@app.route('/ai-buttons')
def ai_buttons():
    """Expose safe AI button metadata to the phone page."""
    return jsonify(public_ai_button_groups(load_ai_settings()))


@app.post('/api/uploads')
def upload_video():
    cleanup_uploads()
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'ok': False, 'error': 'missing file'}), 400
    extension = Path(upload.filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS or not (upload.mimetype or '').startswith('video/'):
        return jsonify({'ok': False, 'error': 'unsupported video type'}), 415
    upload_id = uuid.uuid4().hex
    target = upload_dir() / f'{upload_id}{extension}'
    upload.save(target)
    return jsonify({'ok': True, 'upload': {
        'id': upload_id, 'name': Path(upload.filename).name, 'type': upload.mimetype,
        'size': target.stat().st_size, 'path': str(target),
    }})


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
    videos = data.get('videos') or []
    safe_upload_root = upload_dir().resolve()
    safe_videos = []
    for video in videos:
        if not isinstance(video, dict) or not video.get('path'):
            continue
        try:
            path = Path(video['path']).resolve()
            path.relative_to(safe_upload_root)
            if path.is_file() and path.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                safe_videos.append({**video, 'path': str(path)})
        except (OSError, ValueError):
            continue
    videos = safe_videos
    image_delay_ms = 0
    if images:
        try:
            image_delay_ms = int(data.get('image_delay_ms', 10000))
        except (TypeError, ValueError):
            image_delay_ms = 10000
        image_delay_ms = max(0, min(image_delay_ms, 60000))
    if text or images or videos:
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
                'videos': videos,
                'image_delay_ms': image_delay_ms,
                'image_paste_mode': image_paste_mode,
            },
            broadcast=True,
        )
        return {'ok': True, 'images': len(images), 'videos': len(videos)}
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
