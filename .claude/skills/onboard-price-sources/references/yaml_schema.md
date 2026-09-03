# YAML manifest schema

The manifest sits at `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` (per-country) or `src/prices/configs/_global/<source>.yaml` (truly global aggregate series). Path-derived fields (region, subregion, country, source) **must not appear in the body** — the loader extracts them from the path; duplicating them breaks discovery.

## Body fields

| Field | Required | Notes |
|---|---|---|
| `scaffolding` | yes | `spider` or `fetcher` |
| `extraction_pattern` | yes | One of `scrapy_html`, `scrapy_api`, `scrapy_playwright`, `scrapy_listing`, `rest_api`, `tabular_download`, `pdf`, `html_scrape` |
| `analytical_role` | yes | One of `retailer_sku`, `official_avg`, `tariff`, `cpi_benchmark`, `aggregate_proxy` |
| `coicop_classification` | yes | One of `classifier`, `source_curated`, `publisher_labeled` |
| `channel` | **yes — the key must be present even when the value is `null`** | From the `Channel` enum in `src/prices/enrich/schemas.py`. `null` for non-retail sources. An out-of-enum value *or* an omitted key breaks global `prices collect --list`, not just this source. |
| `coicop_codes` | conditional | Required when `coicop_classification ∈ {source_curated, publisher_labeled}`. List of codes the source's rows carry (e.g. `["07.2.2", "04.5.4"]` for fuel). Absent for `classifier`. |
| `source_key` | yes for `fetcher` | Stable identifier; matches the fetcher function name (`fetch_<source_key>`) |
| `spider` | yes for `spider` | The Scrapy spider's `name` attribute |
| `module` | yes for `fetcher` | Dotted path under `src/prices/fetchers/`, package prefix omitted — `eap.southeast_asia.indonesia.pertamina`, `_shared.eap.shopee`, `_global.wb_pink_sheet` |
| `function` | yes for `fetcher` | Name of the public callable inside `module` |
| `url` | yes | Canonical landing page or API endpoint |
| `language` | yes | ISO 639-1 code of the site's primary listing/page language |
| `cadence` | yes | `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `irregular` |
| `fallback_date` | yes for `fetcher` | Earliest date the fetcher can backfill to (ISO). Used as the cutoff on first run, so set it back far enough that run 1 returns real history. |
| `notes` | no | Free-form maintainer note — anything non-obvious |
| `active` | no | `false` only when intentionally disabled |
| `archive_prefix` | recommended for `spider` | String cap on the Common Crawl index scan. **Bare registrable host, no scheme** — see the rules below. |
| `archive_path_re` | recommended for `spider` | Regex selecting product URLs out of what the prefix admits. See below. |

Fields explicitly **not** in the schema: `source_type` (the old A–F letters), `priority` (PPP wants all sources, not a ranking), `observation_level` (subsumed by `analytical_role`), `coicop_divisions` (replaced by `coicop_codes`).


## `archive_prefix` / `archive_path_re` — the Common Crawl pair

These two drive historical recovery. Both fail **silently**: a wrong value
produces no error and no miss record, the source simply never appears in a
resolve pass. A measured audit on 2026-09-02 found this class had left 261
sources on this project sitting at zero. Get them right at onboarding.

**Rule 1 — derive them from what the ARCHIVE holds, not from the live site.**
This is the one that actually bites. Both failures found on 2026-09-02 were
accurate descriptions of the live site and wrong descriptions of the archive:

- `comoresenligne_km` — prefix `comores-en-ligne.fr/fr/catalogue/product/`
  matched **0 of 725** available captures. Archived PDPs carry neither the
  `/fr/` locale nor a `/product/` segment (real shape
  `/catalogue/<slug>_<id>/`). The site had changed its URL scheme since.
  Corrected value returns 160.
- `pisiffik_gl` — prefix `www.pisiffik.gl/da/` admitted **3,806 of 7,290**,
  silently excluding the entire Greenlandic `/gl/` storefront, which has an
  identical PDP shape.

**Rule 2 — put the bare host in the prefix and let the regex do the work.**
The prefix is a plain string cap applied at `cc_index.py:351`
(`if not line.startswith(key): continue`) **before** the regex is consulted,
so any path segment in the prefix silently caps everything behind it.
`fravega_ar` carried `/p/` and returned 0; dropping to bare host gave
**40,346 rows spanning 2014–2025**.

**Rule 3 — mind what the regex is matched against.** It runs at
`cc_index.py:366` against `urlparse(url).path`, so:
- the **query string is excluded** — a regex containing `?` or `&` can never
  fire;
- it is matched against the **raw** path, so it is **case-sensitive**.

The asymmetry is the trap: `surt_prefix` lowercases the prefix **including its
path**, while the regex is matched against the raw path. So *a prefix that
works is no evidence a same-cased regex will* — the prefix will happily admit
captures the regex then silently rejects on case alone. That is what broke
`cozmo_jo`, which matched 4 records where it should have had 133.

**Rule 4 — never assume one URL encoding.** The cdx stores both, by era. Same
site, two crawls:

    CC-MAIN-2025-21  /da/%C3%B8vrigt-badetilbeh%C3%B8r/71314-...
    CC-MAIN-2022-21  /da/æggebægere/36-gc-æggebæger-ø14-cm-klar-2-stk.html

`[^/]+` matches both (a `%XX` escape contains no slash). A `\w`-based class
would silently drop every raw-UTF-8 capture — i.e. an entire era. Note the
encoding varies **by era within a single source**: it reflects what the
crawler recorded at the time, not what the site serves, so probing one crawl
tells you nothing about the others.

**Rule 5 — `spider` must be set alongside it.** `cc_config.py:147` reads
`if not (cfg.spider and cfg.archive_prefix): continue`, so a manifest with
`source_key` but no `spider` is invisible to the resolver, with no error.

**Validate the pair before shipping — it costs one script and catches the
silent failures.** Run `archive_path_re` against the URLs the spider itself
just collected:

```python
import glob, json, re, yaml
from urllib.parse import urlparse
rx = re.compile(yaml.safe_load(open(CONFIG))["archive_path_re"])
rows = [json.loads(l) for l in open(sorted(glob.glob(RAW_ITEMS))[-1])]
bad = [p for p in (urlparse(r["url"]).path for r in rows) if not rx.search(p)]
print(len(bad), "rejected of", len(rows), bad[:3])
```

Anything other than 0 rejected is a bug in the regex, and it is the cheapest
place to find it. Run on this wave's seven sources it caught a live one:
`sosisvege_gi` used `[a-z0-9\-]+` and silently rejected 2 of 180 paths,
`/shopping-categories/at%C3%BAn-en-tomate` and `.../jud%C3%ADas-verde`.

### The hand-rolled character class is the single most common defect here

An audit of all 890 configs on 2026-09-02 found **98 using a lowercase-only
class in `archive_path_re`, 26 of them behaviourally confirmed** to accept a
plain slug and reject the percent-encoded form of the same path.

**Two independent things must both be right, and fixing one and stopping is
the natural failure:**

1. the class must contain a literal **`%`**, or a `%XX` escape cannot match
   *at all*;
2. it must accept **uppercase** hex, because percent-encoding emits `A-F` in
   caps and the match is case-sensitive.

Each half is individually fatal, proven by a config that got one right and
still lost:

- `kingfoodmart` — `(?i)^/[a-z0-9-]+$`. The `(?i)` fixes the casing half
  completely, and it *still* rejects every encoded path, because `%` is not
  in the class.
- `cassandraonlinemarket_ht` (Haiti, French Creole) — `[a-z0-9%-]`. Someone
  thought about `%` and still lost, because `A-Z` is missing.

**So do not hand-roll the class. Prefer `[^/?]+`,** which is immune to both.

Note this is unsafe *everywhere* but only *costs rows* where the host
actually serves non-ASCII slugs; on a pure-ASCII catalogue it is free. Rank
any remediation by measured loss — how many of the URLs CC actually holds for
that source carry an escape AND are rejected by the configured regex — not by
pattern shape. `expatistan` and `livingcost` carry unsafe patterns over
10,748 and 4,304 paths with zero encoded among them, and warrant no fix.

**The general rule behind both this and the `cozmo_jo` casing trap:** any
stage where the prefix and the regex see *different strings* is a stage where
one passing tells you nothing about the other. The prefix admitted those
sosisvege captures perfectly well; only the regex dropped them, so no
prefix-level check could ever have surfaced it.

### Before writing either value, ask whether the collected URLs are browsable

**A source whose collected URLs are not browsable pages cannot have its
archive values derived locally at all** — they must be measured against the
CC index instead. This is a predicate you can check *before* writing
anything, and it outranks the "derive from the archive" rule because it tells
you in advance that you are in the dangerous case.

`comoresenligne_km` is the worked example: its rows carry the API's own
`/api/v1/products/<id>/` as identity, so it scores 0 of 1,524 on the
validation check above. That is not a regex bug — and it is precisely how
that source's first prefix came to be written, from a guess, and shipped
matching 0 of 725 available captures.

**Disambiguating a 100% rejection rate:** it means either the URLs are not
browsable *or* the regex is simply wrong. Tell them apart by looking at the
collected URLs — an API route (`/api/v1/...`, `/wp-json/...`) means the
former, a page route means you have a real regex bug. Do not read this
section as "0% is always fine and 100% is always benign".

**Also worth recording in `notes`: whether the source emits any structured
data at all.** The archive fetcher ships four generic parser tiers — JSON-LD,
OpenGraph, Next.js flight data, and inline schema.org microdata. A source
with none of them will resolve captures and then parse to zero.
`ckgreaves_vc` is the worked example: no JSON-LD, no `itemtype`, no
OpenGraph, and its only `itemprop` values are `image/name/options/pricing/
savings` — three of which are not schema.org properties, so there is nothing
for the microdata tier to scope. Its price lives solely in a `data-price`
attribute, which no tier reads. Say so in `notes` so the archive side can
skip it or build for it deliberately.

Do **not** add a `platform:` field to record this. `PriceSourceConfig` is
`extra="forbid"`, so any undeclared key raises at load and takes down the
**global** `prices collect --list`. Put it in `notes` as prose.

### The regex must accept every price-bearing page family the ARCHIVE holds

**This is not a rule about the spider.** The archive regex must accept every
page family the *archive* holds that carries prices, regardless of which one
the spider fetches. A listing page the spider never touches is still 5-25x the
product density in a capture we have already paid for; a PDP route the spider
never uses may still be most of what CC captured.

The spider's page type is the single most useful *hint* — it tells you one
family that definitely parses — but it is a floor, not the answer. Write the
regex from the archive, then use the spider to sanity-check that it did not
lose anything.

The failure runs in **both directions**, and one source of each has already
shipped broken:

- `sxmleshalles_mf` — a listing-parsing spider given a PDP-only regex. The
  spider never fetches a PDP; all 2,128 rows came from 823 category pages,
  whose URLs the pattern could not match at all.
- `ckgreaves_vc` — the reverse. A listing-parsing spider whose *archive* is
  full of PDPs. The live PDP route is broken today (it 301s to a doubled
  origin and the target 404s), so it was written off as "no working PDP" —
  but CC captured that route while it worked, and widening to admit it took
  the source from 283 to 1,016 accepted paths, a 3.6x gain.

**A live-site probe is evidence about today only.** The fetch spans ~102
crawls back to 2013. A route that is dead now was very likely alive, and
captured, for most of that window. Never let a live 404 decide what the
archive contains.

Two of four sources onboarded on 2026-09-02 shipped with exactly this defect,
both caught only by re-auditing against the live site *after* the manifests
were written:

| Source | Old regex accepted | New accepts | Why |
|---|---|---|---|
| `sxmleshalles_mf` | 33 of 288 live paths | 184 (5.6x) | Spider never fetches a PDP. All 2,128 rows came from 823 **category** pages. Category URLs are `/{lang}/<id>-<slug>` — two segments, no `.html` — so the PDP pattern could not match them at all. `/fr/101-eaux` renders 12 products and 12 price nodes in one capture. |
| `boutiqueacm_mc` | 15 of 165 live paths | 44 (2.9x) | WooCommerce listing pages carry prices: `/promotions/` renders 12 distinct products and 24 price nodes in one capture, `/collection/<x>/` renders 5. The PDP-only prefix cut all of them. |

**Check both halves of the pair, not just the regex.** `boutiqueacm_mc` also
had `archive_prefix: "boutiqueacm.com/produit/"`, which cut the site's full
mirrored English storefront (`/en/produit/`, `/en/collection/`,
`/en/promotions/`) *before the regex ever ran* — the same defect that cost
`pisiffik_gl` its entire `/gl/` storefront. Prefer a bare-host prefix and let
the regex do the selecting; a prefix that carries a path segment is a silent
cap on everything outside it.

**Locale mirrors are the recurring trap.** Three separate sources
(`pisiffik_gl`, `comoresenligne_km`, `boutiqueacm_mc`) shipped values that
excluded an entire language storefront. Before writing either value, fetch the
home page and list its distinct top-level path segments — a `/en/`, `/fr/`,
`/gl/` or `/da/` segment there means the pattern must admit it.

**Record era hints in `notes` when you can see them.** A regex correct for
2024 markup is routinely wrong for 2017, and route shapes change. Two cheap
signals: a redirect whose *target* differs in shape from the current route
names the older route (`ckgreaves_vc` 301s today's
`/shop/browse/product/<id>_<slug>/` at `/shop/products/<slug>/`, so the
archive plausibly holds all three shapes); and percent-encoding vs raw UTF-8
in paths shifts by era on the same site (`pisiffik_gl` shows `%C3%B8` in
CC-MAIN-2025-21 and raw `æggebægere` in 2022-21). Never use `\w+` or a
lowercase-only hex class — `[^/?]+` handles both eras and both cases.

**A path-count gain is not a row gain, and a spider-side gain does not
transfer to the archive.** Widening a regex is measured in paths accepted;
what matters is rows parsed. The two came apart badly on both sources widened
on 2026-09-02, in opposite directions:

- `sxmleshalles_mf` — the widening admitted 151 category pages (33 → 184
  paths, 5.6x). Run through the real parse chain, those category captures
  yield **zero rows**: the archive's JSON-LD there is `Organization` only,
  with prices in `span.price` text. The 472 PDPs — the family the spider
  never fetches and I never characterised — are the ones that carry JSON-LD
  `Product` and parse. The 5.6x was a real number *for the spider* and worth
  nothing for the archive.
- `ckgreaves_vc` — the reverse: a path count that understated the win, since
  the newly admitted PDPs were the whole value.

So quote path counts as what they are, and get the archive side to run a
parse-yield check per route family before treating any widening as a gain.
`boutiqueacm_mc` is the cautionary case: 449 captures, 302 of them on
families my regex admits, **0 rows** — its Yoast schema graph carries no
`Product` node at all, so the price exists only as rendered markup.

**Validate the widening both ways.** A wider pattern is only safe if it still
accepts everything the old one did. Check the new regex against the spider's
own collected URLs and confirm the match count is unchanged (96/96 and
2,128/2,128 respectively above), then check it against paths harvested from
the live home and category pages to confirm it actually admits more.

### Price-shaped text is not a price — key on the attribute, and say which page you read

Two failures from `ckgreaves_vc`, both found only after an extractor written
from a correct spec returned zero on every real capture.

**1. Characterise the page family the ARCHIVE holds, and record which one you
read.** The spec was accurate — for a *department* page, whose cards are
`article.product-grid-item`. The archive is PDPs, whose card is
`article.col.col-01.single-product-post`: different class, same theme, same
attributes. Keying on the class rejected all 283 captures. Keying on
`<article>` carrying `data-price` covers both templates and is the safer test
anyway — a PDP embeds five `product-grid-item` cards in a related-products
rail but exactly one `data-price`, so the rail cannot be mistaken for the
product. **Always state in `notes` which page family the markup spec was
derived from.** A spec that is correct about a page the archive barely holds
is worse than no spec: it passes review and returns zero.

**2. A recurring price widget makes non-product pages look like product
pages.** The `supershop` theme renders a twelve-item `mini-product-card`
carousel in the chrome of *every* page. Measured on the live site: home has 60
`price-now` against 48 `data-price`, a department page 52 against 40 — the
excess is exactly 12 both times. On a page with no products at all it is 12
against **zero**:

    /2025/11/05/<name>/   (an obituary post)   price-now x12, data-price x0
    rail values flatten to '$235', '$165', '$205', '$000'

So a text-fallback parser pointed anywhere on this host banks twelve
hundredfold-wrong prices ($2.35 read as 235) attributed to an obituary. The
damage is not confined to routes a product regex would target, and nothing
downstream flags it because the output is a plausible number.

**The general rule: extract on the machine-readable attribute, never on the
rendered figure.** If a source has no such attribute, that is a reason to
treat it as unparseable rather than to fall back to text.

### A platform-shaped problem still needs a sizing check

When a defect turns out to be a property of the platform rather than of one
retailer, the reflex is to size the fix by the platform's footprint. That
footprint is the wrong number. What matters is how many sources actually
*fail today*.

Worked example, 2026-09-02. `boutiqueacm_mc` parsed to zero because Yoast
emits a schema graph with no `Product` node, leaving the price only in
rendered `bdi` markup. Counting platforms across the 1,462 configs gives
WooCommerce 146, Shopify 99, Magento 59, VTEX 35, PrestaShop 18 — so the fix
looked like "one generic WooCommerce tier reaching 146 sources."

Measured, it was not:

    WooCommerce configs with a usable archive pair : 130
    sources with archived captures                 :  83
    at least one capture parsed                    :  73
    every read capture yielded nothing             :  10   = 12% of measured
    nothing readable                               :   0

Yoast-without-`Product` is the minority configuration, not the common one. The
addressable population was **10 sources holding 3,760 captures**, against 1.6M
rows already banked by the run in flight. Across all captures the winning tier
was JSON-LD 363, none 83, meta 22, per-source 10. A rendered-figure tier would
have meant carrying the rail exclusion, the `<ins>` preference and the
decimal-comma rule (a 1000x error class) permanently, for that. Correctly
dropped.

The one argument that can override raw volume is **country coverage**, since a
country with no archived history is a gap that more rows elsewhere cannot
fill. Check it explicitly: here exactly one of the ten was its country's only
source (`boutiqueacm_mc` for Monaco), and it is Grand Prix merchandise — not
food, not CPI-relevant. The other nine sat in countries with 5-20 sources
each. So that argument failed too.

**Watch the direction of successive corrections.** This estimate was revised
three times — 21 sources, then 14, then 10 — while the confirmed successes rose
62 → 73. A population that only ever shrinks under scrutiny is a signal in its
own right: the case for not building was strongest after the corrections, not
before them. Had the number moved the other way, that would have been the cue
to re-open the decision rather than to keep defending it.

### Sampling the head of a sorted list is not sampling

The first two versions of the count above were wrong because the study took
`recs[:3]` from a cdx result. **cdx is SURT-sorted**, so that is the three
alphabetically-first paths, not three representative pages. For one source it
drew a delivery-info page twice plus a transient fetch error and scored the
source as yielding nothing; an even spread across the same crawl returned 30,
9 and 30 rows, and that source parses in every crawl from 2016 to 2025.

This is the same error as quoting a path count for a row count, in different
clothes: a number computed off the wrong denominator, reported as if it were
the quantity of interest.

Three practices come out of it, all cheap:

**Put the sampled inputs in the output.** The first run's verdict was
*arithmetically correct on the data it had* — the data was just the head of a
sorted list. Nothing about the verdict alone could reveal that. The corrected
run was only trustworthy because it printed which paths it sampled, so they
could be eyeballed as genuine product routes (`/producto/accu-check-...`,
`/product/d197-musang-king-2-packs/`). A verdict is not checkable without its
inputs.

**Know which way the bias runs.** Head-of-list sampling manufactures false
*zeros*, never false successes — so confirmed successes survive a flawed run
and only the failure count moves, downward. Establish the direction before
deciding how much of a broken study to keep. Fix the study; do not argue the
number down.

**Retry cold objects before believing a fetch failure.** Adding one retry took
the fetch-error count from 88 to 1 and reclassified seven sources from
"unmeasured" to "parses fine". A 35% error rate that looked like a property of
the archive was a property of not retrying. And never score an unmeasurable
source as a failing one — that alone inflated the first estimate from 10 to 21.

Residual caution even in the final number: one of the ten survivors
(`ekissaan_pk`) is backed by 5 captures that are all `/shop/page/2/`-style
pagination stubs, which is not evidence about its product pages. A count can
be correct in aggregate and still rest on a soft row.

### A bounded traversal must distinguish "nothing there" from "budget ran out"

Three independent instances turned up within two days, on opposite sides of the
pipeline, all with the same signature: **the run reports success, the stats look
healthy, and an entire family of pages is silently absent.**

| Traversal | Bound | What went missing |
|---|---|---|
| Spider pagination (`pisiffik_gl`) | `MAX_PAGES_PER_CATEGORY = 250` | Everything past page 250 of the two deepest categories. `request_depth_max` was exactly 250. |
| Spider pagination, chained | a dropped page | The **whole category tail** — page N yields the request for N+1, so one failure ends the chain. |
| cdx block scan (`query_prefix`) | `max_blocks` | cdx is SURT-sorted, so `/about`, `/blog` and `/robots.txt` consume a small budget before the product family is reached. |

Two checks, both cheap:

**Compare the bound against the observed maximum.** A `request_depth_max`,
block count, or page count that *equals* its configured cap is a truncation
signature, not a healthy run. It never means the crawl happened to end there.

**Make the give-up path loud.** In every one of the three, the failure was
silent — returning quietly at the bound is what let a truncated run pass review.
Log which family was abandoned and say plainly that the rest was not collected.
A bounded traversal that exits at its bound must say so; only an exhausted one
may exit quietly.

**Diff two runs per category to detect it.** Shallow families are byte-identical
across runs; the truncating ones wobble. On `pisiffik_gl`, 42 of 44 categories
matched exactly across four runs and the two deep-paginated ones read
2250/2427/2427/1895 and 1624/1050/1357/501 — which is what exposed the chain
break. A single run cannot show this; a second run is the cheapest test there is.


## Examples

Country-bound fetcher (Pertamina Indonesia, fuel):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["07.2.2", "04.5.4"]
channel: null
source_key: id_pertamina
module: eap.southeast_asia.indonesia.pertamina
function: fetch_id_pertamina
url: https://mypertamina.id/fuels-harga
language: id
cadence: monthly
fallback_date: 2020-01-01
notes: |
  Schedule-1 retail prices only. _COICOP_MAP keyed by product name
  (Pertalite/Pertamax/etc. → 07.2.2; Minyak Tanah → 04.5.4).
```

Spider (FairPrice Singapore, retailer SKU):

```yaml
scaffolding: spider
extraction_pattern: scrapy_api
analytical_role: retailer_sku
coicop_classification: classifier
channel: supermarket
spider: fairprice
url: https://www.fairprice.com.sg
language: en
cadence: daily
```

Wholesale market feed (general catalog walker, `official_avg`):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: official_avg
coicop_classification: classifier
channel: wholesale
source_key: th_talaadthai
module: eap.southeast_asia.thailand.talaadthai
function: fetch_th_talaadthai
url: https://talaadthai.com
language: th
cadence: daily
fallback_date: 2024-01-01
notes: |
  Whole-catalog numeric-id walk (~2,000 commodities), not a targeted
  extractor. Emits current + prev daily snapshot as the midpoint of the
  published min/max. Unit passthrough incl. Thai units.
```

CPI benchmark (BPS Indonesia):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: cpi_benchmark
coicop_classification: publisher_labeled
coicop_codes: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
channel: null
source_key: id_bps_cpi
module: eap.southeast_asia.indonesia.bps_cpi
function: fetch_id_bps_cpi
url: https://www.bps.go.id/en/statistics-table/...
language: en
cadence: monthly
fallback_date: 2018-01-01
notes: |
  COICOP 2018 13-division grouping (publisher publishes 12; division
  13 is folded into 12 by BPS). Translation map: Bahasa → COICOP codes.
```

Marketplace — third-party sellers (Shopee in Singapore, thin per-country wrapper):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: retailer_sku
coicop_classification: classifier
channel: marketplace
source_key: sg_shopee
module: eap.southeast_asia.singapore.shopee
function: fetch_sg_shopee
url: https://shopee.sg
language: en
cadence: daily
fallback_date: 2024-01-01
```

Platforms selling through **third-party sellers** (Shopee, Lazada, Rakuten,
Yahoo Shopping) are marketplaces — long-tail catalogs with seller-authored
product names. The authoritative value list, with a discriminating test for
each, is the `channel` entry in `src/prices/docs/GLOSSARY.md`.

Truly global aggregate (World Bank Pink Sheet, at `configs/_global/wb_pink_sheet.yaml`):

```yaml
scaffolding: fetcher
extraction_pattern: tabular_download
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["01", "04", "07"]
channel: null
source_key: wb_pink_sheet
module: _global.wb_pink_sheet
function: fetch_wb_pink_sheet
url: https://www.worldbank.org/en/research/commodity-markets
language: en
cadence: monthly
fallback_date: 1960-01-01
notes: |
  Emits aggregate-region rows (country="Global"). Reference series
  for commodity-price benchmarking across all countries.
```

## Archive fields — `archive_prefix` and `archive_path_re`

These two fields are what makes a source retrievable from **Common Crawl**, which
is how the pipeline recovers historical price series that predate our own
scraping. A live spider gives you today forward; CC gives you 2013 onward. Set
them at onboarding — a source added without them is invisible to the CC resolver
and nobody finds out.

Both are read by `src/prices/price_scraping/archive/cc_index.py`.

### The one rule that matters: `archive_prefix` is the bare registrable host

```yaml
archive_prefix: "banjoosuperstore.com/"      # correct
archive_prefix: "banjoosuperstore.com/product/"   # WRONG — silently caps recall
```

`archive_prefix` is a plain **string** prefix applied to cdx index lines
(`cc_index.py:351`, `line.startswith(surt_prefix(archive_prefix))`) **before**
`archive_path_re` is ever consulted. A path segment in the prefix is therefore a
hard ceiling on what any regex can subsequently see.

When it is wrong, it fails **silently** — no manifest, no miss record, no error,
no zero-row warning. The source simply never appears in a resolve pass. A
2026-09-02 audit found **261 of 882 sources** in exactly this state. Dropping
`fravega_ar` from `/p/` to the bare host took it from **0 rows to 40,346 spanning
2014-2025**; it could never reach its real `/{category}/p` product family.

Optimise for **recall, not scan time**. Over-inclusion costs almost nothing:

- The cap is looser than "path prefix" suggests. `surt_prefix()` does
  `path.rstrip("/")`, so `www.fravega.com/p/` becomes the bare string
  `com,fravega)/p` — which also matches `/panasonic`, `/pampers` and
  `/philips`. It was never the precise filter it looks like.
- `archive_path_re` does the real filtering afterwards, on every candidate.

**The asymmetry is the whole argument.** Over-inclusion costs *scan time*.
Under-inclusion loses *data*, silently, with nothing in any log to say so. Those
are not comparable costs, which is why the answer is always the bare host and not
"a carefully chosen prefix."

And a bare host is the only form that **survives a URL-scheme migration**.
`sheridans_ie` broke when the site moved WooCommerce → Shopify and `/product/`
became `/products/`. `tmpnp_zw`'s own canonical URLs said `/products/` while CC
had only ever archived `/shop/...`. A path prefix cannot survive either; a bare
host is immune to both.

### `www.` does not matter — but subdomains do

`surt_prefix()` mirrors CC's SURT canonicalisation and strips a leading `www.`:

```python
host = host.lower()
if host.startswith("www."):
    host = host[4:]
```

So `www.alvaro.fo/` and `alvaro.fo/` produce the identical key `fo,alvaro)/`. A
site that 308-redirects bare → www is a non-issue: CC indexes the URL it fetched
and both canonicalise the same way.

**Only `www.` is stripped.** A catalog on any other subdomain —
`shop.example.com`, `gcc.luluhypermarket.com` — is a *different* SURT key and
must be written out in full.

### Four ways `archive_path_re` silently never fires

1. **A query string in the pattern — a structural impossibility, not a near
   miss.** The regex is `re.search`ed against `urlparse(url).path`
   (`cc_index.py:366`). The query is *absent from the string being matched*, so
   a pattern containing `?` or `&` cannot fire under any circumstances. A site
   that keys products off `?category=` (e.g. `superselectos_sv`) is unfixable
   through this mechanism — record that; don't ship a pattern that cannot fire.
2. **Case — the prefix is case-insensitive and the regex is case-sensitive.**
   This asymmetry is the actual trap. `surt_prefix` lowercases the prefix
   *including its path* (itself a fix: `shop.cosmed.com.tw/SalePage/` matched
   nothing until the path was lowercased), but `archive_path_re` is matched
   against the **raw** path, which is never lowercased. `cozmo_jo` broke solely
   because its regex demanded lowercase while the site serves
   `/cozmostore/Categories/.../p/<id>`. A prefix that works is no evidence at
   all that a same-cased regex will.
3. **A character class that assumes ASCII.** Percent-encoding varies *by era
   within a single source*, because it depends on what the crawler recorded, not
   on the site. `pisiffik.gl` yields
   `/da/%C3%B8vrigt-badetilbeh%C3%B8r/71314-...` in CC-MAIN-2025-21 and raw
   UTF-8 `/da/æggebægere/36-gc-æggebægere-ø14-cm-klar-2-stk.html` in
   CC-MAIN-2022-21 — the same paths, encoded two ways. A `[^/]+` or `[^/?]+`
   class matches both. A `\w`-based one silently drops the raw-UTF-8 era, which
   is *most of the archive* for the Nordic, Faroese and Greenlandic sources.
   **Default to `[^/?]+`.** Never write `\w+` in a path pattern.
4. **Over-tight depth anchoring.** `re.search` is unanchored at the right, so
   depth is free. `libdelivery_lr` serves four-segment PDPs
   (`/item/restaurants/oportos/breakfast/omelette-ham-cheese/`) and a plain
   `^/item/` matches all of them. Prefer loose.

### One wrong prefix on a chain becomes N wrong prefixes

The mistake does not stay put. A multi-storefront chain is onboarded from one
template, so a path prefix that is wrong on the first storefront is wrong on
every sibling — and they fail *together*, silently, looking exactly like a chain
that CC never crawled.

`koro` is the worked example. Four storefronts on their own domains
(`koro_fr`, `koro_at`, `koro_ch`, `koro_it`) carried `/detail/`, which is
Shopware's **technical canonical**; CC only ever archived the SEO-slug pages, so
the prefix could not see a single product. Dropping to the bare host recovered
129-246 records per storefront. Nine further storefronts live on
`www.koro.com/<locale>/detail/` and carry the same segment — a confirmed
diagnosis, on the same platform, with a known-good fix, replicated nine times.

A 2026-09-02 census of 890 configs found **660 carrying a path in
`archive_prefix`**, clustered hard by stem:

| Stem | Sources | Shared path segment |
|---|---:|---|
| wolt | 16 | `/en/kaz/almaty/venue` |
| cosmed | 12 | `/SalePage` |
| koro | 9 | `/befr/detail` |
| decathlon | 6 | `/p` |
| jarir | 5 | `/bh-en` |
| vodafone | 5 | `/nos-offres` |

`decathlon`'s `/p/` is character-for-character the `fravega_ar` shape, six times
over.

**So when you onboard one storefront of a chain, you are setting the prefix for
all of them.** Two consequences:

1. Use the bare host, which is the only value that cannot replicate a mistake.
2. If you *do* find a chain whose prefix is wrong, say so — the sibling
   storefronts have the same defect by construction, and nobody will find them
   by looking at any one config.

**A locale segment is the same failure in miniature — one storefront per
prefix.** `pisiffik_gl` carried `/da/`, which excluded the entire Greenlandic
`/gl/` catalogue sitting on the same host with the same PDP shape. Invisible,
and not obviously wrong to read. This is the identical root as koro's `/befr/`,
`/dk/`, `/es/`: a per-locale path segment means every locale you did not
enumerate is dark, and multilingual markets are exactly where you least want to
lose half the catalogue. The bare host takes all locales at once.

Note also that a technical canonical (`/detail/{id}`, `/p/{sku}`) is a
particularly seductive wrong answer: it is stable, it appears in the site's own
`<link rel="canonical">`, and it is frequently the URL form CC never archives,
because crawlers follow the human-facing SEO slugs instead.

### Derive the pattern from what CC holds, not from the live site

This is the single most common source of a bad pattern. Nearly every one of the
261 broken prefixes came from reading the live site's URL shape and assuming CC
matched it. The live site is today's scheme; CC is every scheme the site ever
had. `djor_fo` shipped `^/product/[^/?]+` — correct against the live site,
verified against 2,159 freshly scraped rows — and matched **6 of 267** archived
records.

The failure is live, not historical: `comoresenligne_km` was onboarded in a
separate session within the same hour as this section was written, and has
**725 captures with zero reachable**, because its prefix carries a `/fr/` locale
segment and a `/product/` segment that both exist on the live site and appear
nowhere in the archive. Two independent authors, same hour, same mistake. Read
the archive first.

Where a live-site pattern and the archived paths disagree, do not widen the regex
on a guess. Two very different situations produce the same symptom and need
opposite fixes:

| Symptom | Diagnosis | Fix |
|---|---|---|
| Archived paths use a *different product base* with per-product slugs | Site migrated its permalink scheme | Widen the regex to cover both bases |
| Archived paths are only the homepage and a bare/paginated listing | CC never crawled the PDPs | No regex helps — record it and move on |

Telling them apart needs the distinct archived paths, not the counts. Widening a
regex for case 2 sends fetches after listing pages forever.

### `spider` is mandatory for CC, including for sources you think don't need it

`cc_config.py:147` reads:

```python
if not (cfg.spider and cfg.archive_prefix):
    continue
```

A manifest carrying `source_key` and `archive_prefix` but **no `spider`** is
skipped outright — again with no error. 402 of the 608 prefix-less configs in the
tree are fetcher-scaffolded and hit precisely this.

### Recording crawl-era coverage: presence yes, absence no

Record positive facts — "first seen CC-MAIN-2019-04, 936 records across 8
crawls". Do **not** record an absence unless you probed deep (`max_blocks=40`+)
across several crawls.

Shallow probes manufacture false absences. The cdx index is SURT-sorted, so
`/about`, `/blog`, `/images` and `/robots.txt` can consume the entire block
budget before the first `/product...` line is reached.
`pharmacie_saintemarie_ga` read **0 records at 5 blocks and 38 of 38 at 40**.
Crawl recency cuts both ways too: CC-MAIN-2026-25 surfaced content that
CC-MAIN-2024-46 missed entirely for four sources.

### Record the platform fingerprint — it predicts parse yield

Parse coverage, not index coverage, is the real bottleneck. The archive fetch
ships four generic tiers: JSON-LD, OpenGraph meta, Next.js flight data, and
inline microdata. **JSON-LD yield is ~0% pre-2016 and rises to ~46% by 2026**, so
a source whose value is its 2019-2020 tail will lean on the microdata tier
instead.

Note the platform (WooCommerce / Shopify / Magento / VTEX / PrestaShop) and the
extraction route in the inventory so that yield can be predicted rather than
discovered after a scan. There is no `platform:` field on `PriceSourceConfig`
today, and the model is `extra="forbid"` — adding one to a manifest without
adding it to the model raises at load time and takes down the **global**
`prices collect --list`, not just that source. Put it in the inventory prose
unless and until the field is added to the model.
