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

## Shopify store suspended (HTTP 402 payment required)

Not an anti-bot wall — the tenant's Shopify subscription is unpaid/inactive, so **every** path (including `/`) returns `HTTP 402` with `content-length: 0` and `powered-by: Shopify`. Confirmed reproducible across two separate probes minutes apart (not a transient 402). The storefront is genuinely offline, not just hard to scrape — re-check in a few months rather than re-probing selectors.

- **mnfmarket.com** (GU, M&F Market — Korean fresh food & wholesale, Tamuning) — `HTTP/2 402`, `shopify-complexity-score` headers present, `cf-cache-status: DYNAMIC`. Business appears active on Instagram/Facebook (pre-order pickup Mon/Fri) but the Shopify storefront itself is billing-suspended. Probed 2026-08-11.

## Cloudflare strict (curl + Playwright both 403)

403 even with realistic UA + headers. Often serves a challenge page or interstitial. Headless Chromium without stealth + residential IP fails. Bypass would require a paid proxy/solver stack.

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

## Azure Front Door WAF (`Service unavailable / The request is blocked`)

Azure Front Door managed WAF rule returns HTTP 403/1479-byte HTML stub with literal body text "Service unavailable. The request is blocked." plus an Azure request-tracking ID. Confirmed on both curl (multiple header combinations incl. full Chrome sec-ch-ua set + Referer) and Playwright headless — same failure mode as Cloudflare strict, treat identically (skip, don't iterate).

- **deps-1d68840ecf-hehjcxeeeybfdabn.a03.azurefd.net** (BN, DEPS "PM Price List" app, linked from `deps.mofe.gov.bn/pm-price-list/`) — blocks both `/price-monitoring/` and `/wp-content/uploads/...` paths proxied through this Azure Front Door hostname. **Not a structural loss**: the same files are reachable directly on the un-proxied `deps.mofe.gov.bn` origin (see `deps_arp.py` / `deps_cpi.py` fetchers, which pull the XLSX via the WordPress origin + WP REST API media search instead of this CDN hostname). Probed 2026-08-11.

## AWS WAF (`awswaf.com` challenge token)

WAF that returns 403 + a challenge token from `awswaf.com`. Blocks both HTML site and API gateway from the same tenant.

- **klikindomaret.com** + **ap-mc.klikindomaret.com** (ID) — AWS WAF challenge on both site and API gateway.
- **officeworks.com.au** (AU, dept-store/office-electronics — COICOP 05/08 candidate) — HTTP 405 + `x-amzn-waf-action: captcha` from CloudFront/AWS WAF on the front page. Probed 2026-08-07 (round-3 non-food shard).

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

## CDN connection-reset / TCP timeout from non-target IP (country geo-fence)

- **www.mpointmart.com** (LA, M-Point Mart — Vientiane supermarket chain) — TCP timeout (0 bytes, 000 exit code) from non-Lao IP on root and /shop/. Likely CDN geo-fence. COICOP 01/05/13 gap. Re-probe with Lao residential proxy. Probed 2026-06-15.

## CDN connection-reset at TCP layer (`ERR_CONNECTION_RESET`)

Real-browser requests from a non-target-country IP are dropped at the CDN before any HTTP response. Headless Chromium does not bypass — the connection is reset pre-response. Bypass requires a residential proxy in-country.

Distinct from the Internet Archive's intermittent L4 blackhole, which produces the same symptom but only under sustained parallel Wayback backfill and clears on its own — a geo-fence resets every time, from the first request.

- **shop.cpl.com.pg** (PNG, CPL Group — Stop & Shop supermarket, PNG's largest retailer) — `ECONNREFUSED` on WebFetch from non-PNG IP. Online grocery/pharmacy/hardware shop at shop.cpl.com.pg. Likely CDN geo-fence restricting to PNG residential IPs. Probed 2026-06-10. Revisit with PNG residential proxy before attempting to onboard as retailer_sku spider.
- **bachhoaxanh.com** (VN, Mobile World Group) — `ERR_CONNECTION_RESET` on `/` and product paths. WebFetch returns "socket connection was closed unexpectedly".
- **ukrstat.gov.ua** (UA) — TCP-level connection drop from non-UA IPs (`curl` returns code `000`, zero bytes). Affects the entire host including direct XLS downloads, so Wayback is the only workable fallback for stats-office data without a UA residential proxy.
- **kyivmetro.com** + **www.kyivmetro.com** (UA) — same TCP-level drop.
- **eldorado.com.ua** (UA) — TCP-level drop (the `.ua` apex `eldorado.ua` serves a real 404, but the `.com.ua` mirror drops the connection).
- **novus.zakaz.ua** (UA, Novus's q-commerce backend) — 403 with 16-byte body from non-UA; Novus's main `novus.ua` loads cleanly so probe both before classifying.
- **nhathuocankhang.com** (VN, also MWG) — same signature. Both MWG sites share infrastructure; a single bypass effort would unlock both.
- **villamarket.com** (TH) — `ERR_CONNECTION_RESET` on curl AND Playwright `goto`.
- **sendo.vn** (VN, general e-commerce) — redirects to sendofarm.vn; main catalog is a SPA with content-hashed CSS class names (d7ed-* prefix). Zero product prices in SSR HTML. Confirmed 2026-06-15.
- **metro.cn** + **www.maidelong.com** (CN, Metro China) — TLS handshake starts then stalls mid-handshake (same IP 220.196.43.244), classic GFW-style reset from non-CN IP. Probed 2026-07-27.
- **api.freshop.ncrcloud.com** (PH, WalterMart's Freshop catalog API) — **RESOLVED 2026-07-27, spider now `active: true` (~9,495 unique SKUs).** The earlier "aggressive IP throttle / off-network re-test needed" theory was WRONG. Two real causes, both fixed from the same network with a plain client: (1) the `502`/`SSLError` failures were the repo's default **curl_cffi impersonate handler** (`RandomBrowserMiddleware`) whose TLS fingerprint this host rejects — a normal Twisted client (plain `curl`) negotiates cleanly and returns 200. Fix: disable `RandomBrowserMiddleware` in the spider's `custom_settings`. (2) `/2/products` **ignores `offset`/`page`/`token`** (offset=0 and offset=5000 return the identical slice; `token` is an auth token → `sign_out_required`) and **hard-caps responses at 100 rows** (`limit` above 100 is clamped). So paging is impossible — walk the catalog by sharding on **leaf `department_id`** from the `/1/departments` tree (`/2/categories` 404s; `/2/departments` is v1-only) filtered `&department_id=<id>&sort=id`. Notes: the API **403s a non-browser UA** (keep `CustomUserAgentMiddleware`); backend key is `walter_mart`. Residual gap: 45 leaf departments still exceed the 100-cap (~3k tail rows unreached, logged per-department) — close later with dual-sort or price-range sub-sharding.

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

## Cloudflare "One moment please" interstitial (JS challenge, intermittent)

Site sometimes presents a Cloudflare JS verification challenge on the first request but resolves with curl using browser-realistic headers. Not a hard block — retry before treating as structural.

- **laostatefuel.com/en/gas-price.html** (LA, Lao State Fuel Company) — WebFetch returns interstitial but curl with browser UA returns full HTML 2026-06-15. Fetcher uses requests; works fine.

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
- **hktvmall.com** (HK, HK's largest online mall) — the old "Akamai tarpit" flag does NOT reproduce (2026-07-27): no `_abck`/`bm_sz`/`ak_bmsc` cookies, no Access-Denied challenge, only `NLBI` + `x-session-lang`; intermittent 0-byte/302 under rapid curls = rate-gating, not a hard WAF. BUT catalog is **SPA-only** — zero products/prices/JSON-LD in HTML (only nav taxonomy, e.g. `data-maincat="AA11110000000"`), and all hybris/OCC endpoint guesses 404 (`/hktvwebservices/v2/hktv/products/search`, `/occ/v2/...`, etc.). Capture the product-grid XHR with a **headed Playwright/DevTools** trace, then replay. Playwright fallback viable. Probed 2026-07-27.
- **lotuss.com.my** (MY, Lotus's / Siam Makro) — **dual WAF over a Next.js SPA; deprioritize.** Storefront `/en/category/grocery` browsable but 355KB HTML has zero prices / no `__NEXT_DATA__` (client-side XHR). Backend is Siam Makro's "mango" GraphQL BFF, both fronts walled: `api.lotuss.com.my` = Cloudflare hard block (403 all paths); `api.makro.pro/graphql` = Tencent Cloud WAF on POST + needs auth token. (The "Mirakl" lead was a red herring — that's Siam Makro's Maknet B2B in TH, not the MY consumer catalog.) Would need a headless-browser capture of the GraphQL query + WAF-clearance cookies. Probed 2026-07-27.
- **giant.sg** (SG, DFI Retail Group — Giant hypermarket) — jQuery + Algolia InstantSearch v2 SPA; all product routes return HTTP 404 server-side (client-side routing only). Product catalog exclusively served via Algolia index `giant_product_live` (app `PFCHI1YM66`). Algolia DSN (`pfchi1ym66-dsn.algolia.net`) and all three fallback shards (`pfchi1ym66-{1,2,3}.algolianet.com`) return DNS NXDOMAIN from non-SG IPs — not resolvable even from Playwright/headless Chromium. PDP pages return HTTP 404 with 250KB SPA shell; 12s Playwright wait yields no product name, price, or JSON-LD product data. Sitemap (`/sitemap_product.xml`) has 15,630 product slugs (e.g. `uht-full-cream-milk-1l-5001968`) but URLs are client-side routes only. No alternative server-side product API found. Viable only from a Singapore residential IP with a working Algolia DSN route. Probed 2026-06-30.

- **wolt.com restaurant venues** (multi-country, e.g. `wolt.com/en/grc/athens/venue/kalo-pizza`) — **`_wolt_base.py`'s category-walk pattern silently returns near-nothing for restaurant/food venues; it only works for grocery venues.** Grocery venues' `query-state` blob carries a `venue-assortment/category-listing` query (category slugs) + a per-category `venue-assortment/category` query returned by GET-ing `/items/<slug>` — that's what `_wolt_base.py` parses. Restaurant venues have migrated to a "unified store page" content model: the SAME `/items/<slug>` URL (any slug, even a nonexistent one — the category param is ignored) returns only a `venue-assortment/venue-content` query whose single `sections[]` entry is a curated "Most ordered" teaser (~9 items), never the full per-category menu (`ΠΙΤΣΕΣ`/`BURGERS`/etc. category names appear in the DOM as anchor-scroll tabs, not routes). Confirmed via full Playwright network trace (`networkidle` + scroll + tab click) — no further XHR ever fetches the remaining categories; the data plainly is not shipped to the client for categories beyond "Most ordered". The "Most ordered" teaser items do carry real name+price and would individually clear the 5-row gate, but shipping it would badly under-represent the venue's real menu (5 of 6 categories invisible) and the item set is algorithmically curated/rotating, not a stable observable catalog — not shipped. No open menu API found (`consumer-api.wolt.com/order-xp/web/v1/venue/slug/<slug>/dynamic/` returns delivery/checkout metadata only, no items). Division 11 (restaurants & accommodation) remains a genuine gap in the repo; the Eurostat PPP price-level-index route (`prc_ppp_ind`, ppp_cat=A0111) was used instead as a 38-country index-level substitute — a real per-restaurant price source for division 11 is still an open lead. Probed 2026-08-07.

## Hashed-CSS-class SPAs (content-hashed class names)

Next.js / styled-components / similar where class names are content-hashed at build time. Selectors observable in a dump break on every site deploy. Selection by structure (tag positions, attribute prefixes like `class*="ProductCard"`) is sometimes possible but fragile — defer unless high priority.

- **truemeds.in** (IN) — re-tested 2026-05-18: listing returned 0 `a[href^="/otc/"]` anchors; SPA does not hydrate cards in headless Chromium at all (likely bot fingerprinting on top of hashed classes). Stay deferred; needs real-browser stealth + residential IN IP.
- **sendo.vn** (VN) — d7ed-* hashed CSS class names; React SPA; zero product prices in server-rendered HTML. See also CDN connection-reset section for the sendo.vn redirect chain. Probed 2026-06-15.

## JS punishment redirect (session cookie + window.location.reload)

Site returns a tiny HTML stub that sets a session cookie and forces a reload; bare HTTP clients loop forever. Signature: 177-byte HTML body with `document.cookie="D1N=<hex>"` and `window.location.reload(true)`.

- **lazada.vn** (VN, Lazada Vietnam — Alibaba marketplace) — `<script>sessionStorage.x5referer=...;window.location='//…/punish?x5secdata=…'</script>` JS punishment redirect on category/search pages. Probed 2026-06-15.

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

**French Polynesia — ecourses.carrefour.pf (probed 2026-08-11 from a non-PF IP):** Carrefour Polynésie's real online-ordering platform (self-hosted, LiteSpeed server, no CDN/WAF fingerprint — distinct from the Majid Al Futtaim Gulf-Carrefour Akamai tenant elsewhere in this file). `carrefour.pf/courses-en-ligne-iles` links to `ecourses.carrefour.pf/{punaauia,arue}` (~8,500 products per the marketing copy) which 403s with an explicit branded message: "Vous ne pouvez pas accéder à notre boutique depuis votre pays" (you cannot access our store from your country) — an app-level IP geofence, not a bot challenge, so Playwright would hit the identical check from the same egress IP and wasn't run. `carrefour.pf/catalogue-en-ligne` is a red herring — it only embeds a v.calameo.com flip-book flyer, not a product catalog. Needs a PF-resident IP to probe further.

## JD proprietary bot detection — JDR_shields + login wall (200 OK + bot-challenge stub)

JD.com runs its own in-house bot detection stack called `JDR_shields`. Curl to product or category pages returns HTTP 200 but body is a ~2,704-byte JS challenge page (title "京东验证" = "JD Verification", `window.bp_bizid="JDR_shields"`). Playwright with `--disable-blink-features=AutomationControlled` reaches JD's login page (title "京东-欢迎登录"), not product listings — all returned "product-like" links are `passport.jd.com/new/login.aspx` login redirects. No API endpoint is reachable without a valid JD account session. This is a proprietary challenge, not Cloudflare or Akamai. Bypass requires a registered JD account + residential CN IP + captcha solver or official JD Open Platform API key.

- **www.jd.com / channel.jd.com / item.jd.com** (CN, JD.com — largest CN online retailer; covers groceries, pharmacy, apparel, electronics, personal care) — JDR_shields 2704-byte bot challenge on curl; login wall on Playwright. Confirmed blocked 2026-06-30. Probed food category (`channel.jd.com/food.html`) + product PDP + JD supermarket subdomain. COICOP 01/02/05/06/08/13 gap; no public food-retailer coverage available without auth.

## App-only / no scrapeable web catalogue

The site exists but products are not browsable on the web. Skip — no amount of scraping helps.

- **happyfresh.id** (ID) — landing page is "Download the app" only.
- **astronauts.id / astro** (ID) — geo-fenced to ID residential IPs AND mostly app-driven.
- **food.grab.com/mm/en/** (MM, GrabFood Myanmar) — hard login wall; "Login to search location" before any restaurant or menu data is visible. Confirmed June 2026. SKIP.
- **shop.com.mm** (MM, Daraz Myanmar) — SPA with no prices in SSR HTML (confirmed June 2026; see SPA section above). No login required but product cards never populate in HTML source. Alibaba/Daraz platform.
- **Kmanek Supermarket / Leader Hypermart** (TL) — Facebook-only, no public e-commerce site.
- **songo.mn** (MN, food delivery) — ECONNREFUSED on direct fetch 2026-06-10; Facebook page active but web portal appears offline or heavily restricted. Skip until web portal confirmed operational.
- **food.grab.com/vn/en/** (VN, GrabFood Vietnam) — same login wall as GrabFood MM; "Login to search location" before any restaurant/menu data visible. Probed 2026-06-15.
- **viettel.vn** (VN, Viettel telco) — cookie-challenge anti-bot: 177-byte HTML stub with `document.cookie="D1N=…"; window.location.reload(true)`. Plan prices not accessible without a real browser session. Probed 2026-06-15.
- **foody.vn** (VN, restaurant aggregator / delivery) — login wall (21+ occurrences of "login" in page); restaurant menu prices not accessible without account. Probed 2026-06-15.
- **gov.bn "Pengguna Bijak" / SmartConsumer** (BN, `www.gov.bn/Lists/Mobile%20Apps/NewDisplayForm.aspx?ID=5`) — government price-comparison app; the listing page is a bare SharePoint entry with a Google Play link (`bn.gov.egnc.jpke_smartconsumer`) and category "Shopping", no web catalogue, no linked API. Probed 2026-08-11.
- **puregold.com.ph** (PH, Puregold — major hypermarket chain) — corporate Joomla site (IR/news/careers only; `index.php?format=feed&type=atom` is a Joomla tell), zero catalog links. The onboarding-brief URL path `/pgcatalog/category/view/category/...` 404s outright — that catalog route has been removed. Current online-shopping channel is the "Puregold Mobile" app (Google Play, `com.grocery.puregold`) confirmed via web search — app-only. `pgcms.puregold.com.ph` is a Vite SPA titled "Puregold CMS" with an empty `#root` — an internal admin tool, not a public storefront. `shop.`/`eshop.` subdomains don't resolve. Probed 2026-08-11.

## Brochure-only WordPress / no online store

WordPress site for an offline retailer — pages exist, products do not. No /shop/, no /product/, no PDPs.

**A 200 here is not a connectivity win.** Both sites below were flagged "worth retrying from a SEA-origin IP" after earlier probes failed at the network layer, and both did start returning HTTP 200 — with brochure content. The earlier network failure was a red herring; the sites have no catalog to reach. Read the body before treating a status-code change as progress.

- **caring2u.com** (MY, Caring Pharmacy) — WordPress + Elementor brochure; `/products` 404s. For MY pharmacy coverage use `guardian_my` (live Tier 1B) instead.
- **kimiafarmaapotek.co.id** (ID, Kimia Farma) — same shape: Elementor Pro + OceanWP, zero e-commerce hooks. For ID pharmacy coverage `k24klik` is already in the tree.

## sgcaptcha / SignalGate CAPTCHA (200 OK + 168-byte JS redirect stub)

Site returns HTTP 200 but body is a 168-byte HTML stub with `<meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=...">`. The redirect target is a CAPTCHA challenge page. Neither bare curl nor simple browser-UA requests bypass it. Signature: tiny body (<200 bytes), `/.well-known/sgcaptcha/` in the refresh URL, `ipc:` prefix in the challenge parameter.

- **supasave.com.bn** (BN, Supa Save supermarket) — both main domain and `seria.supasave.com.bn` subdomain return the sgcaptcha stub. Brunei's main supermarket chain; COICOP 01 gap remains. Probed 2026-06-10.

## Aggregator / no canonical per-product URL

Site has products but each one is a modal within a shop page, not a canonical `/product/{id}` URL. Doesn't fit the price-spider model unless reworked to per-shop scraping.

- **foodpanda.la** (also caught by PerimeterX above)
- **happyfresh.id** (aggregator + app-only)

## No products on the site (corporate marketing portal)

Domain exists and renders but has no e-commerce — corporate/brand portal.

- **paylessmarkets.com** (GU, Pay-Less Supermarkets Guam — main supermarket chain) — Laravel/Vue corporate site (XSRF-TOKEN + laravel_session cookies). `/departments/grocery` is a department-info landing page + feedback form, zero product links, zero prices in rendered HTML (Playwright network trace showed only a reCAPTCHA call, no product API). Nav has `/specials` and `/promos` — both checked, `/promos` links only recipe-cookbook PDFs (not weekly price flyers), `/specials` has zero price mentions. No online catalog exists on this domain. Probed 2026-08-11.
- **pxmart.com.tw** (TW) — corporate Next.js portal. Links go to /about-us, /bulletin, /esg. No catalog. The real store is **PXGo! (`shop.pxgo.com.tw/mweb/`, Vite hash-routed SPA)** with a **clean no-WAF JSON API** (`https://mwebapi.pxgo.com.tw/2ndwa/`, product endpoint `POST /2ndwa/api/goods/goodsQuery`) — BUT the entire catalog is behind **PX Pay member auth** (every call → 401 `暫未登錄`; token minted via `/api/member/login` → `member.pxpay.com.tw`, no anonymous/guest login in the bundle; registration likely needs a TW mobile + OTP). Scaffold only if a member Bearer token can be held. Probed 2026-07-27.
  - **UPDATE 2026-08-11:** the `/inBatches/category/<id>` group-buy (合購) flow — a separate PXGo entry point from the member-gated `goodsQuery` API above — is *also* blocked, independently: HTTP 403 on both curl (`server: Please assist with the cashier`, `via: 1.1 google`, CSP referencing `*.qcloud.com`/`*.pxpay.com.tw` — looks like a Chinese-market WAF product front, not Cloudflare/Akamai/Incapsula/DataDome) and headless Playwright (`<title>403</title>`, 175-byte generic body). Two independent walls now confirmed on this tenant (member-auth on the API, edge WAF on this web path) — deprioritize PXGo/PXMart entirely rather than re-probing other entry points.
- **www.yonghui.com.cn** (CN, 永辉超市 Yonghui Superstore — major CN grocery chain) — corporate news/IR site. Links are exclusively news article paths (`/html/web/latestnews/...`). Zero prices, zero product links in 49KB HTML. Yonghui's consumer-facing stores operate via app (永辉生活) not a public web catalogue. Probed 2026-06-30. COICOP 01 gap remains.
- **brianbell.com.pg** (PNG) — corporate portal. `/product-category/appliances` 404s. `homecentres.brianbell.com.pg/shop/` redirects to "/" with no e-commerce markup. B2C division has no public web storefront.
- **e-mart.mn** (MN) — corporate marketing site for eMart. Actual store is at **emartmall.mn** (SPA shell — see above).
- **www.superindo.co.id** (ID, Super Indo — Indonesia's 2nd-largest supermarket chain) — marketing/promo portal; no online catalog and no individual product PDPs. Homepage has a rotating "Super Hemat" carousel with ~10 weekly promotional items (SSR HTML text, product name + price, but ZERO href links on the items). All product paths (/produk, /product, /kategori, /category) redirect to homepage. `/promosi/katalog-super-hemat/` serves the weekly catalog as JPEG flyer images (HEMAT_E_26_(N)_DKI.jpg, FLYER_E_26_DKI.jpg). No subdomains (shop.superindo.co.id etc. all ECONNREFUSED). No wp-json, no sitemap, no JSON API. Probed 2026-06-30. DEMOTE: promo-flyer-image-only + no per-product catalog.
- **www.robinsonssupermarket.com.ph** (PH, Robinsons Supermarket — PH's 2nd-largest supermarket chain, 151 branches) — corporate marketing/branding site; no per-product catalog, no pricing API. Homepage APIs (`/api/carouselApi`, `/api/regionApi`, `/api/branchApi`, `/api/promos/offers/featured`) serve promo carousels, branch/store-locator data, and news only. Promo catalogs (`/catalogs`) are PDF flyers. "Order Online" nav link leads to a news article about third-party delivery partners. Subdomains (shop/delivery/order/grocery/online) all ECONNREFUSED. `robinsonsdelivery.com.ph` is a ParkLogic parked domain. `gorobinsons.ph` SSL broken. `gocart.ph` ECONNREFUSED. Robinsons SKUs already covered by the existing `pickaroo` spider via `ops.pickaroo.com/groceries/brands/supermarket/`. Probed 2026-06-30. DEMOTE: no standalone web product catalog.
- **villagegrocer.com.my**, **big.com.my (Ben's Independent Grocer)**, **aeonbig.com.my**, **heromarket.com.my** (MY) — brochure/recipe WordPress; ordering routed to Foodpanda app deep-links. No `/shop` catalog. **giant.com.my** + **econsave.com.my** have WooCommerce themes but empty/absent `/shop` (dead storefronts). Probed 2026-07-27.
- **yiguo.com (易果生鲜)** (CN) — static archived placeholder (`<!-- saved from url=... -->`), banner JPEGs only, effectively defunct. **carrefour.com.cn** — Carrefour exited mainland China Aug 2025 (rebranded CACIOUS under Suning), no live domain. **Missfresh (每日优鲜)** — bankrupt 2023. Probed 2026-07-27.
- **kaibo.com.hk** (HK, Kai Bo Food Supermarket) — brochure-only 1.7KB page (company blurb + store-address nav), no `/shop` or product paths. Probed 2026-07-27.
- **DCH Foods / 大昌食品 (HK)** — eShop is **down/decommissioned**: `dchfood.com` → 302 corporate `dch.com.hk` (no shop); the real eShop host `foodmart.dchliving.com` is **NXDOMAIN**, `www.dchfoodmartdeluxe.com` has no A record. No live storefront to probe. If `foodmart.dchliving.com` returns, likely Shopline (Cloudflare-fronted) → try `/products.json` + JSON-LD. Probed 2026-07-27.

## DataDome bot-protection (HTTP 403, `x-datadome` header)

- **myaeon2go.com** (MY, AEON's q-commerce) — HTTP 403 on every request, `server: DataDome` + `x-datadome: protected`. Needs a real browser + DataDome solver; skip. Probed 2026-07-27.
- **aeoneshop.com** (VN, AEON Vietnam eShop) — HTTP 403 `server: DataDome` on curl (root and product-search paths). Playwright confirms the same wall one layer deeper: page loads a `geo.captcha-delivery.com` interactive-challenge stub (`dd={'rt':'c', ...'host':'geo.captcha-delivery.com'...}`), not just a flat 403. Second AEON property on this file now flagged DataDome (see myaeon2go.com, MY) — worth treating AEON's e-commerce vendor stack as a DataDome tenant going forward, though each is a separate storefront/country deployment, not one shared domain. Probed 2026-08-11.

## SSL certificate mismatch (retired/consolidated domain)

- **uselect.com.hk** (HK, U Select — China Resources Vanguard brand) — TLS cert covers `crc.com.hk` siblings, not this hostname; HTTP 403 even with `-k`. Domain likely retired/folded into the CRV group platform. Probed 2026-07-27.
- **starmartmacao.com** (MO, Star Mart Macao) — not a WAF: HTTPS connect times out at the TCP layer on both apex and `www.`, but plain HTTP (port 80) connects fine and 302-redirects to `index.php`, which renders a registrar "ERRP | Expired Registration Recovery Policy" parking notice. Domain registration has lapsed — no scrapeable business behind it. Probed 2026-08-11.

## Qrator anti-bot (Russian anti-DDoS, `__qrator/qauth.js` JS challenge, HTTP 401/403 titled "HTTP 403")

Qrator is a Russian anti-DDoS/WAF vendor common on large RU retail and government sites. Signature: response body is a near-empty HTML shell whose only content is `<script src="/__qrator/qauth.js">`, or a 401/403 page titled literally "HTTP 403". Confirmed to block both plain curl *and* headless Playwright (no auto-solve of the JS challenge) — see `auchan.ru` below for the paired trace. Not the same product as Cloudflare/Akamai/Incapsula elsewhere in this file; treat as its own tenant-independent class (it's a shared vendor, not one operator's infra) but each site should still be re-checked, since severity varies (dns-shop.ru serves the qauth.js shell on 401; others may only gate specific paths).

- **www.auchan.ru** (RU, Auchan Russia — hypermarket, COICOP 01/02/05/09 candidate) — curl: HTTP 401 + `__qrator/qauth.js` shell. Playwright (headless Chromium, 6s wait): also 401, page titled "HTTP 403", 1262-byte body — same wall, confirms real block per this file's curl+Playwright trigger. Probed 2026-08-07 (round-3 Russia shard).
- **www.utkonos.ru** (RU, Utkonos — grocery delivery, COICOP 01/02 candidate) — curl: HTTP 401 + identical `__qrator/qauth.js` shell (byte-identical to auchan.ru's). Probed 2026-08-07; Playwright not separately re-run (same shell signature as the confirmed auchan.ru pair).
- **www.dns-shop.ru** (RU, DNS — national electronics chain, COICOP 08/09 candidate) — curl: HTTP 401, `qrator_jsr` challenge cookie set on the homepage visit, product-sitemap discovery works (`sitemap-products1..N.xml`, dated today) but every page request 401s. Probed 2026-08-07. Worth revisiting with a Qrator-solving browser session if RU electronics coverage becomes a priority — sitemap + page structure otherwise look tractable.
- **lemanapro.ru** + **www.lemanapro.ru** (RU, Leroy Merlin Russia's 2023 rebrand after the group's exit — home-improvement, COICOP 05 candidate) — `www.` apex 301s to bare domain, which then 401s with the same shell. Probed 2026-08-07.
- **www.vseinstrumenti.ru** (RU, tools/hardware, COICOP 05 candidate) — HTTP 403, small themed error body (1.6KB) rather than the bare qauth.js shell, but same vendor family by response shape. Probed 2026-08-07; not Playwright-confirmed.
- **www.citilink.ru** (RU, electronics, COICOP 08/09 candidate) — HTTP 429 on every request including the bare homepage, single request, cold connection (not burst-triggered). Probed 2026-08-07; not confirmed same vendor but consistent with an aggressive edge-rate-limit posture on this cluster of RU retailers.

## Reachable, HTTP 200, but not extractable without more work (not a hard block — don't re-probe blind, but don't write off either)

- **online.metro-cc.ru** (RU, Metro Cash & Carry — hypermarket, COICOP 01/02/05/09 candidate) — genuinely reachable: homepage sets a `metroStoreId` cookie, `/sitemap-3.xml` lists real `/products/<slug>` URLs, and product pages return 200 with a JSON-LD `Product` block. But the JSON-LD `offers` object carries `priceCurrency`/`availability` and **no `price` field** — the actual price lives only inside a heavily minified `window.__NUXT__=(function(a,b,c,...){...})(...)` positional-argument call, not parseable as JSON without executing the JS (a regex/string search finds no plain `"price":<number>` near the product). A rendered-DOM read (Playwright, `[class*=price]`) is the likely path but wasn't completed this round — the product page itself also 404s/hangs on cold Playwright navigation without first visiting `/` in the same context to pick up `metroStoreId`. Worth a real pass: sitemap + cookie + platform are otherwise clean. Probed 2026-08-07.
- **magnit.ru** (RU, Magnit — one of Russia's two largest grocery chains, COICOP 01/02/05 candidate) — homepage is a real, large (800KB) Nuxt SSR grocery-delivery storefront and `__sitemap__/products.xml` lists ~19,900 `/product/<slug>` URLs with same-day `lastmod`, but **every sampled product URL 404s** (confirmed both via curl-with-cookies and a fresh headless-Playwright session) and the 404 response is a soft-404 that renders the homepage shell (same `<title>`) rather than a real 404 page. The sitemap and the live routing appear to disagree — possibly a recent route-schema migration the sitemap generator hasn't caught up with. Not a WAF block; a data-freshness/routing mismatch. Worth a re-check in a future round rather than a deep dig now. Probed 2026-08-07.
- **www.rigla.ru** (RU, Rigla — national pharmacy chain, COICOP 06/13 candidate) — reachable, real product pages, but **price is per-pharmacy-branch**: the embedded state (`pvzIsgTabs[].items[]`) lists dozens of physical branches each with their own price for the same SKU, with no single "the" price for the product the way apteka.ru or komus.ru expose one. Extractable but needs a branch-selection policy (nearest/median/cheapest) decided before scaffolding — skipped this round in favour of apteka.ru, which already covers the same COICOP ground with a clean single national price. Probed 2026-08-07.
- **detmir.ru** (RU, Detsky Mir — Russia's largest kids' goods retailer, COICOP 03/09/13 candidate) — homepage and category/brand landing pages are real server-rendered HTML (no WAF/challenge), with a `window.appData = JSON.parse("...")` blob (double-JSON-encoded: the outer text is a JS string literal whose *content*, after `json.loads` twice, is one big app-state dict). That blob genuinely contains real product rows with `id`/`title`/`price`/`prices.old`/`prices.sale` (verified: "Комбинезон BabyGo" 349 RUB with a real old-price of 499 RUB) but only inside `.recommendations.products.*.result[]` widget arrays (~15-30 items per page) — the *actual* full category/search product grid (thousands of items, `offerCount` in the JSON-LD confirms e.g. 2776 for one brand) is **not** in the SSR payload; a live Playwright network capture on a `/search/?text=...` page fired 13 XHRs to `api.detmir.ru` (cart, user, menu, recently-viewed) but never the actual search/listing endpoint in a ~6s window — it may fire on scroll, on a different query-param shape, or need a longer wait. Not blocked, just unfinished. Worth a real pass: either (a) find the true listing endpoint via a longer Playwright capture / scrolling the results grid, or (b) walk only the recommendation-widget arrays across many category pages as a lower-volume-but-zero-effort alternative. Probed 2026-08-07 (round-3 Russia shard, shard A3).

## DDoS-Guard (Russian anti-bot, `DDOS-GUARD` page title, `/.well-known/ddos-guard/js-challenge/`)

Distinct vendor from Qrator (different challenge JS path, different page chrome) but same tenant-independent "stop, don't re-probe" logic applies. Confirmed blocking both curl and headless Playwright with an identical page title — the strongest confirmation tier in this file.

- **www.chitai-gorod.ru** (RU, Chitai-Gorod — national bookstore/stationery chain, COICOP 09 candidate) — **UPDATE 2026-08-07 (shard A3 resume): now a confirmed hard block, supersedes the 2026-08-07 "not extractable" entry below.** curl on `/product/<id>`: HTTP 403, 898-byte body, `<title>DDoS-Guard</title>`, `check.ddos-guard.net/check.js`. Playwright (headless Chromium, 8s wait): page title `DDOS-GUARD`, 4739-byte body — same wall. The sitemap-index request that looked clean in the original probe (`/sitemap.xml` → `/sitemap/products1.xml`) still returns HTTP 200 (DDoS-Guard appears to allow sitemap crawling but gate `/product/` pages specifically), so the original "timeout, not diagnosed" verdict undersold it: this is now a clean block signature, not a flaky timeout. COICOP 09 (books/culture) gap remains open elsewhere. Do not re-probe without a residential proxy / captcha-solving setup.

Original (superseded) entry, kept for the timeout signature in case it recurs elsewhere: homepage and `/sitemap.xml` → `/sitemap/products1.xml` (18 chunks, ~50k URLs each) both load fine over plain curl, but every `/product/<slug>` request timed out (`curl: (28)`, 0 bytes) across three separate attempts with pauses in between.

## ServicePipe anti-bot (Russian anti-DDoS, `servicepipe.tech` challenge loader + rotated-image captcha)

Third distinct RU anti-bot vendor seen this round (alongside Qrator and DDoS-Guard). Signature: a tiny (~1.6KB) HTML shell loading `https://servicepipe.tech/loaders/<hash>.js` and `.../checkjs/<hash>/<hash>.js`, with an embedded `get_options()` JS blob and a `<noscript>` refresh to a randomized path. Confirmed blocking both curl and headless Playwright — Playwright resolves the JS challenge redirect but lands on a **rotated-image captcha** page (`sp_rotated_captcha`), not the target site.

- **www.perekrestok.ru** (RU, Perekrestok — X5 Group supermarket chain, COICOP 01/02/05/09/13 candidate) — curl: 200 but 1578-byte ServicePipe challenge shell. Playwright (8s wait): redirected to a `sp_rotated_captcha` image-captcha page, page title empty, 16KB body. Same infra likely shared across the whole X5 Group (Perekrestok, Pyaterochka, Kuper — see below). Probed 2026-08-07 (round-3 Russia shard, shard A3).
- **kuper.ru** (RU, Kuper — X5 Group's rebranded SberMarket grocery-delivery marketplace; `www.sbermarket.ru` 301s here) — identical ServicePipe shell (same `get_location()`/`get_options()` structure, different hashes). Not separately Playwright-confirmed but byte-for-byte same signature as the confirmed perekrestok.ru pair — same tenant. Probed 2026-08-07.

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

## Brochure-only — no online store (Vanuatu)

- **aubonmarche.co** (VU, Au Bon Marché) — corporate/marketing site; no product catalogue, no prices. Retail section returns a job-application page for "Retail Supervisor." Vanuatu's largest supermarket but no e-commerce presence. COICOP 01 retail SKU gap remains. Probed 2026-06-10.

## React SPA with Supabase backend — no server-rendered listings

Site is a React SPA backed by a Supabase PostgreSQL REST API. Server-rendered HTML contains only app shell. Listings load via Supabase PostgREST queries.

- **bas.com.fj** (FJ, Fiji classifieds — cars, property, electronics) — React SPA. Supabase backend at `bflgucswqljuhmkhilvv.supabase.co`. HTML source contains only `<div id="root"></div>` shell. 42,000+ listings in Suva/Nadi/Lautoka. Check whether `supabase.co` PostgREST API is publicly accessible without anon-key headers — if so, Tier 1B (scrapy_api). Otherwise needs Playwright network-capture to sniff the Supabase REST endpoint. Probed 2026-06-10.

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

## Stale DAM PDF URL — 200 OK serving HTML "Page not available"

CDN-fronted document servers (Magnolia, Adobe AEM, similar) sometimes serve a 200 OK + tiny HTML "Page not available" page from a vanity URL whose backing document has been retired. HEAD returns 308 + a content-disposition that *looks* like a PDF, but the body of a real GET is HTML. Always `file <download>` after curl — if it says `HTML document` when content-type claimed `application/pdf`, the URL is stale.

- **www.spgroup.com.sg/wcm/connect/...Tariff+Revision+for+Q4+2025.pdf** — example of a stale Magnolia link surfaced by an old search-engine snapshot. Real current docs live under `/dam/jcr:<uuid>/`. Use `WebSearch allowed_domains=[<host>]` to find the canonical current URL instead of guessing path patterns.

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
