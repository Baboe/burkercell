"""CSV / Excel export of counting results."""

from __future__ import annotations

import csv
import os
from datetime import datetime

from .concentration import Summary
from .models import Chamber, Mode, SquareCount


COLUMNS = [
    "sample", "image", "date", "mode", "dilution", "squares", "per_square_counts",
    "total_cells", "live_cells", "dead_cells", "mean_per_square", "cv_percent",
    "cells_per_ml", "live_cells_per_ml", "viability_percent",
    "poisson_95ci_percent", "chamber_square_mm", "chamber_depth_mm", "source", "warnings",
]


def make_row(sample: str, image: str, mode: Mode, dilution: float, chamber: Chamber,
             per_square: list[SquareCount], s: Summary, source: str) -> dict:
    if mode == Mode.TRYPAN:
        sq = "; ".join(f"{c.live}/{c.dead}" for c in per_square)
    else:
        sq = "; ".join(str(c.total) for c in per_square)
    return {
        "sample": sample,
        "image": image,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": "trypan blue (live/dead)" if mode == Mode.TRYPAN else "unstained",
        "dilution": dilution,
        "squares": s.n_squares,
        "per_square_counts": sq,
        "total_cells": s.total,
        "live_cells": s.live if s.live is not None else "",
        "dead_cells": s.dead if s.dead is not None else "",
        "mean_per_square": round(s.mean_per_square, 3),
        "cv_percent": round(s.cv_percent, 1) if s.cv_percent is not None else "",
        "cells_per_ml": round(s.concentration_per_ml),
        "live_cells_per_ml": round(s.live_per_ml) if s.live_per_ml is not None else "",
        "viability_percent": round(s.viability_percent, 1) if s.viability_percent is not None else "",
        "poisson_95ci_percent": round(s.poisson_rel_error_percent, 1) if s.poisson_rel_error_percent else "",
        "chamber_square_mm": chamber.square_side_mm,
        "chamber_depth_mm": chamber.depth_mm,
        "source": source,
        "warnings": " | ".join(s.warnings),
    }


def write_rows(rows: list[dict], path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        _write_xlsx(rows, path)
    else:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)


def _write_xlsx(rows: list[dict], path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Counts"
    ws.append(COLUMNS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([r.get(k, "") for k in COLUMNS])
    for col in ("M", "N"):  # concentration columns in scientific notation
        for cell in ws[col][1:]:
            cell.number_format = "0.00E+00"
    for i, k in enumerate(COLUMNS, start=1):
        width = max(len(k), *(len(str(r.get(k, ""))) for r in rows)) if rows else len(k)
        ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, width + 2)
    ws.freeze_panes = "A2"
    wb.save(path)
