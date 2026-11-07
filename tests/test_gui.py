import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import Qt  # noqa: E402

from foscount.core.analysis import write_image  # noqa: E402
from foscount.core.synthetic import make_burker_image  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_main_window_flow(app, tmp_path):
    from foscount.gui.main_window import MainWindow
    img, _ = make_burker_image(seed=2, n_cells=80, dead_fraction=0.3)
    p = str(tmp_path / "a.png")
    write_image(p, img)
    w = MainWindow()
    w.add_images([p])
    a = w.cur
    assert a is not None and a.grid_found
    n = len(a.cells)
    w._on_click(20, 20, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    assert len(a.cells) == n + 1 and a.cells[-1].manual
    w._on_click(20, 20, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    assert len(a.cells) == n
    w.mode.setCurrentIndex(1)  # trypan
    assert any(c.state.value == "dead" for c in a.cells)
    rows = w._rows()
    assert rows[0]["squares"] >= 1
    m = w.manual
    for _ in range(3):
        m._tally(0)
    m._tally(1)
    assert m.summary().total == 4 and m.summary().dead == 1
    w.close()
