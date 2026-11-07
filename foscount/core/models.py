"""Data structures shared by the detection, calculation and GUI layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    UNSTAINED = "unstained"
    TRYPAN = "trypan"


class CellState(str, Enum):
    CELL = "cell"  # unstained mode: no live/dead distinction
    LIVE = "live"
    DEAD = "dead"


@dataclass
class Chamber:
    """Bürker chamber geometry.

    A standard Bürker chamber has a depth of 0.1 mm. The counting area is made of
    large squares of 0.2 mm x 0.2 mm (0.04 mm^2) separated by 0.05 mm strips
    (double lines). One large square therefore holds 0.004 mm^3 = 4e-6 mL.
    """

    square_side_mm: float = 0.2
    strip_mm: float = 0.05
    depth_mm: float = 0.1

    @property
    def square_area_mm2(self) -> float:
        return self.square_side_mm ** 2

    @property
    def square_volume_ml(self) -> float:
        # 1 mm^3 = 1 µL = 1e-3 mL
        return self.square_area_mm2 * self.depth_mm * 1e-3


@dataclass
class Cell:
    x: float
    y: float
    radius: float
    state: CellState = CellState.CELL
    manual: bool = False  # added or reclassified by the user
    stain_score: float = 0.0  # trypan: higher = more blue/dark (dead)


@dataclass
class Square:
    """A large counting square in grid-frame pixel coordinates.

    x0/y0 are the top/left boundary lines, x1/y1 the bottom/right ones, in the
    deskewed frame of the parent :class:`Grid` (see ``core.grid``).
    """

    x0: float
    y0: float
    x1: float
    y1: float
    row: int = 0
    col: int = 0
    selected: bool = True


@dataclass
class Grid:
    angle_deg: float = 0.0  # rotation of the grid relative to the image axes
    center: tuple[float, float] = (0.0, 0.0)  # rotation centre (image centre)
    squares: list[Square] = field(default_factory=list)
    px_per_mm: float | None = None
    v_lines: list[float] = field(default_factory=list)  # in rotated frame
    h_lines: list[float] = field(default_factory=list)
    line_width_px: float = 3.0


@dataclass
class SquareCount:
    total: int = 0
    live: int = 0
    dead: int = 0


@dataclass
class CountResult:
    """Counts per square plus derived concentrations."""

    mode: Mode
    per_square: list[SquareCount]
    dilution: float
    chamber: Chamber

    @property
    def n_squares(self) -> int:
        return len(self.per_square)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.per_square)

    @property
    def live(self) -> int:
        return sum(s.live for s in self.per_square)

    @property
    def dead(self) -> int:
        return sum(s.dead for s in self.per_square)
