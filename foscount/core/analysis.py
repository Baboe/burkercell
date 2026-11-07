"""One analysed image: grid + cells + counts, independent of the GUI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from .concentration import Summary, summarize
from .detection import DetectParams, count_squares, detect_cells, set_mode
from .grid import detect_grid, empty_grid, square_corners
from .models import Cell, CellState, Chamber, CountResult, Grid, Mode, SquareCount


def read_image(path: str) -> np.ndarray:
    """Read an image as BGR uint8 (handles non-ASCII paths and 16-bit TIFFs)."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def write_image(path: str, img: np.ndarray) -> None:
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise ValueError(f"Cannot encode image as {ext}")
    buf.tofile(path)


@dataclass
class ImageAnalysis:
    path: str
    image: np.ndarray
    grid: Grid | None = None
    cells: list[Cell] = field(default_factory=list)
    grid_found: bool = False

    @classmethod
    def load(cls, path: str) -> "ImageAnalysis":
        return cls(path=path, image=read_image(path))

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def detect_grid(self, chamber: Chamber) -> bool:
        g = detect_grid(self.image, chamber)
        self.grid_found = g is not None
        self.grid = g if g is not None else empty_grid(self.image.shape)
        return self.grid_found

    def detect_cells(self, params: DetectParams) -> None:
        if self.grid is None:
            self.grid = empty_grid(self.image.shape)
        self.cells = detect_cells(self.image, params, self.grid if self.grid_found else None)

    def run(self, params: DetectParams, chamber: Chamber) -> None:
        self.detect_grid(chamber)
        self.detect_cells(params)

    def set_mode(self, mode: Mode, threshold: float) -> None:
        set_mode(self.cells, mode, threshold)

    def counts(self) -> tuple[list[SquareCount], list[int]]:
        if self.grid is None:
            return [], [-1] * len(self.cells)
        return count_squares(self.cells, self.grid)

    def result(self, mode: Mode, dilution: float, chamber: Chamber) -> CountResult:
        return CountResult(mode, self.counts()[0], dilution, chamber)

    def summary(self, mode: Mode, dilution: float, chamber: Chamber) -> Summary:
        return summarize(self.result(mode, dilution, chamber))

    # ------------------------------------------------------------ rendering
    def annotated(self, mode: Mode) -> np.ndarray:
        """Image with squares, counted cells and per-square counts drawn on it."""
        img = self.image.copy()
        h, w = img.shape[:2]
        th = max(1, int(round(min(h, w) / 500)))
        counts, assign = self.counts()
        if self.grid is not None:
            k = 0
            for sq in self.grid.squares:
                pts = square_corners(self.grid, sq).astype(np.int32)
                if sq.selected:
                    cv2.polylines(img, [pts], True, (255, 160, 0), 2 * th)
                    tl = pts[0]
                    c = counts[k]
                    label = f"{c.total}" if mode == Mode.UNSTAINED else f"L{c.live} D{c.dead}"
                    cv2.putText(img, label, (int(tl[0]) + 6 * th, int(tl[1]) + 22 * th),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7 * th, (255, 160, 0), 2 * th)
                    k += 1
                else:
                    cv2.polylines(img, [pts], True, (160, 160, 160), th)
        for c, a in zip(self.cells, assign):
            col = (40, 40, 230) if c.state == CellState.DEAD else (40, 200, 40)
            if a < 0:
                col = tuple(int(0.5 * v + 64) for v in col)
            r = max(3, int(round(c.radius)))
            cv2.circle(img, (int(round(c.x)), int(round(c.y))), r, col,
                       2 * th if a >= 0 else th)
        return img
