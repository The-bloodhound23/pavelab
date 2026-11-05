"""Offline tests: every API is replaced by a recorded-shape fixture."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harvester import cli, sources  # noqa: E402
from harvester.licences import normalise  # noqa: E402

FIX = {
    "huggingface.co": [
        {"id": "THiNK327/3DCrack", "author": "THiNK327", "lastModified": "2026-09-30T10:00:00.000Z",
         "tags": ["task_categories:image-segmentation", "license:cc-by-4.0"]},
        {"id": "someone/crack-nc", "tags": ["license:cc-by-nc-4.0"]},
        {"id": "someone/no-licence", "tags": []},
    ],
    "zenodo.org": {"hits": {"hits": [
        {"id": 111, "links": {"self_html": "https://zenodo.org/records/111"},
         "metadata": {"title": "Pothole images", "resource_type": {"type": "dataset"},
                      "license": {"id": "cc-by-4.0"}, "creators": [{"name": "Doe, J."}],
                      "publication_date": "2026-05-01"}},
        {"id": 222, "metadata": {"title": "A paper", "resource_type": {"type": "publication"},
                                 "license": {"id": "cc-by-4.0"}}},
    ]}},
    "commons.wikimedia.org": {"query": {"pages": {
        "9": {"title": "File:Pothole in Oshawa.jpg", "imageinfo": [{
            "url": "https://upload.wikimedia.org/a.jpg", "thumburl": "https://upload.wikimedia.org/a_1024.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Pothole_in_Oshawa.jpg", "mime": "image/jpeg",
            "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "Artist": {"value": "<a href='x'>Jane &amp; Co</a>"},
                            "DateTimeOriginal": {"value": "2025-03-04 10:00:00"}}}]},
        "10": {"title": "File:Crack.svg", "imageinfo": [{"mime": "image/svg+xml", "extmetadata": {}}]},
    }}},
    "graph.mapillary.com": {"data": [
        {"id": "555", "thumb_1024_url": "https://scontent.example/555.jpg", "captured_at": 1717200000000,
         "geometry": {"type": "Point", "coordinates": [-78.86, 43.90]}, "creator": {"username": "mapper1"}},
    ]},
    "www.googleapis.com": {"items": [
        {"id": {"videoId": "abc123"}, "snippet": {"title": "Pothole survey &amp; repair", "channelTitle": "City Roads",
                                                  "publishedAt": "2026-01-02T00:00:00Z"}},
    ]},
}


def fake_fetch(url):
    host = url.split("/")[2]
    return json.loads(json.dumps(FIX[host]))


def test_licence_rules():
    assert normalise("cc-by-4.0") == ("CC BY", True, "attribution required")
    assert normalise("CC BY-SA 4.0")[:2] == ("CC BY-SA", True)
    assert normalise("Creative Commons Attribution 4.0 International")[:2] == ("CC BY", True)
    assert normalise("CC0")[:2] == ("CC0", True)
    assert normalise("Public domain")[1] is True
    assert normalise("cc-by-nc-4.0")[1] is False
    assert normalise("CC BY-NC-SA 4.0")[1] is False
    assert normalise("cc-by-nd-4.0")[1] is False
    assert normalise(None)[1] is None
    assert normalise("other")[1] is None


def test_sources_parse_and_flag():
    hf = sources.huggingface("crack", fetch=fake_fetch)
    assert [r["commercial_ok"] for r in hf] == [True, False, None]
    z = sources.zenodo("pothole", fetch=fake_fetch)
    assert len(z) == 1 and z[0]["kind"] == "dataset" and z[0]["author"] == "Doe, J."
    c = sources.commons("pothole", fetch=fake_fetch)
    assert len(c) == 1  # SVG skipped
    assert c[0]["author"] == "Jane & Co" and c[0]["download_ok"] and "blur" in c[0]["notes"]
    m = sources.mapillary("-79,43,-78,44", "TOKEN", fetch=fake_fetch)
    assert m[0]["licence"] == "CC BY-SA" and m[0]["date"] == "2024-06-01" and m[0]["download_ok"]
    y = sources.youtube("pothole", "KEY", fetch=fake_fetch)
    assert y[0]["title"] == "Pothole survey & repair" and y[0]["download_ok"] is False


def test_harvest_dedups_and_skips_keyed_sources_without_keys(tmp_path):
    items = cli.harvest(["a", "b"], bbox="x", fetch=fake_fetch, env={}, log=lambda *_: None)
    assert not any(r["source"] in {"youtube", "mapillary"} for r in items)
    assert len({r["url"] for r in items}) == len(items)  # same items from two queries counted once
    assert items[0]["commercial_ok"] is True  # usable items sorted first
    cli.write_catalogue(items, tmp_path)
    rows = list(csv.DictReader(open(tmp_path / "catalogue.csv", encoding="utf-8")))
    assert len(rows) == len(items) and "licence" in rows[0]


def test_failing_source_does_not_stop_run():
    def flaky(url):
        if "zenodo" in url:
            raise OSError("boom")
        return fake_fetch(url)
    logs = []
    items = cli.harvest(["a"], fetch=flaky, env={"YOUTUBE_API_KEY": "k"}, log=logs.append)
    assert any("zenodo" in l for l in logs)
    assert any(r["source"] == "youtube" for r in items)


def test_download_only_permitted(tmp_path, monkeypatch):
    items = [
        sources.record(source="commons", kind="image", id="1", url="u1", media_url="https://x/m1", licence_raw="CC BY 4.0"),
        sources.record(source="commons", kind="image", id="2", url="u2", media_url="https://x/m2", licence_raw="CC BY-NC 4.0"),
        sources.record(source="youtube", kind="video", id="3", url="u3", media_url="https://x/m3", licence_raw="CC-BY-3.0"),
    ]
    items[0]["download_ok"] = items[1]["download_ok"] = True

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"img"
    fetched = []
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda req, timeout: fetched.append(req.full_url) or R())
    n = cli.download(items, tmp_path)
    assert n == 1 and fetched == ["https://x/m1"]
    assert (tmp_path / "images" / "commons_1.jpg").read_bytes() == b"img"
