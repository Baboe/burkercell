"""Manual entry of counts made by eye at the microscope (no camera needed)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ..core.concentration import Summary, summarize
from ..core.models import Chamber, CountResult, Mode, SquareCount
from . import theme
from .summary_text import summary_html


class ManualEntry(QWidget):
    changed = Signal()

    def __init__(self, mode_getter, dilution_getter, chamber_getter, parent=None):
        """Mode, dilution and chamber come from the shared settings panel."""
        super().__init__(parent)
        self._mode_getter = mode_getter
        self._dilution_getter = dilution_getter
        self._chamber_getter = chamber_getter
        self._undo: list[tuple[int, int]] = []  # (row, col)
        self._updating = False
        self._mode = mode_getter()

        self.n_squares = QSpinBox()
        self.n_squares.setRange(1, 400)
        self.n_squares.setValue(1)

        form = QFormLayout()
        form.addRow("Large squares counted:", self.n_squares)
        note = QLabel("Mode, dilution and chamber are taken from the settings panel on the right.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        form.addRow(note)

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # tally counter
        tally, tally_lay = theme.card("Tally counter  ·  keys: L live/cell, D dead, "
                                      "N next square, Backspace undo")
        self.btn_live = QPushButton("+ Live / cell  [L]")
        self.btn_dead = QPushButton("+ Dead  [D]")
        self.btn_next = QPushButton("Next square  [N]")
        self.btn_undo = QPushButton("Undo  [⌫]")
        self.btn_clear = QPushButton("Clear all")
        for b in (self.btn_live, self.btn_dead, self.btn_next):
            b.setMinimumHeight(44)
        tl = QHBoxLayout()
        tally_lay.addLayout(tl)
        self.btn_live.setProperty("variant", "primary")
        for b in (self.btn_live, self.btn_dead, self.btn_next, self.btn_undo, self.btn_clear):
            tl.addWidget(b)

        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.setWordWrap(True)
        self.result.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QHBoxLayout()
        top.addLayout(form, 1)
        top.addWidget(self.result, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 8)
        lay.setSpacing(12)
        lay.addLayout(top)
        lay.addWidget(tally)
        lay.addWidget(self.table, 1)
        hint = QLabel("Count the cells inside each large square (0.2 × 0.2 mm). "
                      "Count cells touching the top and left lines, not those "
                      "touching the bottom and right lines.")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        lay.addWidget(hint)

        self.n_squares.valueChanged.connect(self._resize)
        self.table.itemChanged.connect(self._item_changed)
        self.btn_live.clicked.connect(lambda: self._tally(0))
        self.btn_dead.clicked.connect(lambda: self._tally(1))
        self.btn_next.clicked.connect(self._next)
        self.btn_undo.clicked.connect(self._undo_last)
        self.btn_clear.clicked.connect(self._clear)
        for key, fn in (("L", lambda: self._tally(0)), ("C", lambda: self._tally(0)),
                        ("D", lambda: self._tally(1)), ("N", self._next),
                        ("Backspace", self._undo_last)):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self._rebuild()

    # ------------------------------------------------------------- helpers
    @property
    def current_mode(self) -> Mode:
        return self._mode

    def settings_changed(self) -> None:
        """Call when the shared mode / dilution / chamber settings change."""
        mode = self._mode_getter()
        if mode != self._mode:
            self._mode = mode
            self._rebuild()
        else:
            self.refresh()

    def _columns(self) -> list[str]:
        return ["Cells"] if self.current_mode == Mode.UNSTAINED else ["Live", "Dead"]

    def _rebuild(self) -> None:
        old = self._values()
        self._updating = True
        cols = self._columns()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(self.n_squares.value())
        for r in range(self.table.rowCount()):
            for c in range(len(cols)):
                v = old[r][c] if r < len(old) and c < len(old[r]) else 0
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.setVerticalHeaderLabels([f"Square {i + 1}" for i in range(self.table.rowCount())])
        self._updating = False
        self.btn_dead.setEnabled(self.current_mode == Mode.TRYPAN)
        self._undo.clear()
        if self.table.currentRow() < 0:
            self.table.setCurrentCell(0, 0)
        self.refresh()

    def _resize(self) -> None:
        self._rebuild()

    def _values(self) -> list[list[int]]:
        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                try:
                    row.append(max(0, int(float(it.text()))) if it else 0)
                except ValueError:
                    row.append(0)
            out.append(row)
        return out

    def _item_changed(self, _item) -> None:
        if not self._updating:
            self.refresh()

    def _tally(self, col: int) -> None:
        if col == 1 and self.current_mode != Mode.TRYPAN:
            return
        r = max(0, self.table.currentRow())
        c = min(col, self.table.columnCount() - 1)
        it = self.table.item(r, c)
        v = self._values()[r][c] + 1
        self._updating = True
        it.setText(str(v))
        self._updating = False
        self._undo.append((r, c))
        self.table.setCurrentCell(r, c)
        self.refresh()

    def _next(self) -> None:
        r = self.table.currentRow() + 1
        if r >= self.table.rowCount():
            self.n_squares.setValue(r + 1)
        self.table.setCurrentCell(r, 0)

    def _undo_last(self) -> None:
        if not self._undo:
            return
        r, c = self._undo.pop()
        v = max(0, self._values()[r][c] - 1)
        self._updating = True
        self.table.item(r, c).setText(str(v))
        self._updating = False
        self.table.setCurrentCell(r, c)
        self.refresh()

    def _clear(self) -> None:
        self._updating = True
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                self.table.item(r, c).setText("0")
        self._updating = False
        self._undo.clear()
        self.table.setCurrentCell(0, 0)
        self.refresh()

    # -------------------------------------------------------------- results
    def per_square(self) -> list[SquareCount]:
        out = []
        for row in self._values():
            if self.current_mode == Mode.UNSTAINED:
                out.append(SquareCount(total=row[0], live=row[0], dead=0))
            else:
                out.append(SquareCount(total=row[0] + row[1], live=row[0], dead=row[1]))
        return out

    def count_result(self) -> CountResult:
        return CountResult(self.current_mode, self.per_square(), self._dilution_getter(),
                           self._chamber_getter())

    def summary(self) -> Summary:
        return summarize(self.count_result())

    def refresh(self) -> None:
        self.result.setText(summary_html("Manual count", self.summary(), self.current_mode))
        self.changed.emit()
