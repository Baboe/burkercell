"""Cell detection and live/dead classification."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage as ndi

from .grid import line_mask, to_grid_frame
from .models import Cell, CellState, Grid, Mode, Square, SquareCount


@dataclass
class DetectParams:
    mode: Mode = Mode.UNSTAINED
    cell_diameter_um: float = 12.0  # used when the grid gives a px/mm scale
    cell_diameter_px: float = 20.0  # fallback when no scale is known
    sensitivity: int = 50  # 0..100, higher finds fainter objects
    min_size: float = 0.6  # relative to expected diameter
    max_size: float = 2.0
    split_touching: bool = True
    circle_pass: bool = True  # also look for round cells with a circle detector
    max_elongation: float = 2.2  # major/minor axis ratio above which a blob is rejected
    dead_threshold: float = 20.0  # trypan stain score above which a cell is dead
    mask_grid_lines: bool = True

    def diameter_px(self, grid: Grid | None) -> float:
        if grid is not None and grid.px_per_mm:
            return max(4.0, self.cell_diameter_um * 1e-3 * grid.px_per_mm)
        return max(4.0, self.cell_diameter_px)


def _odd(n: float) -> int:
    n = max(3, int(round(n)))
    return n if n % 2 else n + 1


def _peaks(dist: np.ndarray, min_dist: int, min_val: float) -> np.ndarray:
    size = 2 * min_dist + 1
    mx = ndi.maximum_filter(dist, size=size, mode="constant")
    peaks = (dist == mx) & (dist >= min_val)
    lab, n = ndi.label(peaks)
    if n == 0:
        return np.zeros((0, 2))
    # plateau -> one point each
    return np.array(ndi.center_of_mass(peaks, lab, range(1, n + 1)))


def background(gray: np.ndarray, d: float) -> np.ndarray:
    """Smooth background estimate that ignores cells and grid lines.

    A median filter over ~5 cell diameters, computed on a downscaled copy for
    speed, then upsampled.
    """
    h, w = gray.shape
    f = min(1.0, 6.0 / max(d, 1.0))
    small = cv2.resize(gray, (max(8, int(w * f)), max(8, int(h * f))),
                       interpolation=cv2.INTER_AREA)
    k = _odd(5 * d * f)
    k = min(k, (min(small.shape) // 2) * 2 - 1)
    med = cv2.medianBlur(np.clip(small, 0, 255).astype(np.uint8), max(3, k))
    med = cv2.GaussianBlur(med.astype(np.float32), (0, 0), sigmaX=max(1.0, d * f))
    return cv2.resize(med, (w, h), interpolation=cv2.INTER_LINEAR)


def split_blobs(binary: np.ndarray, r_exp: float) -> tuple[np.ndarray, int]:
    """Split touching cells: each blob is divided between the local maxima of
    its distance transform (nearest-peak partition, a cheap watershed)."""
    cc, ncc = ndi.label(binary)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    labels = np.zeros(binary.shape, np.int32)
    n = 0
    if ncc == 0:
        return labels, 0
    areas = np.bincount(cc.ravel())[1:]
    # typical single-cell area: median of plausibly sized blobs
    a_exp = np.pi * r_exp ** 2
    plausible = areas[(areas > 0.3 * a_exp) & (areas < 3 * a_exp)]
    a_single = float(np.median(plausible)) if plausible.size >= 5 else a_exp
    for i, sl in enumerate(ndi.find_objects(cc), start=1):
        if sl is None:
            continue
        blob = cc[sl] == i
        pk = []
        if areas[i - 1] > 1.45 * a_single:
            pk = _peaks(np.where(blob, dist[sl], 0), max(2, int(r_exp * 0.9)), r_exp * 0.4)
        if len(pk) <= 1:
            n += 1
            labels[sl][blob] = n
            continue
        seeds = np.zeros(blob.shape, np.int32)
        for j, (py, px) in enumerate(pk, start=1):
            seeds[int(round(py)), int(round(px))] = j
        _, (iy, ix) = ndi.distance_transform_edt(seeds == 0, return_indices=True)
        part = seeds[iy, ix]
        labels[sl][blob] = part[blob] + n
        n += len(pk)
    return labels, n


MIN_CELL_PX = 18.0  # below this expected diameter the image is upsampled first


def _scaled_grid(grid: Grid, f: float) -> Grid:
    return Grid(angle_deg=grid.angle_deg, center=(grid.center[0] * f, grid.center[1] * f),
                squares=[Square(q.x0 * f, q.y0 * f, q.x1 * f, q.y1 * f, q.row, q.col, q.selected)
                         for q in grid.squares],
                px_per_mm=grid.px_per_mm * f if grid.px_per_mm else None,
                v_lines=[v * f for v in grid.v_lines], h_lines=[h * f for h in grid.h_lines],
                line_width_px=grid.line_width_px * f)


def detect_cells(img: np.ndarray, params: DetectParams,
                 grid: Grid | None = None) -> list[Cell]:
    """Detect cells in a BGR (or grayscale) image.

    Small cells (low resolution or low magnification) are detected on an
    upsampled copy so the morphological steps have enough pixels to work with.
    """
    d = params.diameter_px(grid)
    if d >= MIN_CELL_PX:
        return _detect_cells(img, params, grid)
    f = min(4.0, MIN_CELL_PX / d)
    big = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    p2 = DetectParams(**{**params.__dict__, "cell_diameter_px": params.cell_diameter_px * f})
    cells = _detect_cells(big, p2, _scaled_grid(grid, f) if grid is not None else None)
    for c in cells:
        c.x, c.y, c.radius = c.x / f, c.y / f, c.radius / f
    return cells


def _detect_cells(img: np.ndarray, params: DetectParams,
                  grid: Grid | None = None) -> list[Cell]:
    color = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY).astype(np.float32)
    d = params.diameter_px(grid)
    r_exp = d / 2.0

    # background and deviation map: cells differ from the background, darker
    # rims and (for live cells) brighter centres both count.
    lines = None
    if params.mask_grid_lines and grid is not None and (grid.v_lines or grid.h_lines):
        # paint the grid lines out so cells lying on a line are not cut in two
        lines = line_mask(grid, gray.shape, width=int(round(grid.line_width_px * 1.5 + 4)))
        g8 = np.clip(gray, 0, 255).astype(np.uint8)
        gray = cv2.inpaint(g8, lines, 3, cv2.INPAINT_TELEA).astype(np.float32)

    bg = background(gray, d)
    dev = np.abs(gray - bg)
    dev = cv2.GaussianBlur(dev, (0, 0), sigmaX=max(1.0, d / 10))

    # robust background spread: only use the lower half of the distribution,
    # which is dominated by empty background even when many cells are present.
    valid = dev.ravel()
    med = float(np.median(valid))
    low = valid[valid <= med]
    spread = float(np.median(med - low)) * 1.4826 + 1e-3
    k = 12.0 - 0.1 * float(np.clip(params.sensitivity, 0, 100))  # 12 .. 2
    binary = (dev > med + k * spread).astype(np.uint8)

    ks = _odd(d / 5)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kern)
    binary = ndi.binary_fill_holes(binary).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kern)

    labels, n = split_blobs(binary, r_exp) if params.split_touching else ndi.label(binary)

    a_min = np.pi * (params.min_size * r_exp) ** 2
    a_max = np.pi * (params.max_size * r_exp) ** 2
    cells: list[Cell] = []
    for lab_id, sl in enumerate(ndi.find_objects(labels) if n > 0 else [], start=1):
        if sl is None:
            continue
        ys, xs = np.nonzero(labels[sl] == lab_id)
        area = ys.size
        if not (a_min <= area <= a_max):
            continue
        # reject elongated fragments (grid-line remnants, debris, fibres)
        if area >= 5:
            cov = np.cov(np.vstack([xs, ys]).astype(np.float64))
            ev = np.linalg.eigvalsh(cov)
            if ev[0] <= 0 or np.sqrt(ev[1] / ev[0]) > params.max_elongation:
                continue
        cx = float(xs.mean() + sl[1].start)
        cy = float(ys.mean() + sl[0].start)
        cells.append(Cell(cx, cy, float(np.sqrt(area / np.pi))))

    if params.circle_pass:
        raw_dev = np.abs(gray - bg)
        cells += _circle_pass(gray, raw_dev, med + k * spread, cells, r_exp, params.sensitivity)

    # stain scores are always computed so the mode can be switched later
    # without re-detecting (darkness uses the line-free image)
    stain_scores(color, gray, bg, cells)
    set_mode(cells, params.mode, params.dead_threshold)
    return cells


def _circle_pass(gray: np.ndarray, dev: np.ndarray, thr: float, found: list[Cell],
                 r_exp: float, sensitivity: int) -> list[Cell]:
    """Find round cells missed by the threshold mask (faint or partial
    outlines, touching pairs) with a Hough circle transform.

    A circle is kept only if the image clearly differs from the background
    along its outline and it does not duplicate an existing detection.
    """
    g8 = cv2.GaussianBlur(np.clip(gray, 0, 255).astype(np.uint8), (0, 0), max(1.0, r_exp / 6))
    # votes scale with the circumference, so the threshold scales with radius
    acc = max(6, int(round(r_exp * (2.0 - 0.016 * float(np.clip(sensitivity, 0, 100))))))
    circles = cv2.HoughCircles(g8, cv2.HOUGH_GRADIENT, dp=1, minDist=max(3, int(1.1 * r_exp)),
                               param1=60, param2=acc,
                               minRadius=max(2, int(0.6 * r_exp)),
                               maxRadius=max(3, int(1.5 * r_exp)))
    if circles is None:
        return []
    h, w = gray.shape
    ang = np.linspace(0, 2 * np.pi, 32, endpoint=False)
    out: list[Cell] = []
    for x, y, r in circles[0]:
        if any((c.x - x) ** 2 + (c.y - y) ** 2 < (0.8 * max(r, c.radius)) ** 2
               for c in found + out):
            continue
        # strongest deviation in a thin band around the circle, per angle
        best = np.zeros_like(ang)
        for rr in (r - 1.5, r, r + 1.5):
            xs = np.clip(np.round(x + rr * np.cos(ang)).astype(int), 0, w - 1)
            ys = np.clip(np.round(y + rr * np.sin(ang)).astype(int), 0, h - 1)
            best = np.maximum(best, dev[ys, xs])
        # most of the outline must stand out from the background
        if np.mean(best > thr) < 0.5:
            continue
        out.append(Cell(float(x), float(y), float(r)))
    return out


def set_mode(cells: list[Cell], mode: Mode, threshold: float) -> None:
    if mode == Mode.TRYPAN:
        apply_dead_threshold(cells, threshold)
    else:
        for c in cells:
            c.state = CellState.CELL


def stain_scores(color: np.ndarray, gray: np.ndarray, bg: np.ndarray,
                 cells: list[Cell]) -> None:
    """Compute a stain score per cell: blueness above background + darkness."""
    b, g, r = [c.astype(np.float32) for c in cv2.split(color)]
    blue = b - 0.5 * (g + r)
    blue_bg = float(np.median(blue))
    h, w = gray.shape
    for c in cells:
        rr = max(1.5, c.radius * 0.6)
        x0, x1 = int(max(0, c.x - rr)), int(min(w, c.x + rr + 1))
        y0, y1 = int(max(0, c.y - rr)), int(min(h, c.y + rr + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        m = (xx - c.x) ** 2 + (yy - c.y) ** 2 <= rr * rr
        if not m.any():
            continue
        blueness = float(blue[y0:y1, x0:x1][m].mean()) - blue_bg
        darkness = float((bg[y0:y1, x0:x1] - gray[y0:y1, x0:x1])[m].mean())
        c.stain_score = blueness + 0.5 * darkness


def apply_dead_threshold(cells: list[Cell], threshold: float) -> None:
    for c in cells:
        if not c.manual or c.state == CellState.CELL:
            c.state = CellState.DEAD if c.stain_score > threshold else CellState.LIVE


def score_single_cell(img: np.ndarray, cell: Cell, diameter_px: float) -> None:
    """Stain score for a manually added cell."""
    color = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg = background(gray, diameter_px)
    stain_scores(color, gray, bg, [cell])


# -------------------------------------------------------------- square rules
def assign_to_squares(cells: list[Cell], grid: Grid) -> list[int]:
    """Index of the selected square each cell is counted in, or -1.

    Standard counting rule: cells touching the top or left boundary line are
    counted, cells touching the bottom or right line are not. For a cell with
    centre ``c`` and radius ``r`` inside boundaries ``[x0, x1]`` that means
    ``x0 - r <= c < x1 - r`` (and the same for y).
    """
    if not cells:
        return []
    pts = to_grid_frame(grid, np.array([[c.x, c.y] for c in cells]))
    out = []
    for c, (gx, gy) in zip(cells, pts):
        r = c.radius
        idx = -1
        for i, sq in enumerate(grid.squares):
            if not sq.selected:
                continue
            if sq.x0 - r <= gx < sq.x1 - r and sq.y0 - r <= gy < sq.y1 - r:
                idx = i
                break
        out.append(idx)
    return out


def count_squares(cells: list[Cell], grid: Grid) -> tuple[list[SquareCount], list[int]]:
    assign = assign_to_squares(cells, grid)
    selected = [i for i, s in enumerate(grid.squares) if s.selected]
    pos = {sq_i: k for k, sq_i in enumerate(selected)}
    counts = [SquareCount() for _ in selected]
    for c, a in zip(cells, assign):
        if a < 0:
            continue
        sc = counts[pos[a]]
        sc.total += 1
        if c.state == CellState.DEAD:
            sc.dead += 1
        else:
            sc.live += 1
    return counts, assign
