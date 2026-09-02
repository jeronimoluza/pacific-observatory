# Greenland — price source inventory (eca/western_europe/greenland)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- no scrapeable
grocery e-commerce found this pass.**

## Dead ends checked

| Candidate | What | Why it doesn't work |
|---|---|---|
| `pisiffik.gl` | Pisiffik -- Greenland's largest private retail company, ~40 stores | Live PrestaShop storefront (real product pages, EAN-coded SKUs) but the catalogue is mattresses, kitchenware, small electronics, furniture and toys, with only incidental wine/sparkling-wine categories. This is Pisiffik's **department-store** e-commerce arm, not catalogue-led by COICOP 01/02 -- fails win criterion #1. |
| `brugseni.gl` | Brugseni (KNI) -- the other major Greenlandic chain | WordPress corporate site (Yoast SEO plugin), store-locator only (`/butikker/`), no webshop link anywhere. |
| `pilersuisoq.gl` | Pilersuisoq -- government-linked chain serving small settlements | Brochure site, no shop link, no e-commerce platform fingerprint of any kind. |
| `brugsen.gl` | (no "i", guessed variant) | TLS certificate hostname mismatch -- does not serve the real site. |

## Next steps for a future pass

- If Pisiffik's electronics/general-merchandise arm is ever wanted for a
  non-food division (COICOP 05/06/09-adjacent), the PrestaShop catalog at
  `pisiffik.gl` is fully scrapeable (Tier 1A, real PDP pages) -- just not
  a food-and-beverage win.
- No genuine grocery e-commerce sector was found to exist for Greenland
  this pass; Greenland's remote settlement structure (small towns served
  by government-subsidized Pilersuisoq stores) makes a delivery-style
  online grocery offering structurally unlikely, but this was not
  independently confirmed via search (budget exhausted -- see
  faroe_islands.md for the same constraint).

---

## UPDATE 2026-09-01 (second pass) — dead ends CONFIRMED, and Pisiffik re-measured

Re-probed independently 2026-09-01 with `curl_cffi impersonate=chrome124`. All
live, none WAF-blocked. The pass above is **correct on every count**; this only
adds measurement where it had inference.

| Domain | Status | Price tokens on homepage | Verdict |
|---|---|---|---|
| `pisiffik.gl` | 200, 1.48 MB | **491** (DKK) | Real webshop — but non-food, see below |
| `brugseni.gl` | 200, 153 KB | **0** | Brochure-only, confirmed |
| `pilersuisoq.gl` | 200, 60 KB | **0** | Brochure-only, confirmed |
| `brugsen.gl` | TLS `CertificateVerifyError` on chrome124 AND safari17_0 | — | Not the real site, confirmed |

**Pisiffik is a genuine, fully-open webshop** — 491 DKK price tokens, 379 "kurv"
(basket) occurrences, 7,298 "product" occurrences on the landing page alone, no
anti-bot of any kind. But its `<title>` is *"Pisiffik.gl - Elgiganten, Jysk,
Thansen og mange flere"* and its visible price points (4.000 kr, 7.199 kr,
3.199 kr) are electronics, furniture and auto-parts franchises. This confirms
the earlier read: Pisiffik's e-commerce arm is its **department-store** side, and
its supermarket business is not online. Not a food win.

A Greenlandic-language search was run this pass (budget was available) and
surfaced no fourth operator — Brugseni, Pisiffik and Pilersuisoq are the whole
market. Combined with Greenland's settlement structure (small towns served by
subsidised Pilersuisoq stores), **treat "no online grocery" as a structural
absence for Greenland**, not a search gap.

Standing offer from the pass above still holds: if a non-food division ever wants
Greenland, `pisiffik.gl` is Tier 1A and trivially scrapeable today.

---

## UPDATE 2026-09-01 (third note) — Pisiffik SHIPPED as a non-food source.

**Result: 1 source shipped — `pisiffik_gl`. Greenland is no longer greenfield.**

Both passes above correctly identified `pisiffik.gl` as a real, fully-open
webshop and correctly identified it as non-food, then skipped it on that basis.
Under the standing instruction that **non-food sources are wanted too**, being
non-food is no longer a reason to skip: a country with one non-food source beats
a country with none, and the food verdict here is a structural absence
(Brugseni and Pilersuisoq are brochure-only, 0 price tokens each) rather than a
search failure. There is no Greenlandic food e-commerce to find.

PrestaShop 1.7, Tier 1A, no anti-bot. `article.product-miniature` cards carry
full schema.org microdata — `[itemprop="price"]::attr(content)` gives a clean
decimal ("5249.25") and sidesteps the Danish display format ("5.249,25 kr.",
period thousands / comma decimal) that a digit-strip would read as 524925.

Test run 2026-09-01: 129 rows / 83s, all HTTP 200, 129 distinct ids and urls,
0 blanks, 0 non-positive prices, 100% DKK, breadcrumb categories populated,
prices 18–3,099 DKK.

**CRAWL POLICY — read before touching this spider.** pisiffik.gl publishes an
unusually explicit robots.txt: ~35 named AI-training and SEO crawlers blocked
outright (GPTBot, ClaudeBot, anthropic-ai, Claude-Web, CCBot, PerplexityBot,
AhrefsBot, SemrushBot...) with the rationale "no SEO benefit, high resource
cost", plus a Bingbot throttle citing "169 hits in one window". The generic
`User-agent: *` group does NOT disallow category or product pages but sets
`Crawl-delay: 5`. The repo runs `ROBOTSTXT_OBEY = False` globally, so nothing
enforces this — the spider pins `DOWNLOAD_DELAY = 5.0` and one concurrent
request in `custom_settings`, and hard-excludes the two Disallow-ed category ids
(445, 1132) and every Disallow-ed query pattern. Do not raise the rate.

This is an operator-preference judgement, not settled policy: the named blocks
target AI-training crawlers rather than price collection. If that reading is
rejected, drop the manifest.

**Known coverage limit:** category discovery walks homepage links only and finds
45 categories. The site has more behind nested navigation, so this is a partial
catalogue, not the full one. Deepening category discovery is the obvious next
improvement.
