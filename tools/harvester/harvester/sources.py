"""Source adapters. Each returns a list of Record dicts and never downloads media.

All adapters use official APIs, not page scraping:
  Hugging Face Hub, Zenodo, Wikimedia Commons (no key needed),
  Mapillary (MAPILLARY_TOKEN), YouTube Data API (YOUTUBE_API_KEY).
`fetch_json` is injectable so tests can run offline.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
from typing import Callable

from .licences import normalise

USER_AGENT = "pavelab-harvester/0.1 (+https://github.com/The-bloodhound23/pavelab)"
FetchJSON = Callable[[str], dict]


def http_json(url: str, pause: float = 1.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(pause)  # be polite to every API
    return data


def record(**kw) -> dict:
    lic, ok, note = normalise(kw.pop("licence_raw", None))
    base = {
        "source": "", "kind": "", "id": "", "title": "", "url": "", "media_url": "",
        "author": "", "date": "", "query": "", "licence": lic, "commercial_ok": ok,
        "download_ok": False, "notes": note,
    }
    base.update(kw)
    if kw.get("extra_note"):
        base["notes"] = "; ".join(x for x in (note, base.pop("extra_note")) if x)
    base.pop("extra_note", None)
    return base


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# ---------- Hugging Face Hub ----------
def huggingface(query: str, fetch: FetchJSON = http_json, limit: int = 50) -> list[dict]:
    url = "https://huggingface.co/api/datasets?" + urllib.parse.urlencode({"search": query, "limit": limit, "full": "true"})
    out = []
    for d in fetch(url) or []:
        tags = d.get("tags") or []
        lic = next((t.split(":", 1)[1] for t in tags if t.startswith("license:")), None)
        if not lic:
            lic = (d.get("cardData") or {}).get("license")
            lic = lic[0] if isinstance(lic, list) and lic else lic
        out.append(record(
            source="huggingface", kind="dataset", id=d.get("id", ""), title=d.get("id", ""),
            url=f"https://huggingface.co/datasets/{d.get('id', '')}", author=d.get("author", ""),
            date=(d.get("lastModified") or "")[:10], query=query, licence_raw=lic,
        ))
    return out


# ---------- Zenodo ----------
def zenodo(query: str, fetch: FetchJSON = http_json, size: int = 50) -> list[dict]:
    url = "https://zenodo.org/api/records?" + urllib.parse.urlencode({"q": query, "size": size, "sort": "mostrecent"})
    out = []
    for h in ((fetch(url) or {}).get("hits") or {}).get("hits", []):
        m = h.get("metadata") or {}
        rtype = ((m.get("resource_type") or {}).get("type") or "").lower()
        if rtype and rtype not in {"dataset", "image", "video"}:
            continue
        lic = m.get("license") or {}
        out.append(record(
            source="zenodo", kind=rtype or "dataset", id=str(h.get("id", "")), title=m.get("title", ""),
            url=(h.get("links") or {}).get("self_html") or f"https://zenodo.org/records/{h.get('id', '')}",
            author="; ".join(c.get("name", "") for c in m.get("creators", [])[:3]),
            date=m.get("publication_date", ""), query=query,
            licence_raw=lic.get("id") if isinstance(lic, dict) else lic,
        ))
    return out


# ---------- Wikimedia Commons ----------
def commons(query: str, fetch: FetchJSON = http_json, limit: int = 50) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": limit, "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": 1024,
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    out = []
    for pid, p in (((fetch(url) or {}).get("query") or {}).get("pages") or {}).items():
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in {"image/jpeg", "image/png", "image/webp", "image/tiff"}:
            continue  # photos only; skip drawings (SVG), GIFs, audio, PDFs
        meta = info.get("extmetadata") or {}
        val = lambda k: (meta.get(k) or {}).get("value", "")
        rec = record(
            source="commons", kind="image", id=str(pid), title=p.get("title", "").replace("File:", ""),
            url=info.get("descriptionurl", ""), media_url=info.get("thumburl") or info.get("url", ""),
            author=_strip_html(val("Artist")), date=_strip_html(val("DateTimeOriginal"))[:10],
            query=query, licence_raw=val("LicenseShortName"),
            extra_note="may show people or plates: blur before training",
        )
        rec["download_ok"] = rec["commercial_ok"] is True
        out.append(rec)
    return out


# ---------- Mapillary (street-level, needs token) ----------
def mapillary(bbox: str, token: str, fetch: FetchJSON = http_json, limit: int = 100) -> list[dict]:
    """bbox = 'min_lon,min_lat,max_lon,max_lat'. Returns unlabelled street-level images."""
    params = {"access_token": token, "bbox": bbox, "limit": limit,
              "fields": "id,thumb_1024_url,captured_at,geometry,creator"}
    url = "https://graph.mapillary.com/images?" + urllib.parse.urlencode(params)
    out = []
    for d in (fetch(url) or {}).get("data", []):
        lon, lat = ((d.get("geometry") or {}).get("coordinates") or [None, None])[:2]
        ts = d.get("captured_at")
        date = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000)) if isinstance(ts, (int, float)) else ""
        rec = record(
            source="mapillary", kind="image", id=str(d.get("id", "")), title=f"Street-level image {lat},{lon}",
            url=f"https://www.mapillary.com/app/?pKey={d.get('id', '')}", media_url=d.get("thumb_1024_url", ""),
            author=(d.get("creator") or {}).get("username", ""), date=date, query=bbox,
            licence_raw="CC-BY-SA-4.0",
            extra_note="unlabelled street-level image, needs distress labelling; Mapillary blurs faces and plates",
        )
        rec["download_ok"] = True
        out.append(rec)
    return out


# ---------- YouTube (metadata only, needs key) ----------
def youtube(query: str, key: str, fetch: FetchJSON = http_json, limit: int = 50) -> list[dict]:
    params = {"part": "snippet", "q": query, "type": "video", "videoLicense": "creativeCommon",
              "maxResults": min(limit, 50), "key": key}
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    out = []
    for it in (fetch(url) or {}).get("items", []):
        vid = (it.get("id") or {}).get("videoId", "")
        sn = it.get("snippet") or {}
        out.append(record(
            source="youtube", kind="video", id=vid, title=html.unescape(sn.get("title", "")),
            url=f"https://www.youtube.com/watch?v={vid}", author=sn.get("channelTitle", ""),
            date=(sn.get("publishedAt") or "")[:10], query=query, licence_raw="CC-BY-3.0",
            extra_note="metadata only: YouTube's terms restrict downloading; contact the creator or use YouTube's own tools",
        ))
    return out
