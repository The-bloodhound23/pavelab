"""Licence screening. Two separate questions:

- research_ok: may we use it for the paper (non-commercial research)?
- commercial_ok: may PaveLabAI (a commercial product) train on it?

Unknown licences are None for both: a person must check them.
"""
from __future__ import annotations

import re

_OPEN = [
    (r"cc0|cc-?zero|public-?domain|pddl|us-pd|other-pd|^pd$", "Public domain / CC0", ""),
    (r"open-?government-?licen[cs]e.*canada|ogl-?canada|ca-ogl|ogl-lgo|canada-open-government", "OGL-Canada",
     "attribution required"),
    (r"open-?government-?licen[cs]e.*ontario|ogl-?ontario|ogl-?on(-|$)", "OGL-Ontario", "attribution required"),
    (r"cc-?by-?sa", "CC BY-SA", "share-alike: derived datasets keep the licence"),
    (r"cc-?by(?!-?nc)(?!-?nd)", "CC BY", "attribution required"),
    (r"odc-?by", "ODC-By", "attribution required"),
    (r"odbl", "ODbL", "share-alike for databases"),
]


def screen(raw: str | None) -> tuple[str, bool | None, bool | None, str]:
    """Return (licence, research_ok, commercial_ok, note)."""
    if not raw or not raw.strip() or raw.strip().lower() in {"notspecified", "unknown", "other", "license-not-specified"}:
        return "unknown", None, None, "no licence stated: check the source"
    s = re.sub(r"[\s_/.]+", "-", raw.strip().lower())
    s = s.replace("creative-commons-", "cc-").replace("attribution", "by").replace("sharealike", "sa")
    if re.search(r"(^|-)nc(-|$)|non-?commercial", s):
        return raw.strip(), True, False, "non-commercial: research use only"
    if re.search(r"(^|-)nd(-|$)|no-?deriv", s):
        return raw.strip(), True, False, "no-derivatives: research reading only, no derived datasets"
    for pattern, code, note in _OPEN:
        if re.search(pattern, s):
            return code, True, True, note
    return raw.strip(), None, None, "licence not recognised: review manually"
