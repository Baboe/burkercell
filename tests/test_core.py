import os

import numpy as np
import pytest

from foscount.core.analysis import ImageAnalysis, write_image
from foscount.core.batch import run_batch
from foscount.core.concentration import summarize
from foscount.core.detection import DetectParams, count_squares, detect_cells
from foscount.core.export import write_rows, make_row
from foscount.core.grid import detect_grid
from foscount.core.models import (Cell, CellState, Chamber, CountResult, Grid, Mode,
                                  Square, SquareCount)
from foscount.core.synthetic import make_burker_image


def test_square_volume():
    assert Chamber().square_volume_ml == pytest.approx(4e-6)


def test_concentration_and_viability():
    per = [SquareCount(total=50, live=40, dead=10), SquareCount(total=50, live=40, dead=10)]
    s = summarize(CountResult(Mode.TRYPAN, per, dilution=2.0, chamber=Chamber()))
    assert s.mean_per_square == 50
    assert s.concentration_per_ml == pytest.approx(50 * 2 * 250_000)
    assert s.live_per_ml == pytest.approx(40 * 2 * 250_000)
    assert s.viability_percent == pytest.approx(80.0)
    assert s.poisson_rel_error_percent == pytest.approx(196 / 10)


def test_counting_rule_top_left_in_bottom_right_out():
    g = Grid(center=(0, 0), squares=[Square(0, 0, 100, 100)])
    cells = [
        Cell(50, 50, 5),    # inside
        Cell(-3, 50, 5),    # touches left line -> counted
        Cell(50, -3, 5),    # touches top line -> counted
        Cell(98, 50, 5),    # touches right line -> not counted
        Cell(50, 98, 5),    # touches bottom line -> not counted
        Cell(-10, 50, 5),   # fully outside
    ]
    counts, assign = count_squares(cells, g)
    assert counts[0].total == 3
    assert assign == [0, 0, 0, -1, -1, -1]


def test_unselected_squares_are_ignored():
    g = Grid(center=(0, 0), squares=[Square(0, 0, 100, 100, selected=False)])
    counts, assign = count_squares([Cell(50, 50, 5)], g)
    assert counts == [] and assign == [-1]


@pytest.mark.parametrize("angle", [0.0, 2.5, -6.0])
def test_grid_detection(angle):
    img, truth = make_burker_image(angle_deg=angle, seed=3)
    g = detect_grid(img)
    assert g is not None and len(g.squares) >= 1
    assert g.angle_deg == pytest.approx(angle, abs=0.2)
    assert g.px_per_mm == pytest.approx(truth.px_per_mm, rel=0.03)


def _match(cells, truth):
    used, tp, cls_ok = set(), 0, 0
    for c in cells:
        for i, (x, y, r, dead) in enumerate(truth):
            if i not in used and (c.x - x) ** 2 + (c.y - y) ** 2 < (0.6 * r) ** 2:
                used.add(i)
                tp += 1
                cls_ok += (c.state == CellState.DEAD) == dead
                break
    return tp, cls_ok


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_cell_detection_unstained(seed):
    img, truth = make_burker_image(angle_deg=1.5, seed=seed, n_cells=150)
    cells = detect_cells(img, DetectParams(), detect_grid(img))
    tp, _ = _match(cells, truth.cells)
    assert tp / len(truth.cells) >= 0.93          # recall
    assert tp / len(cells) >= 0.93                # precision


def test_trypan_classification():
    img, truth = make_burker_image(angle_deg=-2, seed=4, n_cells=150, dead_fraction=0.4)
    cells = detect_cells(img, DetectParams(mode=Mode.TRYPAN), detect_grid(img))
    tp, cls_ok = _match(cells, truth.cells)
    assert tp / len(truth.cells) >= 0.93
    assert cls_ok / tp >= 0.95


def test_no_grid_returns_none():
    img = np.full((400, 400, 3), 200, np.uint8)
    assert detect_grid(img) is None


def test_export_and_batch(tmp_path):
    folder = tmp_path / "imgs" / "sampleA"
    folder.mkdir(parents=True)
    for s in (1, 2):
        img, _ = make_burker_image(seed=s, n_cells=80)
        write_image(str(folder / f"img{s}.png"), img)
    rows, out = run_batch(str(tmp_path / "imgs"), str(tmp_path / "out"), DetectParams(),
                          Chamber(), 1.0, fmt="csv")
    assert os.path.exists(out)
    assert [r["image"] for r in rows][-1] == "ALL"
    assert rows[-1]["squares"] == rows[0]["squares"] + rows[1]["squares"]
    assert len(os.listdir(tmp_path / "out" / "annotated")) == 2
    x = tmp_path / "r.xlsx"
    write_rows(rows, str(x))
    from openpyxl import load_workbook
    ws = load_workbook(x).active
    assert ws.cell(1, 1).value == "sample" and ws.max_row == len(rows) + 1


def test_image_analysis_roundtrip(tmp_path):
    img, _ = make_burker_image(seed=7, n_cells=60)
    p = tmp_path / "näme.png"  # non-ASCII path
    write_image(str(p), img)
    a = ImageAnalysis.load(str(p))
    a.run(DetectParams(), Chamber())
    assert a.grid_found
    assert a.annotated(Mode.UNSTAINED).shape == img.shape


def test_round_field_of_view_eyepiece_photo():
    """Photos through the eyepiece: round bright field, black corners."""
    import cv2
    img, truth = make_burker_image(angle_deg=-3, seed=2, n_cells=150, dead_fraction=0.4)
    h, w = img.shape[:2]
    m = np.zeros((h, w), np.uint8)
    cv2.circle(m, (w // 2, h // 2), int(0.47 * h), 1, -1)
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 6)
    img = (img * m[..., None]).astype(np.uint8)
    g = detect_grid(img)
    assert g is not None and g.squares
    assert g.angle_deg == pytest.approx(-3, abs=0.2)
    inside = [c for c in truth.cells
              if (c[0] - w / 2) ** 2 + (c[1] - h / 2) ** 2 < (0.47 * h - 25) ** 2]
    cells = detect_cells(img, DetectParams(mode=Mode.TRYPAN), g)
    tp, cls_ok = _match(cells, inside)
    assert tp / len(inside) >= 0.9
    assert cls_ok / tp >= 0.95


def test_tiny_line_bundle_is_not_a_square():
    """A triple line (lines a few px apart) must not be taken for a square."""
    img, _ = make_burker_image(seed=4, n_cells=40)
    g = detect_grid(img)
    side = min(q.x1 - q.x0 for q in g.squares)
    assert side > 0.08 * min(img.shape[:2])
