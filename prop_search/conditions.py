"""Detect and filter out undesirable sale/occupancy conditions.

These conditions (bare ownership, sold-with-tenants, squatter-occupied) are not
exposed as structured fields by any of the portals — they appear in the listing
description text. Every source maps its description into ``Listing.details``, so
this single detector covers all sources from the common model.
"""

from __future__ import annotations

import re
import unicodedata


def _norm(text: object) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# label -> pattern (matched against accent-stripped, lowercased text).
# Patterns are written to avoid the common negations ("sin inquilinos",
# "libre de okupas", "plena propiedad").
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("nuda_propiedad", re.compile(r"nuda\s*propiedad")),
    # rented out, in several phrasings seen in the wild:
    #   "con inquilinos", "se encuentra alquilado", "vivienda arrendada",
    #   "familia residiendo", "contrato de alquiler/arrendamiento en vigor",
    #   "fin de contrato / termina el contrato ...".
    # Participles only (alquilad[ao]/arrendad[ao]); infinitive "alquilar" / noun
    # "alquiler" ("ideal para alquilar") are NOT matched. "arrendatario" is left
    # out on purpose ("libre de arrendatarios" = becoming vacant).
    ("tenants", re.compile(
        r"con\s+inquilin|\balquilad[ao]s?\b|\barrendad[ao]s?\b|residiend|"
        r"contrato\s+de\s+(arrendamiento|alquiler)|"
        r"(termina|finaliza|vence|vencimiento|fin)[^.]{0,25}\bcontrato")),
    # squatter / no-possession: "okupado", "ocupación ilegal", "sin posesión",
    # or "ocupado/ocupada" — but NOT "desocupado" (vacant, word boundary), "no
    # ocupado", or "ocupada por el/su/los propietario(s)" (owner-occupied).
    ("squatters", re.compile(
        r"\bokupad[ao]s?\b|ocupacion\s+ilegal|sin\s+posesion|"
        r"(?<!no )\bocupad[ao]s?\b(?!\s+por\s+(el|su|los|sus)\s+propietari)")),
    ("no_visit", re.compile(r"no\s+se\s+puede\s+visitar")),     # occupied/auction, no viewing
]


def excluded_condition(text: object) -> str | None:
    """Return the label of an excluded condition found in text, else None."""
    t = _norm(text)
    for label, pattern in _PATTERNS:
        if pattern.search(t):
            return label
    return None


def filter_out_conditions(listings: list) -> tuple[list, dict]:
    """Drop listings with an excluded condition; return (kept, counts_by_label)."""
    kept: list = []
    counts: dict[str, int] = {}
    for item in listings:
        label = excluded_condition(item.details)
        if label:
            counts[label] = counts.get(label, 0) + 1
            continue
        kept.append(item)
    return kept, counts
