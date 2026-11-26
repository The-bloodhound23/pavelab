"""pavelab data scout: find public, tabular pavement-performance datasets every day.

    python -m datascout.cli --out scout                       # catalogue only
    python -m datascout.cli --out scout --previous old.json   # mark what's new since then
    python -m datascout.cli --out scout --download            # + small open files (research_ok)

Uses official search APIs only (Zenodo, data.gov, open.canada.ca, data.ontario.ca,
Hugging Face). It never logs in, never scrapes web pages, and never bypasses a portal's
terms: LTPP InfoPave, for example, is listed as a manual download, not fetched.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from .sources import SOURCES, USER_AGENT

DEFAULT_QUERIES = [
    "pavement condition index", "pavement performance", "LTPP", "long-term pavement performance",
    "international roughness index", "pavement distress", "pavement rutting", "road condition survey",
    "pavement freeze thaw", "pavement deterioration", "road surface condition",
]
# A hit must mention one of these in its title or description, or it is dropped as off-topic.
RELEVANT = re.compile(r"pavement|asphalt|\broad(way)?s?\b|highway|\bpci\b|\biri\b|roughness|rutting|ltpp|"
                      r"pothole|chauss|revêtement|route", re.I)
FIELDS = ["new", "source", "title", "url", "date", "licence", "research_ok", "commercial_ok", "licence_note",
          "n_tabular_files", "formats", "query", "key"]


def scout(queries, sources=SOURCES, log=print) -> list[dict]:
    items: dict[str, dict] = {}
    for q in queries:
        for name, fn in sources.items():
            try:
                for r in fn(q):
                    if RELEVANT.search(f"{r['title']} {r['description']}"):
                        items.setdefault(r["key"], r)
            except Exception as e:  # one failing source must not stop the run
                log(f"[warn] {name} '{q}': {e}")
    return sorted(items.values(), key=lambda r: (r["research_ok"] is not True, not r["tabular_files"],
                                                r["source"], r["title"].lower()))


def mark_new(items, previous: Path | None) -> int:
    seen = set()
    if previous and previous.exists():
        try:
            seen = {r["key"] for r in json.loads(previous.read_text(encoding="utf-8"))}
        except (ValueError, KeyError, TypeError):
            seen = set()
    for r in items:
        r["new"] = bool(seen) and r["key"] not in seen
    return sum(r["new"] for r in items)


def write(items, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalogue.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(out / "catalogue.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in items:
            w.writerow({**r, "n_tabular_files": len(r["tabular_files"]),
                        "formats": " ".join(sorted({x["format"] for x in r["tabular_files"] if x["format"]}))})


def _filename(r: dict, f: dict) -> str:
    """Readable, filesystem-safe name plus a hash of the file URL, so different files never
    collide after cleaning or truncation (e.g. `data/a.csv` vs `data_a.csv`)."""
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{r['source']}_{r['id']}_{f['name'] or 'file'}")
    stem, dot, ext = base.rpartition(".")
    if not dot or len(ext) > 8:
        stem, ext = base, ""
    tag = hashlib.sha256(f["url"].encode()).hexdigest()[:10]
    return f"{stem[:120]}-{tag}" + (f".{ext}" if ext else "")


def download(items, out: Path, max_bytes=50_000_000, max_files=40, log=print) -> int:
    """Download tabular files of research_ok items, up to max_bytes each. Writes ATTRIBUTION.csv."""
    d = out / "files"
    d.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for r in items:
        if r["research_ok"] is not True:
            continue
        for f in r["tabular_files"]:
            if n >= max_files or not f["url"].startswith("https://"):
                continue
            if f.get("size") and int(f["size"]) > max_bytes:
                continue
            name = _filename(r, f)
            try:
                req = urllib.request.Request(f["url"], headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = resp.read(max_bytes + 1)
                if len(data) > max_bytes:
                    log(f"[skip] {f['url']}: over {max_bytes} bytes")
                    continue
                (d / name).write_bytes(data)
            except Exception as e:
                log(f"[warn] download {f['url']}: {e}")
                continue
            rows.append({"file": name, "title": r["title"], "licence": r["licence"],
                         "commercial_ok": r["commercial_ok"], "source_url": r["url"]})
            n += 1
    with open(out / "ATTRIBUTION.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "title", "licence", "commercial_ok", "source_url"])
        w.writeheader()
        w.writerows(rows)
    return n


MANUAL = """## Manual sources (need a login or have no search API)
- LTPP InfoPave Standard Data Release (2,500+ US/Canadian sections): https://infopave.fhwa.dot.gov/Data/StandardDataRelease
- Mendeley Data (search "LTPP", "pavement"): https://data.mendeley.com
"""


def summary(items, n_new) -> str:
    research = [r for r in items if r["research_ok"] is True and r["tabular_files"]]
    lines = [f"Found {len(items)} pavement datasets; {n_new} new since the last run.",
             f"{len(research)} have tabular files and a licence that allows research use "
             f"({sum(r['commercial_ok'] is True for r in research)} also allow commercial use); "
             f"{sum(r['research_ok'] is None for r in items)} need a manual licence check.", ""]
    new = [r for r in items if r.get("new")]
    if new:
        lines += ["## New today", ""] + [
            f"- [{r['title']}]({r['url']}) · {r['source']} · {r['licence']} · "
            f"{len(r['tabular_files'])} tabular file(s)" for r in new[:50]] + [""]
    lines += ["## Best candidates (open licence, tabular files)", ""] + [
        f"- [{r['title']}]({r['url']}) · {r['source']} · {r['licence']}" for r in research[:30]] + ["", MANUAL]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="scout")
    p.add_argument("--query", action="append", help="search term (repeatable)")
    p.add_argument("--previous", type=Path, help="catalogue.json from the last run, to mark new items")
    p.add_argument("--download", action="store_true", help="download small tabular files allowed for research")
    a = p.parse_args(argv)
    out = Path(a.out)
    items = scout(a.query or DEFAULT_QUERIES)
    n_new = mark_new(items, a.previous)
    write(items, out)
    if a.download:
        print(f"Downloaded {download(items, out)} files to {out / 'files'}")
    s = summary(items, n_new)
    (out / "SUMMARY.md").write_text("# Data scout\n\n" + s + "\n", encoding="utf-8")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
