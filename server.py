"""
Voice Sync 服务器
实现手机端与电脑端的实时文本同步
"""
import os
import re
import sys
import time
import uuid
import hmac
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, send_file, jsonify, make_response
from flask import request
from flask_socketio import SocketIO, emit
from werkzeug.serving import WSGIRequestHandler

from ai_assistant import load_ai_settings, public_ai_button_groups
from message_store import (
    allocate_file_name,
    attachment_file,
    cleanup_messages,
    create_message,
    list_messages,
)
from network_utils import get_local_ip, get_local_ip_candidates
from transfer_config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    BLOCKED_TRANSFER_EXTENSIONS,
    MAX_TRANSFER_FILE_BYTES,
    MAX_TRANSFER_REQUEST_BYTES,
    PHONE_ACCESS_COOKIE,
    PHONE_ACCESS_COOKIE_SECONDS,
    app_data_root,
    get_phone_access_token,
)


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


PHONE_ACCESS_TOKEN = get_phone_access_token()
app = Flask(__name__, template_folder=resource_path("templates"))
app.config['SECRET_KEY'] = PHONE_ACCESS_TOKEN
app.config['MAX_CONTENT_LENGTH'] = MAX_TRANSFER_REQUEST_BYTES
UPLOAD_TTL_SECONDS = 24 * 60 * 60


def redact_access_log_text(value):
    """Keep pairing credentials out of the persistent server log."""
    return re.sub(r'([?&]token=)[^&\s"]+', r'\1[redacted]', str(value))


class RedactingRequestHandler(WSGIRequestHandler):
    def log(self, log_type, message, *args):
        super().log(
            log_type,
            message,
            *(redact_access_log_text(value) for value in args),
        )


def upload_dir():
    root = app_data_root() / 'uploads'
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
    async_mode='threading',
    max_http_buffer_size=50 * 1024 * 1024,
)


def is_loopback_request():
    return request.remote_addr in {'127.0.0.1', '::1'}


def supplied_phone_token():
    return str(request.args.get('token') or request.cookies.get(PHONE_ACCESS_COOKIE) or '')


def is_phone_authorized():
    if is_loopback_request():
        return True
    candidate = supplied_phone_token()
    return bool(candidate) and hmac.compare_digest(candidate, PHONE_ACCESS_TOKEN)


def phone_access_required(handler):
    @wraps(handler)
    def protected(*args, **kwargs):
        if not is_phone_authorized():
            response = jsonify({'ok': False, 'error': 'phone access token required'})
            response.status_code = 403
            response.headers['Cache-Control'] = 'no-store'
            return response
        return handler(*args, **kwargs)
    return protected


@app.after_request
def prevent_dynamic_page_caching(response):
    if request.endpoint in {'sender', 'ai_buttons', 'phone_messages'}:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/')
def sender():
    """手机端发送页面"""
    if not is_phone_authorized():
        return make_response(
            '访问验证失败，请在电脑端点击复制按钮，使用完整的手机访问地址。',
            403,
            {'Content-Type': 'text/plain; charset=utf-8'},
        )
    response = make_response(render_template('sender.html'))
    query_token = str(request.args.get('token') or '')
    if query_token and hmac.compare_digest(query_token, PHONE_ACCESS_TOKEN):
        response.set_cookie(
            PHONE_ACCESS_COOKIE,
            PHONE_ACCESS_TOKEN,
            max_age=PHONE_ACCESS_COOKIE_SECONDS,
            httponly=True,
            samesite='Lax',
        )
    return response


@app.route('/favicon.ico')
def favicon():
    """浏览器标签页图标"""
    icon_path = resource_path("assets/app-icon.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("语音输入助手.ico")
    if not os.path.exists(icon_path):
        icon_path = resource_path("icon.ico")
    return send_file(icon_path, mimetype="image/x-icon")


@app.route('/ai-buttons')
@phone_access_required
def ai_buttons():
    """Expose safe AI button metadata to the phone page."""
    return jsonify(public_ai_button_groups(load_ai_settings()))


@app.post('/api/uploads')
@phone_access_required
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

def clean_original_name(name):
    name = Path(str(name or 'attachment')).name.replace('\x00', '')
    name = ''.join(char for char in name if ord(char) >= 32)
    return name[:240] or 'attachment'


def validate_pc_upload(upload):
    original_name = clean_original_name(upload.filename)
    extension = Path(original_name).suffix.lower()
    mime_type = (upload.mimetype or '').lower()
    is_image = extension in ALLOWED_IMAGE_EXTENSIONS and mime_type.startswith('image/')
    is_video = extension in ALLOWED_VIDEO_EXTENSIONS and mime_type.startswith('video/')
    if extension in BLOCKED_TRANSFER_EXTENSIONS:
        raise ValueError(f'出于安全原因不能传输此类程序文件：{original_name}')
    if extension in ALLOWED_IMAGE_EXTENSIONS and not is_image:
        raise ValueError(f'图片类型无法识别：{original_name}')
    if extension in ALLOWED_VIDEO_EXTENSIONS and not is_video:
        raise ValueError(f'视频类型无法识别：{original_name}')
    return original_name, mime_type or 'application/octet-stream'


@app.post('/api/pc/messages')
def publish_pc_message():
    """Accept a local Windows message, persist it, then notify phone browsers."""
    if not is_loopback_request():
        return jsonify({'ok': False, 'error': 'PC publish endpoint is local only'}), 403

    text = str(request.form.get('text') or '')
    uploads = [upload for upload in request.files.getlist('files') if upload and upload.filename]
    if not text.strip() and not uploads:
        return jsonify({'ok': False, 'error': '消息内容不能为空'}), 400

    saved = []
    created_paths = []
    try:
        for upload in uploads:
            original_name, mime_type = validate_pc_upload(upload)
            stored_name, target = allocate_file_name(original_name)
            created_paths.append(target)
            upload.save(target)
            size = target.stat().st_size
            if size <= 0:
                raise ValueError(f'附件为空：{original_name}')
            if size > MAX_TRANSFER_FILE_BYTES:
                raise ValueError(f'单个附件不能超过 200MB：{original_name}')
            saved.append({
                'id': Path(stored_name).stem,
                'name': original_name,
                'stored_name': stored_name,
                'type': mime_type,
                'size': size,
                'path': target,
            })
    except ValueError as error:
        for path in created_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return jsonify({'ok': False, 'error': str(error)}), 415
    except Exception as error:
        for path in created_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        print(f'电脑发送到手机失败: {error}', flush=True)
        return jsonify({'ok': False, 'error': '保存消息失败'}), 500

    try:
        message = create_message(text, saved)
    except Exception as error:
        for path in created_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        print(f'电脑发送到手机失败: {error}', flush=True)
        return jsonify({'ok': False, 'error': '保存消息失败'}), 500

    # The database now owns these files. Notification or retention failures must
    # not turn a committed message into a record whose attachment returns 404.
    try:
        socketio.emit('pc_message', message)
    except Exception as error:
        print(f'电脑消息实时通知失败，将等待手机同步: {error}', flush=True)
    try:
        cleanup_messages()
    except Exception as error:
        print(f'电脑消息清理失败: {error}', flush=True)
    return jsonify({'ok': True, 'message': message})


@app.get('/api/messages')
@phone_access_required
def phone_messages():
    """Return persisted PC messages so a phone can catch up after reconnecting."""
    try:
        after_id = int(request.args.get('after', 0))
        limit = int(request.args.get('limit', 100))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid pagination'}), 400
    return jsonify({'ok': True, 'messages': list_messages(after_id, limit)})


@app.get('/api/files/<attachment_id>')
@phone_access_required
def shared_attachment(attachment_id):
    """Preview or download an attachment by opaque id, never by filesystem path."""
    if not attachment_id or not all(char in '0123456789abcdef' for char in attachment_id.lower()):
        return jsonify({'ok': False, 'error': 'file not found'}), 404
    attachment = attachment_file(attachment_id)
    if not attachment:
        return jsonify({'ok': False, 'error': 'file not found'}), 404
    is_previewable = attachment['type'].startswith(('image/', 'video/'))
    response = send_file(
        attachment['path'],
        mimetype=attachment['type'],
        as_attachment=request.args.get('download') == '1' or not is_previewable,
        download_name=attachment['name'],
        conditional=True,
    )
    response.headers['Cache-Control'] = 'private, max-age=3600'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    if not is_phone_authorized():
        return False
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
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
            request_handler=RedactingRequestHandler,
        )
    except OSError as e:
        if "Address already in use" in str(e) or "[WinError 10048]" in str(e):
            print(f"\nError: Port {port} is already in use!")
            print(f"   请检查是否有其他程序占用了 {port} 端口。")
            print("   为避免误关其他程序，本应用不会自动结束占用该端口的进程。")
            return 1
        else:
            print(f"\nError: {e}")
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
