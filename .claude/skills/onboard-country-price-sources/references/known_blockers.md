# Known Blockers

Sites we've already classified as unscrapeable with our current stack (no residential proxy, no captcha solver). **Check this list before probing** — saves cycles.

This file is keyed by **blocker class / CDN family**, not region. Country examples sit as bullets under the class that diagnosed them. When a new site is blocked, attach it to the class whose signature matches — that's how shared infrastructure becomes obvious (Foodstuffs NZ, AS-Watson HK/SG/MY/TW, MWG VN, etc. each share a tenant's blocking profile across countries).

## Cloudflare strict (curl + Playwright both 403)

403 even with realistic UA + headers. Often serves a challenge page or interstitial. Headless Chromium without stealth + residential IP fails. Bypass would require a paid proxy/solver stack.

- **mymedicine.com.mm** (MM) — 403 on `/shop` and `/categories`. Myanmar online pharmacy; confirmed blocked June 2026. MEDiCARE (medicarehb.com.mm) is a viable alternative for COICOP 06.
- **blibli.com** (ID) — 403 on category + PDP. Professional anti-bot.
- **auction.co.kr** (KR, eBay Korea) — 403 on root and category.
- **coupang.com** (KR) — Cloudflare-style challenges plus per-storefront login soft-walls.
- **tops.co.th**, **bigc.co.th**, **homepro.co.th**, **powerbuy.co.th** (TH) — Cloudflare 403 on curl AND Playwright; appear to share a protection profile.
- **khmer24.com** (KH, Cambodia general classifieds) — HTTP 403 + Cloudflare Turnstile challenge page on curl with realistic Chrome UA; cf-ray ID confirmed in response body. Covers cars, real estate, electronics. Probed 2026-06-10.
- **foodpanda.com.kh** (KH, Delivery Hero Cambodia) — HTTP 403 on curl; same PerimeterX + Cloudflare stack as foodpanda.la. Probed 2026-06-10.
- **otw-tl.com** (TL, OTW food delivery Dili) — HTTP 403 on WebFetch to category pages (e.g. `/foods/?kategoriaproduto=...`). Local food delivery app in Dili. COICOP 11.1.1. No bypass attempted. Probed 2026-06-10.

## Cloudflare interactive challenge (`cf-mitigated: challenge`)

Distinct from a plain Cloudflare 403. Signature: HTTP 403 + response header `cf-mitigated: challenge` + a `content-security-policy` referencing `challenges.cloudflare.com` + a Turnstile widget in the body. Cloudflare wants an interactive proof-of-work / CAPTCHA, not just a bot fingerprint check. `scrapy-impersonate` (TLS fingerprinting alone) is **not enough** — needs `scrapy-playwright` + stealth plugin, possibly residential proxies, and for hot sites a Turnstile-solving service. Don't deploy as a side task during routine country onboarding; these are dedicated multi-hour efforts where the *first* site cracked produces a template that accelerates the rest.

- ~~**propertyguru.com.sg** (SG)~~ — **RESOLVED 2026-05-20.** Re-probe with `curl_cffi impersonate=chrome120` returned 200 + clean SSR HTML, no Turnstile, no `cf-mitigated` header. Spider built as plain scrapy-impersonate at `src/prices/price_scraping/spiders/propertyguru_sg.py`; ~560 listings/scrape via per-district crawl. **Lesson:** always re-probe before treating a Cloudflare-challenge entry as a structural blocker — WAF posture drifts.

## AWS WAF (`awswaf.com` challenge token)

WAF that returns 403 + a challenge token from `awswaf.com`. Blocks both HTML site and API gateway from the same tenant.

- **klikindomaret.com** + **ap-mc.klikindomaret.com** (ID) — AWS WAF challenge on both site and API gateway.

## Akamai tenant rate-limit / bot manager

Akamai's bot manager either 403s upfront or, for marketplaces with a softer profile, tarpits the session after ~1.9k items per spider with `curl(28)` timeouts (not 403s). When two Akamai-tenant spiders run in parallel, both die at roughly the same item count — that's the tenant's rate-limit signature. See [[watsons_akamai_2k_tarpit]] and [[watsons_requeue_strategy]] in engram for the requeue protocol.

- **woolworths.co.nz**, **newworld.co.nz**, **paknsave.co.nz**, **chemistwarehouse.co.nz** (NZ) — Foodstuffs/Akamai stack. One bypass effort would unlock all four.
- **watsons.com.tw** (TW, AS Watson) — persistent 403.
- **watsons.com.hk/en/macau-click-collect-express-delivery/\*** (HK/MO, AS Watson) — HTTP 403 from non-HK/MO IP on the Macao Click & Collect catalogue; same AS-Watson Akamai tenant profile as watsons.com.tw. Probed 2026-06-10.
- **shopping.coupang.com**, **lazada.\*.\<tld\>**, **shopee.\*.\<tld\>** — marketplace platforms with Akamai bot manager. Only viable via official affiliate APIs.

## Imperva Incapsula (212-byte JS-challenge stub)

Site returns a tiny (~212-byte) HTML stub containing a JS challenge. `scrapy-impersonate` alone returns the stub — not a real product page. The diagnostic is body length + presence of the Incapsula JS bootstrap. See [[coles_au_ua_impersonate_mismatch]] in engram for the full probe protocol (Coles AU). Also includes the gotcha that scrapy `custom_settings` dict-replace can mask the real failure.

- **makro.co.th** (TH, Siam Makro) — Incapsula 403 on curl AND Playwright.
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

Real-browser requests from a non-target-country IP are dropped at the CDN before any HTTP response. Headless Chromium does not bypass — the connection is reset pre-response. Bypass requires a residential proxy in-country. Distinct from Wayback-IA's intermittent L4 blackhole (see [[wayback_ia_blackhole_risk]]) which only fires under sustained parallel load.

- **shop.cpl.com.pg** (PNG, CPL Group — Stop & Shop supermarket, PNG's largest retailer) — `ECONNREFUSED` on WebFetch from non-PNG IP. Online grocery/pharmacy/hardware shop at shop.cpl.com.pg. Likely CDN geo-fence restricting to PNG residential IPs. Probed 2026-06-10. Revisit with PNG residential proxy before attempting to onboard as retailer_sku spider.
- **bachhoaxanh.com** (VN, Mobile World Group) — `ERR_CONNECTION_RESET` on `/` and product paths. WebFetch returns "socket connection was closed unexpectedly".
- **ukrstat.gov.ua** (UA) — TCP-level connection drop from non-UA IPs (`curl` returns code `000`, zero bytes). Affects the entire host including direct XLS downloads, so Wayback is the only workable fallback for stats-office data without a UA residential proxy.
- **kyivmetro.com** + **www.kyivmetro.com** (UA) — same TCP-level drop.
- **eldorado.com.ua** (UA) — TCP-level drop (the `.ua` apex `eldorado.ua` serves a real 404, but the `.com.ua` mirror drops the connection).
- **novus.zakaz.ua** (UA, Novus's q-commerce backend) — 403 with 16-byte body from non-UA; Novus's main `novus.ua` loads cleanly so probe both before classifying.
- **nhathuocankhang.com** (VN, also MWG) — same signature. Both MWG sites share infrastructure; a single bypass effort would unlock both.
- **villamarket.com** (TH) — `ERR_CONNECTION_RESET` on curl AND Playwright `goto`.
- **sendo.vn** (VN, general e-commerce) — redirects to sendofarm.vn; main catalog is a SPA with content-hashed CSS class names (d7ed-* prefix). Zero product prices in SSR HTML. Confirmed 2026-06-15.

## API requires dynamic security key / JWT

Bare curl returns 401/429 regardless of headers because a non-trivial token is required, derived client-side. Reverse-engineering is rarely worth it.

- **marketplace.com.mm** (MM) `/api/products/all` — dynamic `x-security-key` header (CryptoJS "Salted__" prefix, AES with client-side-derived key). 429 without it.
- **sayurbox.com** (ID) `/graphql/v1` — requires `authorization: Bearer <JWT>` + 10+ custom `x-sbox-*` headers + per-session `deliveryConfigId` base64 blob in the GraphQL variables.
- **alfagift.id** (ID) `webcommerce-gw.alfagift.id/v2/products/category/{id}` — 401 without auth token; init flow not investigated.
- **emartmall.mn** (MN) — SPA shell returns nothing useful to non-JS clients; needs a real Playwright probe to identify any API.

## Cloudflare "One moment please" interstitial (JS challenge, intermittent)

Site sometimes presents a Cloudflare JS verification challenge on the first request but resolves with curl using browser-realistic headers. Not a hard block — retry before treating as structural.

- **laostatefuel.com/en/gas-price.html** (LA, Lao State Fuel Company) — WebFetch returns interstitial but curl with browser UA returns full HTML 2026-06-15. Fetcher uses requests; works fine.

## SPA shell — no productive endpoint (lazy-load never hydrates)

Site loads, renders skeleton cards, but never hydrates fully within a reasonable Playwright wait. Or hides product data behind an API that itself requires SPA session state. The fix here, when there is one, is to find a parallel JSON endpoint (winmart's case).

- **telemor.tl/Home/Broadband** (TL, Telemor broadband) — SPA-gated; broadband/FTTH pricing not in page source; directs to contact email `esd@telemor.tl`. No public retail price list. Skip; mobile plans page (`/Home/Products?parentCode=MOBILE`) has prices in SSR HTML — probe that instead. Checked 2026-06-10.
- **unitel.com.la/en/mobile/packages** (LA, Unitel Laos — ~50% mobile market share) — Angular SPA; package names/prices not in SSR HTML (`{{ t('text') }}` visible). No API endpoint found. SKIP; use laotel.com FTTH as telco alternative. Probed 2026-06-10.
- **winmart.vn** *(HTML front-end)* — products render via `product-card-skeleton` divs that don't hydrate within 8s Playwright wait. **NOTE**: winmart's *JSON API* at `api-crownx.winmart.vn/it/api/web/v3/item/category` works with no auth — see `src/prices/price_scraping/spiders/winmart.py`. Tier 1B, not Tier 2.
- **shop.com.mm** (MM, Daraz Myanmar) — SPA confirmed June 2026. Category pages (`/health-care/`, `/medicines/`) return only navigation chrome in SSR HTML; zero product cards or prices. Alibaba/Daraz platform. No public API endpoint found. SKIP.
- **cargillsonline.com** (LK) — Angular SPA. After 12s wait + scroll, dump contains `{{...}}` placeholder syntax (Angular templates) for product details and only category-level `/Product/<cat>` links — `/ProductDetails/<sku>` URLs never hydrate.
- **osudpotro.com** (BD) — listing URL `/category/buy-over-the-counter-medicine-online-in-dhaka` renders **disease cards** (`<a href="/disease/...">`) not product cards. Catalog is by-disease; needs a different entry URL or direct PDP list.

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
- **telkomcel.tl** (TL, Telkomcel) — SSL certificate verification failure (`unable to verify the first certificate`) on `telkomcel.tl/p/internetrapidodemais` and subpages. Not a WAF; cert misconfiguration issue. Plans page `/page/prepaid/` returns 404. Use `requests` with `verify=False` on the root domain to check for plan pricing pages, or consult Wayback Machine. Checked 2026-06-10.

## Country-wide IP-fence cohort (HTTP 403 from non-target IPs, likely fine in-country)

Distinct from the CDN connection-reset section: these sites complete the TCP handshake and return an HTTP-layer 403 with a branded error page, indicating an application-tier IP allowlist (national CDN POP + WAF rule) rather than a structural anti-bot. Probing from outside the country produces false-negatives — the site likely works from a residential in-country IP. Skip from a non-target IP rather than waste cycles iterating on selectors against the error page.

**Mongolia cohort (probed 2026-06-10 from a non-MN IP):**

- **unegui.mn** (MN) — HTTP 403 from non-Mongolian IP; likely works from MN residential IP. Mongolia's main classifieds/real-estate portal. Application-tier IP allowlist, not Cloudflare. Needs in-country residential IP probe before building spider.

**Ukraine wartime cohort (probed 2026-06-09 from a non-UA IP, all 403'd):**

Supermarkets — silpo.ua, atbmarket.com, auchan.ua, varus.ua, megamarket.ua. Pharmacies — tabletki.ua, apteka911.ua, anc.ua. Marketplaces / electronics — rozetka.com.ua (429, rate-limit not 403), allo.ua, foxtrot.com.ua. Personal care — eva.ua, brocard.ua (404 on /uk/ — branded error). Utility/transport — naftogaz.com, booking.uz.gov.ua, minagro.gov.ua. Delivery — glovoapp.com/ua. Some of these may genuinely run Cloudflare strict — re-probe individually from a UA residential IP before deciding per-source.

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

## Brochure-only WordPress / no online store

WordPress site for an offline retailer — pages exist, products do not. No /shop/, no /product/, no PDPs. See [[caring2u_kimia_brochure_only]] in engram.

- **caring2u.com** (MY) — pharmacy chain WP brochure; flagged on v2 retry list, no online store.
- **kimiafarmaapotek.co.id** (ID) — same shape.

## sgcaptcha / SignalGate CAPTCHA (200 OK + 168-byte JS redirect stub)

Site returns HTTP 200 but body is a 168-byte HTML stub with `<meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=...">`. The redirect target is a CAPTCHA challenge page. Neither bare curl nor simple browser-UA requests bypass it. Signature: tiny body (<200 bytes), `/.well-known/sgcaptcha/` in the refresh URL, `ipc:` prefix in the challenge parameter.

- **supasave.com.bn** (BN, Supa Save supermarket) — both main domain and `seria.supasave.com.bn` subdomain return the sgcaptcha stub. Brunei's main supermarket chain; COICOP 01 gap remains. Probed 2026-06-10.

## Aggregator / no canonical per-product URL

Site has products but each one is a modal within a shop page, not a canonical `/product/{id}` URL. Doesn't fit the price-spider model unless reworked to per-shop scraping.

- **foodpanda.la** (also caught by PerimeterX above)
- **happyfresh.id** (aggregator + app-only)

## No products on the site (corporate marketing portal)

Domain exists and renders but has no e-commerce — corporate/brand portal.

- **pxmart.com.tw** (TW) — corporate Next.js portal. Links go to /about-us, /bulletin, /esg. No catalog.
- **brianbell.com.pg** (PNG) — corporate portal. `/product-category/appliances` 404s. `homecentres.brianbell.com.pg/shop/` redirects to "/" with no e-commerce markup. B2C division has no public web storefront.
- **e-mart.mn** (MN) — corporate marketing site for eMart. Actual store is at **emartmall.mn** (SPA shell — see above).

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

## Stale DAM PDF URL — 200 OK serving HTML "Page not available"

CDN-fronted document servers (Magnolia, Adobe AEM, similar) sometimes serve a 200 OK + tiny HTML "Page not available" page from a vanity URL whose backing document has been retired. HEAD returns 308 + a content-disposition that *looks* like a PDF, but the body of a real GET is HTML. Always `file <download>` after curl — if it says `HTML document` when content-type claimed `application/pdf`, the URL is stale.

- **www.spgroup.com.sg/wcm/connect/...Tariff+Revision+for+Q4+2025.pdf** — example of a stale Magnolia link surfaced by an old search-engine snapshot. Real current docs live under `/dam/jcr:<uuid>/`. Use `WebSearch allowed_domains=[<host>]` to find the canonical current URL instead of guessing path patterns.

## How to use this list

Before probing, grep this file for the candidate's domain. If it's listed:

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
