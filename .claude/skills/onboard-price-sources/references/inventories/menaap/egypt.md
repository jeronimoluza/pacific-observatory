# Egypt — price source inventory (menaap/north_africa)

_Inventory written: 2026-09-01_

Cold-start inventory. Final F&B sweep, MENAAP agent B. Egypt started this
pass at 4 food sources (`gourmet_egypt`, `hyperone_eg`, `seoudi_eg`,
`spinneys_eg` — all supermarket) out of 8 total, and was ranked LAST on
this agent's worklist (highest existing food count). Examined with
whatever budget remained after working top-down through libya/morocco/
afghanistan/djibouti/tunisia/algeria/pakistan. No WebSearch budget
available this pass (session-wide cap already exhausted by other parallel
agents) — discovery used direct domain guesses off known Egyptian
supermarket chain names.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `metro_markets_eg` | supermarket | Bespoke Laravel, fully server-rendered | Metro Markets — real, live Egyptian supermarket chain (distinct operator from the pre-existing `metro_pk` Pakistan source). Confirmed Tier 1A: `curl_cffi` alone returns full product cards (name+price) in raw HTML; a Playwright render of the same page fired no additional API call, confirming genuine SSR. Homepage exposes only 6 featured top-level categories (`/categoryl1/<Name>/<id>`: Bakery, Confectionary, Dairy, Metro, Paper-Products, Yameesh) — the full "Shop" mega-menu is client-side-only and a `/shop` landing page has no category/product links, so the spider walks these 6 known ids. `Metro` category is genuinely empty (0 products) — correctly handled, not a bug. Verified live: 891 rows, 891/891 distinct product_id and url, 0 blanks, 0 zero/neg prices, EGP 3.5-1229.99, food share ~89% (Confectionary+Dairy+Bakery+Yameesh vs. Paper-Products). Cold re-fetch: 3/3 products matched exactly. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Oscar Stores | oscarstores.com | Genuinely live, NOT built — SignalR-backed Tier 2, out of scope this pass | Major Egyptian chain, real EGP prices confirmed via Playwright (e.g. "Chicken Shawerma 1kg — 264.95 EGP"), ~140 category ids. White-labeled by "Zazome" ("ONLINE STORE POWERED BY ZAZOME"); product data arrives via a SignalR (`signalr/hubs`) WebSocket/long-poll connection, not a capturable XHR/fetch — a standard API-sniff approach finds nothing even though the rendered DOM has real products. Needs a genuine `scrapy_playwright` (DOM-read-after-render) build, not an API. Strongest remaining Egypt lead — see `known_blockers.md` for full detail. |
| Awlad Ragab (اولاد رجب) | awladragab.com | DEAD — no reachable online catalog | ASP.NET WebForms corporate/branch-locator site. The one "offers" page (`/ar/Offers.aspx`) renders only a seasonal marketing banner with zero product cards or prices, despite page JS containing genuine cart-workflow function names — likely gated behind a login-only ordering flow not explored this pass. |
| Imtiaz | imtiaz.com.pk (note: .pk, this was a Pakistan-mislabeled search hit, see pakistan.md) | N/A | See pakistan.md — Imtiaz is a Pakistani chain, not Egyptian; listed here only to flag it was NOT an Egypt candidate despite superficially similar branding to some MENA "No. 1 retail chain" copy patterns. |

## Dead ends worth remembering

- **Egypt's e-commerce landscape includes at least 3 real, live supermarket chains beyond the 4 already onboarded** (Metro Markets — now onboarded, Oscar Stores, and likely more unexplored given the limited domain-guess budget this pass) — Egypt is NOT saturated the way its "4 existing food sources" ranking on the worklist suggested; a fresh pass with WebSearch budget would likely find several more.
- **SignalR/WebSocket-backed product delivery is a distinct trap from the usual SPA-with-hidden-API pattern** — the standard "Playwright network trace, filter for xhr/fetch" technique finds nothing because the data never travels as a discrete HTTP response; only a full DOM-read-after-render (Tier 2) approach works, and pattern-matching a `signalr/hubs` request in a network trace is the tell to switch strategies immediately rather than hunting for a REST/GraphQL call that doesn't exist.
- **A Zazome-branded footer credit ("ONLINE STORE POWERED BY ZAZOME") is a reusable platform fingerprint** for future Egypt/MENA onboarding — worth adding to `platform_fingerprints.md` if a second Zazome tenant is found (this pass didn't confirm whether Zazome is single-tenant-per-deployment or has a shared backend across clients the way Hyperzod/Sixam-Mart do).
