"""Build the "Read this first" install guide: docs/Foscount-Read-First.pdf

    python tools/make_install_pdf.py

Uses Qt's HTML-to-PDF support, so no extra dependencies are needed.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QMarginsF, QSizeF  # noqa: E402
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from foscount import __version__  # noqa: E402
from foscount.gui import theme  # noqa: E402

REPO = "https://github.com/Baboe/burkercell"

HTML = f"""
<html><head><style>
  body {{ font-family: {theme.BODY_CSS}; font-size: 10.5pt; color: {theme.TEXT}; }}
  h1 {{ font-family: {theme.HEADING_CSS}; font-size: 26pt; color: {theme.INK}; margin: 0; }}
  h2 {{ font-family: {theme.HEADING_CSS}; font-size: 14pt; color: {theme.PRIMARY};
        margin-top: 16px; margin-bottom: 4px; }}
  .brand {{ font-family: {theme.HEADING_CSS}; font-size: 13pt; font-weight: bold; }}
  .eyebrow {{ color: {theme.PRIMARY}; font-size: 8.5pt; font-weight: bold; letter-spacing: 2px; }}
  .lead {{ font-size: 11.5pt; color: {theme.TEXT}; }}
  .note {{ background: {theme.LAVENDER_SOFT}; }}
  .warn {{ color: {theme.WARN}; font-weight: bold; }}
  td {{ vertical-align: top; padding: 4px 8px; }}
  .step {{ color: {theme.PRIMARY}; font-weight: bold; font-size: 13pt; }}
  a {{ color: {theme.PRIMARY}; }}
  small {{ color: {theme.TEXT_SOFT}; }}
</style></head><body>

<p class="brand"><span style="color:{theme.PRIMARY}">Fos</span><span style="color:{theme.MUTED}">count</span>
&nbsp;<small>version {__version__}</small></p>
<p class="eyebrow">READ THIS FIRST</p>
<h1>Install and first count</h1>
<p class="lead">Foscount counts cells automatically in microscope photos of a B&uuml;rker
counting chamber, for unstained samples and for trypan blue live/dead counts.
This page gets you from download to your first result in about five minutes.</p>

<h2>1. Install (Windows 10 / 11, 64-bit)</h2>
<table width="100%">
<tr><td class="step" width="28">1</td><td>Open the download page:
<b><a href="{REPO}/releases/latest">{REPO}/releases/latest</a></b></td></tr>
<tr><td class="step">2</td><td>Under <b>Assets</b>, download
<b>Foscount-Setup-x.y.z.exe</b> (the installer). No administrator rights are needed.</td></tr>
<tr><td class="step">3</td><td>Double-click the file. Windows will probably show a blue
<b>&ldquo;Windows protected your PC&rdquo;</b> window, because the app is not code-signed yet.
This is expected: click <b>More info</b>, then <b>Run anyway</b>.</td></tr>
<tr><td class="step">4</td><td>Follow the installer. Tick &ldquo;Create a desktop shortcut&rdquo; if
you want one, then start <b>Foscount</b>.</td></tr>
</table>
<p><b>No installation possible?</b> Download <b>Foscount-portable-x.y.z.exe</b>
instead. It is a single file that runs from any folder (for example a USB stick) but starts
more slowly. To remove the installed version: Windows Settings &rarr; Apps &rarr; Foscount &rarr; Uninstall.</p>

<h2>2. Your first count</h2>
<table width="100%">
<tr><td class="step" width="28">1</td><td><b>Open images</b> (top right) or drag photos onto the window.
Foscount finds the counting grid and selects the complete squares.</td></tr>
<tr><td class="step">2</td><td>In the right-hand panel, choose the <b>Mode</b>
(unstained, or trypan blue live/dead) and type the <b>Dilution factor</b>
(1 = undiluted, 2 = mixed 1:1 with trypan blue).</td></tr>
<tr><td class="step">3</td><td><b>Check the square size</b> (see the box below).</td></tr>
<tr><td class="step">4</td><td>Look at the image. Add, remove or re-classify cells by clicking
(<i>Edit cells</i> tool). Include or exclude squares with <i>Select squares</i>.</td></tr>
<tr><td class="step">5</td><td>Read the concentration (cells/mL) and, in trypan mode, the viability at the top
of the right-hand panel. Export with <b>Export results</b> (Excel or CSV).</td></tr>
</table>

<table width="100%" cellpadding="8" class="note"><tr><td class="note">
<span class="warn">Important: set the square size.</span><br>
Foscount can see the squares but cannot know how big they really are. Under
<b>Chamber &rarr; Counting square side</b>, enter the side of the squares in your photo:
<b>0.2 mm</b> for the large B&uuml;rker squares (the default), <b>0.05 mm</b> for the small
squares. If a photo shows a uniform grid without the narrow double-line strips, the app
warns you. A wrong value gives a wrong concentration (0.05 mm instead of 0.2 mm is a factor of 16).
</td></tr></table>

<h2>3. No camera on your microscope?</h2>
<p>Use the <b>Manual entry</b> tab. Type your counts per square, or use the keyboard tally counter:
<b>L</b> = live/cell, <b>D</b> = dead, <b>N</b> = next square, <b>Backspace</b> = undo.
The same calculations and export are used.</p>

<h2>4. Many photos at once</h2>
<p><b>File &rarr; Batch process folder</b> counts every photo in a folder and writes an Excel/CSV
file plus annotated images. Each subfolder is treated as one sample.</p>

<h2>5. Good to know</h2>
<ul>
<li><b>Always check the result by eye.</b> Clumps, debris and out-of-focus cells can be
miscounted. Correct them by clicking.</li>
<li>Count enough cells: at least 100&ndash;200 in total for about 10&ndash;20&nbsp;% precision.
The app shows the counting error and warns when counts are low.</li>
<li>Sharp focus on the grid lines and an evenly lit field give the best results.</li>
<li>Photos taken through the eyepiece (round view, black corners) work: the black surround is ignored.</li>
<li>Foscount is a research tool and has not been validated for clinical or diagnostic use.</li>
</ul>

<h2>Help and updates</h2>
<p>New versions, source code and bug reports:
<a href="{REPO}">{REPO}</a>.<br>
When you report a problem, please attach the photo and say which mode and square size you used.</p>

</body></html>
"""


def main(out: str) -> None:
    app = QApplication([])
    theme.load_fonts()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    w = QPdfWriter(out)
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(18, 16, 18, 16), QPageLayout.Unit.Millimeter)
    w.setResolution(96)  # same as the screen, so point sizes come out right (text stays vector)
    w.setTitle("Foscount: Read this first")
    w.setCreator("Foscount")
    doc = QTextDocument()
    doc.setHtml(HTML)
    # lay the document out in the writer's resolution so the text is sharp
    res = w.resolution()
    page = w.pageLayout().paintRectPixels(res)
    doc.setPageSize(QSizeF(page.width(), page.height()))
    doc.print_(w)
    print("wrote", out)
    del app


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "Foscount-Read-First.pdf"))
