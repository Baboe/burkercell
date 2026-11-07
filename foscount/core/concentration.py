"""Concentration, viability and counting-error calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import CountResult, Mode


@dataclass
class Summary:
    n_squares: int
    total: int
    live: int | None
    dead: int | None
    mean_per_square: float
    cv_percent: float | None
    concentration_per_ml: float  # all cells
    live_per_ml: float | None
    viability_percent: float | None
    # Poisson counting error (95 % interval as relative +/- percent)
    poisson_rel_error_percent: float | None
    warnings: list[str]


def summarize(result: CountResult) -> Summary:
    n = result.n_squares
    warnings: list[str] = []
    if n == 0:
        return Summary(0, 0, None, None, 0.0, None, 0.0, None, None, None,
                       ["No squares counted."])

    totals = [s.total for s in result.per_square]
    total = sum(totals)
    mean = total / n
    cv = None
    if n > 1 and mean > 0:
        var = sum((t - mean) ** 2 for t in totals) / (n - 1)
        cv = 100.0 * math.sqrt(var) / mean

    factor = result.dilution / result.chamber.square_volume_ml
    conc = mean * factor

    live = dead = None
    live_conc = viability = None
    if result.mode == Mode.TRYPAN:
        live = result.live
        dead = result.dead
        live_conc = (live / n) * factor
        viability = 100.0 * live / total if total else None

    rel_err = 100.0 * 1.96 / math.sqrt(total) if total > 0 else None

    if total < 100:
        warnings.append(
            f"Only {total} cells counted; the Poisson error is large "
            "(count at least 100-200 cells for ~10-20 % precision).")
    if mean > 100:
        warnings.append(
            f"{mean:.0f} cells per square on average; consider diluting further "
            "to avoid overlapping cells.")
    if cv is not None and n >= 3 and cv > 2 * (100.0 / math.sqrt(mean) if mean else 0) + 10:
        warnings.append(
            f"High variation between squares (CV {cv:.0f} %); the sample may be "
            "unevenly distributed or the chamber was not filled correctly.")
    if result.dilution < 1:
        warnings.append("Dilution factor below 1 looks wrong (1 = undiluted).")

    return Summary(n, total, live, dead, mean, cv, conc, live_conc, viability,
                   rel_err, warnings)


def format_conc(value: float | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(value))))
    mant = value / 10 ** exp
    return f"{mant:.2f} × 10^{exp}"
