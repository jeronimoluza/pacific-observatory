# Search execution — `ddgs`, in English and local languages

Load this in Phase 2 whenever a step calls for *searching*. It covers how to run
the search, not what to search for — targeting doctrine stays in `discovery.md`.

**Use the `ddgs` Python library, not WebSearch.** WebSearch has a session-wide
call cap (~200, shared across every sub-agent in the run), so it forces discovery
into a handful of careful queries. `ddgs` is a local library hitting public search
backends: a 60-query sweep costs a couple of minutes and no session budget. That
difference is not cosmetic — see "Why breadth is the point" below.

## Install and the one call that matters

```bash
python3 -m venv .ddgsenv && ./.ddgsenv/bin/pip install ddgs curl_cffi
```

```python
from ddgs import DDGS

BACKENDS = "duckduckgo, google, brave, mojeek, startpage, yahoo"

with DDGS() as d:
    results = d.text(query, backend=BACKENDS, max_results=20)
# each result: {"title": ..., "href": ..., "body": ...}
```

## MANDATORY: pin `backend=`

`ddgs` rotates across eight text backends, two of which — `wikipedia` and
`grokipedia` — are encyclopedias, not web search. They find no storefronts, and
the `wikipedia` backend builds its host from the `region` argument: with the
common `region="wt-wt"` it requests `wt.wikipedia.org`, which does not exist, and
the query **raises a DNSError that surfaces as zero results**.

Measured on the 2026-09-10 Botswana run: **9 of 23 queries returned 0 results**
for this reason alone. Re-run with `backend=` pinned, all 14 returned 14–18 hits.

Consequences, both of which have bitten:

- **A 0-result `ddgs` query is not evidence of absence.** It is indistinguishable
  from "this backend DNS-failed." Never write a dead-end row in an inventory file
  on the strength of a 0-result query without re-running it with backends pinned.
- Log the per-query hit count as you sweep. A row of zeros means the backend
  config is wrong, not that the country has no retail.

## Query pack: English *and* local languages

Build one pack per country, across these axes, and run **all** of them. Twenty to
sixty queries is a normal sweep.

| Axis | English shape | Local-language shape |
|---|---|---|
| Grocery / delivery | `online grocery <country> delivery` | native words for *food*, *buy*, *shop*, *market*, *price* |
| Named chains | `<chain> online shopping` — one per chain from Wikipedia/listicles | same, in-script |
| Platform fingerprint | `"powered by Shopify" <country>`, `"wp-json/wc/store" <country>`, `site:*.<cctld> "add to cart"` | rarely useful — markup is English |
| Beverages | `<country> liquor store online`, `buy wine online <country>` | native words for *beer*, *bottle store* |
| Cities | `<capital> online grocery delivery`, plus 2–3 secondary cities | same |
| Official | `<NSO name> retail prices`, `<country> agricultural marketing board prices` | native ministry/board names |

Take the local languages from `src/configs/countries.yaml` (`languages:`), and add
the regional lingua franca where trade crosses a border — for Botswana that meant
Afrikaans alongside Setswana, because South African chains operate there.

### What local-language search is actually worth

It varies enormously by country, and the run should measure rather than assume.
Tag every result with the query that produced it, then report how many domains
were found **only** by local-language queries.

Botswana, 2026-09-10: Setswana + Afrikaans produced 46 domains no English query
returned, but ~42 were academic or linguistic noise — exam papers, Bible
translations, university repositories. Net real yield was **one** live marketplace
(`mmaraka.app`) plus three weak leads. `countries.yaml` lists Botswana as `[en]`
and its retail really is English-language.

The rule that generalises: **local-language search pays in proportion to how much
of the country's commerce is conducted in that language.** For CJK, Thai, Vietnamese,
Arabic, Indonesian markets it is the strongest generator after marketplaces and
absolutely must be run. For an anglophone market with a national language that is
spoken but not transacted in, run one cheap pass, measure it, and record the result
so the next run does not over-invest.

Either way it costs minutes with `ddgs`, so run it — just do not let a thin
local-language yield read as "discovery failed."

## Filter the noise before probing

A raw sweep is ~30–50% junk. Resolve every `href` to a registrable domain,
de-duplicate, and drop:

- social and app stores — `facebook`, `instagram`, `linkedin`, `tiktok`,
  `apps.apple.com`, `play.google.com`
- data/listicle aggregators — `statista`, `tripadvisor`, `hikersbay`,
  `selinawamucii`, `localbotswana`-style top-10 pages
- academic and document hosts — `academia.edu`, `scribd`, `studocu`,
  `files.eric.ed.gov`, `*.ac.*` repositories (these dominate local-language noise)
- the cost-of-living survey publishers — `numbeo`, `livingcost`, `expatistan`,
  `mylifeelsewhere`, `nomadlist`. Never candidates, per `discovery.md`.
- global shippers that merely *deliver* to the country — `ubuy`, `desertcart`,
  `parceldaddy`. They are not in-country retail and their prices are not local.

Then cross-check the survivors against `known_blockers.md` and the country's
existing manifests before spending any probe budget.

## Why breadth is the point — the off-domain storefront rule

`discovery.md` ranks generic English search last, and that ranking still holds
*per query*. What `ddgs` changes is that breadth becomes nearly free, and breadth
buys something a handful of careful queries cannot:

> **A chain's online store frequently lives on a different domain than its
> corporate site.** Probing the corporate domain and recording a dead end is a
> false negative, and it is the single most expensive mistake in this phase —
> it writes off the country's biggest retailer.

Botswana, all four majors:

| Chain | Corporate site (what a careful query returns) | Actual storefront (what a wide sweep returns) |
|---|---|---|
| Sefalana | `sefalana.co.bw` | **`shopsefalana.com`** — nopCommerce, open `/api/products`, ~316,600 products |
| Choppies | `choppies.co.bw` | **`echoppies.com`** — Next.js storefront |
| SPAR | `spar.co.bw` | **`spar2u.co.bw`** |
| Pick n Pay | `pnpbotswana.co.bw` | WhatsApp-order only — a genuine null |

A prior WebSearch-budgeted run recorded Choppies **and** Sefalana as dead ends
after probing the corporate domains. The 2026-09-10 `ddgs` sweep found both
storefronts and verified Sefalana as fully enumerable. Three of four "dead ends"
were false.

So when a chain looks dead, spend three more queries before writing the null:
`<chain> online shop`, `<chain> online supermarket`, `buy <chain> online`, and
scan for a *sibling* domain rather than a path on the corporate one.

## Sweep skeleton

```python
import json, time
from ddgs import DDGS

BACKENDS = "duckduckgo, google, brave, mojeek, startpage, yahoo"

with DDGS() as d, open("sweep.jsonl", "w") as out:
    for q in QUERIES:                     # English + local-language pack
        try:
            res = d.text(q, backend=BACKENDS, max_results=20)
        except Exception as e:
            res = []
            print(f"ERR {q}: {type(e).__name__}")
        for r in res:
            out.write(json.dumps({"q": q, **r}) + "\n")
        out.flush()                        # so a mid-sweep crash keeps the work
        print(f"{len(res):3d}  {q}")       # a run of 0s means backends are wrong
        time.sleep(1.5)                    # be polite; no rate limit hit at this pace
```

Keep the `{"q": ...}` tag on every row — it is what lets you attribute domains to
English vs local-language queries at the end, which is the measurement the next
run needs.

Feed survivors into Phase 2.5 and continue normally. `ddgs` replaces the *search*
step only; probing is still `curl_cffi` per `probe_patterns.md`, and the
access-vs-enumerability gate in Phase 3 is unchanged.
