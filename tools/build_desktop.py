"""Build a standalone desktop app with PyInstaller.

    pip install pyinstaller pillow
    python tools/build_desktop.py            # single file: dist/Foscount.exe
    python tools/build_desktop.py --folder   # folder build: dist/Foscount/ (used by the installer)

Build on the operating system you want to ship to (Windows for .exe).
"""
import os
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sep = ";" if sys.platform.startswith("win") else ":"
png = os.path.join(root, "build", "foscount.png")
subprocess.check_call([sys.executable, os.path.join(root, "tools", "make_icon.py"), png])
ico = os.path.splitext(png)[0] + ".ico"
icon = ico if os.path.exists(ico) else png

args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "Foscount", "--icon", icon,
        # Qt modules the app does not use (keeps the exe smaller)
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "tkinter"]
if "--folder" not in sys.argv:
    args.append("--onefile")
fonts = os.path.join(root, "foscount", "assets", "fonts")
if os.path.isdir(fonts):
    args += ["--add-data", f"{fonts}{sep}foscount/assets/fonts"]
args.append(os.path.join(root, "foscount", "__main__.py"))
subprocess.check_call(args, cwd=root)
