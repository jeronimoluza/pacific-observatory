# Known Blockers

Sites we've already classified as unscrapeable with our current stack (no residential proxy, no captcha solver). **Check this list before probing** — saves cycles.

This file is keyed by **blocker class / CDN family**, not region. Country examples sit as bullets under the class that diagnosed them. When a new site is blocked, attach it to the class whose signature matches — that's how shared infrastructure becomes obvious (Foodstuffs NZ, AS-Watson HK/SG/MY/TW, MWG VN, etc. each share a tenant's blocking profile across countries).

## Cloudflare strict (curl + Playwright both 403)

403 even with realistic UA + headers. Often serves a challenge page or interstitial. Headless Chromium without stealth + residential IP fails. Bypass would require a paid proxy/solver stack.

- **blibli.com** (ID) — 403 on category + PDP. Professional anti-bot.
- **auction.co.kr** (KR, eBay Korea) — 403 on root and category.
- **coupang.com** (KR) — Cloudflare-style challenges plus per-storefront login soft-walls.
- **tops.co.th**, **bigc.co.th**, **homepro.co.th**, **powerbuy.co.th** (TH) — Cloudflare 403 on curl AND Playwright; appear to share a protection profile.

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
- **foodpanda.\*** in general — same vendor.

## CDN connection-reset at TCP layer (`ERR_CONNECTION_RESET`)

Real-browser requests from a non-target-country IP are dropped at the CDN before any HTTP response. Headless Chromium does not bypass — the connection is reset pre-response. Bypass requires a residential proxy in-country. Distinct from Wayback-IA's intermittent L4 blackhole (see [[wayback_ia_blackhole_risk]]) which only fires under sustained parallel load.

- **bachhoaxanh.com** (VN, Mobile World Group) — `ERR_CONNECTION_RESET` on `/` and product paths. WebFetch returns "socket connection was closed unexpectedly".
- **ukrstat.gov.ua** (UA) — TCP-level connection drop from non-UA IPs (`curl` returns code `000`, zero bytes). Affects the entire host including direct XLS downloads, so Wayback is the only workable fallback for stats-office data without a UA residential proxy.
- **kyivmetro.com** + **www.kyivmetro.com** (UA) — same TCP-level drop.
- **eldorado.com.ua** (UA) — TCP-level drop (the `.ua` apex `eldorado.ua` serves a real 404, but the `.com.ua` mirror drops the connection).
- **novus.zakaz.ua** (UA, Novus's q-commerce backend) — 403 with 16-byte body from non-UA; Novus's main `novus.ua` loads cleanly so probe both before classifying.
- **nhathuocankhang.com** (VN, also MWG) — same signature. Both MWG sites share infrastructure; a single bypass effort would unlock both.
- **villamarket.com** (TH) — `ERR_CONNECTION_RESET` on curl AND Playwright `goto`.

## API requires dynamic security key / JWT

Bare curl returns 401/429 regardless of headers because a non-trivial token is required, derived client-side. Reverse-engineering is rarely worth it.

- **marketplace.com.mm** (MM) `/api/products/all` — dynamic `x-security-key` header (CryptoJS "Salted__" prefix, AES with client-side-derived key). 429 without it.
- **sayurbox.com** (ID) `/graphql/v1` — requires `authorization: Bearer <JWT>` + 10+ custom `x-sbox-*` headers + per-session `deliveryConfigId` base64 blob in the GraphQL variables.
- **alfagift.id** (ID) `webcommerce-gw.alfagift.id/v2/products/category/{id}` — 401 without auth token; init flow not investigated.
- **emartmall.mn** (MN) — SPA shell returns nothing useful to non-JS clients; needs a real Playwright probe to identify any API.

## SPA shell — no productive endpoint (lazy-load never hydrates)

Site loads, renders skeleton cards, but never hydrates fully within a reasonable Playwright wait. Or hides product data behind an API that itself requires SPA session state. The fix here, when there is one, is to find a parallel JSON endpoint (winmart's case).

- **winmart.vn** *(HTML front-end)* — products render via `product-card-skeleton` divs that don't hydrate within 8s Playwright wait. **NOTE**: winmart's *JSON API* at `api-crownx.winmart.vn/it/api/web/v3/item/category` works with no auth — see `src/prices/price_scraping/spiders/winmart.py`. Tier 1B, not Tier 2.
- **cargillsonline.com** (LK) — Angular SPA. After 12s wait + scroll, dump contains `{{...}}` placeholder syntax (Angular templates) for product details and only category-level `/Product/<cat>` links — `/ProductDetails/<sku>` URLs never hydrate.
- **osudpotro.com** (BD) — listing URL `/category/buy-over-the-counter-medicine-online-in-dhaka` renders **disease cards** (`<a href="/disease/...">`) not product cards. Catalog is by-disease; needs a different entry URL or direct PDP list.

## Hashed-CSS-class SPAs (content-hashed class names)

Next.js / styled-components / similar where class names are content-hashed at build time. Selectors observable in a dump break on every site deploy. Selection by structure (tag positions, attribute prefixes like `class*="ProductCard"`) is sometimes possible but fragile — defer unless high priority.

- **truemeds.in** (IN) — re-tested 2026-05-18: listing returned 0 `a[href^="/otc/"]` anchors; SPA does not hydrate cards in headless Chromium at all (likely bot fingerprinting on top of hashed classes). Stay deferred; needs real-browser stealth + residential IN IP.

## Country-wide IP-fence cohort (HTTP 403 from non-target IPs, likely fine in-country)

Distinct from the CDN connection-reset section: these sites complete the TCP handshake and return an HTTP-layer 403 with a branded error page, indicating an application-tier IP allowlist (national CDN POP + WAF rule) rather than a structural anti-bot. Probing from outside the country produces false-negatives — the site likely works from a residential in-country IP. Skip from a non-target IP rather than waste cycles iterating on selectors against the error page.

**Ukraine wartime cohort (probed 2026-06-09 from a non-UA IP, all 403'd):**

Supermarkets — silpo.ua, atbmarket.com, auchan.ua, varus.ua, megamarket.ua. Pharmacies — tabletki.ua, apteka911.ua, anc.ua. Marketplaces / electronics — rozetka.com.ua (429, rate-limit not 403), allo.ua, foxtrot.com.ua. Personal care — eva.ua, brocard.ua (404 on /uk/ — branded error). Utility/transport — naftogaz.com, booking.uz.gov.ua, minagro.gov.ua. Delivery — glovoapp.com/ua. Some of these may genuinely run Cloudflare strict — re-probe individually from a UA residential IP before deciding per-source.

## App-only / no scrapeable web catalogue

The site exists but products are not browsable on the web. Skip — no amount of scraping helps.

- **happyfresh.id** (ID) — landing page is "Download the app" only.
- **astronauts.id / astro** (ID) — geo-fenced to ID residential IPs AND mostly app-driven.
- **shop.com.mm** (MM, Daraz Myanmar) — login required to see prices + MM geofence.
- **Kmanek Supermarket / Leader Hypermart** (TL) — Facebook-only, no public e-commerce site.

## Brochure-only WordPress / no online store

WordPress site for an offline retailer — pages exist, products do not. No /shop/, no /product/, no PDPs. See [[caring2u_kimia_brochure_only]] in engram.

- **caring2u.com** (MY) — pharmacy chain WP brochure; flagged on v2 retry list, no online store.
- **kimiafarmaapotek.co.id** (ID) — same shape.

## Aggregator / no canonical per-product URL

Site has products but each one is a modal within a shop page, not a canonical `/product/{id}` URL. Doesn't fit the price-spider model unless reworked to per-shop scraping.

- **foodpanda.la** (also caught by PerimeterX above)
- **happyfresh.id** (aggregator + app-only)

## No products on the site (corporate marketing portal)

Domain exists and renders but has no e-commerce — corporate/brand portal.

- **pxmart.com.tw** (TW) — corporate Next.js portal. Links go to /about-us, /bulletin, /esg. No catalog.
- **brianbell.com.pg** (PNG) — corporate portal. `/product-category/appliances` 404s. `homecentres.brianbell.com.pg/shop/` redirects to "/" with no e-commerce markup. B2C division has no public web storefront.
- **e-mart.mn** (MN) — corporate marketing site for eMart. Actual store is at **emartmall.mn** (SPA shell — see above).

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
