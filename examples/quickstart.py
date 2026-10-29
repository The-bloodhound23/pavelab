"""pavelab quickstart: PCI -> deterioration forecast -> LCCA.

Uses the bundled ILLUSTRATIVE curves (made-up values, not ASTM D6433) and a
synthetic population, so the numbers are for demonstration only.
"""

import numpy as np

import pavelab as pl

# 1. PCI for one sample unit (230 m2)
curves = pl.CurveSet.example()
distresses = [
    pl.Distress("alligator_cracking", "M", 12.0),             # m2
    pl.Distress("longitudinal_transverse_cracking", "L", 40),  # m
    pl.Distress("potholes", "L", 1),                           # count
]
result = pl.compute_pci(distresses, sample_area=230, curves=curves)
print(f"PCI = {result.pci:.1f} ({result.rating}); deducts = {result.deduct_values}")

# 2. Fit a population deterioration curve (synthetic data here; use LTPP in practice)
rng = np.random.default_rng(42)
age = rng.uniform(0, 25, 500)
pci_obs = np.clip(97 * np.exp(-0.045 * age) + rng.normal(0, 3, 500), 0, 100)
model = pl.ExponentialModel().fit(age, pci_obs)
print(model)

current = result.pci
print(f"Forecast from PCI {current:.1f}:", np.round(model.forecast(current, [1, 3, 5, 10]), 1))
print(f"Years until PCI 55: {model.years_to_threshold(current, 55):.1f}")

# 3. Compare maintenance strategies over 50 years (illustrative unit costs, $/m2)
crack_seal = pl.Treatment("Crack seal", unit_cost=1.5, pci_gain=4, min_pci=65, max_pci=85,
                          min_interval_years=4)
thin_overlay = pl.Treatment("Thin overlay", unit_cost=18, pci_after=90, min_pci=50)
mill_overlay = pl.Treatment("Mill & overlay", unit_cost=32, pci_after=95, min_pci=35)
reconstruct = pl.Treatment("Reconstruction", unit_cost=140, pci_after=100)

strategies = [
    pl.Strategy("Do nothing"),
    pl.Strategy("Preventive", [pl.TriggerRule(crack_seal, 80), pl.TriggerRule(thin_overlay, 65),
                               pl.TriggerRule(reconstruct, 25)]),
    pl.Strategy("Rehab at 55", [pl.TriggerRule(mill_overlay, 55), pl.TriggerRule(reconstruct, 25)]),
    pl.Strategy("Reactive", [pl.TriggerRule(reconstruct, 30)]),
]

area = 2400 * 7.4  # 2.4 km x 7.4 m
for r in pl.compare_strategies(model, strategies, current, area, horizon=50, discount_rate=0.03):
    s = r.summary()
    print(f"{s['strategy']:<12} NPV ${s['npv']:>12,.0f}  EUAC ${s['euac']:>10,.0f}  "
          f"avg PCI {s['average_pci']:>5}  min PCI {s['min_pci']:>5}  actions {s['actions']}")
