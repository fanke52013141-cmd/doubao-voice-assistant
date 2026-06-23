"""
创建桌面快捷方式
"""
import os
import subprocess
import sys

try:
    import pythoncom
    from win32com.client import Dispatch
except ImportError:
    pythoncom = None
    Dispatch = None

def base_pythonw_from_venv(script_dir):
    venv_config = os.path.join(script_dir, ".venv", "pyvenv.cfg")
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
    return ""


def fallback_pythonw(script_dir):
    candidates = [
        base_pythonw_from_venv(script_dir),
        os.path.join(script_dir, ".venv", "Scripts", "pythonw.exe"),
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        sys.executable,
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return "pythonw.exe"


def powershell_quote(value):
    return "'" + value.replace("'", "''") + "'"


def save_shortcut(shortcut_path, target, arguments, working_dir, description, icon_path):
    if pythoncom and Dispatch:
        pythoncom.CoInitialize()
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target
        shortcut.Arguments = arguments
        shortcut.WorkingDirectory = working_dir
        shortcut.Description = description
        if os.path.exists(icon_path):
            shortcut.IconLocation = f"{icon_path},0"
        shortcut.save()
        return

    command = [
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut({powershell_quote(shortcut_path)})",
        f"$shortcut.TargetPath = {powershell_quote(target)}",
        f"$shortcut.Arguments = {powershell_quote(arguments)}",
        f"$shortcut.WorkingDirectory = {powershell_quote(working_dir)}",
        f"$shortcut.Description = {powershell_quote(description)}",
    ]
    if os.path.exists(icon_path):
        command.append(f"$shortcut.IconLocation = {powershell_quote(icon_path + ',0')}")
    command.append("$shortcut.Save()")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "; ".join(command),
        ],
        check=True,
    )


def create_shortcut():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    
    shortcut_path = os.path.join(desktop, "语音输入助手.lnk")
    launcher_path = os.path.join(script_dir, "launcher.py")
    runner_path = os.path.join(script_dir, "hidden_runner.pyw")
    hidden_launcher = os.path.join(script_dir, "start_hidden.vbs")
    pythonw = fallback_pythonw(script_dir)
    if os.path.exists(runner_path):
        target = pythonw
        arguments = f'"{runner_path}" "{launcher_path}"'
    elif os.path.exists(launcher_path):
        target = pythonw
        arguments = f'"{launcher_path}"'
    elif os.path.exists(hidden_launcher):
        target = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "wscript.exe")
        if not os.path.exists(target):
            target = "wscript.exe"
        arguments = f'//B //Nologo "{hidden_launcher}"'
    else:
        target = pythonw
        arguments = f'"{launcher_path}"'
    icon_path = os.path.join(script_dir, "语音输入助手.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(script_dir, "icon.ico")
    working_dir = script_dir

    save_shortcut(
        shortcut_path,
        target,
        arguments,
        working_dir,
        "语音输入助手",
        icon_path,
    )
    print(f"Shortcut created: {shortcut_path}")

if __name__ == '__main__':
    create_shortcut()
