# Known Online-Newspaper Aggregators

Pre-extracted per-country newspaper lists from five sources — four online-newspaper aggregator sites plus GDELT's domains-by-country monitoring list. Used by `/onboard-region-newspapers` step 2a as a static seed instead of refetching aggregator homepages every run.

## File layout

One file per region, in this directory:

- `eap.md` — East Asia & Pacific
- `eca.md` — Europe & Central Asia
- `menaap.md` — Middle East, North Africa, Afghanistan & Pakistan
- `sar.md` — South Asia
- `ssa.md` — Sub-Saharan Africa
- `lac.md` — Latin America & Caribbean

Each file groups countries by H2 sections keyed on the country slug (e.g. `## china`), with five nested H3 sub-sections — one per aggregator — each followed by a bullet list of `<outlet name> — <outlet url>` lines. When an aggregator has no entry for a country, the H3 reads `(not listed)` and the bullet list reads `- (no entries)`.

To find a country fast: grep `^## <country_slug>` in the relevant region file.

## Aggregators covered

| aggregator | how it was fetched at population time |
|---|---|
| **w3newspapers** | Playwright (Chromium, headless) — pages are JS-rendered, `httpx`/`WebFetch` return empty body |
| **onlinenewspapers** | `httpx` — regional sitemaps at `/sitemap/<continent>.shtml` enumerate per-country `.shtml` URLs |
| **allyoucanread** | `httpx` — top-level `/newspapers/` page enumerates per-country `<slug>-newspapers/` URLs |
| **abyznewslinks** | `httpx` — `allco.htm` enumerates per-country `.htm` URLs; per-country pages are pre-classified by media type, populator filters to **Internet + Newspaper** sections only (skips Broadcast TV/radio and Press Agency wires) |
| **gdelt** | `httpx` — one flat CSV ([2015-2021 domains-by-country](https://blog.gdeltproject.org/mapping-the-media-a-geographic-lookup-of-gdelts-sources-2015-2021/)), *not* per-country pages. Each domain is argmax-assigned to its highest-affinity country (FIPS 10-4 → ISO3 → slug via `countries.yaml`), then ranked by GDELT monitoring volume and capped per country (default top 40; the section header shows `top N of M`). Entries are bare domains with no curated outlet name, so the tail is noisier than the four curated aggregators (government, tourism, airline, party sites survive) — apply the local-only filter and the `/assess-newspaper-source` gate harder here. Its strength is *recall* of genuine local outlets the curated four miss (e.g. small Pacific markets: `fijitimes.com`, `fbc.com.fj`, `samoaobserver.ws`, `postcourier.com.pg`). Crosswalk + harvest live in `scripts/gdelt_source.py`. |

## Ignore rules (applied during population)

The populator drops any link whose target matches one of the following at extraction time. The skill does **not** need to re-apply these — the pre-extracted lists are already filtered:

- Wikipedia / Wikimedia (`*.wikipedia.org`, `*.wikimedia.org`) — encyclopedic, not news
- BBC (`*.bbc.co.uk`, `*.bbc.com`) — country-profile / world-* hubs are not local news
- CIA Factbook (`*.cia.gov`)
- Foreign wire-service hubs: Reuters, AFP, AP, Al Jazeera, France 24, RFI, VOA, DW, CNN, Bloomberg, NYT, WaPo, The Guardian
- Social platforms: Facebook, Twitter/X, YouTube, Instagram, LinkedIn, Pinterest, Tumblr, Telegram
- Aggregator self-links: w3newspapers, onlinenewspapers, allyoucanread, abyznewslinks
- Path fragments commonly indicating non-news pages: `wiki/`, `factbook`, `country-profiles`, `/news/world-`

The skill should still apply the **local-only filter** documented in `SKILL.md` step 2a (drop diaspora-edited sites, off-country editorial framing, etc.) on top of the pre-extracted lists — that filter is judgement-based and complementary.

## Refreshing this directory

The data is pre-extracted and lightly noisy by design (sports/lifestyle/aggregator-internal noise survives sometimes); the skill's downstream `/assess-newspaper-source` pass weeds out non-suitable candidates per outlet.

To refresh:

```bash
poetry run python ~/.claude/skills/onboard-region-newspapers/scripts/populate_known_aggregators.py \
  --regions /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src/configs/regions.yaml \
  --countries /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src/configs/countries.yaml \
  --out ~/.claude/skills/onboard-region-newspapers/references/known_aggregators/
```

Idempotent — re-running overwrites the per-region files. Wall time ~15-25 minutes for all 215 countries (Playwright per-page latency dominates).

If a single country needs refresh while iterating on the populator, use `--limit N` to cap.

To refresh **only** the GDELT section (fast — one CSV download, no Playwright, leaves the four HTML-aggregator sections byte-for-byte), pass `--gdelt-only`:

```bash
poetry run python .../scripts/populate_known_aggregators.py \
  --regions .../src/configs/regions.yaml \
  --countries .../src/configs/countries.yaml \
  --out .../references/known_aggregators/ \
  --gdelt-only            # optional: --gdelt-cap N (default 40, 0=uncapped)
```

Idempotent: any existing `### gdelt` section is replaced in place. The CSV is cached at `<out>/.gdelt_domains.csv` (override with `--gdelt-cache`).

## Country-slug ↔ aggregator-name mapping

When a country's display name differs from the aggregator's listing label (e.g. our `cabo_verde` vs. their "Cape Verde", `cote_divoire` vs. "Ivory Coast", `russian_federation` vs. "Russia"), the populator uses an alias map defined inside the script (`NAME_ALIASES`). Add new aliases there if you discover a country that resolves to `(not listed)` despite the aggregator clearly listing it under a different name.
