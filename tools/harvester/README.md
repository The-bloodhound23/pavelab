# Pavement dataset harvester

Finds pavement-distress images, videos and datasets online, records each item's **licence**, and flags whether it can be used to train a **commercial** model (PaveLabAI). It uses official APIs only; it does not scrape web pages.

| Source | What it finds | Key needed | Downloads? |
|---|---|---|---|
| Hugging Face Hub | Labelled crack and pothole datasets | No | Catalogue only (datasets are large; fetch the ones you pick) |
| Zenodo | Research datasets, images and videos | No | Catalogue only |
| Wikimedia Commons | Individual photos of potholes and cracks | No | Yes, if the licence allows commercial use |
| Mapillary | Street-level images for a map area (default: Durham Region, Ontario) | `MAPILLARY_TOKEN` | Yes (CC BY-SA; Mapillary already blurs faces and plates) |
| YouTube | Creative Commons videos (road surveys, dashcam footage) | `YOUTUBE_API_KEY` | **No.** YouTube's terms restrict downloading, so videos are listed for you to follow up |

## Licence rules

- **Kept** (`commercial_ok = True`): CC0, public domain, CC BY, CC BY-SA, ODC-By and ODbL. Share-alike items are flagged, because a dataset built from them must keep the same licence.
- **Excluded** (`False`): anything non-commercial (NC) or no-derivatives (ND).
- **Excluded** (`None`): no licence or an unrecognised one. Review these by hand.

This is a screening tool, not legal advice. Check the licence page before training on anything.

## Run it

```bash
cd tools/harvester
python -m harvester.cli --out harvest                 # catalogue only
python -m harvester.cli --out harvest --download      # + images that allow commercial use
python -m harvester.cli --query "frost heave" --query "transverse crack"
```

Outputs in `harvest/`:
- `catalogue.csv` / `catalogue.json`: every item found, usable ones first.
- `SUMMARY.md`: item counts, broken down by licence status.
- `images/` and `ATTRIBUTION.csv`: with `--download` only. Keep the attribution file with the images.

## Automatic weekly run

`.github/workflows/harvest.yml` runs every Monday and on demand (**Actions → Dataset harvest → Run workflow**). The results are attached to the run as a downloadable artifact for 30 days; nothing is committed to the repo. To enable the optional sources, add `MAPILLARY_TOKEN` and `YOUTUBE_API_KEY` as repository secrets (**Settings → Secrets and variables → Actions**).

## Before training on harvested images

1. Remove duplicates and off-topic images.
2. Blur faces and licence plates in any non-Mapillary image.
3. Label distresses by ASTM D6433 type and severity.
4. Keep `ATTRIBUTION.csv` with the dataset, and credit sources in the model card.
