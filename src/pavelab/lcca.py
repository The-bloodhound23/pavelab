"""Life-cycle cost analysis: treatments, trigger strategies, NPV and EUAC.

A strategy is a list of trigger rules. Each simulated year the section's PCI
is forecast with any ``DeteriorationModel``; when it falls to or below a rule's
trigger (and the treatment is applicable), the treatment is applied, its cost
is booked, and the PCI is reset. The curve is then re-anchored through the new
PCI's effective age.

Costs are agency costs in constant dollars. User costs and salvage value are
not included in v0.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .deterioration import DeteriorationModel


@dataclass(frozen=True)
class Treatment:
    name: str
    unit_cost: float  # $ per m2
    pci_after: float | None = None  # PCI immediately after treatment (reset value)
    pci_gain: float | None = None  # alternative: add this many points (capped at 100)
    min_pci: float = 0.0  # applicable only when PCI >= min_pci
    max_pci: float = 100.0  # ... and PCI <= max_pci
    ghg_kgco2e_per_m2: float | None = None  # optional, reported but not used in NPV
    min_interval_years: int = 0  # minimum years between repeat applications

    def __post_init__(self) -> None:
        if (self.pci_after is None) == (self.pci_gain is None):
            raise ValueError("set exactly one of pci_after or pci_gain")

    def apply(self, pci: float) -> float:
        if self.pci_after is not None:
            return max(pci, self.pci_after)
        return min(100.0, pci + self.pci_gain)

    def applicable(self, pci: float) -> bool:
        return self.min_pci <= pci <= self.max_pci


@dataclass(frozen=True)
class TriggerRule:
    treatment: Treatment
    trigger_pci: float  # apply when PCI <= trigger_pci


@dataclass
class Strategy:
    name: str
    rules: list[TriggerRule] = field(default_factory=list)

    def choose(self, pci: float, year: int = 0, last_applied: dict | None = None) -> Treatment | None:
        """First rule (in listed order) whose trigger is met, whose treatment
        applies at this PCI, and whose minimum repeat interval has passed."""
        last_applied = last_applied or {}
        for rule in self.rules:
            t = rule.treatment
            if pci > rule.trigger_pci or not t.applicable(pci):
                continue
            last = last_applied.get(t.name)
            if last is not None and year - last < t.min_interval_years:
                continue
            return t
        return None


@dataclass
class SimulationResult:
    strategy: str
    years: np.ndarray
    pci: np.ndarray
    costs: np.ndarray
    actions: list[tuple[int, str]]
    npv: float
    euac: float
    ghg_kgco2e: float | None
    area_m2: float

    @property
    def average_pci(self) -> float:
        return float(np.mean(self.pci))

    @property
    def area_under_curve(self) -> float:
        """Sum of yearly PCI, a simple condition-benefit measure."""
        return float(np.sum(self.pci))

    def summary(self) -> dict:
        return {
            "strategy": self.strategy,
            "npv": round(self.npv, 2),
            "euac": round(self.euac, 2),
            "average_pci": round(self.average_pci, 1),
            "min_pci": round(float(self.pci.min()), 1),
            "n_treatments": len(self.actions),
            "actions": self.actions,
        }


def npv(cashflows, rate: float) -> float:
    """Net present value of cashflows at years 0, 1, 2, ..."""
    cf = np.asarray(cashflows, dtype=float)
    t = np.arange(len(cf))
    return float(np.sum(cf / (1.0 + rate) ** t))


def euac(present_value: float, rate: float, years: int) -> float:
    """Equivalent uniform annual cost over ``years`` (capital recovery factor)."""
    if years <= 0:
        raise ValueError("years must be positive")
    if rate == 0:
        return present_value / years
    crf = rate * (1 + rate) ** years / ((1 + rate) ** years - 1)
    return present_value * crf


def simulate(
    model: DeteriorationModel,
    strategy: Strategy,
    current_pci: float,
    area_m2: float,
    horizon: int = 20,
    discount_rate: float = 0.03,
) -> SimulationResult:
    """Simulate a strategy year by year over ``horizon`` years.

    Year 0 is the current condition; a treatment can be applied in year 0.
    """
    pci_track = np.zeros(horizon + 1)
    costs = np.zeros(horizon + 1)
    actions: list[tuple[int, str]] = []
    ghg = 0.0
    has_ghg = False

    last_applied: dict[str, int] = {}
    pci = float(current_pci)
    for year in range(horizon + 1):
        if year > 0:
            pci = float(model.forecast(pci, 1.0))
        treatment = strategy.choose(pci, year, last_applied)
        if treatment is not None:
            last_applied[treatment.name] = year
            costs[year] += treatment.unit_cost * area_m2
            actions.append((year, treatment.name))
            if treatment.ghg_kgco2e_per_m2 is not None:
                ghg += treatment.ghg_kgco2e_per_m2 * area_m2
                has_ghg = True
            pci = treatment.apply(pci)
        pci_track[year] = pci

    pv = npv(costs, discount_rate)
    return SimulationResult(
        strategy=strategy.name,
        years=np.arange(horizon + 1),
        pci=pci_track,
        costs=costs,
        actions=actions,
        npv=pv,
        euac=euac(pv, discount_rate, horizon),
        ghg_kgco2e=ghg if has_ghg else None,
        area_m2=area_m2,
    )


def compare_strategies(model, strategies, current_pci, area_m2, horizon=20, discount_rate=0.03):
    """Simulate several strategies and return results sorted by NPV (lowest first)."""
    results = [simulate(model, s, current_pci, area_m2, horizon, discount_rate) for s in strategies]
    return sorted(results, key=lambda r: r.npv)
