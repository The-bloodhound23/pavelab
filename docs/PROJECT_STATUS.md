# Project status

_Last updated: 2026-11-04 · Owner and final approver: Bolu Afolabi (@The-bloodhound23)_

This file is the shared source of truth for everyone working on pavelab and PaveLabAI, human or AI (Claude, ChatGPT). Read it before starting work, and update it in the same pull request as your change.

## Ground rules

1. **Bolu approves every merge and every deploy.** No AI merges to `main`, publishes a package, posts publicly, or deploys to production.
2. **One task per branch** (`feat/…`, `fix/…`, `docs/…`), opened as a pull request. CI must pass.
3. **Claim a task before starting it.** Put your name next to it under "In progress" so two agents don't build the same thing.
4. **Never commit ASTM D6433 deduct or CDV curves**, or any other copyrighted standard text. The bundled curves are illustrative and labelled as such.
5. **Never commit unpublished TAC paper results** or private municipal data.
6. **Every forecast is compared with the carry-forward baseline** (`PersistenceForecaster`), with whole road sections held out in testing.

## Repositories

| Repo | Visibility | What it is | Status |
|---|---|---|---|
| `The-bloodhound23/pavelab` | Public, MIT | Python engine: PCI procedure, deterioration models, LCCA | v0.1 alpha, 32 tests passing, CI on Python 3.9, 3.11 and 3.12 |
| PaveLabAI app (no repo yet) | Private recommended | Hosted web product. Beta live at https://pavelabai.vercel.app | v0.1 static client-side app, currently only a zip and the Vercel deploy |

## Done

- **pavelab v0.1:**
  - ASTM D6433-style PCI procedure: m-value truncation, q-iteration, curves loaded from JSON.
  - Exponential and power-law deterioration models: population fit, anchored forecast, years to threshold.
  - `PersistenceForecaster` baseline.
  - LCCA: treatments, trigger rules, simulation, NPV, EUAC, and optional GHG reporting.
  - `examples/quickstart.py` and the CI workflow.
- **PaveLabAI beta v0.1** (deployed 2026-11-04):
  - Inventory CSV upload or a sample network.
  - Five strategies with life-cycle cost, and a per-road recommendation.
  - 5-year work plan, CSV export and print report.
  - All computation in the browser; data never leaves it.

## Known limitations

- **No real deduct curves bundled.** PCI from a photo or survey needs either licensed ASTM curves or the planned public-domain USACERL TR M-90/05 curve set, which is not yet digitised. This blocks any "real" PCI output.
- **The beta duplicates pavelab's maths in JavaScript** (`engine.js`) and uses a simpler deterioration model with example unit costs and no salvage value.
- **No image or video input**, no accounts, no backend and no billing.
- **Forecasting is untested on sparse municipal data** (surveys several years apart), which is what real customers have.

## Next tasks (proposed, in order; not yet approved)

| # | Task | Why | Suggested lead | Status |
|---|---|---|---|---|
| 1 | Create a private PaveLabAI app repo and commit the beta source | Shared source of truth for the product | Bolu | To do |
| 2 | Digitise the USACERL TR M-90/05 asphalt curves (Appendix B1–B20) into `data/cerl_ac_curves.json`, with provenance | Unblocks real PCI everywhere | Either, reviewed by Bolu | To do |
| 3 | Add salvage (remaining) value to `lcca.simulate` | Required for defensible 20–50 year comparisons | ChatGPT | To do |
| 4 | Talk to 3–5 Ontario public-works engineers, using the beta as the demo | Decides what phase 2 is | Bolu | To do |
| 5 | `pavelab.sparse`: forecasting from surveys years apart, with uncertainty ranges (proposal P7) | Matches the data customers actually have | ChatGPT | Proposed |
| 6 | `pavelab.frontier`: budget-vs-benefit curve for council reports (proposal P6) | Better decision output than a single lowest-NPV answer | Claude | Proposed |
| 7 | Import adapters for existing dashcam vendors' distress exports | Lets PaveLabAI sit on top of data agencies already collect | Claude | Proposed |
| 8 | First live run of the dataset harvester; review `catalogue.csv`; pick datasets for a detector baseline | Turns the harvester into training data | Bolu, then ChatGPT | After PR #2 merges |
| 9 | Label harvested photos by ASTM D6433 type and severity; blur faces and plates in non-Mapillary images | Required before any training | Bolu (or a labelling tool) | To do |

Larger items (video ingestion, GIS map, accounts, LLM assistant) wait until task 4 shows which of them customers will pay for.

## In progress

_Nothing claimed yet._

## Decision log

- **2026-10-17:** MIT licence. The library ships the PCI procedure, not ASTM curves.
- **2026-11-04:** PaveLabAI beta deployed as a static client-side app on Vercel (project `pavelabai`).
- **2026-11-04:** Claude and ChatGPT collaborate through GitHub branches and pull requests. Bolu approves all merges and deploys.
- **2026-11-04:** Training data comes only from sources whose licence allows commercial use, gathered through official APIs (`tools/harvester`, PR #2). There is no page scraping, and YouTube videos are listed but never downloaded, because YouTube's terms restrict downloading.
