# Probe Patterns

Three probe steps in order: **curl → Playwright dump → API sniff**. Stop as soon as one tier succeeds. Each step has a specific decision rule for whether to escalate or skip.

## Setup

All probes use the same browser-style User-Agent that `src/prices/price_scraping/settings.py` sets — keep it consistent so what the probe sees matches what the spider will see:

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
```

The Playwright probe runs under the project's `poetry` environment (which already has `scrapy-playwright` and `playwright` installed). No extra setup required.

## Step 1 — curl probe (Tier 1A check)

Confirms whether the site server-renders product content. If yes, you're done — use Pattern A from `spider_templates.md`.

```bash
# Fetch a category/listing page
LISTING_URL="https://example.com/category/foo"
curl -sL -A "$UA" "$LISTING_URL" -o /tmp/probe_<key>_listing.html -w "HTTP %{http_code}  %{size_download} bytes\n"

# Decision: does the response have product links + visible price text?
grep -oE 'href="/product/[^"]+|/products/[^"]+|/p/[^"]+|/\d+\.html' /tmp/probe_<key>_listing.html | head -5
grep -oE '[$£€¥₹₫₮][\s]?[0-9.,]+|[0-9.,]+[\s]?(USD|VND|MMK|BND|FJD|MNT|KRW|TWD|IDR|LAK)' /tmp/probe_<key>_listing.html | head -5

# If both grep return matches, fetch a PDP to confirm selectors
PDP_URL="<one of the product URLs found above>"
curl -sL -A "$UA" "$PDP_URL" -o /tmp/probe_<key>_pdp.html -w "HTTP %{http_code}  %{size_download} bytes\n"

# Identify selectors:
grep -oE '<h1[^>]*>[^<]+</h1>' /tmp/probe_<key>_pdp.html | head -3                 # product_name candidates
grep -oE '<meta property="og:[^>]+>' /tmp/probe_<key>_pdp.html | head -5            # og: fallbacks
grep -oE '(data-test|data-testid|itemprop)="[a-z_-]+"' /tmp/probe_<key>_pdp.html | sort -u | head -15  # high-quality semantic attrs
grep -oE 'class="[^"]*[Pp]rice[^"]*"' /tmp/probe_<key>_pdp.html | sort -u | head -8 # price class candidates
```

**Decision rule**: if the curl returns 200, the listing has direct `/product/` (or similar) links AND a PDP fetch returns HTML where you can find both the product name in an h1/og:title and the price in a class containing "price" or a `data-price` attribute → **Tier 1A**. Stop here.

If curl returns 403/429/connection-reset, escalate to Playwright (Step 2). If curl returns 200 but PDP is missing the product fields (or h1/og:title is the site name, not the product name) → escalate to Playwright.

## Step 2 — Playwright dump (Tier 2 check)

For sites where curl returns content but the body is a SPA skeleton, or curl returns 403/429 and you want to confirm whether a real browser session can reach the content.

Write a one-shot probe script with the URLs you want to dump. Pattern (mirror this in `/tmp/probe_tier2.py`):

```python
"""Probe SPA sites with Playwright. Dumps rendered listing + first matching PDP."""

import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# (site_key, listing_url, product_url_regex_for_first_pdp)
SITES = [
    ("<key>", "<listing-url>", r"<pdp-href-regex>"),
]


async def probe(browser, key, url, pdp_pat):
    page = await browser.new_page(
        user_agent=UA, viewport={"width": 1280, "height": 900}, locale="en-US"
    )
    out = {"key": key}
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        out["status"] = resp.status if resp else None
        await page.wait_for_timeout(7000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(2500)
        html = await page.content()
        Path(f"/tmp/probe_{key}_listing.html").write_text(html, encoding="utf-8")
        out["listing_bytes"] = len(html)

        anchors = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        pdp_re = re.compile(pdp_pat)
        candidates = [a for a in anchors if pdp_re.search(a)]
        if candidates:
            await page.goto(candidates[0], wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(6000)
            Path(f"/tmp/probe_{key}_pdp.html").write_text(
                await page.content(), encoding="utf-8"
            )
            out["pdp_url"] = candidates[0]
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        await page.close()
    return out


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        for key, url, pat in SITES:
            r = await probe(browser, key, url, pat)
            print(
                f"{r['key']:18s} listing={r.get('status', '-')}/{r.get('listing_bytes', 0):>7} "
                f"pdp_url={r.get('pdp_url', '-')}  err={r.get('error') or '-'}"
            )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

Run with `poetry run python /tmp/probe_tier2.py`.

Then grep the dumped HTML the same way as Step 1.

**Decision rule for Tier 2**: rendered listing yields ≥5 product card matches AND a PDP fetch shows product name + price in the rendered HTML → **Tier 2** (use Pattern B in `spider_templates.md`).

**Tier 2 failures and what to do**:

- `ERR_CONNECTION_RESET` / Playwright `goto` raises → CDN bot block at TCP layer. The real spider will also fail. **Skip this site.** Note it in `known_blockers.md`.
- Listing renders but `<a href="/product/...">` links are absent (only category links) → site uses lazy-loaded product cards via internal API. Skip to Step 3 (API sniff).
- PDP rendered but `<h1>`, `og:*`, and price classes are all missing → site uses very late hydration or atomic CSS. Either increase wait time to 10–12s and re-probe, or skip.

## Step 3 — API sniff (Tier 1B check)

For sites where Playwright works but the rendered HTML uses atomic/dynamic CSS that's hard to select reliably, OR where you want a cleaner data shape. Captures every JSON-like response while the page loads, then you test the most promising endpoints with curl to see if they work standalone.

```python
"""Sniff internal API calls on SPA listings via Playwright network capture."""

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SITES = [
    ("<key>", "<listing-url>"),
]

API_HINTS = re.compile(r"/(api|v\d|graphql|search|product|catalog|listing|disco|menu|item|shop)/", re.I)
SKIP_HINTS = re.compile(r"\.(js|css|png|jpg|jpeg|webp|svg|gif|woff|woff2|ttf|ico|mp4)(\?|$)", re.I)


async def sniff(browser, key, url):
    page = await browser.new_page(
        user_agent=UA, viewport={"width": 1280, "height": 900}, locale="en-US"
    )
    apis: list = []

    async def on_response(resp):
        u = resp.url
        if SKIP_HINTS.search(u):
            return
        ct = (resp.headers.get("content-type") or "").lower()
        if "json" not in ct and not API_HINTS.search(u):
            return
        try:
            body = await resp.body()
            size = len(body)
        except Exception:
            size = 0
        apis.append({"url": u, "method": resp.request.method, "status": resp.status,
                     "ct": ct.split(";")[0], "size": size})

    page.on("response", on_response)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(8000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(3000)
    except Exception as e:
        apis.append({"error": str(e)[:100]})
    finally:
        await page.close()

    Path(f"/tmp/sniff_{key}.json").write_text(json.dumps(apis, indent=2))
    print(f"\n=== {key} ({len(apis)} responses) ===")
    promising = sorted(
        [a for a in apis if "error" not in a and a.get("status") == 200 and a.get("size", 0) > 5000],
        key=lambda x: -x["size"],
    )[:6]
    for a in promising:
        print(f"  {a['status']} {a['size']:>8,}  {a['ct'][:18]:18s}  {a['url']}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        for key, url in SITES:
            await sniff(browser, key, url)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

Then for each promising endpoint, test with curl + Origin/Referer:

```bash
curl -s -A "$UA" -H "Accept: application/json" \
  -H "Origin: https://<site-origin>" \
  -H "Referer: https://<site-origin>/" \
  "<full-api-url>" \
  -o /tmp/api_<key>.json -w "HTTP %{http_code}  %{size_download} bytes\n"

# Inspect the schema:
python3 -c "
import json
d = json.load(open('/tmp/api_<key>.json'))
print('top keys:', list(d.keys()) if isinstance(d, dict) else type(d).__name__)
if isinstance(d, dict):
    for k, v in d.items():
        if isinstance(v, list) and v:
            print(f'list-key {k}: {len(v)} items, sample keys = {list(v[0].keys())[:12]}')
            break
"
```

**Decision rule for Tier 1B**:

- curl returns 200 + structured JSON with product fields → **Tier 1B** (use Pattern C in `spider_templates.md`)
- curl returns 401/403 → API needs an auth token. Check whether there's an init endpoint we can capture, but in practice this rarely pays off — abandon and try Tier 2 instead.
- curl returns 429 → API has dynamic rate-limit or anti-bot key. If headers in the captured request include `x-security-key` / `x-csrf-token` / similar custom headers with non-trivial values, the key is generated client-side by JS and reverse-engineering it isn't worth the effort. **Skip.**
- curl returns the response body but it requires a session cookie — try warming up with a curl to the homepage first, but if it still 429s, skip.

If the curl works, also capture the request headers from Playwright to see if any custom headers are needed beyond Origin/Referer:

```python
async def on_request(req):
    if "<api-path-fragment>" in req.url:
        print(req.method, req.url, dict(req.headers))
page.on("request", on_request)
```

## Cleanup between probes

Playwright leaves chromium processes alive on macOS more often than you'd expect, especially after Ctrl-C. Before each new probe run:

```bash
pkill -9 -f "chrome-headless" 2>/dev/null
pkill -9 -f "scrapy" 2>/dev/null
pkill -9 -f "prices collect" 2>/dev/null
sleep 1
```

## Quick sanity check for skipped sites

If the user later asks "why did you skip site X?", reproduce the failure cheaply:

```bash
curl -sL -A "$UA" "<url>" -o /dev/null -w "HTTP %{http_code}\n"
# 403 = bot wall, 200 + tiny size = SPA shell, ERR_CONNECTION_RESET = TCP-layer block
```

This is the same diagnostic the skill ran — running it again confirms the site state hasn't changed since the original probe.
