"""Indonesia Pertamina non-subsidi announcements (split from the legacy indonesia.py).

Ported unchanged from legacy pacific-observatory
src/cpi/fuel_prices/fetchers/indonesia.py (dev 2d60a353); split only to stay
under the 500-line limit. Shared constants/helpers live in indonesia.py.
"""

from datetime import date, timedelta

import pandas as pd

from fuel.fetchers._shared.eap.indonesia import (
    _ID_PERTAMINA_EARLIEST_KNOWN,
    _ID_PERTAMINA_HEADERS,
    _ID_PERTAMINA_PENGUMUMAN_URL,
    _ID_PERTAMINA_SPECIAL_URLS,
    _collect_pertamina_listing_candidates,
    _load_pertamina_announcement,
    _month_start,
    _next_month,
    _parse_idr_price,
    _pertamina_default_url,
    _pertamina_has_full_coverage,
    _pertamina_url_priority,
    _previous_month,
)
from fuel.fetchers._shared.eap.legacy import make_hash, make_template


def fetch_id_pertamina_pengumuman(cutoff: date) -> pd.DataFrame:
    """Fetch Indonesia fuel prices from Pertamina Pengumuman announcement tables."""
    print("  [id_pertamina] Fetching Pertamina Pengumuman tables (Playwright)...")
    print(f"  [id_pertamina] Cutoff: {cutoff}")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  [id_pertamina] Playwright not available: {e}")
        return pd.DataFrame()

    candidate_map: dict[date, list[str]] = {}

    def add_candidate(eff_date: date, url: str) -> None:
        urls = candidate_map.setdefault(eff_date, [])
        if url not in urls:
            urls.append(url)

    scan_start = max(
        _previous_month(_month_start(cutoff)), _ID_PERTAMINA_EARLIEST_KNOWN
    )
    scan_end = _month_start(date.today())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(
                _ID_PERTAMINA_PENGUMUMAN_URL,
                wait_until="networkidle",
                timeout=60_000,
            )
            listing_candidates = _collect_pertamina_listing_candidates(page, scan_start)
            print(
                f"  [id_pertamina] Listing yielded {len(listing_candidates)} candidate links"
            )
            for eff_date, url in listing_candidates:
                add_candidate(eff_date, url)
        except Exception as e:
            print(f"  [id_pertamina] Pengumuman listing load error: {e}")

        # Also probe predictable monthly slugs so older announcements are not missed.
        d = scan_start
        while d <= scan_end:
            add_candidate(d, _pertamina_default_url(d))
            for extra_url in _ID_PERTAMINA_SPECIAL_URLS.get(d, []):
                add_candidate(d, extra_url)
            d = _next_month(d)

        announcements: list[
            tuple[date, list[tuple[str, list[str], list[list[str]]]]]
        ] = []
        for eff_date in sorted(candidate_map):
            urls = sorted(candidate_map[eff_date], key=_pertamina_url_priority)
            loaded_pages: list[tuple[str, list[str], list[list[str]]]] = []
            for url in urls:
                headers, rows = _load_pertamina_announcement(page, url)
                if headers and rows:
                    loaded_pages.append((url, headers, rows))
                    if _pertamina_has_full_coverage(url):
                        break
            if loaded_pages:
                announcements.append((eff_date, loaded_pages))

        browser.close()

    if not announcements:
        print("  [id_pertamina] No announcement tables found")
        return pd.DataFrame()

    announcements.sort(key=lambda x: x[0])
    print(
        "  [id_pertamina] Announcements found: "
        + ", ".join(d.strftime("%Y-%m-%d") for d, _ in announcements)
    )

    tmpl = make_template(
        country="Indonesia",
        wb_iso3="IDN",
        source_key="id_pertamina_pengumuman_non_subsidi",
        source_name="Pertamina Pengumuman Non-Subsidi",
        source_url=_ID_PERTAMINA_PENGUMUMAN_URL,
        currency="IDR",
        unit="L",
        publication_frequency="monthly",
        observation_method="reported",
        tax_status="tax_inclusive",
    )
    all_rows: list[dict] = []

    today = date.today()
    for idx, (eff_date, pages) in enumerate(announcements):
        next_eff_date = (
            announcements[idx + 1][0] if idx + 1 < len(announcements) else None
        )
        regime_end = (
            today
            if next_eff_date is None
            else min(today, next_eff_date - timedelta(days=1))
        )
        fill_start = max(eff_date, cutoff + timedelta(days=1))
        if regime_end < fill_start:
            continue

        parsed_price_map: dict[
            tuple[str, str, str, str, int | None], tuple[float, str]
        ] = {}
        for url, headers, rows in pages:
            header_map = []
            for h in headers:
                key = h.upper().strip()
                header_map.append(_ID_PERTAMINA_HEADERS.get(key))

            for cells in rows:
                if not cells:
                    continue
                wilayah = cells[0].strip() if cells else None
                if not wilayah:
                    continue
                for cell_idx, cell in enumerate(cells[1:], start=1):
                    if cell_idx >= len(header_map):
                        continue
                    meta = header_map[cell_idx]
                    if not meta:
                        continue
                    price = _parse_idr_price(cell)
                    if price is None:
                        continue
                    prod_name, family, qg, ron = meta
                    key = (wilayah, prod_name, family, qg, ron)
                    parsed_price_map.setdefault(key, (price, url))

        parsed_prices = [
            (*key, price, source_url)
            for key, (price, source_url) in parsed_price_map.items()
        ]

        if not parsed_prices:
            print(f"  [id_pertamina] No price rows parsed for {eff_date}")
            continue

        n_days = (regime_end - fill_start).days + 1
        source_labels = ", ".join(dict.fromkeys(url for *_, url in parsed_prices))
        print(
            f"  [id_pertamina] Forward filling {n_days} days "
            f"({fill_start} → {regime_end}) × {len(parsed_prices)} combos from {source_labels}"
        )

        d = fill_start
        while d <= regime_end:
            for wilayah, prod_name, family, qg, ron, price, source_url in parsed_prices:
                r = tmpl.copy()
                r.update(
                    {
                        "subnational_area": wilayah,
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(eff_date),
                        "effective_to": str(regime_end),
                        "observation_date": str(d),
                        "source_url": source_url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)
            d += timedelta(days=1)

    print(f"  [id_pertamina] {len(all_rows)} rows total")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
