# RUNBOOK — adding price sources and recovering history

Written 2026-09-12 for a second builder working alongside the main effort.
Everything here is F&B scoped; see §1 for why that matters more than it sounds.

Branch: **`prices/fill-gap-sources`** — this is the current tip of the source
work (2,464 sources). `prices/precision-sweep` was fast-forwarded to the same
commit on 2026-09-12. The dashboard lives on **`prices/explorer-redesign`** (§7).

---

## 1. Scope: COICOP 01 and 02 only. This is not a detail.

The scorecard is `coicop_country_grid_measured.xlsx`. Its 257 leaves are
**248 from division 01 and 9 from division 02** — food, non-alcoholic beverages,
alcohol and tobacco. Nothing else is in it.

The cause is one constant, `src/prices/build/basket.py:65`:

```python
FNB_COICOP_PREFIXES: tuple[str, ...] = ("01.", "02.")
```

applied at `aggregate.py:140` before `global_prices_observations.parquet` is
written. Measured: that parquet holds 18,950,870 rows — 17,127,086 in division
01, 1,823,784 in division 02, **zero** in divisions 03-13.

**So a source outside 01/02 fills zero grid cells.** Not "until the next embed
run" — permanently, under this build. That includes electricity and water
tariffs (04.5), rent (04.1), motor cars (07.1), mobile service (08.3), health
(06), education (10) and **restaurant/café menus (11)**.

### What to target

✅ Supermarkets, grocers, minimarts, hypermarkets, grocery delivery, wet and
farmers' markets, bottle shops, tobacconists, cash-and-carry, duty-free,
agricultural and market price bulletins.

❌ Restaurants and cafés (feels like food, is division 11), pharmacies unless
they carry groceries, electronics, apparel, furniture, fuel, telecom, education,
health, housing, vehicles.

`index_observations.csv` is written by `writers.py:66` and **read by nothing in
the build**, so a `cpi_benchmark` source contributes no cells either. Those are
still worth having as benchmarks — just don't count them as coverage.

---

## 2. Not overlapping

Two mechanisms, use both.

**a) The workbook is the register.** `prices_sources_status_v2_with_new_targets.xlsx`
(sheet `sources`). Status is one of `HAVE` / `PENDING` / `LAST_TRY_FAILED`.
It was re-synced against real manifests on 2026-09-12, which flipped **419 rows
to HAVE** that were still listed as PENDING — the workbook had drifted badly, so
re-sync before trusting it:

```bash
python gapwork/mkv3.py     # marks HAVE for any row whose host appears in a manifest
```

**b) The target list is split by COUNTRY, not by source.** See
`FINAL_TARGET_LIST_fnb.csv`, column `owner`. Country-level split means two
builders can never produce a spider for the same host, even by accident, because
a host belongs to exactly one country directory. Countries were ranked by grid
emptiness and dealt alternately, so both owners get a fair share of the
high-value empty countries.

Current split: **WILLIAM 1,083 hosts / JERO 1,212 hosts**, 273 countries,
2,295 total. `country_owner_split.csv` is the per-country assignment — flip an
`owner` cell to trade a country.

**Before building anything**, check the host is not already covered:

```bash
grep -rl "thehost.com" src/prices/configs/
```

---

## 3. Setup

```bash
git clone git@github.com:jeronimoluza/pacific-observatory.git
cd pacific-observatory
git checkout prices/fill-gap-sources

python -m venv ~/venv && ~/venv/bin/pip install -r requirements.txt
# (the repo also carries pyproject.toml / poetry.lock if you prefer poetry)

~/venv/bin/python run.py prices collect --list | tail -1   # expect: 2464 sources
```

That last command is the **global health check**. It loads every manifest, so a
single malformed YAML takes it down — see §5 on `channel`.

---

## 4. Adding a source

The full procedure is a skill in the repo:
`.claude/skills/onboard-price-sources/SKILL.md`. Read it; it is long because
each rule in it was paid for. The short version:

### 4.1 Probe before writing code

Never write selectors you have not seen work. Order of cheapness:

1. **Shopify** — `GET /products.json?limit=250&page=N`. If it answers, you are
   done: reuse `generic_shopify_configured`, no new code.
2. **WooCommerce** — `GET /wp-json/wc/store/v1/products?per_page=100`. Reuse
   `generic_woo_configured`.
3. **Others with a base class** — `_magento_base.py`, `_vtex_base.py`,
   `_jsonld_sitemap_base.py`, `_shopify_base.py`, `_woo_base.py`,
   `generic_opencart_configured`, `generic_prestashop_configured`.
4. **JSON-LD in a sitemap** — if `sitemap.xml` lists PDPs and each carries
   `schema.org/Product`, subclass `_jsonld_sitemap_base` in ~10 lines.
5. **Bespoke spider** — last resort.

Of 17 Botswana sources built this way, 8 needed **no new code at all** and 6
needed a ~10-line subclass. Only 3 needed a real spider. Probe first.

### 4.2 Access: use the impersonation ladder, all of it

```python
from curl_cffi import requests as r
r.get(url, impersonate="chrome124", timeout=30)
```

Ladder: `chrome124` → `chrome120` → `safari17_0` → **`firefox133`**.

**`firefox133` is load-bearing.** On 2026-09-12, three countries independently
hit an identical **6,192-byte 403 stub** from Hostinger `hcdn` that 403s on
chrome120/124/131 *and* safari17_0 and returns **200 on firefox133**. Seven
hosts, two of them open WooCommerce Store APIs. A Chrome-only ladder writes all
of them off as hard WAF blocks.

Never record a block from bare `curl` — that measures curl's TLS handshake, not
the site. 112 such verdicts were re-probed once and a large share fell to
impersonation alone.

**Caveat when pinning a profile:** `RandomBrowserMiddleware` overwrites
`request.meta["impersonate"]` unconditionally from `IMPERSONATE_BROWSERS`
(pinned repo-wide to `chrome120`), so `WooBaseSpider.IMPERSONATE_PROFILE` is a
**silent no-op** — the spider 403s on every request while appearing to declare
the right profile. Narrow `IMPERSONATE_BROWSERS` in that spider's own
`custom_settings` instead.

Check `.claude/skills/onboard-price-sources/references/known_blockers.md` before
probing — and distrust entries that don't name the lever they tried.

### 4.3 Access is not enumerability — prove pagination

A 200 means nothing. **Page 2 must return a different set.** Real failures found
this month, all of which returned 200 and looked healthy:

- `market231` — `?offset=` silently re-serves page one. A spider walked offset to
  19,900, logged `rows=100` two hundred times, and scraped exactly 100 products.
  `?page=`, `?start=`, `?cursor=` are ignored the same way; **`?skip=` works.**
- `nhamburguer` — Nextar ignores `page` entirely; `perPage` is the only lever.
  Proven with a ladder: 100→100, 1000→1000, 5000→3,793.
- `cloudmartsy` — the *same URL twice* returns disjoint 24-card sets. It is a
  random sample, not a catalog.
- `dellkorse` — `?page=2` returns an identical price set.

Also: **homepage products are not a passing probe.** Carousels are curated and
unpaginated.

### 4.4 Reject these, they pass naive gates

- **WooCommerce theme-demo data.** A working Store API full of Woo's own sample
  products. Three in Botswana alone, plus "Wireless Bluetooth Headphones /
  Elegant Summer Dress" seed sets. Look at the product names.
- **Wrong country.** Four Shopify stores probed perfectly for American Samoa and
  declared `countryCode` US, AU, NZ. Two Syrian storefronts on Zid proxy
  `api.zid.sa` and report `currency: SAR`, rendering FX-converted SYP for display
  only — onboarding them books Saudi prices as Syrian. **Check `/meta.json`,
  `countryCode`, and `currency_code`.**
- **`robots.txt` pointing at the wrong TLD.** `crazystore.co.bw/robots.txt`
  advertises the `.co.za` sitemap; following it yields 7,053 ZAR-priced South
  African PDPs. Pin the country sitemap explicitly.
- **Zero/placeholder prices.** 3,813 products all priced `0` (quote-on-request);
  hotel rooms all `0`; Odoo with `itemprop="price"` = `0.0` inside a `d-none`
  block.
- **Catalogs under 5 rows.** That is the gate.
- **Diaspora / remittance shops.** A France-based send-to-family shop priced in
  EUR is not a Chadian retail price.

### 4.5 Write the manifest

Copy `src/prices/configs/_examples/template.yaml` to
`src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`.

Four axes plus the operational fields — full schema in the skill's
`references/yaml_schema.md`. The two that bite:

- **`channel:` is REQUIRED on every manifest, even when the value is `null`.**
  Pick only from the `Channel` enum in `src/prices/enrich/schemas.py` — that
  module is the authority. A value outside the enum, **or an omitted key**,
  raises at load time and takes down the *global* `prices collect --list`, not
  just your source. Both have happened.
- **`coicop_codes`** — set it only for narrow sources (whole catalog inside one
  3-digit class). Leave unset for supermarkets; the classifier assigns per
  product.

Add `throttle_group:` if the host shares an edge with an existing family. Reuse
the existing names: `wolt`, `boltfood`, `zakaz`, `o4a2`, `lezzoo`, `takeapp`,
`caribeeats`, `shopify`, `aswatson`, `ikea`, `lulu`, `jarir`, `costuless`,
`courts`, `digicel`, `eurostat`. **Any spider deriving from `ShopifyBaseSpider`
gets `throttle_group: shopify`** — Shopify throttles per client IP across all
storefronts, not per host.

**Do NOT write `archive_prefix` or `archive_path_re`.** Live-URL-derived prefixes
are measured wrong: only 35 of 84 shipped prefixes returned any records, versus
45 of 61 after CDX correction. Leave both out; they get added later from archived
captures.

### 4.6 Verify

```bash
~/venv/bin/python run.py prices collect --source <name> --max-items 200
~/venv/bin/python run.py prices collect --list | tail -1     # must stay rc=0
```

Rows land in
`data/prices/<region>/<subregion>/<country>/<source>/raw_items/*.jsonl`
(spiders) or `price_observations.csv` (fetchers).

**A `--max-items` count is a verification number, not a catalog size.** Measured
on one Bolt Food wave, uncapped re-collects beat the capped figure every time —
`metroexpress_bolt_cy` 132 → 6,002 (45×), `billa_bolt_sk` 171 → 3,870 (22×).
Twelve sources reported as ~32,607 rows actually held 63,118. Never quote the
capped number as the source's size.

Sanity-check the prices themselves. One spider read `E365 995` — a space as the
thousands separator — as **365**, a 1000× error. Another portal had a
240,000,000 XAF property *sale* filed under "Maison à Louer"; as a monthly rent
it would have been the worst row in that country's corpus.

---

## 5. Full scrapes

`--max-items` is for verification only. Two ways to get the real catalog:

**a) The built-in parallel driver** (respects `throttle_group`):

```bash
~/venv/bin/python run.py prices collect -P 12 --timeout 2700
```

Filters: `--region / --subregion / --country / --source`, plus `--resume <rundir>`.

**`throttle_group` is enforced ONLY here**, in `collect_parallel.py`.
`DEFAULT_GROUP_LIMIT = 1`, so each shared-edge family runs one source at a time
and the dispatcher re-queues rather than blocking.

**b) An xargs harness** — `gapwork/landloop.sh` on the Geekom. Every 600 s it
rescans for manifests newer than a marker, subtracts anything already in the
shared ledger `gapwork/landrun/_done.txt`, and runs the rest at PAR=10 with **no
`--max-items`**.

> ⚠️ **An xargs harness bypasses `throttle_group` entirely.** Never point one at
> Watsons, Shopify, or any shared-edge family — 7 parallel Watsons burned 10.5
> slot-hours for 0 rows and then 403'd every storefront including the homepage,
> with zero 429 warning first.

Budget is 2,700 s per source. The biggest catalogues exit `rc=124` truncated but
still bank what they collected (`talabat_eg` 258,272 rows). Those deserve a
longer per-source `timeout:` in their YAML.

---

## 6. Common Crawl — historical recovery

See **`AWS_CC_SWEEP_COOKBOOK.md`** (shipped alongside this file) for the full
procedure, measured costs, and the four silent-truncation traps.

The three things to internalise:

1. **Read WARCs from `s3://commoncrawl` in us-east-1, never the public CDN.**
   The bucket is `Payer=BucketOwner` — Common Crawl pays for our GETs *and*
   transfer, so reading the whole 2.6 TB costs nothing. S3 sustained 228 rec/s at
   concurrency 64 with zero failures; the public CDN bans your whole IP after
   ~20k requests and returns **403, not 429**.
2. **Count non-200s separately from empty results.** Otherwise a ban is
   indistinguishable from an uncrawled site. One early sweep had 3 of 14 indexes
   report zero records for all 185 sources — it meant "blocked", not "no data".
3. **Fix parsers before sweeping.** Failures self-heal (a `no_extract` page
   writes nothing and is re-fetched next pass), but **under-extraction does not**
   — a page that yielded 1 row is in the skip set, so a parser fix that would now
   yield 40 never revisits it.

Full fleet pass: ~9.4 h on 8 `c7i-flex.large`, **~$7**. Parse is pure-Python and
CPU-bound, so instance count is the only throughput lever.

---

## 7. The dashboard

Lives on **`prices/explorer-redesign`** (`src/prices/explorer/`).

```bash
git checkout prices/explorer-redesign
~/venv/bin/python run.py prices explorer --help     # unit-value explorer
~/venv/bin/python run.py prices publish  --help     # CPI dashboards
```

Files you will actually edit: `_template.html`, `_app.js`, `_catfilter.js`,
`_catfilter.css`, `aggregate.py`, `sources.py`.

Two recorded gotchas:

- **The WB intranet blocks `cdn.jsdelivr.net`** — Posit Connect will not load it.
  Inline your JS/CSS rather than CDN-linking it.
- **The dashboard title is stamped at addon-build time from the local clock**, so
  a rebuild on a machine with a skewed clock mislabels the release.

---

## 8. Gotchas that have cost real time

- **Say which machine a number came from.** Mac checkouts lag the Geekom and
  return confidently wrong answers rather than errors.
- **A backgrounded `&` over ssh dies with the connection.** Use
  `setsid nohup … </dev/null &`.
- **`du -sh` on a parent has reported 0 while children held 500 GB.** Measure per
  subdirectory before deleting.
- **`lxml` can silently truncate a page.** `bmsonline.co.bw` emits a second
  `<!DOCTYPE html><html><head>` inside its own head; parsel sees 8.9 KB of a
  76 KB page and every selector returns zero — at HTTP 200, with no error.
  BeautifulSoup `html.parser` returns all 20 cards. Invisible unless you compare
  two parsers.
- **`DuplicationPipeline` drops items sharing a `url`**, which collapses
  one-page catalogs (menus, price lists) to 1-3 rows. Give each row a
  `#<item-slug>` anchor.
- **`lstrip("www.")` strips a character *set*, not a prefix** — it turns
  `wolt.com` into `olt.com`. Use slicing.
- **A silently empty category is worse than an error.** One classifieds site
  spells its food category `Nouriture`; querying `Alimentation` returns an empty
  result and a spider built on it looks healthy while never touching food.
- **Source stems are not unique across countries.** `eurostat_electricity` exists
  once per country (189 manifests). Any census keyed on bare source name
  undercounts — key on `(country, source)`.
- **Same low row count every run is a failure signature**, not a small catalog.

---

## 9. What is in the handover bundle

The handover has two halves, and they live in different places on purpose.

**Code and procedure — from git.** Clone this branch; these are versioned and
are the files you run against:

| File | What it is |
|---|---|
| `src/prices/docs/RUNBOOK.md` | this file |
| `src/prices/docs/AWS_CC_SWEEP_COOKBOOK.md` | the Common Crawl procedure, costs, traps |
| `src/prices/configs/**` | every existing manifest — the anti-overlap ground truth |
| `src/prices/price_scraping/spiders/**` | the spider templates (§4 names the ones to copy) |
| `src/prices/fetchers/**` | the fetcher templates |
| `infra/fetch/**` | the EC2 CC fetch fleet (`launch_fleet.sh`, `ccfetch.py`) |

**Target register — from the zip, not git.** A worklist is a planning artifact
that changes daily; committing one guarantees every clone carries a stale copy
and that two people diverge on which rows are still open. These arrive in
`prices_will_handover_20260912.zip`:

| File | What it is |
|---|---|
| `WILLIAM_HANDOVER.xlsx` | the register of record — your targets, the full pending pool, the country split |
| `FINAL_TARGET_LIST_fnb.csv` | 2,295 F&B targets with the `owner` split |
| `country_owner_split.csv` | per-country assignment; flip a cell to trade a country |
| `pending_worklist_fnb_ranked.csv` | the same pool ranked food-first, with F&B class and grid emptiness |

Re-read the workbook before starting a country. When you finish rows, send the
sheet back with them flipped rather than committing it — the register is
exchanged, the code is merged.

### Templates — use the real files, not copies

Deliberately *not* duplicated into a `templates/` folder, because a copy drifts
from the thing it copies. Use these paths in the checkout:

| What | Path |
|---|---|
| Manifest template | `src/prices/configs/_examples/template.yaml` |
| `channel` enum (the authority) | `src/prices/enrich/schemas.py` |
| YAML schema reference | `.claude/skills/onboard-price-sources/references/yaml_schema.md` |
| Shopify, zero code needed | `src/prices/price_scraping/spiders/generic_shopify_configured.py` |
| WooCommerce, zero code needed | `src/prices/price_scraping/spiders/generic_woo_configured.py` |
| OpenCart / PrestaShop | `generic_opencart_configured.py`, `generic_prestashop_configured.py` |
| Woo needing JS | `generic_woo_playwright.py` |
| Base classes to subclass (~10 lines) | `_jsonld_sitemap_base.py`, `_woo_base.py`, `_shopify_base.py`, `_magento_base.py`, `_vtex_base.py` |
| Worked bespoke examples | `nhamburguer_gw.py` (perPage ladder), `market231.py` (`?skip=` pagination), `bms_bw.py` (BeautifulSoup fallback), `crazystore_bw.py` (pinned country sitemap) |
| CC resolve / fetch | `src/prices/cc_resolve.py`, `src/prices/cc_fetch.py`, `infra/fetch/`, `infra/resolve/` |
