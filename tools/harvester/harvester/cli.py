"""pavelab dataset harvester: find licensed pavement-distress data and catalogue it.

    python -m harvester.cli --out harvest            # catalogue only
    python -m harvester.cli --out harvest --download # also download permitted images

Writes catalogue.csv / catalogue.json (every item found, with licence and a
commercial_ok flag) and, with --download, images/ plus ATTRIBUTION.csv for
items whose licence permits commercial use.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import sources

DEFAULT_QUERIES = [
    "pavement crack", "road crack detection", "pothole", "pavement distress",
    "road damage", "asphalt crack", "alligator cracking",
]
# Default Mapillary area: Durham Region, Ontario (Oshawa to Pickering)
DEFAULT_BBOX = "-79.10,43.83,-78.84,43.95"
FIELDS = ["source", "kind", "id", "title", "url", "media_url", "author", "date",
          "query", "licence", "commercial_ok", "download_ok", "notes"]


def harvest(queries, bbox=None, fetch=sources.http_json, env=os.environ, log=print) -> list[dict]:
    items: dict[str, dict] = {}

    def add(recs):
        for r in recs:
            items.setdefault(r["url"] or f"{r['source']}:{r['id']}", r)

    for q in queries:
        for name, fn in (("huggingface", sources.huggingface), ("zenodo", sources.zenodo), ("commons", sources.commons)):
            try:
                add(fn(q, fetch=fetch))
            except Exception as e:  # one failing source must not stop the run
                log(f"[warn] {name} '{q}': {e}")
        if env.get("YOUTUBE_API_KEY"):
            try:
                add(sources.youtube(q, env["YOUTUBE_API_KEY"], fetch=fetch))
            except Exception as e:
                log(f"[warn] youtube '{q}': {e}")
    if bbox and env.get("MAPILLARY_TOKEN"):
        try:
            add(sources.mapillary(bbox, env["MAPILLARY_TOKEN"], fetch=fetch))
        except Exception as e:
            log(f"[warn] mapillary: {e}")
    return sorted(items.values(), key=lambda r: (r["commercial_ok"] is not True, r["source"], r["title"]))


def write_catalogue(items, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "catalogue.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(items)
    (out / "catalogue.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")


def download(items, out: Path, max_items=500, log=print) -> int:
    img_dir = out / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for r in items:
        if n >= max_items or not (r["download_ok"] and r["commercial_ok"] is True and r["media_url"]):
            continue
        name = f"{r['source']}_{r['id']}.jpg"
        try:
            req = urllib.request.Request(r["media_url"], headers={"User-Agent": sources.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                (img_dir / name).write_bytes(resp.read())
        except Exception as e:
            log(f"[warn] download {r['url']}: {e}")
            continue
        rows.append({"file": name, "title": r["title"], "author": r["author"], "licence": r["licence"], "source_url": r["url"]})
        n += 1
    with open(out / "ATTRIBUTION.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "title", "author", "licence", "source_url"])
        w.writeheader()
        w.writerows(rows)
    return n


def summary(items) -> str:
    ok = [r for r in items if r["commercial_ok"] is True]
    by = {}
    for r in ok:
        by[(r["source"], r["kind"])] = by.get((r["source"], r["kind"]), 0) + 1
    lines = [f"Found {len(items)} items; {len(ok)} usable commercially, "
             f"{sum(r['commercial_ok'] is False for r in items)} restricted (NC/ND), "
             f"{sum(r['commercial_ok'] is None for r in items)} unknown licence.", ""]
    lines += [f"- {s} / {k}: {c}" for (s, k), c in sorted(by.items())]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="harvest")
    p.add_argument("--query", action="append", help="search term (repeatable); defaults to a pavement-distress set")
    p.add_argument("--bbox", default=DEFAULT_BBOX, help="Mapillary bbox min_lon,min_lat,max_lon,max_lat")
    p.add_argument("--download", action="store_true", help="download images whose licence permits commercial use")
    p.add_argument("--max-downloads", type=int, default=500)
    a = p.parse_args(argv)
    out = Path(a.out)
    items = harvest(a.query or DEFAULT_QUERIES, bbox=a.bbox)
    write_catalogue(items, out)
    if a.download:
        n = download(items, out, a.max_downloads)
        print(f"Downloaded {n} images to {out / 'images'}")
    s = summary(items)
    (out / "SUMMARY.md").write_text("# Harvest summary\n\n" + s + "\n", encoding="utf-8")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
