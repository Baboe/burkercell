"""Zoomable image view with cell / square overlays and editing tools."""

from __future__ import annotations

from enum import Enum

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsPixmapItem,
                               QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsSimpleTextItem, QGraphicsView)

from ..core.grid import square_corners
from ..core.models import Cell, CellState, Grid, Mode, SquareCount
from . import theme


class Tool(str, Enum):
    CELLS = "cells"
    SQUARES = "squares"
    DRAW = "draw"


COL_LIVE = QColor(theme.LIVE)
COL_DEAD = QColor(theme.DEAD)
COL_CELL = QColor(theme.LIVE)
COL_SQUARE = QColor(theme.VIVID)
COL_SQUARE_OFF = QColor(theme.MUTED)


def to_qimage(img: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class ImageView(QGraphicsView):
    # x, y in image coordinates, Qt button, Qt modifiers
    clicked = Signal(float, float, object, object)
    rect_drawn = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#F1EFF6")))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._pix: QGraphicsPixmapItem | None = None
        self._overlay: list = []
        self._rubber: QGraphicsRectItem | None = None
        self._press: QPointF | None = None
        self._pan: QPointF | None = None
        self.tool = Tool.CELLS
        self.show_uncounted = True

    # ------------------------------------------------------------- content
    def set_image(self, img: np.ndarray | None) -> None:
        sc = self.scene()
        sc.clear()
        self._overlay = []
        self._pix = None
        if img is None:
            return
        self._pix = sc.addPixmap(QPixmap.fromImage(to_qimage(img)))
        sc.setSceneRect(QRectF(0, 0, img.shape[1], img.shape[0]))
        self.fit()

    def fit(self) -> None:
        if self._pix is not None:
            self.fitInView(self._pix, Qt.AspectRatioMode.KeepAspectRatio)

    def set_overlay(self, grid: Grid | None, cells: list[Cell], assign: list[int],
                    counts: list[SquareCount], mode: Mode) -> None:
        sc = self.scene()
        for it in self._overlay:
            sc.removeItem(it)
        self._overlay = []
        if self._pix is None:
            return
        w = self._pix.pixmap().width()
        lw = max(1.0, w / 800)

        if grid is not None:
            k = 0
            for sq in grid.squares:
                pts = square_corners(grid, sq)
                poly = QPolygonF([QPointF(float(x), float(y)) for x, y in pts])
                item = QGraphicsPolygonItem(poly)
                col = COL_SQUARE if sq.selected else COL_SQUARE_OFF
                pen = QPen(col, 2.5 if sq.selected else 1.2)
                pen.setCosmetic(True)  # constant on-screen width at any zoom
                if not sq.selected:
                    pen.setStyle(Qt.PenStyle.DashLine)
                item.setPen(pen)
                sc.addItem(item)
                self._overlay.append(item)
                if sq.selected and k < len(counts):
                    c = counts[k]
                    txt = (f"#{k + 1}: {c.total}" if mode == Mode.UNSTAINED
                           else f"#{k + 1}: {c.live} live / {c.dead} dead")
                    t = QGraphicsSimpleTextItem(txt)
                    t.setBrush(QBrush(QColor("white")))
                    f = t.font()
                    f.setPixelSize(int(max(5, w / 70)))
                    f.setBold(True)
                    t.setFont(f)
                    pos = QPointF(float(pts[0][0]) + 4 * lw, float(pts[0][1]) + 4 * lw)
                    br = t.boundingRect()
                    pad = 0.35 * f.pixelSize()
                    bg = QGraphicsRectItem(QRectF(pos.x() - pad, pos.y() - pad / 2,
                                                  br.width() + 2 * pad, br.height() + pad))
                    bg.setBrush(QBrush(QColor(theme.PRIMARY)))
                    bg.setPen(QPen(Qt.PenStyle.NoPen))
                    t.setPos(pos)
                    sc.addItem(bg)
                    sc.addItem(t)
                    self._overlay += [bg, t]
                    k += 1

        for c, a in zip(cells, assign):
            counted = a >= 0
            if not counted and not self.show_uncounted:
                continue
            if c.state == CellState.DEAD:
                col = QColor(COL_DEAD)
            elif c.state == CellState.LIVE:
                col = QColor(COL_LIVE)
            else:
                col = QColor(COL_CELL)
            if not counted:
                col.setAlpha(110)
            r = max(3.0, c.radius)
            e = QGraphicsEllipseItem(c.x - r, c.y - r, 2 * r, 2 * r)
            pen = QPen(col, 2.0 if counted else 1.0)
            pen.setCosmetic(True)
            if c.manual:
                pen.setStyle(Qt.PenStyle.DashLine)
            e.setPen(pen)
            sc.addItem(e)
            self._overlay.append(e)

    # ---------------------------------------------------------------- input
    def wheelEvent(self, ev):
        if self._pix is None:
            return
        f = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.scale(f, f)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton or (
                ev.button() == Qt.MouseButton.LeftButton
                and ev.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._pan = ev.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        p = self.mapToScene(ev.position().toPoint())
        if self.tool == Tool.DRAW and ev.button() == Qt.MouseButton.LeftButton:
            self._press = p
            self._rubber = self.scene().addRect(QRectF(p, p), QPen(COL_SQUARE, 2, Qt.PenStyle.DashLine))
            return
        self._press = p
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._pan is not None:
            d = ev.position() - self._pan
            self._pan = ev.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        if self._rubber is not None and self._press is not None:
            p = self.mapToScene(ev.position().toPoint())
            self._rubber.setRect(QRectF(self._press, p).normalized())
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._pan is not None:
            self._pan = None
            self.unsetCursor()
            return
        p = self.mapToScene(ev.position().toPoint())
        if self._rubber is not None:
            r = self._rubber.rect()
            self.scene().removeItem(self._rubber)
            self._rubber = None
            if r.width() > 5 and r.height() > 5:
                self.rect_drawn.emit(r.left(), r.top(), r.right(), r.bottom())
            self._press = None
            return
        if self._press is not None and self._pix is not None:
            if (p - self._press).manhattanLength() < 6:
                self.clicked.emit(p.x(), p.y(), ev.button(), ev.modifiers())
        self._press = None
        super().mouseReleaseEvent(ev)
