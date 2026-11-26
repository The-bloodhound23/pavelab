import json

import pytest

from datascout import cli, sources
from datascout.licences import screen


@pytest.mark.parametrize("raw, research, commercial", [
    ("cc-by-4.0", True, True),
    ("CC BY-NC 4.0", True, False),
    ("cc-by-nc-nd", True, False),
    ("ca-ogl-lgo", True, True),             # open.canada.ca licence id
    ("OGL-ON-1.0", True, True),
    ("Some custom terms", None, None),
    ("Open Government Licence - Canada", True, True),
    ("us-pd", True, True),
    ("cc-zero", True, True),
    ("notspecified", None, None),
    (None, None, None),
])
def test_screen(raw, research, commercial):
    _, r, c, _ = screen(raw)
    assert (r, c) == (research, commercial)


ZENODO = {"hits": {"hits": [{
    "id": 123, "links": {"self_html": "https://zenodo.org/records/123"},
    "metadata": {"title": "LTPP pavement IRI panel", "license": {"id": "cc-by-4.0"},
                 "publication_date": "2026-11-01", "description": "<p>Roughness for 900 sections</p>"},
    "files": [{"key": "iri.csv", "links": {"self": "https://zenodo.org/api/records/123/files/iri.csv/content"}, "size": 1000},
              {"key": "readme.pdf", "links": {"self": "https://zenodo.org/x.pdf"}, "size": 10}]}]}}

CANADA = {"result": {"results": [
    {"name": "road-condition-2025", "title": {"en": "Provincial road condition", "fr": "État des routes"},
     "license_id": "Open Government Licence - Canada", "metadata_modified": "2026-10-02T00:00:00",
     "notes": {"en": "Pavement condition index by segment"},
     "resources": [{"name": "pci", "url": "https://example.ca/pci.csv", "format": "CSV"}]},
    {"name": "fish", "title": {"en": "Fish counts"}, "license_id": "cc-by", "notes": {"en": "Salmon"}, "resources": []},
]}}


def fake_sources():
    return {
        "zenodo": lambda q: sources.zenodo(q, fetch=lambda url: ZENODO),
        "open.canada.ca": lambda q: sources.ckan("https://open.canada.ca/data", "open.canada.ca",
                                                 "https://open.canada.ca/data/en")(q, fetch=lambda url: CANADA),
        "broken": lambda q: (_ for _ in ()).throw(RuntimeError("down")),
    }


def test_scout_parses_filters_and_dedupes():
    logs = []
    items = cli.scout(["pci", "iri"], sources=fake_sources(), log=logs.append)
    assert [r["key"] for r in items] == ["open.canada.ca:road-condition-2025", "zenodo:123"]  # fish dropped, deduped
    canada, zen = items
    assert canada["title"] == "Provincial road condition"
    assert canada["url"] == "https://open.canada.ca/data/en/dataset/road-condition-2025"
    assert (canada["research_ok"], canada["commercial_ok"]) == (True, True)
    assert [f["format"] for f in zen["tabular_files"]] == ["csv"]  # pdf is not tabular
    assert any("broken" in m for m in logs)  # a failing source is logged, not fatal


def test_mark_new_and_outputs(tmp_path):
    items = cli.scout(["pci"], sources=fake_sources(), log=lambda m: None)
    assert cli.mark_new(items, None) == 0  # first run: nothing is "new"
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps([{"key": "zenodo:123"}]))
    assert cli.mark_new(items, prev) == 1
    cli.write(items, tmp_path / "out")
    assert "open.canada.ca:road-condition-2025" in (tmp_path / "out" / "catalogue.csv").read_text()
    s = cli.summary(items, 1)
    assert "1 new since the last run" in s and "## New today" in s and "infopave" in s.lower()


def test_download_only_research_ok_and_size_capped(tmp_path, monkeypatch):
    items = cli.scout(["pci"], sources=fake_sources(), log=lambda m: None)
    items.append({**items[0], "key": "x:nc", "id": "nc", "research_ok": None,
                  "tabular_files": [{"name": "a", "url": "https://example.com/a.csv", "format": "csv"}]})
    got = []

    class Resp:
        def __init__(self, url): self.url = url
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n): return b"x" * (10 if "pci" in self.url else n)  # zenodo file is "too big"

    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda req, timeout: got.append(req.full_url) or Resp(req.full_url))
    n = cli.download(items, tmp_path, max_bytes=100, log=lambda m: None)
    assert n == 1
    assert "https://example.com/a.csv" not in got  # unknown licence never downloaded
    assert (tmp_path / "ATTRIBUTION.csv").read_text().count("\n") == 2


def test_filenames_never_collide():
    r = {"source": "huggingface", "id": "org/pavement"}
    a = cli._filename(r, {"name": "data/a.csv", "url": "https://huggingface.co/x/data/a.csv"})
    b = cli._filename(r, {"name": "data_a.csv", "url": "https://huggingface.co/x/data_a.csv"})
    assert a != b and a.endswith(".csv") and b.endswith(".csv")
    long1 = cli._filename(r, {"name": "x" * 300 + "1.csv", "url": "https://e.com/1"})
    long2 = cli._filename(r, {"name": "x" * 300 + "2.csv", "url": "https://e.com/2"})
    assert long1 != long2 and len(long1) < 150
    assert cli._filename(r, {"name": "a.csv", "url": "https://e.com/a"}) == cli._filename(r, {"name": "a.csv", "url": "https://e.com/a"})
