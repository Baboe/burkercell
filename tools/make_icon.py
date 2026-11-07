"""Render the Foscount app icon to PNG (and .ico when Pillow is installed).

    python tools/make_icon.py build/foscount.png
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

from foscount.gui.theme import app_icon  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "foscount.png"
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
app = QApplication([])
app_icon().pixmap(256, 256).save(out)
print("wrote", out)
try:  # Windows .ico for the exe and the installer (needs Pillow)
    from PIL import Image
    ico = os.path.splitext(out)[0] + ".ico"
    Image.open(out).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", ico)
except ImportError:
    pass
