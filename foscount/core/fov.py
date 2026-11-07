"""Field-of-view handling for photos taken through the eyepiece.

Phone or camera photos taken through the eyepiece show a round, bright field
of view surrounded by black. The black part must be ignored: it would distort
the background estimate, the noise threshold and the grid search.
"""

from __future__ import annotations

import cv2
import numpy as np


def field_of_view(gray: np.ndarray) -> np.ndarray | None:
    """Boolean mask of the illuminated field, or ``None`` if (almost) the
    whole image is illuminated."""
    g = gray.astype(np.float32)
    small_f = min(1.0, 400.0 / max(g.shape))
    small = cv2.resize(g, None, fx=small_f, fy=small_f, interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 2)
    bright = float(np.percentile(small, 75))
    dark = small < 0.35 * bright
    # only dark regions touching the image border count as "outside"
    n, lab = cv2.connectedComponents(dark.astype(np.uint8))
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    outside = np.isin(lab, list(border)) & dark
    if outside.mean() < 0.03:
        return None
    inside = ~outside
    # stay clear of the blurry rim of the field
    k = max(3, int(round(0.015 * max(small.shape))) | 1)
    inside = cv2.erode(inside.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    mask = cv2.resize(inside, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    return mask


def fill_outside(gray: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Replace everything outside the field of view by the median inside."""
    if mask is None:
        return gray
    out = gray.astype(np.float32).copy()
    out[~mask] = float(np.median(out[mask]))
    return out
