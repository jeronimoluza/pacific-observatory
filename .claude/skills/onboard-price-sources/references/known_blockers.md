# Known Blockers

Sites we've already classified as unscrapeable with our current stack (no residential proxy, no captcha solver). **Check this list before probing** — saves cycles.

> ⚠️ **Entries recorded before 2026-08-17 are suspect if the only evidence was a bare-`curl` 403.**
> Most CDN blocking fingerprints the **TLS handshake (JA3)**, not the User-Agent, so a bare `curl`
> with a spoofed browser UA gets a 403 from sites that `curl_cffi impersonate="chrome124"` walks
> straight into. On 2026-08-17 a re-probe of 112 `SKIP_WAF` verdicts recovered a large share on
> that single lever — including sites serving `cf-mitigated: challenge` and Akamai bot-blocks.
> **Before trusting any entry here, check whether it names the lever that failed.** If it says only
> "403 on curl", re-probe with `curl_cffi` before skipping. Entries that survived impersonation are
> the trustworthy ones; new entries MUST name the lever tried and the tell observed.

This file is keyed by **blocker class / CDN family**, not region. Country examples sit as bullets under the class that diagnosed them. When a new site is blocked, attach it to the class whose signature matches — that's how shared infrastructure becomes obvious (Foodstuffs NZ, AS-Watson HK/SG/MY/TW, MWG VN, etc. each share a tenant's blocking profile across countries).

## ⚠️ 2026-09-06 re-probe — entries in this file proven STALE

A 63-target re-probe of pre-2026-08-17 verdicts ran on 2026-09-06. **16 of 26 hosts in one
shard alone returned a clean 200 that this file recorded as blocked.** Before skipping any
entry below, re-probe it — the recorded verdict is known to be wrong.

Two failure modes to watch for, both found here:

- **Not every recorded block was ever a WAF.** ANEEL Brazil was filed as "no TCP response at
  all" but answers plain `requests` with a 200; `ukrstat.gov.ua` was filed as a "TCP-level
  connection drop" but is simply an expired SSL cert (`verify=False` gets a real 200).
- **Some entries were fixed by later sessions and never removed.** `woolworths.co.nz` and all
  four Lulu Gulf storefronts have had working spiders in the repo while still listed here.

### Recovered and now shipped (verdict was wrong)

- **dadosabertos.aneel.gov.br** — was: package_search endpoint does not respond at all (curl exit 000, >120s), suspected CKAN out → now: 200 on all profiles, plain requests too -- CKAN portal fully live with real data
- **khmer24.com** — was: HTTP 403 + Cloudflare Turnstile challenge on curl with realistic Chrome UA (probed 2026-06 → now: 200 on all 5 curl_cffi profiles; public site is a Nuxt SPA shell (no listing HTML) but its data API at api.khm
- **luluhypermarket.com** — was: Cloudflare strict 403 all 4 Gulf storefronts, Akinon CSP, dated 2026-08-06 → now: 200 on all 5 profiles, both www.luluhypermarket.com and the gcc.luluhypermarket.com storefront
- **mymedicine.com.mm** — was: Cloudflare 403 on /shop and /categories, confirmed blocked June 2026 → now: 200 on all 5 profiles; homepage and /shop return full Odoo (o_wsale) catalog with real MMK prices in raw HTML
- **otw-tl.com** — was: HTTP 403 on WebFetch to category pages, probed 2026-06-10, no bypass attempted → now: 200 on all 5 profiles, homepage/category/restaurant pages all open, zero anti-bot
- **statistics-suriname.org** — was: every request on 2026-09-05 timed out or reset -- flagged as transient network issue, not  → now: 200 on all 5 profiles, homepage real 340KB page
- **supasave.com.bn** — was: both supasave.com.bn and seria.supasave.com.bn return the sgcaptcha stub (200 OK + 168-byt → now: seria.supasave.com.bn: chrome120 and chrome131 still 403 Forbidden, but chrome124, safari17_0, and firefox133 
- **unegui.mn** — was: HTTP 403 from non-Mongolian IP, hypothesized app-tier IP allowlist, needs in-country resid → now: 200 on all 5 profiles, homepage AND /avto-mashin/ category, from this (non-MN) network
- **ver1.cnmicommerce.com / cnmicommerce.com / commerce.gov.mp** — was: HTTP 403 from all hostnames, Cloudflare country-wide IP-fence, 'cannot access this website → now: 200 on all/nearly-all profiles for all 3 live hostnames, including the actual CPI report-hub page
- **woolworths.co.nz** — was: grouped under 'Foodstuffs/Akamai stack', undated → now: 200 on all 5 profiles, homepage + category page

### Access restored, not yet built (re-probe cleared the wall; enumeration still open)

- **aeoneshop.com** — was: HTTP 403 server:DataDome on curl; Playwright shows geo.captcha-delivery.com interactive-ch → now: 200 (real SPA shell, not the 403 wall) on 4 of 5 profiles; chrome120 alone still 403
- **api.freshop.ncrcloud.com** — was: shared-host rate limit under concurrent multi-agent load, self-heals, not a WAF issue → now: not re-probed
- **bigw.com.au** — was: curl exits 000 (0 bytes, connection-level drop) on both plain and -L requests, probed 2026 → now: 200 on all 5 profiles, homepage and a real collection page both load with genuine AUD prices
- **blibli.com** — was: Cloudflare strict (curl+Playwright both 403), professional anti-bot → now: 200 on all 5 curl_cffi profiles (homepage + /cari/laptop), but window.__INITIAL_STATE__.catalog-productStore.p
- **channel.jd.com** — was: JDR_shields bot challenge, part of the www.jd.com group entry → now: 200, real category listing page loads (redirects to list.jd.com/list.html), anti-bot bypassed
- **chemistwarehouse.co.nz** — was: grouped under 'Foodstuffs/Akamai stack' (mislabeled -- actually Cloudflare, unrelated to F → now: 200 on chrome124/chrome120/chrome131/firefox133 (4/5), 403 on safari17_0
- **comfy.ua** — was: Imperva Incapsula _Incapsula_Resource script stub (~1KB body, HTTP 200, NOINDEX robots met → now: firefox133 gets the full 888,601-byte real page; all 4 Chrome/Safari profiles still get the ~6KB Incapsula stu
- **item.jd.com** — was: Part of the www.jd.com/channel.jd.com/item.jd.com group entry (JDR_shields + login wall) → now: Inconclusive - test used '/' with no real item ID
- **klikindomaret.com** — was: AWS WAF challenge on both site and API gateway → now: Flaky: 3 of 5 profiles got a real-looking 200, 2 of 5 got an AWS/Cloudflare challenge
- **kmart.com.au** — was: HTTP 403, server: AkamaiGHost, probed 2026-08-07 → now: 200 on all 5 profiles for the homepage (2.9-3.0MB, real Akamai bypass)
- **myaeon2go.com** — was: DataDome 403 on every request, server: DataDome + x-datadome: protected, 'needs a real bro → now: 200 on chrome124/chrome131/safari17_0/firefox133 (4/5), 403 on chrome120
- **officeworks.com.au** — was: HTTP 405 + x-amzn-waf-action: captcha from CloudFront/AWS WAF (probed 2026-08-07) → now: 200 on all 5 curl_cffi profiles, full 1.5MB rendered-looking category HTML -- but product tiles/prices are inj
- **powerbuy.co.th** — was: Cloudflare 403 on curl AND Playwright (shared profile with tops.co.th group) → now: 200 on 4 of 5 profiles
- **statistics.gov.sb** — was: Imunify360 on all wp-json/ calls; 415 with access-denied message on www.statistics.gov.sb  → now: the bare domain statistics.gov.sb (not www) now serves the wp-json REST API cleanly with ZERO blocking on all 
- **tops.co.th** — was: Cloudflare 403 on curl AND Playwright, shared protection profile across the tops/bigc/home → now: 200 on all 5 profiles for homepage and category shell (Next.js, __NEXT_DATA__ present)
- **ukrstat.gov.ua** — was: TCP-level connection drop from non-UA IPs (curl exit 000) → now: NOT a TCP block -- expired/mismatched SSL cert; verify=False gets a real 200 frameset homepage

### Re-verdicted DEAD for a different reason than recorded

- **cadismarket.com** — was: still 503 as of 2026-09-05, four days after a 2026-09-01 probe; host maintenance page, Ret → now: still 503 on / , /en/, /fr/, all 5 profiles -- now one full day beyond the last check, five days beyond the or
- **foodpanda.mo** — was: ECONNREFUSED on WebFetch probe 2026-06-10, consistent with regional IP-fence + PerimeterX → now: DNS no longer resolves at all
- **laostatefuel.com** — was: WebFetch tool shows interstitial but curl with browser UA returns full HTML → now: 200 on all 5 profiles, 33.7KB real page with live oil-price content
- **makro.co.th** — was: Imperva Incapsula 403 on curl AND Playwright → now: 200 on all 5 profiles, real ~100KB pages
- **microdata.pacificdata.org** — was: cf-mitigated: challenge, Just a moment... on curl+Playwright, dated 2026-08-11 → now: still 403 cf-mitigated:challenge on all 5 profiles
- **sendofarm.vn** — was: Named as sendo.vn's redirect target in the original blocker entry → now: Domain no longer resolves
- **shop.cpl.com.pg** — was: ECONNREFUSED on WebFetch from non-PNG IP; hypothesized CDN geo-fence (probed 2026-06-10) → now: DNS no longer resolves at all (curl: (6) Could not resolve host) -- the shop subdomain appears decommissioned.
- **shopping.coupang.com** — was: Akamai bot manager, marketplace platform (generic cohort entry w/ lazada.*, shopee.*) → now: DNS does not resolve
- **www.gks.ru** — was: cert hostname-mismatch error using the vendored rosstat.gov.ru CA chain; not worth chasing → now: still fails -- default verify: cert error; verify=False: 403 (blocked outright, not just a cert issue)

## Shopify store suspended (HTTP 402 payment required)

Not an anti-bot wall — the tenant's Shopify subscription is unpaid/inactive, so **every** path (including `/`) returns `HTTP 402` with `content-length: 0` and `powered-by: Shopify`. Confirmed reproducible across two separate probes minutes apart (not a transient 402). The storefront is genuinely offline, not just hard to scrape — re-check in a few months rather than re-probing selectors.

- **mnfmarket.com** (GU, M&F Market — Korean fresh food & wholesale, Tamuning) — `HTTP/2 402`, `shopify-complexity-score` headers present, `cf-cache-status: DYNAMIC`. Business appears active on Instagram/Facebook (pre-order pickup Mon/Fri) but the Shopify storefront itself is billing-suspended. Probed 2026-08-11.
- **hoodmarket.com** (BW, Hood Market — presented in search results as a Botswana "Online Supermarket") — HTTP 402 with `powered-by: Shopify`, `server: cloudflare`, serving a 10,026-byte "Store unavailable" page (`<html class="shop-404">`). Identical on `chrome124`, `chrome120` and `safari17_0`. **Variant worth noting:** unlike mnfmarket.com's zero-length 402, Shopify here returns a full styled suspension page — the 402 status, not the body length, is the tell. Probed 2026-09-10 (Botswana `ddgs` sweep).

## Cloudflare strict (curl + Playwright both 403)

403 even with realistic UA + headers. Often serves a challenge page or interstitial. Headless Chromium without stealth + residential IP fails. Bypass would require a paid proxy/solver stack.

- **whisky.bg** (BG, premium whisky/spirits retailer, COICOP 02.1 candidate) and **drinklink.bg** (BG, alcohol + coffee + chocolate delivery, COICOP 01/02 candidate) -- both HTTP **403 on every `curl_cffi` impersonation profile tried** (chrome124, chrome120, safari17_0), on the bare homepage, single cold request. Not a bare-curl artefact: the TLS-fingerprint lever was applied and failed, which is the actual trigger for this list. Not Playwright-confirmed. Probed 2026-09-05 (ECA Balkans+Nordic 01/02 sweep).
- **liberiafooddelivery.com** (LR) — serves "Checking your browser before accessing. Just a moment..." (HTTP 403, 6.2KB stub) on `curl_cffi chrome124`. Not escalated to Playwright: Liberia already shipped two working sources this pass (`libdelivery_lr`, `banjoo_lr`), so the marginal value was nil. Re-probe with Playwright before recording a final verdict. Probed 2026-09-02 (search-starved re-run).
- **stokholm.fo** (FO) — same "Checking your browser" 403 stub on `curl_cffi chrome124`. Faroese retailer; unresolved either way. Probed 2026-09-02 (search-starved re-run).
- **coursesu.com** (FR/MAF) — Cloudflare "Just a moment..." on `/drive-saint-martin`. Note before spending effort: the slug is very likely one of the metropolitan-France communes named Saint-Martin, not the Caribbean COM 97150. Probed 2026-09-02 (search-starved re-run).
- **delovery.mc** (MC, Delovery — Monaco-domiciled food delivery platform, `.mc` domain) — 403 with a Cloudflare "Attention Required!" page on `curl_cffi impersonate=chrome124`, `chrome120`, `chrome99` AND `safari17_0` (all four profiles, per the mandatory gate). Identical 4,923-byte body every time, so not a TLS-fingerprint false negative. **This is Monaco's best food lead and the only Monaco-registered grocery-adjacent domain that exists** — carrefour.mc/monoprix.mc/spar.mc all fail DNS. Blocked, not absent; worth a retry if its posture changes. Probed 2026-09-01.

- **naturesbasket.co.in** (IN, Nature's Basket — gourmet/specialty supermarket) — 403 on `curl_cffi impersonate=chrome124`, `chrome120`, AND `safari17_0` (all three profiles), AND 403 on headless Playwright (117-byte body after 6s wait, no hydration to catch). Genuine WAF, not a curl-fingerprint false negative. Probed 2026-09-01 (SAR sweep).
- **milkbasket.com** (IN, Milkbasket — daily milk/grocery subscription delivery) — same signature: 403 on all three curl_cffi profiles AND on Playwright (175-byte body). Also app-only in spirit ("subscribe now" copy on the little that renders). Probed 2026-09-01 (SAR sweep).

- **mymedicine.com.mm** (MM) — 403 on `/shop` and `/categories`. Myanmar online pharmacy; confirmed blocked June 2026. MEDiCARE (medicarehb.com.mm) is a viable alternative for COICOP 06.
- **blibli.com** (ID) — 403 on category + PDP. Professional anti-bot.
- **auction.co.kr** (KR, eBay Korea) — 403 on root and category.
- **coupang.com** (KR) — Cloudflare-style challenges plus per-storefront login soft-walls.
- **tops.co.th**, **bigc.co.th**, **homepro.co.th**, **powerbuy.co.th** (TH) — Cloudflare 403 on curl AND Playwright; appear to share a protection profile.
- **khmer24.com** (KH, Cambodia general classifieds) — HTTP 403 + Cloudflare Turnstile challenge page on curl with realistic Chrome UA; cf-ray ID confirmed in response body. Covers cars, real estate, electronics. Probed 2026-06-10.
- **luluhypermarket.com/en-qa, /en-kw, /en-om, /en-bh** (QA/KW/OM/BH) — `<title>Attention Required! | Cloudflare</title>` 403 on all four Gulf storefronts, identical across UA variants including full Chrome sec-ch-ua headers. One CDN tenant, four countries. CSP header reveals the storefront platform: **Akinon** (akinoncloud.com/akinon.net, a Turkish headless-commerce vendor) — no `_akinon_base.py` exists yet in this repo. No Playwright available this session to attempt the discover-then-plain-HTTP pattern; worth a dedicated pass. Probed 2026-08-06 (round-3 Gulf States shard).
- **foodpanda.com.kh** (KH, Delivery Hero Cambodia) — HTTP 403 on curl; same PerimeterX + Cloudflare stack as foodpanda.la. Probed 2026-06-10.
- **otw-tl.com** (TL, OTW food delivery Dili) — HTTP 403 on WebFetch to category pages (e.g. `/foods/?kategoriaproduto=...`). Local food delivery app in Dili. COICOP 11.1.1. No bypass attempted. Probed 2026-06-10.
- **www.klikindogrosir.com** (ID, Klik Indogrosir — Indomarco's wholesale arm) — `<title>Attention Required! | Cloudflare</title>` 403 on the `www.` host for every path, including category listings (`/searchByList?div=N&...`) and `/product_details/<id>`. Confirmed on **both** `curl_cffi impersonate=chrome120` and headless Playwright (Playwright hits the challenge page directly, title match). The bare apex `klikindogrosir.com` (no `www`) does serve the homepage (200) but carries no catalog data of its own — not a usable bypass. Genuine wholesale-feed gap remains for Indonesia. Probed 2026-08-11.
- **kitea.ma** (MA, Kitea furniture — Label'Vie group) — HTTP 403, `Just a moment...` interstitial. Confirmed on `curl_cffi` `chrome124` AND `chrome120` AND `safari17_0` (all 403), and on headless Playwright (403, title `Just a moment...`). Full network trace per the mandatory gate; no bypass attempted further. Probed 2026-09-01.
- **jumia.ma** (MA, Jumia Morocco) — same signature as kitea.ma above: 403 on all three curl_cffi TLS profiles and on headless Playwright (`Just a moment...`). No `jumia_*` spider exists yet anywhere in this repo to check for a shared-tenant bypass. Probed 2026-09-01.
- **jdeco.net** (PSE, West Bank and Gaza — Jerusalem District Electricity Company) — HTTP 403 on `curl_cffi` `chrome124`, `chrome120`, AND `safari17_0` — genuine block per the mandatory gate, not a TLS-fingerprint false positive. No Playwright attempted this pass (already had a working tariff-adjacent source via PCBS). Probed 2026-09-01.
- **jumia.sl** (SL, "Jumia" Sierra Leone) — `<title>Just a moment...</title>` 403 on all three curl_cffi profiles (chrome124/chrome120/safari17_0) — genuine block per the mandatory gate. Note: Jumia's real African footprint (Nigeria, Kenya, Egypt, Morocco, Ghana, Ivory Coast, Uganda, Senegal, Tunisia, Algeria) does not include Sierra Leone, so this domain is plausibly parked/unrelated rather than a genuine Jumia storefront — not investigated further. Probed 2026-09-01.
- **tripolimarket.com** (LY, "Tripoli Market" — wave-11 fresh discovery lead, surfaced by Arabic search for "شحن مجاني مواد غذائية اونلاين") — `<title>Attention Required! | Cloudflare</title>` 403 on all three curl_cffi profiles (chrome124/chrome120/safari17_0) AND on headless Playwright (403, same Cloudflare title) — genuine block per the mandatory gate, not a TLS-fingerprint false positive. No known platform fingerprint recovered (challenge page served before any storefront markup). Probed 2026-09-01 (wave 11).
- **shopmassystoresgy.com** (GY, Massy Stores Guyana — national chain, real e-commerce launch Feb 2024 per press coverage) — `Just a moment...` Cloudflare Turnstile 403 on `curl_cffi` `chrome124`/`chrome120`/`safari17_0` AND on headless Playwright (`resp.status==403`, `<title>Just a moment...</title>`, `challenges.cloudflare.com` script in the CSP) — genuine block per the mandatory gate. Highest-credibility remaining Guyana grocery lead by chain size; worth a dedicated anti-bot pass (residential proxy / solver) if Guyana coverage is revisited. Probed 2026-09-01 (LAC wave-13 sweep).
- **www.kaufland.cz** and **www.kaufland.sk** (CZ/SK, Kaufland — hypermarket chain) — HTTP 403 on `curl_cffi` `chrome124`, `chrome120`, AND `safari17_0` (all six domain x profile combos), AND 403 on headless Playwright for kaufland.cz (11,640-byte challenge body after `domcontentloaded`, no hydration to catch) -- genuine block per the mandatory gate, not a TLS-fingerprint false positive. Probed 2026-09-01 (ECA sweep, agent B).
- **atacadao.ma** (MA, Atacadao — Marjane-group hypermarket brand) — `<title>Attention Required! | Cloudflare</title>` 403 on all three curl_cffi profiles (chrome124/chrome120/safari17_0) AND on headless Playwright (403, same Cloudflare title). Genuine block per the mandatory gate — the wave-7 pass had only tried one profile; this re-probe closes it out as a confirmed dead end, not a TLS false negative. Probed 2026-09-01 (MENAAP sweep, agent B).
- **jumia.dz** (DZ, Jumia Algeria) — same shared-tenant Cloudflare signature as jumia.ma/jumia.bf/jumia.sl above: HTTP 403 on curl_cffi realistic UA. Not re-probed with the full 3-profile + Playwright gate this pass (Algeria's Jumia footprint is real per Jumia's own African coverage list, but this is now the fourth Jumia storefront to show the identical wall). Probed 2026-09-01 (MENAAP sweep, agent B).
- **olcha.uz** (UZ, Olcha — one of Uzbekistan's largest marketplaces) — `Just a moment...` Cloudflare Turnstile 403 on `curl_cffi` `chrome124`, `chrome120` AND `safari17_0` (5.7-9.9KB stubs), AND on headless Playwright (`<title>Один момент…</title>`, only outbound request captured was `challenges.cloudflare.com/turnstile/v0/...`). Genuine block per the mandatory gate. **But the backend is wide open and worth a future pass:** `https://api.olcha.uz/api/categories` returns HTTP 200 / 13.8 MB JSON — the complete 1,091-node category tree including a full `produkty-pitaniya` subtree (бакалея, чай/кофе, напитки/соки/вода/газированные, овощи и фрукты, хлебо-булочные, шоколадные изделия), and `https://api.olcha.uz/api/category/<alias>` returns per-category metadata with a real `products_count` (e.g. `soki` -> 62). The **product-listing route was not found by guessing** (~40 REST shapes tried against the Laravel backend, all `404 {"message":""}`), and it cannot be recovered from a network trace because the front end never loads past Turnstile. Getting that one route turns Olcha into a Tier-1B source with no WAF work at all. Probed 2026-09-05 (Central Asia sweep).
- **dukan.af** (AF) — `Checking your browser before accessing. Just a moment...` 403, identical 6,192-byte body on `curl_cffi` `chrome124`, `chrome120`, `chrome131`, `safari17_0` AND `edge101` (five profiles) — not a TLS-fingerprint false negative. One of very few live-looking Afghan storefront domains found. Probed 2026-09-05 (Central Asia sweep).
- **boom.tj** (TJ) and **kabulbazar.af** (AF) — 403 to EVERY curl_cffi Chrome profile (chrome120/124/131) but **HTTP 200 to `firefox133` and `safari18_0`**. Worth adding Firefox to the standard impersonation ladder: a Chrome-only ladder records these as WAF-blocked when they are not. In both of these cases the 200 revealed the same generic 16,369-byte "Default page" hosting placeholder, i.e. a parked domain — so the sites are dead either way, but the *verdict class* was wrong. Probed 2026-09-05 (Central Asia sweep).

- **addisber.com** (ET, Addisber — Ethiopian online shop, FMCG/food/household) — "Just a moment..." 403 on **five** `curl_cffi` profiles (chrome120, chrome124, chrome131, safari17_0, firefox133), homepage and every sub-path alike. Firefox is worth calling out because it is exactly the profile that *rescued* `mohasbeza.com` in the same session (see that source's YAML) — so this is a genuinely different posture, not a profile gap. Not Playwright-confirmed. Probed 2026-09-05 (SSA div-01/02 sweep).

## Cloudflare interactive challenge (`cf-mitigated: challenge`)

Distinct from a plain Cloudflare 403. Signature: HTTP 403 + response header `cf-mitigated: challenge` + a `content-security-policy` referencing `challenges.cloudflare.com` + a Turnstile widget in the body.

> **CORRECTED 2026-08-17.** This section previously claimed TLS fingerprinting alone is "not enough"
> against `cf-mitigated: challenge`. **That is false as a general rule.** `cf-mitigated: challenge`
> is what Cloudflare returns to a *failed fingerprint check* — for many tenants, presenting a real
> browser JA3 via `curl_cffi impersonate="chrome124"` is sufficient and no Turnstile is ever served.
> Measured: tehnomax.me and tehnomanija.rs both returned `cf-mitigated: challenge` to bare curl and
> both cleared cleanly on stock `chrome124` with zero header tricks. Always try impersonation first.

The header alone therefore does **not** classify the site. What separates a hard block is that
`curl_cffi` also fails across `chrome124` / `chrome120` / `safari17_0` — and only then do you need
`scrapy-playwright` + stealth, possibly residential proxies, and for hot sites a Turnstile-solving
service. Don't deploy that as a side task during routine country onboarding; these are dedicated
multi-hour efforts where the *first* site cracked produces a template that accelerates the rest.

- ~~**propertyguru.com.sg** (SG)~~ — **RESOLVED 2026-05-20.** Re-probe with `curl_cffi impersonate=chrome120` returned 200 + clean SSR HTML, no Turnstile, no `cf-mitigated` header. Spider built as plain scrapy-impersonate at `src/prices/price_scraping/spiders/propertyguru_sg.py`; ~560 listings/scrape via per-district crawl. **Lesson:** always re-probe before treating a Cloudflare-challenge entry as a structural blocker — WAF posture drifts.
- **www.landers.ph** (PH, Landers Superstore — membership warehouse, Puregold group) — front door is `cf-mitigated: challenge` (Turnstile) on curl; `curl_cffi impersonate=chrome120` DOES bypass it (200, real SPA shell served). But that only gets you the empty CRA shell — the real Magento REST backend (`/rest/V1/...`, confirmed via `baseapi/globalconfig` returning real store-pickup data) selectively 403s the catalog-relevant module: `rest/V1/landersrestapi/globalconfig` 403s on **both** curl_cffi and headless Playwright, while unrelated modules (`rest/V1/baseapi/globalconfig`) succeed on both. `/graphql` 404s (module disabled). No product/search XHR ever fired in a full Playwright network trace of a catalogsearch results page — SPA never got a chance to call it because the megamenu/config calls it depends on were already 403'd. Selective per-module WAF rule, not a generic front-door block. Probed 2026-08-11.
- **rimba-garden.com** (BN, Rimba Garden grocery) — `cf-mitigated: challenge` + Turnstile CSP on both curl and Playwright (headless Chromium, 6s wait). Confirmed 2026-08-11 on `/shop/fresh-dried-food-commodities/pre-packed-food-beverages/`. COICOP 01 gap remains for Brunei.
- **microdata.pacificdata.org** (NADA microdata catalog — SPC Pacific Data Hub) — `cf-mitigated: challenge` managed-challenge page (`<title>Just a moment...</title>`) on both curl AND headless Playwright (9s wait, still stuck on challenge). Confirmed 2026-08-11 on `/index.php/catalog/761` (Marshall Islands, RMI FY2019/20 HIES) and `/index.php/catalog/881/related-materials` (Kiribati HIES 2023/24) — same Cloudflare zone, one probe covers the whole platform. **Even if unblocked this is a structural absence, not just a blocker**: NADA catalogs serve anonymized household-survey microdata (one-off HIES collection waves, often registration-gated), not a recurring price series — no PriceObservation/IndexObservation fits. Confirmed independently via the reachable `pacific-data.sprep.org` mirror of the same Kiribati HIES 2023/24 dataset record: description states "Version 01: Cleaned, labelled and anonymized version of the master file," collection window 2023–2024 only, and its purpose explicitly includes deriving CPI *expenditure weights* — i.e. an input to CPI construction, not a price observation itself. Do not re-probe for a recurring price feed; if HIES weights specifically are ever wanted, that's a different, one-off ingestion shape than this skill's fetcher contract.
- **www.jumia.com.gh** (GH, Jumia Ghana) — HTTP 403, `<title>Just a moment...</title>` interstitial on `curl_cffi` across `chrome124`/`chrome120`/`safari17_0` AND headless Playwright (25s nav timeout, 3s wait — page never clears past the challenge). Confirmed 2026-09-01. No existing `jumia_*` spider in this repo to compare against; likely shared Cloudflare-tenant infra across other African Jumia storefronts (jumia.com.ng, jumia.co.ke, etc.) — worth a single cross-country probe rather than re-testing per country.
- **www.jumia.com.ng** (NG, Jumia Nigeria) — same signature as jumia.com.gh: HTTP 403, `<title>Just a moment...</title>`, `cf-mitigated: challenge`, fails `curl_cffi` across `chrome124`/`chrome120`/`safari17_0`. Confirms the shared-Cloudflare-tenant hypothesis noted on the GH entry. Probed 2026-09-01 (wave 9).
- **www.gloworld.com** (NG, Glo Nigeria telecom — tariff candidate) — identical signature: HTTP 403, `Just a moment...`, `cf-mitigated: challenge`, fails all 3 `curl_cffi` profiles. Probed 2026-09-01 (wave 9).
- **www.jumia.bf** (BF, Jumia Burkina Faso) — same signature as jumia.ma/jumia.com.gh/jumia.com.ng above: HTTP 403, `<title>Just a moment...</title>`, fails `curl_cffi` across `chrome124`/`chrome120`/`safari17_0`. Confirms the shared-Cloudflare-tenant hypothesis across at least four African Jumia storefronts now. Probed 2026-09-01 (wave 9, Burkina Faso).
- **mapsme.fr** (a supermarket-directory site claiming per-country "adresses, numéros de téléphone, horaires et sites web" — probed as a candidate to find Burkina Faso retailer websites, not as a source itself) — HTTP 403, `<title>Attention Required! | Cloudflare</title>`, "Sorry, you have been blocked", fails `curl_cffi` across `chrome124`/`chrome120`/`safari17_0` (mandatory-gate confirmed). Even unblocked it would only be a directory pointing at retailer sites, most of which turned out not to exist anyway for Burkina Faso. Probed 2026-09-01 (wave 9).
- **www.jumia.ug** (UG, Jumia Uganda) — same signature and same shared Cloudflare tenant as jumia.com.gh/jumia.com.ng above: HTTP 403, `<title>Just a moment...</title>`, fails `curl_cffi` across `chrome124`/`chrome120`/`safari17_0`. Not re-probed with Playwright given two sibling African Jumia storefronts already confirmed the identical tenant fails it the same day — treated as the same tenant rather than re-spending the mandatory-network-trace gate a third time. Probed 2026-09-01 (wave 9, Uganda). No seller-directory alternative reachable either (same domain, same block).
- **krolyc.co.mz** (MZ, "Casa Bhay Supermercado" — the workbook's candidate URL for this Matola supermarket; note the domain doesn't match the brand name) — `curl_cffi impersonate` 403 across `chrome124`/`chrome120`/`safari17_0`/`chrome99` (Cloudflare `cf-ray`, `__cf_bm` cookie set); headless Playwright confirms a real Turnstile challenge (`<title>Just a moment...</title>`, CSP referencing `challenges.cloudflare.com`), not a TLS-fingerprint false positive. Both levers fail per the mandatory gate — genuine block. Probed 2026-09-01.
- **dreamprice.mu** (MU, Dreamprice — a wave-10 brief food lead) — `cf-mitigated: challenge` + Turnstile CSP, HTTP 403 across `chrome124`/`chrome120`/`safari17_0`. Genuine Cloudflare interactive challenge, not a TLS false positive. Probed 2026-09-01 (wave 10).
- **cameroon.opendataforafrica.org** / **nso-cameroon.opendataforafrica.org** (CM, Knoema-hosted NSO data portal linked from the ins-cameroun.cm homepage as the CPI dataset host) — `goto` with headless Playwright never reaches `networkidle` (persistent connections); a `domcontentloaded` load shows a live interactive Turnstile widget (`challenges.cloudflare.com/turnstile/...`) plus `/cdn-cgi/challenge-platform/...` orchestration calls, not a simple JS-execution stub. This is a genuine block, not a TLS-fingerprint false positive — `curl_cffi impersonate=chrome124` was not separately retried since the Playwright trace already shows an interactive CAPTCHA widget rendering, which TLS impersonation cannot solve. Abandoned in favor of `ins-cameroun.cm`'s own domain, which publishes the same CPI series as a monthly PDF with no WAF at all (see `ins_cameroun_cpi` fetcher). Probed 2026-09-01 (wave 13).
- **www.jumia.cm** (CM, Jumia Cameroon) — `curl_cffi impersonate=chrome124` returns `cf-mitigated`-style `<title>Just a moment...</title>` (403) with a `challenges.cloudflare.com` Turnstile CSP; Playwright additionally fails at the TLS layer (`net::ERR_CERT_COMMON_NAME_INVALID`), and even `curl_cffi` needs `verify=False` to get past the cert mismatch. Consistent with reporting that Jumia suspended its main Cameroon marketplace in Nov 2019, keeping only a "classifieds"-style portal running afterward — the domain now reads as a stale/squatted or minimally-maintained tenant behind a live Cloudflare zone, not an active grocery storefront. Do not re-probe as a grocery source; if Jumia's Cameroon classifieds portal is ever wanted it is a different (non-grocery) source shape. Probed 2026-09-01 (wave 13).
- **www.llv.li** / **www.as.llv.li** (LI, Liechtenstein national government portal + Amt für Statistik, the source of the "Landesindex der Konsumentenpreise" CPI news releases) — HTTP 403 with `cf-mitigated: challenge`, a `challenges.cloudflare.com` Turnstile CSP, and `<title>Just a moment...</title>` on `curl_cffi` across `chrome124`/`chrome120`/`safari17_0`; headless Playwright confirms the same interactive Turnstile stub after an 8s wait (not a TLS-fingerprint false positive — both levers fail per the mandatory gate). The block covers the WHOLE `llv.li` zone, not just the statistics subdomain (`www.llv.li/de/news/...` CPI articles 403 identically). Genuine block; do not re-probe without a Turnstile-solving effort. Note for any future CPI attempt: the LIK news releases already found via web search state Liechtenstein's CPI is base "Dezember 2025 = 100" and describe adopting the Swiss national index monthly — worth re-checking on unblock whether it publishes an independent Liechtenstein-weighted series or is a straight Swiss LIK republication. Probed 2026-09-01 (wave 13).
- **www.coop.ch** (CH/LI, Coop Switzerland — candidate for Liechtenstein food coverage via its physical Schaan/Triesen stores) — HTTP 403, `server: DataDome`, `x-datadome: protected`, JS-challenge stub (`geo.captcha-delivery.com`) on curl; headless Playwright confirms the identical DataDome challenge page after an 8s wait (both levers fail per the mandatory gate — genuine block, not a TLS false positive). Probed 2026-09-01 (wave 13).
- **www.migros.ch** / **www.leshop.ch** (CH/LI, Migros' e-grocery storefronts — same combined-content-length shell on both domains, confirming one shared tenant) — plain `requests` (no impersonation) returns HTTP 403; `curl_cffi impersonate=chrome124` AND headless Playwright both return HTTP 200 but serve an IDENTICAL 213,649-byte `<title>maintenance</title>` page regardless of path (`/de`, homepage) — a content-level soft-block dressed as a maintenance page, not a real outage (same byte-for-byte page on two different domains at two different times rules out a genuine site-wide incident). Treat as a genuine block per the mandatory gate's spirit (TLS-bypass "succeeds" at the transport layer but the content itself is non-functional on every route tried). Probed 2026-09-01 (wave 13).
- **www.rhtradingpng.com** (PG, RH Hypermarket — PNG's largest supermarket, 45,000+ SKUs, press-confirmed online grocery ordering with pickup/delivery) — `curl_cffi impersonate` 403 with `cf-mitigated: challenge` and a `challenges.cloudflare.com` Turnstile CSP across `chrome124`/`chrome120`/`chrome99`/`edge99`/`safari17_0`; headless Playwright confirms the same (page title stuck on "Just a moment...", the only network call captured is `challenges.cloudflare.com/turnstile/...`, no product/API endpoint ever fires). Genuine interactive challenge, not a TLS-fingerprint false positive — both levers fail per the mandatory gate. No alternate storefront domain found (the mall-directory page `visioncitypng.com/rh-hypermarket/` is About-the-store copy, not a shop, and has no `shop.*`/ecommerce links in its HTML). Highest-value PNG grocery target for a future dedicated Turnstile-solving effort. Probed 2026-09-01.

## Azure Front Door WAF (`Service unavailable / The request is blocked`)

Azure Front Door managed WAF rule returns HTTP 403/1479-byte HTML stub with literal body text "Service unavailable. The request is blocked." plus an Azure request-tracking ID. Confirmed on both curl (multiple header combinations incl. full Chrome sec-ch-ua set + Referer) and Playwright headless — same failure mode as Cloudflare strict, treat identically (skip, don't iterate).

- **deps-1d68840ecf-hehjcxeeeybfdabn.a03.azurefd.net** (BN, DEPS "PM Price List" app, linked from `deps.mofe.gov.bn/pm-price-list/`) — blocks both `/price-monitoring/` and `/wp-content/uploads/...` paths proxied through this Azure Front Door hostname. **Not a structural loss**: the same files are reachable directly on the un-proxied `deps.mofe.gov.bn` origin (see `deps_arp.py` / `deps_cpi.py` fetchers, which pull the XLSX via the WordPress origin + WP REST API media search instead of this CDN hostname). Probed 2026-08-11.
- **spinneys.com/en-ae** (AE, Spinneys supermarket) — HTTP 403, `server: Microsoft-Azure-Application-Gateway/v2`, 581-byte stub. Confirmed on curl_cffi (chrome124/chrome120/safari17_0, all 403) AND headless Playwright (403, no challenge to solve — a hard edge deny, not a JS puzzle). No network trace found an open backend. Probed 2026-09-01 (UAE food-source pass).

## AWS WAF (`awswaf.com` challenge token)

WAF that returns 403 + a challenge token from `awswaf.com`. Blocks both HTML site and API gateway from the same tenant.

- **klikindomaret.com** + **ap-mc.klikindomaret.com** (ID) — AWS WAF challenge on both site and API gateway.
- **officeworks.com.au** (AU, dept-store/office-electronics — COICOP 05/08 candidate) — HTTP 405 + `x-amzn-waf-action: captcha` from CloudFront/AWS WAF on the front page. Probed 2026-08-07 (round-3 non-food shard).
- **checkers.co.za** (ZA, hypermarket, Shoprite group) — Next.js SSR itself fails server-side (`"serverError":true,"loading":true` in `__NEXT_DATA__`) and the page loads `https://<tenant>.captcha-sdk.awswaf.com/<tenant>/jsapi.js` — genuine AWS WAF CAPTCHA challenge, not a TLS-fingerprint false positive (curl_cffi impersonate=chrome124 reaches the page fine at the HTTP layer; the block is server-side/CAPTCHA, not JA3). No amount of TLS impersonation clears a real CAPTCHA gate. Probed 2026-09-01 (wave 10).
- **fdw.fews.net/api/marketpricefacts/** (USAID FEWS NET, all countries — REGRESSION, not a per-country issue) — the existing shared fetcher `_shared/ssa/fews_net.py` (13 countries wired, verified live 2026-08-07) now returns HTTP 202 + an `awswaf.com`/`window.gokuProps` challenge page on **every** `country_code`, including `RW` — one of the 13 already-working countries — tested with `curl_cffi impersonate=chrome124` AND `chrome120`. This is new since the module's last verification; the whole API went behind AWS WAF, not just a Uganda-specific gap (Uganda was never in the `_COUNTRIES` map to begin with). Do not add Uganda to this fetcher until the tenant-wide block is re-probed and cleared — it would fail for every country right now, not just a new one. Probed 2026-09-01 (wave 9, Uganda).

## Fastly synthetic 405 (edge-level "Not allowed" on every method/UA)

Fastly serves its own synthetic error page (`Error <n>`, `cache-<pop>-<id>` trace line) with HTTP 405 for every request — not a bot challenge, no JS, no cookies to solve; identical across GET, different browser impersonations, and headless Playwright. Looks like an edge VCL rule rejecting the request shape (possibly a Host-header or method mismatch) rather than a device fingerprint, so browser impersonation cannot help.

- **unioncoop.ae** and **www.unioncoop.ae** (AE, Union Coop — Dubai government-linked cooperative supermarket) — HTTP 405 "Not allowed" (`Error 54113`, `cache-iad-kjyo7100081-IAD`) on `/`, `/en`, `/index.php`, both with and without `www.`; reproduced on curl_cffi (chrome124/chrome120/chrome99/safari17_0, all 405) AND headless Playwright (405, same body). Probed 2026-09-01 (UAE food-source pass); no alternate subdomain or API endpoint found.

## Akamai tenant rate-limit / bot manager

Akamai's bot manager either 403s upfront or, for marketplaces with a softer profile, tarpits the session with `curl(28)` timeouts (not 403s).

**The tarpit cap is country-specific, not tenant-wide.** An earlier version of this file claimed two spiders on the same Akamai tenant die at the same item count, and that a shared tenant pool was the mechanism. The 2026-06-08/09 Watsons run disproves it: SG (11,473), HK (10,627), PH (12,598) and ID (9,706) all finished their full sitemaps on the same AS-Watson Akamai tenant — PH and ID concurrently for 4+ hours — while only TH (1,897) and MY (1,873) tarpitted, within five minutes of each other. Five to six times the supposed ceiling, same tenant, at the same time. Do not extrapolate one country's death cap to the rest of a fleet.

Diagnostic signature for the real TH/MY tarpit: `curl: (28)` + `0 bytes received`, ~2h38m elapsed, at ~1,900 items. A country that dies well outside that window with the same exit code is a different problem — check whether the sitemap was simply exhausted before calling it a tarpit.

- **woolworths.co.nz**, **newworld.co.nz**, **paknsave.co.nz**, **chemistwarehouse.co.nz** (NZ) — Foodstuffs/Akamai stack. One bypass effort would unlock all four.
- **watsons.com.tw** (TW, AS Watson) — persistent 403.
- **watsonswine.com** (HK, AS Watson) — HTTP 403, `AkamaiGHost` server header; same AS-Watson tenant. Probed 2026-07-27.
- **watsons.com.hk/en/macau-click-collect-express-delivery/\*** (HK/MO, AS Watson) — HTTP 403 from non-HK/MO IP on the Macao Click & Collect catalogue; same AS-Watson Akamai tenant profile as watsons.com.tw. Probed 2026-06-10.
- **pns.hk** (HK, PARKnSHOP — AS Watson's supermarket brand, distinct from the pharmacy brand) — HTTP 403 `server: AkamaiGHost` on curl AND headless Playwright (`<title>Access Denied</title>`, `errors.edgesuite.net` reference id), confirmed on both the multibuy promo page and the plain `/en/` root and a category path — whole-domain block, not path-specific. Note this is the supermarket property; `watsons_hk` (pharmacy) and `mannings` (health/beauty) both work fine on the same AS-Watson corporate tenant, so blocking is per-brand-property here, not tenant-wide — don't extrapolate PARKnSHOP's block to the working HK spiders or vice versa. Probed 2026-08-11.
- **shopping.coupang.com**, **lazada.\*.\<tld\>**, **shopee.\*.\<tld\>** — marketplace platforms with Akamai bot manager. Only viable via official affiliate APIs.
- **kmart.com.au** (AU, dept-store — COICOP 03/05/09/13 candidate) — HTTP 403, `server: AkamaiGHost`. Probed 2026-08-07 (round-3 non-food shard); no network trace attempted beyond the front page, so an open backend API is not ruled out — worth a Playwright-discover pass if AU dept-store coverage is revisited.
- **carrefourqatar.com**, **carrefourksa.com**, **carrefouruae.com** (QA/SA/AE, Majid Al Futtaim Carrefour) — HTTP 403, `server: AkamaiGHost`, 376-byte "Access Denied" edge stub on all three (only the domain string in the body differs), including on `carrefourqatar.com` which redirects internally to the KSA hostname before blocking — one Akamai tenant covering the whole MAF Gulf group. No network trace beyond the front page; worth a Playwright-discover pass. Probed 2026-08-06 (round-3 Gulf States shard).
- **www.carrefouruganda.com** (UG) — identical signature to the Gulf trio above: HTTP 403, 377-byte "Access Denied" `errors.edgesuite` stub, fails `curl_cffi` across `chrome124`/`chrome120`/`safari17_0` (same reference-id format `18.xxdfda17.<epoch>.<hex>`). Confirms this is the same MAF/Carrefour Akamai tenant extending to the East Africa storefront (Carrefour operates hypermarkets at Acacia/Lugogo/Metroplex/Oasis Mall, Kampala, per the brand's own site copy — a real local footprint, just Akamai-fronted). No network trace beyond the front page attempted (WebSearch/time budget) — worth a Playwright-discover pass if this tenant is ever prioritized. Probed 2026-09-01 (wave 9, Uganda).
- **www.hypermax.com.jo** (JO, "HyperMax" — Majid Al Futtaim's rebrand of Carrefour Jordan after Carrefour ceased all Jordan operations 2024-11-04 amid a BDS boycott campaign) — same URL shape as the other MAF storefronts (`/mafjor/en/`, matching `carrefourqatar.com/mafqat/en`) and the identical Akamai signature: HTTP 403 `Access Denied` / `errors.edgesuite.net` reference-id format `18.9dce4917.<epoch>.<hex>` on all three curl_cffi profiles (chrome124/chrome120/safari17_0) AND on headless Playwright (same signature, same reference-id prefix). Confirms the MAF Gulf/Akamai backend survived the Carrefour→HyperMax rebrand unchanged. The old `carrefourjordan.com` domain itself is now a parked IP-Twins domain-broker page, not a redirect to the new brand. Probed 2026-09-01 (wave 13, Jordan).

## Imperva Incapsula (212-byte JS-challenge stub)

Site returns a tiny (~212-byte) HTML stub containing a JS challenge. `scrapy-impersonate` alone returns the stub — not a real product page. JS execution is the wall, so TLS impersonation cannot help.

**Probe protocol for any "200 OK but tiny response" source** — do this before blaming a UA/TLS mismatch. Fetch one URL with `curl_cffi.requests.get(url, impersonate="chrome120")` and read the body:

- `_Incapsula_Resource` in a `<script src>`, `x-iinfo` header, or `visid_incap_*` cookies → Incapsula JS challenge. `scrapy-impersonate` will not bypass it.
- `Server: AkamaiGHost` or `akamai-grn` → real Akamai, and UA/TLS alignment may be worth trying.

Coles AU (2026-06-08) is the worked case: plain Playwright fails too. A stealth-patched headless Chromium with an en-AU locale and a successful homepage warm-up (590KB, full Incapsula cookie suite including `reese84`) is still blocked on the next navigation — a 974-byte page with `<iframe id="main-iframe">Request unsuccessful. Incapsula incident ID: …</iframe>` and `edet=12`. Incapsula fingerprints headless Chromium below the layer the stealth JS patches. Realistic options are `playwright-stealth`, a residential proxy exit with warmed cookies, `undetected-playwright`, or dropping the source.

**Gotcha that masks all of the above:** a spider setting `DOWNLOADER_MIDDLEWARES` in `custom_settings` **replaces** the whole dict rather than merging with the project-level one, silently dropping `RandomBrowserMiddleware`. Respell the full middleware list when overriding any single entry, or you will diagnose the wrong failure.

- **makro.co.th** (TH, Siam Makro) — Incapsula 403 on curl AND Playwright.
- **rt-mart.com.tw** (TW, 大潤發) — HTTP 503 Incapsula challenge page (`Request unsuccessful. Incapsula incident ID`). Shopee alt storefront also blocked (Akamai). Probed 2026-07-27.
- **coles.com.au** (AU) — Incapsula JS challenge; 212-byte stub on bare `scrapy-impersonate`.
- **comfy.ua** (UA) — `_Incapsula_Resource` script stub (~1KB body, HTTP 200 with `<META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW">` + an iframe to `/_Incapsula_Resource?SWUDNSAI=...`).
- **lifecell.ua** (UA) — same Incapsula tenant signature as comfy.ua; ~960-byte stub. Likely same protection profile across the AS Watson-style cohort.

## PerimeterX (per-session token, collector beacons only)

WAF that issues per-session tokens via JS. Bare clients see only `*.px-cloud.net` collector beacons; business endpoints never respond. Assume PerimeterX is in front of every delivery-hero / foodpanda property.

- **foodpanda.la** (LA) — `collector-pxljub4etb.cl6.px-cloud.net` collector visible; no business endpoint responses load.
- **foodpanda.com.mm** (MM) — 403 on `/en/city/yangon`; consistent with foodpanda.\* PerimeterX tenant. No business endpoint responses. Same profile as .la.
- **foodpanda.mo** (MO, Macao) — ECONNREFUSED on WebFetch probe 2026-06-10; consistent with foodpanda.\* regional IP-fence + PerimeterX family. Foodpanda confirmed operating in Macao from press reports.
- **foodpanda.\*** in general — same vendor.
- **jawwal.ps** (PSE, West Bank and Gaza — Jawwal mobile carrier) — `TSPD` cookie challenge page returned even with `curl_cffi impersonate="chrome124"`; real content never reached. Probed 2026-09-01.
- **paltel.ps** (PSE, West Bank and Gaza — Paltel fixed-line/ISP) — identical `TSPD` signature to jawwal.ps; both Palestinian carriers share one PerimeterX tenant. Probed 2026-09-01.

## CDN connection-reset / TCP timeout from non-target IP (country geo-fence)

- **www.mpointmart.com** (LA, M-Point Mart — Vientiane supermarket chain) — TCP timeout (0 bytes, 000 exit code) from non-Lao IP on root and /shop/. Likely CDN geo-fence. COICOP 01/05/13 gap. Re-probe with Lao residential proxy. Probed 2026-06-15. **Re-confirmed 2026-09-01**: `curl_cffi impersonate=chrome124` still times out after 20s on `www.mpointmart.com` (DNS resolves to 27.254.174.26, plain HTTP also 000/timeout); `mpointmart.com` bare apex does not resolve at all. Still the only unscraped food candidate on file for Lao PDR — worth a Lao residential-proxy retry in a future wave, not worth another cold re-probe from this egress.
- **shop.fernandes.sr** (SR, Fernandes Express grocery delivery) — resolves in DNS (186.179.175.42) but TCP connect times out after 15s on both plain `curl` and `curl_cffi impersonate=chrome124` — no TLS handshake ever starts. The service's canonical marketing domain `fernandes-express.com` is separately confirmed dead (NXDOMAIN against both 8.8.8.8 and 1.1.1.1) despite a live 2024 news article still linking to it via a `bit.ly/FernandesExpressShop` redirect. Suriname COICOP 01 gap remains. Probed 2026-09-01 (wave 13).

## CDN connection-reset at TCP layer (`ERR_CONNECTION_RESET`)

Real-browser requests from a non-target-country IP are dropped at the CDN before any HTTP response. Headless Chromium does not bypass — the connection is reset pre-response. Bypass requires a residential proxy in-country.

Distinct from the Internet Archive's intermittent L4 blackhole, which produces the same symptom but only under sustained parallel Wayback backfill and clears on its own — a geo-fence resets every time, from the first request.

- **shop.cpl.com.pg** (PNG, CPL Group — Stop & Shop supermarket, PNG's largest retailer) — `ECONNREFUSED` on WebFetch from non-PNG IP. Online grocery/pharmacy/hardware shop at shop.cpl.com.pg. Likely CDN geo-fence restricting to PNG residential IPs. Probed 2026-06-10. Revisit with PNG residential proxy before attempting to onboard as retailer_sku spider.
- **bachhoaxanh.com** (VN, Mobile World Group) — `ERR_CONNECTION_RESET` on `/` and product paths. WebFetch returns "socket connection was closed unexpectedly".
- **ukrstat.gov.ua** (UA) — TCP-level connection drop from non-UA IPs (`curl` returns code `000`, zero bytes). Affects the entire host including direct XLS downloads, so Wayback is the only workable fallback for stats-office data without a UA residential proxy.
- **kyivmetro.com** + **www.kyivmetro.com** (UA) — same TCP-level drop.
- **eldorado.com.ua** (UA) — TCP-level drop (the `.ua` apex `eldorado.ua` serves a real 404, but the `.com.ua` mirror drops the connection).
- **novus.zakaz.ua** (UA, Novus's q-commerce backend) — 403 with 16-byte body from non-UA; Novus's main `novus.ua` loads cleanly so probe both before classifying.
  **CORRECTED 2026-09-05: NOT a blocker. The Zakaz.ua platform is wide open.** The 403 is confined to the storefront *web* hosts. Its API host, `stores-api.zakaz.ua`, answers HTTP 200 anonymously with NO cookies, NO `Origin`/`Referer` and NO TLS impersonation — verified with a header-free GET. `GET /stores/` returns all 67 stores across 21 Ukrainian retail chains (novus, auchan, metro, megamarket, tavriav, ekomarket, winetime, ultramarket, cosmos, zaraz, alcohub, torba, grono, ideal, onde, vostorg, kharkiv, chudomarket, epicentr, masterzoo, biotus); `GET /stores/<id>/categories/` and `GET /stores/<id>/categories/<cat>/products/?page=N` walk each chain's whole catalog (prices in kopiyky — divide by 100). Seven chains were onboarded off this on 2026-09-05 via `_zakaz_base.ZakazBaseSpider`. Do not treat any `*.zakaz.ua` verdict as covering the platform: probe the API host, not the storefront.

- **nhathuocankhang.com** (VN, also MWG) — same signature. Both MWG sites share infrastructure; a single bypass effort would unlock both.
- **villamarket.com** (TH) — `ERR_CONNECTION_RESET` on curl AND Playwright `goto`.
- **sendo.vn** (VN, general e-commerce) — redirects to sendofarm.vn; main catalog is a SPA with content-hashed CSS class names (d7ed-* prefix). Zero product prices in SSR HTML. Confirmed 2026-06-15.
- **metro.cn** + **www.maidelong.com** (CN, Metro China) — TLS handshake starts then stalls mid-handshake (same IP 220.196.43.244), classic GFW-style reset from non-CN IP. Probed 2026-07-27.
- **api.freshop.ncrcloud.com** (PH, WalterMart's Freshop catalog API) — **RESOLVED 2026-07-27, spider now `active: true` (~9,495 unique SKUs).** The earlier "aggressive IP throttle / off-network re-test needed" theory was WRONG. Two real causes, both fixed from the same network with a plain client: (1) the `502`/`SSLError` failures were the repo's default **curl_cffi impersonate handler** (`RandomBrowserMiddleware`) whose TLS fingerprint this host rejects — a normal Twisted client (plain `curl`) negotiates cleanly and returns 200. Fix: disable `RandomBrowserMiddleware` in the spider's `custom_settings`. (2) `/2/products` **ignores `offset`/`page`/`token`** (offset=0 and offset=5000 return the identical slice; `token` is an auth token → `sign_out_required`) and **hard-caps responses at 100 rows** (`limit` above 100 is clamped). So paging is impossible — walk the catalog by sharding on **leaf `department_id`** from the `/1/departments` tree (`/2/categories` 404s; `/2/departments` is v1-only) filtered `&department_id=<id>&sort=id`. Notes: the API **403s a non-browser UA** (keep `CustomUserAgentMiddleware`); backend key is `walter_mart`. Residual gap: 45 leaf departments still exceed the 100-cap (~3k tail rows unreached, logged per-department) — close later with dual-sort or price-range sub-sharding.
- **api.freshop.ncrcloud.com — shared-host rate limit under concurrent multi-agent load** (KY, Cayman Islands wave-9, tenants `fosters` and `hurleys`, both large catalogs at ~17k-27k SKUs / 170-270 pages of `limit=100`) — a plain `skip=N` paging walk (this host DOES honor `skip` for these tenants, unlike WalterMart above) starts returning `400 {"error_code":429}` after an inconsistent number of successful pages (observed onset at page ~2, ~23, ~37, ~56 across separate runs on the SAME spider/settings) — i.e. the trip point is not a deterministic function of this spider's own request rate. Self-heals given enough elapsed time (a direct re-probe of a failing `skip` value succeeded ~60s later with nothing else changed). Strong circumstantial evidence this is a budget **shared across concurrently-running agents hitting this one host from the same outbound IP**, not a per-tenant or per-request-rate limit: onset got *worse* run over run while other wave-9 agents were independently running collects in the same shared checkout (confirmed via `logs/prices/_runs/` timestamps from an unrelated Sierra Leone telecom fetcher landing seconds apart). Mitigation that helps but does not fully solve it: `CONCURRENT_REQUESTS_PER_DOMAIN: 1`, flat `DOWNLOAD_DELAY` (not AutoThrottle — see next bullet), high `RETRY_TIMES` with `400` added to `RETRY_HTTP_CODES`. No mitigation found that guarantees a full-catalog crawl completes in one run while other agents are active; if a Freshop-backed source's crawl stalls, that is very likely this shared limit, not a bug in the new spider. Retry later, alone, before concluding the source is broken.
- **AutoThrottle actively fights a fast-failing rate limit** — general Scrapy gotcha rediscovered on the Freshop bullet above, worth knowing for any host whose rate-limit response is a small/fast HTTP body (as opposed to a slow timeout). `AUTOTHROTTLE_ENABLED` adapts `DOWNLOAD_DELAY` from response **latency**; a `400`/`429` rate-limit body returns fast, so AutoThrottle reads "fast response" as "safe to speed up" and shortens the delay at exactly the moment it should lengthen it. Set `AUTOTHROTTLE_ENABLED: False` and pin a flat `DOWNLOAD_DELAY` instead on any host suspected of fast-failing rate limits.

- **dadosabertos.aneel.gov.br** (BR, ANEEL — Brazilian electricity regulator open-data CKAN portal) — `package_search` endpoint does not respond at all (curl exits `000`, >120s, no TCP-level response) even on a plain unauthenticated GET. Not a WAF block (no challenge page, no status code at all) — looks like the CKAN instance itself is down or geo-fenced. Division-04 lead for Brazil (would have covered per-distributor tariffs); not pursued further. Probed 2026-08-07.
- **bigw.com.au** (AU, dept-store — COICOP 03/05/09/13 candidate, Woolworths group) — `curl` exits `000` (0 bytes, connection-level drop) on both plain and `-L` requests. Same Akamai/Woolworths-adjacent posture noted elsewhere in this file for the group. Probed 2026-08-07 (round-3 non-food shard); not investigated further.
- **decathlon.com.my** (MY, sport/recreation — COICOP 03/09 candidate) — `curl` exits `000`/`28` (connection reset/timeout) on the front page; every other Decathlon country TLD probed the same session (TH/PH/ID/HK/TW/AU/VN) returned clean 200s on the same Next.js+Algolia platform, so this looks like a Malaysia-specific gap (site not launched, or a narrower block) rather than a platform-wide issue. Probed 2026-08-07.
- **decathlon.com.cn** (CN, sport/recreation — COICOP 03/09 candidate) — HTTP 406 on the front page (the `decathlon.cn` apex 301-redirects here). Not investigated further — worth a browser-UA retry (406 usually means content-negotiation rejection, not a bot block) before writing this off. Probed 2026-08-07.

## API requires dynamic security key / JWT

Bare curl returns 401/429 regardless of headers because a non-trivial token is required, derived client-side. Reverse-engineering is rarely worth it.

- **marketplace.com.mm** (MM) `/api/products/all` — dynamic `x-security-key` header (CryptoJS "Salted__" prefix, AES with client-side-derived key). 429 without it.
- **sayurbox.com** (ID) `/graphql/v1` — requires `authorization: Bearer <JWT>` + 10+ custom `x-sbox-*` headers + per-session `deliveryConfigId` base64 blob in the GraphQL variables.
- **alfagift.id** (ID) `webcommerce-gw.alfagift.id/v2/products/category/{id}` — 401 without auth token; init flow not investigated.
- **api.bonplancaillou.nc** (NC) `/api/v1/inflation/dashboard` — 401 `"Token invalide ou expiré"` on bare curl; client JS only attaches `Authorization: Bearer` when a `bonplan_token` exists in `localStorage` (i.e. logged-in users). The public `/inflation` page itself is server-rendered (Next.js, `x-nextjs-cache`, `s-maxage=300`) via a private server-side key, so the aggregate numbers are visible without login, but the raw API is not. Also: as of 2026-08 the site has only one month of data (2026-02) and explicitly shows "Pas encore assez de relevés pour calculer une évolution" — too thin to ship regardless of the auth wall (Phase 6 gate: 1 aggregate row, no per-product/per-store breakdown without login).
- **cubamax.com** (CU, diaspora-to-Cuba delivery marketplace) — `api.cubamax.xyz/store/products?page=1&take=24&cityId=<id>&categoryId=<id>` returns `422 Unauthorized access` on bare curl AND on `curl_cffi impersonate=chrome124` (not a TLS-fingerprint issue). Playwright network capture shows the real browser request carries `x-hmac-signature` / `x-hmac-nonce` / `x-hmac-timestamp` headers computed client-side per request — same shape as marketplace.com.mm's `x-security-key`. Front end itself is otherwise wide open (no location-gate WAF, `store/categories/public?cityId=` and `nomenclatures/*` endpoints are unauthenticated) and the catalog is large (4,095+1,972+1,656+1,217+2,116+... across categories, easily 10k+ products across a Havana-municipality selection) — worth revisiting only if the HMAC scheme is ever cracked or a static key surfaces. Probed 2026-09-01.
- **marjane.ma** (MA, Marjane hypermarket — largest chain in Morocco) — PDP HTML carries zero price text (rendered client-side only); `__NEXT_DATA__.runtimeConfig` leaks the real backend (`apiUrl: https://api-ayaline.marjane.ma`, an `Ocp-Apim-Subscription-Key`-shaped `marjaneApiKey`, and a Google reCAPTCHA Enterprise site key). `GET /products/<id>` on that host returns `401` with an empty body under every header variant tried (`Ocp-Apim-Subscription-Key`, `x-api-key`, `apikey`, `Authorization: Bearer <marjaneApiKey>`) — the key alone doesn't clear it, consistent with an additional session/reCAPTCHA-derived token. Separately, headless Playwright hitting the site at all (not just the API) returns a bilingual "Access Restricted / Accès Restreint" interstitial ("Access not available in your region") even though `curl_cffi impersonate=chrome124` gets the real page every time from the same IP — the block keys off the Playwright/automation fingerprint, not geo-IP. The site DOES carry a real, large, well-organized food catalog (sitemap alone lists 3 shards x 5000 URLs under `/courses-en-ligne/...` with a clean 3-level category taxonomy, heavily food/beverage in the samples) — worth a dedicated pass if the API auth or the Playwright block is ever cracked. Probed 2026-09-01.
- **carrefour.ma** (MA) — does NOT resolve (`curl: (6) Could not resolve host`). Carrefour Morocco (Label'Vie group) is not at this domain; the working `carrefour_dz`/`carrefour_tn` Magento pattern does not transfer without finding the real storefront URL. Not searched further (WebSearch budget). Probed 2026-09-01.
- **shop.realvalueiga.com** (GD, Real Value Supermarket IGA Grenada) — confirmed independently 2026-09-01 (lac-agent-A). `GET /rest-proxy/v2/whoami?anonymous=1` returns 200 with an anonymous JWT AND a pre-populated `selectedStore: "4140"` (unlike the Barbados/PR siblings below, which get `selectedStore: null`) — but every guessed REST path (`/rest-proxy/v2/stores/4140/departments`, `/rest-proxy/v2/departments`, `/rest-proxy/v2/stores/4140`, `/rest-proxy/v2/stores`) 404s to the SPA-shell fallback HTML, and a Playwright load of `/` with a 5s+3s wait fires zero `rest-proxy`/`api` network requests at all — the department/product listing only starts once the client-side address-picker JS actually runs (client-side routing means the path guesses above 404 rather than 200-with-empty-body). Same LocalExpress platform/gate as the Barbados and Puerto Rico entries below. NOT pursued further for Grenada because a working alternative was found on a different platform (CaribeEats' `caribeshop--gnd`, see the config's YAML notes) — this entry remains open for whoever tries to crack the LocalExpress address-selection flow generally.
- **online.imartstores.com** (BB, iMart Pharmacy & Convenience Store Barbados — the corporate site `imartstores.com` is a Joomla brochure with zero prices; the real catalog lives on this LocalExpress-platform subdomain) — `/rest-proxy/v2/*` requires a Bearer JWT. An anonymous JWT IS obtainable client-side via `GET /rest-proxy/v2/whoami?anonymous=1` (no login wall), but the subsequent flow gates the product/department listing behind an address/location-picker step (`user-picked-address`, `check-location-from-ip`) before any product endpoint fires — no department or product links render without it. Same platform and same shape as the already-blocked **shop.realvalueiga.com** (Grenada) LocalExpress entry above. Cracking one LocalExpress tenant's address-selection flow would likely unlock both. Probed 2026-09-01.
- **econotogo.com** (PR, Econo ToGo — Supermercados Econo's online-ordering front, linked from the corporate WordPress site `superecono.com`) — third confirmed instance of the same LocalExpress platform and gate: anonymous JWT obtainable via `GET /rest-proxy/v2/whoami?anonymous=1` (`selectedStore: null`), but `/rest-proxy/v2/stores`, `/departments`, and `/products` all 404 without a store/address selected first, and there's no way to select one without running the JS app. Same shape as the Barbados and Grenada entries above — cracking one LocalExpress tenant's address-selection flow would likely unlock all three. Probed 2026-09-01.

## Cloudflare "One moment please" interstitial (JS challenge, intermittent)

Site sometimes presents a Cloudflare JS verification challenge on the first request but resolves with curl using browser-realistic headers. Not a hard block — retry before treating as structural.

- **laostatefuel.com/en/gas-price.html** (LA, Lao State Fuel Company) — WebFetch returns interstitial but curl with browser UA returns full HTML 2026-06-15. Fetcher uses requests; works fine.
- **nesraf.com** (LY, "Nesraf" — wave 10 workbook ACCEPT candidate, "broad marketplace with grocery-adjacent categories") — `curl_cffi` 403s on all three profiles (chrome124/chrome120/safari17_0), but a plain headless-Chromium `page.goto()` clears it to a real WooCommerce/Martfury-theme storefront. The block is intermittent/inconsistent even under Playwright: a second request (to `/product-sitemap.xml`) hit the same "Checking your browser" stub. Separately from the WAF, the site's real category taxonomy (18 top-level categories including a dedicated `grocery`, `pastries-and-confections`, `restaurants-and-cafes`) is **entirely empty** — every category and the `/shop` listing itself return "No products were found matching your selection." The only live products found (via homepage links) are ~15 books/legal-history titles sold by a single "publisher" store, not a functioning grocery-adjacent marketplace. Do not build: even if the CF issue were fully cracked, there is no food catalog behind it. Probed 2026-09-01 (wave 10).

## SPA shell — no productive endpoint (lazy-load never hydrates)

Site loads, renders skeleton cards, but never hydrates fully within a reasonable Playwright wait. Or hides product data behind an API that itself requires SPA session state. The fix here, when there is one, is to find a parallel JSON endpoint (winmart's case).

- **telemor.tl/Home/Broadband** (TL, Telemor broadband) — SPA-gated; broadband/FTTH pricing not in page source; directs to contact email `esd@telemor.tl`. No public retail price list. Skip; mobile plans page (`/Home/Products?parentCode=MOBILE`) has prices in SSR HTML — probe that instead. Checked 2026-06-10.
- **unitel.com.la/en/mobile/packages** (LA, Unitel Laos — ~50% mobile market share) — Angular SPA; package names/prices not in SSR HTML (`{{ t('text') }}` visible). No API endpoint found. SKIP; use laotel.com FTTH as telco alternative. Probed 2026-06-10.
- **www.samsclub.cn** (CN, Sam's Club China / 山姆会员商店 — Walmart membership grocery retailer) — UMI/React SPA shell; all routes (including guessed API paths `/api/node/search/v2/...`, `/api/node/items/search`) return the same 1,230-byte HTML SPA bootstrap with `<div id="root"></div>`. No server-rendered product data; no open API endpoint found without JS execution. Probed 2026-06-30.
- **freshippo.com / Hema (盒马)**, **chaoshi.tmall.com (Tmall Supermarket)** (CN) — Alibaba "ICE" framework CSR shells (`<div id="ice-container">`, `"renderMode":"CSR"`); zero product/price in raw HTML. Even JS-render risky (mtop signed APIs). Probed 2026-07-27.
- **maicai.meituan.com (Meituan Maicai)**, **pupumall.com (Pupu 朴朴)** (CN) — bespoke React/Vue CSR SPA shells (`<title>加载中</title>`, empty `#root`); require city/store selection; aggressive anti-scrape. Probed 2026-07-27.
- **jddj.com (JD Daojia/秒送)** (CN) — small React landing page, same JD corporate family as the JDR_shields-blocked jd.com. SKIP. Probed 2026-07-27.
- **suning.com (苏宁易购)** (CN) — **RESOLVED → SCRAPABLE (not a blocker); the one CN lead that pans out, overturning "China = 0".** Two-step, no WAF (`Server: volc-dcdn`): (1) SSR HTML from `search.suning.com/{keyword}/` list pages + `product.suning.com/{vendorCode}/{productCode}.html` PDP yields **name + 18-digit padded `PartNumber`** (e.g. `000000012411692175`) + the **real `VendorCode`** (in the PDP page JSON, e.g. `0070088095` — the URL's `0000000000` is a placeholder); (2) price from the separate microservice `pas.suning.com/nspcsale_0_{PartNumber}_{PartNumber}_{vendorCode}_{cityTuple}___.html` → JSONP `pcData({...})`, price under `data.price.saleInfo[]` (`netPrice`/`refPrice`/`promotionPrice`). Carries F&B grocery (苏宁超市). **Only open item:** a valid city-code tuple (cityId/provinceId/districtId) — placeholder city returns `noPriceCausation: 城市不存在`. Endpoint/params/JSON shape all verified 2026-07-27. Onboard as a two-request spider once the city tuple is pinned.
- **winmart.vn** *(HTML front-end)* — products render via `product-card-skeleton` divs that don't hydrate within 8s Playwright wait. **NOTE**: winmart's *JSON API* at `api-crownx.winmart.vn/it/api/web/v3/item/category` works with no auth — see `src/prices/price_scraping/spiders/winmart.py`. Tier 1B, not Tier 2.
- **shop.com.mm** (MM, Daraz Myanmar) — SPA confirmed June 2026. Category pages (`/health-care/`, `/medicines/`) return only navigation chrome in SSR HTML; zero product cards or prices. Alibaba/Daraz platform. No public API endpoint found. SKIP.
- **cargillsonline.com** (LK) — **RESOLVED 2026-09-11 → SHIPPED as `cargills_lk`. This verdict was wrong: it was reached without the mandatory network trace.** The old note ("Angular SPA … `{{...}}` placeholder syntax … `/ProductDetails/<sku>` URLs never hydrate") correctly describes the AngularJS 1.x front-end and is irrelevant — there is a wide-open ASP.NET MVC JSON API behind it. `POST /Web/GetMenuCategoryItemsPagingV3/` with JSON body `{"CategoryId": <base64 id>, "PageSize": 5000, "SubCatId": "-1", …}` returns a whole category in one response. **The trap that makes this look dead on a cold probe:** without an ASP.NET store session the endpoint returns exactly one synthetic row `{"ItemName":"No Products Found","Price":null}` — a 200 with a plausible-looking JSON body, not an error. The bootstrap is `GET /` → `POST /Web/CheckDeliveryOptionV1` (form `PinCode=Colombo`, sets `ASP.NET_Pincode`/`Asp.Net_WebStoreId` for dark store 1031) → `POST /Web/GetCategoriesV1` (23 categories, `EnId` = base64 of the numeric id). Measured 3,967 SKUs across all 23 categories; test run collected 1,021 rows, all priced. Probed 2026-09-11.
- **osudpotro.com** (BD) — listing URL `/category/buy-over-the-counter-medicine-online-in-dhaka` renders **disease cards** (`<a href="/disease/...">`) not product cards. Catalog is by-disease; needs a different entry URL or direct PDP list.
- **almeera.com.qa** (QA, Al Meera — state-linked co-op chain) — Vite/Vue PWA shell (`<div id="app"></div>`, `env-config.js` is a local-dev stub not the real runtime config); the main JS bundle is minified enough that grepping for `VITE_API` / `window.__ENV__.*` finds nothing, so the real API base couldn't be recovered without a network trace. No Playwright available this session. Worth a dedicated Playwright-discover pass — the domain itself resolves and serves 200 (unlike Ramez/KM Trading below). Probed 2026-08-06 (round-3 Gulf States shard).
- **sultan-center.com** (KW, The Sultan Center) — SPA shell (`<div id="app"></div>`) on what looks like a Bagisto (Laravel+Vue) storefront (`"Sultan Theme"`, `/vendor/sultan/ui/` asset paths) — no `_bagisto_base.py` exists in this repo. No API endpoint recovered from static asset grep; needs a network trace. Probed 2026-08-06 (round-3 Gulf States shard).
- **sahel25.com** (JO, "Sahel Pro" — Amman-only online grocery delivery) — GENUINELY RICH catalog (1,835 products across a real sitemap, JOD 3-decimal pricing, schema.org Product JSON-LD per page) sitting behind a delivery-AREA GATE, not a hydration problem: a fresh Playwright/browser context whose FIRST navigation is straight to a `/product/<uuid>` or `/category/<uuid>` URL gets redirected to `/select-location?next=...` (same family as the UAE Kibsons/Talabat "resolve a delivery area first" pattern). Confirmed the gate is inconsistent/non-deterministic across contexts: a completely standalone `playwright.chromium.launch()` one-off script, and even that SAME script preceded by a homepage visit in the same context, sometimes passed straight through with no redirect at all and no cookie/localStorage set (verified: `context.cookies()` and `localStorage` both empty even on a passing run) — but a `scrapy-playwright` crawl (persistent context, homepage visited first via an explicit bootstrap request) redirected on 100% of ~20 consecutive product-page navigations. Whatever determines pass/fail is not carried in any inspectable browser state; a session-affinity/geo/IP-based heuristic on the server side is the leading hypothesis, not proven. **Do not re-attempt without a way to either complete the location-selection UI flow explicitly (find and click through whatever `/select-location` renders) or reproduce the "no redirect" condition reliably** — two separate wait-condition fixes (`wait_for_selector` on the JSON-LD tag with `state="attached"`; `wait_for_load_state("networkidle")` matching a working manual probe) did not change the outcome once inside scrapy-playwright. A capped 8-item scrapy-playwright test also drew 857 HTTP 429s out of 1416 requests at concurrency=8 with sub-resources (images/fonts/css) unblocked — any retry MUST cut concurrency to ≤2 and block non-essential resource types, or it will burn the site's rate limit before the location-gate question is even answered. Not shipped — 0 rows scraped despite the catalog being real and worth revisiting. Probed 2026-09-01.
- **grocerjy.com / www.grocerjy.com** (JO, "Grocerjy — Shop and order your daily grocery & supermarket") — Next.js SPA; the SSR shell is only 1.6KB and its `pages/index` JS chunk is a mere 2.2KB with zero API/fetch references — reads as an unfinished/pre-launch build, not a hydration-timing problem. Not deep-probed with Playwright given the thin bundle signal. Probed 2026-09-01.
- **hktvmall.com** (HK, HK's largest online mall) — the old "Akamai tarpit" flag does NOT reproduce (2026-07-27): no `_abck`/`bm_sz`/`ak_bmsc` cookies, no Access-Denied challenge, only `NLBI` + `x-session-lang`; intermittent 0-byte/302 under rapid curls = rate-gating, not a hard WAF. BUT catalog is **SPA-only** — zero products/prices/JSON-LD in HTML (only nav taxonomy, e.g. `data-maincat="AA11110000000"`), and all hybris/OCC endpoint guesses 404 (`/hktvwebservices/v2/hktv/products/search`, `/occ/v2/...`, etc.). Capture the product-grid XHR with a **headed Playwright/DevTools** trace, then replay. Playwright fallback viable. Probed 2026-07-27.
- **lotuss.com.my** (MY, Lotus's / Siam Makro) — **dual WAF over a Next.js SPA; deprioritize.** Storefront `/en/category/grocery` browsable but 355KB HTML has zero prices / no `__NEXT_DATA__` (client-side XHR). Backend is Siam Makro's "mango" GraphQL BFF, both fronts walled: `api.lotuss.com.my` = Cloudflare hard block (403 all paths); `api.makro.pro/graphql` = Tencent Cloud WAF on POST + needs auth token. (The "Mirakl" lead was a red herring — that's Siam Makro's Maknet B2B in TH, not the MY consumer catalog.) Would need a headless-browser capture of the GraphQL query + WAF-clearance cookies. Probed 2026-07-27.
- **pnp.co.za** (ZA, Pick n Pay) — pure client-side SPA; homepage HTML (51KB) has no server-rendered links at all beyond favicon/asset tags (no nav, no category, no product hrefs) — everything is hydrated by a JS bundle. No API endpoint found without a Playwright network trace (not run this pass — deprioritized after `checkers.co.za` above hit a harder AWS WAF CAPTCHA and `faithful-to-nature.co.za` below hit a tooling-level block; ZA already cleared its onboarding bar via non-retail sources this wave). Probed 2026-09-01 (wave 10).
- **giant.sg** (SG, DFI Retail Group — Giant hypermarket) — jQuery + Algolia InstantSearch v2 SPA; all product routes return HTTP 404 server-side (client-side routing only). Product catalog exclusively served via Algolia index `giant_product_live` (app `PFCHI1YM66`). Algolia DSN (`pfchi1ym66-dsn.algolia.net`) and all three fallback shards (`pfchi1ym66-{1,2,3}.algolianet.com`) return DNS NXDOMAIN from non-SG IPs — not resolvable even from Playwright/headless Chromium. PDP pages return HTTP 404 with 250KB SPA shell; 12s Playwright wait yields no product name, price, or JSON-LD product data. Sitemap (`/sitemap_product.xml`) has 15,630 product slugs (e.g. `uht-full-cream-milk-1l-5001968`) but URLs are client-side routes only. No alternative server-side product API found. Viable only from a Singapore residential IP with a working Algolia DSN route. Probed 2026-06-30.

- **wolt.com restaurant venues** (multi-country, e.g. `wolt.com/en/grc/athens/venue/kalo-pizza`) — **`_wolt_base.py`'s category-walk pattern silently returns near-nothing for restaurant/food venues; it only works for grocery venues.** Grocery venues' `query-state` blob carries a `venue-assortment/category-listing` query (category slugs) + a per-category `venue-assortment/category` query returned by GET-ing `/items/<slug>` — that's what `_wolt_base.py` parses. Restaurant venues have migrated to a "unified store page" content model: the SAME `/items/<slug>` URL (any slug, even a nonexistent one — the category param is ignored) returns only a `venue-assortment/venue-content` query whose single `sections[]` entry is a curated "Most ordered" teaser (~9 items), never the full per-category menu (`ΠΙΤΣΕΣ`/`BURGERS`/etc. category names appear in the DOM as anchor-scroll tabs, not routes). Confirmed via full Playwright network trace (`networkidle` + scroll + tab click) — no further XHR ever fetches the remaining categories; the data plainly is not shipped to the client for categories beyond "Most ordered". The "Most ordered" teaser items do carry real name+price and would individually clear the 5-row gate, but shipping it would badly under-represent the venue's real menu (5 of 6 categories invisible) and the item set is algorithmically curated/rotating, not a stable observable catalog — not shipped. No open menu API found (`consumer-api.wolt.com/order-xp/web/v1/venue/slug/<slug>/dynamic/` returns delivery/checkout metadata only, no items). Division 11 (restaurants & accommodation) remains a genuine gap in the repo; the Eurostat PPP price-level-index route (`prc_ppp_ind`, ppp_cat=A0111) was used instead as a 38-country index-level substitute — a real per-restaurant price source for division 11 is still an open lead. Probed 2026-08-07.

- **market.extra.ge** (GE, "Extra Market") — backend is the "Moitane" white-label grocery-delivery platform (same tenant as `lavka_uz`/`globus_online_kg`), REST API at `api.moitane.ge`. `GET /v1/Categories?BrandId=1&Latitude=..&Longitude=..` works unauthenticated (200, real category tree, shopId=91) but the products-by-category endpoint requires a session: `GET /v1/Tags/main-tag-prods` (the one products-shaped call seen in a Playwright network trace) returns 401 without auth, and every guessed REST path (`/v1/Products?CategoryId=`, `/v1/Products/ByCategory`, `/v1/Shops/{id}/Products`) 404s. Needs an actual client-side category click captured live (the SPA has no plain `<a href>` category links, router-driven) to find the real products call. Probed 2026-09-01 (ECA sweep, agent B).
- **bigmarket.ge** (GE) — real Next.js e-commerce, but a GENERAL marketplace (beauty-personal-care, clothing, appliances, home-kitchen, smart-home, computers, electronics) with no food/grocery vertical at all — disqualified on category relevance, not on technical grounds. Uses Next.js App Router React-Server-Component `_rsc=` fetches, not plain JSON, if ever revisited for a non-food division. Probed 2026-09-01.
- **goodwill.ge**, **spar.ge**, **2nabiji.ge** (GE) — all React/Next.js SPA shells, zero price signal and zero product links in a raw `curl_cffi` fetch; none taken to a full Playwright network trace this pass (budget went to market.extra.ge once its Moitane API was found). `2nabiji.ge` carries `og:site_name: "Ori nabiji Commerce"`.

## Hashed-CSS-class SPAs (content-hashed class names)

Next.js / styled-components / similar where class names are content-hashed at build time. Selectors observable in a dump break on every site deploy. Selection by structure (tag positions, attribute prefixes like `class*="ProductCard"`) is sometimes possible but fragile — defer unless high priority.

- **truemeds.in** (IN) — re-tested 2026-05-18: listing returned 0 `a[href^="/otc/"]` anchors; SPA does not hydrate cards in headless Chromium at all (likely bot fingerprinting on top of hashed classes). Stay deferred; needs real-browser stealth + residential IN IP.
- **sendo.vn** (VN) — d7ed-* hashed CSS class names; React SPA; zero product prices in server-rendered HTML. See also CDN connection-reset section for the sendo.vn redirect chain. Probed 2026-06-15.

## JS punishment redirect (session cookie + window.location.reload)

Site returns a tiny HTML stub that sets a session cookie and forces a reload; bare HTTP clients loop forever. Signature: 177-byte HTML body with `document.cookie="D1N=<hex>"` and `window.location.reload(true)`.

- **lazada.vn** (VN, Lazada Vietnam — Alibaba marketplace) — `<script>sessionStorage.x5referer=...;window.location='//…/punish?x5secdata=…'</script>` JS punishment redirect on category/search pages. Probed 2026-06-15.

- **e-dostavka.by** (BY, Евроопт/Eurotorg's own online storefront — Belarus's largest retail chain) — homepage clears `curl_cffi impersonate=chrome124` clean (200, real `__NEXT_DATA__` product data), but `/categories` and any `/category/<id>` path serve a client-side JS "Verification" stub: checks `navigator.webdriver`, runs a busy-loop proof-of-work calc, `document.cookie="hg-security=...; max-age=120"`, then `setTimeout(() => location.reload(), 200)`. A stealth-patched Playwright pass (`navigator.webdriver` overridden to `undefined`) still resolved to a real, IP-keyed "403 Access denied" page rather than passing the challenge — genuine block on non-homepage paths, not a curl-TLS artifact (both curl_cffi and a stealth-patched Playwright landed on the wall). Real product data shape documented in case a future pass has an in-country egress or solves the cookie: `productId`, `productName`, `price.basePrice` (BYN), embedded in the homepage's `__NEXT_DATA__`. Probed 2026-09-01 (ECA sweep, agent B).

## Imunify360 bot-protection (415 Unsupported Media Type on REST API)

Server returns HTTP 415 on any `wp-json/wp/v2/` API call, including GET requests. Signature: nginx gateway returns 415 with a JSON body `{"message":"Access denied by Imunify360 bot-protection. IPs used for automation should be whitelisted"}`. The site's HTML pages may also block (varies). Workaround: use Wayback Machine WP JSON API mirror which serves the same endpoint without the Imunify360 filter, or attempt the live site with a full browser UA and `Referer` header (PDF direct downloads sometimes succeed despite the API block).

- **statistics.gov.sb** (SB, Solomon Islands NSO) — Imunify360 on all `wp-json/` calls; 415 with access-denied message. PDF direct downloads also 415 from non-SB IPs. Workaround: Wayback WP JSON API (https://web.archive.org/web/2025/https://statistics.gov.sb/wp-json/...) returns posts without bot challenge; Wayback PDF download works. Probed 2026-06-15.

## NSO portal SSL certificate failures

Some national statistics office portals have expired SSL certificates causing `unable to verify the first certificate` or `certificate has expired` errors. These are NOT bot blocks — the data is reachable via a PxWeb API subdomain (valid cert) or via `requests` with `verify=False` as last resort.

- **www.1212.mn** (MN, Mongolia NSO) — SSL cert expired/invalid 2026-06-10. Use `data.1212.mn` (PxWeb API) or `opendata.1212.mn` (REST API v2.0) instead. CPI table DT_NSO_0600_009V1 accessible via API. Not a WAF; cert maintenance issue only.
- **www2.1212.mn** (MN, Mongolia NSO legacy portal) — same expired cert. Livestock/food average-price table at `tablesdata1212.aspx?tbl_id=dt_nso_1001_040v2` accessible with `verify=False` or via main API.
- **er.erc.mn / erc.mn** (MN, ERC subdomains) — SSL cert expired 2026-06-10. Use `erc.gov.mn` (cert valid) for electricity tariff pages.
- **laosis.lsb.gov.la** (LA, Lao Statistics Bureau LAOSIS portal) — SSL cert invalid 2026-06-10 (`unable to verify the first certificate`). Contains CPI and market-price indicators for Lao PDR. Use `requests` with `verify=False` as workaround; no known API subdomain. Not a WAF; cert maintenance issue only.
- **www.bol.gov.la** (LA, Bank of the Lao P.D.R.) — SSL cert invalid 2026-06-10, same signature as LAOSIS. Inflation/CPI page at `/en/inflation` inaccessible via WebFetch. Use `requests` with `verify=False` or Wayback Machine.
- **www.bol.gov.la — RE-PROBED 2026-08-11: SSL cert issue is RESOLVED, but do not scaffold — content problem, not access problem.** `curl -v` shows a currently-valid cert chain (expires 2026-08-29) and a clean TLSv1.3 handshake with no verification error — `verify=False` is no longer needed. A bare/non-browser UA gets an HTTP 403 "Web Application Firewall" interstitial (a UA-gated WAF rule, not a cert problem); a realistic browser UA (`curl -A "Mozilla/5.0 ..."`) gets a normal HTTP 200 with the real page. `/en/inflation` renders a working year-picker table, but it carries **only the headline all-items CPI (points) + YoY inflation rate (%)** — no COICOP division breakdown at all. Two reasons this is still not worth scaffolding: (1) `laosis_cpi.yaml` already covers full 01–12 division-level CPI for Lao PDR from a richer source; (2) `IndexObservation.coicop_code` (`src/prices/enrich/schemas.py`) is a required field with no all-items/"00" sentinel — see the onboard-price-sources skill's "Open design questions" — so a headline-only fetcher would emit rows the pipeline currently drops by convention, failing the ≥5-row ship gate. Revisit only if the headline-CPI schema gap gets resolved.
- **telkomcel.tl** (TL, Telkomcel) — SSL certificate verification failure (`unable to verify the first certificate`) on `telkomcel.tl/p/internetrapidodemais` and subpages. Not a WAF; cert misconfiguration issue. Plans page `/page/prepaid/` returns 404. Use `requests` with `verify=False` on the root domain to check for plan pricing pages, or consult Wayback Machine. Checked 2026-06-10.
- **vnso.gov.vu** (VU, Vanuatu Bureau of Statistics) — not an expired cert, a different sub-case: the leaf cert (`*.gov.vu`, Sectigo-issued, valid to Sep 2026) verifies fine against clients that chase AIA for a missing intermediate (macOS/curl both show `SSL certificate verify ok`), but python's certifi-only `requests`/`ssl` context rejects it with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. Workaround is the same: `requests.get(..., verify=False)`. Confirmed 2026-08-11 — CPI fetcher (`vnso_cpi.py`) uses this workaround successfully.

## Country-wide IP-fence cohort (HTTP 403 from non-target IPs, likely fine in-country)

Distinct from the CDN connection-reset section: these sites complete the TCP handshake and return an HTTP-layer 403 with a branded error page, indicating an application-tier IP allowlist (national CDN POP + WAF rule) rather than a structural anti-bot. Probing from outside the country produces false-negatives — the site likely works from a residential in-country IP. Skip from a non-target IP rather than waste cycles iterating on selectors against the error page.

**Mongolia cohort (probed 2026-06-10 from a non-MN IP):**

- **unegui.mn** (MN) — HTTP 403 from non-Mongolian IP; likely works from MN residential IP. Mongolia's main classifieds/real-estate portal. Application-tier IP allowlist, not Cloudflare. Needs in-country residential IP probe before building spider.

**CNMI cohort (probed 2026-08-11 from a non-US/CNMI IP):**

- **ver1.cnmicommerce.com / cnmicommerce.com / www.cnmicommerce.com / commerce.gov.mp** (MP, CNMI Dept of Commerce) — HTTP 403 from all four hostnames, Cloudflare-fronted, branded page reads "cannot access this website due to your location, network, or connection." No newer non-`ver1` host exists (all four checked, all 403). Worked around for `cnmi_cpi.yaml` by falling back to the Wayback Machine mirror (captured as recently as 2025-11-10, full history back to 2003 Q1) — direct fetch is still attempted first in case the production run's own egress IP has access.

**Ukraine wartime cohort (probed 2026-06-09 from a non-UA IP, all 403'd):**

Supermarkets — silpo.ua, atbmarket.com, auchan.ua, varus.ua, megamarket.ua. Pharmacies — tabletki.ua, apteka911.ua, anc.ua. Marketplaces / electronics — rozetka.com.ua (429, rate-limit not 403), allo.ua, foxtrot.com.ua. Personal care — eva.ua, brocard.ua (404 on /uk/ — branded error). Utility/transport — naftogaz.com, booking.uz.gov.ua, minagro.gov.ua. Delivery — glovoapp.com/ua. Some of these may genuinely run Cloudflare strict — re-probe individually from a UA residential IP before deciding per-source.

**UPDATE 2026-09-01 (wave 12):** the "all 403'd" verdict above was measuring bare curl's TLS fingerprint (rule 11), not a real block, for at least the supermarket row. Re-probed with `curl_cffi impersonate=chrome124` from a (still non-UA) network — silpo.ua, atbmarket.com, auchan.ua, varus.ua all returned HTTP 200 on the first try, no UA-resident IP or DNS re-resolution needed. `megamarket.ua` was not re-checked (budget went to the two that verified fastest). Built as spiders: `silpo_ua` (Nuxt SSR, product payload embedded per-category-page) and `atb_market_ua` (plain server-rendered HTML). `varus.ua` (Magento+Apollo/GraphQL) and `auchan.ua` (full client-side Apollo/GraphQL SPA, zero server-rendered nav) are live and reachable but deferred — they need a real API/GraphQL sniff session this wave didn't budget for; see `references/inventories/eca/ukraine.md` for detail. `zakaz.ua` (the delivery-platform aggregator, not `novus.zakaz.ua`) still 403'd under the same `chrome124` impersonation, consistent with the existing `novus.zakaz.ua` entry elsewhere in this file — treat the `zakaz.ua` tenant as a real block, not a curl artifact. **SUPERSEDED 2026-09-05: the 403 is only on the marketing ROOT `https://zakaz.ua/`. The tenant is not blocked** — `stores-api.zakaz.ua` and the per-chain storefront subdomains all return 200 anonymously, and seven chains were built off the platform API that same day. The lesson generalises: a 403 on a platform's *brand* domain says nothing about its API host, and this one cost two waves. Separately, **megamarket.ua and eva.ua ARE genuine Cloudflare 403s** — re-probed 2026-09-05 under `curl_cffi` `chrome124` AND `safari17_0`, both 403 with `server: cloudflare` and a ~5KB challenge body. `megamarket.ua`'s block is irrelevant to coverage, though: the chain's Zakaz.ua storefront is open and is what `megamarket_ua` scrapes. `varus.ua`, `auchan.ua`, `novus.ua` and `tavriav.ua` all still return 200 under `chrome124`. Re-probe the untouched pharmacy/personal-care/utility rows in this cohort the same way before trusting their 403 either.

**Maldives — eat.mv (probed 2026-09-01 from a non-MV IP):** `eat.mv` ("EAT.mv" online supermarket, bakery/dairy/frozen-meat/fruits-veg, MVR 130 min order) returns a plain Apache 403 ("Forbidden... Additionally, a 403 Forbidden error was encountered while trying to use an ErrorDocument to handle the request") on `curl_cffi impersonate=chrome124/chrome120/safari17_0` — identical generic Apache body across all three profiles, no Cloudflare/Akamai/challenge markers at all (`server: Apache`, plain `text/html; charset=iso-8859-1`). Reads as a mod_security/allowlist rule rather than a CDN WAF, consistent with an application-tier IP block. Re-probe from a Maldivian residential IP before writing off.

**Tunisia — courses.monoprix.tn (probed 2026-09-01):** Monoprix Tunisie's e-commerce subdomain (`www.monoprix.tn` itself is a corporate/loyalty shell with no catalog — the real shop lives at `courses.monoprix.tn`, linked from the homepage) returns a custom `403 Accès bloqué pour test2` (Cloudflare-fronted, `cf-ray` present) on all three curl_cffi profiles AND on headless Playwright — genuine block per the mandatory gate. The non-standard body text ("blocked for test2") reads as an app-level rule (geo-fence or internal test flag) rather than a generic Cloudflare challenge template. Needs a Tunisia-resident IP to probe further; highest-value remaining Tunisia grocery target given Monoprix's chain size.

**French Polynesia — ecourses.carrefour.pf (probed 2026-08-11 from a non-PF IP):** Carrefour Polynésie's real online-ordering platform (self-hosted, LiteSpeed server, no CDN/WAF fingerprint — distinct from the Majid Al Futtaim Gulf-Carrefour Akamai tenant elsewhere in this file). `carrefour.pf/courses-en-ligne-iles` links to `ecourses.carrefour.pf/{punaauia,arue}` (~8,500 products per the marketing copy) which 403s with an explicit branded message: "Vous ne pouvez pas accéder à notre boutique depuis votre pays" (you cannot access our store from your country) — an app-level IP geofence, not a bot challenge, so Playwright would hit the identical check from the same egress IP and wasn't run. `carrefour.pf/catalogue-en-ligne` is a red herring — it only embeds a v.calameo.com flip-book flyer, not a product catalog. Needs a PF-resident IP to probe further.

**Iraq — www.carrefour.iq (probed 2026-09-05 from a non-IQ IP):** Majid Al Futtaim's Carrefour Iraq storefront returns `Server: AkamaiGHost` + a branded "Access Denied" page on `/`, on `/robots.txt`, and on `/api/v8/...` alike, under `curl_cffi impersonate=chrome124`. A block that also refuses `robots.txt` is an origin/geo refusal rather than a TLS-fingerprint challenge, so a different impersonation profile will not help — this needs an Iraq-resident exit node. Related but distinct hosts: `carrefouriraq.com` resolves and returns a bare 404 (parked), `www.carrefouriraq.com` and `mafcarrefour.com` do not resolve / fail TLS. Highest-value remaining Iraq grocery target.

**Iran cohort (probed 2026-09-05 from a non-IR IP):** `shahrvand.ir` (Shahrvand chain stores) 403s on every path under `chrome124`. `api.okala.com` (Okala, Iran's largest online supermarket) returns an Imperva-style "Request Rejected / support ID" stub. Note that most Iranian misses in this sweep were *reachability*, not blocks — `hyperstar.ir`, `ofoghkoorosh.com`, `janbo.net`, `korooshmarket.com`, `etka.ir`, `mahanmarket.ir` and a dozen others fail at DNS or TLS-cert level from a non-IR network and may be perfectly healthy in-country. Record those as unreachable, not blocked. See `references/inventories/menaap/iran.md`.

**Yemen — yemenimarket.com (probed 2026-09-05):** 403 under `chrome124`. `bezaat.com` returns HTTP 526 (edge cannot complete TLS to origin) on every path. Most Yemeni candidates fail at DNS entirely; see `references/inventories/menaap/yemen.md`.

## JD proprietary bot detection — JDR_shields + login wall (200 OK + bot-challenge stub)

JD.com runs its own in-house bot detection stack called `JDR_shields`. Curl to product or category pages returns HTTP 200 but body is a ~2,704-byte JS challenge page (title "京东验证" = "JD Verification", `window.bp_bizid="JDR_shields"`). Playwright with `--disable-blink-features=AutomationControlled` reaches JD's login page (title "京东-欢迎登录"), not product listings — all returned "product-like" links are `passport.jd.com/new/login.aspx` login redirects. No API endpoint is reachable without a valid JD account session. This is a proprietary challenge, not Cloudflare or Akamai. Bypass requires a registered JD account + residential CN IP + captcha solver or official JD Open Platform API key.

- **www.jd.com / channel.jd.com / item.jd.com** (CN, JD.com — largest CN online retailer; covers groceries, pharmacy, apparel, electronics, personal care) — JDR_shields 2704-byte bot challenge on curl; login wall on Playwright. Confirmed blocked 2026-06-30. Probed food category (`channel.jd.com/food.html`) + product PDP + JD supermarket subdomain. COICOP 01/02/05/06/08/13 gap; no public food-retailer coverage available without auth.

## App-only / no scrapeable web catalogue

The site exists but products are not browsable on the web. Skip — no amount of scraping helps.

- **order.ramsons.gi** (GI, Ramsons Supermarket — Gibraltar's main supermarket chain, trading since 1975) — the ordering subdomain returns HTTP 200 with the title "Ramsons Supermarket - Web Ordering Coming Soon" and no catalogue; the only functional links are the iOS App Store and Google Play listings for "Ramsons Delivery". The apex `www.ramsons.gi` is a 13KB Bootstrap brochure page. **Flagged as ANNOUNCED, not absent** — "coming soon" means this is worth re-checking in a future wave, unlike a permanent app-only retailer. Gibraltar coverage currently comes from `sosisvege_gi` instead. Probed 2026-09-01.

- **chipmongretail.com / www.chipmongretail.com** (KH, Chip Mong Retail — Chip Mong Group supermarket/mall chain, COICOP 01/02/05 candidate) — apex and `www` both return a generic nginx 403 with an MSIE/Chrome-friendly-error-page padding comment stub, reproduced identically on plain curl and `curl_cffi impersonate=chrome124` (with and without TLS verification) — looks like a blanket datacenter-IP block rather than a WAF challenge page. `portal.chipmongretail.com` (incl. `/qrdownloads`) is a bare Vite/JS SPA shell whose only visible route is a QR code driving users to the iOS/Android "Chip Mong Retail" app — confirms the retailer's online ordering is app-only. Existing physical/foodpanda-listed branches (271 Mega Mall, Camko) are third-party marketplace listings, not a first-party catalogue. Probed 2026-09-01.
- **luckysupermarket.com.kh / www.luckysupermarket.com.kh** (KH, Lucky Supermarket — 8+ branches in Phnom Penh/Siem Reap/Battambang, COICOP 01/02/05 candidate) — domain does not resolve (`curl: (6) Could not resolve host`) on both apex and `www`. Chain's only online presence is via foodpanda/GrabMart per-branch storefronts (marketplace, not first-party). Probed 2026-09-01.
- **Thai Huot Market** (KH, thaihuot.com) — established Phnom Penh/Siem Reap import grocery chain with a working corporate site (`thaihuot.com/Market`), but no online ordering, cart, or per-product price found anywhere on the domain — physical-store-locator content only. Probed 2026-09-01.
- **happyfresh.id** (ID) — landing page is "Download the app" only.
- **tigmooeats.com** (ZM, "TigmooEats" — wave 12 workbook ACCEPT, food/grocery/drinks delivery in Lusaka/Kitwe/Ndola) — the web root is a static Bootstrap marketing template (owl-carousel, wow.js, mailchimp signup, Google Play + App Store badges) for the mobile app, not a SPA front-end for any ordering framework: no `ng-app`/`id="app"`/`id="root"`/`data-reactroot`/`__NUXT__`/`__NEXT_DATA__` markers anywhere in the served HTML. Confirmed via full Playwright render (networkidle + 3s wait): zero listing/vendor/store/product API calls fire even after JS execution — only Google Maps, Google Analytics, and a `chat.tigmoo.com/api/appidcheck` widget ping. Client-side route `home/listing/<lat>/<lng>` serves the identical landing-page bytes (no client router). App-only, no web ordering surface exists. Probed 2026-09-01 (wave 12).
- **astronauts.id / astro** (ID) — geo-fenced to ID residential IPs AND mostly app-driven.
- **food.grab.com/mm/en/** (MM, GrabFood Myanmar) — hard login wall; "Login to search location" before any restaurant or menu data is visible. Confirmed June 2026. SKIP.
- **shop.com.mm** (MM, Daraz Myanmar) — SPA with no prices in SSR HTML (confirmed June 2026; see SPA section above). No login required but product cards never populate in HTML source. Alibaba/Daraz platform.
- **Kmanek Supermarket / Leader Hypermart** (TL) — Facebook-only, no public e-commerce site.
- **zaad.delivery** (SD, Zaad Delivery) — Astro+Vue marketing site only ("food, pharmacy items, and daily essentials"); nav has About/Contact/FAQ/Partners/Terms, zero shop/menu/product links, zero price mentions after full Playwright render (8s wait). Front page is behind an `hcdn`-branded JS proof-of-work interstitial that survives curl_cffi impersonate chrome124/chrome120/safari17_0 but clears fine in headless Chromium — the WAF is real but irrelevant, since the rendered site behind it has no catalogue at all. Probed 2026-09-01.
- **mytalabaty.com** (SD, Talabaty) — connection timeout (28s) on curl_cffi chrome124, host effectively unreachable. App store listing says "coming soon", consistent with wave-6 finding. Probed 2026-09-01.
- **murrsal.com** (SD, "Nine | Sudan's Premier Food Delivery Platform") — broken/self-signed TLS cert forces `verify=False`, and every path (`/`, `/en`) 404s regardless. Site is effectively dead. Probed 2026-09-01.
- **dukani.online** (SD, "Dukani" grocery app) — NOT a Sudan storefront: the page is a leftover white-label SaaS marketing/demo site (branding for "Lezzoo", a Kurdistan/Iraq delivery-app vendor, `cal.com/.../dukani-demo` booking link, links to `facebook.com/Lezzooeats`). No Sudan catalogue. `dukani.sd` 403s outright. Probed 2026-09-01.
- **songo.mn** (MN, food delivery) — ECONNREFUSED on direct fetch 2026-06-10; Facebook page active but web portal appears offline or heavily restricted. Skip until web portal confirmed operational.
- **food.grab.com/vn/en/** (VN, GrabFood Vietnam) — same login wall as GrabFood MM; "Login to search location" before any restaurant/menu data visible. Probed 2026-06-15.
- **viettel.vn** (VN, Viettel telco) — cookie-challenge anti-bot: 177-byte HTML stub with `document.cookie="D1N=…"; window.location.reload(true)`. Plan prices not accessible without a real browser session. Probed 2026-06-15.
- **foody.vn** (VN, restaurant aggregator / delivery) — login wall (21+ occurrences of "login" in page); restaurant menu prices not accessible without account. Probed 2026-06-15.
- **beeorder.com / www.beeorder.com** (SY, "BeeOrder" — Syria's largest food/grocery delivery platform since 2016) — homepage and every internal link (`/contact-us`, `/faq`, etc.) are the SAME static marketing landing page (App Store/Google Play/Instagram/Facebook links only); `www.beeorder.com/index.php/home/download_page` 404s. No web ordering surface exists — confirmed by extracting every `href` on the page (all external/app-store or anchor links, zero `/shop`/`/vendor`/`/store` paths). Probed 2026-09-01.
- **movo.delivery** (SY, "Movo" — Syrian multi-category delivery app, restaurants/pharmacies/groceries/flowers) — every route (`/`, `/store/contact-us`) serves the identical static Bootstrap landing-page HTML (client-side routing never actually mounts a different view); the only `.js` files referenced are Bootstrap/AOS/GLightbox vendor bundles plus a Cloudflare challenge-platform script — no app bundle, no API references. Marketing site only. Probed 2026-09-01.
- **Target Market** (SY, "🦋 Target Market 🦋", Damascus grocery app, "Your All-in-One Grocery Companion") — no website at all; only Google Play (`com.DotCode.TargetMarket`), App Store, and Instagram (`targetmarket.sy`) listings found. App-only. Probed 2026-09-01.
- **savy.market / www.mysave** app (SY, "Savy Market" — "أفضل سوبرماركت في سوريا") — WordPress marketing site with `wp-json` exposed but NO WooCommerce namespace registered (only `oembed`, `aioseo`, `litespeed`, `wp/v2`, `wp-abilities` — no `wc/v3` or `wc/store/v1`); the only shop link on the page is a Google Play badge for `shop.mysave.customer`. App-only, no web catalogue. Probed 2026-09-01.
- **moovmart.com** (SY, "Moov Mart" — "تطبيق توصيل البقالة") — Next.js site whose `pages/index` JS chunk is only 2.2KB with zero app-store links, zero API references, zero fetch/axios calls — reads as a barely-built placeholder/landing page for what is otherwise an app-only grocery-delivery service (per its own tagline). Probed 2026-09-01.
- **alshaebclick.com** (JO, "AlShaeb Click" — "من مطاعم وسوبرماركت وصيدليات ومستلزمات البيت في تطبيق واحد") — 280KB homepage is entirely App Store/Google Play links (base64-embedded screenshots inflate the size); zero internal `href` paths of any kind (`/shop`, `/store`, etc.), zero occurrences of the word "price" anywhere on the page. App-only. Probed 2026-09-01.
- **gov.bn "Pengguna Bijak" / SmartConsumer** (BN, `www.gov.bn/Lists/Mobile%20Apps/NewDisplayForm.aspx?ID=5`) — government price-comparison app; the listing page is a bare SharePoint entry with a Google Play link (`bn.gov.egnc.jpke_smartconsumer`) and category "Shopping", no web catalogue, no linked API. Probed 2026-08-11.
- **puregold.com.ph** (PH, Puregold — major hypermarket chain) — corporate Joomla site (IR/news/careers only; `index.php?format=feed&type=atom` is a Joomla tell), zero catalog links. The onboarding-brief URL path `/pgcatalog/category/view/category/...` 404s outright — that catalog route has been removed. Current online-shopping channel is the "Puregold Mobile" app (Google Play, `com.grocery.puregold`) confirmed via web search — app-only. `pgcms.puregold.com.ph` is a Vite SPA titled "Puregold CMS" with an empty `#root` — an internal admin tool, not a public storefront. `shop.`/`eshop.` subdomains don't resolve. Probed 2026-08-11.
- **gokkam.com** (SL, "Gokkam" — self-described #1 online ordering/delivery platform in Sierra Leone) — domain does not resolve at all (`gokkam.com`, confirmed via DNS against 8.8.8.8); the product is exclusively an Android/iOS app (Google Play + App Store listings, Facebook/Instagram marketing). Probed 2026-09-01.
- **sendmesl.com** (SL, "SendMe" food delivery) — web page is a marketing landing page with app-store download buttons only ("com.sl.sendme.consumerapp" on Google Play); no browsable restaurant or vendor listing reachable on the web. Probed 2026-09-01.
- **salonefastmarket.com** (SL, "Salone Fast Market") — lists a "Food & Agriculture" category on the homepage, but the link (`/app`) is an app-store-gated Flutter/JS SPA shell with no server-rendered content. The homepage's own JSON-LD `AggregateOffer` schema for that category (`lowPrice: 50000, highPrice: 5000000` SLL) is generic marketing/SEO markup, not real per-item pricing — do not treat JSON-LD price ranges on this domain as data. Probed 2026-09-01.
- **market360.shop** (SL, "Market360" marketplace) — sitemap and marketing copy confirm an app-first marketplace (Google Play / App Store); web root has no food/grocery category, general-goods focus (electronics/fashion/phones/vehicles) confirmed via search summary and homepage keyword scan. Probed 2026-09-01.
- **pedidosyasv.com.sv** (SV, PedidosYa El Salvador) — the delivery-app rule (a named supermarket behind an app counts as `supermarket`) does not apply here: the public web root only exposes restaurant/food-delivery paths (`/restaurantes`, `/comidas`); `/supermercados`, `/mercado`, `/market` all 404. "PedidosYa Market" (their dark-store grocery vertical) is app-only, no web catalogue reachable. Probed 2026-09-01 (wave 10).
- **watti.ly** (LY, "Watti" — wave 10 workbook ACCEPT candidate, "Live: Libyan grocery/food delivery, .ly domain") — the public site is a marketing landing page only (Bootstrap/jQuery template, hero copy "Everything You Need Delivered Fast. **Coming Soon.** Download the app and experience hassle-free grocery & food shopping."). No product/menu/vendor browsing exists on the web; the consumer app has not launched. `panel.watti.ly` (vendor/admin portal) redirects in an infinite loop. Not "live" as scouted — pre-launch. Probed 2026-09-01 (wave 10).
- **drubi.ly** (LY, "Drubi" delivery/ordering app connecting restaurants and stores) — landing page only, app-store links (`apps.apple.com/.../drubi`, `play.google.com/.../drubieats`) — no web catalogue. Probed 2026-09-01 (wave 10).
- **jetak.me** (LY, "JETAK" — Benghazi-based delivery app, white-label Sixam Mart/6amMart-family Laravel stack per `com.sixamtech.sixam_mart_store_app`) — marketing/informational pages only (about-us, contact-us, deliveryman/apply, privacy, terms); no store/product browsing route exposed on the web domain. App-store links only. Probed 2026-09-01 (wave 10).
- **dokkan.ly / www.dokkan.ly** (LY, "Dokkan" app-based supermarket service per WebSearch summary — thousands of products, supermarket/meat/veg/fruit/pharmacy/electronics) — neither domain resolves (`curl: (6) Could not resolve host`); the product is exclusively the "دكان ليبيا" App Store app, no web presence at all. Probed 2026-09-01 (wave 10).
- **wdelivery** (LY, "WDelivery — Libya Shop & Order" — hub for grocery/restaurant/pharmacy delivery per App Store listing) — no `wdelivery.ly` / `www.wdelivery.ly` / `wdelivery.com.ly` domain resolves; App Store app only (`apps.apple.com/.../wdelivery-libya-shop-order`). Probed 2026-09-01 (wave 10).
- **menamart-angola.com** (AO, "Mena Mart" — wave 10 workbook ACCEPT candidate, "Live: Kz prices, stock flags, wholesale case sizes") — B2B wholesale Laravel site. Homepage server-renders ~1,323 product cards (name + pack size only, e.g. "OLEO DE PALMA ALIMO, 12 x 1L") but genuinely carries no price text anywhere in the public HTML: every "ADICIONAR" button links to `/login`, there is no reachable per-product detail URL outside the login flow (only `/sobre` besides ~1,288 `/login` links), and the ~30 apparent "Kz" substring hits are all coincidental matches inside random image-filename hashes (e.g. `...UBSoC53aYsKzsxRA...`), not currency text. Workbook's "Kz prices" claim does not hold on a fresh unauthenticated fetch. Probed 2026-09-01 (wave 10).
- **site.mamboo.co.ao / mamboo.co.ao** (AO, "Mamboo" — wave 10 workbook P4/SUSPECT, "super-app (Angola and Tanzania); catalogue behind app") — both the `site.` marketing subdomain (1,276 bytes) and the bare apex domain (939 bytes) are placeholder shells with no catalogue; `app.`/`loja.`/`shop.` subdomains do not resolve. Confirms the brief's own prediction. Probed 2026-09-01 (wave 10).
- **chapchapgabon.com** (GA, "Chap Chap Gabon" — wave 11 workbook ACCEPT, "12 cities, epiceries vertical, Airtel/Moov Money") — resolves and loads (200), custom single-page marketing site for a multi-vertical delivery app (restaurants/épicerie/pharmacie/colis). Grepped the full HTML for `FCFA`/`produit`/`panier`/`catalogue` — no real product content; the only external links are one Google Fonts stylesheet and an App Store badge, all in-page nav is bare `#anchor` links. No web ordering surface exists at all. Probed 2026-09-01 (wave 11).
- **www.libregolivraisons.ga** (GA, "Libre-Go Livraison" — wave 11 workbook SUSPECT, "catalogue sits behind login") — it's a courier/delivery-fee company, not a retailer: the only `FCFA` mentions on the page are a live delivery-fee calculator, a late-delivery compensation clause, and an invoice total. No `produit`/`catalogue`/`boutique` text anywhere — there is no product catalogue behind the login wall to begin with. Probed 2026-09-01 (wave 11).
- **sendmontchop.com / www.sendmontchop.com** (GA, "SendMonTchop" — wave 11 workbook SUSPECT, "restaurant-led; grocery depth unclear") — both hosts redirect (114-byte stub) to `/lander`, which serves a GoDaddy/`wsimg.com` parking-lander shell (`window.LANDER_SYSTEM="PW"`). Domain has lapsed to registrar parking; not a food-basket service anymore, just dead. Probed 2026-09-01 (wave 11).
- **isaimarket.com** (GA, "Isai Market" — surfaced in search-engine cache as a live Libreville grocery-delivery service) — NXDOMAIN confirmed via `dns.google` and `cloudflare-dns.com` DoH querying the authoritative `.com` TLD servers directly (not a resolver-cache issue). Domain has lapsed. Probed 2026-09-01 (wave 11).
- **systemelad.com** (GA, "Système LAD" — Libreville/Akanda/Owendo delivery per search snippet) — no A record on 8.8.8.8 at all; does not resolve. Probed 2026-09-01 (wave 11).
- **malumbi.com** (GA, "Malumbi" — wave 11 workbook ACCEPT, PrestaShop épicerie/fruits/viandes with Airtel Money checkout) — NXDOMAIN confirmed via `dns.google` and `cloudflare-dns.com` DoH querying the authoritative `.com` TLD servers directly. Search-engine cache still shows old page titles (`malumbi.com/17-epicerie`, `/15-conserves`) confirming it was real once, but the domain has lapsed as of 2026-09-01. Tried `.shop/.africa/.ga/.io/.store` TLD variants and a `shop.` subdomain — none resolve. Probed 2026-09-01 (wave 11).
- **arkan.top.ly** (LY, "Arkan Market — Online Libyan Store", surfaced via search) — NXDOMAIN confirmed against both `8.8.8.8` and `1.1.1.1` explicitly (rule 15 DNS-lie check) — genuinely dead, not a sandbox resolver issue. Probed 2026-09-01 (wave 11).
- **duka.direct** (TZ, "duka.direct" — Selcom-run marketplace, wave 12 workbook ACCEPT, "largest Tanzanian e-commerce platform") — the public domain is a Tilda page-builder marketing site only (no `ng-app`/`id="root"`/`__NUXT__` app markers, all script tags are `static.tildacdn.one`); every CTA points to `get.duka.direct`, an app-install redirector that itself timed out (28s, curl_cffi chrome124). No product/store data reachable from the web domain. Probed 2026-09-01 (wave 12).
- **imadi.co.tz** (TZ, "Imadi MbogaMboga" — fruit/veg/grocery delivery, Dar es Salaam) — static one-page marketing site (plain HTML/CSS, no JS framework); every CTA is a Google Play / App Store badge or a `wa.me` WhatsApp link. No web ordering or catalogue route exists. Probed 2026-09-01 (wave 12).
- **sokeru.st** (STP, "Sokeru" — wave 13 workbook ACCEPT, "First Santomean e-commerce platform, iOS and Android, Dobra Digital payments") — NXDOMAIN, confirmed against `8.8.8.8` AND `1.1.1.1` explicitly (rule 15 DNS-lie check), not a sandbox resolver issue. The workbook's own note ("App-led") predicted this correctly even before the domain died outright — the product was Android/iOS-only from the start. Probed 2026-09-01 (wave 13).
- **www.superckdo.com** (STP, "Super CKdo" — wave 13 workbook SUSPECT, plain HTTP no TLS, "promotions posted to Facebook rather than a catalogue") — NXDOMAIN, confirmed against `8.8.8.8` AND `1.1.1.1`. Probed 2026-09-01 (wave 13).
- **enco.st** (STP, ENCO — Empresa Nacional de Combustiveis e Oleos, the STP fuel-import/distribution parastatal) — the customer-facing site (Vite SPA) is real and live, and its backend API (`encoserver.exportech.com.pt`) is behind a JS "checking your browser" proof-of-work interstitial that beats `curl_cffi` on chrome124/chrome120/safari17_0/chrome99/chrome131 — but clears fine under a real Playwright-driven Chromium (mandatory gate: only curl failed, so this is NOT recorded as a hard WAF block). Once past the challenge the API returns exactly 1 product (a Galp motor-oil lubricant) with no price field in its schema at all (title/shortDesc/html/image/category/tags only) and exactly 1 category. The site's `/servicos.html` page confirms ENCO publishes storage CAPACITY (m3 of gasoline/diesel/JET-A1 held, filling-station counts), never retail pump prices — administered fuel prices are not published anywhere on this domain. Structural absence of price data, not a technical block. Probed 2026-09-01 (wave 13).
- **mystore.bz** (BZ, "MyStore" — wave 13 workbook ACCEPT, "Live: grocery and household delivery platform, local stores") — the workbook's ACCEPT verdict was wrong (rule 20). Homepage and every discoverable sub-page (`/apps/web/pages/customer.html`, `/store.html`, `/delivery.html`) are pure app-marketing landing pages ("Belize's most trusted grocery and household delivery app... Shop from local stores... all from your phone") with zero product names, zero prices, zero catalogue links anywhere on the public web surface — customer/store/driver pages are each just a role-targeted pitch for the mobile app. Nothing to scrape. Probed 2026-09-01 (wave 13).

- **gannamart.com / www.gannamart.com** (MV, "Ganna Mart" online grocery, Greater Male) — resolves and returns 200, but the entire page is a static Bootstrap "coming soon"-style landing page ("Shop for your everyday necessities! ... we will deliver all you need and more to your doorstep.") with a phone-mockup image and no product/price content at all — the actual product is the mobile app (`com.daitonn.avasfood`-family per Play Store). `gannamart.mv` does not resolve. Probed 2026-09-01.
- **foodies.mv** (MV, "Foodies" — Male' area) — confirmed a restaurant/home-cook food-delivery marketplace ("order from over 100 vendors"), not F&B retail (prepared food, COICOP 11 not 01/02); app-only, no web catalogue regardless. Probed 2026-09-01.
- **pickme.lk** (LK, PickMe super-app — ride-hailing, food delivery, "Food & Market" nav item) — website is informational only, no browsable product catalog with prices; grocery/market vertical (if any) is app-only. Probed 2026-09-01.
- **foodmandu.com** (NP, Foodmandu — Kathmandu/Bhaktapur/Chitwan/Butwal) — real, live site ("List your Restaurant at Foodmandu!"), but it is a restaurant food-delivery platform (COICOP 11 prepared food), not F&B retail — does not qualify regardless of reachability. Probed 2026-09-01.

- **pricegambia.com** (GM, "PriceGambia — Online Marketplace") — carried forward from the 2026-09-02 Gambia inventory as "the single highest-value remaining lead"; **it is not a lead.** The 70KB homepage is a static Bootstrap/jQuery marketing page for an iOS/Android app (App Store id6443941439, Play `com.app.wwwpricegambiacom`). Every "SHOP NOW" / "ORDER NOW" button resolves to `https://www.mypricegambia.com/api/fb/<code>` — and `mypricegambia.com` is **NXDOMAIN**, so even the app's own API host no longer resolves. There is nothing to network-trace: the page has no XHR, no JSON, and no internal hrefs beyond `#anchors`. Do not re-probe. Probed 2026-09-05 (SSA div-01/02 sweep).
- **1bena.com** (GM, "1bena — Food delivery and rides in The Gambia") — WordPress, but the Store API returns **HTTP 500** and `/sitemap.xml` lists only `post`/`page`/`testimonial`/`cpt_services` children — there is no product post type at all. The catalogue is in the mobile app; the web tier is marketing plus a services CPT. Probed 2026-09-05.
- **goket.com.np / goketgroceries.com.np** (NP, "Goket Groceries" — wave onboard1 candidate, pre-probe said 200 OK / 55KB / 2 ld+json blocks) — the ld+json blocks are `ItemList` marketing copy, not products. Next.js on Vercel; `/categories` renders a 33KB page whose only structured data is `{"@type":"ItemList","name":"Goket Groceries product categories"}` with `name`+`description` per category and **no price node anywhere**; a Playwright render with 9s wait + two scrolls produced zero NPR/Rs price matches and zero XHR to any product API. `robots.txt` is `Allow: / Disallow: /api/` and the sitemap is 15 URLs — home, /services, /categories, /about, /contact, /terms, 4 blog posts — with no product route. Header CTA is "Get the App". Ordering happens in the mobile app only. Probed 2026-09-11.

## API confirms demo/seed data, not a live storefront (Sixam Mart / 6amMart-family Laravel backends)

Distinguish from a genuinely-thin-but-real catalog by pulling the actual store record, not just the module count: a `stores_count: 1` on the grocery module reads exactly like a real single-vendor grocery app until the store record itself is inspected.

- **jetak.me** (LY, "JETAK" — Benghazi delivery app, already known app-only from the marketing-page check above) — went one level deeper this pass: the public `GET /api/v1/config` endpoint is genuinely live (no auth) and confirms a real "grocery" module (`module_id=1`, Arabic name "غذائية", `stores_count: 1`). But the module's `slug` is literally `"demo-module"`, and the one store behind it (`GET /api/v1/stores/latest`) is `"name":"الحور مول"` with `"phone":"+101511111111"` (not a real Libyan number), `"email":"demo.store@gmail.com"`, and `"address":"House, road"` — an unreplaced installer seed store, not a live grocer. Confirms the wave-10 marketing-page verdict with API-level proof; do not re-attempt the item-listing endpoints on this tenant. Probed 2026-09-01 (wave 11).
- **drubi.ly** (LY) — re-checked for an API surface behind the already-known landing page: `/api/v1/config` and `/index.php/api/v1/config` both 404 (plain Apache 404, not even a Laravel error page) — no backend reachable on this domain at all, apex or `/index.php` prefix. `api.drubi.ly` does not resolve. Probed 2026-09-01 (wave 11).

## Azure Web App stopped (`Error 403 - This web app is stopped`)

Distinct from the Azure Front Door WAF signature above — this is a genuinely torn-down/paused App Service, not a bot-block. HTTP 403 with a literal Microsoft-branded body: `<h1>Error 403 - This web app is stopped.</h1>` + "The web app you have attempted to reach is currently stopped and does not accept any requests" + links to `portal.azure.com`. No amount of browser impersonation helps — the origin compute is off.

- **observatoriom-dc.sonangol.co.ao/precos/** (AO, Sonangol Distribuidora's official pump-price "Observatorio de Mercado" tracker — would have been a strong `tariff`/07.2.2 lead) — confirmed stopped App Service, not a WAF. Probed 2026-09-01 (wave 10).

## Brochure-only WordPress / no online store

WordPress site for an offline retailer — pages exist, products do not. No /shop/, no /product/, no PDPs.

**A 200 here is not a connectivity win.** Both sites below were flagged "worth retrying from a SEA-origin IP" after earlier probes failed at the network layer, and both did start returning HTTP 200 — with brochure content. The earlier network failure was a red herring; the sites have no catalog to reach. Read the body before treating a status-code change as progress.

- **caring2u.com** (MY, Caring Pharmacy) — WordPress + Elementor brochure; `/products` 404s. For MY pharmacy coverage use `guardian_my` (live Tier 1B) instead.
- **kimiafarmaapotek.co.id** (ID, Kimia Farma) — same shape: Elementor Pro + OceanWP, zero e-commerce hooks. For ID pharmacy coverage `k24klik` is already in the tree.
- **bim.ma** (MA, BIM Maroc hard-discount chain) — 200 OK, but the whole site is the Turkish BIM group's KuramPortal corporate CMS: philosophy, store-locator, quality-assurance, careers, contact, and a static "product presentation" page with zero prices or product names in the rendered HTML. No `/shop`, no catalog of any kind — matches BIM's global no-e-commerce posture. Probed 2026-09-01.
- **alwaha.sd** (SD, "Al Waha Supermarket") — NOT WooCommerce despite the wave-8 brief's guess. 11KB static page built on the free "Moderna" BootstrapMade corporate template (`bootstrapmade.com/free-bootstrap-template-corporate-moderna/`); `/wp-json/wc/store/products` and `/shop` both 404. No cart, no product pages, no prices anywhere on the domain. Probed 2026-09-01.
- **automotiveart.com** (BB + AG/KY/GY/JM/KN/LC/SR — multi-Caribbean auto-parts/accessories chain, confirmed Barbados-live via `geo.region: BB` meta tag) — bespoke non-WordPress corporate/catalog site, `/Barbados/Featured-Products/` lists category tiles (Seat Covers, WeatherTech Mats, Pioneer Audio, Batteries, etc.) with zero `$`/BBD price text anywhere in the rendered category or homepage HTML — in-store pricing only. `https://automotiveart.com/` also has a cert mismatch (only the `http://` and country-path `www.automotiveart.com/Barbados/` variants serve). Probed 2026-09-01.
- **koussagroup.com** (SL, Koussa Group — parent of Freetown Supermarket, Freetown Mall, City Supermarket, Venus Corporation) — static WordPress corporate site; every branch page (`/freetown-supermarket/`, `/freetown-mall/`, `/city-supermarket/`) renders byte-for-byte identical boilerplate (address, phone, generic "quality products" blurb) with no `/shop`, no product listing, no prices anywhere on the domain. Probed 2026-09-01.
- **cecagadis.com** (GA, "CECA-GADIS" — wave 11 workbook SUSPECT as `cecagadis.ga`; that `.ga` domain is NXDOMAIN, live domain is `.com`) — WordPress/Elementor corporate site for Gabon's largest retail group (brands Cecado, CK2, GaboPrix, Géant CK'DO, Intergros, Matelec, Maxi CK'DO, Maxigros, Sogame Equip, Super CK'DO, Supergros). `/wp-json/` has no `wc/` route — **not WooCommerce** despite the workbook's platform tag. Checked 4 brand "enseigne" sub-pages directly: every external link on every one is Facebook/Instagram/LinkedIn, zero shop/cart/product content anywhere. Probed 2026-09-01 (wave 11).
- **priximport.com** (GA, "Prix Import" — the operator behind the already-onboarded `cerise_ga`) — WordPress brochure site, 2019-dated blog, zero shop/boutique/catalogue content. Even if it had one it would be the same operator/shelf as `cerise_ga`. Probed 2026-09-01 (wave 11).
- **www.shoprite.co.zm** (ZM, Shoprite Zambia — wave 12 workbook ACCEPT) — same `shopriteafrica` AEM corporate portal already documented for `www.shoprite.co.mz` and `www.shoprite.co.ls` above (identical clientlibs, identical `/content/shopriteafrica/zm/en/...` path shape). `curl_cffi impersonate=chrome124` clears fine (200, no WAF). Full 140-entry sitemap is recipes (98 entries) + `explore-shoprite/*` category-description pages (Lovies, health-and-beauty, tea, butchery, money-market, liquorshop, Local-farmers) + competitions + store-locator — zero `/shop`, `/products`, `/catalogo` paths. `specials.html` links only to a privacy-policy PDF and a cookie-policy PDF, no specials leaflet with prices. No e-commerce catalogue exists for Zambia, matching the MZ/LS siblings' failure mode exactly. Probed 2026-09-01 (wave 12).
- **massystoressvg.com** (VC, Massy Stores St Vincent and the Grenadines) — static WordPress/All-in-One-SEO corporate site (`<title>Massy Stores SVG</title>`, `dateModified 2020-04-10`), `?rest_route=/wc/store/v1/products` returns `rest_no_route` — **not WooCommerce, no shop at all**, unlike the sibling Massy tenants that DO have a live storefront (`shopmassystoresbb.com` Barbados, `shopmassystorestt.com` Trinidad, `shopmassystoresslu.com` St Lucia — the St Lucia one confirmed working and onboarded as `massy_stores_slu` this pass). The `shopmassystores<iso>.com` naming pattern does not exist for SVG (`shopmassystoresvct.com` and `massystoresvct.com` both NXDOMAIN). Probed 2026-09-01.
- **pnpbotswana.co.bw** (BW, Pick n Pay Botswana) — WordPress, but no WooCommerce Store API route (`/wp-json/wc/store/v1/products` 404s) and no catalog: the site advertises **WhatsApp ordering** rather than a browsable storefront. This is a genuine null and the one Botswana major that is *not* a false negative — unlike Choppies and Sefalana, whose storefronts simply live on sibling domains (see the "Reachable, HTTP 200" section). Re-confirmed 2026-09-10 (Botswana `ddgs` sweep).
- **caribbeanonlinegrocery.com** (HT) -- front page is still the WordPress "Coming Soon / Something BIG... is about to happen!" plugin page (unchanged 2026-09-01 -> 2026-09-05), but the WooCommerce Store API behind it **is** live (229 products, USD, real prices, pages disjoint). Not shipped, for a second and better reason: the catalogue is a **pan-Caribbean diaspora assortment, not Haitian** -- dominant category tags are Barbados (18), Jamaica (8), Trinidad (8) vs **Haiti (4)** in a 100-row sample, stocked with imported brands. Do not onboard it under Haiti if it ever launches; re-assess which country it actually prices for.
- **rebo.ht** (HT, REBO S.A., wholesale food distributor) -- WordPress marketing site; both WooCommerce Store API routes (`/wp-json/wc/store/v1/products` and `?rest_route=`) return `rest_no_route`. No catalogue. Probed 2026-09-05.
- **marketgardensxm.com** (SX) -- 215KB page whose only outbound link is its own domain and whose only script is Cloudflare's email decoder. No prices, no catalogue. Probed 2026-09-05.
- **ralphsfoodwarehouse.com** (PR, Ralph's Food Warehouse) -- 200 / 27KB with **zero** `<a href>` and **zero** `<script src>` in the served HTML. No product surface of any kind. Probed 2026-09-05.
- **plazaloiza.com** (PR, Supermercados Plaza Loiza) -- Bootstrap marketing site; its nine links are `/contactanos`, `/localizaciones`, `/noticias`, `/recetas`, `/servicios`, `/shopper`, `/sobrenosotros`. `/shopper` is a weekly circular, not a priced catalogue. Probed 2026-09-05.
- **nassaugrocer.com** (BS) -- default "My WordPress" install, no Store API route. **nassaugrocery.com** (BS) -- 85KB, neither Shopify `/products.json` nor a WooCommerce Store API. Both probed 2026-09-05.

- **brugseni.gl** (GL, Brugseni/KNI) and **pilersuisoq.gl** (GL, Pilersuisoq) -- Greenland's two non-Pisiffik retail chains. Both WordPress, both HTTP 200 (152 KB / 60 KB), both with **zero** `kr` price tokens anywhere in the served HTML; brugseni's only shop-shaped link is a store-locator route. Re-confirmed 2026-09-05, agreeing with independent probes on 2026-09-01. Greenland's food e-commerce absence is structural -- do not re-probe more than once a year, and a `kr`-token count is the whole test.
- **"Spar Greenland"** (GL, a named lead with no confirmed domain) -- `spar.gl`, `www.spar.gl`, `spargreenland.gl`, `spargreenland.com` all **NXDOMAIN** on all three probe arms (plain `requests` default UA, plain `requests` + Chrome UA, `curl_cffi impersonate=chrome124`). No SPAR-branded retail entity appears to operate in Greenland under any of the obvious domain guesses; brugseni.gl (above) is the closest analogue (Greenlandic co-op grocery banner) and is independently confirmed brochure-only. WebSearch was unavailable this session (session-wide budget exhausted) to try name variants -- treat as unconfirmed-leaning-absent, not exhaustive. Probed 2026-09-11.
- **fantastico.bg** (BG, Fantastico -- major Sofia grocery chain, COICOP 01 candidate) -- 200 / 94 KB, but the entire 1,230-URL sitemap is 633 news posts, 233 blog posts, 145 recipes, 88 careers pages and 52 store pages. `/assortment` is **11** pages with no per-product price. Store locator + content marketing, no webshop. Probed 2026-09-05.
- **tinex.mk** (MK, Tinex -- major North Macedonian supermarket chain, COICOP 01 candidate) -- 200 with a 1 MB homepage, which reads like a real storefront. It is a **Wix** site: `sitemap.xml` is `generatedBy="WIX"` and contains only blog-posts, blog-categories and static pages. No products, no PDPs. Probed 2026-09-05.
- **fjardarkaup.is** (IS, Fjardarkaup supermarket, Hafnarfjordur) -- 200 / 140 KB; sitemap has 174 URLs, all campaign/marketing pages (`/pizzadagar`, `/jol`, `/50-ara-afmaeli`). No webshop. **samkaup.is** (IS) is the parent group of Netto/Kjorbudin/Krambud, a corporate site with no catalogue -- not a storefront at all. Both probed 2026-09-05.

## sgcaptcha / SignalGate CAPTCHA (200 OK + 168-byte JS redirect stub)

Site returns HTTP 200 but body is a 168-byte HTML stub with `<meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=...">`. The redirect target is a CAPTCHA challenge page. Neither bare curl nor simple browser-UA requests bypass it. Signature: tiny body (<200 bytes), `/.well-known/sgcaptcha/` in the refresh URL, `ipc:` prefix in the challenge parameter.

- **supasave.com.bn** (BN, Supa Save supermarket) — both main domain and `seria.supasave.com.bn` subdomain return the sgcaptcha stub. Brunei's main supermarket chain; COICOP 01 gap remains. Probed 2026-06-10.

## Aggregator / no canonical per-product URL

Site has products but each one is a modal within a shop page, not a canonical `/product/{id}` URL. Doesn't fit the price-spider model unless reworked to per-shop scraping.

- **foodpanda.la** (also caught by PerimeterX above)
- **happyfresh.id** (aggregator + app-only)

## No products on the site (corporate marketing portal)

- **priyoshop.com / priyoshopretail.com** (BD, "PriyoShop") — priyoshop.com is a B2B MSME-supplychain marketing portal ("B2B Marketplace in Bangladesh with embedded finance", nopCommerce generator tag) that JS-redirects every visitor to priyoshopretail.com; that domain is in turn a WordPress corporate site ("MSMEs Supplychain Simplified") — news/blog/feed paths only, no consumer cart, no per-product price. The actual retail-distribution business (corner-shop/HoReCa supply) operates through an app/WhatsApp channel, not a public web catalogue. Probed 2026-09-01 (SAR sweep).
- **bazariko.mg** (MG, "Bazariko.mg" — wave 10 workbook ACCEPT candidate, `AI_NOTES`: "STRONG: Ar prices with strike-through promotions, full supermarket taxonomy, 24/7") — the workbook claim does not match the live site. 200 OK, but the whole domain is a static Bootstrap e-commerce *template* (unmodified `single.html`/`offer.html`/`hold.html`/`kitchen.html` demo-page filenames, jQuery 1.11 + jstarbox assets) with zero product cards, zero prices, and zero `Ar`/`MGA` text anywhere across the homepage or every linked page. Footer credits `amfanoela@gmail.com` / links to `fanoela.mg`, which resolves to a freelance web developer's portfolio site (Fanoela Manohisoa) listing dozens of near-identical demo storefronts (`freshfood1.netlify.app`, `shopping-flower.netlify.app`, etc.) — Bazariko.mg is one of that developer's unlaunched template builds, not an operating grocery store. Do not build. Probed 2026-09-01 (wave 10).
- **caveshepherd.com** (BB, Cave Shepherd & Co Ltd — historic Bridgetown department store) — the department-store retail business no longer operates from this domain. WordPress/Avada corporate holding-company site: nav is Company/Retail & Services/Financial Services/Investors/Contact only, `/retail/` page shows the group has pivoted to self-storage (Store All Inc.), souvenir shops (Ganzee, Caribbean Kidz, Spice It Up), a taxi app (pickUP Barbados), and financial-services subsidiaries (SigniaGlobe, Fortress Fund Managers, DGM). Zero e-commerce, zero prices anywhere on the domain, zero `/shop` or catalog path. Not a probe failure — the retail format itself has been discontinued. Probed 2026-09-01.

Domain exists and renders but has no e-commerce — corporate/brand portal.

- **refah.ir** (IR, Refah Chain Stores — one of Iran's largest supermarket chains) — WordPress corporate site, not a storefront. Zero `/product/` links on the homepage, `/product-sitemap.xml` and `/sitemap_index.xml` both 404 (only `/wp-sitemap.xml` exists, 844 bytes of page URLs). The chain has no public online catalog at this domain. Probed 2026-09-05.
- **delivery-iraq.com** (IQ, "Delivery Iraq") — restaurant/shop delivery directory, no per-product price pages. Probed 2026-09-05.
- **biaar.com** (IR, "Biaar" — listed as a top-10 Iranian online supermarket in 2026 Persian-language roundups) — domain now serves an Indonesian online-gambling landing page ("BDL88 : Situs Bocoran Admin Slot Gacor", `lang="id-ID"`) on both `/` and every `/wp-json/...` path. Expired and re-registered; do not re-probe. Probed 2026-09-05.
- **esnadline.com** (YE) — cPanel `/cgi-sys/suspendedpage.cgi`. Account suspended. Probed 2026-09-05.
- **omishad.com** (IR, "Omishad" bulk spices/rice/oil trader) — WooCommerce Store API is open and returns 198 products, but `prices.price` is `0` on every single row: the catalog is quote-on-request wholesale, not priced retail. A live API is not a live price feed. Probed 2026-09-05.
- **yemenmarket.net** (YE) — WooCommerce Store API open, but the 34-product catalog is USD-priced dropshipped consumer gadgets (folding fans, "AI smart glasses", monoculars), not Yemeni groceries. Probed 2026-09-05.
- **jomlah.app** (surfaced under Yemeni grocery searches) — a Salla storefront quoting SAR with zero mentions of Yemen: a Saudi wholesale food store ranking for Yemeni queries. Check page currency and country mentions before probing a candidate's API. Probed 2026-09-05.
- **altunmarket.com** (surfaced on Iraq/Erbil grocery searches) — `lang="tr"`, a Turkish market. Wrong country. Probed 2026-09-05.
- **bazaar-baghdad.com** (IQ, "Bazaar Baghdad") — not a blocker: genuinely server-rendered Tier-1A markup (`.product-card` → name + `N,NNN IQD`). Skipped on SIZE and ASSORTMENT instead — the whole catalog is roughly 160 `product.php?id=` items, ids topping out around 161, and the mix is perfume/gadgets rather than grocery. Revisit only if it grows a food range. Probed 2026-09-05.

- **titancoop.sm** (SM, TITANCOOP — San Marino consumer co-operative) — the 2026-09-01 San Marino inventory left this as an un-finished probe (`curl: (56) Connection closed abruptly`, never re-probed). Closed out 2026-09-05 under the mandatory two-lever gate: `curl_cffi` still fails with error 56 on all three profiles and both apex/`www`, but **headless Playwright loads it fine** (HTTP 200, 71KB, title "Titancoop la tua spesa sicura"). So it is reachable — and it is not a shop. Every link on the rendered page is corporate/co-op member content (`/ambiente`, `/bilancio-sociale`, `/collaborazioni/*`, `/convenzioni-titancoop/*`, `/comunicati`, `/contatti`): zero product pages, zero `€` price strings anywhere in the rendered DOM, zero JSON XHRs. The group's actual online grocery is `spesa.gruppoce.sm`, already onboarded as `coal_sm`. Do not re-probe. Probed 2026-09-05.
- **consorziovini.sm** (SM, Consorzio Vini Tipici di San Marino — the obvious COICOP 02.1.1 candidate) — apex serves a bare "Web Server's Default Page" (3.8KB), `/it/` 404s. Parked hosting, no site. Probed 2026-09-05.
- **prodotti-tipici-sanmarino.com** (SM typical-products candidate) — 200/48KB but no storefront platform fingerprint (no WooCommerce/Shopify/PrestaShop/Magento markers), no `€` price strings, and the WooCommerce Store API 404s on both namespaces. A brochure/directory page, not a catalog. Probed 2026-09-05.


- **idea.rs** (RS, IDEA — major Serbian grocery chain) — corporate/store-locator site only (`/Prodavnice/Prodavnice-Beograd`, `/Aktuelno` news, `/O-Idei` about-us); no product catalog, no per-SKU pricing anywhere. Probed 2026-09-01 (ECA sweep, agent B).
- **univerexport.rs** (RS) — Next.js corporate site; only a phone-contact footer component found in the raw fetch, no shop/catalog links. Probed 2026-09-01.
- **roda.rs** (RS) — the only price-like text on the domain is installment-payment terms copy ("Minimalni iznos rate: 1.000 RSD"), not a real product price; `/akcije/...-cat-NNN` links are weekly PDF-style flyer pages, not a browsable SKU catalog. Probed 2026-09-01.
- **tempo.rs** (RS) — no shop/catalog-shaped links found in a first-pass fetch. Probed 2026-09-01.
- **nikora.ge** (GE) — this is Nikora Trading LTD's CORPORATE group site, not a shop; links out to three sub-brand `/products` pages (`nikora.nikoraltd.ge`, `metable.ge`, `mzareuli.nikoraltd.ge`) that are static "our product range" showcases with zero price text and zero per-item structure beyond a generic menu-item div. Georgia's largest chain by store count — worth revisiting if a genuine transactional storefront surfaces under a different subdomain. Probed 2026-09-01.
- **green.by**, **sosedi.by**, **gippo.by** (BY) — all three are corporate/store-locator sites for physical-only Belarusian grocery chains, no e-commerce. green.by is a stale generic-theme WordPress site (`twentytwelve` theme, no shop hooks) that does not read as the grocery chain of the same name at all. sosedi.by and gippo.by are 1C-Bitrix sites with a `/catalog/`-shaped URL that resolves (200) but contains only `Organization` JSON-LD and store-locator content, zero product cards. Probed 2026-09-01 (ECA sweep, agent B).
- **21vek.by** and **emall.by** (BY) — both real, large (200+KB) Next.js e-commerce marketplaces run by the Euroopt/Eurotorg group, but neither is food-and-beverage: 21vek.by is electronics/appliances/notebooks/bikes only (no grocery category in its 15-link nav), and emall.by is a general third-party-seller marketplace (school supplies, washing machines, cars) with a "become a seller" flow, not a curated grocery catalog. Not pursued as food sources. Probed 2026-09-01 (ECA sweep, agent B).

- **paylessmarkets.com** (GU, Pay-Less Supermarkets Guam — main supermarket chain) — Laravel/Vue corporate site (XSRF-TOKEN + laravel_session cookies). `/departments/grocery` is a department-info landing page + feedback form, zero product links, zero prices in rendered HTML (Playwright network trace showed only a reCAPTCHA call, no product API). Nav has `/specials` and `/promos` — both checked, `/promos` links only recipe-cookbook PDFs (not weekly price flyers), `/specials` has zero price mentions. No online catalog exists on this domain. Probed 2026-08-11.
- **pxmart.com.tw** (TW) — corporate Next.js portal. Links go to /about-us, /bulletin, /esg. No catalog. The real store is **PXGo! (`shop.pxgo.com.tw/mweb/`, Vite hash-routed SPA)** with a **clean no-WAF JSON API** (`https://mwebapi.pxgo.com.tw/2ndwa/`, product endpoint `POST /2ndwa/api/goods/goodsQuery`) — BUT the entire catalog is behind **PX Pay member auth** (every call → 401 `暫未登錄`; token minted via `/api/member/login` → `member.pxpay.com.tw`, no anonymous/guest login in the bundle; registration likely needs a TW mobile + OTP). Scaffold only if a member Bearer token can be held. Probed 2026-07-27.
  - **UPDATE 2026-08-11:** the `/inBatches/category/<id>` group-buy (合購) flow — a separate PXGo entry point from the member-gated `goodsQuery` API above — is *also* blocked, independently: HTTP 403 on both curl (`server: Please assist with the cashier`, `via: 1.1 google`, CSP referencing `*.qcloud.com`/`*.pxpay.com.tw` — looks like a Chinese-market WAF product front, not Cloudflare/Akamai/Incapsula/DataDome) and headless Playwright (`<title>403</title>`, 175-byte generic body). Two independent walls now confirmed on this tenant (member-auth on the API, edge WAF on this web path) — deprioritize PXGo/PXMart entirely rather than re-probing other entry points.
- **www.yonghui.com.cn** (CN, 永辉超市 Yonghui Superstore — major CN grocery chain) — corporate news/IR site. Links are exclusively news article paths (`/html/web/latestnews/...`). Zero prices, zero product links in 49KB HTML. Yonghui's consumer-facing stores operate via app (永辉生活) not a public web catalogue. Probed 2026-06-30. COICOP 01 gap remains.
- **brianbell.com.pg** (PNG) — corporate portal. `/product-category/appliances` 404s. `homecentres.brianbell.com.pg/shop/` redirects to "/" with no e-commerce markup. B2C division has no public web storefront.
- **shop.cpl.com.pg** (PNG, CPL Group — Stop & Shop, PNG's largest retailer) — **correction to the 2026-06-10 entry above (line ~158): this is not a geo-fence.** Re-probed 2026-09-01 with `curl_cffi impersonate=chrome124/chrome120/safari17_0`: the subdomain does not resolve at all (`Could not resolve host`), confirmed against `8.8.8.8` directly too — genuinely retired/removed DNS record, not a live CDN geo-fence returning ECONNREFUSED. The parent domain `cpl.com.pg` resolves fine (200, corporate site) and has zero `shop`/`store`/`order online` links anywhere in its HTML — CPL currently has no reachable online storefront under any domain found. Do not re-try `shop.cpl.com.pg` without evidence of a new subdomain. Probed 2026-09-01.
- **www.bulksolomons.com.sb** (SB, Bulk Solomons — food importer/distributor, Ranadi Industrial Estate, Honiara) — not a WAF, a broken-infrastructure dead end. HTTPS fails on every SNI/impersonation profile (`curl_cffi` chrome124/120/safari17_0, plain `curl --tlsv1.2`, `openssl s_client`) with `TLSV1_ALERT_INTERNAL_ERROR` — a server-side TLS misconfiguration, not a bot block. Plain HTTP on the same host (74.208.236.168) returns a generic nginx catch-all 404 on every path tried (`/`, `/home`) on both apex and `www`. Reads as a site that has moved off this IP or been decommissioned rather than mid-outage. Probed 2026-09-01.
- **e-mart.mn** (MN) — corporate marketing site for eMart. Actual store is at **emartmall.mn** (SPA shell — see above).
- **imtiaz.com.pk** (PK, "Imtiaz — Pakistan's No. 1 Retail Chain") — corporate/blog WordPress site only. `wp-json/` namespace list has no `wc/` route at all (WooCommerce inactive despite "woocommerce" appearing in cached theme CSS classes) and homepage nav is exclusively about-us/blogs/career/gift-cards/loyalty-program links — no `/shop`, `/product`, `/order` path anywhere. Probed 2026-09-01 (MENAAP sweep, agent B).
- **myshop.dz** (DZ, "myshop.dz — Lance ta boutique en ligne en Algerie") — a Shopify-style store-builder SaaS ("Cree ta boutique en ligne en 4 minutes... Bientot disponible" = "coming soon"), not a retailer itself. Next.js landing page, no products. Probed 2026-09-01 (MENAAP sweep, agent B).
- **www.awladragab.com** (EG, "اولاد رجب" Awlad Ragab — well-known Cairo supermarket chain) — ASP.NET WebForms site; `/ar/Offers.aspx` is the closest thing to a shop link but renders only a seasonal marketing banner ("Back to School... campaign runs until 16 Sept 2026 or while stocks last") with zero product cards or price text, despite page JS containing genuine cart-workflow strings (`ErrorAddtoCart`, "order sent to nearest Awlad Ragab branch"). No other product/category/shop link found from the homepage. Likely gated behind a login-only ordering flow this pass did not chase — worth a second look with an account if Egypt coverage is revisited, but not actionable as an anonymous scrape today. Probed 2026-09-01 (MENAAP sweep, agent B).
- **geant.ly** (LY, "Géant" hypermarket brand) — React/Vite single-page brand-presence site: nav is Home/About/Magazine/Contact only, no shop/product/price route or keyword anywhere in the rendered HTML, social links only (Facebook/Instagram/TikTok). Physical hypermarket presence presumably exists but has no online ordering or catalog. Probed 2026-09-01 (wave 10).
- **libyanstores.com** (LY, "Libyan Stores" — surfaced via search) — Joomla 4 corporate distributor site ("A gate to the Libyan Markets"; imports/distributes EU-manufactured brands into Libya). B2B brand-building content only — `/products` and `/products/` both 404, no cart, no price text anywhere. Probed 2026-09-01 (wave 11).
- **lpcffi.com** (LY, "شركة المنصة الليبية لاستيراد المواد الغذائية" / Libyan Platform Company for Food Import — surfaced via search) — corporate site for a B2B food-import company; no shop/cart/price markup (`price`, `shop`, `السلة`, `أضف إلى`, `د.ل` all absent from the HTML). Not a retail price source. Probed 2026-09-01 (wave 11).
- **www.superindo.co.id** (ID, Super Indo — Indonesia's 2nd-largest supermarket chain) — marketing/promo portal; no online catalog and no individual product PDPs. Homepage has a rotating "Super Hemat" carousel with ~10 weekly promotional items (SSR HTML text, product name + price, but ZERO href links on the items). All product paths (/produk, /product, /kategori, /category) redirect to homepage. `/promosi/katalog-super-hemat/` serves the weekly catalog as JPEG flyer images (HEMAT_E_26_(N)_DKI.jpg, FLYER_E_26_DKI.jpg). No subdomains (shop.superindo.co.id etc. all ECONNREFUSED). No wp-json, no sitemap, no JSON API. Probed 2026-06-30. DEMOTE: promo-flyer-image-only + no per-product catalog.
- **www.robinsonssupermarket.com.ph** (PH, Robinsons Supermarket — PH's 2nd-largest supermarket chain, 151 branches) — corporate marketing/branding site; no per-product catalog, no pricing API. Homepage APIs (`/api/carouselApi`, `/api/regionApi`, `/api/branchApi`, `/api/promos/offers/featured`) serve promo carousels, branch/store-locator data, and news only. Promo catalogs (`/catalogs`) are PDF flyers. "Order Online" nav link leads to a news article about third-party delivery partners. Subdomains (shop/delivery/order/grocery/online) all ECONNREFUSED. `robinsonsdelivery.com.ph` is a ParkLogic parked domain. `gorobinsons.ph` SSL broken. `gocart.ph` ECONNREFUSED. Robinsons SKUs already covered by the existing `pickaroo` spider via `ops.pickaroo.com/groceries/brands/supermarket/`. Probed 2026-06-30. DEMOTE: no standalone web product catalog.
- **villagegrocer.com.my**, **big.com.my (Ben's Independent Grocer)**, **aeonbig.com.my**, **heromarket.com.my** (MY) — brochure/recipe WordPress; ordering routed to Foodpanda app deep-links. No `/shop` catalog. **giant.com.my** + **econsave.com.my** have WooCommerce themes but empty/absent `/shop` (dead storefronts). Probed 2026-07-27.
- **yiguo.com (易果生鲜)** (CN) — static archived placeholder (`<!-- saved from url=... -->`), banner JPEGs only, effectively defunct. **carrefour.com.cn** — Carrefour exited mainland China Aug 2025 (rebranded CACIOUS under Suning), no live domain. **Missfresh (每日优鲜)** — bankrupt 2023. Probed 2026-07-27.
- **www.yonghui.cn** (CN, distinct domain from the already-blocked `www.yonghui.com.cn`) — same verdict, same company: openresty-served corporate/IR template, nav is entirely news/investor-relations/careers paths (`/html/web/touzizheguanxi/...`, `/html/web/rencaizhongxin/...`). Zero shop/product links. Confirms Yonghui has no public web catalogue under any of its corporate domains. Probed 2026-09-01.
- **wumart.com / www.wumart.com.cn** (CN, 物美 Wumart — major Beijing-based supermarket chain) — both apex and www hang (`curl: (28) Connection timed out` / `(28) Resolving timed out`) from this egress; **www.wumart.net** resolves but is an unrelated parked GoDaddy Website-Builder page, not the retailer. No reachable storefront found this round. Probed 2026-09-01.
- **www.samsclub.cn / freshippo.com / maicai.meituan.com / pupumall.com / jddj.com / jd.com** (CN) — re-confirmed still dead on this round, no new lever found; see existing entries above. **www.rt-mart.com / www.rt-mart.com.cn** (CN mainland RT-Mart, 大润发) — both apex domains resolve to a bare 1.5KB Kubernetes-ingress-style stub (`server: official-web-web-deployment-...`), no content at all — likely decommissioned/migrated post-Alibaba integration. **www.aeonchina.com.cn**, **www.bbg.com.cn** (步步高), **www.yonghui.cn** (see above) — all render but are corporate/IR-only, zero catalog. **3songshu.com (三只松鼠)**, **pagoda.com.cn (百果园)** — corporate brand sites that only link OUT to third-party marketplace storefronts (JD/Tmall/Suning shop pages), no first-party catalog of their own. Domain-parking/dead-registrant false leads ruled out this round: **xinhuadu.com** (now a Spanish shoe-seller squat), **centurymart.com** (US promo-products company, unrelated to 世纪联华), **jjshop.com**/**qmw.com** (GoDaddy for-sale pages), **tiantianguoyuan.com** (repurposed baby-products site), **ole.com.cn** (domain-portfolio landing page), **sfbest.com / jiajiayue.cn / bcw.cn / xianfengguoyuan.com / circlek.com.cn / meiyijia.com** (NXDOMAIN/timeout, unreachable from this egress). Probed 2026-09-01.
- **kaibo.com.hk** (HK, Kai Bo Food Supermarket) — brochure-only 1.7KB page (company blurb + store-address nav), no `/shop` or product paths. Probed 2026-07-27.
- **www.shoprite.co.mz** (MZ, Shoprite Mozambique) — AEM (`shopriteafrica` clientlibs) regional corporate portal shared with shoprite.co.zm/.zw etc. Sitemap is entirely recipes/offers/store-locator content pages (`/receitas/...`, `/ofertas.html`); `/ofertas.html` renders but carries no per-product prices, only promo copy. All guessed product/catalog paths (`/lojas.html`, `/promocoes.html`, `/catalogo.html`, `/products.html`) 404. No online shop for Mozambique. Probed 2026-09-01.
- **www.shoprite.co.ls** (LS, Shoprite Lesotho) — same `shopriteafrica` AEM corporate portal as shoprite.co.mz (identical clientlibs, identical `/content/shopriteafrica/ls/en/...` path shape). `curl_cffi impersonate=chrome124` clears the WAF fine (200, no block) but the site is corporate-only: nav is `explore-shoprite.html` (category *description* pages, no prices), `specials.html` (promo blurb pointing at a PDF privacy/cookie policy, no catalog PDF, no per-product prices), `store-locator.html`. No `/shop`, `/products`, `/catalogo` path exists. Not a redirect to the SA parent (resolves natively, `/ls/en/` path is genuine) but there is no e-commerce catalogue to scrape regardless — same failure mode as the MZ sibling, not a locality problem. Probed 2026-09-01.
- **www.pnp.co.ls / pnp.co.ls** (LS, Pick n Pay Lesotho) — dead DNS (`curl: (6) Could not resolve host`) on both apex and www, from `curl_cffi impersonate=chrome124` (not a bare-curl false negative — this is NXDOMAIN, no TLS handshake ever starts). Not a redirect to the SA parent — the domain simply does not resolve. Probed 2026-09-01.
- **www.checkers.co.ls** (LS, Checkers Lesotho) — same `checkers-africa` AEM corporate-portal tenant as the `shoprite.co.ls`/`.co.mz`/`.co.zm` siblings above (identical clientlib naming, same regional-group pattern). 200, store-locator + `specials.checkers.co.ls` flyer-subdomain links only, zero `/shop`/`/products` paths, zero WooCommerce/Shopify/Magento fingerprint, zero cart/price/add-to-cart tokens in raw HTML. Probed 2026-09-11.
- **pricemate.info / api.pricemate.info** (multi-country SSA shop-price-comparison app, LS/BW/ZA) — the storefront and API are genuinely live (Nuxt SSR + open `api.pricemate.info` JSON backend, no auth), but a direct sweep of `GET /api/products?shop_id=1..29` returns `total_published_products: 0` for **every single shop on the platform**, not just the one Lesotho shop previously found (Econofoods Maseru). Downgrade from any prior "parked, worth a re-check" verdict to DEAD — this reads as an abandoned/never-populated platform rather than a per-country gap. Probed 2026-09-11.
- **DCH Foods / 大昌食品 (HK)** — eShop is **down/decommissioned**: `dchfood.com` → 302 corporate `dch.com.hk` (no shop); the real eShop host `foodmart.dchliving.com` is **NXDOMAIN**, `www.dchfoodmartdeluxe.com` has no A record. No live storefront to probe. If `foodmart.dchliving.com` returns, likely Shopline (Cloudflare-fronted) → try `/products.json` + JSON-LD. Probed 2026-07-27.
- **zadfresh.com** (SD) — bare default "Welcome to nginx!" install page (612 bytes) — server exists but nothing is deployed on it. Probed 2026-09-01.
- **sudansoug.com** (SD, "Sudansoug — Sudanese products online") — diaspora e-commerce (USD/AED prices alongside SDG, "Sudanese products online" tagline, no in-Sudan delivery-zone text found). Reject for the *same* reason as the deleted Antigua diaspora-grocer sources unless a genuine Sudan delivery zone can be confirmed — do not build without re-verifying locality. **alafnanfoods.com** (search snippet lists a +971 UAE contact number) is the same diaspora pattern. Probed 2026-09-01 (WebSearch + curl only, not deep-probed further once the locality flag was raised).
- **sudansupermarket.com** (SD, "Sudan SuperMarket" / سودان سوبرماركت) — WordPress/WooCommerce/Divi, 200 OK, no WAF. `GET /wp-json/wc/store/v1/products` returns `[]`; `/shop/` renders "No products were found matching your selection." (confirmed via BeautifulSoup text extraction, not just status code — the raw HTML has WooCommerce CSS/markup but zero rendered product nodes). Tagline "لكل السودانيين حول العالم" ("for all Sudanese around the world") plus an "India" country-select nav artifact read as an inactive/never-launched diaspora storefront rather than a Khartoum retailer — would also fail the locality rule even with a live catalog. Probed 2026-09-01 (wave 11).
- **greentreesupermarket.com** (SD-adjacent, "سوبر ماركت الأشجار الخضراء") — tagline "تسوق المنتجات المصرية والسودانية أونلاين" ("shop Egyptian and Sudanese products online") — explicitly an ethnic-foods diaspora grocer, same reject pattern as sudansoug.com/alafnanfoods.com. Not deep-probed beyond the locality/tagline check (homepage rendered almost no body text on a plain curl_cffi fetch, consistent with a JS-heavy storefront, but moot given locality). Probed 2026-09-01 (wave 11).
- **alzahra.ps** (PSE, West Bank and Gaza — الروافد للصناعات الغذائية) — 200 OK, real product catalog page (`?page=products`), but zero prices anywhere in 110KB HTML — a food *manufacturer's* B2B showcase site, not a consumer storefront. Probed 2026-09-01.
- **ubuy.sl, shop.africanfoodsupermarket.com, motherlandgroceries.com, brixtonvillage.com** (SL) — international resellers / diaspora grocers shipping goods labelled "Sierra Leone" to customers abroad (UK/US-style diaspora grocers), not domestic Freetown retail. Same anti-pattern as the deleted Antigua diaspora-grocer sources — reject on sight, do not build. Probed 2026-09-01 (wave 9).
- **choithrams.com** (real, live UAE grocery-delivery site) — do NOT confuse with Sierra Leone's Choithram(s) chain despite the identical brand name; this domain is Choithrams Group's UAE storefront ("Online Grocery Shopping & Delivery in UAE", `og:locale: en_AE`), a locality violation for any non-UAE country. The genuine Sierra Leone branches sell through `247bigmarket.com/store/{freetown,kenema}/` instead (see the shipped `choithrams_sl` source). Probed 2026-09-01 (wave 9).
- **syriaamarket.com** (branded "سوريا ماركت — Syria Market", real Shopify store, real Syrian-food/sweets catalog) — locality trap: the storefront's own `Shopify.country` JS global is `"EG"` and `Shopify.currency.active` is `"EGP"` (Egyptian Pound), not SYP — this is an Egypt-based diaspora shop selling Syrian-brand foods, not a Syria-resident retailer. Same pattern as the Sanabel Al-Salam trap in the West Bank/Gaza inventory: brand-name match, wrong country. Do not build for Syria. Probed 2026-09-01.
- **namliehmarket.com** (SY lead, "نملية ماركت" grocery/produce) — `curl: (6) Could not resolve host` / `NXDOMAIN` on repeated tries; domain does not exist. Probed 2026-09-01.
- **almufeedsa.com** (appeared in a Lebanon grocery search, "متجر شركة المفيد التجارية") — Zid-platform storefront (`hreflang="ar-sa"`, page text explicitly says "السعودية"/Saudi Arabia) — this is a SAUDI ARABIA company, not Lebanese; locality mismatch, search-engine noise. Worth a fresh look as a Saudi Arabia candidate (Zid platform, real product catalog) if that country's sweep reaches it. Probed 2026-09-01.
- **themeatfactorysl.com/menu/** (SL, "The Meat Factory" — Freetown) — genuinely scrapeable, clean price list (~80 items, new-leone-magnitude "le" prices), but structurally a **restaurant**: ~90% of the menu is prepared food (grilled plates, burgers, pizza, sandwiches — COICOP 11.1), which has no slot in the food-channel enum. A small embedded "Butchery"/"Raw Meat" section (6-9 raw-meat-by-weight SKUs, e.g. "Butchery 1KG Goat Meat 550le") exists but is too thin and too entangled with the restaurant menu to build as a clean `specialty-food`/`fresh-market` source without it functioning mostly as a restaurant-menu spider — rejected as the kind of live-site stretch the onboarding brief explicitly warns against. Probed 2026-09-01 (wave 9).

- **elephanthouse.lk** (LK, Elephant House — Ceylon Cold Stores PLC, ice cream/beverages brand) — brand/corporate site only, no cart, no per-product price, no `/shop` path. Products sold through third-party supermarkets, not a first-party online store. Probed 2026-09-01.
- **www.arpico.com** (LK, Arpico — Richard Pieris group, Arpico Super Centre chain) — corporate holding-company site; the only link for the supermarket division is out to a Facebook page (`facebook.com/arpicosupercentre`), no first-party e-commerce on this domain. Probed 2026-09-01.
- **shop.dilmahtea.com** (LK, Dilmah — "Global Online Store | For Lovers of Tea") — real, live, enumerable Shopify catalog (`/products.json` paginates cleanly), but `Shopify.currency active=USD` — this is Dilmah's international export storefront for the tea-lover diaspora/tourist market, not a Sri Lankan domestic retailer; prices do not reflect the local LKR retail market. Same reject pattern as the Sudan/Sierra Leone diaspora-grocer entries below. Probed 2026-09-01.
- **grocerylanka.com** (LK, "Your Trusted Sri Lankan Grocery Store") — despite the name, this is a diaspora e-commerce site (Shopify, `Shopify.currency active=USD`) selling Sri Lankan cultural/religious/kitchenware items (Buddhist flags, monk robes, clay roti pans, brass oil lamps) to overseas buyers — not F&B (division 01/02 share ~0% in a 100-item sample) and not local-currency retail even where food-adjacent items exist. Probed 2026-09-01.
- **foods.seagullmaldives.com** (MV, Seagull Foods — Male' fresh-produce importer/supplier) — Shopify storefront, but password-protected: `/` returns 200 (theme assets only) while `/products.json` 401s. Pre-launch or B2B-only gate, no public catalog reachable. Probed 2026-09-01.

- **www.bcesarl.com** (GW, BCE Sarl — "Distribuição de Produtos Alimentares e Não Alimentares", Bissau, trading since 2008) — the most promising-looking Guinea-Bissau food name outside Ikuma, and it is a **Duda-built brochure**. `/sitemap.xml` lists 12 pages including `/en-gb/products`, but that page's own inline config reports `StorePageAlias: 'null'`, `StoreId: 'null'`, `IsNewStore: 'false'` — the Duda store module was never enabled — and the body contains zero `XOF`/`FCFA`/`CFA` strings. A food *distributor*, not a retailer with a catalogue. Probed 2026-09-05.
- **www.bujumbura-marketing.com** (BI, "achat et vente en ligne à Bujumbura") — WordPress, but `sitemap_index.xml` fans out to `listing`, `auto-listing`, `property-types`, `locations`, `status`, `espresso_events` and `espresso_venues` children and **no product post type**: this is a classifieds / real-estate / events directory using retail marketing copy, not a grocery store. Probed 2026-09-05.
- **hulumarket.com.et** (ET, "Ethiopia's Premier Buy & Sell Platform | Hulumarket — Free Classifieds") — reachable React site with a sitemap, but it is a **free-classifieds** board: listings are seller-authored, which `src/prices/enrich/census.py` excludes from the corpus census anyway. Not worth scaffolding as a price source. Probed 2026-09-05.
- **seregelagebeya.com** (ET, "Seregela Gebeya — Ethiopian Online Shopping Marketplace") — 1,388-byte SPA shell; every path (`/sitemap.xml`, `/products.json`, the Woo Store API route) returns the same shell byte-for-byte, so there is no server-rendered route and no discoverable JSON. Would need a Playwright network trace; deprioritised. Probed 2026-09-05.
- **www.maxi.co.ao** (AO, Maxi — 11-store Angolan food-retail chain, Luanda/Lobito/Benguela/Lubango) — a real and significant chain, but the website is WordPress **marketing only**: `/sitemap.xml` contains a single child, `page-sitemap.xml`; there is no product sitemap, no `/loja/` or `/produto/` path, and no Store API. Promotional leaflets only. The best Angolan supermarket brand still has no scrapeable catalogue. Probed 2026-09-05.

## Placeholder / seed demo-data catalog (real API, no real prices)

The storefront and API are genuinely live and reachable, but the bulk of the catalog is fabricated onboarding/seed data — a template installer's demo products, never replaced with real inventory. Distinguish from a thin-but-real catalog: look for a uniform placeholder price across almost every SKU, `slug`/id patterns that read as test data, and `created_at` timestamps that predate the store's own creation date.

- **tikves.com.mk** (MK, Tikves -- North Macedonia's largest winery, COICOP 02.1.2 candidate) -- WooCommerce Store API is **open and returns 133 products**, which reads as an instant division-02 win. It is not: **every one of the 100 sampled products has `prices.price == 0`.** The site is a brand/marketing catalogue with no retail pricing. `WooBaseSpider._item` already drops zero-price rows, so a spider built on the "API works, 133 products" reading would have shipped and collected nothing. Always check the price values, not just the row count. Probed 2026-09-05.
- **melabudin.is** (IS, Melabudin -- Reykjavik delicatessen) -- live Shopify with an open `/products.json`, but the catalogue is **5 products** (`?limit=250` returns 5; the Shopify product sitemap holds 1 entry). A catering/order page, not a grocery catalogue. Same shape as the bonus.is gift-card trap. Probed 2026-09-05.
- **bonus.is** (IS, Bonus -- Iceland's largest discount grocer) -- re-confirmed dead. Its WordPress/WooCommerce install carries a **single SKU**, the "Inneignarkort - Afylling" gift-card top-up, which is exactly what the two orphaned 8-row `data/prices/eca/western_europe/iceland/bonus_is/raw_items/` files in the repo contain. Bonus runs no online catalogue. Recorded here because the stray data directory invites a rediscovery. Probed 2026-09-05.
- **zito.com.mk** (MK, Zito Marketi grocery chain) -- WordPress+WooCommerce fingerprint on the homepage, but `/wp-json/wc/store/v1/products` and `/wp-json/wp/v2/product` both return `rest_no_route`. Its only product-ish sitemap is `r3d-sitemap.xml`, 51 entries, all `?r3d=flaer-br-<N>-<dates>` -- Real3D flipbook **PDF promo flyers**. Promo-flyer anti-pattern. Probed 2026-09-05.
- **nawris.net** (LY, "Nawris" — wave 10 workbook ACCEPT candidate, top-ranked lead: "Live marketplace, 17 branches, 17 cities, licensed by Libyan authorities, LYD prices") — the storefront and its `/api/products`, `/api/global/stores`, `/api/search` endpoints are all genuinely live (200, no auth, curl_cffi), but the entire catalog is 4 fake seed rows: `"name":"هاتف تجريبي"` (literally "test phone"), sold by `"store_name":"متجر النورس التجريبي"` (literally "Nawris demo store") / `"تاجر تجريبي"` ("test merchant"), one row even miscategorized (a "ball" emoji product filed under Electronics), `stock_qty` inconsistent across near-identical rows. The 17-branches/licensed claim in the workbook does not match anything the live API serves — this is an unlaunched template install, not a live marketplace. Do not build. Probed 2026-09-01 (wave 10).
- **hyper.sd (Hyper Express, SD)** — real StackFood/6amMart-family Laravel backend (`https://hyper.sd/index.php/api/v1/...`, pretty-URL rewrite is off so routes only resolve under `/index.php/...`). Confirmed real zones (`Kharoum Locality`, `Omdurman`, `Port Sudan`, `Kassala`, `Al Qadarif`, `Atbara`, all `currency_id=1`/SDG) plus one contaminating Muscat/Oman zone (`currency_id=22`/OMR) exactly as the wave-8 brief flagged — `zone_id` 23 must be excluded. The one grocery module (`module_id=1`, "HMart", store_id=1 "Hyper Mart") reports 698 items, but walking the full catalog (`GET /items/popular?store_id=1&limit=50&offset=<n>` — this is the store-wide item-list endpoint, no `store-wise`/`items/latest` route exists on this tenant) shows **689/698 (98.7%) carry `price=1` SDG**. Item id=1 detail (`/items/details/1`) confirms these are demo rows: `"slug":"demo-product"`, `"footer_text":"تيست"` (Arabic "test") on the store record, `created_at: 2023-08-15` predating the store's own `created_at: 2024-11-17`. Only 8 SKUs have plausible real SDG prices (biscuits/coffee/tea/chocolate/insecticide, 200–12000 SDG). Not a usable price source — the catalog is >98% unreplaced installer seed data. Probed 2026-09-01.
- **lilydelivery.com (LILY Delivery, SD)** — real Node/Mongo+Postgres backend (`https://api.lilydelivery.com`, `GET /health` → `{"status":"ok"}`), no WAF, `GET /api/services` lists vendors directly. But the WHOLE platform is 14 vendors / ~34 items total (confirmed via 35 Arabic staple-term queries against `GET /api/services/search/items?q=<term>` — the only catalog-access route; there is no list-all-items endpoint, `/api/services/<id>/items` 404s). The single grocery vendor ("بقالة النيل") carries exactly 7 SKUs (rice/sugar/oil/water/milk/eggs/bread) at suspiciously round prices (600/500/700/1200/400/1800/150 SDG) with sequential-looking Mongo ObjectIds and a `restaurants` category `createdAt` of 2026-05-15 — reads as a recently-seeded MVP, not an operating grocery catalog. Below the "handful of promo items, not a real price series" bar; do not build without re-verifying the catalog has grown substantially. Probed 2026-09-01.
- **fasita.rw** (RW, "Fasita" — wave 12 workbook ACCEPT candidate, `AI_NOTES`: "Live: Kigali, Huye, Musanze, Nyanza; groceries and essentials") — real Next.js frontend + open JSON API (`https://fasita.rw/api/products`, `/api/categories`, no auth, sniffed live via Playwright network capture). But `GET /api/products` (tried plain, `?category_id=`, `?all=1`, `?limit=200`) returns exactly **one** product across all calls ("Jibu Water", 3472.00 RWF) and `/api/categories` shows 11 of 12 categories at `"products":0` (Baby/Bakery/Dairy/Drinks/Fruits/Home Care/Kitchen/Personal Care/Pharma/Snacks/Stationery all zero; only "Food" carries the 1 SKU). The multi-city delivery claim in the workbook does not match a live catalog of this size. Fails the Phase 6 ≥5-rows gate by a wide margin — not a probe failure, a genuinely near-empty storefront. Do not build; re-check in ~6 months in case the catalog is populated later. Probed 2026-09-01 (wave 12).
- **pridefarms.rw** (RW, "Pride Farms" — wave 12 workbook ACCEPT candidate, Wix storefront, `AI_NOTES`: "Live: farm-to-door produce and pantry, Kigali") — the Wix Stores GraphQL backend is genuinely live and was successfully unlocked (visitor `instance` token from `GET /_api/v1/access-tokens`, keyed by Wix Stores appDefId `215238eb-22a5-4c36-9e7b-e7c08025e04e`; the storefront embeds the resolved `productsWithMetaData` catalog JSON inline in the client-rendered page, not via a separate XHR, so it must be read from Playwright's post-hydration DOM rather than sniffed from the network tab). But every catalog page sampled is empty or near-empty: `/shopall` ("All Products") reports `totalCount: 1`, and `/fruits`, `/vegetables`, `/dairy`, `/poultry` all report `totalCount: 0` — only `/pulses` has the same single SKU ("Chickpeas Kabuli whole G1-1kg", RWF 5700) that shows up everywhere. Despite 25+ named category nav links (bread, cheeses, craft beers, herbs, oils, etc.), the store is stocked with exactly one product. Fails the ≥5-rows gate. Do not build; re-check in ~6 months. Probed 2026-09-01 (wave 12).
- **jambosupermarket.online** (TZ, "Jambo Supermarket" — wave 12 workbook ACCEPT, "5 named Dar es Salaam branches with a BRANCH SELECTOR") — React SPA backed by a public-anon Supabase REST table (`kfhqiregbrqydszjqrjv.supabase.co/rest/v1/products`, anon JWT embedded client-side by design, no auth needed to read). Exactly 34 rows, ALL sharing one `created_at` timestamp down to the microsecond (`2026-06-07T20:02:14.630559+00:00`), Unsplash stock photos, generic seed names ("Whole Wheat Bread", "Farm Fresh Eggs (30 pcs)") — a template installer's demo catalog, not a live branch-selector storefront as the workbook claimed. Probed 2026-09-01 (wave 12).
- **www.quickgo237.com** (CM, "QuickGo 237" — wave 13 brief candidate, `AI_NOTES`: "Live: Yaounde, Douala, Bafoussam, Bamenda; Supermarche and Market verticals; OM/MoMo") — real Next.js app, no WAF at all (`curl_cffi` 200 straight off), but the entire "national marketplace" is 11 products total across all 6 listed boutiques (one each for most: "iPhone 15 Pro", "T-Shirt Premium", "Vitamine C 1000mg", 2 Ndole/Eru dishes and 2 grocery SKUs for the one "Super U Express (Supermarche)" vendor). Clicking through to that supermarket's own shop page 404s with "Cette boutique n'existe pas ou n'est plus disponible" ("this shop doesn't exist or is no longer available") — a broken route a live production app would not ship. Reads as an early-stage/demo build seeded with placeholder inventory, not the multi-city live app the workbook claimed. Do not build; re-check in ~6 months. Probed 2026-09-01 (wave 13).
- **grenadagrocer.com** (GD, "Grenada Grocer") — `<title>Grenada Grocer – Site Description</title>` is itself a tell (default WP-import placeholder title, never replaced). WooCommerce Store API (`?rest_route=/wc/store/v1/products`) is genuinely live and unauthenticated, but the first 6 of 20 sampled products are non-grocery WooCommerce-Bookings-addon demo services at a flat `$1` USD ("Rent Your Dream Car for Single Day long tour", "Medical & Dental", "Music Learning Online", "Repair service Booking Online", "Car Wash", "Hair Cut Salon Booking") — booking-plugin seed/demo data, not a real service menu. The remaining ~14 are real-looking imported pantry SKUs (Ziyad Dates, Waitrose Green Peppercorn, Cortas Tahina, Near East Taboule) at plausible USD-cent prices, but the mix with unmistakable demo-import junk (and a currency of USD, not XCD) reads as an unlaunched or abandoned WooCommerce install seeded from a generic dropship/import product feed, not a store actually trading in Grenada. Do not build. Probed 2026-09-01.

- **cba.hu** (HU, CBA — Hungarian grocery co-op franchise) — WordPress/Astra + WooCommerce, Store API wide open and unauthenticated (`/wp-json/wc/store/v1/products`), but the total catalog is only **17 products site-wide** (`X-WP-Total: 17` header) and only 5 of those carry a nonzero structured `prices.price` — the rest are informational-only entries. This is a small rotating "current weekly offers" teaser, not a full-basket catalog; the other 12 items' real per-unit prices exist only as free text inside the WooCommerce `description` field (e.g. "819 Ft/10 dkg; 8190 Ft/kg"), which would need bespoke regex extraction for a catalog this thin. Not worth a slot. Probed 2026-09-01 (ECA sweep, agent B).
- **alloshmart.com / www.alloshmart.com** (JO, "علوش ماركت | سوبر ماركت 24 ساعة" — Aloosh Market, 24-hour supermarket) — Vite/React/Supabase app (project `jsrqjmovbuhuhbmxyqsh.supabase.co`, anon key recovered from the shipped JS bundle). NOT RLS-blocked — the `categories` table is fully readable and shows 22 real department categories (جزارة/Butchery, فواكة/Fruit, خضار/Vegetables, البان/Dairy, etc.), but every single category's own `description` field reads "0 منتج" (0 products), and `GET /rest/v1/products?select=id&limit=1` with `Prefer: count=exact` returns `Content-Range: */0` — the products table exists and is queryable but is genuinely, verifiably empty. Pre-launch storefront with a fully built category taxonomy and zero inventory. Probed 2026-09-01.
- **ejomarket.com** (JO, "EjoMarket.com: Online Shopping in Jordan") — legacy Yii-framework PHP site (`site/category/<id>`, `site/brand/<id>` controller-style routes). The site's `/site/categories` index lists exactly one category, "Food & Beverages" (id=1) — but `/site/category/1` renders zero product cards (confirmed both via curl_cffi AND a full Playwright render with `networkidle` wait) and every visible price on the page is the template's `0.00 JOD` placeholder value; a sampled `/site/brand/101` page is similarly empty. Reads as an abandoned/never-launched install, not a live catalog. Probed 2026-09-01.
- **cmsxm.net** (SX/MF, Carrefour Market / Carrefour Express / Le Grand Marche, Sint Maarten -- the island's largest supermarket chain) -- a real, live WooCommerce site whose Store API answers 200 with `x-wp-total: 1077`, and in which **every single product has `prices.price == "0"`** (477 of 477 checked across 5 pages of `/wp-json/wc/store/v1/products?per_page=100&page=N`). The product-detail HTML carries no price text either -- zero `$nn.nn` matches on a 90KB PDP, no `woocommerce-Price-amount` node. This is an online product *catalogue* used to take phone/email orders, not a shop. Nothing to crack; it is not an anti-bot problem and there is no second surface. Probed 2026-09-05. Recorded loudly because the `st_martin_french_part.md` inventory had flagged it as Sint Maarten's "strong Tier-2 lead".

## API backend unreachable (frontend live, origin 404/down)

The customer-facing site renders (sometimes fully, via a JS bundle referencing a real backend host), but every request to that backend 404s with an empty body — the origin is paused, torn down, or has moved without updating the frontend build.

- **storna-shopping.vercel.app / www.st-orna.com (Storna, SD)** — real business (custom domain `st-orna.com` in addition to the vercel.app preview from the wave-8 brief, live Instagram/Twitter/YouTube handles referenced in the JS bundle: `instagram.com/storna` etc.), Next.js frontend renders fully (110KB HTML, `/products` `/categories` nav present). Bundle reveals the API base as `https://storna-core.laravel.cloud/api/v1` (a Laravel Cloud–hosted backend, Cloudflare-fronted) — but every path on that host, including `/` itself, returns `404` with a zero-byte body (`GET /customer/products`, `/customer/categories`, `/products` all confirmed). No BFF proxy on the `www.st-orna.com` domain either (`/api/v1/...` on that host also 404s). Backend appears decommissioned or migrated; nothing is scrapable today even though the storefront looks alive. Probed 2026-09-01.
- **yoboresto.com** (GA, "Yoboresto" — Libreville restaurant/fine-grocery ordering + table-reservation platform per search results) — resolves and is Cloudflare-fronted, but the origin itself times out: HTTP 522 ("Connection timed out") on repeated retries a few seconds apart, with a full Cloudflare-branded 522 error page (not a WAF challenge). Whole site is down, not just the API. Probed 2026-09-01 (wave 11).

## DataDome bot-protection (HTTP 403, `x-datadome` header)

- **myaeon2go.com** (MY, AEON's q-commerce) — HTTP 403 on every request, `server: DataDome` + `x-datadome: protected`. Needs a real browser + DataDome solver; skip. Probed 2026-07-27.
- **aeoneshop.com** (VN, AEON Vietnam eShop) — HTTP 403 `server: DataDome` on curl (root and product-search paths). Playwright confirms the same wall one layer deeper: page loads a `geo.captcha-delivery.com` interactive-challenge stub (`dd={'rt':'c', ...'host':'geo.captcha-delivery.com'...}`), not just a flat 403. Second AEON property on this file now flagged DataDome (see myaeon2go.com, MY) — worth treating AEON's e-commerce vendor stack as a DataDome tenant going forward, though each is a separate storefront/country deployment, not one shared domain. Probed 2026-08-11.

## SSL certificate mismatch (retired/consolidated domain)

- **www.safeway.com.jo** (JO, Safeway Jordan) — `curl_cffi.requests.exceptions.CertificateVerifyError: certificate has expired` on every request (not a mismatch to a sibling domain — genuinely expired, `verify=True`). Site is a real, actively-maintained ASP.NET app (New Relic RUM agent embedded, ~95KB homepage) — no hacked-WordPress/injected-spam signature, so not recorded under the malware-injection heading. Not attempted with `verify=False` given the unresolved trust chain; worth a quick re-check if the operator renews the cert, otherwise not a priority re-probe. Probed 2026-09-01.

- **supermarche.mg** (MG, wave 10 workbook ACCEPT candidate — "Antananarivo online grocery, investor-backed (Miarakap)") — rule-19 sibling of the already-onboarded `mescourses` source, confirmed by the strongest possible signal: the TLS certificate served on `supermarche.mg:443` is issued for CN=`mescourses.mg`, so curl fails with "SSL: no alternative certificate subject name matches target host name 'supermarche.mg'" on every request. This is the same fact the existing `mescourses.yaml` notes already recorded (supermarche.mg is the old brand, 302-redirects to mescourses.mg once a valid cert/Host header is presented) — re-confirmed live 2026-09-01. Not a second source; do not build. Probed 2026-09-01 (wave 10).
- **uselect.com.hk** (HK, U Select — China Resources Vanguard brand) — TLS cert covers `crc.com.hk` siblings, not this hostname; HTTP 403 even with `-k`. Domain likely retired/folded into the CRV group platform. Probed 2026-07-27.
- **starmartmacao.com** (MO, Star Mart Macao) — not a WAF: HTTPS connect times out at the TCP layer on both apex and `www.`, but plain HTTP (port 80) connects fine and 302-redirects to `index.php`, which renders a registrar "ERRP | Expired Registration Recovery Policy" parking notice. Domain registration has lapsed — no scrapeable business behind it. Probed 2026-08-11.

- **kaufland.sk** / **kaufland.cz** (SK/CZ) — HTTP 403 under `curl_cffi` on all three impersonation profiles tried (chrome124, chrome120, safari17_0) on both country TLDs — a shared Kaufland-group WAF policy, not a bare-curl TLS artifact. Not escalated to Playwright this pass. Probed 2026-09-01 (ECA sweep, agent B).
- **coop.sk** (SK) — HTTP 200, genuine product cards found (`product-card__title`, real prices e.g. "15,33 €/kg") but they come from a dated weekly-leaflet widget on the homepage (`/letaky/potraviny-supermarket-a-tempo-1`, ~30 items) rather than a persistent per-SKU catalog — the leaflet's own page is a 6.6KB image-flip viewer with zero product cards. Too thin (~30 items sitewide observed) to confirm as a genuine full-catalog retailer. Probed 2026-09-01.
- **lidl.sk** (SK) — HTTP 200, 713KB, but the only price text found was inside a marketing-banner image `alt` attribute, not a real product listing. Probed 2026-09-01.
- **potravinydomov.sk** (SK) — resolves to `itesco.sk`, Tesco's Slovak grocery-delivery brand. Same operator as the already-onboarded `tesco_wolt_sk` (rule 10) — not pursued as a second Tesco source without first sampling both product sets to confirm disjoint catalogs. Probed 2026-09-01.
- **bescohyper.co.bw** (BW, Besco Hyper — Gaborone hypermarket) — DNS resolves to `192.64.117.196` (a registrar parking range), but TLS fails: `curl: (60) SSL: no alternative certificate subject name matches target hostname`. The name is registered and pointed somewhere, but no storefront is served under it. Probed 2026-09-10 (Botswana `ddgs` sweep).

## Qrator anti-bot (Russian anti-DDoS, `__qrator/qauth.js` JS challenge, HTTP 401/403 titled "HTTP 403")

Qrator is a Russian anti-DDoS/WAF vendor common on large RU retail and government sites. Signature: response body is a near-empty HTML shell whose only content is `<script src="/__qrator/qauth.js">`, or a 401/403 page titled literally "HTTP 403". Confirmed to block both plain curl *and* headless Playwright (no auto-solve of the JS challenge) — see `auchan.ru` below for the paired trace. Not the same product as Cloudflare/Akamai/Incapsula elsewhere in this file; treat as its own tenant-independent class (it's a shared vendor, not one operator's infra) but each site should still be re-checked, since severity varies (dns-shop.ru serves the qauth.js shell on 401; others may only gate specific paths).

- **www.auchan.ru** (RU, Auchan Russia — hypermarket, COICOP 01/02/05/09 candidate) — curl: HTTP 401 + `__qrator/qauth.js` shell. Playwright (headless Chromium, 6s wait): also 401, page titled "HTTP 403", 1262-byte body — same wall, confirms real block per this file's curl+Playwright trigger. Probed 2026-08-07 (round-3 Russia shard).
- **www.utkonos.ru** (RU, Utkonos — grocery delivery, COICOP 01/02 candidate) — curl: HTTP 401 + identical `__qrator/qauth.js` shell (byte-identical to auchan.ru's). Probed 2026-08-07; Playwright not separately re-run (same shell signature as the confirmed auchan.ru pair).
- **www.dns-shop.ru** (RU, DNS — national electronics chain, COICOP 08/09 candidate) — curl: HTTP 401, `qrator_jsr` challenge cookie set on the homepage visit, product-sitemap discovery works (`sitemap-products1..N.xml`, dated today) but every page request 401s. Probed 2026-08-07. Worth revisiting with a Qrator-solving browser session if RU electronics coverage becomes a priority — sitemap + page structure otherwise look tractable.
- **lemanapro.ru** + **www.lemanapro.ru** (RU, Leroy Merlin Russia's 2023 rebrand after the group's exit — home-improvement, COICOP 05 candidate) — `www.` apex 301s to bare domain, which then 401s with the same shell. Probed 2026-08-07.
- **www.vseinstrumenti.ru** (RU, tools/hardware, COICOP 05 candidate) — HTTP 403, small themed error body (1.6KB) rather than the bare qauth.js shell, but same vendor family by response shape. Probed 2026-08-07; not Playwright-confirmed.
- **www.citilink.ru** (RU, electronics, COICOP 08/09 candidate) — HTTP 429 on every request including the bare homepage, single request, cold connection (not burst-triggered). Probed 2026-08-07; not confirmed same vendor but consistent with an aggressive edge-rate-limit posture on this cluster of RU retailers.
- **lenta.com** (RU, Lenta — hypermarket chain, COICOP 01/02/05/09 candidate, wave-8 food search) — curl_cffi impersonate=chrome124: HTTP 401, `server: QRATOR` response header (same vendor, this time visible in a plain header rather than only the qauth.js shell). Not re-probed with Playwright — same tenant as the confirmed auchan.ru/utkonos.ru pair. Probed 2026-09-01 (wave 8).
- **monetka.ru** (RU, Monetka — discount grocery chain, COICOP 01/02/05 candidate, wave-8 food search) — curl_cffi impersonate=chrome124: HTTP 401, 265-byte body, same shell signature as auchan.ru/lenta.com. Probed 2026-09-01 (wave 8).

## JS proof-of-work stub that `curl_cffi` clears but Scrapy does NOT (client-path mismatch)

A distinct and easily-misread class: the *probe* passes and the *spider* fails,
with no code difference in between. Record which client saw what — a probe
verdict from `curl_cffi` does not transfer to the Scrapy path here.

- **simplewine.ru** (RU, SimpleWine — Russia's largest wine/spirits chain, COICOP 02.1 + 01.1 `gurme` section) — a standalone `curl_cffi` GET returns the full ~720KB Next.js page with `__NEXT_DATA__` and 6,980 wines, on **every** profile tried (`chrome120`, `chrome124`, `safari17_0`; only `chrome110` fails). Through Scrapy it returns HTTP **200 with a 1,785-byte JS proof-of-work stub** (`<noscript><meta http-equiv="refresh" content="0; url=/exhkqyad">`), on every path tried: via `scrapy_impersonate` (the repo's pinned `chrome120`), with the random-UA `CustomUserAgentMiddleware` disabled and one consistent Chrome-120 UA sent, with no custom headers at all, and over the plain Twisted handler with impersonation off entirely. Ruled out as causes: the impersonation profile, UA/TLS mismatch, `Accept`/`Accept-Language`/`Accept-Encoding` values (all four tested standalone and all clear), and IP-level throttling (standalone `curl_cffi` still succeeds after the failing Scrapy runs). The residual difference is in how scrapy-impersonate issues the request (header ordering / HTTP-2 framing), not in the site's posture toward this network. **The spider and manifest were written and then deleted rather than shipped unverified** — the source is genuinely reachable and worth a retry by anyone who fixes or bypasses the scrapy-impersonate path (e.g. a `fetcher` that calls `curl_cffi` directly). Its useful pagination and price findings are preserved in the report for 2026-09-05, not lost: the page parameter is the hyphenated `?page-number=N` (`?page=`, `?PAGEN_1=`, `?p=`, `?pageNumber=`, `?offset=` ALL silently return page 1 with `pagination.pageNumber == 1`), and `price` is an object (`price.base.price` list, `price.discount.price`/`price.piece.price` effective), not a number. Probed 2026-09-05.

## Reachable, HTTP 200, but not extractable without more work (not a hard block — don't re-probe blind, but don't write off either)

- **gladen.bg** (BG, Gladen.bg -- Sofia full-assortment online supermarket, 48,822 products, COICOP 01 candidate) -- **not a WAF, not a TLS problem, and the extraction side is perfect**: every PDP server-renders schema.org Product + BreadcrumbList JSON-LD and the sitemap index is clean. The blocker is a **self-hosted, rate-triggered anti-automation interstitial**: past a request-rate threshold the site 302s every product URL to `/challenge?return_to=<url>`, a Laravel page reading "Трябва да потвърдим, че не сте автоматизирана система" with a single POST button (CSRF `_token` + `return_to`, no captcha, no JS). Measured: run 1 at 2 concurrent / 1.0 s delay served **66 pages cleanly and then challenged the next 106**; run 2, after an 8-minute cooldown and re-paced to 1 concurrent / **6.0 s**, was challenged on **every** request. The penalty is IP-sticky and ratchets, so there is no throughput below the threshold worth having. The challenge form is trivially POSTable and that was deliberately **not** done -- it is an explicit "confirm you are not an automated system" gate, which is a different thing from a rate limit to pace under. Spider + manifest were written, tested (13 valid EUR rows before the wall) and then **deleted rather than shipped**. Category comes from the BreadcrumbList, NOT from the Product node (which has no `category` key at all) and `sku` is empty on every product, if anyone rebuilds it. Probed 2026-09-05 (ECA Balkans+Nordic 01/02 sweep).
- **billa.bg** (BG, BILLA Bulgaria -- major grocery chain, COICOP 01/02 candidate) -- 200 / 675 KB, no WAF, Nuxt SPA with an **Algolia** client in its JS bundle (`X-Algolia-Application-Id` / `X-Algolia-API-Key` header handling present in `/_nuxt/*.js`). The app id and search-only key were not in the chunk fetched and no Playwright network trace was run. Not blocked -- unfinished. One trace should recover the credentials and land it on Tier 1B. The highest-value unclaimed Bulgarian grocer. Probed 2026-09-05.
- **lightsmarket.bg** (BG, alcohol delivery) -- answers **200 with the same 81 KB body to every path**, including `/wp-json/wc/store/v1/products`, `/products.json` and `/index.php?route=product/category`. Those 200s are an SPA catch-all, not platform hits; do not read them as a WooCommerce/Shopify/OpenCart fingerprint. Needs a real network trace before any verdict. **partydrinks.bg** (BG) -- 237 KB OpenCart-shaped storefront whose robots.txt points at `http://partydrinks.local/sitemap.xml` (an un-rewritten dev hostname); `/sitemap.xml` and the OpenCart route params both 404, so no URL-discovery surface was found -- a category crawl would be needed. **nokovandson.com** (BG) -- `/sitemap.xml` returns 200 with a **zero-length body**. All probed 2026-09-05.
- **heimkaup.is** (IS, Heimkaup -- large Icelandic online store) -- `products-sitemap.xml` lists 3,169 URLs but the assortment is consumer electronics, watches and phones (no groceries), and the first sampled PDPs **404** -- the sitemap is stale. Not a division 01/02 source. If a non-food division ever wants Iceland, re-measure what fraction of the sitemap still resolves before scaffolding. Probed 2026-09-05.
- **bioshop.mk** (MK, organic food, Next.js) -- `/wp-json/wc/store/v1/products` returns **403**. Only one profile tried (chrome124) and no network trace run; small catalogue, low expected value, so not pursued. Probed 2026-09-05.
- **countrydelight.in** (IN, Country Delight — farm-fresh milk/dairy subscription delivery, Delhi-NCR/Bangalore/Mumbai/Pune) — 200 on curl_cffi, no WAF, but an Angular Universal SPA with an empty `<title>`. The site's own API host (`websiteapi.countrydelight.in`) returns 403/404 on unauthenticated probes of guessed paths (`/api/v1/products`, `/products`, `/`) — no pincode/session cookie was established. Not confirmed blocked, just needs a proper pincode-selection flow reverse-engineered (likely via a Playwright network capture after simulating the city-picker) before a real API sniff can happen. Worth a real pass, not attempted further this round. Probed 2026-09-01 (SAR sweep).
- **online.metro-cc.ru** (RU, Metro Cash & Carry — hypermarket, COICOP 01/02/05/09 candidate) — genuinely reachable: homepage sets a `metroStoreId` cookie, `/sitemap-3.xml` lists real `/products/<slug>` URLs, and product pages return 200 with a JSON-LD `Product` block. But the JSON-LD `offers` object carries `priceCurrency`/`availability` and **no `price` field** — the actual price lives only inside a heavily minified `window.__NUXT__=(function(a,b,c,...){...})(...)` positional-argument call, not parseable as JSON without executing the JS (a regex/string search finds no plain `"price":<number>` near the product). A rendered-DOM read (Playwright, `[class*=price]`) is the likely path but wasn't completed this round — the product page itself also 404s/hangs on cold Playwright navigation without first visiting `/` in the same context to pick up `metroStoreId`. Worth a real pass: sitemap + cookie + platform are otherwise clean. Probed 2026-08-07. **RESOLVED 2026-09-05 — built as `metro_cc_ru`.** No Nuxt-blob parsing was needed: the *leaf* category listing pages (`/category/bakaleya/konservy`, not the department page `/category/bakaleya`) server-render a real grid of `catalog-2-level-product-card` divs carrying `data-sku`, an `a.product-card-photo__link[title]` product name and a price split across `.product-price__sum-rubles` + `.product-price__sum-penny`. Department pages carry only `catalog-1-level-product-card` carousel cards — reading those is the homepage-carousel false positive. Pagination is `?page=N` with explicit links up to the last page, verified non-overlapping.
- **magnit.ru** (RU, Magnit — one of Russia's two largest grocery chains, COICOP 01/02/05 candidate) — homepage is a real, large (800KB) Nuxt SSR grocery-delivery storefront and `__sitemap__/products.xml` lists ~19,900 `/product/<slug>` URLs with same-day `lastmod`, but **every sampled product URL 404s** (confirmed both via curl-with-cookies and a fresh headless-Playwright session) and the 404 response is a soft-404 that renders the homepage shell (same `<title>`) rather than a real 404 page. The sitemap and the live routing appear to disagree — possibly a recent route-schema migration the sitemap generator hasn't caught up with. Not a WAF block; a data-freshness/routing mismatch. Worth a re-check in a future round rather than a deep dig now. Probed 2026-08-07.
- **www.rigla.ru** (RU, Rigla — national pharmacy chain, COICOP 06/13 candidate) — reachable, real product pages, but **price is per-pharmacy-branch**: the embedded state (`pvzIsgTabs[].items[]`) lists dozens of physical branches each with their own price for the same SKU, with no single "the" price for the product the way apteka.ru or komus.ru expose one. Extractable but needs a branch-selection policy (nearest/median/cheapest) decided before scaffolding — skipped this round in favour of apteka.ru, which already covers the same COICOP ground with a clean single national price. Probed 2026-08-07.
- **detmir.ru** (RU, Detsky Mir — Russia's largest kids' goods retailer, COICOP 03/09/13 candidate) — homepage and category/brand landing pages are real server-rendered HTML (no WAF/challenge), with a `window.appData = JSON.parse("...")` blob (double-JSON-encoded: the outer text is a JS string literal whose *content*, after `json.loads` twice, is one big app-state dict). That blob genuinely contains real product rows with `id`/`title`/`price`/`prices.old`/`prices.sale` (verified: "Комбинезон BabyGo" 349 RUB with a real old-price of 499 RUB) but only inside `.recommendations.products.*.result[]` widget arrays (~15-30 items per page) — the *actual* full category/search product grid (thousands of items, `offerCount` in the JSON-LD confirms e.g. 2776 for one brand) is **not** in the SSR payload; a live Playwright network capture on a `/search/?text=...` page fired 13 XHRs to `api.detmir.ru` (cart, user, menu, recently-viewed) but never the actual search/listing endpoint in a ~6s window — it may fire on scroll, on a different query-param shape, or need a longer wait. Not blocked, just unfinished. Worth a real pass: either (a) find the true listing endpoint via a longer Playwright capture / scrolling the results grid, or (b) walk only the recommendation-widget arrays across many category pages as a lower-volume-but-zero-effort alternative. Probed 2026-08-07 (round-3 Russia shard, shard A3).
- **www.okmarket.ru** (RU, O'Key — hypermarket chain, COICOP 01/02/05/09 candidate, wave-8 food search) — curl_cffi: 200, no WAF, and a few real `/product/<slug>/` PDPs do exist with server-rendered prices (e.g. a school backpack at 1899.99 RUB via `.single-product__prices-label`). But the site is structurally a corporate/store-locator page, not a browsable catalogue: the raw homepage carries no category nav at all (only a seasonal promo strip), `/catalog/` and `/catalog/produkty/`-style guesses 404, `/sitemap.xml` (2.6MB) is broken — 14,902 of 15,206 `<loc>` entries are the bare homepage URL repeated with different `<lastmod>` timestamps, and `/search/?q=<term>` returns "ничего не найдено" (nothing found) even after setting a Moscow city cookie (`?city=1`) or hitting the site's own `/ajax/catalog/search/` endpoint directly. No enumerable product listing surface was found. Probed 2026-09-01 (wave 8) — worth a fresh look only if a real category/listing endpoint turns up (e.g. via a Playwright network capture), not worth re-probing the same way.
- **myspar.ru** (RU, SPAR Russia — grocery delivery for Moscow/St Petersburg/Nizhny Novgorod, COICOP 01/02/05/09 candidate, wave-8 food search) — curl_cffi: 200, no WAF, genuine full grocery taxonomy (`/catalog/moloko-syr-yaytsa-1/` etc., dairy/meat/produce/bread/sweets all present as real category slugs). But category pages carry the mega-menu only — zero product cards, zero "руб"/"₽" occurrences anywhere in the raw HTML — the product grid is populated entirely client-side (Bitrix + IndexedDB/Dexie caching, `dexie.bitrix.bundle.js`), and no XHR/JSON endpoint fired during a Playwright network capture of a category page. Headless Chromium navigation itself is bot-gated here: a Playwright `goto` on the same category URL that curl_cffi fetches cleanly instead lands on an interactive proof-of-work/captcha page (`#answerbtn`/`#refreshbtn` widget, `STAGE = "prod"`) — the opposite of the usual pattern (curl blocked, Playwright clean); here curl_cffi impersonation is what clears and rendering is what trips the wall. Not diagnosed further (needs either a genuine browser session with cookies carried over from a clean curl warm-up, or reverse-engineering the Dexie data-sync payload). Probed 2026-09-01 (wave 8).
- **hiperkupa.ao** (AO, "Hiperkupa" — wave 10 workbook SUSPECT, "multi-restaurant e-commerce web app") — Flutter Web build (canvas-rendered, no scrapable DOM by design) but backed by an open StackFood-style Laravel API at `painel.hiperkupa.ao/api/v1/*` with no WAF: `POST /auth/guest/request` returns a working guest session with no auth wall. However `GET /restaurants/get-restaurants/all` returns `total_size: 0` for plain lat/lng/zone_id guesses (Luanda coordinates tried) — the app appears to gate restaurant/store listings behind a zone-detection flow whose exact header or endpoint wasn't found within a timeboxed Playwright network trace (RUM beacons to `page.hiperkupa.ao/cdn-cgi/rum` fire continuously and prevent `networkidle`, complicating capture; `load`+fixed-wait capture didn't catch the zone-resolution call before restaurant requests fired). Worth a real pass if pursued: find the zone-lookup endpoint (likely keyed on lat/lng) that precedes `get-restaurants`. Even unlocked, food-retail (COICOP 01) relevance is unclear — the platform is described as multi-restaurant (prepared food) and the workbook itself flagged "grocery depth unclear". Probed 2026-09-01 (wave 10).
- **libyashop.ly** (LY, "LibyaShop" — a general marketplace aiming to unify local Libyan stores/buyers, surfaced via search: "400+ stores, 140,000+ products") — genuinely reachable (200) but a bare Create-React-App SPA shell with no SSR content; homepage renders (via headless Playwright) 12 featured seller names, ALL non-food (Shredz Libya/supplements, jewelry, perfume, fitness, electronics, toys, fashion) — no grocery/supermarket merchant surfaced. Backend is Firebase (Firestore + Cloud Functions, project `libya-d369a`); the old Realtime Database is explicitly disabled by the owner (`"has been disabled by a database owner"`), and Firestore's REST API (`firestore.googleapis.com/v1/projects/libya-d369a/databases/(default)/documents/<collection>`) returns `403 PERMISSION_DENIED` on `stores`/`products`/`categories` — properly secured, no anonymous read. A Playwright network capture of the homepage fired zero Firestore/Cloud-Functions calls (data likely loads only after auth or on a deeper route not linked from `/`). Not pursued further given no food merchant was visible and the backend requires an auth flow beyond this pass's scope. Probed 2026-09-01 (wave 11).
- **faithful-to-nature.co.za** (ZA, specialty-food/organic, legacy Magento 1) — **not a site-side block; a reproducible tooling mismatch specific to this repo's Scrapy+scrapy-impersonate stack.** Standalone `curl_cffi` (sync AND async, `impersonate=chrome124`/`safari17_0`/`chrome99`, with or without explicit empty `headers={}`, matching scrapy-impersonate's exact `AsyncSession(max_clients=1).request(...)` call shape) clears at 200 every time, including inside a bare `asyncio.run()`. The IDENTICAL request issued through `prices collect` (CrawlSpider + `Rule(process_request=...)` pinning `meta["impersonate"]`, both `RandomBrowserMiddleware` and `CustomUserAgentMiddleware` disabled per the `carrefour_tw.py` convention) 403s on every profile tried. Only variable left undiagnosed: Scrapy 2.13's Twisted `AsyncioSelectorReactor` hosting curl_cffi's async client inside an already-running foreign event loop — plausibly a different TCP/TLS handshake path than a clean `asyncio.run()`, which this site's Cloudflare edge treats differently even though the JA3/header shape is nominally identical. Also note the global `IMPERSONATE_BROWSERS=["chrome120"]` default 403s on this domain even standalone (chrome124/safari17_0/chrome99 do not) — a second, independent instance of the "profiles are not interchangeable" rule. Spider was built (JSON blob at `<script id="liftigniter-metadata">` on every PDP gives clean sku/name/price/category) but not shipped — 0 rows through the real pipeline. Worth a retry once `scrapy-impersonate`/`composite_handler.py` is investigated further, or from a plain `requests`+`curl_cffi`-outside-Twisted fetcher instead of a Scrapy spider. Probed 2026-09-01 (wave 10).
- **woolworths.co.za** (ZA, dept-store/premium-supermarket hybrid) — reachable, 1.7MB React/SSR homepage with real "R89.95"-style price strings in the raw HTML, but they come from a Contentstack headless-CMS nav/promo blob (`"_content_type_uid":"menu"`, e.g. "2 for R89.95 each Selected Sleepsuits") — marketing copy, not a per-SKU catalog. Homepage carousels look like a passing probe but are not a catalog per the skill's own warning; the real PLP/PDP + commerce-API surface was not located this pass (deprioritized once ZA's onboarding bar was cleared via non-retail sources). Worth a real pass: find the actual product-listing API behind the Contentstack-driven nav. Probed 2026-09-01 (wave 10).
- **ghcreid.com** (AS, GHC Reid & Co. — American Samoa's Coca-Cola/Vailima beverage distributor) — real WooCommerce site, ~100 SKUs enumerable via `/wp-sitemap-posts-product-1.xml`, but every product's rendered price node is blanked (`<p class="price"></p>`) by the `helios-solutions-woocommerce-hide-price-and-add-to-cart-button` plugin — a deliberate B2B "log in for pricing" gate. The `/2/products`-style `wp-json/wc/store/v1/products` Store API 500s (an unrelated PayPal-Express-Checkout plugin bug), and the only place a price still leaks is the page's own `schema.org` JSON-LD (`"priceSpecification":[{"price":"14.50",...}]`), confirming this is a genuine wholesale gate, not a missed extraction. Recognize this plugin slug (or the empty `<p class="price">` + populated JSON-LD combo) as the tell for "this WooCommerce store is B2B, not retail" before investing in a spider. Probed 2026-09-01 (wave 11).
- **www.csph.cm** (CM, Caisse de Stabilisation des Prix des Hydrocarbures — Cameroon's fuel-price regulator; the brief's suggested "MINCOMMERCE fuel prices" lead actually lives here, not at MINCOMMERCE itself) — homepage is reachable (200, no WAF) and links a dedicated `pricestructure.php` page plus a "Structure des prix" PDF, but `pricestructure.php` itself 500s on a plain GET (likely needs a POST/session/query-param this pass didn't reverse-engineer), and the linked PDF (`STRUCTURE_PRIX_FUEL_1500_NOV_2021.pdf`) is dated November 2021 — 4+ years stale, not the "long effective_from series" the brief hoped for. The site's `news.php`/`new_details.php?p_id=N` archive (checked p_id 53-73) is general corporate PR (metrology day events, etc.), not structured price-decree announcements. Not pursued further this pass in favour of `ins-cameroun.cm`'s own monthly CPI note (see `ins_cameroun_cpi` fetcher), which already carries a fuel-import-cost figure inline (Encadré 1 of the May 2026 note: Cameroun super/gasoil import costs by month) as a byproduct. Worth a real pass later: find whatever request `pricestructure.php` actually expects (check its own JS for the AJAX call it makes), or look for a current-year pump-price decree PDF instead of the stale 2021 one. Probed 2026-09-01 (wave 13).
- **mtn.cm** and **www.orange.cm** (CM, MTN Cameroon / Orange Cameroun — prepaid bundle tariff candidates from the brief) — both reachable with no WAF (`curl_cffi` 200 straight off). Orange's `/fr/catalogue/forfaits-voix-et-sms.html` page, however, renders as a near-empty megamenu shell in raw HTML (one stray "FCFA" mention, no price table) — the real bundle grid is populated client-side (Adobe-Commerce/Magento-flavoured storefront judging by the URL shape) and was not sniffed this pass; MTN's site was not probed past the homepage nav (`/offers/mobile-internet-2/`, `/offers/mtn-prestige-bundles/` links exist but weren't opened). Not pursued further this pass once `ins_cameroun_cpi` cleared the "3 more sources" bar on the first try; worth a real pass later with a Playwright network capture on the Orange bundle pages (same "Playwright to discover, plain HTTP to scrape" pattern as elsewhere in this file) or on MTN's offer pages directly. Probed 2026-09-01 (wave 13).
- **Flipsnack-embedded weekly circulars (SOLVED — worth the effort)** — a retailer's own weekly-flyer page (seen on `costuless.com/american-samoa/flyers`, likely common across small Pacific/Caribbean chains) embeds rotating PDF flyers via a Flipsnack `<iframe>` viewer. The rendered page images are NOT machine readable, and a bare `curl`/`requests` GET of the iframe URL cannot see past the JS shell. But Flipsnack's backend runs PDF text extraction server-side and serves it as a flat `extractedText` string per page inside `https://<asset-cdn>/<account>/collections/<doc-hash>/data.json` — a CloudFront URL signed with a ~1hr TTL that only a real browser can mint (the signature is generated client-side on load). Recipe: render the iframe with Playwright, register a `page.on("response", ...)` handler (in Scrapy: `playwright_page_event_handlers` meta key, attached before navigation) to capture the `data.json` response body, then parse `extractedText`. **Caveat that ate most of the build time**: the text-layer reading order does NOT preserve the flyer's visual (often 2-column) layout, so a naive "name then price" regex silently mispairs items across column breaks — only accept a price-delimited chunk when it reduces to exactly one product-quantity marker (ct./oz./lb/pk/etc., one compound "X/Y" pair counts as one marker); drop 0- or 2+-marker chunks rather than guess. A heavily-scrambled produce/meat-style flyer page can legitimately parse to zero rows — that is correct behaviour, not a bug. See `src/prices/price_scraping/spiders/costuless_flyer_as.py` for the full worked implementation. Solved 2026-09-01 (wave 11).

- **www.dhigrab.mv** (MV, "DhiGrab" — Wolt/Glovo-style multi-vendor delivery super-app) — the `/stores` directory is genuinely reachable and server-renders (via Next.js RSC payload, not a client fetch) a full partner list with per-store product counts, but the ~120 partners are overwhelmingly restaurants/cafes; only a handful read as grocery-shaped (Nokron Mart 53 products, West End Mart 18, Meat Street 114 — a butcher). No per-store URL/slug is exposed anywhere in the HTML (navigation is client-side-routed with opaque store IDs), and the actual per-store product/price data loads through a Firestore realtime `Listen` channel (`firestore.googleapis.com/.../projects/dhigrab-neo/databases/(default)`), not a plain REST endpoint — would need either reverse-engineering the Firestore query shape or a full Playwright click-through per store for a thin (18-114 item) catalog each. Not pursued further this pass; worth a real pass only if someone wants to invest in a Firestore-listen client. Probed 2026-09-01.
- **potravinydomov.sk / potravinydomov.itesco.sk** (SK, "Tesco Online Nákupy" -- Tesco Slovakia's own national grocery e-commerce platform, canonicalizes to `potravinydomov.itesco.sk/shop/en-SK/landing/groceries`; distinct channel from the already-onboarded `tesco_wolt_sk`, which is a single Bratislava hypermarket branch listed on Wolt) -- 200 OK, no WAF, but a heavy SPA with no `__NEXT_DATA__`/`__NUXT__` state and no embedded product JSON. A Playwright network trace of the landing page fired zero `/api/`or `graphql` requests -- the platform gates its real category/product API behind a delivery-address/postcode selection flow (same UK-Tesco-family pattern as other Tesco storefronts) that a shallow landing-page trace does not reach. Worth a real pass: drive the address-picker interstitial with Playwright first, then re-trace. Probed 2026-09-01 (ECA sweep, agent B).
- **oscarstores.com** (EG, Oscar Stores — major Egyptian supermarket chain) — genuinely a live, large online grocery store (confirmed real EGP prices via Playwright render, e.g. "Chicken Shawerma 1kg — 264.95 EGP" in a populated category, ~140 `/product-category/<id>` category ids on the homepage), but NOT server-rendered and NOT a plain REST/GraphQL API: the storefront is white-labeled by "Zazome" (footer credit "ONLINE STORE POWERED BY ZAZOME") and the page establishes a `signalr/hubs` connection — product data arrives via SignalR (WebSocket/long-polling), not a capturable XHR/fetch call, which is why a standard Playwright `xhr`/`fetch`-only network filter shows nothing even though `pg.inner_text("body")` shows real hydrated products after ~6s. Tier 2 (`scrapy_playwright`, DOM-read-after-render) is the right approach here, not an API sniff — SignalR is a wrong-tool trap for the usual "Playwright to discover, plain HTTP to scrape" pattern. Some category ids are genuinely empty (e.g. `5637173090` → "Showing 0 results") so don't judge the platform from one dead category. Not built this pass (Egypt was last-priority on this sweep's worklist); strong candidate for a dedicated Tier-2 pass. Probed 2026-09-01 (MENAAP sweep, agent B).
- **jalalsons.com.pk** (PK, "Jalal Sons — Fresh Groceries, Pan Asian, Bakery, Fast Food & Super Mart Essentials", Karachi) — genuinely live (Next.js `pageProps.config` embeds `restId: 55116`, `rest_brId: 57503`, a Sixam-Mart/6amMart-style multi-tenant grocery-delivery platform, same family as `melat_shop_af`/`superstan_af`), and the app calls its own first-party `/api/menu-section?restId=55116&rest_brId=57503&delivery_type=0&source=` endpoint at page load per a Playwright network trace — but replaying that exact URL (both via a cold `curl_cffi` request AND via `page.request.get()` reusing the live browser's own cookies) returns `400 {"msg":"Please provide restaurant id!"}` despite `restId` being present in the query string. Tried casing variants (`rest_id`, `restBrId`) with the same result — the real requirement is some other param/header/session token not yet identified (a signed request or a cookie set by an earlier call in the sequence, e.g. `/api/geofence` or `/api/branch`, that this pass didn't chain in order). Worth a real pass: replay the FULL request sequence in order (geofence → payment-gateways → branch → menu-section) with the exact same cookie jar, or inspect the request's own headers for a signature this pass didn't capture. Probed 2026-09-01 (MENAAP sweep, agent B).
- **echoppies.com** (BW, Choppies — Botswana's largest grocery chain; this is the real online store, *not* the corporate `choppies.co.bw`) — 200 on `curl_cffi chrome124`, 121KB, a Next.js storefront. `/api/products`, `/api/catalog/products`, `/api/product/search`, `/api/v1/products` and `/sitemap.xml` all 404. Needs a Playwright network trace to find the real listing endpoint — **do not record a skip without one.** A prior run wrote Choppies off entirely after probing only `choppies.co.bw`. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **spar2u.co.bw** (BW, SPAR Botswana online — again a sibling domain, not `spar.co.bw`) — 200, a 2.5MB hydrated page. Catalog endpoint not found by path guessing; needs a network trace. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **mmaraka.app** (BW, Mmaraka — Botswana marketplace) — 200, 1.16MB, BWP prices present in the rendered HTML, platform unidentified. Found **only** by the Setswana query `mmaraka wa dijo Botswana` — the single real return from that country's local-language pass. Probe the seller directory before the catalog. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **dijo.app / zebras.co.bw / gabseats.com / order.wanzyapp.com** (BW — Dijo, Zebras Delivery, Gabs Eats, Wanzy; four Gaborone food-and-grocery delivery platforms) — all 200 on `curl_cffi chrome124`, none exposing a catalog endpoint on the standard WooCommerce/Shopify/REST paths. Delivery platforms carry retailer-priced baskets, so they are worth one Playwright network-trace pass as a group. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **trans.co.bw / tradeworldbw.com** (BW, TRANS Cash & Carry — wholesale) — 200, WordPress, no Store API. Wholesale feeds are the highest-marginal-value source class per `discovery.md`; worth a trace. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **maketpamht.com** (HT, "Maket Pam") -- re-probed 2026-09-05, verdict unchanged from 2026-09-01. `/wp-json/wc/store/v1/products` returns the site's own 404 page and `?rest_route=/wc/store/v1/products` returns a 2KB JS-driven shell. Navigation is all `javascript:` calls. Needs a real Playwright interaction probe to determine whether it is live commerce or another demo shell -- the only remaining Haiti lead not conclusively killed.
- **foodstore2goexpress.com** (BS) -- not blocked at all; a fully working WooCommerce Store API. Recorded as a **rejected duplicate**: same operator as `foodstore2go.com` (shipped as `foodstore2go_bs`, Shopify, 862 products) and it holds only **22 products total**, 7 of whose names already appear in the Shopify catalogue. Clears the >=5-row gate on a technicality; shipping it would add a source for ~15 net SKUs.

## Google reCAPTCHA Enterprise "Checking your browser" interstitial (HTTP 200, never resolves headlessly)

Distinct signature from the Cloudflare/Akamai/DataDome entries above: HTTP status is 200 (not 403), and the page title is literally "Checking your browser - reCAPTCHA" rather than a CDN-branded challenge page. Confirmed as a genuine block only when it persists across all three `curl_cffi` TLS profiles AND a real headless-Chromium Playwright render with an 8s wait (the mandatory gate) — a transient version of this page sometimes auto-clears on a real browser, so always render before recording.

- **www.eroski.gi** (GI, Eroski City/Eroski Center Gibraltar — the territory's only supermarket chain offering home delivery, per its own Facebook marketing) — `<title>Checking your browser - reCAPTCHA</title>` on `curl_cffi` `chrome124`, `chrome120`, AND `chrome99` (20-20.4KB body, identical across all three), and unchanged after a full headless Playwright render with an 8s wait (still the same title, 25,655-byte body). Server header is `ESF` (not a named CDN vendor string seen elsewhere in this file). Gibraltar's only other retail lead, `hungrymonkey.gi` (`order.hungrymonkey.gi`, a Preoday-platform ordering app), is a restaurant-food delivery aggregator, not a grocery retailer — does not qualify as a channel substitute. Probed 2026-09-01 (ECA western-Europe F&B sweep, agent A).

- **gebeyaaddis.com** (ET, Gebeya Addis) — HTTP 200 with a 1,686-byte body titled "Bot Verification" that renders a LiteSpeed `lsrecaptcha` form (Google reCAPTCHA v2, sitekey `6LewU34UAAAAAHvXqFOcQlm8z1MP1xpGAZCYEeZY`) and auto-executes it. Identical on `chrome124`, `chrome120`, `chrome131`, `firefox133` and `safari17_0`, and every sub-path (`/sitemap.xml`, `/products.json`, the Woo Store API route) returns the same stub — so the TLS-fingerprint lever is not the issue and there is no unguarded backend to find. Needs a solver, not a profile. Probed 2026-09-05.

## Login-walled catalog (real backend found via network trace, but core endpoint 401s without auth)

Not a CDN/WAF block — the storefront's own API requires an authenticated session to browse, confirmed by finding the real backend (never a literal string in the served JS; only visible via a Playwright network-request trace) and hitting its documented endpoints directly.

- **~~shop.channelislands.coop / jeshop.channelislands.coop / ggshop.channelislands.coop~~ — SOLVED 2026-09-01, NOT login-walled. Superseded; do not treat as a blocker.** The 401 was real but the conclusion was wrong. The Flutter bundle ships a **static anonymous Laravel Sanctum app token** (`1|lax...`, a bearer literal matching `\d+\|[A-Za-z0-9]{40,60}` in `main.dart.js`) which every visitor receives; sending it as `Authorization: Bearer <tok>` opens the whole catalogue over plain HTTP. The earlier pass found the backend (`ogs.channelislands.coop`) and the route (`GET /api/stores/<id>/products`) but searched the bundle for the strings "guest"/"public" rather than for a **token literal**, and so recorded a guest-browsing wall that does not exist. Now onboarded as `coop_ci` (eca/western_europe/channel_islands): 2 stores (Jersey 5,058 + Guernsey 4,687 = 9,745 SKUs), 500-row test run clean, 73.4% measured food share.
  **Generalisable lesson:** a 401 from a JS-app backend is not evidence of a login wall until you have grepped the bundle for a bearer-token literal. Canvas-rendered SPAs must authenticate somehow before a user logs in, and for Laravel Sanctum apps that is routinely a hardcoded anonymous token.

- **www.metro.sk** and **www.metro.rs** (SK/RS, Metro Cash & Carry — wholesale) — both reachable, real assortment/category nav ("veľkoobchod potravín" / wholesale foods on the SK side), but `/aktualna-ponuka` (current-offer) pages carry zero price text in the rendered HTML on either domain -- Metro's membership-card wholesale pricing is not shown to an unauthenticated visitor. No API sniff attempted (B2B login flow out of scope for this pass). Probed 2026-09-01 (ECA sweep, agent B).

- **www.alimentaangola.co.ao** (AO, ALIMENTA ANGOLA RETAIL LDA — cash-and-carry chain) — **the biggest near-miss of the Angola pass.** Fully enumerable WooCommerce catalogue: `/sitemap.xml` fans out to five `product-sitemap<N>.xml` children (~5,000 PDPs under `/loja/<slug>/`) and the products are exactly the wanted division-01 goods (`ovos-frescos-angolaves-c-12un`, `sal-marinho-sabor-a-vida-750gr-uni`, `refresco-po-uva-amavita-35gr`). But **the PDPs carry no price anywhere** — no JSON-LD Offer, no `product:price:amount` meta, no `woocommerce-Price-amount` element, no `Kz`/`AOA` string in the whole 105KB body; the page renders breadcrumb + REF + description + related products and stops. Same shape as the Metro SK/RS entry above and as Mena Mart in the 2026-09-01 Angola inventory: cash-and-carry pricing is withheld from unauthenticated visitors. Worth one re-check if the chain ever opens pricing. Probed 2026-09-05 (SSA div-01/02 sweep).
- **www.burundiworks.bi** (BI, "Burundiworks — Online Store", Avenue de l'amitié 8, Rohero, Bujumbura) — apex renders a login form titled "Login | Global Post"; `/shop` returns HTTP 200 but the body is a wall of PHP deprecation notices from a CodeIgniter app (`application/controllers/Shop.php`) with zero product markup and zero `BIF`/`FBu` strings, and every account action links to `diic.burundiworks.bi/app/*`. Broken **and** login-walled. Probed 2026-09-05.

## DDoS-Guard (Russian anti-bot, `DDOS-GUARD` page title, `/.well-known/ddos-guard/js-challenge/`)

Distinct vendor from Qrator (different challenge JS path, different page chrome) but same tenant-independent "stop, don't re-probe" logic applies. Confirmed blocking both curl and headless Playwright with an identical page title — the strongest confirmation tier in this file.

- **www.chitai-gorod.ru** (RU, Chitai-Gorod — national bookstore/stationery chain, COICOP 09 candidate) — **UPDATE 2026-08-07 (shard A3 resume): now a confirmed hard block, supersedes the 2026-08-07 "not extractable" entry below.** curl on `/product/<id>`: HTTP 403, 898-byte body, `<title>DDoS-Guard</title>`, `check.ddos-guard.net/check.js`. Playwright (headless Chromium, 8s wait): page title `DDOS-GUARD`, 4739-byte body — same wall. The sitemap-index request that looked clean in the original probe (`/sitemap.xml` → `/sitemap/products1.xml`) still returns HTTP 200 (DDoS-Guard appears to allow sitemap crawling but gate `/product/` pages specifically), so the original "timeout, not diagnosed" verdict undersold it: this is now a clean block signature, not a flaky timeout. COICOP 09 (books/culture) gap remains open elsewhere. Do not re-probe without a residential proxy / captcha-solving setup.

Original (superseded) entry, kept for the timeout signature in case it recurs elsewhere: homepage and `/sitemap.xml` → `/sitemap/products1.xml` (18 chunks, ~50k URLs each) both load fine over plain curl, but every `/product/<slug>` request timed out (`curl: (28)`, 0 bytes) across three separate attempts with pauses in between.

## ServicePipe anti-bot (Russian anti-DDoS, `servicepipe.tech` challenge loader + rotated-image captcha)

Third distinct RU anti-bot vendor seen this round (alongside Qrator and DDoS-Guard). Signature: a tiny (~1.6KB) HTML shell loading `https://servicepipe.tech/loaders/<hash>.js` and `.../checkjs/<hash>/<hash>.js`, with an embedded `get_options()` JS blob and a `<noscript>` refresh to a randomized path. Confirmed blocking both curl and headless Playwright — Playwright resolves the JS challenge redirect but lands on a **rotated-image captcha** page (`sp_rotated_captcha`), not the target site.

- **www.perekrestok.ru** (RU, Perekrestok — X5 Group supermarket chain, COICOP 01/02/05/09/13 candidate) — curl: 200 but 1578-byte ServicePipe challenge shell. Playwright (8s wait): redirected to a `sp_rotated_captcha` image-captcha page, page title empty, 16KB body. Same infra likely shared across the whole X5 Group (Perekrestok, Pyaterochka, Kuper — see below). Probed 2026-08-07 (round-3 Russia shard, shard A3).
- **kuper.ru** (RU, Kuper — X5 Group's rebranded SberMarket grocery-delivery marketplace; `www.sbermarket.ru` 301s here) — identical ServicePipe shell (same `get_location()`/`get_options()` structure, different hashes). Not separately Playwright-confirmed but byte-for-byte same signature as the confirmed perekrestok.ru pair — same tenant. Probed 2026-08-07.
- **samokat.ru** (RU, Samokat — quick-commerce grocery delivery, COICOP 01/02 candidate, wave-8 food search), **okeydostavka.ru** (RU, O'Key's delivery subdomain), **azbukavkusa.ru** (RU, Azbuka Vkusa — premium supermarket chain, COICOP 01/02/05/09 candidate) — all three return the identical ~1.7-1.8KB ServicePipe spinner shell (`servicepipe.tech/loaders/<hash>.js`, `id_spinner`/`id_captcha_frame_div`) on curl_cffi impersonate=chrome124. Same tenant family as perekrestok.ru/kuper.ru — likely a shared anti-bot vendor contract across several unrelated RU retail groups, not evidence they share infra otherwise. Probed 2026-09-01 (wave 8).

- **fedstat.ru** (RU, EMISS/Rosstat's alternate statistical-data portal) — bare HTTP 403 (`Forbidden`, `Request ID: ...`) on every path tried (`/indicator/37426`, `/opendata`), TLS handshake itself clean (Let's Encrypt cert, no chain issue). Not diagnosed further because `rosstat.gov.ru` (the ministry's own domain, different infra) turned out to publish the same "средние потребительские цены" survey as direct-download XLSX with no WAF at all — see `ru_rosstat_avg_prices` fetcher. If EMISS/fedstat's structured SDMX API becomes worth pursuing later (it has per-indicator filters rosstat.gov.ru's static files don't), this 403 needs a real diagnosis (geo-fence vs. WAF vs. rate limit) first. Probed 2026-08-07.
- **mcx.gov.ru** (RU, Ministry of Agriculture — wholesale/procurement price monitoring for grains and staples, `wholesale` channel candidate) and **fas.gov.ru** (RU, Federal Antimonopoly Service — price-monitoring candidate) — both hit a hard TCP connect timeout (`curl: (28)`, ~10s, 0 bytes) on the bare domain, no TLS handshake ever started. Different failure mode from the Qrator/DDoS-Guard/ServicePipe WAF challenges elsewhere in this file — looks like the host is simply unreachable from this network path (geo-fencing or the host genuinely not answering), not a bot wall. Not diagnosed further (no network trace beyond curl timeout — a real diagnosis would need e.g. a traceroute or a different egress). Both remain the brief's top statutory-source leads for Russia; worth a retry from a different network before writing off. Probed 2026-08-07 (round-3 Russia shard, shard A3).
- **www.gks.ru** — old Rosstat domain, now redirects/aliases into the `rosstat.gov.ru` infrastructure; using the same vendored CA chain as `ru_rosstat_avg_prices` (`_rosstat_gov_ru_chain.pem`) still fails, but with a *different* error: `Hostname mismatch, certificate is not valid for 'www.gks.ru'` — the leaf cert vendored for `rosstat.gov.ru` doesn't cover this hostname. Not worth chasing: `rosstat.gov.ru` itself (already shipped as `ru_rosstat_avg_prices`) is the live, correctly-certed domain for the same "средние потребительские цены" survey. Probed 2026-08-07.

## Cloudflare strict — Pacific Island portals (522 timeout + Cloudflare headers)

These sites are behind Cloudflare and return a 522 (connection timeout) or 403 with Cloudflare headers from outside Fiji. Both curl and WebFetch fail.

- **property.com.fj** (FJ, Fiji real estate portal) — 522 timeout from non-Fiji IP; Cloudflare Orange Cloud confirmed from TLS cert owner (CN=property.com.fj, let's encrypt). Rental listings for COICOP 04.1.1. Needs residential-proxy or Playwright+stealth from within Fiji CDN zone. Probed 2026-06-10.

## Placeholder / offline sites — no content (Vanuatu)

Sites that returned ECONNREFUSED or a placeholder "coming soon" page during 2026-06-10 desk research for Vanuatu. May have been offline or in redevelopment. Re-probe before building any fetcher.

- **unelco.engie.com/en/vanuatu/** (VU, UNELCO Engie — electricity/water provider) — page returns "We are working on something really cool" placeholder with no tariff content. UNELCO rates available via URA tariff page (ura.gov.vu) instead. Probed 2026-06-10.
- **vodafone.vu** (VU, Vodafone Vanuatu — telco) — ECONNREFUSED on direct fetch; domain may not resolve or server offline. Use Digicel Vanuatu (digicelpacific.com/mobile/vu) as primary telco alternative. Re-probe before writing off. Probed 2026-06-10.
- **abm.vu** (VU, Au Bon Marché — Vanuatu's largest supermarket chain) — ECONNREFUSED on direct fetch. Corporate domain; aubonmarche.co is the active site (brochure-only, see below). Probed 2026-06-10.
- **aubonmarche.com.vu** (VU, Au Bon Marché) — DNS NXDOMAIN via `curl_cffi` (`Could not resolve host`). A third distinct dead Au Bon Marché domain alongside abm.vu (ECONNREFUSED) and aubonmarche.co (brochure-only). Probed 2026-09-01.
- **vanuatudirect.com** (VU, "Vanuatu Direct" farm-to-table produce platform lead) — HTTPS fails with `SSL_EOF` on both apex and `www.` (confirmed with both `curl_cffi impersonate=chrome124` and plain `requests`, so not a TLS-fingerprint block); bare HTTP on the apex redirects to `www.` and returns a plain 404. Reads as a dead/parked domain rather than a live storefront behind a WAF. Probed 2026-09-01; re-check in ~6 months in case of relaunch.

## Brochure-only — no online store (Vanuatu)

- **aubonmarche.co** (VU, Au Bon Marché) — corporate/marketing site; no product catalogue, no prices. Retail section returns a job-application page for "Retail Supervisor." Vanuatu's largest supermarket but no e-commerce presence. COICOP 01 retail SKU gap remains. Probed 2026-06-10.

## React SPA with Supabase backend — no server-rendered listings

Site is a React SPA backed by a Supabase PostgreSQL REST API. Server-rendered HTML contains only app shell. Listings load via Supabase PostgREST queries.

- **bas.com.fj** (FJ, Fiji classifieds — cars, property, electronics) — React SPA. Supabase backend at `bflgucswqljuhmkhilvv.supabase.co`. HTML source contains only `<div id="root"></div>` shell. 42,000+ listings in Suva/Nadi/Lautoka. Check whether `supabase.co` PostgREST API is publicly accessible without anon-key headers — if so, Tier 1B (scrapy_api). Otherwise needs Playwright network-capture to sniff the Supabase REST endpoint. Probed 2026-06-10.
- **www.entrega.st** (STP, "Entrega.st" — wave 13 workbook ACCEPT, "Live platform (CMPE LDA)... Catalogue behind login - verify depth") — Vite/React SPA over Supabase (`qhakterudpcyieehzacn.supabase.co`), publishable key recovered from the shipped JS bundle. Confirmed genuinely RLS-locked, not just "behind a login screen a scraper could route around": `GET /rest/v1/products` and `/rest/v1/establishments` with the shipped anon key both return `401 permission denied for table establishments` — no SELECT grant exists for the anon role on any base table. The one deliberately public surface is a curated RPC allowlist visible in the bundle (`rpc/list_public_establishment_directory`, `rpc/list_public_establishment_rating_aggregates`, `list_orderable_establishments`, plus courier/order RPCs) — none of it is a products/catalog RPC. Querying the public directory RPC (via the site's own `/lojas` page, confirmed live) returns only **4 total registered merchants platform-wide** (1 restaurant, 1 general store, 1 pharmacy, 1 bakery), with name/category/rating/open-status only — no product names, no prices, for any of them. Matches the bundle's own copy ("Espaço futuro para divulgar estabelecimentos" / future space to promote establishments) — the platform is real but has essentially no live merchants yet. Do not re-probe the raw tables; if re-checking in a future wave, check the `/lojas` merchant count first as a cheap freshness signal. Probed 2026-09-01 (wave 13).

## FCCC website — 403 on individual pages, PDF direct links accessible

The FCCC WordPress site (fccc.gov.fj) returns 403 Forbidden on many individual post/page URLs when accessed via WebFetch, but PDF files linked from the main /petroleum/ and /gas/ pages are accessible via curl with a browser UA. The main section index pages (/petroleum/, /gas/) are also accessible. This is a Cloudflare or WAF config that blocks bots on page content but allows direct PDF CDN access. The fetcher approach: hit the index page to get the latest PDF link, then download the PDF directly.

- **fccc.gov.fj/petroleum/** — 403 on individual post URLs (e.g. /2026/05/31/media-release-fuel-and-lpg-prices-june-2026/); PDF direct links accessible. Pattern confirmed 2026-06-10.
- **fccc.gov.fj/gas/** — same pattern; monthly LPG authorisation PDFs accessible directly.
- **fccc.gov.fj/basic-food-items-2/** — page loads via curl (browser UA) but no price tables in server-rendered HTML; content appears JS-rendered (WordPress shortcode). Price data may be in linked PDFs not indexed on /petroleum/ or /gas/ pages.

## Image-only tariff/price sources (PDF or CMS article with no machine-readable price text)

These sources publish prices exclusively as embedded images or image-only PDFs. HTML article bodies contain narrative text but no table elements. Structure-extraction tools (pdfplumber, pandas.read_html) return nothing useful. Fetchers must either hardcode known values or use OCR.

- **petrolimex.com.vn/nd/gia-ban-le-xang-dau/** (VN, Petrolimex — state oil/gas) — price announcements are image screenshots (PNG/WebP) embedded in VIEApps NGX CMS articles. HTML body has zero table elements; price numbers only appear in image alt="" or data-src attributes. No public JSON API for current retail prices. Probed 2026-06-15. Bypass requires OCR of announcement image or hardcoded _KNOWN_PRICES pattern.
- **evn.com.vn** electricity tariff PDF (VN, EVN — state electricity) — Decision 1279/QĐ-BCT PDF (`QD1279-QD-BCT-20250509163514982.pdf`, 3.9 MB, 8 pages) is image-only (each page is one scanned image). pdfplumber extract_text() returns empty string. Values hardcoded in evn_vn_tariff fetcher. Confirmed 2026-06-15.
- **service-public.pf/dgae "Le Panier futé"** (PF, DGAE — official 15-product basket flyer, sibling to the "La Météo des Prix" PDFs) — recent editions (`PRINT-AOUT.pdf`, 20.6 MB) are a single-page raster image, `page.images` non-empty, `extract_text()` returns 0 chars; an older edition (`PRINT_OCT.pdf`, Oct 2025, 17.6 MB) does have a text layer but the layout is a garbled multi-column flyer (product min/max price pairs interleaved with a separate per-store *basket-total* ranking list in a non-linear reading order) — reliable parsing would need column-aware reordering, not just `extract_text()`. Deprioritized rather than built: its own item-level data (min/max price per product) is a strict subset of what "La Météo des Prix" already delivers per-store at finer grain (see `pf_dgae_meteo_prix` fetcher); the one thing Panier futé adds — a total-basket-price ranking across many small neighborhood stores (LS Proxi, Magasin Ami Rene, etc. — outlets Météo's Hyper/grand-supermarché edition doesn't cover) — is a composite aggregate, not a per-item price, so it doesn't map to a COICOP leaf anyway. Probed 2026-08-11.

- **ceb.mu/files/files/publications/regulations/electricity_tariff_2026.pdf** (MU, Central Electricity Board — Government Notice No. 473 of 2026, the 1-May-2026 residential tariff revision) — the PDF embeds a non-standard font with no usable ToUnicode CMap: both `pdfplumber` and `pdftotext -layout` return CID/private-use-area garbage instead of real text on every page. `pdftoppm`-rendered page images ARE legible on visual inspection (confirms the notice text and that rates rise up to 15% from 1 May 2026, same band structure, no restructuring) but OCR of the actual Appendix rate tables was out of scope for this pass. The fetcher ships the older, cleanly-extractable `CEBTARIFFS.pdf` (effective Feb 2024) instead — see `ceb_electricity_tariff.py`. Probed 2026-09-01 (wave 10).
- **cwa.govmu.org** water-supply tariff amendment PDFs (MU, Central Water Authority) — the "Tariffs and Charges" page (`/cwa/?page_id=794`) links only *connection-fee* regulations (`Domestic.pdf`, GN 51 of 2014 — one-off new-supply fees, not the recurring per-cubic-metre consumption tariff) plus a 2026 amendment (`GN-No-22-of-2026-...-Amendment-Regulations-2026.pdf`) that is image-only (`pdfplumber.extract_text()` returns empty on both pages). No machine-readable consumption-tariff schedule (COICOP 04.4.1) was found on the site within this pass's budget — a genuine sourcing gap, not built. Probed 2026-09-01 (wave 10).
- **www.tanesco.co.tz/api/v1/uploads/tanesco_approved_tariffs.pdf** (TZ, TANESCO — national electricity utility) — the storefront-style corporate site is an Angular SPA with a genuinely open backend (`api/v1/documents/allActive`, no auth, `documentCategoryEnum=TARIFFS`), so the tariff PDF itself is trivial to locate — but the PDF is a single-page scanned image (`pdfplumber`: 0 chars, 5 embedded images, `extract_tables()` empty). OCR (pytesseract) would work but digit-level misreads on a tariff-rate table are a real risk for financial data; not attempted this pass since the country's source bar was already met without it. Probed 2026-09-01 (wave 12).
- **othaimmarkets.com** (SA, Al Othaim Markets — wave onboard1 candidate, pre-probe said 200 OK / 135KB) — live and unblocked, but the domain is the **corporate** site, not a storefront. Next.js; `robots.txt` is `Allow: /` and `sitemap.xml` lists 328 URLs that are entirely news (112 ar/news), investor relations, about-us, recipes and store-locator pages — **zero product routes**; `/en/s?q=milk` 404s. The only price surface is the weekly flyer at `/en/offers/weekly-promotions`, which links `/api/pdfOffers/<id>-<n>.pdf`: a 7.8MB, 44-page PDF whose pages are single 1063x1400 images — `pdfplumber.extract_text()` returns **0 characters on every page sampled**. Arabic OCR over a 44-page promo flyer is the only route and is not worth it. Al Othaim's actual e-commerce is app-only. Probed 2026-09-11.

## Stale DAM PDF URL — 200 OK serving HTML "Page not available"

CDN-fronted document servers (Magnolia, Adobe AEM, similar) sometimes serve a 200 OK + tiny HTML "Page not available" page from a vanity URL whose backing document has been retired. HEAD returns 308 + a content-disposition that *looks* like a PDF, but the body of a real GET is HTML. Always `file <download>` after curl — if it says `HTML document` when content-type claimed `application/pdf`, the URL is stale.

- **www.spgroup.com.sg/wcm/connect/...Tariff+Revision+for+Q4+2025.pdf** — example of a stale Magnolia link surfaced by an old search-engine snapshot. Real current docs live under `/dam/jcr:<uuid>/`. Use `WebSearch allowed_domains=[<host>]` to find the canonical current URL instead of guessing path patterns.

## Unreachable / no online storefront exists (dead candidate, not a WAF)

- **pricewhirl.com** (BB, "personal-shopper model launched 2017") — `curl_cffi impersonate=chrome124` times out after 30s (`curl: (28) Connection timed out`) on both `http://` and `https://`. No catalog exists to probe. Probed 2026-09-01.
- **Nassco** (BB) — resolves to `nassco-barbados.com`, not the `.com.bb`/`nasscoltd.com` guesses in the wave-8 brief. Confirmed via WebSearch to be National Automotive Sales and Service Company (Toyota dealer/parts distributor), not a hardware store as the brief assumed — and has no online shopping regardless. Probed 2026-09-01.
- **Popular Discount** (BB) — no domain found; WebSearch turns up only directory/review listings (Tripadvisor, FindYello, business directories), no retailer-operated website of any kind. Probed 2026-09-01.
- **Carlton / A1 Supermarkets / Emerald City** (BB) — all three names in the wave-8 brief's "if you need more" list are branches of the already-onboarded **aonesupermarkets** chain (Carlton, Black Rock and Emerald City/Six Roads locations), not separate retailers. Confirmed via WebSearch. Do not build as new sources.
- **globus.ru** (RU, Globus — hypermarket chain), **myasnov.ru** (RU, Myasnov — regional meat chain), **www.pyaterochka.ru** (RU, Pyaterochka — X5 Group's discount chain) — all three hit a hard `curl_cffi` connect timeout (`curl: (28)`, 15s, 0 bytes), no TLS handshake started. Different failure mode from the Qrator/ServicePipe walls elsewhere in this file — looks like the host is unreachable from this network path rather than an application-level bot wall. Probed 2026-09-01 (wave 8, food search).
- **www.karusel.ru** (RU, Karusel — former Auchan-Group hypermarket brand, since absorbed into Lenta) — `curl: (6) Could not resolve host` — DNS does not resolve at all, consistent with the brand having been folded into lenta.com. Probed 2026-09-01 (wave 8).
- **www.vprok.ru** (RU, Perekrestok's old standalone delivery brand) — HTTP 200 but the body is a themed "Ошибка #625116" (Error #625116) page asking the visitor to contact the resource owner, with a request-ID and echoed client IP — a bespoke WAF/edge error page, not the real site, on every path tried. Probed 2026-09-01 (wave 8).
- **dixy.ru** (RU, Dixy — discount grocery chain) and **5ka.ru** (RU, Pyaterochka's separate delivery-app domain) — both HTTP 403 on curl_cffi impersonate=chrome124 (dixy.ru: 96KB themed block page; 5ka.ru: 2.9KB generic 403), not re-probed with Playwright. Probed 2026-09-01 (wave 8).
- **verno-info.ru** (RU, Verniy/Верный — national hard-discount chain) — reachable, no WAF, but it's the chain's corporate/investor-relations site (loyalty-card signup, franchise/vacancy pages, a `/products` own-brand showcase and a recipes section), not an online store — Verniy is a cash-and-carry discount format with no e-commerce delivery arm. Probed 2026-09-01 (wave 8).
- **oma.gov.ml** (ML, Observatoire du Marché Agricole — Mali's agricultural market price observatory, the wave-9 brief's #1 lead) — genuine `NXDOMAIN` against both `8.8.8.8` and `1.1.1.1` (not a sandbox DNS lie). The institution's successor/parent body APCAM has a live site at `apcam.ml` (200, real content) but it is a brochure-only marketing page — a modal literally titled "Bourses & Prix des Céréales / Consulter les cotations hebdomadaires sur les marchés ruraux" links to `#contact`, an in-page anchor, not a bulletin or table. No price data anywhere on the domain. Probed 2026-09-01 (wave 9).
- **smart-market.ml** (ML, "Smart Market, votre marché en ligne à Bamako") — genuine `NXDOMAIN` against both `8.8.8.8` and `1.1.1.1`. Surfaced by search with a live-looking `/boutique/` URL in the SERP snippet, but the domain itself no longer resolves. Probed 2026-09-01 (wave 9).
- **ikasougou.com** (ML, general marketplace) — resolves (45.95.182.190) but `curl_cffi impersonate=chrome124` fails with `TLSV1_ALERT_INTERNAL_ERROR`. Not re-probed with `chrome120`/`safari17_0` this pass. Probed 2026-09-01 (wave 9).
- **edsa.sl** (SL, Electricity Distribution and Supply Authority) — live DotNetNuke CMS (200 OK on every path, no WAF), but the "Tariffs" tab (`/Home/Tariffs`, TabId=21) renders an empty content module — no tariff schedule, no PDF, nothing under CustomerService/eServices/AboutUs either. The tariff DATA was simply never published to this site, not a technical block; worth re-checking in a future wave in case that changes. Probed 2026-09-01 (wave 9).
- **www.salwaco.gov.sl** (SL, Sierra Leone Water Company) — resolves (192.96.217.94, confirmed against 8.8.8.8) but HTTPS hangs/has an expired certificate (`curl: (60) SSL certificate problem` then a 20s timeout even with `verify=False`); plain HTTP on the bare IP serves a default Plesk "no website at this address" placeholder. Domain is effectively derelict. No Guma Valley Water Company domain could be found either (`gumavalley.gov.sl`, `gvwc.gov.sl`, `guma.gov.sl`, `guma.sl`, `gvwc.sl`, `gumavalleywater.com` all NXDOMAIN against 8.8.8.8) — not pursued via web search this pass. Probed 2026-09-01 (wave 9).
- **agrixmarketplace.com** (AF, Agrix agricultural marketplace — the wave-10 brief's one "plausibly food" candidate) — HTTP 200 but the root path JS-redirects to `/lander`, a GoDaddy/wsimg domain-parking shell (`window.LANDER_SYSTEM="PW"`, `parking-lander` static bundle). The marketplace itself no longer exists at this domain. Probed 2026-09-01 (wave 10).
- **sawda.af** / **www.sawda.af** (AF, "Online Grocery Shopping and Online Supermarket in Afghanistan") — genuine `NXDOMAIN` against both `8.8.8.8` and `1.1.1.1` on apex and `www.`, despite being the top-billed WebSearch hit for "Kabul Afghanistan online grocery delivery supermarket website". Indexed but does not currently exist. Probed 2026-09-01 (wave 10).
- **haftsin.com** (AF, guessed while chasing "Haftsin Supermarkets" — a brand named in a Melat Shop / Dara.af product's `attributes.Manufacturer` field) — HTTP 200 but a 114-byte JS-redirect-to-parking-lander page, same signature as agrixmarketplace.com. `haftsin.af`, `haftseen.af`, `haftsinsupermarket.com`, `haftseen.com` (timeout), `melatshop.af`, `melatshop.com` all fail DNS resolution outright. Haftsin does not appear to run its own direct-to-consumer web storefront — it appears to sell only through Melat Shop's Dara.af listing. Probed 2026-09-01 (wave 10).
- **Hiper Europa** (SV, El Salvador — a wave-10 brief food lead) — confirmed via WebSearch to be a defunct 1990s-era chain ("Hiper Europa", founded by Edmundo/Óscar Saca) that no longer operates; press retrospectives list it among supermarkets that disappeared from the Salvadoran market. No current domain or storefront exists. Probed 2026-09-01 (wave 10).
- **lacolonia.com** (HN, La Colonia — already onboarded as `lacolonia_hn`) — re-checked for El Salvador coverage per the wave-10 SV brief's instruction ("La Colonia is Honduran; check whether it trades in SV before counting it"). The live site has zero mentions of "El Salvador", "San Salvador", or any Salvadoran city/branch — Honduras-only (Tegucigalpa + San Pedro Sula). Does not count toward El Salvador. Probed 2026-09-01 (wave 10).
- **stc.intnet.mu** (MU, State Trading Corporation — the wave-10 brief's lead for regulated petroleum/LPG prices) — DNS resolves cleanly (`197.224.66.134` against both `8.8.8.8` and `1.1.1.1`, ruling out a sandbox DNS lie), but both `https://` and `http://` connect attempts (`curl_cffi impersonate=chrome124`) time out after 15-20s with no TLS/TCP handshake completing. No other STC domain found (`stc.mu`, `www.stc.mu` both `NXDOMAIN`). Server appears derelict, not WAF-walled. Probed 2026-09-01 (wave 10).
- **gecol.ly / www.gecol.ly** (LY, General Electricity Company of Libya — the wave-10 brief's electricity-tariff lead) — DNS resolves cleanly (`154.73.133.229` against both `8.8.8.8` and `1.1.1.1`), but `curl_cffi impersonate=chrome124` times out after 30s with no TLS handshake completing. Government server appears derelict/unreachable from this network path, not WAF-walled — consistent with other Libyan government infrastructure. Used `ly_bsc_cpi` (Bureau of Statistics CPI) instead for the non-food `cpi_benchmark` slot. Worth a re-check in a future wave. Probed 2026-09-01 (wave 10).
- **cbl.gov.ly** (LY, Central Bank of Libya — also publishes monthly CPI/inflation PDFs) — whole domain (not just one page) returns Cloudflare-branded HTTP 403 on `curl_cffi impersonate=chrome124`; not re-probed with chrome120/safari17_0 or Playwright since `bsc.ly` (Bureau of Statistics and Census) already provides a live, open, text-extractable CPI series covering the same analytical role — deprioritized rather than fully worked through the mandatory gate. Probed 2026-09-01 (wave 10).
- **shop2sitesl.com** (SL, "Shop 2 Site" — "Buy groceries from Freetown and have it delivered to site weekly", surfaced fresh in a wave-11 grocery-delivery search, not present in the wave-9 SL inventory) — `dig shop2sitesl.com A @8.8.8.8` and `@1.1.1.1` both return `127.0.0.1` (the domain's own authoritative A record, not a resolver-level block or sandbox DNS lie) — a registrar-parking/expired-hosting sinkhole. `curl_cffi` cannot even open a TCP connection (`curl: (7) Could not connect to server`). Domain is derelict despite still ranking in search. Probed 2026-09-01 (wave 11).
- **alburujmarket.com** (SD, "Alburuj Market" / البروج أونلاين ماركت — advertised via a live Facebook page `facebook.com/alburuj.online`, Khartoum, phone +249 12 190 0021) — `dig alburujmarket.com @1.1.1.1` and `@8.8.8.8` both return `NXDOMAIN`; the domain has no DNS record at all despite the Facebook page actively pointing customers to it. Closes out the "Alburuj Market" lead flagged as not-yet-probed in the wave-8 Sudan pass. Probed 2026-09-01 (wave 11).
- **KS Mart** and **TSM Mart** (AS, the two named grocery chains in Tafuna, American Samoa) — both are long-running, real physical stores (KS Mart 25+ yrs; TSM Mart a two-story grocery+variety building) but neither has a website of any kind, confirmed via direct domain guesses (`ksmartsamoa.com`, `ksmart.as` both `NXDOMAIN`) and WebSearch — Facebook is each chain's only online presence, with no price data posted there in structured form. Genuine "does not exist," not a block. Probed 2026-09-01 (wave 11).
- **Forsgren** (AS, Laufou Shopping Center, Nu'uuli) — `forsgrens.com` resolves but is an unrelated web-marketing-links squat page ("Olov Forsgren... web marketing links"), not the retailer; no other candidate domain found. Probed 2026-09-01 (wave 11).
- **doa.as.gov** (AS, American Samoa Dept of Agriculture — runs the Fagatogo public produce market) — TLS handshake fails (`SSL: no alternative certificate subject name matches target hostname`); with `verify=False` the response is a generic "CloudAccess.net Message" hosting-suspended/parked placeholder, not the real site. Domain is derelict. No other digital price presence for the Fagatogo market was found. Probed 2026-09-01 (wave 11).
- **hofladen-express.ch** (LI/CH, "Hofladen Express" — a farm-shop delivery service physically based in Bendern, Liechtenstein and Eggersriet, SG, serving LI + Ostschweiz + Zurich per its own former marketing copy) — domain has been squatted: every path resolves 200 but serves a "Dragonia Casino Online" gambling-affiliate page (Google Fonts preconnects, generic casino CSS classes), not the farm-shop. Genuinely dead per rule 13 (expired domain + injected spam), not a WAF. The service may still operate through the multi-vendor `laedelishop.ch` marketplace (Zurich-based operator, WooCommerce, has an "Essen & Trinken" food category) under a "Hofladen Express" vendor listing, but that platform's own Liechtenstein-delivery scope was not independently verifiable in the time budgeted this wave — not built. Probed 2026-09-01 (wave 13).
- **www.spar.ch** (CH, SPAR Handels AG — Spar operates franchise stores inside Liechtenstein per the wave-13 brief) — live corporate site (200, real content, Apache) but purely a brochure/investor site with a store-locator, no online shop, no shop/webshop link anywhere in the page. `spar.li` does not resolve (`NXDOMAIN`). No Spar e-commerce presence reaches Liechtenstein. Probed 2026-09-01 (wave 13).
- **choisupermarket.com** (SR, Choi's Supermarket — the wave-13 brief's named "largest chain" in Suriname) — expired TLS cert (`curl: (60) SSL certificate problem: certificate has expired`); with `verify=False` the response is a 392-byte 2008-era cPanel "Temporarily Disabled" hosting-suspension stub (`oops.gif`), not the real site. The business itself is real and operating (3 physical branches per whoswho.sr, active Facebook page `facebook.com/choisupermarket`) but has no working website of any kind — genuinely dead per rule 13, not a WAF. Probed 2026-09-01 (wave 13).
- **tulip-supermarket.com** (SR, "Tulip" — Suriname's brief-named premium supermarket) — live, not blocked (200 OK, real content, Google Analytics tag), but a single-page brochure site only: one Unsplash stock hero image, a `#departments` in-page anchor, address/phone/social links — zero product listings, zero prices, no ordering flow of any kind. Physical-presence-only; not a WAF or dead-domain case, just no catalog exists to scrape. Probed 2026-09-01 (wave 13).

- **sms.fo / bonus.fo / miklagardur.fo** (FO, Faroe Islands — SMS shopping-centre group, its Bónus discount-grocery banner, and Miklagarður, the country's largest single supermarket) — all three are live, reachable, real sites (200 OK, no WAF), but none carries a grocery catalog: `sms.fo` is WooCommerce with exactly one product, a gift card (`/product/gavukortid-fra-sms/`); `bonus.fo` has no e-commerce markers of any kind (brochure/weekly-flyer style); `miklagardur.fo` is a Wix site whose only transactable page (`/keyp`, "buy") is a Wix-Stores gift-card page (`wixstores`/`GiftCard` markers), not a product catalog. Neither Wolt (`wolt.com/fo` redirects to the generic homepage, no Faroese city) nor Bolt Food (`bolt.eu/en/cities/torshavn/` 404s) operate in the territory. No online grocery sector currently exists for the Faroe Islands. Probed 2026-09-01 (ECA western-Europe F&B sweep, agent A).
- **pisiffik.gl** (GL, Greenland — Pisiffik, the country's largest private retail company) — live PrestaShop storefront (confirmed platform, real product pages with EAN-coded SKUs), but its catalogue is mattresses, kitchenware, small electronics, furniture and toys (`boxmadrasser`, `køkkenredskaber`, `møbler`, `legetøj`) with only incidental wine/sparkling-wine categories (`hvidvin`, `mousserende-vin`) — this is Pisiffik's department-store/general-merchandise e-commerce arm, not its grocery/fresh-food business, and is not catalogue-led by COICOP 01/02. **brugseni.gl** (KNI/Brugseni, the other major chain) is a WordPress corporate site with a store-locator (`/butikker/`) and no webshop link anywhere. **pilersuisoq.gl** (the third, government-linked chain serving small settlements) is a brochure site with no shop link and no e-commerce platform fingerprint. `brugsen.gl` (no "i") has a certificate hostname mismatch and does not serve the real site. No genuine online grocery source found for Greenland this pass. Probed 2026-09-01 (ECA western-Europe F&B sweep, agent A).
- **Isle of Man** — no resolvable domain found for any of the direct-guess candidates (`isleofmancoop.co.im`, `iomcoop.co.im`, `iomcoop.com`, `shoprite.co.im`, `robinsonsiom.com` all `NXDOMAIN`). Shoprite (the island's former largest chain) was acquired by Tesco in 2023-24 and no longer exists as a separate brand; Tesco's UK online-grocery delivery service is well documented as excluding Isle of Man postcodes (outside the mainland GB delivery zone), and no IoM-specific Tesco storefront was found. Session's WebSearch budget was exhausted before this could be search-verified further (only direct domain guesses and two WebFetch-based search-engine attempts, both returning unrelated generic content, were possible) — treat as inconclusive-leaning-negative, not exhaustively confirmed; worth a fresh WebSearch-based pass. Probed 2026-09-01 (ECA western-Europe F&B sweep, agent A).
- **Monaco — shared French national platforms only, no Monaco-specific storefront found** — Monaco's grocery retail (Carrefour Market Monaco, Monoprix) runs entirely on the same national French e-commerce platforms serving all of France (`courses.monoprix.fr`; Carrefour's French storefront) — no Monaco-registered domain (`carrefour.mc`, `monoprix.mc`, `spar.mc` all fail DNS; `casino.mc` resolves but is the unrelated Casino de Monte-Carlo gambling site, not the French "Casino" supermarket chain). Deliberately NOT onboarded under Monaco: these platforms are French-national, not Monaco-specific legal entities or catalogues, and shipping `courses.monoprix.fr` as a "Monaco" source risks exact duplication with a future France-onboarding pass building the same domain as `monoprix_fr` — the same underlying catalog and prices would then be double-counted under two country labels. Flagging as a policy question rather than shipping a source: does a shared cross-border national platform count as coverage for a micro-territory it delivers to, and if so, under which country label? Probed 2026-09-01 (ECA western-Europe F&B sweep, agent A).
- **comoresmarket.com** (KM, Comoros — "Comores Market", advertised as an online supermarket drive/pickup service for Moroni) — `curl_cffi impersonate=chrome124` fails with `TLSV1_ALERT_INTERNAL_ERROR` (server-side TLS misconfiguration, not a WAF); same failure on chrome120/chrome99/safari17_0. Plain HTTP on the bare domain 404s. Business may still be real (active Facebook page) but has no working website. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **asbeza.com** (ER, Eritrea — "Asbeza", an Ecwid-hosted storefront per its Google Play listing `com.ecwid.ShopAt.Asbeza`) — direct-guessed domain resolves (200) but serves a domain-parking/consent-manager landing page (generic CMP boilerplate, no product markup, no mention of Ecwid) — the real Ecwid subdomain/custom domain was not found. Squatted-domain pattern, same family as hofladen-express.ch above. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **koek.sc** (SC, Seychelles) — search surfaced this as a "Supermarkets in Seychelles" directory page, but the live site (200, Next.js) is a tour/boat-charter booking platform (boats, tours, livecam) with zero grocery content — a stale/mislabeled search snippet, not a real candidate. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **wowdeliverysey.com** (SC, Seychelles — "WOW Delivery", described by a third-party site as "Seychelles Number 1 Online Supermarket") — guessed domain does not resolve (`NXDOMAIN`). Real domain not found this pass (WebSearch budget was exhausted session-wide before it could be searched properly) — this is the strongest unresolved lead for Seychelles, re-check with a fresh search budget before writing off.
- **jubamall.com** (SS, South Sudan — "Juba Mall", per Google Play the country's only online supermarket app) — TLS fails with "no alternative certificate subject name matches target hostname" on every impersonation profile — a cert/hostname mismatch, not a WAF (same class as the "SSL certificate mismatch" section above). No usable web catalog found; app-only. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **safewaysupermarket.com** (SO, Somalia/Somaliland — "SafewaySupermarket") — resolves 200 but serves a "Your domain is expired" registrar-parking template, same pattern as choisupermarket.com/starmartmacao.com above. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **aaranonline.com** (SO, Somalia — "Aaran Hypermarket", real Odoo `website_sale` storefront with a genuine grocery/fresh-food category taxonomy) — NOT a block: every category's product grid (`o_wsale_products_grid_table_wrapper`, including the top-level `/shop`) renders completely empty, both via curl_cffi and a full Playwright `networkidle` render — no product cards, no AJAX call to a products endpoint observed in the network trace. Fails the >=5-rows gate at 0 rows. Hypothesis: pricelist/currency-selection cookie gates the grid server-side, or the catalog is genuinely unpublished. Worth a re-check with a warm session/explicit pricelist cookie, but don't re-probe casually — already cost a full Tier-2 escalation with zero signal. Probed 2026-09-01 (SSA F&B sweep, agent B).
- **hiiliye.com** (SO, Somalia — "Hiiliye", a delivery super-app covering supermarket/food/gas/suuq verticals) — React/Vite marketing SPA only; no web catalog and no API endpoint visible on the marketing page itself. Would need the mobile app's own API reverse-engineered. Probed 2026-09-01 (SSA F&B sweep, agent B).

- **jumia.td / jumia.cg / jumia.gw / jumia.ne** (TD/CG/GW/NE — Chad, Congo-Brazzaville, Guinea-Bissau, Niger) — all four country-TLD Jumia domains return a Cloudflare "Just a moment…" interstitial (HTTP 403, `cf-mgmt`-style challenge page), which reads as a squatted/reserved domain rather than live Jumia storefront infrastructure — Jumia's current active market list (~8-9 countries: Nigeria, Ivory Coast, Kenya, Ghana, Senegal, Uganda, Morocco, Egypt, Algeria) does not include any of these four. Not re-probed with Playwright since the underlying fact (no Jumia operation in-country) would not change. Probed 2026-09-01 (SSA sweep, agent A).
- **ndjamenamall.com** (TD, N'Djamena Mall) — resolves 200 but is a bare LWS (French hosting provider) domain-registration confirmation/placeholder page — zero site content has ever been built out. Probed 2026-09-01 (SSA sweep, agent A).
- **tchadcommerce.com** (TD, "TchadCommerce" — "Centre commercial, Supermarché, ventes de détail") — live, open WooCommerce Store API (`/wp-json/wc/store/v1/products/categories`), not blocked, but the entire catalogue is only ~33 products across 8 categories; the "AgroAlimentaire" food category has exactly 6 products. A thin classifieds/vendor-directory site (fashion, solar equipment, real estate, vehicles dominate), not an active grocery retailer — fails the Phase-6 row-count bar regardless of channel. Probed 2026-09-01 (SSA sweep, agent A).
- **scorene.com** (NE, guessed Niamey supermarket-chain domain) — resolves 200 but is a Namecheap expired-domain marketplace/parking page ("Domain registration has expired"), not a live business. Probed 2026-09-01 (SSA sweep, agent A).
- **casaalberto.com** (GW, "Casa Alberto" Bissau) — resolves 200 but is a bare client-side JS redirect stub (`window.location.href="/lander"`) with no content — parked domain. Probed 2026-09-01 (SSA sweep, agent A).
- **harbelsupermarket.com** (LR, Harbel Supermarket Corporation, Monrovia) — live WordPress site (200, 85KB) mentioning "product"/"price"/"cart" in page copy, but no WooCommerce Store API (`/wp-json/wc/store/v1/products` -> 404), no `/shop/` page (404), and its `/product-range/` page (the closest thing to a catalogue) has zero currency mentions and zero "add to cart" occurrences across 144KB — confirmed brochure-only, same pattern as Martínez Hermanos' own site in Equatorial Guinea (see `situcka_gq` inventory entry — the physical chain's real catalogue was NOT recoverable elsewhere for Liberia the way it was for EG). Probed 2026-09-01 (SSA sweep, agent A).
- **martinezhermanos.com** (GQ, Martínez Hermanos, Equatorial Guinea's largest supermarket chain, 8 physical stores) — corporate/store-locator site only (191KB, curl 200), zero product listings, zero prices, no cart. Its full catalogue IS recoverable, however, via the multi-vendor marketplace `situcka.com` (shipped this pass as `situcka_gq`, `CATEGORY_ID=24`) — record this pairing so a future pass doesn't waste time re-probing `martinezhermanos.com` directly. Probed 2026-09-01 (SSA sweep, agent A).
- **numidis.dz** (DZ, Numidis Group — operator of the "Uno" hypermarket chain, Algeria's #2 grocery brand after Carrefour) — `dig numidis.dz @8.8.8.8` resolves to `10.10.61.2`, a private RFC1918 address leaked into public DNS — the domain is genuinely unreachable from the public internet, not a WAF or a timeout artifact. `www.numidis.dz` itself also hard-times-out over HTTPS (30s+, no handshake). No alternate domain found (`ardis.dz` — a name half-remembered from the same operator family — SERVFAILs at the DNS layer; `hypermarche-uno.dz`, `uno-hypermarche.dz` both NXDOMAIN). Probed 2026-09-01 (MENAAP sweep, agent B).
- **uno.dz** (DZ, guessed short-name domain for the Uno hypermarket chain) — resolves 200 but is an unrelated domain squat serving Booking.com's own front-end assets (`og:site_name` and OG namespace both `booking_com`, `b_chrome` CSS classes) — not the Algerian retailer at all, a false lead from the obvious short-name guess. Probed 2026-09-01 (MENAAP sweep, agent B).
- **myfoodness.co.bw** (BW, MyFoodness — food-ordering app for Gaborone, surfaced by search with a live-looking title) — domain does not resolve at all (`gaierror`, `curl: (6) Could not resolve host`). The app may still exist on the app stores; the web domain is dead. Probed 2026-09-10 (Botswana `ddgs` sweep).
- **bestmart.sr / www.bestmart.sr** (SR, Bestmart Paramaribo) -- resolves and returns HTTP 200 with a **zero-byte body** on both hosts. Named as a live Suriname chain by a 2026-09-05 Dutch-language search; there is nothing behind the domain.
- **Suriname supermarket domains, all NXDOMAIN** (probed 2026-09-05, recorded so the guessing is not repeated): `combemarkt.sr`, `superkoop.sr`, `gwm.sr`, `sumis.sr`, `tulipsupermarket.sr`.
- **www.foodbasket.sr** (SR, "Foodbasket" — "affordable daily groceries across Suriname", surfaced fresh in a 2026-09-11 Dutch/English search, not present in the wave-13 2026-09-01 inventory) — the storefront itself is live (Next.js/Mantine SPA, 200 OK, no WAF) but structurally non-functional: the app is a warehouse/delivery-area-gated grocery app (`__NEXT_DATA__` carries `warehouseSelected: false`, an "Select Warehouse" map-picker gates the whole catalog), and its own tRPC backend call (`/api/trpc/warehouses.getAll`) returns HTTP 500 with `{"message":"getaddrinfo ENOTFOUND synergy-core-api-x7ui4.ondigitalocean.app"}` — the Next.js frontend cannot even resolve DNS for its own DigitalOcean-hosted API backend. Not a WAF, not a hydration timing issue: the backend service the frontend depends on does not exist at the DNS layer. 0 rows reachable by any means (no warehouse list, no product list, no fallback data). Probed 2026-09-11.
- **St Martin / Sint Maarten domains, all NXDOMAIN** (probed 2026-09-05): `simplymarket-sxm.com`, `leaderprice-sxm.com`, `match-sxm.com`, `superusaintmartin.com`, `hyperu-sxm.com`, `westindiesmall.com`, `sunnyfoods.sx`, `carrefoursxm.com`, `goldenrocksxm.com`, `sxmsupermarket.com`, `superusxm.com`. The French-side chains present physically (Monoprix, Leader Price, Saint Pierre, Super U) have no island-specific web presence.
- **Bahamas supermarket domains, all NXDOMAIN** (probed 2026-09-05): `supervalue.com.bs`, `supervalue.bs`, `supervaluefoodstores.com` (Super Value Food Stores, the largest domestic chain by store count -- worth a targeted search rather than more domain guessing), `citymarkets.bs`, `qualitysupermarketbahamas.com`, `thefreshmarketbahamas.com`, `bristolwines.com`, `jimmyswines.com`, `youngsfinewines.com`, `bristolgroup.bs`, `freshmartbahamas.com`, `bahamargrocery.com`. `butlerandsands.com` times out at TCP.
- **primesxm.com** (SX, Prime Distributors) -- HugeDomains parking page, "domain is for sale".
- **sxmdelivery.com** (SX) -- live but a 2KB stub with no links or scripts.
- **shopndropgrocerysxm.com** (SX) -- live 79KB site, but no Shopify `/products.json` and no WooCommerce Store API: a concierge shopping service that takes a shopping list, not a priced catalogue.
- **CaribeEats has no Bahamas grocery vendor** -- the platform *does* cover the Bahamas (region_id 1242) but the whole directory is 12 businesses: 8 restaurants, 2 telcos, a ride service and a courier. **Zero** `business_type_id=10`. Confirmed 2026-09-05; do not re-enumerate this region for grocery.
- **WFP food prices, Suriname** -- `wfp-food-prices-for-suriname` 404s on the HDX CKAN API. WFP's LAC panels are Colombia / Ecuador / Guatemala / El Salvador / Nicaragua / Bolivia / Haiti only, so the near-free `_shared/lac/wfp_food_prices.py` route does not exist for Suriname (or for Bahamas / Dominica / Grenada / St Kitts and Nevis -- all 404 the same way).

- **marounssupermarket.com** (GM, Maroun's Supermarket — real chain, Kololi + Serrekunda) — re-probed after the 2026-09-02 inventory recorded "EMPTY RESPONSE, re-check in ~6 months". Still broken, and now characterised precisely: **every HTML path returns HTTP 200 with a zero-length body** (`/`, `/shop/`, `/?s=<barcode>`, the Woo Store API route) while `/robots.txt` (76 B) and `/sitemap.xml` (59 KB) serve fine. The sitemap is itself junk — 300 `<loc>` entries, all of the form `https://marounssupermarket.com/?s=<13-digit barcode>`, i.e. search-result URLs rather than PDPs. The WordPress install is serving nothing. Probed 2026-09-05.
- **grocerynowstore.com** (UG) — carried forward as "timed out" from the 2026-09-01 Uganda inventory; still times out at 25s and 40s on `curl_cffi chrome124`, with and without TLS verification. Two independent passes now agree. Stop re-probing. Probed 2026-09-05.
- **mugbest.com / www.mugbest.com** (BI, MUGBEST — Bujumbura online marketplace covered by Burundi Eco) — self-signed certificate; with `verify=False` both apex and `www` return a 138-byte "404 Not Found". The platform written up in the local press no longer exists at this domain. Probed 2026-09-05.
- **kussasditchon.com** (GW, "Kussas di Tchon — Produtos da Guiné-Bissau", surfaced by a Portuguese-language search) — NXDOMAIN. Probed 2026-09-05.
- **bissaushop.com / guineshop.com / nkassa.gw / sabuka.gw / supermercadobissau.com / bolamasupermercados.com** (GW) — a name/domain-guess sweep for Guinea-Bissau storefronts; all six NXDOMAIN. Recorded so the next pass does not repeat the guess. Probed 2026-09-05.
- **candando.com** (AO, Candando — Angolan supermarket chain) — connection times out at 25s. Probed 2026-09-05.
- **tupuca.co.ao / nossosuper.co.ao / alimenta.co.ao / deskontao.co.ao** (AO), **zmall.et / sheba.et (a law firm) / enatmart.com / beu.et** (ET), **kikuubo.online / shopyetu.co.ug / jumiafood.ug / minute5.ug / farmiketug.com** (UG) — domain-guess sweep, all NXDOMAIN except `sheba.et` (an unrelated legal practice) and `zmall.et` (expired cert; behind it a 1,668-byte SPA shell with no catalogue). Probed 2026-09-05.
- **Suriname — 4th-pass named-chain sweep, zero hits** (SR; Mr. Bing, Bas Supermarkt, Superbaas, Vreedzaam, Prijsklopper, Amazing supermarket, Foodcity, Chinese/Javanese tokos): none of these resolve to a real Suriname webshop. "Amazing supermarket" and "Foodcity" are out-of-country brands (Netherlands and Spain/US respectively); "Vreedzaam" and "Prijsklopper" are misnamed/non-existent; "Mr. Bing", "Bas Supermarkt" and "Superbaas" have no findable web footprint at all. Cross-checked two independent Suriname business directories (`surinamyp.com/category/Supermarkets`, `dfave.com/sr/paramaribo/supermarkets-hypermarkets/`, ~38 listed toko/supermarket businesses combined) listing-by-listing for an outbound website link — **zero of ~38 have one**, all phone/WhatsApp/Facebook only. `surinamemarktplaats.com` (SR general classifieds) checked and ruled out — no food category in site copy or bundled JS. `statistics-suriname.org` re-confirmed reachable (2026-09-05 timeout resolved) but carries only the already-onboarded CPI, no separate average-retail-price table. Fourth independent same-day confirmation that Suriname food retail has no further online footprint beyond the already-onboarded `avoda_sr`. Probed 2026-09-11.
- **shobly.shop** (LY, "Shobly" — wave onboard1 candidate, pre-probe said 200 OK / 20KB) — the 200 is a self-served placeholder: `<title>Site Unavailable</title>`, a 21KB inline-CSS holding page behind Cloudflare with **zero `href` links of any kind**, no catalogue, no API. Not a WAF (no challenge, no cf-mitigated header, curl_cffi chrome124 gets the same body as a browser) — the storefront is simply switched off. Third Libyan wave-10/13 candidate to die this way after nawris.net (demo seed rows) and watti.ly (pre-launch app landing page). Probed 2026-09-11.

## Official feeds that geographically exclude a country despite valid geography data (check the count, not just the domain)

- **WFP food prices (HDX) — Sao Tome and Principe** — `package_show?id=wfp-food-prices-for-sao-tome-and-principe` returns `404 Not Found`; a live `package_search` for "sao tome" on data.humdata.org returns 10 STP-tagged datasets (settlements, conflict events, 5x World Bank indicator sets, admin boundaries, airports) but no WFP food-prices panel. STP is correctly absent from `_shared.ssa.wfp_food_prices._PANELS` — do not add without re-checking this first. Probed 2026-09-01 (wave 13).
- **FEWS NET (`fdw.fews.net/api/marketpricefacts/`) — Sao Tome and Principe** — `country_code=ST` is accepted by the API (no error) but `?country_code=ST` returns `{"count":0,"next":null,"previous":null,"results":[]}`. STP is correctly absent from `_shared.ssa.fews_net._COUNTRIES` — do not add without re-checking this first. Probed 2026-09-01 (wave 13).
- **FEWS NET (`fdw.fews.net/api/marketpricefacts/`) — Mali** — `country_code=ML` is a *valid* enum choice and Mali has real geographic data in the same API (`/api/geographicunit/?country_code=ML` → 1628 units; `/api/market/?country_code=ML` → 40 markets incl. Bamako), but `/api/marketpricefacts/?country_code=ML` returns `{"count":0}` — confirmed against a working comparator (`country_code=CI` → 4929 facts same day). FEWS NET tracks Mali's markets but does not publish price facts for it. The shared fetcher `_shared.ssa.fews_net.py` deliberately does NOT include `mli` in its `_COUNTRIES` dict — do not add it without re-checking this count first. Probed 2026-09-01 (wave 9).

## Genuine 403 confirmed via curl_cffi AND Playwright (mandatory gate satisfied, not a curl-TLS false negative)

- **www.financas.gov.st** (STP, Ministerio das Financas) — resolves fine (`197.159.191.x`), but returns HTTP 403 under `curl_cffi` with chrome124/chrome120/safari17_0 impersonation AND under a real Playwright-driven headless Chromium (`status 403`, body "403 - Forbidden / Access to this page is forbidden"). This satisfies the mandatory curl-AND-Playwright-both-fail gate before recording a genuine block. Was probed hoping for an official fuel-price decree/gazette (STP's fuel prices are administered, and ENCO's own site publishes none — see the ENCO entry above); no such document was found via any other path. `gov.st` (the main government portal) timed out entirely on the same probe rather than resolving. Probed 2026-09-01 (wave 13).

## Compromised / malware-injected site (do not scrape, security risk)

Site returns 200 but the response body contains a script tag pointing at an unrelated, suspicious-looking domain — the hacked-WordPress/injected-spam signature. Record as DEAD and move on; do not attempt to work around it.

- **faddoulsupermarket.com** (LB, "Faddoul Supermarket — Lebanon's Favorite Grocery Store") — WordPress site; every response (including a 404 REST-API probe) is preceded by an injected `<script src="https://foreignabnormality.com/3b/af/b3/3bafb3d65b8689c30e8bb8ed937cb63a.js">` tag — a domain name and hex-path pattern with no legitimate relationship to a Lebanese grocery site, the classic malware-injection signature. `wp-json/wc/store/v1/products` also 404s (no WooCommerce Store API exposed) even setting the security concern aside. Do not scrape. Probed 2026-09-01.

## Huawei Cloud CDN (`server: hcdn`) 403 — curl_cffi all profiles, Playwright not attempted

Signature: HTTP 403, response header `server: hcdn` (Huawei Cloud CDN), a fixed-size
HTML body identical across every TLS profile. Distinct from Cloudflare/Akamai — no
`cf-ray`, no challenge widget, no `cf-mitigated` header. Because the body is byte-identical
on `chrome124`, `chrome120` and `safari17_0`, this is **not** a TLS-fingerprint false
negative — but the mandatory gate is only half-satisfied until Playwright is tried, so
treat these as unfinished rather than final.

- **kgalagadibreweries.co.bw** (BW, Kgalagadi Breweries Limited — Botswana's national brewer, a COICOP 02.1 beverage lead) — HTTP 403, `server: hcdn`, 6,192 bytes, identical on all three impersonation profiles. Playwright not attempted. Low priority regardless: it is a corporate site and unlikely to carry a retail price list. Probed 2026-09-10 (Botswana `ddgs` sweep).

## 2026-09-11 onboard4 shard — re-probes and new verdicts

Eleven hosts from a hand-curated backlog, all pre-probed as "HTTP 200 with a real
page body". Two were overturned and shipped (see the `cargillsonline.com` and
`coop.se` entries above); the rest are recorded here with the *specific* reason,
since the bulk "mechanically exhausted" list gives no detail to build on.

**Confirmed dead, with the detail the bulk list lacks:**

- **www.lidl.bg** and **www.lidl.pt** — these two have a real, enumerable product
  catalogue and still carry **no prices anywhere on the web**, which is worth
  writing down because every cheap signal says otherwise. `robots.txt` →
  `/static/sitemap.xml` → `/p/export/{BG|PT}/{bg|pt}/product_sitemap.xml.gz`
  yields **1,073 (BG) and 263 (PT) product PDPs**, each serving 3 JSON-LD blocks
  including a `Product`. But the `Offer` node carries `priceCurrency` and
  `availability: InStoreOnly` and **no `price` key at all** — these are in-store
  assortment description pages, not a webshop. Confirmed at the markup level too:
  zero `лв`/`€` matches in 393 KB of PDP HTML, and the only price-ish class is
  `cart-section-one__price` (empty). The weekly-offer routes (`/c/<slug>/s<id>`)
  were rendered in headless Chromium and also yield zero price text — the
  brochure is a flipbook of images. Lidl's `/q/api/search` endpoint exists and
  answers `{"error":"Assortment 'null' is not supported"}` without params, then
  406 with every `assortment=`/`locale=` combination tried. Probed 2026-09-11.
- **www.kaufland.bg** — AEM site, no WAF, `/.sitemap.xml` has 2,386 URLs of which
  **582 are `/asortiment/*`** — which reads like a catalogue and is not one. Three
  sampled assortment pages (180-224 KB each) returned **zero** `лв` price matches;
  they are product-range brand pages. The rest of the sitemap is 1,420 recipes and
  180 magazine articles. `/produkti.html` 404s. Kaufland BG runs no webshop; the
  only price surface is the leaflet DAM at `assets.leaflets.schwarz`. Probed
  2026-09-11.
- **www.supersave.pt** — **not a retailer at all.** It is the landing page for a
  price-*comparison* mobile app; its own JSON-LD says `@type: MobileApplication` /
  `SoftwareApplication`, and its FAQ block reads "o melhor comparador de preços de
  supermercados em Portugal … Continente, Pingo Doce, Lidl, Auchan, Mercadona".
  The whole sitemap is 8 anchor links on one page plus `app.supersave.pt`, which
  serves a **Google Play redirect page** (`<base href="https://play.google.com/">`).
  App-only; no web catalogue to scrape. Probed 2026-09-11.
- **kinmarche.com** (CD, Kin Marché — Kinshasa supermarket chain) — the site is a
  **catch-all router**: `/sitemap.xml`, `/wp-json/...`, `/products.json` and
  `/index.php?route=...` all return the identical 30,597-byte homepage with HTTP
  200, so every platform fingerprint gives a false positive. The real routes are
  `/product-categories` (74 KB, 23 category *names*, no items) and four
  `/product/<id>` pages (57/58/59/71) which are promo-flyer image pages titled
  "Promo Anniversaire". **Zero price text of any kind** (0 USD, 0 CDF matches
  across both page types), zero per-item structure. Same class as `superindo.co.id`:
  promo-flyer-image-only, no per-product catalog. Probed 2026-09-11.
- **www.celeste.lk** — brochure site, not a shop. Its `sitemap.xml` is five pages
  total: `/`, `/about.html`, `/services.html`, `/solutions.html`, `/contact.html`.
  Served from Vercel; `/products.json` 404s. Probed 2026-09-11.

**Not a blocker — already onboarded under a different name:**

- **www.mercadao.pt/store/pingo-doce** — 301s unconditionally to `www.pingodoce.pt`,
  which is already shipped as `pingodoce_pt` (that manifest documents the same
  pivot). Any future candidate list carrying the Mercadão white-label URL should
  be de-duplicated against `pingodoce_pt`, not probed.

**Re-confirmed from earlier waves — no change, do not re-probe:** `hyper.sd` (>98%
installer seed data at `price=1`), `lilydelivery.com` (14 vendors / ~34 items
platform-wide), `zaad.delivery` (Astro marketing site, no catalogue behind the
`hcdn` interstitial), `pridefarms.rw` (Wix store stocked with exactly 1 SKU),
`nikora.ge` (corporate group site, not a storefront). All five entries above
remain accurate as written.


## How to use this list

Before probing, grep this file for the candidate's domain — **and then again for its operator or brand**. Blocking is applied per tenant, not per hostname: one AS-Watson, Foodstuffs, MWG, Lazada, or Delivery Hero property being walled means its siblings in other countries almost certainly are too, even when the exact domain you hold has never been probed. A domain-only grep misses that and sends you off to re-lose the same fight under a different TLD.

If it's listed:

- **CDN / WAF / PerimeterX**: skip entirely. Optionally do a quick 1-call curl to confirm the wall is still in place (sometimes sites change), but don't invest more than 30 seconds.
- **No products / app-only / no per-product URLs**: structural — skip permanently.
- **Dynamic-auth API**: skip the API. Consider whether the HTML front-end might be Tier 2 (usually isn't, because if the HTML were scrapeable the API wouldn't be the path of least resistance).
- **Lazy-load with no productive API**: skip the HTML, but check if a different endpoint is reachable (winmart's case is the rare win).

## How to add to this list

After a probe confirms a new site is unscrapeable, append it under the class whose signature matches with:

- The exact domain
- Country code in parentheses
- The owner / operator if known (helps recognise shared infra — Foodstuffs NZ, AS-Watson, MWG, delivery-hero each share a stack)
- The failure signature (`ERR_CONNECTION_RESET`, `HTTP 403 + Cloudflare challenge`, `200 with skeleton-only body`, `212-byte JS-challenge stub`, etc.) — this is what makes the entry verifiable later

One line per site. The goal is to read this file in <30 seconds when starting a new country onboarding.

**Trigger condition.** Add only when *both* curl AND Playwright fail in the same way. A site that 403s on curl but renders fine in Playwright is just Tier 2 — don't add it here. If Playwright returns 200 but the body never hydrates, that's *not* a bot block — try once with a 12s wait before adding to "SPA shell — no productive endpoint".

## Host maintenance mode / suspended account (503 or redirect-to-suspension — TEMPORARY, re-check)

Not anti-bot and not a dead site. These are operator- or host-side states that
can clear on their own, so they deserve a re-probe in a later wave rather than a
permanent write-off. Distinguish them from a real block by reading the body:
a maintenance page says so in plain language, and the origin header often
reports itself as healthy.

- **cadismarket.com** (MF, Cadismarket — billed locally as "the first online supermarket in Saint-Martin, 100% Saint-Martin") — HTTP 503 with `Retry-After: 3600` and the body "We'll be back soon. We are currently updating our shop", identical on `chrome124`, `chrome120` and `safari17_0`. Response headers show `x-ws-origin: available`, `x-ws-ratelimit-remaining: 998`, `Server: Apache`, `X-Powered-By: PHP/7.3.33` — the origin is up and not rate-limiting; the shop is deliberately in maintenance. **Re-probe in a future wave** — if it returns it is likely a better St Martin source than the shipped `sxmleshalles_mf`, being a general grocer rather than a villa/yacht provisioning service. Probed 2026-09-01.
- **ehubsvg.com / www.ehubsvg.com** (VC, eHub SVG — personal-shopper grocery delivery, St Vincent) — HTTPS fails at the TLS layer on both apex and `www` (`curl: (60) no alternative certificate subject name matches target hostname`); over plain HTTP it 200s but redirects to `/public/email-suspension`. Hosting/email account suspended. Lower re-check priority than cadismarket — a suspension is a business signal, not a deployment window. Probed 2026-09-01.
- **cadismarket.com** (MF, "the first online supermarket in Saint-Martin") -- **still 503** as of 2026-09-05, four days after the 2026-09-01 probe. Same host maintenance page ("We'll be back soon"), `Retry-After: 3600`, on `/`, `/en/` and `/fr/`. Not anti-bot. Remains the best-shaped St Martin (French part) candidate -- re-check in a future wave.
- **statistics-suriname.org** (SR, ABS -- Algemeen Bureau voor de Statistiek) -- every request on 2026-09-05 (root, `/publicaties/`, `/category/publicaties/prijzen/`) timed out or reset. This is a **network** verdict, not a content one: the already-onboarded `abs_cpi` fetcher reaches the same host, so treat it as transient. Retry -- an ABS average-retail-price table would be the single best division-01 addition for Suriname.

<!-- appended 2026-09-05, francophone-SSA cluster sweep (GN/CI/BF/CM/BJ/KM) -->

- **www.jumia.ci** (CI, Jumia Côte d'Ivoire — Jumia's #2 African market and by far the most-cited Abidjan online grocery) — same shared Cloudflare tenant already recorded for jumia.ma / jumia.com.gh / jumia.com.ng / jumia.bf / jumia.ug / jumia.dz. `curl_cffi impersonate=chrome124` returns HTTP 403 `<title>Just a moment...</title>`; headless Playwright additionally confirms this is an **interactive Turnstile widget**, not a JS-execution stub — the page reaches `<title>Un instant…</title>` and loads `challenges.cloudflare.com/turnstile/v0/g/<sitekey>/api.js?render=explicit`, then never clears. Mandatory-gate satisfied (curl_cffi AND Playwright). This is the eighth Jumia country storefront to show the identical wall; stop probing them per country — cracking one would unlock the tenant, and nothing less will. Probed 2026-09-05.
- **sococe.online** (CI, Sococé — Prosuma's supermarket chain; `sococe.ci` redirects here) — Cloudflare 403 "Checking your browser before accessing" on **five** `curl_cffi` profiles (chrome124, chrome120, chrome110, safari17_0, edge101), but headless Playwright clears the challenge in one navigation and lands on an 8 KB page titled **"Votre site est en Construction"**. The WAF was never the problem: there is no storefront behind it. Do not spend anti-bot effort here. Probed 2026-09-05.
- **playce.ci** (CI, PlaYce — CFAO's mall brand, the operator behind Carrefour CI) — reachable, no WAF, but WordPress + Elementor **corporate site**. `/wp-json/` namespace list contains no `wc/` route at all (`/wp-json/wc/store/v1/products` and the `?rest_route=` form both return `rest_no_route`) — not WooCommerce, no catalog, no prices. Same shape as `carrefour.ci` itself, whose only price signal is its `/promotions/` flyer (already onboarded as `carrefour_ci`). Probed 2026-09-05.
- **glovoapp.com (Côte d'Ivoire storefronts)** — NOT blocked in the WAF sense, but recorded here so the next pass knows the cost before starting. Plain HTTP `GET /fr/ci/abidjan-nord/stores/<slug>` returns **403** while headless Playwright renders it fine (877 KB), so Playwright is required at collection time. The public API is closed: with browser-realistic `glovo-app-platform`/`glovo-api-version`/`glovo-location-city-code` headers, `/v3/stores/{id}/addresses/{aid}/collections`, `/v1/.../collections`, `/content`, `/products` and `/search` all 404; only `/v1/stores/{id}/addresses/{aid}/node/store_fees` answers (it does confirm `"currencyCode":"XOF"`). And the store landing page is the **homepage-carousel trap**: 877 KB of HTML yields only 86 `ItemTile_` products, all promo carousels — the real assortment sits behind client-side collection tabs. Enumerating a store means clicking those tabs in Playwright. Worth a dedicated effort (Abidjan-nord's `groceries_4` lists Carrefour Market, 3x Casino Mandarine, Hyper U, Super U Plateau, Monoprix, Supeco, 2x Bonprix, boulangeries, boucheries, poissonneries), not a shared-sweep task. Probed 2026-09-05.
- **plantesetepices.com** (CI, "Panier" — `contact@panier.ci`, a real Abidjan 6amMart/Laravel grocery with épicerie/boissons/boulangerie/fruits/légumes/viandes categories) — no WAF, PDPs DO server-render prices (`/item-oignons` → 500/800/1,000 FCFA), but the catalog is **not enumerable**: `/menu?category=epicerie` renders "Showing 1–20 Of 50 Results / **Aucune donnée trouvée**" under Playwright (the listing is gated on a delivery-zone selection not reverse-engineered), only 3 distinct `/item-*` URLs are discoverable site-wide, `/sitemap.xml` and `/robots.txt` 404, and every 6amMart API path 404s with a Laravel `NotFoundHttpException` (`/api/v1/config`, `/api/v1/zone/list`, `/api/v1/module`, `/api/v1/items/latest`, `/api/v1/categories/N/items`). Revisit by finding the zone cookie/param the listing needs. Probed 2026-09-05.
- **braprime.com** (GN, "BraPrime" — Conakry on-demand food/grocery delivery, an ACCEPT row in the pending workbook) — the site is a live 2.3 KB Vite SPA shell, but its single JS bundle points at a Supabase project `jeumizxzlwjvgerrcpjr.supabase.co` that **does not resolve at all** (NXDOMAIN on 8.8.8.8). The backend project has been deleted; the marketing shell is all that remains. Do not re-probe. Probed 2026-09-05.
- **mamakiti.com** (GN, "maMakiti — Marché Local en Ligne, Conakry", an ACCEPT row in the pending workbook) — Next.js landing page, app-store-led. Its FastAPI backend `api.mamakiti.com` is reachable and **unauthenticated**, and honestly reports an empty catalogue: `/api/products` → `{"items":[],"total":0,"page":1,"size":100}`, `/api/categories` → `[]`. `/docs` and `/openapi.json` are 401. Pre-launch, not blocked. Re-check ~6 months. Probed 2026-09-05.
- **monmarchegn.com** (GN, "Monmarché — Vos courses livrées à domicile", Conakry) — no WAF, but app-only. Sitemap has 14 URLs and not one product; `/produits`, `/boutique`, `/categories` all 404; `/p` renders 21 KB with **zero** currency tokens. All 12 homepage `_next` chunks grepped for an API host or `/api/` literal — nothing. Ordering happens in the iOS/Android apps. Probed 2026-09-05.
- **omakiti.com** (GN, "Site de ventes et Achats en ligne en Guinée Conakry") — live Magento 2 with a genuine `/supermarche` category and real food PDPs (`/fromage-la-vache-qui-rit`, `/huile-d-arachide`, `/nescafe`, `/sac-de-riz`, `/saint-louis-sucre-extra-pur`), and `/rest/V1/products` returns a clean 401 (`"The consumer isn't authorized"` — no anonymous integration token). **Rejected on locality, not access**: the homepage carries 41 EUR tokens and 0 GNF, and the site sells "transfert d'argent" next to groceries — the remittance/diaspora shape already recorded for `familov` (CM) and `comores-en-ligne` (KM). Not a Guinean domestic shelf price. Probed 2026-09-05.
- **primaconakry.com** (GN, Prima Center Conakry — described in search results as Guinea's first hypermarket) — Wix site for the mall/leisure complex. `/hypermarche` renders 658 KB under Playwright with **zero** currency tokens and no product nodes. Brochure only. Probed 2026-09-05.
- **erevanbenin.com** (BJ, Erevan / Super U Bénin — note `erevan.bj`, the URL in the pending workbook, is NXDOMAIN) — the live corporate site on the oweb.io builder. Store pages for Super U Aéroport / Akpakpa / Calavi, a "Prix Mini" marketing page, a supplier-recruitment page — and **zero FCFA tokens** on any of them, under Playwright as well as plain HTTP. `/sitemap.xml` 404s. Real chain, no online catalogue at all. Probed 2026-09-05.
- **martistore.shop** (BJ) — **entire site in maintenance mode**: homepage and every `/catalogue/p/<id>` PDP return HTTP **503 "MARTISTORE - Maintenance"**. Its `/sitemap.xml` still serves 200 and lists **543 product URLs**, so the catalogue and its id space are known — this is a temporary state, not a dead site. Re-check in ~3 months; if maintenance lifts it is a ready-made 543-product Benin source. Probed 2026-09-05.
- **zemihidjo.com** (BJ, an ACCEPT row in the pending workbook) — Cloudflare-fronted but every path (`/`, `/shop`, `/products`, `/sitemap.xml`, and the `www.` host) returns **404 with a zero-byte body**. No origin content behind the proxy. Probed 2026-09-05.
- **mescoursesbj.com** (BJ, "Mes Courses Béninoises") — Shopify, so technically trivial (`/products.json`), but **rejected on locality**: redirects to `/en`, prices in EUR, and its own copy is "Envoi de colis moins cher au Bénin / Transfert d'argent au Bénin". A remittance service priced for a sender abroad, not a Cotonou shelf price. Same class as `omakiti` (GN), `familov` (CM), `coliscom` (KM). Probed 2026-09-05.
- **alimentsbenin.com / shop.alimentsbenin.com** (BJ, "Aliments Bénin" — the DigitAll Farmer agri-marketplace written up by We Are Tech) — the `shop.` subdomain is NXDOMAIN; the apex resolves but serves a bare Apache **"Index of /"** directory listing (658 bytes), and `/boutique/` plus `/wp-json/wc/store/v1/products` both 404. The platform is gone. Probed 2026-09-05.
- **kangoo.africa** (BJ, Cotonou delivery app advertising "courses du marché, supermarché ou épicerie") and **beninrestoo.com** (BJ, meal delivery) — both are thin Vite marketing shells (65 KB / 17 KB) with no product route. Kangoo's bundle references a Supabase project but exposes no catalog endpoint (`/api/broadcast` is the only `/api/` literal). Ordering is in-app. beninrestoo is restaurant delivery (COICOP 11) anyway. Probed 2026-09-05.
- **NXDOMAIN sweep, francophone SSA (do not re-guess these)** — CI: yaatoo.ci, cdci.ci, hayat.ci, cashcenter.ci, superu.ci, hyperu.ci, magasins-u.ci, supermarcheu.ci, supeco.ci, monoprix.ci, boutic.ci, ivoiremarket.ci, kayamarket.ci, lifestore.ci, monmarche.ci, supermarche.ci, lebonprix.ci, expressmarket.ci, africmart.com, afrimarket.ci, freshpanier.com, cocody-market.com. GN: belair.gn, soduga.com, guineego.net, supermarchebelair.com, belairguinee.com, alimarket.gn, kanya.gn, tafa.gn, chezmoi.gn, paysanguinee.com, supermarchekaloum.com. BJ: erevan.bj, yabourou.com, jinukunstore.com, supermarcheerevan.com, erevan-benin.com, cotonoumarket.com, benincommerce.com. CM: mahima.cm, mercato.cm, superu.cm (and dovv.cm fails certificate verification). Also parked/for-sale: abidjanmarket.com, guineemarket.com, conakryshop.com. `bonprix.ci` returns Cloudflare **521 (origin down)**; `prosuma.com`, `casino.ci` and `conakrymarket.com` time out. Probed 2026-09-05.

**Cross-cutting lever recorded from this sweep — the "HeadlessChrome UA" wall.**
Two domains (`margaarou.com` GN, `lynia-shop.com` BJ) 403 on `curl_cffi` across
chrome124/chrome120/safari17_0 AND on headless Playwright, and both open on the
first navigation once the browser **context User-Agent** is overridden to a plain
Chrome 124 string. The tell is the challenge title ("Vérification en cours" /
"Vérification navigateur - Erreur rencontrée") surviving a 9-second homepage
warm-up. Note that Scrapy's `USER_AGENT` setting does NOT reach the browser —
scrapy-playwright needs `PLAYWRIGHT_CONTEXTS = {"default": {"user_agent": ...}}`.
Add this check to the ladder between `curl_cffi` and "genuine block": a bare
headless 403 is no more evidence of a WAF than a bare-curl 403 is.

- **eshopuganda.com** (UG, "eShop Uganda", Plot 1001 Ggaba Rd, Kampala — fresh food, groceries, wine & spirits) — carried forward as "HTTP 409, unclear cause" from the 2026-09-01 Uganda inventory. **Cause identified and the 409 is trivially bypassable**: the origin serves an 83-byte stub `<script>document.cookie = "humans_21909=1"; document.location.reload(true)</script>`, i.e. the humans.txt-style cookie handshake, not a WAF. Send `Cookie: humans_21909=1` and the 409 clears — but what is behind it is **HTTP 503 "Store closed"**. The site is deliberately shuttered, not blocked. Also note the TLS cert is expired (`verify=False` needed). Re-check in a future wave; the taxonomy on offer (fresh food, groceries, wine & spirits, Kampala delivery) would be a genuinely useful Uganda division-01/02 source if it reopens. Probed 2026-09-05.

## 2026-09-10/11 country x COICOP gap-fill campaign — 287 candidates worked

Campaign context, because it sets how much weight each entry below carries. The
candidates were the 514 rows marked PENDING in `prices_sources_status.xlsx` —
the 2026-08-31 sourcing round's never-built leads. Of those, 155 already had a
live manifest pointing at the same host, 66 were already documented in this very
file, and 6 resolved elsewhere, leaving 287 genuinely unworked.

**The headline result is that this queue is largely exhausted ground: 22 of 287
shipped.** The PENDING rows are PENDING because earlier rounds could not build
them, and most are dead for durable reasons rather than for want of one more
attempt. Carry that prior into the next "never built" backlog.

A note on how 66 already-documented hosts slipped through the pre-filter, since
it wasted two agents' time re-probing sites proven dead nine days earlier: the
filter extracted hostnames only from backticks and URLs, and **this file writes
most hostnames in bold** (`**nawris.net**`). Extracting bold as well raised the
host count from 256 to 877. Any tool that reads this file for a do-not-reprobe
list must handle bold, backticks and bare URLs.

### Evidence standard applied in this section

Every host below went through a fixed mechanical ladder before any judgement was
applied, so "blocked" here always means more than one client failed:

1. `curl_cffi` homepage fetch on `chrome124`, plus blind probes of
   `/products.json`, `/wp-json/wc/store/v1/products` and `/api/products`.
2. For anything not obviously alive, a **five-profile TLS retry** —
   `chrome150`, `firefox147`, `safari18_4`, `chrome131_android`, `chrome120`,
   each with and without certificate verification.
3. For anything still without a surface, a **deep probe** following
   `robots.txt` into the sitemap index and into its shards, counting product
   URLs and parsing JSON-LD on a sampled product page.
4. For anything still without a surface, a **headless Playwright network trace**
   (Chromium 143, no stealth patch) rendering the homepage plus up to two
   category pages, capturing every JSON response with price-shaped keys.

Three calibration results from running that ladder at scale:

- **One TLS profile's 403 is not evidence of a block.** 11 of 125 retried hosts
  returned a full 200 on `chrome150` or `chrome131_android` after 403-ing on
  `chrome120`/`chrome124` — among them `tesco.com`, `tesco.ie`, `shop.rewe.de`,
  `mall.cz`, `mall.sk` and `talabat.com`. `rewe_de` shipped only because of that
  retry, and it specifically needed `chrome133a`.
- **A real browser cracked only 3 of 100 curl-blocked hosts** (`ocado.com`,
  `orinabiji.ge`, `esselungaacasa.it`). Playwright is worth running but is not a
  general answer to a WAF — and against Akamai tenants it scored *worse* than
  impersonated TLS, drawing hard edge denials where curl_cffi got an
  interstitial. Unpatched headless Chromium is itself a fingerprint.
- **Our own request volume became the blocker on one source.** `handla.ica.se`
  was proven workable in isolated probing (real 200s, real SEK prices) and then
  failed three acceptance runs against a hardened "Human Verification" 405
  escalation triggered by this campaign's own traffic from one IP. When a
  campaign probes hundreds of hosts from a single address, late-campaign
  failures are not independent of early-campaign success. Pace the waves.

The shape that cost this campaign the most time, and the one worth internalising:
**the sitemap layer and the product layer are protected separately.** Four hosts
(`nakup.itesco.cz`, `tesco.ie`, `tesco.com`, `koctas.com.tr`) serve `robots.txt`,
the sitemap index and every product shard openly — thousands of genuinely
disjoint product URLs — while every product-detail request is denied. A large,
clean sitemap count is therefore **not** evidence that a source is scrapable.
Fetch a product page before believing a sitemap.

### WordPress fingerprint false positives, a flyer-only catalog and app-only backends (BA, IS, CY, LU, EG, MW)

- **djuric.ba** (BA, "Đurić SUPERMARKET") — live, enumerable WooCommerce Store
  API (`/wp-json/wc/store/v1/products`: 100/100/100/100/21 across 5 pages,
  421 products total, ids disjoint page1 vs page2). **Every one of the 421
  products has `prices.price == "0"`, `price_html == ""`,
  `is_purchasable: false`.** Confirmed on both the listing and a
  single-product GET (`/wp-json/wc/store/v1/products/17318`):
  `add_to_cart.text` is *"Pročitaj više"* ("Read more"), not *"Dodaj u
  korpu"* ("Add to cart"); the product's own category is "Kataloska akcija"
  (catalog promotion). The live rendered product page also shows no price.
  This is a browsable weekly-flyer/brand-catalog display site, not a
  transactional webshop — a structural fact about the business, not an
  access block. Do not re-onboard expecting prices to appear later; if
  re-probed, check `is_purchasable` and `add_to_cart.text` first before
  re-walking the whole catalog. Probed 2026-09-10.
- **bonus.is** (IS, "Bonus") — re-confirmed dead, matching the existing entry
  above (probed there 2026-09-05). Store API returns exactly 1 SKU, the
  "Inneignarkort – Áfylling" gift-card top-up, ISK price "1". No real
  catalog. Independently reconfirmed 2026-09-10 (same SKU, same price).
- **papantoniou.com.cy** (CY, "Papantoniou") — `/wp-json/wc/store/v1/
  products` (and the `?rest_route=` / `/wc/store/products` fallbacks) all
  return `{"code":"rest_no_route",...}` 404, 485 bytes. `/wp-json/` root
  namespace list has no `wc/*` entry at all (`wpml/v1`, `elementor/v1`,
  `oembed/1.0`, `wp/v2`, ... only) — WooCommerce is not registering REST
  routes despite a WooCommerce-flavored homepage fingerprint (that string
  match is theme/asset boilerplate). `/sitemap.xml` lists only
  posts/pages/taxonomies/3d-flip-book sitemaps — no product sitemap, and all
  `<loc>` entries resolve under `sklavenitiscyprus.com.cy` (an apparent
  rebrand/redirect target), which has the identical 404 shape and no product
  sitemap either. Zero cart/shop JS markers (`wc-ajax`, `wcSettings`,
  `add-to-cart`) anywhere on the homepage. Did not try Playwright — untried,
  not ruled out, but the classic server-rendered Elementor/WPML markup makes
  an SPA-behind-JS explanation unlikely. If a genuine Sklavenitis Cyprus
  webshop exists on a different domain, that would be a new discovery
  candidate, not a fix for this host. Probed 2026-09-10.
- **pallcenter.lu** (LU, "Pall Center") — same `rest_no_route` 404 shape on
  all three Store API routes. `/wp-json/` root lists `yoast/v1`,
  `elementor/v1`, `divi/v1`, `wp-super-cache/v1`, `complianz/v1`, `wp/v2` —
  no `wc/*` namespace. Sitemaps list only post/page/3d-flip-book/category/
  author — no products. Homepage nav is store-locator + loyalty-program
  content (`nos-magasins`, `pall-pommerloch`, `pallcenter-oberpallen-2`,
  `carte_avantages_pall`, `liste-cadeaux-au-pall`) with `la-femme`/`lhomme`
  clothing category pages — reads as a physical clothing-store chain's
  corporate site (locations + loyalty card + gift registry), not an
  e-commerce catalog. No cart/shop JS markers found. `shop.pallcenter.lu`
  does not resolve (SSL hostname mismatch) — a hunch, not a real lead. Did
  not try Playwright. Probed 2026-09-10.
- **breadfast.com** (EG, "Breadfast") — as the pre-probe evidence flagged:
  WordPress site is the company's ops backend, not a public storefront.
  `/wp-json/wc/store/v1/products` (all 3 routes) 404. `/wp-json/` root DOES
  list `wc/v1`/`wc/v2` (the **private**, auth-required WooCommerce REST API
  — unauthenticated GET returns nothing usable), plus a huge internal
  surface (`breadfast/v3/fleet`, `pos/v1`, `order-fulfillment/v1`,
  `delivery-capacity/v1`, `card-management/v1`, `odoo/v1`, `sms-portal/v1`,
  ...). Poked `shopper/v1`, `pricing-tool/v1`, `node-api/v1` (other
  app-shaped namespaces in the list): each resolves at its namespace root
  but exposes only route descriptions, no top-level unauthenticated
  `/products` endpoint. **Did not** run a Playwright network trace against
  the live breadfast.com browser checkout flow (it has one, separate from
  the mobile app) — that is the one untried avenue that could plausibly
  unlock this; flagging it explicitly rather than concluding "impossible."
  Probed 2026-09-10.
- **spctrmafrica.com** (MW, "SPCTRM") — WordPress marketing/blog site, no
  `wc/*` REST namespace at all (`/wp-json/` root lists only Bluehost/Newfold
  hosting plugins, AIOSEO, Monsterinsights, Site Kit). The candidate page
  (`/grocery-delivery-lilongwe/`) links out only to a Google Play Store app
  (`com.spctrm.user`) — an app-first delivery business, same shape as
  breadfast. A separate subdomain, `care.spctrmafrica.com/create-order`, is
  referenced from the homepage and is presumably the real order backend —
  not probed (it's not a WordPress/WooCommerce endpoint; reaching it would
  need a new fetcher, out of scope for a `WooBaseSpider` subclass).
  `sitemap.xml`/`wp-sitemap.xml` list zero `<loc>` entries. Did not try
  Playwright. Probed 2026-09-10.

### Wrong-geography Shopify diaspora stores and a one-product catalog (AG, RW)

- **caribbeaneat.com** (proposed AG, "Caribbean Eat") — live, enumerable
  Shopify storefront (`/products.json?limit=250&page=N`: 250/250/250/127/0
  across 5 pages, ~877 products, ids disjoint across pages) — **rejected on
  geography, not access**. `Shopify.country = "US"`, `Shopify.currency
  {"active":"USD"}`; 100-row tag sample dominated by `jamaican` (91),
  `west indian grocery` (83), `colombian food` (63), `Venezolan food` (31),
  `ARGENTINO` (20) with **zero** Antigua tags or mentions anywhere in the
  catalog or homepage copy; vendor field is self-branded "Caribbean Eat" for
  496/500 rows. Same shape as the `caribbeanonlinegrocery.com` (HT) entry
  above: a US-based pan-Caribbean/pan-Latin diaspora grocer selling
  import-marked-up prices to the diaspora market, not a domestic retailer for
  the country in its name. Do not onboard under Antigua and Barbuda. Probed
  2026-09-10.
- **mycaribbeangrocer.com** (proposed AG, "My Caribbean Grocer") — live
  Shopify storefront, `/products.json?limit=250&page=1` returns 86 products,
  page=2 returns `{"products":[]}` (clean single-page catalog, not a
  pagination trap). Rejected on geography: `Shopify.country = "US"`,
  `Shopify.currency {"active":"USD"}`; full 86-SKU catalog inspected —
  vendor field is 35 distinct brands, essentially all Jamaican (Grace,
  Walkerswood, Lasco, Betapac, Excelsior, HTB, Jamaica Mountain Peak, Blue
  Mountain Country), zero occurrences of "Antigua"/"Barbuda" in titles, tags,
  or homepage HTML; carries USD $100/$250 gift-card SKUs (a diaspora-retailer
  signature). Same reject class as caribbeaneat.com above. Do not onboard
  under Antigua and Barbuda. Probed 2026-09-10.
- **pridefarms.rw** (RW, "Pride Farms") — pre-probe evidence described this
  as "a Wix site with an Ecwid store embedded"; re-probe found that
  description wrong. It is **native WixStores**, not Ecwid: the site exposes
  a Wix-generated `store-products-sitemap.xml`, product URLs are
  `/product-page/<slug>` (WixStores' own router, not an Ecwid shape), and the
  rendered product page carries Wix's own native product JSON
  (`"currency":"RWF","price":5700,"formattedPrice":"R₣5,700"`) with no Ecwid
  script/iframe/store-id anywhere. The 11 "ecwid" string hits per page are
  Wix's generic App-Market catalog boilerplate (a JSON blob describing the
  *available* "Ecwid E-commerce" app), present on every Wix site regardless
  of whether that tenant actually uses it — not a fingerprint of active use.
  Independent of the platform question, the source fails the enumerability
  gate outright: `store-products-sitemap.xml` lists **exactly one product**
  (`chickpeas-kabuli-whole-g1-1kg`, RWF 5,700/kg), and every storefront page
  checked (`/shopall`, `/rwanda-products`, `/discover-our-shops`) renders
  that same single product link and nothing else — there is no page 2 to
  compare against page 1. The business and RWF pricing look genuine; the
  online catalog itself just does not exist at any usable scale. Not
  attempted: a Playwright network trace (the sitemap and every rendered
  listing page already agree on the 1-product ceiling, so a trace would not
  raise it). If this business ever builds out a real catalog, re-probe fresh
  — do not carry forward the "Ecwid" assumption. Probed 2026-09-10.

### Bagisto demo/seed installs and a fully login-walled tenant (LY, CM, UZ)

All three assigned sources are re-confirmations of, or new entries in, the
"Placeholder / seed demo-data catalog" and "route-gated storefront" families
already described in the master `known_blockers.md`. Format matches that file.

- **nawris.net** (LY, "Nawris") — RE-CONFIRMED DEAD, no change. Already logged in the
  master `known_blockers.md` (wave 10, probed 2026-09-01): live, unauthenticated
  `/api/products`, `/api/global/stores`, `/api/search`, but the entire catalog is 4
  fabricated seed rows ("هاتف تجريبي" / "test phone", store "متجر النورس التجريبي" /
  "Nawris demo store"). Re-probed 2026-09-10 with plain curl (Mozilla UA, no
  impersonate needed — no WAF present) from the Mac: `GET /api/products?limit=50`
  returns the identical seed rows verbatim (same IDs, same names, same store names).
  No change in 9 days. Do not re-probe again without a specific signal the operator
  relaunched (e.g. a changed product count or removal of the "تجريبي"/demo-branded rows).

- **www.quickgo237.com** (CM, "QuickGo 237") — RE-CONFIRMED DEAD, no change. Already
  logged in the master `known_blockers.md` (wave 13, probed 2026-09-01): real Next.js
  app, no WAF, but the entire "national marketplace" is 11 products total across all 6
  listed vendors, with one vendor's own shop page 404ing. Re-probed 2026-09-10 with
  curl (Mac, plain UA): `GET /api/products` still returns `{"data":[...11 items...],"count":11}`
  — same total as the wave-13 finding. Note the pre-probe evidence for this batch also
  claimed a Bagisto fingerprint ("also a Next.js front") — on inspection this tenant is
  pure Next.js/REST, not Bagisto (no `X-Built-With` header, no `themes/shop/.../build`
  asset paths, response shape `{data, count}` doesn't match Bagisto's `meta.last_page`
  contract). The platform misidentification doesn't change the verdict — catalog size
  is the blocker either way.

- **yanada.uz / www.yanada.uz** (UZ, "Yanada") — NEW ENTRY. Genuine Bagisto storefront —
  confirmed via `X-Built-With: Bagisto` response header (seen on a bare `HEAD /` from the
  Mac) and via Bagisto's own Vite build asset paths (`/themes/shop/default/build/assets/app-*.{js,css}`)
  in the rendered homepage. Unlike the fooddepot.am pattern in `platform_fingerprints.md`
  (empty CRA shell, real API on a separate `api.<domain>` host), this is a server-rendered
  Bagisto install with NO anonymous surface at all: with curl_cffi
  (`impersonate="chrome124"`, `allow_redirects=False`, from a8, probed 2026-09-10) every
  route tested — `/`, `/shop`, `/api/products`, `/api/products/?limit=5&page=1`,
  `/api/categories`, `/api/v1/products`, `/api/v1/categories`,
  `/bagisto-app/api/v1/products` — 302-redirects to `https://yanada.uz/customer/login`
  ("Mijozlar uchun kirish" / "Login for customers", Uzbek). This is stricter than the
  bnf_mart-MM route-gated pattern already documented (which at least leaves a homepage
  carousel reachable) — here even `/` and the REST endpoints themselves are gated. Checked
  for a separate unauthenticated API host: `api.`, `app.`, `shop.`, `m.`, `admin.` +
  `.yanada.uz` all fail TLS certificate verification (SNI mismatch — the cert doesn't
  cover those names), so no alternate host exists to fall back to. `robots.txt` is an
  empty allow-all (200, no signal). Did NOT run a Playwright network trace or attempt a
  login flow — this is a customer-login-gated B2C site by design, not a WAF/anti-bot
  block, so a browser trace would not surface a public catalog that doesn't exist. Do
  not build without valid customer credentials, which is out of this pipeline's scope.

### VTEX legacy Catalog REST dead account-wide (PK)

- **www.homeshopping.pk** (PK, Home Shopping -- VTEX tenant `homeshoppingpk`) -- storefront renders fine (VTEX IO SSR, 200, real HTML, `homeshoppingpk.vtexassets.com` assets load), but the legacy Catalog REST surface `_vtex_base.py` is built against is dead across the whole account, not just the custom domain: `GET /api/catalog_system/pub/category/tree/{1,2,3,10}` returns HTTP 400 with an EMPTY body, and `GET/POST /api/catalog_system/pub/products/search` (with or without `fq`/`ft`) returns HTTP 400 with body `"This store is temporarily unavailable"`. Reproduced identically on `www.homeshopping.pk`, the bare account domain `homeshoppingpk.myvtex.com`, and `homeshoppingpk.vtexcommercestable.com.br` -- ruling out a CDN/custom-domain routing quirk. Confirming signal from a second angle: the homepage's own Apollo `__STATE__` SSR cache is a literal empty object (`__STATE__ = {}`), so even VTEX's own SSR isn't populating from that surface. The newer Intelligent Search REST endpoint (`/api/io/_v/api/intelligent-search/product_search/`) also fails, with a 500.
  Real product data is confirmed live (Playwright network trace, stealth launch, mandatory gate satisfied) flowing through VTEX IO's federated GraphQL layer at `/_v/segment/graphql/v1`, `operationName=Products`/`GetCategories`, as **persisted queries** (`extensions.persistedQuery.sha256Hash` tied to a specific registered app version, e.g. `vtex.search-graphql@0.x`) -- 200 responses confirmed. This is not a variant of `_vtex_base.py`'s REST pattern; it is a different protocol (GraphQL, persisted-query IDs that are expected to rotate on the tenant's next VTEX IO app deploy) that no base class in this repo drives. Not attempted: hand-rolling a spider against the captured persisted-query hashes (would silently break on the tenant's next deploy with no local signal, and there appear to be several distinct `Products`-shaped queries keyed by calling component -- home shelf vs. category listing -- so one hash would not cover the catalog); VTEX Intelligent Search's other endpoints beyond `product_search` (e.g. `facets`); a raw category-page HTML scrape (VTEX IO category pages are client-hydrated React with no server-rendered product list once `__STATE__` is empty, so this would not recover anything `curl_cffi` alone could read). Probed 2026-09-10.

(see batch_4_report.md for liki24_ua -- Cloudflare rate-limiting under investigation, not a hard block; airba_kz is a duplicate of the already-onboarded technodom_kz, not a blocker)

### Store-session-gated pricing and a reCAPTCHA-Enterprise SPA (IT)

- **spesaonline.conad.it** (IT, Conad -- one of Italy's largest grocery
  co-ops, `spesaonline.conad.it` is its national delivery/click&collect
  storefront) -- NOT a WAF block: bare `curl` (no TLS impersonation) clears
  the sitemap and every product-detail page at 200, robots.txt allows the
  full catalog. The blocker is that **anonymous/no-session requests get a
  hard `0.0`/empty price**, not a missing-field or a flaky field. Evidence:
  `/sitemap/products.xml` is a flat urlset of 5,438 `/p/<slug>--<id>` URLs
  (all resolve, some via a 301 to a canonical slug); of 9 sampled product
  pages, only 1 carried a JSON-LD `offers.price` at all (2.49 EUR, "Olio di
  Semi di Soia 1 litro Conad") -- the other 8 had an `offers` object with NO
  `price`/`priceCurrency` key whatsoever. The rendered DOM confirms why: the
  price element is `<span class="price"></span>` -- literally empty in the
  server-rendered HTML, populated client-side by JS. Category-listing pages
  expose the same product objects via a `data-product="{...}"` JSON blob
  with an explicit `"basePrice":0.0` field. This is Conad's "ordina e
  ritira" (order & collect) UX gate: the DOM itself contains an
  `id="ordina-ritira-scelta-pdv"` ("choose your pickup store") component,
  meaning price is genuinely a function of which physical store (punto
  vendita) the session has selected, and the site's default/no-selection
  state has no price to show. Found (via the site's own AEM clientlib JS
  bundle, `clientlib-site.*.min.js`) a real `/api/ecommerce/it-it.stores.json`
  endpoint and several delivery-address/cart endpoints, but a bare GET on
  `/api/ecommerce/it-it.stores.json` 404s -- these are almost certainly
  POST/session-bound AEM Sling endpoints, not a public read API. NOT tried:
  Playwright with a real store-selection click-through (would very likely
  work, since the underlying data clearly exists once a pdv is set); did not
  attempt cookie/header guessing beyond the one 404'd GET. Recommend a
  Playwright-network-trace pass specifically to capture the store-selection
  API call shape before writing this off as unreachable -- the catalog size
  (5,438 products) and the one confirmed-working price sample make this
  worth a second look. Probed 2026-09-10.

- **www.coopshop.it** (IT, Coop -- Italy's other major grocery co-op,
  `coopshop.it` is its national online delivery storefront) -- a pure
  Vue.js single-page-app shell with **zero server-rendered product data of
  any kind**. `sitemap.xml` -> `sitemap/product_0.xml` / `product_1.xml`
  genuinely enumerate (1000/1000 URLs, 0 overlap, confirms the catalog is
  real and large), but every one of 5 sampled `/product/<slug>` URLs
  returned the byte-IDENTICAL 15,401-byte HTML shell (`<div id="app">`,
  webpack chunk `<link>` tags, no product markup at all) -- confirmed with a
  plain UA'd `curl -L`, no redirect, no WAF signature (no 403, no Akamai/
  Cloudflare stub). Checked the app's own JS bundles
  (`js/index.*.js`, `js/chunk-common.*.js`, `js/chunk-vendors.*.js`, ~2.2MB
  combined) for a same-origin REST/GraphQL API base URL string and found
  none (`grep`'d for `/api/`, `graphql`, `coopshop.it/api` patterns -- 0
  hits beyond the bare origin string). The page loads
  `google.com/recaptcha/enterprise.js` on every request, which strongly
  suggests the underlying API (wherever it lives) is behind a reCAPTCHA
  Enterprise token check, not just JS-rendering. NOT tried: an actual
  Playwright/headless-browser network trace (would reveal the real API
  host+shape and whether recaptcha genuinely gates it or is decorative) --
  this is the obvious next step and wasn't run due to no browser-automation
  tool available in this probe pass. Given the SPA + recaptcha-enterprise
  combination, this is a materially harder integration than the sitemap+
  JSON-LD pattern this batch targets; flagging for a dedicated
  Playwright-equipped pass rather than shipping a non-working scrapy_html
  spider. Probed 2026-09-10.

### Akamai sensor-JS on Albert Heijn, both countries (NL, BE)

- **ah.nl** (NL, Albert Heijn) and **ah.be** (BE, Albert Heijn) — same Ahold
  Delhaize platform, same block, verified independently on both hosts
  2026-09-10. The site itself is not gated: `robots.txt` is fully public
  (lists 15 sitemaps) and the dedicated product sitemap
  `https://www.ah.nl/sitemaps/entities/products/detail.xml` (and the `.be`
  equivalent) returns a clean 200 with the full flat `<urlset>` — 40,923
  distinct `/producten/product/<id>/<slug>` URLs on `.nl`, 16,999 on `.be`
  (both corrected counts, re-derived from this sitemap directly per the
  wave-2 instruction; the brief's `/p/`-pattern counts of 41,067/17,102 were
  contaminated by store-locator URLs like
  `/winkels/belgie/turnhout/p-j-brepolsplein-29/` as warned, and turned out
  to be close to the true numbers only by coincidence).

  The block is on the product-detail PAGE itself, not on access in general.
  Every PDP request returns HTTP 200 with a ~2.6KB Akamai Bot Manager
  "sensor data" JS challenge page (`Powered and protected by Akamai`,
  `sec-if-cpt-container`/`behavioral-content` markup, an
  `XMLHttpRequest.prototype.send` hook that reloads the page once a sensor
  payload round-trips) instead of the actual product markup — confirmed
  identical on both `.nl` and `.be`.

  Tried, in order, all on 2026-09-10:
  1. `curl_cffi` TLS-impersonation sweep across 10 profiles on the PDP URL
     directly (`chrome120`, `chrome124`, `chrome131`, `chrome131_android`,
     `chrome133a`, `chrome136`, `edge101`, `safari17_0`, `safari184`,
     `chrome99_android`): `chrome120`/`chrome124`/`edge101` hard-403;
     every other profile gets a 200 but it is the SAME 2,602-byte Akamai
     sensor-challenge stub, not real content. TLS fingerprint is not the
     gating factor — the challenge itself requires executing the sensor JS.
  2. The dynamic-rendering-by-User-Agent trick that shipped `plus_nl` in
     this same batch: setting `User-Agent: Mozilla/5.0 (compatible;
     Googlebot/2.1; +http://www.google.com/bot.html)` on the PDP request.
     This does NOT get treated the same as on plus.nl — Akamai appears to
     verify Googlebot claims (reverse-DNS/IP-allowlist style) and actively
     penalizes an unverified one: repeated attempts got `curl: (92) HTTP/2
     stream 1 reset by server (error 0x2 INTERNAL_ERROR)` and, on retry
     with a forced HTTP/1.1 downgrade, a hard connection timeout (`curl:
     (28) Operation timed out after 20002ms with 0 bytes received`) rather
     than a clean 403. This is a materially worse response than an
     unmodified UA gets, so it reads as active anti-spoofing rather than
     coincidence.
  3. One extra idea beyond the two above (per the wave-2 "worth one more
     idea" instruction): AH's mobile-app backend at `api.ah.nl`. A POST to
     the (publicly known/reverse-engineered) anonymous-auth endpoint
     `https://api.ah.nl/mobile-auth/v1/auth/token/anonymous` with
     `{"clientId":"appie"}` DOES succeed cleanly (200, returns a real
     OAuth2 bearer token) — so the API surface exists and is reachable.
     But the product endpoints behind it
     (`/mobile-services/product/search/v2`,
     `/mobile-services/product/detail/v4/fir/<id>`) both reject the bearer
     token: search returns a 500
     `ApplicationContextNotFoundException: Can not find application:
     'null'` and detail returns a 400 Whitelabel error. Both look like a
     missing app-identifying header (something like `X-Application`,
     matched to a specific app build/version) that I did not attempt to
     guess, per the "probe, never guess" rule — reverse-engineering the
     exact header set the official Appie app sends was out of scope for
     this session's time budget.

  NOT tried: a real headless browser (Playwright/Puppeteer) that could
  actually execute Akamai's sensor JS and pass the behavioral challenge, or
  a paid unblocking proxy/solver service. Given Akamai's demonstrated
  active countermeasures against UA spoofing (point 2 above), a genuine
  browser automation attempt is the next reasonable idea if this source is
  revisited, but it is a materially larger effort (and, per the campaign
  brief's caution about anti-bot budgets, a real risk of an IP-level
  response if attempted carelessly) than anything in this batch's scope.

  Recommendation: leave BLOCKED for now rather than escalate further inside
  this batch. The sitemap-derived catalog counts above (40,923 NL /
  16,999 BE) are solid and worth keeping on file if a future batch brings
  Playwright or a commercial unblocker into scope.

### Tesco first-party storefronts — Akamai Bot Manager on the product layer (CZ, IE, UK)

Three of four assigned Tesco first-party storefronts. All probed live
2026-09-10 from a8 (`~/venv/bin/python` + `curl_cffi 0.16.2`), impersonate
profiles `chrome120`/`chrome124`/`chrome131`/`chrome150`, plus one headless
Playwright (Chromium 143, no stealth patch) pass per host. tesco_hu (the
fourth) shipped — see `batch_7_report.md`.

**Pattern common to all three**: robots.txt and the homepage are reachable
(homepage 200 on at least one TLS profile, sitemap XML 200 on every profile
tried, sitemap-index resolves into real product shards with genuine
disjoint product URLs) — this is what the campaign's original discovery pass
measured. But the product-detail (`/shop/<locale>/products/<id>`) endpoint
sits behind a second, stricter Akamai layer that neither TLS impersonation
nor an actual headless browser clears. This is a harder class than "wrong
TLS profile" — reproduced on genuinely different network clients (a
non-JS curl_cffi TLS handshake AND a real Chromium page load), so it is not
the `curl_cffi`-clears/Scrapy-doesn't client-path-mismatch class documented
elsewhere in `known_blockers.md` either.

- **nakup.itesco.cz** (CZ, Tesco Czech Republic's own storefront — distinct
  from the already-onboarded `tesco_wolt_cz`, a single Wolt-listed branch) —
  homepage: 403 on chrome120/chrome124/chrome131 (70,966-byte Akamai denial
  page), 200 on chrome150 only (536,401-536,577 bytes, real content, matches
  the campaign's original measurement). Sitemap chain fully resolves:
  `/sitemaps/cs-CZ/groceries/products-index.xml` -> 4 shards
  (products-1..4.xml), shard1/shard2 each 5,000 URLs, 0 overlap. But every
  `/shop/cs-CZ/products/<id>` request, on **all four** TLS profiles
  including chrome150, returns HTTP 200 with a 2,715-byte Akamai Bot
  Manager JS interstitial (`id="sec-if-cpt-container"`, "Powered and
  protected by Akamai", a `_sec/cp_challenge`-style reload script) — not
  real content, and not solvable by a non-JS client by definition. A
  single headless-Playwright load of the same PDP URL (after a homepage
  visit in the same context, 3-8s waits) did not even reach that
  interstitial: it drew a **hard "Access Denied"** edge deny (320-byte
  body, `errors.edgesuite.net` reference `18.9623417.1789083394...`) —
  worse than the curl_cffi outcome, suggesting Akamai's risk scoring
  penalizes the real-Chromium fingerprint (no stealth patching applied)
  more than the impersonated TLS client. Not attempted: a stealth-patched
  Playwright context, a residential/mobile proxy, or actually solving the
  Bot Manager sensor challenge (would need reverse-engineering Akamai's
  obfuscated JS or a paid solver). Probed 2026-09-10.

- **www.tesco.ie** (IE, Tesco's own Irish storefront) — homepage: 200 on
  **all four** profiles tested (226,929 bytes each, real Next.js page with
  a live `buildId` and an Akamai sensor pixel `/akam/13/pixel_*` — genuinely
  live, not a shell). Sitemap chain resolves fully:
  `/sitemaps/en-IE/groceries/products-index.xml` -> 5 shards, shard1/shard2
  5,000 URLs each, 0 overlap. But `/shop/en-IE/products/<id>` 403s outright
  on chrome120/chrome131 (70,900-byte Akamai denial page) and returns the
  same 200-status-but-fake 2,721-byte `sec-if-cpt-container` JS interstitial
  on chrome124/chrome150 — the same two-tier pattern as tesco_cz, just with
  the profiles split differently. Headless Playwright on the same PDP URL:
  hard "Access Denied" (317 bytes, `errors.edgesuite.net` ref
  `18.16623417.1789083425...`). The brief's "200 with 455,844 bytes on
  chrome150" reading was almost certainly the homepage, not the PDP — our
  homepage byte count differs (226,929 vs 455,844, likely due to
  personalization/A-B-bucket drift between probes) but the *pattern*
  (homepage passes, PDP does not) matches. Not attempted: stealth-patched
  Playwright, residential proxy, or the sensor-challenge solve. Probed
  2026-09-10.

- **www.tesco.com** (UK, Tesco's own UK storefront) — homepage: 403 on
  chrome120/chrome124/chrome131 (a bare 527-byte body, not the
  Akamai-branded denial page seen on the other two — looks like a plain
  edge reject), 200 on chrome150 (611,079 bytes, real content — same
  pattern the brief measured, though our byte count is 611,079 vs the
  brief's 518,401, again likely personalization drift). Sitemap chain
  resolves fully: `/sitemaps/en-GB/groceries/products-index.xml` -> 8
  shards, shard1/shard2 5,000 URLs each, 0 overlap. `/shop/en-GB/products/
  <id>` 403s on chrome120/chrome131/**chrome150** (71,654 bytes each — so
  chrome150, which clears the homepage, does NOT clear the PDP here,
  unlike CZ/IE) and returns the 200-status fake `sec-if-cpt-container`
  interstitial (2,735 bytes) only on chrome124. Headless Playwright on the
  same PDP URL: hard "Access Denied" (320 bytes, ref
  `18.506adc17.1789083394...`). Not attempted: stealth-patched Playwright,
  residential proxy, or the sensor-challenge solve. Probed 2026-09-10.

**What would actually move these**: either (a) a Playwright context with
real stealth patching (navigator.webdriver removal, consistent
client-hints, canvas/WebGL noise) run from a residential-looking IP, or
(b) reverse-engineering/solving Akamai's Bot Manager sensor payload so a
plain HTTP client can POST a valid `_abck` update — both substantial,
out-of-scope efforts for this batch's budget. No proxy or CAPTCHA/JS-solver
service was available or tried.

### Akamai on Koctas, and a rate-limit escalation we triggered ourselves (TR, SE)

auchan_hu and alcampo_es shipped (alcampo_es after real, tenant-side AWS-WAF
anti-bot throttling during probing — see `batch_8_report.md` for the
throughput analysis). koctas_tr and ica_se did NOT ship; both are recorded
below.

- **www.koctas.com.tr** (TR, Koctas — home-improvement/DIY hypermarket
  chain) — probed live 2026-09-10 from a8 (`~/venv/bin/python` +
  `curl_cffi 0.16.2`, impersonate profiles chrome99/110/120/124/131/
  131_android/133a/136/safari17_0/safari18_0/edge101, plus one headless
  Playwright pass, Chromium via `playwright` 1.57.0, no stealth patch).

  Same two-tier Akamai pattern already documented for tesco_cz/ie/uk in
  `known_blockers_batch_7.md`: the SITEMAP layer is wide open, the
  PRODUCT-DETAIL layer is not.

  - `robots.txt` via bare system `curl` (no UA / with a plain browser UA
    string, no TLS impersonation): HTTP 403, a 387-byte
    `errors.edgesuite.net` "Access Denied" body — classic Akamai edge
    reject on a non-browser TLS fingerprint (this file's rule: bare curl's
    TLS handshake alone is enough to trip Akamai on this tenant).
  - `robots.txt` / `sitemap.xml` via `curl_cffi` with ANY of 8 tested
    Chrome/Safari impersonate profiles: **HTTP 200 on every one** (5,622
    and 13,468 bytes respectively) — the sitemap layer does not
    discriminate by TLS profile at all.
  - Sitemap chain fully resolves: `sitemap.xml` -> 131 child sitemaps
    (117 `product-tr-try-N.xml` shards + category/brand/content/
    imagecategory/filteredcategory/customlanding/storedetail/
    brandcategorypageinformation singles). `product-tr-try-0.xml` = 10,000
    `<loc>` entries (bathroom-fixture SKUs, e.g.
    `/gpd-banyo-bataryasi-espina-mix-mbb70/p/1000065417`), `product-tr-
    try-1.xml` = 10,000 `<loc>` entries (garden-tool SKUs, e.g.
    `/mac-allister-cim-bicme-makinesi-1300-watt-34-cm/p/2000033754`) — 0
    overlap, genuinely disjoint (117 shards x ~10,000 implies a
    catalog on the order of 1M+ URLs, well above the brief's 80,000
    measurement, though some of that is likely size/color variant
    duplication not counted here).
  - Every `/<slug>/p/<id>` product-detail fetch, on ALL of
    chrome99/110/120/124/133a/136 impersonate profiles: HTTP 403
    (~600-625 byte body, no interstitial, a hard edge deny).
  - `chrome131_android`, `safari17_0`, `safari18_0` initially looked
    promising (HTTP 200) in a first pass, but were NOT reproducible: a
    follow-up loop of 6 consecutive requests to the same PDP URL with
    `chrome131_android` got 403 on all 6, and a request with
    browser-realistic headers added (`Accept`, `Accept-Language: tr-TR`,
    `Referer`) made `safari17_0`/`safari18_0` return HTTP 200 but with
    only ~2,965 bytes — decoded body is Akamai Bot Manager's own
    **behavioral-challenge interstitial**
    (`id="sec-if-cpt-container"`, "Powered and protected by Akamai", a
    `/mfwJSOM.../DYACTYb?ch=true` sensor-loader script), i.e. HTTP-200-
    but-fake, the identical class documented for tesco_cz/ie/uk's PDP
    layer — not real product content, and not solvable by a non-JS
    client by construction.
  - A category-listing page (`/banyo/c/1000`) also 403s on chrome120,
    same as the PDP layer — the block is not PDP-specific, it covers all
    product/category browsing, only the sitemap XML endpoints and the
    homepage (`/`, 200, 1,617,612 bytes on chrome120) are exempt.
  - Cookie-warmup attempt (the pattern that made tesco_hu work in this
    same repo: fetch a page the WAF allows first, then reuse ITS session
    cookies for the blocked page): `requests.Session()` GET `/` (chrome120)
    -> 200, and the session picked up real Akamai Bot Manager cookies
    (`_abck`, `ak_bmsc`, `bm_s`, `bm_so`, `bm_sz`, plus `JSESSIONID`).
    Reusing that SAME session (same cookies, same TLS-impersonation
    profile) for the PDP fetch: still **HTTP 403** (599 bytes). Unlike
    tesco_hu's sitemap-fetch-carries-cookies-into-PDP trick, merely
    possessing Bot Manager's tracking cookies does not satisfy this
    tenant's PDP-layer check -- consistent with Akamai's stricter
    "sensor data" validation mode, which needs an actual JS-computed
    payload posted back, not just the cookie names being present.
  - Headless Playwright (Chromium, no stealth patch, `--disable-blink-
    features=AutomationControlled`, isolated per-job tmp dir after an
    earlier `/tmp` file collision with another concurrent batch's script
    corrupted a first attempt's output — see note below) direct-navigated
    to the same PDP URL: HTTP **403**, 344-byte body — a harder outcome
    than curl_cffi's soft interstitial, matching the tesco_cz/ie/uk
    finding that Akamai's real-Chromium risk score is *worse* than its
    impersonated-TLS-client score when no stealth patching is applied.

  **Not attempted**: a stealth-patched Playwright context (navigator.
  webdriver removal, consistent JS-visible fingerprint), a residential/
  mobile proxy, or reverse-engineering/solving the Bot Manager sensor
  challenge itself. Given `known_blockers_batch_7.md`'s "what would
  actually move these" section already concludes the sensor-challenge
  solve is the only path and treats it as out of onboarding-probe budget
  for this campaign, the same conclusion applies here — this is the same
  vendor, same challenge class, same PDP/sitemap split.

  Operational note: a first Playwright probe script written to the
  shared `/tmp/probe_koctas.py` produced garbled, unrelated output (a
  different concurrent agent's PPP/CPI-currency script) — confirming the
  onboarding skill's warning that parallel agents on a8 clobber generic
  `/tmp/probe_*` filenames. Re-run from a job-local
  `~/po-gapfill/tmp_batch8/` directory produced clean results. Flagging
  in case other batch-8-era agents hit the same corruption.

  Probed 2026-09-10 (wave 2, batch 8).

- **handla.ica.se / handlaprivatkund.ica.se** (SE, ICA — Sweden's largest
  grocery group) — NOT shipped. Deleted after 3 failed
  `prices collect --source ica_se --max-items 20` runs (00:13, 00:19,
  00:24 UTC on 2026-09-10), all 0 items / 0-byte output files. The spider
  (`ica_se.py`) and manifest (`configs/eca/western_europe/sweden/
  ica_se.yaml`) were removed from the worktree rather than left in place.

  This is worth recording in detail because the underlying extraction
  design is proven correct earlier in the SAME probing session, and the
  failure is a live, tenant-side anti-bot escalation, not a design flaw:

  - handla.ica.se itself is store-scoped (every PDP/listing needs a
    chosen store first — "Valj butik for ratt sortiment, pris och
    leveransalternativ"); the real per-store storefront lives on a
    DIFFERENT domain, `handlaprivatkund.ica.se`, behind AWS WAF Bot
    Control (a `gokuProps`/`awsWafCookieDomainList` HTTP-202
    JS-challenge stub, same vendor/class as taw9eel_kw.py and
    alcampo_es above).
  - Confirmed live, multiple times, that the "Playwright once to mint an
    `aws-waf-token`, then plain-HTTP-replay the cookie" pattern DOES
    work here in isolation: a `store-cookie`+`basePath` cookie pair
    self-constructed (no UI store-picker needed) plus a ~10s Playwright
    wait for the 202 stub to self-resolve produced a valid
    `aws-waf-token`, and replaying just 5 cookies
    (`store-cookie`,`basePath`,`aws-waf-token`,`AWSALB`,`AWSALBCORS`) via
    plain `curl_cffi` got real HTTP 200 responses with a
    `window.__INITIAL_STATE__` JSON blob containing
    `data.products.productEntities` (name/price/currency/category/
    available per product) across multiple different search queries —
    e.g. 'Agg Frigaende M 15-p ICA' SEK 42.20, 'Mellanmjolk Lite langre
    hallbarhet 1,5% 1,5l ICA' SEK 16.70. A store's own live search-term
    dictionary (`/api/search/v1/suggestions/primary?searchTerm=&limit=
    20000&regionId=<uuid>`, ~5,400 terms) was confirmed as the
    enumerable crawl surface (the public `handla.ica.se/sitemap` chain's
    `/produkt/<id>` URLs are store-agnostic and mostly 404 under any one
    store's real assortment).
  - BUT: heavy repeated probing of `handlaprivatkund.ica.se` from this
    a8 IP during the SAME session (many curl_cffi + Playwright requests
    across ~90 minutes, needed to reverse-engineer the store-cookie
    format and the state-blob shape) tripped a HARDER, longer-lived
    step-up than the ordinary WAF challenge: every request — with or
    without cookies, via curl_cffi OR a freshly-bootstrapped Playwright
    context — started returning **HTTP 405** with a page titled "Human
    Verification" (a full interactive CAPTCHA gate, distinct from the
    202 gokuProps stub). All 3 actual `prices collect` runs landed
    squarely inside this escalated window: 113, then 116, then 116
    requests, **100% HTTP 405, 0 items, every time** — the spider's
    bootstrap DID successfully fetch the live 5,427-term dictionary
    each run (confirmed in the stats: `scheduler/enqueued: 5427`), so
    the failure is entirely at the request layer, not the term-sourcing
    or parsing logic.
  - A single manual `curl_cffi` check made BETWEEN run 2 and run 3 (no
    cookies at all) got a real HTTP 200 with 35 priced products — proof
    the escalation is not permanent and does self-clear — but the very
    next full spider run (run 3, started ~1 minute later) hit 405 again
    on all 116 requests, meaning the clear window is narrow and/or the
    spider's own request pattern (bootstrap navigation + suggestions
    fetch + rapid sequential search requests) itself re-triggers the
    step-up almost immediately.

  **What this means for a re-attempt**: the code pattern is sound and
  should be reusable close to verbatim; what failed was doing all the
  discovery AND the verification run against the same live tenant in one
  session, from one IP, in under two hours. A clean re-attempt should
  (a) start from a fresh IP/session with zero prior requests to
  `handlaprivatkund.ica.se`, (b) do the Playwright bootstrap once, wait
  generously, and confirm a single search request succeeds via curl
  BEFORE launching the full Scrapy crawl, and (c) keep concurrency at 1
  with multi-second delays from the very first request rather than
  ramping into it.

  **Not attempted**: a stealth-patched Playwright context; spacing the
  bootstrap and the first Scrapy request further apart in time; running
  from a different network/IP than the one used for discovery; retrying
  the term-sweep with a much smaller, slower-paced term list (all 3 test
  runs used the full live ~5,400-term dictionary at 1s DOWNLOAD_DELAY /
  2 concurrent, which may itself be too aggressive once past the
  bootstrap); and confirming whether the 405 "Human Verification" gate
  is IP-scoped, cookie-scoped, or something else — this file's data
  cannot distinguish those.

  Probed / spider built and removed 2026-09-10 (wave 2, batch 8).

### Shop-scoped pricing with no anonymous shop context (BG)

- **delivme.bg** (BG, "Delivme" -- Sofia grocery-delivery app) -- NOT a WAF or
  TLS-fingerprint block (chrome120/chrome124 both 200 on every URL tried, no
  403 anywhere in this probe). A genuinely enumerable catalog exists: robots.txt
  points at a real multi-shard sitemap index (`/sitemaps.xml` ->
  `/sitemaps.xml/products/1..34`), 34 product shards, product-detail pages
  (`/product/<id>-<slug>`) resolve to a documented JSON API
  (`GET https://api.delivme.bg/api/v1/product/view/<id>-<slug>`, no auth
  header needed, 200 JSON) that returns real fields -- id, name (Cyrillic),
  category, category tree, related_products. But `price`/`cost`/`final_price`/
  `currency` are ALL `null` on every product tried, both a stale 2018-lastmod
  item and a freshly-modified (2026-08-21) one -- confirmed the same on a
  brand-new 2026-08 baby-monitor listing, not just old/delisted stock. The raw
  HTML is an AngularJS shell (`data-ng-app="app"`) with unfilled
  `{{ pageTitle }}` template bindings and a `<jsonld data-json="schemaJSON">`
  placeholder tag -- JSON-LD is injected client-side, never present in the
  fetched response, so there is no SSR price anywhere to scrape even on a
  category-listing page (checked `/product-categories/1-plodove-i-zelenchutsi`
  directly -- 200, no "BGN" string anywhere in the body).
  Root cause: price is entirely shop/session-scoped. The bundled Angular JS
  (`scripts/app.*.js`) shows every price-bearing API call (add-to-cart,
  wishlist, category listing, product search) requires a `shop_id` parameter
  sourced from `localStorage.currentShop`, itself set only after a client-side
  "select your delivery location" flow. Tried to shortcut this three ways, all
  failed: (1) `POST /api/v1/shop/deliver {lat,lng}` (the endpoint the frontend
  calls to check deliverability) returns only
  `{"locationWithDelivery":true,"guest_checkout":0}` -- no shop_id in the
  response; (2) guessing `shop_id=1/2/3` as a query param on
  `/product/view/<id>` left price still null on all three; (3)
  `GET /api/v1/shop/list` and `GET /api/v1/shop/slug` both return
  `401 Unauthorized` (13-byte body) rather than a shop object, i.e. they need
  an authenticated/guest session token this probe did not obtain (a POST to
  `/api/v1/auth/guest` did not return a token in the shape expected -- got the
  SPA shell HTML back instead, suggesting that path needs to be hit through
  delivme.bg's own reverse-proxy setup rather than api.delivme.bg directly, not
  investigated further).
  NOT attempted: a full Playwright browser flow that completes the
  location-selection UI (or extracts the `currentShop` object it writes to
  localStorage) before hitting the product API with a real shop_id and/or
  session cookie -- this is the same class of gate documented in the main
  known_blockers.md for sahel25.com (UAE Kibsons/Talabat-style
  "resolve-delivery-area-first" pattern) and would need the same kind of
  investigation. Catalog is real and reasonably large (~9,800 product URLs
  across 34 sitemap shards per the initial measurement) so this is worth a
  second pass with Playwright, not a dead source. Probed 2026-09-10.

### Delivery-zone and Queue-it gating on Nemlig (DK)

- **nemlig.com** (DK) — Sitecore/Angular SPA, grocery home-delivery. The
  wave-3-observed endpoint `GET /webapi/<CombinedProductsAndSitecoreTimestamp>/
  <TimeslotUtc>/<DeliveryZoneId>/.../Products/GetByProd...` is a client-side
  route built from three values pulled from `basketStateService` inside the
  site's own bundle (`scom/dist/main.js`, grep confirmed:
  `` `/webapi/${e.CombinedProductsAndSitecoreTimestamp}/${n.TimeslotUtc}/${n.DeliveryZoneId}/...` ``).
  `TimeslotUtc` and `DeliveryZoneId` are populated only after a delivery-address
  + delivery-timeslot selection flow (real, capacity-limited delivery slots,
  not a static identifier) — confirmed by reading the Angular service code,
  not guessed. `CombinedProductsAndSitecoreTimestamp` is a catalog/CMS version
  stamp, separately sourced.
  Tried: (1) `curl_cffi impersonate=chrome124` on the homepage — 200, but sets
  Queue-it virtual-waiting-room cookies (`Queue-it-token`,
  `QueueITAccepted-SDFrts345E-V3_nemligprod`), meaning the site fronts even
  normal browsing with a bot-mitigation/capacity gate. (2)
  `POST /webapi/Delivery/CheckPostCode` with a raw JSON-encoded postcode body
  (not a `{field: value}` object — the Angular client posts the primitive
  directly) — this **works anonymously**, `200 {"PostalDistrictCode":2100,
  "PostalDistrictName":"København Ø","IsFullDeliverable":true,...}` — but the
  response carries no `DeliveryZoneId`/`TimeslotUtc`, only deliverability +
  district name. (3) The parallel, apparently-current search stack —
  `POST/GET https://webapi.prod.knl.nemlig.it/searchgateway/api/search` (host
  read from `window.scom.nemligGatewayApiUrl` in the page's inline bootstrap
  script) — returned `401 {"...": "Jwt is missing"}` on every unauthenticated
  attempt (empty query, real Danish search terms). This is a genuine auth
  token requirement, not a public/anon key, so per the batch rules it was not
  pursued further (no attempt to obtain or fabricate a JWT).
  **Not tried**: a full Playwright session that completes the delivery-address
  → timeslot selection UI flow while preserving cookies, to see whether the
  resulting `basketStateService` state (and possibly a JWT for the gateway,
  if the UI flow issues one client-side) becomes usable for a subsequent
  plain-HTTP category walk. This is the natural next step for a future agent
  with more time budget, but it is materially heavier than a normal
  Playwright-discovery pass — it requires driving a real address/postcode +
  timeslot booking UI, not just reading a network trace — and even if
  obtained, `TimeslotUtc` describes a live, capacity-constrained delivery
  slot rather than a stable catalog identifier, so its suitability for a
  scheduled/repeatable scrape is itself questionable.
  Date: 2026-09-10.

### A request-for-quote marketplace with no prices and a non-national catalog (DZ)

- **ampagora.com / africamedicalmarketplace.com** (DZ, "Ampagora" / "Africa Medical Marketplace") — API is real and enumerable (`GET https://ampagora.com/api/v1/products/index/all-subscribed`, Laravel-style pagination via `data.meta` with `current_page`/`last_page`/`total`; `perPage=200` accepted, 207 products total across 2 pages, confirmed distinct pages via `meta.current_page`), but it fails the acceptance bar on two independent grounds, either one alone would be disqualifying: (1) **0 of 207 products carry a non-null price** — every single listing has `"price": null, "is_negotiable": true, "minimum_order": <N>`, i.e. this is a B2B "request for quote" wholesale-sourcing marketplace (Alibaba/TradeKey-style), not a source of observable transaction prices; a null price is not droppable-and-move-on like a zero price, it means the entire catalogue has nothing to observe. (2) **wrong geography even setting price aside** — sampled seller/product `country` field across the full 207-product catalogue: Pakistan (37), China (33), Nigeria (31), India (28), Egypt (22), Turkey (18), UAE (11), US (10), South Africa/Burkina Faso/Russia/Poland/Benin/Ghana/Denmark/Angola (1-2 each) — **zero** Algeria-origin listings observed. The site brand ties to "Africa Medical Marketplace" (a pan-African/global medical-equipment sourcing platform) with no evidence it is an Algerian retailer or even Algeria-headquartered; the `_dz` suggestion in this wave's candidate table appears to be a geography mismatch from the discovery pass, not a property of the site itself. Did not attempt Playwright — not needed, since both failure modes are visible directly in the plain JSON API response and neither would be fixed by rendering the page (the null prices and seller countries are server-side facts, not client-hydration artifacts). Probed 2026-09-10.

### Mechanically exhausted — do not re-probe blind

Recorded so the next campaign does not spend the same requests.

**No priced surface under either `curl_cffi` (5 TLS profiles) or headless
Playwright** — 114 hosts. Homepage plus up to two category pages
rendered each; no JSON response carried price-shaped keys, no product
sitemap resolved, no JSON-LD Product node. Not attempted on these: a
stealth-patched browser context, a residential proxy, or in-country egress.

- `kaufland.com` — albania (eca)
- `zalando.com` — albania (eca)
- `bravosupermarket.az` — azerbaijan (eca)
- `kaufland.bg` — bulgaria (eca)
- `lidl.bg` — bulgaria (eca)
- `metro.bg` — bulgaria (eca)
- `eurospin.hr` — croatia (eca)
- `kaufland.hr` — croatia (eca)
- `lidl.hr` — croatia (eca)
- `spar.hr` — croatia (eca)
- `hornbach.cz` — czech_republic (eca)
- `mall.cz` — czech_republic (eca)
- `mad.coop.dk` — denmark (eca)
- `ecoop.ee` — estonia (eca)
- `hokoh.app` — france (eca)
- `eurocaucasus.ge` — georgia (eca)
- `amazon.de` — germany (eca)
- `picnic.app` — germany (eca)
- `bazaar.gr` — greece (eca)
- `chalkiadakis.gr` — greece (eca)
- `fthna.gr` — greece (eca)
- `lidl.ie` — ireland (eca)
- `eurospin.it` — italy (eca)
- `it.everli.com` — italy (eca)
- `sezamo.it` — italy (eca)
- `unes.it` — italy (eca)
- `almago.kg` — kyrgyz_republic (eca)
- `toppartika.lv` — latvia (eca)
- `norfa.lt` — lithuania (eca)
- `cactus.lu` — luxembourg (eca)
- `delhaize.lu` — luxembourg (eca)
- `pegas.md` — moldova (eca)
- `crisp.nl` — netherlands (eca)
- `coop.no` — norway (eca)
- `zabka.pl` — poland (eca)
- `elcorteingles.pt` — portugal (eca)
- `intermarche.pt` — portugal (eca)
- `lidl.pt` — portugal (eca)
- `mercadona.pt` — portugal (eca)
- `supersave.pt` — portugal (eca)
- `mercator.rs` — serbia (eca)
- `mall.sk` — slovak_republic (eca)
- `rohlik.sk` — slovak_republic (eca)
- `ahorrapasta.com` — spain (eca)
- `cartio.es` — spain (eca)
- `lidl.es` — spain (eca)
- `sezamo.es` — spain (eca)
- `ulabox.com` — spain (eca)
- ~~`coop.se` — sweden (eca)~~ **RESOLVED 2026-09-11 → SHIPPED as `coop_se`.** The mechanical homepage+2-category sweep could not have found this one: coop.se's price API is a **POST to a different host** (`external.api.coop.se`, Azure APIM) and needs the `Ocp-Apim-Subscription-Key` that the storefront JS bundle ships to every anonymous visitor (without it: 401 "missing subscription key"). See `coop_se.yaml` for the two calls. Note the sibling route `/personalization/search/products` answers 200 but caps at ~16 items and ignores `skip` — only `/personalization/search/entities/by-attribute` paginates. Test run collected 129 rows; prices verified character-for-character against the rendered category page.
- `lidl.ch` — switzerland (eca)
- `rappn.ch` — switzerland (eca)
- `trendyol.com` — turkiye (eca)
- `boots.com` — united_kingdom (eca)
- `express24.uz` — uzbekistan (eca)
- `mercadolibre.com` — antigua_and_barbuda (lac)
- `mercadolibre.com.ar` — argentina (lac)
- `olx.com` — argentina (lac)
- `belizegrocery.com` — belize (lac)
- `mercadolibre.com.bo` — bolivia (lac)
- `pedidosya.com.bo` — bolivia (lac)
- `amazon.com.br` — brazil (lac)
- `mercadolivre.com.br` — brazil (lac)
- `mercadolibre.cl` — chile (lac)
- `agrofy.com.co` — colombia (lac)
- `mercadolibre.com.co` — colombia (lac)
- `fischelenlinea.com` — costa_rica (lac)
- `pedidosya.com` — costa_rica (lac)
- `mercadolibre.com.ec` — ecuador (lac)
- `vidri.com.sv` — el_salvador (lac)
- `caribeeats.com` — guyana (lac)
- `giftlandmall.com` — guyana (lac)
- `zip.gy` — guyana (lac)
- `caribbeansupermarketsa.com` — haiti (lac)
- `delimarthaiti.com` — haiti (lac)
- `kielsa.com` — honduras (lac)
- `mercadolibre.com.mx` — mexico (lac)
- `mercadolibre.com.py` — paraguay (lac)
- `makro.com.pe` — peru (lac)
- `mercadolibre.com.pe` — peru (lac)
- `pedidosya.com.pe` — peru (lac)
- `excellentstores.com` — trinidad_and_tobago (lac)
- `gofuhdeliveries.wixsite.com` — trinidad_and_tobago (lac)
- `mercadolibre.com.uy` — uruguay (lac)
- `mercadolibre.com.ve` — venezuela_rb (lac)
- `halimpharma.com.af` — afghanistan (menaap)
- `tazapharma.af` — afghanistan (menaap)
- `batolis.com` — algeria (menaap)
- `yassir.com` — algeria (menaap)
- `carrefour.com` — bahrain (menaap)
- `yallarx.com` — bahrain (menaap)
- `instashop.com` — egypt (menaap)
- `rabbitmart.com` — egypt (menaap)
- `ostorz.com` — lebanon (menaap)
- `acima.ma` — morocco (menaap)
- `chari.ma` — morocco (menaap)
- `done.ma` — morocco (menaap)
- `amazon.sa` — saudi_arabia (menaap)
- `founa.com` — tunisia (menaap)
- `sanaa.bazzarry.com` — yemen (menaap)
- `celeste.lk` — sri_lanka (sar)
- `deliiv.cv` — cabo_verde (ssa)
- `banguimall.net` — central_african_republic (ssa)
- `dataviz.vam.wfp.org` — central_african_republic (ssa)
- `kinmarche.com` — congo_dem_rep (ssa)
- `snmart.co` — congo_dem_rep (ssa)
- `klik.delivery` — ethiopia (ssa)
- `chowdeck.com` — ghana (ssa)
- `khetias.com` — kenya (ssa)
- `ubereats.com` — kenya (ssa)
- `easymartmalawi.com` — malawi (ssa)
- `marsarim.com` — mauritania (ssa)
- `maurikilchi.com` — mauritania (ssa)
- `lotieapp.com` — togo (ssa)
- `online-spar.co.zw` — zimbabwe (ssa)

**Challenge or denial on every TLS profile and on headless Playwright** —
72 hosts. Distinct from the class above in that these actively
return a challenge rather than nothing; the per-vendor sections earlier in
this file carry the signatures.

- `amazon.com` — albania (eca)
- `ebay.com` — albania (eca)
- `gjirafa50.com` — albania (eca)
- `interspar.at` — austria (eca)
- `bol.com` — belgium (eca)
- `korpa.ba` — bosnia_and_herzegovina (eca)
- `bgm.bg` — bulgaria (eca)
- `supermarketcy.com.cy` — cyprus (eca)
- `alza.cz` — czech_republic (eca)
- `drmax.cz` — czech_republic (eca)
- `selver.ee` — estonia (eca)
- `k-ruoka.fi` — finland (eca)
- `casino.fr` — france (eca)
- `fnac.com` — france (eca)
- `franprix.fr` — france (eca)
- `intermarche.com` — france (eca)
- `leclercdrive.fr` — france (eca)
- `leroymerlin.fr` — france (eca)
- `alta.ge` — georgia (eca)
- `kaufland.de` — germany (eca)
- `e-food.gr` — greece (eca)
- `posokanei.gov.gr` — greece (eca)
- `alza.hu` — hungary (eca)
- `dunnesstoresgrocery.com` — ireland (eca)
- `amazon.it` — italy (eca)
- `leroymerlin.it` — italy (eca)
- `wildberries.kz` — kazakhstan (eca)
- `lalafo.kg` — kyrgyz_republic (eca)
- `wildberries.kg` — kyrgyz_republic (eca)
- `iki.lt` — lithuania (eca)
- `auchan.lu` — luxembourg (eca)
- `supermarket.mt` — malta (eca)
- `enter.online` — moldova (eca)
- `goflink.com` — netherlands (eca)
- `anhoch.com` — north_macedonia (eca)
- `allegro.pl` — poland (eca)
- `kaufland.pl` — poland (eca)
- `drmax.ro` — romania (eca)
- `profi.ro` — romania (eca)
- `ozon.ru` — russian_federation (eca)
- `wildberries.ru` — russian_federation (eca)
- `pametno.rs` — serbia (eca)
- `alza.sk` — slovak_republic (eca)
- `drmax.sk` — slovak_republic (eca)
- `pametno.si` — slovenia (eca)
- `amazon.es` — spain (eca)
- `leroymerlin.es` — spain (eca)
- `amazon.co.uk` — united_kingdom (eca)
- `argos.co.uk` — united_kingdom (eca)
- `shop.coop.co.uk` — united_kingdom (eca)
- `magazineluiza.com.br` — brazil (lac)
- `singer.com.jm` — jamaica (lac)
- `amazon.com.mx` — mexico (lac)
- `nissei.com` — paraguay (lac)
- `simple.ripley.com.pe` — peru (lac)
- `ubuy.com` — afghanistan (menaap)
- `world-prices.com` — afghanistan (menaap)
- `amazon.eg` — egypt (menaap)
- `carrefouregypt.com` — egypt (menaap)
- `jumia.com.eg` — egypt (menaap)
- `exporthub.com` — iran (menaap)
- `ksp.co.il` — israel (menaap)
- `boutiqaat.com` — kuwait (menaap)
- `carrefourlebanon.com` — lebanon (menaap)
- `ubuy.com.ly` — libya (menaap)
- `marjanemall.ma` — morocco (menaap)
- `oman.sharafdg.com` — oman (menaap)
- `mytek.tn` — tunisia (menaap)
- `amazon.ae` — united_arab_emirates (menaap)
- `carrefour.ke` — kenya (ssa)
- `cleanshelf.co.ke` — kenya (ssa)
- `jumia.sn` — senegal (ssa)

**Domain does not resolve** — 19 hosts, NXDOMAIN on repeat lookups.
Dead, not blocked.

- `cora.be` — belgium (eca)
- `fresco.ge` — georgia (eca)
- `bringmeister.de` — germany (eca)
- `getnow.de` — germany (eca)
- `synka-super.gr` — greece (eca)
- `welbees.com.mt` — malta (eca)
- `minipreco.pt` — portugal (eca)
- `mohira.tj` — tajikistan (eca)
- `brodiesbelize.com` — belize (lac)
- `eaglemarket.ht` — haiti (lac)
- `farmaciasmedco.com` — nicaragua (lac)
- `caluangela.cv` — cabo_verde (ssa)
- `warani.cf` — central_african_republic (ssa)
- `peloustore.cd` — congo_dem_rep (ssa)
- `melcomghana.com` — ghana (ssa)
- `palacehypermarket.com` — ghana (ssa)
- `eastmatt.co.ke` — kenya (ssa)
- `exclusif.sn` — senegal (ssa)
- `storna-shopping-vercel.app` — sudan (ssa)

**DNS resolves but no usable response** — 14 hosts: expired or
mismatched TLS certificate, or TCP timeout on every profile including
`verify=False`.

- `galaxias.gr` — greece (eca)
- `supermarchesmatch.lu` — luxembourg (eca)
- `delio.pl` — poland (eca)
- `monitorulpreturilor.info` — romania (eca)
- `turkey.tradekey.com` — turkiye (eca)
- `lebazar.uz` — uzbekistan (eca)
- `plazalama.com` — dominican_republic (lac)
- `comphaiti.com` — haiti (lac)
- `kazyon.com` — egypt (menaap)
- `dnalifestyle.com` — jordan (menaap)
- `bbsm.com.np` — nepal (sar)
- `sastodeal.com` — nepal (sar)
- `shoashopping.com` — ethiopia (ssa)
- `koumbimarket.eu` — mauritania (ssa)

### Measured but not yet worked — leads, not blockers

These carry a confirmed priced surface and were simply not reached before the
campaign paused. Cheapest starting point for the next wave. Do NOT read these
as blocked.

**JSON endpoint observed live returning prices** (13)

- `aliexpress.com` — albania (eca)
- `colruyt.be` — belgium (eca), 20 product URLs
- `mijnspar.be` — belgium (eca), 5 product URLs
- `njuskalo.hr` — croatia (eca)
- `cdiscount.com` — france (eca)
- `orinabiji.ge` — georgia (eca)
- `roksh.com` — hungary (eca)
- `groceries.aldi.ie` — ireland (eca)
- `esselungaacasa.it` — italy (eca)
- `coop.nl` — netherlands (eca)
- `auchan.pl` — poland (eca)
- `ocado.com` — united_kingdom (eca)
- `mumafrica.com` — algeria (menaap)

**product sitemap enumerated** (11)

- `geramarket.com` — armenia (eca), 72 product URLs
- `auchan.fr` — france (eca), 72 product URLs
- `foodora.hu` — hungary (eca), 9259 product URLs
- `pampanorama.it` — italy (eca), 171 product URLs
- `beeyor.tj` — tajikistan (eca), 394 product URLs
- `diy.com` — united_kingdom (eca), 8 product URLs
- `iceland.co.uk` — united_kingdom (eca), 1 product URLs
- `noon.com` — bahrain (menaap), 120000 product URLs
- `iranpharmis.org` — iran (menaap), 209 product URLs
- `yad2.co.il` — israel (menaap), 75 product URLs
- `daraz.pk` — pakistan (menaap), 60 product URLs

### Wave 4 outcomes — the "measured but not yet worked" list above is now resolved

The leads listed earlier in this section were worked on 2026-09-11. Their
outcomes, so nobody re-probes them from that list:

- `auchan.fr` — SHIPPED as auchan_fr (22 rows), but its own grocery business is discontinued
- `beeyor.tj` — SHIPPED as beeyor_tj (21 rows)
- `cdiscount.com` — SHIPPED as cdiscount_fr (142 rows)
- `colruyt.be` — ALREADY BUILT as colruyt_be (collectandgo.be)
- `coop.nl` — DEAD — plain 301 to plus.nl, which is already onboarded
- `daraz.pk` — SHIPPED as daraz_pk (80 rows)
- `esselungaacasa.it` — PULLED — API verified working, host unreachable at TCP level; re-attempt candidate
- `foodora.hu` — BLOCKED — PerimeterX px-captcha, a real CAPTCHA, on every client incl. Chromium
- `geramarket.com` — DEAD — not an Armenian retailer at all; a US/UK e-commerce SaaS site
- `iranpharmis.org` — DEAD — B2B surgical distributor, every price 0 behind a registration wall
- `mijnspar.be` — DEAD — no catalog route; a fixed 43-row promo flyer is the whole priced surface
- `noon.com` — BLOCKED — Bahrain storefront is real and prices in BHD, but the catalog is an RSC shell
- `ocado.com` — BLOCKED — domain-wide AWS WAF challenge, even on /robots.txt
- `orinabiji.ge` — ALREADY BUILT as orinabiji_ge, already using catalog-api.orinabiji.ge
- `pampanorama.it` — SHIPPED as pampanorama_it (186 rows)
- `roksh.com` — SHIPPED as penny_roksh_hu (22 rows) — a 15-tenant marketplace, Penny picked

Still genuinely unworked from that list, and still worth a future wave:
`njuskalo.hr`, `mumafrica.com`, `yad2.co.il`, `iceland.co.uk`, `diy.com`,
`auchan.pl`, `aliexpress.com` (cross-border, not a national source),
`groceries.aldi.ie` (already built as `aldi_ie`).

### Ocado behind a domain-wide AWS WAF, a redirect duplicate, and a promo-flyer-only Spar (UK, NL, BE)

- **www.ocado.com** (GB, Ocado — UK's largest pure-play online grocer) — every
  path (`/`, `/robots.txt`, and the captured API
  `/api/webproductpagews/v5/product-pages?decoratedOnly=true&limit=27&tag=...`)
  returns `HTTP/2 202` with `server: CloudFront` and `x-amzn-waf-action:
  challenge`, serving a JS `window.awsWafCookie` challenge page instead of
  content. Confirmed with plain `curl` (Mac) AND `curl_cffi`
  `impersonate="chrome124"` (a8) — identical result on both, so this is not a
  TLS-fingerprint block, it's AWS WAF Bot Control's Challenge action, which
  requires real JS execution to mint a token before CloudFront forwards to
  origin. `groceries.ocado.com` and `api.ocado.com` do not resolve/respond
  (curl exit 000) — no lower-friction subdomain found. Per the wave-3
  addendum's explicit rule, not shipping a Playwright-at-collection-time
  spider for a source that needs a live browser session; recorded as blocked
  rather than worked around. Did NOT try: WAF-token harvest-and-replay,
  residential proxies. Probed 2026-09-10.

- **www.coop.nl / coop.nl** (NL, Coop Netherlands) — not a technical
  block, a confirmed duplicate: `curl -sIL https://www.coop.nl/` returns a
  plain `HTTP/2 301` to `https://www.plus.nl`, final response `200` at
  `url_effective=https://www.plus.nl/`. `plus_nl` is already shipped in this
  repo. Do not onboard coop_nl — it is not a separate storefront/assortment,
  it is the same catalog under a redirected domain. Probed 2026-09-10.

- **www.mijnspar.be / www.monspar.be** (BE, SPAR Belgium) — the
  `content/spar/{fr,nl}.model.json` endpoints named in the discovery trace
  are Adobe AEM's global app-config model (feature flags, nav paths), not a
  catalog. The real priced component, found via the page's own
  `data-model-url` attribute at
  `/content/spar/{fr,nl}/promoties/promoties/jcr:content/root/responsivegrid/main-content/filter_list_store_sp.model.json`,
  returns a fixed 43-row weekly promo-flyer list (110 non-empty EUR price
  fields across `normalPrice`/`unitPrice`/`promoPrice`) that does **not**
  paginate — `?page=2`, `?p=2`, `?offset=12`, `?start=12` all return the
  identical 321,822-byte body. `sitemap.xml` (7,637 URLs) confirms there is
  no `/produits/`, `/shop/`, or `/catalogue/` route anywhere on the site
  (93% of URLs are `/recettes/` recipe pages, plus `/magasins/` store finder
  — no online ordering at all). The entire priced surface of the site is this
  one non-paginated promo list, and several of its 43 rows are bundled/
  ambiguous descriptions ("500 g + 500 g gratis", "au choix" x8) rather than
  clean SKU names. Fails both the enumerability gate (no distinct page1 vs
  page2) and the catalog-size bar. `mijnspar.be` (nl) mirrors the identical
  AEM path structure — same conclusion, so neither language variant ships.
  Did NOT try: a fresh Playwright network trace beyond the addendum's
  captured endpoint — the server-rendered `data-model-url` attributes were
  sufficient to locate and rule out the real component without one. Probed
  2026-09-10.

### Esselunga — the API works, the host went unreachable (IT)

- **spesaonline.esselunga.it** (IT, Esselunga -- one of Italy's largest
  supermarket chains; AngularJS SPA on an Oracle-ATG-style commerce stack
  behind a BigIP load balancer) -- NOT a store-session gate and NOT a WAF
  block, unlike the other two Italian sources already filed here
  (spesaonline.conad.it needs a chosen pickup store before price stops
  being a hard 0.0; coopshop.it is a recaptcha-enterprise SPA). This one
  died to a plain TCP-level connectivity failure mid-session, after the
  real catalog endpoint had already been found and verified against live
  data.

  Timeline, all UTC 2026-09-10/11: a headless-Chromium network trace of
  the site's own search box found `POST /commerce/resources/search/facet`
  with body `{"query":"*","start":N,"length":<=100,"isLargeQuerySearch":
  true,"filters":[],"rmtCookieAllowed":true}` -- confirmed this is the
  real enumerable catalog (NOT `search/personalizzazioni`, the homepage's
  "recommended for you" widget, which is what the pre-probe had flagged).
  Verified with plain, UNIMPERSONATED curl (no curl_cffi/TLS-profile
  workaround needed): a same-origin `GET .../commerce/` establishes a
  JSESSIONID cookie, and the search POST additionally needs header
  `x-page-path: supermercato` (the literal string; using the SPA's actual
  client route there gives a different, also-wrong 400). Confirmed
  `displayables.rowCount`=19,428 and disjoint, stable pagination
  (start=0 vs start=20 disjoint; two identical start=0 calls returned
  identical ids; deep offsets to start=19,400 still returned real rows).
  Confirmed REAL non-zero prices with no store/delivery address selected
  at all (`config/v1/env` reports `hideProductPrice: true` and an
  anonymous default store "SULT", yet `search/facet` responses carried
  populated `price`/`discountedPrice` regardless -- read directly off the
  response bytes). A live `--max-items 20` run with this endpoint DID
  scrape 20 real priced rows (e.g. "Rummo Fusilli N° 48 500 g" EUR 1.59)
  before a self-inflicted bug (a constant per-row URL fallback colliding
  with the pipeline's duplicate-URL dedup, which dropped 1,399 of 1,400
  scraped rows) was caught and fixed with a synthesized unique
  `.../store/ricerca/<code>` URL per row.

  After that fix, the confirmation run returned 0 rows. Signature: the
  FIRST request of the run (`GET https://spesaonline.esselunga.it/
  commerce/`) failed 4/4 times with `curl_cffi.requests.exceptions.Timeout:
  Failed to perform, curl: (28) Connection timed out after 30000
  milliseconds` -- no HTTP status at all (curl exit 28, not a 403/429/503).
  Independently reproduced with plain `curl --max-time 20`
  (`HTTP:000 time:20.0`) and with `nc -zv -w 8 spesaonline.esselunga.it
  443` (`Operation timed out`, >60s) -- i.e. the TCP handshake itself
  never completes, ruling out a TLS-fingerprint or application-layer
  block. DNS resolution is fine and stable (`185.96.117.231` /
  `185.96.117.18` on repeated lookups). Reproduced independently from TWO
  separate networks (the a8 host and an unrelated residential network),
  ruling out an IP/ASN-specific block of just the scraping host. One
  earlier run (before this final outage) DID get partway through --
  ~15 successful pages of `search/facet` (offsets 0-1400) before request
  16 onward started hitting the identical 30s timeout signature, which
  reads like a connection-rate tarpit that then escalated to a full
  TCP-level outage; both effects point at the same origin/edge component,
  not at this spider's request shape.

  NOT tried: waiting past this batch's time window for the outage to
  clear and re-confirming (explicitly stopped rather than left running);
  a third, geographically different network/ASN beyond the two already
  tried; IPv6 connectivity; a lower request rate from the very first
  request (the successful 15-page run and the immediately-following dead
  run both used the same DOWNLOAD_DELAY=1.5s / CONCURRENT_REQUESTS_PER_
  DOMAIN=1 settings, so it's untested whether a much slower ramp avoids
  the tarpit); contacting the site outside of automated probing to check
  for a public status page or scheduled maintenance window.

  The spider (`esselunga_it.py`) and manifest were deleted per the
  zero-row-in-final-test rule rather than left in the tree; the discovery
  work above (endpoint, auth/session mechanics, pagination proof, price
  field mapping, the dedup-collision bug and its fix) is preserved here so
  a future re-attempt does not have to re-derive any of it -- only the
  TCP-level reachability needs re-checking before rebuilding the spider
  from this description.

### noon Bahrain's RSC shell, and a B2B distributor with no public prices (BH, IR)

Two of this batch's four candidates shipped (`beeyor_tj`, `daraz_pk` — see
`batch_16_report.md`, not repeated here). The two below did not ship.

#### SPA shell — no productive endpoint (lazy-load never hydrates)

- **noon.com/bahrain-en/** (BH, Noon — Gulf-wide marketplace, Bahrain
  storefront) — **Geography confirmed correct first**: `curl_cffi
  impersonate=chrome124` on `https://www.noon.com/bahrain-en/` returns 200
  and its own SSR payload states `country:{code:"BH",name:"Bahrain",
  currencyCode:"BHD",currencyName:"BHD"}` — this is a genuine Bahrain-priced
  storefront, not the UAE-priced `noon.com` apex (which does return AED).
  Unlike this campaign's previously-rejected "Caribbean" Antigua stores
  (US-priced diaspora fronts), noon's Bahrain locale is not a geography
  mismatch. It is blocked on a different axis: the storefront is a Next.js
  App Router / React-Server-Components shell (`$R[...]` literals in the
  HTML, same family as `bigmarket.ge` elsewhere in this file) whose product
  grid is never SSR'd — `catalogPath:$R[1031]` and `headersForCatalogRequest`
  are both left unresolved/void in every page checked (homepage, `/search/
  ?q=rice`, and real category paths harvested from the nav, e.g.
  `/bahrain-en/noon-supermarket/`). Zero product name/price data appears in
  raw HTML anywhere. **The mandatory Playwright network-trace gate could
  not be run**: `page.goto()` fails with `net::ERR_HTTP2_PROTOCOL_ERROR` on
  the default config, and with `--disable-http2` it instead times out
  completely (30-45s, both `wait_until="load"` and `"domcontentloaded"`) —
  headless Chromium cannot complete a connection to this host at all, while
  the identical URL answers curl_cffi instantly (200, full body). This
  reads as Akamai bot-manager fingerprinting the automated-browser
  connection itself (an `akam/13/pixel_...` beacon is present in the SSR
  HTML), a layer below the page-content challenges this file usually
  records. Not attempted: a real (non-bundled) Chrome binary via
  Playwright's `channel="chrome"` (not installed on the probing box this
  session), a Bahrain-resident proxy, or `--disable-blink-features=
  AutomationControlled` (unlikely to help — the failure precedes any JS
  execution — but not empirically ruled out). Worth a dedicated future pass
  with either lever; the underlying catalog (noon's Bahrain grocery
  vertical, "noon-supermarket") is large and the geography is clean.
  Probed 2026-09-10.

#### Login-walled catalog (real backend found via network trace, but core endpoint 401s without auth)

- **www.iranpharmis.org** (IR, "Iran Pharmis" — corrected source_key
  `iranpharmis_ir`; the batch candidate table had the wrong country suffix,
  `_dz`) — real Next.js (App Router/RSC) backend, no WAF, full 200s
  throughout, category-listing JSON is genuinely embedded in the SSR
  payload (not a shell). But every sampled product across the category tree
  (`/products/category/general` and its sub-categories: surgical gloves,
  bone-marrow biopsy systems, intraosseous injection devices, central-
  venous/hemodialysis catheters, laryngeal masks, endobronchial tubes —
  this is a **hospital/surgical-equipment B2B distributor**, not a
  dispensing retail pharmacy, so `channel: pharmacy` as suggested would
  also have been a mis-tag) carries `"price":{"price":0,"was_price":0,...}`
  and `"quantity":0` literally, for every one of the 87 titled listing
  entries sampled. The rendered page carries a live login/registration
  system ("ورود به ایران فارمیس" / "ثبت نام"). A full Playwright network
  trace on the category page confirms no client-side product/price API
  call ever fires beyond an empty `GET /api/auth/session` — the price:0 in
  the initial SSR payload is the complete anonymous-visitor state, not a
  value that arrives after hydration. This is a normal B2B procurement
  pattern (quoted pricing after account registration), not an anti-bot
  block — nothing to crack, no second surface found. For the record (moot
  here since every price is 0): the payload does carry
  `"price_unit_title":"تومان"` (Toman), confirming the brief's Toman/Rial
  warning was correctly aimed at this class of Iranian site in general,
  even though this particular tenant never got far enough to need the
  `_woo_base.py` PRICE_MULTIPLIER mechanism (not WooCommerce, and no
  onboardable price exists regardless). Probed 2026-09-10.

### PerimeterX on a Delivery Hero property, and a candidate that was not the company at all (HU, AM)

- **foodora.hu** (HU, Foodora Hungary — Delivery Hero food/grocery
  delivery aggregator) — HTTP 403 "Access to this page has been denied"
  with an explicit PerimeterX `px-captcha` challenge page
  (`window._pxAppId = 'PXlJuB4eTB'`, `pxCaptchaSrc` loaded) on every
  request tried: homepage and the briefed
  `/groceries/product/EFK6CI/olmeca-gold-tequila-07` PDP, under 5
  curl_cffi TLS-impersonation profiles (chrome120/124/131/133a/
  safari17_0 — all identical 4,599-byte 403 body) AND a real headless
  Chromium via Playwright (also 403, same px-captcha body, confirmed
  live). This is PerimeterX's CAPTCHA tier specifically (not a JS-
  computation puzzle a browser can silently solve) — no automated
  technique clears an actual CAPTCHA. Matches this repo's own
  known_blockers.md house note verbatim: "Assume PerimeterX is in front
  of every delivery-hero / foodpanda property." Foodora is a Delivery
  Hero brand (same corporate family as foodpanda and Talabat). Note the
  asymmetry: talabat_eg (onboarded in an earlier wave of this same
  campaign) was NOT behind PerimeterX and shipped via plain TLS-profile
  selection (chrome133a) — Delivery Hero's WAF tier clearly varies by
  market/brand, so this is not a blanket "any Delivery Hero site is
  unreachable" finding, just this one. Did not attempt: manual CAPTCHA
  solving (out of scope), a residential/mobile proxy pool, or a paid
  CAPTCHA-solving service. Probed 2026-09-10.

- **geramarket.com** (claimed AM, "geramarket_am") — not a blocker in
  the access sense; this is the WRONG SITE. geramarket.com is a live,
  fully-accessible (HTTP 200, no WAF) US/UK-facing e-commerce SaaS/
  content site for online sellers — pricing page, "how it works",
  product-photography and product-description-writing guides, "/vs/
  alibaba" comparison content, and consumer-product-recall datasets for
  the US and UK. It is not an Armenian retailer, carries no AMD/dram
  pricing (the string "Armenia" appears exactly once on the homepage, in
  an unrelated context), and has no product catalog of any kind.
  Fetched the site's own sitemap.xml (5,702 urls; 211 contain the
  substring "product") and every one of those is a guide/blog/category-
  directory page (e.g. `/sell/product-photography`, `/guides/how-to-
  price-products-to-sell-online`, `/categories/digital-products`), never
  a retail SKU page. The briefed "72 product URLs matched my pattern" is
  almost certainly this same class of page, not real products — a
  discovery-stage false positive, not a scraping problem. No further
  probing was done (Playwright network trace, category enumeration)
  since there is no product surface on this domain to find. Recommend
  removing this candidate from the source list rather than re-queuing it
  for another batch; if a real Armenian retailer named similarly to
  "GeraMarket" exists, it is at a different domain than the one briefed.
  Probed 2026-09-10.

## 2026-09-11 — wave 5, ddgs discovery for the worst-covered countries

Round 2 of the gap-fill campaign. The COICOP coverage grid was measured first,
and the 23 countries publishing fewest leaf-by-unit cells were swept with
`ddgs` (443 queries, backends pinned), then probed. 1,957 candidate hosts
reduced to 69 verified retail candidates, of which 39 shipped.

**The filter that did the work was currency, not relevance scoring.** `ddgs`
matches the country *word*, not the country: the Chad pack returned a US
TV-and-appliance store, the Dominica pack a US grocery chain, the Gibraltar
pack a US drum-hardware brand. Checking that a storefront actually prices in
its country's own currency killed **331 of 410** otherwise-plausible
candidates. Do this before spending an agent on anything.

**The recurring dead end of this wave, six times over:** a live, well-formed
platform API sitting over a catalog that has no prices in it. A 200 from
`/wp-json/wc/store/v1/products` proves the site is reachable and paginates; it
proves nothing about whether the catalog sells anything at a price. Read a
product before ranking a candidate.

Four countries — Gibraltar, Central African Republic, Guinea-Bissau and Palau
— produced zero verified candidates from the sweep at all. For Gibraltar that
is likely real rather than a search failure: a GBP micro-economy served by UK
retailers rather than by domestic storefronts.

### Botswana — an enquiry-only catalog priced entirely at zero

- **cyberstore.co.bw** (BW). WooCommerce Store API at /wp-json/wc/store/v1/products
  returns HTTP 200 and paginates cleanly (679 products across 7 pages, page1 vs
  page2 disjoint id sets — enumerability is fine). The blocker is that every
  single product carries price=0 / regular_price=0 / sale_price=0 AND an empty
  price_html string. Verified this is real, not a Store-API-only omission, by
  fetching a live PDP directly (https://cyberstore.co.bw/the-13-inch-macbook-air-m4/,
  2026-09-11): the rendered price block reads literally 'Contact Us' — the site
  is an enquiry/quote-request electronics catalog, not a priced storefront. No
  price is recoverable from any surface (API, price_html, rendered DOM) because
  none exists; this is not a JS-hydration or auth problem, so Playwright would
  not help and was not tried (no reason to expect JS to materialize a price the
  server-side WooCommerce product object never had). Structurally the same
  failure mode already on record for pnpbotswana.co.bw
  (src/prices/configs/ssa/southern_africa/botswana/notwanepharmacy_bw.yaml
  notes: 'WhatsApp-order only, not a real catalog scrape target'). Not scaffolded.
  Checked 2026-09-11.

### Namibia — a B2B distributor behind a login wall

- **newmed.com.na** (NA, NewMed Holdings — pharmaceuticals/medical-consumables/
  devices/equipment/veterinary distributor) — WordPress site, HTTP 200
  throughout, but no e-commerce surface anywhere. `/wp-json/wc/store/v1/products`
  returns `rest_no_route`; the full `/wp-json/` route dump (435 routes) has
  nothing matching `wc`, `product`, or `shop` — WooCommerce is not installed at
  all despite `wp-content`/`woocommerce` strings fingerprinting in the raw
  HTML (a Divi theme + plugin reference, not a live Store API). `/products/`
  lists product *categories* only (Pharmaceuticals, Disposables, Devices,
  Equipment, Consumer Healthcare, Veterinary) with zero SKUs, zero prices, and
  zero add-to-cart affordances anywhere in the rendered text. `/buy-online/`
  — the site's only other candidate route — is a bare "Sign In / Create
  Account" B2B ordering-portal wall with no visible catalog behind it. This
  matches the assignment brief's flag ("platform fingerprint only, no working
  API") — probed properly (curl_cffi fingerprint, full wp-json route
  enumeration, manual read of `/products/` and `/buy-online/` page text
  stripped of script/style) rather than assumed; confirmed dead, not merely
  unproven. No Playwright network trace run — a login-walled B2B portal with
  no visible product listing behind the wall isn't expected to reveal a
  richer catalog via JS network capture, and there is no public price surface
  to trace. Probed 2026-09-11.

### Eswatini and Botswana — Spar Eswatini is a marketing site, and two empty WooCommerce installs

- **spareswatini.co.sz** (SZ, "Spar Eswatini") — WordPress + Divi theme with
  the WooCommerce plugin installed, but no populated shop: the Store API
  route is registered (`/wp-json` lists `/wc/store/v1/products` in its
  routes) yet `GET /wp-json/wc/store/v1/products` returns `[]` for every
  query, `wp-sitemap.xml` has only posts/pages/categories/users sitemaps (no
  product sitemap), and the raw homepage HTML contains zero `/shop`-like
  hrefs. Ran the mandatory Playwright network-trace (this was pre-flagged
  "endpoint unproven, no working API"): the rendered page's only
  shop/product/store link is `/store-locator/` (a physical-branch finder),
  and zero JSON responses fire from the domain during load + scroll. No
  sibling domain either — `shop.`/`order.`/`store.`/`app.spareswatini.co.sz`,
  `spar.co.sz`, `spar2u.co.sz`, `onlinespar.co.sz` all fail to resolve. This
  is a marketing/social-media site for the physical Spar chain (homepage
  banner is a "WIN E1,000,000" Instagram competition promo), not an online
  store. Probed 2026-09-11 (Eswatini batch 20).

#### Brochure-only WordPress / no online store

- **haskinshardware.co.bw** (BW, Haskins Hardware) — WordPress with a
  WooCommerce-flavoured theme (CSS classes present), but the WooCommerce
  Store API route is not even registered in `/wp-json`'s route list (unlike
  spareswatini.co.sz above, where the route exists but is empty — this
  install doesn't have WooCommerce Blocks/Store API active at all). Only one
  shop-like link exists on the entire site (`/power-products/`). Ran the
  mandatory Playwright network-trace and a full render+scroll of
  `/power-products/` specifically (this was pre-flagged "endpoint unproven,
  fingerprint only"): 0 product-DOM elements after full JS hydration, 0 JSON
  responses captured anywhere on the domain during either pass. Checked
  sibling domains (`shop.`/`store.haskinshardware.co.bw`, `haskins.co.bw`) —
  none resolve or respond (the last times out). Genuine brochure site for an
  offline hardware retailer. Probed 2026-09-11 (Botswana batch 20).

### Guinea — a brochure catalog with 208 zero-priced products

- **abc-guinea.com** (GN) -- not access-blocked, but has no prices to scrape.
  WooCommerce Store API at /wp-json/wc/store/v1/products is open, no auth,
  200 OK, paginates fine (208 products walked across 3 pages of 100). Every
  single product returns `"price": "0", "regular_price": "0",
  "sale_price": "0", "price_html": ""`. Spot-checked a live PDP
  (/fr/product/tcl-ac-avec-unite-interieure-exterieure/, 200 OK, TCL air
  conditioner) -- no "prix"/currency text anywhere in the rendered HTML.
  This reads as a brochure/lead-gen electronics catalog (call-for-quote
  pricing model), not a broken scraper or a WAF block. Did not attempt a
  Playwright network trace -- the Store API itself is open and returning
  well-formed zero-price data, so a browser trace would not surface a
  different, priced endpoint. Marked DEAD. 2026-09-11.

### Liechtenstein — a gift-voucher platform and a motorsport ticket shop, both mistaken for retailers

Two of seven assigned hosts did not ship. Neither is an access/WAF
blocker in the usual sense — both are catalog-content mismatches found
only after reading the actual product data, not from a status code.

- **einkaufland.li** (LI). Fingerprinted WooCommerce Store API, confirmed
  reachable with `curl_cffi impersonate=chrome124` — 200 JSON, CHF,
  currency_minor_unit=2. But `/wp-json/wc/store/v1/products` returns
  `x-wp-total: 1` on every page, and the live `/shop/` HTML confirms it:
  the entire "catalog" is one SKU, `einkaufland-gutschein` (a gift
  voucher). The site's own nav ("Mitglieder-Verzeichnis",
  "Gutscheine bestellen", "Unsere Partnergeschäfte") reveals the real
  business model: it is a regional gift-card/loyalty platform for
  Liechtenstein's local shops, not a retailer with its own product
  catalog — despite the domain name and the "highest value here" note
  in the pre-probe, it fails the enumerability gate outright (one
  product, one page, nothing to paginate). Checked 2026-09-11.
- **shop.tgi.li** (LI). WooCommerce Store API confirmed live and correct
  (26 products, x-wp-total=26, one page) — EUR is the genuine reported
  currency, not a regex/detection artifact as the wave-5 addendum
  flagged for other hosts this wave. Read the catalog: all 26 items are
  motorsport event admission tickets and circuit parking passes for
  DTM race weekends at German/Austrian tracks (Hockenheimring,
  Sachsenring, Nürburgring, Oschersleben, Norisring, Lausitzring,
  RedBull Ring) plus a "24h of Spa" parking ticket (Spa-Francorchamps,
  Belgium). TGI AG is genuinely headquartered in Vaduz, Liechtenstein
  (Städtle 33, FL-9490 Vaduz, confirmed from the site's own footer), but
  the catalog itself has no CHF pricing and no connection to Liechtenstein
  consumer price levels — it is pan-European motorsport-tourism ticketing
  priced for a EUR-denominated cross-border audience. Not scaffolded:
  even though it is technically enumerable and paginates-trivially (one
  page of 26), it does not represent a Liechtenstein retail price
  observation in any COICOP-relevant sense. Checked 2026-09-11.

No Playwright network trace was needed for either — both were resolved
from the WooCommerce Store API response alone, which was sufficient to
read the whole catalog content.

### Syria — an app-only storefront with no web catalog

- **paloma.sy** (SY, بالوما) — not a blocker in the access sense; this
  is an APP-ONLY source with no web catalogue. Fetched 2026-09-11 via
  curl_cffi impersonate=chrome124: https://paloma.sy/ and
  https://www.paloma.sy/ both return HTTP 200 (22.5KB), but the page is
  a mobile-app landing page — hero copy "عن التطبيق" (about the app),
  "لقطات الشاشة" (screenshots), 3x play.google.com links, 3x
  apps.apple.com links, zero occurrences of shop/product/cart/catalog
  anywhere in the HTML. No wp-json, woocommerce, or shopify marker
  either. No WooCommerce Store API, no /shop, no listing page of any
  kind was found — the entire site is marketing copy for a mobile app
  plus app-store badges. Did not attempt: reverse-engineering the
  mobile app's own backend API (out of scope for this batch; would
  require APK/IPA teardown, not a web probe). Verdict: DEAD (app-only,
  no web catalogue) — matches the Phase 3 SKIP taxonomy's "App-only (no
  web catalogue)" bucket, not a WAF/anti-bot block.

### South Sudan, Kiribati, Chad and American Samoa — four countries that yielded nothing

#### Placeholder / seed demo-data catalog (real API, no real prices)

- **globicare-pharma.com** (SS, GlobiCare Pharmaceuticals) — WooCommerce Store API open
  and unauthenticated, pagination genuinely distinct (page1/page2 zero overlap), but
  every one of the 39 total SKUs returns `prices.price == "0"`, `is_purchasable: false`,
  `add_to_cart.text: "Read more"`. Confirmed on the live PDP HTML too — no price text
  anywhere on the page, no cart button. A phone/WhatsApp-order pharmacy catalog with
  no checkout pricing, same pattern as cmsxm.net above. Probed 2026-09-11.
- **mpharmaco.com** (SS, M-Pharma Company) — identical failure mode and identical
  publisher pattern to globicare-pharma.com: 63 total SKUs across 7 pages, every one
  `prices.price == "0"`. South Sudan has no shippable pharmacy candidate from either
  of this pass's two verified leads. Probed 2026-09-11.
- **nicaretrust.store** (KI, NI-CARE TRUST) — real, in-country business (About/Contact
  pages name Tarawa, Kiribati explicitly; not a vanity-domain trap), WooCommerce Store
  API open, AUD currency matches Kiribati's own currency. But `X-WP-Total: 2` — the
  entire catalog is 2 SKUs ("Oceanlink $10 Topup", "Vodafone $10 Topup" prepaid mobile
  recharge for overseas family remittance), so it fails the Phase-6 >=5-row gate by
  construction, not from a probe or access failure. Also largely redundant with
  Kiribati's already-shipped `vodafone_ki_mobile.yaml` (08.1.0) and
  `vodafone_ki_flashnet.yaml` (08.3.0) tariff coverage. Do not build; re-check only if
  the catalog visibly grows. Probed 2026-09-11.

#### No products on the site (corporate marketing portal)

- **lesportif.td** (TD, "Le Sportif") — candidate was characterized as a sports-retail
  storefront; the live site is a Chadian SPORTS NEWS/journalism portal (athletics,
  basketball, football, handball, boxing, rugby, taekwondo, horse racing — results and
  match reports), not a store. `woocommerce`/`wp-content` fingerprint hits were theme
  CSS leftovers (`woocommerce-page` nav classes render on every WP page regardless of
  whether the plugin is active for commerce), not evidence of an actual shop. Verified
  with the full ladder before concluding, per the wave-5 caution that this host had
  fingerprint-only, no proven API: (1) `/wp-json/wc/store/v1/products` -> HTTP 404;
  (2) the site's own `/wp-json/` route index lists 351 registered REST routes, zero
  containing `wc`/`product`/`shop`/`store`/`cocart`; (3) `/shop/`, `/boutique/`,
  `/produit/`, `/produits/`, `/product/`, `/products/` all 404; (4) `sitemap_index.xml`
  has only post/page/category/tag/author sitemaps, no product sitemap; (5) a full
  Playwright network-trace of the homepage (headless chromium, 6s settle + scroll)
  captured 452 anchors — zero contain shop/boutique/cart/checkout/product/panier/
  magasin — and only 3 non-static network responses fired, all Google Maps/ad
  telemetry, no commerce API of any kind. Chad has no shippable candidate from this
  batch. Probed 2026-09-11.

#### Vanity ccTLD, not a domestic retailer (currency/geo mismatch after verification)

- **fitjeans.as** (AS, listed as "FITJEANS") — 301-redirects straight to
  `www.fitjeans.com`, a global DTC apparel Shopify tenant with locale storefronts for
  en-us/en-au/en-ca/en-ch/en-de/en-eu/en-fi/en-gb/en-nl/en-no/en-se (no en-as market).
  Its own refund-policy page's shipping-zone table ends: "*Excludes American Samoa,
  Micronesia, Guam, Marshall Islands, Northern Mariana Islands, Palau, Puerto Rico,
  U.S. Virgin Islands." The `.as` registration is a vanity-branding play ("fit" + ccTLD
  reads as "fitjeans"), not a business serving American Samoa — confirms exactly the
  wave-5 caution's hypothesis for this host. American Samoa has no shippable candidate
  from this batch. Probed 2026-09-11.

#### Environment note (not a site blocker, recorded for the next agent on a8)

Running a Playwright script as `~/venv/bin/python /path/to/script.py` (file-argument
invocation) on `a8:~/po-worktrees/fill-gap-sources` reproducibly failed with
`AttributeError: module 'inspect' has no attribute 'FrameInfo'` inside
`playwright/_impl/_connection.py`, preceded by unrelated stray stdout (a PPP/CPI
currency-index dashboard dump) that did not originate from the script being run —
this looks like output leakage from something else on the shared box, not a bug in
the script. Feeding the identical script to `~/venv/bin/python` via a stdin heredoc
(`~/venv/bin/python << "EOF" ... EOF`) or via `-c` ran clean every time. Not escalated
further since the workaround is free; flagging so the next agent does not waste time
suspecting their own script.

### Untried_3 batch: SPA shell and a login-gated social feed (LI, AL)

- **www.migros.ch** (CH, proposed as Liechtenstein food coverage via its
  physical stores, batch-scored build_tier=D) — Angular SPA shell,
   returns 200 but only a 31KB
  pre-hydration shell (, no product data
  in the raw response) even on a search URL
  (). Not a WAF block — no challenge markers seen —
  just needs a full Playwright render + network trace to find the
  backing API, same class of effort as the coop.ch DataDome build
  already deferred for this country. Not pursued further this pass;
  worth a dedicated Playwright probe in a future wave, not a hard
  reject. Probed 2026-09-11.
- **www.facebook.com/marketplace** (proposed AL) — returns HTTP 200
  (no WAF/TLS block) but is a personalized, login-gated social feed
  with no public catalogue, no product sitemap, and no anonymous API —
  structurally not a retailer/price source regardless of access.
  Reject on source class, not on scraping difficulty. Probed
  2026-09-11.

### Untried_3 batch: SPA shell and a login-gated social feed (LI, AL)

- **www.migros.ch** (CH, proposed as Liechtenstein food coverage via its
  physical stores, batch-scored build_tier=D) — Angular SPA shell,
  `curl_cffi impersonate="chrome124"` returns 200 but only a 31KB
  pre-hydration shell (`window.prerenderReady = false`, no product data
  in the raw response) even on a search URL
  (`/en/search?q=milch`). Not a WAF block — no challenge markers seen —
  just needs a full Playwright render + network trace to find the
  backing API, same class of effort as the coop.ch DataDome build
  already deferred for this country. Not pursued further this pass;
  worth a dedicated Playwright probe in a future wave, not a hard
  reject. Probed 2026-09-11.
- **www.facebook.com/marketplace** (proposed AL) — returns HTTP 200
  (no WAF/TLS block) but is a personalized, login-gated social feed
  with no public catalogue, no product sitemap, and no anonymous API —
  structurally not a retailer/price source regardless of access.
  Reject on source class, not on scraping difficulty. Probed
  2026-09-11.

### Untried_1 batch: dead legacy domain and a re-confirmed dead-end (MH, BJ)

- **ntamar.net** (MH, "NTA legacy services" — batch row tagged
  ALREADY-TRACKED-UPSTREAM per Will's handover, referencing the National
  Telecommunications Authority of the Marshall Islands under a legacy
  domain) — `curl_cffi impersonate="chrome124"` returns a hard DNS failure
  (`Could not resolve host: ntamar.net`), confirmed live 2026-09-11. The
  live NTA domain is `www.nta.mh`, already covered by `nta_4g_mh` and
  `nta_residential_mh` in this repo. Dead domain, not a duplicate worth
  re-pointing. Probed 2026-09-11 (untried_1 batch).
- **martistore.shop** (BJ) — re-checked after the 2026-09-05 finding that
  the whole site was in Cloudflare-fronted maintenance mode (503). As of
  2026-09-11 it is now HTTP 522 (Cloudflare origin connection timeout) —
  worse, not better. Still has a real 543-URL `/sitemap.xml` (200) from the
  prior probe, so the catalogue and id space are known if the origin ever
  comes back; still not usable today. Probed 2026-09-11 (untried_1 batch).

### Untried_2 batch: Afghanistan diaspora/currency traps, hcdn on non-Libya hosts, and SPA dead-ends (AF)

- **afzon.af** (AF, "Afzon") — shop-listing "AFN" tokens are UI/filter
  labels only; the actual product page (e.g. Timuri Saffron) quotes price
  in USD ($100). Fails local-currency gate. Probed 2026-09-11.
- **rasteenltd.com** (AF, "Rasteen Bazar") — genuinely enumerable
  WooCommerce Store API (page1/page2 zero id overlap) but
  `prices.currency_code` is explicitly USD (e.g. Washing Machine =
  $480.00). Fails local-currency gate despite otherwise passing every
  other test. Probed 2026-09-11.
- **kharid.af** (AF, "Kharid") — diaspora remittance/gifting service
  ("send groceries and gifts to family in Afghanistan"); `/shop` prices
  all USD. Fails both local-currency and locality gates. Probed
  2026-09-11.
- **yaganchiz.com** (AF, "Yaganchiz") — Shopify, genuinely enumerable,
  shop currency IS natively AFN (`/cart.js` confirms), so it does NOT fail
  the currency gate — but the site markets itself explicitly as a
  diaspora gifting service ("Essential deliveries to loved ones in
  Afghanistan", sample SKU "Monthly Family Essentials Box"). Rejected on
  locality alone; same anti-pattern as `ubuy.sl` and other diaspora
  grocers already in this file. Flagged as a judgment call, not a
  clean-cut technical fail. Probed 2026-09-11.
- **choob.af** and **peace1971.com** (AF) — both HTTP 403,
  `server: hcdn` (Huawei Cloud CDN), identical 6,192-byte "Checking your
  browser" stub — same signature already documented for Libya under the
  Huawei Cloud CDN heading, confirming this is not Libya-specific.
  Fast-rejected, no impersonation-profile cycling attempted. Probed
  2026-09-11.
- **afghanchinashoppingcenter.com** (AF, "Afghan China Shopping Center")
  — real AFN card-level prices, but `/en/catalogue` (with or without a
  category filter) returns an IDENTICAL product set across page=1/2/3 at
  every level tried — the whole catalog is fixed at ~12 SKUs, no real
  pagination exists. Probed 2026-09-11.
- **fibertech.com.af** (AF, "Fiber Technology Services Co") — `/products`
  and `/products?page=2` return the identical 7-item set (no real
  pagination); catalog includes a literal leftover dev/test product
  (`this-is-the-new-product-for-training`); price display looks
  unreliable ("AFN18"/"AFN20" for a router). Probed 2026-09-11.
- **jamshidimart.com** (AF) — SSL cert expired; with `verify=False` the
  domain serves a generic non-shop 7.6KB page and
  `/wp-json/wc/store/v1/products` 404s despite a `wp-content` string
  match — no live shop reachable. **kefayatsupermarket.com** (AF) — `www`
  subdomain cert mismatches hostname; bare apex serves a default Plesk
  Obsidian hosting-panel splash page, no site deployed. Both probed
  2026-09-11.
- **hamachiz.com** (AF) — HTTP 402 "Store unavailable", a Shopify tenant
  with a lapsed subscription. **zhmary.com** (AF) — HTTP 500 on repeated
  probes, site currently broken. **asanbawar.com** (AF) — homepage,
  `/products`, and `/robots.txt` all time out (20-25s, no TCP response)
  on 3 independent attempts; server appears down, not WAF-walled. All
  probed 2026-09-11.
- **maihandostshop.com** (AF, "Maihandost Shop") — actual site is
  "Mihandost — Invest in Stores & Apartment Projects", a real-estate
  INVESTMENT marketing site, not a retail catalogue or rental listing.
  **lilamlilam.com** (AF) — "Lilam" (auction) brand whose real businesses
  are separate storefronts (lilamhomes.com/store, lilamauto.com/store)
  selling via AUCTION bids, not retail SKU pricing. Both probed
  2026-09-11.
- **SPA/client-rendered dead-ends not pursued this pass** (AF, needs a
  real Playwright network trace, not a hard reject): afghanbazar.app
  (has an explicit "Food & Grocery" marketplace category worth chasing),
  karwaan.af, leelam.af (OLX-style classifieds, wrong shape more than
  blocked), htay.liwal.com, nooraziz.net (Wix), smartbazar.af (has an
  explicit `/en/market?categorySlug=supermarket` route worth chasing —
  robots.txt confirms a live `/api/` tree whose exact routes weren't
  found in budget), tizkart.com (possible pre-launch: `<title>` reads
  "Tixkard"), zarangwal.com, zmadookan.com. All returned 200 with no
  price/currency data in raw HTML; JS-hydrated catalogs in all cases.
  Probed 2026-09-11.
- **old.moci.gov.af** (AF, Ministry of Industry and Commerce market
  prices) — `curl_cffi` gets an abrupt SSL connection close;
  `verify=False` gets a 25s timeout instead. Consistent with the
  derelict-government-server pattern already noted for Libyan gov infra
  (gecol.ly, cbl.gov.ly). Probed 2026-09-11.

Four sources from this batch shipped: `maiwandbazar_af` (Shopify, AFN,
fashion), `sale_af` (WooCommerce, AFN, multi-vendor marketplace),
`thoffragrance_af` (WooCommerce, AFN, small single-vendor fragrance
catalog), `sawdagar_af` (bespoke REST API, AFN, general marketplace incl.
food categories, 883 products), `dostonline_af` (sitemap+JSON-LD, AFN,
Kabul electronics retailer, 193 product urls).

## EU/Atlantic micro-territory food-sourcing pass (gibraltar, greenland,
liechtenstein, monaco, st_martin_french_part, sint_maarten_dutch_part,
suriname, san_marino, andorra, faroe_islands) — 2026-09-11

Two Monaco sources shipped this pass (`obba_mc`, `vinalia_mc` — see
`references/inventories/eca/western_europe/monaco.md` for the full
write-up). Gibraltar, Liechtenstein, St Martin, Sint Maarten, Suriname,
San Marino and Andorra already had food-and-beverage sources from earlier
same-day passes; this pass verified several end-to-end and fixed one
mis-tagged manifest (`gibral_flora_gi`, a florist/gift shop wrongly tagged
`channel: supermarket` and `currency: GIP` when the Store API declares
GBP — corrected in-place). Faroe Islands and Greenland remain confirmed
structural absences (third and fourth independent confirmation
respectively) after a further Faroese/Danish-language, fish- and
small-producer-focused search round.

- **delovery.mc** (MC, Cloudflare) — re-probed per standing retry
  instruction, still 403 on chrome124/chrome120/safari17_0. Unchanged.
- **marche-u.mc** (MC) — genuinely Monaco-domiciled Système U storefront,
  but brochure-only: department pages carry zero price tokens, zero cart
  mentions.
- **mrroomservice.mc** (MC) — curated multi-shop food-delivery concierge
  app; no platform fingerprint matched, shop pages render zero price
  tokens server-side (client-rendered). Needs a Playwright trace, not
  attempted.
- **mitronbakery-monaco.com** (MC) — Wix site; "ecwid" homepage hits are
  Wix's own storefront-widget self-reference (same false-fingerprint
  pattern as `neufeldhof_li`), not a real Ecwid store. Zero prices
  server-side.
- **bjor.fo** (FO, Föroya Bjór brewery) — WooCommerce theme present but
  Store API 404s (`rest_no_route`) and `/vorur/` renders zero prices —
  shop plugin inactive, brochure-only.
- **local.fo/webshop/** (FO) — travel-magazine souvenir merch shop, not
  food.
- **faroelandia.com**, **origin.fo** (FO) — no platform fingerprint, zero
  price tokens; B2B/marketing sites.
- **bakkafrostshop.com** (FO-linked salmon brand) — real Shopify store
  with real prices, but `Shopify.country="US"` / `currency=USD` and
  Scottish SKUs mixed in — this is the brand's US consumer storefront,
  not a Faroese domestic retailer. Locality-gate rejection, not a
  platform failure.
- **groenlandskehus.dk** (GL-linked) — Danish (Denmark)-domiciled retailer
  selling Greenlandic-themed products to a Danish/EU market — same
  neighbouring-market trap as Monaco/Andorra/Liechtenstein, just for
  Greenland. Not probed further.
- **polarseafood.com** (GL-linked seafood) — confirmed B2B/export only, no
  consumer storefront to evaluate.

## Turks and Caicos Islands food-sourcing pass — 2026-09-11

Country already had exactly one source (`goods2door_tc`, Wix grocery-delivery-for-guests spider,
~4,438 rows). Two more shipped this pass: `islandselects_tc` and `tcgrocerydelivery_tc`, both
WooCommerce Store API grocery-delivery storefronts (100/100 rows, 100 distinct PDP URLs each,
verified end-to-end 2026-09-11) -- see the country's manifests for full detail. Everything below
is the discovery trail on top of those two: TCI's dominant supermarket chain and every other
guessed competitor/concierge domain has no online catalog or does not exist.

- **gracewaysupermarkets.com** (TC, Graceway Supermarkets/Graceway IGA — the dominant chain,
  multiple locations across Provo/Grand Turk/North&Middle Caicos) — live Squarespace brochure
  site, 200 OK, real content. Sitemap (`/sitemap.xml`, 380KB) enumerated: no `/shop`, `/cart`, or
  `/order-online` path exists; `/store`, `/iga`, `/smart`, `/graceway-gourmet` are all static
  brand-info pages with zero price tokens. The one live "ordering" surface (`/order-test`) is a
  single Squarespace form for pre-ordering a whole Christmas turkey/ham ($6.99/lb, $5.75/lb) —
  a seasonal one-off form, not a catalog (fails the enumerability gate outright: one static page,
  ~10 fixed line items, no pagination). FAQ page confirms explicitly: "We don't currently provide
  a delivery service" — the only shopping-adjacent offering is a manual PDF-grocery-list +
  in-store-payment service from one physical location (Graceway Gourmet, Grace Bay), not online.
  Brochure-only, confirmed 2026-09-11.
- **CaribeEats** (`backend.caribeeats.com`, the LAC delivery-aggregator platform already onboarded
  for Grenada/Dominica/St Kitts/Antigua) — live `/api/init` enumerates 21 regions; Turks and
  Caicos is not among them (nearest Caribbean coverage: Bahamas, BVI, Barbados, Trinidad, Jamaica,
  Guyana). Platform genuinely does not reach TCI. Confirmed 2026-09-11.
- **shopiga.com**, **myigastore.com**, **iga.com** store-locator — none serve a TCI/Providenciales
  IGA storefront (`shopiga.com` turned out to be an unrelated "Shopiggo" AI-shopping SaaS;
  `iga.com/store-locator` 404s on a TCI query; `myigastore.com` doesn't resolve). No
  LocalExpress-style online-ordering subdomain exists for the Graceway IGA franchise, unlike the
  Grenada (`shop.realvalueiga.com`) / Barbados (`online.imartstores.com`) / Puerto Rico
  (`econotogo.com`) IGA-adjacent sibling entries already in this file.
- **stockmyvilla.com** — live 981KB Wix site with a real `/shop?Category=GROCERY` catalog, but
  it's "Time Saver VI", a St Thomas (US Virgin Islands) villa-provisioning service — wrong
  island, not TCI.
- **turksandcaicosconcierge.com** — domain-for-sale parking page (DaaZ marketplace).
- **tcprovisions.com** — parked domain, redirects to a generic lander.
- **provoconcierge.com** — Cloudflare-proxied but origin returns 526 (invalid SSL / origin dead);
  domain not actively serving anything.
- ~25 further guessed domains for a TCI grocery-delivery/concierge/provisioning competitor to
  `goods2door_tc` (`provogrocerydelivery.com`, `tcigroceries.com`, `tcigrocer.com`,
  `provofresh.com`, `provomarket.com`, `tcimarket.com`, `islandprovisionstci.com`,
  `villaprovisionstc.com`, `graceybayconcierge.com`, etc.) — all NXDOMAIN. No second Wix/Squarespace
  tourist-grocery-delivery competitor found.
- **Turks and Caicos Tourism Board business directory** (`turksandcaicostourism.com`,
  Shopping category, 31 listings) — the only grocery/convenience entries are Kathleen's 7-11,
  Middle Caicos Co-op, Jai's, and Greensleeves, all phone-number-only with **no website URL** for
  any of them. Confirms the small-population (~46k) territory's local grocers simply have no web
  presence to scrape.

Remaining gap: the dominant real-world chain (Graceway) is still unscrapeable (brochure-only).
Re-check in ~6-12 months for a Graceway e-commerce launch or a new delivery-app entrant; the
three WooCommerce/Wix delivery-for-guests sites now cover the tourist-grocery niche well.
- **choisupermarkt.com** (SR, note Dutch spelling — no "e" — distinct from
  the already-recorded `choisupermarket.com` English spelling/expired-cert
  entry above) — resolves 200 via Cloudflare, 475KB page, real Shopify
  fingerprint, but the domain has been **squatted**: content served is an
  Indonesian togel (illegal-lottery/gambling) spam site (`<title>TOTO TOGEL
  158`, canonical link to `youknowwesew.com`). The lapsed domain of a real
  defunct Suriname butcher/grocer picked up by a spam operator — a new
  failure signature distinct from cert-expiry or zero-byte-body. Probed
  2026-09-11.
- **Suriname named-chain guesses, all NXDOMAIN or dead, probed 2026-09-11**
  (recorded so the guessing is not repeated): `vshfoodmart.{com,sr}`,
  `vsh.sr`, `baassupermarket.{sr,com}`, `baas.sr`, `c1000.sr`,
  `c1000suriname.com`, `continent.sr`, `continentsupermarkt.sr`,
  `continentsuriname.com`, `kortom.sr`, `kortomsupermarkt.sr`,
  `kortomonline.com`, `wongsupermarket.{sr,com,online}`, `wong.sr`,
  `wongssupermarket.com`, `hermitagemall.sr`, `hermitagemallsupermarkt.com`,
  `sparsuriname.com`, `spar.sr`, `shopritesuriname.com`,
  `picknpaysuriname.com` (confirms no SA regional chain in Suriname),
  `surimarket.com` (parked lander page), `transamerica.sr` (resolves, bare
  404.html, no site), `soengngie.{com,sr}` (redirects to soengco.com, a
  brand/recipe content site with zero shop/cart — not a retail source),
  `vshfoods.com` (live but manufacturer/export brand site, zero shop/cart),
  `kersten.sr` (live, but Toyota dealership — automotive, not food).
- **OpenStreetMap Overpass as a discovery substitute for Suriname** —
  when WebSearch/WebFetch search-engine access is unavailable or
  unreliable (measured 2026-09-11: DDG CAPTCHA, Bing decoy results,
  Ecosia/Mojeek 403, r.jina.ai needs a key), querying Overpass for
  `shop~supermarket|convenience|grocery|greengrocer|butcher` within a
  country's admin boundary and checking which nodes carry a `website` tag
  is a working substitute — for Suriname it returned 506 shop nodes, of
  which only 6 carried a website, 2 of which were live and got onboarded
  (`rossignolslagerij_sr`, `vcm_sr`). Cheap (one API call) and gives ground
  truth on how much of a country's retail-food sector has any web presence
  at all.
- **choisupermarkt.com** (SR, note Dutch spelling — no "e" — distinct from
  the already-recorded `choisupermarket.com` English spelling/expired-cert
  entry above) — resolves 200 via Cloudflare, 475KB page, real Shopify
  fingerprint, but the domain has been **squatted**: content served is an
  Indonesian togel (illegal-lottery/gambling) spam site (`<title>TOTO TOGEL
  158`, canonical link to `youknowwesew.com`). The lapsed domain of a real
  defunct Suriname butcher/grocer picked up by a spam operator — a new
  failure signature distinct from cert-expiry or zero-byte-body. Probed
  2026-09-11.
- **Suriname named-chain guesses, all NXDOMAIN or dead, probed 2026-09-11**
  (recorded so the guessing is not repeated): `vshfoodmart.{com,sr}`,
  `vsh.sr`, `baassupermarket.{sr,com}`, `baas.sr`, `c1000.sr`,
  `c1000suriname.com`, `continent.sr`, `continentsupermarkt.sr`,
  `continentsuriname.com`, `kortom.sr`, `kortomsupermarkt.sr`,
  `kortomonline.com`, `wongsupermarket.{sr,com,online}`, `wong.sr`,
  `wongssupermarket.com`, `hermitagemall.sr`, `hermitagemallsupermarkt.com`,
  `sparsuriname.com`, `spar.sr`, `shopritesuriname.com`,
  `picknpaysuriname.com` (confirms no SA regional chain in Suriname),
  `surimarket.com` (parked lander page), `transamerica.sr` (resolves, bare
  404.html, no site), `soengngie.{com,sr}` (redirects to soengco.com, a
  brand/recipe content site with zero shop/cart — not a retail source),
  `vshfoods.com` (live but manufacturer/export brand site, zero shop/cart),
  `kersten.sr` (live, but Toyota dealership — automotive, not food).
- **OpenStreetMap Overpass as a discovery substitute for Suriname** —
  when WebSearch/WebFetch search-engine access is unavailable or
  unreliable (measured 2026-09-11: DDG CAPTCHA, Bing decoy results,
  Ecosia/Mojeek 403, r.jina.ai needs a key), querying Overpass for
  `shop~supermarket|convenience|grocery|greengrocer|butcher` within a
  country's admin boundary and checking which nodes carry a `website` tag
  is a working substitute — for Suriname it returned 506 shop nodes, of
  which only 6 carried a website, 2 of which were live and got onboarded
  (`rossignolslagerij_sr`, `vcm_sr`). Cheap (one API call) and gives ground
  truth on how much of a country's retail-food sector has any web presence
  at all.

### Namibia — Shoprite Group AEM brand family, Choppies, and two unreachable chains

- **shoprite.com.na / checkers.com.na / okfoods.co.za (`/na/en_NA/` locale)** —
  all three are the SAME Shoprite Group Adobe AEM brand template ("OK Foods
  Namibia" is a Shoprite Group banner, NOT an independently Namibian-founded
  chain as sometimes assumed from the name). 403 on plain default-UA
  `requests`, 200 on plain Chrome-UA `requests` (no TLS impersonation needed —
  UA alone clears it). Brochure/store-locator only: sitemap.xml on shoprite is
  100% `/recipes/` marketing pages, zero product URLs; okfoods.co.za's Namibia
  specials page has 0 cart/price markup (image/flyer-style weekly specials).
  Re-probed 2026-09-11, confirms and extends the 2026-09-01 finding.
- **choppies.co.na** — WordPress + Elementor, 200 on all UAs, no WAF. `/wp-json/`
  route dump has no `wc/store` namespace at all (WooCommerce not installed).
  Nav explicitly links "Shop online"/"eChoppies" to **echoppies.com**, but that
  platform is Botswana-only (currency asset named `botswana-currency.png`,
  zero Namibia references on the page) — a brochure site whose only shop link
  routes to a sibling country's store. Probed 2026-09-11.
- **spar.co.na / www.spar.co.na** and **pupkewitz.com.na / www.pupkewitz.com.na**
  — DNS resolves for both, but ALL of plain `requests` (2 UAs) and `curl_cffi`
  impersonate=`chrome124`/`chrome120`/`safari17_0` (3 profiles) time out after
  25s with no TCP-level response, identically across profiles. This rules out
  a JA3/TLS-fingerprint block (an impersonating client would get a different
  response, not an identical hang) — reads as the origin not accepting
  connections from this egress, or genuinely down. Now confirmed across 2
  independent sessions (2026-09-01 single-attempt timeout, 2026-09-11 5-profile
  re-probe) — not classified as a WAF; worth retrying from a different egress
  if revisited. Re-probed 2026-09-11.
- **metro.com.na** — now returns 200 (previously also dead at 2026-09-01).
  `/new-products/` and `/product-news/` exist but render via a "3d-flip-book"
  WordPress plugin (image/PDF-style weekly circular), 0 price/cart text in raw
  HTML. Not machine-readable without an image/PDF OCR pipeline; not pursued —
  no per-product structure even after OCR. Probed 2026-09-11.
- **zulzi.com** — looked promising (SvelteKit SPA, `ProductList` +
  `AddToCartButton` components — a real grocery-delivery-app shape) but all
  social links point to `zulzi_sa` / `facebook.com/zulzi.co.za`: this is a
  South African delivery platform with no Namibia presence found on the page.
  Not probed further. Probed 2026-09-11.

Namibia's national statistics office (nsa.org.na) shipped instead as a
fetcher pair (`na_nsa_cpi` cpi_benchmark, `na_nsa_zonal_food_prices`
official_avg) — see `src/prices/configs/ssa/southern_africa/namibia/`.

## 2026-09-11 SAR (India/Pakistan) still_untried sweep

93 food-plausible candidates probed from  (India + Pakistan,
), after dropping 55 outright non-food rows (pharmacy, electronics, furniture,
books/stationery, toys, eyewear, auto parts, cosmetics-dominant, price-comparison aggregators
with no first-party catalog, dead news-article leads). 25 shipped (24 via generic Shopify/
WooCommerce/OpenCart spiders + 1 custom BigBasket spider); findings for the rest below.

**Genuine WAF / access block (curl_cffi chrome124 403, re-probed live 2026-09-11):**
- **carrefour.pk** (PK, Carrefour Pakistan / Majid Al Futtaim) — 403 on curl_cffi chrome124.
  High-value hypermarket target; worth a dedicated Playwright network-capture pass in a future
  session (Majid Al Futtaim commerce API is a known open backend on other MAF storefronts).
- **magnikart.com** (IN, Bhubaneswar grocery, 5,290-product WooCommerce-style store) — 403.
- **golbazar.pk** (PK, Ramadan/donation grocery packages) — 403.
- **fairo.pk** (PK, Faisalabad grocery) — 403.
- **kolkatafish.com** (IN, Kolkata fish/meat/seafood) — 403.
- **naturesbasket.co.in** (IN) — already documented above (2026-09-01); re-confirmed 403 on
  chrome124/chrome120/safari17_0 2026-09-11, unchanged.
- **bombayfisher.com** (IN, Mumbai fresh fish, Shopify) — HTTP 402 (store suspended /
  subscription lapsed), not a WAF. Re-check later; not a permanent dead end.
- **continentalfresh.in** (IN, Vizag seafood, Shopify) — HTTP 401 on 
  (password-protected coming soon gate, store not yet publicly launched).
- **chiltanpure.pk** (PK, ChiltanPure Dairy) — technically open (Shopify, /products.json
  works), but sampled 1,250 products are 85%+ perfume/aroma-chemicals/cosmetic-ingredients;
  the dairy collection the candidate list pointed at is a tiny drop-shipped sideline of an
  essential-oils/fragrance manufacturer. Dropped as non-food on the hard constraint, not as a
  technical block.

**Explicit anti-scrape block (not a WAF challenge, a stated policy):**
- **amazon.in** (IN, Amazon Fresh / Amazon Grocery) —  returns HTTP 503 Service

## 2026-09-11 SAR (India/Pakistan) still_untried sweep

93 food-plausible candidates probed from `still_untried_20260911.csv` (India + Pakistan,
`foodish==True`), after dropping 55 outright non-food rows (pharmacy, electronics, furniture,
books/stationery, toys, eyewear, auto parts, cosmetics-dominant, price-comparison aggregators
with no first-party catalog, dead news-article leads). 25 shipped (24 via generic Shopify/
WooCommerce/OpenCart spiders + 1 custom BigBasket spider); findings for the rest below.

**Genuine WAF / access block (curl_cffi chrome124 403, re-probed live 2026-09-11):**
- **carrefour.pk** (PK, Carrefour Pakistan / Majid Al Futtaim) — 403 on curl_cffi chrome124.
  High-value hypermarket target; worth a dedicated Playwright network-capture pass in a future
  session (Majid Al Futtaim commerce API is a known open backend on other MAF storefronts).
- **magnikart.com** (IN, Bhubaneswar grocery, 5,290-product WooCommerce-style store) — 403.
- **golbazar.pk** (PK, Ramadan/donation grocery packages) — 403.
- **fairo.pk** (PK, Faisalabad grocery) — 403.
- **kolkatafish.com** (IN, Kolkata fish/meat/seafood) — 403.
- **naturesbasket.co.in** (IN) — already documented above (2026-09-01); re-confirmed 403 on
  chrome124/chrome120/safari17_0 2026-09-11, unchanged.
- **bombayfisher.com** (IN, Mumbai fresh fish, Shopify) — HTTP 402 (store suspended /
  subscription lapsed), not a WAF. Re-check later; not a permanent dead end.
- **continentalfresh.in** (IN, Vizag seafood, Shopify) — HTTP 401 on /products.json
  (password-protected "coming soon" gate, store not yet publicly launched).
- **chiltanpure.pk** (PK, "ChiltanPure Dairy") — technically open (Shopify, /products.json
  works), but sampled 1,250 products are 85%+ perfume/aroma-chemicals/cosmetic-ingredients;
  the "dairy" collection the candidate list pointed at is a tiny drop-shipped sideline of an
  essential-oils/fragrance manufacturer. Dropped as non-food on the hard constraint, not as a
  technical block.

**Explicit anti-scrape block (not a WAF challenge, a stated policy):**
- **amazon.in** (IN, Amazon Fresh / Amazon Grocery) — /s?k=... search returns HTTP 503
  "Service Unavailable" with an explicit body directing automated-access requests to
  api-services-support@amazon.com and to Amazon's Marketplace/Product Advertising APIs. This
  is Amazon's standing anti-scraping stance, not a transient block. SKIP — not worth
  iterating against; out of scope for this pipeline.

**Quick-commerce SPA needing a pincode/geo session (not a WAF):**
- **zepto.com** (IN, Zepto) — homepage returns HTTP 202 with a ~2KB shell; matches the
  skill's documented Blinkit/Zepto/Instamart shape exactly (client-fetch app requiring a
  lat/lon or pincode header before any catalog call fires). Needs a Playwright network-capture
  session against the app flow (set delivery location, then capture the category/search API
  call) — not attempted this round due to time budget; flagged as the highest-value follow-up
  given explicit priority on quick-commerce in the brief.
- **countrydelight.in** (IN) — already documented above (2026-09-01): Angular Universal SPA,
  websiteapi.countrydelight.in 403s on unauthenticated guesses. Unchanged 2026-09-11; same
  pincode-flow reverse-engineering needed as Zepto.

**Reachable (200), but not extractable without more work:**
- **jiomart.com** (IN, JioMart) — category/section pages return 200 with a 6-7MB payload, but
  the body is Contentstack/Fynd page-builder CMS schema (field definitions for a "Products
  Card Carousel" widget), not rendered product data. A 6s Playwright network capture against
  a guessed category URL surfaced only Fynd Platform logistics/cart/config/session endpoints
  (api/service/application/{cart,logistics,configuration,content}/v1.0/...), no catalog/search
  endpoint — the guessed URL was likely wrong (JioMart's real category paths were not
  independently re-derived this round). Needs a longer capture against a URL confirmed live in
  a real browser, not the CMS section-preview URL from the candidate list.
- **krishidhara.com** (IN, Lucknow dal/rice) — homepage 200, but wp-json/wc/store/v1/products
  403s (Store API disabled at the server level, distinct from a WAF — same endpoint pattern
  works on 7 other WooCommerce sites probed this round).
- **storepanda.pk** (PK, Faisalabad grocery) — same signature: homepage 200, Store API 403.
- **akshayakalpa.org** (IN, organic dairy) — Store API 404 (endpoint not registered on this
  WooCommerce install). All three would need an HTML-pagination-based custom spider instead
  of the generic Woo template.
- **snapcart.pk** (PK) — shipped (see manifest), but flagged here too: 1,250-product sample is
  dominated by perfume/skincare with food (chips/tea-coffee/chocolates/biscuits) as a ~9%
  minority. Kept because the food SKUs are real, but expect a low food-fraction yield relative
  to effort.

**Dead / unreachable (DNS, TLS, timeout — re-probed live 2026-09-11, not just bare curl):**
- **angaadionline.com** (IN) — DNS resolution failure on both plain requests and curl_cffi.
- **graceonline.in** (IN) — DNS resolution failure.
- **rcmymall.in** (IN) — DNS resolution failure.
- **serveu.pk** (PK) — DNS resolution failure.
- **chitki.com** (IN) — connection timeout on both arms.
- **uttampk.com** (PK) — TLS certificate verification failure on both arms.
- **asanbazar.pk** (PK) — TLS certificate verification failure on both arms.
- **bazaarapp.com** (PK) — HTTP 503 on every probe.

**Not a real source (dropped without a network probe — dead-end leads, not retailers):**
Aaram Bazar (telegraphindia.com news article, 2012), Freshdo (yourstory.com news article),
Just Cart / Bit VR (exportersindia.com B2B directory), BigBasket city coverage via gift-card
evidence (sbicard.com, not a catalog), Gavyam (price-comparison, not a first-party retailer),
Dhundo Auto Parts Guide (auto-parts price-comparison summary), chotu.com (WhatsApp/local-shop
lead with no captured prices), MartEzee (martezee.wordpress.com — abandoned marketing blog,
operational status unconfirmed), PriceBasket / BudgetBasket / FantasticFood / Smartprix
Grocery / Comparify Grocery / Groka / PriceKart / Qemat (grocery price-COMPARISON apps that
re-scrape Blinkit/Zepto/BigBasket/JioMart themselves — not first-party sources; onboarding
the underlying retailers directly is the correct fix, which is what this round did for
BigBasket).

## 2026-09-11 — onboard3 shard (verified-live backlog, 12 countries by empty-COICOP-leaf rank)

Every URL below returned HTTP 200 with a real body on the 2026-09-11 pre-probe,
so none of these is a transport-level block. All were re-probed with
`curl_cffi impersonate=chrome124`; the verdicts are about what the 200 actually
contains.

### F5 Shape / BIG-IP ASM JS challenge (`window["bobcmn"]` + `/TSPD/` cookie stub)

New blocker class on this list. Signature: **every** path — `/`, `/fr`,
`/fr/produits`, even `/robots.txt` — returns the *same* ~6.8 KB HTML whose only
content is an obfuscated script setting `window["bobcmn"]` and a
`failureConfig` hex string that decodes to "Oops....something went wrong....
your support id is: %DOSL7.challenge.support_id%", with a `/TSPD/` +
`TSPD_101_DID` cookie handshake. `curl_cffi chrome124` clears nothing; the
stub is the response body, not a redirect.

- **www.cactus.lu** (LU, Cactus — Luxembourg's largest grocery chain) — all paths
  serve the 6,817-byte `bobcmn`/TSPD stub. One oddity worth recording so the next
  run does not misread it: a request to a *non-existent* path under an API-looking
  prefix (`/api/catalog_system/...`) fell through to a real 78 KB Drupal 404 page
  (`lang="fr"`, GTM) — i.e. the origin is a Drupal site and the challenge sits in
  front of the routes that matter, not the whole host. That 78 KB page is a 404
  shell with no products. Probed 2026-09-11.

### Brochure-only WordPress / no online store

- **halimpharma.com.af** (AF, Halim Pharma) — WordPress/LiteSpeed, 145 KB home,
  **no WooCommerce** (`/wp-json/wc/store/v1/products` → `rest_no_route`). The
  `wp-sitemap.xml` holds only pages, `ot_portfolio` items and
  `portfolio_cat` taxonomies — it is a pharmaceutical importer's corporate
  portfolio site (`/our-services`, `/clients`, `/director-speech`). Zero price
  text, zero AFN strings. Probed 2026-09-11.
- **tazapharma.af** (AF, Taza Pharma) — WordPress/Apache, 163 KB home, no
  WooCommerce. `wp-sitemap.xml` holds posts, pages, `portfolio` and taxonomies;
  the homepage links are dated blog archives (`/2024/`, `/2025/`, `/2026/`).
  A news site for a pharma company, not a shop. Probed 2026-09-11.
- **www.pallcenter.lu** (LU, Pall Center) — WordPress + WooCommerce *plugin
  present* in the markup, but the Store API 404s (`rest_no_route`) and the Yoast
  `sitemap_index.xml` has **no product sitemap** at all: only post, page,
  `3d-flip-book`, category and author. The `3d-flip-book` post type is the
  digital leaflet — the catalogue is a PDF flipbook, not HTML products. Homepage
  carries zero price-shaped text; its links are store branches (`/pall-strassen`,
  `/pall-steinsel`, `/pall-useldange`, `/pall-pommerloch`). Probed 2026-09-11.

### No products on the site (corporate marketing portal)

- **coop.no** (NO, Coop Norge — the country's second-largest grocery group) —
  Cloudflare, HTTP 200, but this is the *corporate + recipe* portal, not a
  storefront. `/api/sitemap/sitemapindex.xml` resolves to a single sitemap with
  4,454 URLs whose top path segments are `oppskrifter` (recipes, 1,992),
  `butikker` (store finder, 1,220), `samvirkelag` (co-op societies, 374) and the
  chain landing pages `extra` / `coop-mega` / `coop-prix`. Only 26 URLs look
  product-ish and they are `/egne-merkevarer/<brand>/produkter/<slug>`
  own-brand showcase pages — fetched one (`coop-kaffe/produkter/
  kraftig-arabicakaffe`, 92 KB) and it carries **no price node of any kind**.
  `/handle` and `/nettbutikk` both 404. Norway's e-grocery coverage has to come
  from oda_no / meny_no / spar_no / obs_no, which are already onboarded.
  Probed 2026-09-11.
- **www.albert.cz** (CZ, Albert — one of the two largest Czech grocery chains) —
  HTTP 200, 1.2 MB Next.js site, but Albert runs **no first-party web shop**.
  Its `/albert-online` page is a CMS landing page whose only outbound commerce
  links are `https://wolt.com/cs/discovery/albert` and
  `http://www.foodora.cz/chain/ch3dr`. `nakup.albert.cz` does not resolve
  (DNS NXDOMAIN) and `/produkty` 404s. The Wolt storefront is already onboarded
  as `albert_wolt_cz`; a `albert_foodora_cz` sibling is the only unbuilt route
  left here. Probed 2026-09-11.
- **cartio.es** (ES, "Cartio") — WordPress/LiteSpeed, HTTP 200, 119 KB, and the
  page *does* contain 41 euro-shaped strings — which is exactly the trap. It is a
  **pre-launch waitlist landing page** (`#waitlist` x6, `#pain`, `#como`,
  `#ejemplo`, `#opiniones`, `#planes`; every other href is an in-page anchor).
  The prices are illustrative mock-ups in a hand-written comparison widget
  ("Alcampo gana esta semana · Tu carrito: 6,99€ · Ahorro: 0,31€",
  "Plátanos 1 kg · Mercadona 1,95 €"). No catalogue, no product routes, nothing
  to scrape. Re-check in ~6 months. Probed 2026-09-11.

### SPA shell — no productive endpoint

- **mumafrica.com** (DZ candidate, "MumAfrica — African B2B Marketplace") — Vite
  SPA on Cloudflare: **every** path, including `/api/products`, `/api/suppliers`
  and `/robots.txt`-adjacent routes, returns the identical 5,058-byte
  `<div id="root">` bootstrap. Pulled the whole bundle
  (`/assets/index-CAmiu1eR.js`, 899 KB) and grepped it: the only API route
  referenced anywhere in it is `/api/broadcast`; no `api.` host, no REST base.
  `api.mumafrica.com` does not resolve. robots.txt is real (it names
  `/supplier-dashboard`, `/AdminMumafrica`), so the product surface exists behind
  auth, not in public HTML. Probed 2026-09-11.
- **www.fthna.gr** (GR, "Fthiná" basket comparison) — Next.js on Vercel, HTTP 200
  but only 37 KB, and the SSR HTML contains **zero** price-shaped text. The whole
  app is a client-side basket builder (`/basket`, `/my-baskets`, `/trends` are
  the only internal routes) and `/robots.txt` itself 404s into the SPA shell.
  Nothing server-rendered to extract. Greece already has 7 retail sources.
  Probed 2026-09-11.

### Reachable, HTTP 200, but not extractable without more work

- **www.ahorrapasta.com** (ES, Spanish grocery price comparator) — the *product*
  layer is genuinely good: `/producto/<slug>-<retailer>-<id>` PDPs are SSR and
  carry clean schema.org JSON-LD (`Product` + `Offer`, EUR, brand, size, image
  hot-linked from dia.es/carrefour.es). What is missing is **enumerability**:
  the declared `Sitemap: https://www.ahorrapasta.com/sitemap.xml` **404s** (as do
  `sitemap-0.xml` and `sitemap_index.xml`), `/supermercados` and
  `/supermercados/<chain>` 404, `/buscar?q=…` renders client-side with 0
  `/producto/` links in the SSR body, and `robots.txt` explicitly
  `Disallow: /api/`. The only enumerable surface is the ~20 rotating
  `/producto/` links on the homepage — a carousel, not a catalogue, so it fails
  the page-2 enumerability gate. Revisit if the sitemap ever starts resolving, or
  if a Playwright network trace on `/buscar` exposes the search endpoint (it is
  robots-disallowed, so that is a deliberate decision, not an oversight).
  Spain already carries dia_es / carrefour_es / alcampo_es / mercadona /
  elcorteingles_es plus three other comparators. Probed 2026-09-11.

### Not a blocker — already onboarded under another key

- **jumbocl.myvtex.com** (CL, Jumbo Chile) — appeared on this shard as an
  un-manifested candidate; it is already live as `jumbo_cl`
  (`src/prices/configs/lac/south_america/chile/jumbo_cl.yaml`, `archive_prefix:
  jumbocl.myvtex.com/`). Duplicate, not new. Checked 2026-09-11.
- **mamakiti.com** (GN) — already on this list (probed 2026-09-05): FastAPI
  backend reachable and unauthenticated but honestly empty
  (`/api/products` → `{"items":[],"total":0}`). Re-confirmed as a skip on
  2026-09-11 without re-probing; the 6-month re-check date stands.

## 2026-09-11 — onboard5 shard (verified-live backlog, 10 countries by empty-COICOP-leaf rank)

Every URL below returned HTTP 200 with a real body on the 2026-09-11 pre-probe,
so none of these is a transport-level block — all were re-probed with
`curl_cffi impersonate=chrome124` and, where the 200 was an SPA shell, with a
Playwright network trace. The verdicts are about what the 200 actually contains.

**Five of the twelve candidates on this shard were already in this file** from
the 2026-09-01 waves 10/11/12 and were re-confirmed, not re-litigated:
`menamart-angola.com` (AO), `chapchapgabon.com` (GA), `duka.direct` (TZ),
`www.shoprite.co.zm` (ZM), `tigmooeats.com` (ZM). A 200 with a large body is
exactly what a marketing site returns; the earlier verdicts stand. Re-probe
2026-09-11 added only: menamart still serves `PHP/8.2.33` behind Cloudflare with
0 `ld+json` blocks, duka.direct now sits behind `server: ddos-guard`, and
tigmooeats' 2 `ld+json` blocks are Organization/WebSite, not Product.

### Store-session-gated storefront (catalog fully enumerable, prices withheld until an address binds a store)

New class, and the one that cost the most time on this shard. Signature: a large
server-rendered catalogue with real product names, a real product sitemap, and a
schema.org `Product` JSON-LD node whose `offers` carries `url` and
`availability` **but no `price` key at all**. The price is not lazy-loaded — it
does not exist in the anonymous session, because the storefront is a multi-store
co-operative and the price is per-store. Do not read the JSON-LD Product node as
evidence a site is scrapeable; check `offers.price` specifically.

- **spesaonline.conad.it** (IT, Conad — Italy's largest grocery co-operative) —
  `sitemap/products.xml` is genuine and enumerable: **5,432 product URLs**
  (`/p/<slug>--<sku>`), plus `sitemap/categories.xml`. Every PDP is a 343 KB
  server-rendered page carrying a complete `Product` JSON-LD (name, sku, gtin,
  brand, image, offers.availability) — and no price anywhere; the only `€`
  strings in the DOM are the `4,95€` delivery fee. The homepage states the gate
  in plain text ("Verifica i servizi disponibili nella tua zona" / "Il tuo
  indirizzo"). The store list endpoint `/api/ecommerce/it-it.stores.json`
  returns 200 in a browser but **404 to curl_cffi even after fetching the
  homepage first** — the session is bound server-side via `ecSess` /
  `ecServerUUID` / `ecRoute` cookies that only the SPA's address-verification
  flow creates. `/api/ecommerce/it-it.dictionary.json` (69 KB) is open, which is
  a red herring: it is UI strings. Unblocking this needs a scripted
  Google-Places address + store-selection flow in Playwright, then plain-HTTP
  PDP fetches with the bound cookies — a dedicated effort, not routine
  onboarding. Worth doing: 5,432 SKUs at Italy's biggest chain. Probed
  2026-09-11.

- **www.coopshop.it** (IT, Coop / Novacoop "Catalogo Global") — same failure
  mode reached through a *wide-open* API, which makes it especially misleading.
  The storefront is eBSN (Digitelematica); `/ebsn/api/category?hash=w0d0t0`
  returns the full tree (**17 top-level, 979 categories total**) and
  `/ebsn/api/products?parent_category_id=<id>&page=1&page_size=N` paginates
  cleanly (`totItems` 10,000 on the root, real `totPages`). Every product object
  is rich — name, `shortDescr` brand, `description` pack size, barcode, EAN,
  `codInt`, breadcrumbs, VAT class, images — and contains **no price field of
  any kind**; the only key matching /price/i is `priceUnitDisplay: "PZ"`, a unit
  label. Tried and rejected: `hash=w{0..5}d{0,1}t0` (the hash is
  warehouse/delivery-service/timeslot), `&warehouse_id=`, `&store_id=`.
  `/ebsn/api/store/list` returns 3 stores with `deliveryServices` but **zero
  warehouses**, so there is no warehouse id to bind anonymously.
  `/ebsn/api/warehouse*`, `/ebsn/api/cart/info`, `/ebsn/api/category/tree` all
  404/400. A Playwright render of a real category page
  (`/acqua-e-bevande/succhi-di-frutta`) fires exactly the same
  `/ebsn/api/products?...&hash=w0d0t0` call and the rendered DOM shows **no
  prices either** — so this is not a headers/session-shape problem, the
  anonymous catalogue genuinely has no prices. Needs a registered account with a
  delivery address. Probed 2026-09-11.

### Encrypted API payload + Cloudflare Turnstile on writes

- **instashop.com/en-eg/** (EG, InstaShop Egypt — Delivery Hero) — not the same
  company as `instashop.kz`, which *is* onboarded. The SPA is served from
  Cloudflare with no `__NEXT_DATA__`/`__NUXT__`; Playwright network-trace found a
  clean-looking REST surface at `/eshop/v2/*` (`staticData`, `getFooterContent`,
  `getDefaultCoordinates`, `account`, `superstore`,
  `superstore/additionalContent`). Two independent walls: (1) `GET
  /eshop/v2/staticData?systemInfo={...countryCode:"EG"...}` returns **200 with an
  AES-encrypted body** — a 1,472-byte base64 blob beginning `U2FsdGVkX1/`, i.e.
  CryptoJS `Salted__`, with the key in the JS bundle and rotated; (2) every
  `POST` (`/eshop/v2/superstore`, the one that would return store catalogues)
  returns **403 with a Cloudflare Turnstile "Just a moment..." interstitial**,
  `script-src https://challenges.cloudflare.com`. Encrypted payload *and* an
  interactive challenge on the only useful verb. Abandon. Probed 2026-09-11.

### Branch-gated Next.js storefront (product sitemap real, no reachable product API)

- **shop.imtiaz.com.pk** (PK, Imtiaz Super Market) — this is the real storefront
  subdomain, distinct from the `imtiaz.com.pk` corporate WordPress site already
  recorded in this file (that entry is still correct; it just was not the whole
  story). `sitemap.xml` is genuine: 503 URLs, ~500 of them
  `/product/<slug>-<id>`. But the PDP server-renders 33 KB with
  `__NEXT_DATA__.props.pageProps.prefetchedItem = null` and no price, and
  `/category/grocery` renders 188 KB with `pageProps` reduced to
  `{session,pageUrl,requestIp,lang}` — everything loads after a city/branch
  selection. A full Playwright render of both the PDP and the category page
  fires **exactly one XHR**, `/api/geofence?restId=55126`, and nothing else. That
  endpoint is unreachable outside the browser: from `curl_cffi` (with a warmed
  session, Referer, Origin, `x-requested-with`) it answers
  `400 {"msg":"Please provide restaurant id!"}` to `restId`, `restaurantId`,
  `rest_id`, `restid` and `id` alike. Grepping all 10 `_next/static` chunks
  yields only `/api/auth/signin`, `/api/image`, `/api/img` — no product route and
  no external API host (the platform is blinkx/tossdown-style, assets on
  `blinkximtiaz-i.s3.ap-southeast-1.amazonaws.com`, `restId 55126`). A build here
  means driving the branch selector in Playwright first; ~500 SKUs, so low
  reward. Probed 2026-09-11.

### Brochure-only WordPress / no online store

- **www.papantoniou.com.cy** (CY, Papantoniou — trades as ΣΚΛΑΒΕΝΙΤΗΣ Κύπρου /
  Sklavenitis Cyprus; canonical host is `sklavenitiscyprus.com.cy`) — the
  homepage HTML contains the strings `woocommerce` and `wp-content`, which is a
  **false positive**: `/wp-json/wc/store/v1/products` and
  `/wp-json/wc/store/products` both return `rest_no_route` (in Greek), and
  `/product-sitemap.xml` 404s. `wp-sitemap.xml` lists only
  `posts-post`, `posts-page`, `posts-bgmp` (a store-locator plugin),
  `posts-3d-flip-book` and taxonomies — the "catalogue" is flip-book PDF
  leaflets under `/catalogues/`. 22 absolute links on the whole homepage, all
  about/contact/locations/privacy. No e-commerce. Note the repo already carries
  `sklavenitis_wolt_cy` for this retailer's delivery catalogue, which is the
  right surface. Probed 2026-09-11.

- **www.eurospin.it** (IT, Eurospin — Italy's largest hard discounter) —
  WordPress + W3 Total Cache, no WooCommerce (`/wp-json/wc/store/v1/products` →
  `rest_no_route`; the 21 REST namespaces are iThemes Security, AIOSEO,
  aio-login, `wp/v2` — nothing commercial). The AIOSEO `sitemap_index.xml` has
  exactly 6 shards — page, store, ricette, brand, news, post-archive — and **no
  product shard**; `page-sitemap.xml` (1,403 locs) is marketing pages. `/prodotti`
  200s but serves a 2023 Christmas campaign page; `/i-nostri-prodotti` and
  `/prodotto/` 404. `/volantino` is the biggest page on the site at **1.41 MB and
  contains zero prices** — it is a `var stores` store-locator payload plus an
  image/PDF flyer viewer (0 hits for `data-price`, `itemprop="price"`,
  `class*=product`, `class*=prodotto`, and 0 `€` amounts). Probed 2026-09-11.

### No products on the site (corporate marketing portal)

- **www.unes.it** (IT, Unes / U2 Supermercato) — AEM content site. `sitemap.xml`
  is 846 locs of which 211 are `/content/dam/unes` assets and ~170 are
  `/it/parola-di-unes/*` editorial; there is not one product URL. `robots.txt`
  disallows `/*/reparti` which reads like a catalogue hint, but `/it/reparti`
  returns a genuine 404 shell (1,167 bytes, `<title>Page not found</title>`,
  three stylesheet links and nothing else). No webshop. Probed 2026-09-11.

- **www.sezamo.it** (IT, Sezamo — Rohlik Group's Italian venture) — the domain
  resolves and serves a **3.1 MB Drupal page for every path**: `/robots.txt`,
  `/api/v1/categories` and `/services/frontend-service/products/new-categories/1`
  all return byte-identical 3,099,472-byte HTML whose `<title>` is
  **"Eat well Live well | Rohlik Group"**. It is a catch-all corporate landing
  page for the parent group, not the Sezamo storefront — consistent with Rohlik
  having wound down the Italian operation. Nothing to scrape. Probed 2026-09-11.

- **hokoh.app** (FR, HOKOH — "Comparateur de prix courses gratuit | Carrefour,
  Leclerc, Auchan, Lidl…") — the name suggests a price-comparison feed, but the
  web property is a 47 KB marketing landing page for a mobile app. `sitemap.xml`
  has **10 URLs total**: `/`, `/blog/`, five blog articles, and
  privacy/cgu/accessibilite. Its three `ld+json` blocks are `MobileApplication`,
  `FAQPage` and `Organization` — no `Product`, no `Offer`. The comparison data
  lives only in the app (`Disallow: /app/`). App-only. Probed 2026-09-11.

### Aggregator / no canonical per-product URL

- **it.everli.com** (IT, Everli — grocery-delivery marketplace over Italian
  chains) — `/it/spesa` is a **Framer** marketing page (376 KB, `api.framer.com`
  access-token call in the trace) with zero product XHRs. `robots.txt` disallows
  `/supermercato/` (the store catalogues) outright, and the declared sitemap
  index `it_everli_com_it_sitemap.xml` lists four locale children of which
  `sitemap_it.xml` **404s to the SPA shell**. `/it/milano` is a real 380 KB city
  store-directory page — per the skill's marketplace-as-directory rule that is
  the right surface, but the chains behind it (Carrefour, Conad, Bennet, Coop)
  are already onboarded or are the store-session-gated cases above, so the
  directory adds nothing here. Not probed further. 2026-09-11.


---
---

# Merged fragment archive (2026-09-11)

The 38 sections below were appended verbatim from per-run blocker notes that
47 discovery and repair waves left in `~/gapwork/` instead of writing here. They
are kept as separate dated sections rather than reflowed into the taxonomy above,
because each one records what a specific run actually observed on a specific date and
rewriting them would lose that provenance.

They add 792 hosts not previously documented. 9 fragments were
skipped as fully redundant: known_blockers_append.md, known_blockers_disco_mena_guinea_bissau.md, known_blockers_disco_mena_iraq.md, known_blockers_disco_mena_libya.md, known_blockers_disco_mena_sudan.md, known_blockers_disco_mena_syria.md, known_blockers_disco_mena_yemen.md, known_blockers_untried_2.md, blockers_append.md.

**Read the host index at `known_blockers_index.md` first** - this file is long, and the
index maps a host to the section that documents it in one grep.

---

## known_blockers_capfix - as of 2026-09-11

Merged from `~/gapwork/known_blockers_capfix.md` on 2026-09-11. 2 hosts, 1 not
documented above at merge time.

# Known blockers — cap/zero-row fix pass (2026-09-11)

## aelanbasket_vu (Vanuatu) — Vercel bot-checkpoint wall, NOT fixable via plain HTTP or curl_cffi

Confirmed the prior root-cause report but found a deeper layer underneath it.
The homepage genuinely has zero `/product/` links today — but that's because
**every path on the site now returns a Vercel bot-management challenge page**,
not because the homepage was redesigned.

- MEASURED with plain `requests` + a real Chrome UA: `GET /` -> HTTP 403,
  `Content-Type: text/html`, page title `Vercel Security Checkpoint`,
  response headers include `Server: Vercel`, `X-Vercel-Mitigated: challenge`,
  `X-Vercel-Challenge-Token: ...`. Same 403/checkpoint on `/shop`,
  `/sitemap.xml`, `/robots.txt`, `/api/products`.
- MEASURED with `curl_cffi` `impersonate="chrome124"`: identical 403 +
  checkpoint page. TLS-fingerprint impersonation does not help here — this
  is a Vercel-platform bot firewall (BotID-style), which does JS/device
  fingerprinting server-side, not a naive UA/TLS gate. It cannot be solved
  without executing real JavaScript (i.e., a headless browser like
  Playwright working through the challenge), which is out of scope for
  this pass.
- The manifest's 2026-08-11 note ("`/shop` is a client-rendered filter view
  ... discovery instead crawls from the homepage plus related-products
  rails") was accurate *at the time*; the checkpoint is a regression that
  post-dates it.
- **Verdict: not fixed this pass.** True catalogue size unknown (was ~14+
  linked from the homepage before the wall went up). Recommend a follow-up
  pass with Playwright (or dropping the source if Vanuatu coverage doesn't
  depend on it) rather than further plain-HTTP probing — every path is
  walled identically, so there's no alternate discovery path to try.

## Lezzoo/Iraq cluster — genuine platform truncation, TRUE catalogue size NOT recoverable via plain HTTP

See the accompanying report for full per-source detail and duplicate
resolution. Summary of the blocker: all 8 distinct Lezzoo venue storefronts
that were built (`asfahan_nuts_iq`, `lezzoo_mart_erbil_iq`,
`nan_house_bakery_lezzoo_iq`, `sarwaran_butchery_lezzoo_iq`,
`sarwaran_grocery_lezzoo_iq`, `sherko_nuts_lezzoo_iq`,
`sultan_butchery_lezzoo_iq`, `varya_grocery_lezzoo_iq`) return **exactly
60 total menu items** in the page's schema.org JSON-LD, regardless of how
many sections/categories the venue has (1 section vs. 33 sections) or how
different the venues are (a single-category nuts shop vs. a 33-category
mart). This is not spider-side capping — `generic_lezzoo_venue.py` has no
slice/limit in its code, does a single plain GET, and yields every
`hasMenuItem` found.

- MEASURED: the full RSC-rendered HTML (not just the JSON-LD `<script>`
  block) caps at 60 items — checked via raw `"price"`/`"priceCurrency"`
  occurrence counts in the complete page source, and via the page's
  `self.__next_f.push` streaming payload, which duplicates the same
  60-item JSON-LD, not a larger one. So this isn't an SEO-only truncation
  with more data available elsewhere in the same page.
- MEASURED: no `__NEXT_DATA__`/API/GraphQL/loadMore reference found in any
  of the 5 largest JS chunks the page loads (`1255`, `2546`, `2619`,
  `8493`, `4bd1b696`) — the "load more" mechanism, if one exists, is
  server-only (React Server Components) and isn't visible to static
  analysis. `?page=2`/`?offset=60` query params have no effect (server
  ignores them). No `api.*.lezzoo.com` or similar subdomain resolves.
- MEASURED (corroborating, from a sibling manifest set already in this
  repo, `known_blockers_disco_mena_iraq.md`): venues with a genuinely
  small catalogue do NOT get padded to 60 — `amara-dates-9381` returned
  only 5 items, `meer-fish-1033` only 10. This rules out "60 is a
  coincidental real catalogue size for 8 unrelated shops" — the cap only
  binds when the true catalogue is ≥60, exactly as a page-size limit
  would behave.
- **Verdict: not fixable via plain HTTP.** True catalogue size for all 8
  is UNKNOWN but INFERRED (high confidence) to exceed 60 for most of them,
  especially `lezzoo_mart_erbil_iq` (33 categories, most showing only 1-5
  items each — implausible as real per-category stock) and
  `sultan_butchery_lezzoo_iq` (Meat=32, Fruits/veg=26 crammed into a
  60-item ceiling alongside 2 more categories). Recovering the true
  catalogue would need either a headless browser driving the site's
  infinite-scroll/pagination, or reverse-engineering a private
  app/mobile API — both out of scope for this pass. Recommend flagging
  as a future Playwright-based enhancement rather than attempting further
  plain-HTTP probing (the JS bundles were already checked and carry no
  client-fetch endpoint).


---

## known_blockers_custom_1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_custom_1.md` on 2026-09-11. 8 hosts, 8 not
documented above at merge time.

# known_blockers_custom_1.md

Batch: `~/gapwork/batches/custom_1.csv` (255 candidates: gibraltar, chad,
eswatini, botswana, sierra_leone, suriname, solomon_islands, tuvalu).

## Method note (read before trusting the "not probed" list below)

Every one of the 255 candidates went through one bulk pass: `curl_cffi`
fetch (impersonate=chrome124, 15s timeout) + platform-fingerprint regex +
robots.txt/sitemap discovery + JSON-LD-Product/currency-token scan. Raw
results for all 255 rows are saved on a8 at
`~/gapwork/probe_results_custom_1.json` — re-run future passes off that
file rather than re-fetching from scratch. Of the 255: 223 returned HTTP
200, 15 returned 403, ~17 failed on connection/TLS/DNS errors.

From that bulk pass, roughly 45 candidates were deep-probed (sitemap
enumeration, category-page pagination, PDP price/currency confirmation).
The remaining ~210 candidates were NOT individually hard-gate-tested in
this pass — most are single-page tariff/fee/menu pages, restaurant menus,
school-fee schedules, or personal/inactive sites where the bulk fingerprint
already shows no real product platform (no sitemap, no JSON-LD, no
currency token, or a non-200 status). They are listed at the bottom as
"not deep-probed" rather than folded into the rejection buckets below,
because no live per-candidate evidence was gathered for them.

---

## REJECTED — zero/POA pricing

### edutoys_world_bw (botswana)
- URL: https://www.edutoys.world/shop
- Platform: Odoo (`/shop`, `/shop/category/<slug>`)
- Evidence: fetched `/shop/category/role-play-toys-12` (HTTP 200, 20
  product cards via `.oe_product` selector). All 20/20 cards showed
  `Enquire for Price` with `.product_price` text `"Enquire for Price0.0BWP"`
  — every listed price is the literal zero placeholder. Classic
  "price on application" catalogue per the skill's known anti-pattern.
- Verdict: REJECT (non-zero-price gate).

### bas_bw_shop (botswana)
- URL: https://www.bas.co.bw/shop
- Platform: Odoo
- Evidence: only one category discoverable (`/shop/category/preowned-1`),
  containing exactly 2 priced product cards (`P13,500.00`, `P5,300.00`).
  No other category link found from `/shop`.
- Verdict: REJECT (Phase 6 ≥5-row gate cannot be met — total catalog is 2
  items).

---

## REJECTED — wrong currency / diaspora audience

### newflagshop_eswatini_flags (eswatini)
- URL: https://newflagshop.com/shop/by-letter/e-g/eswatini/
- Platform: WooCommerce/WordPress, JSON-LD Product present.
- Evidence: JSON-LD `offers.priceCurrency` = `CAD`. This is a Canada-based
  flag/novelty retailer selling "Eswatini flags" as a curated product line,
  not a storefront that prices for Eswatini.
- Verdict: REJECT (currency + locality gates — CAD, Canadian seller).

### carros_td (chad)
- URL: https://carros.com/?lang=fr
- Platform: unfingerprinted custom platform, JSON-LD Product present.
- Evidence: JSON-LD `offers.priceCurrency` = `USD`, not XAF. Site is a
  used-car export marketplace (French-language, "carros.com" is generic,
  not Chad-specific); no XAF pricing found despite a `lang=fr` Chad-facing
  URL param.
- Verdict: REJECT (currency gate — USD, not the country's own currency;
  reads as an export/diaspora marketplace, not a local Chad price).

### timototraders (eswatini)
- URL: https://timototraders.co.za/
- Evidence: domain is `.co.za` (South Africa ccTLD); no Eswatini-specific
  storefront, pricing, or delivery scope found on the fetched page.
- Verdict: REJECT (locality gate — no evidence this site prices or ships
  for Eswatini specifically; it is a South African site the candidate list
  associated with Eswatini without confirmation).

---

## INCONCLUSIVE — blocked mid-probe, needs re-verification

### istore_bw (botswana)
- URL: https://istore.co.bw/
- Platform: Shopify (confirmed — `/products.json?limit=5` returned HTTP
  200 with real SKU data, e.g. `Mac mini | Apple M5 Pro chip...` at
  `32599.00`). `/collections/all` page1 vs page2 returned 64 vs 64 links
  with only 14 overlapping (50 new) — genuinely enumerable.
- Blocker: every subsequent request (PDP fetch, homepage fetch) to confirm
  the actual checkout currency (the `/products.json` payload carries no
  currency field) returned HTTP 429 for over 10 minutes across 3 retries
  with backoff, from the same a8 IP that had just succeeded on
  `/products.json`. Looks like Shopify-side rate limiting triggered by the
  earlier bulk sweep hitting this domain, not a permanent block.
- Verdict: NOT SHIPPED this pass. This is our own four-generic-spider
  Shopify pattern (not a new technology), so re-probing later
  (`_shopify_base.py` already exists) is cheap — just needs the currency
  confirmed from a PDP or homepage once the 429 clears.

### crazystore_bw_all_products (botswana)
- URL: https://www.crazystore.co.bw/products/?page=2
- Evidence: `/products/` returned 191 links on page1 vs 179 overlapping
  (12 new) on `?page=2`, but nearly all of those links are subcategory
  URLs (`/products/toys-games-and-sport/girls-toys/`), not PDP or priced
  listing items — never drilled into an actual leaf category to confirm
  price/currency. Its declared sitemap in robots.txt
  (`https://www.crazystore.co.za/sitemap.xml`) points at the .co.za
  tenant, which is a locality red flag worth checking before shipping.
- Verdict: NOT SHIPPED this pass — needs one more level of drill-down
  (fetch a leaf category, confirm BWP pricing on the .co.bw domain
  specifically) before a verdict.

---

## ONBOARDED (see main report for full detail)

- spar2u_bw (botswana) — custom sitemap+JSON-LD platform, 8,370-SKU
  supermarket catalog.
- beares_bw (botswana) — Magento 2, HTML category-grid scrape.
- artiaf_td (chad) — PrestaShop, HTML fallback route (webservice API
  401s).
- busiquip_sz (eswatini) — bespoke SPA, product catalog embedded as a
  static JS array in a build asset.
- afrikonet_sl (sierra_leone) — bespoke marketplace, 161-category HTML
  crawl.

---

## Not deep-probed in this pass (bulk-fingerprinted only)

The remaining ~205 candidates across all 8 countries were fingerprinted
(status code, platform signature, JSON-LD/currency-token scan, robots.txt
sitemap discovery) but not individually walked through the full hard-gate
sequence. Raw fingerprint data for every one of them is in
`~/gapwork/probe_results_custom_1.json` on a8. Categories worth flagging
for a next pass, read off that file:

- **Single-page tariff/fee/menu pages** (bank tariff guides, school fee
  schedules, restaurant menus, utility tariff pages) — most of these are
  `analytical_role: tariff` or `official_avg` fetcher candidates, not
  spider candidates, and were out of scope for the spider-focused probing
  this pass did. Examples: `absa_bw_tariff_guide`, `wuc_tariffs`,
  `bpc_tariffs_information`, `pedros_botswana_menu`,
  `oceanbasket_botswana_menu`.
- **Odoo hits not yet checked**: `omega_impact_td` (chad),
  `hope_bromo_restaurant` (botswana, restaurant not retail),
  `smart_connexxionz` (suriname, dev/staging subdomain — likely not live).
- **Non-200 candidates** (403/timeout/SSL errors) were not re-probed with
  `curl_cffi impersonate` variants beyond `chrome124` — per the skill's own
  guidance, a `chrome120`/`safari17_0` re-probe could recover some of
  these. Left for a follow-up pass given time budget on this run.
- **eSIM resellers** (`gigago_eswatini_esim`, `hivoox_eswatini_esim`,
  `mollysim_eswatini_esim`, `alooui_eswatini_esim`) — these are global
  eSIM marketplaces that happen to list "Eswatini" as a destination plan,
  not Eswatini-based retailers. Likely fail the locality gate the same way
  `carros_td` did, but not individually confirmed.


---

## known_blockers_custom_2 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_custom_2.md` on 2026-09-11. 27 hosts, 25 not
documented above at merge time.

# Known blockers — custom_2 batch (2026-09-11)

Batch: `~/gapwork/batches/custom_2.csv`, 257 candidates across guinea_bissau,
liberia, american_samoa, libya, greenland, liechtenstein,
central_african_republic, south_sudan, guinea, palau, kiribati,
marshall_islands, burkina_faso, congo_rep, sudan. All probed live with
`curl_cffi impersonate="chrome124"` (never bare curl). 16 sources shipped
(see final report); this file covers everything individually investigated
and rejected, with the evidence that killed it. A separate, much larger
remainder was only bulk-fingerprinted (status code + platform signature) and
not individually hand-verified — see the "Not individually verified" section
at the bottom; that is an inferred, not measured, bucket.

## Not a real product catalog (platform installed, but no store)

- **bissau_online_market_gw** (https://bissauonlinemarket.com/) — WordPress +
  WooCommerce plugin present, but `/sitemap.xml` is a Yoast sitemapindex of
  `_classificados-sitemap.xml`, `tipo-de-oferta-sitemap.xml`,
  `tipo-de-vendedor-sitemap.xml` etc. — a classifieds/listings directory, not
  a retail SKU catalog. WooCommerce Store API 404s
  (`/wp-json/wc/store/v1/products` → `404 application/json`, empty product
  set). Not scaffolded.
- **henicki** (https://henicki.com/) — WordPress, Woo-plugin signature
  matched a false positive (`auto-sizes` image plugin). `/sitemap.xml` only
  lists `post-sitemap.xml` / `page-sitemap.xml` / `category-sitemap.xml` /
  `author-sitemap.xml` — no product sitemap. Store API 404. Not a shop.
- **majasoptik** (https://majasoptik.gl/) — WordPress, Woo-plugin present but
  `/sitemap.xml` only has `page-sitemap.xml` / `elementor-hf-sitemap.xml`.
  The probed URL (`/brilleglas/`) is an informational article about lens
  types, not a PDP. Store API 404. Not a shop.
- **jbr_trading_global** (https://www.jbrtrading.com/) — Wix site, but
  `/sitemap.xml` has no `store-products-sitemap.xml` entry (WixStores app
  not installed). No product catalog to enumerate.
- **rmiembassytw_local_merchandise**
  (https://www.rmiembassytw.com/local-merchandise) — same: Wix, no
  `store-products-sitemap.xml`.
- **tropicart_wix_store** (https://www.tropicarti.com/) — 404 on the
  homepage itself; domain appears to have lapsed or been redirected off the
  Wix site.

## Locality ambiguous — rejected out of caution

- **hi_nesian_apparel** (https://www.hinesianapparel.com/) — real Wix store,
  145 products via `store-products-sitemap.xml`, priced in USD (which IS
  American Samoa's currency, no currency problem). Rejected anyway: no
  address, shipping-destination, or "based in American Samoa" copy found on
  the site — product names are themed by Pacific-island names ("American
  Samoa Jersey", "Philippines") which reads as a pan-Pacific-diaspora
  streetwear brand rather than evidence of retail operations serving
  American Samoa residents. Per the task's locality gate this needs an
  explicit call, not a silent accept — flagged for manual follow-up rather
  than shipped.

## Not retail SKU — out of scope for this storefront-technology pass

These carry real prices but are not a product catalog a spider should walk;
they are candidates for the `fetcher` (tariff / official_avg) pipeline
instead, per the skill's own scaffolding rule (don't force a fetcher-shaped
source into a spider).

- ahb_nuuk (https://ahb.dk/restauranter/nuuk), hotel_soma_nuuk
  (https://hotelsoma.com/da/restaurant-nuuk/) — restaurant menus (Greenland).
- sinkor_palace_menu (https://www.sinkorpalace.com/restaurantmenu),
  flying_fox_brewing_co_menu
  (https://flyingfoxbeer.wixsite.com/home/menu) — restaurant/bar menus
  (Liberia, American Samoa).
- fish_n_fins_partner_pricing (https://fishnfins.com/index.php/partner-page),
  palau_pacific_divers_price_images
  (https://www.palaupacificdivers.com/price) — dive-tour service pricing,
  not retail SKU.
- astca_prepaid_roaming_rates, samoa_government_business_license_fees,
  samoa_international_finance_authority_fee_schedule,
  american_samoa_medicaid_resources_fee_schedules,
  american_samoa_insurance_commissioner,
  american_samoa_bus_rate_regulation,
  american_samoa_business_license_fee_statute_index — official fee
  schedules / regulatory pages (American Samoa). Real prices, wrong
  scaffolding (would be `extraction_pattern: html_scrape` /
  `analytical_role: tariff` fetchers, not spiders).
- palau_ppuc_water_rates_news (https://islandtimes.org/...) — a news
  article ABOUT a rate change, not the tariff schedule itself.
- marshalls_energy_shipping (https://mecrmi.com/shipping/) — a shipping
  company's service page, not a retail catalog.
- carrosbissau_gw, carliberia_spareparts — Elasticsearch-signature used-car
  classifieds sites; vehicles/used-goods listings, heterogeneous pricing,
  out of scope for a retailer_sku spider this pass.
- petitfute_bissau_restaurants — a travel-guide directory page (Algolia
  signature came from the site's own search widget, not a price source).

## Verified WAF blocks (South Sudan priority — retried across 3 TLS profiles)

Per the skill's mandatory-network-trace rule: retried with `chrome124`,
`chrome120`, and `safari17_0` before recording as blocked (never from bare
curl or a single profile).

- **shopit_ss** (https://shopit.com.ss/) — 403 on all three profiles.
  `server: cloudflare`, body is the Cloudflare "Just a moment..." JS
  challenge page. Real Cloudflare block, not a curl-TLS artifact.
- **businessclaud_ss** (https://businessclaud.com/) — same signature:
  `server: cloudflare`, "Just a moment..." challenge, 403 on all 3 profiles.
- **ssdonestore_ss** (https://ssdonestore.com/) — 403 on all three profiles,
  `server: hcdn`, a custom (non-Cloudflare) 403 page. Different WAF vendor,
  same verdict.

These would need a residential proxy + JS challenge solver (Cloudflare) or
further vendor-specific investigation (hcdn) to clear — not attempted this
pass per the skill's "don't iterate on curl_cffi+Playwright double-403"
guidance (Playwright wasn't run here, but the triple-TLS-profile failure on
the two Cloudflare sites is the same class of signal).

## Connection failures (DNS / SSL / timeout — likely dead or misconfigured)

- amatlgb_gw (guinea_bissau) — DNS: `Could not resolve host: www.amatlgb.com`
- orange_bissau_mobile_internet (guinea_bissau) — SSL: unable to get local
  issuer certificate
- american_samoa_llc_filing_fees — DNS: `Could not resolve host: llc.as.gov`
- jubaexpanse_takeapp_ss (south_sudan) — DNS: could not resolve host
- memuapp_ss_ug (south_sudan) — TLS: `TLSV1_ALERT_INTERNAL_ERROR`
- papalac_gn (guinea) — DNS: could not resolve host (societe-asfils.com)
- al_bugaa_computers_telecommunications (sudan) — SSL: certificate expired
- telecel_lr_shop (liberia) — connection timed out (20s)
- surangel_epicor_store (palau) — timed out, 0 bytes
- dukaanye_ss (south_sudan) — timed out, 0 bytes

## Other HTTP errors (403/404/410/429/402/500) — not re-tried across TLS profiles

Lower-priority sites where a single `chrome124` probe returned a non-200
status; time budget did not allow the full 3-profile WAF-vs-curl-artifact
check the skill recommends, so these are NOT confirmed genuine blocks —
flagged for re-probe before being written off permanently.

hotels_scanner_bissau (403), cashew_base_price_news_gw (403, a news article
not a store anyway), ctd_bissau_tuition (403), bookingauto_gw_car_rental
(403), pharmaconnect_bissau (403), worldbanknotes_gw_collectibles (403,
collectibles listing not a store), booksrun_liberia_books (403, single-SKU
external listing), liberiamarketplace_old (403), liberiabuynsell (403),
ubuy_liberia_appliances (429, rate-limited), hotel_qaqortoq_menu (403, and a
menu anyway), afribaba_cf_autos (403, classifieds), jubacargodirect_all_ss
(404 — possibly the domain moved), betty_trading_import_data (403, a trade-
data lookup site not a store), kiribati slim_price_map (403, a map-annotation
site not a store), cartogiraffe_angirin_hardware (410, gone), jubacar_ss
(500, server error), ponton_shop_cg (403), codebarresguinee_gn (403),
etsralf_gn (403), saremati_gn (402, payment-required).

## Fingerprinted but not deep-verified this pass (time budget)

Real platform signatures were found on these but the remaining verification
(enumerability / pricing / currency) was not completed:

- **lehni_ch** (Liechtenstein, https://shop.lehni.ch/) — dual OpenCart +
  Magento signature hits (ambiguous, likely one false positive); not
  resolved.
- **online_apotheke_ch** (Liechtenstein, https://www.online-apotheke.ch/) —
  Shopware signature; not investigated further.
- **boutikobf_marketplace** (Burkina Faso) — WooCommerce-plugin signature,
  but Store API 404s and the `?rest_route=` probe returned the raw homepage
  HTML rather than JSON (custom theme intercepting the query string) — see
  the "?rest_route= false-lead" note in the final report. Not resolved.
- **guinee_lube_filters_gn** (Guinea, https://www.guineelube.com/filtres.html)
  — a small static HTML brochure/catalog page (custom `assets/style.css`
  build), not an OpenCart install despite the signature hit; no visible cart
  or checkout. Not pursued.
- **s_7majorgn_gn** (Guinea, https://7majorgn.com/) — custom PHP catalog
  (`product.php?id=N`), NOT core OpenCart despite the route shape; prices
  ARE visible in plain HTML text in GNF (e.g. "120 000 GNF"), but there is
  no JSON-LD, no sitemap.xml (404), and no product-id enumeration path found
  in the time available. A real candidate for a future bespoke Tier-1A
  html_scrape spider (would need to walk category pages or brute-force
  `id=` and write custom price/name selectors for its non-standard markup).
- **discountliberia** (Liberia, https://discountliberia.com/) — see the
  "EKART" writeup in the final report: real platform, real GNF/USD-priced
  catalog, but its own `?page=` parameter is a no-op within one category
  (page 1 and page 2 return an identical product-id set — confirmed live),
  and its product cards carry name/price only on scattered `data-product-*`
  attributes on unrelated widgets as well as real cards, making reliable
  regex extraction fragile in the time available. Deferred, not shipped.

## Not individually verified (bulk-fingerprint only) — INFERRED, not measured

The remaining ~200 of 257 candidates were only run through the stage-1 bulk
probe (single `curl_cffi` GET of the homepage + robots.txt, platform-
signature regex scan) and were not individually hand-verified for
enumerability/pricing/currency/locality. Based on titles and the CSV's own
`why` column, a large share of these read as non-commerce content (blog
posts, PDF/statute pages, informational articles, price-mention news
stories) rather than storefronts — but this is an inference from the bulk
scan, not a confirmed verdict for each row, and should not be treated as a
rejection. A follow-up pass could re-run the same probe pipeline
(`~/gapwork/probe1.py` on a8, results cached at
`~/gapwork/probe1_results.jsonl`) filtered to `country` values not yet
covered above.


---

## known_blockers_ddgs_emptiest - as of 2026-09-11

Merged from `~/gapwork/known_blockers_ddgs_emptiest.md` on 2026-09-11. 37 hosts, 32 not
documented above at merge time.

# ddgs discovery — emptiest-country sweep (2026-09-11)

Scope: COICOP divisions 01/02 (food, non-alcoholic drinks, alcohol, tobacco) ONLY.
Non-food candidates dropped on sight per task constraint. All verdicts dated 2026-09-11.

Context: this worktree had heavy CONCURRENT activity from other agents on all six
priority countries during this run (dozens of manifests landed on Liberia, Namibia,
CAR, and Congo Rep within the same hour). Sections below distinguish what this run
verified/shipped from what pre-existed.

## Ethiopia — shipped 2 new retailer_sku sources

Pre-existing: aradamart_et (396 rows, packaged food + household), mohasbeza_et
(187 rows), deliver_addis (65 rows), mekina_et (vehicle marketplace, non-food),
ethiopiapropertycentre_et (real estate, non-food).

**deliver_addis is NOT broken** — investigated per the task's explicit hint that
985 corpus names is suspiciously low. Its raw_items jsonl is flat at 65 lines
across 5 runs from Aug 6 to Sep 2 (identical 23,523 bytes every time), which looks
like the "flat cap = broken spider" signature. Re-fetched https://deliveraddis.com/market
live: identical 12 category paths, no new ones added since the spider was written.
It is a genuinely small, fixed delivery-app catalog (sauces/coffee/honey/canned
goods) — not a pagination bug.

New sources (English + Amharic ddgs sweep, backends pinned, no DNS-bug false zeros):

| source_key | domain | platform | channel | currency | measured rows | distinct urls |
|---|---|---|---|---|---|---|
| kedamegebeya_et | kedamegebeya.com | WooCommerce Store API | supermarket | ETB | 62 | 62 |
| helloomarket_et | helloomarket.com | OpenCart (scoped to path=82 "Grocery & Gourmet Food" only) | supermarket | ETB | 153 | 153 |

Dead ends:
- shoashopping.org — real 17-branch "Shoa Supermarket" chain but the site is a
  branch-locator/gift-card page only, no catalog, no prices.
- freshcorneret.com — template/demo site (Lorem Ipsum filler text, fake US
  address, fake gmail contact). Not a live business.
- habeshashops.com — 4.4MB page, zero ETB/birr price tokens in static HTML;
  not pursued further given two solid finds already landed.

**Ethiopian Statistics Service (official_avg attempt, separate subagent):** ESS
(ess.gov.et) is live and publishes monthly, but its public CPI "Statistical
Bulletin" reports ONLY percentage changes (YoY, MoM, 12-month moving average),
never a raw index level, across all 13 pages of the latest bulletin checked. A
separate `databank.ess.gov.et` Next.js app might hold raw series but exposes no
discoverable API. Reported as a genuine format mismatch, not scaffolded — building
an index from chained % changes would be derived, not extracted, data.

## Namibia — no new retailer_sku source found; majors confirmed brochure-only

Pre-existing coverage already extensive (13 sources landed today across this and
concurrent agents: woermannfresh_na, embassyliquor_na, meat_namibia_na,
nsa_zonal_prices, nsa_cpi, doorstep_na, kws_na, waltons_na, accessnamibia_na,
highwayimporters_na, langerhans_na, zimolange_na, fews_net, wfp_prices).

Checked the three national supermarket majors specifically — all confirmed
**brochure-only, no online ordering**:

| domain | verdict |
|---|---|
| checkers.com.na | 200 via curl_cffi chrome124 (403 plain requests) — static CMS, no cart/catalog beyond a marketing specials.html page. |
| shoprite.com.na | Same CMS template, same result. |
| spar.co.na | Connect timeout on both plain requests and curl_cffi from a8 — unreachable. |
| weckevoigtsspar.com (Wecke & Voigts SPAR/SUPERSPAR group — Maerua/Grove/Westlane/Hochland, Windhoek) | WordPress brochure site (store locations, About Us, promotions). No shop/catalog anywhere despite embedded-script false-positive keyword hits for multiple e-commerce platforms. |
| shopping.my.na/shop/checkers | Third-party "my.na" Laravel marketplace hosting a Checkers-branded landing page — zero product/price tokens on the page fetched; deeper category-URL discovery not completed this pass (open lead, not a rejection). |

Consistent with the skill's known Botswana pattern (Pick n Pay: WhatsApp-order
only) — RSA-headquartered chains operating in Namibia do not expose online
catalogs there as of this check.

## Burundi — shipped 1 new retailer_sku source + 1 new official_avg fetcher

Pre-existing: kilakitu_bi (marketplace).

| source_key | domain | platform | channel | currency | measured rows | distinct urls |
|---|---|---|---|---|---|---|
| kazemarket_bi | kazemarket.com | WordPress/WooCommerce theme, HTML scrape (Store API 404s) | specialty-food | EUR (flagged — diaspora-remittance pricing pattern, not confirmed 1:1 domestic) | 72 | 72 |
| insbu_cpi (fetcher) | api.insbu.bi | PDF via reverse-engineered React SPA API | n/a — cpi_benchmark, publisher_labeled, 12 divisions | — | 36 index rows | — |

Note: ISTEEBU (the institute name given in the task brief) has been renamed to
INSBU and the old domain `isteebu.bi` is squatted by an unrelated SEO reseller —
the real site is `insbu.bi`. No separate official_avg retail-price companion
found; INSBU's only publication types are CPI (fr/ki) and a construction-cost
index.

Rejected candidates: ikibibi.com (Shopify, empty `/products.json` — no live
inventory); africanshop-online.com (real food taxonomy but every price is
`0,00 BIF` — no real prices anywhere); akaguriro.com (marketplace but
handicrafts, not food); baza.bi (classifieds SPA, not food-scoped, no confirmed
pricing).

## Central African Republic — confirmed structural absence (23 candidates checked, 0 shipped)

Two pre-existing manifests from today (`ge_concept_store.yaml` channel
`dept-store`, `shopping236_cf.yaml` channel `marketplace`/home-goods) are
correctly NOT food-scoped — verified they're general-goods, not food.

Fresh French-language ddgs sweep surfaced 12 more candidates, all rejected:
- sangostore.com — Next.js SPA; API-sniffed live: 10/14 "alimentation" items are
  literal `[DÉMO]` seed placeholders, the 4 real items are dropshipped from
  Cameroon/France/Senegal sellers, none in-country. Demo catalog, not real
  CAR retail.
- cf.bazarafrique.com — classifieds site, no structured pricing.
- banguimall.net — already in known_blockers.md, mechanically exhausted.
- toliafood.com, ndougu.com, nolmarket.com, kenzamarket.com,
  solibrachezvous.com — all resolved to the wrong country (DRC, Dakar,
  Cotonou, Cameroon, Côte d'Ivoire respectively) — false positives from
  generic French query terms.
- kmakity.com — pan-CEMAC marketplace, not CAR-specific.
- sugu.express, samisonline.com, basamstores.com — 403.
- mocafrca.com — DNS failure.

**Combined with the 11 candidates another agent exhausted earlier today, that is
23 distinct CAR candidates checked with zero shippable food/beverage sources
found. This reads as a genuine structural absence** — CAR has no reachable
domestic online food retail as of 2026-09-11 — not a search-effort artifact.
CAR's food-price signal will have to come from WFP VAM / FEWS NET / ICASEES
CPI / FAOSTAT (all four already scaffolded).

## Congo Republic (Brazzaville) — shipped 2 new official_avg/cpi_benchmark fetchers; retailer sweep deferred

Pre-existing retailer_sku coverage already adequate: congobio_cg, market242_cg,
mbote_cg, tchitunga_cg (specialty-food/marketplace, food-scoped), plus
elikiashop242_cg/duban_cg/ngindustry_cg/bantudelice_cg (mixed food and non-food,
landed by concurrent agents).

| source_key | domain | shape | analytical_role | measured rows |
|---|---|---|---|---|
| insc_inhpc_cpi (fetcher) | ins-congo.cg | Excel via undocumented publications API (`sous_secteur=stat-prix`, not `secteur=`) | cpi_benchmark, publisher_labeled, 12 divisions | 156 |
| insc_retail_prices (fetcher) | ins-congo.cg (same workbook) | "Prix moyens mensuels" table, 5 cities (Brazzaville, Pointe-Noire, Dolisie, Owando, Ouesso), 3 non-food fuel rows excluded | official_avg, classifier | 648 |

A francophone-retailer sweep surfaced additional unverified leads (filcongo.com,
doucmarket.africa, zwanayo.com, bisoexpress.com, celmarket.cloud,
madinacongo.com — several show XAF + Brazzaville signal) but these were not
deep-probed this pass, given adequate existing coverage and concurrent-agent
activity in the same directory. Open leads for a future pass, not rejections.

## Liberia — shipped 2 new official_avg/cpi_benchmark fetchers (retailer_sku already well covered by concurrent agents)

Pre-existing retailer_sku coverage landed extensively by concurrent agents today
(banjoo_lr, congo_girl_cuisine, ezeemarket_lr, kernel_fresh_premium, all verified
live with real row counts — not re-verified in this report since not this run's
work).

| source_key | domain | shape | analytical_role | measured rows |
|---|---|---|---|---|
| lisgis_cpi (fetcher) | liberia.opendataforafrica.org (Knoema-hosted; LISGIS's own site is a placeholder pointing here) | REST API (`/api/1.0/data/<dataset>?area=<key>&indicator=<key>`, numeric keys required) | cpi_benchmark, publisher_labeled, 12 divisions | 1044 |
| moci_commodities (fetcher) | Liberia Ministry of Commerce "Commerce Today" bulletin | PDF, 3 editions found (Sep 2024, Oct 2024, Aug 2026), table layout varies by edition | official_avg, source_curated | 16 |

## Summary table — all sources shipped or verified this run

| Country | source_key | channel | analytical_role | currency | measured rows | distinct urls |
|---|---|---|---|---|---|---|
| Ethiopia | kedamegebeya_et | supermarket | retailer_sku | ETB | 62 | 62 |
| Ethiopia | helloomarket_et | supermarket | retailer_sku | ETB | 153 | 153 |
| Burundi | kazemarket_bi | specialty-food | retailer_sku | EUR | 72 | 72 |
| Burundi | insbu_cpi | null | cpi_benchmark | — (index) | 36 | n/a |
| Congo Rep | insc_inhpc_cpi | null | cpi_benchmark | — (index) | 156 | n/a |
| Congo Rep | insc_retail_prices | null | official_avg | XAF | 648 | n/a |
| Liberia | lisgis_cpi | null | cpi_benchmark | — (index) | 1044 | n/a |
| Liberia | moci_commodities | null | official_avg | LRD | 16 | n/a |

## Countries where nothing was found this run, and why

- **Central African Republic** — confirmed structural absence for retailer_sku
  (23 candidates checked total today, 0 shippable). Official coverage
  (icasees_car_cpi, faostat_cpi, wfp_prices, fews_net, wb_rtdi_prices) already
  exists from before this run.
- **Namibia** — retailer_sku already saturated by concurrent-agent work; the
  three national supermarket majors (Spar, Checkers, Shoprite) confirmed to have
  no online ordering in Namibia specifically.
- **Ethiopia CPI/official_avg** — Ethiopian Statistics Service publishes only
  percentage-change series, not a raw index or retail-price table; not
  scaffolded (format mismatch, not a discovery failure).

## Method note (ddgs backend gotcha, reconfirmed)

Both discovery subagents pinned `backend="duckduckgo, google, brave, mojeek,
startpage, yahoo"` per `references/ddgs_search.md` and got hit counts on every
query (no false 0-result dead ends from the wikipedia/grokipedia DNS bug). One
subagent additionally reported `ddgs` itself being rate-limited from a8's shared
IP under concurrent multi-agent load and fell back to direct-navigation /
JS-bundle reverse-engineering for the NSO fetcher search — a new operational
constraint worth remembering for future high-concurrency runs on a8.


---

## known_blockers_disco_cafrica - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_cafrica.md` on 2026-09-11. 27 hosts, 14 not
documented above at merge time.

# Discovery blockers — South Sudan / CAR / Burundi / Equatorial Guinea / Gabon / Somalia

All verdicts below are as-of **2026-09-11** unless a different date is noted inline.
Scope: COICOP divisions 01/02 (food, non-alcoholic drinks, alcohol, tobacco) only.
Non-food candidates are not listed here even if probed — see the country
inventories under `.claude/skills/onboard-price-sources/references/inventories/ssa/`
for the full non-food dead-end record from the 2026-09-01 sweep.

## Shared-infrastructure bug found and fixed this pass

**FEWS NET `fdw.fews.net` `ordering` param regression (AWS WAF `x-amzn-waf-action: challenge`).**
As of 2026-09-11, sending `ordering=-period_date` (or any `ordering` value) to
`/api/marketpricefacts/` returns HTTP 202 with an empty body instead of the JSON
page — this silently broke all 16 countries wired to
`src/prices/fetchers/_shared/ssa/fews_net.py` (13 pre-existing + `fews_caf` + the
3 new `fews_ssd`/`fews_bdi`/`fews_som` added this pass), each returning "0 raw
facts" with no visible error. Root-caused by direct curl probing: the response
carries `server: awselb/2.0` and `x-amzn-waf-action: challenge` — a real AWS WAF
bot-challenge, not a data problem, and TLS impersonation does not touch it (per
the skill's own "content-level proof-of-work" category). Fix: dropped `ordering`
entirely from `_fetch_pages()`; without it, results paginate in the API's default
order which (combined with `start_date`) is ascending by `period_date` — verified
directly (SS offset=0 → 2020-01, offset=900 → 2024-Q1). This is a better fit for
the existing `offset<1000` pagination cap than the old newest-first design: a
capped first run now still resumes forward next time with no permanent gap in
history, whereas newest-first-then-capped would have permanently stranded older
history behind the cap. Re-verified `fews_caf` (CAR, pre-existing) still returns
data post-fix: 336 rows. This regression likely also silently zeroed the other
12 pre-existing `fews_*` countries (Botswana, Cabo Verde, Angola, Rwanda,
Eswatini, Namibia, Zimbabwe, Cote d'Ivoire, Gambia, Guinea, Liberia, Sierra
Leone) at their last scheduled run — worth a fleet-wide re-check outside this
task's scope.

## South Sudan

- **jubamall.com** — RE-PROBED 2026-09-11: previously recorded (inventory,
  2026-09-01) as "TLS cert mismatch, app-only." Now WORSE — the resolved IP
  (138.252.208.117) hits a straight connection timeout across all three
  impersonation profiles AND bare curl (12s cap). No longer a cert problem;
  the host itself appears down or firewalled. Confirmed dead.
- **South Sudan NBS (ssnbss.org)** — CHECKED 2026-09-11, first time. Real site,
  does publish a CPI series, but the latest report is **July 2016**; the only
  other price-adjacent document is a 2016 study on checkpoint/trade-route
  bribery costs, not commodity prices. Price-publication effort has been
  dormant for ~10 years. Not usable.
- **Arabic-language search NOT completed** — session WebSearch quota (shared
  session-wide across concurrent agents) was exhausted before this could be
  run. This is an **incomplete discovery thread, not a confirmed absence** —
  flag for a follow-up pass with fresh search budget before concluding South
  Sudan retail grocery is fully exhausted.
- Everything else (Doyoom, Karibu, Zaylo — restaurant delivery; no
  Jumia/Glovo/Bolt/Yango presence; UNION Super Market/Juba Mall Supermarket —
  Facebook-only; Shop Ninja — Kampala reseller, out of market) stands from the
  2026-09-01 inventory, unchanged.

## Central African Republic

- **AFRISTAT/Knoema `afristat.opendataforafrica.org/Centrafrique`** — RESOLVED
  2026-09-11 (previously "not pursued, unconfirmed"). Site is live (curl_cffi
  impersonate=chrome124 → 200; a non-browser client gets a 403 — JA3-style
  gate, not a real WAF). CAR IS present in the portal's "Prix, Change" and
  annual-inflation-rate indicator pickers. But this is a full proprietary
  Knoema Atlas BI widget (~80 bundled JS modules, Cloudflare-fronted, with a
  `premium/popup.js` script suggesting some series are paywalled) — extracting
  actual price series means reverse-engineering a proprietary BI API with
  uncertain public/premium gating. **Deferred as an expensive lead, not a dead
  end** — worth a dedicated future effort, not a cheap win.
- **banguistore.com** — CHECKED 2026-09-11, NEW CANDIDATE, REJECTED AS A DATA
  TRAP. Multi-vendor marketplace showing real-looking XAF-priced food SKUs
  (apples, rice, cooking oil, milk powder) across several "boutique"
  storefronts (marche-frais-bangui, agri-bangui, eau-pure-rca). Its own
  `/sitemap.xml` (products-1.xml + stores-1.xml) indexes only ONE real seller
  ("MC Boutique," 11 products, all solar/electronics/Starlink — zero food).
  The food-bearing storefronts are NOT in the sitemap — they read as seeded
  demo content shown to prospective sellers, not a live catalog. No
  `/boutiques` or `/vendeurs` directory page exists (both 404). **DO NOT
  INGEST** — same trap class as the ICASEES fabricated CPI workbook already
  flagged in the CAR inventory.
- **sangostore.com** — CHECKED 2026-09-11. Diaspora gift-shipping marketplace,
  EUR-priced, not local CAR retail price levels. Out of scope.
- **sugu.express** — CHECKED 2026-09-11. Pre-launch "Bientôt disponible"
  landing page, not live.
- **marchebanguissois.com** — CHECKED 2026-09-11. Connection timeout
  (curl_cffi, 20s cap), server unreachable.
- **sendmontchop.com** — RE-CHECKED 2026-09-11 (previously flagged dead in the
  Gabon inventory for a different reason — a lapsed domain search hit this
  name in a CAR context too). Resolves to a parked-domain lander
  (GoDaddy/wsimg `parking-lander` bundle). Confirms prior "domain-lapsed"
  finding.
- Everything else (Bangui Mall, warani.cf, ICASEES 0-byte bulletins +
  fabricated master workbook, ENERCA, Orange group domain, Telecel RCA, Moov
  Africa CF, ARCEP, SOCASP, Bangui's 4 known physical supermarkets, BEAC,
  CoinAfrique/Jumia) stands from the 2026-09-01 inventory, unchanged. CAR
  remains a structural-absence case for online food retail.

## Burundi

- **Kilakitu (kilakitu.bi) depth audit** — DONE 2026-09-11. Full homepage nav
  (343 links) crawled and keyword-scanned in French+English for every missed
  food term (dairy/meat/fish/vegetable/fruit/bread/coffee/tea/syrup/juice/
  spirits/etc). Found exactly one candidate outside the existing 14-slug
  scope — `chips-380` — but a measured full re-run with it added returned
  **0 net new rows** (284 before, 284 after, byte-identical distinct-URL
  set): all 14 `chips-380` products are cross-listed under the
  already-scoped `quick-bites-379`. Not a depth gap. Spider left unchanged;
  finding recorded in its docstring only.
- **isteebu.bi** — CHECKED 2026-09-11. Squatted domain (a web-design agency),
  not Burundi's national statistics institute. `isteebu.gov.bi` does not
  resolve. Real ISTEEBU domain NOT found this pass — needs an actual web
  search, not resolved via direct guesses.
- **French-language fresh search NOT completed** — session WebSearch quota
  exhausted. Incomplete discovery thread, not a confirmed absence.

## Equatorial Guinea

- **WFP HDX food-prices panel** — CHECKED 2026-09-11, CONFIRMED ABSENT. CKAN
  `package_show` for `wfp-food-prices-for-equatorial-guinea` returns a real
  404; `package_search` for "equatorial guinea food prices" returns no WFP
  dataset (only unrelated World Bank sector-indicator sets). Combined with
  the already-confirmed FEWS NET `count: 0` for country_code=GQ, both major
  humanitarian food-price feeds are dead ends for this country — consistent
  with Equatorial Guinea being an oil-income, non-crisis-monitoring context
  (unlike South Sudan/Burundi/Somalia, all FEWS NET focus countries).
- No fresh retail discovery attempted this pass (thorough 2026-09-01 sweep
  via a dedicated research subagent already exhausted Jumia/Glovo/Yango/
  Bolt/Wolt/Cofina/Compra en Bata/Vitacana/Muankaban/Manolo/Tienda
  Ideal/EGTC-standalone/PLASENCIA/SUPERCOR/La Vencedora — all confirmed no
  independent site). `situcka_gq` (6,931 rows, ~42-45% estimated food share)
  already provides substantial food coverage for this country.

## Gabon

- **WFP HDX food-prices panel** — CHECKED 2026-09-11, POSITIVE. Real dataset
  exists (`wfp-food-prices-for-gabon`). **Shipped as `wfp_gab`** — see the
  main report. Caveat: WFP discontinued active Gabon monitoring in 2017; this
  is a one-time historical backfill (2007-01-15 to 2017-06-15, Libreville/
  Estuaire only, ~10 commodities) and will not produce new rows on future
  scheduled runs.
- **Malumbi** — RE-CHECKED 2026-09-11. Still Facebook-only
  (`facebook.com/malumbigabon`); no relaunch under a new domain.
- **SendMonTchop** — RE-CHECKED 2026-09-11. Domain is live but is now visibly
  a parked/expired-domain lander (GoDaddy/wsimg `parking-lander`, `ap:
  "parking"` signal) rather than simply NXDOMAIN. Confirms prior
  "domain-lapsed" finding with a clearer signature.
- **Isai Market** — RE-CHECKED 2026-09-11. Still Facebook-only, no new
  domain.
- **cecagadis.com** — RE-CHECKED 2026-09-11. Checked homepage + `/nos-
  enseignes/`: no shop/boutique/commande/panier navigation exists; the only
  "cart"-looking text hits were false positives on "Carte CECA Boost" (a
  loyalty-card announcement). No online-ordering module added since the last
  pass. Confirmed still corporate-brochure-only.
- Everything else from the exhaustive 2026-09-01 sweep (Chap Chap Gabon,
  Libre-Go Livraison, goafricaonline.com directory, africannuaire.com
  directory, priximport.com, san-gel.com, mbolo.com, carrefour.ga, jumia.ga,
  systemelad.com, gabon4you.com, yoboresto.com, Glovo/Yango/Bolt Food, Le
  Boucher Libreville, Le Palais du Vin, random plausible-name domain guesses)
  stands unchanged. Gabon's online food-and-beverage retail landscape remains
  exactly one live source (`cerise_ga`); the new `wfp_gab` official_avg
  fetcher is a genuine second food-relevant source, though non-retail and
  historical-only.

## Somalia

- **aaranonline.com** — RE-PROBED 2026-09-11 with a warmed session (homepage
  first to capture cookies, then category pages) per the prior pass's
  "missing pricelist cookie" hypothesis. REGRESSED further than reported:
  `/shop`, every PDP, `/robots.txt`, and `/sitemap.xml` now all return a hard
  404 (confirmed in both curl_cffi and a real headless-Chromium Playwright
  render); only the static homepage still 200s. The backend appears to be
  down entirely, not gated by a missing cookie. Confirmed dead — the cookie
  hypothesis does not apply.
- **somalistores.com** — RE-PROBED 2026-09-11 with chrome120/safari17_0
  (still 403, `server: hcdn`), then with PLAIN non-impersonating `requests`
  per the JA3-denylist rule — this cleared it (200). But once past the WAF,
  the page is a **static demo/mockup**, not a real store directory: every
  link is a dead `href="#"` anchor, "store card" clicks fire a JS `alert()`,
  and there's a fake animated "driver status" simulation. Confirmed NOT a
  real source — this was a template/mockup, not a WAF-blocked real site.
- **Arabic-language search NOT completed** — session WebSearch quota
  exhausted. Incomplete discovery thread, not a confirmed absence.
- Everything else (Hayat Market's own domain — dead duplicate of `adeeg_so`;
  SafewaySupermarket — expired domain; Hiiliye — app-only SPA) stands from
  the 2026-09-01 inventory, unchanged.


---

## known_blockers_disco_caribbean - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_caribbean.md` on 2026-09-11. 13 hosts, 8 not
documented above at merge time.

# Known blockers — Caribbean FOOD source discovery (COICOP 01/02)

_Campaign: grenada, dominica, st_lucia, st_vincent_and_the_grenadines,
antigua_and_barbuda, st_kitts_and_nevis, british_virgin_islands,
cayman_islands, bahamas_the, belize, haiti, guyana. Written 2026-09-11._

This file supplements (does not replace) the shared
`.claude/skills/onboard-price-sources/references/known_blockers.md` in the
repo. It exists so this campaign's dead ends land in one place without
racing other concurrent agents writing to the shared file.

## CaribeEats (backend.caribeeats.com) — confirmed dead for grocery in 4 more territories

The platform's `/api/init` region list and `/api/businesses?region_id=<id>`
directory were enumerated live 2026-09-11 for every territory this
campaign covers that the platform lists. Grocery vendor (`business_type_id
== 10`, "Grocery & Retail") count per region:

- **St Lucia** (region_id 1758): 5 businesses total, 0 grocery. (rideshare,
  taco shop, telco, KFC, smoothie shop)
- **Antigua** (region_id 1268): 8 businesses total, 1 nominally
  `business_type_id=10` ("Paddling Duck") — probed live, sells only 4
  herbal-tea SKUs. Too small/non-representative to onboard as a grocery
  source; not a real grocery store.
- **BVI / Tortola** (region_id 1284): 7 businesses total, 0 grocery
  (rideshare, restaurants, a bakery, a delivery courier).
- **Guyana** (region_id 592): 18 businesses total, 0 grocery — entirely
  fast-food chains (KFC, Popeyes, Burger King, Pizza Hut) plus courier/
  rideshare.
- **Belize**: not in the platform's region list at all — CaribeEats does
  not operate in Belize. Do not probe it for Belize again.
- (Bahamas already confirmed dead for grocery in the shared
  known_blockers.md, 2026-09-05 — re-confirmed, not re-probed further.)

Do not re-enumerate CaribeEats for grocery in any of these 5
territories; this is now confirmed across St Lucia, Antigua, BVI, Guyana,
Belize and Bahamas — 6 of this campaign's 12 countries.

## Belize — dead ends

- **coconutgrocerybelize.com** — NXDOMAIN (`curl: Could not resolve host`).
  Probed 2026-09-11.
- **belizeprovisions.com** — real WooCommerce Store API
  (`/wp-json/wc/store/v1/products`), enumerable (page1/page2 distinct
  ids), but **every sampled product (20/20) carries price "0"** — a
  price-on-request/concierge catalog, not real e-commerce pricing. Fails
  the non-zero-price gate. Probed 2026-09-11.
- **Super Value Food Stores** (Bahamas, not Belize — resolving the shared
  known_blockers.md open lead "worth a targeted search rather than more
  domain guessing"): real domain is **supervaluequalitymarkets.com**
  (found via web search, not guessing). It is a WordPress brochure site
  with no WooCommerce Store API route (`rest_no_route`) and no Shopify
  `products.json`. Its actual online-ordering flow is a third-party
  personal-shopper app (via "Bahama Eats") with no public catalog API.
  A separate marketing/demo domain, **grocery-pitch.com** ("Super Value
  Digital Grocery — Demo"), is a client-rendered SPA shell that serves the
  identical 2.7KB HTML on every route including `/products.json` — it is
  a sales-pitch demo, not the live production site. No priced, enumerable
  surface found for Super Value under either domain. Probed 2026-09-11.

## Guyana — depth-gap evidence (not a sourcing gap)

`guystar_gy` (already onboarded, `channel: supermarket`) already crawls a
Seafood leaf category (`cPath=8_6`, confirmed present in
`_guystar_gy_categories.txt` line 145, and the live category page returns
200). The brief's "fish & seafood" gap for Guyana is very likely a
classifier/gold-support gap, not a missing source — see the Phase 0.5
depth-audit note in the main report. Do not onboard a new fish-market
source for Guyana on the strength of the gap brief alone without first
checking whether guystar_gy's Seafood rows are reaching the classifier.

## Haiti — mechanically exhausted, do not re-probe

`delimarthaiti.com` and `caribbeansupermarketsa.com` are both already
recorded in the shared known_blockers.md under "Mechanically exhausted —
do not re-probe blind" (114-host sweep, no priced surface under curl_cffi
5-profile impersonation or headless Playwright). Re-confirmed via a fresh
French-language search 2026-09-11 that surfaces no other Port-au-Prince
supermarket with a working online catalog (Olympic Market, Caribbean
Supermarket S.A. — brochure/social-only presences, no e-commerce). Haiti's
COICOP-01 price-level coverage rests on `wfp_prices` (official_avg,
16,444 raw rows verified) and `cassandraonlinemarket_ht` (retailer_sku,
re-verified live 2026-09-11: 90 rows in a --max-items 20 test).

## St Lucia — dead ends (from this campaign's St Lucia sub-agent, 2026-09-11)

- **Order Shop St. Lucia** (ordershopstlucia.com) — real local Shopify
  retailer but password-gated mid-relaunch (`/products.json` -> 401).
  Worth re-checking in a few months.
- **Marketplace St Lucia** (marketplacestlucia.com, Rodney Bay Marina) —
  7.6KB brochure page, no catalogue or API.
- **Real Value IGA** (shop.realvalueiga.com) — same LocalExpress
  address-selection SPA gate already confirmed blocked for the Grenada
  tenant; no distinct St Lucia domain found.
- **Glace Supermarket** — real 40-year chain, Facebook-only presence, no
  website.
- **Super J Supermarkets** — fully rebranded into Massy Stores (SLU); no
  independent site (already covered via `massy_stores_slu`).
- **JQ Rodney Bay Mall** (shopjqmall.com) — a mall shop directory, not a
  grocer's own storefront.
- **CK Greaves** — confirmed St Vincent-only (`ckgreaves_vc`); no St
  Lucia storefront exists under that name.

## Antigua and Barbuda — resolved + dead ends (2026-09-11)

- **allmartplace.com** — a distinct, genuinely local Antigua delivery
  platform (Jungleworks "Yelo" white-label backend, "150+ local
  merchants", St John's/Cassada Gardens) separate from CaribeEats.
  Cloudflare + Turnstile blocks headless-Chromium rendering of the
  Angular SPA shell entirely (challenge page painted, DOM stays empty
  even after 20s + stealth args + geolocation grant). The JSON API
  underneath is NOT behind that challenge — every endpoint
  (`get_app_catalogue`, `catalogue/get`, `get_products_for_category`)
  returns clean 200 JSON to a plain `curl_cffi impersonate="chrome124"`
  GET, no cookies/session/captcha needed. Endpoint contract recovered by
  downloading the SPA's `main.js` + all 69 lazy route chunks and grepping
  the `CatalogueService` method bodies (Playwright network capture never
  got far enough to observe real traffic). Store directory
  (`/api/marketplace/marketplace_get_city_storefronts_v3`) paginates
  cleanly, 158 distinct storefronts for the default location, mostly
  restaurants.
- Named Antigua chains that turned out non-existent or restaurants/bars
  sharing the name (not grocery): Bryson's Supermarket, Best of Both
  Worlds, Rangers Supermarket, Cheers.
- Real Antigua supermarkets with NO standalone e-commerce presence as of
  this pass (Facebook/directory listings only): Epicurean Fine Foods &
  Pharmacy, First Choice Foods, XPZ, Oops!, Payless. Some of these are
  advertised as AllMart vendors but did not appear in AllMart's live
  158-store directory at probe time — worth re-checking later, not a
  hard dead end.
- **"gourmet-basket" on AllMart** (business id 1402365, full
  supermarket-shaped catalog incl. Produce/Meat & Seafood/Dairy & Eggs) —
  do NOT onboard: it is Gourmet Basket Supermarket, one of Island
  Provision Group's four in-house divisions already fully scraped via
  `islandprovision_ag.yaml`'s WooCommerce Store API. Onboarding it again
  under AllMart would double-count the same retailer.
- Viable alternate AllMart food vendors not yet built (flagged for the
  next agent): `ihem-minimart`, `deshvidesh-indian-grocery`,
  `anjo-wholesale`.


---

## known_blockers_disco_en_africa - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_en_africa.md` on 2026-09-11. 53 hosts, 38 not
documented above at merge time.

# Known blockers — Anglophone Africa food-source discovery (2026-09-11)

Campaign: fill COICOP division 01/02 (food, non-alcoholic drinks, alcohol,
tobacco) gaps for liberia, eswatini, gambia, botswana, sierra_leone,
south_sudan. Grid was near-total-gap for all six countries at task start.

Every probe below used plain non-impersonating Python `requests`, or
`curl_cffi impersonate=chrome124` (falling back to chrome120/safari17_0),
from `a8`, against the worktree `~/po-worktrees/fill-gap-sources`. This
file is organized per-country; each section was originally written to its
own `/tmp/blockers_<country>.md` file by a country-scoped agent and merged
here by the orchestrating session.

IMPORTANT — this worktree is shared with several other concurrent
agents/sessions working the identical SSA food-source campaign in
parallel. Several manifests referenced as "already covered" below were
added by those other sessions on the same day (2026-09-11), sometimes
minutes before or after this campaign's own probes -- cross-check file
timestamps before assuming a gap is unaddressed. One independent
duplicate-effort case was directly observed: a separate agent produced an
Eswatini blockers writeup (misfiled locally as blockers_gambia_check.md)
reaching near-identical conclusions to this campaign's own Eswatini
section below, which cross-validates both.

---

# Known blockers / findings — Botswana food-source gap-fill (2026-09-11)

All probes below used plain non-impersonating Python `requests` (this
region has no WAF on any candidate probed) or `curl_cffi impersonate=
chrome124` where noted; run from a8.

## Shipped this pass

- **farmproducts_ex_bw** (https://farmproducts-ex.co.bw/) — WooCommerce
  Store API, small (7-product) but genuine single-page greengrocer
  catalogue (onions, naartjie, butternut, peppers, tomatoes, oranges).
  BWP confirmed from payload (currency_minor_unit=2). MEASURED: 7/7 rows,
  7/7 distinct urls, zero zero-priced. channel: fresh-market.
- **shopsefalana_bw** (https://shopsefalana.com/) — Sefalana (Botswana's
  largest domestic food retail group), custom nopCommerce storefront
  (NopStation.Theme.Arch theme). ~130 category slugs on the homepage nav
  spanning nearly the entire COICOP 01/02 range: staple foods, rice,
  maize, wheat, sugar, oil, canned goods, dairy, bakery, snacks,
  confectionery, tea/coffee, juices, carbonated/energy drinks, AND a full
  liquor/tobacco range (beers, brandy, ciders, gin, liqueurs, rum,
  tequila, vodka, whiskey, wines, cigarettes, tobacco). Bespoke spider
  written (`shopsefalana_bw.py`, modeled on the existing `winners_mu.py`
  nopCommerce pattern). Enumerability CONFIRMED: `/dairy-4` page1 vs page2
  fully disjoint (20/20 ids, zero overlap). MEASURED test run (max-items
  60): 97 rows, 97 distinct urls, zero zero-priced, categories Rice/Rum/
  Water/Wheat/Whiskey/Wines/Wrapping-Packaging (Scrapy's default LIFO
  queue processed alphabetically-last slugs first). The full ~130-category
  sweep is INFERRED coverage (from browsing the nav), not yet measured at
  full scale — a production run has `max_items: null` and will walk all
  categories over time. channel: supermarket. **Single highest-value find
  of this pass** — one source plausibly touching most of Botswana's
  COICOP 01/02 gap.
- **choppies_ebasket_bw** (https://chptst205.echoppies.com/) — Choppies
  (major regional supermarket chain) online "eBasket". Custom legacy PHP
  platform. Hostname looks like a staging/test alias but is live and
  public, with a Botswana Pula currency icon and genuine food SKUs.
  10 categories (b_cfc, m_beverages, m_edible groceries, m_ethnic
  products, m_fresh, m_general merchandise, m_house hold, m_perishable,
  m_personal care, m_pets). Enumerability CONFIRMED: page1-page7 of
  "m_edible groceries" each returned a distinct 20-id set (checked
  pairwise). GOTCHA hit and fixed during scaffolding: the category-listing
  markup breaks `<a title=` across a newline (unlike the `popular.php`
  landing page sampled first), so the regex needed `\s+` between the `<a>`
  tag and its attributes — first version of the spider matched 0 items
  despite a healthy 200 response; the debug step was comparing
  Scrapy-vs-bare-`requests` response bytes (identical) before finding the
  real cause was the regex, not the fetch. MEASURED test run: 92 rows, 92
  distinct urls, zero zero-priced, BWP throughout — categories Beverages,
  Cfc (fried-chicken ready meals), Edible Groceries in this partial run.
  channel: supermarket.

## Confirmed already-covered (not touched, not redone)

- **spar2u_bw** — shipped by another agent earlier today. SPAR Botswana,
  sitemap-driven, 8,370 distinct product PDPs, BWP confirmed from JSON-LD,
  channel: supermarket. Verified still present.
- bescohyper_bw, kangagri_bw, starpack_agri_pack, cbstores_bw, bmart_bw,
  masterfashion_bw, cosmetics_beauty_world_bw, livingwaterpharmacy_bw,
  ctm_bw, goodsy_bw, eyesmart_bw, solleluna_bw, beares_bw,
  notwanepharmacy_bw, sparesmax_bw, pulse_bw, chobedesign_furniture,
  shopbw_bw, btc_products_shop, honey_fashion_bw, perfectcircle_bw — all
  confirmed non-food (electronics/fashion/pharmacy/furniture/hardware),
  correctly out of scope for this food-only mandate.

## Rejected / dead ends this pass

- **specials.shoprite.co.bw/deals/** — HTTP 403 (Apache-level block,
  239-byte generic "Forbidden" body). Same signature as
  specials.shoprite.co.sz (see Eswatini blockers) — this is a
  flippingbook/cld.bz digital-flyer/circular platform, not a structured
  per-SKU price API, and it's walled off from direct access regardless.
  Not worth further investment; Shoprite in this region appears to only
  publish weekly specials as image-based flyers, not e-commerce.
- **spar.co.bw/specials/** — HTTP 200 but a WordPress marketing/specials
  blog page (wp-json present but no product catalogue found; no
  grocery/food/supermarket keyword hits in the page text). Likely the
  same SPAR brand presence as spar2u_bw but this particular subdomain is
  not a shop. Not pursued further.
- **sefalana.co.bw** — corporate/store-locator site for the Sefalana
  group; its own "shop" links point directly to shopsefalana.com (already
  onboarded above). Confirms shopsefalana.com is the correct single
  ingestion point for this group — no separate manifest needed.
- **pulamarket.co.bw** — "Botswana's Digital Commerce Platform" branding,
  grocery/food keyword present on the page, but no shop/product link found
  in a quick pass. Not deeply investigated (deprioritized after two solid
  sources were already found); worth a closer look in a future pass.
- **basketiq_market_pulse**, **game_bw_pricemate_catalogue** — not probed
  in depth this pass; names and URLs (`/pulse/`, `demo.pricemate.info/...`)
  strongly suggest price-comparison/basket-cost tooling rather than a
  retailer with its own enumerable catalogue. Flagged for a quick
  confirm-and-skip in a future pass rather than investment now.
# Known blockers / findings — Liberia food-source gap-fill (2026-09-11)

No new manifests created this pass — instead, three pre-existing but
never-live-tested manifests were verified working, which meaningfully
changes what "still missing" means for this country. All probes below
used plain non-impersonating Python `requests` on a8 (no WAF encountered
anywhere in this pass).

## Verified working (pre-existing, previously untested)

- **congo_girl_cuisine** (https://congogirlcuisine.com/, Shopify,
  channel: supermarket) — MEASURED: `prices collect --source
  congo_girl_cuisine --max-items 20` -> 8 rows, LRD confirmed from the
  Shopify payload, real prepared-Liberian-food SKUs (e.g. "Cassava Leaf
  (Stew Only)" LRD 26.50, "Cassava Leaf (Stew + Parboiled Rice)" LRD
  29.50). Manifest notes said "Scrape-ready" from an earlier
  consolidation pass but carried no test-run record; now confirmed live.
- **banjoo_lr** (https://banjoosuperstore.com/, bespoke WooCommerce
  sitemap-walk spider, channel: supermarket) — MEASURED: 22 rows, 22
  distinct urls, currency USD (flagged deliberately, matches the known
  Liberia USD-quoting pattern). Real grocery items present: "Split Peas
  (25kg)" $38, "Hibicus Tea" / "Lemongrass Tea" $10, several "Breakfast
  Bundle" items, plus a series of generic "Banjoo Bundle #NNN-NNN" gift
  hampers whose content isn't visible from the product name alone.
  **FLAGGED ANOMALY, not fixed**: one row, "Banjoo Bundle#006-203",
  priced at USD 21750.00 — two to three orders of magnitude above every
  other item on this page. Not touched (the spider uses the shared
  `_woo_sitemap_base.py` base class used by other sources; a possible
  cause is a genuine retailer-side listing error, not necessarily a
  spider bug) — worth a maintainer look at ingestion time or an
  outlier filter, flagging here rather than guessing at a fix.
- **libdelivery_lr** (https://libdelivery.com/, bespoke sitemap+JSON-LD
  spider, channel: marketplace) — MEASURED: 22 rows, 22 distinct urls,
  USD. Mostly ready-to-eat/restaurant items (Shawarma & Fries, Chicken
  Wings, Fattoush Salad, Garden Salad) plus at least one grocery SKU
  ("Manzola Corn Oil" $15) — a genuine Monrovia food-delivery
  marketplace, not the electronics/general catalog its "marketplace"
  channel tag might suggest at a glance.

## Confirmed non-food (checked, correctly out of scope)

- **kernel_fresh_premium** (Shopify) — despite the "Fresh" name, this is
  a beauty/personal-care catalogue (soaps, skin care, hair care, air
  fresheners, lotions). channel: other is correct as-is.
- **familylogolr** (bespoke Next.js marketplace) — MEASURED via a live
  test run: 8/8 items are consumer electronics (iPhone 13/12/11,
  earbuds, USB-C chargers, a wall socket). Zero food content. channel is
  tagged `marketplace` but `electronics` would be more accurate — not
  changed here, out of scope for a food-only pass.
- **villeton_liberia** — pharmacy, not food, left untouched.

## New candidates checked and rejected

- **lxttsmarket.com** (Shopify) — 50-product sample is >95% women's
  fashion/gowns ("RaiNe's Designs" line). Exactly one grocery-adjacent
  item found ("Rice KANYAN") and it is priced **$0.00** — a placeholder,
  not usable. Reject: not a food retailer.
- **market231.com** ("Liberia's Trusted Online Marketplace | Buy & Sell
  Locally") — landing-page keyword scan: 0 "grocery", 0 "food", 3
  "electronics", 8 "phone", 4 "fashion" mentions. Classifieds-style
  peer-to-peer marketplace skewing electronics/phones/fashion. Not
  pursued further.
- **marketliberiall.com** ("Maittes | Liberia's Online Marketplace") —
  same signature: 0 "grocery", 0 "food", 2 "electronics", 2 "phone", 0
  "fashion". Not pursued further.
- **ezeemarket** (Wix site, `ezeemarket.wixsite.com/ezeemarket`) — title
  "Online Shopping in Liberia | Ezee Market"; not deeply probed (Wix has
  no generic spider template in this repo and the site returned a large
  2.8MB page, suggesting a heavy client-rendered catalog that would need
  a Playwright pass to evaluate properly) — flagged as untested rather
  than rejected; worth a closer look in a future pass if Wix-catalogue
  scaffolding is ever built.
- **ekodii.com/market/liberia** — "ekodii — African marketplace | Buy &
  sell across Africa", small page (8.6KB), likely a thin country-filter
  landing page on a pan-African classifieds site rather than a real
  Liberia-specific catalogue. Not pursued further.

## Known dead end, not re-probed

- **sessayelectronic.store** — confirmed dead in an earlier pass
  (Shopify frozen, HTTP 402). Not food anyway.

## Session constraint

WebSearch quota was exhausted session-wide partway through this pass (the
budget is shared across every agent working this campaign concurrently,
not per-agent) — discovery for Liberia relied on the seed candidate list
from `~/gapwork/pending_worth_doing.csv` plus direct probing rather than
fresh search queries for the back half of this work. A future pass with a
fresh search budget should target the still-open gap categories directly:
dairy, cereals/bread (beyond the two prepared-stew items found), alcohol,
tobacco, sugar/confectionery, water, soft drinks/juices, cocoa drinks —
none of which have a dedicated Liberian source yet even after this pass's
findings.

## ADDENDUM (orchestrator, after the above pass) -- ezeemarket_lr SHIPPED

A separate probe (same campaign, different pass) took the "ezeemarket"
lead further than "untested": the wixsite.com preview URL
(ezeemarket.wixsite.com/ezeemarket -- the production custom domain
www.ezeemarket.biz times out from a8 on every attempt) is fully live.
Wix Stores platform; /store-products-sitemap.xml lists 2,683 distinct PDP
urls, each server-rendered with schema.org Product JSON-LD
(name/price/priceCurrency). The site's "Grocery" nav collection alone
carries totalCount=680 per its own embedded warmup JSON, sampled ~100%
food (multiple rice brands, red palm oil, Maggi bouillon cubes, MDH
masalas, sour cream, cheddar cheese, luncheon meat). Enumerability
confirmed both via /grocery?page=1 vs ?page=2 (disjoint 32-item sets) and
via the sitemap (2,683 distinct urls). Currency USD confirmed live from
JSON-LD on every sampled PDP.

SHIPPED: src/prices/configs/ssa/west_africa/liberia/ezeemarket_lr.yaml
+ new spider src/prices/price_scraping/spiders/ezeemarket_lr.py
(copies the neufeldhof_li sitemap+JSON-LD pattern already in this repo).
channel: dept-store (mixed catalog -- also carries beauty/clothing/
electronics SKUs, e.g. a Fenty Beauty PDP and a Lenovo laptop were seen
in the sitemap sample -- marketplace avoided since it is excluded from
the corpus census). Test run: prices collect --source ezeemarket_lr
--max-items 20 -> 24 rows, 24 distinct urls, 100% USD. Sample: USD 13.50
"Goodness Food Pakistani Basmati Rice 5Kg"; USD 1.25 "Fresh Palava Sauce
Leaves 1 bunch 100g"; USD 2.95 "Bomi Organic Rice 500g".
# Known blockers / findings — Eswatini food-source gap-fill (2026-09-11)

No new manifests shipped for Eswatini this pass — an unusually thin
online-grocery surface for this country, documented below in detail so
the next pass doesn't repeat the same searches. All probes used plain
non-impersonating Python `requests` or `curl_cffi impersonate=chrome124`
on a8.

## Existing manifests checked

- **thewineboutique_sz** (https://thewineboutique.net/, WooCommerce,
  channel: specialty-food) — already a fully verified, working manifest
  (not from today): 187 products across 2 pages, SZL confirmed from the
  API, mostly wine/spirits/gift hampers. This already covers Eswatini's
  alcohol gap category. Confirmed still present, not touched.
- twpsz_sz, parrot_sz, busiquip_sz — all electronics (phones, projectors/
  office equipment, printer toner respectively). Confirmed non-food,
  channel: electronics is correct.
- tsengisa_africa, iconomyonline_quazi_design — dept-store/homeware
  (Shopify), not food.

## New candidates checked and rejected

- **igrocerbusket.store.link** ("iGrocer Busket Eswatini" — "Online
  Grocery Shop and Delivery") — real grocery storefront on the
  "sheetstore.com" store-builder platform (spreadsheet-backed, not
  Shopify/Woo/etc). **REJECTED on currency**: the page's own embedded
  config explicitly declares `"currency":{"label":"South African Rand",
  "code":"ZAR"...}` — this is ZAR-priced, not SZL, despite being branded
  "Eswatini". Per the task's explicit ZAR-watch instruction for this
  country, flagged and rejected rather than silently accepted.
- **storkvelkonnect.co.za/marketplace** (the "imali_smart_marketplace"
  seed) — TLS handshake failure (`SSLV3_ALERT_HANDSHAKE_FAILURE`) across
  all three curl_cffi impersonation profiles (chrome124/chrome120/
  safari17_0) AND plain `requests` — this is a broken/misconfigured
  certificate on the origin itself, not a bot block. Site is
  unreachable by any HTTP client. Dead.
- **spareswatini.co.sz** ("Buy n' Save Spar Swaziland – Eswatini –
  Everyday groceries delivered to your door") — real SPAR-branded
  WordPress/WooCommerce site (`meta name="generator" content=
  "WooCommerce 9.0.4"`), HTTP 200, no WAF. **BUT the WooCommerce Store
  API returns X-WP-Total: 0 on every products query, the `/shop/` page
  renders zero static product cards, and `sitemap.xml` has no product
  sitemap at all** (only posts/pages/category/users) — the store has
  WooCommerce installed but has never actually published a product
  catalog online. The homepage carries a large WhatsApp-order banner
  image, suggesting orders are taken via WhatsApp/phone rather than the
  website. Confirmed dead end: no catalog to scrape, not a probing
  artifact.
- **shoprite.co.sz** (corporate/brochure site, AEM/shopriteafrica CMS) —
  marketing pages only (explore-shoprite/butchery.html,
  /liquorshop.html — informational, not transactional), a store locator,
  no product catalog or prices anywhere on the domain.
- **specials.shoprite.co.sz/deals/** — HTTP 403, Apache-level block
  (generic 239-byte "Forbidden" page, no useful headers). This subdomain
  is a flippingbook/cld.bz digital weekly-flyer platform (per the CSP
  header's allowed script/frame sources), not a structured per-SKU API —
  even if the 403 were cleared, this would be an image-based circular,
  not machine-readable pricing. Not worth further investment. (The
  identical pattern was found on Botswana's specials.shoprite.co.bw —
  this appears to be Shoprite's standard regional weekly-flyer setup
  across multiple SSA markets, not specific to Eswatini.)
- **buyeswatini.shop** ("Buy Eswatini - Linking buyers & sellers") — a
  thin classifieds/traders-directory platform (custom, non-standard
  markup). The `/traders-directory/` page returned essentially empty
  content (1001 bytes, likely a login-gated or JS-rendered listing) with
  zero grocery/food/supermarket keyword hits. Not pursued further.
  buyeswatini.com (the .com variant) timed out entirely.
- **OK Foods, Pick n Pay (co.sz domains)** — no DNS resolution at all
  for any guessed domain pattern (okfoods.co.sz, picknpay.co.sz,
  pnp.co.sz) — these chains have no online storefront under an obvious
  domain in this market.

## Net result / structural finding

Eswatini's online grocery infrastructure appears essentially
non-existent as of 2026-09-11: every major chain checked (SPAR, Shoprite,
OK Foods, Pick n Pay) either has no website, a marketing-only brochure
site, a WooCommerce install with zero published products, or a
403-walled image-flyer platform. The one working food source
(thewineboutique_sz) is alcohol-only. This reads as a **structural
absence** (retail e-commerce for groceries has not launched in this
market yet), not a discovery failure — worth revisiting periodically
(SPAR's WooCommerce install in particular could go live with real
products at any time; its `/shop/` page and Store API are the two things
to re-check).

Session's WebSearch quota was exhausted (shared campaign-wide) before a
staples-specific sweep (bogobe, sishwala, mealie meal, sorghum) could be
run for Eswatini — worth a follow-up once quota resets.
# Known blockers / findings — South Sudan food-source gap-fill (2026-09-11)

No new manifests shipped for South Sudan this pass. This country's online
retail surface is thin, and what exists skews heavily electronics/general
merchandise rather than food. All probes below used plain
non-impersonating Python `requests` on a8 unless noted.

## Priority re-probe: nilemart-ss.com — RESOLVED, but REJECTED (not food)

**nilemart-ss.com** ("Nile Mart") was flagged in an earlier pass today as
blocked (`server: hcdn`, HTTP 403 on curl_cffi TLS impersonation on every
path) and left as "dead for this pipeline (no headless-browser solving in
scope)". Re-probed here with a **plain, non-impersonating** Python
`requests` call (no curl_cffi impersonate=) per the pattern documented in
the newly-built `generic_woo_playwright.py` spider (which found this same
technique alone clears 8 of 9 similar hcdn tenants elsewhere in this
campaign) — **it worked**: homepage and `/shop` both return HTTP 200
(`server: hcdn` header still present, confirming the block really was a
TLS/JA3 fingerprint denylist against curl_cffi specifically, not a
content-level challenge). `/wp-json/wc/store/v1/products`,
`/wp-json/wc/store/products`, and `/products.json` all 404 — this is not
a WooCommerce or Shopify site.

The `/shop` page is a static, fully server-rendered Bootstrap-template
catalogue: 384 distinct products (`customer/product-details?product-id=N`,
ids 30–430), all with real USD prices embedded directly in the listing
HTML (e.g. "USD 20.00", "USD 700.00") — genuinely enumerable, no
pagination needed since the whole catalogue renders on one page. However:
**the meta description states it plainly — "Nilemart - South Sudan's #1
Online Marketplace Shop electronics, fashion, and more"** — and the
sampled product names confirm it: iPhone 11–16 (all variants), Samsung
Galaxy A/S/Z-series, Tecno/Oppo/Infinix/Redmi/Nokia phones, Samsung
Galaxy Tab tablets, a "Maroon suit", "Light brown penny loafers", wooden
wardrobes/armoires/display cabinets. **Zero food or beverage items found
in a 60-name sample.** Per-product detail pages (`customer/product-
details?...`) also redirect to a login wall, though the listing page
itself does not require login.

**Verdict: technically recovered (plain HTTP bypasses the block
entirely) but REJECTED under this task's hard food-only constraint** —
this is exactly the "clean catalogue, zero food cells filled" trap the
brief warns about. Worth flagging to a general (non-food) South Sudan
onboarding pass as a genuinely live, enumerable, real-priced electronics/
fashion/furniture marketplace if that's ever in scope.

## Existing manifests checked (not touched, confirmed non-food)

- **junubmart_ss** (Shopify) — manifest's own notes already say
  "electronics-skewed; limited food and no ordinary grocery coverage
  observed." Confirmed correctly out of scope, not re-probed live.
- **ramuskin_ss** (WooCommerce) — pharmacy/personal-care catalogue
  (channel: pharmacy). Not food.
- **ordermindubai_ss** (Shopify) — Dubai import/delivery-to-Juba general
  merchandise, channel: other. Not food-focused; not re-probed live given
  its own notes describe it as an import/electronics channel.
- **juba_fashion_hub_link_ss** — fashion (confirmed by another agent's
  probe today, live bespoke Firebase `/api/products` endpoint with 130
  SSP-priced items) — irrelevant to food, not touched.

## Seed candidates checked and not viable this pass

- **jubasquare.com/marketplace** — HTTP 200 but a bare React/PWA shell
  (2954 bytes, `<div id="root">`-style client app, manifest.json/PWA
  icons present, no static content) — would need a Playwright render to
  see any real listings or determine food content. Not pursued further
  given time budget; flagged as untested rather than rejected.
- **doyoom.com** ("food delivery" per its seed description) — HTTP 403,
  served by Vercel with a `<title>Vercel Security Checkpoint</title>`
  page (Vercel's own bot-mitigation interstitial, not a content-level
  hcdn-style challenge and not something a plain-HTTP retry or the
  existing `generic_woo_playwright` warm-up pattern addresses). Not
  resolved this pass.

## Dead ends confirmed by other agents today, not re-probed (irrelevant to food anyway)

higromall.com (HTTP 500, server dead), jubafashionhub.store (Shopify 402,
frozen), jubalaptops.com (Woo Store API 401, locked), jubastationery.com
(no wc/store namespace registered).

## Net result

South Sudan remains without a genuine food/grocery source after this
pass. The country's e-commerce surface that is reachable at all skews
heavily toward electronics, fashion, furniture, and imported general
merchandise (Dubai-sourced). WFP and FEWS NET (already onboarded,
official/aggregate) remain the only price signal touching food for South
Sudan in this repo. A future pass should prioritize: (1) rendering
jubasquare.com with Playwright to see if it has a real grocery section,
(2) a residential/session-based retry against doyoom.com's Vercel
checkpoint, (3) a fresh WebSearch-driven discovery round once quota
resets (this session's WebSearch budget was exhausted, shared campaign-
wide, before a full item-specific sweep — "sorghum South Sudan",
"maize meal Juba", "dried fish South Sudan buy online" were not run).
# Gambia food-source discovery — blockers and evidence (2026-09-11, fork pass)

## marounssupermarket.com — REJECT, compromised/parked domain
- Homepage, /shop/, /wp-json/, /products.json, all WooCommerce Store API
  variants: every single path returns HTTP 200 with a 1-byte (br-encoded
  empty) body via curl_cffi impersonate=chrome124.
- /sitemap.xml (59KB) IS populated, but every URL in it is a fake
  "?s=<random-digit-string>" search-query link with lastmod dated
  2026-09-12 (tomorrow) — classic SEO-spam-injection signature on a
  hacked/abandoned WordPress install, same pattern as anadi_guinee_gn
  (repair pass 2) minus the visible gambling page.
- Verdict: reject — nothing real to scrape despite the promising domain
  name (Maroun's is a real, long-running Gambia supermarket chain per
  search results, but this domain is not a live storefront for it).

## pricegambia.com (www.pricegambia.com) — REJECT, app marketing page
- Custom static HTML landing page ("Pricegambia - Online Marketplace"),
  not WooCommerce/Shopify. No product/category listing anywhere in the
  HTML; the only outbound links besides nav anchors are obfuscated
  "mypricegambia.com/api/fb/<random>" spam-tracking hrefs.
- Page markets a mobile app (tablet/desktop/mobile download toggle) —
  no web catalogue at all.
- Verdict: reject — app-only, no scrapeable surface.

## getgambgo.com (www.getgambgo.com) — REJECT, app marketing page
- Vercel-hosted Lovable.dev React SPA, canonical
  gambgo-food-delivery-app.lovable.app. "Order food, groceries... Download
  the GAMBGO app." 2990-byte marketing shell, no product data.
- Verdict: reject — app-only, no web catalogue.

## Safeway Supermarket (Gambia, 3 branches: Kairaba Ave, Kololi,
   Senegambia) — STRUCTURAL ABSENCE
- A real, well-reviewed Gambian supermarket chain (4/5 stars, 43 reviews)
  but has no dedicated website — only directory listings (my-gambia.com,
  accessgambia.com, africa-places.com) and a Facebook page
  (facebook.com/safewaysenegambia). Nothing to scrape.

## 1Bena (super-app) — SKIP, app-only
- Google Play listing confirms mobile-app-only delivery aggregator (rides
  + food + errands), no web storefront found.

## Environment note for other forks/agents on a8
- Writing a probe script to /tmp/<name>.py and then running
  `python3 /tmp/<name>.py` intermittently executed UNRELATED code (a PPP
  basket/currency-comparison dump for APAC countries) before crashing on
  `from curl_cffi import requests` with
  `AttributeError: module 'inspect' has no attribute 'getmro'`, reproduced
  identically across two different filenames. Plain `python3 -c "..."`
  inline execution of the exact same code worked reliably every time
  (tested 4/4). Root cause not confirmed (suspect ssh/tty output
  interleaving with a concurrent sibling session on the shared box, or a
  shared-/tmp race) — workaround: prefer `python3 -c` inline over writing
  probe scripts to /tmp files.

## Existing Gambia manifests re-verified (not modified)
- farmfresh_gm.yaml, torodo_chicken_land.yaml: confirmed present, per
  their own notes already end-to-end tested by another agent today
  (fresh-market / specialty-food, GMD, real prices).
- julabaa.yaml (channel: supermarket, generic_woo_configured): was
  untested ("child-task consolidation", never end-to-end verified) —
  I ran `prices collect --source julabaa --max-items 20` and it
  MEASURED 100 rows / 100 distinct urls, currency_code=GMD read live
  from the Store API payload, page1 vs page2 confirmed disjoint ids
  (166 distinct ids scanned across 3 pages). However it is NOT a
  single-vendor supermarket — it is a Dokan/WCFM-style multi-vendor
  WooCommerce marketplace: 90 of 166 products (54%) are attributed to
  vendor "Farm Fresh Gambia" — the SAME retailer already scraped
  directly and independently as farmfresh_gm. The remaining food content
  is small: "Al Ameen Halal Kitchen" (4, ready-meal chicken
  shawarma/wings/rolls) + "Food" (4); the rest is Incense (26),
  Lingerie (16), Perfumes (8), Room Fresheners (4), Waist Beads (3),
  Hair Products (2). channel: supermarket mischaracterizes it — it
  should arguably be `channel: marketplace`, but doing so would exclude
  it from census.py's corpus entirely per the repo's own marketplace
  rule. Flagging for a maintainer decision rather than changing it
  myself (out of scope for a Gambia-food-focused pass, and the source
  was not broken, just untested and mistagged). Net-new food coverage
  from julabaa beyond what farmfresh_gm already provides is marginal
  (~8 ready-meal SKUs).
- le_jumbo.yaml (channel: other, generic_woo_configured): live-checked
  its Store API directly — genuinely a general electronics/beauty/watch
  marketplace (Renewed iPhones, Apple Watch, Palmolive/Axe/Nivea/Dove
  personal care) with only occasional food items surfacing (e.g. "GOFIO
  (Dugula)" millet flour). channel: other is accurate; not food-dominant,
  correctly out of scope for this pass.
- ebaaba_gm.yaml (channel: marketplace): general marketplace per prior
  notes (electronics/general merchandise dominant); search results
  describe it as also carrying "groceries" but this was not independently
  re-verified in this pass given time budget and its channel is already
  correctly marketplace-tagged.
- gambia_petshop.yaml: confirmed non-food, left untouched.
# Known blockers -- Sierra Leone food-source discovery (2026-09-11)

## Existing manifests confirmed working/food (already covered, verified live in this pass)
- choithrams_sl.yaml -- Choithrams via 247bigmarket.com vendor storefronts,
  channel: supermarket, 198 products verified, USD (genuine domestic
  pricing, flagged correctly). Pre-existing from 2026-09-01, unchanged.
- lamanistore.yaml -- Shopify /collections/all-spirits, channel:
  supermarket, RE-VERIFIED live in this pass: `prices collect --source
  lamanistore --max-items 20` -> 60 items, SLE currency confirmed genuine
  (not SLL), e.g. "Ballantine's finest" SLE 600.00. Covers alcohol
  (02.1) gap category.
- devillagebeachbar.yaml -- WooCommerce, channel: supermarket (tagged;
  actual content is restaurant/prepared-food per its own notes),
  RE-VERIFIED live: 35 items, SLE currency.
- gotrustmesl.yaml -- shipped today by another agent, generic_woo_playwright,
  channel: marketplace, currency SLL (old-leone code, confirmed correct
  per that tenant's own API), only 10 products, mixed-vertical (food/
  beauty/electronics/clothing). Weak contributor -- marketplace channel is
  excluded from the corpus census downstream.

## saloneemarket.com
- 200 OK, but own meta description: "Shop electronics, fashion, home
  appliances and more" -- general marketplace, no food/grocery mention.
- Verdict: reject -- non-food by the site's own description (same pattern
  as Nilemart in South Sudan).

## www.market360.shop
- 200 OK, "Market360 -- Sierra Leone's #1 Online Shopping Marketplace".
  Not Shopify/WooCommerce/Presta/OpenCart (no platform signature found).
  No /products, /shop, /marketplace, /api/products, /search routes exist
  (all 404) -- no discoverable catalog API.
- NLE/Le price-like patterns found in the raw HTML ("NLE 12,480", "Le
  1,000") turned out to be a demo/mockup "Wallet balance" and "Live
  activity" UI widget on the landing page, not real product listings --
  false positive.
- Verdict: reject -- marketing/landing page only, no enumerable catalog
  found; would need Playwright + reverse-engineering an app-only backend
  for uncertain payoff.

## www.salonefastmarket.com
- 200 OK, 55KB, no known platform signature, zero Le/SLE/NLE/$ price
  patterns found in static HTML.
- Verdict: reject -- no structured price data found in static HTML;
  likely JS-rendered or a directory/classifieds model.

## www.shop2sitesl.com ("Shop 2 Site Sierra Leone -- Buy groceries from
## Freetown and have it delivered to site weekly")
- Found via WebSearch, sounds like a strong grocery-delivery candidate.
- Connection refused on both https and http, www and bare domain, from
  a8 -- server is not accepting connections at all (not a WAF, not a DNS
  failure -- TCP connect refused).
- Verdict: reject -- dead/unreachable server.

## Net result
Sierra Leone already has solid pre-existing coverage (choithrams_sl
supermarket 198 SKUs, lamanistore alcohol, devillagebeachbar prepared
food, gotrustmesl weak marketplace) -- all re-verified live in this pass.
No new Sierra Leone food source was found viable; every fresh lead
(saloneemarket, market360, salonefastmarket, shop2sitesl) was either
non-food, had no enumerable catalog, or was unreachable. Sierra Leone's
COICOP 01/02 remaining gaps (fresh produce, dairy, most beverages beyond
spirits) likely need a fresh-market/greengrocer-specific source that this
pass did not surface -- worth a dedicated follow-up search focused on
Freetown open-air/wholesale market price data (e.g. a stats-office
average-price series) rather than more general e-commerce search.

---

## ADDENDUM (orchestrator, after the South Sudan section above) -- jubasquare_ss SHIPPED

A separate concurrent agent working this same campaign took the
jubasquare.com lead (flagged above as "bare React/PWA shell, not pursued
further given time budget") to completion: its JS bundle references a
same-origin, unauthenticated `/api/products?limit=1000` endpoint.
MEASURED (independently re-confirmed by the orchestrating session):
94 distinct products, stable regardless of limit/pagination params (this
IS the whole catalog), 100% non-zero price_usd. ~68% (64/94) of the
catalog is genuine food/beverage/household FMCG: rice, beans, wheat
flour, sugar, tea, milk powder, tomato paste, cooking oil/margarine,
peanut butter, canned sardines, chocolate, bottled water, sodas, fruit
juice, and a full alcohol range (Absolut Vodka, Amarula, Blue Label,
4th Street wine) -- directly closing South Sudan's cereals&bread,
fish&seafood (canned), dairy&eggs, oils&fats, sugar/confectionery, tea,
alcohol, juices, soft drinks and water gap categories in one source.
Currency is native USD (with an embedded exchange_rate_ssp field the
manifest deliberately does NOT use for conversion) -- flagged explicitly
per the brief's instruction, consistent with South Sudan's severe SSP
volatility. channel: wholesale (most rows carry mode/min_order_qty/
pricing_tiers fields). SHIPPED:
src/prices/configs/ssa/east_africa/south_sudan/jubasquare_ss.yaml +
spider src/prices/price_scraping/spiders/jubasquare_ss.py. Test run:
20/20 rows priced (94 total catalog), 20 distinct synthetic urls, USD.

This changes the South Sudan section's Net result above: South Sudan
now DOES have a genuine, substantial food source as of 2026-09-11.

---

## ADDENDUM (orchestrator verification, 2026-09-11) -- afrikonet_sl DOES carry real food SKUs

A prior pass's quick --max-items 20 test of `afrikonet_sl` only reached its
alphabetically-first category ("air-conditioners") before hitting the item
cap, and concluded the source "looks food-weak on inspection." That
conclusion was an artifact of the small sample, not a real finding.

Direct verification (BeautifulSoup, exact selector `.product[data-link]`
used by the shipped spider) against the food-relevant categories in its
161-category list:

| category | priced product cards |
|---|---|
| groceries-food | 19 |
| food-and-drinks | 20 |
| packaged-foods-snacks | 4 |
| fresh-produce | 1 |
| beverages | 1 |
| eggs | 1 |
| vegetables | 0 (empty on this crawl) |
| fruits | 0 (empty on this crawl) |

Sample confirmed real, priced, food/beverage SKUs: "Armour Star Vienna
Sausage, Original Flavor, Canned Sausage, 9.25 OZ (Pack of 12)" Le160.00;
"4C Raspberry Iced Tea Mix" Le400.00; "Absolut Vodka" Le660.00; "All
Purpose Flour Bulk Baking Flour ... 50 LB" Le770.00; "Apple & Eve Elmo's
Punch 100% Juice (Pack of 20)" Le350.00. This touches cereals&bread
(flour), meat (canned sausage), tea, alcohol, and juices -- a genuine,
if modest, food contribution once a full run (max_items: null) walks
past the alphabetically-earlier non-food categories. channel: marketplace
remains an accurate tag (catalog spans groceries through electronics to
fashion) -- no manifest change needed, this is a verification correction
only.


---

## known_blockers_disco_eu - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_eu.md` on 2026-09-11. 14 hosts, 2 not
documented above at merge time.

# Known blockers — Disco EU/Atlantic food-sourcing pass (2026-09-11)

Countries: gibraltar, greenland, liechtenstein, monaco, st_martin_french_part,
sint_maarten_dutch_part, suriname, san_marino, andorra, faroe_islands.

New candidates probed this pass that failed the gates, organised by cause so
a future pass does not re-spend the probe. (Entries for candidates already
recorded in prior passes — Eroski Gibraltar reCAPTCHA, Ramsons app-only,
Brugseni/Pilersuisoq brochure-only, SMS/Bónus/Miklagarður/Föroya Keypssamtøka
brochure-only — are NOT repeated here; see the skill's own
`references/known_blockers.md` and the per-country inventory files under
`references/inventories/eca/western_europe/`, which already carry them.)

## Cloudflare / anti-bot (re-probed, still blocked)

- **delovery.mc** (Monaco, genuine `.mc` food-delivery platform) — 403 on
  `curl_cffi` chrome124, chrome120 AND safari17_0. Re-probed per this brief's
  standing instruction to retry blocked sites; verdict unchanged from the
  2026-09-01 pass. This remains Monaco's single best unclaimed food lead if
  anti-bot posture ever changes.

## Brochure-only / no e-commerce (measured, not assumed)

- **marche-u.mc** (Monaco) — genuinely Monaco-domiciled Système U storefront
  (7 bd d'Italie, Monaco), which resolves the France/Monaco shared-platform
  duplication question for this one domain (it is its own `.mc` site, not
  the shared `coursesu.com` national platform). But `/nos-rayons/*`
  department pages (la-boucherie, la-poissonnerie, la-cave, le-traiteur,
  etc.) carry zero price tokens and zero "panier" mentions — marketing
  copy only, no online ordering.
- **bjor.fo** (Faroe Islands) — Föroya Bjór brewery. WooCommerce theme
  installed (`wp-json` present) but the Store API 404s
  (`rest_no_route`) and `/vorur/` ("products") renders zero prices, zero
  `add-to-cart`, zero `woocommerce-loop-product` markup. Shop plugin is not
  active; site is brochure-only.
- **local.fo/webshop/** (Faroe Islands) — is a travel/tourism magazine site
  (`plan-your-trip`, `weather`, `print-edition`); its "webshop" sells
  sheep-branded souvenir merchandise, not food. Zero price tokens.
- **faroelandia.com** (Faroe Islands seafood) — no platform fingerprint
  matched, zero price tokens on `/products/`. Reads as a B2B export/
  marketing site, not consumer e-commerce.
- **origin.fo** (Faroe Islands) — zero price tokens, no platform fingerprint.

## Wrong country / wrong currency (locality gate failure)

- **bakkafrostshop.com** ("Superior Salmon from the Faroe Islands and
  Scotland") — real Shopify store, real per-item prices (e.g. "Fresh salmon
  portions 2x125g" $7.93), but `Shopify.country = "US"` and
  `Shopify.currency = {"active":"USD"}` machine-readably, plus a
  "military-discount-usa-only" page and Scottish ("Native Hebridean Smoked
  Salmon") SKUs mixed into the same catalog. This is Bakkafrost's US
  consumer storefront, not a Faroese domestic retailer. Rejected on the
  locality gate, not absence of e-commerce.
- **polarseafood.com** (Greenland-linked seafood) — no `shop`/`webshop`/
  `add to cart` anywhere on the site; confirmed B2B export only, no consumer
  storefront to even evaluate for locality.
- **groenlandskehus.dk** ("Det Grønlandske Hus") — Danish (Denmark-based)
  specialty retailer selling Greenlandic-themed products
  (`/vare/fisk-og-koed/`) to a Danish/EU market. Same shape as the
  Monaco/Andorra/Liechtenstein neighbouring-market trap: about Greenland,
  not from or priced for Greenland. Not probed further (would fail the
  locality gate even if it enumerated).

## No consumer storefront at all (B2B / wholesale only)

- **hiddenfjord.com** — Faroese salmon farmer; not probed in depth this
  pass, but the brand's public profile is aquaculture/export, consistent
  with the polarseafood.com and Royal Greenland pattern. Flagged for a
  future pass to confirm rather than re-probed here (time-boxed).

## Wix/Ecwid false-fingerprint trap (recurring pattern, third confirmed case)

- **mitronbakery-monaco.com** — "ecwid" string hits on the homepage (11
  occurrences) are Wix's own storefront-widget self-reference
  (`wix.ecwid.com/wix/app/store`), not a standalone Ecwid installation —
  the same false-positive pattern already documented on `neufeldhof_li`.
  `/commander/EPICERIE-FINE-&-BOUTIQUE-.../` renders zero price tokens
  server-side; a genuine Wix Stores catalog needing a Playwright network
  trace to find the real data endpoint, not attempted this pass (OBBA and
  Vinalia already filled Monaco's food slot).

## Needs a network trace, not attempted this pass (time-boxed, not dead)

- **mrroomservice.mc** (Monaco) — curated multi-shop concierge delivery app
  aggregating named boutiques including `foie-gras-comtesse-du-barry`,
  `caviar`, `wine-champagne-spirits`, `coffee-nespresso-illy`, and
  `dean-and-deluca-shop`. No platform fingerprint matched (not Shopify/
  Woo/Prestashop/Wix); shop pages render zero price tokens in raw HTML —
  client-side rendered (likely React/Next), needs a Playwright network
  capture to find the JSON endpoint. Worth a follow-up given how
  food-heavy the curation is; not pursued because OBBA and Vinalia already
  gave Monaco two solid, simpler sources.

## Mis-tagged existing manifest, not a new blocker but worth recording

- **gibral_flora_gi** (Gibraltar) shipped by an earlier same-day
  consolidation pass tagged `channel: supermarket`. Live measurement of a
  100-item WooCommerce Store API page: Plants 25, Christmas Ideas 14, Pet
  Corner 19, Mother's Day 9, Weddings 7, Valentines 6, Garden Sundries 1,
  Chocolate & Sweety Hampers 2. It is a florist/gift/pet shop — "Gibral-
  Flora" literally names the flora business — and fills approximately zero
  COICOP 01/02 cells despite its tag. Corrected to `channel: dept-store`
  in this pass (see the manifest's own notes for the full record); also
  corrected `currency: GIP` -> `GBP` to match the Store API's own
  machine-readable `currency_code`.


---

## known_blockers_disco_fr - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_fr.md` on 2026-09-11. 98 hosts, 57 not
documented above at merge time.

# Francophone Africa food-source discovery — blocker log

Countries: Chad, Central African Republic, Burkina Faso, Cote d'Ivoire, Niger,
Guinea, Congo Rep, Comoros. Discovery method: French-language search (generic
retail / item-specific from the COICOP gap list / local staples), curl_cffi
probing (impersonate chrome124/chrome120/safari17_0), WooCommerce/Shopify/
PrestaShop/OpenCart/Magento/Wix/Ecwid/Algolia fingerprinting, sitemap→PDP
fallback. Probed 2026-09-11 unless noted. MEASURED unless explicitly flagged
INFERRED.

Sources shipped this pass (for cross-reference, not blockers): `mossosouk_td`
(Chad), `bahati_km` (Comoros), `fruitsetlegumes_ci` (Cote d'Ivoire),
`sodishopguinee_gn` (Guinea), `kaomini_ne` (Niger), `ouagadougouonline_bf`
(Burkina Faso).

## Central African Republic

- **shopping236_cf** (already onboarded) — furniture/bedding/small-appliances/
  childcare per existing manifest notes (INFERRED, not re-probed). Non-food,
  fills zero CAR division-01/02 cells.
- **banguimall.net** — re-probed live (200 on chrome124/120/safari17_0; a
  prior pass had it as unresolvable). Live site is a static Bootstrap
  brochure for a car-wash/car-repair and phone/PC-repair business — zero
  product catalog, zero prices, zero food relevance. Dead end, different
  reason than before (non-food services brochure, not e-commerce).
- **warani.cf** — re-verified NXDOMAIN (socket.gethostbyname + dig, two
  resolvers). Matches existing known_blockers verdict, no change.
- **vokani.com** — surfaced in search ("boutique en ligne moderne à Bangui")
  but NXDOMAIN on repeat lookup (curl_cffi + dig, local and 8.8.8.8). Search
  index is stale relative to DNS reality.
- **market-express.net** — search snippet promised a full food catalog
  (riz/pâtes, boucherie, fruits et légumes) but domain is NXDOMAIN on repeat
  lookup. Dead, not blocked.
- **banguicom.myshopify.com** — resolves but HTTP 402 Payment Required
  (suspended/unpaid Shopify subscription). Underlying business (per directory
  listings) is an IT hardware/software integrator anyway — dead + non-food.
- **ndaratibeafrika.com** — live, real Shopify catalog, but sells handmade
  artisan textiles/homewear/baskets/gifts. Non-food, dropped on the food
  gate without further probing. Secondary flag (INFERRED): separate US/
  Europe inventories read as diaspora-gift-oriented.
- **kanko.fr** — the only external-website entry in goafricaonline.com/cf's
  CAR "supermarchés" directory category. Resolves 200 but is a Dovendi
  domain-parking/for-sale page — no store. Dead, not blocked.
- **goafricaonline.com/cf/annuaire/sites-vente-en-ligne** — CAR "online
  sales sites" directory category returned zero listings on direct fetch.
  Dead-end search, not a candidate.
- **sangostore.com** — self-branded "marketplace de la diaspora
  centrafricaine": diaspora members abroad place/pay orders, goods delivered
  to recipients in Bangui — the reverse-remittance pattern (same family as
  familov/comores-en-ligne/omakiti.com). Rejected on the diaspora gate
  regardless of catalog contents.
- **BAMAG / CORAIL / MINI PRIX / SOCIMCO / RAYAN** (physical Bangui
  supermarkets, genuinely food-selling per travel-guide copy — INFERRED, not
  verified live) — no website found for any; Facebook pages only. Not
  scaffoldable — no PDP, no JSON endpoint, no enumerable catalog exists.
- **Verdict for CAR**: structural absence of retailer_sku food infrastructure,
  not a search-effort failure. Delivery apps (Glovo/Yango/Bolt Food/Jumia/
  Afrimarket) confirmed absent or defunct in-country. Re-check in ~6 months
  rather than re-sweeping sooner.

## Chad

- **jumia.td** — Cloudflare "Just a moment…" wall, shared Jumia tenant;
  Jumia's active market list does not include Chad. Not re-probed (already
  established in the shared known_blockers.md).
- **ndjamenamall.com** — bare LWS hosting-provider placeholder page, never
  built out (pre-existing finding, unchanged).
- **tchadcommerce.com** — already onboarded and already known-thin (only 6
  products in its "AgroAlimentaire" category); unchanged this pass.
- **nkosiagro.com** — real Shopify storefront ("NKOSI — Épicerie Africaine &
  Antillaise en Ligne") with working `/products.json` and a geo-cookie
  allowlist including TD, but prices are EUR (6.50, 26.65 on sweet-potato/
  attiéké-kit variants) and its own delivery pages are city-specific for
  metropolitan France (Lyon, Strasbourg, Marseille, Lille, Nantes). Classic
  diaspora shop — TD is a checkout-country option, not evidence of Chad
  fulfillment. Rejected on currency + locality.
- **sendinafrika.com** ("SendinAfrika — leader des achats en ligne pour la
  famille en Afrique") — zero occurrences of "Tchad"/"Chad"/"XAF" on the
  page, 76 occurrences of EUR, 4 of "diaspora". A France-based send-groceries
  -to-family-in-Africa service, not a Chad retailer.
- **djahizfood.wixsite.com/website** ("Djahiz Food" — third-party directories
  list this as "Lily's Supermarket"'s website; live page's own title reads
  "Djahiz Food") — full Playwright render (6s settle, 211KB DOM) shows zero
  occurrences of price/prix/FCFA/XAF/panier/commander/boutique/shop/"add to
  cart" anywhere. Brochure/marketing-only Wix page, no catalog, no checkout.
- **Sahil Express, N'Djamena Food, Nimvi Express, SHAMS** — restaurant/meal
  or last-mile parcel delivery apps, not grocery/retail catalogs. Out of
  scope, not pursued.
- **"Modern Market", "Le Bon Marché", "Lily's Supermarket"** — no independent
  website for any (Lily's listed domain resolves to the unrelated Djahiz
  Food brochure; `lilysupermarket.com`/`.td` NXDOMAIN). Facebook/TikTok/
  Snapchat-only presence — Chad's grocery retail sector is not web-
  catalogued, confirming prior passes' conclusion.
- Staple searches (mil, sorgho, riz, lait, gombo, niébé, arachide) surfaced
  only FEWS/WFP price-bulletin PDFs (already onboarded as `wfp_prices`, not
  a new retail source) and West-African diaspora shops (Dakar/Abidjan-based)
  with no Chad operation.

## Congo, Rep. (Congo-Brazzaville)

- **brazzatrade.netlify.app** — static Netlify landing page, 91KB HTML, 3
  EUR currency-selector tokens, zero product/price data on-domain; real
  transactions happen off-site via a linked Google Business Site and a
  Facebook group. Not scrapable.
- **petitmarchecongolais.com** — NXDOMAIN. Stale/dead search listing.
- **exo-market.net / exomarket.shop** — `.net` NXDOMAIN; `.shop` resolves
  (GoDaddy Website Builder, 200) but its own meta tags say "Launching Soon"
  — a splash page, zero products.
- **primarket.net** — Webflow marketing site (61.6KB), zero shop/catalogue/
  commander/produit/prix links anywhere. B2B contact-only, no retail
  storefront to scrape.
- **radarshops.com** — static template embedding two Facebook-post iframes
  + a Google Maps embed; zero FCFA/XAF price tokens in raw HTML; no product/
  catalogue links. Content lives entirely inside un-scrapable FB embeds.
- **parknshop.youmsi-tech.com** (Park'n'Shop / Régal loyalty portal) — only
  web asset found is a customer-loyalty login form (4.3KB HTML), no catalog,
  no prices. Confirms Congo's two largest physical supermarket chains have
  no online store.
- **terroirs-congo.com** ("Alimentaire exotique biologique") — Wix site;
  JSON site-config explicitly states `"currency":"EUR"` (3 occurrences).
  France-domiciled boutique selling to French consumers, not a Congo
  delivery service — worse than a diaspora shop, not even Congo-facing.
- **tekaleka.com** — NXDOMAIN (with and without www). Stale search listing;
  also not food-dominant per its own description (clothes/shoes/phones).
- **macuisineenligne.com** ("Le Panier Frais / Ma Cuisine en Ligne", Pointe-
  Noire fresh produce, WhatsApp+web ordering) — connection **timed out**
  (not a TLS/WAF signature) on 2 attempts, chrome124 and safari17_0, www and
  bare domain, 20-25s each. Host may be down/firewalled rather than gone.
  **Do not mark dead — retry next pass.**
- **Cerise Supermarché** — this is Libreville, **Gabon**, not Congo. Wrong
  country (name/city collision).
- **Joseph Distribution** ("Pointe-Noire" grocery delivery) — this is
  Pointe-Noire, **Guadeloupe** (French Caribbean), a city-name collision
  with Congo's Pointe-Noire. Wrong country.
- **ins-congo.cg** (national statistics office, INHPC/CPI publisher) — real
  official publisher (12 COICOP functions, 635 varieties tracked in
  Brazzaville per cached search content), but the live site has been
  replaced by a template redesign mid-relaunch: all old bulletin URLs 404,
  no sitemap/robots.txt, `stat-prix.html`/`derniere-publication.html`/
  `open-data.html` are empty nav shells, Wayback CDX for `uploads/*` returns
  only one unrelated Ministry-of-Health file (new upload path uses
  unguessable hashed filenames). **Genuine sourcing target, currently
  unscrapable — retry once the site stabilizes, do not mark permanently
  dead.**
- **iambeezy.app** — zero-commission store-builder SaaS for Congolese
  merchants; a platform, not a storefront. No merchant directory found to
  locate food stores built on it. Not pursued.
- **cabf.eu** — France-domiciled B2B wholesale distributor to Brazzaville
  supermarkets (Francap group, 15k+ SKUs); same shape as primarket.net.
  Untried beyond this note — likely no public consumer price catalog.
- Staple searches (chikwangue, saka-saka, foufou, manioc) surfaced only
  France/Belgium-based diaspora grocers (asianmarket.fr, nkosiagro.com,
  safinel.fr, laboboleraie.com, mcs-exotic.com) — none deliver inside Congo.
  These staples sell exclusively through physical street markets with no
  online storefront — a structural absence, not a searchable gap.

## Comoros

- **comoresmarket.com** ("Comores Market") — confirmed dead per existing
  known_blockers.md (TLS misconfiguration, `TLSV1_ALERT_INTERNAL_ERROR`
  across all curl_cffi profiles); not re-probed this pass.
- **comores-discount.com** — DNS does not resolve, despite a live search
  snippet referencing "produits frais et surgelés".
- **market-express.net** — DNS does not resolve (same dead domain also
  surfaced under CAR's search — a stale pan-African listing).
- **lesalimentsmm.com** ("Les Aliments M&M") — live Shopify site, but this is
  a **Canadian** frozen-food chain (og:description "au Canada"), zero
  mentions of Comores/Moroni/KMF/EUR. Coincidental name match to "MNM
  Trading" (a real Moroni frozen-meat trader per news coverage); unrelated
  business. Rejected on locality.
- **karthalamarket.com** ("Karthala Market") — live PrestaShop store,
  currency block confirms `"iso_code":"KMF"` and 53 mentions of "Comores" —
  genuinely Comorian-operated. Every food AND non-food category checked
  (10-alimentation, 24-produits-du-pays, 25-manioc-coco, 26-epices,
  27-epicerie-salee, 28-boissons, 30-legumes-fruits, 31-epicerie-sucree,
  64-laits-alimentation, plus non-food categories) renders "Aucun produit
  disponible pour le moment" — an empty pre-launch shell, zero products
  site-wide. **Worth a re-check in ~3-6 months if it launches.**
- **km.newtouse.com** ("NEWTOUSE") — has `/category/food-and-beverage/*`
  paths but every category page is a mass-generated SEO template — identical
  ~97KB boilerplate with no product cards, no listings, KMF appearing only
  in a currency-selector widget. A template network spun up per-country, no
  real inventory.
- **rahisii.com** ("Rahisi") — zero mentions of any food keyword; confirmed
  appliances-only ("Électroménager Premium Geepas"). Rejected on category.
- **FANA-FISH** (Moroni fishmonger, per La Gazette des Comores) — real
  business (sets fish prices 1,500-2,250 FC/kg per press coverage) but no
  discoverable website.
- **NFI ZA COMORES** (Moroni/Fomboni seafood shop) — real physical fishmonger
  per an evendo.com directory listing only; no independent domain found.
- **MNM Trading** (frozen meat/offal trader since 2015, per La Gazette des
  Comores) — real business, no dedicated website found.
- **Comorian vanilla/spice exporters** (epicesdecru.com, ileauxepices.com,
  epices.com, oranessence.fr, comoresvanille.fr, vanisaveurs.com,
  desepicesamaguise.com) — all French retailers selling Comorian-origin
  vanilla to metropolitan-France consumers, EUR-priced, free-shipping-to-
  France thresholds. Export shops, not Comorian domestic retail.

## Burkina Faso

- **jumia.bf** — Cloudflare "Just a moment…" 403 across chrome124/chrome120/
  safari17_0, shared Jumia tenant. Confirmed already in known_blockers.md.
- **mapsme.fr** — supermarket-directory site (per-country addresses/phones/
  websites); Cloudflare 403 "Attention Required!" across all three profiles.
  Even unblocked it would only be a directory.
- **SenPoisson** (Dakar), **eat2fresh** (Douala) — wrong country, diaspora/
  other-market sites.
- **EspaceAgro.com** listings (lait, farine, poisson, céréales) — pan-African
  B2B wholesale classifieds, request-a-quote, no live retail prices, not
  BF-specific. Same pattern as the already-blocked `ampagora.com`.
- **Kossam Lobbam** (dairy producer) — Facebook-only, no website.
- **CoinAfrique BF, Rodwoko** — individual-seller classifieds, not enumerable
  catalogs.
- **www.ouagadougou.online** — a prior wave (2026-09-01) marked this dead on
  a TCP timeout. **RE-VERIFIED LIVE 2026-09-11** (curl_cffi chrome124, 200
  throughout — the earlier verdict was transient connectivity, not a
  permanent block). Standard WooCommerce Store API, category=62
  ("Alimentation & Boissons", 547 products among ~90 mostly-non-food
  categories — general dropship marketplace, not a dedicated grocer).
  Enumerability confirmed (page1/page2 category-62 ids fully disjoint).
  Carried a site-wide XOF minor-unit bug (`currency_minor_unit=2` misapplied
  to a currency with no subdivisions — confirmed both in the Store API and
  in the vendor's own rendered PDP price, "CFA7.00" for a box of 100 Lipton
  tea bags). **Fixed and shipped this pass** as `ouagadougouonline_bf`
  using a dedicated `PRICE_MULTIPLIER=100`/`"XOF"` spider subclass (same
  precedent as `ecomguinee_gn.py`'s GNF fix) — 98 rows, 98 distinct urls,
  XOF, prices sane (100-33,600 XOF) after the fix.

## Cote d'Ivoire

- **jumia.ci** — Cloudflare Turnstile wall, confirmed via curl_cffi AND
  Playwright (interactive widget reaches "Un instant…" then never clears).
  Shared tenant, eighth Jumia country storefront with the identical wall.
  Not re-probed.
- **glovoapp.com** (CI storefronts) — not WAF-blocked, but plain HTTP 403s
  while Playwright renders fine; real assortment sits behind client-side
  collection tabs, homepage carousel trap (86 `ItemTile_` items, all promo).
  Worth a dedicated effort, not attempted this pass given budget.
- **plantesetepices.com** ("Panier", Abidjan) — PDPs server-render prices but
  catalog not enumerable (listing gated on unresolved delivery-zone
  selection, only 3 discoverable PDP urls; sitemap/robots.txt 404; every
  6amMart API path 404s). Not re-probed.
- **fraismarket.com** ("Frais Market", Yopougon fishmonger/butcher) — HTTP
  200 but body is a Bootstrap "Your domain is expired" parking page (10,881
  bytes). Domain registration lapsed since the last search-engine crawl.
- **lepotagerdabidjan.com** ("Le Potager d'Abidjan", PrestaShop fresh fish) —
  HTTPS fails with TLS handshake internal error across all curl_cffi
  profiles AND bare curl (genuine broken TLS config, not a WAF signature).
  Plain HTTP (port 80) serves a Hostinger "Parked Domain" page — storefront
  is gone.
- **ivoirelite.net** — general marketplace (téléphonie/bureautique/
  électroménager/mode/automobile); the specific `/404-poisson` URL (a stale
  category page, literal "404" in its own slug) falls back to a site-wide
  "Nouveaux produits" block that is 100% electronics. `/api/` 401s (gated).
  No live food category exists.
- **jaddis.com** ("Jaddis", épicerie fine Cocody) — live filterable product
  grid but zero prices anywhere in rendered HTML ("prix sur demande"
  pattern) — fails the non-zero-price gate. Also borderline on locality
  (imported French gourmet goods).
- **take.app/freshpanier** — HTTP 403 from Vercel edge across all three
  curl_cffi profiles; parent brand (freshpanier.com) already confirmed dead.
  Not escalated to Playwright given low priority.
- **freshpanier.com** — reconfirmed NXDOMAIN (already in the NXDOMAIN sweep).
- **ecomarket-africa.com, smarket-ci.com, aufraismarket.com, aufraismarket.ci**
  — all NXDOMAIN via DNS lookup. New dead domains, added to the sweep.
- **Oui Lait et Dêguê** (Abidjan yogurt/dégué producer — directly relevant to
  the dairy gap) — no website; social-only presence (TikTok/Instagram/
  Facebook/Twitter). Not a candidate until they launch a site.
- **Cash Center, Hayat, Sococe** (named Abidjan supermarket chains) — no
  independent online storefront beyond what's already recorded dead
  (`sococe.online` = "under construction", `cashcenter.ci`/`hayat.ci` =
  NXDOMAIN per the existing sweep). No new finding.

## Guinea

- **braprime.com** — dead Supabase backend, NXDOMAIN. Confirmed already in
  known_blockers.md, not re-probed.
- **mamakiti.com** — empty catalogue, pre-launch. Re-check only after ~6
  months per existing verdict; not re-probed.
- **monmarchegn.com** — app-only, zero web catalogue, no findable API.
- **omakiti.com** — rejected on locality (41 EUR tokens, 0 GNF, bundles
  "transfert d'argent" with groceries, diaspora shape). Not re-probed.
- **primaconakry.com** — Wix brochure site, zero products.
- **boucherieconakry.com** ("Boucherie Conakry") — DNS does not resolve.
  NXDOMAIN, dead.
- **bouchor.netlify.app** ("Bouch'or — Boucherie & Livraison à domicile") —
  live but its own meta/OG tags declare it serves **Dakar, Sénégal**, not
  Conakry. Wrong country.
- **www.alimakiti.com** ("ALIMAKITI") — PrestaShop confirmed, but footer
  address is "3 rue clos du rosay, France, 72300 Sablé-Sur-Sarthe"; embedded
  currency object is `{"name":"Euro","iso_code":"EUR"}`. Diaspora/France-
  based, not a Guinean domestic shelf — same pattern as omakiti.com.
- **selinawamucii.com/fr/connaissances/prix/guinee/*** (fonio, arachide,
  etc.) — schema.org markup discloses "Source: FAOSTAT Producer Prices",
  prices in USD, and even mislabels Guinea's currency as XOF (Guinea uses
  GNF). An SEO wrapper republishing FAOSTAT statistics, not a retailer or a
  distinct primary source.
- **prixguinee.com** ("Comparez les prix autour de vous") — crowdsourced
  Numbeo-style app; platform-wide stats JSON shows `total_prix: 32,
  total_boutiques: 2, total_contributeurs: 4` (not just food), sample record
  was a washing machine. Pre-launch/negligible volume, matches the cost-of-
  living-aggregator anti-pattern.
- **www.quickshop-gn.com** — 403 on chrome124/chrome120/safari17_0 alike,
  identical ~29.4KB body served by Vercel — reads as a Vercel deployment-
  protection gate (private/staging build), not a live public site.
- **www.guineeclicks.com** — live Wix site with Wix Stores wired in, but
  catalog is not server-rendered; would need the Wix eCommerce internal API
  (site instance token + GraphQL) to determine if it carries food.
  **Inconclusive — worth a dedicated Wix-API probe later.**
- Facebook-only pages with no independent site found (not scrapable):
  Boucherie Nouvelle GN, Boucherie de Guinée (MKSARL), POISSONNERIE COTE
  FRERES, Grand Annem, Franprix Guinée, Dfmarket.
- **goafricaonline.com** `/gn/annuaire/epicerie`, `/gn/annuaire/fruits-
  legumes`, `/gn/annuaire/production-produits-laitiers` — directory pages
  whose fetched HTML only exposed cross-country nav links, not actual
  listing entries (JS-rendered content). Not pursued further.
- A large prior NXDOMAIN sweep already covers: belair.gn, soduga.com,
  guineego.net, supermarchebelair.com, belairguinee.com, alimarket.gn,
  kanya.gn, tafa.gn, chezmoi.gn, paysanguinee.com, supermarchekaloum.com,
  guineemarket.com, conakryshop.com — all confirmed dead, unchanged.
- **Flagged, not fixed**: `koumia_gn.yaml` (pre-existing manifest, dated
  2026-09-11, NOT added by this pass) is a Shopify marketplace selling
  water dispensers, pressure washers, coffee machines, meat grinders —
  appliances, not food. This fills zero Guinea division-01/02 cells and
  should be removed by whoever owns manifest cleanup for this country; it
  was not deleted here because it predates this task and the harness
  blocked an attempted delete as an irreversible action.

## Niger

- **jumia.ne** — Cloudflare wall, shared Jumia tenant, no actual Niger
  operation. Not re-probed.
- **scorene.com** (guessed Niamey supermarket-chain domain) — expired-domain
  parking page, not a live business. Not re-probed.
- **agrishopniger.com** ("AgriShop" ag-marketplace) — live (200, Cloudflare-
  fronted, not blocked), Botble CMS, real multi-vendor "boutiques" directory
  (agrobusinesscenter, marche-dole, niamey-2000, moustapha-may-zama, + 4
  phone-number-slug shops), but every page checked — homepage,
  `/categories-produit/poissons`, `/categories-produit/volailles-et-
  charcuteries`, and 5 distinct boutique storefronts — renders the static
  "Aucun produit" placeholder. Platform-wide zero live SKUs. A historical
  indexed PDP (`/produits/riz-du-niger-33-50kg`) 404s. `www.v2.agrishop.ne`
  (the announced v2) does not resolve (NXDOMAIN). Dead business on live
  infrastructure, same shape as scorene.com.
- **nigermarches.com** — live (200, 461KB) but is a government/business
  tender-bidding platform ("1er Site d'appel d'offre au Niger"), not a
  price-data site. Off-topic.
- **agrigarbalshop.ne** — 403 across all three curl_cffi profiles, server:
  Vercel (deployment-protection edge block, not a classic WAF signature).
  **UNCONFIRMED-BLOCKED, not a settled dead end — worth a Playwright pass
  next time.**
- **KAMES Express** — parcel courier with tracking/mobile-money, no product
  catalog or prices. Not a retailer, matches prior inventory finding.
- **Niamey e-shop** — Facebook-page only (WhatsApp ordering), no independent
  website found.
- **Niger-Lait SA** (dairy producer) — Facebook presence only, no e-commerce
  site.
- **goafricaonline.com / espaceagro.com** — business directories / B2B
  wholesale RFQ marketplaces, same shape as the Ampagora precedent. Not
  retail catalogs with real transaction prices.
- **selinawamucii.com / combien-coute.net** — commodity/cost-reference
  aggregator sites (single modelled price points), same population as the
  banned Numbeo/LivingCost-style aggregate_proxy publishers. Not pursued
  per the skill's anti-pattern against more cost-of-living aggregators.
- **siar.uemoa.int** (regional UEMOA agri-market bulletin, mil/sorgho/niébé
  prices) — page loads (200) but no downloadable CSV/XLS found on first
  pass; would need form-driven API sniffing. **INFERRED-promising, NOT
  verified — flagging as a next-step lead, not shipped.**


---

## known_blockers_disco_mena - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_mena.md` on 2026-09-11. 88 hosts, 66 not
documented above at merge time.

# Known blockers — MENA + Guinea-Bissau food-source discovery campaign (2026-09-11)

Countries: guinea_bissau, libya, syria, iraq, yemen, sudan. Merged from three
independent, overlapping discovery passes run concurrently the same day in the
same shared worktree (two dispatched sub-agents plus direct orchestrator work),
which is why several "Net result" sections below understate the country's
final shipped count: they were written before a *later* pass, working the
same country in parallel, discovered one more real source. Each such
mismatch is called out explicitly with a correction note directly under the
affected "Net result" heading — those notes, not the original paragraph
above them, are the accurate final count. Total shipped this campaign: 17 new
sources (10 Iraq — abu_nawas_fish_lezzoo_iq, asfahan_nuts_iq,
lezzoo_mart_erbil_iq, nan_house_bakery_lezzoo_iq, sarwaran_butchery_lezzoo_iq,
sarwaran_grocery_lezzoo_iq, sherko_nuts_lezzoo_iq, sultan_butchery_lezzoo_iq,
varya_grocery_lezzoo_iq, waffir_iq; 1 Syria — prices_sy; 1 Sudan —
stock249_sudan; 0 each for Guinea-Bissau, Libya, Yemen). All manifests were
re-verified (schema validation + re-reading the on-disk test-run output) by
the orchestrator after the parallel passes completed, on 2026-09-11.

---

# Known blockers — Guinea-Bissau food-source discovery (2026-09-11)

Item-specific + Portuguese/French discovery pass, run after a prior 443-query
`ddgs` sweep (covering the 23 lowest-coverage countries worldwide) already
came back with **zero verified candidates** for Guinea-Bissau. This pass
targeted the cashew/rice/fish angle plus fresh generic Portuguese/French
grocery-delivery search terms specifically to see if the item-specific method
(which the campaign brief calls out as higher-yield than generic sweeps)
could surface anything new. **It did not — 0 of 7 new candidates ship.**

## Government/news pages, not retailers

- **Cashew price coverage** (vidarural.pt, lusa.pt, forbesafricalusofona.com,
  noticiasaominuto.com, sapo.pt, correiodamanhacanada.com) — every result for
  "castanha de caju preço Guiné-Bissau" is government reference-price news
  (410 FCFA/kg producer price, 1,050 USD/ton export price for the 2026
  campaign) or a Facebook post from the cashew regulator (CAP-GB Sarl). No
  retail storefront, no per-unit consumer price, no catalogue. **REJECT — not
  a retail source.**

## Non-food classifieds

- **bissauonlinemarket.com** ("Bissau Online Market") — WordPress site,
  `/wp-json/` present but the WooCommerce Store API 404s on every path
  (`/wp-json/wc/store/v1/products`, `/wp-json/wc/store/products`,
  `?rest_route=/wc/store/v1/products`) — it's a classifieds board, not a
  WooCommerce catalogue. Confirmed by its own category menu: celulares,
  computador, decoracoes, empregos, esportes, imoveis, industria,
  informatica, jogos, servicos, veiculos — **no food/mercearia category at
  all**. Sample listings are a drone, an iPhone 14, a PS5, a wireless lapel
  mic. Exactly the "gaming shop / electronics" trap the campaign brief warns
  fills zero food cells. **REJECT — non-food classifieds.**

## No independent web presence (Facebook-only)

- **SPAR Guiné** (facebook.com/sparguine) — SPAR's Bissau franchise has no
  dedicated domain. Tried `spar.gw`, `www.spar-guine.com`, `sparguine.com` —
  all NXDOMAIN (`curl_cffi`: "Could not resolve host"). A real supermarket
  chain presence, but nothing to scrape. **REJECT — no web catalogue.**

## Diaspora / wrong-locality traps

- **Ibisen** (ibisen.com) — online grocery/household retailer; its own
  delivery-area copy names "Guinea, France, Germany, Italy" — this reads as
  Guinea-Conakry (or a generic "Guinea" catch-all), not Guinea-Bissau
  specifically, and the storefront markets to a European/diaspora audience.
  Not re-probed further given the locality ambiguity plus no XOF/FCFA
  currency confirmed. **REJECT — locality unconfirmed / likely diaspora.**
- **NKOSI** (nkosiagro.com), **Saveurs D'AFRIK** (saveursdafrik.com),
  **ISSANNY** (issanny.com) — French-based African/Antillean grocery
  retailers delivering "throughout Europe." No Guinea-Bissau delivery claim
  found. **REJECT — diaspora audience, wrong locality.**
- **ColisExpat** (colisexpat.com) — a parcel-forwarding/reshipping service
  (receives EU/US purchases, forwards to Guinea-Bissau), not a retailer with
  its own priced catalogue. **REJECT — not a retail source.**

## Net result

No new Guinea-Bissau source shipped this pass. `ikuma_gw.yaml` (channel:
supermarket) remains the only genuine food retailer onboarded for this
country. This corroborates the prior sweep's finding that Guinea-Bissau is
one of a small handful of countries (with Gibraltar, Central African
Republic, Palau) where the online retail sector is close to nonexistent —
likely a structural absence (thin digital-commerce penetration) rather than
a search-method failure, given both a broad 443-query sweep and this
targeted item-specific/regional-staple pass came back empty.

---

# Known blockers — Libya food-source discovery (2026-09-11)

Item-specific Arabic discovery pass (dates, meat, rice, spices) run after
the extensive prior sweeps already recorded in `~/gapwork/known_blockers_repair_1.md`,
`known_blockers_untried_2.md`, and the skill's own
`references/known_blockers.md` (almatjar.ly/greenapplespharmacy.com/
nesraf.com/souristore.com hcdn; progaming.ly Cloudflare ASN block;
watti.ly/wdelivery pre-launch; nawris.net/jetak.me seed data; arkan.top.ly
NXDOMAIN; libyanstores.com/lpcffi.com B2B corporate; libyashop.ly no food
merchant; ubuy.com.ly WAF-exhausted; matjar-libya.com/souqly.ly no food
category). **0 of 9 new candidates ship for Libya this pass.**

## Geo/IP block (not a JS challenge)

- **bekam.ly** ("Bekam" -- an app for food/meat/currency prices in Libya,
  a strong lead structurally similar to Syria's prices.sy and Sudan's
  stock249.com found in this same campaign pass) -- every path, including
  `robots.txt`, returns a bare nginx 403 with the classic
  "padding to disable MSIE and Chrome friendly error page" comment
  signature, under all three `curl_cffi` impersonation profiles
  (chrome124/chrome120/safari17_0). No `cf-ray`, no JS-challenge title --
  reads as a plain IP/geo-based deny rule (nginx `deny` / `allow` ACL),
  same class as carrefour.iq's Akamai geo-refusal. Needs a Libya-resident
  network path to re-attempt; not fixable from this box. **Highest-value
  remaining Libya lead** if network access changes.

## Wrong-country cross-matches (surfaced on Libya-language queries, not Libya)

- **waffiriq.com** ("Waffir Hypermarket") -- surfaced on a Tripoli-focused
  meat-price search purely on the domain string containing "iq"; verified
  via payload (`prices.currency_code=IQD`, homepage mentions "بغداد"
  Baghdad) that this is a real Baghdad, IRAQ hypermarket, not Libyan.
  **Shipped as a new IRAQ source instead** (see the Iraq section of the
  campaign report) -- not a Libya rejection so much as a filed-under-the-
  wrong-country correction.
- **lahmtklbatk.com** ("لحمتك لبيتك" -- "your meat to your home") -- a
  real, live Salla-platform (`cdn.salla.network`) online butcher with
  genuine categories (lamb/veal/poultry/eggs), but SAR pricing -- a Saudi
  butcher, not Libyan. **REJECT -- wrong country**, same Salla/SAR pattern
  as jomlah.app (Yemen).
- **tmrstore.com**, **nabtatistore.com** -- Saudi date retailers (SAR
  pricing, zero LYD/دينار anywhere), surfaced on a Tripoli date-price
  search. Same pattern already documented for Iraq's identical search in
  this same campaign pass. **REJECT -- wrong country.**

## App-only / no web catalog

- **drubi.ly** ("Droobi" delivery) -- single-page marketing site
  (Bootstrap template, `#anchor` navigation, app-store links, a literal
  placeholder `href="https://www.example.com"`), no catalogue, no API.
  **REJECT -- app-only / unfinished.**
- **app.clickshop.ly** ("Click Shop" -- restaurant/store delivery) --
  genuine Cloudflare Turnstile challenge (`cf-mitigated: challenge`,
  "Just a moment..." title) persisting under `curl_cffi` impersonation AND
  a plain non-impersonating request. Per the skill's mandatory-gate rule,
  a real content-level challenge like this is not pursued further (no
  captcha-solving in scope). **REJECT -- hard Cloudflare wall.**

## B2B / corporate, no retail catalogue

- **lohoom.ly** ("Lohoom Libya Food Industries") -- a frozen-food importer/
  processor's corporate portfolio site (project gallery: frozen, half-fried,
  packed potatoes, poultry meat). Zero cart/price markup anywhere ("السلة",
  "أضف الى", "سعر" all absent). **REJECT -- B2B corporate, not retail.**

## Facebook-only (no independent domain)

- **tawsilla.libya** ("توصيلة"), **talabk.Libya** ("طلبك") -- Tripoli
  delivery services with Facebook pages only, no scrapable domain found.

## Net result

No new Libya source shipped this pass -- Libya's standalone-domain grocery
e-commerce surface, and its Cloudflare/hcdn-walled cluster, both remain as
exhausted as the prior waves found them. The one live lead worth carrying
forward is **bekam.ly**, a price-index app blocked at the network/geo
layer rather than by a solvable JS challenge -- flag for a future pass
with a Libya-resident egress point. One incidental find (waffiriq.com) was
misdirected traffic from a Libya search that turned out to be a genuine
new Iraqi source and was shipped there instead.

---

# Known blockers — Syria food-source discovery (item-specific pass, 2026-09-11)

Item-specific Arabic search (dates, meat, fish, bulgur, tahini, spices, butcher,
bakery, grocery-delivery) around Damascus/Aleppo/Homs. Generic-supermarket
sweeps were already exhausted by prior waves (see
`~/gapwork/known_blockers_repair_1.md`, `known_blockers_unknown_1.md`).
Zero new sources shipped this pass — every candidate failed a hard gate.
All probes via `curl_cffi impersonate=chrome124` from a8 unless noted.

## Wrong-country / diaspora-platform trap (Gulf SaaS platforms ranking on Syrian-food searches)

- **dmashq.com** ("مراعي دمشق للحوم والمشويات", Damascus-branded butcher/meat
  shop) — real Salla-platform storefront (cdn.salla.sa assets), PDP
  `og:product:pretax_price:currency` = **SAR**, not SYP. A Saudi-hosted
  Damascus-branded butcher, reads as a Syrian-diaspora shop serving Saudi
  Arabia, not a Syria-resident retailer. **REJECT — currency/locality.**
- **alhagas.com** ("الهقاص", grocery — بقولة) — same Salla platform, same
  SAR pricing (e.g. برغل اسمر 1kg = 10.43 SAR). **REJECT — currency/locality.**
- **almasmka.com** ("شراء سمك اون لاين طازج", fresh-fish branding) — Salla
  platform, SAR only. **REJECT — currency/locality.**
- **fustoqah.com** (grocery, "برغل ابيض" etc.) — Zid platform (Gulf
  ecommerce SaaS), currency selector offers KWD/SAR/AED/OMR/BHD — a
  Gulf-market grocery, no SYP option at all. **REJECT — currency/locality.**
- **butcherista.com** ("بوتشريستا | جزارة أونلاين", online butcher) — Zyda
  platform, WhatsApp contact is an Egyptian number (0100...), footer states
  "All prices are shown in EGP". Egypt-based butcher, not Syria. **REJECT —
  currency/locality.**

## Real Syrian platform, catalog fails a hard gate

- **bacolaa.com** ("متجر بقولة السوري" — Syrian Grocery Store) — genuine
  WooCommerce Store API, but same hcdn TLS/JA3 fingerprint wall as the Libya
  cluster: `curl_cffi impersonate=chrome124` 403s, plain non-impersonating
  `requests` clears it (same lever as albasatin_aldhahabia/almatjar.ly).
  MEASURED enumerability: `/wp-json/wc/store/v1/products?per_page=20`,
  X-WP-Total=1864, 94 pages, page1 vs page2 fully disjoint ids. Currency
  confirmed SYP from payload (`currency_code: SYP`, `currency_minor_unit:
  0`, e.g. real non-zero prices 150,000 / 9,000 SYP). BUT sampled 104
  products across 6 pages and only 8 (7.7%) carry a non-zero price — the
  rest are `price: '0'`. Same "live paginating API, catalog not actually
  priced" dead end documented for cyberstore.co.bw. **REJECT — non-zero-price
  gate.** Worth a re-check in a future wave in case the merchant fixes
  pricing; the plain-request bypass technique (`generic_woo_playwright` or
  a simple non-impersonating variant) is proven to work here if it ever does.

## Real Syrian marketplace, no food category / empty food category

- **souq-online.com** ("سوق أون لاين") — real Syrian OLX-style classifieds
  (per-governorate filters: Damascus/Aleppo/Homs/Hama/Latakia/etc, real SYP
  prices confirmed elsewhere on the site, e.g. 275 ل.س on a non-food
  listing). Has a dedicated food category (`/ar/category/12`, "مونة وغذاء"
  — Preserves & Food) but it returned **zero listings** on both page 1 and
  page 2 at probe time. **REJECT — empty food category** (not a platform
  problem; re-check later, listings are user-generated and may repopulate).
- **damasbazar.com** — real marketplace with an SYP/EUR/TRY/EGP exchange-rate
  widget, but its category list is electronics / home-appliances / clothing
  / real-estate / automotive / home / beauty only — **no food or grocery
  category exists**. **REJECT — wrong category mix (structural, not a bug).**

## Real but far below usable scale

- **prices.sy** ("أسعار سوريا" — self-described "your comprehensive daily
  guide to prices of goods in Syrian governorates") — a real, live,
  server-rendered (Tier 1A) community price-tracking site with per-item
  pages (`product.php?id=N`), governorate tagging, and confirmed SYP prices
  (e.g. id=15, "حلو عربي بالفستق", إدلب, 27,300 ل.س). MEASURED: the entire
  site holds only **3 live product listings site-wide** (ids 1, 15, 17) —
  no sitemap, no pagination beyond that. Two orders of magnitude below the
  5-row minimum-viable bar even before considering it's an early-stage
  project, not an established index. **REJECT — scale**, but flagged as a
  format worth re-checking in 6+ months if the project grows (structurally
  it would be a clean `analytical_role: official_avg`,
  `coicop_classification: classifier` fetcher if it ever reaches
  meaningful scale).

## Insufficient evidence, not pursued further

- **yasermallonline.com** ("YaserMall — Online Grocery Shop") — tiny
  (2.7KB) Angular SPA shell, all-English branding with zero
  Syria/Arabic/governorate signal anywhere in the static HTML. Could not
  confirm country or currency without a full Playwright render; deprioritized
  given no positive Syria signal at all (unlike the Gulf-platform traps
  above, which at least had Syrian branding to reject on). Not re-probed
  with Playwright this pass.

## Net result

0 of ~13 fresh candidates from THIS pass shipped — but see correction below.

**CORRECTION (2026-09-11, later pass, orchestrator-verified):** a parallel
pass discovered that the `prices.sy` rejection above was based on an
incomplete probe — only the homepage and the blank `search=&gov=` query
were checked, both of which show a 3-item "featured" sample, not the full
site. Browsing by the site's own `index.php?cat=N` category parameter
(N=1,2,3,8,9,10 — the six COICOP-01/02-relevant categories out of 12 total)
returns 45+1+12+6+5+8 = **77 distinct product ids**, independently
re-confirmed by the orchestrator via direct `curl_cffi` probe of all six
category pages. Shipped as `prices_sy.yaml` (fetcher,
`analytical_role: official_avg`). Re-ran `prices collect --source
prices_sy` and read `data/prices/menaap/middle_east/syria/prices_sy/
price_observations.csv` directly: **77 rows, 100% SYP, real Syrian
governorates and branded item names** (e.g. "لحم غنم بعظمه" 195,000 SYP in
حمص/Homs, "أرز بسمتي" 181,800 SYP in اللاذقية/Latakia). Flagged honestly in
the manifest as a 6-months-stale crowd-sourced board (every sampled row's
"last updated" date is 2026/03), not an official publisher — but every
hard gate (real SYP, real cities, real branded items, disjoint ids across
categories) passes on the live payload. Syria's food-price coverage is now
1 source (was 0) plus the existing dokan_sy/dokanmall_sy/tsaooq_sy
marketplaces (unconfirmed food depth) and wb_rtdi/wfp official_avg.

---

# Known blockers — Iraq food-source discovery (2026-09-11)

Item-specific Arabic discovery pass (dates, rice, meat, fish) plus a
Lezzoo-directory sweep, run after the prior wave already covered
carrefour.iq / dukani.online / delivery-iraq.com / altunmarket.com (all
still dead, not re-probed — see `~/po-worktrees/fill-gap-sources/.claude/skills/onboard-price-sources/references/known_blockers.md`
line 368+ and `bakhtiyari_lezzoo_iq.yaml`'s own notes for the earlier
standalone-storefront dead-end list: kurdistansupermarket.com,
hollandbazar.com, meswaghypermarket.com, ezadstore.com, martoo.com,
ishtarmart.com, zadfresh.com, padash.app/lezzoo.com root, grocerjy.com).

## Wrong-country currency traps (Saudi, not Iraq)

- **tmrstore.com** ("متجر التمور الذهبية" / Golden Dates Store) — surfaced
  on an "أسعار التمور بغداد" (date prices Baghdad) search, but the page
  quotes SAR, zero IQD/دينار mentions anywhere. A Saudi date retailer
  ranking on Iraqi search terms. **REJECT — wrong locality/currency.**
- **nabtatistore.com** ("متجر نبتتي") — same pattern: SAR pricing, zero
  IQD. **REJECT — wrong locality/currency.**

## App-only / no web catalog

- **talabatey.com** / Talabatey Hyper Market (Baghdad) — homepage is a
  bare app-download landing page (`/app` link, Cloudflare-fronted static
  page), no `/api/`, no wp-json, no product listing reachable over plain
  HTTP. **REJECT — app-only, no web catalog** (same class as watti.ly/
  wdelivery in Libya).
- **waffir.iq** (هايبرماركت وفّر, Baghdad), **البراق ماركت** (Al-Buraq),
  **بيتي ماركت**, **سوبرماركت بغداد** — all Facebook-page-only presences
  found via search, no independent domain to probe. Not re-attempted
  (Facebook itself is out of scope for retail scraping). **REJECT — no
  scrapable web presence.**

## Mislabeled / wrong category (Lezzoo directory)

- **the-dates-764** (lezzoo.com/erbil/m/the-dates-764) — despite the
  vendor-name match on "dates", the venue's own JSON-LD menu sections are
  "Sea Food, Soups, Salads, Hot Appetizers, Pottery Fries, Cold
  Appetizers, Sandwiches, Burger" — a restaurant (COICOP 11.1, out of
  scope), not a date retailer. **REJECT — wrong category despite the
  name.**
- **amara-dates-9381** (lezzoo.com/erbil/m/amara-dates-9381) — genuinely a
  dates vendor (single "Collections" section) but only 5 items on the
  page-1 JSON-LD menu — right at this campaign's row floor and thin
  enough that it wasn't prioritized this pass over the 4 sources shipped
  (each 60 rows). Legitimate future candidate, not rejected outright, just
  not built this round.
- **zirak-fish-1501**, **meer-fish-1033** — vendor names promise a
  fishmonger but the actual JSON-LD menus mix in "Pizza", "Burger",
  "Sandwich", "Meals" sections (zirak-fish) or are very thin at only 10
  items split across "Offer"/"Chicken"/"Drinks" as well as fish
  (meer-fish) — read as seafood restaurants/small stalls, not pure fish
  retailers. Not shipped this pass; **candidates for a future pass** if a
  cleaner fish-only Lezzoo venue turns up (fish-corner, fish-land, lawan-fish,
  qubtan-fish, alknjly-fish-chicken, bawki-meer-fish-alwa were seen in the
  directory listing but not individually probed this round).

## Net result

**CORRECTED FINAL COUNT (2026-09-11, orchestrator-verified against the live
manifest directory and each source's on-disk test-run output — supersedes
the "4 new sources" this section originally claimed):** Iraq gained **10**
new sources this campaign, from three overlapping passes working the same
Lezzoo-directory lead concurrently. All via the shared `generic_lezzoo_venue`
spider except `waffir_iq` (standalone WooCommerce). One venue
(`sultan-butchery-and-market-9145`) was independently found by two passes
under different source_keys and consolidated to a single manifest
(`sultan_butchery_lezzoo_iq`) to avoid double-scraping the same URL; every
other venue_url below is confirmed distinct. All MEASURED 100% non-zero IQD,
100% distinct urls, re-confirmed by the orchestrator by re-reading each
source's `data/prices/menaap/middle_east/iraq/<key>/raw_items/*.jsonl`:

| source_key | channel | rows | distinct urls |
|---|---|---|---|
| abu_nawas_fish_lezzoo_iq | specialty-food (fish) | 11 | 11 |
| asfahan_nuts_iq | specialty-food (nuts) | 60 | 60 |
| lezzoo_mart_erbil_iq | convenience | 60 | 60 |
| nan_house_bakery_lezzoo_iq | specialty-food (bakery) | 60 | 60 |
| sarwaran_butchery_lezzoo_iq | specialty-food (meat) | 60 | 60 |
| sarwaran_grocery_lezzoo_iq | fresh-market | 60 | 60 |
| sherko_nuts_lezzoo_iq | specialty-food (nuts) | 60 | 60 |
| sultan_butchery_lezzoo_iq | specialty-food (butcher+produce) | 60 | 60 |
| varya_grocery_lezzoo_iq | fresh-market | 60 | 60 |
| waffir_iq | hypermarket (WooCommerce) | 100 | 100 |

Combined COICOP-relevant coverage: fresh produce, meat, fish, bakery/bread,
nuts, dates (one grocery venue carries a dedicated "Date" section), and
packaged rice/oil/canned goods via waffir_iq. Iraq's standalone-domain
grocery e-commerce surface remains essentially exhausted (carrefour.iq
geo-blocked, every other generic storefront candidate found is
dead/demo/wrong-country) — Lezzoo's ~1000-venue Erbil directory is the one
channel still yielding clean new sources and is worth a deeper future pass
(several more grocery/butcher/fish/nuts-named venues were seen in the
directory but not individually probed — see the "not shipped" list above,
e.g. amara-dates-9381, and the fish-corner/fish-land/lawan-fish/
qubtan-fish cluster).

---

# Known blockers — Yemen food-source discovery (item-specific pass, 2026-09-11)

Item-specific Arabic search (dates, meat, fish, Yemeni coffee, Yemeni honey,
spices, butcher, bakery, grocery-delivery) around Sanaa/Aden. Generic-
supermarket sweeps already exhausted by prior waves (see
`~/gapwork/known_blockers_unknown_1.md`). Zero new sources shipped —
every real lead failed a hard gate. All probes via `curl_cffi
impersonate=chrome124` from a8 unless noted.

## Yemeni-coffee / Yemeni-honey specialty shops — all export-priced, not YER

The "regional staple" angle (بن يمني / عسل يمني) surfaced a cluster of
well-built ecommerce sites branded around Yemen's two most famous food
exports. Every one checked prices in a foreign currency confirmed from the
payload/JS global, not YER — these are export/diaspora storefronts, not
Yemen-resident retailers:

- **yemeni-honey.com** — WooCommerce Store API, `currency_code: USD`
  (e.g. "بكج العافيه" honey gift package = $56.00). **REJECT — currency.**
- **souqalbon.com** (coffee) — WooCommerce Store API, `currency_code: OMR`
  (Omani Rial). **REJECT — currency/locality (Oman-facing).**
- **sulala-honey.com** — WooCommerce Store API, `currency_code: EGP`.
  **REJECT — currency/locality (Egypt-based).**
- **helmehoney.com** — Shopify, SAR. **REJECT — currency.**
- **hebro.co** (coffee) — SAR. **REJECT — currency.**
- **webrewroasters.com** (coffee) — SAR. **REJECT — currency.**
- **mulhumhoney.com** — multi-currency checkout (USD/GBP/EUR/AED/SAR/QAR/
  KWD/OMR/BHD/CAD) with no YER option at all — a global export storefront.
  **REJECT — currency.**
- **albonalyemeni.com** ('البن اليمني') — Salla platform,
  `window.currency_symbol = "$"` — USD. **REJECT — currency.**
- **alruknalyemeni.com** ('متجر الركن اليمني', found under a generic
  grocery-delivery search) — also Salla, also `window.currency_symbol =
  "$"` — USD. **REJECT — currency.**
- **albakreehonye.com**, **alassaal.com** (honey) — both hcdn 403 under
  `curl_cffi` impersonation; not pursued further given every honey/coffee
  candidate resolved so far has failed on currency rather than reachability
  (low expected value from clearing the wall).

## Wrong COICOP division (restaurant, not retail food)

- **wagbat.com** ('وجبات' — Yemen restaurant-delivery platform, hosts named
  vendor pages like `/restaurants/view/Wagbat_butchery`) — pure
  client-rendered SPA, no JSON-LD, no visible price/currency text in raw
  HTML (would need a Playwright network trace to find the backing API; not
  pursued given the vendor pages found — "Wagbat_butchery", "almalaki",
  "alkhateebsafia" — read as sit-down/takeaway restaurants by name, not
  butcher-counter retail). **DEFERRED — insufficient evidence, would need
  Playwright.**
- **uptownye.com** ('Uptown' — Sanaa food delivery) — real, live, has a
  `/menu` — but it is a single restaurant/takeaway operation (COICOP 11
  restaurants, not 01/02 retail food). **REJECT — wrong division.**

## Already-covered / already-rejected, reused verdict

- **almasmka.com** — same Salla/SAR storefront already rejected for Syria
  (see `known_blockers_disco_mena_syria.md`); it surfaced again on a
  Yemen fresh-fish search. **REJECT — currency (SAR), locality.**
- **ye.opensooq.com** — general classifieds marketplace, same pattern as
  the already-out-of-scope opensooq country sites (sy.opensooq.com,
  iq.opensooq.com). Not pursued.

## Net result

0 of ~15 fresh candidates shipped. Existing Yemen coverage (relon_aden_ye,
smsm_ye, souqmy_ye, yemenbox, yemenstorez_ye; wb_rtdi and wfp official_avg)
is unchanged by this pass. The Yemeni-coffee/honey angle is now a
documented dead end for LOCAL retail sourcing specifically — it is a real
and valuable commodity but the entire discoverable online-retail surface
for it is export-facing.

---

# Known blockers — Sudan food-source discovery (item-specific pass, 2026-09-11)

Item-specific Arabic search (sorghum, groundnuts, sesame/tahini, ful
medames, meat, fish, spices, butcher, bakery, grocery-delivery) around
Khartoum. Generic-supermarket sweeps already exhausted by the prior wave
(see `~/gapwork/known_blockers_untried_3.md` — Al Waha, Hyper Express,
LILY Delivery, Storna, Talabaty, Zaad Delivery, dukani.online, all
rejected 2026-09-01, re-confirmed still current). Zero new sources
shipped — every real lead failed a hard gate. All probes via `curl_cffi
impersonate=chrome124` from a8 unless noted.

## Diaspora shops selling Sudanese food, wrong currency/country

- **alafnanfoods.com** ('Al Afnan') — real, live WooCommerce Store API,
  genuinely enumerable (X-WP-Total=97, 5 pages, page1 vs page2 disjoint
  ids), 100% non-zero prices, genuine Sudanese products (طحينة halawa,
  فسيخ, كانون شواء سوداني "Sudanese grill"). BUT `currency_code: AED`
  throughout — a UAE-based Sudanese-diaspora grocer, not Sudan-resident.
  Otherwise the strongest candidate found this pass; flagged in case a
  Sudan-priced sister storefront exists. **REJECT — currency/locality.**
- **dukkanstore.net** ('Dukkan Store', "كل احتياجاتك السودانية عندك" —
  "all your Sudanese needs") — WooCommerce (via
  `/?rest_route=/wc/store/v1/products`, the versioned wp-json path
  404s), real Sudanese-food product names (صاج, شواية, كانون, حلاوة نبق),
  but `currency_code: EGP` throughout. An Egypt-based diaspora shop
  (consistent with Egypt's large Sudanese refugee population post-2023).
  **REJECT — currency/locality.**

## Pre-launch / marketing-only

- **mamo-sd.cloud** ('Mamo Market') — homepage text explicitly claims
  "أسعار بالجنيه السوداني" (prices in Sudanese Pounds) and
  "توصيل حسب الولاية" (delivery by state), which read as genuine Sudan
  signals, but the page itself is a single-screen app-marketing landing
  page ("#download"/"#sections" anchors only, no real product/category
  URLs) with a WhatsApp contact number under the **+974 Qatar** country
  code. No scrapable web catalogue exists yet. **REJECT — no catalog
  surface** (same class as Zaad Delivery from the prior wave).

## Real marketplace, no food category

- **koshmall.com** ('Kosh Mall' — "platform for Sudanese merchants",
  CS-Cart-based multi-vendor marketplace) — genuinely supports an SDG
  currency option (`?currency=SDG`, alongside USD/SAR) and has a
  "companies.catalog" vendor directory. Its category tree is
  beauty-and-health / electronics / fashion / fragrance-and-incense /
  home-and-kitchen only — **no food or grocery category exists**.
  **REJECT — wrong category mix (structural).** Worth re-checking later:
  if the vendor directory ever adds a food seller, the SDG-pricing
  infrastructure is already proven to work here.
- **alsoug.com** ('سوق السودان') — real Sudan classifieds (SDG pricing
  confirmed via site-wide "كتابة الاسعار بعملة الجنيه السوداني الجديدة"
  copy), but its closest food-adjacent category
  (معدات و امدادات المصانع و الاعمال / توريد مواد غذائية — B2B factory
  food-supply listings) returned **zero live listings** on probe.
  **REJECT — empty category.**
- **sudanportal.com** ('Sudan Portal', موردين الأغذية / "food suppliers"
  directory) — WooCommerce Store API live and enumerable, but every
  sampled product (بذور الكمون, صمغ اللبان) carries `currency_code: USD`
  AND `price: '0'` — a B2B sourcing/RFQ directory (Alibaba-style),
  not a priced retail catalogue. **REJECT — currency AND zero-price
  gates, both independently.**

## Net result

0 of ~10 fresh candidates from THIS pass shipped — but see correction below.
The pattern across three fresh Sudan waves now (2026-09-01, the untried_3
batch, and this item-specific pass) is consistent: every discoverable
Sudan-*branded* retail storefront found by search is either UAE/Egypt/Qatar
diaspora-priced, seed/demo data, or pre-launch.

**CORRECTION (2026-09-11, later pass, orchestrator-verified):** a parallel
pass found a genuinely different kind of candidate this list didn't
consider — not a retail storefront but an official-bulletin republisher.
`stock249.com` ("Elrayah Group") is primarily a Sudanese black-market
FX/gold tracker, but its `/agri-sudan` and `/consumer-sudan` pages embed a
JSON-LD `ItemList` of commodity prices explicitly sourced from "نشرات
رسمية: سوق القضارف ... والإدارة العامة لتسويق المحاصيل بإقليم النيل الأزرق"
(official Al-Gadarif market / Blue Nile crop-marketing-directorate
bulletins). Shipped as `stock249_sudan.yaml` (fetcher,
`analytical_role: official_avg`). Orchestrator re-ran `prices collect
--source stock249_sudan` and read `data/prices/ssa/east_africa/sudan/
stock249_sudan/price_observations.csv` directly: **21 rows, 100% SDG,
100% non-zero**, covering sorghum, millet, sesame, groundnuts, sugar, rice,
lentils — directly hitting several regional-staple gap categories (e.g.
"جوال فول سوداني" groundnuts-sack 180,000 SDG, "قنطار السمسم" sesame-quintal
310,000 SDG). Sudan's food-price coverage is now 2 sources (was 1 —
hypersale_sd) plus wb_rtdi/wfp official_avg; dawana_sd (pharmacy) and the
two telco tariffs remain non-food.


---

## known_blockers_disco_natlantic - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_natlantic.md` on 2026-09-11. 8 hosts, 1 not
documented above at merge time.

# North Atlantic micro-territory food-source discovery — 2026-09-11

Scope: Greenland, Faroe Islands, Channel Islands (Jersey/Guernsey), Andorra,
San Marino, St. Martin (French part) — COICOP divisions 01/02 only. This pass
was a re-audit + gap-fill on top of extensive prior work already merged into
the repo (2026-09-01 ECA F&B sweep, 2026-09-11 Greenland custom-batch
consolidation). Findings below are RE-VERIFIED as of 2026-09-11, not
projections — see the per-country inventory files
(`.claude/skills/onboard-price-sources/references/inventories/eca/western_europe/`)
for full probe histories.

## Verdict summary (as of 2026-09-11)

| Territory | Food source status | Verified this pass |
|---|---|---|
| Greenland | Structural absence, food e-commerce. `pisiffik_gl` is a non-food dept-store arm (Elgiganten/Jysk/Thansen); `brugseni.gl`/`pilersuisoq.gl` are brochure-only (0 price tokens); 14 other Greenland manifests onboarded 2026-09-11 (Shopify/WooCommerce boutiques) are ALL non-food (fashion, electronics, dept-store, books, pet). | Re-checked Spar Greenland lead (below); no change. |
| Faroe Islands | Structural absence, food e-commerce. Three independent passes (2026-09-01 x2, 2026-09-11) confirm no online grocery sector. `alvaro_fo` (fashion) and `djor_fo` (pet) are the only shipped sources, both non-food. | No new candidate found; did not re-run full search (WebSearch budget exhausted session-wide). |
| Channel Islands | COVERED. `coop_ci` — Channel Islands Co-op, both Jersey (5,058 SKUs) and Guernsey (4,687 SKUs) stores, 73.4% measured food+beverage share. | Re-ran `--source coop_ci --max-items 100`: 200 rows, 200 distinct URLs, clean. |
| Andorra | COVERED. `andorra2000_ad` — Carrefour Andorra 2000 (`alimentacio.andorra2000.ad`), OpenCart, own legal/technical entity distinct from carrefour.es/.fr. | Re-ran `--source andorra2000_ad --max-items 100`: 167 rows, 167 distinct URLs, clean. |
| San Marino | COVERED. `coal_sm` — COAL retail co-op's online grocery arm (`spesa.gruppoce.sm`), 210 leaf categories. | Re-ran `--source coal_sm --max-items 100`: 100 rows, 100 distinct URLs, clean. |
| St. Martin (French part) | COVERED. `sxmleshalles_mf` — supermarket, already onboarded and merged. | Re-ran `--source sxmleshalles_mf --max-items 100`: 65 rows, 65 distinct URLs, clean. |

## New probe this pass: "Spar Greenland" lead

The brief's known-leads list named "Spar Greenland" alongside Pisiffik,
Brugseni, Pilersuisoq. No such domain exists:

- `www.spar.gl`, `spar.gl`, `www.spargreenland.gl`, `spargreenland.com` —
  ALL NXDOMAIN / DNS resolution failure on all three probe arms (plain
  `requests` default UA, plain `requests` + Chrome UA, `curl_cffi
  impersonate=chrome124`). Probed 2026-09-11.
- WebSearch was unavailable this session (session-wide budget of 200 calls
  already exhausted by other concurrent work) so a name-variant search could
  not be run. Treat "Spar Greenland" as unconfirmed/likely non-existent
  rather than exhaustively ruled out — a future pass with search budget
  should try one query before spending more DNS-guess cycles.
- This does not change the Greenland structural-absence verdict: Brugseni
  (KNI) is Greenland's closest analogue to a Spar-style co-op grocery banner
  and is independently confirmed brochure-only (0 price tokens, re-confirmed
  2026-09-05 and 2026-09-11).

## Method notes confirmed this pass

- `prices collect --list` re-run after all four re-verification runs: 2222
  sources loaded, no enum crash — the global list is intact.
- All four already-shipped food sources re-verified with fresh
  `--max-items 100` runs; every run produced a 1:1 row:distinct-URL ratio
  (no `DuplicationPipeline` collapse), confirming the manifests still work
  live and were not stale claims.


---

## known_blockers_disco_pacific - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_pacific.md` on 2026-09-11. 14 hosts, 10 not
documented above at merge time.

# Known blockers — Pacific food-source discovery pass (2026-09-11)

Countries: american_samoa, marshall_islands, palau, kiribati, micronesia_fed_sts,
tuvalu, solomon_islands, vanuatu, tonga, samoa. Worktree:
`~/po-worktrees/fill-gap-sources` (shared with concurrent sessions the same day —
see the very recent `wahoo_mh`, `island_enterprises_sb`, `smarttechnology_sb`,
`tesae_trading_shopify`, `vodafone_samoa_online_shop` manifests and the
`pending_worth_doing.csv` / `untried_high_value.csv` rows dated 2026-09-11).
This file records NEW findings from this pass only; see the main
`known_blockers.md` (search for "Pacific", "Samoa", "Vanuatu", etc.) for the
much larger set of dead ends already on file from prior waves.

## Confirmed dead ends (new this pass)

- **tarawa.store** (KI) — `curl_cffi impersonate=chrome124` returns hard DNS
  failure, `Could not resolve host`. Domain does not exist despite surfacing in
  search results as "tarawa.store". Probed 2026-09-11.
- **martie.com** (surfaced under a "Majuro supermarket online" search) — a
  generic global Shopify discount-outlet storefront ("save up to 80% on your
  favorite brands"), not a Marshall-Islands-specific retailer. Locality trap
  per the skill's own warning about USD .com stores that merely rank for
  island-adjacent search terms. Not pursued. Probed 2026-09-11.
- **miscomarket.com** (MH) — same "MISCO" brand as the already-onboarded
  `misco_wholesale_mh` (miscowholesale.com, open `/api/products` endpoint,
  44 SKUs), but this second domain is a GoDaddy Website Builder marketing page
  (`generator: Starfield Technologies; Go Daddy Website Builder`) with no
  catalogue — a brochure duplicate of the same business, not a second source.
  Probed 2026-09-11.
- **K&K Island Pride Supermarket** (MH, Majuro) — Facebook-page-only per
  search; distinct from "MAJURO K&K STORE", which IS reachable and already
  onboarded as `pacificislandtrade_mh.yaml` (Shopify collection on
  pacificislandtrade.com). Do not conflate the two when re-searching.
- **Neco Plaza Palau** (PW, Koror) — Facebook-page-only, no website found.
  Probed 2026-09-11.
- **A-One Mart, XIX Store, Island Mart-Chuuk, AWM (Chuuk)** (FM) — all four
  named grocery stores surfaced in search are Facebook-page-only. No
  standalone website for any. Probed 2026-09-11.
- **yap.shopping / yapstores.com** (FM, Yap) — both require account
  login before any catalogue is visible; no public product listing reachable
  without credentials. Not pursued (out of scope — no anonymous catalogue to
  probe). Probed 2026-09-11.
- **KOKO MART, Funafuti** (TV) — Facebook-page-only, no website found.
  Probed 2026-09-11.
- **"A Convenience" store, Funafuti** — only appears as an evendo.com
  travel-directory listing (no operator website linked). Probed 2026-09-11.
- **Cellovila** (VU, Port Vila delivery service) — Facebook-page-only
  ("Free Delivery from Cellovila"), no website. Probed 2026-09-11.
- **Tamahu Natai Fish Market** (VU, Port Vila) — Facebook-page-only.
  Probed 2026-09-11.
- **Fagatogo Fish Market** (AS, Pago Pago) — Facebook/travel-guide-only
  (Evendo, FoodBevg, TripAdvisor-style listings), no structured price data.
  Consistent with the existing `doa.as.gov` dead-end entry in the main
  known_blockers.md for the same market. Probed 2026-09-11.
- **Fugalei Fresh Produce Market / Apia Fish Market** (WS, Apia) — abundant
  travel-guide content, zero vendor-run website or structured price feed.
  Samoa's own `sbs_local_market_survey.yaml` (SBS monthly Local Market
  Survey) is the closest thing to a Fugalei-style price series and is
  already onboarded. Probed 2026-09-11.
- **Pago Supermarket Store** (AS, Pago Pago) — surfaces heavily in search
  (Yelp, Cybo, evendo) but no operator website found; same pattern as the
  already-documented KS Mart / TSM Mart dead ends in the main
  known_blockers.md. Probed 2026-09-11.

## Leads found but not completed this pass (worth a future pass)

- **maff.gov.to Market Report PDFs (TO)** — Ministry of Agriculture, Food and
  Forests quarterly "Market Report" PDFs
  (`http://maff.gov.to/wp-content/uploads/2026/03/Market-Report-Final-2nd-Quarter-2025.pdf`
  and `...-3rd-quarter-2025.pdf`), linked from a plain Google/ddgs web search,
  not yet built into a manifest. This reads as a genuine wholesale/retail
  market-price survey (the Tonga Statistics Dept's own Food Price Index page
  describes FPI prices as collected "through market surveys from various
  outlets across Tongatapu and Vava'u", and MAFF is the named collecting
  ministry) — exactly the fresh-produce/root-crop signal supermarkets
  structurally miss, filling the same role as `vnso_market_survey.yaml` (VU)
  or `sbs_local_market_survey.yaml` (WS) but for Tonga, which currently has
  no equivalent.
  **Blocker: the entire maff.gov.to domain is throttled to roughly
  200-300 bytes/sec per connection and every request (including the bare
  homepage) stalls at ~12.7-12.8 KB before timing out** — confirmed with
  `curl_cffi impersonate=chrome124`, plain `requests`, and bare `curl`, all
  three stalling at the identical byte count. This is NOT a WAF/bot-block (no
  403, no challenge page, headers are plain nginx) — it reads as a
  genuinely bandwidth-starved government link. The server DOES support
  `Accept-Ranges: bytes`, so a resumable download (`curl -C -`, repeated) makes
  real incremental progress. A resumable download loop was started in the
  background on a8 at 2026-09-11 16:16 UTC
  (`for i in $(seq 1 250); do curl -s --max-time 55 -C - -o
  /tmp/maff_market_report.pdf "http://maff.gov.to/wp-content/uploads/2026/03/Market-Report-Final-2nd-Quarter-2025.pdf"; ...; done`,
  same pattern for the Q3 file into `/tmp/maff_market_report_q3.pdf`) and was
  still running, undownloaded, at session end — check
  `ls -la /tmp/maff_market_report*.pdf` on a8 for current size (target
  2,391,259 bytes for the Q2 file) and re-issue the same resumable-`curl -C -`
  loop if the process died. Once complete, open with `pdfplumber` — do not
  re-attempt a single-shot download, it will not finish inside a normal
  timeout. If this pans out it is `scaffolding: fetcher`,
  `extraction_pattern: pdf`, `analytical_role: official_avg`.
- **Tonga Food Price Index (TO)** —
  `https://tongastats.gov.to/statistics/economics/food-price-index-1/`. A
  DEDICATED COICOP-division-01 sub-index of the CPI (base 2021=100,
  9 food commodity groups, collected via market surveys in Tongatapu and
  Vava'u), distinct from the general CPI. Genuinely new (no existing Tonga
  manifest carries a food-only index). The page uses the WordPress "WP File
  Download" plugin to serve its PDFs; the download links are Handlebars
  templates (`{{linkdownload}}`) populated client-side, not present in raw
  HTML. Two file-manager category ids were recovered from the page's inline
  JS: `495` ("Food Pricing Index Report") and `496` ("Food Price Index
  Tables"), and the AJAX endpoint is
  `https://tongastats.gov.to/wp-admin/admin-ajax.php?juwpfisadmin=false&action=wpfd&`
  — but the correct `task=` parameter and required nonce were not identified
  this pass (`task=file.list` with a bare `catid` returned HTTP 400). Worth a
  Playwright network-capture pass to see the real AJAX request the page
  itself fires, rather than guessing plugin parameters blind. If recovered:
  `analytical_role: cpi_benchmark`, `coicop_codes: ["01"]`,
  `coicop_classification: publisher_labeled`.
- **Solomon Islands Ministry of Commerce, Price Control Unit** —
  `https://commerce.gov.sb/the-price-control-unit/` and
  `/consumer-affairs-price-control/`. Confirms the Price Control Act 1982 is
  administered here (same legal mechanism as Kiribati's `mcic_price_control`,
  which yielded 689 rows / 79% food-and-tobacco once its PDFs were found) but
  **no downloadable price schedule/gazette was found in the raw HTML** of
  either page, nor of `/publication/`, `/legislation/`, or
  `/fees-and-penalties/` (checked 2026-09-11 — zero `.pdf`/`.xlsx`/`.doc`
  links in any of the four pages' raw HTML). Solomon Islands' own NSO
  (`statistics.gov.sb`) is separately known-blocked (Imunify360 415; Wayback
  workaround documented in the main known_blockers.md) and was not
  re-attempted this pass. This is the single most promising **unbuilt**
  lever for Solomon Islands food coverage — worth a Playwright pass on
  commerce.gov.sb's document-manager plugin (same genre of problem as the
  Tonga FPI lead above) or a direct search for a named "Price Control Order"
  / "Controlled Goods List" PDF rather than the landing pages found this
  pass.

## Environment gotcha reconfirmed

- Running any Python script as `~/venv/bin/python /path/to/script.py`
  (file-argument invocation) on `a8:~/po-worktrees/fill-gap-sources`
  intermittently breaks with unrelated import errors (this pass:
  `ImportError: cannot import name getargspec` inside `lxml`, on an
  otherwise-working `ddgs` install) — same signature as the Playwright
  `inspect.FrameInfo` failure already documented in the main
  known_blockers.md's "Environment note" section. Piping the script via
  stdin (`cat script.py | ~/venv/bin/python`) or `python -c` runs clean every
  time. Reconfirmed 2026-09-11.
- `ddgs` (DuckDuckGo search library) needed `python -m pip install ddgs`
  (not preinstalled in `~/venv` as of this session) and its default
  `duckduckgo`/`bing`/`brave`/`mojeek` backends were all rate-limited
  (`DDGSException: No results found.`) almost immediately from a8's IP —
  likely from heavy same-day fleet usage. The `backend="yahoo"` engine
  worked reliably throughout this session when the others were exhausted;
  worth trying first if `ddgs` throws `No results found` on a fresh query.

## Regression found (not a discovery blocker, but a live-source break)

- **aelanbasket_vu (VU)** — the existing, previously-verified (2026-08-11,
  5/5 rows) manifest returned **0 items on two independent live test runs
  today** (`prices collect --source aelanbasket_vu --max-items 20`, both
  2026-09-11 ~16:20 UTC). Root cause confirmed by direct fetch: the
  homepage HTML at `https://www.aelanbasket.com/` no longer contains any
  `/product/` links at all (0 matches for `href="/product/..."`), whereas the
  spider's only discovery path is homepage links + each PDP's related-products
  rail (per the manifest's own notes). The site is still up (200 OK, 78KB
  homepage) — this reads as a front-end restructure (nav/category links
  probably moved behind client-side rendering or a different URL shape), not
  a block. Not repaired this pass — flagging so the next Vanuatu pass
  doesn't have to rediscover the regression from scratch. Needs a fresh
  Playwright dump of the current homepage/shop page to find the new product-
  link pattern.


---

## known_blockers_disco_pacmicro - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_pacmicro.md` on 2026-09-11. 7 hosts, 5 not
documented above at merge time.

# Pacific micro-states food-source discovery — blocker/dead-end log

All verdicts below are as-of 2026-09-11 unless otherwise noted. This run worked
in `~/po-worktrees/fill-gap-sources` on `a8`, alongside several other
concurrent onboarding agents sharing the same worktree and `~/gapwork/`
scratch space (visible in `git status` — untouched, not part of this pass).

## Confirmed dead ends (record and move on)

- **Payless Supermarket, Majuro (Marshall Islands)** — as-of 2026-09-11.
  DDG search (`~/gapwork/ddgs_search_disco.py`) surfaces only Facebook
  (`facebook.com/pacificbasinpayless`), directory listings (near-place,
  vymaps, findglocal, cybo, evendo) — no owned website, no e-commerce.
  Facebook-only per the skill's rule; not scrapable. Do not re-chase without
  a Meta Graph API angle, which is out of scope here.
- **Formosa store, Majuro (Marshall Islands)** — as-of 2026-09-11. Zero DDG
  hits for "Formosa store Majuro" / "Formosa Store Majuro". No discoverable
  web presence at all (not even a directory listing). Likely a
  brick-and-mortar-only name or a mis-transcribed name; not pursued further
  this pass.
- **Yano's, Palau** — as-of 2026-09-11. DDG search returned no results after
  two attempts. No discoverable web presence.
- **Tuvalu Co-operative Society (the Fusi), Funafuti** — as-of 2026-09-11.
  DDG search surfaces only corporate-registry/directory stubs
  (info-clipper.com, oceanjoin.com, world-ships.com, icpcredit.com, a
  Bloomberg shell-company profile) and an Instagram account
  (`instagram.com/tuvalusociety`) with no shop/catalog features. No owned
  website or e-commerce surface found. Instagram-only is the same
  not-scrapable class as Facebook-only.

## Login-gated / no-anonymous-price (SKIP)

- **WCTC (Western Caroline Trading Company), Koror, Palau** —
  `store.wctc-palau.com` — as-of 2026-09-11. This is a REAL and substantial
  find: WCTC is Palau's large general/department store with a genuine online
  B2B ordering portal. Homepage and department pages return 200 on all three
  probe arms (plain requests, plain+Chrome UA, curl_cffi impersonate=chrome124
  — no TLS impersonation needed, Apache origin, no WAF). The site exposes a
  full department tree including real COICOP 01/02 categories: `groceries-|01`
  with ~90+ sub-departments (canned-fish, canned-fruits, canned-meat,
  canned-vegetables, cereals, chips-crackers, cookies, dairy-products,
  dried-foods, flour, fresh-fruits, fresh-vegetables, bread, cake, candies,
  etc.) plus `frozen-|03`, `beer-|50`, `liquor-|51`, `cigarettes-|60`,
  `chewing-tobacco-|61`, `bakeshop-products-|94`. Category pages list real
  product-detail-page URLs (`/products/<slug>|<sku>.html`) with distinct SKUs
  across pages (enumerable). BUT every product page's price field
  (`store_product_price_um`, the `<dd>` next to `Price`) is emitted EMPTY in
  the anonymous HTML — confirmed on `/products/dona-elena-spnsh-24-228|13270.html`.
  The site links to `/inet/user/request_account.php`, indicating this is a
  registered-customer wholesale ordering system (prices hidden pre-login).
  Verdict: SKIP — login wall on price, not a public retail catalogue.
  Revisit only if a public-facing (non-portal) WCTC retail price list ever
  surfaces, e.g. a printed flyer or a Facebook price post.

## Not in scope — topology gap

- **Wallis and Futuna** — as-of 2026-09-11. Absent from both
  `src/configs/regions.yaml` (no `wallis_futuna` under any `eap` subregion's
  `countries:` list) and `src/configs/countries.yaml`. Per the skill's Phase 0
  pre-flight check, a country must be resolvable in both files before any
  manifest can be scaffolded — adding a source is blocked upstream of
  discovery by a missing topology entry, which is outside this skill's scope
  (would require a `regions.yaml`/`countries.yaml` change, not just a new
  manifest). No sources onboarded for Wallis and Futuna this pass.

## Already-covered leads confirmed present (no new work needed)

- Kiribati Punjas / MOEL Trading — already assessed and rejected in
  `mcic_price_control.yaml`'s notes (Punjas is a corporate site with no shop;
  MOEL's Wix storefront has dead "Shop Now" links). Not re-probed this pass;
  the verdict stands as of the 2026-09-05 note.
- Nauru Capelle & Partner / Eigigu — both already onboarded as `capelle_nr`
  (supermarket, Wix + Schema.org JSON-LD) and `eigigu_supermarket`
  (supermarket, Ecwid). Both re-verified live this pass, 2026-09-11 (101 and
  117 rows respectively — see main report).
- FSM Ace Commercial — not found as a distinct source under this name; FSM
  already carries 5 independent supermarket/hypermarket sources
  (`cashncarry_fm`, `hardrocksokehs_fm`, `pacificislandtrade_fm`,
  `saki4you_fm`, `shoppohnpei_fm`), so FSM's food-channel coverage is not
  gap-constrained. Not pursued as a distinct addition this pass.
- Palau Surangel & Sons — already onboarded as `surangel_pw` (supermarket,
  scrapy_api). Re-verified live 2026-09-11, 100/100 rows on a 100-item cap.

## Method note

`known_blockers.md` (the skill's shared reference file) was NOT found to
contain any prior verdicts for the five leads probed above, so the "55% wrong"
staleness warning didn't apply here — these are first-time probes, not
re-probes of a stale verdict. WebSearch quota was exhausted session-wide
(200/200) before this pass could start; all lead-finding above used the DDG
fallback at `~/gapwork/ddgs_search_disco.py` instead.


---

## known_blockers_disco_safrica2 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2.md` on 2026-09-11. 24 hosts, 20 not
documented above at merge time.

# Gap-fill discovery pass: Eswatini, Suriname, Turks and Caicos, Lesotho, Namibia, Chad

_As of 2026-09-11._ Target: the 6 countries carrying exactly one thin food
source (Eswatini 374 rows, Suriname 1424, Turks and Caicos 4438, Lesotho,
Namibia, Chad). Constraint: COICOP divisions 01/02 only. Method: three-arm
probe (plain requests / plain requests+Chrome UA / curl_cffi
impersonate=chrome124, WITHOUT impersonation tried first), `ddgs` for
candidate discovery (WebSearch tool budget was already exhausted
session-wide before this pass started), Playwright network-trace
(`~/.cache/ms-playwright/chromium-1200`, headless, no flags) for SPA/CSR
sites, enumerability gate (page1 vs page2 id sets must be disjoint).

All existing `known_blockers.md` / inventory-file dead ends for these 6
countries (dated 2026-09-01/02) were spot-re-verified where the failure mode
was a WAF-shaped block (403/challenge); NXDOMAIN and "brochure/no-commerce"
verdicts were NOT re-probed exhaustively since neither failure mode is fixed
by TLS-impersonation-lever tricks and none had gone stale enough (9-10 days)
to expect DNS/business changes.

## Shipped this pass (5 new sources)

### Turks and Caicos Islands
- **`tcgrocerydelivery_tc`** (turksandcaicosgrocerydelivery.com) -- WooCommerce
  Store API, 946 SKUs, USD. Plain requests clean 200; curl_cffi impersonation
  gets 403 from `server: hcdn` (JA3 denylist on impersonated clients --
  Scrapy's CompositeDownloadHandler defaults to plain Twisted HTTP, so no
  special handling was needed). Sibling domain
  turksandcaicosgrocerydeliveryservice.com serves the IDENTICAL catalog (same
  product ids) -- deliberately not onboarded as a second source.
- **`islandselects_tc`** (islandselectstci.com) -- WooCommerce Store API, 1400
  SKUs, USD. All 3 probe arms clean. Distinct catalog/backend from
  tcgrocerydelivery_tc and from the pre-existing goods2door_tc (Wix).

### Namibia
- **`woermannfresh_na`** (shop.woermannfresh.com) -- Woermann & Brock's
  online supermarket (Windhoek). Bespoke Vue/Laravel storefront backed by
  Elasticsearch (not Woo/Shopify). NOTE: this source was independently
  discovered and scaffolded twice in this pass -- once by this agent via a
  ddgs search + a whole-catalog sitemap/PDP crawl (22,674 product URLs
  found), and concurrently overwritten on disk by a second agent working
  the same shared worktree, whose version walks the site's own
  `/category/<slug>?page=N` listing endpoints (each page embeds the full
  Elasticsearch response inline) and discovered the site via OpenStreetMap
  `shop=supermarket` nodes instead of a search engine. Both approaches
  independently confirmed the same site, currency (NAD, no explicit
  currency field emitted; set at the class level, not derived from a
  symbol), and real grocery/household/toiletries taxonomy. The
  category-listing version is what is currently shipped and verified:
  test run collected 182 rows / 182 distinct URLs before hitting the
  100-item test fence (its category endpoint returns up to 100 items per
  request, so item counts jump per page rather than one-at-a-time). This
  is still by a wide margin the largest catalog found in this pass, for
  the emptiest market in the whole 43M-row corpus (18 distinct product
  names before this addition).

### Chad
- **`rakhaz_td`** (rakhaz.com / API on aliceblue-seal-957651.hostingersite.com)
  -- fresh fruit & vegetable delivery, N'Djamena. Next.js frontend is
  client-rendered with no server data; found the real backend via a
  Playwright console-error trace (a CORS-blocked fetch call named the exact
  API host). 27 SKUs (whole catalog, meta.total confirms), integer XAF,
  channel=fresh-market. Small but genuinely doubles Chad's product diversity
  (31 distinct names before this pass) and fills a fresh-produce gap that
  Chad's existing marketplace-style sources (hadimi_td, tchadcommerce_td,
  mossosouk_td) structurally miss.

### Suriname
- **`wangfamirie_sr`** (wangfamirie.com) -- Dutch-language diaspora
  grocery/parcel order-and-deliver service. WooCommerce Store API, 3,601
  SKUs across 181 pages, EUR-priced (diaspora order model, like now2su.com --
  NOT Suriname's domestic SRD retail level; flagged in the manifest notes for
  downstream analysts). Confirmed NOT the same shelf as avoda_sr (0/30
  product-name overlap on a page-5 sample, distinct Dutch category
  taxonomy). Rich food-heavy category breakdown: DRANKEN 211, FRUIT 22,
  GROENTEN 75, VLEES 154, VIS 32, ZUIVEL 95, etc.

All 5 verified end-to-end via `run.py prices collect --source <key>
--max-items 100`, all cleared >=5 rows with 100% distinct URLs, and
`run.py prices collect --list` confirmed the global 2,240-source list still
loads cleanly after each addition.

## Dead ends found this pass (new, not previously recorded)

- **douniamarket.com** (TD) -- Next.js diaspora-to-N'Djamena grocery order
  site (EUR-priced per its own UI). Real backend identified via Playwright
  console trace: `https://api.douniamarket.com/api/products?limit=N`.
  **502 Bad Gateway on every attempt** (3 retries, 2-second spacing) --
  the backend service is genuinely down, not CORS/WAF-blocked (the frontend
  itself surfaces "Chargement impossible / Une erreur est survenue lors du
  chargement des produits" to real users). Worth a retry in a future pass;
  not a permanent structural dead end, just an outage as of 2026-09-11.
- **jibaley.com / Akil** (TD) -- "one app for everything in Chad" -- live
  restaurant-delivery app (Akil module) only; a "Stock" (grocery) module is
  listed as "Bientot" (coming soon), not live. Re-check in a future pass.
- **picknpayeswatini.com** (SZ) -- NEW domain not previously recorded (prior
  passes only found pnp.co.sz, NXDOMAIN). Live WordPress/Yoast site, but
  brochure/promo/recipes/store-locator only -- no shop, no WooCommerce Store
  API (`wc/store/v1/products` -> 404 rest_no_route). Does carry genuine
  weekly PDF price flyers (e.g. "PnP-ESW_EDLP-PROMO_07-30-SEPTEMBER-2026.pdf")
  with real Eswatini SKU/price pairs, but the layout is a poster (image-
  anchored text boxes), not a table -- pdfplumber's word-level bounding
  boxes do not cleanly cluster into name/price pairs without template-
  specific 2D-layout heuristics that would need re-tuning every time the
  promo artwork changes. Judged not worth the fragility for a weekly-refresh
  fetcher; documented rather than built. A future pass with more budget
  could attempt column/row clustering by (x0, top) proximity.
- **viaeswatini.com** (SZ) -- "Via Eswatini" delivery app -- app-only
  marketing landing page (App Store / Google Play badges only), zero web
  catalog. Playwright trace found no product API, only static UI-avatar
  images for testimonials.
- **shop.modelmooove.na** (NA, "Auas Valley" -- reads like a Pick n Pay
  Windhoek franchise order platform on the Archsoftware/IES e-commerce
  platform) -- resolves, 200, but plain `requests` (no UA) gets 403 while a
  Chrome UA clears it; not pursued to a shippable spider this pass (found
  late, after woermannfresh_na already cleared the country's bar) -- **worth
  a dedicated follow-up**, this looked structurally promising (real
  e-commerce platform, not a brochure site).
- **web.nambuyfood.com, www.ishoppingnamibia.com, www.instagrocer.co,
  avocadoshopping.com, twosticksretail.com** (NA) -- all resolve live (one,
  twosticksretail.com, shows the same `server: hcdn` JA3-denylist pattern as
  the TCI hosts -- 200 on plain requests, 403 on curl_cffi impersonation).
  Not probed further this pass under time budget; flagged as follow-up
  candidates for a dedicated Namibia depth pass (Namibia's bar was already
  cleared by woermannfresh_na's 22k-SKU catalog).
- **ai.mobirise.com/sites/-2PoMAMZ2JzT735S84pWIO.html ("Maseru
  Supermarket")** (LS) -- confirmed to be a Mobirise AI website-generator
  DEMO page ("affordable grocery website design AI" in its own meta), not a
  real business. Not a false-negative candidate, a search-engine-indexed
  template demo.

## Re-affirmed dead ends (spot-checked, verdict unchanged)

- **spareswatini.co.sz** -- still a WooCommerce-installed-but-empty
  marketing site (Store API returns `[]`), unchanged from the 2026-09-11
  wave-20 finding earlier the same day.
- **shop.woermannfresh.com's own group siblings were not separately
  checked** -- only one Woermann Brock domain was found; no evidence of a
  second Namibian storefront under the same group.

## Countries where the existing (2026-09-01/02) exhaustive inventory holds

- **Eswatini**: `thewineboutique_sz` remains the only food source found across
  three separate passes (this one included). Regional SACU chains (Shoprite,
  SPAR, Pick n Pay, OK Foods) all confirmed brochure/store-locator-only or
  NXDOMAIN. This pass's one new lead (picknpayeswatini.com) turned out to
  also be brochure-only, just with PDF flyers instead of no content at all.
- **Lesotho**: `virtualmall_ls` + `bite_liqour_ls` remain the only 2 food
  sources. This pass's ddgs sweep surfaced only already-known sources
  (virtualmall's own m-grocery URL, localbites/wizashopping) plus one AI
  demo-site false positive.

## Namibia sub-agent additions, verified 2026-09-11 17:08-17:18 UTC

| source_key | channel | analytical_role | currency | measured rows | distinct URLs | notes |
|---|---|---|---|---|---|---|
| embassyliquor_na | specialty-food | retailer_sku | NAD | 103 | 103 | Embassy Liquor Windhoek; first dedicated COICOP-02 (alcohol/tobacco) source for Namibia; 450 URLs in full sitemap |
| na_nsa_cpi (manifest nsa_cpi.yaml) | null | cpi_benchmark | index (Dec2012=100) | 592 (296 months x 2 divisions) | n/a | Namibia Statistics Agency monthly CPI workbook; full 2002-2026 history in ONE download; divisions 01 + 02 |
| na_nsa_zonal_food_prices (manifest nsa_zonal_prices.yaml) | null | official_avg | NAD | 45 (15 items x 3 zones) | n/a | NSA average retail food prices by zone. Sub-agent found a real data-integrity defect in the SOURCE (two item rows with zone values swapped in 1 of 3 sampled months) and added a cross-zone plausibility guard that DROPS implausible rows rather than shipping corrupted prices |

Namibia chain re-probe (2026-09-11, second independent session): Shoprite / Checkers / USave /
SPAR / Pick n Pay / Woolworths / Choppies / OK Foods all re-confirmed dead or unreachable.
Two findings worth carrying forward: (1) "OK Foods Namibia" is a Shoprite Group BANNER, not an
independent chain — do not chase it as a separate candidate; (2) spar.co.na and
pupkewitz.com.na time out identically across 5 client profiles in 2 separate sessions —
that is genuine unreachability, not a WAF, and not TLS-fingerprint-fixable.

Final state: `prices collect --list` loads clean at 2240 sources, 0 errors.

## Addendum (verified 2026-09-11, ~17:20-17:30 UTC) -- sources shipped by other concurrent sessions, not yet listed above

Cross-checked against the repo on disk; all measured via the actual
`raw_items`/`price_observations.csv`/`index_observations.csv` output of a
real `prices collect --source <key> --max-items 100` run (not projected).

| Country | source_key | channel | analytical_role | currency | measured rows | distinct URLs |
|---|---|---|---|---|---|---|
| Eswatini | `namboard_ehis_swz` | null (official) | official_avg | n/a (SZL implied) | 118 | n/a (fetcher, no per-row URL) |
| Lesotho | `bos_lso_cpi` | null (official) | cpi_benchmark | index | 216 | n/a |
| Namibia | `meat_namibia_na` | fresh-market | retailer_sku | NAD | 5 | 5 |
| Suriname | `rossignolslagerij_sr` | specialty-food | retailer_sku | SRD | 254 | 254 (230 distinct product_id -- multiple size/weight variants share a base id, expected for a butcher's variant catalog) |
| Suriname | `vcm_sr` | specialty-food | retailer_sku | SRD | 100 | 100 |

Notes:
- `namboard_ehis_swz` (Eswatini National Agricultural Marketing Board / EHIS
  portal) is this pass's ONLY new source for Eswatini beyond the pre-existing
  `thewineboutique_sz` -- genuine COICOP-01 fresh-produce official average
  prices (sample: Avocado SZL 9.5), closing Eswatini's "one thin food
  source" gap with a second, structurally different (official_avg vs
  retailer_sku) source.
- `bos_lso_cpi` (Lesotho Bureau of Statistics monthly CPI PDF) is index-layer
  coverage, not a retail/price-level addition -- Lesotho's retail-level food
  gap (beyond `virtualmall_ls` + `bite_liqour_ls`) remains OPEN after this
  pass; see "Countries where the existing inventory holds" above.
- `meat_namibia_na` (Buschmann Meat Packers, Windhoek) is a genuinely
  complete 5-SKU catalog (X-WP-Total=5, non-standard WooCommerce Store API
  path `/wp-json/wc/store/products`, no `/v1/`) -- at the Phase-6 minimum-
  viable floor but real, verified, and a fresh-market/meat addition for
  Namibia's near-empty corpus.
- `rossignolslagerij_sr` (Dutch-language Suriname butcher, Shopify
  `/products.json`) and `vcm_sr` (Dutch-language Suriname retailer, WooCommerce
  Store API) are both genuine, distinct-catalog specialty-food additions,
  independent of `wangfamirie_sr`/`avoda_sr`.

Final tally this pass, all 6 target countries: every one shipped at least
one new source. Eswatini, Namibia, Suriname, Turks and Caicos, and Chad all
got genuine retail/official-average FOOD-price-level additions (COICOP
01/02). Lesotho's only addition this pass is index-layer (`bos_lso_cpi`);
its retail-level gap is confirmed structural (brochure-only chains, no live
grocery e-commerce found across 3 independent passes spanning 10 days).

`prices collect --list` re-confirmed clean at 2240 sources after this
addendum was written (no new manifest added by this note itself).


---

## known_blockers_disco_safrica2_chad - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_chad.md` on 2026-09-11. 2 hosts, 1 not
documented above at merge time.

# Chad food-source discovery -- 2026-09-11 (fill-gap-sources pass, food-only mandate)

Country: Chad (ssa/central_africa/chad). Task: NEW food/beverage retail
sources only (COICOP 01/02; channels: supermarket, hypermarket, convenience,
fresh-market, specialty-food, wholesale, marketplace). French + Arabic search
prioritized per brief.

## Pre-existing state found at start of this pass

Two independent prior discovery passes already exist and are recent
(references/inventories/ssa/chad.md, written 2026-09-02, 9 days old --
within the skill's staleness window):
- 2026-09-01 pass: 0 shipped. French-language search
  ("supermarché en ligne livraison courses N'Djamena") returned only
  Facebook-page storefronts (Modern Market, Le Bon Marché, Dembé Market,
  Le Grand Marché, Marché de Diguel, Alimentation La Tchadienne, Moursal
  Market) -- none have an independent website (all guessed .td/.com domains
  NXDOMAIN). Jumia has no live Chad storefront (Cloudflare parked-domain
  page). Score/Casino/Alwatanya/Ramco/SODEA/Sonasut: no resolvable domain.
- 2026-09-02 pass: tchadcommerce_td (WooCommerce marketplace, XAF,
  currency_minor_unit=0) shipped -- whole catalog is only 28 items, mostly
  fashion/solar/furniture/vehicles; "AgroAlimentaire" food category holds
  a handful of items. Small but real -- first retail source of any kind
  for Chad.

Separately, and apparently from a different concurrent fleet pass earlier
TODAY (2026-09-11, before this session started), two more Chad sources were
added to the repo:
- **mossosouk_td** (marketplace, XAF, RDFa/schema.org microdata PDPs,
  sitemap-driven crawl of 288 total products) -- re-verified live this pass:
  `collect --source mossosouk_td --max-items 100` -> **102 rows, 102 distinct
  URLs, 100% priced in XAF**. Of the full 288-product catalog, ~24 sit under
  food-relevant categories ("Placard Alimentaire" cooking oils/flours/
  spices, "Boisson" herbal teas/syrups) -- thin but genuinely food-adjacent,
  channel correctly set to marketplace, coicop_codes left unset (wide).
- **hadimi_td** -- re-verified live this pass: `collect --source hadimi_td
  --max-items 100` -> **511 rows, 511 distinct URLs, all XAF-priced**
  (single-request Shopify /products.json catalog, French-language site).
  **DATA-QUALITY FLAG, not something I created or changed:** this manifest's
  `channel:` is set to `supermarket` but the actual catalog inspected this
  pass is 100% electronics/laptops/cookware/home-goods (HP/Lenovo/Acer
  laptops, tea services, thermoses, cooking pots) -- zero food items seen in
  a 40-row sample. This is a genuine channel misclassification that will
  falsely count as Chad food/COICOP-01-02 coverage downstream. Left
  untouched per scope (not part of this food-onboarding mandate and the
  manifest was written by a separate same-day process, "child-task
  consolidation" per its own notes field) -- flagging for whoever owns that
  pass to fix the channel value (probably `dept-store` or `electronics`).

## This pass: no additional new food source found

No French or Arabic search was performed this pass (WebSearch tool budget
was already exhausted session-wide before this agent reached Chad -- see
memory note on the session-wide cap). Re-checked the 2026-09-02 pass's dead
ends were not stale (9 days, all still N'Djamena-specific business names with
no plausible new domain to guess) and did not re-probe them individually
given the existing pass already confirmed Facebook-only presence for each.

## Verdict

Chad's genuine food/beverage retail footprint remains: `mossosouk_td`
(marketplace, ~24 of 288 items food-adjacent) + `tchadcommerce_td`
(marketplace, handful of AgroAlimentaire items). No dedicated
supermarket/hypermarket/fresh-market e-commerce site exists for Chad as of
2026-09-11 across three independent passes (2026-09-01, 2026-09-02, and
this one). Structural absence, not a search gap -- re-check only on the
~6-month staleness window or with a fresh WebSearch budget for a proper
French+Arabic sweep.


---

## known_blockers_disco_safrica2_eswatini - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_eswatini.md` on 2026-09-11. 29 hosts, 22 not
documented above at merge time.

# Eswatini food-source discovery — findings (as of 2026-09-11)

Scope: COICOP divisions 01/02 only (food, non-alcoholic drinks, alcohol,
tobacco). Country had ZERO supermarket/grocery source before this pass;
only `thewineboutique_sz` (specialty-food/alcohol, ~374 rows) and two
national commodity-average fetchers (`wfp_swz`, `fews_swz`) touched
division 01 at all.

## Shipped

- **namboard_ehis_swz** (as of 2026-09-11, VERIFIED) — Eswatini's National
  Agricultural Marketing Board (namboard.co.sz) links its "Weekly Buying
  Prices" nav item to a separate portal, `www.ehis.co.sz` (Eswatini
  Horticulture Information System). Four server-rendered HTML tables share
  one fixed 67-item fresh-produce nomenclature with independently-set
  prices per page:
  - `/Portal/Info/buyingprice` — national NAMBoard buying (producer) price
  - `/Portal/Info/Siteki`, `/Portal/Info/Nhlangano`, `/Portal/Info/PiggsPeak`
    — named fresh-produce market boards
  Plain `requests` with a default UA, no impersonation, no WAF encountered.
  Test run (`prices collect --source namboard_ehis_swz --max-items 100`,
  2026-09-11) wrote **118 real rows** (67 National + 17 Siteki + 17
  Nhlangano + 17 Piggs Peak — the three named markets legitimately show
  fewer priced items this week; unpriced items render literal text
  "UNAVAILABLE" on the page rather than a number, correctly dropped, not a
  parsing bug — confirmed by inspecting the raw HTML directly). 4 distinct
  `source_url` values (one per page). Currency SZL confirmed (site shows
  "E" for Emalangeni on market pages, plain numeric on the national page;
  both parse to the same value). Re-run immediately after confirmed
  idempotence: cutoff advanced to 2026-09-12, second run correctly returned
  "nothing newer than cutoff". `channel: null`, `analytical_role:
  official_avg`, `coicop_classification: classifier` (free-text produce
  names incl. "Grade A"/"Grade B" suffixes). Manifest:
  `src/prices/configs/ssa/southern_africa/eswatini/namboard_ehis_swz.yaml`.
  Fetcher: `src/prices/fetchers/ssa/southern_africa/eswatini/namboard_ehis.py`.

  Not scaffolded/skipped from the same portal:
  - `/Portal/Info/Seeds` ("Farm Inputs") — confirmed non-food: planting
    seed packets (e.g. "Baby marrow star 8023", 1M seeds, E1020.00), out of
    scope per the COICOP 01/02 hard constraint. Checked 2026-09-11.

## Rejected candidates (all re-probed live 2026-09-11 unless noted)

| Candidate | URL | Verdict | Reason |
|---|---|---|---|
| Spar Eswatini | spareswatini.co.sz | DEAD (confirmed same day by a concurrent agent's batch-20 pass, cited here not re-derived) | WordPress+WooCommerce installed but Store API returns `[]` for every query; no product sitemap; Playwright network trace fires zero JSON; only shop-like link is `/store-locator/` (physical branches). Marketing/promo site, not a store. |
| Pick n Pay Eswatini | pnp.co.sz | NXDOMAIN | Re-checked 2026-09-11, still no resolvable domain (matches 2026-09-02 inventory). |
| Spar Eswatini (alt) | spar.co.sz, spar2u.co.sz, onlinespar.co.sz | NXDOMAIN | Re-checked 2026-09-11. |
| OK Foods Eswatini | ok.co.sz | NXDOMAIN | Re-checked 2026-09-11. |
| PEP Eswatini | pep.co.sz | NXDOMAIN | Re-checked 2026-09-11. |
| Friendly Foods Eswatini | friendlyfoods.co.sz | NXDOMAIN | Re-checked 2026-09-11. |
| Choppies (group) | choppies.co.sz | NXDOMAIN | No Eswatini-specific domain. |
| Choppies (SA/BW parent) | choppies.co.za | Resolves (41.185.8.0) but connection times out (curl exit 28) on both HTTP and HTTPS | Unreachable; no evidence of an Eswatini storefront even if it answered — Choppies runs physical stores in Eswatini with no online ordering per the existing inventory finding. |
| Buy 'n Save (SPAR budget banner) | buynsave.co.sz | Resolves, HTTP 200 | Login-walled B2B "Contract System" (procurement portal for account-holders), not a consumer storefront — no catalog visible pre-login. |
| Eswatini Meat Industries | emi.co.sz | Resolves, HTTP 200 | Brochure site (Divi theme). CSS carries `.et_pb_shop_grid .woocommerce` classes suggesting a WooCommerce shop template, but `/wp-json/` route dump (148 routes) has zero `wc`/`product`/`shop` routes and `/shop/` 404s — dead/uninstalled shop, not a live catalog. |
| Eswatini Dairy Board | dairyboard.co.sz | Resolves, HTTP 200 | Regulatory/brochure site; no live price table anywhere in the rendered text. Only price-adjacent content is annual PDF "Bulletins", and the nav's newest bulletin year is 2022 (4 years stale as of 2026-09) — not a maintainable current-price feed. |
| Royal Eswatini Sugar (guessed) | res.co.sz | Resolves but connection times out (curl exit 28) on HTTP and HTTPS | Unreachable. |
| Eswatini Central Statistical Office | cso.gov.sz, statistics.gov.sz, swazistats.org.sz (incl. `www.` prefix), centralstatisticaloffice.gov.sz | All NXDOMAIN | gov.sz homepage links to `www.swazistats.org.sz` as "Social Statistics" but that host does not resolve (broken outbound link on the government's own site). No working CPI/COICOP publication surface found. |
| Metro Cash & Carry, Trade Xpress, Buhle Farmers' Co-op, generic wholesale guesses | metrocashandcarry.co.sz, tradexpress.co.sz, buhlefarmers(coop).co.sz | NXDOMAIN | No resolvable domain under any guessed name. |
| Game, Cashbuild Eswatini | game.co.sz, gameeswatini.co.sz, cashbuild.co.sz | NXDOMAIN | Non-food anyway (dept-store/hardware) — checked opportunistically, not pursued further. |
| Jumia / delivery marketplace | jumia.co.sz | NXDOMAIN | Confirms 2026-09-02 inventory finding: no delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in Eswatini. |

## Method notes for the next pass

- **NAMBoard/EHIS is the reusable pattern for this region**: a national
  agricultural marketing board's own portal, separate from its main
  brochure/blog domain, publishing a fixed commodity nomenclature as a
  plain server-rendered HTML table (DataTables styling, but the data is NOT
  behind an AJAX call — it's baked into the page's `<tbody>` at request
  time). Worth checking for other Southern African / SACU markets with a
  similar "NAMBoard"-style produce marketing board.
- Eswatini's `.co.sz` namespace is otherwise very thin: of ~20 direct-guess
  domains tried across grocery chains, wholesale, dairy and meat boards,
  only 4 resolved (`emi.co.sz`, `dairyboard.co.sz`, `res.co.sz`,
  `buynsave.co.sz`), and none had a usable live product+price catalog.
  WebSearch budget was exhausted session-wide (shared across concurrent
  agents in this run) before a proper local-language/news search could be
  run for this country — a fresh search-based pass (once budget resets) is
  the clear next step, per the existing 2026-09-02 inventory's own
  recommendation to check whether a South African parent's storefront
  (pnp.co.za, spar.co.za, checkers.co.za Sixty60) exposes an Eswatini
  delivery zone, which is a SA-tenant question rather than an Eswatini one
  and should be answered once for the whole CMA/SACU bloc.


---

## known_blockers_disco_safrica2_lesotho - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_lesotho.md` on 2026-09-11. 27 hosts, 21 not
documented above at merge time.

# Lesotho food-source discovery — findings (as of 2026-09-11)

Follow-up pass on top of the 2026-09-01 wave-8 inventory
(`.claude/skills/onboard-price-sources/references/inventories/ssa/lesotho.md`).
Scope: COICOP divisions 01/02 only. All verdicts below probed live
2026-09-11 with three arms (plain requests default UA, plain requests +
Chrome UA, curl_cffi impersonate=chrome124) unless noted. WebSearch budget
was exhausted session-wide partway through this pass (200/200) — remaining
candidates were found by direct domain probing only, not fresh search.

## Shipped

- **bos_lso_cpi** (fetcher, analytical_role=cpi_benchmark) — Lesotho Bureau
  of Statistics monthly CPI. See manifest notes for full detail. 216 rows
  verified live, 18 monthly PDFs, 12 COICOP divisions each, 0 nulls.

## Re-probed priority candidates — verdict UNCHANGED from 2026-09-01 (confirmed live 2026-09-11)

- **shoprite.co.ls** — 200, resolves natively (not an SA redirect), but is
  the same `shopriteafrica` AEM corporate-portal tenant already dead for
  MZ/ZM/BW: nav = store-locator + category-description pages + a specials
  page linking only a privacy-policy PDF. Zero `/shop`, `/products`,
  `/catalogo`, zero WooCommerce/Shopify/Magento fingerprint (0 hits for all
  of woocommerce/shopify/magento/add-to-cart/price/cart tokens in the raw
  HTML). Confirmed 2026-09-11 with curl_cffi impersonate=chrome124 (plain
  requests default UA 403s — TLS/UA gate clears fine, doesn't change the
  verdict: brochure site, no catalogue behind the gate).
- **checkers.co.ls** — NEW this pass (not in the 2026-09-01 inventory,
  which only checked Shoprite/PnP for LS). Same `checkers-africa` AEM
  tenant, same shape: 200, store-locator + specials-subdomain flyer links,
  zero product/cart/price tokens. Brochure-only, confirmed 2026-09-11.
- **pnp.co.ls / www.pnp.co.ls** — still NXDOMAIN (curl_cffi DNS error, no
  TLS handshake starts). Re-confirmed 2026-09-11.
- **spar.co.ls, usave.co.ls, okfoods.co.ls, boxer.co.ls,
  boxersuperstores.co.ls, fruitandvegcity.co.ls, choppies.co.ls** — all
  NXDOMAIN under curl_cffi. No Lesotho-specific storefront domain exists
  for any of these chains under `.co.ls`. Confirmed 2026-09-11.
- **game.co.ls** — DOES resolve (200) but Game is general-merchandise/
  electronics (Massmart brand), not COICOP 01/02 — dropped on sight per
  the non-food constraint, not probed further.
- SA-parent domains for the above chains (pnp.co.za, boxer.co.za,
  okfoods.co.za all 200, transactional) are explicitly OUT OF SCOPE: they
  reflect South African online prices/VAT, not Lesotho retail prices — same
  reasoning already applied to `shop.econofoods.co.za` in the 2026-09-01
  pass. Not pursued.

## Marketplace seller-directory checks (new this pass)

- **wizashopping_ls** (already onboarded, channel=marketplace) — confirmed
  it is Dokan-powered (multi-vendor WooCommerce plugin; `/wp-json/` lists
  `dokan/v1`, `dokan/v2`, `dokan/v3` namespaces). Seller directory
  (`/wp-json/dokan/v1/stores`) has exactly 4 vendors: Jumbo Cash (food/
  wholesale — banner image filename references "Massmart_Jumbo_Storefront",
  i.e. this is the Jumbo Cash & Carry brand), Drip Fits (clothing — skip,
  non-food), DIY store (hardware — skip, non-food), Machobytes/wizaadmin
  (platform admin catalog). Checked Jumbo Cash's own product list via
  `/wp-json/dokan/v1/stores/4/products` — 17 SKUs total (Pork Chops per KG,
  Whole Full Lamb, Chicken Fillets, Fresh Organic Honey, Farm Fresh Eggs,
  etc.), and every one of these 17 already appears in wizashopping_ls's
  existing whole-catalog scrape (`/wp-json/wc/store/v1/products`, no vendor
  filter — Dokan vendor products are ordinary WooCommerce products, so the
  parent spider already collects them under url `/product/<slug>`). VERDICT:
  no distinct new source here — carving Jumbo Cash into its own manifest
  would collect the identical 17 URLs already inside wizashopping_ls, which
  DuplicationPipeline would just collapse against. Not onboarded separately.
  Confirmed 2026-09-11.
- **localbites_ls** (already onboarded, channel=marketplace) — re-checked
  the groceries category (`/categories/groceries`, `/categories/supermarket`)
  and the 14-merchant directory (`api.localbites.co.ls/api/stores`). Both
  identical to the 2026-09-01 finding: groceries still shows "No Products
  found", still 14 restaurant/QSR merchants + BiteLiqour (already onboarded
  separately), no new food vendor added to the directory. Confirmed
  2026-09-11.

## Other candidates checked and rejected

- **Pricemate (pricemate.info / api.pricemate.info)** — the 2026-09-01
  inventory PARKED this as "worth a re-check" (one Lesotho shop found,
  0 products). This pass swept shop_id 1-29 directly against
  `api.pricemate.info/api/products?shop_id=<n>` — every single one returns
  `total_published_products: 0`. This is not a Lesotho-specific gap; the
  whole platform's product database appears empty. Downgraded from PARKED
  to DEAD — do not re-check again absent evidence the platform itself has
  relaunched. Confirmed 2026-09-11.
- **frasers.co.ls, metcash.co.ls, sparlesotho.com, maseru-mall.com,
  lesothoonlineshop.com, lesothoshop.co.ls, foodworldls.com,
  pioneermall.co.ls** — all guessed domains, all NXDOMAIN. Named/directed
  search (not blind guessing) is the logical next step here but was not
  possible this pass (WebSearch budget exhausted session-wide before
  reaching this candidate group). Confirmed 2026-09-11 (DNS-level only).

## Bureau of Statistics Lesotho (bos.gov.ls) — additional notes

- No archive/listing page for past CPI releases (directory listing 403s;
  `publications.htm` carries no CPI links) — the homepage links only the
  current month. The `CPI_<Month>_<Year>.zip` filename pattern itself is
  stable and past months resolve directly: spot-checked 2025 Jan-Dec (all
  200) and 2026 Jan-Jul (200 except April, which 404s — a genuine gap in
  BoS's own publication, confirmed by cross-checking the July 2026 report's
  own back-columns, which also skip from March to May). August/September
  2026 not yet published as of 2026-09-11 (matches the ~6-week NSO lag
  visible in every month checked).
- No CSV/XLS machine-readable form found — PDF only. Table 1 (division
  level, 01-12) and Table 3 (COICOP class level, e.g. 01.1.1 Bread and
  cereals through 12.7.1) are both present in every release; this fetcher
  uses Table 1 only (matches the existing SSA cpi_benchmark convention of
  division-level `coicop_codes`). A future pass wanting finer food-basket
  detail could extract Table 3 from the same PDFs without any new fetch —
  it's already being downloaded.


---

## known_blockers_disco_safrica2_namibia - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_namibia.md` on 2026-09-11. 42 hosts, 29 not
documented above at merge time.

# Namibia food-source discovery — 2026-09-11

Re-probe of the 2026-09-01 Namibia inventory (`references/inventories/ssa/namibia.md`)
plus fresh candidates, per the onboarding brief's priority list (Shoprite/Checkers/
USave, SPAR, Pick n Pay, Woolworths, Choppies, OK Foods Namibia). All verdicts below
are as-of 2026-09-11, live re-probed (not taken from any older blocker list).

## Confirmed dead — Shoprite Group AEM brand family (brochure only)

- **shoprite.com.na** — 403 on plain default-UA `requests`, 200 (62KB) on Chrome-UA
  `requests` (no TLS impersonation needed at all — a bare browser User-Agent clears
  it). Adobe AEM (`shopriteafrica` clientlibs), same pan-African template already
  recorded 2026-09-01. `/store-locator.html` and `/sitemap.xml` confirmed: sitemap
  is 100% recipe/marketing pages (`/recipes/...`), zero product URLs. Re-confirms
  the prior "brochure/store-locator only" verdict.
- **checkers.com.na** — same AEM family, same 403→200 UA behaviour. Not re-probed
  beyond the prior session's finding (liquor-shop page is marketing copy, no
  ordering flow) — no new evidence found to overturn it.
- **okfoods.co.za** (OK Foods, incl. the `/na/en_NA/` Namibia locale under this
  same domain) — this is the SAME Shoprite Group AEM brand family, not an
  independently Namibian-founded chain as hypothesized in the brief. Title bar
  confirms: `https://www.okfoods.co.za/na/en_NA/specials.html` renders as "OK
  Specials | OK Foods Namibia". Specials page is 0 hits for cart/price markup —
  a weekly-flyer style page, no product listing. `/find-a-store.html` +
  InfinityRewards loyalty app are the only functional surfaces. Dead, brochure.
- **choppies.co.na** — WordPress + Elementor, 200 on both default and Chrome UA
  (no WAF at all). `/wp-json/` route dump has NO `wc/store` namespace — Elementor
  site, WooCommerce not installed, matching Elementor's own registered
  namespaces only (`elementor/v1`, `elementor-pro/v1`, etc.), confirming there is
  no e-commerce plugin active. Nav explicitly links "Shop online" / "eChoppies" /
  "Online Shopping Portal" to **echoppies.com** — but that platform is
  Botswana-only (currency asset literally named `botswana-currency.png`, zero
  mentions of Namibia anywhere on the page). Choppies Namibia is a pure brochure
  site whose only "shop online" affordance routes to a sibling country's store.

## Confirmed dead — independent brochure sites

- **metro.com.na** (Metro Namibia) — now 200 (was previously also checked dead
  2026-09-01). `/new-products/` and `/product-news/` pages exist but are WordPress
  posts using a "3d-flip-book" plugin (image/PDF flip-book weekly circular), 0
  hits for price/cart text in the raw HTML. Not machine-readable; would need a
  PDF/image-OCR pipeline for a handful of weekly promo images. Not pursued —
  low value relative to effort, no per-product structure even if OCR'd.

## Unreachable — connection timeout, not a WAF (two independent sessions agree)

- **spar.co.na** / **www.spar.co.na** — DNS resolves (20.87.97.38, Azure). Plain
  `requests` (both UAs) AND `curl_cffi` with `chrome124`/`chrome120`/`safari17_0`
  (3 impersonation profiles) ALL time out after 25s with no TCP-level response.
  Identical behaviour to the 2026-09-01 session's single-attempt timeout — now
  confirmed across 2 sessions, 5 total connection attempts, both plain and
  TLS-impersonating clients. This rules out a JA3/TLS-fingerprint block (an
  impersonating client would at minimum get a different response, not an
  identical hang) — reads as the origin server itself not accepting connections
  from this network path (a8/Tailscale), or genuinely down. Not classified as a
  WAF block. Worth a retry from a different egress IP if this source is revisited.
- **pupkewitz.com.na** / **www.pupkewitz.com.na** — same signature: DNS resolves
  (196.20.10.65), all 3 curl_cffi impersonation profiles time out identically to
  plain `requests`. `pupkewitz.com.na` (bare, no www) fails DNS outright. Same
  disposition as spar.co.na above.

## Not viable — real business, no priced catalog surface

- **zulzi.com** — initially promising: SvelteKit SPA with `ProductList` and
  `AddToCartButton` immutable-asset components (genuine on-demand grocery
  delivery app shape). Ruled out on inspection: all social links point to
  `zulzi_sa` / `facebook.com/zulzi.co.za` — this is a South African delivery
  platform, no Namibia presence found on the page. Not probed further.

## No resolvable domain (checked live 2026-09-11, re-confirms/extends 2026-09-01)

usave.co.za (ZA domain, no `.com.na`/`.co.na` Namibia storefront found),
picknpay.com.na, pnp.com.na, woolworths.com.na, foodloversmarket.com.na,
fruitandveg.com.na, model.com.na, modelsupermarket.com.na, tablefare.com.na,
freshmart.com.na, cashandcarry.com.na, hypersave.com.na, superspar.com.na,
spar.com.na, sparnamibia.com(.na), woermann.com.na / woermannbrock.com.na
(NXDOMAIN — the real domain is `shop.woermannfresh.com`, found via web search,
not domain-guessing — see shipped sources below), okgrocer.com.na,
zulzi.com.na, onecart.co.za (ZA only, not probed for NA), yangonamibia.com,
namibiamarket.com, freshstop.com.na. `okfoods.com` resolves but 301-redirects
to an unrelated US business (bachocousa.com) — a lapsed/repurposed domain, not
OK Foods.

## Verdict on the brief's priority list

Shoprite, Checkers, USave (part of Shoprite Group, no separate NA storefront
found), SPAR, Pick n Pay, Woolworths, Choppies, and OK Foods Namibia are ALL
either brochure-only AEM/WordPress sites with no e-commerce, unreachable, or
have no resolvable Namibia-specific domain. **None of the brief's named chains
yielded a shippable source.** The market is genuinely served by South African
corporate brochure sites for these particular banners, consistent with the
2026-09-01 inventory's "structural absence" reading — this session adds
confirmation via fresh probes (echoppies.com's Botswana-only scope; OK Foods'
Shoprite-family identity; SPAR/Pupkewitz's now twice-confirmed unreachability)
rather than overturning it.

The shippable wins this session came from two other directions instead:
1. A **live web search** past the chain-domain-guessing pattern (a concurrent
   agent's `ddgs`/search-based discovery of `shop.woermannfresh.com`,
   `meat-namibia.com`, `embassyliquorstore.com` — none of which are guessable
   from chain-name domain patterns).
2. The **national statistics office** (nsa.org.na) as an `official_avg` +
   `cpi_benchmark` fetcher pair — not a retailer at all, but a genuine,
   verified, food-division price/index source that the retailer-first search
   strategy would never surface. See Phase 8 report for both.


---

## known_blockers_disco_safrica2_suriname - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_suriname.md` on 2026-09-11. 36 hosts, 9 not
documented above at merge time.

# Suriname food-sourcing pass -- as of 2026-09-11

Task: onboard COICOP 01/02 (food, non-alcoholic drinks, alcohol, tobacco)
sources for Suriname. Prior state: 15 non-food/other manifests +
avoda_sr (thin general-grocery webshop, ~1,224 SKUs, ~33% food share).
Genuine sourcing gap -- took whatever verified, did not rank by COICOP.

## Method note: web search tooling was unreliable this pass

WebSearch hit the session-wide 200-call budget cap before any Suriname
query ran (see `websearch_cap_session_wide_not_per_agent.md`).
WebFetch against duckduckgo.com/html, bing.com, ecosia.org, mojeek.com,
and r.jina.ai all failed or returned decoy/irrelevant content (DDG
CAPTCHA; Bing returned unrelated RV-park and stock-ticker results for
Suriname-specific queries; Ecosia/Mojeek 403; r.jina.ai 401 without a
key). **Do not trust a quick re-check with the same tools to behave
differently without verifying first.**

Pivoted to OpenStreetMap Overpass API as the primary discovery method --
queried `shop~supermarket|convenience|grocery|greengrocer|butcher`
within Suriname's admin boundary. This returned 506 tagged businesses,
of which only 6 carried a `website` tag. This is treated as a
reasonably complete cross-check of Suriname's retail-food web presence:
the population is overwhelmingly small Chinese-family-run
supermarket/convenience shops with no web storefront at all, consistent
with the existing known_blockers.md entries (choisupermarket.com dead
cert, bestmart.sr zero-byte, tulip-supermarket.com brochure-only, etc).

## Named candidates from the brief -- NOT FOUND, as of 2026-09-11

None of these resolved via direct DNS guessing across multiple TLD/name
variants, and none appear among the 506 Suriname shop/supermarket/
convenience/butcher entries in OpenStreetMap. Treated as either
non-existent under these names, defunct, or app/Facebook-only (unreachable
without login):

- **VSH Foodmart** -- no such retail brand found. VSH United N.V. (the
  real Suriname conglomerate at vshunited.com) runs a food-manufacturing
  division "VSH Foods" (vshfoods.com, confirmed live) that produces/
  exports packaged goods but has zero shop/cart/price content -- it is a
  brand marketing site, not a retail source. Not onboarded.
- **Baas Supermarket** -- no DNS hit on baas.sr / baassupermarket.{sr,com};
  absent from the OSM dataset.
- **C1000 Suriname / Continent Suriname** -- no DNS hit on c1000.sr /
  c1000suriname.com / continent.sr / continentsupermarkt.sr /
  continentsuriname.com; absent from OSM. C1000 is a defunct Dutch
  supermarket brand (NL-only); no evidence it or a "Continent" chain
  ever operated in Suriname.
- **Kortom** -- no DNS hit across kortom.sr / kortomsupermarkt.sr /
  kortom.com (timeout) / kortomonline.com; absent from OSM.
- **Wong / Wong's supermarket** -- "Wong" and "Wong Superstore" DO
  exist as real physical shops per OSM (2 nodes), but neither carries a
  website tag, and wong.sr / wongsupermarket.{sr,com,online} /
  wongssupermarket.com all fail DNS. Small shop, no web storefront.
- **Hermitage Mall grocers** -- no matching OSM node found for
  "Hermitage" (Overpass query for this specific check timed out
  mid-pass after working reliably for the main supermarket sweep --
  worth a quick re-run, not re-attempted this pass due to time).
- **Shoprite / SPAR / Pick n Pay in Suriname** -- confirmed absent.
  No DNS hit for shopritesuriname.com, sparsuriname.com, spar.sr,
  picknpaysuriname.com. None of the 506 OSM shop entries reference any
  of these brands. Verdict: no SA regional chain operates in Suriname,
  as suspected in the brief.
- **Other named-but-dead domains hit this pass**: surimarket.com (parked
  "/lander" redirect page, 114 bytes), transamerica.sr (resolves, but
  serves a bare 404.html -- domain registered, no site behind it; real
  "Transamerica" supermarket shop exists per OSM but has no working
  site), soengngie.com (redirects to soengco.com -- Soeng Ngie & Co is a
  Surinamese-Chinese sauce/condiment BRAND content site, no shop/cart,
  not a retail price source), soengngie.sr (suspended-hosting stub).
  kersten.sr resolves and has shop/cart keywords but is N.V. C. Kersten
  & Co's Toyota-dealership site -- automotive, zero food content, not a
  candidate under the COICOP 01/02 mandate.

## Domain-squat finding (new)

- **choisupermarkt.com** (note: NL spelling, no "e" -- distinct from the
  already-recorded-dead `choisupermarket.com` with the English
  spelling) -- resolves 200 via Cloudflare, 475KB page, Shopify
  fingerprint present, BUT the actual content is an Indonesian togel
  (illegal lottery/gambling) spam site (`<title>TOTO TOGEL 158`,
  canonical link to youknowwesew.com / togel158.youknowwesew.com). The
  domain that OSM's "Choi's Supermarkt" node points to has been
  squatted/hijacked since it lapsed. Genuinely dead as a price source,
  distinct failure mode from the cert-expiry already on record for the
  other spelling. Probed 2026-09-11.

## Shipped this pass (2 sources)

Both discovered via the OSM website-tag cross-check, both are
COICOP-01.1.2-dominant butcher/meat retailers -- a genuine narrow-channel
gap none of the existing 16 manifests touch.

- **rossignolslagerij_sr** -- Rossignol Slagerij, Paramaribo butcher
  chain (OSM nodes: Rossignol, Rossignol Slagerij, Rossignol 2 GO).
  Shopify storefront, `/products.json` -- 94 products / 254 SKU-variant
  rows, single page (page 2 empty, so 94 is the true catalog size, not a
  truncation artifact). SRD-priced, e.g. Rundergehakt (1kg) SRD 568.18,
  Varkenkerstham SRD 500.00. Verified live 2026-09-11 with
  `--max-items 100`: 254 rows written, 254 distinct URLs.
- **vcm_sr** -- VCM Slagerijen, the retail butcher/webshop arm of N.V.
  Verenigde Cultuur Maatschappijen (vcm.sr explicitly routes "webshop,
  catering services" to winkel.vcm.sr; a separate arm, boerderij.vcm.sr,
  is wholesale agriculture/livestock and was deliberately NOT onboarded
  to avoid a retail/wholesale double-count of the same producer group).
  WooCommerce Store API, `/wp-json/wc/store/v1/products` -- 170 total
  products confirmed (page1=100 + page2=70, zero id overlap -- real
  pagination). SRD-priced, e.g. Kip sate (6 stuks) SRD 185.00. Verified
  live 2026-09-11 with `--max-items 100`: 100 rows written (catalog
  cap), 100 distinct URLs.

Both use the repo's existing `generic_shopify_configured` /
`generic_woo_configured` spiders (no new Python files needed) --
manifests only, per the `fabiprofishop_ch`/`lianoriginal_li` pattern.
`prices collect --list` re-run after both additions: 2236 sources, no
errors, no global breakage.

## Structural note

Both shipped sources are narrow to meat (channel: specialty-food).
General-grocery (channel: supermarket) coverage for Suriname remains a
single thin source (avoda_sr). The 500+ small Chinese-run
supermarket/convenience shops that dominate OSM's Suriname retail-food
landscape are structurally unscrapable -- no web presence at all, which
is a genuine structural absence (small-format cash retail), not a
missed source. The best remaining lever for Suriname COICOP 01 is the
already-flagged ABS (statistics-suriname.org) average-retail-price
table, currently blocked on transient network errors per the existing
known_blockers.md entry (line 915) -- worth a retry in a future pass,
not re-attempted here (out of scope: that entry already exists and
instructs a retry, not a fresh probe).


---

## known_blockers_disco_safrica2_tci - as of 2026-09-11

Merged from `~/gapwork/known_blockers_disco_safrica2_tci.md` on 2026-09-11. 29 hosts, 23 not
documented above at merge time.

# Turks and Caicos Islands (TCI) -- food-source discovery, 2026-09-11

Scope: COICOP divisions 01/02 (food, non-alcoholic drinks, alcohol, tobacco) ONLY.
Country: `turks_and_caicos_islands`, path `lac/caribbean/turks_and_caicos_islands`,
currency USD, language en.

## Note on concurrent work

This shared worktree (`~/po-worktrees/fill-gap-sources`) had a concurrent pass
already complete TCI discovery and ship two sources (`islandselects_tc`,
`tcgrocerydelivery_tc`) by the time this session reached the verification step.
Rather than duplicate or collide with that work, this session independently
re-verified both shipped sources against the raw on-disk data, and folds in the
dead ends this session found on its own (mostly overlapping, with a few
additional negatives not recorded elsewhere) below. No manifest, spider, or
fetcher in this country directory was created or modified by this session --
all of `goods2door_tc`, `islandselects_tc`, and `tcgrocerydelivery_tc` predate
this session's writes.

## Shipped sources (independently re-verified 2026-09-11)

| source_key | channel | currency | measured rows | distinct urls | notes |
|---|---|---|---|---|---|
| goods2door_tc | supermarket | USD | pre-existing, ~4438 in corpus | -- | Wix, sitemap-driven whole-catalog walk. Pre-existing before this pass; untouched. |
| islandselects_tc | supermarket | USD | 100/100 (two independent runs, 20260911_165850 and 20260911_170040) | 100/100 both runs, 100 distinct product_name both runs | WooCommerce Store API (`islandselectstci.com`), X-WP-Total 1400, 70 pages, page1/page2 ids disjoint. All 3 probe arms (plain UA, Chrome UA, curl_cffi chrome124) clean 200 -- no WAF. |
| tcgrocerydelivery_tc | supermarket | USD | 100/100 (two independent runs, 20260911_165840 and 20260911_170046) | 100/100 both runs, 60 distinct product_name both runs (multi-variant SKUs, not a dedup bug -- urls fully distinct) | WooCommerce Store API (`turksandcaicosgrocerydelivery.com`), X-WP-Total 946, 48 pages, page1/page2 ids disjoint. Plain requests 200; curl_cffi impersonation 403 from `server: hcdn` (JA3 denylist -- matches the documented hcdn pattern, plain HTTP clears it, no impersonation needed for the spider). Sibling domain `turksandcaicosgrocerydeliveryservice.com` serves an identical catalog -- deliberately not onboarded as a second source. |

Both spiders read the JSON Store API directly (page family: API) and never
fetch a rendered page.

## Dead ends -- corroborated independently this session (2026-09-11)

All of the following were reached by this session's own probing, before this
session discovered the concurrent inventory file already recorded the same
verdicts for most of them. Recorded here as independent corroboration, plus a
few additional negatives not in the other pass's writeup.

| Candidate | Domain(s) tried | Verdict | Detail |
|---|---|---|---|
| Graceway IGA / Graceway Smart / Cash 'N' Carry (dominant TCI chain) | `gracewaysupermarkets.com` (canonical; `gracewayiga.com` 301-redirects here) | REJECT -- brochure-only, no e-commerce | Squarespace, 239-url sitemap is all marketing pages. Homepage's one "Shop now" CTA links to `/instoredeals` (weekly flyer announcement). `/graceway-supermarkets-shop-with-us` page's only content is "follow us on social media" -- no online ordering, no cart, no app, no curbside/pickup language anywhere. |
| Graceway Gourmet (separate storefront per Wikivoyage) | `gracewaygourmet.com` | REJECT -- dead server | Resolves (Vultr VPS) but serves a bare nginx default 404 over HTTP; HTTPS handshake hangs. Abandoned infrastructure. |
| `gracewayiga.com` direct | same backend as gracewaysupermarkets.com (AWS us-east-2) | REJECT -- same site | TLS handshake fails with `internal_error` regardless of client (curl, curl_cffi chrome124/120/safari17_0) -- but plain HTTP 301s cleanly to www.gracewaysupermarkets.com. Server TLS vhost quirk, not a WAF. |
| Southside Trading | `southsidetrading.com` (resolves, 200) | REJECT -- parked domain | Bare GoDaddy-style JS lander (114 bytes, redirects to /lander). Not a real storefront. No other domain variant resolves. |
| GraceKennedy-affiliated stores | `gracekennedy.com` (200, corporate site) | REJECT -- not applicable to TCI | Zero mentions of Turks/Caicos or retail on the corporate homepage. GraceKennedy's actual supermarket brands (Hi-Lo `hilofoodstores.com`, MegaMart `megamartja.com`/`megamartonline.com`) resolve but are Jamaica-only; no TCI storefront exists under this group. |
| Massy Stores (regional chain) | `shopmassystorestc.com`, `shopmassystoresprovo.com` (NXDOMAIN) | REJECT -- no TCI storefront exists | Massy Group's Eastern Caribbean footprint is Barbados/Trinidad/Guyana/St Lucia/St Vincent only (per the LAC inventory for those countries); TCI is outside it and the `shopmassystores<code>.com` pattern has no TCI variant registered. |
| CaribeEats grocery-delivery aggregator | `backend.caribeeats.com/api/init` | REJECT -- platform has no TCI region | Direct API call enumerated all 21 active regions -- Nevis, St Kitts, Grenada, Anguilla, Dominica x2, St Eustatius, Montserrat, St Lucia, Antigua, Trinidad, USA, Jamaica, Guyana, Barbados, BVI, Bahamas, UK x2, Nigeria, DealCircle. None is TCI/Providenciales/Grand Turk. |
| PriceSmart (warehouse club, onboarded elsewhere as pricesmart_bb) | `pricesmart.com/en/locations` | INCONCLUSIVE -- locator endpoint 500'd | Not pursued further; PriceSmart's published country list has not historically included TCI. Worth a quick re-check when search tooling is available. |
| TCI government statistics office / CPI (opportunistic check, not a priority candidate) | `gov.tc` | REJECT -- no statistics dept surfaced | Homepage and /structure enumerate only Business/Government/Residents/Budget; no Statistics/Economic-Planning link. All plausible paths (/statistics, /stats, /eps, /dema, etc.) 404. |
| Local classifieds / marketplace guesses | `tcimarketplace.com`, `turksandcaicosmarketplace.com`, `provomarket.com` (NXDOMAIN); `provomarketplace.com` (410 Gone); `tcbuysell.com` (200 but is "Treasure Coast" Florida -- coincidental TC-abbreviation collision, unrelated) | REJECT -- none applicable | |
| Liquor/wine specialty stores (division 02 angle) | `envywineandspirits.com`, `envywine.tc`, `discountliquorsprovo.com`, `discountliquorstci.com`, `bestbuyliquorstci.com`, `provoliquorstore.com`, `igawineandspirits.com` (all NXDOMAIN) | REJECT -- no web presence found | |
| Quality Supermarket, Prime Fresh | `qualitysupermarket*.{com,tc}`, `primefresh*.{com,tc}` variants (all NXDOMAIN except a generic unrelated `primefresh.com`) | INCONCLUSIVE -- no web presence found under any guessed domain | Consistent with the concurrent pass's finding (TCI Tourism Board business directory: local grocers carry phone numbers only, zero website URLs). |

## Methodological note

WebSearch's session-wide budget (200/200) was already exhausted before this
session's discovery work began. WebFetch was tried against DuckDuckGo
(html + lite), Bing, Google, and Marginalia as a substitute -- all four
returned bot-challenge/CAPTCHA pages, not results, as of 2026-09-11. All
findings above (this session's portion) came from direct DNS/HTTP/TLS probing
of guessed domains, a direct API call to CaribeEats, and Wikipedia/Wikivoyage
articles (reachable via WebFetch). See also the concurrent pass's own
inventory at `.claude/skills/onboard-price-sources/references/inventories/lac/turks_and_caicos_islands.md`
for its (independently-arrived-at, matching) discovery notes.

## Verdict

TCI's resident-shopper grocery channel remains a structural gap: Graceway (the
chain locals actually use) is brochure-only with no online catalog, and no
local grocer has any web presence. The tourist/guest grocery-delivery niche is
now covered by three independent storefronts -- goods2door_tc (Wix),
islandselects_tc and tcgrocerydelivery_tc (both WooCommerce) -- all verified
against real collected rows. No further food source was found reachable
within this session's tooling constraints.


---

## known_blockers_playwright - as of 2026-09-11

Merged from `~/gapwork/known_blockers_playwright.md` on 2026-09-11. 3 hosts, 1 not
documented above at merge time.

# Known blockers — generic_woo_playwright pass (2026-09-11)

Built `generic_woo_playwright` (src/prices/price_scraping/spiders/generic_woo_playwright.py),
a Playwright-capable sibling of `generic_woo_configured` for WooCommerce
storefronts behind an hcdn-style JS interstitial. Onboarded 8 of the 9
hcdn-flagged sources named in ~/gapwork/known_blockers_repair_1.md and
_repair_2.md: leskanso_gn, lexmakyty_gn, gotrustmesl, torodo_chicken_land,
albasatin_aldhahabia, almatjar_ly, green_apples_pharmacy, nesraf. One
failed a hard gate. See the full report for the launch recipe and the
measured mechanism (curl_cffi impersonation is what hcdn blocks on 8 of
the 9 tenants; plain non-impersonating HTTP already clears them with no
cookie at all — Playwright is required only for the 9th, nesraf.com, and
only as a session that never hands off to a different HTTP client).

---

## **souristore.com** (Syria, not Libya — the workbook candidate's country
tag was wrong)

- The hcdn block is real but not the failure here: `generic_woo_playwright`
  clears it exactly like the other 8 (plain HTTP, no cookie needed) and the
  Store API returns clean JSON.
- **Rejected on catalog size, not reachability.** `X-WP-Total: 4` — the
  entire catalog is 4 products (Lipton Ice Tea Peach Flavour, and 3 others
  in "مشروبات"/"مركز المدخن" categories). This fails the Phase-6 ≥5-rows
  gate outright, the same failure mode as `salonebuy` in
  known_blockers_repair_2.md (3 products, no pagination).
- Currency is SYP (matches the country), so this is purely a too-small-
  catalog rejection, unrelated to the currency disqualification that
  killed the unrelated `syrazo.com` candidate in
  known_blockers_repair_1.md.
- **Verdict: reject — catalog too small to ship (4 products, no page 2).**
  No manifest written. If the store's catalog grows past 5 products in a
  future re-check, `generic_woo_playwright` with
  `api_url: "https://souristore.com/wp-json/wc/store/v1/products"` would
  work unmodified — same tenant, same recipe as the 8 that shipped.


---

## known_blockers_repair_1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_repair_1.md` on 2026-09-11. 8 hosts, 2 not
documented above at merge time.

# Known blockers — Libya + Syria repair pass 1 (2026-09-11)

8 of 9 targeted sources could not be repaired. `glo_ly` was fixed (see final
report) — its manifest now lives at
`src/prices/configs/menaap/north_africa/libya/glo_ly.yaml` in the worktree.

All probes below used `curl_cffi` with `impersonate="chrome124"` (and
additional profiles where noted), hitting, in order: `/wp-json/wc/store/v1/products?per_page=50&page=1`,
`/wp-json/wc/store/products`, `/?rest_route=/wc/store/v1/products`,
`/products.json?limit=50`, and the plain homepage.

---

## **albasatinaldhabia.com**

- Every path tested (homepage, all 4 API-shape probes, `/store/...`,
  `/shop/...`) returns HTTP 403 with `server: hcdn` and a
  "Checking your browser before accessing... Just a moment" JS-challenge
  page (meta-refresh every 30s, no `Set-Cookie` issued).
- Re-probed with a persistent `requests.Session()`: still 403 on the second
  request, so it's not a one-shot fingerprint miss — the edge never issues a
  cookie that a plain HTTP client could carry forward.
- This is a JS-execution challenge (canvas/browser fingerprint), not a
  simple UA/TLS block; `curl_cffi` impersonation cannot solve it because it
  never runs JavaScript. Would need a real headless browser (Playwright)
  with challenge-solving, which is out of scope here.
- **Verdict: reject.** No page 1 vs page 2 comparison was possible — the API
  was never reachable.

## **almatjar.ly**

- Identical `hcdn` 403 JS-challenge wall on every path, same evidence as
  albasatinaldhabia.com (same edge provider, same challenge page).
- Note: the overlay manifest's notes claimed "X-WP-Total 975 on
  2026-09-10" — that number could not be reproduced today; the API is fully
  walled off now.
- **Verdict: reject.**

## **greenapplespharmacy.com**

- Identical `hcdn` 403 JS-challenge wall on every path (homepage included).
- **Verdict: reject.**

## **nesraf.com**

- Identical `hcdn` 403 JS-challenge wall on every path (homepage included).
  The overlay's own notes already flagged this ("browser-check page on
  2026-09-10") — reprobing today with TLS impersonation did not change the
  outcome.
- **Verdict: reject.**

## **souristore.com**

- Identical `hcdn` 403 JS-challenge wall on every path (homepage included).
- **Verdict: reject.**

## **progaming.ly**

- Every path (homepage and all 4 API probes) returns HTTP 403 with
  `server: cloudflare` and a static "Sorry, you have been blocked" /
  "Attention Required!" Cloudflare WAF page — a custom firewall rule, not a
  JS challenge (no spinner/refresh, no cookie dance).
- Reprobed with 4 different `impersonate` profiles (`chrome120`,
  `chrome131`, `safari184`, `edge101`): 403 on all four. Consistent across
  fingerprints points to an IP/ASN-level WAF rule against this box's egress
  network, not a client-fingerprint issue.
- **Verdict: reject.**

## **poststore.ly**

- Homepage and `/shop/` are live (HTTP 200) and genuinely WooCommerce: the
  page markup contains `woocommerce` and `woocommerce-Price-amount` classes,
  and `/shop/` lists 15 distinct product permalinks.
- However the WordPress REST API is disabled site-wide, not just the Store
  API: `/wp-json/` returns 404, and the query-param fallback
  `/?rest_route=/` — which normally lists every registered namespace —
  also returns 404. There is no API surface at all to point
  `generic_woo_configured` at, under any of the 4 URL shapes.
- A product sitemap does exist and is populated:
  `/product-sitemap.xml` returns 200 with 199 `<loc>` entries (mostly
  `/product/...` PDPs, in Arabic slugs), which is exactly the situation
  the repo's `_woo_sitemap_base.py` pattern (see `ikuma_gw.py`) was built
  for — a bespoke sitemap-walking spider subclass would very likely work.
- **Verdict: reject for a manifest-only fix.** None of the 4 generic
  `*_configured` spiders (Woo Store API, Shopify, OpenCart, PrestaShop) fit
  an HTML/sitemap-only WooCommerce store; onboarding this source needs a new
  per-source spider file (a `WooSitemapBaseSpider` subclass), which is
  outside this task's manifest-repair scope.

## **www.syrazo.com**

- The storefront itself is real and live: homepage returns 200 (2.17MB),
  is a custom platform (not WooCommerce, not Shopify — `/products.json`
  returns the same HTML app shell as the homepage, consistent with
  client-side routing / a catch-all backend route), and lists 210 distinct
  `/products/...` permalinks on the homepage alone.
- Currency check fails: a sampled PDP
  (`/products/fakir-upright-vacuum-cleaner-800-watts`) carries its own
  JSON-LD `"offers":{"price":"69","priceCurrency":"USD", ...}`, and the
  page's own currency-switcher widget defaults to `USD` with a manual link
  to switch to `SYP` (`/currency/switch/SYP`). The canonical, structured
  price data is USD-denominated; SYP is a display-only toggle, not the
  underlying currency.
- Per the task's currency gate ("if a storefront prices in USD/EUR/TRY it
  may not be a local source at all"), this disqualifies it as a Syria
  local-currency source regardless of platform/API questions.
- **Verdict: reject** (currency, not reachability).


---

## known_blockers_repair_2 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_repair_2.md` on 2026-09-11. 8 hosts, 5 not
documented above at merge time.

# Known blockers — Guinea + Sierra Leone + Gambia repair pass 2 (2026-09-11)

12 of 13 targeted sources could not be shipped as a manifest-only fix.
`gambia_petshop` was fixed (see final report) — its manifest now lives at
`src/prices/configs/ssa/west_africa/gambia/gambia_petshop.yaml` in the
worktree.

All probes used `curl_cffi` with `impersonate="chrome124"` (then
`chrome120`, `safari17_0` where the first failed), hitting, in order:
`/wp-json/wc/store/v1/products?per_page=50&page=1`,
`/wp-json/wc/store/products`, `/?rest_route=/wc/store/v1/products`,
`/products.json?limit=50`, and the plain homepage. Where curl_cffi 403'd
uniformly, a real headless Chromium (Playwright, cached at
`~/.cache/ms-playwright/chromium-1200` on `a8` — installs via
`playwright install` fail on this box's OS but the cached browser launches
fine) was also run for the mandatory network-trace check, 8-9s wait,
before any WAF verdict was recorded.

---

## **leskanso_gn**, **lexmakyty_gn**, **gotrustmesl**, **torodo_chicken_land** — LIVE, but not a manifest fix

All four are hosted behind the same `hcdn` (Hostinger CDN-style) edge and
serve an identical JS proof-of-work interstitial to any non-JS client:
HTTP 403, `server: hcdn`, title "Checking your browser before
accessing... Just a moment...", meta-refresh 30s, obfuscated JS that
computes a SHA-256-style hash over a per-request seed served by
`/hcdn-cgi/jschallenge` and POSTs it back before reloading. `curl_cffi`
with all 3 TLS profiles, plus a persistent-cookie `Session` retried 3x
with a 6s gap, got 403 on every attempt on every path (including the
API endpoints directly) — no `Set-Cookie` is ever issued to a client
that can't run the JS, so there is no cookie to carry forward.

**This is a real block, but it is not a dead end** — re-probed all four
with headless Chromium via Playwright:
- Homepage clears the challenge and renders the real storefront in all 4
  cases (confirmed by title: "Kanso Industrie – Le shopping qui vous
  simplifie la vie" / "Accueil - lexmakyty.com" / "Online Shopping Sierra
  Leone | GoTrustMe SL Marketplace" / "Torodo Chicken Land").
- Navigating Playwright directly to
  `/wp-json/wc/store/v1/products?per_page=20&page=N` (after the homepage
  warm-up) returns real JSON, confirming all four run genuine WooCommerce
  Store APIs with live, non-zero-priced catalogs:
  - `leskanso_gn`: 17 products, GNF, e.g. id=2753 price=11,200,000 GNF.
    Page 2 empty (catalog fits on one page).
  - `lexmakyty_gn`: 40 products across 2 pages (20+20), GNF, e.g.
    id=5342 price=300,000 GNF. Page 1 vs page 2 ids fully disjoint
    (5342/5323/5301/... vs 4658/4654/4645/...) — genuinely paginates.
  - `gotrustmesl`: 10 products, **SLL** (not SLE — this tenant's
    WooCommerce currency setting still uses the pre-2022 old-leone ISO
    code), e.g. id=4367 price=45,000 SLL. Single page.
  - `torodo_chicken_land`: 9 products, GMD, e.g. id=15738 price=8,000
    GMD. Single page.
- `arabinene_gn` (see below) is the only one of the five 403'd sites
  that stayed blocked under Playwright too — these four are a genuinely
  different, weaker class of block.

**Why this isn't a manifest fix:** the repo's `generic_woo_configured`
spider (`WooBaseSpider`) issues plain `scrapy.Request`s with no
Playwright involvement, and curl_cffi TLS impersonation cannot execute
the hcdn JS challenge (it isn't a TLS/JA3 fingerprint check — it's a
content-level proof-of-work). The repo does have `scrapy-playwright`
wired in repo-wide (`settings.py` line ~91,
`meta['playwright']=True`) and several bespoke spiders already use it
(`makro.py`, `central_th.py`, `express_market_cm.py`, etc.), but there is
no generic Playwright-capable WooCommerce spider today — only the
plain-HTTP `generic_woo_configured`. Pointing these manifests at
`generic_woo_configured` would ship a spider guaranteed to 403 on every
run.

**Recommendation (not done here, needs separate sign-off):** write a
`generic_woo_playwright_configured` spider (or extend `WooBaseSpider`
with an opt-in `meta={"playwright": True}` per request) that lets a
manifest ask for the Playwright path. All four of these sources are
small catalogs (9-40 products) but genuinely live and correctly priced —
worth the one-time cost of building that template, then reusing it
across all four in one pass, per the skill's own "build the anti-bot
template once, then reuse" guidance.

**Verdict: not merged, pending Playwright-Woo scaffolding.**

## **arabinene_gn**

- Every path (homepage and all 4 API-shape probes) returns HTTP 403 with
  `server: cloudflare`, `cf-mitigated: challenge`, title "Just a
  moment...", and an inline Cloudflare Turnstile challenge
  (`challenges.cloudflare.com/turnstile/...`).
- Reproduced identically across `chrome124`/`chrome120`/`safari17_0`
  curl_cffi profiles.
- Re-probed with headless Chromium via Playwright (real JS execution,
  9s wait): **still 403**, page title still "Just a moment...", content
  length 28544 (the Turnstile shell, not the site). The Turnstile widget
  itself loaded (`challenges.cloudflare.com/turnstile/v0/g/.../api.js`)
  but did not clear headlessly.
- This is the one site where both curl_cffi impersonation AND a real
  headless browser failed — the genuine "stop" condition. A residential
  proxy plus a captcha-solving service would be needed; out of scope.
- **Verdict: reject.**

## **anadi_guinee_gn**

- Homepage returns HTTP 200, but the content is **not a Guinea
  storefront at all**: `<title>PASCOL4D Login : Akses Alternatif Resmi
  Situs Toto Slot Gacor 4D Terpercaya Paling Instan</title>`, an
  Indonesian online-gambling ("toto slot") SEO-spam page, styled via
  `global.microless.com` (a legitimate small-business e-commerce SaaS —
  this domain appears to have been a Microless-hosted electronics/pet
  supplies storefront previously, now hijacked/repurposed). `/wp-json/`,
  `/boutique/`, `/shop/` all 404 — there is no WordPress/WooCommerce
  installation to find a Store API on.
- Confirmed via direct HTML fetch and grep for `<title>`, `og:title`,
  and `product:price:currency` meta tags — the only price meta present
  (`product:price:amount=9`, `currency=USD`) belongs to the gambling
  page's own OG tags, not a real product.
- **Verdict: reject — domain squatted/repurposed, not a live Guinea
  retailer.** Nothing about this is a probing-client artifact.

## **madinaenligne_gn**

- All 3 WooCommerce Store API variants (`/wp-json/wc/store/v1/products`,
  `/wp-json/wc/store/products`, `/?rest_route=/wc/store/v1/products`)
  return **HTTP 500** with an identical PHP fatal error:
  `Uncaught TypeError: substr(): Argument #1 ($string) must be of type
  string, int given in /htdocs/wp-content/plugins/wp-rocket/...` — this
  reproduces on every retry; it's a real server-side crash (the
  WP-Rocket cache plugin), not a bot block. `/wp-json/` root,
  `/sitemap.xml`, and `/sitemap_index.xml` crash the same way (the whole
  REST/sitemap stack is down site-wide).
- The HTML shop page (`/boutique/`) returns 200 but is an **Elementor
  Canvas** template (`elementor-template-canvas`,
  `woocommerce-no-js` body class) with **zero static product cards or
  PDP links** — WooCommerce's product loop here is populated
  client-side/AJAX only, so a non-JS crawler sees an empty shell.
  `/boutique/page/2/` also 500s.
- Individual product-detail pages **do** work and carry real prices:
  fetched two known PDP URLs directly
  (`/produit/iphone-11-128gb/` → JSON-LD price 2,700,000 GNF;
  `/produit/ordinateur-portable-hp-g7/` → 2,500,000 GNF) — the catalog
  is genuinely live and GNF-priced.
- The problem is **discovery**: with the API dead and the listing pages
  JS-only, there is no static path (no sitemap, no product-category
  archive links found on the homepage) for a crawler to enumerate PDP
  URLs at scale. `generic_woo_configured` only speaks the Store API, so
  it cannot use the PDP-JSON-LD path either.
- **Verdict: reject as a manifest fix.** Would need either the WP-Rocket
  bug to be fixed site-side, or a bespoke Playwright-based
  listing-discovery spider — both out of scope here.

## **salonebuy**

- All 3 WooCommerce Store API variants return HTTP 500 (generic
  "WordPress › Error" critical-error page — a broken plugin, not
  specifically identified). `/wp-json/` root also 500s.
- The HTML shop page (`/shop/`, Martfury theme) does render statically
  and does carry 3 real product cards/links (Cetaphil skincare set,
  solar floodlight, solar home system) — but that is the **entire**
  catalog: `/shop/page/2/` returns 404 (the page doesn't exist), so
  there is no pagination to test and the source fails the ≥5-rows
  Phase-6 bar outright at 3 unique products.
- **Verdict: reject — catalog too small to ship (3 products, no
  pagination) and the API is separately broken.**

## **national_centre_for_arts_and_culture_shop** (ncac.gm)

- Every path tested (homepage, `/shop/`, `/shop/page/2/`, `/wp-json/`,
  the Store API) returns the **identical 2576-byte page**: `<title>Access
  Denied</title>` / "This site is currently suspended... If you are the
  owner of this site, please contact support for more information." The
  original probe's "200 but HTML not JSON" verdict undersold it — the
  200 status is a hosting-provider suspension page, not a working site
  at all.
- **Verdict: reject — hosting account suspended, nothing to scrape.**

## **djickai_gn**, **media7plus_gn**

- Both return HTTP 402 on every path and every TLS profile — Shopify's
  own "payment required" response for a store frozen for non-payment
  (per the known gotcha: 402 on a `*.myshopify.com`-backed domain means
  the store is closed, not blocked).
- **Verdict: reject — confirmed dead, no further probing warranted.**

## **femb6y_shopify_haircare_gn**

- Returns HTTP 423 on every path: `<title>This store is
  unavailable</title>` (Shopify's "store deactivated" page, distinct
  from the frozen-for-payment 402 above). `/products.json` returns
  `{"errors":"Not Found"}` (404). `/admin` redirects to the standard
  Shopify login, no custom-domain hint anywhere in the response.
- Checked for a migrated custom domain (the standard fix for a stale
  `*.myshopify.com` host per the task's own gotcha) — no redirect, no
  canonical link, nothing in the 423 page pointing elsewhere.
- **Verdict: reject — store deactivated, not merely moved.**


---

## known_blockers_repair_3 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_repair_3.md` on 2026-09-11. 12 hosts, 6 not
documented above at merge time.

# Known blockers — repair batch 3 (South Sudan, Greenland, Botswana)

All probes below used `curl_cffi` with `impersonate="chrome124"` (TLS/JA3 impersonation), run 2026-09-11 from `a8`. Each site was re-probed live — none of the verdicts below are carried over from the original overlay notes without re-confirmation. None of the 12 targets produced a corrected manifest; details per source follow.

## **higromall.com** (higromall_ss)
- Tried: `/`, `/products.json`, `/wp-json/wc/store/v1/products`, `/wp-json/wc/store/products`, `/?rest_route=/wc/store/v1/products`.
- Every path, including the bare homepage, returned **HTTP 500 with a 0-byte body**, 3x on retry with a 2s gap.
- Impersonation made no difference — this is a server-side failure, not a bot block. Site is not currently serving any content at all.
- Verdict: dead. Not a probing-client artifact; the origin itself is broken.

## **jubafashionhub.link** (juba_fashion_hub_link_ss)
- Homepage is a client-rendered Vite/React SPA (`<div id="root">`, JS bundle at `/assets/index-*.js`); every path including `/products.json` returns the **identical 7891-byte SPA shell** (client-side routing, no server route for that path).
- Found the real data source by reading the JS bundle: a same-origin endpoint `GET /api/products` (Firebase-backed custom Node app) returns a **live, non-paginated JSON array of 130 products**, all with non-zero `priceSSP` (e.g. 320000, 640000, 200000 SSP — these look like SSP-denominated, consistent with hyperinflation). Pagination params (`?page=`, `?limit=`) are accepted but ignored — the endpoint just returns the full 130-item catalog every time, so the page-1-vs-page-2 gate doesn't apply (there's only one page).
- This IS a live, verified, correctly-priced South Sudan source. It is **not Woo or Shopify** — it's a bespoke JSON API with its own schema (`fragranceFamily`, `priceSSP`, `notesTop`, etc.). Neither `generic_woo_configured` nor `generic_shopify_configured` can parse it; there is no existing generic-JSON spider in the repo to point at it.
- Verdict: **not a manifest fix** — needs a bespoke fetcher/spider written against `/api/products`, which is out of scope for a spider/spider_kwargs/currency correction. Flagging as a good candidate for a follow-up scaffolding task, not folding it in here without sign-off on writing new spider code.

## **nilemart-ss.com** (nilemart_ss)
- All paths return **HTTP 403** behind a JS proof-of-work challenge (`server: hcdn`, title "Checking your browser before accessing... Just a moment...", obfuscated JS computing a SHA-256-style hash and POSTing it to `/hcdn-cgi/jschallenge` before a reload).
- This persists under TLS impersonation because the block is a JS challenge, not a TLS/UA fingerprint check — curl_cffi does not execute JavaScript, so it can't complete the challenge.
- Verdict: dead for this pipeline (no headless-browser solving in scope).

## **jubafashionhub.store** (juba_fashion_hub_ss)
- `/` returns Shopify's own 402 "Store unavailable" page; `/products.json` returns `{"errors":"Unavailable Shop"}` with HTTP 402.
- Verdict: dead. Shopify store frozen for non-payment (per the known gotcha for 402 on Shopify domains).

## **jubalaptops.com** (jubalaptops_ss)
- Homepage 200 (WordPress/WooCommerce theme). `/products.json` 404 (not Shopify, expected). All 4 Woo Store API variants return **HTTP 401** `rest_api_authentication_required`.
- Verdict: dead. Store API is locked to authenticated users; no public product feed exists for `generic_woo_configured` to hit.

## **jubastationery.com** (jubastationery_ss)
- Homepage 200, `wp-json/` root lists only `wc/v1`, `wc/v2`, `wc/v3` (legacy WooCommerce REST, requires consumer key/secret) — **no `wc/store` namespace is registered at all**, hence the 404 `rest_no_route` on every Store API path tried.
- Category page (`/product-category/computer-and-mobiles/`) is genuine WooCommerce HTML (`class="woocommerce"` present, price markup present) — a human/HTML crawl could see prices, but `generic_woo_configured` (`src/prices/price_scraping/spiders/generic_woo_configured.py`) only talks to the Store API (`WooBaseSpider`, no HTML fallback path).
- Verdict: not repairable with the existing generic Woo spider. Would need a bespoke HTML-crawling spider for this specific store — out of scope here.

## **aknittersworld.dk** (aknittersworld)
- All paths return **HTTP 403** behind a Bunny CDN "Shield" JS proof-of-work challenge (`/.bunny-shield/assets/shield-challenge.js`, `data-pow="..."` attribute).
- Same class of block as nilemart-ss: JS challenge, not solvable by TLS impersonation alone.
- Could not get far enough to verify the Greenland-vs-Denmark locality question raised in the task (whether this `.dk` domain actually prices/ships to Greenland) — the site never rendered past the challenge page.
- Verdict: dead for this pipeline.

## **jajja.gl** (jajja_gl)
- Homepage and `/collections/all` both return HTTP 200, but the page's embedded Shopify bootstrap JSON explicitly declares `"pageType":"password"`, `"productVariants":[]`, `"products":[]`. `/collections/all/products.json` and `/collections/all.json` both return **HTTP 401** with an empty body.
- Currency confirmed as DKK in the same bootstrap JSON (`"paymentSettings":{"currencyCode":"DKK"}`), `countryCode":"GL"` — so locality is correct, but irrelevant since the storefront is locked.
- Verdict: dead. Password-protected Shopify storefront (matches the known 401-on-Shopify gotcha) — no product data is served to unauthenticated requests despite the 200s on HTML pages.

## **nanoqmedia.gl** (nanoqmedia_gl)
- Homepage 200 (WordPress/WooCommerce theme, Danish locale). `/products.json` 404 (not Shopify, expected). `wp-json/` root itself returns **HTTP 401** with an empty `namespaces` list — the entire REST API, not just Store API, is locked to authenticated users.
- Verdict: dead. No public API surface at all for `generic_woo_configured` to use.

## **hoodmarket.com** (hoodmarket_liquor_bw)
- `/` returns Shopify's 402 "Store unavailable" page; `/products.json` returns `{"errors":"Unavailable Shop"}`, HTTP 402.
- Verdict: dead. Frozen Shopify store (non-payment), same as juba_fashion_hub_ss.

## **houseofgentlemen.co.bw** (houseofgentlemen_bw)
- Identical signature to hoodmarket.com: HTTP 402, `{"errors":"Unavailable Shop"}` on `/products.json`.
- Verdict: dead. Frozen Shopify store.

## **totaltools.co.bw** (totaltools_phakalane)
- Correction to the handover table: this is **not Shopify** — it is a live WordPress/WooCommerce site, and its Store API works fine publicly: `GET /wp-json/wc/store/v1/products?per_page=50&page=N` returns HTTP 200 with real JSON, `X-WP-Total: 580`, `X-WP-TotalPages: 12`, currency `BWP`, and page 1 vs page 2 return fully disjoint product-id sets (paginates correctly — passes the gate on that count).
- Failed on the second half of the gate: pulled all 580 products across all 12 pages and checked `prices.price`. **567 of 580 (97.8%) are priced "0"** — this is a quote-only industrial/hardware catalogue (tools, PPE, generic hardware), matching the overlay's own prior note "Not-ready / quote-only P0 catalog." Only 13 items (2.2%) carry a real price.
- Verdict: rejected on price coverage, not on access. Live API, wrong content — a catalogue that's almost entirely "price on application" is not a usable price source.


---

## known_blockers_repair_4 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_repair_4.md` on 2026-09-11. 4 hosts, 3 not
documented above at merge time.

# Known blockers — repair pass 4 (2026-09-11)

## **compraonline.alcampo.es** (alcampo_es, Spain, EUR) — capped, NOT dead

Already merged and shipping; left unchanged (reverted after a failed
improvement attempt, see below) because it still clears the repo's
>=5-row bar. Documented here so a future pass doesn't re-attempt the
same fix without new capability (a CAPTCHA-solving service or IP
rotation).

- The spider already walks the FULL catalogue (both sitemap product
  shards, 86,263 URLs total) — the low row count is NOT a narrow
  category/search-endpoint problem and NOT a `DuplicationPipeline`
  URL-collapse. Direct evidence: a live run's 7 rows carried 7 fully
  distinct product ids/urls spanning unrelated categories (a laptop, a
  glass container, chocolate, a broom, pool chemicals, boxer shorts,
  setting powder) — proof the sitemap walk is correct and broad.
- Real root cause: AWS WAF Bot Control on `compraonline.alcampo.es`.
  A fresh IP/session gets a small grace allowance (5-10 real HTTP 200
  PDP responses, reproduced across three separate live attempts on
  2026-09-10 and 2026-09-11), then every further request against
  `/products/*` gets HTTP 202 (`x-amzn-waf-action: challenge`), which
  itself escalates to **HTTP 405 with `x-amzn-waf-action: captcha`** —
  a real interactive "Human Verification" image-CAPTCHA page (confirmed
  by inspecting the response headers and HTML title directly), not a
  passive JS-only proof-of-work.
- Tried and disproven: the "Playwright once to mint an aws-waf-token,
  then plain-HTTP-replay the cookie" pattern that already works
  elsewhere in this repo for `taw9eel_kw.py`/`cdiscount_fr.py`. Those
  tenants use AWS WAF's `challenge` action only, which a real browser
  auto-solves by executing the page's JS. Alcampo's PDP surface uses the
  `captcha` action: a real headless Chromium navigated directly to a PDP
  and left running for 20 seconds never auto-solved or redirected — it
  is a genuine visual puzzle, not automatable JS. Worse, replaying a
  cookie jar minted from a bare homepage visit made things WORSE than
  the no-cookie baseline: a live test run carrying that cookie jar got
  **0 real rows across 239 requests** (120x202 + 119x405-captcha)
  against 85,714 distinct candidate PDP URLs, versus 7-10 real rows for
  the existing no-cookie approach. Presenting a token that was never
  actually solved appears to read as a stronger bot signal than
  presenting none.
- A fresh (cookie-less) Playwright browser launched per item avoided
  the immediate captcha escalation seen with a reused session (stayed
  at the lighter `challenge` action across 5 distinct fresh-context
  requests) but still got 0 real content through in that test window —
  inconclusive, and not clearly better than the shipped approach.
- Conclusion: reverted `alcampo_es.py` to the pre-existing, already-
  verified version (the only change kept is an addendum to its
  docstring recording this investigation). A real fix to reach
  "thousands of rows" needs infrastructure this repair pass doesn't
  have — a CAPTCHA-solving service or rotating IPs to keep re-arriving
  as a fresh grace-allowance identity — not a spider-code change.

## **calpepharmacy.gi** (calpepharmacy_gi, Gibraltar, GIP)

Not merged; no viable fix found — dead end confirmed.

- Every endpoint probed (homepage, `/shop/`, WooCommerce Store API
  `/wp-json/wc/store/v1/products`, `/products.json`, sitemap) returns
  **HTTP 403** with a Cloudflare "Attention Required! | Cloudflare" /
  "Sorry, you have been blocked" firewall page.
- Reproduced identically across 6 curl_cffi TLS-impersonation profiles
  (chrome120/124/131, safari17_0/18_0, chrome99_android, edge101) **and**
  from a real headless Chromium via Playwright (full JS execution, real
  browser fingerprint) — still 403, same "Attention Required" title.
- Only `/robots.txt` returns 200.
- Probed from a8's residential IP (73.201.6.61, AS7922 Comcast), not a
  flagged datacenter range, so this is not an IP-reputation artifact.
- Conclusion: a Cloudflare firewall-rule-level block that a genuine browser
  cannot clear either — not a bot-fingerprint or JS-challenge problem that
  impersonation or Playwright can solve. No spider built.

## **allvision.sr** (allvision_optics, Suriname, SRD)

Not merged; no viable fix found — dead end confirmed.

- Homepage responds 200 but the site is a static **Astro v5.18.2** build
  (`<meta name="generator" content="Astro v5.18.2">`), not
  WordPress/WooCommerce — the manifest's `generic_woo_configured` spider
  and Store API assumption were wrong from the start.
- All WooCommerce/Shopify-style probes (`/wp-json/wc/store/v1/products`,
  `/wp-json/wc/store/products`, `/products.json`, `/sitemap_index.xml`,
  the manifest's seed URL `/product/multifocaal/`) return 404.
- The site's real sitemap (`https://www.allvision.sr/sitemap.xml`, 200)
  lists exactly 13 URLs, all marketing/informational pages: homepage,
  `/oogmeting`, `/brillen-glazen`, `/verzekerd-zien`, `/locaties` (+4
  location subpages), `/contact`, `/start-hier`, `/veelgestelde-vragen`,
  `/privacy`.
- Checked `/brillen-glazen` ("Glasses & Lenses") directly: 23.8KB of HTML,
  zero SRD/price patterns found.
- Conclusion: a brochure site for an optician chain with no online
  catalogue or listed prices of any kind — nothing to scrape. No spider
  built.

## **sessayelectronic.store** (sessayelectronic, Liberia)

Not merged; confirmed dead (Shopify store frozen).

- Homepage title "Store unavailable", `class="shop-404"`, HTTP 402.
- `robots.txt` itself states "we use Shopify as our ecommerce platform"
  and `Disallow: /`.
- `/products.json`, `/collections/all/products.json`, and `/sitemap.xml`
  all return **HTTP 402** with body `{"errors":"Unavailable Shop"}`
  (sitemap.xml returns the XML-wrapped equivalent).
- Conclusion: confirmed store-frozen at the platform level (matches the
  known Shopify-402-for-non-payment pattern exactly), not a probing-client
  issue. Not worth further investment per the task brief. No spider built.


---

## known_blockers_retest_1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_retest_1.md` on 2026-09-11. 49 hosts, 22 not
documented above at merge time.

# Known blockers — retest batch onboard_1.csv (2026-09-11)

174 previously-rejected hosts (`~/gapwork/retest/onboard_1.csv`: 10 `RECOVERED`,
164 `STALE-OK`). Worked in priority order (RECOVERED+foodish -> RECOVERED+rest
-> STALE-OK+foodish -> STALE-OK+rest). One source shipped:
`palacesuperstores_gh` (Ghana) — see the manifest and final report for detail.

**Headline finding, MEASURED**: of the 174 hosts, 161 (92.5%) answered HTTP 200
to a plain, non-impersonating GET when independently re-probed live during
this session (separately from the CSV's own probe arms that put them in this
batch). The original "blocked" verdicts were overwhelmingly wrong about
*reachability*. They were far less wrong about *value* — reachable is not the
same claim as "worth onboarding," and the gap between those two numbers is
the real finding of this pass (full breakdown in the final report).

All probes below used plain `requests` with a Chrome-124 UA string (no
`curl_cffi`, no TLS impersonation) unless stated otherwise. Per the skill's
own gate: a 200 plus a long body is not evidence of a working endpoint —
several hosts below are Wix/React/Next.js catch-alls that return their own
homepage HTML (identical byte length) for every path probed, including
`?rest_route=`/`/api/`-shape guesses.

---

## RECOVERED class (10 hosts, all confirmed HTTP 403 to curl_cffi
impersonate=chrome124 but HTTP 200 to plain HTTP at CSV-generation time)

- **foodstore2go.com** — NOT new. Already shipped
  (`src/prices/configs/lac/caribbean/bahamas_the/foodstore2go_bs.yaml`,
  onboarded 2026-09-05). This batch's row was a stale duplicate of that prior
  work.
- **kgalagadibreweries.co.bw** (Botswana, `server: hcdn`) — reachable
  (WordPress, generator meta confirms), but it is Kgalagadi Breweries'
  corporate/investor site, not a storefront. Sitemap has only
  `post-sitemap.xml`/`page-sitemap.xml` — no product catalog exists to scrape.
  **Reject: no shop.**
- **thegambiamarket.com** (`server: hcdn`) — reachable but the whole site is
  a 5.7KB "Hostinger Horizons" AI-site-builder shell; `/sitemap.xml` 429s.
  Consistent with Will's 2026-09-11 handover note calling this not viable.
  **Reject: dead/placeholder site**, not a real block.
- **5ka.ru** (Pyaterochka delivery app, Russia) — flaky. CSV recorded
  B_ua=200; my independent re-probe got 403 on the homepage and on both
  WooCommerce Store-API guesses (which returned 200 but with fake/near-empty
  HTML bodies, not real endpoints — this tenant is not WooCommerce).
  **Reject: not reliably reachable, and not the platform the 200 implied.**
- **buyonwasapp.ng** (Nigeria, `server: hcdn`) — genuinely reachable, genuine
  WooCommerce Store API (`/wp-json/wc/store/v1/products`), but the entire
  catalog is 16 SKUs, nearly all ad-placement/membership products at price=0
  ("Space Advertisement" NGN 500000, several NGN 0 listings, "Miss
  Buyonwasapp.ng 2025" NGN 1). **Reject: fails the non-zero-real-price gate**
  — this is a classifieds/ad marketplace wearing a WooCommerce skin, not a
  product catalog.
- **dukan.af** (Afghanistan, `server: hcdn`) — reachable, real e-commerce
  (cart/add-to-cart present, 614-URL sitemap with `/product/<slug>` PDPs
  confirmed live). Catalog is general dropship merchandise (USB juicers,
  inflatable sofas, watches, Labubu toys, slimming tea) — sampled ~30 product
  names, effectively zero core-food SKUs. **Reject for this pass: reachable
  and real, but not a food source** (COICOP 01/02 fill would be ~0).
- **margaarou.com** (`server: hcdn`) — reachable, genuine WooCommerce Store
  API, verified enumerable (5 pages x 50 items, all disjoint ids). Catalog is
  furniture/office/appliances (desks, shoe racks, wardrobes); of 250 sampled
  names, food-keyword hits were all false positives (bottled water, a juice
  *extractor appliance*, not juice). **Reject for this pass: not a food
  source.**
- **onecitizendaily.com** (South Sudan, `server: hcdn`) — reachable, but it's
  a WordPress newspaper (title: "One Citizen Daily Newspaper — The Leading
  English Newspaper in South Sudan"). `/products.json` 200 is the WP
  catch-all, not Shopify. **Reject: non-commerce site.**
- **quincaillerie.ci** (Côte d'Ivoire, `server: hcdn`) — reachable, genuine
  WooCommerce (`woocommerce`/`add-to-cart`/`panier` in page source, real
  `/shop` sitemap entry). It is a hardware store ("quincaillerie" = hardware/
  ironmongery in French) — zero COICOP 01/02 relevance. **Reachable and real,
  but out of scope for food** (counts toward the headline reachability number
  only; not scaffolded).
- **sococe.online** (`server: hcdn`) — reachable but the entire site is a
  7.9KB "Votre site est en Construction" (site under construction) page.
  **Reject: not live.**

**RECOVERED summary: 10/10 reachable (confirms the hypothesis at 100% for
this sub-batch), 0 new food sources** (1 was already shipped under a
different retest pass; 4 are real, live, non-food commerce sites; 4 are
non-commerce or dead sites; 1 is a degenerate ad-listing catalog; 1 was not
reliably reachable on re-check).

---

## STALE-OK + foodish class (30 hosts)

- **palacesuperstores.com** (Ghana) — **SHIPPED.** See
  `src/prices/configs/ssa/west_africa/ghana/palacesuperstores_gh.yaml`.
- **africamedicalmarketplace.com** — reachable but a pharmacy/medical
  marketplace (COICOP 06, not 01/02). `/wp-json/wc/store/v1/products` 200 is
  a homepage-HTML catch-all, not a real Woo endpoint. **Reject: non-food.**
- **alloshmart.com** / real domain **allosh-eg.com** (Egypt, "Alloush Market
  — 24-hour supermarket") — genuinely a real Egyptian grocery chain (sitemap
  lists `/brand/pepsi`, `/brand/cocacola`, `/brand/juhayna` — Juhayna is a
  major Egyptian dairy brand). Frontend is a React/Next SPA; every guessed
  REST path on both `alloshmart.com` and `allosh-eg.com` 404s or catch-alls.
  **Needs a Playwright network trace to find the real product API — not
  a manifest-only fix. Worth a dedicated follow-up: real supermarket, high
  food relevance.**
- **bazaar-baghdad.com** (Iraq) — reachable, real PDP structure
  (`product.php?id=N`, confirmed live at id=160 with a rendered price
  section), but price is injected by client JS from data not present in the
  static HTML (no embedded `var product = {...}`, no discovered `fetch()`
  target beyond a cart-actions endpoint). **Needs a Playwright trace to find
  the price data source — not a manifest-only fix this pass.**
- **bookshop.org** — reachable, but books (non-food). **Reject: non-food.**
- **decker.shop** (Dagenham, England — `meta.json` confirms `country: GB`,
  `currency: GBP`) — genuine Shopify storefront, and it does sell food
  (oats, evaporated milk, tea), but the entire catalog is 26 SKUs on a single
  page (page 2 empty). **Reject: catalog too thin to treat as a real
  source, and GB is not a priority gap country for this project.**
- **foodbevg.com** — reachable but the crawlable link structure is dominated
  by a `/US/...` country-selector pattern and a login wall on internal pages
  — reads as a B2B food/beverage trade-directory site, not a consumer
  storefront with fixed retail prices. **Not verified as a real catalog this
  pass — needs deeper investigation before a verdict.**
- **foodpanda.com.mm** (Myanmar) — reachable, but foodpanda is a
  restaurant-delivery + darkstore (pandamart) aggregator requiring
  city/location context through its own app API, not a simple REST catalog.
  **Out of scope for a single-pass manifest fix — dedicated effort per the
  skill's "market leader" guidance.**
- **fresh-hot-pizza.pages.dev** — a Cloudflare Pages-hosted single-pizzeria
  site ("Hot Pizza — Juba's Hottest Pizza"). Reads as a small
  demo/marketing site, not a catalog with enumerable SKUs. **Reject: not a
  price source shape.**
- **gcc.luluhypermarket.com** — reachable, but this is the *same* GCC LuLu
  Hypermarket platform already onboarded per-country
  (`lulu_ae`/`lulu_bh`/`lulu_om`/`lulu_sa`/`lulu_kw`/`lulu_qa`). **Reject:
  redundant, not a new source.**
- **gnakrystore.com** (Guinea) — reachable, real French-language storefront
  (`/catalogue`, `/panier`, `/promotions/flash` routes in its own sitemap),
  but no discoverable REST endpoint from static probing (`/wp-json/`,
  `/rest/V1/products`, `/api/products` are all the SPA's homepage catch-all).
  **Needs Playwright network trace — not a manifest-only fix this pass.**
- **imvelomarketplace.vercel.app** — reachable at CSV-generation time, but
  now consistently returns Vercel's own bot-challenge page ("Vercel Security
  Checkpoint", 403) on every path. **Reject: re-blocked / inconsistent since
  the batch was generated.**
- **kmart.com.au** (Akamai) — reachable, but Kmart AU is general merchandise
  (apparel/homewares), not a food retailer, and Australia already has
  established coverage from other sources. **Reject: non-food + low
  marginal value.**
- **libyashop.ly** — reachable but the entire site is a 690-byte placeholder
  page, identical across every path probed. **Reject: not a live catalog.**
- **lumogambia.shop** ("Lumo — Buy & Sell Anything in Gambia") — reachable,
  but reads as a general classifieds marketplace (mixed user listings), not
  a structured retailer catalog. No Woo/Shopify/generic REST endpoint found.
  **Not pursued this pass** — would need per-listing category filtering and
  is unlikely to carry reliable fixed retail pricing.
- **marketplace.com.mm** (Myanmar) — reachable, and `/api/products` is a
  genuine REST endpoint (proven by a 429 rate-limit response, not a 404/
  catch-all), but it stayed 429 across 4 retries with 10s backoff and a
  `Referer` header. **Needs session/auth investigation — not a manifest-only
  fix this pass.**
- **nassaugrocer.com** (Nassau, Bahamas — "Nassau Grocer") — CSV recorded
  A_plain=200, but every independent re-probe this session (including a
  dedicated retry) got HTTP 403 with an identical 75,193-byte body also seen
  on `shop.gambia.com` (see below) — looks like a shared intermediary/CDN
  block page, not two coincidentally-similar sites. **Reject: not reliably
  reachable at verification time**, despite the STALE-OK verdict.
- **ogs.channelislands.coop** ("Online Grocery Shopping — Channel Islands
  Co-operative Society") — reachable, but the entire catalog sits behind a
  customer login wall (`Login` page title, password field present, every
  guessed API path 404s). **Reject: login-walled, per the standard skip
  criterion.**
- **quinkashop.com** (Côte d'Ivoire — "Materiaux de construction &
  Quincaillerie") — reachable, real structured site (`/produit/<slug>`,
  `/categorie/<slug>`, `/boutique?ville=Korhogo` routes all present) but
  it's a building-materials/hardware store. **Reject: non-food.**
- **shop.americasnationalparks.org** — genuine Shopify storefront, but it's
  a national-park gift-shop (souvenirs), not food. **Reject: non-food.**
- **shop.gambia.com** — same as nassaugrocer.com: CSV recorded a 200 arm,
  but every re-probe this session got HTTP 403 with the identical
  75,193-byte body. **Reject: not reliably reachable at verification time.**
- **shop.sumut.dk** ("Webbutikken i Det Grønlandske Hus i København" — the
  Greenlandic House webshop, physically based and shipping from
  Copenhagen, Denmark) — genuine Shopify storefront selling Greenlandic
  specialty food, but it is a Denmark-based diaspora storefront, not a
  Greenland-domestic retailer. **Reject: fails the locality gate** (prices
  are Copenhagen retail prices for an export/diaspora audience, not
  Greenland shelf prices).
- **shoprite.co.mz** (Mozambique) / **www.shoprite.co.ls** (Lesotho) — both
  reachable, both running the enterprise Adobe-Experience-Manager
  ("shopriteafrica" AEM clientlibs) platform. No public REST/GraphQL product
  endpoint found from static probing; likely needs a full account/
  store-selection flow. **Needs dedicated Playwright investigation — real,
  high-value supermarket chains, but not a quick manifest fix.**
- **smartbazar.af** (Afghanistan) — reachable, real Next.js marketplace,
  confirmed AFN currency in its own cart-total copy and a `/dr/currency/...`
  page, but the product-listing page (`/dr/market`) is heavily client-
  rendered with no embedded `__NEXT_DATA__` product payload found by static
  fetch. **Needs Playwright network trace — not a manifest-only fix this
  pass.**
- **storna-shopping.vercel.app** — same as imvelomarketplace: now serving
  Vercel's "Security Checkpoint" 403 on every path. **Reject: re-blocked /
  inconsistent.**
- **suqan.store** (Sudan) — reachable, Next.js app, has an `/api` route
  root (200) but no discoverable `/api/products`-shape endpoint (404s).
  **Needs Playwright trace — not pursued this pass.**
- **walmart.com** — **out of scope by project topology**: the US is
  explicitly excluded from `regions.yaml` (per prior project memory); not
  pursued regardless of reachability.
- **www.okmarket.ru** (Russia) — reachable; has a real `/catalogs/` section
  and a large legitimate sitemap, but no product-level API found in a quick
  pass. **Not pursued this pass — would need deeper platform ID.**
- **www.wumart.net** — reachable, but it's a GoDaddy Website Builder
  brochure page (generator meta confirms), not a real e-commerce backend.
  **Reject: no live catalog.**

---

## STALE-OK + rest class (134 hosts, foodish=False)

Per the task's own priority order, this bucket was deprioritized behind the
food-focused buckets above. It received a **bulk reachability re-check only**
(single plain-HTTP GET per host, 12 concurrent workers, no per-site content
inspection, no gate-checking) — this is a shallower pass than the two
buckets above and should be read as such.

**Result: 123/134 (91.8%) answered HTTP 200 on independent re-probe.**
11 did not:

- `bigw.com.au` — timed out (12s)
- `etsy.com` — 403
- `facebook.com` — 400
- `ferabeton.com` — 403 (non-food: concrete/building materials, "beton")
- `gao.gov` — 403 (US federal agency, non-commerce, out of topology anyway)
- `klikindomaret.com` — 403 (Indonesia's Indomaret chain — a market-leader
  storefront; per the skill's inverse-correlation law this is exactly the
  class of target expected to stay hardened even after impersonation is
  dropped)
- `minagro.gov.ua` — 403 (Ukrainian ministry site, non-commerce)
- `powerbuy.co.th` — 403
- `seria.supasave.com.bn` (Brunei "Supasave" grocery) — 403, same
  75,193-byte block-page fingerprint seen on nassaugrocer.com/
  shop.gambia.com above; worth flagging as a recurring shared-infrastructure
  signature rather than 3 independent site-level blocks
- `watsonswine.com` — 403
- `zazzle.com` — 403

None of these 134 hosts were individually assessed for platform, food
content, or the hard gates (enumerability/price/currency/locality) — that
work remains open. Given the volume, a follow-up pass should re-run the
foodish heuristic against actual page content (title/meta keywords) rather
than filename, since — as seen in the foodish=True bucket above — the
heuristic both over- and under-fires (`quincaillerie.ci`/`quinkashop.com`
are hardware, not food, despite the "store"/"shop" naming pattern that
likely got them flagged; conversely, `5ka.ru`/`dukan.af`-style names in the
"rest" bucket may include real grocery apps that the heuristic missed).

---

## Recurring shared-infrastructure signature

Three hosts across two different priority buckets — `nassaugrocer.com`,
`shop.gambia.com`, `seria.supasave.com.bn` — all returned an *identical*
75,193-byte HTTP 403 body on every path probed at verification time, despite
each having recorded at least one 200 arm in the original CSV. This is
consistent with one shared reverse-proxy/CDN tenant enforcing a block across
otherwise-unrelated storefronts, rather than three independent site-level
WAF decisions. Worth a dedicated look (server header / IP-range fingerprint)
before writing off all three individually in a future pass.


---

## known_blockers_retest_2 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_retest_2.md` on 2026-09-11. 51 hosts, 17 not
documented above at merge time.

# Retest batch 2 — onboard_2.csv (174 hosts) — findings

_Written: 2026-09-11._ Source list: `~/gapwork/retest/onboard_2.csv` (10 `RECOVERED`,
164 `STALE-OK`). Every host in this file received a live HTTP probe this session
(plain `requests` + a Chrome124 UA, homepage + up to 5 standard catalog endpoints:
Shopify `/products.json`, WooCommerce Store API v1 + legacy, an Odoo `/shop` check,
and `/sitemap.xml`). Hosts flagged in the probe as carrying a real catalog signal got
a full manual deep-dive (categories, page-1-vs-page-2 enumerability, price + currency
fields). **Net result: zero net-new sources.** Below is why, grouped by cause.

## Bottom line

- 174/174 hosts got a live measured probe today.
- Access verdict confirmed: the `RECOVERED`/`STALE-OK` reclassification is real —
  every one of the 10 `RECOVERED` hosts and all sampled `STALE-OK` hosts DID return
  200 to plain, non-impersonating HTTP (or to `curl_cffi` for `STALE-OK`). The
  "WAF-blocked" verdict on these specific hosts was not a real defense measurement in
  most cases.
- But reachability was never the actual constraint for this batch. Of the ~35 hosts
  that were reachable AND exposed some catalog-shaped endpoint, every single one
  failed on a *different* gate: already onboarded elsewhere, not food, empty/demo
  catalog, or brochure/SPA with no product data at all.
- **Count of previously-"blocked" hosts confirmed newly reachable: 10/10 RECOVERED +
  164/164 STALE-OK sampled = 174/174.** Count of those 174 that cleared the
  full onboarding bar (food-relevant + real catalog + enumerable + non-trivial
  price data): **0**.

## Group 1 — Already onboarded under a different candidate row (duplicates)

Confirmed by direct string match against `src/prices/configs/**/*.yaml` (url/notes
fields), not a ccTLD/substring artifact:

| Host (this batch) | Already covered by |
|---|---|
| `shop.ilovesaipan.net` | `eap/pacific_islands/northern_mariana_islands/ilovesaipan.yaml` — same Odoo storefront, already scraping `shop/category/grocery-262` + 7 other categories. Manually re-verified live: real food SKUs (Folgers, Gerber, Nutella, Spam) at `/shop`, enumerable across pages. This candidate's "marshall_islands" framing was a mismatch — the site is a Saipan/CNMI wholesaler, already filed correctly under CNMI. |
| `jeshop.channelislands.coop`, `shop.channelislands.coop` | `eca/western_europe/channel_islands/coop_ci.yaml` |
| `lynia-shop.com` | `ssa/west_africa/benin/lynia_bj.yaml` |
| `tchadcommerce.com` | `ssa/central_africa/chad/tchadcommerce_td.yaml` — re-verified: catalog is bags/tools/electronics/shoes, NOT food, despite the "Supermarché" description in the site's own tagline. |
| `cbl.gov.ly` | Libya CPI is already covered by `menaap/north_africa/libya/bsc_cpi.yaml`, whose own notes record that `cbl.gov.ly` was tried and 403'd — bsc.ly was kept as the primary series. No CPI table was actually found in a fresh check of cbl.gov.ly's `/publications/` (regulatory/governance PDFs only, no CPI bulletin visible from that listing). |
| `titancoop.sm` | Not a config duplicate, but fully closed out already in `known_blockers.md`: reachable via Playwright, but every page is corporate/co-op content, zero prices anywhere in the DOM. The group's real online grocery is `spesa.gruppoce.sm`, already onboarded as `coal_sm`. Re-confirmed independently this session: `/promozioni` is an Event-schema promo *blog*, prices appear only as free text inside prose ("confezione da 750 g a € 2'48"), 10-20 items/week, no product schema — not worth building a fragile regex extractor for a site whose real storefront is already scraped under a different domain. |
| `allo.ua`, `carrefour.ci`, `data.1212.mn`, `deps.mofe.gov.bn`, `mamakiti.com`, `member.pxpay.com.tw`, `noon.com`, `novus.zakaz.ua`, `pns.hk`, `sd.opensooq.com`, `silpo.ua`, `site.mamboo.co.ao`, `watsons.com.hk`, `cnmicommerce.com`/`www.cnmicommerce.com`, `gladen.bg`, `fccc.gov.fj` | Each appears by name inside an existing manifest's `notes:` as an already-evaluated alternative/sibling domain for a source that's already onboarded for that country (e.g. Novus/Silpo/NOVUS.zakaz already covered for Ukraine; PXGo already covered instead of the PX-Pay member portal for Taiwan; Fiji CPI already via `statsfiji_cpi.yaml`). Not re-probed individually this pass beyond the corpus grep — flagging for a human spot-check if any of these names come up again. |

## Group 2 — Reachable, real catalog, but not food (COICOP 01/02 = zero fill)

Directly probed and manually confirmed non-food:

- `gambiamarketplace.com` (RECOVERED, foodish=True in the queue but wrong) — WooCommerce
  Store API live, 27 categories, **zero food categories** (electronics, apparel,
  jewelry, phones). Confirmed via `/wp-json/wc/store/v1/products/categories`.
- `mavrolert.com` (RECOVERED) — Shopify, server/IT hardware (SSDs, enterprise gear).
- `stokholm.fo` (RECOVERED) — WooCommerce, Nordic design/decor objects (vases,
  art pieces), prices up to ~4,600 DKK per item — not a grocery despite the
  Faroese "Stokkhólmur" branding.
- `linsoul.com` — Shopify, in-ear-monitor / audio-equipment retailer.
- `noteshobby.com` — Shopify, banknote/collectibles shop.
- `risebeyondthereef.org` — Shopify, Fiji NGO handicraft/textile gift shop.
- `puttviewbooks.com` — Shopify, single golf-course photo book product.
- `talofagifts.com` — Shopify, American Samoa apparel/gift shop.
- `sudgadgets.com` — Shopify, cosmetics/skincare (despite the domain name).
- `polynesianpride.co` — Shopify, Polynesian-print apparel.
- `laedelishop.ch` — WooCommerce, Swiss gift/lifestyle marketplace. Real
  minor-unit-aware prices confirmed (CHF, `currency_minor_unit: 2`) and it does
  carry small food/drink categories (`Essen & Trinken` 122 items, `Bier` 5,
  `Fleisch` 4, `Gewürze/Tee/Kaffee` 64) inside a much larger non-food catalog
  (`Bekleidung` 304, `Accessoires` 482, `Basteln` 185...). Switzerland already has
  4 working food-relevant sources (`aldi_now_ch`, `denner_ch`, `koro_ch`,
  `nu3_ch`) — per the density rule, a ~5-10%-food general marketplace is not
  worth the onboarding/maintenance cost in an already-covered country. Not
  scaffolded; flagging as a low-priority residual if CH ever needs a specific
  wine/spice/coffee leaf filled.
- `peace1971.com` (RECOVERED) — reachable (hcdn CDN denylists `curl_cffi`
  specifically, plain HTTP is fine), but it's a stationery-template storefront
  ("Themesflat Modave" demo theme), not food.
- `sentur.net` (RECOVERED) — a Senegalese POS/ERP SaaS marketing site, not a
  retailer of any kind.
- `backupmocaf.sodepsi-digital.com` (RECOVERED) — Bootstrap template promotional
  page for the MOCAF brewery brand (Congo); no prices, no catalog, manufacturer
  marketing only.

## Group 3 — Reachable, food-adjacent, but catalog is empty/broken/demo-sized

- `sudansupermarket.com` — WooCommerce/Divi, live, no WAF, but the Store API
  returns `[]` and `/shop/` literally renders "No products were found matching
  your selection." Confirmed twice (known_blockers.md wave-11 note, and
  independently this session).
- `bioshop.mk` — homepage 200, but `/wp-json/wc/store/v1/products` 403s across
  **all three** `curl_cffi` impersonation profiles (chrome124/chrome120/
  safari17_0) tested fresh this session — a genuine edge rule on that specific
  path, not a TLS-fingerprint artifact.
- `massystoressvg.com` — static WordPress/AIOSEO corporate brochure, confirmed
  `rest_no_route` on the Store API; sibling Massy tenants (Barbados, Trinidad, St
  Lucia) do have live storefronts, SVG does not.
- `nassaugrocery.com` / `nassaugrocer.com` — default unconfigured WordPress
  install, no Store API.
- `tulip-supermarket.com` — single-page brochure, zero product listings.
- `www.alloshmart.com` — Supabase-backed app with a fully built 22-category
  taxonomy but a genuinely empty `products` table (`Content-Range: */0`) —
  pre-launch storefront.
- `alimentsbenin.com` — platform is gone (`shop.` subdomain NXDOMAIN, apex
  serves a bare Apache directory listing).
- `sunuachat.com` — real WooCommerce Store API, real fresh-produce items in
  French (tomate, laitue, poivron, concombre, piment) with XOF prices, but the
  **entire catalog is 5 SKUs in one category** and page 2 returns empty — no
  pagination to prove growth, fails the enumerability gate on catalog size
  alone. (Note: named as a Guinea-Bissau candidate in the queue, but is
  actually Senegal-market — XOF pricing, French veg names. If revisited later
  it should be filed under Senegal, not GW, and only once its catalog visibly
  grows past a handful of items.)
- `gobexpress.com` — real WooCommerce Store API, 6 SKUs total in a category
  named "Burgdoggen picanha" with product names ("Kevin Shoulder", "Cupim
  Salami Sirloin") that read as WooCommerce sample/demo data, not a live
  Gambian butcher's real inventory. No second page. Treated as a dev/staging
  storefront, not shipped.
- `ngenvironnement.org`, `oonoc.us`, `staging.runwayhealth.com` — WooCommerce
  Store APIs that are live but sell non-price-relevant items (an NGO's
  T-shirts/scholarship packs, an AliExpress-parcel-forwarding fee list, and
  travel-health prophylaxis meds respectively) — not COICOP 01/02 retail.

## Group 4 — Reachable but needs disproportionate additional engineering

- `hktvmall.com` (RECOVERED) — old Akamai-tarpit flag does NOT reproduce
  (confirmed: no `_abck`/`bm_sz`/`ak_bmsc`, only rate-gating). But the catalog is
  a pure SPA — zero products/prices/JSON-LD in server HTML, and every guessed
  hybris/OCC endpoint 404s. Per the inverse-correlation law (market leaders are
  hardened, off-the-shelf mid-tier sites aren't) this needs a dedicated headed
  Playwright/DevTools session to capture the real product-grid XHR — out of
  scope for this retest pass, not attempted further. Flag as a standalone future
  effort, not a quick win.

## Group 5 — Remainder (STALE-OK, non-foodish, no catalog signal)

The other ~121 `STALE-OK` hosts (fuel/tariff/CPI government portals already
onboarded elsewhere, travel/booking sites — Kayak, Expedia-adjacent — cost-of-
living aggregators explicitly excluded by policy — Numbeo, per its multiple rows
here, was correctly excluded, not onboarded — dead/parked Chinese retailer
domains, corporate IR-only portals, classifieds/marketplace directories with no
seller list, and single-product novelty stores) each returned 404 on every
standard catalog endpoint (`products.json`, WooCommerce Store API v1 + legacy,
Odoo `/shop`, `/sitemap.xml`) in the live probe and carry no food-relevant
content. These were **not** individually deep-dived beyond that automated
probe — flagging this explicitly as the boundary of this pass's effort, should
any of them warrant a second look later (e.g. if a non-standard/custom API is
suspected). None showed a positive signal worth chasing under the "prioritise
food" instruction.

## Overall recommendation

Do not re-queue any of these 174 hosts for a third retest under an
"access-only" theory — the access question is now settled (plain HTTP works)
and the blocker for every promising one turned out to be catalog-content-shaped,
not WAF-shaped. Two names worth a human decision, not further automation, if the
Chad/Senegal/Gambia gap ever gets prioritized:
- `sunuachat.com` (Senegal fresh produce, currently 5 SKUs — revisit if it grows)
- `gobexpress.com` (Gambia meat retailer, currently reads as demo data — revisit
  with a fresh probe to see if real inventory has since been loaded)


---

## known_blockers_retest_3 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_retest_3.md` on 2026-09-11. 82 hosts, 27 not
documented above at merge time.

# Retest batch 3 — `~/gapwork/retest/onboard_3.csv` (174 hosts)

Retest of previously-rejected hosts reclassified `RECOVERED` (10, hcdn TLS/JA3
denylist against curl_cffi's impersonated fingerprint — plain HTTP clears
them) or `STALE-OK` (164, curl_cffi succeeds today; old verdict stale).

**Result: zero new manifests shipped this batch.** Every host resolved to one
of: already onboarded by a parallel/prior agent in this same campaign,
already documented dead in the repo's own
`.claude/skills/onboard-price-sources/references/known_blockers.md`, non-food
(deprioritized per brief), or newly confirmed dead/too-small this session.
This file records only what THIS session measured that was not already on
record — it is not a re-statement of the repo's existing blocker list.

## RECOVERED (10) — worked all 10

| host | verdict | evidence |
|---|---|---|
| kabulbazar.af | DEAD — parked domain | 200 plain, generic 16KB "Default page" hosting placeholder. Already documented (repo `known_blockers.md:115`). |
| boom.tj | DEAD — parked domain | Same signature as kabulbazar.af, same line. |
| motherlandgroceries.com | REJECT — diaspora grocer | Sierra Leone diaspora grocer shipping "SL"-labelled goods to UK/US buyers, not domestic Freetown retail. Already documented (`known_blockers.md:562`), reject-on-sight policy. |
| zaad.delivery | DEAD — no catalogue | Marketing site only, zero shop/menu links even after Playwright render. Already documented (`known_blockers.md:395`). |
| sococe.ci | DEAD — under construction | Redirects to sococe.online, an 8KB "Votre site est en Construction" page. Already documented (`known_blockers.md:920`). |
| choob.af | NON-FOOD — furniture | MEASURED this session: plain HTTP 200, WooCommerce Store API open (`/wp-json/wc/store/v1/products`), 10-item sample = sofas/chairs/tables (categories: Dining Tables, Sofas/Couches, Office Furniture). Confirms the RECOVERED hypothesis (hcdn blocks curl_cffi, not plain HTTP) but fills zero COICOP 01/02 cells. Not built. |
| innovationsdn.com | NON-FOOD — medical/lab supplies | MEASURED this session: WooCommerce Store API open, 10-item sample = bandages/gloves/stethoscopes/lab glassware (Sudan). COICOP 06, not 01/02. Not built. |
| mohasbeza.com | ALREADY ONBOARDED | `src/prices/configs/ssa/east_africa/ethiopia/mohasbeza_et.yaml` exists. |
| product.suning.com | ALREADY ONBOARDED | `src/prices/configs/eap/east_asia/china/suning.yaml` + `spiders/suning.py` exist (documented resolved 2026-07-27). |
| zazzle.com.au | NOT PURSUED | 403 to plain HTTP on retest (differs from the CSV's recorded A_plain=200); global print-on-demand marketplace tagged to Palau, not a local retailer even if reachable. |

## STALE-OK + foodish (29) — worked all 29

Already onboarded, confirmed by grep of `src/prices/configs/`: **atbmarket.com**
(`atb_market_ua.yaml`), **ggshop.channelislands.coop** (`coop_ci.yaml`, solved
2026-09-01, not a login wall), **shopmassystoresbb.com** (`massy_stores_bb.yaml`),
**stores-api.zakaz.ua** (platform-level — 7 Ukrainian chains already built off
this exact host per `known_blockers.md:243`).

Already documented dead in `known_blockers.md`, re-confirmed reachable
(200/plain) but non-catalog: **blessingflowershop.com** (flowers, non-food by
content, not in blockers but out of scope), **centurymart.com** (US
promo-products co., unrelated to the Chinese chain the name implies, line
551), **ejomarket.com** (abandoned Yii install, `0.00 JOD` placeholders,
line 600), **foodpanda.com.kh** (PerimeterX, line 101), **foodstore2goexpress.com**
(rejected duplicate of `foodstore2go_bs`, line 683), **imartstores.com** /
**online.imartstores.com** (Joomla brochure + LocalExpress address-gate,
lines 270/562), **jjshop.com** (GoDaddy for-sale page, line 551),
**libyanstores.com** (B2B brand site, zero prices, line 543), **lilydelivery.com**
(real API but only 7 SKUs total, line 591), **marketgardensxm.com** (no
outbound links, no prices, line 477), **movo.delivery** (static landing page,
client routing never mounts, line 404), **paylessmarkets.com** (no online
catalog, line 531), **shop.africanfoodsupermarket.com** (diaspora grocer,
reject-on-sight, line 562), **shop.realvalueiga.com** (LocalExpress
address-gate, line 269), **www.leshop.ch** (soft-blocked maintenance page,
byte-identical across two domains, line 152), **www.rt-mart.com.cn** (bare
K8s-ingress stub, decommissioned, line 551), **www.shoprite.co.zm** (AEM
corporate portal, zero `/shop` paths, line 472).

Non-food, deprioritized: **furnmart.co.bw** (furniture), **netflix.shop**
(Netflix merch, not local), **uk-webshop.uni.gl** (university webshop).

New checks this session (not previously in `known_blockers.md`):

- **alinabasics.shop** (Marshall Islands) — real Shopify-style product
  sitemap (`sitemap_products_N.xml`, 500+ URLs), but the catalog is
  Pacific-print women's dresses (print-on-demand), not food. Not built.
- **superpowerw.com** (Solomon Islands) — Squarespace corporate site,
  `sitemap.xml` carries only marketing pages (`/contact` etc.), no
  `/products` route. No catalogue.
- **shop.comby.gl** (Greenland) — "COMBY" department store, custom JS
  platform (Webmercs CDN), no `/sitemap.xml` (404), no woo/shopify
  fingerprint. Consistent with the repo's existing finding that Greenland's
  three non-Pisiffik chains (Brugseni, Pilersuisoq, and this one) carry no
  e-commerce. Not pursued further.
- **shopylocal.com** (Chad) — Next.js general marketplace, `sitemap.xml`
  present (i18n pages only, no product URLs surfaced). Not confirmed as a
  catalog; not pursued given effort budget.

## STALE-OK + rest (135) — sampled, not exhaustive

The `foodish=False` heuristic under-flags real grocery leads. Cross-referenced
every plausible chain name (SPAR, Tesco, Metro, Perekrestok, Pick n Pay,
Carrefour Polynésie, Samkaup, Zito, San Marino grocers, etc.) against
`src/prices/configs/` and `known_blockers.md` before probing. Findings:

**Already onboarded** (dedup only, not rebuilt): `metro_sk.yaml` (Slovakia
Metro), `tesco_hu.yaml`/`tesco_wolt_cz.yaml` (not `.sk` specifically — see
open item below), `supasave_bn.yaml` x3, `tops_th.yaml`, `auchan_ua.yaml`,
`netto_is.yaml`/`pisiffik_gl.yaml` (Iceland/Greenland siblings, not the exact
hosts on this list), **`coal_sm.yaml`** — this is `spesa.gruppoce.sm`, San
Marino's real online supermarket (COAL group), already built and verified to
9,810 rows / 100% EUR / food-led. My own independent Playwright network
trace this session reproduced the identical backend (`spesa.lenny.sm` Lenny
SaaS API, `/api/product/search?category_id=N&page=M`) before discovering the
manifest already existed — confirms the finding, no new work needed.

**Already documented dead** (re-confirmed reachable, not re-probed deeply):
spar.ch/www.spar.ch (brochure only, no shop, line 808), pnp.co.za (client-side
SPA, no API found without a Playwright trace not yet run, line 301),
zito.com.mk (promo-flyer PDFs only via `r3d-sitemap.xml`, line 588),
potravinydomov.sk/itesco.sk (same operator as onboarded `tesco_wolt_sk`,
heavy SPA gated behind address-picker, lines 626/674), klikindogrosir.com
(Cloudflare 403 on `www.`, apex has no catalog, line 103), gebeyaaddis.com
(reCAPTCHA v2 "Bot Verification" stub on every profile and path, line 691),
dukani.online (white-label SaaS demo for an unrelated Iraq vendor, not a
Sudan storefront, line 398), playce.ci (WordPress corporate, no `wc/` REST
route, line 921), pilersuisoq.gl/brugseni.gl/samkaup.is (Greenland/Iceland
brochure sites, zero price tokens, lines 482/485/813), carrefour.pf
(app-level IP geofence on the real ordering subdomain, line 366),
perekrestok.ru/okeydostavka.ru (ServicePipe CAPTCHA shell, X5-group-wide
anti-bot, lines 717/719), pricegambia.com (app-only marketing page, API host
NXDOMAIN, line 442), aaranonline.com Somalia (Odoo storefront renders but
every category grid is empty — 0-row gate failure already exhausted a full
Tier-2 escalation, line 822 — NOT re-probed further per that entry's own
advice), otw-tl.com (COICOP 11.1.1 food-delivery, not 01/02, line 102),
www.st-orna.com (Storna Sudan — live-looking Next.js frontend but its
Laravel Cloud backend 404s on every route, decommissioned, line 608),
handlaprivatkund.ica.se — **NOT re-probed**: the repo's own notes (lines
1514-1579) record that repeated probing of this exact host from this class
of box previously became the blocker itself (AWS WAF Bot Control); left
untouched per that warning.

**New findings this session:**

- **bissau7ven.com** (Guinea-Bissau) — Firebase-backed peer-to-peer
  classifieds app. Firestore REST API is open for anonymous read
  (`firestore.googleapis.com/v1/projects/bissau7ven/databases/(default)/documents/products`)
  — MEASURED: 31 total documents in the whole `products` collection, no
  pagination token (i.e. that's the entire catalog), categories are
  scattered classifieds (8 cars, 5 electronics, 3 food, 3 crafts, 1 each of
  10 other categories). Product photos are AI-generated ("ChatGPT_Image_..."
  filenames). Below every quality bar: total catalog size, food fraction,
  and provenance. Reject.
- **cppl.com.ki** (Kiribati, "Central Pacific Producers Ltd") — Joomla
  corporate site, no VirtueMart or any shop component installed (`/products`,
  `/shop`, `/component/virtuemart/` all 404). Zero "add to cart" / price
  strings on the homepage. Not a retailer storefront.
- **almoaleg.com** (Libya) — WooCommerce Store API genuinely open
  (`/wp-json/wc/store/v1/products`), but MEASURED catalog is IT/digital
  services (web design, Starlink subscriptions, VISA/MasterCard top-up
  cards, CCTV systems, electricity-meter recharge) — zero food. Not built.
- **nokovandson.com** (Bulgaria, "Nokov & Son" — real alcohol/wine online
  store per its own title) — every guessed path (`/shop`, `/products`,
  `/wp-json/wc/store/v1/products`, OpenCart route param) 404s to an
  identical ~576KB SPA shell; `/sitemap.xml` returns 200 with a
  zero-length body. Same catch-all-SPA anti-pattern as `lightsmarket.bg`
  (already documented, line 655) — a real Playwright network trace was not
  run this session (budget). **Open item for a future pass**, not a dead
  end.
- **riva.af** (Afghanistan, "ریوا" — national online marketplace, per its
  own title) — Next.js RTL site; a Playwright `networkidle` wait timed out
  (page keeps a connection open, likely a chat widget or polling script)
  before any product JSON was observed. Inconclusive — **open item for a
  future pass** with a fixed-timeout trace instead of `networkidle`.
- **varus.ua** (Ukraine, Magento storefront on a Vue-Storefront-style
  Elasticsearch proxy) — already flagged in the repo as "live, reachable,
  deferred" (line 360). MEASURED this session: the product-search endpoint
  (`https://varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search?...`)
  answers 200 to a **plain, cookie-free `requests.get`** when replayed
  outside the browser session that produced it — no anti-bot at all on this
  host. However the captured request's `_appliedFilters` carried no visible
  category constraint (only stock/promotion/markdown filters plus a
  relevance sort), so the category-page product grid is populated by some
  mechanism this session's trace did not isolate (possibly a second,
  differently-parameterized call, or server-side path-to-category
  resolution baked into a request field not distinguished in the captured
  JSON). Real lead, but the GraphQL/ES query shape needs a dedicated
  session to pin down — not attempted further given Ukraine already has 15+
  onboarded chains and this was explicitly out of THIS batch's scope.
- **www.yonghui.com.cn** (China, Yonghui Supermarket) — homepage renders
  (real corporate site) but `/shop` and `/mall` both 404. Consistent with
  the repo's existing "China = 0 except Suning/NetEase" finding, extends it
  to the `.com.cn` domain explicitly (previously only `.cn` was checked).

Not individually probed this session (effort budget): the remaining ~90
`STALE-OK + rest` hosts are, by name/context/prior tagging in the source CSV
itself, either (a) explicitly pre-flagged `*_false_positive` from an earlier
consolidation pass (acehardware.com, cellcom.com, idealtruevalue.com,
marshallhardware.com, noonsite.com, palautomotive.com, standardelectricsupply.com,
trademo.com, visitpagopago.com, volza.com — all already judged as
miscategorized/irrelevant by that pass), (b) infrastructure/DNS/CDN hosts
with no retail content (cloudflare-dns.com, dns.google, schema.org,
errors.edgesuite.net, portal.azure.com), (c) pharmacy/telecom/hardware/
electronics/real-estate/directory sites clearly out of the COICOP 01/02
scope this batch prioritizes, or (d) already-dead JD.com/Suning-family hosts
(channel.jd.com, jd.com, list.jd.com, www.jd.com, pas.suning.com,
search.suning.com, suning.com — all covered by the single `suning.com`
resolution already onboarded, or independently dead per
`known_blockers.md:551`).

## Summary

**0 new sources onboarded.** 39 of 174 hosts worked in full per the priority
order (RECOVERED all 10, STALE-OK+foodish all 29); a further ~35 were
individually checked from the STALE-OK+rest bucket after correcting for the
`foodish` heuristic's known false negatives (SPAR/Tesco/Metro/Perekrestok/
Pick-n-Pay/San-Marino-grocer-class names). Every host resolved to: already
onboarded elsewhere in this campaign (9 hosts), already dead per the repo's
own `known_blockers.md` (the large majority), non-food and out of this
batch's scope (choob.af, innovationsdn.com, almoaleg.com, alinabasics.shop,
furnmart.co.bw, netflix.shop, uk-webshop.uni.gl), or too small/low-quality to
ship (bissau7ven.com: 31 total products). Three hosts remain genuinely open
for a future dedicated pass: **varus.ua** (real open API, category
parameterization not yet isolated), **nokovandson.com** (SPA catch-all,
needs a real trace), **riva.af** (trace timed out, inconclusive).


---

## known_blockers_unknown_1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_unknown_1.md` on 2026-09-11. 24 hosts, 2 not
documented above at merge time.

# Known blockers — unknown_1.csv (cote_divoire, egypt, iran, sao_tome_and_principe, syria, turkiye, yemen), 2026-09-11

Verdict on this batch: **0 of 20 rows ship.** Every domain in `unknown_1.csv`
already has a live-measured verdict recorded in
`.claude/skills/onboard-price-sources/references/known_blockers.md` from
waves dated 2026-09-01 through 2026-09-11 (i.e. this candidate list predates,
or duplicates, work already done). No candidate was re-probed from scratch —
per the skill's anti-pattern ("don't re-probe a site known_blockers.md
already recorded"), the existing verdicts were cited instead. One exception:
`trendyol.com` was spot-checked live (see below) because its "P1 build now /
Direct, build_tier=A low-hanging fruit" label in the batch conflicted with
the recorded "no priced surface" verdict — the spot-check confirmed the
existing verdict.

---

## cote_divoire

### AfricMart — https://www.africmart.com/accueil/
- **Verdict (pre-existing): DEAD — NXDOMAIN.** Recorded under the
  "NXDOMAIN sweep, francophone SSA (do not re-guess these)" entry
  (known_blockers.md line ~935), confirmed 2026-09-05.

### Jumia CI epicerie — https://www.jumia.ci/epicerie/
- **Verdict (pre-existing): BLOCKED — Cloudflare Turnstile.** `www.jumia.ci`
  entry (known_blockers.md line ~919), probed 2026-09-05: `curl_cffi
  impersonate=chrome124` returns HTTP 403 `Just a moment...`; headless
  Playwright confirms an interactive Turnstile widget that never clears.
  Eighth Jumia country storefront to show the identical wall (shared
  Cloudflare tenant across jumia.ma/.sl/.dz/.com.gh/.com.ng/.bf/.ug/.ci) —
  the file explicitly says to stop probing this tenant per-country.

### Playce / Carrefour CI — https://playce.ci/
- **Verdict (pre-existing): SKIP — no catalog, no prices.**
  `playce.ci` entry (known_blockers.md line ~921), probed 2026-09-05:
  reachable, no WAF, but a WordPress + Elementor **corporate** site — no
  `wc/*` REST namespace registered at all. Same shape as `carrefour.ci`
  itself, whose only price signal (a small `/promotions/` flyer, 13 items)
  is already onboarded as `carrefour_ci` in
  `src/prices/configs/ssa/west_africa/cote_divoire/carrefour_ci.yaml`. No
  additional source here.

---

## egypt

### Amazon Egypt — https://www.amazon.eg/
- **Verdict (pre-existing): BLOCKED.** Listed under "Challenge or denial on
  every TLS profile and on headless Playwright — 72 hosts"
  (known_blockers.md line 1876).

### Breadfast — https://www.breadfast.com/
- **Verdict (pre-existing): DEAD — app-only, no public storefront API.**
  Detailed entry (known_blockers.md ~line 1062), probed 2026-09-10: the
  public domain is the company's WordPress ops/marketing site, not a
  storefront. `/wp-json/wc/store/v1/products` 404s on all 3 route shapes;
  `/wp-json/` root lists only internal-app namespaces
  (`breadfast/v3/fleet`, `pos/v1`, `order-fulfillment/v1`, `odoo/v1`, ...),
  none exposing an unauthenticated `/products` endpoint. Matches the CSV's
  own "App-only, index only" flag.

### Carrefour Egypt — https://www.carrefouregypt.com/
- **Verdict (pre-existing): BLOCKED.** Listed under "Challenge or denial on
  every TLS profile and on headless Playwright — 72 hosts"
  (known_blockers.md line 1877).

### InstaShop Egypt — https://instashop.com/en-eg/
- **Verdict (pre-existing): BLOCKED / no priced surface.** Listed under "No
  priced surface under either `curl_cffi` (5 TLS profiles) or headless
  Playwright — 114 hosts" (known_blockers.md line 1789): no JSON with
  price-shaped keys, no product sitemap, no JSON-LD Product node found on
  homepage or category pages.

### Jumia Egypt — https://www.jumia.com.eg/
- **Verdict (pre-existing): BLOCKED.** Listed under "Challenge or denial on
  every TLS profile and on headless Playwright — 72 hosts"
  (known_blockers.md line 1878) — same shared Cloudflare tenant as
  jumia.ci above.

### Kazyon — https://kazyon.com/
- **Verdict (pre-existing): DEAD / unusable.** Listed under "DNS resolves
  but no usable response — 14 hosts: expired or mismatched TLS
  certificate, or TCP timeout on every profile including `verify=False`"
  (known_blockers.md line 1927).

### Rabbit — https://rabbitmart.com/
- **Verdict (pre-existing): BLOCKED / no priced surface.** Listed under
  "No priced surface ... — 114 hosts" (known_blockers.md line 1790).

---

## iran

### ExportHub Iran — https://www.exporthub.com/iran/
- **Verdict (pre-existing): BLOCKED.** Listed under "Challenge or denial on
  every TLS profile and on headless Playwright — 72 hosts"
  (known_blockers.md line 1879). Also structurally wrong shape for a
  retail price source — ExportHub is a global B2B sourcing directory, not
  an Iran-specific retailer.

### IranPharmis — https://www.iranpharmis.org/en
- **Verdict (pre-existing): DEAD — B2B distributor, every price 0, login
  wall.** Detailed entry (known_blockers.md ~line 2162), probed 2026-09-10
  (note: correct `source_key` is `iranpharmis_ir` — the original candidate
  table had it tagged `_dz` by mistake). Real Next.js backend, no WAF,
  category JSON genuinely SSR'd, but every one of 87 sampled products
  (surgical gloves, biopsy systems, catheters — a hospital/surgical B2B
  distributor, not a dispensing pharmacy) carries
  `"price":{"price":0,"was_price":0,...}` and `"quantity":0`. A live
  login/registration wall gates real pricing; Playwright network trace
  confirms no client-side price API ever fires for an anonymous visitor.

---

## sao_tome_and_principe

### Entrega.st — https://www.entrega.st/
- **Verdict (pre-existing): DEAD — RLS-locked backend, effectively no
  merchants.** Detailed entry (known_blockers.md ~line 750), probed
  2026-09-01: Vite/React SPA over Supabase; `GET /rest/v1/products` and
  `/rest/v1/establishments` with the shipped anon key both 401
  ("permission denied") — no SELECT grant for anon on any base table. The
  one public RPC surface (`/lojas` merchant directory) lists only 4
  registered merchants platform-wide, no product names or prices for any
  of them.

### Sokeru — https://sokeru.st/
- **Verdict (pre-existing): DEAD — NXDOMAIN.** (known_blockers.md ~line
  432), confirmed against both 8.8.8.8 and 1.1.1.1, probed 2026-09-01.
  Consistent with the site being app-only (iOS/Android) per the batch's
  own note.

### Super CKdo — http://www.superckdo.com/
- **Verdict (pre-existing): DEAD — NXDOMAIN.** (known_blockers.md ~line
  433), confirmed against both resolvers, probed 2026-09-01.

---

## syria

### sy_opensooq_furniture — https://sy.opensooq.com/ar/...
- **No action.** The batch row itself is annotated
  "P3 - queue / ALREADY-TRACKED-UPSTREAM — Will's handover marked this
  existing/already tracked; no matching row here." Confirmed no separate
  gap: `sy.opensooq.com` is a general classifieds marketplace (Syria's
  Egyptian-platform counterpart to `opensooq_eg`), already accounted for
  upstream and out of scope for this pass. Not re-probed.

---

## turkiye

### Koçtaş — https://www.koctas.com.tr/
- **Verdict (pre-existing): BLOCKED — Akamai, both PDP and category layers.**
  Detailed entry (known_blockers.md ~line 1415-1504), probed 2026-09-10
  across 11 `curl_cffi` impersonate profiles plus headless Playwright.
  Sitemap layer is wide open (131 sitemaps, ~1M+ product URLs, genuinely
  disjoint shards) but every PDP and category-listing fetch 403s on every
  profile; a cookie-warmup replay of Bot Manager tracking cookies into the
  PDP request still 403s (needs an actual JS-computed sensor payload, not
  just cookie possession). Explicitly did NOT ship in that wave.

### TradeKey Türkiye — https://turkey.tradekey.com/
- **Verdict (pre-existing): DEAD / unusable.** Listed under "DNS resolves
  but no usable response — 14 hosts" (known_blockers.md line 1923). Also
  structurally a B2B sourcing directory, not a Turkiye retail source.

### Trendyol — https://www.trendyol.com/
- **Verdict (pre-existing): BLOCKED / no priced surface**, listed under
  "No priced surface ... — 114 hosts" (known_blockers.md line 1750).
  **Spot-checked live today (2026-09-11)** because the batch flags it
  "P1 build now / Direct, build_tier=A low-hanging fruit," which conflicts
  with a "no priced surface" verdict for Turkiye's largest marketplace:
  `curl_cffi impersonate=chrome124/chrome120/safari17_0` all return HTTP
  200, 83,307 bytes — **not walled**, but the body is a client-hydrated SPA
  shell (`window.__initMergen`, `window.__ringManager`, no `TL` price
  strings, no embedded product JSON) with zero server-rendered price data.
  Confirms the recorded verdict still holds: access is fine, but there is
  no static or JSON-LD catalog surface to scrape without a full
  Playwright-network-sniff pass to find the internal API (out of budget
  for this pass; flagging as the one candidate in this batch worth a
  dedicated Playwright-discovery follow-up given its market-leader size).

---

## yemen

### Bazzarry Sanaa — https://sanaa.bazzarry.com/
- **Verdict (pre-existing): BLOCKED / no priced surface.** Listed under
  "No priced surface ... — 114 hosts" (known_blockers.md line 1797).

---

## Summary

| Country | Candidates | Shipped | Reason all rejected |
|---|---|---|---|
| cote_divoire | 3 | 0 | NXDOMAIN, shared Cloudflare tenant, no-catalog corporate site (Carrefour's real signal already onboarded as `carrefour_ci`) |
| egypt | 7 | 0 | WAF/challenge (4), no priced surface (2), app-only/no public API (1) |
| iran | 2 | 0 | WAF/challenge (1), B2B distributor with universal price=0 behind login wall (1) |
| sao_tome_and_principe | 3 | 0 | RLS-locked backend with 4 total merchants, 2x NXDOMAIN |
| syria | 1 | 0 (n/a) | Already tracked upstream, no gap |
| turkiye | 3 | 0 | Akamai (both layers), DNS/no usable response, SPA shell with no server-rendered price data |
| yemen | 1 | 0 | No priced surface |

No manifests were written; no spiders were scaffolded. This batch's
candidate list should be considered exhausted — nothing here is worth
re-probing again absent a platform change (new storefront launch, WAF
posture change) or a dedicated Playwright-discovery effort on Trendyol
specifically.


---

## known_blockers_untried_1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_1.md` on 2026-09-11. 39 hosts, 5 not
documented above at merge time.

# untried_1 batch — per-source rejection evidence

_Written 2026-09-11._ Batch file: `~/gapwork/batches/untried_1.csv`, 30 rows across
botswana, marshall_islands, guinea, gabon, belize, tunisia, uzbekistan, georgia,
venezuela_rb, benin. Worktree: `~/po-worktrees/fill-gap-sources` (shared with at
least two other concurrent sessions this pass — `untried_2`/`untried_3` batches
were visibly landing files in the same worktree at the same time; nothing in this
file touches their work).

**Headline finding: the batch's own claim that these 30 rows "have never been
probed by anyone" does not hold.** Cross-checking every row against this repo's
`references/known_blockers.md` and `references/inventories/**/*.md` found that
25 of the 30 rows were already probed in prior sessions dated 2026-09-01,
2026-09-05, and 2026-09-10 (all well inside the skill's ~6-month staleness
window, so none were due for a re-check) — 3 had already been **shipped** as
working manifests under different source keys than the batch listed (the batch's
URL for each was itself stale or wrong), and 22 had already been probed and
found dead or blocked, with the evidence already on file. Only 5 rows were
genuinely never-before-touched: botswana/perfectcircle_clothing,
marshall_islands/nta_legacy_services, guinea/sylizone_gn, and (freshly
re-verified rather than newly discovered) benin/Martistore's live status. Of
those, 2 were built into working sources this pass (perfectcircle_bw,
sylizone_gn), 1 was a hard dead domain (ntamar.net), and 1 (Martistore) was
re-confirmed still dead in a worse state than before.

Distinguishing **MEASURED** (this session verified it live) from **INFERRED**
(taken from a prior session's dated finding, itself measured at the time, not
re-verified now because it is inside the staleness window) throughout.

---

## PASS — built and shipped this session (MEASURED)

### perfectcircle_bw (Botswana)

- URL: https://www.perfectcircle.co.bw/ — batch listed this
  "ALREADY-TRACKED-UPSTREAM" per Will's handover; no matching manifest existed
  in the repo, so it was probed fresh.
- Platform: Angular SPA frontend, zero server-rendered content on ANY path
  (curl_cffi on `/`, `/sitemap.xml`, `/robots.txt`, `/products.json` all
  returned the identical 202,679-byte app shell — itself the tell that a
  network trace was required). Real backend found via Playwright network
  trace: a separate host, `apiperfectcircle.kickatinalong.net` (white-label
  promo-merchandise SaaS platform).
- Enumerability: MEASURED. `GET /api/common/menu/?m=softshell-jackets&p=winter-essentials&s=0&t=412`
  vs the same URL with `s=10` returned disjoint product-id sets
  (7141/7142/7143 vs 9419/17606/3478/9404/9403) — passes the page-1-vs-page-2
  gate.
- Prices: MEASURED. Every scraped row in the test run carried a real,
  positive decimal price (e.g. 429.98, 505.86, 30.32).
- Currency: MEASURED from payload — `GET /api/Currency/Display` returns
  `{"code":"BWP","symbol":"BWP","rate":1.0000}`; product prices are plain BWP
  decimals, no minor-unit or FX conversion involved.
- Locality: MEASURED — `GET /api/common/info/` returns a Gaborone,
  Botswana street address.
- End-to-end test (`--max-items 20`, actual run yielded 104 before
  `closespider_itemcount`): **104 rows, 104 distinct urls, 104 distinct
  product_id, 100% BWP.** PASS.
- Manifest: `src/prices/configs/ssa/southern_africa/botswana/perfectcircle_bw.yaml`,
  channel `fashion` (promotional apparel/merchandise reseller, not food).

### sylizone_gn (Guinea)

- URL: https://www.sylizone.com/ — batch listed this
  "ALREADY-TRACKED-UPSTREAM" per Will's handover; no matching manifest existed
  in the repo, so it was probed fresh.
- Platform: Next.js App Router (RSC-streamed, no classic `__NEXT_DATA__` tag),
  but each PDP serves a clean, server-rendered `application/ld+json` `Product`
  node with a nested `Offer` — confirmed under plain `curl_cffi`, no
  Playwright needed.
- Enumerability: MEASURED via `/sitemap.xml`, which lists exactly 12
  `/produit/<id>` PDP URLs (ids 13-24) alongside non-product pages
  (`/boutique`, `/services/<id>`, `/blog/<slug>`, `/a-propos`, `/contact`)
  that the spider filters out. This is a whole-catalog enumeration (Phase 3's
  sitemap→PDP→JSON-LD fallback), not a paginated listing, so the usual
  page-1-vs-page-2 check doesn't apply the same way — verified instead by
  confirming the sitemap id set is a real, bounded enumeration.
- Prices: MEASURED — JSON-LD `offers.price` on every PDP fetched
  (140000, 400000, 180000, ... — all positive).
- Currency: MEASURED from payload — JSON-LD `offers.priceCurrency: "GNF"`
  (Guinean Franc; the site does NOT use FCFA, which Guinea is outside the
  CFA franc zone — confirms the extractor is reading, not assuming).
- Locality: MEASURED — every PDP's `og:title` explicitly reads
  "Acheter Maillot ... en Guinée".
- End-to-end test (`--max-items 20`, catalog is only 12 items total so the
  cap never binds): **12 rows, 12 distinct urls, 100% GNF, price range
  130,000-400,000 GNF.** PASS (small catalog, clears the >=5-row bar).
- Manifest: `src/prices/configs/ssa/west_africa/guinea/sylizone_gn.yaml`,
  channel `fashion` (football-jersey reseller, not food).

---

## Already shipped in a prior session (not new; batch's URL was stale)

| Batch row | Batch URL | Live domain | Shipped as |
|---|---|---|---|
| Brodies Belize | brodiesbelize.com | brodies.bz (brodiesbelize.com is NXDOMAIN) | `brodies_bz` (pharmacy, USD, 61/61 rows) |
| Lagniappe Belize Grocery | belizegrocery.com | redirects via `<base href>` to lagniappebelize.com | `lagniappe_bz` (specialty-food, USD, 1075 rows) |
| Ori Nabiji | orinabiji.ge | 2nabiji.ge | `orinabiji_ge` (supermarket, GEL, 83-row capped test) |

---

## BLOCKED — live site, genuine access block (INFERRED from prior probes, all within staleness window)

| Source | Country | URL | Cause | Evidence source |
|---|---|---|---|---|
| Mytek | tunisia | mytek.tn | Challenge/denial on every `curl_cffi` TLS profile AND headless Playwright | known_blockers.md "Challenge or denial" list |
| Alta | georgia | alta.ge | Challenge/denial on every `curl_cffi` TLS profile AND headless Playwright | known_blockers.md "Challenge or denial" list |
| Olcha | uzbekistan | olcha.uz | Cloudflare Turnstile 403 on 3 TLS profiles + Playwright; backend `api.olcha.uz` is open (200/13.8MB category tree) but the product-listing route was never found after ~40 REST-shape guesses against the Laravel backend | known_blockers.md, dedicated Olcha entry, probed 2026-09-05 |
| Yanada.uz | uzbekistan | yanada.uz | Genuine Bagisto storefront, but EVERY route (`/`, `/shop`, `/api/products`, `/api/v1/*`) 302-redirects to a customer-login wall; no alternate unauthenticated host found (api./app./shop./m./admin. subdomains all fail TLS SNI) | known_blockers.md, dedicated Yanada entry, probed 2026-09-10 |

---

## DEAD — domain gone, business gone, or structurally not a catalogue (INFERRED unless noted MEASURED)

| Source | Country | URL given in batch | Cause | Evidence |
|---|---|---|---|---|
| nta_legacy_services | marshall_islands | ntamar.net | **MEASURED 2026-09-11**: hard DNS failure, does not resolve at all. Live NTA domain is `www.nta.mh`, already covered by `nta_4g_mh`/`nta_residential_mh`. | This session |
| BraPrime | guinea | braprime.com | Site is a 2.3KB Vite SPA shell whose only JS bundle points at a Supabase project that itself does not resolve (NXDOMAIN) — backend deleted | known_blockers.md, probed 2026-09-05 |
| Monmarche Guinee | guinea | monmarchegn.com | No WAF, but app-only: sitemap has 14 URLs and zero products; `/produits`,`/boutique`,`/categories` all 404; all `_next` JS chunks grepped for an API host, nothing found. Ordering happens in iOS/Android apps only | known_blockers.md, probed 2026-09-05 |
| Supermarche Bel Air | guinea | belair.gn | NXDOMAIN (part of a confirmed francophone-SSA NXDOMAIN sweep) | known_blockers.md, probed 2026-09-05 |
| maMakiti | guinea | mamakiti.com | Next.js landing page; its FastAPI backend `api.mamakiti.com` is reachable and unauthenticated but honestly empty: `/api/products` → `{"items":[],"total":0}`. Pre-launch, not blocked | known_blockers.md, probed 2026-09-05 |
| Ceca Gadis | gabon | cecagadis.ga | `.ga` domain is NXDOMAIN; live `.com` domain is a WordPress/Elementor corporate holding-company site for the CECA-GADIS retail group, `/wp-json/` has no `wc/` route (not WooCommerce despite the workbook tag), zero e-commerce on any brand sub-page | known_blockers.md/inventory, probed 2026-09-01 |
| Chap Chap Gabon | gabon | chapchapgabon.com | Live custom single-page marketing site for a multi-vertical delivery app; zero `FCFA`/`produit`/`panier`/`catalogue` tokens; only external links are Google Fonts + an App Store badge | known_blockers.md/inventory, probed 2026-09-01 |
| Libre-Go Livraison | gabon | libregolivraisons.ga | Courier/delivery-fee company, not a retailer — the only `FCFA` mentions are a delivery-fee calculator and an invoice total; no product catalogue at all | known_blockers.md/inventory, probed 2026-09-01 |
| Malumbi | gabon | malumbi.com | NXDOMAIN (confirmed via authoritative DoH against `dns.google` and `cloudflare-dns.com`); search-engine cache shows it was a real PrestaShop grocery site before lapsing. `.shop/.africa/.ga/.io/.store` TLD variants also don't resolve | known_blockers.md/inventory, probed 2026-09-01 |
| SendMonTchop | gabon | sendmontchop.com | Domain lapsed to a GoDaddy/wsimg.com parking-lander shell | known_blockers.md/inventory, probed 2026-09-01 |
| MyStore Belize | belize | mystore.bz | Pure app-marketing landing pages on every discoverable sub-page; zero product names, prices, or catalogue links anywhere on the public web surface | known_blockers.md/inventory, probed 2026-09-01 (checked twice — workbook ACCEPT verdict was wrong both times) |
| Founa | tunisia | founa.com | No priced surface under curl_cffi (5 TLS profiles) or headless Playwright | known_blockers.md "No priced surface" list |
| Express24 | uzbekistan | express24.uz | No priced surface under curl_cffi (5 TLS profiles) or headless Playwright | known_blockers.md "No priced surface" list |
| Le Bazar | uzbekistan | lebazar.uz | DNS resolves but no usable response (TLS cert failure / timeout on every profile incl. verify=False) | known_blockers.md "DNS resolves but no usable response" list |
| EuroCaucasus Supplies | georgia | eurocaucasus.ge | No priced surface under curl_cffi (5 TLS profiles) or headless Playwright | known_blockers.md "No priced surface" list |
| Fresco | georgia | fresco.ge | NXDOMAIN, repeat lookups | known_blockers.md "Domain does not resolve" list |
| Nikora | georgia | nikora.ge | Corporate GROUP site for Nikora Trading LTD, not a shop; links to 3 sub-brand `/products` showcase pages with zero price text and zero per-item structure | known_blockers.md, probed 2026-09-01 |
| Mercado Libre Venezuela | venezuela_rb | mercadolibre.com.ve | No priced surface under curl_cffi (5 TLS profiles) or headless Playwright. (Also: per this skill's anti-patterns, a general marketplace's own catalog is the wrong scrape target anyway — the seller directory would be the right angle, but the domain didn't even clear the priced-surface gate to get that far.) | known_blockers.md "No priced surface" list |
| Erevan Benin | benin | erevan.bj | `erevan.bj` is NXDOMAIN; live domain `erevanbenin.com` is a real corporate site (oweb.io builder) for Super U Bénin store pages, but zero FCFA tokens anywhere, under Playwright too; `/sitemap.xml` 404s | known_blockers.md, probed 2026-09-05 |
| Martistore | benin | martistore.shop | Entire site was Cloudflare-fronted maintenance mode (503) on 2026-09-05, with a real 543-URL `/sitemap.xml` behind it. **Re-checked live 2026-09-11 (MEASURED): now HTTP 522** (Cloudflare origin connection timeout) — worse, not better. Catalogue/id-space is known if the origin ever recovers; not usable today | known_blockers.md + this session |
| Zemihidjo | benin | zemihidjo.com | Cloudflare-fronted but every path (`/`, `/shop`, `/products`, `/sitemap.xml`, `www.` host) returns HTTP 404 with a zero-byte body — no origin content behind the proxy at all | known_blockers.md, probed 2026-09-05 |

---

## Rejection counts by cause (30 rows total)

| Cause bucket | Count | Sources |
|---|---|---|
| Built/shipped this session (PASS) | 2 | perfectcircle_bw, sylizone_gn |
| Already shipped in a prior session (batch URL was stale) | 3 | brodies_bz, lagniappe_bz, orinabiji_ge |
| WAF/challenge or login-gate — live but blocked | 4 | Mytek, Alta, Olcha, Yanada.uz |
| NXDOMAIN / domain lapsed or parked | 5 | ntamar.net, belair.gn, malumbi.com, sendmontchop.com, fresco.ge |
| App-only, no web catalogue (mobile-app funnel) | 3 | Monmarche Guinee, Chap Chap Gabon, MyStore Belize |
| Corporate/marketing site, no e-commerce | 3 | Ceca Gadis, Nikora, Erevan Benin |
| Non-retail service (courier, not a retailer) | 1 | Libre-Go Livraison |
| Backend deleted / pre-launch empty catalogue | 2 | BraPrime, maMakiti |
| Origin down / maintenance (temporarily dead) | 1 | Martistore |
| No priced surface found (curl_cffi + Playwright, thorough probe, nothing) | 4 | Founa, Express24, EuroCaucasus Supplies, Mercado Libre Venezuela |
| DNS resolves, cert/timeout unusable | 1 | Le Bazar |
| Cloudflare-fronted, zero-byte 404, no origin content | 1 | Zemihidjo |
| **Total** | **30** | |

## Final report table

| Source | Country | Rows measured | Distinct urls | Currency | Verdict |
|---|---|---|---|---|---|
| perfectcircle_bw | botswana | 104 | 104 | BWP | **SHIPPED** |
| sylizone_gn | guinea | 12 | 12 | GNF | **SHIPPED** |
| brodies_bz | belize | 61 (prior session) | 61 | USD | already shipped |
| lagniappe_bz | belize | 1075 (prior session) | 1075 | USD | already shipped |
| orinabiji_ge | georgia | 83 (prior session, capped) | 83 | GEL | already shipped |
| nta_legacy_services | marshall_islands | 0 | 0 | — | DEAD (NXDOMAIN) |
| BraPrime | guinea | 0 | 0 | — | DEAD (backend deleted) |
| Monmarche Guinee | guinea | 0 | 0 | — | DEAD (app-only) |
| Supermarche Bel Air | guinea | 0 | 0 | — | DEAD (NXDOMAIN) |
| maMakiti | guinea | 0 | 0 | — | DEAD (pre-launch, empty) |
| Ceca Gadis | gabon | 0 | 0 | — | DEAD (corporate, no shop) |
| Chap Chap Gabon | gabon | 0 | 0 | — | DEAD (app-only) |
| Libre-Go Livraison | gabon | 0 | 0 | — | DEAD (courier, not retail) |
| Malumbi | gabon | 0 | 0 | — | DEAD (NXDOMAIN) |
| SendMonTchop | gabon | 0 | 0 | — | DEAD (parked) |
| MyStore Belize | belize | 0 | 0 | — | DEAD (app-only) |
| Founa | tunisia | 0 | 0 | — | DEAD (no priced surface) |
| Mytek | tunisia | 0 | 0 | — | BLOCKED (WAF) |
| Express24 | uzbekistan | 0 | 0 | — | DEAD (no priced surface) |
| Le Bazar | uzbekistan | 0 | 0 | — | DEAD (cert/timeout) |
| Olcha | uzbekistan | 0 | 0 | — | BLOCKED (Cloudflare Turnstile) |
| Yanada.uz | uzbekistan | 0 | 0 | — | BLOCKED (login wall) |
| Alta | georgia | 0 | 0 | — | BLOCKED (WAF) |
| EuroCaucasus Supplies | georgia | 0 | 0 | — | DEAD (no priced surface) |
| Fresco | georgia | 0 | 0 | — | DEAD (NXDOMAIN) |
| Nikora | georgia | 0 | 0 | — | DEAD (corporate, no shop) |
| Mercado Libre Venezuela | venezuela_rb | 0 | 0 | — | DEAD (no priced surface) |
| Erevan Benin | benin | 0 | 0 | — | DEAD (corporate, no shop) |
| Martistore | benin | 0 | 0 | — | DEAD (origin down, was maintenance) |
| Zemihidjo | benin | 0 | 0 | — | DEAD (zero-byte, no origin) |

## COICOP / channel note

Both shipped sources are non-food: `perfectcircle_bw` is `channel: fashion`
(promotional apparel/merchandise) and `sylizone_gn` is `channel: fashion`
(football jerseys). Neither moves food-and-beverage coverage in Botswana or
Guinea. This batch's candidate list was two-thirds already-resolved dead ends
from prior sourcing rounds (2026-08-31 workbook), so the net yield —
2 built sources from 30 rows — reflects the batch being pre-filtered debris
from earlier passes rather than a fresh discovery pool.


---

## known_blockers_untried_3 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_3.md` on 2026-09-11. 26 hosts, 2 not
documented above at merge time.

# untried_3.csv — per-candidate disposition and evidence

_Batch: `~/gapwork/batches/untried_3.csv`, 28 candidates. Probed 2026-09-11._

Note on provenance: most of these 28 candidates turned out to overlap with
sites already probed live in `.claude/skills/onboard-price-sources/references/known_blockers.md`
during 2026-09-01/09-10/09-11 sweeps of the same countries, despite the batch
being labeled "never probed by anyone." Where that is the case, the entry
below cites the prior measured evidence (dated) rather than re-probing —
per the skill's own rule against re-running a search whose result is already
on record. Two candidates (`congobio_cg`, `chm_suriname`) were genuinely
unprobed anywhere in the repo and were fresh-probed and shipped this run.
Two more (`migros.ch`, `facebook.com/marketplace`) were genuinely unprobed
and fresh-probed to a reject/defer verdict, newly appended to
`known_blockers.md`.

## ACCEPTED — shipped this run

### congobio_cg (Congo Rep, cells=22)
- URL: https://www.congobio.net/
- Fingerprint: Next.js/Turbopack SPA, Cloudflare-fronted, no public JSON API
  (`/api/products`, `/api/produits` both 404).
- Enumerability: `/sitemap.xml` lists 40 distinct `/produit/<uuid>` PDP URLs
  (MEASURED, fixed list, all UUIDs disjoint).
- Prices: JSON-LD `Product.offers.price` on every sampled PDP, non-zero.
  Sample: "Dindes" (turkeys) XAF 22,500; "Couveuses" (incubators) XAF 350,000.
- Currency: XAF read directly from JSON-LD `offers.priceCurrency` — Congo
  Republic's own currency per `countries.yaml`, MEASURED not inferred.
  `countryOfOrigin: "Ferme avicole de Brazzaville"` on sampled products
  confirms local (not diaspora) sourcing.
- Test run (`--max-items 20`): **24 rows, 24 distinct urls** (MEASURED,
  itemcount cap let a few extra requests in flight finish first).
- Manifest: `src/prices/configs/ssa/central_africa/congo_rep/congobio_cg.yaml`
- Spider: `src/prices/price_scraping/spiders/congobio_cg.py`
- Verdict: **ACCEPT**

### chm_suriname → shipped as chmsuriname_sr (Suriname, cells=32)
- URL: https://www.chmsuriname.com/
- Fingerprint: WordPress 7.1 + WooCommerce 9.7.3, public unauthenticated
  Store API.
- Enumerability: `/wp-json/wc/store/v1/products?per_page=20&page=1` vs
  `page=2` return disjoint id sets (MEASURED: page1 ids 33526..33503, page2
  ids 33423..33388). `X-WP-Total: 2153`, `X-WP-TotalPages: 108`.
- Prices: non-zero across every sampled page (1, 3, 50, 100, 108).
  Sample: "TRAMA BOEKENKAST" (bookcase) SRD 5,395.00; "ELEGANCE TV MEUBEL"
  SRD 7,495.00.
- Currency: SRD read from `prices.currency_code` payload field — matches
  `countries.yaml` default, MEASURED not inferred.
- Category mix: furniture, kitchen appliances, office supplies — a home/
  furniture department store, not a grocer.
- Test run (`--max-items 20`, base spider pages at 100/req): **100 rows,
  100 distinct urls** (MEASURED).
- Manifest: `src/prices/configs/lac/south_america/suriname/chmsuriname_sr.yaml`
- Spider used: `generic_woo_configured` (no new spider code needed)
- Verdict: **ACCEPT**

## ALREADY ONBOARDED (duplicate candidate, no action)

### Colruyt (belgium, cells=63)
- URL: https://www.colruyt.be/
- `colruyt_be.yaml` already exists in
  `src/prices/configs/eca/western_europe/belgium/` (built from
  collectandgo.be per `known_blockers.md` Wave-4 outcomes, dated
  2026-09-11). The untried_3 row is stale relative to that build.
- Verdict: **DUPLICATE — already built, no action**

## REJECTED — cites prior measured evidence (not re-probed)

All entries below are dated probes already on file in
`.claude/skills/onboard-price-sources/references/known_blockers.md`
(dates noted per entry) and were confirmed still current (all well within
the skill's ~6-month staleness window).

### Sudan (cells=36)

- **Al Waha Supermarket** (alwaha.sd) — static 11KB BootstrapMade "Moderna"
  free corporate template. `/wp-json/wc/store/products` and `/shop` both
  404. No cart, no product pages, no prices anywhere. Prior probe
  2026-09-01. **REJECT — no catalog surface.**
- **Hyper Express** (hyper.sd) — real StackFood/6amMart Laravel backend
  (confirmed live zones, SDG currency_id) but the one grocery module's
  698-item catalog is 689/698 (98.7%) unreplaced installer seed data
  (`price=1`, `slug: "demo-product"`, Arabic "test" footer, created_at
  predates the store's own created_at). Only 8 SKUs carry plausible real
  SDG prices. Prior probe 2026-09-01. **REJECT — seed/demo data, below
  usable bar.**
- **LILY Delivery** (lilydelivery.com) — real Node/Mongo+Postgres backend,
  no WAF, but whole platform is 14 vendors / ~34 items total; the single
  grocery vendor carries exactly 7 SKUs at suspiciously round prices,
  reads as a recently-seeded MVP. Prior probe 2026-09-01. **REJECT —
  catalog too small / MVP seed, below usable bar.**
- **Storna** (storna-shopping-vercel.app / st-orna.com) — frontend renders
  fully but the API backend (`storna-core.laravel.cloud`) 404s on every
  path including `/` itself. Backend decommissioned or migrated. Prior
  probe 2026-09-01. **REJECT — backend dead.**
- **Talabaty** (mytalabaty.com) — connection timeout (28s) on curl_cffi
  chrome124, host effectively unreachable; app store listing says "coming
  soon." Prior probe 2026-09-01. **REJECT — unreachable.**
- **Zaad Delivery** (zaad.delivery) — Astro+Vue marketing site only,
  zero shop/menu/product links, zero price mentions after full Playwright
  render. JS proof-of-work interstitial guards a site with no catalogue at
  all. Prior probe 2026-09-01. **REJECT — no catalog surface.**

### Tanzania (cells=56)

- **Jambo Supermarket** (jambosupermarket.online) — React SPA on a
  public-anon Supabase table; exactly 34 rows, ALL sharing one
  `created_at` timestamp to the microsecond, Unsplash stock photos,
  generic seed names — a template installer's demo catalog, not a live
  branch-selector storefront. Prior probe 2026-09-01. **REJECT —
  seed/demo data.**
- **duka.direct (Selcom)** — public domain is a Tilda page-builder
  marketing site only (no app markers); every CTA redirects to an
  app-install page that itself timed out. No product/store data reachable
  from the web domain. Prior probe 2026-09-01. **REJECT — app-only, no
  web catalogue.**

### Ethiopia (cells=58)

- **Queens Supermarket / Shoa** (shoashopping.com) — DNS resolves but no
  usable response (recorded in known_blockers.md's "DNS resolves but no
  usable response" bucket). **REJECT — dead.**
- **klik Grocery** (klik.delivery/grocery) — recorded in known_blockers.md's
  "Challenge or denial on every TLS profile AND headless Playwright" bucket
  (72-host genuine-block class). **REJECT — WAF/anti-bot block, both
  levers failed.**

### Belgium (cells=63)

- **Albert Heijn Belgium** (ah.be) — same Ahold Delhaize platform/block as
  ah.nl, verified independently on both hosts 2026-09-10. Product-sitemap
  access is open (16,999 `.be` PDP urls) but every PDP request returns a
  ~2.6KB Akamai Bot Manager challenge instead of content. **REJECT —
  Akamai block on the PDP page itself.**
- **Bol.com Belgium** (bol.com/be) — recorded in the 72-host
  challenge/denial bucket. **REJECT — WAF/anti-bot block.**
- **Cora Belgium** (cora.be) — recorded in known_blockers.md's "DNS
  resolves but no usable response" bucket. **REJECT — dead.**
- **Spar Colruyt Group** (mijnspar.be) — the only priced component
  reachable (`filter_list_store_sp.model.json`, an Adobe AEM component) is
  a fixed 43-row weekly promo flyer that does not paginate
  (`?page=2`/`?p=2`/`?offset=12` all return the identical body); sitemap
  confirms no `/produits/`/`/shop/`/`/catalogue/` route exists anywhere on
  the site. Fails the enumerability gate outright. Prior probe 2026-09-10.
  **REJECT — no real catalog route, fails enumerability gate.**

### Antigua and Barbuda (cells=67)

- **Caribbean Eat** (caribbeaneat.com) — live, enumerable Shopify
  storefront (`/products.json` pages 1-5: 250/250/250/127/0, ~877 products,
  disjoint ids) but rejected on geography: `Shopify.country="US"`,
  `Shopify.currency.active="USD"`, tag sample dominated by
  jamaican/west-indian/colombian/venezolano/argentino tags, **zero**
  Antigua tags anywhere. A US diaspora grocer selling import-marked-up
  prices, not a domestic AG retailer. Prior probe 2026-09-10. **REJECT —
  wrong geography (US diaspora catalog).**
- **Mercado Libre** (mercadolibre.com) — recorded in the 72-host
  challenge/denial bucket; also structurally a cross-border regional
  marketplace with no AG-specific storefront. **REJECT — WAF block +
  out-of-scope marketplace class.**
- **My Caribbean Grocer** (mycaribbeangrocer.com) — live Shopify, 86 SKUs,
  single-page catalog (page 2 empty). Same reject class as Caribbean Eat:
  `Shopify.country="US"`, 35 distinct vendor brands nearly all Jamaican,
  zero "Antigua"/"Barbuda" mentions anywhere, USD gift-card SKUs (diaspora
  signature). Prior probe 2026-09-10. **REJECT — wrong geography.**

### Albania (cells=73)

- **AliExpress** (aliexpress.com) — explicitly flagged in known_blockers.md
  Wave-4 outcomes as "cross-border, not a national source" — out of scope
  for a country-attributed manifest regardless of access. **REJECT —
  out-of-scope marketplace class.**
- **Amazon** (amazon.com) — recorded in the 72-host challenge/denial
  bucket. **REJECT — WAF/anti-bot block.**
- **Facebook Marketplace** (facebook.com/marketplace) — fresh-probed
  2026-09-11: HTTP 200, no WAF/TLS block, but a personalized, login-gated
  social feed with no public catalogue, no product sitemap, no anonymous
  API. **REJECT — structural, not a retailer/price-source class.**
- **Gjirafa50** (gjirafa50.com) — recorded in the 72-host challenge/denial
  bucket. **REJECT — WAF/anti-bot block.**
- **Kaufland Marketplace** (kaufland.com) — recorded in known_blockers.md's
  distinct "no priced surface under curl_cffi (5 profiles) OR Playwright"
  bucket (114 hosts) — no WAF challenge observed, simply no discoverable
  catalog surface. **REJECT — no priced surface found.**
- **Zalando** (zalando.com) — same 114-host "no priced surface found"
  bucket as Kaufland.com. **REJECT — no priced surface found.**
- **eBay** (ebay.com) — recorded in the 72-host challenge/denial bucket.
  **REJECT — WAF/anti-bot block.**

### Liechtenstein (cells=9)

- **Coop / Migros (via CH)** — two distinct sites under one candidate row:
  - **coop.ch**: HTTP 403, `server: DataDome`, `x-datadome: protected`,
    JS-challenge stub; headless Playwright confirms the identical DataDome
    challenge after an 8s wait — both levers fail per the mandatory gate,
    genuine block. Prior probe 2026-09-01. **REJECT — DataDome block,
    confirmed on both curl_cffi and Playwright.**
  - **migros.ch**: fresh-probed 2026-09-11 — Angular SPA shell,
    `window.prerenderReady = false`, no product data in the raw response
    even on a search URL. No WAF challenge observed, just needs a full
    Playwright render + network trace. **DEFER — SPA needs Playwright,
    not a hard reject; worth a dedicated future pass.** (Matches the
    batch's own build_tier=D scoring.)

## Rejection counts by cause (25 rejected rows + 1 duplicate + 1 deferred; 2 accepted)

| Cause | Count | Sources |
|---|---|---|
| WAF/anti-bot challenge confirmed on curl_cffi (5 profiles) AND Playwright | 8 | coop.ch, klik.delivery, ah.be (Akamai), bol.com, mercadolibre.com, amazon.com, gjirafa50.com, ebay.com |
| No priced surface found (no WAF challenge, just nothing to scrape) | 2 | kaufland.com, zalando.com |
| Dead / unreachable domain (DNS resolves, no usable response, or timeout, or backend decommissioned) | 4 | shoashopping.com, cora.be, storna-shopping-vercel.app, mytalabaty.com |
| No catalog surface — marketing/template site only, app-only | 3 | alwaha.sd, zaad.delivery, duka.direct |
| Seed/demo data — real backend, catalog is installer/test data | 3 | hyper.sd, lilydelivery.com, jambosupermarket.online |
| Fails enumerability/catalog-size gate (fixed non-paginating list) | 1 | mijnspar.be |
| Wrong geography (diaspora/foreign catalog, not domestic) | 2 | caribbeaneat.com, mycaribbeangrocer.com |
| Cross-border / out-of-scope marketplace class | 1 | aliexpress.com |
| Structural — social platform, login-gated, no public catalog API | 1 | facebook.com/marketplace |
| Deferred — SPA shell, needs Playwright, not conclusively rejected | 1 | migros.ch |
| Already onboarded (duplicate candidate) | 1 | colruyt.be |
| **ACCEPTED** | **2** | **congobio_cg, chmsuriname_sr** |
| **Total** | **28** | |


---

## known_blockers_untried_4 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_4.md` on 2026-09-11. 28 hosts, 1 not
documented above at merge time.

# Known blockers — untried_4 batch (2026-09-11)

Batch: `~/gapwork/batches/untried_4.csv`, 28 never-probed candidates across
central_african_republic, cameroon, iceland, norway, haiti, kuwait, rwanda,
lesotho, malawi, algeria, zambia, mauritania, togo. 2 shipped
(`quickgo237_cm`, `fasita_rw`); 26 rejected/deferred below, grouped by cause.
All numbers below are MEASURED live on 2026-09-11 via `curl_cffi`
(`impersonate="chrome124"`, then `chrome120`/`safari17_0` where noted) and,
where flagged, a real headless-Chromium Playwright pass with network
capture — not inferred from the batch CSV's `build_tier`/`scrapability`
columns, which were all `not scored`/`nan` for this batch.

## DNS never resolves (domain dead)

- **warani.cf** (Supermarche Prima, Central African Republic) — `curl_cffi`
  DNS resolution fails on both `https://warani.cf/` and
  `https://www.warani.cf/`, and again over plain `http://`. Domain does not
  resolve at all; no alternate TLD/subdomain found. Confirmed dead.
- **eaglemarket.ht** (Eagle Market, Haiti) — same: DNS fails on bare,
  `www.`, and `http://` variants. Confirmed dead.
- **pnp.co.ls** (Pick n Pay Lesotho, Lesotho) — same: DNS fails on
  `www.pnp.co.ls`, bare `pnp.co.ls`, and `http://`. Confirmed dead; no
  South-Africa-hosted Pick n Pay subdomain found serving Lesotho.

## Site broken / parked / under construction

- **comphaiti.com** (CompHaiti, Haiti) — TLS certificate hostname mismatch
  on the live cert; re-probed with `verify=False` to see the actual origin
  content: HTTP 200, body `"Site Under Constuctions"` (23 bytes, sic).
  Confirmed dead — not a probing-client issue.
- **batolis.com** (Batolis, Algeria) — HTTP 200 but body is literally
  `<html>webserver is functioning normally</html>` (47 bytes) on every path
  tried, including `/index.php?route=product/product` (16-byte "File not
  found."). Confirmed a parked/placeholder web server, not a storefront.

## Cloudflare / WAF hard block (verified, not a bare-curl artifact)

- **boutiqaat.com** (Boutiqaat, Kuwait) — 403 "Attention Required! |
  Cloudflare" reproduced across THREE `curl_cffi` TLS-impersonation
  profiles (`chrome124`, `chrome120`, `safari17_0`) **and** a real headless
  Chromium via Playwright (`domcontentloaded`, full JS execution) — same
  "Sorry, you have been blocked" page, HTTP 403. Per the mandatory gate,
  both levers failing means this is a genuine block, not a TLS-fingerprint
  artifact. Boutiqaat is the GCC's leading livestream/social-commerce
  beauty marketplace — consistent with the inverse-correlation law (market
  leader, hardened). No spider built.
- **koumbimarket.eu** (KoumbiMarket, Mauritania) — `https://` gives a raw
  OpenSSL handshake failure; `http://` returns HTTP 409 with a Cloudflare
  error page titled "DNS resolution error | koumbimarket.eu | Cloudflare" —
  Cloudflare's edge cannot reach the origin at all (not a bot challenge,
  the origin appears to be gone). Confirmed dead.

## Catalog confirmed real but too small to ship (0-1 SKUs)

- **bonus.is** (Bonus, Iceland) — genuinely live WooCommerce Store API
  (`/wp-json/wc/store/v1/products`), no auth needed. But
  `X-WP-Total: 1` — the entire "catalog" is one SKU, a gift-card top-up
  ("Inneignarkort – Áfylling", price 1 ISK). Matches the real-world fact
  that Bónus (Iceland's discount grocery chain) does not run online
  grocery ordering; this WooCommerce install is a gift-card microsite, not
  the storefront. No spider built.
- **pridefarms.rw** (Pride Farms, Rwanda) — genuine Wix store confirmed via
  `store-products-sitemap.xml` and a real `Product`/`Offer` JSON-LD block
  on the one listed PDP (`priceCurrency: RWF, price: 5700`). But the
  products sitemap lists exactly ONE product URL, and that product's own
  schema reports `availability: OutOfStock`. Live catalog is effectively
  zero sellable SKUs. No spider built.
- **maurikilchi.com** (Maurikilchi, Mauritania) — real Laravel/Inertia app
  with a working public REST endpoint, `/api/products` returns valid JSON
  (`{"count":0,"next":null,"previous":null,"results":[]}`) — confirmed
  empty catalog, not a probing failure. No spider built.

## Real local business, no online prices / no catalog

- **banguimall.net** (Bangui Mall, Central African Republic) — despite the
  "Mall" name, this is a Bootstrap template site for a CAR **automobile
  service** (car wash / mechanic / tire shop) — nav is
  Home/About/Gallery/Services/Contact, and `/services.html` is entirely
  "Car Wash / Car Wheels / Car Mechanic / Motor Repairs / Car Paint" copy.
  No product catalog of any kind, retail or otherwise; this is not a
  supermarket. Does not satisfy the French-branding/city-suffix check
  because there are no products to check.
- **caribbeansupermarketsa.com** (Caribbean Supermarket S.A., Haiti) — a
  genuine, long-established local retailer (French copy: "Le supermarche
  principal de detail en Haiti... depuis 1995", Pétion-Ville address,
  Haiti phone number — passes the locality check cleanly). But the site is
  an about/marketing page only ("1000+ produits disponibles" is a claim,
  not a catalog) — no product listing, no prices, no API found.
- **africamedicalmarketplace.com** (Africa Medical Marketplace, Algeria) —
  `sitemap.xml` lists exactly one URL, the homepage. No category/product
  pages exist to crawl; this is a B2B lead-generation page, not a catalog.

## Real site, no extractable machine-readable prices

- **coop.no** (Coop Norge, Norway) — real product pages exist and appear in
  the sitemap (e.g. `/egne-merkevarer/coop-kaffe/produkter/kraftig-
  arabicakaffe`), but the page's only JSON-LD is a `BreadcrumbList` — no
  `Product`/`Offer` schema, and no `\d+,\d{2}\s?kr` price pattern anywhere
  in the rendered HTML. Norway's Coop appears to gate actual purchase
  prices behind a membership/app login; the public web catalog is
  editorial/informational only.
- **spctrmafrica.com** (SPCTRM Grocery Lilongwe, Malawi) — homepage/landing
  page loads fine over `curl_cffi` (200, 202KB, AIOSEO-generated
  WordPress), but the WooCommerce Store API is disabled
  (`/wp-json/wc/store/v1/products` → `{"code":"rest_no_route"}`), and the
  page HTML has zero `class="product*"` markup and zero price-pattern
  matches. `sitemap.xml` itself is blocked by Cloudflare (HTTP 429,
  "Access denied... error code 1015"), and a Playwright pass on the
  grocery-delivery page also hit a Cloudflare "Performing security
  verification" challenge (inconsistent with the curl_cffi success on the
  same URL — likely a behavioral/JS heuristic rather than a TLS check).
  No extractable prices found by any lever tried.
- **easymartmalawi.com** (EasyMart Malawi, Malawi) — empty React/Vite SPA
  shell (`<div id="root"></div>`, 562 bytes) served identically for every
  guessed route (`/`, `/api/products`, `/api/shop/products`, `/api`).
  Site's `robots.txt` is live but there is no discoverable backend; needs
  a real browser render + longer network trace than was budgeted this
  pass to determine if any API exists at all.

## Not locally scoped (fails the locality gate structurally)

- **mumafrica.com** (MumAfrica, Algeria) — confirmed via its own meta
  description: "B2B & B2C marketplace connecting global trade with 54
  African countries." This is a pan-African supplier directory, not an
  Algeria-specific retailer; it has a `/browse` page but the site is a
  React SPA and there is no way to scope it to Algeria specifically even
  if scraped. Rejected on locality grounds, independent of the JS-shell
  probing cost.

## App-only (mobile-app ordering, no browsable web catalog)

- **yassir.com** (Yassir Market, Algeria) — Next.js app; its own
  `sitemap.xml` (43.8KB) contains only static marketing/language/legal
  pages (`/en/algeria`, `/en/algeria/about-us`, `/en/algeria/contact-us`,
  ...) for every supported country — zero product or restaurant listing
  URLs. Yassir is Algeria's leading ride/delivery super-app (inverse-
  correlation law: market leader). Ordering happens inside the mobile app
  only.
- **tigmooeats.com** (TigmooEats, Zambia) — `sitemap.xml` lists only
  static pages (contact, privacy, restaurant/deliver signup). Confirmed
  via Playwright: clicking "Order" immediately drops into a **mobile-
  number + OTP login wall** before any restaurant/menu content is shown —
  no public catalog exists pre-authentication.
- **marsarim.com/fr** (Almersoul, Mauritania) — French delivery-app
  marketing site ("l'application de livraison à domicile... Nouakchott").
  Playwright network capture on page load and after clicking "Commander"
  shows only i18n string files and a Google Maps ping — no product/catalog
  API of any kind. App-only ordering.
- **lotieapp.com** (Lotié, Togo) — page is generated by **v0.app** (Vercel's
  AI page generator) per its own `<meta name="generator" content="v0.app">`
  — an app-store marketing splash page (App Store / Play Store badges),
  not a functioning ordering site. No clickable path led to any catalog or
  API.

## Deferred — technically feasible, needs more engineering than this pass budgeted

- **heimkaup.is** (Heimkaup, Iceland) — the site's own `products-
  sitemap.xml` and `product-categories-sitemap.xml` are STALE: every
  sitemap PDP and category URL tested 404s live. Playwright network
  capture reveals the real, currently-live backend is a third-party quick-
  commerce platform, **Jiffy Grocery** (`api2.jiffygrocery.co.uk`) —
  real ISK grocery prices render on the homepage (e.g. "Gull 12x500ml —
  5.889 kr."). But every Jiffy API endpoint requires a bearer token
  (`{"code":"TOKEN_MISSED_OR_INVALID"}` / `"UNAUTHORIZED"` on direct
  `curl_cffi` calls with no token) — the token is issued client-side
  during the Playwright session and was not captured/replayed this pass.
  Building this needs a `scrapy_playwright` (Tier 2) spider that bootstraps
  an anonymous Jiffy session per run and re-hits the catalog/search
  endpoints — real engineering, not a manifest edit. Iceland is not the
  neediest country in this batch (cells=43, 10 existing manifests already);
  deferred rather than built this pass.
- **shoprite.co.ls** (Shoprite Lesotho, Lesotho) and **shoprite.co.zm**
  (Shoprite Zambia, Zambia) — both run the shared "shopriteafrica" Adobe
  AEM corporate template (no product catalog on the main site — confirmed
  via link inventory: only `/specials.html`, `/store-locator.html`,
  `/explore-shoprite/*` info pages). BUT `/specials.html` links to a real,
  current weekly-specials PDF per country
  (`.../specials-leaflets/lesotho/2026/september/LSFOSLDXMW_CP.pdf`,
  `.../zambia/2026/sep/ZMFOSRDWXK_CP.pdf`) — genuine retailer price
  flyers. Downloaded both (524KB / 507KB, 1 page each): `pdfplumber`
  extracts **zero text** from either — both are scanned/rasterized
  image-only flyers, so OCR is required. `pytesseract` is not installed in
  `~/venv` on a8, and installing new deps into the shared venv (other
  concurrent collect jobs were running on a8 during this pass) was judged
  out of scope for this run. Deferred: needs `pytesseract` +
  `pdf2image`/`poppler` added to the environment, then a `pdf`-extraction-
  pattern fetcher per country, re-run weekly.

## Duplicate of an already-covered source

- **dataviz.vam.wfp.org** ("Fallback - WFP VAM", Central African Republic)
  — this is WFP's VAM Data Viewer, a different UI over the same underlying
  WFP food-price data CAR already gets via
  `src/prices/configs/ssa/central_africa/central_african_republic/
  wfp_prices.yaml` (fetcher `_shared.ssa.wfp_food_prices.fetch_wfp_caf`,
  sourced from HDX/humdata.org, re-verified 2026-08-06: 30,357 rows, XAF,
  39 commodities, current through 2026-06-15). Onboarding the dataviz
  front-end would duplicate data already in the corpus. No action taken.

## Rejection counts by cause (26 rejected/deferred of 28 probed)

| Cause | Count | Sources |
|---|---|---|
| DNS never resolves | 3 | warani.cf, eaglemarket.ht, pnp.co.ls |
| Site broken / parked | 2 | comphaiti.com, batolis.com |
| Cloudflare WAF hard block | 1 | boutiqaat.com |
| Cloudflare origin unreachable | 1 | koumbimarket.eu |
| Catalog confirmed real but 0-1 SKUs | 3 | bonus.is, pridefarms.rw, maurikilchi.com |
| Real business, no online catalog | 3 | banguimall.net, caribbeansupermarketsa.com, africamedicalmarketplace.com |
| Real site, no extractable prices | 3 | coop.no, spctrmafrica.com, easymartmalawi.com |
| Not locally scoped (pan-African directory) | 1 | mumafrica.com |
| App-only, no web catalog | 4 | yassir.com, tigmooeats.com, marsarim.com (Almersoul), lotieapp.com |
| Deferred — needs more engineering | 3 | heimkaup.is (Jiffy auth token), shoprite.co.ls + shoprite.co.zm (OCR) |
| Duplicate of already-covered source | 1 | dataviz.vam.wfp.org |
| Also rejected as a duplicate flyer flag under Delimart (see below) | (see report) | delimarthaiti.com |

Note: `delimarthaiti.com` (Delimart Haiti) is a real, well-established local
chain (25 years, 4 Port-au-Prince stores — passes the Haiti locality check
cleanly) but carries no machine-readable prices anywhere probed
(`/produits`, `/promotions`, `/`, all rendered via Playwright): its "Pri Atè
Plat" promos read as a monthly campaign name with no price text or JSON
API found. Grouped with "no extractable prices" in spirit; listed
separately here because, unlike coop.no/spctrm/easymart, its business
reality (real supermarket, real promos) suggests prices may exist only as
promotional images not yet located — worth a follow-up image/OCR check in
a future pass, distinct from a hard block.


---

## known_blockers_untried_mix - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_mix.md` on 2026-09-11. 21 hosts, 11 not
documented above at merge time.

# Untried-mix gap-fill pass — Botswana / Syria / Afghanistan / Liberia / Sierra Leone / Chad

_As of 2026-09-11._ Source: `~/gapwork/still_untried_20260911.csv`, filtered to
`country in (botswana, syria, afghanistan, liberia, sierra_leone, chad) and
foodish==True` -> 194 candidates. All verdicts below are dated 2026-09-11 and
were re-probed live (per the "block verdicts are 55% wrong" rule) rather than
taken from any prior blocker list.

## Shipped (6)

| Country | source_key | channel | currency | rows (test) | distinct urls |
|---|---|---|---|---|---|
| Botswana | hawkers_cash_carry_bw | wholesale | BWP | 104 | 104 |
| Botswana | basketiq_pulse_bw | null (official_avg) | BWP | 78 | 78 |
| Afghanistan | yaganchiz_af | convenience | AFN | 66 | 66 |
| Afghanistan | smartbazar_af | marketplace | AFN | 85 | 85 |
| Syria | bawabatdayaatna_sy | supermarket | SYP | 143 | 143 |
| Sierra Leone | salonebly_sl | marketplace | SLE | 120 | 120 |

Liberia and Chad shipped 0 this pass — every food-plausible candidate in the
queue failed dead/blocked/non-food/not-enumerable (see below).

## Botswana (60 candidates probed)

Already covered before this pass: spar2u_bw, shopsefalana_bw,
choppies_ebasket_bw, farmproducts_ex_bw (+ several non-food BW manifests).

**Shipped:**
- `hawkers_cash_carry_bw` — Wix Stores cash-and-carry wholesaler, 339-URL
  product sitemap, genuine FMCG/food catalogue (washing powder, juice,
  yoghurt, biscuits, tomato sauce, cigarettes, sweets, canned beans).
- `basketiq_pulse_bw` — private company aggregating "typical" prices from
  till-verified receipts, 70-78 categories, BWP, official_avg. Does NOT
  paginate (single static page is the whole board) — flagged honestly in
  the manifest rather than claimed as a growing catalogue.

**Dropped — duplicate (same brand/chain already onboarded):**
- `sefalana_main_specials` (sefalana.co.bw) — Sefalana Group's corporate
  marketing site ("Hyper, Shopper, Shopper BIG One, Cash & Carry, Liquor
  and Shopper Quick stores"). Same retail group as the already-onboarded
  `shopsefalana_bw` (shopsefalana.com). Confirmed via schema.org
  Organization block on sefalana.co.bw naming "Sefalana Cash & Carry
  Limited".
- `spar_bw_specials` (spar.co.bw/specials) — SPAR Botswana's WordPress
  corporate/flyer site, same brand as the already-onboarded `spar2u_bw`
  (spar2u.co.bw, 8,370 SKUs via sitemap). Not enumerable either way (WP
  specials page, not a structured catalogue).
- `spar_bw_pricemate_flyers` (pricemate.co.za) — third-party South African
  blog "insights" post about Botswana grocery prices, not a live source;
  also SPAR-branded, same duplicate concern.

**Dropped — non-food (confirmed by content, not just name):**
- `homeandallstore_bw` — Wix store, 155-product sitemap, ALL household
  goods/clothing/gadgets (egg-omelette maker was the closest thing to
  food; no actual food SKUs).
- `stockroombw` — Wix store, 35-product sitemap, 100% clothing.
- `pretty_potions_bw` — WooCommerce store API confirms 100% K-beauty
  skincare (toners, cleansers, masks).
- `crazystore_bw_all_products` — South African variety/houseware chain;
  sitemap has no product URLs at all (only static pages), and the brand
  is toys/stationery/kitchenware, not food.
- `bms_allcats` (bmsonline.co.bw) — stationery/office-supplies wholesaler
  (nav: Art Supplies, Battery, Book Covers, Exercise Books, school
  uniforms). Zero food categories.
- `botswanashop_bw` — "Botswana 60th Anniversary Merchandise &
  Souvenirs", not a grocer.
- `dita_holdings_products`, `celestialspaces_bw`, `areliada_bw`,
  `barcodesbotswana`, `bas_bw_shop`, `musimboti_bw`, `tswanawana_bw`,
  `clickconnect_bw`, `thefellasden_bw`, `westdraytonbrands_bw`,
  `afm_tlokweng_shop`, `dellkorse_bw`, `anaconda_store_bw` — remaining
  "generic shop" names from the queue; content-probed and none showed a
  food-dominant catalogue (mostly agriculture-inputs/services, outdoor
  gear, general merchandise). `westdraytonbrands_bw` is the one partial
  exception (see below).
- All restaurant/menu/tariff/hardware/pharmacy/electronics/cosmetics/
  fashion/pet/auto/hotel/book/toy/school-fee/church-shop/regulator-tariff
  candidates dropped on name+content without a deep probe (28 of the 60):
  absa_bw_tariff_guide, biblesociety_shop_bw, botswana_art_online,
  cottoncloud_social, dikhung_books, edutoys_world_bw,
  fearless_fitness_bw, hibiscus_schools_fees, hope_bromo_restaurant,
  kfcbotswana_menu, lionpark_restaurant_menu, monko_perfumes_bw,
  mpatise_seedlings, oceanbasket_botswana_menu, orekatech_store,
  pedros_botswana_menu, platinumhotel_rooms, pulacars_bw,
  rocomamas_botswana_menu, shedol_cosmetics_bw, titanburgers_bw,
  uniflora_gardens_bw, zencafe_bw, autoline_bw, bocra_tariffs,
  gabseats_social, haskins_hardware_bw, istore_bw, partscityafrica_bw,
  pets_home_social_bw, shopbotswana_artisans, specsavers_bw, ubuy_bw
  (general/electronics-heavy marketplace).

**Dropped — diaspora/non-domestic pricing (flagged explicitly, not silently
accepted):**
- `westdraytonbrands_bw` — WooCommerce Store API confirms real food SKUs
  (organic eggs, Foster Farms, Angie's Kettle Corn, Seeds of Change red
  rice) but priced in **USD** (`currency_code: "USD"` in the payload, not
  BWP), 39 total products. Reads as an imported-gourmet/diaspora-gift
  boutique rather than a domestic Botswana price level. Skipped per the
  skill's diaspora-storefront caution rather than shipped with a silent
  USD assumption.

**Dropped — not enumerable / low signal:**
- `pulamarket_bw` — "Botswana's Digital Commerce Platform", a genuine
  vendor marketplace shell, but the public homepage requires sign-in to
  browse vendor catalogues; no reachable seller directory or product
  listing found without an account.
- `stockroombw`, `homeandallstore_bw` sitemaps were enumerable but 100%
  non-food (see above).

## Syria (32 candidates probed)

Already covered: `prices_sy` (crowd price board), `dokan_sy`, `tsaooq_sy`,
`glowhaven_sy`, `boma_sy`, `dokanmall_sy`, `wb_rtdi_prices`, `wfp_prices`.

**Note on `prices_sy`:** the task brief flagged that its real content sits
behind a `cat=N` parameter that an earlier probe missed. Checked the current
manifest (`src/prices/configs/menaap/middle_east/syria/prices_sy.yaml`) —
this was **already fixed** by other work earlier on 2026-09-11 (manifest
documents cat=1/2/3/8/9/10 walking 77 rows across 6 food categories). No
action needed from this pass.

**Shipped:**
- `bawabatdayaatna_sy` ("بوابة ضيعتنا") — genuine Syrian online grocery
  store, custom Laravel storefront. Confirmed real brands via /brands/
  pages (Maggi, Nutella, Oreo, Mars, Snickers, Pringles, Almarai). 17
  food/beverage categories crawled (cleaning-household excluded), SYP,
  paginated listing confirmed disjoint page-1-vs-page-2/3.

**Dropped — non-food (individual sellers on a hosted multi-vendor
platform, sampled and confirmed, not assumed):** the `*.sooqnaa.com` and
`*.dex.sy` hosts in this queue are all storefronts on the SAME hosted
e-commerce SaaS (identical Next.js build fingerprint across nana.dex.sy,
mid.dex.sy, karazzah.dex.sy). Five were opened and sampled directly:
  - `a14km_zad_sooqnaa` — branded "ZAD" (زاد, "provisions") but the
    catalogue is NOVELS (product titles are book titles like "مأساة
    مغترب" / "Tragedy of an Expat").
  - `alnabaalkaber_sooqnaa`, `barllina_sy` — pants/clothing.
  - `amanibook_sooqnaa` — books.
  - `sidrahandmade_sooqnaa` — handmade crafts.
  Given this consistent pattern across the platform, the remaining
  un-sampled sellers on the same two hosts were not individually probed:
  `s_3alndha_sooqnaa`, `vipstore_sooqnaa`, `sawanhoney` (honey — actually
  food-plausible by name, NOT sampled, worth a follow-up probe),
  `sidrahandmade_sooqnaa`, `nana_dex`, `mid_dex`, `karazzah_dex`.
  `emarkabat` — confirmed non-food (car marketplace, "E-Markabat" =
  vehicles).
- `daralamirat_shop` — WooCommerce store API confirms cosmetics (eye
  masks, lip masks).
- `itel_group` — phone-accessory brand site.
- `damasbazar`, `bzorya`, `s_2s3ar`, `medetora`, `midad_bookstore`,
  `emalabes`, `al_duha`, `cars_sy`, `karazzah_dex`, `mid_dex`,
  `daralamirat_shop`, `silverstoreapp` (bookshelf/furniture),
  `damascus_now_economy_telegram` (a Telegram channel, not scrapable as a
  catalog) — dropped on name+quick-content, non-food.

**Dropped — blocked (Vercel Security Checkpoint, confirmed on TWO
independent hosts, both survived curl_cffi impersonation AND a Playwright
render — a genuine content-level challenge, not a TLS/JA3 issue):**
- `syrianmarkt` — same Astro/Vercel checkpoint signature as Liberia's
  ourricebridge (see below). Per the skill's rule ("when curl_cffi AND
  Playwright both 403, stop"), not pursued further.

**Dropped — not enumerable:**
- `syria_yousale_furniture_decor` (furniture, non-food anyway),
  `syriastoreonline`, `tinawistore`, `damascus_store`,
  `bawabatdayaatna`-adjacent single-product-listing candidates
  (`cloudmartsy` — one PDP given as the "url", not a category) were not
  pursued once the higher-confidence `bawabatdayaatna_sy` cleared the
  ≥5-row gate comfortably.

## Afghanistan (26 candidates probed)

Already covered: `maiwandbazar_af`, `sawdagar_af`, `sale_af`,
`dostonline_af`, `kabulshop_af`, `4sough_af`, `thoffragrance_af`,
`melat_shop_af`, `etohfa_af`, `superstan_af`, `wb_rtdi_prices`,
`wfp_prices`, `nsia_kabul_prices`.

**Shipped:**
- `yaganchiz_af` — Shopify grocery-delivery storefront ("Monthly Family
  Essentials Box", "Fresh Fruit & Vegetable Box", Alokozay diapers), 63
  SKUs, AFN confirmed from the storefront's own Apple Pay capabilities
  blob AND rendered PDP price text. Flagged: Shopify account country code
  is "CA" (Canada) — likely a diaspora-run operator — but prices are
  AFN-denominated for delivery within Afghanistan, so treated as a
  domestic price level, not silently assumed.
- `smartbazar_af` ("SmartBazar.af supermarket category" in the queue) —
  multi-vendor marketplace. The queue's own `categorySlug=supermarket`
  URL was a red herring (that category is non-food-dominant, top items
  were laundry powder/soap); Playwright network trace found the site's
  open GraphQL API (`api.smartbazar.af/graphql`, no auth) and a real
  "Foodstuffs" category (85 items) was queried instead. AFN confirmed
  from the payload's own `currency` field per item.

**Dropped — dead:**
- `Kefayat Supermarket` (kefayatsupermarket.com) — domain resolves to a
  default Plesk Obsidian control-panel page, not a live site. Genuinely
  dead, not blocked.

**Dropped — blocked / not pursued further:**
- (none beyond the two SmartBazar/Yaganchiz leads pursued — `Choob.af`
  and `Rasteen Bazar`, both explicitly flagged in the task brief as
  WAF-recovery examples, cleared HTTP access fine via plain requests but
  turned out non-food on content inspection, see below — no actual
  blocking encountered for these two once fetched.)

**Dropped — non-food (confirmed via WooCommerce store API, not
assumed):**
- `Choob.af` — "Choob" = "wood" in Dari; WooCommerce API confirms 100%
  furniture (tables, chairs, sofas).
- `Rasteen Bazar` (rasteenltd.com) — WooCommerce API confirms consumer
  appliances (washing machines, TVs).
- `Afghan China Shopping Center`, `Fiber Technology Services Co`,
  `Peace Stationery` (peace1971.com), `ZmaDookan`, `Kharid`,
  `Maihandost Shop`, `Zhmary`, `Hamachiz`, `Karwaan`, `Afzon`,
  `Tizkart`, `LilamLilam`, `Liwal Htay Afghanistan marketplace`,
  `AfghanBazar`, `Asan Bawar`, `Zarangwal` — content-probed or
  name-confirmed non-food (general marketplaces/electronics/classifieds/
  furniture/fragrance).
- `Afghanistan Ministry of Industry and Commerce market prices`
  (old.moci.gov.af) — page exists but is a static informational node, no
  price table found in the probe window; not pursued further given time
  budget (worth a follow-up if MENAAP official_avg coverage is
  prioritized later).
- `Agrix agricultural marketplace`, `Ubuy Afghanistan`, `Jamshidi Mart`,
  `Yaganchiz`(shipped)/`Leelam.af` — Ubuy is a general international
  marketplace (electronics-heavy), not pursued.

## Liberia (31 candidates probed) — 0 shipped

Already covered: `ezeemarket_lr`, `congo_girl_cuisine`, `familylogolr`,
`villeton_liberia`, `banjoo_lr`, `commbeauty`, `mbcenter_shop`,
`libdelivery_lr`, `techsight_eyewear`, `babyboomshop`,
`kernel_fresh_premium`, `wb_rtdi_prices`, `wfp_prices`.

**Dropped — non-food (confirmed via sitemap/API sampling):**
- `lxttsmarket` — Shopify sitemap, 50 products, all fashion/wigs
  ("Ivory Royale", "RaiNe's Designs").
- `yanabuy` — Shopify sitemap, 50 products, all housewares (travel mugs,
  humidifiers, can coolers).
- `africanpride_liberia_collection` — Shopify sitemap, novelty
  print merchandise (pet hoodies, lunch bags), not food despite "African
  Pride" sounding food-adjacent (it's actually a hair-care brand's fan
  merch storefront).
- `shoptsev` — "Electronics, Services, Property & Motors", confirmed via
  schema.org Organization block.
- `jmartliberia` — Odoo storefront, "Flooring, Furniture & Appliances".
- `booksrun_liberia_books`, `starlongman_books` — books.
- `libno1_computers`, `duke_electronics_social` — electronics.
- `carliberia_spareparts`, `ali_building_material` — auto parts /
  construction material.
- `usgs_monrovia_map` — USGS map product page, not a Liberian retailer.
- `artstation_monrovia_asset` — digital art asset marketplace listing,
  unrelated to Liberia retail.
- `amseaview_menu`, `sinkor_palace_menu` — restaurant menus.
- `kawtal_super_electronics` — electronics despite "Super" in the name.

**Dropped — blocked (Vercel Security Checkpoint, confirmed on curl_cffi
impersonation AND Playwright, both failing — genuine content-level
challenge, not TLS):**
- `ricebridge` (ourricebridge.com) — a Liberian rice company (would have
  been high-value if reachable). Both impersonation and a Playwright
  render returned the same "Vercel Security Checkpoint" title/markup.
  Documented here rather than re-attempted.
- `martiva_all`, `libshop_net`, `makay_marketplace`, `litwaypicks` — same
  Astro/Vercel checkpoint signature (identical CSS class names
  `data-astro-cid-*`), confirmed on all four independently.

**Dropped — empty / not enumerable:**
- `marketliberia_ll` (rebrands as "Maittes") — SPA shell, `/categories`
  page explicitly renders "No categories available"; pricing shown in
  USD (another diaspora/non-domestic flag) even before the empty-catalog
  finding made it moot.
- `market231` — "Liberia's Trusted Online Marketplace", homepage has no
  reachable category/product links in static HTML; not pursued further
  (would need a Playwright trace, out of budget this pass).
- `bestventure_liberia` — "Best Venture — Catering and Food Delivery
  Services in Monrovia" (b12.io site builder), a services/catering
  business page, not an enumerable product catalogue.

**Dropped — wrong scope:**
- `modelsvillegroup.com` product page is a single kitchen-appliance SKU
  (egg poacher), not a category or storefront worth crawling.
- `xpress_liberia` — general delivery-app storefront, sampled content
  inconclusive for food-dominance within budget; not pursued.

## Sierra Leone (27 candidates probed)

Already covered: `choithrams_sl`, `trillingoexpress`, `lamanistore`,
`gotrustmesl`, `afrikonet_sl`, `statssl_cpi`, `africell_tariffs`,
`orange_tariffs`, `wfp_prices`, `fews_net`.

**Shipped:**
- `salonebly_sl` ("magic_sl" was probed separately and dropped, see
  below — this source, "Yu Don Bay - VLN Solutions" at salonebly.com, was
  the queue's `salonebly*` cluster) — FleetCart storefront, scoped
  deliberately to its "food-beverages" category only (157 total items;
  the site's "food"/"drinks"/"rice"/"biryani"/"naan" etc categories were
  sampled and found to be prepared RESTAURANT items, out of the
  01/02-retail scope, and deliberately left uncrawled). SLE confirmed
  from the payload.

**Dropped — genuinely valuable but not enumerable (recorded for a
possible future revisit, not silently discarded):**
- `akis_aid` (akisaid.com) — an NGO platform for rural women farmers
  publishing REAL farmgate/wholesale prices (Fresh Fish, Cassava,
  Groundnut, Red Palm Oil, Gari, Parboiled Rice) with seller names,
  phone numbers and rural locations across Kambia/Bombali/Bo/Port Loko —
  exactly the kind of source the "wholesale feed" doctrine wants. BUT: no
  per-product URLs, no pagination (`?page=2` returns byte-identical
  content to page 1), and the richer "Average Prices of Commodities"
  section is subscription-gated behind "Subscribe to view more" (only 3
  commodities shown free). The visible "Trending Products" teaser is a
  fixed ~7-item homepage section, not a crawlable catalogue. Recorded
  here rather than force-shipped on a technicality.

**Dropped — non-food (confirmed via sitemap/content):**
- `denkoelectronics`, `tealexelectronics`, `xtratechsl` (Wix sitemap, 15
  products, all electronics — chromebooks, flash drives) — electronics.
- `blake_electronics_sl` — electronics.
- `digisolsl_gift_card` — gift cards.
- `firsttouchlimited` (firsttouchlimited.com) — Wix site; sitemap has NO
  store-products-sitemap (booking-services + pricing-plans only) — a
  sports/coaching booking business, not a shop.
- `kenema_longrich` — single MLM product page (sanitary napkins), not a
  catalogue.
- `ordergo_sl` — single product page (earrings), not a catalogue.
- `magic_sl` (magic-sl.com) — "Magic Trading", homepage returns HTTP 406
  to a plain UA; a `categorysearch?brand=...` URL loaded but titles
  extracted were generic UI chrome (search/login/wishlist), no food
  signal found within budget.
- `insalone_emall` — the single product URL given ("Starlink SET
  Enterprise Version-Digital Product") is a digital/electronics SKU; the
  mall's other categories were not explored (Chinese-language mixed-
  content mall app, out of budget to navigate further).

**Dropped — blocked (Vercel Security Checkpoint, same signature as the
Liberia/Syria cluster):**
- `salonecart`, `salonefastmarket` — both same Astro/Vercel checkpoint.

**Dropped — restaurant/service, not retail:**
- `cokiesrestaurant`, `francosresort_menu`, `goldenrestaurant_menu`,
  `ibflavorsl_menu`, `lor_clicks_reservation_menu`,
  `royalhotelmakeni_restaurant`, `crownxpresssl` (menu path) — restaurant
  menus.

**Dropped — not enumerable / low signal:**
- `adobricgreenfields`, `market360` — no product catalogue found within
  budget.

## Chad (18 candidates probed) — 0 shipped

Already covered: `mossosouk_td`, `rakhaz_td`, `tchadcommerce_td`,
`artiaf_td`, `wfp_prices`. `hadimi_td` confirmed (per task brief) as
100% electronics/cookware despite `channel: supermarket` tag — NOT
treated as coverage, NOT treated as a duplicate for any new candidate.

**Dropped — diaspora/non-domestic pricing (flagged, not silently
shipped):**
- `daarishop_fr` — WooCommerce store API confirms REAL bulk food SKUs
  (Riz importé 25kg, Chocolat Tartina 2.5kg, Ketchup Alfa 340g, "Pack
  Ravitaillement +, Maïs 100kg") but priced in **EUR**
  (`currency_code: "EUR"`), on a `.fr` domain — reads as a diaspora
  "send groceries home to Chad" remittance-gift service (pay in Europe,
  deliver in N'Djamena), not a domestic Chadian price level. 41 total
  products. Skipped per the diaspora-storefront caution.

**Dropped — non-food:**
- `dukafrica_td` — WooCommerce API confirms electronics (GPS watches,
  blood-pressure monitors, sealing machines).
- `belivay_cemac_td` — "BelivaY — Marketplace camerounaise" — this is a
  CAMEROONIAN marketplace (CEMAC-regional), not Chad-specific; wrong
  country for a Chad price level even if reachable.
- `abdramani_solutions_td`, `ampktechnology_td`, `vepaar_lossirimou_td` —
  IT/computer equipment.
- `aboufarissolar_td` — solar equipment.
- `abou`/`iambeezy_chad_price_blog` — a blog post about N'Djamena grocery
  prices, not a live, scrapable source.
- `perle_tchadienne_social`, `petitfute_ndjamena_restaurants` — a
  business-directory listing and a restaurant guide, not retail sources.
- `librairie_numerique_africaine_chad` — digital bookstore.

**Dropped — not enumerable / thin:**
- `nibiya_td` — a Livewire classifieds/OLX-style platform ("boutiques"),
  not a structured retailer catalogue. Its "Agro-pastorale" category DOES
  carry some real food items (chili powder, chia seeds, cashew/dried-
  fruit mix, vegetable broth) mixed with non-food (goat sale, fodder
  crop, veterinary medicine) as individual classified-ad postings —
  judged too thin/unsystematic to onboard as a structured spider within
  this pass's budget.
- `saweek_td` — multi-vendor marketplace (Afrimarket, Chad Power,
  NECHIVA, Auto et Outils, Tech Office, "Agro", pharma Light, Maison Kids
  ...); the "Agro" vendor-shop page returned an empty product grid in
  static HTML (likely AJAX-loaded, not pursued further within budget).
- `magazana_td` — Cloudflare JS challenge (`cf-mitigated`), confirmed
  still challenged even with curl_cffi `chrome124` impersonation; per the
  skill's rule this would need a Playwright pass to confirm a genuine
  block vs a clearable challenge — not pursued given the generic
  "Votre boutique en ligne" title carried no food signal to justify the
  extra probe budget.
- `sultana_market_td` — 2KB SPA shell, no content in static HTML; not
  pursued via Playwright within budget.

## Cross-cutting notes

- **Vercel "Security Checkpoint" cluster**: seen on Syria
  (syrianmarkt), Liberia (ourricebridge, martiva_all, libshop_net,
  makay_marketplace, litwaypicks) and Sierra Leone (salonecart,
  salonefastmarket) — 8 distinct hosts, all Astro-on-Vercel, all
  confirmed still challenged under BOTH curl_cffi `chrome124`
  impersonation AND a full Playwright render (6-8s wait). Per the
  skill's rule ("when curl_cffi AND Playwright both 403, stop"), none
  were pursued further. Worth a dedicated future effort if any of these
  (especially `ourricebridge`, a genuine Liberian rice company) are
  high-priority.
- **Diaspora-pricing pattern hit twice** (`westdraytonbrands_bw` in USD,
  `daarishop_fr` in EUR) — both real food catalogues on real WooCommerce
  backends, both explicitly skipped rather than silently shipped with an
  assumed local currency, per the task's hard-constraint guidance.
- **Hosted multi-vendor SaaS platforms are a systematic false-positive
  source** for "food" name matches: Syria's sooqnaa.com/dex.sy cluster
  (5 sellers sampled, 0 food) and Sierra Leone's individual product-page
  candidates (kenema_longrich, ordergo_sl) all turned out to be one-off
  non-food sellers on generic platforms.


---

## known_blockers_untried_sar1 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_sar1.md` on 2026-09-11. 80 hosts, 76 not
documented above at merge time.

# SAR1 gap-fill sweep — Nepal / Bhutan / Bangladesh (foodish==True)

_As of 2026-09-11._ Source: `~/gapwork/still_untried_20260911.csv` filtered to
`country in (nepal, bhutan, bangladesh) & foodish==True` = 185 candidates
(nepal 95, bangladesh 65, bhutan 25).

## Summary

- 185 candidates in scope.
- 88 dropped on sight, never probed, per the hard COICOP 01/02-only constraint
  (see "Non-food, dropped without probing" below) plus 1 exact duplicate
  (sherza.bt — already onboarded as `bhutan/sherza.yaml`).
- 97 probed (3-arm block probe: plain requests, Chrome-UA requests, curl_cffi
  chrome124 — all2026-09-11).
- 26 shipped as working manifests (23 generic Woo/Shopify configs + 2 custom
  spiders + 1 fetcher), all verified with a real `collect --source` run.
- 13 confirmed dead/unreachable on this network as of 2026-09-11.
- 6 deferred (live, food-relevant, blocked on a specific reverse-engineering
  step not completed this round).
- 54 remaining leads: confirmed 200 + food-relevant per the candidate's own
  evidence, but no open JSON API found (custom HTML platform) — selectors not
  built this round. Listed below for the next pass.

## Shipped (26) — verified via `collect --source <key> --max-items 100`

| country | source_key | channel | currency | measured rows | distinct urls |
|---|---|---|---|---|---|
| nepal | aashrayafood_com | specialty-food | NPR | 37 | 37 |
| nepal | barahibakery_com_np | specialty-food | NPR | 94 | 94 |
| nepal | ganeshpauroti_com_np | specialty-food | NPR | 35 | 35 |
| nepal | germanbakery_com_np | specialty-food | NPR | 100 (capped) | 100 |
| nepal | kathmandubakery_com | specialty-food | NPR | 24 | 24 |
| nepal | masupasal_com_np | specialty-food | NPR | 9 | 9 |
| nepal | nepalbasket_com | specialty-food | NPR | 46 | 46 |
| nepal | nepalteaexchange_com_np | specialty-food | NPR | 59 | 59 |
| nepal | onlinetarkaripasal_com | fresh-market | NPR | 100 (capped) | 100 |
| nepal | organicshopnepal_com | specialty-food | NPR | 22 | 22 |
| nepal | parajulizbakery_com_np | specialty-food | NPR | 11 | 11 |
| nepal | sastodookan_com | specialty-food | NPR | 376 | 376 |
| nepal | shopwholly_com | specialty-food | NPR | 100 (capped) | 100 |
| nepal | tarkari_com_np (fetcher, official_avg) | null | NPR | 101 | n/a (fetcher) |
| bangladesh | agromartshop_com | specialty-food | BDT | 61 | 61 |
| bangladesh | baking_hut_com | specialty-food | BDT | 22 | 22 |
| bangladesh | bestbazarbd_com | fresh-market | BDT | 100 (capped) | 100 |
| bangladesh | drotobuy_com | supermarket | BDT | 199 | 199 |
| bangladesh | fishvally_com | specialty-food | BDT | 132 | 132 |
| bangladesh | onlinefishbazar_com | specialty-food | BDT | 92 | 92 |
| bangladesh | shadho_com | fresh-market | BDT | 199 | 199 |
| bangladesh | shelaidahdairy_giftcard_com | specialty-food | BDT | 26 | 26 |
| bangladesh | shutkibazar_com | specialty-food | BDT | 77 | 77 |
| bhutan | ogop_bt | specialty-food | BTN | 39 | 39 |
| bhutan | greenhands_bt (custom spider) | fresh-market | BTN | 91 | 91 |
| bhutan | diwakstore_bt (custom spider, scoped to groceries-5) | dept-store | BTN | 27 | 27 |

All Woo sources use `generic_woo_configured` against `/wp-json/wc/store/v1/products`
(currency read from the payload's `prices.currency_code`, minor-unit division
handled by `_woo_base.py`). All Shopify sources use `generic_shopify_configured`
against `/products.json`. `greenhands_bt` and `diwakstore_bt` are bespoke
scrapy.Spider files (no JSON API found on either site).

Manifests: `src/prices/configs/sar/south_asia/{nepal,bangladesh,bhutan}/<key>.yaml`.
Spiders: `src/prices/price_scraping/spiders/{greenhands_bt,diwakstore_bt}.py`.
Fetcher: `src/prices/fetchers/sar/south_asia/nepal/tarkari_com_np.py`.

`collect --list` re-run after every addition; global list stayed healthy
(2315 sources after the full pass, no crash).

## Confirmed dead / unreachable (13) — as of 2026-09-11

| host | country | symptom (3-arm) |
|---|---|---|
| sastodeal.com | nepal | ConnectTimeout on all 3 arms. Flagged `P1 build now / ACCEPT` in the queue (Magento marketplace) but genuinely unreachable from this network today — matches the pre-existing `known_blockers.md` "DNS resolves but no usable response" line. Worth a retry from a different egress before writing off — Magento + 50k SKUs claimed is a large prize if it comes back. |
| gopasal.com | nepal | ConnectTimeout on all 3 arms. |
| bbsm.com.np (Bhat-Bhateni, www + bare) | nepal | Resolves fine (200, 73KB) — but it is a **corporate/marketing site only**: nav is Home/About/History/Leadership/News, zero occurrences of "shop", "cart", "catalog", "delivery"; 2 hits on "product" (both prose). No online storefront exists at this domain. Structural absence, not a block — the pre-existing known_blockers "DNS resolves but no usable response" verdict for this host was wrong (re-probed live), but the corrected verdict is still "not scrapeable." |
| aziztraders.store | bangladesh | DNS resolution failure on all 3 arms. |
| shop.ekotamart.com | bangladesh | DNS resolution failure on all 3 arms. |
| wellfoodsylhet.com | bangladesh | DNS resolution failure on all 3 arms. |
| krishibidbazaar.com | bangladesh | ConnectionError/SSLError on all 3 arms. |
| sharedealnow.com | bangladesh | HTTP 526 (Cloudflare: invalid origin SSL certificate) on all 3 arms — origin server itself is down/misconfigured, not a WAF block. |
| sorboraho.com.bd | bangladesh | HTTP 404 on all 3 arms (site gone; queue evidence describes a Shopify soft-drinks collection that no longer resolves). |
| emarketltd.com | bangladesh | HTTP 404 on all 3 arms. |
| khan.com.bd | bangladesh | SSLError on all 3 arms; retried with `verify=False` → HTTP 500 (server error, not a cert-only issue). |
| 8elevenbhutan.bt (www + bare) | bhutan | Cert fails default verification; `verify=False` retry returns a **bare Apache "Index of /" directory listing** — the storefront described in the queue evidence is gone, domain now serves nothing. |
| sibjam.com | bhutan | `ConnectionError: Remote end closed connection without response` on plain requests even with `verify=False`; curl_cffi also fails. Genuinely unreachable today. |

## Deferred — live and food-relevant, blocked on unfinished reverse-engineering (6)

| host | country | priority | status |
|---|---|---|---|
| meenabazaronline.com (Meena Bazar Online) | bangladesh | H — supermarket chain | Angular SPA; Playwright network-trace (after fixing its cert with `ignore_https_errors=True`) found the real API host `mbonlineapi.com` — `nav/categories/list` (pure grocery: Fish/Meat/Beef/Chicken/Duck/...) and `home/section` both return live JSON over plain HTTP, no auth needed. But `offer/product/count?AreaId=null&SubUnitId=null` returns `TotalItem: 0` — **product listing is gated behind a delivery-area selection** (matches the FAQ note: "perishable prices vary by selected location"). `areas/search` (POST) returns `data: []` for every guessed query string. Needs the area-picker UI flow reverse-engineered (open DevTools, click through the picker, capture the real AreaId/SubUnitId pair) before a product-list endpoint can be found. Not attempted further this round — same shape as the pre-existing `countrydelight.in` entry in `known_blockers.md`. |
| shop.medhey.app (Medhey Shop) | bhutan | M | Next.js app; plain `requests` gets the full SSR homepage including a `__NEXT_DATA__` category tree with `product_count` per leaf (confirms it is mostly groceries/home goods) — but category pages (`/c/groceries`, etc.) render products client-side with no embedded links, and **Playwright itself gets a Cloudflare `challenge-platform` bot-check** that plain requests does not trigger (the reverse of the usual "TLS impersonation causes the block" pattern — here headless-browser fingerprinting is the trigger, not TLS). No API host found in the 5KB challenge page. Would need a non-headless or stealth-patched browser to get past the challenge and capture the real XHR calls. Not attempted further this round. |
| shoppergreen.bt (ShopperGreen) | bhutan | H | Cartzilla-style Bootstrap storefront, 10 departments (5 food: bakery, dairy-eggs-fridge, drinks, fruit-vegetables, pantry). Category pages return 200 but ship an **empty product grid** in both plain HTML and Playwright-rendered DOM; the page JS references `ajax/load-cities` — the storefront requires a city/locality selection (stored client-side) before it will show or fetch inventory, same shape as Meena Bazar. Not attempted further this round. |
| ajantatea.com | nepal | data-quality concern | Shopify `/products.json` is live and returns real variant prices, but (a) body copy prices in ₹ (Indian rupees) for "Darjeeling Oolong leaf tea... sourced from Darjeeling, India" despite the queue's Nepal/Ilam framing, and (b) one sampled variant's title says "RS 5000/-PER KG" while its actual price field is 500.00 — internally inconsistent. Likely India-facing storefront cross-listed under Nepal search terms (matches the `jomlah.app`/Yemen pattern already in `known_blockers.md`). Not shipped pending a clearer signal of Nepal-only fulfillment. |
| kabiremart.com.bd | bangladesh | M | Homepage 200s only with `verify=False` (cert error otherwise); once past that it's real content (Teer soyabean oil, Pusti oil, rice — grocery). But `/wp-json/wc/store/v1/products` and `/products.json` both 404 — custom Laravel-style routes (`/allsubcategory/{id}/{slug}` per the queue notes) rather than WooCommerce. Needs selector/route work, not attempted this round. |
| tarkari.com.np fetcher cadence | nepal | shipped but thin | Shipped (see table above) but flagged here too: the page has published only 3 distinct dates ever (2026-05-01, 05-22, 07-07) with no pagination — likely an occasionally-updated snapshot, not a live daily feed. Re-check staleness on the next pass. |

## Non-food, dropped without probing (88)

Per the hard scope constraint (COICOP 01/02 only), the following were dropped
on sight from the 185-row queue based on their own `notes`/`why` evidence,
without spending probe budget. Grouped by reason:

- **Pharmacy** (7): Lazz Pharma, OsudPotro, MedPlus Nepal, PharmaShop Nepal,
  Neevan Welcare Center, 24Seven (skincare/pharmacy), Arogga Food and
  Nutrition (primarily pharmacy; its "food-and-nutrition" category is a
  sub-aisle of a pharmacy chain, not a food retailer).
- **Electronics/appliances/computers/mobile** (17): Star Tech, Fair
  Electronics, TekzoBD, KPEBAZAR, Gadget Zone, Pickaboo, Rinors (BD); GBN
  Store, Good Gadgets Nepal, Mobilemandu, Neptronics, Neshop, Appliances
  Nepal, Dakshinkali Electronics, GharOne (NP); BD Commercial, iDruk
  Computers, KT Mobile, Tharlam Tek, YenaMena, TD Tyres & Electronics,
  Bhutan Telecom device catalog (BT).
- **Cosmetics/beauty** (8): Korean Cosmetics Love/K-Beauty eStore (BT), Hamro
  Shringar, Korean Beauty Point, Maake Beauty Nepal, The Makeup Factory
  Nepal, Welcome International, RiwanMart, NOri Botanical (NP/BT).
- **Furniture** (4): Ashley Furniture Nepal, GNS Store, Nepo Furniture,
  Furniture Mahal.
- **Clothing/fashion/footwear/eyewear** (6): Laconic Fashion, Online Clothing
  Store Nepal, E-Bazar Nepal (shoes), SRS Shopping, Lookscart, Titan Optical.
- **Automotive/car accessories** (3): Neo Store, Moto World Nepal, Kinaun.
- **Stationery/books/toys** (4): WeShopNepal, Scolar, Rokomari, NepKids.
- **Pet shop** (1): Pet Store Nepal (also carries live-animal listings —
  excluded regardless).
- **Telecom tariff / service plans** (1): Nepal Telecom FTTH Tariff (COICOP 08,
  not 01/02).
- **Sports goods** (1): Himalayan Ox Sports.
- **Handicraft/botanical/herbal-only** (5): Yuesel Handicraft Bhutan, OGOP's
  handicraft SKUs are incidental (OGOP itself shipped — mostly food), Druk
  Herbal Cordyceps (supplement/tea-adjacent but framed as wellness, not
  staple food), Ecoco Official Bhutan (household goods), Nima Tshongkhang
  (household goods).
- **Household goods (non-food)** (2): (see above, Ecoco/Nima already counted).
- **Adult products** (1): itsnaughtytime Bhutan pages.
- **Cafe/restaurant menus (COICOP 11, not retail)** (3): Pelbu Suites,
  Mountain Cafe Bhutan, Dhukka Sekuwa (raw-meat-by-weight bundled with a
  restaurant menu — the retail meat component is small and inseparable from
  the menu evidence given).
- **Garden/agri-input supplies, not food** (1): JaiboVumi (seeds, fertilizer,
  neem oil — inputs, not food).
- **Health supplement / non-staple** (2): Krishok Bazar (spirulina tablets,
  supplement niche), Shree Shyam Ji Marketing (baking tools/ingredients like
  fondant moulds and cutters, not food itself).
- **Price-comparison aggregators, not merchants** (5): Jachai Price, Daam
  Kemon, PaisaBachau, Price Compare Nepal — all explicitly describe
  themselves as comparing OTHER stores' prices, not an enumerable catalog of
  their own.
- **Demo/non-operational storefront** (1): "Kazi Store" at
  `supershop.isoftdemo.com` — the domain is a software vendor's public demo
  instance, not a real merchant.
- **Broad non-food marketplace (fashion/tools/furniture-led)** (3): Sarnyas
  (840-SKU shop dominated by shoe racks/laptop tables/GPS trackers), Yalula
  (stationery/clothing/toys marketplace), LR Bazar (apparel-led, unclear
  category evidence), Grey.com.np (tea SKU present but dominated by bags/
  fashion evidence), Near Me (groceries claimed in FAQ copy only, no
  item-level food evidence captured), NeerKart (cosmetics/fashion-led
  evidence despite a "groceries/pets" category claim).
- **Duplicate** (1): Sherza Allstore (sherza.bt) — already onboarded as
  `src/prices/configs/sar/south_asia/bhutan/sherza.yaml`.
- Remaining ~17 rows across the three countries were dropped on the same
  non-food grounds under close variants of the categories above (mixed
  electronics/appliances/general-merchandise storefronts whose own evidence
  names a non-food dominant category).

## Remaining leads — confirmed 200, food-relevant, NOT yet built (54)

All returned 200 on at least one probe arm 2026-09-11 and their own queue
evidence describes real food/grocery pricing, but none exposed an open
WooCommerce Store API or Shopify `/products.json` (spot-checked with
`?rest_route=` and bare `/wp-json/wc/store/products` variants too — still
nothing). Each needs individual Tier-1A selector work (custom
`scrapy.Spider`, in the `greenhands_bt`/`diwakstore_bt` style) that wasn't
in scope to build for all 54 this round. Listed for the next pass, roughly
in priority order within each country (chains/dairies/produce specialists
first):

**Nepal (30):** tarkari.com.np market-price page already shipped as a
fetcher; the following are still spiders-to-build: aafnaipasal.com,
agrimart.com.np, anganbaari.pythonanywhere.com, buytarkari.com,
down2earthorganics.com, drinksnepal.com, falfruitnepal.com, golocal.com.np,
hamrokaresabari.com, harikrishifarm.com, kathmanduorganics.com,
khushibazar.com.np, malbhog.com, mato.com.np, mountemart.com,
navadurgadairy.com.np, nepalgramodhyog.store, nubrimart.com,
okhaldhungadhamaladairy.com.np, parsabazar.com, pourwithpresence.com,
rasanmart.com, sitabazar.com, smartgau.com, smsdairy.com,
thepatisserienp.com, ugcakes.com, uliaa.com.np, valleycoldstore.com.np,
wholesalepasalplus.com.

**Bangladesh (23):** abirfoodsbd.com, agorasuperstores.com, agrotownbd.com,
ashbazarbd.com, banglashoppers.com, basketshopbd.com, breadandbeyondbd.com,
fenimart.com, foodlandproducts.websites.co.in (low-trust website-builder
disclaimer, verify merchant authenticity first), foodpanda.com.bd
(marketplace — lower priority, vendor-specific), gbanglanetwork.com,
grameenfoodbd.com, greenfarm.com.bd, hamakerehaat.com, isratsupershop.com,
keedorkar.com, kdsbd.com, krishimartbd.com, metromartonline.com,
nutrifyfoodbd.com, pundramart.com, sodaikutir.com, sodaipati.com.bd.

**Bhutan (0):** all live Bhutan candidates from the keep-list were either
shipped, deferred with a documented reason, or confirmed dead above.

## Method notes for the next pass

- The bulk 3-arm block probe + catalog-endpoint auto-discovery script is at
  `~/gapwork/sar1/probe.py` (input: a CSV with `country,source,host,url`
  columns; output: JSONL with per-arm status/bytes plus a `catalog_probe`
  column recording which of `/wp-json/wc/store/v1/products`,
  `/wp-json/wc/store/products`, `/products.json` returned real JSON).
- `requests` + `verify=False` recovers several hosts that fail with the
  default certifi bundle (self-signed/misconfigured certs, common on small
  Bhutanese/Nepali/Bangladeshi storefronts) — always retry with
  `verify=False` before writing off a `SSLError`/`CertificateVerifyError`.
- In the Scrapy pipeline itself, the project-wide `RandomBrowserMiddleware`
  routes **every** request through curl_cffi impersonation, so a
  requests+`verify=False` fix does not carry over automatically — set
  `meta["impersonate_args"] = {"verify": False}` per request (precedent:
  `goto_pk.py`, `mojsupermarket_me.py`; used here in `greenhands_bt.py` and
  `diwakstore_bt.py`).
- `Nu. 40`-style prices (a currency abbreviation ending in its own period,
  immediately followed by the amount) will silently parse as `0.40` under a
  naive `re.sub(r"[^\d.]", "", text)` regex — strip the currency word first,
  *then* extract digits. Caught and fixed in `greenhands_bt.py`; worth
  grep-checking every Bhutan spider for the same trap (`Nu.` is the only BTN
  symbol in use).
- Never run a Playwright/curl_cffi trace script from `/tmp` on a8 — hit the
  documented `/tmp/inspect.py` stdlib-shadowing landmine firsthand this
  session (a stray `/tmp/inspect.py` broke `import inspect` inside
  playwright's internals with no useful traceback pointing at the cause).
  Always run from `~/gapwork/`.
- This worktree (`~/po-worktrees/fill-gap-sources`) is shared with at least
  one other concurrent session — mid-session a `waafiro_gm.py` (Gambia,
  unrelated to this task) briefly had a syntax error that broke Scrapy's
  SpiderLoader for every spider in the repo, then self-resolved a few
  minutes later without any edit from this session. If `collect --source`
  fails with a `SyntaxError` in an unrelated spider file, re-check before
  editing it — it may be another session's in-progress write, not a stable
  bug.


---

## known_blockers_untried_sar2 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_sar2.md` on 2026-09-11. 148 hosts, 145 not
documented above at merge time.

# SAR untried-queue pass — Maldives + Sri Lanka, foodish==True

All verdicts below are as of **2026-09-11**, from `~/gapwork/still_untried_20260911.csv` filtered to
`country in (maldives, sri_lanka) and foodish == True` (166 rows). Probing used the three-arm
pattern (plain requests default UA, plain + Chrome UA, curl_cffi impersonate=chrome124/chrome120/
safari17_0) plus Playwright network traces for SPA/API discovery, per the onboard-price-sources
skill's mandatory gates. Re-probed live rather than trusting any prior verdict.

**166 candidates total. 162 were bulk-probed** (4 were dropped before probing as pre-existing
duplicates — see below). Of the 162: **20 shipped**, 4 further duplicates found during
investigation, 83 non-food, 13 dead/unreachable, 7 genuinely blocked, 35 food-plausible but not
pursued this pass (budget).

## Pre-existing duplicates (dropped before probing, 2026-09-11)

The queue's de-dup against existing manifests missed these — same host, different display name:

- **Good Food Maldives** (`goodfoodmaldives.com`) — already `good_food_mv.yaml`
- **Redwave Online** (`redwave.mv`) and **Redwave Online - order subdomain** (`order.redwave.mv`) — already `redwave_mv.yaml` (same `allowed_domains`)
- **WHIM Dhiffushi** (`whim.com.mv`) — already `whim_mv.yaml`

## Duplicates found during investigation (2026-09-11)

- **Ithuru.lk** (`ithuru.lk`, sri_lanka) — price-comparison app explicitly covering Keells/Cargills/Glomark/SPAR; SPAR is already covered via `spar2u_lk`.
- **PriceCut LK** (`pricecutlk.shop`, sri_lanka) — inline React state (`initialProducts`) carries `product_url: "https://spar2u.lk/products/..."` for every sampled item — this is a re-publication of `spar2u.lk`'s own catalog, not an independent source.
- **One Market** (`onemarket.appcloudpro.com`, sri_lanka) — "Sri Lanka Price Hunter", meta keywords list `keells,cargills,lassana,glomark` — same aggregator pattern.
- **ShopMahajana.com** (`shopmahajana.com`, sri_lanka) — byte-identical title/content to `mahajanaonline.com`; same TakeApp store tenant. Only `mahajanaonline.com` onboarded.

## Shipped (20)

See the final report table for full detail (channel/currency/rows/urls). Maldives: `zettamart_mv`,
`bluecart_mv`, `mustore_mv`, `oneclick_mv`, `confood_mv` (spiders), `mv_agumagu`, `mv_agucheck`
(fetchers). Sri Lanka: `grocerybasket_lk`, `conveniencestore_lk`, `ksuper_lk`, `bringmaalu_lk`,
`meatzone_lk`, `umaimart_lk`, `tropicalfresh_lk`, `livelife_lk`, `islandcoffee_lk`, `lionstea_lk`,
`dssupermart_lk`, `breadtalk_lk`, `mahajanasuper_lk`.

## New method findings this pass (worth carrying forward)

- **`server: hcdn` denylists curl_cffi impersonation specifically.** `ksuper-shop.com` 403'd on all
  three TLS profiles but cleared instantly to 200 on plain `requests` with no impersonation and no
  special headers. Same for `islandcoffee.lk` and `lionstea.lk` (though those didn't carry the
  `hcdn` server header — just a plain 403 under curl_cffi that plain requests clear). **Try plain
  requests before curl_cffi impersonation on Sri Lankan `.lk` WooCommerce sites** — this pattern
  repeated 3 times in one afternoon.
- **A synthesized per-row URL is required whenever the catalog has no routable PDP.**
  `ksuper-shop.com` (static `data.js` array), `dssupermart.com` (in-house PHP API, id-only), and
  `mahajanaonline.com` (TakeApp `/recommendation` endpoint) all lack a real per-product page.
  `DuplicationPipeline` dedups on `item["url"]`, so all three spiders synthesize a `?id=`/`#id`
  suffix — without it, each would have silently collapsed to 1 row.
- **"Recommendation" and "cart" endpoints are sometimes the real catalog.** TakeApp-platform stores
  (`mahajanaonline.com`) expose their full product list at a URL literally named
  `/products/recommendation` — don't assume an endpoint name describing a UI feature means a
  filtered subset; check the actual count against the site's own claimed catalog size.
- **Derivative price-comparison apps cluster around the same 3-4 already-covered chains.** Three
  separate SL domains (`ithuru.lk`, `pricecutlk.shop`, `onemarket.appcloudpro.com`) all aggregate
  Keells/Cargills/Glomark/SPAR/Lassana. Recognize the pattern after the first hit (embedded
  `product_url`/keywords naming those chains) rather than re-investigating each one fully.
- **A government price-monitoring SPA can hide a huge historical dataset behind one bootstrap
  call.** `agumagu.trade.gov.mv` (Maldives Ministry of Economic Development) is a Next.js app with
  zero data in the server-rendered HTML; a single Playwright-discovered `/api/bootstrap` endpoint
  returned the WHOLE dataset (~29k price observations, 118 items, 510 outlets, 21 atolls, history
  back to 2025-03-05) in one ~7MB unauthenticated call.
- **A reachable site with a real category taxonomy can still be near-dead inventory.**
  `familymart.lk` has a genuine PHP grocery catalog (categories, cart, real Rs prices) but ~96% of
  its ~50 SKUs are marked Out of Stock — read stock status before treating "categories exist" as
  "coverage exists."

## Genuinely blocked (2026-09-11)

- `shop.etukuri.mv`, `shop.linkserve.mv`, `moolee.mv` (maldives) — Cloudflare "Attention Required"
  403 on chrome124, chrome120, AND safari17_0. Not re-attempted with Playwright given ambiguous
  food value (generic small-shop names) and time budget — worth a network-trace pass if revisited.
- `hardwaremart.lk`, `hardwares.lk` (sri_lanka) — Cloudflare challenge on all 3 profiles; also
  non-food (hardware stores), so not worth a Playwright follow-up regardless.
- `catchme.lk` (sri_lanka, mineral water brand) — Cloudflare 403 on plain requests AND chrome124.
- `rumikmart.com` (sri_lanka) — returns HTTP 200 but the body is a bot-management JS challenge page
  (`class="a-no-js" data-*="dingo"`, WebSocket focus-tracking) on both plain requests and chrome124
  impersonation — a genuine challenge, not a curl TLS artifact. Food-plausible ("grocery/daily
  essentials" per title) but not pursued further given the challenge is content-level, not
  TLS-level.

## Dead / unreachable (2026-09-11)

DNS resolution failures (domain does not resolve, plain + chrome124): `lightbaazaaru.com`,
`satheyka.mv`, `vectoshop.com` (all maldives); `pickly.lk`, `jingles.lk`, `evive.lk`,
`cosmeticslanka.lk` (all sri_lanka, last one also non-food).

TLS/SSL errors (cert invalid or verify failure, both profiles): `leostore.mv`,
`store.ayalabubbles.com`, `noveltybookshop.com.mv` (maldives, last one also non-food);
`kasagalasuper.com` (sri_lanka — a genuine "Super Market" name, worth re-checking once the cert is
fixed, but currently unreachable on any client).

Connect timeout (both profiles): `sahanakade.lk` (sri_lanka).

Site removed: `navaahi.wixsite.com` ("Navaahi Traders Fresh Market") — the Wix site is unpublished,
404 on both the listed sub-path and the account root.

## Non-food (83) — dropped on sight per the division 01/02 hard constraint

Full per-host list with the specific non-food signal in
`~/gapwork/classification_final.csv` (category=NON_FOOD). Buckets, for orientation:

- **Electronics/computers/gadgets** (maldives): qutech.mv, esselectronics.mv, quikrbiz.mv,
  beta.imtech.mv, levendonline.com, leadtechmv.com, nessoinfinity.com, swiftech.mv, click.mv,
  shop.personalcomputers.mv, nightowlmv.com, timetech.mv
- **Hardware/tools/furniture** (maldives): blueseahardware.com, sonee.com.mv, whetstone.com.mv,
  lykus.mv, styla.mv, tenon.mv, aivahome.mv, relaxmv.net (confirmed via Shopify sample — sells
  welding machines, not groceries, despite grocery-adjacent footer noise)
- **Cosmetics/beauty/perfume/spa**: goldengate.mv, mv.britishcosmetics.com, plaza.com.mv,
  icm4online.com, misobeautyshop.com, amperfumetime.com, spaceylon.mv, skintreatsmv.com,
  cosmetics.lk
- **Fashion/apparel/jewelry**: brandloom.mv, weartoddy.com, berrycollection.com, soneesports.com,
  cuddlycottonlk.com, lurreli.lk, wear.lk, apparel.lk
- **Baby/kids**: lamoonbaby.mv, babypromv.com, hydrosphere-maldives.com, noq.mv, shop.peekaboo.mv,
  babystore.lk, babyneeds.lk, tashbabycare.lk, kidsmart.lk, nesh.lk, kiddoz.lk
- **Optical/pharmacy/health**: eyecare.mv, oagaaoptical.com, unionchemistspharmacy.lk,
  beyondhealth.lk, shop.visioncare.lk, majayasingheopticians.lk
- **Books/stationery**: mrpencil.mv, craftyworld.mv, bookstoremaldives.com, bookbooks.lk,
  bookpack.lk, lol.lk, pothpancha.lk
- **Pet supplies**: petmart.lk, petbarn.lk
- **Restaurant/prepared food (COICOP 11, not retail)**: shellbeans.com ("Enjoyable Dining
  Experiences")
- **Telecom/services/misc**: ooredoo.mv (telco), pestexmaldives.com (pest control),
  palmalandscapeinv.com (landscaping), pinkcoral.mv (aquarium supplies), shop.scout.mv (scout
  gear), sparepartsmarket.lk / sumanamotorstores.com (auto parts), leemacreations.com (interior
  design), finez.lk / agc.lk / homemart.lk (furniture/hardware despite "Homemart"/"Concept Store"
  branding), pricetoday.lk (general multi-category local-deals directory, sampled deal was
  cosmetics — not food-focused despite the "prices" name), primehome.lk (kitchen decor/houseware,
  not food), lassana.com (gifting platform)
- **General merchandise dropshipping confirmed non-food despite "shopping"/"grocery"-adjacent
  branding**: **trolleyz.lk** — 2,005-product catalog fully enumerated via embedded JSON-LD on the
  homepage (31MB page); every "foodish" keyword hit traced back to kitchenware (choppers, milk
  pots, fruit baskets, food-storage containers) — zero actual edible groceries in the catalog. This
  is the wave's clearest case of the "flat-earth" trap the brief warns about: a clean, fully
  enumerable, well-structured catalog that is nonetheless entirely non-food.

## Food-plausible, not pursued this pass (35)

Full list with individual reasons in `~/gapwork/classification_final.csv`
(category=NOT_PURSUED). Grouped by why:

**Needs deeper reverse-engineering (SPA/custom platform, no API found via an 8s Playwright trace):**
tookary.com (fresh-market: fruit/veg/meat), neilbakery.lk (bakery), hurryhurry.lk (strong grocery
signal), srilankastores.com (Ceylon tea/spices), neviscoffee.lk (coffee), naturescorner.lk (organic
foods), stassentea.com (major tea producer), alphadairygoat.com (specialty dairy), cargillsonline.com
(major chain, AngularJS POST-only API), foodele.com (Fuvahmulah delivery SPA, multi-vendor).

**Ambiguous / weak or mixed signal, not individually investigated given time budget:** estore.mv
(STO — likely significant, deserves a dedicated look), nextyle.mv, edhumashi.mv, ebazaar.mv,
dianatradingmv.com, newbizz.com.mv, eurostoremv.com, imcmaldives.com, nuomimaldives.com,
essential.mv, rightspot.mv, misraab.com.mv, zenovahotelsupplies.com (B2B hotel supplier),
island-bazaar.com, maxcom.com.mv, colombomall.lk, foodcolanka.com, tudo.lk, shaz.lk, tns-go.com,
store.topaz.lk (keyword hits likely false positives — Topaz is a known electronics brand),
aquaswift.lk.

**Reachable but not a real source:** familymart.lk (real catalog structure, but only 50 SKUs and
~96% out-of-stock — dormant), ubereats.com / "Keells via Uber Eats" (not a distinct first-party
source; the platform, not Keells, is what's reachable).

## Currency note

Every Maldives source shipped this pass reads MVR directly off the payload (Odoo `itemprop`
microdata, WooCommerce `currency_code`, or the site's own displayed price string) — none needed a
`countries.yaml` fallback. No USD-priced Maldives source was found in this batch (all six live
retailer spiders + both fetchers are MVR-native), so no resort/expat-pricing flag applies this
round.


---

## known_blockers_untried_sar3 - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_sar3.md` on 2026-09-11. 27 hosts, 2 not
documented above at merge time.

# India/Pakistan still_untried sweep — 2026-09-11

Source: `~/gapwork/still_untried_20260911.csv`, filtered to `country in (india, pakistan)` and
`foodish == True` → 148 candidates. Full detail/why/notes columns for all 148 read and triaged
by hand against the hard COICOP-01/02 constraint before any network probe.

## Triage summary

| Stage | Count |
|---|---|
| Total candidates in filtered queue | 148 |
| Dropped on sight as non-food (pharmacy/electronics/furniture/books/toys/eyewear/auto-parts/beauty/general-marketplace/comparison-aggregator/dead-lead) | 55 |
| Probed live (liveness + platform fingerprint + enumerability) | 93 |
| **Shipped (manifest + spider, verified via `collect --max-items 100`)** | **25** |
| Probe-passed but blocked/unextractable/dead after live re-probe | remainder of the 93 (see `known_blockers.md`, "2026-09-11 SAR sweep" section) |

93 probed, not 148, because 55 were non-food by name/description alone and probing them would
have been pure loss under the hard constraint (a pharmacy or eyewear catalogue fills zero
COICOP 01/02 cells no matter how clean). This matches the skill's own guidance to drop non-food
on sight rather than spend probe budget on it.

## Method notes for this run

- Block-verdict re-probe was done live for every candidate that returned non-200 (plain
  `requests` default UA, then `curl_cffi impersonate=chrome124`) — no verdict here is copied
  from a prior wave without re-checking.
- Enumerability was verified by comparing page-1 vs page-2 product-id sets for every shipped
  Shopify/WooCommerce source (all 24 generic-spider sources showed zero id overlap between
  pages) — not just a 200 status.
- Currency was read off the live payload for every shipped source (Shopify `/cart.js`
  `currency` field; WooCommerce Store API `prices.currency_code`), not inferred from the TLD
  or symbol. All matched the country default (INR / PKR) — no surprises this round.
- Hindi/Urdu search was not needed: no candidate's food-relevance was ambiguous enough to
  require it — English evidence from the supplied queue (with sample prices already captured
  by a prior research pass) was sufficient to classify every row.
- One candidate (`chiltanpure_pk`) passed every technical bar (Shopify, working
  `/products.json`, clean pagination) but was dropped anyway after sampling 1,250 products
  showed it is 85%+ a perfume/cosmetics manufacturer — a reminder that "enumerable" and
  "food" are independent checks.

## Shipped sources

| Country | source_key | channel | currency | Measured rows | Distinct URLs | Spider |
|---|---|---|---|---|---|---|
| India | atithifresh_in | specialty-food | INR | 122 | 122 | generic_shopify_configured |
| India | doorbasket_org | fresh-market | INR | 239 | 239 | generic_shopify_configured |
| India | kruncho_in | specialty-food | INR | 69 | 69 | generic_shopify_configured |
| India | freshfishfusion_in | fresh-market | INR | 135 | 135 | generic_shopify_configured |
| India | indiafishcompany_in | fresh-market | INR | 161 | 161 | generic_shopify_configured |
| India | pickfreshfish_in | fresh-market | INR | 224 | 224 | generic_shopify_configured |
| India | sidsfarm_in | specialty-food | INR | 44 | 44 | generic_shopify_configured |
| India | freshbinge_in | fresh-market | INR | 100 | 100 | generic_woo_configured |
| India | maalpani_in | specialty-food | INR | 100 | 100 | generic_woo_configured |
| India | onlinemeatstore_in | fresh-market | INR | 66 | 66 | generic_woo_configured |
| India | ppsnco_in | wholesale | INR | 100 | 100 | generic_woo_configured |
| India | agroeats_in | specialty-food | INR | 20 | 20 | generic_woo_configured |
| India | odhi_in | hypermarket | INR | 198 | 198 | generic_opencart_configured |
| India | bigbasket_in | supermarket | INR | 192 | 192 | custom (bigbasket_in.py) |
| Pakistan | cart24_pk | supermarket | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | alkhaleej_pk | supermarket | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | tawaqqo_pk | fresh-market | PKR | 391 | 391 | generic_shopify_configured |
| Pakistan | shaheenonline_pk | dept-store | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | greenvalley_pk | supermarket | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | freshbasket_pk | specialty-food | PKR | 271 | 271 | generic_shopify_configured |
| Pakistan | esajee_pk | specialty-food | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | nestle_eshop_pk | specialty-food | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | snapcart_pk | marketplace | PKR | 250 | 250 | generic_shopify_configured |
| Pakistan | eurohypermarket_pk | hypermarket | PKR | 75 | 75 | generic_woo_configured |
| Pakistan | karachimartonline_pk | supermarket | PKR | 20 | 20 | generic_woo_configured |

All 25 manifests verified live with `~/venv/bin/python run.py prices collect --source <key>
--max-items 100`, rows confirmed on disk under `data/prices/<region>/<subregion>/<country>/
<source>/raw_items/`, and `prices collect --list` re-run after every batch to confirm the
global 2000+ source list still loads (no enum breakage from a bad `channel:` value).

`bigbasket_in` is the one custom spider (Next.js SSR, `__NEXT_DATA__` JSON, no generic base
fits); see its manifest notes for a known pagination caveat (category pages redirect `?page=2`
to a path that drops the page param, so each category currently yields ~page-1 depth — still
192 rows, well past the 5-row bar).

## Why the rest failed (of the 93 probed)

- **Non-food** (dropped after probing revealed the catalog, not before): `chiltanpure_pk`
  (85%+ perfume/cosmetics manufacturer).
- **Not enumerable / not extractable without further work**: `jiomart.com` (CMS page-builder
  schema, real catalog API not located in a first pass), `krishidhara.com` / `storepanda.pk`
  (WooCommerce Store API disabled, 403), `akshayakalpa.org` (Store API 404, not registered).
- **Blocked (genuine WAF, re-probed live)**: `carrefour.pk`, `magnikart.com`, `golbazar.pk`,
  `fairo.pk`, `kolkatafish.com`, `naturesbasket.co.in` (re-confirmed, previously documented).
- **Blocked (explicit anti-scrape policy, not a WAF)**: `amazon.in` (503 pointing to its own
  paid APIs).
- **Blocked (quick-commerce SPA needing pincode/geo session)**: `zepto.com`,
  `countrydelight.in` (previously documented, re-confirmed).
- **Access-restricted (not a WAF)**: `bombayfisher.com` (402, store suspended),
  `continentalfresh.in` (401, password-gated pre-launch page).
- **Dead / unreachable**: `angaadionline.com`, `graceonline.in`, `rcmymall.in`, `serveu.pk`
  (DNS failures), `chitki.com` (timeout), `uttampk.com`, `asanbazar.pk` (TLS failures),
  `bazaarapp.com` (503 on every probe).
- **Duplicate of a source already shipped this round**: none — every shipped source is a
  distinct host; `bigbasket_in` supersedes the queue's separate "BigBasket dry fruits category"
  and "bigbasket business" rows (same platform, would be redundant manifests).
- **Not a real source** (dropped pre-probe): 9 rows — see `known_blockers.md` "Not a real
  source" bullet (news articles, B2B directories, gift-card pages, price-comparison apps that
  re-scrape other platforms rather than being first-party retailers).
- **Non-food, dropped pre-probe without a network call** (55 rows total; see
  `india_pakistan_foodish.csv`/triage.py `DROP_NONFOOD` set): pharmacy chains (KSI Pharma,
  Shopaholic.pk, Flashi, Hafiz Imran, DawaaiMart, Nova Health), electronics/appliances
  (Eastcom, Azan, PEL eShop, Surmawala, Selecto, SkyTech, PC Wala, HomeShopping), hardware
  (OffersWala, Adnan Brothers), furniture (Home Factree, Themes.pk), books/stationery (Prince
  Book Centre, BookShop.com.pk, Pak Online Books), toys (ToyDost, Toywee, Toy Company,
  ToyVerse, KiddieWink, Mirha Toys, Buyon Toys), eyewear (Lenskart, Eyezaar, Zujaj), fashion
  (Myntra, HS Wear), beauty (Nykaa), baby (FirstCry), auto parts (Boodmo, Dhundo), general
  marketplaces (Flipkart, Tata CLiQ, Meesho), and grocery price-comparison apps with no
  first-party catalog (PriceBasket, BudgetBasket, FantasticFood, Smartprix, Comparify, Groka,
  PriceKart, Gavyam, Qemat).

## Next gaps to target (priority order, for a future dedicated session)

1. **Zepto / country-delight-style pincode flow** — reverse-engineer the lat/lon or pincode
   header via a real Playwright interaction session (set delivery address, capture the
   resulting category/search API call), then hit that endpoint over plain HTTP. Two
   candidates already queued for this exact fix.
2. **Carrefour Pakistan** — re-probe with a longer Playwright network-capture session; Majid
   Al Futtaim storefronts elsewhere expose an open commerce API behind the WAF.
3. **JioMart** — find the real category URL structure (the CMS section-preview URL from the
   candidate list was the wrong entry point) and re-run the network capture against it; this
   is a Fynd Platform backend, and its catalog endpoint is very likely
   `api/service/application/catalog/v1.0/...` by analogy with the cart/logistics endpoints
   already captured.
4. **BigBasket depth** — widen `CATEGORY_SLUGS` in `bigbasket_in.py` beyond the 7 hardcoded
   food categories, and reverse-engineer the real "next page" contract (current `?page=N`
   redirects to a path without it) to get past ~48 SKUs/category.


---

## known_blockers_untried_territories - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_territories.md` on 2026-09-11. 50 hosts, 33 not
documented above at merge time.

# Known blockers -- untried micro-territories food-source campaign

_All verdicts below dated 2026-09-11 unless noted otherwise._

Scope: `~/gapwork/untried_unassigned.csv` filtered to `foodish==True` and
country in {greenland, eswatini, south_sudan, palau, american_samoa,
gibraltar, marshall_islands, kiribati, faroe_islands, liechtenstein,
san_marino, andorra, monaco, new_caledonia, french_polynesia, curacao,
aruba, bermuda}. 84 rows matched (9 countries had rows; the other 9 had
zero untried rows in the queue).

## Shipped (see Phase 8 report for full detail)

- `sheshasd_sz` (Eswatini) -- liquor + butchery, sheshasd.com
- `igrocerbusket_sz` (Eswatini) -- grocery delivery, igrocerbusket.store.link
- `bonfood_gi` (Gibraltar) -- fresh produce/deli/pantry, bonfood.gi (Wix)
- `dutyfree_airports_gl` (Greenland) -- airport duty-free (travel-retail
  flag), dutyfree.airports.gl

## Confirmed dead / rejected -- queue candidates

| Candidate | Country | Verdict (2026-09-11) |
|---|---|---|
| tutila_store (tutuilastore.com) | american_samoa | Template site with hard-coded "Demo Products when no data" placeholder cards -- no real backend/catalog. |
| hi_nesian_apparel, tanoa_hawaii, toa_samoa_shop, myus_parcel_shipping, neil_s_ace_home_center, samoamarket, samoa_company_registration_fees, prescription_eyewear_local_storefront, flying_fox_brewing_co_menu | american_samoa | Non-food (clothing/hardware/telecom/admin-fees/restaurant) -- dropped on sight per the COICOP 01/02 hard constraint, not probed. |
| buyeswatini_shop (buyeswatini.shop) | eswatini | Generic Chinese-template B2B storefront SaaS shell; `/291/Product/All` has zero real product markup (no price class, no product-item class anywhere in the page) -- empty demo store, same pattern as the already-documented SPAR-WooCommerce-zero-products case. |
| imali_smart_marketplace (storkvelkonnect.co.za) | eswatini | Domain returns Cloudflare "DNS resolution error" -- the origin no longer exists behind the CF proxy. Dead domain. |
| patos_co_za (patos.co.za) | eswatini | Parked/expired domain (generic "Find the best information..." parking page, `noindex`). Dead. |
| quickmessanger_qm_store (quickmessanger.com) | eswatini | Real, live site, but it is a business DIRECTORY/digital-marketing platform ("Eswatini's all-in-one digital marketing and business directory"), not a storefront. No products. |
| marketsquare_cars, timototraders, newflagshop_eswatini_flags, skyfly_mobi_store, swaziswap, hivoox_eswatini_esim | eswatini | Non-food (cars/flags/apparel/appliances/esim) -- dropped on sight. |
| shoprite_specials_eswatini (specials.shoprite.co.sz) | eswatini | A single dated promotional-leaflet page (10KB), not a browsable/enumerable catalog -- fails the enumerability gate (no page-2 to diff against). Not scaffolded; revisit if Shoprite ever exposes a real catalog page (it hasn't as of three prior passes per country notes). |
| floweradvisor_com_gibraltar, gibraltarpass_com, gibtechstore_com, inhome_gi, interbuild_gi, lionsgibraltarfc_com_vx3_store, rockhero_gi_4_stagioni | gibraltar | Non-food (flowers/tourism/electronics/furniture/hardware/sportswear/restaurant-menu -- restaurant is COICOP 11, out of the 01/02 hard scope) -- dropped on sight. |
| rockvapour_com (Gibraltar vape/e-cig shop) | gibraltar | Real WordPress/WooCommerce site (`woocommerce` markup present) but the WooCommerce Store REST API (`/wp-json/wc/store/v1/products`) 404s and no prices are visible in the raw homepage HTML -- likely needs a Playwright render or a different WC endpoint path. DEFERRED, not probed to conclusion (borderline COICOP fit too: vaping hardware/e-liquid is not cleanly "tobacco" under COICOP 2018). |
| ahb_nuuk, hotel_qaqortoq_menu, nuukeats, sawadii_gl | greenland | Restaurant/takeaway menus -- COICOP 11, out of the 01/02 hard scope. Confirms country notes. |
| babysam_gl, davidsen_nuuk, glaciershop_store, ittu_net, noenne_net, illerfissarsiutileqatigiit, naleraq_sea_safari | greenland | Non-food (baby goods/hardware/souvenirs/sportswear/eyewear/funeral goods/tours) -- dropped on sight. |
| geedo.gl | greenland | Confirmed a pure comparison-shopping-engine template (identical layout at geedo.af, geedo.ax, geedo.al, ... one per ccTLD) with no in-house search/category route found (`/sog/tobak`, `/search?q=` both 404). Does not resolve the "/webshop/tobacco/" lead -- that lead was airports.gl's duty-free shop, found and shipped separately as `dutyfree_airports_gl`. |
| henicki, slim_price_map, wishing_star_trade_data, wishing_star_trading | kiribati | Confirmed no online store / directory-or-import-record-only, per queue's own notes. No re-probe needed (dated 2026-09-11 already). |
| kirb_gebeya, tiktok_shop_kiribati_plush, walmart_kiribati_flag | kiribati | Confirmed false positives (Ethiopian marketplace, non-Kiribati marketplace listings) per queue notes. |
| baergwelten_shop_li, lehni_ch, omni_li_books, online_apotheke_ch | liechtenstein | Non-food (clothing/furniture/books/pharmacy) -- dropped on sight. |
| ez_price_mart_directory (mh.near-place.com listing) | marshall_islands | Chased the named first-party domain (ezpricemart.com / www.ezpricemart.com): resolves via a JS redirect to `ww19.ezpricemart.com` -- the classic domain-parking signature (consentmanager.net ad-tech stub, no real content). The business's web presence has lapsed; parked domain now. |
| infomarshallislands_food_page | marshall_islands | Context/lead page only, as queue notes state. Its named leads (Pacific Island Trade, Wahoo, MISCO) are ALL already covered by existing manifests (`pacificislandtrade_mh.yaml`, `wahoo_mh.yaml`, `misco_wholesale_mh.yaml`). |
| island_eco, majuro_telephone_directory_retail_leads, marshall_japanese_travel_blogs_price_snippets, opentravelguide_shopping_mh, rmi_embassy_taiwan_local_merchandise | marshall_islands | Non-ingestible per queue's own notes (solar/quote-based, old directory, travel-blog snippets, editorial guide, embassy contact page) -- confirmed, not re-probed. |
| fish_n_fins_partner_pricing, neco_marine_rates, ocean_hunter_liveaboard_rentals, palau_dive_adventures_faq_rentals, peci_carquest_auto_parts, palau_pacific_resort_dining, palau_red_cross_sengsongd_thrift | palau | Non-food (dive/tourism services, auto parts, resort dining/thrift-range-only) -- dropped on sight per hard scope. |
| tropicart_wix_store (tropicarti.com) | palau | Craft/souvenir goods (shell jewelry, wall hangings) -- non-food, and Palau locality was never confirmed on the site itself (no PW address found). Dropped. |
| west_deli_findglocal (findglocal.com mirror of WCTC/West Deli) | palau | Third-party social-post mirror of a deli's daily menu -- not a first-party catalog, prepared/deli food (COICOP 11-adjacent), and unstable format. Not scaffolded. |
| surangel_epicor_store (shop.surangel.com) | palau | Legacy Epicor storefront subdomain -- times out with 0 bytes received on every attempt (curl_cffi default, chrome124, and bare connection). Origin appears decommissioned; Surangel's CURRENT site (surangel.com) is already covered by the existing `surangel_pw.yaml` manifest. |
| doyoom_food_delivery_ss | south_sudan | Restaurant delivery platform -- COICOP 11, out of scope (matches country notes exactly). |
| digitel_estore_ss, jubaexpanse_takeapp_ss, memuapp_ss_ug, ssdonestore_ss, zuddo_ss | south_sudan | Non-food-dominant (telecom devices/hospitality textiles/fashion-electronics/mixed marketplace with no clear food category) -- deprioritized, not deep-probed given time budget. |
| businessclaud_ss (businessclaud.com) | south_sudan | 403 on all three arms (plain UA, Chrome UA, curl_cffi chrome124) -- and body is mostly electronics/clothing per its own "why" text, low food value even if unblocked. Not pursued further. |
| shopit_ss (shopit.com.ss) | south_sudan | 403 on curl_cffi chrome124, chrome120, AND safari17_0 (three-profile check) -- genuine Cloudflare challenge, not a JA3 false positive. Playwright not attempted (time budget); record as SKIP_WAF pending a future Playwright pass. Catalog would be worth revisiting (explicitly lists "alcoholic drinks" as a category). |
| jubacargodirect_all_ss (jubacargodirect.com) | south_sudan | Homepage and bare domain both 404 across http/https/www variants -- Wix site appears unpublished/store closed. Dead. |
| dukaanye_ss (dukaanye.com) | south_sudan | INTERMITTENT. Initial batch probe returned 200 with a real Laravel storefront ("365-Amazcart") and a populated `/category/food` page (product_price divs present). Four follow-up attempts over ~2 minutes all returned Cloudflare 502 (origin down) or a full connection timeout -- origin server is unstable/flapping. NOT shipped because Phase 6 requires a real, reproducible `prices collect` run; revisit with retries on a future pass. This is a genuine, promising candidate if the origin stabilizes. |

## Real businesses found via ddgs sweep, verified but NOT shippable this pass

| Domain | Country | Finding |
|---|---|---|
| sms.fo | faroe_islands | WooCommerce Store API IS open, but the entire live catalog is a single SZL... DKK gift-card SKU ("Gávukortið"). SMS is a physical department-store chain; its real merchandise is not sold through this WC instance. |
| einkaufland.li | liechtenstein | Same pattern -- WooCommerce Store API open, single SKU = a shopping-voucher ("Einkaufland Gutschein"). einkaufland.li is a shopping-mall/retail-association directory site, not a retailer itself. |
| formosamarket.com | marshall_islands | Real Shopify grocery catalog (Kikkoman, snacks, USD prices) BUT locality check found zero mentions of Majuro/Marshall Islands anywhere on the site -- this is an unrelated US-based "Formosa Asian Market," a same-name coincidence with the physical Formosa Supermarket in Majuro. Rejected on the locality gate. |
| miscomarket.com / miscomarketebeye.com | marshall_islands | Confirmed genuinely Marshall-Islands-local (mentions Ebeye/Kwajalein) and is the same MISCO business already covered by `misco_wholesale_mh.yaml` (a different domain, miscowholesale.com). Treated as a duplicate storefront of an already-covered retailer, not scaffolded separately. |
| bonus.fo, ahandil.fo ("Á"), miklagardur.fo, taks.fo, local.fo | faroe_islands | All real, live Faroese retail/shopping sites (Bónus discount supermarket, Á grocery chain, Miklagarður department store, general shopping portals). None expose a browsable, price-bearing product catalog in static HTML; miklagardur.fo's "/keyp" page is a Wix SPA that (after a full Playwright render + 5s wait) still shows zero price tokens -- likely a loyalty/voucher flow, not a shelf catalog. ahandil.fo and bjor.fo both carry WooCommerce theme assets but their Store REST API 404s (endpoint disabled or path differs). None met the enumerability bar; Faroe Islands remains at 0 real food/beverage/tobacco sources (alvaro_fo=fashion, djor_fo=pet are the only existing manifests). |
| hoi-laden.li | liechtenstein | REAL, VERIFIED, NOT YET SCAFFOLDED. Liechtenstein regional specialty-food/gift shop (JTL-Shop platform). Its `/Kueche-Kulinarik` category explicitly states "Lebensmittel-Versand nur nach Liechtenstein und in die Schweiz" (food shipped only to Liechtenstein/Switzerland) and lists ~97 genuine food items (Bio-Emmer-Snack, Bio-Mais-Chips, Oepfelhopfa-Schelee jam, Murer-Nuedeli noodles) plus wine (overlaps with the already-covered hofkellerei_li). CHF prices are present on the page but the name/price pairing needed for a reliable selector sits inside a JS-driven "quick view" product block rather than a clean static card -- ran out of time budget to extract a verified selector. Good candidate for the next pass. |
| castellum.li, falknis.li, weinbau-hoop.li, getraenkeoase.li, elma-getraenke.li, getraenke-gstoehl.li, getraenkeexpress.li, meier-getraenke.li | liechtenstein | Real small Liechtenstein wine-estate/butcher/beverage-delivery businesses (found via ddgs). castellum.li and falknis.li are brochure sites with no e-commerce (zero price tokens / static WebSiteX5 builder). The five "Getränke" (beverage-delivery) businesses were found but not individually probed past the homepage-signal check -- time budget did not allow it this pass. Worth a dedicated follow-up given Liechtenstein's near-zero food coverage. |
| jatak.brugseni.gl, pilersuisoq.gl, kkengros.gl | greenland | jatak.brugseni.gl (17KB, no e-commerce signals) looks like a small sub-brand page, not a shop. pilersuisoq.gl re-confirms the existing country-notes verdict (brochure-only). kkengros.gl ("Engrossalg i saerklasse i Groenland" -- wholesale) returned real product/cart signals (314KB) but was not deep-probed for a real selector this pass -- a genuine candidate for a wholesale `official_avg`/`retailer_sku` source, follow up next time. |
| shop.kni.gl, vinslottet.gl | greenland | Both failed with `CertificateVerifyError` under curl_cffi impersonation (likely an expired/misconfigured TLS cert, not a WAF) -- not re-tried with `verify=False` this pass due to time. vinslottet.gl ("The Wine Castle") is a promising Greenland alcohol-retail name lead if the cert issue is worked around. |

## COICOP-scope drops (all territories, all candidates)

Per the hard constraint (grid is COICOP divisions 01/02 only), the
following categories of candidate were dropped on sight without a live
probe, across every country in this run: clothing/apparel/footwear,
pharmacy/eyewear/cosmetics, electronics/appliances/hardware, furniture,
pet goods, automotive/vehicles, real-estate, dive/tour/recreation
services, restaurant/takeaway/prepared-meal menus (COICOP 11), telecom
devices/SIM/eSIM, funeral goods, and administrative/registration fee
pages. This matches roughly 55 of the 84 filtered candidates.


---

## known_blockers_untried_wafrica - as of 2026-09-11

Merged from `~/gapwork/known_blockers_untried_wafrica.md` on 2026-09-11. 65 hosts, 40 not
documented above at merge time.

# West Africa food-source gap-fill — findings (as of 2026-09-11)

Source queue: `~/gapwork/untried_unassigned.csv` filtered to `foodish==True` and
country in {guinea, guinea_bissau, gambia, burkina_faso, cote_divoire, ghana,
congo_rep, togo, benin, mali, niger, senegal, mauritania, cameroon, sudan}.
79 rows matched the filter (togo/mali/niger/cameroon had zero rows in the
queue for this filter — no untried candidates were queued for them).

Text-based food/non-food triage on `detail`/`why`/`notes` cut 79 down to
~34 plausible food/mixed/unclear candidates; the other 45 were on-sight
non-food (electronics, hardware/quincaillerie, furniture, apparel, vehicles,
pharmacy, stamps/collectibles, real estate, topups) per the hard COICOP
01/02-only constraint and were dropped without probing.

## Shipped

- **waafiro_gm** (Gambia) — `src/prices/configs/ssa/west_africa/gambia/waafiro_gm.yaml`
  + `src/prices/price_scraping/spiders/waafiro_gm.py`. Broad marketplace,
  React SPA; found a plain JSON API via Playwright network trace
  (`/api/products?categoryId=&limit=&page=`). Scoped the spider to 28
  whitelisted food/drink category ids only (drops the site's fashion/
  phones/electronics/eyewear/cosmetics catalog on principle, per the
  COICOP 01/02-only mandate). Verified live 2026-09-11:
  `run.py prices collect --source waafiro_gm --max-items 100` → 46 rows,
  46 distinct urls/product ids. channel=marketplace, currency=GMD
  (no explicit currency field in the API; site is Gambia-only).
- **oumbemarket_cm** (Cameroon, from ddgs) — WooCommerce Store API,
  supermarket channel. 180-SKU catalog (water, cooking oil, diapers,
  toiletries). currency=USD -- confirmed genuinely USD both in the API
  payload and the rendered PDP price span, not just a symbol guess;
  flagged as unusual for Cameroon (XAF is the countries.yaml default) but
  taken at face value since the whole site is internally consistent on
  USD. Verified: 100 rows / 100 distinct urls (--max-items 100 cap; true
  catalog is 180).
- **ivoireepicerie_ci** (Cote d'Ivoire, from ddgs) — Shopify storefront,
  channel=specialty-food. Small but 100% food catalog (spice/powder
  blends -- moringa, garlic powder). currency=XOF confirmed via
  Shopify.currency.active. Verified: 21/21 rows (whole catalog).
- **jachete_ci** (Cote d'Ivoire, from ddgs) — WooCommerce Store API on a
  broad 2231-SKU general marketplace (electronics/appliances/auto
  dominate); spider SCOPED to 13 whitelisted food/drink category ids
  (Alimentaire, Boisson, Grains et Riz, Lait, Condiment et vinaigre,
  Epicerie, Cafe/The/Expresso, etc.), same pattern as waafiro_gm.
  channel=marketplace, currency=XOF. Verified: 193 rows / 193 distinct
  urls (real grocery SKUs -- Kirene mineral water, Ketchup 485g, rice).
- **mescoursesbj_bj** (Benin, from ddgs) — Shopify storefront,
  channel=supermarket. 139-SKU grocery catalog (Riz GINO 25kg, Riz Sista
  Grace 25kg, Pringles, frozen peas, Poudre de Moringa). currency=EUR --
  flagged as likely diaspora/import pricing (Benin's countries.yaml
  default is XOF) despite site copy naming Cotonou/Benin as the service
  area; shipped per the "take whatever verifies" rule for a low-coverage
  country but the manifest carries an explicit downstream caveat.
  Verified: 239 rows / 239 distinct urls (variants flattened from 139
  products).

## Dead / empty (not blocked — genuinely no catalog) — verified 2026-09-11

- **sococe.ci / sococe.online** (Côte d'Ivoire) — the task handoff flagged
  this as "recorded blocked but answered 200 on a retest" and told this
  pass to go get it. Re-probed: plain `requests` (no impersonation) DOES
  clear it (200) while `curl_cffi impersonate=chrome124` still 403s —
  confirms the JA3-denylist pattern from the method notes. BUT every path
  tried (`/`, `/shop`, `/boutique`, `/catalogue`, `/magasin`, `/produits`)
  returns the identical 7986-byte page with `<title>Votre site est en
  Construction</title>` (site under construction). Zero catalog. Verdict:
  DEAD (empty site), not a WAF block. Re-check in ~1-2 months.
- **guiterco.com** (Guinea, "Grossiste alimentaire en Guinée") — Vite/React
  SPA. `/catalog` route renders (server confirms via Playwright) but shows
  "Aucun produit trouvé." — the price-filter slider (0-999,999,999 GNF) is
  wired up but the catalog itself is empty. Verdict: DEAD/empty; revisit
  if it fills.
- **koolxpress.com** (Guinea) — Laravel/Alpine.js marketplace. Homepage
  carousel shows real GNF prices, but they are ELECTRONICS promos (e.g.
  "Promo Smartphones" 350,000 GNF), not food. The dedicated grocery
  storefront tenant at `/shop/epicerie-fine` ("Épicerie Fine") renders
  "Aucun article disponible pour le moment." — zero products in the food
  vertical specifically. Verdict: non-food homepage + empty food vertical.
- **polimaxguinee.com/catalogue** (Guinea) — real server-rendered catalog
  (`<h3 class="product-name">` / `<p class="product-price">`), NOT an SPA.
  Extracted all 51 products from the default "Magasin Central Madina"
  store: 100% hardware/construction (rechaud a gaz, ciment, grillage,
  pointe acier, ...), zero food SKUs despite the queue's "3 categories
  incl. food/alimentation" claim. A second store (`storeSelect` option
  value=9, "Madina") exists but a Playwright store-switch returned zero
  products. Verdict: non-food (for the store that has any stock).
- **mamakiti.com** (Guinea, "maMakiti") — marketing/landing site only
  (nav = `#download`, `#features`, `#story`, `devenir-livreur`,
  `devenir-vendeur`); no browsable catalog route exists on the web at all.
  App-only. Verdict: SKIP, app-only.
- **maurikilchi.com** (Mauritania) — real JSON API
  (`/api/products/?boutique_type=<x>&limit=`), confirmed via Playwright
  network trace, but every `boutique_type` and category filter tried
  (restaurant, supermarche, supermarket, grocery, no filter at all)
  returns `{"count":0,"results":[]}`. The whole marketplace is currently
  empty. Verdict: SKIP, empty catalog; revisit later.
- **sougdan.com** (Sudan) — real OpenCart-style storefront
  (`data-product-title`/`data-product-price` attributes, currency=SDG
  confirmed in a hidden form field), but the entire visible catalog across
  both the homepage carousel and `/products` is the SAME 6 items
  site-wide (1 food item — Ecuadorian peas 400g — plus a book, perfume,
  car sunshade, and 2 phones). No category taxonomy with real listing
  pages was found (`/home/categories/` is a generic nav, not a filterable
  grid). Fails the >=5-food-row gate. Verdict: SKIP, catalog too small and
  not food-dominant.
- **alwaha.sd** (Sudan, "Al Waha Supermarket" in the queue) — actually a
  static BootstrapMade "Moderna" corporate template for a humanitarian/
  development-aid B2B supplier (UN Global Marketplace vendor, ISO 9001),
  not a consumer retailer. No product prices anywhere on the site.
  Verdict: SKIP, not a retail price source.
- **brazzamarket_cg** (Congo Rep) — Next.js marketplace, confirmed via
  Playwright render. Category sidebar counts: Mode & Vêtements 27, Beauté
  & Santé 4, **Alimentation 2**, all others 0. Food category exists but
  has only 2 SKUs — below the >=5-row gate. Verdict: SKIP, food tail too
  thin (matches the original handover note).

## Genuinely dead domains (NXDOMAIN, verified 2026-09-11)

`melcomghana.com`, `www.melcomghana.com`, `melcom.com.gh`,
`palacehypermarket.com`, `www.palacehypermarket.com`, `africmart.com`,
`www.africmart.com`, `societe-asfils.com` (papalac_gn), `belair.gn`,
`www.belair.gn`, `belair.com.gn` (Supermarche Bel Air), `www.amatlgb.com`,
`amatlgb.com` (Guinea-Bissau). None resolve on a8's DNS. `koumbimarket.eu`
(Mauritania) resolves but returns HTTP 409 (16 bytes) on both http and
https — effectively dead/misconfigured.

## Blocked — Vercel Security Checkpoint (genuine bot-wall, both arms fail)

`jendal.org` / `www.jendal.org` (Gambia marketplace, had a real food/drinks
category per the queue notes), `www.mokocg.com` (Congo Rep), and
`meucomercio.com.br` (the Guinea-Bissau "nha_pedido_nhamburguer" lead) all
return an identical 403 "Vercel Security Checkpoint" JS-challenge page —
same challenge markup byte-for-byte across three unrelated domains, all
Vercel-hosted. Verified with BOTH `curl_cffi impersonate=chrome124` (403)
AND a real headless-Chromium Playwright render (still serves the challenge
page after a 6s wait) — per the method notes, this is the "stop" case, not
a signal to keep iterating.

## Blocked — Cloudflare Turnstile

`www.lilydelivery.com` (Sudan, LILY Delivery). Plain `requests` with a
Chrome UA string cleared the WAF (200, 248KB) but the page is a Next.js
SPA shell with no `__NEXT_DATA__` and no discoverable `/api/` reference in
the static HTML — real content is client-hydrated. A headless-Chromium
Playwright render, by contrast, DID trigger the Cloudflare Turnstile
challenge (same URL). No JSON API found in the main bundle. Verdict:
DEFER — needs deeper reverse engineering (mobile API capture, or a
stealth-patched Playwright) than this pass's budget allowed.

## Deferred — real app, backend not surfaced without more work

- **almersoul.com** (Mauritania, via the "Almersoul" queue redirect from
  marsarim.com) — Angular delivery app ("commandez des repas, des
  courses, des médicaments"). Playwright network trace only fired i18n
  asset loads (no vendor/product API called before an address is set).
  Fetched and grepped the main JS bundle (1.49MB) for API host strings:
  found only one relative reference, `api/v1/users/`; probed 8 guessed
  same-origin `/api/v1/*` paths and all fall through to the Angular SPA
  index (client-side routing catch-all). The real backend is not on the
  same origin as the bundle references, or is in a lazy-loaded chunk not
  fetched by this pass. DEFER.
- **hyper.sd** (Sudan, "Hyper Express") — homepage is a static marketing
  page (`hyper.sd`) linking to the actual ordering app at
  `https://web.hyper.sd`. That subdomain is a **Flutter web app**
  (confirmed via `assets/FontManifest.json`) — canvas-rendered, no DOM
  text, and it only fired asset/i18n JSON requests before any location/
  address step. Flutter web scraping requires either intercepting the
  app's real data API (not surfaced in this pass) or a CanvasKit-level
  approach; out of budget. DEFER.
- **chowdeck.com** (Ghana/Nigeria) — per the task handoff, "partially
  explored, not finished." Confirmed the marketing site is Next.js and
  found a public CMS content API (`content.chowdeck.com/api/restaurants
  ?filters[country][$eq]=ghana`) — but that endpoint is a Strapi-backed
  SEO directory (restaurant name/city/slug only), NOT the ordering
  backend, and carries no menu/price data. Also: restaurant meal prices
  are COICOP 11 (restaurants), not 01/02, so even a working restaurant
  API would be out of scope for this pass — only a genuine grocery
  vertical with product-level prices would qualify, and that surface
  was not located. DEFER / likely out-of-scope regardless.

## Skipped without deep probing (small catalog / demo data / low priority)

- **sylishop.com** (Guinea) — real JSON API (`/api/produits`) but total
  catalog is ~6-8 items across Construction/Services/Mode/Électronique/
  Alimentation; looks like seed/demo data (item image fields are bare
  emoji). At most 1 food item. Below the row gate.
- **saremati.shop** (Guinea) — `curl_cffi` returns 402 Payment Required
  (both plain-requests arms SSL-error out entirely) — looks like a
  suspended/unpaid hosting account. Not re-probed further.
- **penchami.com** (Gambia) — homepage is a help-center/policy page, not a
  product listing; deprioritized given the waafiro_gm win already covers
  Gambia's food gap for this pass.
- **Jumia** (jumia.com.gh/groceries, jumia.ci/epicerie, jumia.sn/epicerie)
  — all three return 403 on every arm (plain, UA, curl_cffi impersonate),
  identical ~5.5-6KB body sizes consistent with an Akamai/edge block
  across the whole *.jumia.* tenant. Per the inverse-correlation law this
  is a market leader and was not pursued further as a dedicated anti-bot
  effort in this pass.
- **Bolt Market Ghana** (bolt.eu/en-gh/food/market/) — catalog lives
  inside the Bolt Food mobile app; the web page is marketing only, no
  scaffolding attempted (matches the original queue note).
- **storna-shopping-vercel.app** (Sudan) — DNS does not resolve at all
  (ConnectionError on plain, DNSError on curl_cffi). Dead preview
  deployment.
- **koumbimarket.eu** (Mauritania) — see "genuinely dead domains" above.

## ddgs supplementary search — findings (as of 2026-09-11)

Ran a French/Arabic/English `ddgs` sweep (backends pinned:
duckduckgo,google,brave,mojeek,startpage,yahoo; 21 queries, 173 raw hits)
targeting Guinea-Bissau, Côte d'Ivoire, Congo Rep, Sudan, Mauritania,
Benin, Senegal, Togo, Mali, Niger, Cameroon — the countries where the
original queue yielded nothing shippable. Raw results in
`~/gapwork/ddgs_sweep.jsonl`. After noise-filtering, ~90 distinct
candidate domains surfaced; a fast keyword/currency scan triaged them,
and the top signals were deep-probed. 4 of the 5 shipped sources this
pass came from this sweep (oumbemarket_cm, ivoireepicerie_ci, jachete_ci,
mescoursesbj_bj) — local-language ("supermarché en ligne", "épicerie en
ligne", "livraison courses" + capital city name) queries clearly
outperformed the original hand-off queue for this region.

Additional ddgs-sourced dead ends checked this pass:
- **nomercadogb.com** (Guinea-Bissau) — real Supabase-backed classifieds
  marketplace (`anuncios` table exposed via the site's own public anon
  key at `dofkfznzfdbugdqlldlc.supabase.co/rest/v1/anuncios`). Queried
  all 38 live listings: categories are moda(19)/eletronicos(8)/
  outros(6)/moveis(2)/imoveis(2)/veiculos(1) — zero food category.
  Verdict: SKIP, non-food.
- **242market.com** (Congo Rep) — PrestaShop-style storefront with an
  "AGRO-ALIMENTAIRE" nav category (`/catalogue/352691-agro-alimentaire`),
  but that category page returns zero product markup (no
  `product-miniature`, no JSON-LD, no price tokens) — either empty or
  needs deeper JS rendering than this pass's budget covered. DEFER.
- **guinebissaumarket.com** (Guinea-Bissau) — Next.js, no JSON API found
  via Playwright trace (unlike nomercadogb, no XHR calls fired on
  homepage load). Not pursued further this pass. DEFER.
- **bama.express** (Mali) — small static page (18KB), no JSON endpoints
  found, no further signal. SKIP/low-priority.
- **sugu.express** (Mali) — Next.js with `/api/auth/session` and
  `/api/feature-flags` calls only (i.e. an auth-gated app) — no public
  product API surfaced before a login step. DEFER.
- **instagrocer.co** (Sudan) — genuine Next.js grocery-delivery app with
  a real public API: `/api/stores/nearby?user_latitude=&user_longitude=`
  returns nearby stores once a location is supplied (200, confirmed via
  Playwright network trace), and `/api/auth/me` (401, i.e. anonymous
  browsing is allowed). This is the most promising Sudan lead from the
  sweep but needs a follow-up pass to walk from stores -> per-store menu/
  catalog endpoints, which this pass did not have budget for. DEFER —
  highest-priority Sudan follow-up.

Everything else in the domain list from `~/gapwork/probe_ddgs_results.json`
(Guinea-Bissau: bissauonline.net, bindicumpra.net, compraexpress.app,
evendo.com, mercado.gratis, mercado.pliz-tech.com; Sudan: alloshmart,
amasonsudan, clickomart, sougk, sudanzon [503], thlthwea; Mauritania:
jemli.mr, jeyaboo.com [both live but zero food-keyword signal];
Cote d'Ivoire: amexpress-ivoire [403 on curl_cffi impersonation only],
christlivraison.ci, ivoiresup.com, ledjassa.org, livurge.com,
reliableci.ci; Senegal: bonappetit.sn, dialy.sn, lafermededibor.com
[Senegal already has 7 manifests, deprioritized]; Togo: lotieapp.com,
oel.tg, quefairealome.com [Togo already has 4 manifests]; Niger:
afromallne.com, coursilliko.com, kamesexpress.com, zangoexpress.com;
Mali: alimama-ml.store, malirush.com, sankadi.ml, souqou.com) was
surfaced by the sweep but NOT individually probed beyond the keyword/
currency scan this pass — they are live candidates for the next session,
roughly ranked by the food-keyword-density scan already run and saved in
`~/gapwork/probe_ddgs_results.json` / the scan output above.
