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

## Phase 2 (planned, not built): in-feed body extraction

For feeds carrying full `content:encoded`/`description`, extract the body straight from the feed
item and skip the article-page fetch. This is the unlock for the deferred stubs and WAF/JS-blocked
sources (buckets 2–3 above), and is more robust everywhere (no per-site body selector, immune to
article-page WAFs). Implementation shape: route the feed body to `prefetched_articles` exactly as
the API strategy does at `scraper.py:428-447`, gated on a config flag (e.g. `body_in_feed: true`)
and a namespace-aware extractor (`element.find("content:encoded")`, not CSS `select`). Bounded,
well-understood change; deferred to keep this pass scoped to the listing strategy.

## Backlog

- Build phase-2 in-feed body; then revive `_0_dawn`, `_0_gulf_news`, and onboard citizen.digital.
- Onboard the remaining confirmed feeds that are genuine gaps (esp. more ECA/Central Asia).
- Maldives market: sun.mv is headline-only (no body via any path) — RSS gives dates+titles only;
  thepress.mv carries Dhivehi body in `<description>` → a phase-2 in-feed-body target.
- Deep backfill (`--rebuild`) is inherently shallow for RSS (front-page-only) — pair RSS with the
  existing sitemap/pagination strategies where historical depth is needed.
