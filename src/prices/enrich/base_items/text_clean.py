"""Name-cleaning helpers: subtract packaging + neutral containers before parse.

Faithful port of _pack_strip (apple_fresh_flip_v2), _container_strip
(apple_fresh_flip_v3) and strip2 (ao_rice_cascade). The order matters: tier-a
extract_pack removes numeric packaging as whole spans (units included) so spaCy
does not mis-read "1kg" -> "kg" as a residual noun, THEN neutral produce
containers are stripped, THEN tolerance/format tails.
"""

from __future__ import annotations

import re

from prices.enrich.normalize import extract_pack

from .static import CONTAINER, FORMAT, STRAY, TOL


def pack_strip(name: str, lang: str | None) -> str:
    """Iterate tier-a extract_pack until the packaging pattern is fully removed."""
    s = name
    for _ in range(4):
        cleaned = extract_pack(s, lang if isinstance(lang, str) else None)[0]
        if not cleaned or cleaned == s:
            break
        s = cleaned
    return s.strip() or name


def container_strip(s: str) -> str:
    return re.sub(r"\s+", " ", CONTAINER.sub(" ", s)).strip()


def strip2(s: str) -> str:
    s = TOL.sub(" ", s)
    s = STRAY.sub(" ", s)
    s = FORMAT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_for_parse(name: str, lang: str | None) -> str:
    """The full pre-parse cleaning chain used by the cascade."""
    return strip2(container_strip(pack_strip(name, lang)) or name) or name
