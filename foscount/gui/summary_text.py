from __future__ import annotations

import html

from ..core.concentration import Summary, format_conc
from ..core.models import Mode


def _sci(v: float | None) -> str:
    s = format_conc(v)
    if "^" in s:
        m, e = s.split("^")
        return f"{m}<sup>{e}</sup>"
    return s


def summary_html(title: str, s: Summary, mode: Mode) -> str:
    rows = [f"<span style='color:#2E1D3F; font-weight:600'>{html.escape(title)}</span>",
            f"Squares counted: <b>{s.n_squares}</b>"]
    if mode == Mode.TRYPAN and s.live is not None:
        rows.append(f"Cells: <b>{s.total}</b> (live {s.live}, dead {s.dead})")
    else:
        rows.append(f"Cells: <b>{s.total}</b>")
    rows.append(f"Mean per square: {s.mean_per_square:.2f}"
                + (f" &nbsp; CV {s.cv_percent:.0f} %" if s.cv_percent is not None else ""))
    rows.append(f"Concentration: <b>{_sci(s.concentration_per_ml)} cells/mL</b>")
    if mode == Mode.TRYPAN and s.live_per_ml is not None:
        rows.append(f"Live: <b>{_sci(s.live_per_ml)} cells/mL</b>")
        if s.viability_percent is not None:
            rows.append(f"Viability: <b>{s.viability_percent:.1f} %</b>")
    if s.poisson_rel_error_percent:
        rows.append(f"Counting error (95 %, Poisson): ±{s.poisson_rel_error_percent:.0f} %")
    for w in s.warnings:
        rows.append(f"<span style='color:#B45309'>⚠ {html.escape(w)}</span>")
    return "<br>".join(rows)
