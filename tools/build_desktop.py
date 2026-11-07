"""Build a standalone desktop app with PyInstaller.

    pip install pyinstaller
    python tools/build_desktop.py

Result: dist/Foscount/ (Windows: Foscount.exe, macOS: Foscount.app).
Build on the operating system you want to ship to.
"""
import os
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sep = ";" if sys.platform.startswith("win") else ":"
args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
        "--name", "Foscount", os.path.join(root, "foscount", "__main__.py")]
fonts = os.path.join(root, "foscount", "assets", "fonts")
if os.path.isdir(fonts):
    args += ["--add-data", f"{fonts}{sep}foscount/assets/fonts"]
subprocess.check_call(args, cwd=root)
