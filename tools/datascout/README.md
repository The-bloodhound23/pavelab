# Pavement data scout

Every day, searches official data APIs for **public, tabular pavement-performance datasets** (PCI, IRI, rutting, cracking, LTPP extracts, road-condition surveys) and lists what's new.

| Source | API |
|---|---|
| Zenodo | records search, `type=dataset` |
| data.gov (US) | CKAN `package_search` |
| open.canada.ca | CKAN `package_search` |
| data.ontario.ca | CKAN `package_search` |
| Hugging Face Hub | datasets search |

It never logs in, never scrapes web pages and never works around a portal's terms. Sources that need an account (LTPP InfoPave) or have no open search API (Mendeley Data) are listed in every summary as manual downloads.

## Licence screening
Each dataset gets two flags:
- `research_ok`: usable for research (the paper). Open licences, and NC or ND licences, are research-only.
- `commercial_ok`: usable to train PaveLabAI. Only CC0 or public domain, CC BY(-SA), OGL-Canada or Ontario, ODC-By and ODbL qualify.
- Unknown or missing licence: both are left empty. Check by hand; nothing is downloaded.

This is a screening aid, not legal advice.

## Run
```
cd tools/datascout
python -m datascout.cli --out scout                         # catalogue
python -m datascout.cli --out scout --previous old.json     # mark new items
python -m datascout.cli --out scout --download              # + tabular files ≤ 50 MB with research_ok
```
Outputs: `catalogue.csv` and `catalogue.json`, `SUMMARY.md` (new items first), and, with `--download`, `files/` plus `ATTRIBUTION.csv`.

## Daily run
`.github/workflows/datascout.yml` runs daily at 09:43 UTC, and on demand from **Actions → Data scout → Run workflow**. Yesterday's catalogue comes back from the Actions cache, so "New today" works. The results are a run artifact, kept for 30 days. Nothing is committed: data never lands in this public repo.
