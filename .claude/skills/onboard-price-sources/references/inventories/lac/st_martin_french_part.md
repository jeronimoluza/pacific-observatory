# St. Martin (French part)

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass, which explicitly asked not to be treated as a confirmed
absence)

Before this pass: 0 sources total, 0 food. **Result: 0 shipped.** The genuine
per-country French-language WebSearch the previous file named as "the highest-
yield remaining lever" was run. It did not yield a scrapeable storefront, and
it turned up an explicit statement of absence.

## What the search returned

The chains the previous pass hypothesised are indeed present on the island —
Monoprix (Rue de Hollande, Marigot), Leader Price (14 rue Griselle), Saint
Pierre (6 rue Galisbay), and a Super U — but none has a St-Martin online
grocery catalog:

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Courses U "Drive Saint-Martin" | https://www.coursesu.com/drive-saint-martin | **CLOUDFLARE 403 + wrong Saint-Martin** | Returns a Cloudflare "Just a moment…" interstitial. Beyond the block, this is very likely one of the several metropolitan-France communes named Saint-Martin rather than the Caribbean COM 97150 — the name collides badly in French search and every `coursesu.com` drive slug is a mainland commune. Do not assume this is the island. |
| Monoprix Marigot | (via Mapstr listing) | **NO OWN STOREFRONT** | Ordering surfaced only through a third-party map app listing, not a catalog. |
| Leader Price / Saint Pierre / Match | — | **NO ONLINE CATALOG** | Physical presence confirmed; Saint Pierre's delivery offer is for professional/bulk clients by arrangement. |
| supermarche.tv 97150 page | http://www.supermarche.tv/cp/97150.htm | **EXPLICIT NEGATIVE** | States outright that no general online supermarket serves postal code 97150 and the commune cannot be delivered to by one. |

Carried forward and unchanged: CaribeEats does not cover St Martin or Sint
Maarten (confirmed via `/api/init`, 21 regions, no Martin/Maarten/SXM/MAF),
and Massy Group does not operate in the French Antilles at all.

## Verdict

Now a **searched negative** rather than a tooling artefact. St Martin's food
retail is physical-only; the French-Antilles e-commerce platforms serve
Guadeloupe and Martinique, not this island.

## Next steps

- If French-Antilles coverage is ever wanted, aim at Guadeloupe/Martinique
  (`carrefour.gp`-class domains) as their own countries — not through St
  Martin.
- Beware the Saint-Martin name collision in any future French search.
_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for this
country before this file. Before this pass: 0 sources total, 0 food.

**Examined but inconclusive — not a confirmed "no online grocery" finding.** The
session's shared WebSearch budget (capped session-wide across all 12 parallel
sweep agents, not per-agent) was exhausted by the time this country was reached,
after being spent primarily on Grenada/St Kitts/St Lucia/Dominica discovery. What
was tried instead:

- CaribeEats (backend.caribeeats.com) — the delivery aggregator that yielded wins
  for Grenada, St Kitts, Nevis, and Dominica — does **not** cover St Martin or Sint
  Maarten. Confirmed via its `/api/init` region list (21 regions, none named
  Martin/Maarten/SXM/MAF).
- Massy Group (whose St Lucia storefront shipped as `massy_stores_slu`) does not
  operate in the French Antilles at all (its footprint is Anglophone Caribbean +
  Guyana).
- WebFetch against Google/Bing/DuckDuckGo search-results URLs (attempted as a
  fallback once the WebSearch tool itself was capped) did not return usable
  results — Google/Bing pages rendered no visible result content to the fetch
  summarizer, and DuckDuckGo's HTML endpoint served a bot-CAPTCHA challenge.

**Not tried:** a genuine per-country WebSearch (the highest-yield remaining lever
for this specific gap), and known French-Antilles chain names one would normally
search for by hand (Carrefour Market/Contact, Leader Price, Match — all present in
Guadeloupe/Martinique and plausibly present in St Martin given the shared
department/COM status, but not verified to have a presence or an online storefront
on this island specifically).

## Recommendation for the next agent

Do **not** treat this as an exhausted/negative search like the "already exhausted"
21-country list in the sweep brief — this file records a tooling constraint, not a
confirmed absence. Re-run Phase 2 discovery with a working WebSearch budget,
starting with "Saint Martin Guadeloupe supermarché carrefour leader price" style
queries and the Carrefour/Leader Price online-ordering platforms used elsewhere in
the French Antilles.

---

## Update 2026-09-01 (Tier-1 greenfield pass) — SOURCE SHIPPED

St Martin is no longer a zero-source country. The earlier file's advice was
right: this was a tooling constraint, not a confirmed absence.

| Source | URL | Channel | Status | Notes |
|---|---|---|---|---|
| SXM Les Halles | https://www.sxmleshalles.com/ | supermarket | **SHIPPED — `sxmleshalles_mf`** | Online grocery / villa / yacht provisioning service delivering to both sides of the island. Assigned to the French part on the site's own evidence: the PrestaShop page config reports country `{"iso_code":"FR","call_prefix":33}` and the bare domain redirects to `/fr/`. PrestaShop 1.7, Tier 1A, 148 categories, 24 cards/page, full grocery range plus a deep wine and spirits cellar. **Prices are USD, not the EUR in countries.yaml** — the storefront declares `{"iso_code":"USD"}` machine-readably and renders "$37.00"; SXM's provisioning market is dollarised. |
| Cadismarket | https://cadismarket.com/ | — | **TEMPORARILY DOWN — recheck** | Billed locally as "the first online supermarket in Saint-Martin, 100% Saint-Martin". Serves HTTP 503 with `Retry-After: 3600` and the body "We'll be back soon. We are currently updating our shop" on all three TLS profiles. This is a maintenance page from the host (`x-ws-origin: available`, PHP/7.3.33), NOT anti-bot. Worth re-probing in a future wave — if it comes back it is likely a better St Martin source than SXM Les Halles, being a general grocer rather than a provisioning service. |
| Super U Saint-Martin (Hope Estate) | https://www.magasins-u.com/magasin/superu-saintmartinhopeestate | — | **DEAD — no online ordering** | Physically present in Saint-Martin, but the store page states no drive and no delivery service. |
| coursesu.com/drive-saint-martin | — | — | **NOT APPLICABLE + Cloudflare 403** | Système U national drive platform; the "Saint-Martin" in the slug is a mainland French commune, not the Caribbean collectivity. Also 403s behind Cloudflare. |
| Shop N Drop, SXM Delivery, cmsxm.net | — | — | **DUTCH SIDE / not probed for MAF** | `cmsxm.net` (Carrefour Market / Le Grand Marché) is a live WooCommerce site but is Sint Maarten (Dutch part) — a separate country slug and a **strong Tier-2 lead for `sint_maarten_dutch_part`**, which currently has 1 source and 0 food. Recorded here so the next pass picks it up. |
