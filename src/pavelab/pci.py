"""ASTM D6433-style PCI calculation for asphalt (AC) sample units.

pavelab implements the *procedure* only. Deduct-value and corrected-deduct
curves are loaded from a JSON file supplied by the user. The bundled
``example_curves.json`` is ILLUSTRATIVE ONLY: its values are made up and are
not the ASTM D6433 curves. Do not use it for real condition ratings.

Procedure summary (paraphrased):
1. density = quantity / sample-unit area x 100 for each distress type and severity
2. deduct value (DV) is read from that distress/severity curve
3. if no more than one DV exceeds 2, CDV = sum of DVs
4. otherwise keep only the m highest DVs, where m = 1 + (9/98)(100 - HDV) <= 10
   (the m-th DV is multiplied by the fractional part of m), then iterate:
   q = number of DVs > 2, CDV = f_q(total deduct), set the smallest DV > 2 to 2,
   repeat until q = 1. The maximum CDV is used.
5. PCI = 100 - max CDV
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable

import numpy as np

SEVERITIES = ("L", "M", "H")


@dataclass(frozen=True)
class Distress:
    """One observed distress in a sample unit."""

    type: str
    severity: str
    quantity: float  # in the curve's unit (m2, m, or count)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")


@dataclass
class PCIResult:
    pci: float
    max_cdv: float
    deduct_values: dict[str, float]
    m_value: float | None
    iterations: list[dict] = field(default_factory=list)

    @property
    def rating(self) -> str:
        return pci_rating(self.pci)


def pci_rating(pci: float) -> str:
    """Conventional seven-band PCI rating label."""
    bands = [(85, "Good"), (70, "Satisfactory"), (55, "Fair"), (40, "Poor"),
             (25, "Very Poor"), (10, "Serious")]
    for lower, label in bands:
        if pci > lower:
            return label
    return "Failed"


class CurveSet:
    """Deduct-value and CDV curves loaded from JSON.

    JSON format::

        {
          "name": "...",
          "deduct_curves": {
            "<distress_type>": {"unit": "m2", "L": [[density, dv], ...], "M": [...], "H": [...]}
          },
          "cdv_curves": {"1": [[tdv, cdv], ...], "2": [...], ...}
        }

    Deduct curves are interpolated linearly in log10(density); CDV curves
    linearly in total deduct value.
    """

    def __init__(self, data: dict):
        self.name: str = data.get("name", "unnamed")
        self.disclaimer: str | None = data.get("disclaimer")
        self.deduct_curves: dict = data["deduct_curves"]
        self.cdv_curves: dict[int, np.ndarray] = {
            int(q): np.asarray(pts, dtype=float) for q, pts in data["cdv_curves"].items()
        }
        self._validate()

    @classmethod
    def from_json(cls, path: str | Path) -> "CurveSet":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    @classmethod
    def example(cls) -> "CurveSet":
        """Bundled ILLUSTRATIVE curves (made-up values, not ASTM)."""
        text = resources.files("pavelab.data").joinpath("example_curves.json").read_text("utf-8")
        return cls(json.loads(text))

    def _validate(self) -> None:
        for dtype, curves in self.deduct_curves.items():
            for sev in SEVERITIES:
                if sev not in curves:
                    continue
                pts = np.asarray(curves[sev], dtype=float)
                if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
                    raise ValueError(f"{dtype}/{sev}: need >= 2 [density, dv] points")
                if np.any(np.diff(pts[:, 0]) <= 0) or np.any(pts[:, 0] <= 0):
                    raise ValueError(f"{dtype}/{sev}: densities must be positive and increasing")
        if 1 not in self.cdv_curves:
            # q = 1 means CDV = total deduct by definition
            self.cdv_curves[1] = np.array([[0.0, 0.0], [100.0, 100.0]])

    def distress_types(self) -> list[str]:
        return sorted(self.deduct_curves)

    def deduct_value(self, distress_type: str, severity: str, density: float) -> float:
        if distress_type not in self.deduct_curves:
            raise KeyError(f"no deduct curve for distress type {distress_type!r}")
        curves = self.deduct_curves[distress_type]
        if severity not in curves:
            raise KeyError(f"no {severity!r} curve for {distress_type!r}")
        if density <= 0:
            return 0.0
        pts = np.asarray(curves[severity], dtype=float)
        d_min = pts[0, 0]
        if density < d_min:
            # scale linearly from (0, 0) to the first curve point
            return float(pts[0, 1] * density / d_min)
        x = np.log10(pts[:, 0])
        dv = float(np.interp(math.log10(min(density, pts[-1, 0])), x, pts[:, 1]))
        return max(0.0, min(100.0, dv))

    def cdv(self, total_deduct: float, q: int) -> float:
        q_key = min(q, max(self.cdv_curves))
        if q_key == 1:
            return min(100.0, total_deduct)
        pts = self.cdv_curves[q_key]
        return float(min(100.0, np.interp(total_deduct, pts[:, 0], pts[:, 1])))


def allowable_deducts(hdv: float) -> float:
    """m = 1 + (9/98)(100 - HDV), capped at 10 (asphalt surfaces)."""
    return min(10.0, 1.0 + (9.0 / 98.0) * (100.0 - hdv))


def corrected_deduct(deduct_values: Iterable[float], curves: CurveSet) -> tuple[float, float | None, list[dict]]:
    """Return (max CDV, m, iteration log) for a list of individual deduct values."""
    dvs = sorted((float(v) for v in deduct_values if v > 0), reverse=True)
    if sum(1 for v in dvs if v > 2.0) <= 1:
        total = sum(dvs)
        return min(100.0, total), None, [{"q": 1, "total": total, "cdv": min(100.0, total)}]

    m = allowable_deducts(dvs[0])
    n_full = int(math.floor(m))
    frac = m - n_full
    kept = dvs[:n_full]
    if frac > 0 and len(dvs) > n_full:
        kept.append(dvs[n_full] * frac)

    work = list(kept)
    log: list[dict] = []
    while True:
        q = sum(1 for v in work if v > 2.0)
        total = sum(work)
        c = curves.cdv(total, q)
        log.append({"q": q, "total": total, "cdv": c, "deducts": list(work)})
        if q <= 1:
            break
        # reduce the smallest deduct value greater than 2 to 2.0
        idx = min((i for i, v in enumerate(work) if v > 2.0), key=lambda i: work[i])
        work[idx] = 2.0
    return max(entry["cdv"] for entry in log), m, log


def compute_pci(distresses: Iterable[Distress], sample_area: float, curves: CurveSet) -> PCIResult:
    """Compute PCI for one asphalt sample unit.

    Quantities of the same type and severity are summed before density is
    computed.
    """
    if sample_area <= 0:
        raise ValueError("sample_area must be positive")
    totals: dict[tuple[str, str], float] = {}
    for d in distresses:
        totals[(d.type, d.severity)] = totals.get((d.type, d.severity), 0.0) + d.quantity

    dv_map: dict[str, float] = {}
    for (dtype, sev), qty in totals.items():
        density = qty / sample_area * 100.0
        dv_map[f"{dtype}/{sev}"] = curves.deduct_value(dtype, sev, density)

    max_cdv, m, log = corrected_deduct(dv_map.values(), curves)
    pci = max(0.0, min(100.0, 100.0 - max_cdv))
    return PCIResult(pci=pci, max_cdv=max_cdv, deduct_values=dv_map, m_value=m, iterations=log)
