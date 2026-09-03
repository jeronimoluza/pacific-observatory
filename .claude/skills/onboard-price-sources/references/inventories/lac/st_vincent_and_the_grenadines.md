# St. Vincent and the Grenadines

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass, which explicitly asked not to be treated as exhausted)

Before this pass: 0 sources total, 0 food. **Result: 0 shipped.** The fresh
per-country WebSearch the previous file asked for was run, and it did not
surface an online storefront.

## What the search returned

Every SVG grocery result is a **Facebook page or a directory listing**, not a
storefront:

| Candidate | Where it lives | Status |
|---|---|---|
| C.K. Greaves Supermarkets | facebook.com/greavessupermarkets, insandoutsofsvg.com listing | **FACEBOOK / DIRECTORY ONLY** — Upper Bay Street Kingstown, in-store pickup only per its listing. No independent domain surfaced. |
| Bonadie Supermarket #2 | facebook.com/bonadieno2 | **FACEBOOK-ONLY** — Middle Street & Egmont Street, Kingstown. |
| EHub SVG | facebook.com/eHubSVG | **FACEBOOK-ONLY** — a personal grocery-shopping and island-wide delivery service, i.e. a concierge shopper, not a catalog with prices. |
| Massy Stores SVG | https://www.massystoressvg.com/ | **BROCHURE** — carried forward and unchanged: static WordPress, `?rest_route=/wc/store/v1/products` returns `rest_no_route`. The `shopmassystores<code>.com` pattern used by the Barbados / Trinidad / St Lucia storefronts does not exist for SVG (`shopmassystoresvct.com`, `massystoresvct.com` both NXDOMAIN). |
| CaribeEats | backend.caribeeats.com | **NOT APPLICABLE** — carried forward: its `/api/init` region list (21 regions) has no St Vincent entry. |

## Verdict

This is now a **searched negative**, not an unexamined country. SVG's grocery
retail transacts through Facebook pages and phone orders; there is no
scrapeable catalog. That is a different and stronger statement than the
2026-09-01 file could make.

## Next steps

- Watch for Massy Group extending its `shopmassystores*` storefront platform
  to SVG — Massy already runs physical stores in Kingstown and Arnos Vale, and
  the platform exists for four sibling markets. That is the single most likely
  future win, and it costs nothing to re-check the domain pattern.
_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for this
country before this file. Before this pass: 0 sources total, 0 food.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Massy Stores SVG (main brand site) | https://www.massystoressvg.com/ | — | **DEAD — brochure only, no shop** | Massy Group operates physical stores in Kingstown and Arnos Vale, but this domain is a static WordPress/AIOSEO corporate site with no WooCommerce shop route (`?rest_route=/wc/store/v1/products` returns `rest_no_route`). See `known_blockers.md` § "Brochure-only WordPress / no online store". Confirmed the `shopmassystores<code>.com` naming pattern used by the Barbados/Trinidad/St Lucia storefronts does NOT exist for SVG (`shopmassystoresvct.com`, `massystoresvct.com` both NXDOMAIN). |
| CaribeEats | https://backend.caribeeats.com/api/init | — | **NOT APPLICABLE** | Platform's region list (21 regions, confirmed via `/api/init`) does not include St Vincent/SVG/VCT under any spelling tried. |

**Examined but inconclusive beyond the above — not a confirmed "no online grocery"
finding.** The session's shared WebSearch budget (capped session-wide across all 12
parallel sweep agents) was exhausted before a fresh per-country search could be run
for St Vincent specifically. WebFetch against Bing/Google/DuckDuckGo search-results
URLs (attempted as a fallback) returned no usable result content — see
`st_martin_french_part.md` for the same tooling-constraint note, which applies
identically here.

## Recommendation for the next agent

Do not treat this as exhausted/negative. Re-run Phase 2 discovery with a working
WebSearch budget. St Vincent shares a retail ecosystem with the rest of the Eastern
Caribbean (Massy operates physical stores here, CK Greaves and other regional names
are plausible), so a fresh search plus the CaribeEats-style delivery-aggregator
pattern (which worked for Grenada/St Kitts/Nevis/Dominica) are the two highest-yield
next moves.

---

## Update 2026-09-01 (Tier-1 greenfield pass) — SOURCE SHIPPED

St Vincent is no longer a zero-source country.

| Source | URL | Channel | Status | Notes |
|---|---|---|---|---|
| C.K. Greaves & Company | https://www.ckgreaves.com/ | supermarket | **SHIPPED — `ckgreaves_vc`, 14,842 rows** | Vincentian grocery chain founded 1954 (Upper Bay Street, Kingstown; three locations, third opened Pembroke 2012). A genuine full-catalogue webshop: 30 departments, 15,828 stated products, prices in XCD. Full grocery range including fresh produce (201), dairy (600), meat (280), seafood (14), bread & bakery (65), plus household (2,443), beauty (1,705) and snacks (1,679). Tier 1A, WordPress "supershop" theme, permissive robots.txt. |
| VincyCart | https://vincycart.com/ | — | **VIABLE BUT NOT SHIPPED — catalogue too small** | Real Laravel/Livewire diaspora gifting storefront ("order groceries for loved ones in SVG"), server-rendered, EC$ prices, genuine grocery SKUs. But the entire catalogue is **34 products** — confirmed two ways: `?per_page=100` reports "Showing 1-34 of 34", and the distinct product-slug count is exactly 34. Superseded by C.K. Greaves at 437x the size. Would be a legitimate second source if a wider SVG basket is ever wanted. |
| eHub SVG | http://www.ehubsvg.com/ | — | **DEAD — account suspended** | Personal-shopper delivery service. HTTPS fails with an SSL hostname mismatch on both `ehubsvg.com` and `www.ehubsvg.com`; over HTTP it redirects to `/public/email-suspension`. |
| Massy Stores SVG | https://www.massystoressvg.com/ | — | **DEAD — brochure only (RE-VERIFIED)** | The earlier finding stands. Re-probed this pass: the homepage does carry WooCommerce/wp-content markers, but all three Store API routes (`/wp-json/wc/store/v1/products`, `/?rest_route=…`, `/wp-json/wc/store/products`) still return `rest_no_route`. Theme markers are not a shop. |

**Why this was missed twice.** The earlier pass recorded SVG as "0 sources,
WebSearch budget exhausted" after checking only Massy Stores SVG and CaribeEats.
C.K. Greaves — the country's obvious grocery chain, with a live webshop — was
never probed. It surfaced on the first search of this pass. The recorded dead
ends were accurate; the problem was that the search stopped after two names.
