"""Batch processing of a folder of images."""

from __future__ import annotations

import os
from typing import Callable

from .analysis import ImageAnalysis, write_image
from .concentration import summarize
from .detection import DetectParams
from .export import make_row, write_rows
from .models import Chamber, CountResult, SquareCount

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def find_images(folder: str, recursive: bool) -> list[str]:
    out = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            out += [os.path.join(root, f) for f in files
                    if os.path.splitext(f)[1].lower() in IMAGE_EXT]
    else:
        out = [os.path.join(folder, f) for f in os.listdir(folder)
               if os.path.splitext(f)[1].lower() in IMAGE_EXT]
    return sorted(out)


def run_batch(folder: str, out_dir: str, params: DetectParams, chamber: Chamber,
              dilution: float, *, recursive: bool = True, save_annotated: bool = True,
              fmt: str = "xlsx",
              progress: Callable[[int, int, str], bool] | None = None) -> tuple[list[dict], str]:
    """Analyse every image in ``folder``.

    Each folder containing images is treated as one sample: besides a row per
    image, a pooled row ("ALL") combines the squares of all its images.
    ``progress(i, n, name)`` may return False to cancel.
    Returns (rows, path of the results file).
    """
    images = find_images(folder, recursive)
    os.makedirs(out_dir, exist_ok=True)
    rows: list[dict] = []
    pooled: dict[str, list[SquareCount]] = {}
    for i, path in enumerate(images):
        rel = os.path.relpath(path, folder)
        sample = os.path.dirname(rel) or os.path.basename(os.path.normpath(folder))
        if progress and progress(i, len(images), rel) is False:
            break
        try:
            a = ImageAnalysis.load(path)
            a.run(params, chamber)
            counts, _ = a.counts()
            s = summarize(CountResult(params.mode, counts, dilution, chamber))
            if not a.grid_found:
                s.warnings.insert(0, "Counting grid not found; image not counted.")
            rows.append(make_row(sample, rel, params.mode, dilution, chamber, counts, s, "auto"))
            pooled.setdefault(sample, []).extend(counts)
            if save_annotated:
                base = os.path.splitext(rel.replace(os.sep, "__"))[0]
                ann_dir = os.path.join(out_dir, "annotated")
                os.makedirs(ann_dir, exist_ok=True)
                write_image(os.path.join(ann_dir, base + "_annotated.png"), a.annotated(params.mode))
        except Exception as e:  # keep going with the other images
            rows.append({"sample": sample, "image": rel, "warnings": f"ERROR: {e}"})
    for sample, counts in pooled.items():
        s = summarize(CountResult(params.mode, counts, dilution, chamber))
        rows.append(make_row(sample, "ALL", params.mode, dilution, chamber, counts, s, "auto (pooled)"))
    if progress:
        progress(len(images), len(images), "done")
    out = os.path.join(out_dir, f"foscount_results.{fmt}")
    write_rows(rows, out)
    return rows, out

