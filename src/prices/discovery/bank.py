"""Per-country query banks: an LLM writes the vocabulary, code writes the queries.

A bank is `banks/<country>.yaml`: the country's names, cities, currency words
and, per language, the local terms for each kind of price source. `expand`
crosses those terms with fixed templates. Writing ~30 lines of vocabulary per
country instead of ~200 queries keeps the LLM step small and reviewable, and
the expansion is deterministic, so a query's id is stable across re-loads and
the run ledger never repeats it.

A language may leave a term out where locals search in another language
(Sango has no common word for "supermarket"); English must define every term,
because it is the fallback everywhere.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BANKS_DIR = HERE / "banks"
COUNTRIES_YAML = HERE.parents[1] / "configs" / "countries.yaml"
CLDR = json.loads((HERE / "cldr_languages.json").read_text(encoding="utf-8"))["by_iso3"]

# term -> candidate kind. Retail terms are searched per city; the rest only
# at country level, since tariffs and bulletins are national.
RETAIL = (
    "online_shop",
    "supermarket",
    "pharmacy",
    "electronics",
    "phone_shop",
    "building_materials",
    "cosmetics",
    "clothing",
    "furniture",
    "food_delivery",
)
NATIONAL = (
    "fuel_price",
    "electricity_tariff",
    "water_tariff",
    "mobile_data_plans",
    "transport_fares",
    "market_prices",
    "consumer_price_index",
    "classifieds",
)
GENERIC = ("price", "buy_online", "price_list")
TERMS = RETAIL + NATIONAL + GENERIC

# Pass-1 queries: the generic shop searches most likely to surface a
# country's biggest online sellers. Each template is tried in every language,
# in priority order, until 20 distinct queries exist -- a sparse second
# language (Nigerian Pidgin defines almost nothing) then cannot leave pass 1 short.
TOP20_TEMPLATES = (
    ("online_shop", "{online_shop} {name}"),
    ("supermarket_capital", "{supermarket} {capital}"),
    ("buy_online", "{buy_online} {name}"),
    ("supermarket_price", "{supermarket} {name} {price}"),
    ("pharmacy_price", "{pharmacy} {capital} {price}"),
    ("electronics_price", "{electronics} {name} {price}"),
    ("price_list", "{price_list} {currency} {name}"),
    ("food_delivery", "{food_delivery} {capital}"),
    ("classifieds", "{classifieds} {name}"),
    ("fuel_price", "{fuel_price} {name}"),
    ("phone_shop_price", "{phone_shop} {capital} {price}"),
    ("market_prices", "{market_prices} {name}"),
    # Enough extra shapes that a one-language country still reaches 20.
    ("online_shop_capital", "{online_shop} {capital}"),
    ("supermarket_country", "{supermarket} {name}"),
    ("pharmacy_country", "{pharmacy} {name}"),
    ("electronics_capital", "{electronics} {capital} {price}"),
    ("cosmetics_price", "{cosmetics} {name} {price}"),
    ("building_materials_price", "{building_materials} {capital} {price}"),
    ("furniture_capital", "{furniture} {capital}"),
    ("mobile_data_plans", "{mobile_data_plans} {name}"),
)

MAX_QUERIES = 220
MAX_CHARS = 100


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def query_id(country: str, text: str) -> str:
    return hashlib.sha1(f"{country}|{_norm(text)}".encode()).hexdigest()[:12]


def country_meta(country: str) -> dict:
    meta = yaml.safe_load(COUNTRIES_YAML.read_text(encoding="utf-8"))
    if country not in meta:
        raise KeyError(f"{country} is not in {COUNTRIES_YAML}")
    return meta[country]


def expected_languages(country: str, config_languages: list[str]) -> list[str]:
    """Search languages, in priority order.

    Languages the country's existing sources are written in come first (sites
    really publish in them), then English, then any CLDR language spoken by
    >= 10% of people. Config values that are not language codes
    ("multilingual", "chinese_traditional") are dropped.
    """
    cldr = CLDR.get(country_meta(country).get("iso3", ""), [])
    codes = [lang for lang in config_languages if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]+)?", lang)]
    local = sorted(
        (lang for lang in codes if lang != "en"),
        key=lambda lang: cldr.index(lang) if lang in cldr else len(cldr),
    )
    order = [*local, "en", *cldr]
    return list(dict.fromkeys(order))


def load_vocab(country: str) -> dict:
    return yaml.safe_load((BANKS_DIR / f"{country}.yaml").read_text(encoding="utf-8"))


def _fill(template: str, terms: dict, slots: dict) -> str | None:
    needed = re.findall(r"{(\w+)}", template)
    values = {}
    for key in needed:
        if key in slots:
            values[key] = slots[key]
        elif terms.get(key):
            values[key] = terms[key]
        else:
            return None
    return template.format(**values)


def expand(country: str, vocab: dict) -> list[dict]:
    """Vocabulary -> ordered queries. Earlier queries win the per-country cap."""
    langs = list(vocab["terms"])
    # The first city is the main commercial city, which is not always the
    # capital (Lagos, not Abuja); it fills the `{capital}` slot.
    capital = vocab["cities"][0]
    currency = vocab["currency_words"][0]

    def slots(lang: str) -> dict:
        return {
            "name": vocab["names"].get(lang) or vocab["names"]["en"],
            "capital": capital,
            "currency": currency,
        }

    out: list[dict] = []
    seen: set[str] = set()

    def add(text: str | None, lang: str, template: str, tier: str) -> None:
        if not text or _norm(text) in seen:
            return
        seen.add(_norm(text))
        out.append({"text": text, "lang": lang, "template": template, "tier": tier})

    for name, template in TOP20_TEMPLATES:
        for lang in langs:
            if sum(q["tier"] == "top20" for q in out) == 20:
                break
            add(_fill(template, vocab["terms"][lang] or {}, slots(lang)), lang, name, "top20")

    for lang in langs:
        terms, s = vocab["terms"][lang] or {}, slots(lang)
        for term in RETAIL:
            if not terms.get(term):
                continue
            add(f"{terms[term]} {s['name']}", lang, term, "deep")
            for city in vocab["cities"]:
                add(f"{terms[term]} {city}", lang, f"{term}_city", "deep")
            if terms.get("price"):
                add(f"{terms[term]} {s['name']} {terms['price']}", lang, f"{term}_price", "deep")
        for term in NATIONAL:
            if terms.get(term):
                add(f"{terms[term]} {s['name']}", lang, term, "deep")
                add(f"{terms[term]} {currency} {s['name']}", lang, f"{term}_currency", "deep")
    return out[:MAX_QUERIES]


def validate(country: str, vocab: dict, config_languages: list[str]) -> list[str]:
    """Problems that block loading. Empty list = the bank can load."""
    errors = []
    if vocab.get("country") != country:
        errors.append(f"country field {vocab.get('country')!r} != {country!r}")
    for key in ("names", "cities", "currency_words", "terms"):
        if not vocab.get(key):
            errors.append(f"missing {key}")
    if errors:
        return errors
    want = expected_languages(country, config_languages)
    got = list(vocab["terms"])
    if got != want:
        errors.append(f"languages {got} != expected {want} (order matters)")
    unknown = {t for terms in vocab["terms"].values() for t in (terms or {})} - set(TERMS)
    if unknown:
        errors.append(f"unknown terms {sorted(unknown)}")
    missing_en = [t for t in TERMS if not (vocab["terms"].get("en") or {}).get(t)]
    if missing_en:
        errors.append(f"English must define every term; missing {missing_en}")
    if errors:
        return errors
    queries = expand(country, vocab)
    n_top = sum(q["tier"] == "top20" for q in queries)
    if n_top != 20:
        errors.append(f"{n_top} top20 queries, need 20")
    long = [q["text"] for q in queries if len(q["text"]) > MAX_CHARS]
    if long:
        errors.append(f"queries over {MAX_CHARS} chars: {long[:3]}")
    return errors


def load_bank(con: sqlite3.Connection, country: str) -> dict:
    row = con.execute("SELECT languages FROM countries WHERE country = ?", (country,)).fetchone()
    if row is None:
        raise KeyError(f"{country} is not seeded; run `po prices discovery seed` first")
    config_languages = (row["languages"] or "").split(",") if row["languages"] else []
    vocab = load_vocab(country)
    errors = validate(country, vocab, config_languages)
    if errors:
        return {"country": country, "errors": errors}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    queries = expand(country, vocab)
    inserted = 0
    for q in queries:
        cur = con.execute(
            """INSERT OR IGNORE INTO queries
               (query_id, country, text, lang, template, tier, origin, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'bank', ?)""",
            (
                query_id(country, q["text"]),
                country,
                q["text"],
                q["lang"],
                q["template"],
                q["tier"],
                now,
            ),
        )
        inserted += cur.rowcount
    return {"country": country, "errors": [], "queries": queries, "inserted": inserted}
