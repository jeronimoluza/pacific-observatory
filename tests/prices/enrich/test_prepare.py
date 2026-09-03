import pandas as pd
import pytest

from pandas.testing import assert_frame_equal

from prices.enrich.stages import prepare as prepare_mod
from prices.enrich.stages.prepare import (
    parse_price,
    prepare_input,
    prepare_input_streaming,
)
from prices.enrich.versioning import input_hash


def test_parse_price_us_format():
    assert parse_price("$1,250.00", "USD") == pytest.approx(1250.0)


def test_parse_price_eu_format():
    assert parse_price("1.250,00 €", "EUR") == pytest.approx(1250.0)


def test_parse_price_idr_format():
    # Legacy parse_price handled IDR specially — preserve that.
    assert parse_price("Rp 27.000", "IDR") == pytest.approx(27000.0)
    assert parse_price("Rp 1.234.567,50", "IDR") == pytest.approx(1234567.50)


def test_parse_price_numeric_passthrough():
    assert parse_price(42.5, "USD") == pytest.approx(42.5)
    assert parse_price(100, "USD") == pytest.approx(100.0)


def test_parse_price_empty_and_invalid():
    assert parse_price(None, "USD") is None
    assert parse_price("", "USD") is None
    assert parse_price("not a price", "USD") is None


def test_prepare_dedups_on_input_hash():
    raw = pd.DataFrame(
        [
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "60.00",
            },
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "60.00",
            },
            {
                "product_name": "Pepsi 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "55.00",
            },
        ]
    )
    out = prepare_input(raw)
    assert len(out) == 2
    assert set(out.columns) >= {
        "input_hash",
        "product_name_original",
        "category",
        "country",
        "currency",
        "price",
        "n_rows",
    }
    coke = out[out["product_name_original"] == "Coke 1L"].iloc[0]
    assert coke["n_rows"] == 2
    # Identity for a URL-less row is (name, country, currency) — `category` is
    # deliberately NOT part of it (see _row_input_dict), so that the same product
    # filed under two breadcrumbs still collapses to one input_hash.
    assert coke["input_hash"] == input_hash(
        {
            "product_name_original": "Coke 1L",
            "country": "PH",
            "currency": "PHP",
        }
    )


def test_prepare_threads_declared_unit_through_and_it_is_not_the_dedup_key():
    """`unit` is carried like `category`/`details` (first_non_empty per
    input_hash group), not folded into the dedup identity -- the same product
    scraped twice with the unit populated on only one row must still collapse
    to a single row, and that row must keep the declared unit."""
    raw = pd.DataFrame(
        [
            {
                "product_name": "Ajwan",
                "country": "india",
                "currency": "INR",
                "price": "500",
                "unit": "",
            },
            {
                "product_name": "Ajwan",
                "country": "india",
                "currency": "INR",
                "price": "500",
                "unit": "quintal (100 kg)",
            },
        ]
    )
    out = prepare_input(raw)
    assert len(out) == 1
    assert out.iloc[0]["unit"] == "quintal (100 kg)"


def test_prepare_missing_unit_column_defaults_to_empty_string():
    raw = pd.DataFrame(
        [{"product_name": "Bread", "country": "PH", "currency": "PHP", "price": "1"}]
    )
    out = prepare_input(raw)
    assert out.iloc[0]["unit"] == ""


def test_prepare_parses_all_four_date_shapes_as_utc():
    """The corpus mixes tz-aware ISO, tz-naive ISO, RFC2822 (Common Crawl) and
    compact numeric stamps. Without utc=True pandas returns object dtype and the
    `observation_date=max` aggregation dies with a TypeError."""
    raw = pd.DataFrame(
        [
            {
                "product_name": f"P{i}",
                "country": "PH",
                "currency": "PHP",
                "price": "1.00",
                "date": d,
            }
            for i, d in enumerate(
                [
                    "2026-07-31T13:46:05.226977+00:00",
                    "2026-02-06T12:00:00",
                    "Fri, 06 Feb 2026 12:00:00 GMT",
                    "20251212100333",
                ]
            )
        ]
    )
    out = prepare_input(raw)
    assert len(out) == 4
    assert str(out["observation_date"].dtype) == "datetime64[ns, UTC]"
    assert out["observation_date"].notna().all()


def test_prepare_streaming_matches_whole_frame(tmp_path):
    """The chunked path must be exactly equivalent to the whole-frame path.

    This is the load-bearing test for prepare_input_streaming: `price=median`
    and `_modal_or_empty` do not decompose across arbitrary chunks, and are only
    safe because the shuffle guarantees every row of an input_hash shares a
    bucket. If that invariant ever breaks, this test is what catches it."""
    rows = []
    for i in range(300):
        for rep in range(3):
            rows.append(
                {
                    "product_name": f"Item {i % 47}",
                    "category": "Drinks",
                    "country": ["PH", "VN", "ID"][i % 3],
                    "currency": ["PHP", "VND", "IDR"][i % 3],
                    "channel": ["retailer", "aggregator"][rep % 2],
                    "price": f"{10 + (i % 7) + rep}.50",
                    "date": "2026-02-06T12:00:00+00:00",
                }
            )
    raw = pd.DataFrame(rows)

    whole = prepare_input(raw).sort_values("input_hash").reset_index(drop=True)

    out = tmp_path / "streamed.parquet"
    chunks = [raw.iloc[i : i + 137].copy() for i in range(0, len(raw), 137)]
    assert len(chunks) > 1
    prepare_input_streaming(
        chunks, out, shuffle_dir=tmp_path / "shuffle", verbose=False
    )
    streamed = pd.read_parquet(out).sort_values("input_hash").reset_index(drop=True)

    assert_frame_equal(whole, streamed, check_dtype=True, check_exact=True)


def test_fused_idr_price_is_refused_not_glued():
    """The hypermart archive defect: an archive parser flattened a sale price and
    its struck-through original into one node. Stripping every `Rp` used to glue
    the digit runs, so `Rp 78.875Rp 102.975` parsed as 78,875,102,975 IDR and
    shipped as a trusted $21M/kg unit value. Refuse instead of guessing which
    half is the real price."""
    assert parse_price("Rp 78.875Rp 102.975", "IDR") is None
    assert parse_price("Rp 85.500Rp 99.975", "IDR") is None
    # Case-insensitively, and with no space after the token.
    assert parse_price("RP78.875rp102.975", "IDR") is None


def test_single_token_idr_prices_still_parse():
    """The guard must not cost the healthy path -- one token is the normal case."""
    assert parse_price("Rp 102.975", "IDR") == 102975.0
    assert parse_price("102.975", "IDR") == 102975.0
    assert parse_price("Rp 1.699.000", "IDR") == 1699000.0


def test_other_currencies_stop_at_their_symbol_when_fused():
    """Only a STRIPPED token can fuse digit runs. Every other currency keeps its
    symbol into the numeric search, which halts there -- so a fused string yields
    the first price rather than a glued one. Asserted so the asymmetry is a
    recorded property, not an accident nobody checks."""
    # EUR is EU-format too ('.' thousands), but its symbol is never stripped.
    assert parse_price("€78.875€102.975", "EUR") == 78875.0
    assert parse_price("$78,875$102,975", "USD") == 78875.0


# Slovak-sources defect (2026-09-03): billa_sk/tesco_wolt_sk/metro_sk spiders
# already hand parse_price a clean dot-decimal string (e.g. "1.45"). The old
# EU-format branch unconditionally treated EUR's '.' as a thousands
# separator, so "1.45" -> "145" -> 145.0: every trusted Slovak price shipped
# ~100x too high. The fix decides decimal-vs-thousands from the numeral's own
# shape (a thousands group is always exactly 3 digits) and only falls back to
# the currency's native separator when that shape is genuinely ambiguous.
@pytest.mark.parametrize(
    "currency",
    ["EUR", "ARS", "BRL", "CLP", "COP", "IDR", "VND", "USD", "GBP", "JPY"],
)
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.45", 1.45),  # dot-decimal: never a valid 3-digit thousands group
        ("0.47", 0.47),
        ("145", 145.0),  # no separator: unambiguous either way
    ],
)
def test_parse_price_dot_decimal_shape_wins_over_currency(raw, expected, currency):
    assert parse_price(raw, currency) == pytest.approx(expected)


@pytest.mark.parametrize(
    "currency,decimal_native",
    [
        ("EUR", ","),
        ("ARS", ","),
        ("BRL", ","),
        ("CLP", ","),
        ("COP", ","),
        ("IDR", ","),
        ("VND", ","),
        ("USD", "."),
        ("GBP", "."),
        ("JPY", "."),
    ],
)
def test_parse_price_ambiguous_three_digit_group_uses_currency_native_decimal(
    currency, decimal_native
):
    """The one genuinely ambiguous shape: a single separator with exactly
    three trailing digits could be a thousands group or a 3-decimal amount.
    The currency's NATIVE decimal character always wins the tie; its
    thousands character defaults to thousands."""
    native_thousands = "." if decimal_native == "," else ","
    assert parse_price(f"1{decimal_native}234", currency) == pytest.approx(1.234)
    assert parse_price(f"1{native_thousands}234", currency) == pytest.approx(1234.0)


@pytest.mark.parametrize("currency", ["EUR", "USD", "IDR", "VND"])
def test_parse_price_mixed_separators_last_one_is_decimal(currency):
    assert parse_price("1.234,56", currency) == pytest.approx(1234.56)
    assert parse_price("1,234.56", currency) == pytest.approx(1234.56)


@pytest.mark.parametrize("currency", ["EUR", "USD", "IDR"])
def test_parse_price_repeated_separator_is_always_thousands(currency):
    assert parse_price("1.234.567", currency) == pytest.approx(1234567.0)
    assert parse_price("1,234,567", currency) == pytest.approx(1234567.0)


def test_parse_price_idr_vnd_dot_thousands_regression_still_holds():
    """F1 (2026-07-30): VND '10.000₫' must stay 10000, not collapse to 10.0.
    Guards the fix in this file against re-introducing that regression while
    changing the EUR path."""
    assert parse_price("10.000₫", "VND") == pytest.approx(10000.0)
    assert parse_price("Rp 27.000", "IDR") == pytest.approx(27000.0)


def test_billa_sk_real_payload_price_is_not_inflated_100x():
    """Real captured payload, billa_sk raw_items
    (data/prices/eca/central_europe/slovak_republic/billa_sk/raw_items/
    billa_sk_20260812_223117.jsonl): 'RAUCH ĽADOVÝ ČAJ CITRÓN 1.5L'
    scraped at price "1.45" EUR. The spider already converts the site's
    comma-decimal ("1,45 €") to a dot-decimal string before writing
    raw_items; parse_price must not re-read that dot as a EUR thousands
    separator."""
    assert parse_price("1.45", "EUR") == pytest.approx(1.45)


def test_tesco_wolt_sk_real_payload_price_is_not_inflated_100x():
    """Real captured payload, tesco_wolt_sk raw_items
    (.../tesco_wolt_sk/raw_items/tesco_wolt_sk_20260902_181322.jsonl):
    'Thymos Marco Polo RýchlosĽ 100 g' at price 0.47 EUR. The Wolt
    base spider already divides the API's minor-unit price by 100 (see
    _wolt_base.py); by the time raw_prices.csv round-trips this back to a
    plain string ("0.47"), parse_price must read it as a decimal, not as a
    EUR thousands group."""
    assert parse_price("0.47", "EUR") == pytest.approx(0.47)
    assert parse_price("3.69", "EUR") == pytest.approx(3.69)


def test_metro_sk_real_payload_price_is_not_inflated_100x():
    """Real captured payload, metro_sk raw_items
    (.../metro_sk/raw_items/metro_sk_20260901_235553.jsonl):
    'aro Chlieb toastový tmavý 500 g' at price "1.33" EUR (the
    spider does `str(price_val)` on the API's already-major-unit float)."""
    assert parse_price("1.33", "EUR") == pytest.approx(1.33)
    assert parse_price("1.19", "EUR") == pytest.approx(1.19)


def test_slovak_sources_survive_the_full_prepare_pipeline():
    """End-to-end: a raw_prices.csv-shaped frame for all three Slovak sources
    must come out of prepare_input at the real EUR price, not 100x it."""
    raw = pd.DataFrame(
        [
            {
                "product_name": "RAUCH ĽADOVÝ ČAJ CITRÓN 1.5L",
                "country": "slovak_republic",
                "currency": "EUR",
                "source": "billa_sk",
                "price": "1.45",
            },
            {
                "product_name": "Thymos Marco Polo RýchlosĽ 100 g",
                "country": "slovak_republic",
                "currency": "EUR",
                "source": "tesco_wolt_sk",
                "price": "0.47",
            },
            {
                "product_name": "aro Chlieb toastový tmavý 500 g",
                "country": "slovak_republic",
                "currency": "EUR",
                "source": "metro_sk",
                "price": "1.33",
            },
        ]
    )
    out = prepare_input(raw)
    prices = dict(zip(out["product_name_original"], out["price"]))
    assert prices["RAUCH ĽADOVÝ ČAJ CITRÓN 1.5L"] == pytest.approx(1.45)
    assert prices["Thymos Marco Polo RýchlosĽ 100 g"] == pytest.approx(0.47)
    assert prices["aro Chlieb toastový tmavý 500 g"] == pytest.approx(1.33)


@pytest.mark.parametrize(
    "currency", ["EUR", "ARS", "BRL", "CLP", "COP", "IDR", "VND", "USD", "GBP", "JPY"]
)
@pytest.mark.parametrize("raw_price", ["1.45", "0.47", "145", "399000.0", "3.5"])
def test_parse_price_float_and_string_inputs_agree(raw_price, currency):
    """The actual invariant `prepare.run`/`aggregate._iter_raw_chunks` need:
    for a numeral shape a spider would hand over as a genuine Python float
    (plain, single '.', decimal-digit count that is never exactly 3), parsing
    must return the SAME value whether pandas typed the column as float64 (an
    all-numeric CSV chunk) or object/str (a chunk sharing its window with one
    non-numeric price). This is the property that made the dtype-pin fix
    necessary: without it, the code path -- and therefore the answer -- for
    these EXACT strings depended on what else shared the 2M-row chunk.
    Restricted to shapes with a decimal-digit count other than 3: a lone '.'
    followed by exactly three digits is the one shape genuinely ambiguous
    between a decimal fraction and a thousands group, and no currency-blind
    float reconstruction can stand in as ground truth for it."""
    as_string = parse_price(raw_price, currency)
    as_float = parse_price(float(raw_price), currency)
    assert as_string == pytest.approx(as_float)


def test_prepare_run_price_is_immune_to_chunk_boundary_placement(tmp_path):
    """spar_si regression (2026-09-03): the SAME raw price ("1.28" EUR) parsed
    to 1.28 on one scrape date's build and 128.0 on another. parse_price is
    pure, so identical input producing different output could only mean
    pandas was inferring the `price` column's dtype PER CHUNK in
    `prepare.run` -- an all-numeric 2M-row window reads it as float64, a
    window sharing even one non-numeric price reads it as object/str. Proven
    here by placing the same clean EUR row on both sides of a poisoned-vs-
    clean chunk boundary and asserting it parses identically either way."""
    cols = [
        "url_hash",
        "product_name",
        "price",
        "currency",
        "country",
        "source",
        "date",
        "product_url",
        "product_id",
        "region",
        "subregion",
        "wayback",
        "channel",
        "category",
        "details",
        "unit",
    ]

    def _row(url_hash, name, price):
        return {c: "" for c in cols} | {
            "url_hash": url_hash,
            "product_name": name,
            "price": price,
            "currency": "EUR",
            "country": "slovak_republic",
            "source": "billa_sk",
            "wayback": False,
        }

    target = _row("h1", "RAUCH ĽADOVÝ ČAJ CITRÓN 1.5L", "1.28")
    poison = _row("h2", "not a real price row", "n/a")
    clean1 = _row("h3", "ANOTHER CLEAN ROW 1", "2.50")
    clean2 = _row("h4", "ANOTHER CLEAN ROW 2", "3.75")

    # chunk_rows=2: arrangement A puts the target's 2-row chunk entirely
    # clean; arrangement B puts the target in the SAME 2-row chunk as the
    # non-numeric poison row. Pre-fix, that changed the inferred dtype of
    # `price` for the target's chunk (float64 vs object); post-fix, dtype is
    # pinned so both arrangements take the same code path.
    for rows, label in [
        ([target, clean1, poison, clean2], "clean_chunk"),
        ([poison, target, clean1, clean2], "poisoned_chunk"),
    ]:
        csv_path = tmp_path / f"raw_{label}.csv"
        out_path = tmp_path / f"out_{label}.parquet"
        pd.DataFrame(rows)[cols].to_csv(csv_path, index=False)
        # Inlines what prepare.run() does (dtype-pinned chunked read ->
        # prepare_input_streaming) rather than calling run() itself, so this
        # test can pin shuffle_dir under tmp_path instead of run()'s default
        # (a shared repo-relative directory that a parallel test run, or a
        # real pipeline run, could be writing to at the same time).
        chunks = pd.read_csv(
            csv_path, low_memory=False, chunksize=2, dtype={"price": str}
        )
        prepare_mod.prepare_input_streaming(
            chunks, out_path, shuffle_dir=tmp_path / f"shuffle_{label}", verbose=False
        )
        out = pd.read_parquet(out_path)
        price = out.loc[
            out["product_name_original"] == "RAUCH ĽADOVÝ ČAJ CITRÓN 1.5L", "price"
        ].iloc[0]
        assert price == pytest.approx(1.28), f"{label}: got {price}, expected 1.28"
