# 2026-07-31 — RSS/Atom listing strategy: recon, build, and production start

Goal: add RSS as a first-class **listing strategy** for the text pipeline. Six sonnet
agents (one per region) probed aggregator hosts for working RSS/Atom feeds to learn how
the technology is exposed and how to extract data; the strategy was then built, validated
end-to-end, and started in production.

## What shipped (code)

New listing strategy `type: rss`, mirroring `type: sitemap`:

- `src/text/scrapers/strategies/rss.py` — `RssStrategy`. Fetches each feed URL, parses with
  the lxml **XML** parser, dedups items by `<link>`, optional `url_regex`, optional
  `page_param` pagination. Yields `<item>`/`<entry>` elements through the shared thumbnail
  extractor; the article **body is fetched from the article page** via `article.body`
  (RSS is listing-only, exactly like pagination).
- `src/text/scrapers/strategies/__init__.py` — `rss` → `RssStrategy` dispatch + export.
- `src/text/scrapers/models.py` — `"rss"` added to the `listing.type` whitelist.

Validated end-to-end in production against live feeds (see "Production start" below).

### Load-bearing mechanics (why the YAML looks the way it does)

- **Parse with `BeautifulSoup(content, "xml")`, never `html.parser`** — under `html.parser`,
  `<link>` is a void element and its URL text is dropped. The strategy handles this internally.
- **Selectors are CASE-SENSITIVE** under the XML parser: `pubDate::text`, not `pubdate::text`
  (the latter silently matches nothing). RSS 2.0 → `link::text` / `title::text` / `pubDate::text`;
  Atom → `link::attr(href)` / `title::text` / `published::text`.
- `content:encoded` / `description` (in-feed body) are **not CSS-selectable** (namespaced colon),
  so the current strategy cannot read body from the feed — it fetches the article page. See phase-2.
- **Front-page-only by default.** Feeds serve the latest ~10–100 items. Set `page_param: paged`
  ONLY for WordPress feeds verified to walk older items via `?paged=N`.

Template + quirks are documented in the onboarding skill:
`.claude/skills/onboard-region-newspapers/references/yaml_templates.md` §2b and
`references/known_quirks.md` ("RSS/Atom feed strategy").

## How RSS is displayed, by region (recon)

Five feeds probed per region (~150 hosts total). Headline findings:

| Region | Dominant shape | Body in-feed? | Pagination |
|---|---|---|---|
| SAR | RSS 2.0; WP `/feed/` vs custom CMS (Witter, feeder) | WP: full `content:encoded`; custom: teaser/none | WP `?paged=N` works; custom ignores |
| MENAAP | RSS 2.0 only (no Atom) | Exception, not rule (only Gulf News, Dawn) | Essentially none (only Arab News) |
| SSA | RSS 2.0; WP + Drupal + Nuxt | WP: full; non-WP: truncated lede | WP `?paged=N` works; non-WP ignores |
| LAC | RSS 2.0; **Arc Publishing** `/arc/outboundfeeds/rss/` + WP | **Full body the norm** (`content:encoded`) | Arc ignores (latest ~100); WP works |
| ECA | RSS 2.0; uniformly WP `/feed/` | Usually full; minority teaser-only | WP `?paged=N` works reliably |
| EAP | RSS 2.0; WP + Drupal | ~half full (in `content:encoded` or `description`) | WP works; Drupal/non-standard don't |

**Cross-region laws:**
1. RSS 2.0 is universal; working Atom/RDF feeds are rare-to-absent.
2. WordPress feeds are the sweet spot: full `content:encoded` body **and** working `?paged=N`.
3. Non-WP CMSs (Arc Publishing, Drupal, Nuxt, in-house) commonly ship full body but ignore
   pagination, OR paginate but ship only a teaser — verify both **per host**, never regionally.
4. Verify feeds with a **GET**, not just a HEAD content-type — WAF/CDN hosts return valid XML
   content-type on access-denied/empty stubs (`eleconomista.com.mx`, `pulzo.com`).
5. A feed's own `<language>` tag can lie (Online Khabar declares `en-US`, is Nepali) — always
   set YAML `language:` from the actual content.

### Confirmed feeds (the recon "5 per region")

- **SAR:** dhakatribune.com, thebhutanese.bt, thehindu.com (`/feeder/default.rss`), onlinekhabar.com, island.lk
- **MENAAP:** arabnews.com (`/rss.xml`), tehrantimes.com (`/rss`), dawn.com (`/feeds/home`), gulfnews.com (`/feed`), alroya.om (`/rss`)
- **SSA:** citizen.digital (`/feed.xml`), radiookapi.net, journalducameroun.com, gabonreview.com, journaldebangui.com
- **LAC:** infobae.com + semana.com + nacion.com (Arc `/arc/outboundfeeds/rss/`), dominicantoday.com, prensalibre.com
- **ECA:** kursiv.kz, civil.ge, zdg.md, turkishminute.com, monitor.al
- **EAP:** matangitonga.to (`/rss.xml`), postcourier.com.pg, islandsbusiness.com, freemalaysiatoday.com, rappler.com
- **Maldives (SAR, user-flagged RSS-only, confirmed):** sun.mv (`/feed/`, headline-only), thepress.mv (`/rss`, full Dhivehi body)

## Where RSS actually adds coverage

Most confirmed feeds belong to outlets **already onboarded** via pagination/API — so RSS's
net-new value is concentrated in three buckets:
1. **ECA/Central Asia** — the biggest zero-config region; its WP feeds are all clean gaps.
2. **Deferred `_0_` stubs with a working feed** — e.g. `_0_dawn` (Pakistan), `_0_gulf_news` (UAE):
   custom-code stubs that RSS can revive (both need phase-2 in-feed body — article pages are hard).
3. **Sources with full `content:encoded` but JS/WAF-blocked article pages** — e.g. citizen.digital
   (Nuxt). Also blocked on phase-2.

## Production start

Two genuinely-new live sources onboarded and validated end-to-end (listing-only, body from
the article page):
- `radio_okapi` (DRC, `ssa/central_africa/congo_dem_rep`) — Drupal, no WP API → RSS is the
  right strategy. 50 feed items → 5/5 articles with body.
- `dominican_today` (Dominican Republic, `lac/caribbean/dominican_republic`) — WordPress,
  `?paged=N` works. 10 → 5/5 with body. (A WP REST API config would also work here; RSS is fine.)

**Batch onboarding (ECA ×5 + EAP ×4) produced ZERO new configs** — a sonnet agent found every one
of the 9 targets already covered by an existing, *richer* config (WP REST API or sitemap, which
fetch full bodies directly and paginate). This is the key production finding: **among the recon
set, RSS's net-new onboarding surface is nearly empty.** Where a WP API or working pagination
exists it dominates RSS-listing-only, and it usually already does. RSS earns its keep only in the
three buckets above — and buckets 2–3 (deferred stubs, WAF/JS-blocked) both require phase-2.

Skipped-as-already-covered: kursiv (kz, `kursiv.kz`→`kz.kursiv.media`, WP API), civil_georgia
(WP API en-filter), ziarul_de_garda (WP API), turkish_minute (sitemap), monitor_al (WP API),
post_courier (pagination), matangi_tonga (pagination), islands_business (WP API), rappler (WP API).

_Flagged, not touched_: `eap/pacific_islands/pacific/islands_business.yaml` sets `country: pacific`
in a `pacific/` dir not listed in `regions.yaml` — likely intentional (pan-Pacific magazine), left
for a human taxonomy decision.

## Historical depth via `?paged=N` — the CMS decides, not the outlet (measured)

Empirical probes settled the "do feeds only cover recent months?" question. It is the **CMS**, not
the site, that determines depth:

| Feed | CMS | `?paged=N` | Reach (measured 2026-07-31) |
|---|---|---|---|
| dominican_today | WordPress | walks, 10/pg | today → **May 5** (~95 pages ≈ 950 articles), hard 404 at pg 100 |
| prensalibre | WordPress | walks, **99/pg** | pg 30 → Jun 20 (~3000 articles) and continuing |
| radio_okapi | Drupal | **ignored** | pg 1/10/30/60/100 all return the identical 50 items, same oldest date |

Laws: **WordPress feeds are a real (bounded) backfill mechanism** — months deep, occasionally
further; `posts_per_rss` (10 vs 99) sets how many requests that depth costs, and each site has a
page ceiling (often a few hundred). **Non-WP feeds (Drupal/Arc/Nuxt) are a front-page snapshot with
zero feed-side history.** `RssStrategy` already exploits this via `page_param: paged` (walks until an
empty page). Still shallower than a WP REST API / sitemap, which reach the full archive — so where
those exist, prefer them for deep backfill and use RSS for incremental + medium-depth.

## Phase 2 (BUILT 2026-07-31): in-feed body extraction

Shipped. For feeds carrying `content:encoded`/`description`, the body is read straight from the feed
item and the per-article fetch is skipped — no per-site body selector, immune to article-page WAFs,
and combined with `?paged=N` a WordPress feed becomes a self-contained, months-deep, full-body
collector.

- `RssStrategy.extract_body(el)` — tries `feed_body_tags` (default `content:encoded`, then
  `description`); each holds CDATA-wrapped HTML, so the raw string is re-parsed with `html.parser`
  and flattened to text. Returns `""` when nothing usable → caller falls back to the article page.
- `scraper._maybe_prefetch_feed_body(thumb_elem, thumbnail)` — appends an `ArticleRecord` to
  `prefetched_articles`; the existing generic consumption (`scraper.py` ~1144 / ~1388) streams them
  and only HTML-scrapes the thumbnails *without* an in-feed body. Called from both live element
  loops (`_original_discover_and_scrape_thumbnails` via the orchestrator, and
  `_discover_thumbnails_incremental`).
- Config: `listing.body_in_feed: true` (opt `feed_body_tags: [...]`).
- **Gotcha:** `el.find("content:encoded")` resolves only when the `content:` namespace is declared
  on `<rss>` (always true in real feeds; test fixtures must include `xmlns:content=...`).

Validated end-to-end: `dominican_today` flipped to `body_in_feed: true` → 20/20 rows with full feed
bodies (733–2106 chars, median 1247), dates populated, no article-page fetch. Unit test:
`tests/unit/test_strategies_split.py::test_rss_strategy_factory_and_in_feed_body`.

## All-region gap sweep + production onboarding (2026-07-31)

Six sonnet agents (one per region) hunted outlets **not already onboarded** with a verified RSS
feed, deduped against existing configs. Yield: **57 verified net-new candidates** (ECA 15, SSA 10,
MENAAP 14, EAP 4, LAC 7, SAR 7). SSA/MENAAP were richest in full-body WordPress; EAP/LAC thinnest
(already well-covered). **Dedup gotcha:** the agents' base_url grep missed *quoted* `base_url:`
values — a quote-aware re-dedup across the whole tree caught 1 already-onboarded domain (irna.ir).
Always quote-aware-dedup before onboarding.

**Onboarded 23 new sources (all validated end-to-end), commits `8128c7e6` + `595ca94b`:**
- **21 full-body (`body_in_feed: true`), 21/21 with full text:** ECA hnonline_sk / 444.hu /
  atavatan_turkmenistan; SSA beto.cd / rjdh / midi_madagasikara / habarileo / softpower_ug /
  taarifa_rw / panorama_rw / burundi_times / al_comorya; MENAAP days_of_palestine / sana_sy /
  north_press / syriahr / roya_news (Atom, `feed_body_tags: [content]`); EAP dnc_nc; LAC
  antigua_observer / panama_america (Drupal body-in-description); SAR deshbandhu (280 items/feed).
- **2 listing-only** (teaser feed + generic WP `entry-content` article selector): vanuatu_independent,
  nationwide_jm.
- Configs generated from a template script (deterministic, no LLM variance); `page_param: paged`
  set only where the agent confirmed the feed walks; generic `div.entry-content p` article.body
  fallback (a required field even when the body comes from the feed).

Thin-country wins: Turkmenistan, CAR, Comoros, Burundi, Madagascar, New Caledonia, Antigua, Panama,
and Hindi (Deshbandhu) / Swahili (HabariLeo) / Kinyarwanda (Panorama) coverage.

## Backlog

- **Tier-2 teaser feeds (~34 remaining):** carry only an excerpt, so they need a per-site
  `article.body` selector (assess-newspaper-source). The 5 WP-teaser ones tried by generic selector
  failed on WAF/JS-blocked article pages (actualite.cd, ewnews, guyanachronicle, vishvasnews,
  nknews) — need bespoke handling. The custom-CMS teasers (Czech/Slovak/Slovenian majors, Iranian
  wires, etc.) need per-site selectors. Good candidates for a follow-up onboarding agent wave.
- Revive `_0_dawn`, `_0_gulf_news` and onboard citizen.digital / thepress.mv using `body_in_feed`.
- Maldives: sun.mv is headline-only (no body anywhere); thepress.mv carries Dhivehi body in
  `<description>` → `body_in_feed` target.
- **Data hygiene:** the LAC sweep flagged that an already-onboarded source, `reporter.bz`, now
  resolves to a hijacked feed serving lottery/gambling spam — its config needs review/removal.
