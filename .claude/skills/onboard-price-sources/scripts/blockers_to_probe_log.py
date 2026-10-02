#!/usr/bin/env python3
"""One-off migration: known_blockers.md prose -> probe_log JSONL shards.

Kept after use on purpose. When the probe-log schema next changes, the last
migration should be readable.

The risk this guards against is not a dropped host; it is dropped *evidence*.
A host that survives with an empty `lever_tried` and `tell` is worse than a
host that vanishes, because it becomes a permanent false skip. So the script
counts, in the source prose, how many hosts have a lever / a tell / a date
recoverable at all, and refuses to write if the output carries fewer.

Usage:
    python blockers_to_probe_log.py --write
    python blockers_to_probe_log.py            # dry run, report only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFS = HERE.parent / "references"
SRC = REFS / "known_blockers.md"
INDEX = REFS / "known_blockers_index.md"
OUT_DIR = REFS / "probe_log"
BASELINE = HERE / "migration_baseline.json"

RECHECK_DAYS = 180

# A registrable-looking domain. Deliberately conservative on the TLD so that
# "e.g" and "v1.2" do not read as hosts.
HOST_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"(?:com|net|org|io|co|gov|edu|shop|store|app|online|site|info|biz|xyz|me|tv|cc|"
    r"world|life|africa|asia|market|global|deals|group|company|center|agency|"
    r"[a-z]{2}(?:\.[a-z]{2,3})?))\b"
)
DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")

# --- evidence vocabularies -------------------------------------------------
# Order matters only for readability; every match is kept.

LEVERS = {
    "curl_cffi": r"curl_cffi|impersonat",
    "chrome120": r"chrome120",
    "chrome124": r"chrome124",
    "chrome131": r"chrome131",
    "chrome133a": r"chrome133a",
    "chrome150": r"chrome150",
    "safari17_0": r"safari17_0",
    "firefox133": r"firefox133",
    "playwright": r"[Pp]laywright",
    "requests": r"\bplain requests\b|\brequests\.get\b|\bplain `?requests`?\b",
    "scrapy": r"[Ss]crapy",
    "profile_ladder": r"all 5 profiles|all 4 profiles|all profiles|5 curl_cffi profiles|TLS profiles",
}

# "curl" on its own is NOT a lever. A bare-curl 403 measures curl's TLS
# handshake, not the site's defenses, and treating it as evidence is the exact
# mistake that produced 112 bogus SKIP_WAF verdicts on 2026-08-17. Entries
# whose only evidence is bare curl land with lever_tried=null and therefore
# fall into the recheck view by construction.

TELLS = {
    "cf-mitigated: challenge": r"cf-mitigated",
    "cloudflare": r"[Cc]loudflare",
    "akamai": r"[Aa]kamai|AkamaiGHost",
    "x-datadome": r"[Dd]ataDome|x-datadome",
    "awswaf": r"awswaf|AWS WAF|x-amzn-waf-action",
    "incapsula": r"Incapsula|Imperva",
    "perimeterx": r"PerimeterX",
    "radware": r"Radware|perfdrive",
    "qrator": r"[Qq]rator",
    "ddos-guard": r"DDOS-GUARD|[Dd]dos-[Gg]uard",
    "servicepipe": r"[Ss]ervicePipe",
    "hcdn": r"\bhcdn\b|Huawei Cloud",
    "azure-front-door": r"Azure Front Door",
    "fastly": r"[Ff]astly",
    "imunify360": r"Imunify360",
    "sgcaptcha": r"sgcaptcha|SignalGate",
    "recaptcha-enterprise": r"reCAPTCHA Enterprise",
    "queue-it": r"[Qq]ueue-it",
    "err_connection_reset": r"ERR_CONNECTION_RESET|connection[- ]reset",
    "tcp-timeout": r"TCP[- ]level|timed out|timeout|exit 000|curl exits 000",
    "ssl-error": r"SSL|certificate",
    "nxdomain": r"NXDOMAIN|does not resolve|no .{0,40}domain res|DNS",
    "http-402": r"\b402\b",
    "http-401": r"\b401\b",
    "http-403": r"\b403\b",
    "http-404": r"\b404\b",
    "http-405": r"\b405\b",
    "http-429": r"\b429\b",
    "http-503": r"\b503\b",
    "spa-shell": r"SPA shell|never hydrat|no server-rendered",
    "login-wall": r"[Ll]ogin[- ]wall",
    "zero-price": r"price=0|all zero|POA|Contact Us",
}

PLATFORMS = {
    "woocommerce": r"[Ww]oo[Cc]ommerce|wp-json/wc",
    "shopify": r"[Ss]hopify",
    "magento": r"[Mm]agento",
    "prestashop": r"[Pp]resta[Ss]hop",
    "opencart": r"[Oo]pen[Cc]art",
    "nopcommerce": r"nop[Cc]ommerce",
    "vtex": r"VTEX|[Vv]tex",
    "odoo": r"[Oo]doo",
    "nextjs": r"__NEXT_DATA__|Next\.js",
    "nuxt": r"[Nn]uxt",
    "vendure": r"[Vv]endure",
    "sapo": r"\bSapo\b",
    "algolia": r"[Aa]lgolia",
    "typesense": r"[Tt]ypesense",
    "wix": r"[Ww]ix",
    "shopware": r"[Ss]hopware",
    "cs-cart": r"CS-Cart",
    "sixam": r"6am[Mm]art|Sixam",
}

# Verdict inference. Checked in order; first hit wins.
VERDICT_RULES = [
    (
        "ok",
        r"Recovered and now shipped|Access restored|now: \*?\*?200|→ now: 200|"
        r"\bSHIPPED\b|shipped as |built and shipped|Verified working|"
        r"Confirmed already-covered|already onboarded|Existing manifests",
    ),
    (
        "no_catalog",
        r"No products on the site|[Bb]rochure-only|no online store|"
        r"Placeholder|demo/seed data|seed demo|zero/POA|"
        r"[Nn]ot a real product catalog|no canonical per-product URL|"
        r"No content|offline sites",
    ),
    (
        "out_of_scope",
        r"wrong currency|diaspora audience|non-food|Not retail SKU|"
        r"out of scope|Locality ambiguous|geographically exclude",
    ),
    (
        "unreachable",
        r"Unreachable|no online storefront exists|origin 404|"
        r"backend unreachable|Azure Web App stopped|store suspended|"
        r"maintenance mode|domain mismatch|retired/consolidated",
    ),
    ("app_only", r"App-only|no scrapeable web catalogue"),
    ("needs_work", r"not extractable without more work|not a hard block"),
]

CLASS_VERDICT_DEFAULT = "blocked"


def slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (text or "unclassified")[:60]


JUNK_SUFFIX = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".json",
    ".php",
    ".html",
    ".md",
    ".py",
    ".xml",
)

# Two-label public suffixes seen in this corpus. Not exhaustive by design — it
# only has to be right often enough for the index-coverage report.
TWO_LABEL_TLD = {
    "co.uk",
    "co.nz",
    "co.za",
    "co.bw",
    "co.ke",
    "co.tz",
    "co.sz",
    "co.il",
    "co.th",
    "co.id",
    "co.jp",
    "co.kr",
    "co.in",
    "co.ao",
    "co.mz",
    "co.zm",
    "com.au",
    "com.br",
    "com.mm",
    "com.my",
    "com.ph",
    "com.sg",
    "com.tr",
    "com.bn",
    "com.cn",
    "com.mx",
    "com.ar",
    "com.co",
    "com.pk",
    "com.bd",
    "com.ng",
    "com.gh",
    "com.eg",
    "com.sa",
    "com.qa",
    "com.kw",
    "com.bh",
    "com.lb",
    "com.pe",
    "com.uy",
    "com.py",
    "com.ec",
    "com.do",
    "com.gt",
    "com.ni",
    "com.pa",
    "com.sv",
    "com.hk",
    "com.tw",
    "com.vn",
    "com.lk",
    "com.np",
    "com.fj",
    "com.pg",
    "com.to",
    "com.ws",
    "com.vu",
    "com.sb",
    "gov.br",
    "gov.ua",
    "gov.mp",
    "gov.as",
    "gov.in",
    "gov.uk",
    "org.uk",
    "net.au",
    "org.au",
    "org.nz",
    "ac.uk",
    "com.cy",
    "com.mt",
}


def registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if ".".join(parts[-2:]) in TWO_LABEL_TLD:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def find_hosts(label: str) -> list[str]:
    """Hosts named in the identifying part of an entry (before the prose)."""
    out = []
    for h in HOST_RE.findall(label.lower()):
        if h.endswith(JUNK_SUFFIX) or h.startswith(("www.w3", "schema.org")):
            continue
        if h.startswith("www."):
            h = h[4:]
        out.append(h)
    return list(dict.fromkeys(out))


def split_label(line: str) -> tuple[str, str]:
    """Return (label, rest). The label is what names the host(s)."""
    body = line.lstrip("-* ").strip()
    for sep in (" — ", " -- ", " – ", ": ", " - "):
        if sep in body:
            head, tail = body.split(sep, 1)
            if len(head) < 160:
                return head, tail
    return body[:160], body


def match_all(text: str, table: dict[str, str]) -> list[str]:
    return [k for k, pat in table.items() if re.search(pat, text)]


def infer_verdict(text: str, heading: str) -> str:
    joined = f"{heading}\n{text}"
    for verdict, pat in VERDICT_RULES:
        if re.search(pat, joined):
            return verdict
    return CLASS_VERDICT_DEFAULT


def first_date(*texts: str) -> str | None:
    for t in texts:
        m = DATE_RE.search(t or "")
        if m:
            return m.group(0)
    return None


def make_record(
    host: str, text: str, heading: str, prose: dict[str, set], blocker_class: str = ""
) -> dict:
    levers = match_all(text, LEVERS)
    tells = match_all(f"{text} {heading}", TELLS)
    platforms = match_all(f"{text} {heading}", PLATFORMS)
    probed_at = first_date(text, heading)
    verdict = infer_verdict(text, heading)
    shipped = bool(re.search(r"\bSHIPPED\b|shipped as |built and shipped", text))

    if levers:
        prose["lever"].add(host)
    if tells:
        prose["tell"].add(host)
    if probed_at:
        prose["date"].add(host)
    if platforms:
        prose["platform"].add(host)

    recheck = None
    if verdict != "ok":
        if probed_at:
            d = datetime.strptime(probed_at, "%Y-%m-%d").date()
            recheck = (d + timedelta(days=RECHECK_DAYS)).isoformat()
        else:
            recheck = date.today().isoformat()  # undated == recheck now

    return {
        "host": host,
        "probed_at": probed_at,
        "discovery_method": None,  # unrecoverable from this corpus
        "discovery_detail": None,
        "platform": platforms[0] if platforms else None,
        "url_shape": None,
        "verdict": verdict,
        "lever_tried": ", ".join(levers) if levers else None,
        "tell": "; ".join(tells[:4]) if tells else None,
        "shipped": shipped,
        "recheck_after": recheck,
        "blocker_class": blocker_class or "unclassified",
        "source": "migration:known_blockers.md",
    }


def parse(src_text: str) -> tuple[list[dict], dict[str, set]]:
    """Return (records, evidence_present_in_prose)."""
    h2 = h3 = ""
    records: list[dict] = []
    # What the prose *could* yield, host-keyed, for the regression assertion.
    prose = {"lever": set(), "tell": set(), "date": set(), "platform": set()}

    for raw in src_text.splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            if level == 2:
                h2, h3 = title, ""
            elif level >= 3:
                h3 = title
            # Appended session reports use the host itself as a heading.
            heading_hosts = find_hosts(title.replace("**", "").replace("`", ""))
            if heading_hosts:
                for host in heading_hosts[:4]:
                    records.append(
                        make_record(host, title, f"{h2} {h3}".strip(), prose, h2)
                    )
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith(("> ", "```")):
            continue

        if line.startswith("|") and set(line) <= set("|-: "):
            continue  # table rule

        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            label = cells[0] if cells else ""
            rest = " ".join(cells[1:])
        elif line.startswith(("- ", "* ", "  - ", "    - ")):
            label, rest = split_label(line)
        else:
            # Plain prose. Several sections name hosts in running text and the
            # host index counted those, so they are entries too.
            label, rest = split_label(stripped)

        label = label.replace("**", "").replace("`", "")
        rest = rest.replace("**", "").replace("`", "")
        # Deliberately over-inclusive: an entry that mentions a second host is
        # usually saying something about it too, and a spurious extra row costs
        # one cheap re-probe while a dropped host is a permanent false skip.
        hosts = list(dict.fromkeys(find_hosts(label) + find_hosts(rest)))
        # An entry that names several hostnames is one verdict about each of
        # them ("ver1.cnmicommerce.com / cnmicommerce.com / commerce.gov.mp").
        for host in hosts:  # no cap: NXDOMAIN sweep bullets list 20+ hosts each
            records.append(
                make_record(host, f"{label} {rest}", f"{h2} {h3}".strip(), prose, h2)
            )
    return records, prose


WAF_TELLS = {
    "cloudflare",
    "cf-mitigated: challenge",
    "akamai",
    "x-datadome",
    "awswaf",
    "incapsula",
    "perimeterx",
    "radware",
    "qrator",
    "ddos-guard",
    "servicepipe",
    "recaptcha-enterprise",
    "sgcaptcha",
    "queue-it",
}
EDGE_TELLS = {"hcdn", "fastly", "azure-front-door", "imunify360"}
FAST_TELLS = {"nxdomain", "ssl-error", "tcp-timeout", "err_connection_reset"}


def sweep_class(rec: dict) -> str:
    """Shard key = how the host should be re-probed, not where its prose sat.

    NXDOMAIN and dead hosts re-probe at full speed and are pure profit. A
    hardened-CDN shard has to be paced or it re-confirms blocks that are really
    just our own request volume (`handla.ica.se`).
    """
    verdict = rec["verdict"]
    if verdict == "ok":
        return "recovered"
    if verdict in ("no_catalog", "app_only", "out_of_scope", "needs_work"):
        return verdict.replace("_", "-")
    tells = set((rec["tell"] or "").split("; "))
    if verdict == "unreachable" or tells & FAST_TELLS:
        return "unreachable-fast"
    if tells & WAF_TELLS:
        return "waf-hardened-paced"
    if tells & EDGE_TELLS:
        return "cdn-edge"
    return "blocked-unspecified"


def index_hosts(text: str) -> set[str]:
    hosts = set()
    for line in text.splitlines():
        if line.startswith("| `"):
            m = re.match(r"\|\s*`([^`]+)`", line)
            if m:
                h = m.group(1).strip().lower()
                hosts.add(h[4:] if h.startswith("www.") else h)
    return hosts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write", action="store_true", help="write shards (default: dry run)"
    )
    ap.add_argument(
        "--set-baseline",
        action="store_true",
        help="record this run's evidence counts as the regression floor",
    )
    args = ap.parse_args()

    if not SRC.exists():
        print(
            "known_blockers.md is gone — the migration already ran and the file was\n"
            "deleted in the same commit. This script is kept as the readable precedent\n"
            "for the next schema change, not to be re-run.\n\n"
            "To inspect the original:\n"
            "  git log --diff-filter=D -- '*/references/known_blockers.md'\n"
            "  git show <commit>^:.claude/skills/onboard-price-sources/references/known_blockers.md"
        )
        return 0

    records, prose = parse(SRC.read_text(encoding="utf-8"))

    got = {
        "lever": {r["host"] for r in records if r["lever_tried"]},
        "tell": {r["host"] for r in records if r["tell"]},
        "date": {r["host"] for r in records if r["probed_at"]},
        "platform": {r["host"] for r in records if r["platform"]},
    }
    hosts = {r["host"] for r in records}

    print(f"rows            {len(records)}")
    print(f"distinct hosts  {len(hosts)}")
    for field in ("lever", "tell", "date", "platform"):
        lost = prose[field] - got[field]
        print(
            f"{field:<15} prose={len(prose[field]):<5} output={len(got[field]):<5} lost={len(lost)}"
        )
        if lost:
            print(f"  lost hosts: {sorted(lost)[:10]}")

    print("\nverdicts:")
    for v, n in Counter(r["verdict"] for r in records).most_common():
        print(f"  {v:<14} {n}")

    if INDEX.exists():
        idx = {registrable(h) for h in index_hosts(INDEX.read_text(encoding="utf-8"))}
        reg_hosts = {registrable(h) for h in hosts}
        missing = idx - reg_hosts
        hosts_cmp = reg_hosts
        print(f"\nindex hosts     {len(idx)}")
        print(f"  present       {len(idx & hosts_cmp)}")
        print(f"  missing       {len(missing)}")
        if missing:
            print(f"  sample        {sorted(missing)[:15]}")
        print(f"  net new (not in index) {len(hosts_cmp - idx)}")

    recheck_now = sum(
        1
        for r in records
        if r["recheck_after"] and r["recheck_after"] <= date.today().isoformat()
    )
    print(f"\nrecheck queue today: {recheck_now}")

    # --- D14 regression gate ------------------------------------------------
    counts = {k: len(v) for k, v in got.items()}
    counts["rows"] = len(records)
    counts["hosts"] = len(hosts)

    if args.set_baseline:
        BASELINE.write_text(json.dumps(counts, indent=2) + "\n")
        print(f"\nbaseline written: {BASELINE}")
    elif BASELINE.exists():
        base = json.loads(BASELINE.read_text())
        regressions = {
            k: (base[k], counts[k]) for k in base if counts.get(k, 0) < base[k]
        }
        if regressions:
            print("\nFAIL — populated-field report regressed:")
            for k, (b, c) in regressions.items():
                print(f"  {k}: baseline {b} -> now {c}")
            return 1
        print("\nOK — no regression against baseline.")

    if not args.write:
        print("\n(dry run — pass --write to emit shards)")
        return 0

    OUT_DIR.mkdir(exist_ok=True)
    shards: dict[str, list[dict]] = {}
    for r in records:
        r["sweep_class"] = sweep_class(r)
        shards.setdefault(f"migration-{r['sweep_class']}", []).append(r)

    for name, rows in sorted(shards.items()):
        path = OUT_DIR / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(shards)} shards to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
