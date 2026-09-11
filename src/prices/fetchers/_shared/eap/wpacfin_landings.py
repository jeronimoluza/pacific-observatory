"""WPacFIN commercial-landings prices -- NOAA PIFSC Western Pacific Fisheries
Information Network, shared across American Samoa, Guam and the Northern
Mariana Islands (CNMI).

WPacFIN is the joint NOAA / territorial-fisheries-agency programme that
compiles commercial fish receipts in the US Pacific territories. The "PR"
dataset is the annual price series: for each island, year and taxon it
publishes pounds sold, the value of that catch, and `RPT_PRICE_LB` -- the
reported price per pound. That is a FIRST-SALE (ex-vessel / dealer-receipt)
price, not a retail shelf price. It is the only island-wide, multi-decade
seafood price series these three territories publish, and in territories
where fish is a staple it is the price of the staple at the point the
market forms.

ENDPOINT (verified live 2026-09-11)
-----------------------------------
    GET apps-pifsc.fisheries.noaa.gov/wpacfin/DAL/DAL-WEB_PIR_SUM_TIMESERIES.php
        ?isAsync=1&displayField=PIR_COMMON_NAME
        &yearStart=<y>&yearEnd=<y>&orderby=year
        &islands[]=<Island>&datasets[]=PR

Plain GET, no auth, no cookie, returns a bare JSON array. Two parameter traps,
both of which fail as a 200 with a JSON error body rather than an HTTP error:

  * `islands[]` takes the island's DISPLAY name and is case-sensitive:
    "American Samoa", "Guam", "CNMI" work; "AS", "GUAM", "AMERICAN SAMOA",
    "AmericanSamoa", "Saipan" all return
    {"outcome": false, "message": "Invalid parameter value for ISLAND."}.
    Hawaii is also served but is outside this project's topology.
  * `datasets[]` accepts only "PR" of the codes tried (CR/EX/LD/CM all
    return "Invalid parameter value for DATASET.").

The response is not paginated and `yearStart=1900&yearEnd=2026` returns the
whole series in one call (2,447 rows across the three islands, 1980-2025), so
the fetcher makes exactly one request per island. A JSON object rather than a
list means the request was rejected and is raised.

`PERIOD` is "YY" on every row -- the series is annual only -- so
`period_kind` is `annual_avg` and `observation_date` is 1 January of `YEAR`.

COICOP
------
`_COICOP_BY_FAMILY` keys on the publisher's own `FAMILY` column (39 values),
with `_COICOP_BY_TAXON` overriding it where one family spans two leaves. Two
places need the override and both are real:

  * Scombridae defaults to 01.1.3.1.5 (tunas, skipjack, bonito) because that
    is what almost all of it is -- skipjack, albacore, yellowfin, bigeye,
    kawakawa and dogtooth tuna are all Thunnini -- but wahoo
    (Acanthocybium solandri) is not a tuna and goes to the pelagic leaf.
  * The publisher's catch-all rows carry a taxonomic rank, not a family, in
    `FAMILY`, so "Animalia (kingdom)" covers both "Invertebrates" and
    "Miscellaneous Seafood", and "Perciformes (order)" covers both
    "Miscellaneous Fishes" and "Pelagic Fish". Those are separated on the
    `SCIENTIFIC_NAME` value, which carries the distinction.

Every row is landed whole and unprocessed, so the fresh leaves (01.1.3.1.x
fish, 01.1.3.4.x crustaceans / molluscs) are the right ones -- none of the
prepared or preserved 01.1.3.3.x / 01.1.3.6.x leaves apply.

Two taxa are deliberately left UNCODED rather than guessed at:
"Unknown/Unclassified" and "Animalia (kingdom): Miscellaneous" (labelled
"Miscellaneous Seafood"), because neither says whether it is a fish or an
invertebrate. Under `coicop_classification: classifier` a null coicop_code is
legitimate -- the row still reaches the corpus and the head decides -- so
they are emitted, not dropped.

`_COICOP_MAP` stamps a per-row COICOP-2018 leaf while the manifests stay
`coicop_classification: classifier`, the same deliberate pairing as
stat_uz_avg_prices: `concatenate`'s `_build_classifier_csv_map` ingests a
fetcher's price_observations.csv ONLY for `classifier` sources, so declaring
`source_curated` would remove these files from the corpus altogether; the
per-row code instead rides through as `declared_coicop_codes` and
short-circuits the head in `classify` (`state=narrow_source`, confidence 1.0).

`item_name` is the publisher's leading common name -- the name a local reader
uses, "Aku", "Onaga", "Mahimahi" -- followed by the scientific name in
parentheses. The taxon is part of the NAME and not only of `notes` because
the lead common name is not unique ("Shrimp" leads both Caridea and Penaeidae
rows, "Parrotfishes" both Scaridae and Scarus spp.) and `_IDENT` keys on
item_name, so without it two taxa in one year would hash identically and the
writer would drop one price as a duplicate. The family and the remaining
local names ride in `notes`.

Emits PriceObservation rows.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://apps-pifsc.fisheries.noaa.gov/wpacfin/DAL/DAL-WEB_PIR_SUM_TIMESERIES.php"
)
_CURRENCY = "USD"
_FIRST_YEAR = 1980

# island display name (the API's own, case-sensitive) -> (country, source_key)
_ISLANDS = {
    "American Samoa": ("American Samoa", "as_wpacfin_landings"),
    "Guam": ("Guam", "gu_wpacfin_landings"),
    "CNMI": ("Northern Mariana Islands", "mp_wpacfin_landings"),
}

_IDENT = ["source_key", "observation_date", "item_name"]

# Publisher's FAMILY column -> COICOP-2018 leaf. All landed whole/fresh.
_COICOP_BY_FAMILY = {
    # --- fish ---
    "Acanthuridae": "01.1.3.1.9",  # surgeonfishes, unicornfishes
    "Actinopterygii (gigaclass)": "01.1.3.1.9",  # "Reef fishes"
    "Berycidae": "01.1.3.1.9",  # alfonsino
    "Bothidae": "01.1.3.1.3",  # lefteye flounders -- flatfish
    "Bramidae": "01.1.3.1.6",  # monchong (pomfret), pelagic
    "Carangidae": "01.1.3.1.6",  # jacks, trevallies, scads, amberjack
    "Cichlidae": "01.1.3.1.1",  # tilapia -- freshwater
    "Coryphaenidae": "01.1.3.1.6",  # mahimahi
    "Etelinae (subfamily)": "01.1.3.1.9",  # deep-slope snappers
    "Holocentrinae (subfamily)": "01.1.3.1.9",  # squirrelfishes
    "Istiophoridae": "01.1.3.1.6",  # marlins, sailfish
    "Kyphosidae": "01.1.3.1.9",  # rudderfishes
    "Labridae": "01.1.3.1.9",  # wrasses
    "Lethrinidae": "01.1.3.1.9",  # emperors
    "Lutjanidae": "01.1.3.1.9",  # snappers
    "Mugilidae": "01.1.3.1.9",  # mullets
    "Mullidae": "01.1.3.1.9",  # goatfishes
    "Myripristinae (subfamily)": "01.1.3.1.9",  # soldierfishes
    "Percoidei (suborder)": "01.1.3.1.9",  # "Bottomfishes"
    "Scaridae": "01.1.3.1.9",  # parrotfishes
    "Scombridae": "01.1.3.1.5",  # tunas / skipjack / bonito (see overrides)
    "Selachii (infraclass)": "01.1.3.1.9",  # sharks
    "Serranidae": "01.1.3.1.9",  # groupers
    "Siganidae": "01.1.3.1.9",  # rabbitfishes
    "Sphyraenidae": "01.1.3.1.9",  # barracudas
    "Thunnini (tribe)": "01.1.3.1.5",  # "Tunas"
    "Xiphiidae": "01.1.3.1.6",  # swordfish
    # --- crustaceans and molluscs ---
    "Achelata (infraorder)": "01.1.3.4.2",  # lobsters
    "Brachyura (infraorder)": "01.1.3.4.2",  # crabs
    "Caridea (infraorder)": "01.1.3.4.1",  # shrimp / prawn
    "Decapodiformes (superorder)": "01.1.3.4.4",  # squids
    "Octopodidae": "01.1.3.4.4",  # octopus
    "Palinuridae": "01.1.3.4.2",  # spiny lobsters
    "Penaeidae": "01.1.3.4.1",  # penaeid shrimp
    "Raninidae": "01.1.3.4.2",  # Kona / spanner crab
    "Scyllaridae": "01.1.3.4.2",  # slipper lobsters
}

# SCIENTIFIC_NAME -> leaf, for taxa whose FAMILY value spans two leaves.
_COICOP_BY_TAXON = {
    "Acanthocybium solandri": "01.1.3.1.6",  # wahoo/ono: Scombridae, not a tuna
    "Animalia (kingdom): Invertebrates": "01.1.3.4.9",
    "Perciformes (order): Miscellaneous": "01.1.3.1.9",
    "Perciformes (order): Pelagic Fish": "01.1.3.1.6",
}

# Rows the publisher itself declines to identify. Emitted uncoded, not dropped.
_UNCODED = frozenset(
    {
        "Unknown/Unclassified",
        "Animalia (kingdom): Miscellaneous",  # "Miscellaneous Seafood"
    }
)


def _coicop_for(row: dict) -> str | None:
    taxon = (row.get("SCIENTIFIC_NAME") or "").strip()
    if taxon in _COICOP_BY_TAXON:
        return _COICOP_BY_TAXON[taxon]
    if taxon in _UNCODED:
        return None
    return _COICOP_BY_FAMILY.get((row.get("FAMILY") or "").strip())


def _item_name(row: dict) -> str:
    """'Aku (Katsuwonus pelamis)' -- leading common name plus the taxon.

    The taxon is part of the name rather than only of `notes` because the
    leading common name is NOT unique: "Shrimp" is the lead name of both
    Caridea and Penaeidae rows, and "Parrotfishes" of both Scaridae (family)
    and Scarus spp. `_IDENT` keys on item_name, so two taxa sharing a lead
    name in one year would hash identically and the writer would silently
    drop one of the two prices as a duplicate.
    """
    taxon = (row.get("SCIENTIFIC_NAME") or "").strip()
    lead = (row.get("NAME_TYPE") or "").strip().split(";", 1)[0].strip()
    if not lead:
        return taxon
    return "%s (%s)" % (lead, taxon) if taxon else lead


def _fetch_island(island: str, cutoff: date) -> pd.DataFrame | None:
    country, source_key = _ISLANDS[island]
    session = get_session()
    params = {
        "isAsync": "1",
        "displayField": "PIR_COMMON_NAME",
        "yearStart": str(_FIRST_YEAR),
        "yearEnd": str(date.today().year),
        "orderby": "year",
        "islands[]": island,
        "datasets[]": "PR",
    }
    resp = session.get(_BASE_URL, params=params, timeout=180)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        # The endpoint reports a rejected parameter as HTTP 200 with
        # {"outcome": false, "message": "Invalid parameter value for ISLAND."}
        raise ValueError("%s: endpoint rejected the request: %r" % (source_key, payload))

    rows: list[dict] = []
    unmapped: set[str] = set()
    for entry in payload:
        raw_price = entry.get("RPT_PRICE_LB")
        if raw_price in (None, "", "."):
            continue
        try:
            price = float(raw_price)
            year = int(entry["YEAR"])
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        obs_date = date(year, 1, 1)
        if obs_date <= cutoff:
            continue

        coicop = _coicop_for(entry)
        taxon = (entry.get("SCIENTIFIC_NAME") or "").strip()
        if coicop is None and taxon not in _UNCODED:
            unmapped.add("%s / %s" % (entry.get("FAMILY"), taxon))

        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "annual_avg",
            "country": country,
            "subnational_area": None,
            "source_key": source_key,
            "coicop_code": coicop,
            "item_name": _item_name(entry),
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "lb",
            "source_url": resp.url,
            "notes": "ex-vessel; %s; family=%s; %s"
            % (taxon, entry.get("FAMILY"), entry.get("NAME_TYPE")),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if unmapped:
        logger.warning(
            "%s: no COICOP mapping for %d taxon(s): %s",
            source_key,
            len(unmapped),
            "; ".join(sorted(unmapped)),
        )
    return pd.DataFrame(rows) if rows else None


def fetch_as_wpacfin_landings(cutoff: date) -> pd.DataFrame | None:
    return _fetch_island("American Samoa", cutoff)


def fetch_gu_wpacfin_landings(cutoff: date) -> pd.DataFrame | None:
    return _fetch_island("Guam", cutoff)


def fetch_mp_wpacfin_landings(cutoff: date) -> pd.DataFrame | None:
    return _fetch_island("CNMI", cutoff)
