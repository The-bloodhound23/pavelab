"""Normalise licence strings and decide whether an item may be used commercially.

Rule: anything not clearly permissive is excluded. Non-commercial (NC) and
no-derivatives (ND) licences are excluded because training a commercial model
on them is not allowed or at best unclear. Unknown licences are excluded.
"""
from __future__ import annotations

import re

# (normalised code, commercial use allowed, note)
_PERMISSIVE = [
    (r"^(cc0|cc-?zero|cc0-1\.0)$", "CC0", ""),
    (r"^(pd|pddl|pddl-1\.0|public[- ]domain|pd-.*)$", "Public domain", ""),
    (r"^cc[- ]?by[- ]?sa(-?[\d.]+)?$", "CC BY-SA", "share-alike: derived datasets must keep the same licence"),
    (r"^cc[- ]?by(-?[\d.]+)?$", "CC BY", "attribution required"),
    (r"^(odc-?by(-1\.0)?)$", "ODC-By", "attribution required"),
    (r"^(odbl(-1\.0)?)$", "ODbL", "share-alike for databases"),
    (r"^(mit|apache-2\.0|bsd-[23]-clause)$", None, "software licence; check it covers the data"),
]


def normalise(raw: str | None) -> tuple[str, bool | None, str]:
    """Return (licence, commercial_ok, note). commercial_ok is None when unknown."""
    if not raw:
        return "unknown", None, "no licence stated"
    s = raw.strip().lower()
    s = re.sub(r"\s+", "-", s.replace("_", "-"))
    s = s.replace("creative-commons-", "cc-").replace("attribution", "by").replace("sharealike", "sa")
    s = re.sub(r"-(international|unported|generic)$", "", s)
    if re.search(r"(^|-)nc(-|$)|noncommercial", s):
        return raw.strip(), False, "non-commercial licence: research use only"
    if re.search(r"(^|-)nd(-|$)|noderiv", s):
        return raw.strip(), False, "no-derivatives licence"
    for pattern, code, note in _PERMISSIVE:
        if re.match(pattern, s):
            return (code or raw.strip().upper()), True, note
    return raw.strip(), None, "licence not recognised: review manually"
