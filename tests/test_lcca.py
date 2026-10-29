import numpy as np
import pytest

from pavelab import (
    ExponentialModel,
    Strategy,
    Treatment,
    TriggerRule,
    compare_strategies,
    euac,
    npv,
    simulate,
)

MODEL = ExponentialModel(100, 0.06)
OVERLAY = Treatment("Thin overlay", unit_cost=20.0, pci_after=92, min_pci=40)
RECON = Treatment("Reconstruction", unit_cost=120.0, pci_after=100)
SEAL = Treatment("Crack seal", unit_cost=2.0, pci_gain=5, min_pci=65, max_pci=85)


def test_npv_basic():
    assert npv([100], 0.05) == pytest.approx(100)
    assert npv([0, 105], 0.05) == pytest.approx(100)


def test_euac_matches_annuity():
    pv = 1000.0
    a = euac(pv, 0.04, 10)
    assert npv([0] + [a] * 10, 0.04) == pytest.approx(pv)
    assert euac(1000, 0.0, 10) == pytest.approx(100)


def test_do_nothing_costs_nothing_and_declines():
    r = simulate(MODEL, Strategy("Do nothing"), 80, area_m2=1000, horizon=10)
    assert r.npv == 0
    assert r.actions == []
    assert np.all(np.diff(r.pci) < 0)


def test_trigger_fires_and_resets():
    s = Strategy("Overlay at 60", [TriggerRule(OVERLAY, 60)])
    r = simulate(MODEL, s, 70, area_m2=1000, horizon=20)
    assert r.actions, "overlay should be triggered"
    year = r.actions[0][0]
    assert r.pci[year] == pytest.approx(92)
    assert r.costs[year] == pytest.approx(20_000)
    assert r.npv == pytest.approx(npv(r.costs, 0.03))


def test_applicability_window():
    assert not OVERLAY.applicable(30)
    s = Strategy("Overlay only", [TriggerRule(OVERLAY, 60)])
    r = simulate(MODEL, s, 30, area_m2=100, horizon=3)
    assert r.actions == []  # too far gone for an overlay


def test_rule_order_and_gain():
    s = Strategy("Seal then overlay", [TriggerRule(SEAL, 80), TriggerRule(OVERLAY, 60)])
    r = simulate(MODEL, s, 79, area_m2=100, horizon=1)
    assert r.actions[0] == (0, "Crack seal")
    assert r.pci[0] == pytest.approx(84)


def test_treatment_requires_one_reset_mode():
    with pytest.raises(ValueError):
        Treatment("bad", 1.0)
    with pytest.raises(ValueError):
        Treatment("bad", 1.0, pci_after=90, pci_gain=5)


def test_compare_sorted_by_npv():
    strategies = [
        Strategy("Reactive recon", [TriggerRule(RECON, 30)]),
        Strategy("Do nothing"),
        Strategy("Overlay at 60", [TriggerRule(OVERLAY, 60)]),
    ]
    res = compare_strategies(MODEL, strategies, 75, 7000, horizon=20)
    npvs = [r.npv for r in res]
    assert npvs == sorted(npvs)
    assert res[0].strategy == "Do nothing"


def test_ghg_reported_when_given():
    t = Treatment("Overlay", 20.0, pci_after=92, ghg_kgco2e_per_m2=8.0)
    r = simulate(MODEL, Strategy("x", [TriggerRule(t, 70)]), 65, area_m2=100, horizon=1)
    assert r.ghg_kgco2e == pytest.approx(800)


def test_min_interval_prevents_repeat():
    seal = Treatment("Seal", 1.0, pci_gain=3, max_pci=90, min_interval_years=4)
    r = simulate(MODEL, Strategy("seal", [TriggerRule(seal, 85)]), 84, area_m2=10, horizon=8)
    years = [y for y, _ in r.actions]
    assert all(b - a >= 4 for a, b in zip(years, years[1:]))
    assert years[0] == 0
