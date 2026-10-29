"""Non-linear pavement deterioration models.

* ``ExponentialModel``: PCI(t) = PCI0 * exp(-lambda * t)
* ``PowerLawModel``:   PCI(t) = PCI0 - alpha * t ** beta
* ``PersistenceForecaster``: carry-forward baseline (next PCI = current PCI)

Models can be fitted to a population (many sections, age vs PCI) and then
*anchored* to one section's current condition through its effective age:
the age at which the population curve reaches the observed PCI.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

import numpy as np
from scipy.optimize import curve_fit


class DeteriorationModel(ABC):
    """Monotonically decreasing PCI-vs-age curve."""

    @abstractmethod
    def predict(self, age) -> np.ndarray:
        """Population PCI at the given age(s), clipped to [0, 100]."""

    @abstractmethod
    def effective_age(self, pci: float) -> float:
        """Age at which the curve reaches ``pci`` (inverse of predict)."""

    @abstractmethod
    def fit(self, age, pci) -> "DeteriorationModel":
        """Fit parameters to observed (age, PCI) pairs; returns self."""

    def forecast(self, current_pci: float, years) -> np.ndarray:
        """Anchored forecast: PCI ``years`` from now, starting at ``current_pci``."""
        t0 = self.effective_age(current_pci)
        return self.predict(t0 + np.asarray(years, dtype=float))

    def years_to_threshold(self, current_pci: float, threshold: float) -> float:
        """Years until the anchored curve drops to ``threshold`` (0 if already below)."""
        if current_pci <= threshold:
            return 0.0
        return max(0.0, self.effective_age(threshold) - self.effective_age(current_pci))


class ExponentialModel(DeteriorationModel):
    def __init__(self, pci0: float = 100.0, lam: float = 0.05):
        self.pci0 = float(pci0)
        self.lam = float(lam)

    def predict(self, age):
        a = np.maximum(np.asarray(age, dtype=float), 0.0)
        return np.clip(self.pci0 * np.exp(-self.lam * a), 0.0, 100.0)

    def effective_age(self, pci: float) -> float:
        pci = min(max(float(pci), 1e-6), self.pci0)
        return math.log(self.pci0 / pci) / self.lam

    def fit(self, age, pci, fix_pci0: bool = False):
        age = np.asarray(age, dtype=float)
        pci = np.asarray(pci, dtype=float)
        if fix_pci0:
            f = lambda t, lam: self.pci0 * np.exp(-lam * t)  # noqa: E731
            (self.lam,), _ = curve_fit(f, age, pci, p0=[self.lam], bounds=([1e-6], [5.0]))
        else:
            f = lambda t, p0, lam: p0 * np.exp(-lam * t)  # noqa: E731
            (self.pci0, self.lam), _ = curve_fit(
                f, age, pci, p0=[self.pci0, self.lam], bounds=([1.0, 1e-6], [100.0, 5.0])
            )
        return self

    def __repr__(self) -> str:
        return f"ExponentialModel(pci0={self.pci0:.2f}, lam={self.lam:.4f})"


class PowerLawModel(DeteriorationModel):
    def __init__(self, pci0: float = 100.0, alpha: float = 1.0, beta: float = 1.5):
        self.pci0 = float(pci0)
        self.alpha = float(alpha)
        self.beta = float(beta)

    def predict(self, age):
        a = np.maximum(np.asarray(age, dtype=float), 0.0)
        return np.clip(self.pci0 - self.alpha * a ** self.beta, 0.0, 100.0)

    def effective_age(self, pci: float) -> float:
        drop = max(self.pci0 - float(pci), 0.0)
        return (drop / self.alpha) ** (1.0 / self.beta)

    def fit(self, age, pci, fix_pci0: bool = False):
        age = np.asarray(age, dtype=float)
        pci = np.asarray(pci, dtype=float)
        if fix_pci0:
            f = lambda t, a, b: self.pci0 - a * t ** b  # noqa: E731
            (self.alpha, self.beta), _ = curve_fit(
                f, age, pci, p0=[self.alpha, self.beta], bounds=([1e-6, 0.3], [50.0, 4.0])
            )
        else:
            f = lambda t, p0, a, b: p0 - a * t ** b  # noqa: E731
            (self.pci0, self.alpha, self.beta), _ = curve_fit(
                f, age, pci, p0=[self.pci0, self.alpha, self.beta],
                bounds=([1.0, 1e-6, 0.3], [100.0, 50.0, 4.0]),
            )
        return self

    def __repr__(self) -> str:
        return f"PowerLawModel(pci0={self.pci0:.2f}, alpha={self.alpha:.4f}, beta={self.beta:.3f})"


class PersistenceForecaster:
    """Carry-forward baseline: the forecast equals the current value.

    Every forecasting model should be compared against this.
    """

    def forecast(self, current_pci: float, years) -> np.ndarray:
        return np.full(np.shape(years), float(current_pci))


def r2_score(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
