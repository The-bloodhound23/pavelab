# pavelab

**Open-source Python toolkit for pavement condition, deterioration forecasting and life-cycle cost analysis (LCCA).**

pavelab covers the questions agencies budget around:

- **What condition is this section in?** PCI using the ASTM D6433 procedure
- **When will it hit an intervention threshold?** Non-linear deterioration models
- **Which strategy costs least over 20 years?** Trigger-based LCCA with NPV and EUAC

> **Status: v0.1 (alpha).** APIs may change. Licensed under MIT.

## Install

```bash
pip install git+https://github.com/The-bloodhound23/pavelab.git   # until released on PyPI
```

Requires Python 3.9+, numpy and scipy.

## Quick start

```python
import pavelab as pl

# 1. PCI for one sample unit
curves = pl.CurveSet.example()            # ILLUSTRATIVE curves, see note below
result = pl.compute_pci(
    [pl.Distress("alligator_cracking", "M", 12.0),
     pl.Distress("potholes", "L", 1)],
    sample_area=230, curves=curves,
)
print(result.pci, result.rating)

# 2. Deterioration: fit to a population, then anchor to this section
model = pl.ExponentialModel().fit(ages, pcis)     # or pl.PowerLawModel()
model.forecast(result.pci, [1, 5, 10])
model.years_to_threshold(result.pci, 55)

# 3. LCCA: compare strategies
overlay = pl.Treatment("Thin overlay", unit_cost=18, pci_after=90, min_pci=50)
recon   = pl.Treatment("Reconstruction", unit_cost=140, pci_after=100)
strategies = [
    pl.Strategy("Do nothing"),
    pl.Strategy("Overlay at 65", [pl.TriggerRule(overlay, 65), pl.TriggerRule(recon, 25)]),
    pl.Strategy("Reactive", [pl.TriggerRule(recon, 30)]),
]
for r in pl.compare_strategies(model, strategies, result.pci, area_m2=17_760):
    print(r.summary())
```

A complete runnable script is in [`examples/quickstart.py`](examples/quickstart.py).

## Important: deduct curves

ASTM D6433 deduct-value and corrected-deduct-value (CDV) curves are copyrighted, so **pavelab ships the procedure, not the curves.** You load your own curve file:

```python
curves = pl.CurveSet.from_json("my_curves.json")
```

The bundled `example_curves.json` contains **made-up illustrative values** for demos and tests. **Do not use it for real condition ratings.** The JSON format is documented in `pavelab/pci.py`. A public-domain curve set is planned for a later release.

## What's in v0.1

| Module | Contents |
|---|---|
| `pavelab.pci` | D6433-style procedure for asphalt sample units: density, log-interpolated deduct values, m-value truncation, q-iteration, max CDV, PCI and rating bands. Curves come from JSON. |
| `pavelab.deterioration` | `ExponentialModel` (PCI0·e^(−λt)) and `PowerLawModel` (PCI0 − αt^β): population fitting, effective-age anchoring, years to threshold. `PersistenceForecaster` carry-forward baseline. `r2_score`. |
| `pavelab.lcca` | `Treatment` (reset value or point gain, applicability window, minimum repeat interval, optional GHG), `TriggerRule`, `Strategy`, year-by-year `simulate`, `compare_strategies`, `npv`, `euac`. |

The LCCA engine accepts any object with a `forecast(current_pci, years)` method, so you can plug in your own models.

## Known limitations (v0.1)

- **NPV counts agency costs only.** There are no user costs or salvage value yet, so "Do nothing" always has the lowest NPV. Compare strategies on cost **and** condition (`average_pci`, `min_pci`, `area_under_curve`), not NPV alone.
- PCI covers asphalt surfaces only. Concrete is not supported yet.
- Treatment effects are simple (reset or fixed gain), and post-treatment deterioration reuses the same curve.
- Simulations are deterministic, with no uncertainty bands.

## Roadmap

- Public-domain deduct curve set
- ML forecasters trained on LTPP data, benchmarked against the persistence baseline with section-grouped cross-validation
- Salvage value, user costs and probabilistic LCCA
- Adapters from image-based distress detections to D6433 distress records

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Background

pavelab grew out of research on freeze-thaw pavement deterioration using FHWA LTPP data from US and Canadian sections.

## License

MIT © 2026 Boluwatife Afolabi
