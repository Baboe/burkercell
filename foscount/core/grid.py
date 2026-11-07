"""Detection of the Bürker counting grid.

Approach
--------
1. Enhance thin line structures with a morphological top-hat / black-hat.
2. Estimate the grid rotation by searching the angle that makes the row and
   column projection profiles sharpest (lines then add up in a single bin while
   cells average out).
3. Deskew and find line positions as peaks in the projection profiles.
4. Classify the gaps between consecutive lines. In a Bürker chamber the large
   counting squares (0.2 mm) are four times wider than the strips between the
   double lines (0.05 mm), so the largest regular gap is a counting square.

All square coordinates are expressed in the *grid frame*: the image rotated by
``grid.angle_deg`` around ``grid.center``. Use :func:`to_grid_frame` and
:func:`from_grid_frame` to convert points.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks, peak_widths

from .models import Chamber, Grid, Square


# ----------------------------------------------------------------- transforms
def _matrix(grid: Grid) -> np.ndarray:
    return cv2.getRotationMatrix2D(grid.center, grid.angle_deg, 1.0)


def to_grid_frame(grid: Grid, pts: np.ndarray) -> np.ndarray:
    """Image coordinates (N,2) -> grid frame coordinates (N,2)."""
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    m = _matrix(grid)
    return pts @ m[:, :2].T + m[:, 2]


def from_grid_frame(grid: Grid, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    inv = cv2.invertAffineTransform(_matrix(grid))
    return pts @ inv[:, :2].T + inv[:, 2]


def square_corners(grid: Grid, sq: Square) -> np.ndarray:
    """The 4 corners of a square in image coordinates (TL, TR, BR, BL)."""
    pts = np.array([[sq.x0, sq.y0], [sq.x1, sq.y0], [sq.x1, sq.y1], [sq.x0, sq.y1]])
    return from_grid_frame(grid, pts)


# ------------------------------------------------------------------ detection
def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.astype(np.float32)


def _line_maps(gray: np.ndarray) -> list[np.ndarray]:
    k = max(7, int(round(min(gray.shape) * 0.015)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    dark = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    bright = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    return [dark, bright]


def _rotate(img: np.ndarray, angle: float, center: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rot = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpAffine(np.ones((h, w), np.float32), m, (w, h),
                           flags=cv2.INTER_NEAREST, borderValue=0)
    return rot, valid


def _profiles(enh: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    col_n = valid.sum(axis=0)
    row_n = valid.sum(axis=1)
    col = enh.sum(axis=0) / np.maximum(col_n, 1)
    row = enh.sum(axis=1) / np.maximum(row_n, 1)
    # ignore columns/rows that are mostly outside the rotated image
    col[col_n < 0.5 * enh.shape[0]] = 0
    row[row_n < 0.5 * enh.shape[1]] = 0
    return col, row


def _sharpness(profile: np.ndarray) -> float:
    p = profile[profile > 0]
    if p.size < 10:
        return 0.0
    return float(np.std(p) / (np.mean(p) + 1e-6))


def estimate_angle(enh: np.ndarray, max_angle: float = 12.0) -> tuple[float, float]:
    """Return (angle_deg, score) maximising projection sharpness."""
    h, w = enh.shape
    s = min(1.0, 700.0 / max(h, w))
    small = cv2.resize(enh, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    c = (small.shape[1] / 2.0, small.shape[0] / 2.0)

    def score(a: float) -> float:
        rot, valid = _rotate(small, a, c)
        col, row = _profiles(rot, valid)
        return _sharpness(col) + _sharpness(row)

    angles = np.arange(-max_angle, max_angle + 1e-9, 0.5)
    scores = [score(a) for a in angles]
    best = float(angles[int(np.argmax(scores))])
    for step in (0.1, 0.02):
        fine = np.arange(best - 5 * step, best + 5 * step + 1e-9, step)
        fs = [score(a) for a in fine]
        best = float(fine[int(np.argmax(fs))])
    return best, max(scores)


def find_lines(profile: np.ndarray, min_sep: int) -> tuple[np.ndarray, float]:
    """Line positions (sub-pixel) as peaks in a projection profile, plus the
    median full width of the lines at 25 % of their height."""
    p = profile.astype(np.float64)
    nz = p > 0
    if nz.sum() < 10:
        return np.array([]), 0.0
    base = median_filter(p, size=max(15, 4 * min_sep) | 1, mode="nearest")
    d = p - base
    d[~nz] = 0
    noise = 1.4826 * np.median(np.abs(d[nz] - np.median(d[nz]))) + 1e-9
    peaks, props = find_peaks(d, distance=max(2, min_sep), prominence=6 * noise)
    if peaks.size == 0:
        return peaks.astype(float), 0.0
    # keep only peaks clearly above the typical peak height (rejects texture)
    # grid lines span the whole image, so they are by far the strongest peaks;
    # cells (especially dark, stained ones) only make small bumps
    strong = props["prominences"] >= 0.3 * props["prominences"].max()
    peaks = peaks[strong]
    width = float(np.median(peak_widths(d, peaks, rel_height=0.75)[0]))
    # sub-pixel refinement by parabola fit
    out = []
    for i in peaks:
        if 0 < i < len(d) - 1:
            a, b, c = d[i - 1], d[i], d[i + 1]
            den = a - 2 * b + c
            off = 0.5 * (a - c) / den if den != 0 else 0.0
            out.append(i + float(np.clip(off, -0.5, 0.5)))
        else:
            out.append(float(i))
    return np.array(out), width


def _square_intervals(lines: np.ndarray) -> tuple[list[tuple[float, float]], float | None, bool]:
    """Pick the gaps between lines that are large counting squares.

    Returns (intervals, square_size_px, confident). ``confident`` is True when
    strips with ~1/4 of the square size were also found, confirming the scale.
    """
    if len(lines) < 2:
        return [], None, False
    gaps = np.diff(lines)
    big = gaps.max()
    cand = gaps[gaps >= 0.7 * big]
    size = float(np.median(cand))
    intervals = [(float(lines[i]), float(lines[i + 1]))
                 for i, g in enumerate(gaps) if 0.8 * size <= g <= 1.2 * size]
    ratio = 0.05 / 0.2
    has_strips = bool(np.any(np.abs(gaps / size - ratio) < 0.08))
    return intervals, size, has_strips


def detect_grid(img: np.ndarray, chamber: Chamber | None = None,
                max_angle: float = 12.0) -> Grid | None:
    """Detect the counting grid. Returns ``None`` if no square was found."""
    chamber = chamber or Chamber()
    gray = _to_gray(img)
    h, w = gray.shape
    center = (w / 2.0, h / 2.0)

    best: Grid | None = None
    best_score = -1.0
    for enh in _line_maps(gray):
        angle, score = estimate_angle(enh, max_angle)
        rot, valid = _rotate(enh, angle, center)
        col, row = _profiles(rot, valid)
        min_sep = max(3, int(min(h, w) * 0.004))
        v, vw = find_lines(col, min_sep)
        hl, hw = find_lines(row, min_sep)
        xi, xs, xconf = _square_intervals(v)
        yi, ys, yconf = _square_intervals(hl)
        if not xi or not yi:
            continue
        # squares must be (roughly) square
        if not (0.75 < xs / ys < 1.33):
            continue
        sc = score + (1.0 if (xconf and yconf) else 0.0)
        if sc > best_score:
            squares = []
            for r, (y0, y1) in enumerate(yi):
                for c, (x0, x1) in enumerate(xi):
                    squares.append(Square(x0, y0, x1, y1, row=r, col=c))
            px_per_mm = 0.5 * (xs + ys) / chamber.square_side_mm
            best = Grid(angle_deg=angle, center=center, squares=squares,
                        px_per_mm=px_per_mm, v_lines=list(v), h_lines=list(hl),
                        line_width_px=max(vw, hw))
            best_score = sc
    return best


def empty_grid(img_shape: tuple[int, ...]) -> Grid:
    h, w = img_shape[:2]
    return Grid(angle_deg=0.0, center=(w / 2.0, h / 2.0))


def line_mask(grid: Grid, shape: tuple[int, ...], width: int = 3) -> np.ndarray:
    """Binary mask (uint8) of detected grid lines in image coordinates."""
    h, w = shape[:2]
    mask = np.zeros((h, w), np.uint8)
    big = 2 * max(h, w)
    for x in grid.v_lines:
        p = from_grid_frame(grid, np.array([[x, -big], [x, big]]))
        cv2.line(mask, tuple(np.round(p[0]).astype(int)), tuple(np.round(p[1]).astype(int)), 255, width)
    for y in grid.h_lines:
        p = from_grid_frame(grid, np.array([[-big, y], [big, y]]))
        cv2.line(mask, tuple(np.round(p[0]).astype(int)), tuple(np.round(p[1]).astype(int)), 255, width)
    return mask
