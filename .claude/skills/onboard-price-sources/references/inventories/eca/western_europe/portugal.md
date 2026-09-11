# Portugal

_Inventory written: 2026-09-11_

Scope note: three-candidate pass from the onboard4 backlog shard (Portugal ranked
118 of 257 COICOP leaves empty). All three failed, for three different reasons —
recorded so they are not re-probed.

Already onboarded before this pass: `continente_pt`, `auchan_pt`, `pingodoce_pt`
(all supermarket), `koro_pt`, plus the Eurostat electricity/gas/PPP fetchers.

| Candidate | URL | Outcome |
|---|---|---|
| Pingo Doce / Mercadão | https://www.mercadao.pt/store/pingo-doce | **Already onboarded — de-duplicate, do not probe.** The URL 301s unconditionally to `www.pingodoce.pt`, which is shipped as `pingodoce_pt`. That manifest documents the same pivot (the Mercadão white-label storefront was retired/merged). Any future candidate list carrying this URL resolves to an existing source. |
| Lidl Portugal | https://www.lidl.pt/ | **Dead — no prices published on the web.** Everything cheap says otherwise: `/static/sitemap.xml` → `/p/export/PT/pt/product_sitemap.xml.gz` yields 263 real product PDPs, each with three JSON-LD blocks including a `Product`. But the `Offer` node has `priceCurrency: EUR`, `availability: InStoreOnly` and **no `price` key**; zero `€` matches in 359 KB of PDP HTML. In-store assortment pages, not a webshop. See `known_blockers.md`. |
| Super Save | https://www.supersave.pt/ | **Not a retailer.** It is the landing page for a price-*comparison* app (own JSON-LD: `@type: MobileApplication`; FAQ: "o melhor comparador de preços de supermercados em Portugal"). `app.supersave.pt` serves a Google Play redirect. App-only. See `known_blockers.md`. |

**Gaps for the next run.** No `official_avg` or `cpi_benchmark` source of
Portuguese origin (INE Portugal publishes both, and INE has a public REST API —
that is the obvious unclaimed win, and it is a fetcher). On retail, Mercadona
Portugal, Intermarché and Minipreço are all untried; Super Save's own FAQ names
them as the comparator's inputs, which is a free candidate list.
