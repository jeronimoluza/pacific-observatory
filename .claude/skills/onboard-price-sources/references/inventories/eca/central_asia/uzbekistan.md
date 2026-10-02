# Uzbekistan — price source inventory

_Inventory written: 2026-09-28_

Region: `eca` / `central_asia`. First inventory file for this country — no prior
version to merge. Written after w40 onboarding pass (run-id `w40`); full probe
detail in `probe_log/w40-uzbekistan.jsonl`.

## Covered at pass start (8 sources; not re-probed unless noted)

| Source | Domain | Role | Scaffolding | Notes |
|---|---|---|---|---|
| `asaxiy_uz` | asaxiy.uz | retailer_sku | spider | dept-store (electronics/books/household) |
| `korzinka_uz` | www.korzinka.uz / catalog.korzinka.uz | retailer_sku | spider | largest chain; storefront WAF-hardened, open API subdomain used instead |
| `dostavo4ka_uz` | dostavo4ka.uz | retailer_sku | spider | Samarkand grocery, food-heavy (div 01/02) |
| `lavka_uz` | lavka.yandex.uz | retailer_sku | spider | Yandex Lavka rapid grocery, Tashkent |
| `makromarket_uz` | makromarket.uz | retailer_sku | spider | Tashkent grocery chain |
| `texnomart_uz` | texnomart.uz | retailer_sku | spider | electronics/appliances/houseware |
| `uzum_uz` | uzum.uz | retailer_sku | spider | largest general marketplace, 23 root categories incl. non-food; lives in the `refactor` worktree only as of this pass — **not yet merged into `onboard-refactor`**, see note below |
| `stat_uz_avg_prices` | stat.uz | official_avg | fetcher | NSC farmers'-market average prices, division 01 only |

**Worktree state note (2026-09-28):** `~/po-worktrees/onboard-refactor` (this
skill's working tree) is missing `dostavo4ka_uz.yaml` and `stat_uz_avg_prices.yaml`
that exist in `~/po` (production), and missing `uzum_uz.yaml` that exists only in
`~/po-worktrees/refactor`. The 8-source count above is per `~/po-worktrees/refactor`,
the most complete tree found. Next session: reconcile before assuming any one
tree's manifest set is ground truth.

Despite 8 sources, the 2026-09-15 trusted build shows only **1 COICOP division**
populated — a likely classifier/gold-support gap (Phase 0.5 territory), not a
sourcing gap; this pass targeted sourcing only, per its brief.

`second_surface_check.py` run 2026-09-28 against 7 of the 8 domains (all but
`uzum.uz`, unavailable in the checked tree): **no second surface found** on any
covered domain.

## Added this pass (w40, 2026-09-28) — 3 sources, all institutional/tariff fetchers

All existing 8 sources are retail-catalog- or food-average-shaped; COICOP divisions
07 (transport), 08 (communication) and 10 (education) had zero price-level coverage.
Marketplace generators (uzum.uz) were already covered and flagged by the
orchestrator as likely to open non-food divisions on their own — deferred to avoid
duplicating uzum's broad classifier-routed catalog; institutional verticals (Phase 2
generator 5) were cheaper and more targeted.

| Source | Domain | Role | Division | Rows (test run) |
|---|---|---|---|---|
| `uz_ucell_tariffs` | ucell.uz | tariff | 08.3.0 | 19 |
| `uz_uzmetro_fares` | uzmetro.uz | tariff | 07.3.2 | 7 |
| `uz_kontrakt_edu_prices` | kontrakt.edu.uz / kontrakt-api.edu.uz | tariff | 10.4.0 | 3,005 |

## Dead ends (this pass)

| Host | Verdict | Lever | Tell |
|---|---|---|---|
| yanada.uz | blocked | curl_cffi chrome124+firefox133 | genuine login wall ("Mijozlar uchun kirish" = customer login) |
| express24.uz | no_catalog | curl_cffi chrome124+firefox133 | service discontinued — page states restaurants moved to Yandex Eda |
| lebazar.uz | no_catalog | curl_cffi + http fallback | domain lapsed, cctld.uz REDEMPTION PERIOD page |
| eda.yandex.uz | blocked | curl_cffi chrome124 | bot-challenge ("Are you not a robot?") |
| olcha.uz / api.olcha.uz | blocked (not re-probed this pass; full ladder incl. Playwright already exhausted 2026-09-05) | — | Cloudflare, http-403/404 |
| medimax.uz | needs_work | curl_cffi chrome124 | real clinic price list (325 price hits) but Tilda absolute-positioned grid — no DOM link between service name and price, needs coordinate-pairing extraction |
| astramed-clinic.com | no_catalog | curl_cffi chrome124 | 200 but zero visible price text in raw HTML |
| bankchart.uz | unreachable | curl_cffi chrome124 | http-522 (Cloudflare origin timeout) on the gas-tariff indicator page |
| minenergy.uz | unreachable | curl_cffi chrome124 | http-503 |
| beeline.uz | needs_work | curl_cffi chrome124 | 200 but client-rendered, zero price text server-side — needs a Playwright network trace (ucell.uz's sibling telco, same fix would likely work) |

## Not pursued, flagged for a future pass

- **OLX.uz** — named by the orchestrator as a likely wide-division marketplace; not
  probed this pass (budget went to institutional verticals instead, and the
  orchestrator's own caution was that big marketplaces open many *non-food*
  divisions the country may not need prioritized right now).
- **beeline.uz** — same shape as `ucell.uz`, likely has an equivalent per-plan
  JSON-LD or API once traced with Playwright; good next-pass candidate for
  redundant 08.3.0 coverage.
- **medimax.uz** — real division-06 (health) catalog, blocked only by extraction
  cost, not access. Worth a dedicated coordinate-pairing pass.
- **Railway (railway.uz / eticket.uzrailpass.uz)** and **electricity/gas tariff
  decree** (lex.uz / lex resolutions) — surfaced by search, not probed: railway
  ticket pricing needs a route/date query interface (harder than a static
  schedule); the electricity/gas tariff needs locating the exact Cabinet of
  Ministers resolution text on lex.uz rather than a news summary. Both are
  plausible division 04.5 / 07.3.1 candidates for a dedicated institutional pass.

## countries.yaml flag

`languages: [en]` for `uzbekistan` looks stubbed — every source in this country
(existing and new) uses `ru` or `uz`, never `en`. Not fixed this pass (out of
scope for a per-country worker; `_resolve_lang()` falls back to the country's
first language only when a manifest omits `language:`, and none here do), but
worth a maintainer look.
