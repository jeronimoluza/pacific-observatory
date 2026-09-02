"""
TriniCart (Trinidad and Tobago) — https://trinicart.pro/.

"Trinidad's premium digital supermarket" (site author metadata: "Maraval
Market" — Maraval is a residential district of Port of Spain). Real
grocery SKUs priced in TT$: Julie Mango, Christophene, Scotch Bonnet
Peppers, Bermudez Crix, Chief seasonings, Caribbean Dreams Sorrel Drink —
all Trinidad-specific produce/brands, not a diaspora storefront.

The React SPA (Vite build, gpt-engineer scaffold) has no server-rendered
HTML and no conventional REST/GraphQL product API. The catalogue lives in
two places, both public and unauthenticated:

1. A hardcoded seed catalogue baked directly into the built JS bundle as
   two literal arrays: a produce/weight-based array (first element
   `{id:"p1",slug:"ripe-bananas",...}`) and a set of packaged-goods object
   constructor calls of the shape `<fn>({name:"...",departmentId:...,
   price:...})` where `<fn>` is a short minifier-assigned identifier (was
   `ee` at probe time 2026-08-31, 66 objects). Both are parsed out of the
   bundle text with a balanced-brace scanner + a light JS-literal ->
   JSON normalizer (unquoted keys, `!0`/`!1` booleans, trailing commas,
   `fn("string")` wrapper calls collapsed to the string).
2. Store-owner edits/additions layered on top, in a public Supabase
   Postgres instance (project ref discovered as a literal
   `https://<ref>.supabase.co` + anon JWT in the bundle) via PostgREST:
   `GET /rest/v1/admin_content?key=eq.maraval-catalog-v1&select=value`.
   The `value.custom` array holds additional products (e.g. Julie Mango,
   Christophene) not present in the seed bundle; `value.removedSeedIds`
   lists seed ids the owner deleted (empty at probe time).

Smoke-verified 2026-08-31: 66 seed packaged goods + 15 seed produce items
+ 48 supabase custom items = 129 total, 129 distinct ids, zero zero-price
rows, zero blank names, price range TT$5-180. ~87% of rows (112/129) sit
under food/beverage departments (Fresh Produce, Meat & Seafood, Dairy &
Eggs, Bakery, Pantry, Frozen, Beverages, Snacks) vs Household/Health &
Beauty for the rest.

FRAGILITY: the seed-bundle parse depends on the current Vite build's
minified output shape (a short identifier immediately followed by
`({name:"..."`, and the anchor string `{id:"p1",slug:"` for the produce
array). A future TriniCart redeploy could rename/reshape either without
changing the catalogue itself. Both stages fail soft (log + skip, no
exception) so a shape change silently degrades to the Supabase `custom`
slice (still real, still TTD, still ~48 rows) rather than crashing the
spider or the run.

No server-rendered product URLs exist (client-side routed SPA), so each
row is given a synthetic `https://trinicart.pro/product/<slug-or-id>#<src>`
url — required so the DuplicationPipeline's url-dedup does not collapse
these into a single row (see apua_rates_ag.py precedent).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://trinicart.pro"
SUPABASE_URL = (
    "https://lmrfzrshpwqxaeorfecv.supabase.co/rest/v1/admin_content"
    "?key=eq.maraval-catalog-v1&select=value"
)
SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6"
    "ImxtcmZ6cnNocHdxeGFlb3JmZWN2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY1ODI5"
    "NDAsImV4cCI6MjA5MjE1ODk0MH0.U7rhI6bJ6IFU9VJVPs1AI88KZupVrjDLzDk4Cw4Dne4"
)

_BUNDLE_RE = re.compile(r"/assets/index-[\w.-]+\.js")
_PACKAGED_CALL_RE = re.compile(r'\b[a-zA-Z_$]{1,4}\(\{name:"')
_PRODUCE_ANCHOR = '{id:"p1",slug:"'

_DEPT_NAMES = {
    "d1": "Fresh Produce",
    "d2": "Meat & Seafood",
    "d3": "Dairy & Eggs",
    "d4": "Bakery",
    "d5": "Pantry",
    "d6": "Frozen",
    "d7": "Beverages",
    "d8": "Household",
    "d9": "Baby",
    "d10": "Health & Beauty",
    "d11": "Snacks",
}

_UNQUOTED_KEY_RE = re.compile(r"([{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*:")
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _extract_balanced(text, start, open_c="{", close_c="}"):
    """Return the balanced-bracket substring of `text` starting at index
    `start` (which must point at `open_c`), respecting quoted strings."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                i += 1
        i += 1
    return None


def _strip_wrapper_calls(text):
    """Collapse `fn("string")` wrapper calls (e.g. image-URL helpers) down
    to the bare string literal, so the result is valid JSON once keys are
    quoted."""
    out = []
    i, n = 0, len(text)
    call_re = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\(")
    while i < n:
        m = call_re.match(text, i)
        if m and m.end() < n and text[m.end()] == '"':
            j = m.end()  # index of the opening quote
            k = j + 1
            while k < n and text[k] != '"':
                if text[k] == "\\":
                    k += 1
                k += 1
            if k + 1 < n and text[k + 1] == ")":
                out.append(text[j : k + 1])  # keep both quotes
                i = k + 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _parse_js_object(raw):
    """Best-effort JS-object-literal -> dict, for the minified seed
    catalogue snippets. Raises on failure; callers must catch."""
    t = _strip_wrapper_calls(raw)
    t = _UNQUOTED_KEY_RE.sub(r'\1"\2":', t)
    t = t.replace("!0", "true").replace("!1", "false")
    t = _TRAILING_COMMA_RE.sub(r"\1", t)
    return json.loads(t)


def _split_top_level_objects(array_text):
    """Split a `[{...},{...}]` array body into its top-level `{...}`
    member strings."""
    objs = []
    depth = 0
    cur_start = None
    i, n = 0, len(array_text)
    while i < n:
        c = array_text[i]
        if c == '"':
            i += 1
            while i < n and array_text[i] != '"':
                if array_text[i] == "\\":
                    i += 1
                i += 1
        elif c == "{":
            if depth == 0:
                cur_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and cur_start is not None:
                objs.append(array_text[cur_start : i + 1])
        i += 1
    return objs


def _slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "item"


class TrinicartTtSpider(scrapy.Spider):
    name = "trinicart_tt"
    allowed_domains = ["trinicart.pro", "supabase.co"]
    currency = "TTD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_home, errback=self.errback
        )

    def parse_home(self, response):
        m = _BUNDLE_RE.search(response.text)
        if not m:
            logger.error(f"{self.name}: no Vite bundle path found on homepage")
            return
        bundle_url = f"{BASE_URL}{m.group(0)}"
        yield scrapy.Request(
            bundle_url, callback=self.parse_bundle, errback=self.errback
        )

    def parse_bundle(self, response):
        seed_items = self._parse_seed_packaged(response.text)
        seed_items += self._parse_seed_produce(response.text)
        if seed_items:
            logger.info(f"{self.name}: parsed {len(seed_items)} seed catalogue items")
        else:
            # Observed live on 2026-08-31: the bundle fetched 200 with its
            # anchors intact, yet every object failed to parse, and the run
            # shipped only the ~48 Supabase rows. That is a ~63% silent
            # shortfall, so it must not degrade quietly at INFO.
            logger.warning(
                f"{self.name}: parsed 0 seed catalogue items from the bundle. "
                "Only the Supabase custom slice will be emitted, which is "
                "roughly a third of the catalogue. If this persists, the Vite "
                "build has been reshaped and the parser needs updating."
            )
        yield scrapy.Request(
            SUPABASE_URL,
            callback=self.parse_custom,
            errback=self.errback,
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "authorization": f"Bearer {SUPABASE_ANON_KEY}",
            },
            meta={"seed_items": seed_items},
        )

    def _parse_seed_packaged(self, text):
        items = []
        for m in _PACKAGED_CALL_RE.finditer(text):
            obj_start = text.index("{", m.start(), m.end())
            raw = _extract_balanced(text, obj_start)
            if not raw:
                continue
            try:
                obj = _parse_js_object(raw)
            except Exception as exc:
                logger.debug(f"{self.name}: packaged parse failed: {exc}")
                continue
            if "departmentId" not in obj or "price" not in obj or not obj.get("name"):
                continue
            items.append(("seed", obj))
        return items

    def _parse_seed_produce(self, text):
        anchor = text.find(_PRODUCE_ANCHOR)
        if anchor == -1:
            logger.warning(f"{self.name}: produce-array anchor not found in bundle")
            return []
        bracket = text.rfind("[", 0, anchor)
        if bracket == -1:
            logger.warning(f"{self.name}: no '[' preceding produce anchor")
            return []
        arr_text = _extract_balanced(text, bracket, "[", "]")
        if not arr_text:
            logger.warning(f"{self.name}: produce array not balanced")
            return []
        items = []
        for raw in _split_top_level_objects(arr_text):
            try:
                obj = _parse_js_object(raw)
            except Exception as exc:
                logger.debug(f"{self.name}: produce parse failed: {exc}")
                continue
            if not obj.get("name") or "price" not in obj:
                continue
            items.append(("seed", obj))
        return items

    def parse_custom(self, response):
        seed_items = response.meta["seed_items"]
        custom_items = []
        removed = set()
        try:
            rows = response.json()
            value = rows[0]["value"] if rows else {}
            removed = set(value.get("removedSeedIds") or [])
            for obj in value.get("custom") or []:
                if obj.get("id") in removed or not obj.get("name"):
                    continue
                custom_items.append(("custom", obj))
        except Exception as exc:
            logger.error(f"{self.name}: supabase custom-catalogue parse failed: {exc}")

        if removed:
            seed_items = [
                (src, obj) for src, obj in seed_items if obj.get("id") not in removed
            ]

        now = datetime.now(timezone.utc).isoformat()
        seen_ids = set()
        count = 0
        for src, obj in seed_items + custom_items:
            price = obj.get("price")
            if price is None:
                continue
            name = str(obj.get("name", ""))[:500]
            slug = obj.get("slug") or _slugify(name)
            pid = obj.get("id") or f"sp-{slug}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            dept = _DEPT_NAMES.get(obj.get("departmentId"), obj.get("departmentId"))
            stock = obj.get("stockStatus")
            available = stock != "out_of_stock"

            yield {
                "product_id": str(pid),
                "product_name": name,
                "category": dept or "",
                "price": str(price),
                "currency": self.currency,
                "available": available,
                "url": f"{BASE_URL}/product/{slug}#{src}",
                "language": self.language,
                "scraped_at_utc": now,
            }
            count += 1

        logger.info(f"{self.name}: emitted {count} products")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
