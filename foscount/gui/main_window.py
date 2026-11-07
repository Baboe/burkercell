"""Main application window."""

from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget,
                               QMainWindow, QMessageBox, QProgressDialog, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..core.analysis import ImageAnalysis, write_image
from ..core.concentration import format_conc, summarize
from ..core.detection import DetectParams, score_single_cell
from ..core.export import make_row, write_rows
from ..core.grid import empty_grid, to_grid_frame
from ..core.models import Cell, CellState, Chamber, CountResult, Mode, Square
from . import theme
from .batch_dialog import BatchDialog
from .image_view import ImageView, Tool
from .manual_entry import ManualEntry
from .summary_text import summary_html

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All files (*)"

HELP = """
<h3>Foscount — Bürker chamber cell counter</h3>
<ol>
<li><b>Open images</b> (File ▸ Open, or drag &amp; drop). Each image is analysed
automatically: the counting grid is detected and all <i>complete</i> large squares
(0.2 × 0.2 mm) are selected.</li>
<li>Choose the <b>mode</b>: <i>Unstained</i> counts all cells; <i>Trypan blue</i>
classifies cells as live (clear) or dead (blue). Adjust the <b>dead threshold</b>
until the classification matches what you see.</li>
<li>Enter the <b>dilution factor</b> (e.g. 2 when mixing 1:1 with trypan blue).</li>
<li>Check the result. Correct it with the tools above the image:
 <ul>
 <li><b>Edit cells</b>: left-click empty space = add a cell (Shift+click = add a
 dead cell), left-click a cell = toggle live/dead (trypan mode),
 right-click a cell = remove it.</li>
 <li><b>Select squares</b>: click a square to include/exclude it.</li>
 <li><b>Draw square</b>: drag a rectangle around one large square if the grid
 was not found.</li>
 </ul></li>
<li>All images of the list are pooled into one <b>sample</b> result.</li>
<li>Export with File ▸ Export results (CSV/Excel) or Export annotated images.</li>
</ol>
<p><b>Counting rule</b>: cells touching the top or left line of a square are
counted, cells touching the bottom or right line are not. Bold circles are
counted, faded circles are outside the selected squares.</p>
<p><b>Concentration</b> = mean cells per large square × dilution ÷ volume of a
square (0.2 mm × 0.2 mm × 0.1 mm = 0.004 µL), i.e. mean × dilution × 250 000
cells/mL for a standard Bürker chamber.</p>
<p>Use <b>Manual entry</b> when you count by eye at the microscope; it has a
keyboard tally counter (L, D, N, Backspace).</p>
<p>Navigation: mouse wheel = zoom, middle button or Alt+drag = pan, F = fit.</p>
"""


def _sup(s: str) -> str:
    if "^" in s:
        m, e = s.split("^")
        return f"{m}<sup>{e}</sup>"
    return s


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Foscount {__version__}")
        self.resize(1400, 860)
        self.setAcceptDrops(True)
        self.analyses: list[ImageAnalysis] = []
        self.settings = QSettings("Foscount", "Foscount")
        self._redetect = QTimer(self, singleShot=True, interval=500)
        self._redetect.timeout.connect(self._auto_redetect)

        self._build_ui()
        self._build_menu()
        self._load_settings()
        self._refresh()

    # ================================================================== UI
    def _build_ui(self):
        # ---- left: image list
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list.setWordWrap(True)
        self.list.currentRowChanged.connect(self._show_current)
        b_add = QPushButton("Add images…")
        b_add.setProperty("variant", "primary")
        b_add.clicked.connect(self.open_images)
        b_rem = QPushButton("Remove")
        b_rem.clicked.connect(self._remove_current)
        left = QWidget()
        left.setObjectName("sidePanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 10, 14)
        cap = QLabel("Images in this sample")
        cap.setObjectName("eyebrow")
        cap.setFont(theme.eyebrow_font())
        ll.addWidget(cap)
        ll.addWidget(self.list, 1)
        hb = QHBoxLayout()
        hb.addWidget(b_add)
        hb.addWidget(b_rem)
        ll.addLayout(hb)

        # ---- centre: image tab + manual tab
        self.view = ImageView()
        self.view.clicked.connect(self._on_click)
        self.view.rect_drawn.connect(self._on_rect)
        tools = QHBoxLayout()
        tools.setContentsMargins(12, 10, 12, 6)
        seg = QFrame()
        seg.setObjectName("segment")
        segl = QHBoxLayout(seg)
        segl.setContentsMargins(2, 2, 2, 2)
        segl.setSpacing(2)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for i, (label, tool, tip) in enumerate([
                ("Edit cells", Tool.CELLS, "Left-click: add cell / toggle live-dead. "
                 "Shift+click: add dead cell. Right-click: remove cell."),
                ("Select squares", Tool.SQUARES, "Click a square to include or exclude it."),
                ("Draw square", Tool.DRAW, "Drag a rectangle around one large square (0.2 × 0.2 mm).")]):
            rb = QPushButton(label)
            rb.setCheckable(True)
            rb.setToolTip(tip)
            rb.setProperty("tool", tool)
            self.tool_group.addButton(rb, i)
            segl.addWidget(rb)
            if i == 0:
                rb.setChecked(True)
        tools.addWidget(seg)
        self.tool_group.buttonClicked.connect(lambda b: setattr(self.view, "tool", b.property("tool")))
        tools.addStretch(1)
        b_fit = QPushButton("Fit to window  F")
        b_fit.setProperty("variant", "ghost")
        b_fit.clicked.connect(self.view.fit)
        tools.addWidget(b_fit)
        img_tab = QWidget()
        il = QVBoxLayout(img_tab)
        il.setContentsMargins(0, 0, 0, 0)
        il.addLayout(tools)
        il.addWidget(self.view, 1)
        self.manual = ManualEntry(lambda: self.mode.currentData() if hasattr(self, "mode") else Mode.UNSTAINED,
                                  lambda: self.dilution.value() if hasattr(self, "dilution") else 1.0,
                                  self.chamber)
        b_mexp = QPushButton("Export manual count…")
        b_mexp.setProperty("variant", "primary")
        b_mexp.clicked.connect(self.export_manual)
        man_tab = QWidget()
        ml = QVBoxLayout(man_tab)
        ml.addWidget(self.manual, 1)
        ml.addWidget(b_mexp)
        self.tabs = QTabWidget()
        self.tabs.addTab(img_tab, "Image analysis")
        self.tabs.addTab(man_tab, "Manual entry (no camera)")

        # ---- right: settings + results
        self.sample = QLineEdit()
        self.sample.setPlaceholderText("e.g. culture A, day 3")
        self.mode = QComboBox()
        self.mode.addItem("Unstained (count all cells)", Mode.UNSTAINED)
        self.mode.addItem("Trypan blue (live / dead)", Mode.TRYPAN)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.dilution = QDoubleSpinBox()
        self.dilution.setRange(0.001, 1e6)
        self.dilution.setDecimals(3)
        self.dilution.setValue(1.0)
        self.dilution.setToolTip("Total dilution factor (1 = undiluted, 2 = 1:1 with trypan blue)")
        sg, sgl = theme.card("Sample")
        sf = QFormLayout()
        sgl.addLayout(sf)
        sf.addRow("Name:", self.sample)
        sf.addRow("Mode:", self.mode)
        sf.addRow("Dilution factor:", self.dilution)

        self.diam_um = QDoubleSpinBox()
        self.diam_um.setRange(1, 200)
        self.diam_um.setValue(12)
        self.diam_um.setSuffix(" µm")
        self.diam_um.setToolTip("Typical cell diameter (used when the grid gives a scale)")
        self.diam_px = QDoubleSpinBox()
        self.diam_px.setRange(3, 500)
        self.diam_px.setValue(20)
        self.diam_px.setSuffix(" px")
        self.diam_px.setToolTip("Cell diameter in pixels, used only when no grid scale is available")
        self.sens = QSlider(Qt.Orientation.Horizontal)
        self.sens.setRange(0, 100)
        self.sens.setValue(50)
        self.sens_lbl = QLabel("50")
        self.split = QCheckBox("Split touching cells")
        self.split.setChecked(True)
        self.dead_thr = QSlider(Qt.Orientation.Horizontal)
        self.dead_thr.setRange(-20, 120)
        self.dead_thr.setValue(20)
        self.dead_lbl = QLabel("20")
        self.dead_thr.setToolTip("Stain score above which a cell is counted as dead. "
                                 "Lower = more cells counted as dead.")
        self.show_unc = QCheckBox("Show cells outside counted squares")
        self.show_unc.setChecked(True)
        self.show_unc.toggled.connect(self._show_unc)
        for w in (self.diam_um, self.diam_px):
            w.valueChanged.connect(self._params_changed)
        self.sens.valueChanged.connect(lambda v: (self.sens_lbl.setText(str(v)), self._params_changed()))
        self.split.toggled.connect(self._params_changed)
        self.dead_thr.valueChanged.connect(self._dead_changed)
        dg, dgl = theme.card("Detection")
        df = QFormLayout()
        dgl.addLayout(df)
        df.addRow("Cell diameter:", self.diam_um)
        df.addRow("…without scale:", self.diam_px)
        sl = QHBoxLayout()
        sl.addWidget(self.sens, 1)
        sl.addWidget(self.sens_lbl)
        df.addRow("Sensitivity:", sl)
        df.addRow("", self.split)
        dl = QHBoxLayout()
        dl.addWidget(self.dead_thr, 1)
        dl.addWidget(self.dead_lbl)
        self.dead_row_lbl = QLabel("Dead threshold:")
        df.addRow(self.dead_row_lbl, dl)
        df.addRow("", self.show_unc)

        self.sq_side = QDoubleSpinBox()
        self.sq_side.setRange(0.01, 5)
        self.sq_side.setDecimals(3)
        self.sq_side.setValue(0.2)
        self.sq_side.setSuffix(" mm")
        self.chamber_depth = QDoubleSpinBox()
        self.chamber_depth.setRange(0.01, 1)
        self.chamber_depth.setDecimals(3)
        self.chamber_depth.setValue(0.1)
        self.chamber_depth.setSuffix(" mm")
        for w in (self.sq_side, self.chamber_depth, self.dilution):
            w.valueChanged.connect(self._refresh)
            w.valueChanged.connect(self.manual.settings_changed)
        cg, cgl = theme.card("Chamber")
        cf = QFormLayout()
        cgl.addLayout(cf)
        ch_hint = QLabel("Side of the squares the grid detector finds. Bürker: 0.2 mm "
                         "large squares (0.05 mm for small squares), 0.1 mm deep.")
        ch_hint.setWordWrap(True)
        ch_hint.setObjectName("hint")
        cf.addRow("Counting square side:", self.sq_side)
        cf.addRow("Depth:", self.chamber_depth)
        cgl.addWidget(ch_hint)

        b_an = QPushButton("Re-analyse image")
        b_an.setProperty("variant", "primary")
        b_an.clicked.connect(self.analyse_current)
        b_cells = QPushButton("Re-detect cells only")
        b_cells.clicked.connect(self.redetect_current)
        b_all = QPushButton("Re-analyse all images")
        b_all.clicked.connect(self.analyse_all)
        b_sel = QPushButton("Select all squares")
        b_sel.clicked.connect(lambda: self._select_all(True))
        b_clr = QPushButton("Remove all squares")
        b_clr.clicked.connect(self._clear_squares)
        ag, al = theme.card("Actions")
        for b in (b_an, b_cells, b_all):
            al.addWidget(b)
        h2 = QHBoxLayout()
        h2.addWidget(b_sel)
        h2.addWidget(b_clr)
        al.addLayout(h2)

        self.res_img = QLabel()
        self.res_sample = QLabel()
        for lab in (self.res_img, self.res_sample):
            lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            # let the label wrap to the panel width instead of widening it
            lab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            lab.setMinimumWidth(10)
        rg, rl = theme.card("Results")
        self.res_big = QLabel("–")
        self.res_big.setFont(theme.heading_font(28))
        self.res_big.setTextFormat(Qt.TextFormat.RichText)
        self.res_big.setObjectName("headline")
        self.res_big_sub = QLabel("cells/mL · this image")
        self.res_big_sub.setObjectName("hint")
        rl.addWidget(self.res_big)
        rl.addWidget(self.res_big_sub)
        rl.addWidget(self.res_img)
        rl.addWidget(self.res_sample)

        right = QWidget()
        right.setObjectName("sideInner")
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(12, 14, 14, 14)
        # never squeeze the cards; let the scroll area scroll instead
        rlay.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        rlay.setSpacing(12)
        for g in (rg, sg, dg, ag, cg):
            rlay.addWidget(g)
        rlay.addStretch(1)
        scroll = QScrollArea()
        self.side_scroll = scroll
        scroll.setObjectName("sideScroll")
        scroll.setWidget(right)
        scroll.setWidgetResizable(True)
        # wide enough for the content plus the vertical scrollbar
        scroll.setMinimumWidth(max(380, right.minimumSizeHint().width() + 16))
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.tabs)
        split.addWidget(scroll)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 780, 380])
        split.setHandleWidth(1)

        b_open = QPushButton("Open images")
        b_open.setProperty("variant", "primary")
        b_open.clicked.connect(self.open_images)
        b_batch = QPushButton("Batch folder")
        b_batch.clicked.connect(self.batch)
        b_exp = QPushButton("Export results")
        b_exp.clicked.connect(self.export_results)
        central = QWidget()
        central.setObjectName("central")
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(theme.Header([b_batch, b_exp, b_open]))
        cl.addWidget(split, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Open microscope images of a Bürker chamber to start.")

    def _build_menu(self):
        m = self.menuBar().addMenu("&File")

        def act(menu, text, fn, key=None):
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
            a.triggered.connect(fn)
            menu.addAction(a)
            return a
        act(m, "&Open images…", self.open_images, QKeySequence.StandardKey.Open)
        act(m, "&Batch process folder…", self.batch, "Ctrl+B")
        m.addSeparator()
        act(m, "&Export results (CSV / Excel)…", self.export_results, "Ctrl+E")
        act(m, "Export &annotated images…", self.export_annotated, "Ctrl+Shift+E")
        m.addSeparator()
        act(m, "&Quit", self.close, QKeySequence.StandardKey.Quit)
        v = self.menuBar().addMenu("&View")
        act(v, "&Fit image", self.view.fit, "F")
        h = self.menuBar().addMenu("&Help")
        act(h, "&How to use", self._help, "F1")
        act(h, "&About", lambda: QMessageBox.about(
            self, "About", f"Foscount {__version__}\n\n"
            "Automatic cell counting in Bürker chamber micrographs.\n"
            "Always check the automatic result visually."))

    # ============================================================ settings
    def chamber(self) -> Chamber:
        if not hasattr(self, "chamber_depth"):  # called while the UI is being built
            return Chamber()
        return Chamber(square_side_mm=self.sq_side.value(), depth_mm=self.chamber_depth.value(),
                       strip_mm=self.sq_side.value() / 4)

    def params(self) -> DetectParams:
        return DetectParams(mode=self.mode.currentData(), cell_diameter_um=self.diam_um.value(),
                            cell_diameter_px=self.diam_px.value(), sensitivity=self.sens.value(),
                            split_touching=self.split.isChecked(),
                            dead_threshold=float(self.dead_thr.value()))

    def _load_settings(self):
        s = self.settings
        try:
            self.mode.setCurrentIndex(int(s.value("mode", 0)))
            self.dilution.setValue(float(s.value("dilution", 1.0)))
            self.diam_um.setValue(float(s.value("diam_um", 12)))
            self.diam_px.setValue(float(s.value("diam_px", 20)))
            self.sens.setValue(int(s.value("sens", 50)))
            self.dead_thr.setValue(int(s.value("dead_thr", 20)))
            self.split.setChecked(str(s.value("split", "true")).lower() == "true")
            self.sq_side.setValue(float(s.value("sq_side", 0.2)))
            self.chamber_depth.setValue(float(s.value("depth", 0.1)))
        except (TypeError, ValueError):
            pass
        self._mode_changed()

    def closeEvent(self, ev):
        s = self.settings
        s.setValue("mode", self.mode.currentIndex())
        s.setValue("dilution", self.dilution.value())
        s.setValue("diam_um", self.diam_um.value())
        s.setValue("diam_px", self.diam_px.value())
        s.setValue("sens", self.sens.value())
        s.setValue("dead_thr", self.dead_thr.value())
        s.setValue("split", self.split.isChecked())
        s.setValue("sq_side", self.sq_side.value())
        s.setValue("depth", self.chamber_depth.value())
        super().closeEvent(ev)

    # =============================================================== state
    @property
    def cur(self) -> ImageAnalysis | None:
        i = self.list.currentRow()
        return self.analyses[i] if 0 <= i < len(self.analyses) else None

    def _refresh(self):
        mode = self.mode.currentData()
        a = self.cur
        if a is not None:
            counts, assign = a.counts()
            self.view.set_overlay(a.grid, a.cells, assign, counts, mode)
            s = a.summary(mode, self.dilution.value(), self.chamber())
            title = f"This image ({a.name})"
            extra = ""
            if not a.grid_found and not (a.grid and a.grid.squares):
                extra = ("<br><span style='color:#c00'>Counting grid not found. Use "
                         "<b>Draw square</b> to mark the large squares by hand.</span>")
            elif a.grid_found and a.grid.px_per_mm:
                extra = f"<br><span style='color:gray'>Scale: {a.grid.px_per_mm:.0f} px/mm, grid angle {a.grid.angle_deg:.1f}°</span>"
                if not a.grid.strips_found:
                    extra += ("<br><span style='color:#B45309'>⚠ Uniform grid without double-line "
                              "strips: check that <b>Counting square side</b> matches the squares "
                              f"in this photo (now {self.sq_side.value():g} mm; Bürker large squares "
                              "are 0.2 mm, small squares 0.05 mm).</span>")
            self.res_img.setText(summary_html(title, s, mode) + extra)
            big = s.live_per_ml if mode == Mode.TRYPAN and s.live_per_ml is not None else s.concentration_per_ml
            self.res_big.setText(_sup(format_conc(big)) if s.n_squares else "–")
            self.res_big_sub.setText(("live cells/mL" if mode == Mode.TRYPAN else "cells/mL")
                                     + (f" · {s.viability_percent:.0f} % viable" if mode == Mode.TRYPAN and s.viability_percent is not None else "")
                                     + " · this image")
        else:
            self.view.set_overlay(None, [], [], [], mode)
            self.res_big.setText("–")
            self.res_img.setText("<span style='color:#6B7280'>Open microscope photos of a Bürker chamber to start.</span>")
        if len(self.analyses) > 1:
            self.res_sample.setText("<hr>" + summary_html(
                f"Sample (all {len(self.analyses)} images pooled)", self.sample_summary(), mode))
        else:
            self.res_sample.setText("")
        self._fit_labels()
        for i, an in enumerate(self.analyses):
            c, _ = an.counts()
            it = self.list.item(i)
            if it is not None:
                tot = sum(x.total for x in c)
                it.setText(f"{an.name}  —  {len(c)} sq, {tot} cells" if an.grid and an.grid.squares
                           else f"{an.name}  —  no grid")

    def _fit_labels(self):
        """Wrapped rich-text labels do not report their height reliably to the
        layout; size them for the current panel width."""
        w = self.side_scroll.viewport().width() - 64
        if w < 100:
            w = self.side_scroll.minimumWidth() - 64
        for lab in (self.res_img, self.res_sample):
            lab.setFixedHeight(lab.heightForWidth(w) if lab.text() else 0)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "res_img"):
            self._fit_labels()

    def sample_counts(self):
        out = []
        for a in self.analyses:
            out.extend(a.counts()[0])
        return out

    def sample_summary(self):
        return summarize(CountResult(self.mode.currentData(), self.sample_counts(),
                                     self.dilution.value(), self.chamber()))

    # =========================================================== loading
    def open_images(self):
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        files, _ = QFileDialog.getOpenFileNames(self, "Open microscope images", str(start), IMAGE_FILTER)
        if files:
            self.settings.setValue("last_dir", os.path.dirname(files[0]))
            self.add_images(files)

    def add_images(self, files: list[str]):
        prog = QProgressDialog("Analysing images…", "Cancel", 0, len(files), self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(300)
        first_new = len(self.analyses)
        errors = []
        for i, f in enumerate(files):
            prog.setValue(i)
            prog.setLabelText(f"Analysing {os.path.basename(f)}…")
            QApplication.processEvents()
            if prog.wasCanceled():
                break
            try:
                a = ImageAnalysis.load(f)
                a.run(self.params(), self.chamber())
            except Exception as e:
                errors.append(f"{os.path.basename(f)}: {e}")
                continue
            self.analyses.append(a)
            self.list.addItem(a.name)
        prog.setValue(len(files))
        if errors:
            QMessageBox.warning(self, "Open images", "Some images could not be read:\n" + "\n".join(errors))
        if len(self.analyses) > first_new:
            self.list.setCurrentRow(first_new)
        self._refresh()

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        files = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        files = [f for f in files if os.path.splitext(f)[1].lower()
                 in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}]
        if files:
            self.add_images(files)

    def _remove_current(self):
        i = self.list.currentRow()
        if i < 0:
            return
        self.analyses.pop(i)
        self.list.takeItem(i)
        if not self.analyses:
            self.view.set_image(None)
        self._refresh()

    def _show_current(self, _row: int):
        a = self.cur
        self.view.set_image(a.image if a else None)
        self._refresh()

    # ========================================================= analysis
    def analyse_current(self):
        a = self.cur
        if a is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            a.run(self.params(), self.chamber())
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(
            "Grid found." if a.grid_found else
            "Counting grid NOT found - draw the squares by hand (Draw square tool).", 8000)
        self._refresh()

    def redetect_current(self):
        a = self.cur
        if a is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            a.detect_cells(self.params())
        finally:
            QApplication.restoreOverrideCursor()
        self._refresh()

    def analyse_all(self):
        if not self.analyses:
            return
        if any(any(c.manual for c in a.cells) for a in self.analyses):
            if QMessageBox.question(self, "Re-analyse", "Manual corrections will be lost. Continue?") \
                    != QMessageBox.StandardButton.Yes:
                return
        prog = QProgressDialog("Analysing…", "Cancel", 0, len(self.analyses), self)
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        for i, a in enumerate(self.analyses):
            prog.setValue(i)
            QApplication.processEvents()
            if prog.wasCanceled():
                break
            a.run(self.params(), self.chamber())
        prog.setValue(len(self.analyses))
        self._refresh()

    def _params_changed(self, *_):
        a = self.cur
        if a is None:
            return
        if any(c.manual for c in a.cells):
            self.statusBar().showMessage(
                "Detection settings changed. Click 'Re-detect cells only' to apply "
                "(your manual corrections on this image will be lost).", 10000)
        else:
            self._redetect.start()

    def _auto_redetect(self):
        a = self.cur
        if a is not None and not any(c.manual for c in a.cells):
            self.redetect_current()
            self.statusBar().showMessage(
                "Cells re-detected on this image. Use 'Re-analyse all images' to apply to all.", 6000)

    def _mode_changed(self, *_):
        trypan = self.mode.currentData() == Mode.TRYPAN
        self.dead_thr.setEnabled(trypan)
        self.dead_row_lbl.setEnabled(trypan)
        for a in self.analyses:
            a.set_mode(self.mode.currentData(), float(self.dead_thr.value()))
        self.manual.settings_changed()
        self._refresh()

    def _dead_changed(self, v: int):
        self.dead_lbl.setText(str(v))
        if self.mode.currentData() == Mode.TRYPAN:
            for a in self.analyses:
                a.set_mode(Mode.TRYPAN, float(v))
            self._refresh()

    def _show_unc(self, on: bool):
        self.view.show_uncounted = on
        self._refresh()

    # ============================================================ editing
    def _cell_at(self, a: ImageAnalysis, x: float, y: float) -> int:
        best, bd = -1, 1e18
        for i, c in enumerate(a.cells):
            d = (c.x - x) ** 2 + (c.y - y) ** 2
            if d <= max(c.radius, 4) ** 2 and d < bd:
                best, bd = i, d
        return best

    def _on_click(self, x, y, button, mods):
        a = self.cur
        if a is None:
            return
        if self.view.tool == Tool.CELLS:
            i = self._cell_at(a, x, y)
            trypan = self.mode.currentData() == Mode.TRYPAN
            if button == Qt.MouseButton.RightButton:
                if i >= 0:
                    a.cells.pop(i)
            elif button == Qt.MouseButton.LeftButton:
                if i >= 0:
                    if trypan:
                        c = a.cells[i]
                        c.state = CellState.LIVE if c.state == CellState.DEAD else CellState.DEAD
                        c.manual = True
                else:
                    d = self.params().diameter_px(a.grid if a.grid_found else None)
                    dead = bool(mods & Qt.KeyboardModifier.ShiftModifier)
                    c = Cell(x, y, d / 2, manual=True)
                    score_single_cell(a.image, c, d)
                    if trypan:
                        c.state = CellState.DEAD if dead else CellState.LIVE
                    a.cells.append(c)
        elif self.view.tool == Tool.SQUARES and a.grid is not None:
            gx, gy = to_grid_frame(a.grid, np.array([[x, y]]))[0]
            for sq in a.grid.squares:
                if sq.x0 <= gx <= sq.x1 and sq.y0 <= gy <= sq.y1:
                    sq.selected = not sq.selected
                    break
        self._refresh()

    def _on_rect(self, x0, y0, x1, y1):
        a = self.cur
        if a is None:
            return
        if a.grid is None:
            a.grid = empty_grid(a.image.shape)
        pts = to_grid_frame(a.grid, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))
        gx0, gy0 = pts.min(axis=0)
        gx1, gy1 = pts.max(axis=0)
        a.grid.squares.append(Square(float(gx0), float(gy0), float(gx1), float(gy1),
                                     row=-1, col=len(a.grid.squares)))
        self.statusBar().showMessage(
            "Square added. It is counted as one large square "
            f"({self.sq_side.value():g} × {self.sq_side.value():g} mm).", 6000)
        self._refresh()

    def _select_all(self, on: bool):
        a = self.cur
        if a and a.grid:
            for sq in a.grid.squares:
                sq.selected = on
        self._refresh()

    def _clear_squares(self):
        a = self.cur
        if a and a.grid:
            a.grid.squares.clear()
        self._refresh()

    # ============================================================= export
    def _rows(self) -> list[dict]:
        mode, dil, ch = self.mode.currentData(), self.dilution.value(), self.chamber()
        sample = self.sample.text().strip() or "sample"
        rows = []
        for a in self.analyses:
            counts, _ = a.counts()
            s = summarize(CountResult(mode, counts, dil, ch))
            manual = any(c.manual for c in a.cells)
            rows.append(make_row(sample, a.name, mode, dil, ch, counts, s,
                                 "auto + manual corrections" if manual else "auto"))
        if len(self.analyses) > 1:
            rows.append(make_row(sample, "ALL", mode, dil, ch, self.sample_counts(),
                                 self.sample_summary(), "pooled"))
        return rows

    def _save_dialog(self, title: str, default: str) -> str | None:
        start = os.path.join(str(self.settings.value("last_dir", os.path.expanduser("~"))), default)
        path, flt = QFileDialog.getSaveFileName(self, title, start,
                                                "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return None
        if not os.path.splitext(path)[1]:
            path += ".csv" if "csv" in flt.lower() else ".xlsx"
        return path

    def export_results(self):
        if not self.analyses:
            QMessageBox.information(self, "Export", "No images analysed yet.")
            return
        path = self._save_dialog("Export results", "foscount_results.xlsx")
        if path:
            try:
                write_rows(self._rows(), path)
                self.statusBar().showMessage(f"Saved {path}", 8000)
            except Exception as e:
                QMessageBox.critical(self, "Export", f"Could not save:\n{e}")

    def export_manual(self):
        m = self.manual
        s = m.summary()
        if s.total == 0:
            QMessageBox.information(self, "Export", "Enter some counts first.")
            return
        path = self._save_dialog("Export manual count", "foscount_manual.xlsx")
        if path:
            row = make_row(self.sample.text().strip() or "sample", "-", m.current_mode,
                           self.dilution.value(), self.chamber(), m.per_square(), s, "manual")
            try:
                write_rows([row], path)
                self.statusBar().showMessage(f"Saved {path}", 8000)
            except Exception as e:
                QMessageBox.critical(self, "Export", f"Could not save:\n{e}")

    def export_annotated(self):
        if not self.analyses:
            return
        d = QFileDialog.getExistingDirectory(self, "Folder for annotated images",
                                             str(self.settings.value("last_dir", "")))
        if not d:
            return
        mode = self.mode.currentData()
        for a in self.analyses:
            base = os.path.splitext(a.name)[0]
            write_image(os.path.join(d, base + "_annotated.png"), a.annotated(mode))
        self.statusBar().showMessage(f"Saved {len(self.analyses)} annotated images to {d}", 8000)

    def batch(self):
        BatchDialog(self.params(), self.chamber(), self.dilution.value(), self).exec()

    def _help(self):
        box = QMessageBox(self)
        box.setWindowTitle("How to use")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(HELP)
        box.exec()
