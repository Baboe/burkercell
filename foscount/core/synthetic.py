"""Synthetic Bürker chamber images for testing and demos.

These are *not* real micrographs: they imitate a brightfield image with a
(slightly rotated) Bürker grid, round cells with a dark rim and, optionally,
trypan-blue stained dead cells. Ground truth is returned so the detectors can
be tested.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class SyntheticTruth:
    cells: list[tuple[float, float, float, bool]]  # x, y, r, dead
    angle_deg: float
    px_per_mm: float
    square_origin: tuple[float, float]  # grid-frame (x, y) of the first big square


def make_burker_image(width: int = 1600, height: int = 1200, px_per_mm: float = 2400.0,
                      angle_deg: float = 2.0, n_cells: int = 120, cell_um: float = 13.0,
                      dead_fraction: float = 0.0, seed: int = 0,
                      line_dark: bool = True) -> tuple[np.ndarray, SyntheticTruth]:
    rng = np.random.default_rng(seed)
    big = int(max(width, height) * 1.6)
    canvas = np.full((big, big, 3), (205, 200, 196), np.float32)  # BGR
    if dead_fraction > 0:
        canvas[:] = (212, 196, 186)  # trypan gives a bluish background

    sq = 0.2 * px_per_mm
    strip = 0.05 * px_per_mm
    period = sq + strip
    lw = max(2, int(round(px_per_mm * 0.0012)))
    off = big / 2 - period * 3 - sq / 2  # put a square near the centre
    color = (60, 60, 60) if line_dark else (245, 245, 245)
    pos = []
    x = off - period * 6
    while x < big:
        pos.extend([x, x + sq])
        x += period
    for p in pos:
        pi = int(round(p))
        cv2.line(canvas, (pi, 0), (pi, big), color, lw)
        cv2.line(canvas, (0, pi), (big, pi), color, lw)

    # rotate canvas and crop to output size
    c = (big / 2, big / 2)
    m = cv2.getRotationMatrix2D(c, -angle_deg, 1.0)
    canvas = cv2.warpAffine(canvas, m, (big, big), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REFLECT)
    ox, oy = (big - width) // 2, (big - height) // 2
    img = canvas[oy:oy + height, ox:ox + width].copy()

    # cells
    r0 = cell_um * 1e-3 * px_per_mm / 2
    cells = []
    tries = 0
    while len(cells) < n_cells and tries < n_cells * 50:
        tries += 1
        r = r0 * rng.uniform(0.85, 1.15)
        cx, cy = rng.uniform(r, width - r), rng.uniform(r, height - r)
        if any((cx - x2) ** 2 + (cy - y2) ** 2 < (1.15 * (r + r2)) ** 2 for x2, y2, r2, _ in cells):
            continue
        dead = rng.random() < dead_fraction
        cells.append((cx, cy, r, dead))
    yy, xx = np.mgrid[0:height, 0:width]
    for cx, cy, r, dead in cells:
        x0, x1 = int(max(0, cx - r - 3)), int(min(width, cx + r + 4))
        y0, y1 = int(max(0, cy - r - 3)), int(min(height, cy + r + 4))
        dd = np.sqrt((xx[y0:y1, x0:x1] - cx) ** 2 + (yy[y0:y1, x0:x1] - cy) ** 2)
        patch = img[y0:y1, x0:x1]
        rim = np.exp(-((dd - r) ** 2) / (2 * (0.12 * r + 0.8) ** 2))
        inside = dd < r
        if dead:
            patch[inside] = patch[inside] * 0.35 + np.array([150, 70, 40]) * 0.65
            patch -= rim[..., None] * 60
        else:
            patch[inside] += 22
            patch -= rim[..., None] * 95
    img += rng.normal(0, 4, img.shape)
    # gentle vignetting
    vy, vx = (yy - height / 2) / height, (xx - width / 2) / width
    img *= (1 - 0.25 * (vx ** 2 + vy ** 2))[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (0, 0), 0.8)

    # grid-frame origin of the square used as reference (only for tests)
    truth = SyntheticTruth(cells=cells, angle_deg=angle_deg, px_per_mm=px_per_mm,
                           square_origin=(off - ox, off - oy))
    return img, truth
