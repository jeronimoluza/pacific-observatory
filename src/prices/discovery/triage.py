"""First look at `discovered` candidates: is there a price list worth a spider?

Plain requests only, under an honest user-agent: robots.txt obeyed, 1 request
per second per host, at most 3 pages per candidate (the landing page the search
found, the home page, and one shop-looking link). A site that refuses a plain
request is `blocked_plain` -- scaffolding may retry it with curl_cffi or
Playwright -- and a CAPTCHA or login wall is `blocked_hard`. Nothing here solves
a challenge or disguises the client.

Verdicts:
  verified       local-currency prices: a JSON-LD Product in the local
                 currency, or >= 5 local prices on one page
  ambiguous      some signal, not enough: 1-4 local prices, prices in three or
                 more currencies (converters, indexes), a shop platform
                 with no prices seen, prices in another currency, PDF lists on
                 a tariff/bulletin site. The daily Claude session reads these.
  rejected       news site, prices only in a foreign currency, nothing priced,
                 unreachable, robots.txt says no
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import yaml

from prices.discovery.search import BLOCKLIST

USER_AGENT = (
    "PacificObservatoryPriceDiscovery/0.1 (+https://github.com/jeronimoluza/pacific-observatory)"
)
MAX_PAGES = 3
MAX_BYTES = 2_000_000
TIMEOUT = 20
MIN_LOCAL_PRICES = 5

# Written forms of a currency beyond its ISO code. The bank's currency_words
# are added per country, so this only needs symbols a bank would not spell out.
SYMBOLS = {
    "NGN": ("₦",),
    "XAF": ("FCFA", "F CFA", "F.CFA", "CFA"),
    "XOF": ("FCFA", "F CFA", "F.CFA", "CFA"),
    "USD": ("US$", "$"),
    "EUR": ("€",),
    "GBP": ("£",),
    "GHS": ("GH₵", "GH¢", "₵"),
    "KES": ("KSh", "Ksh"),
    "ZAR": ("R",),
    "INR": ("₹", "Rs"),
}
_NUM = r"\d{1,3}(?:[ .,  ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_CODE_PRICE = re.compile(rf"\b([A-Z]{{3}})\s?(?:{_NUM})|(?:{_NUM})\s?([A-Z]{{3}})\b")
_ANY_PRICE = re.compile(
    rf"(?:[$€£₦₹]|\b[A-Z]{{3}}\b)\s?(?:{_NUM})|(?:{_NUM})\s?(?:[$€£₦₹]|\b[A-Z]{{3}}\b)"
)

_PLATFORMS = (
    ("shopify", ("cdn.shopify.com", "Shopify.theme")),
    ("woocommerce", ("woocommerce", "wc-blocks")),
    ("magento", ("Magento_", "mage/cookies", "/static/version")),
    ("prestashop", ("prestashop", "PrestaShop")),
    ("opencart", ("route=product/", "catalog/view/theme")),
    ("wix", ("wixstatic.com", "X-Wix")),
    ("odoo", ("/web/assets/", "odoo")),
    ("nopcommerce", ("nopCommerce",)),
)
_SHOP_LINK = re.compile(
    r"/(shop|store|products?|produits?|boutique|tienda|productos?|catalog(ue)?|categor(y|ies|ie|ia)|collections?|price|prix|precios?|tarifs?)\b",
    re.IGNORECASE,
)
_CHALLENGE = ("cf-chl", "challenge-platform", "Just a moment", "Attention Required")
_CAPTCHA = ("g-recaptcha", "h-captcha", "hcaptcha", "captcha")
_LOGIN_PATH = re.compile(
    r"/(login|signin|sign-in|account/login|connexion|iniciar-sesion)\b", re.IGNORECASE
)
_JSONLD = re.compile(
    r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL
)
_HREF = re.compile(r"""href=["']([^"'#]+)["']""", re.IGNORECASE)


def _iso_codes() -> frozenset[str]:
    from prices.discovery.bank import COUNTRIES_YAML

    meta = yaml.safe_load(COUNTRIES_YAML.read_text(encoding="utf-8"))
    return frozenset(str(m["currency"]).upper() for m in meta.values() if m.get("currency"))


ISO_CODES = _iso_codes() | {"USD", "EUR", "GBP", "CNY", "JPY", "CHF"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_price_re(currency: str, words: list[str]) -> re.Pattern:
    tokens = sorted({currency, *SYMBOLS.get(currency, ()), *words}, key=len, reverse=True)
    tok = "|".join(re.escape(t) for t in tokens if t)
    # Letters on either side would make "CFA" match inside a word.
    tok = rf"(?<![A-Za-z])(?:{tok})(?![A-Za-z])"
    return re.compile(rf"{tok}\s?(?:{_NUM})|(?:{_NUM})\s?{tok}", re.IGNORECASE)


def _jsonld_nodes(html: str) -> list[dict]:
    nodes: list[dict] = []

    def walk(x) -> None:
        if isinstance(x, dict):
            nodes.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for blob in _JSONLD.findall(html):
        try:
            walk(json.loads(blob.strip()))
        except ValueError:
            continue
    return nodes


def _types(node: dict) -> set[str]:
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t} if isinstance(t, str) else set()


def analyse(html: str, local: re.Pattern, currency: str) -> dict:
    nodes = _jsonld_nodes(html)
    types = Counter(t for n in nodes for t in _types(n))
    jsonld_currencies = Counter(
        str(n["priceCurrency"]).upper() for n in nodes if n.get("priceCurrency")
    )
    local_hits = [m.group(0) for m in local.finditer(html) if re.search(r"[1-9]", m.group(0))]
    return {
        "products": types["Product"],
        "news": bool(
            types.keys() & {"NewsArticle", "ReportageNewsArticle", "NewsMediaOrganization"}
        ),
        "local_jsonld": jsonld_currencies[currency],
        "jsonld_currencies": jsonld_currencies,
        "local_prices": local_hits,
        "codes": {a or b for a, b in _CODE_PRICE.findall(html)} & ISO_CODES,
        "any_prices": len(_ANY_PRICE.findall(html)),
        "platform": next((p for p, marks in _PLATFORMS if any(m in html for m in marks)), None),
        "pdf_links": sum(
            1 for h in _HREF.findall(html) if h.lower().split("?")[0].endswith(".pdf")
        ),
    }


class _Host:
    """One site, fetched politely: robots.txt first, then >= 1 s between requests."""

    def __init__(self, base: str):
        self.base = base
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "*"})
        self.last = 0.0
        self.robots: RobotFileParser | None = None

    def get(self, url: str) -> requests.Response | None:
        wait = 1.0 - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True)
            body = b""
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) >= MAX_BYTES:
                    break
            r._content = body
            return r
        except requests.RequestException:
            return None
        finally:
            self.last = time.monotonic()

    def load_robots(self) -> bool:
        """False when the host does not answer at all."""
        r = self.get(urljoin(self.base, "/robots.txt"))
        if r is None:
            return False
        self.robots = RobotFileParser()
        if r.status_code in (401, 403):
            self.robots.disallow_all = True
        elif r.status_code >= 400:
            self.robots.allow_all = True
        else:
            self.robots.parse(r.text.splitlines())
        return True

    def allowed(self, url: str) -> bool:
        return self.robots is None or self.robots.can_fetch(USER_AGENT, url)


def _pick_host(cand: sqlite3.Row) -> _Host | None:
    """The first of the hit's host, the bare domain and www. that answers."""
    bases = []
    if cand["best_url"]:
        p = urlparse(cand["best_url"])
        bases.append(f"{p.scheme or 'https'}://{p.netloc}")
    bases += [
        f"https://{cand['domain']}",
        f"https://www.{cand['domain']}",
        f"http://{cand['domain']}",
    ]
    for base in dict.fromkeys(bases):
        host = _Host(base)
        if host.load_robots():
            return host
    return None


def triage_one(cand: sqlite3.Row, currency: str, local: re.Pattern) -> dict:
    out = {"robots_ok": "unknown", "platform": None, "n_items_est": None, "price_evidence": None}
    if cand["domain"] in BLOCKLIST:
        return {**out, "status": "rejected", "reason": "blocklisted domain, not fetched"}
    host = _pick_host(cand)
    if host is None:
        return {**out, "status": "rejected", "reason": "unreachable"}

    urls = [u for u in (cand["best_url"], host.base + "/") if u]
    urls = list(dict.fromkeys(urls))
    if not any(host.allowed(u) for u in urls):
        return {**out, "robots_ok": "no", "status": "rejected", "reason": "robots.txt disallows"}
    out["robots_ok"] = "yes"

    pages, codes, refused = [], [], []
    for url in urls:
        if not host.allowed(url):
            continue
        r = host.get(url)
        if r is None:
            codes.append("conn")
            continue
        codes.append(r.status_code)
        text = r.text
        if _LOGIN_PATH.search(urlparse(r.url).path) and not _LOGIN_PATH.search(urlparse(url).path):
            refused.append(("hard", "redirected to a login page"))
        elif r.status_code != 200:
            if any(m in text for m in _CHALLENGE):
                refused.append(("plain", f"HTTP {r.status_code} browser challenge"))
            elif r.status_code in (401, 403, 429, 503) and any(m in text for m in _CAPTCHA):
                refused.append(("hard", f"HTTP {r.status_code} CAPTCHA"))
            elif r.status_code in (401, 403, 429, 503):
                refused.append(("plain", f"HTTP {r.status_code}"))
        elif len(text) < 15000 and any(m in text.lower() for m in _CAPTCHA):
            refused.append(("hard", "CAPTCHA page"))
        else:
            pages.append((r.url, text))
    # Third page: one shop-looking link from what we have, same host only.
    if pages and len(urls) < MAX_PAGES:
        netloc = urlparse(host.base).netloc
        seen = {u for u, _ in pages} | set(urls)
        for _, text in pages:
            link = next(
                (
                    u
                    for u in (urljoin(host.base + "/", h) for h in _HREF.findall(text))
                    if urlparse(u).netloc == netloc
                    and _SHOP_LINK.search(urlparse(u).path)
                    and u not in seen
                ),
                None,
            )
            if link and host.allowed(link):
                r = host.get(link)
                codes.append(r.status_code if r is not None else "conn")
                if r is not None and r.status_code == 200:
                    pages.append((r.url, r.text))
                break

    if not pages:
        if refused:
            kind, why = next((x for x in refused if x[0] == "hard"), refused[0])
            return {**out, "status": f"blocked_{kind}", "reason": why}
        return {**out, "status": "rejected", "reason": f"no page served ({codes})"}

    found = [(url, analyse(text, local, currency)) for url, text in pages]
    best_url, best = max(
        found, key=lambda f: (f[1]["local_jsonld"], len(f[1]["local_prices"]), f[1]["products"])
    )
    platform = next((a["platform"] for _, a in found if a["platform"]), None)
    products = max(a["products"] for _, a in found)
    n_local = len(best["local_prices"])
    pdfs = sum(a["pdf_links"] for _, a in found)
    foreign = Counter()
    for _, a in found:
        foreign.update({c: n for c, n in a["jsonld_currencies"].items() if c != currency})
    out.update(
        platform=platform,
        best_url=best_url,
        n_items_est=max(products, n_local) or None,
        price_evidence=" | ".join(dict.fromkeys(best["local_prices"]))[:300] or None,
        currency_seen=(
            currency
            if n_local or best["local_jsonld"]
            else (foreign.most_common(1)[0][0] if foreign else None)
        ),
    )
    news = any(a["news"] for _, a in found) and not products
    if news:
        return {**out, "status": "rejected", "reason": "news site"}
    # A shop prices in one currency. Three or more next to numbers is a
    # converter, cost-of-living or fuel-index page (themoneyconverter,
    # goldpricez, oilpricez on the CAR dry run): a person decides.
    others = best["codes"] - {currency}
    if len(others) >= 2 and not best["local_jsonld"]:
        return {
            **out,
            "status": "ambiguous",
            "reason": f"prices in {len(others) + 1} currencies; converter or aggregator?",
        }
    if best["local_jsonld"] or n_local >= MIN_LOCAL_PRICES:
        how = "JSON-LD Product" if best["local_jsonld"] else f"{n_local} local prices on one page"
        return {**out, "status": "verified", "reason": f"{how} ({currency})"}
    if foreign and not n_local:
        return {
            **out,
            "status": "rejected",
            "reason": f"prices in {', '.join(foreign)}, not {currency}",
        }
    if n_local:
        return {**out, "status": "ambiguous", "reason": f"only {n_local} local prices seen"}
    if platform or products:
        return {
            **out,
            "status": "ambiguous",
            "reason": f"{platform or 'JSON-LD Product'} with no local price seen",
        }
    if pdfs and cand["kind"] in ("tariff", "bulletin"):
        return {
            **out,
            "status": "ambiguous",
            "reason": f"{pdfs} PDF links on a {cand['kind']} site",
        }
    if max(a["any_prices"] for _, a in found) >= MIN_LOCAL_PRICES:
        return {**out, "status": "ambiguous", "reason": "prices seen, currency not recognised"}
    return {**out, "status": "rejected", "reason": "no prices seen"}


def country_currency(con: sqlite3.Connection, country: str) -> tuple[str, list[str]]:
    from prices.discovery.bank import BANKS_DIR, country_meta, load_vocab

    row = con.execute("SELECT currency FROM countries WHERE country = ?", (country,)).fetchone()
    currency = (row and row["currency"]) or country_meta(country)["currency"]
    words = (
        load_vocab(country).get("currency_words", [])
        if (BANKS_DIR / f"{country}.yaml").exists()
        else []
    )
    return currency.upper(), words


def run_triage(
    con: sqlite3.Connection,
    country: str | None = None,
    limit: int | None = None,
    workers: int = 6,
    echo=print,
) -> Counter:
    sql = "SELECT * FROM candidates WHERE status = 'discovered'"
    params: list = []
    if country:
        sql += " AND country = ?"
        params.append(country)
    sql += " ORDER BY country, domain"
    if limit:
        sql += f" LIMIT {int(limit)}"
    cands = con.execute(sql, params).fetchall()
    money = {c: country_currency(con, c) for c in {r["country"] for r in cands}}
    patterns = {c: local_price_re(cur, words) for c, (cur, words) in money.items()}
    echo(f"triaging {len(cands)} candidates")

    def one(cand):
        return cand, triage_one(cand, money[cand["country"]][0], patterns[cand["country"]])

    tally: Counter = Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for cand, v in pool.map(one, cands):
            tally[v["status"]] += 1
            with con:
                con.execute(
                    """UPDATE candidates SET status = ?, reason = ?, robots_ok = ?, platform = ?,
                           n_items_est = ?, price_evidence = ?, currency_seen = ?,
                           best_url = COALESCE(?, best_url), updated_at = ?
                       WHERE country = ? AND domain = ? AND status = 'discovered'""",
                    (
                        v["status"],
                        v["reason"],
                        v["robots_ok"],
                        v.get("platform"),
                        v.get("n_items_est"),
                        v.get("price_evidence"),
                        v.get("currency_seen"),
                        v.get("best_url"),
                        _now(),
                        cand["country"],
                        cand["domain"],
                    ),
                )
            echo(
                f"  {v['status']:<13} {cand['country'][:20]:<20} {cand['domain']:<36} {v['reason']}"
            )
    return tally
