"""Piece-grammar extraction for non-food goods sold by the piece.

Stage B routes a product here when its leaf's allowed bases are only `item`
and `count` (`trust.piece_leaves`); every other leaf keeps `extract.py`. The
result has the same fields as `extract()`: `count` basis with the pack size
when the name states a homogeneous pack, else one `item`. Measures never
become a basis here. Patterns: `regex_patterns_nonfood` (shared -> country ->
source).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

import pandas as pd

from prices.enrich.declared_unit import parse_declared_count
from prices.enrich.extract import StructuralFields
from prices.enrich.regex_patterns.flag_markers import PROMO_MARKERS
from prices.enrich.regex_patterns_nonfood import load
from prices.enrich.stages.extraction import EXTRACTION_COLS

# A pack larger than this, or a number that reads as a year, is a code.
MAX_PACK = 1000
_YEARS = range(1900, 2101)
_WORD_N = {"twin": 2, "double": 2, "triple": 3}
_PROMO = re.compile("|".join(r for rs in PROMO_MARKERS.values() for r in rs), re.IGNORECASE)
# Fixes from the 2026-10-08 language hand check, applied to every non-food product.
_ONE = re.compile(r"(?<![\d.,])1\s*(?:'+\s*s|s|pcs?\.?|pieces?|ชิ้น|units?|cái|chiếc)(?![a-z])", re.I)
# "Hộp 3 vỉ x 10 viên", "5 Strips @ 6 Tabs", "6 x 10's": the pack is a x n.
_BLISTER = re.compile(
    r"(?<![\d.,])(?P<a>\d{1,3})\s*(?:(?:vỉ|strips?|blisters?)\s*(?:x|@|\*)|x)\s*(?P<n>\d{1,3})\s*"
    r"(?:viên|tab|cap|'?s\b)", re.I)
_PER_ONE = re.compile(r"\(\s*per\s+(?:tablet|capsule|cap|caplet|pill|strip|pcs?)\s*\)", re.I)
_SIZE = r"(?:ml|g|kg|l|มล|ก|กรัม|ลิตร)"
# "โลชั่น 370 มล.+เจลลี่ 50 มล.": two sized products under one price.
_TWO_SIZES = re.compile(
    r"\d\s*" + _SIZE + r"\.?\s*\+\s*[^+\d]{0,40}?\d+(?:[.,]\d+)?\s*" + _SIZE + r"(?![a-z/])", re.I
)
_KIT = re.compile(r"\b(?:kit|set)\b|bộ", re.I)
# "400 มล. x 1+1", "[1+1]": buy one get one, two units; not "(1+1)-Nonlinear".
_BOGO = re.compile(r"(?<![\w(])1\s*\+\s*1(?![\w)])")


def _item(promo: bool, bundle: bool) -> StructuralFields:
    return StructuralFields("item", None, "item", 1, 1, promo, bundle, False, None)


def _count(n: int, promo: bool) -> StructuralFields:
    return StructuralFields("count", None, "unit", n, 1, promo, False, True, None)


def extract_nonfood(
    name: str,
    coicop_code: str | None = None,
    country: str | None = None,
    source: str | None = None,
) -> StructuralFields:
    if not name or not str(name).strip():
        return StructuralFields(None, None, None, None, None, None, None, None, None)
    text = unicodedata.normalize("NFKC", str(name))
    promo = bool(_PROMO.search(text))
    pats = [p for p in load(country, source) if p.applies(coicop_code)]
    for p in pats:
        if p.role == "blank":
            text = p.regex.sub(" ", text)
    if any(p.regex.search(text) for p in pats if p.role == "bundle"):
        return _item(promo, True)

    def numbers(role):
        # In pattern order; a match consumes its span, so "2 x 36pcs" is read
        # once as 72 and not again as 36.
        nonlocal text
        out = []
        for p in pats:
            if p.role != role:
                continue
            for m in p.regex.finditer(text):
                g = m.groupdict()
                n = next(v for k, v in g.items() if k.startswith("n") and v)
                n = int(n) if n.isdigit() else _WORD_N[n.lower()]
                out.append(n * (int(g["a"]) if g.get("a") else 1))
            text = p.regex.sub(" ", text)
        return out

    # Read before the strong patterns consume it: "1 set, 35pcs" is one set.
    is_set = any(p.regex.search(text) for p in pats if p.role == "setnoun")
    # "(1 Pack) ... (28 pcs)": a pack of one says nothing; read on.
    found = [n for n in numbers("strong") if n > 1]
    if not found and not numbers("set") and not is_set:
        found = numbers("weak")
    sizes = {n for n in found if 1 < n <= MAX_PACK and n not in _YEARS}
    if len(sizes) == 1:
        return _count(sizes.pop(), promo)
    return _item(promo, False)


def extract_frame_nonfood(products: pd.DataFrame) -> pd.DataFrame:
    """`extract_frame` for piece leaves: one row in, one row out, same columns.

    Falls back to `details`, then to a declared countable `unit`, only when the
    name gives one item and no bundle."""
    rows = []
    for r in products.itertuples(index=False):
        code, country, source = r.coicop_code, r.country, r.source
        sf = extract_nonfood(r.product_name_original, code, country, source)
        declared = False
        if sf.pricing_basis == "item" and not sf.is_bundle:
            details = getattr(r, "details", None)
            if isinstance(details, str) and details.strip():
                sf2 = extract_nonfood(details, code, country, source)
                if sf2.pricing_basis == "count":
                    sf = replace(sf2, is_promotion=sf.is_promotion)
            n = parse_declared_count(getattr(r, "unit", None)) if sf.pricing_basis == "item" else None
            if n is not None and n > 1:
                sf, declared = _count(n, sf.is_promotion), True
        rows.append({
            "input_hash": r.input_hash, "country": country, "source": source,
            "pricing_basis": sf.pricing_basis, "amount_value": sf.amount_value,
            "standard_unit": sf.standard_unit, "count": sf.count, "multiplier": sf.multiplier,
            "is_promotion": sf.is_promotion, "is_bundle": sf.is_bundle,
            "is_multipack": sf.is_multipack, "promo_reason": sf.promo_reason,
            "unit_declared": declared,
        })
    return pd.DataFrame(rows, columns=EXTRACTION_COLS)


def nonfood_frame(ex: pd.DataFrame, products: pd.DataFrame, is_piece: pd.Series) -> pd.DataFrame:
    """Non-food extraction: `ex` (the food grammar on measured leaves) plus the
    piece grammar on piece leaves, then the name-level fixes."""
    ex = ex.set_index("input_hash")
    item = ex.index[ex["pricing_basis"].isna() | ex["pricing_basis"].eq("item")]
    # A measured-leaf product with no size may still state its pieces
    # ("Mascara 1's", "100 ชิ้น"): the piece grammar reads them. Its bundle
    # call is not taken: "Vitamin C + Zinc" is one product here.
    todo = products[~is_piece & products["input_hash"].isin(item)]
    fb = extract_frame_nonfood(todo).set_index("input_hash")
    name = todo.set_index("input_hash")["product_name_original"].fillna("").astype(str)
    one = name.str.contains(_ONE)
    # "Favorites Set X21", "Kit 2 Light/Medium": a cosmetics kit's number is not its pieces.
    kit = name.str.contains(_KIT).reindex(fb.index, fill_value=False)
    take = fb["pricing_basis"].eq("count") & ~kit
    single = ~take & ~fb["is_bundle"].eq(True) & one.reindex(fb.index, fill_value=False)
    fb.loc[single, ["pricing_basis", "standard_unit", "count", "multiplier"]] = ["count", "unit", 1, 1]
    cols = ["pricing_basis", "amount_value", "standard_unit", "count", "multiplier", "is_bundle", "is_multipack"]
    fb["amount_value"] = pd.to_numeric(fb["amount_value"], errors="coerce").astype("float64")
    idx = fb.index[take | single]
    ex.loc[idx, cols] = fb.loc[idx, cols]
    ex = pd.concat([ex.reset_index(), extract_frame_nonfood(products[is_piece])], ignore_index=True)

    names = ex["input_hash"].map(products.set_index("input_hash")["product_name_original"])
    for i, name in zip(ex.index, names.fillna("").astype(str)):
        name = unicodedata.normalize("NFKC", name)
        m = None if _PER_ONE.search(name) else _BLISTER.search(name)
        if m and 1 < int(m["a"]) * int(m["n"]) <= MAX_PACK:
            ex.loc[i, ["pricing_basis", "amount_value", "standard_unit", "count", "multiplier"]] = [
                "count", float("nan"), "unit", int(m["a"]) * int(m["n"]), 1]
        if _TWO_SIZES.search(name):
            ex.loc[i, "is_bundle"] = True
        if _BOGO.search(name) and pd.isna(ex.at[i, "count"]) | (ex.at[i, "count"] == 1):
            ex.loc[i, "count"] = 2
            if ex.at[i, "pricing_basis"] in (None, "item") or pd.isna(ex.at[i, "pricing_basis"]):
                ex.loc[i, ["pricing_basis", "standard_unit"]] = ["count", "unit"]
    return ex
