import math

import pytest

from pavelab import CurveSet, Distress, allowable_deducts, compute_pci, pci_rating
from pavelab.pci import corrected_deduct


@pytest.fixture(scope="module")
def curves():
    return CurveSet.example()


def test_example_curves_are_labelled_illustrative(curves):
    assert "ILLUSTRATIVE" in curves.disclaimer


def test_no_distress_gives_pci_100(curves):
    r = compute_pci([], sample_area=230, curves=curves)
    assert r.pci == 100
    assert r.rating == "Good"


def test_m_value_formula():
    assert allowable_deducts(50) == pytest.approx(1 + 9 / 98 * 50)
    assert allowable_deducts(0) == 10  # capped
    assert allowable_deducts(100) == 1


def test_single_deduct_uses_total(curves):
    r = compute_pci([Distress("alligator_cracking", "M", 23)], 230, curves)
    dv = curves.deduct_value("alligator_cracking", "M", 10.0)
    assert r.pci == pytest.approx(100 - dv)
    assert r.m_value is None


def test_deduct_interpolates_in_log_density(curves):
    # 5 and 10 are adjacent curve points; their geometric mean is the log midpoint
    lo = curves.deduct_value("alligator_cracking", "M", 5)
    hi = curves.deduct_value("alligator_cracking", "M", 10)
    mid = curves.deduct_value("alligator_cracking", "M", math.sqrt(50))
    assert mid == pytest.approx((lo + hi) / 2)


def test_more_distress_lowers_pci(curves):
    base = [Distress("alligator_cracking", "L", 10)]
    worse = base + [Distress("potholes", "H", 2), Distress("rutting", "M", 30)]
    assert compute_pci(worse, 230, curves).pci < compute_pci(base, 230, curves).pci


def test_higher_severity_lowers_pci(curves):
    for sev_lo, sev_hi in [("L", "M"), ("M", "H")]:
        a = compute_pci([Distress("block_cracking", sev_lo, 40)], 230, curves).pci
        b = compute_pci([Distress("block_cracking", sev_hi, 40)], 230, curves).pci
        assert b < a


def test_same_type_and_severity_are_summed(curves):
    a = compute_pci([Distress("patching", "M", 5), Distress("patching", "M", 5)], 230, curves)
    b = compute_pci([Distress("patching", "M", 10)], 230, curves)
    assert a.pci == pytest.approx(b.pci)


def test_cdv_iteration_hand_check(curves):
    # deducts 40, 30, 10, 1 -> HDV 40, m = 1 + 9/98*60 = 6.51, all four kept
    max_cdv, m, log = corrected_deduct([40, 30, 10, 1], curves)
    assert m == pytest.approx(1 + 9 / 98 * 60)
    assert [e["q"] for e in log] == [3, 2, 1]
    assert log[0]["total"] == pytest.approx(81)
    assert log[1]["total"] == pytest.approx(40 + 30 + 2 + 1)
    assert log[2]["total"] == pytest.approx(40 + 2 + 2 + 1)
    assert log[2]["cdv"] == pytest.approx(45)  # q = 1: CDV = total
    assert max_cdv == pytest.approx(max(e["cdv"] for e in log))


def test_m_value_truncates_with_fraction(curves):
    # HDV 90 -> m = 1 + 9/98*10 = 1.918: keep 90 and 0.918 * 50
    _, m, log = corrected_deduct([90, 50, 40], curves)
    assert m == pytest.approx(1.9183673)
    assert log[0]["deducts"][1] == pytest.approx(50 * (m - 1))
    assert len(log[0]["deducts"]) == 2


def test_pci_bounded(curves):
    heavy = [Distress(t, "H", 230) for t in curves.distress_types()]
    r = compute_pci(heavy, 230, curves)
    assert 0 <= r.pci <= 100


def test_invalid_inputs(curves):
    with pytest.raises(ValueError):
        Distress("potholes", "X", 1)
    with pytest.raises(ValueError):
        compute_pci([], 0, curves)
    with pytest.raises(KeyError):
        curves.deduct_value("unknown", "L", 5)


def test_rating_bands():
    assert pci_rating(90) == "Good"
    assert pci_rating(60) == "Fair"
    assert pci_rating(5) == "Failed"
