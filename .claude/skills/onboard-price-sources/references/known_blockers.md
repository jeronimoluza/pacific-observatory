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
- **cargillsonline.com** (LK) — Angular SPA. After 12s wait + scroll, dump contains `{{...}}` placeholder syntax (Angular templates) for product details and only category-level `/Product/<cat>` links — `/ProductDetails/<sku>` URLs never hydrate.
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
- `coop.se` — sweden (eca)
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
