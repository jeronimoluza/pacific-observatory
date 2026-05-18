# Known Blockers

Sites we've already classified as unscrapeable with our current stack (no proxy / no captcha solver). **Check this list before probing** — saves cycles.

Update this file whenever a probe confirms a new site is blocked, and include the exact failure mode so future runs can verify the state hasn't changed.

## Categories

### CDN bot-block (TCP-layer ERR_CONNECTION_RESET)

Real-browser requests from a non-target-country IP are dropped at the CDN. Headless Chromium does not bypass these — the connection is reset before any HTTP response. Would require a residential proxy in-country.

- **bachhoaxanh.com** (VN, Mobile World Group / Thế Giới Di Động) — `ERR_CONNECTION_RESET` on `/`, `/thuc-pham-tuoi-song`, `/rau-an-la`, `/robots.txt`. WebFetch returns "socket connection was closed unexpectedly".
- **nhathuocankhang.com** (VN, also Mobile World Group) — same `ERR_CONNECTION_RESET` signature. Both MWG sites share infrastructure, so a single proxy/bypass effort would unlock both.
- **villamarket.com** (TH) — `ERR_CONNECTION_RESET` on curl AND Playwright `goto`.

### Cloudflare / AWS WAF / Akamai bot manager (403 from any non-real-browser)

403 even with realistic UA + headers. Often serves a challenge page or interstitial. Headless Chromium without stealth + residential IP fails. Would require ScrapeOps, Bright Data, or similar paid proxy/solver.

- **woolworths.co.nz**, **newworld.co.nz**, **paknsave.co.nz**, **chemistwarehouse.co.nz** (NZ) — all on the Foodstuffs/Akamai stack. One bypass effort would unlock all four.
- **watsons.com.tw** (TW, AS Watson) — persistent 403.
- **blibli.com** (ID) — 403 on category + PDP. Professional anti-bot.
- **auction.co.kr** (KR, eBay Korea) — 403 on root and category.
- **coupang.com** (KR) — Cloudflare-style challenges plus per-storefront login soft-walls.
- **klikindomaret.com** + `ap-mc.klikindomaret.com` (ID) — AWS WAF (`awswaf.com` challenge token). Blocks both HTML site and API gateway.
- **shopping.coupang.com**, **lazada.*.<tld>**, **shopee.*.<tld>** — all marketplace platforms with Akamai bot manager. Only viable via official affiliate APIs.
- **tops.co.th**, **bigc.co.th**, **homepro.co.th**, **powerbuy.co.th** (TH) — Cloudflare 403 on curl AND Playwright. Big-3 TH supermarkets/electronics chains; appear to share a similar protection profile.
- **makro.co.th** (TH, Siam Makro) — Incapsula (Imperva) 403 on curl AND Playwright. Same skip class as MWG sites above.

### PerimeterX / dynamic anti-bot fingerprinting

WAF that issues per-session tokens via JS; bare clients see only collector beacons.

- **foodpanda.la** (LA) — `collector-pxljub4etb.cl6.px-cloud.net` collector visible; no business endpoint responses ever load.
- **foodpanda.\*** in general — assume PerimeterX is in front of every delivery-hero site.

### App-only / no scrapeable web catalogue

The site exists but products are not browsable on the web. Skip — no amount of scraping will help.

- **happyfresh.id** (ID) — landing page is "Download the app" only.
- **astronauts.id / astro** (ID) — geo-fenced to ID residential IPs AND mostly app-driven.
- **shop.com.mm** (MM, Daraz Myanmar) — login required to see prices + MM geofence.
- **Kmanek Supermarket / Leader Hypermart** (TL) — Facebook-only, no public e-commerce site.

### Aggregator / no per-product URLs

Site has products but each one is a modal within a shop page, not a canonical `/product/{id}` URL. Doesn't fit the price-spider model unless reworked to per-shop scraping.

- **foodpanda.la** (also caught by PerimeterX above)
- **happyfresh.id** (aggregator + app-only)

### No products on the site

The site exists and renders but has no e-commerce — typically a corporate / brick-and-mortar marketing portal.

- **pxmart.com.tw** (TW) — corporate Next.js portal. Links go to /about-us, /bulletin, /esg. No product catalog.
- **brianbell.com.pg** (PNG) — corporate portal. `/product-category/appliances` 404s. `homecentres.brianbell.com.pg/shop/` redirects to "/" with no e-commerce markup. The B2C division does not have a public web storefront.
- **e-mart.mn** (MN) — corporate marketing site for eMart. The actual store is at **emartmall.mn** (which is an SPA shell — see below).

### API has dynamic security key / JWT auth that requires reverse engineering

Bare curl returns 401/429 regardless of headers because a non-trivial token is required.

- **marketplace.com.mm** (MM) `/api/products/all` — requires dynamic `x-security-key` header (CryptoJS "Salted__" prefix, AES with client-side-derived key). Reverse-engineering not worth the effort. 429 without it.
- **sayurbox.com** `/graphql/v1` — requires `authorization: Bearer <JWT>` + 10+ custom `x-sbox-*` headers + per-session `deliveryConfigId` base64 blob in the GraphQL variables.
- **alfagift.id** `webcommerce-gw.alfagift.id/v2/products/category/{id}` — returns 401 without auth token; init flow not investigated.
- **emartmall.mn** (MN) — SPA shell that returns nothing useful to non-JS clients; needs a real Playwright probe to identify any API.

### Heavy lazy-load with no productive API (SPA but unscrapeable)

Site loads, renders skeleton cards, but never hydrates fully OR hides product data behind an API that itself requires the SPA's session state.

- **winmart.vn** *(the HTML front-end)* — products render via `product-card-skeleton` divs that don't hydrate within 8s Playwright wait. **NOTE**: winmart's *JSON API* at `api-crownx.winmart.vn/it/api/web/v3/item/category` works perfectly with no auth — see `src/prices/price_scraping/spiders/winmart.py`. Use Pattern C, not the HTML.
- **cargillsonline.com** (LK) — Angular SPA. After 12s wait + scroll, the dump contains `{{...}}` placeholder syntax (Angular templates) for product details and only category-level `/Product/<cat>` links — no `/ProductDetails/<sku>` URLs ever hydrate.
- **osudpotro.com** (BD) — listing URL `/category/buy-over-the-counter-medicine-online-in-dhaka` renders **disease cards** (`<a href="/disease/...">`) not product cards. Site's catalog organization is by-disease; need a different entry URL or direct PDP list to scrape products.

### Hashed-CSS-class SPAs (Next.js / styled-components with build-time hashes)

Selectors observable in a dump break on every site deploy because class names are content-hashed at build time. Selecting by structure (tag positions, attribute prefixes like `class*="ProductCard"`) is sometimes possible but fragile — defer unless the site is high priority.

- **truemeds.in** (IN) — re-tested 2026-05-18 with Playwright (networkidle + scroll): the listing page returned **0 `a[href^="/otc/"]` anchors** — the SPA does not hydrate product cards in headless Chromium at all (likely bot fingerprinting on top of the hashed-class issue). Even though the page was previously documented as having a usable anchor pattern, the cards never render. Stay deferred; requires real-browser stealth + likely a residential IN IP.

## How to use this list

Before probing, grep this file for the candidate's domain. If it's listed:

- For CDN/WAF/PerimeterX blockers: skip entirely. Optionally do a quick 1-call curl to confirm the wall is still in place (sometimes sites change), but don't invest more than 30 seconds.
- For "no products on the site" / "app-only" / "no per-product URLs": these are structural — the site fundamentally doesn't expose a product catalogue we can scrape. Skip permanently.
- For "API with dynamic auth": skip the API. Consider whether the HTML front-end might be Tier 2 (it usually isn't, because if the HTML were scrapeable the API wouldn't be the path of least resistance).
- For "Heavy lazy-load with no productive API": skip the HTML, but check if a different endpoint (e.g. winmart's `api-crownx.winmart.vn`) is reachable — those are the rare wins.

## How to add to this list

After a probe confirms a new site is unscrapeable, append it to the appropriate section with:

- The exact domain
- Country code in parentheses
- The owner/operator if known (helps you recognize shared infra — MWG sites all share an anti-bot stack)
- The specific failure signature (`ERR_CONNECTION_RESET`, `HTTP 403 + Cloudflare challenge`, `200 with skeleton-only body`, etc.) — this is what makes the entry verifiable later.

Be concise — one line per site is enough. The goal is to read this file in <30 seconds when starting a new country onboarding.

**When to add — the trigger condition.** The bar for adding to this list is *both* curl AND Playwright failing in the same way (e.g. both returning 403, or both `ERR_CONNECTION_RESET`). A site that 403s on curl but renders fine in Playwright is just Tier 2 — don't add it here. The point of this file is to short-circuit probing for sites that will block real-browser sessions too.

If Playwright returns a 200 but the body never hydrates, that's *not* the same as a bot block — it might be slow lazy-load. Try once with a 12s wait before adding to the "Heavy lazy-load" section.
