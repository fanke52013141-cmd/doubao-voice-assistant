"""Run a project script with venv packages while using the real pythonw.exe."""
import os
import runpy
import site
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, ".venv")
SITE_PACKAGES = os.path.join(
    VENV_DIR,
    "Lib",
    "site-packages",
)
SCRIPTS_DIR = os.path.join(VENV_DIR, "Scripts")


if os.path.isdir(SITE_PACKAGES):
    site.addsitedir(SITE_PACKAGES)
if os.path.isdir(SCRIPTS_DIR):
    os.environ["PATH"] = SCRIPTS_DIR + os.pathsep + os.environ.get("PATH", "")
if os.path.isdir(VENV_DIR):
    os.environ["VIRTUAL_ENV"] = VENV_DIR

os.chdir(BASE_DIR)

if len(sys.argv) < 2:
    raise SystemExit("Missing script path")

script_path = os.path.abspath(sys.argv[1])
sys.argv = [script_path] + sys.argv[2:]
runpy.run_path(script_path, run_name="__main__")
