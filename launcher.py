"""
Hidden launcher for Voice Sync.

Runs the Flask Socket.IO server without a console window, then starts the
PyQt client in the same no-console process. Closing the client stops the
background server that this launcher started.
"""
import ctypes
import os
import socket
import subprocess
import sys
import time


APP_NAME = "语音输入助手"
PORT = 56789
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BASE_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
RUNTIME_DIR = (
    os.path.join(os.environ.get("APPDATA", BASE_DIR), "VoiceInputAssistant")
    if getattr(sys, "frozen", False)
    else BASE_DIR
)
os.makedirs(RUNTIME_DIR, exist_ok=True)
SERVER_LOG = os.path.join(RUNTIME_DIR, "voice-sync-server.log")
FIREWALL_RULE_NAME = f"VoiceInputAssistant {PORT}"
MUTEX_NAME = "Local\\VoiceInputAssistant-56789"
ERROR_ALREADY_EXISTS = 183


def real_pythonw_executable():
    """Use the base Python GUI executable, not the venv launcher shim."""
    venv_config = os.path.join(BASE_DIR, ".venv", "pyvenv.cfg")
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

    executable = sys.executable
    dirname = os.path.dirname(executable)
    pythonw = os.path.join(dirname, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return executable


def hidden_runner_path():
    runner = os.path.join(BASE_DIR, "hidden_runner.pyw")
    return runner if os.path.exists(runner) else None


def show_error(message):
    """Show a Windows message box when there is no console to print to."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        pass


def acquire_single_instance_lock():
    """Prevent multiple desktop receivers from pasting the same message."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if not handle:
            return None
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        return handle
    except Exception:
        return None


def release_single_instance_lock(handle):
    if handle in (None, False) or os.name != "nt":
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)
    except Exception:
        pass


def pythonw_executable():
    """Prefer pythonw.exe so Python itself does not create a console window."""
    return real_pythonw_executable()


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def listening_pids(port):
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"],
            cwd=BASE_DIR,
            creationflags=CREATE_NO_WINDOW,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return set()

    pids = set()
    needle = f":{port}"
    for line in output.splitlines():
        if needle not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if parts and parts[-1].isdigit():
            pids.add(parts[-1])
    return pids


def cleanup_port(port):
    """Stop a stale server from an earlier launch."""
    current_pid = str(os.getpid())
    for pid in listening_pids(port):
        if pid == current_pid:
            continue
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            cwd=BASE_DIR,
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def run_hidden(args):
    return subprocess.run(
        args,
        cwd=BASE_DIR,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        check=False,
    )


def write_log(message):
    try:
        with open(SERVER_LOG, "a", encoding="utf-8") as log:
            log.write(message + "\n")
    except Exception:
        pass


def firewall_warning_message(detail):
    """Build a non-blocking firewall warning for the client window."""
    write_log(f"[firewall] {detail}")
    if not detail or not detail.isascii():
        detail = "需要管理员权限，或系统策略阻止添加防火墙规则"
    return (
        "防火墙放行规则没有自动配置成功。\n"
        "如果手机打不开这个地址，请在 Windows 网络访问提示里选择“允许访问”，"
        "或者右键以管理员身份运行本程序一次；不建议直接关闭防火墙。\n"
        f"需要放行：{sys.executable}\n"
        f"端口：TCP {PORT}\n"
        f"系统返回：{detail[:500]}"
    )


def ensure_firewall_rule():
    """Allow inbound LAN access for the packaged executable when possible."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return None

    executable = os.path.abspath(sys.executable)
    show_result = run_hidden([
        "netsh", "advfirewall", "firewall", "show", "rule",
        f"name={FIREWALL_RULE_NAME}",
        "verbose",
    ])
    if show_result.returncode == 0 and executable.lower() in show_result.stdout.lower():
        return None

    add_result = run_hidden([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={FIREWALL_RULE_NAME}",
        "dir=in",
        "action=allow",
        f"program={executable}",
        "enable=yes",
        "profile=private,domain",
        "protocol=TCP",
        f"localport={PORT}",
    ])
    if add_result.returncode != 0:
        return firewall_warning_message(add_result.stdout.strip() or "需要管理员权限添加防火墙规则")
    return None


def start_server():
    log = open(SERVER_LOG, "a", encoding="utf-8")
    log.write(f"\n--- launcher start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log.flush()
    command = (
        [sys.executable, "--server"]
        if getattr(sys, "frozen", False)
        else (
            [pythonw_executable(), hidden_runner_path(), os.path.join(BASE_DIR, "server.py")]
            if hidden_runner_path()
            else [pythonw_executable(), os.path.join(BASE_DIR, "server.py")]
        )
    )
    process = subprocess.Popen(
        command,
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    return process, log


def wait_for_server(process, port, timeout_seconds=25):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_port_open(port):
            return True
        time.sleep(0.15)
    return False


def stop_process(process):
    if not process or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()


def run_client():
    import client

    try:
        client.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    return 0


def main():
    if "--server" in sys.argv:
        import server
        return server.main()

    instance_lock = acquire_single_instance_lock()
    if instance_lock is False:
        show_error("语音输入助手已经在运行，请不要重复启动。")
        return 0

    server_process = None
    server_log = None
    exit_code = 0

    try:
        firewall_warning = ensure_firewall_rule()
        if firewall_warning:
            os.environ["VOICE_ASSISTANT_FIREWALL_WARNING"] = firewall_warning
        cleanup_port(PORT)
        server_process, server_log = start_server()
        if not wait_for_server(server_process, PORT):
            show_error(
                "服务端启动失败。\n\n"
                f"请确认端口 {PORT} 没有被其他程序占用，并查看日志文件：\n{SERVER_LOG}"
            )
            return 1
        exit_code = run_client()
    finally:
        stop_process(server_process)
        if server_log:
            server_log.close()
        release_single_instance_lock(instance_lock)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
