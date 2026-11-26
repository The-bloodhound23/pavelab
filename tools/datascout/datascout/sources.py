"""Official search APIs. Each source returns a list of records (see record())."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from .licences import screen

USER_AGENT = "pavelab-datascout/0.1 (+https://github.com/The-bloodhound23/pavelab)"
TABULAR = {"csv", "xlsx", "xls", "zip", "json", "parquet", "tsv", "accdb", "mdb", "txt"}
FetchJSON = Callable[[str], dict]


def http_json(url: str, pause: float = 1.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(pause)  # be polite to every API
    return data


def _ext(name: str | None) -> str:
    name = (name or "").lower().split("?")[0]
    return name.rsplit(".", 1)[-1] if "." in name[-8:] else ""


def record(*, source, id, title, url, licence_raw, query, files=(), date="", description="") -> dict:
    lic, research_ok, commercial_ok, note = screen(licence_raw)
    def fmt(f):
        return ((f.get("format") or "").lower() or _ext(f.get("name")) or _ext(f.get("url")))

    tab = [f for f in files if fmt(f) in TABULAR]
    return {
        "key": f"{source}:{id}", "source": source, "id": str(id), "title": (title or "").strip()[:200],
        "url": url, "date": date or "", "query": query, "licence": lic, "research_ok": research_ok,
        "commercial_ok": commercial_ok, "licence_note": note,
        "tabular_files": [{"name": f.get("name", ""), "url": f.get("url", ""),
                           "format": fmt(f),
                           "size": f.get("size")} for f in tab][:20],
        "description": " ".join((description or "").split())[:300],
    }


def zenodo(q: str, fetch: FetchJSON = http_json, size: int = 25) -> list[dict]:
    url = "https://zenodo.org/api/records?" + urllib.parse.urlencode(
        {"q": q, "type": "dataset", "size": size, "sort": "mostrecent"})
    out = []
    for h in fetch(url).get("hits", {}).get("hits", []):
        m = h.get("metadata", {})
        files = [{"name": f.get("key"), "url": (f.get("links") or {}).get("self"), "size": f.get("size")}
                 for f in h.get("files", [])]
        lic = (m.get("license") or {}).get("id") if isinstance(m.get("license"), dict) else m.get("license")
        out.append(record(source="zenodo", id=h.get("id"), title=m.get("title"),
                          url=(h.get("links") or {}).get("self_html") or f"https://zenodo.org/records/{h.get('id')}",
                          licence_raw=lic, query=q, files=files, date=m.get("publication_date", ""),
                          description=m.get("description", "")))
    return out


def ckan(base: str, name: str, page_base: str | None = None) -> Callable[..., list[dict]]:
    """CKAN portals: catalog.data.gov, open.canada.ca, data.ontario.ca."""
    page_base = page_base or base
    def search(q: str, fetch: FetchJSON = http_json, rows: int = 25) -> list[dict]:
        url = f"{base}/api/3/action/package_search?" + urllib.parse.urlencode({"q": q, "rows": rows})
        out = []
        for p in (fetch(url).get("result") or {}).get("results", []):
            files = [{"name": r.get("name"), "url": r.get("url"), "format": r.get("format"), "size": r.get("size")}
                     for r in p.get("resources", [])]
            title = p.get("title")
            if isinstance(title, dict):  # open.canada.ca returns {"en": ..., "fr": ...}
                title = title.get("en") or next(iter(title.values()), "")
            notes = p.get("notes")
            if isinstance(notes, dict):
                notes = notes.get("en", "")
            out.append(record(source=name, id=p.get("name") or p.get("id"), title=title,
                              url=f"{page_base}/dataset/{p.get('name') or p.get('id')}",
                              licence_raw=p.get("license_id") or p.get("license_title"), query=q,
                              files=files, date=p.get("metadata_modified", "")[:10], description=notes or ""))
        return out
    return search


def huggingface(q: str, fetch: FetchJSON = http_json, limit: int = 25) -> list[dict]:
    url = "https://huggingface.co/api/datasets?" + urllib.parse.urlencode({"search": q, "limit": limit, "full": "true"})
    data = fetch(url)
    out = []
    for d in data if isinstance(data, list) else []:
        lic = next((t.split(":", 1)[1] for t in d.get("tags", []) if t.startswith("license:")), None)
        files = [{"name": s.get("rfilename"), "url": f"https://huggingface.co/datasets/{d['id']}/resolve/main/{s.get('rfilename')}"}
                 for s in d.get("siblings", []) or []]
        out.append(record(source="huggingface", id=d["id"], title=d["id"], url=f"https://huggingface.co/datasets/{d['id']}",
                          licence_raw=lic, query=q, files=files, date=(d.get("lastModified") or "")[:10],
                          description=(d.get("description") or "")))
    return out


SOURCES = {
    "zenodo": zenodo,
    "data.gov": ckan("https://catalog.data.gov", "data.gov"),
    "open.canada.ca": ckan("https://open.canada.ca/data", "open.canada.ca", "https://open.canada.ca/data/en"),
    "data.ontario.ca": ckan("https://data.ontario.ca", "data.ontario.ca"),
    "huggingface": huggingface,
}
