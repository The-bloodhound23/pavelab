import numpy as np
import pytest

from pavelab import ExponentialModel, PersistenceForecaster, PowerLawModel, r2_score


def test_exponential_fit_recovers_parameters():
    rng = np.random.default_rng(0)
    age = rng.uniform(0, 25, 300)
    pci = 95 * np.exp(-0.04 * age) + rng.normal(0, 1.0, 300)
    m = ExponentialModel().fit(age, pci)
    assert m.pci0 == pytest.approx(95, abs=1.0)
    assert m.lam == pytest.approx(0.04, abs=0.003)


def test_power_law_fit_recovers_parameters():
    rng = np.random.default_rng(1)
    age = rng.uniform(0, 20, 400)
    pci = 98 - 0.6 * age ** 1.6 + rng.normal(0, 1.0, 400)
    m = PowerLawModel().fit(age, pci)
    assert m.beta == pytest.approx(1.6, abs=0.1)
    assert r2_score(pci, m.predict(age)) > 0.95


@pytest.mark.parametrize("model", [ExponentialModel(95, 0.05), PowerLawModel(98, 0.8, 1.4)])
def test_effective_age_inverts_predict(model):
    for age in [0.5, 3, 8, 15]:
        assert model.effective_age(float(model.predict(age))) == pytest.approx(age, rel=1e-6)


@pytest.mark.parametrize("model", [ExponentialModel(95, 0.05), PowerLawModel(98, 0.8, 1.4)])
def test_anchored_forecast_starts_at_current(model):
    assert float(model.forecast(72.0, 0.0)) == pytest.approx(72.0)
    path = model.forecast(72.0, np.arange(0, 10))
    assert np.all(np.diff(path) <= 0)


def test_years_to_threshold():
    m = ExponentialModel(100, 0.05)
    yrs = m.years_to_threshold(80, 60)
    assert float(m.forecast(80, yrs)) == pytest.approx(60, abs=1e-6)
    assert m.years_to_threshold(50, 60) == 0.0


def test_persistence_baseline():
    assert np.all(PersistenceForecaster().forecast(67.0, [1, 2, 3]) == 67.0)


def test_predict_clipped():
    m = PowerLawModel(100, 5, 2)
    assert m.predict(100) == 0.0
