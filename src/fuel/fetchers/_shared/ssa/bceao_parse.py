"""Table parsing for the BCEAO statistical bulletins (see ``bceao``).

Reads the ``pdftotext -layout`` text of one edition and returns its
"Prix à la pompe ... dans les pays de l'UEMOA" cells. Cells outside
300-2000 XOF/L, rows that do not split into one value per country, months
out of order, and cells an edition states twice with different values are
dropped with a warning.
"""

from __future__ import annotations

import calendar
import logging
import re
import unicodedata
from datetime import date

logger = logging.getLogger(__name__)

_PRICE_MIN, _PRICE_MAX = 300, 2000

COUNTRIES: dict[str, dict] = {
    "bj": {"name": "Benin", "header": r"\bbenin\b"},
    "bf": {"name": "Burkina Faso", "header": r"burkina"},
    "ci": {"name": "Cote d'Ivoire", "header": r"\bcote\b|ivoire"},
    "gw": {"name": "Guinea-Bissau", "header": r"guinee|bissau"},
    "ml": {"name": "Mali", "header": r"\bmali\b"},
    "ne": {"name": "Niger", "header": r"\bniger\b"},
    "sn": {"name": "Senegal", "header": r"senegal"},
    "tg": {"name": "Togo", "header": r"\btogo\b"},
}
_EXTRA_COLUMNS = {"uemoa": r"\buemoa\b"}

MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}

_TABLE_RE = re.compile(
    r"tableau.*prix a la pompe (?:de l'|de l |du |de la |des )?(.+?)" r" dans les pays"
)
_ROW_RE = re.compile(r"^\s*(?:(20\d{2})\s+)?([^\W\d_]{3,9})\.?\s+(\d.*)$")
_NUMS_RE = re.compile(r"^[\d\s,.]+$")
_LABEL_RE = re.compile(r"^\s*(?:20\d{2}\s+)?[^\W\d_]{3,9}\.?\s*$")
_PRODUCTS = (
    ("super", "Essence super"),
    ("gazoil", "Gasoil"),
    ("gasoil", "Gasoil"),
    ("gas-oil", "Gasoil"),
    ("petrole", "Pétrole lampant"),
)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.replace("’", "'").lower())


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _row_month(token: str) -> int | None:
    token = fold(token)
    if token.startswith("juin"):
        return 6
    if token.startswith("juil"):
        return 7
    prefixes = {
        "jan": 1,
        "fev": 2,
        "mar": 3,
        "avr": 4,
        "mai": 5,
        "aou": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return prefixes.get(token[:3])


def _column_order(header: list[str]) -> list[str] | None:
    """Country keys left to right, by the leftmost column each name starts at."""
    lines = [
        "".join(
            c
            for c in unicodedata.normalize("NFKD", line.lower())
            if not unicodedata.combining(c)
        )
        for line in header
    ]
    positions = []
    for key, pattern in {
        **{cc: m["header"] for cc, m in COUNTRIES.items()},
        **_EXTRA_COLUMNS,
    }.items():
        starts = [m.start() for line in lines for m in re.finditer(pattern, line)]
        if starts:
            positions.append((min(starts), key))
        elif key in COUNTRIES:
            return None
    return [key for _, key in sorted(positions)]


def _cells(rest: str, n: int) -> list[float | None] | None:
    cells = re.split(r"\s{2,}", rest.strip())
    if len(cells) != n:
        tokens = rest.split()
        if len(tokens) != n or not all(re.fullmatch(r"\d{3,4}", t) for t in tokens):
            return None
        cells = tokens
    values: list[float | None] = []
    for cell in cells:
        cell = cell.replace(" ", "").replace(" ", "").replace(",", ".")
        if re.fullmatch(r"\d+(\.\d+)?", cell):
            values.append(float(cell))
        elif cell in {"-", "nd", "n.d.", "ND", "..."}:
            values.append(None)
        else:
            return None
    return values


def _product(title: str) -> str | None:
    for needle, product in _PRODUCTS:
        if needle in title:
            return product
    return None


def _join_split_rows(lines: list[str]) -> list[str]:
    """Older quarterlies print a row's values one line above its month label."""
    out: list[str] = []
    pending: str | None = None
    for line in lines:
        if not line.strip():
            continue
        if _NUMS_RE.match(line):
            if pending is not None:
                out.append(pending)
            pending = line
            continue
        if pending is not None and _LABEL_RE.match(line):
            out.append(f"{line.rstrip()}   {pending.strip()}")
        else:
            if pending is not None:
                out.append(pending)
            out.append(line)
        pending = None
    if pending is not None:
        out.append(pending)
    return out


def _parse_table(lines: list[str], product: str, label: str, ref: date) -> list:
    """(cc, month_end, product, value) cells from one table's lines."""
    lines = _join_split_rows(lines)
    body_start = next((i for i, x in enumerate(lines) if _ROW_RE.match(x)), None)
    if body_start is None:
        logger.warning("[bceao] %s %s: no data rows", label, product)
        return []
    order = _column_order(lines[:body_start])
    if order is None:
        logger.warning("[bceao] %s %s: country header not found", label, product)
        return []
    out = []
    year: int | None = None
    last: date | None = None
    for line in lines[body_start:]:
        match = _ROW_RE.match(line)
        if not match:
            if re.search(r"\d{3}", line):
                logger.warning("[bceao] %s %s: unparsed line %r", label, product, line)
            continue
        if match.group(1):
            year = int(match.group(1))
        month = _row_month(match.group(2))
        if month is None or year is None:
            logger.warning("[bceao] %s %s: unreadable row %r", label, product, line)
            continue
        obs = month_end(year, month)
        if (last and obs <= last) or obs > ref:
            logger.warning("[bceao] %s %s: month out of order %r", label, product, line)
            continue
        values = _cells(match.group(3), len(order))
        if values is None:
            logger.warning("[bceao] %s %s: row not split %r", label, product, line)
            continue
        last = obs
        for key, value in zip(order, values):
            if key not in COUNTRIES or value is None:
                continue
            if not _PRICE_MIN <= value <= _PRICE_MAX:
                logger.warning(
                    "[bceao] %s %s %s %s: %s outside %s-%s, dropped",
                    label,
                    product,
                    key,
                    obs,
                    value,
                    _PRICE_MIN,
                    _PRICE_MAX,
                )
                continue
            out.append((key, obs, product, value))
    return out


def parse_edition(text: str, label: str, ref: date) -> list:
    """All pump-price cells of one edition, dropping cells it states twice
    with different values."""
    lines = text.splitlines()
    starts = []
    for i, line in enumerate(lines):
        match = _TABLE_RE.search(fold(line))
        if match:
            starts.append((i, _product(match.group(1))))
    cells: dict[tuple, set] = {}
    for i, product in starts:
        if product is None:
            logger.warning("[bceao] %s: unknown product table %r", label, lines[i])
            continue
        end = next(
            (
                j
                for j in range(i + 1, len(lines))
                if fold(lines[j]).startswith("source")
            ),
            min(i + 80, len(lines)),
        )
        for cc, obs, prod, value in _parse_table(
            lines[i + 1 : end], product, label, ref
        ):
            cells.setdefault((cc, obs, prod), set()).add(value)
    out = []
    for (cc, obs, prod), values in sorted(cells.items()):
        if len(values) > 1:
            logger.warning(
                "[bceao] %s %s %s %s: edition states %s, dropped",
                label,
                cc,
                obs,
                prod,
                sorted(values),
            )
            continue
        out.append((cc, obs, prod, values.pop()))
    return out
