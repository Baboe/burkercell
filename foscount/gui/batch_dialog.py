"""Dialog that runs the batch processor in a worker thread."""

from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from ..core.batch import find_images, run_batch
from ..core.detection import DetectParams
from ..core.models import Chamber


class _Worker(QThread):
    progressed = Signal(int, int, str)
    finished_ok = Signal(str, int)
    failed = Signal(str)

    def __init__(self, args: dict):
        super().__init__()
        self.args = args
        self.cancel = False

    def run(self):
        try:
            def cb(i, n, name):
                self.progressed.emit(i, n, name)
                return not self.cancel
            rows, out = run_batch(progress=cb, **self.args)
            self.finished_ok.emit(out, len(rows))
        except Exception as e:  # pragma: no cover - shown to the user
            self.failed.emit(str(e))


def _path_row(edit: QLineEdit, title: str, parent) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    b = QPushButton("Browse…")
    lay.addWidget(edit, 1)
    lay.addWidget(b)

    def pick():
        d = QFileDialog.getExistingDirectory(parent, title, edit.text() or os.getcwd())
        if d:
            edit.setText(d)
    b.clicked.connect(pick)
    return w


class BatchDialog(QDialog):
    def __init__(self, params: DetectParams, chamber: Chamber, dilution: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch processing")
        self.resize(560, 260)
        self.params, self.chamber, self.dilution = params, chamber, dilution
        self.worker: _Worker | None = None

        self.inp = QLineEdit()
        self.out = QLineEdit()
        self.inp.textChanged.connect(lambda t: self.out.setText(os.path.join(t, "foscount_output")) if t else None)
        self.recursive = QCheckBox("Include subfolders (each folder = one sample)")
        self.recursive.setChecked(True)
        self.annot = QCheckBox("Save annotated images")
        self.annot.setChecked(True)
        self.fmt = QComboBox()
        self.fmt.addItems(["xlsx", "csv"])
        form = QFormLayout()
        form.addRow("Image folder:", _path_row(self.inp, "Image folder", self))
        form.addRow("Output folder:", _path_row(self.out, "Output folder", self))
        form.addRow("", self.recursive)
        form.addRow("", self.annot)
        form.addRow("Results format:", self.fmt)
        mode = "trypan blue (live/dead)" if params.mode.value == "trypan" else "unstained"
        info = QLabel(f"Uses the current settings: mode <b>{mode}</b>, dilution <b>{dilution:g}</b>, "
                      f"sensitivity {params.sensitivity}, cell diameter {params.cell_diameter_um:g} µm. "
                      "All complete squares found in each image are counted.")
        info.setWordWrap(True)
        self.bar = QProgressBar()
        self.status = QLabel("")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.run_btn = self.buttons.addButton("Run", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.accepted.connect(self._run)
        self.buttons.rejected.connect(self._close)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(info)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)
        lay.addWidget(self.buttons)

    def _run(self):
        folder, out = self.inp.text().strip(), self.out.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Batch", "Choose an existing image folder.")
            return
        n = len(find_images(folder, self.recursive.isChecked()))
        if n == 0:
            QMessageBox.warning(self, "Batch", "No images (png, jpg, tif, bmp) found.")
            return
        self.run_btn.setEnabled(False)
        self.worker = _Worker(dict(folder=folder, out_dir=out, params=self.params,
                                   chamber=self.chamber, dilution=self.dilution,
                                   recursive=self.recursive.isChecked(),
                                   save_annotated=self.annot.isChecked(),
                                   fmt=self.fmt.currentText()))
        self.worker.progressed.connect(self._progress)
        self.worker.finished_ok.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _progress(self, i, n, name):
        self.bar.setMaximum(max(1, n))
        self.bar.setValue(i)
        self.status.setText(f"{i}/{n}  {name}")

    def _done(self, path, nrows):
        self.run_btn.setEnabled(True)
        self.status.setText(f"Done. Results written to {path}")
        QMessageBox.information(self, "Batch", f"Finished.\n\nResults: {path}")

    def _failed(self, msg):
        self.run_btn.setEnabled(True)
        QMessageBox.critical(self, "Batch", f"Batch failed:\n{msg}")

    def _close(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel = True
            self.worker.wait(5000)
        self.reject()
