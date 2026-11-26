# Architecture

## Principle

**Numbers come from tested code, never from a language model.** Computer vision detects distresses, pavelab calculates PCI and life-cycle cost, deterioration models forecast, and an LLM (if added later) only explains outputs that the engine has already verified. A photo or video alone gives a *preliminary condition estimate*. It becomes a standards-based PCI only when sample-unit measurements and licensed or public-domain deduct curves are available.

## Today

```
pavelab (this repo, Python, MIT)          PaveLabAI beta (separate, static web app)
├── pci.py           PCI procedure          index.html / app.js / styles.css
├── deterioration.py forecast models        engine.js  ← JavaScript port of the
├── lcca.py          strategies, NPV, EUAC             forecast + LCCA logic
└── data/example_curves.json (illustrative)  Chart.js (CDN), runs entirely in the browser
```

### `pavelab.pci`
- `Distress(type, severity, quantity)` and `CurveSet.from_json()` / `CurveSet.example()`.
- `compute_pci(distresses, sample_area, curves)` → `PCIResult` (PCI, rating, deducts, m, iterations).
- Deduct curves are interpolated on log density. CDV comes from q-iteration with m-value truncation (`allowable_deducts`).

### `pavelab.deterioration`
- `DeteriorationModel` (abstract), with `ExponentialModel` and `PowerLawModel` implementations. Each supports a population `fit(ages, pcis)`, an anchored `forecast(current_pci, years)` and `years_to_threshold`.
- `PersistenceForecaster` is the carry-forward baseline every model must beat. `r2_score` is a dependency-free metric.

### `pavelab.lcca`
- `Treatment` (unit cost, PCI after, applicable PCI band), `TriggerRule`, `Strategy`.
- `simulate(model, strategy, current_pci, area_m2, horizon, discount_rate)` → `SimulationResult`.
- `compare_strategies`, `npv`, `euac`, and optional GHG reporting.

### PaveLabAI beta
- **Input:** inventory CSV (`length_m`, `width_m` and `pci` required; `id`, `name`, `age` and `traffic` optional).
- **Engine:** `engine.js` re-implements anchored exponential decay plus banded trigger strategies and recommends the lowest-cost strategy per road that stays above the minimum PCI.
- **Privacy:** no server. Data never leaves the browser.

### `tools/harvester` (data acquisition, PR #2)
- Licence-aware search across Hugging Face, Zenodo, Wikimedia Commons, Mapillary (token) and YouTube Creative Commons (API key), through official APIs only.
- `licences.normalise()` keeps CC0, public domain, CC BY, CC BY-SA, ODC-By and ODbL. It excludes NC, ND and unknown licences, and flags share-alike.
- Outputs a catalogue, a summary, and permitted images with `ATTRIBUTION.csv`. YouTube results are metadata only.
- Runs weekly and on demand via `.github/workflows/harvest.yml`, with results attached to the run as an artifact.

## Stack

| Layer | Today | Planned |
|---|---|---|
| Engineering engine | `pavelab` (Python: numpy, scipy) | Same, exposed through a Python API service |
| Training data | `tools/harvester` (licensed sources only) | Labelling workflow, then detector baseline |
| Distress detection | none | Open-licence detector (e.g. YOLO or segmentation) fine-tuned on harvested, labelled data |
| Web app | Static HTML, JS and Chart.js on Vercel (PaveLabAI beta) | App calls the pavelab service |
| Automation | GitHub Actions: CI and weekly harvest | Same |
| AI collaborators | Claude (implementation, integration) and ChatGPT/Codex (methodology, review), via pull requests | Same; LLMs explain results, never compute them |

## Target (staged, each stage gated on customer feedback)

```
Inputs: inventory CSV · survey history · vendor distress exports · photos/video (later) · GIS (later)
        │
        ▼
Ingestion + validation  (schema checks, match records to road sections)
        │
        ▼
pavelab engine  (Python service): PCI · forecasting with uncertainty · LCCA with salvage · budget frontier
        │
        ▼
PaveLabAI app: work plan · strategy comparison · council report · audit trail
        │
        └── optional LLM layer: explains engine outputs and drafts report text; never computes numbers
```

### Decisions to make before moving beyond the static app
- **One engine.** Once there's a backend, the app should call pavelab instead of keeping a separate JavaScript copy, so results can't drift apart.
- **Data handling.** A backend ends the "data never leaves your browser" promise. Municipal data and street imagery (faces, licence plates) then need security, retention and blurring policies.
- **Imagery rights.** Don't assume Google Street View or similar imagery may be processed with AI. Use municipal-owned or licensed imagery only.
- **Build or integrate capture.** Dashcam vendors (for example vialytics, Blyncsy and RoadAI) already capture and detect distresses. PaveLabAI's edge is the engineering decision layer, so import their outputs before building a video pipeline.
