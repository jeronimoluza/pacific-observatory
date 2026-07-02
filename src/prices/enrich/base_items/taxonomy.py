"""coicop_categories.xlsx -> candidate base_items + shared FORM/NEG lexicons.

Three entry points:
  derive_lexicons(nlp)      faithful port of derive_coicop_lexicon.py — distils the
                            shared NEG (div 05/06/12 goods -> EXCLUDE) and FORM
                            (fruit processed-form + div-02 beverage -> OTHER_FORM)
                            lexicons straight from the xlsx, provenance-stamped.
  seed_from_config(path)    load the locked base_item_config.json into
                            base_items.parquet rows (apple/orange/rice) so the loop
                            has working data immediately.
  extract_candidates(nlp)   spaCy noun-chunk CANDIDATE base_items over the deepest
                            leaves (food 6-digit, non-food 5-digit, services
                            skipped). Candidate, not authoritative — refined by the
                            validation loop. The SERVICE filter needs a COICOP
                            review before first production run (see SKIP_DIVS).

data/ coicop_categories.xlsx is READ-only here; outputs go to base_items.parquet
and the two derived lexicon parquets under data/prices/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from prices.enrich.config import REPO_ROOT

from . import store
from .store import BASE_ITEM_COLS, _now, upsert_base_items

XLSX = REPO_ROOT / "data" / "prices" / "_enrich" / "coicop_categories.xlsx"

FORM_LEAVES = {
    "01.2.1.0.0": "juice",
    "01.1.8.3.9": "jams/marmalades/jellies/purees/pastes",
    "01.1.6.7.9": "dried fruit",
    "01.1.8.9.1": "preserved by sugar",
    "01.1.9.3.9": "condiments/sauces",
}
FORM_PARTICIPLES = {"dried", "dehydrated", "preserved", "candied", "glace"}
NEG_DIVS = {"05", "06", "12"}
FOOD_DIVS = {"01", "02"}

# Divisions that are predominantly SERVICES (avoid per user). VERIFY against
# COICOP 2018 before the first production sweep — this is the one place needing
# domain review (plan open item).
SKIP_DIVS = {"04", "07", "08", "09", "10", "11", "13"}
SERVICE_TITLE = re.compile(
    r"\b(service|services|repair|rental|hire|insurance|licen[cs]e|fee|fees|"
    r"subscription|hairdressing|catering|accommodation|tuition|transport|"
    r"maintenance|installation|premium|membership)\b",
    re.I,
)

STOP = {
    "product",
    "products",
    "service",
    "services",
    "good",
    "goods",
    "item",
    "items",
    "other",
    "type",
    "types",
    "kind",
    "part",
    "parts",
    "use",
    "uses",
    "device",
    "devices",
    "preparation",
    "preparations",
    "material",
    "materials",
    "care",
    "personal",
    "equipment",
    "system",
    "unit",
    "form",
    "kg",
    "gram",
    "piece",
    "example",
    "e.g",
    "i.e",
    "etc",
    "group",
    "class",
    "division",
    "category",
    "person",
    "people",
    "purpose",
    "range",
    "number",
    "level",
    "value",
    "fruit",
    "fruits",
    "vegetable",
    "vegetables",
    "plant",
    "plants",
    "food",
    "honey",
    "nut",
    "nuts",
    "peel",
}
GUARD = {
    "china",
    "washington",
    "imported",
    "local",
    "premium",
    "import",
    "light",
    "white",
    "dark",
    "red",
    "green",
    "yellow",
    "gold",
    "golden",
    "black",
    "brown",
    "fresh",
    "whole",
    "large",
    "small",
    "big",
    "mini",
    "jumbo",
    "sweet",
    "sour",
    "medium",
    "extra",
    "loose",
    "can",
    "tin",
    "jar",
    "bottle",
    "roll",
    "bar",
    "box",
    "pack",
    "packet",
    "bag",
    "pouch",
    "carton",
    "case",
    "tray",
    "punnet",
    "bottled",
}
FORM_DROP = {
    "water",
    "ice",
    "mineral",
    "content",
    "source",
    "alcohol",
    "sugar",
    "beverage",
    "production",
    "grape",
}
TAG = re.compile(r"\s*\((?:ND|D|SD|S)\)\s*$")
GOODS = re.compile(r"\((?:ND|D|SD)\)\s*$")


def _plausible_for_division(code) -> str:
    """Physically-possible bases for a leaf's COICOP division (comma-joined for
    the parquet; store._parse_basis maps 'none' -> None on load)."""
    dv = str(code)[:2]
    if dv == "01":
        return "mass,count,item,none"  # food / produce
    if dv == "02":
        return "volume,count,item,none"  # beverages / liquids / oils
    if dv in ("03", "05", "06", "12"):
        return "count,item,none"  # durable / non-food goods
    return "mass,count,item,none"  # default -> produce


def _basis_repr(values) -> str:
    """Config basis list -> the comma-joined lowercased string that
    store._parse_basis round-trips (mirrors _plausible_for_division)."""
    if not values:
        return ""
    return ",".join(str(v).strip().lower() for v in values)


def _clean(x) -> str:
    if pd.isna(x):
        return ""
    return re.sub(r"_x000D_|\r", " ", str(x))


def _bullets(cell) -> list[str]:
    txt = _clean(cell)
    return [b.strip(" *\t") for b in re.split(r"[*\n]", txt) if b.strip(" *\t")]


def _terms(nlp, text: str) -> set[str]:
    """noun/PROPN lemmas + form-participles (lowercased, alpha, len>2)."""
    out = set()
    for t in nlp(text):
        lem = t.lemma_.lower()
        if not t.is_alpha or len(lem) < 3:
            continue
        if t.pos_ in {"NOUN", "PROPN"} or lem in FORM_PARTICIPLES:
            out.add(lem)
    return out


def _read_xlsx() -> pd.DataFrame:
    df = pd.read_excel(XLSX)
    df["code"] = df["code"].astype(str)
    df["dv"] = df["code"].str.slice(0, 2)
    df["ttl"] = df["title"].map(lambda s: TAG.sub("", _clean(s)))
    return df


def _division_titles(df: pd.DataFrame) -> dict[str, str]:
    return {r.code: r.ttl for r in df[df["code"].str.len() == 2].itertuples()}


# --- FORM / NEG shared lexicons (port of derive_coicop_lexicon.py) -------------
def derive_lexicons(nlp) -> tuple[int, int]:
    df = _read_xlsx()
    food_terms = set()
    for _, r in df[df["dv"].isin(FOOD_DIVS)].iterrows():
        food_terms |= _terms(nlp, r["ttl"])

    neg_rows, seen_neg = [], set()
    neg_src = df[df["dv"].isin(NEG_DIVS) & df["title"].astype(str).str.contains(GOODS)]
    for _, r in neg_src.iterrows():
        cand = _terms(nlp, r["ttl"])
        for b in _bullets(r["includes"]):
            cand |= _terms(nlp, b)
        for term in cand:
            if term in STOP or term in GUARD or term in food_terms or term in seen_neg:
                continue
            seen_neg.add(term)
            neg_rows.append({"term": term, "source_code": r["code"]})

    form_rows, seen_form = [], set()

    def _emit(terms, code):
        for term in terms:
            if term in STOP or term in GUARD or term in FORM_DROP or term in seen_form:
                continue
            seen_form.add(term)
            form_rows.append({"term": term, "leaf_code": code})

    for code in FORM_LEAVES:
        row = df[df["code"] == code]
        if not row.empty:
            _emit(_terms(nlp, row.iloc[0]["ttl"]), code)
    for _, r in df[
        df["code"].str.startswith("02.1") & (df["code"].str.count(r"\.") >= 2)
    ].iterrows():
        cand = _terms(nlp, r["ttl"])
        for b in _bullets(r["includes"]):
            cand |= _terms(nlp, b)
        _emit(cand, r["code"])

    neg = pd.DataFrame(neg_rows)
    form = pd.DataFrame(form_rows)
    if not form.empty and not neg.empty:
        neg = neg[~neg["term"].isin(set(form["term"]))].reset_index(drop=True)
    store.FORM_LEXICON_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    neg.to_parquet(store.NEG_LEXICON_PARQUET, index=False)
    form.to_parquet(store.FORM_LEXICON_PARQUET, index=False)
    return len(neg), len(form)


# --- seed base_items from the locked config -----------------------------------
def seed_from_config(config_path: Path) -> pd.DataFrame:
    cfg = json.loads(Path(config_path).read_text())
    df = _read_xlsx()
    dv_titles = _division_titles(df)
    ts = _now()
    rows = []

    def _emit(base_item, base_name, role, code, form_leaf, prov, allowed, plausible):
        rows.append(
            {
                "base_item": base_item,
                "base_name": base_name,
                "language": "en",
                "role": role,
                "coicop_code": code,
                "coicop2digit_title": dv_titles.get(str(code)[:2], ""),
                "allowed_basis": allowed,
                "plausible_basis": plausible,
                "form_leaf": form_leaf or "",
                "provenance": prov,
                "created_at": ts,
            }
        )

    for base, rec in cfg["base_items"].items():
        leaf = rec["default_leaf"]
        allowed = _basis_repr(rec.get("allowed_basis"))
        plausible = (
            _basis_repr(rec["plausible_basis"])
            if rec.get("plausible_basis")
            else _plausible_for_division(leaf)
        )
        for alias in rec["aliases"]:
            _emit(base, alias, "alias", leaf, "", "config:alias", allowed, plausible)
        for tag, terms in rec.get("variety", {}).items():
            for v in terms:
                _emit(
                    base,
                    v,
                    "variety",
                    leaf,
                    "",
                    f"config:variety:{tag}",
                    allowed,
                    plausible,
                )
        for token, form_leaf in rec.get("form", {}).items():
            _emit(
                base, token, "form", leaf, form_leaf, "config:form", allowed, plausible
            )
        for w in rec.get("nonfood", []):
            _emit(base, w, "nonfood", leaf, "", "config:nonfood", allowed, plausible)
        for w in rec.get("species_veto", []):
            _emit(
                base,
                w,
                "species_veto",
                leaf,
                "",
                "config:species_veto",
                allowed,
                plausible,
            )

    return upsert_base_items(pd.DataFrame(rows, columns=BASE_ITEM_COLS))


# --- xlsx noun-chunk CANDIDATE base_items (auto, refined by the loop) ----------
def _leaf_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Deepest leaf per division-depth rule, services skipped."""
    codes = set(df["code"])
    keep = []
    for r in df.itertuples():
        code, dv = r.code, r.dv
        if dv in SKIP_DIVS or len(code) == 2:
            continue
        if SERVICE_TITLE.search(str(r.ttl)):
            continue
        ncomp = code.count(".") + 1
        target = 5 if dv in FOOD_DIVS else 4  # 6-digit food / 5-digit non-food
        if ncomp != target:
            continue
        # leaf = not a strict prefix of a deeper kept code
        if any(c != code and c.startswith(code + ".") for c in codes):
            continue
        keep.append(code)
    return df[df["code"].isin(keep)]


def extract_candidates(nlp) -> pd.DataFrame:
    df = _read_xlsx()
    dv_titles = _division_titles(df)
    leaves = _leaf_codes(df)
    ts = _now()
    rows = []
    for r in leaves.itertuples():
        doc = nlp(r.ttl)
        for ch in doc.noun_chunks:
            head = ch.root
            if head.pos_ not in {"NOUN", "PROPN"} or not head.is_alpha:
                continue
            base_item = head.lemma_.lower()
            if len(base_item) < 3 or base_item in STOP:
                continue
            rows.append(
                {
                    "base_item": base_item,
                    "base_name": head.lower_,
                    "language": "en",
                    "role": "alias",
                    "coicop_code": r.code,
                    "coicop2digit_title": dv_titles.get(r.code[:2], ""),
                    "allowed_basis": "",
                    "plausible_basis": _plausible_for_division(r.code),
                    "form_leaf": "",
                    "provenance": f"xlsx-candidate:title:{r.code}",
                    "created_at": ts,
                }
            )
            for c in ch:
                if c is head or c.pos_ not in {"ADJ", "PROPN", "NOUN"}:
                    continue
                if not c.is_alpha or len(c) < 3 or c.lower_ in STOP | GUARD:
                    continue
                rows.append(
                    {
                        "base_item": base_item,
                        "base_name": c.lower_,
                        "language": "en",
                        "role": "variety",
                        "coicop_code": r.code,
                        "coicop2digit_title": dv_titles.get(r.code[:2], ""),
                        "allowed_basis": "",
                        "plausible_basis": _plausible_for_division(r.code),
                        "form_leaf": "",
                        "provenance": f"xlsx-candidate:variety:{r.code}",
                        "created_at": ts,
                    }
                )
    cand = pd.DataFrame(rows, columns=BASE_ITEM_COLS).drop_duplicates(
        subset=["base_item", "base_name", "role"]
    )
    return cand
