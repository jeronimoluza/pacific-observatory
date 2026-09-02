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
