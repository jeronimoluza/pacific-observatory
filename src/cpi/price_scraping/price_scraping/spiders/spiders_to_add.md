# List of spiders to add

26 spiders were attempted. **13 are confirmed working.** 13 were blocked by anti-bot and removed.

## Session Results Summary

**13 working spiders** across 9 countries, using 5 different architectures:
- 5 CrawlSpider (server-rendered HTML)
- 3 GraphQL API (Magento PWA)
- 3 Playwright (JS rendering)
- 1 REST API
- 1 CrawlSpider + embedded JSON regex

---

## China
- [x] Jianke https://www.jianke.com/ → `jianke.py` — **WORKING** (CrawlSpider, `div.product-name h1` name, `dl.bigPrice em` price, `div.crumb_p a` breadcrumbs)
- [x] 111 https://m.111.com.cn/ → `pharmacy_111.py` — **WORKING** (CrawlSpider, `.productName` name, `span.price` price)

## Hong Kong
- [x] Mannings https://www.mannings.com.hk/en → `mannings.py` — **WORKING** (GraphQL API, Magento PWA, 50 products/page across 7 categories)

## Mongolia
- [x] CityPharm https://citypharm.mn/ → `citypharm.py` — **WORKING** (CrawlSpider, Odoo platform, `itemprop` selectors)

## Taiwan
- [x] Cosmed https://shop.cosmed.com.tw/ → `cosmed.py` — **WORKING** (CrawlSpider + JSON regex, Angular SPA with embedded JSON data containing "Title"/"Price"/"CategoryName")

## Indonesia
- [x] K24Klik https://www.k24klik.com/ → `k24klik.py` — **WORKING** (Playwright, `li.product` cards, `img[alt]` names, Rp regex prices. Root cause of initial failure: product cards are `<li>` not `<div>`)

## Malaysia
- [x] Guardian (MY) https://guardian.com.my/ → `guardian_my.py` — **WORKING** (GraphQL API, Magento PWA, 9192 total products across 8 categories)
- [x] Doctor On Call https://www.doctoroncall.com.my/ → `doctor_oncall.py` — **WORKING** (Playwright, `section.product` cards, `h3 a` names, RM regex prices. Root cause of initial failure: product cards are `<section>` not `<li>` or `<div>`)

## Philippines
- [x] South Star Drug https://southstardrug.com.ph/ → `south_star_drug.py` — **WORKING** (CrawlSpider, Shopify platform, `h1.product__title` name)

## Singapore
- [x] Guardian (SG) https://guardian.com.sg/ → `guardian_sg.py` — **WORKING** (GraphQL API, Magento PWA, 50 products/page across 6 categories)
- [x] FairPrice https://www.fairprice.com.sg/ → `fairprice.py` — **WORKING** (Playwright, `.product-container` cards, `img[alt]` names, dollar regex prices)

## Thailand
- [x] Boots https://store.boots.co.th/ → `boots_th.py` — **WORKING** (REST API at `/api/v1/products/web`, 4286 total products, no auth needed)
- [x] Exta https://www.exta.co.th/ → `exta.py` — **WORKING** (CrawlSpider, WooCommerce, `h1.product_title` name, `woocommerce-Price-amount bdi` price)

---

## Removed (blocked by anti-bot — spider files deleted)

| Site | Country | Blocker |
|---|---|---|
| Chemist Warehouse | Australia | HTTP 403, Cloudflare |
| Watsons HK | Hong Kong | HTTP 000, connection refused |
| Watsons TW | Taiwan | HTTP 000, connection refused |
| Watsons ID | Indonesia | HTTP 000, connection refused |
| Watsons MY | Malaysia | HTTP 000, connection refused |
| Watsons PH | Philippines | HTTP 000, connection refused |
| Watsons SG | Singapore | HTTP 000, connection refused |
| Watsons TH | Thailand | HTTP 000, connection refused |
| Matsumoto Kiyoshi | Japan | Playwright timeout, heavy anti-bot |
| Olive Young | South Korea | Playwright blocked, anti-bot |
| Emonos | Mongolia | Next.js SPA, no API, fully client-rendered |
| Fascino | Thailand | Vue Storefront SPA, API requires auth tokens |
| Pharmacity | Vietnam | API auth required, product listing 404 |

To unblock these in the future: residential proxies, geo-specific IPs, or reverse-engineering auth tokens from browser sessions.
