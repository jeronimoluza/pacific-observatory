"""Read-only audit of text source configs (schema, duplicates, stale, failing).

Usage (from repo root):
    PYTHONPATH=src python scripts/text_config_audit.py \
        [--status-dir ../niger-radio-text/outputs/text] [--today 2026-10-05]

Writes outputs/text/reports/audit/config_audit_<YYYYMMDD>.{md,csv}. Never reads news.csv.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import yaml

from core.config import known_country_slugs
from text.scrapers.models import NewspaperConfig
from text.scrapers.orchestration.validate import validate_schema

CONFIGS_DIR = Path("src/text/configs")
OUT_DIR = Path("outputs/text/reports/audit")
STALE_DAYS = 90
MAX_ROWS = 25


def norm_url(url):
    url = re.sub(r"^https?://", "", str(url or "").strip().lower())
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def list_configs():
    """Return (live, underscore0) lists of (key, path); key = (region, subregion, country, stem)."""
    live, zero = [], []
    for path in sorted(CONFIGS_DIR.rglob("*.yaml")):
        rel = path.relative_to(CONFIGS_DIR).parts
        if path.name == "template.yaml" or any(p.startswith("_") for p in rel[:-1]):
            continue
        if len(rel) < 4:
            continue
        key = (rel[0], rel[1], rel[2], path.stem)
        (zero if path.stem.startswith("_0_") else live).append((key, path))
    return live, zero


def read_status(status_dir):
    status = {}
    for f in sorted((status_dir / "database_status").glob("sources_*.json")):
        for s in json.loads(f.read_text())["sources"]:
            status[(s["region"], s["subregion"], s["country"], s["newspaper"])] = s
    return status


def read_reports(status_dir):
    """region -> list of (name, {(country, source): (status, note)}), oldest first."""
    out = defaultdict(list)
    for f in sorted((status_dir / "reports" / "collect").glob("collect_*_*.md")):
        rows = {}
        for line in f.read_text().splitlines():
            c = [x.strip() for x in line.split("|")]
            if len(c) > 8 and c[3] in ("DONE", "FAIL", "TIMEOUT-KILLED"):
                rows[(c[1], c[2])] = (c[3], c[7])
        out[f.name.split("_")[1]].append((f.name, rows))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status-dir", default="../niger-radio-text/outputs/text")
    ap.add_argument(
        "--today", default="2026-10-05", help="reference date for staleness"
    )
    args = ap.parse_args()
    status_dir, today = Path(args.status_dir), date.fromisoformat(args.today)
    cutoff = today - timedelta(days=STALE_DAYS)

    live, zero = list_configs()
    status = read_status(status_dir)
    reports = read_reports(status_dir)
    countries = known_country_slugs()
    flags = []
    cfgs = {}
    disabled = 0

    def flag(check, key, detail, keeper=""):
        st = status.get(key, {})
        flags.append(
            {
                "check": check,
                "region": key[0],
                "subregion": key[1],
                "country": key[2],
                "source": key[3],
                "detail": detail,
                "articles": st.get("article_count", ""),
                "latest_date": st.get("latest_date", ""),
                "keeper": keeper,
            }
        )

    # 1. schema (+ country folder present in the regions.yaml topology)
    for key, path in live:
        try:
            cfg = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            flag("schema", key, f"YAML: {str(e)[:150]}")
            continue
        if not isinstance(cfg, dict):
            flag("schema", key, "not a mapping")
            continue
        cfgs[key] = cfg
        disabled += cfg.get("enabled") is False
        try:
            NewspaperConfig(**cfg)
            pyd_ok = True
        except Exception as e:
            pyd_ok = False
            flag("schema", key, "pydantic: " + str(e).replace("\n", " ")[:200])
        # validate.py's listing-type list lags the scrapers (rejects 'sitemap');
        # pydantic is authoritative, so its extra errors are reported separately.
        try:
            for level, msg in validate_schema(cfg, path):
                if level == "error":
                    flag("schema" if not pyd_ok else "schema_validatepy_only", key, msg)
        except Exception as e:
            flag(
                "schema" if not pyd_ok else "schema_validatepy_only",
                key,
                f"validate_schema crashed: {e}",
            )
        if key[2] not in countries:
            flag("schema", key, f"folder country '{key[2]}' not in regions.yaml")

    # 2. duplicates
    groups = {
        "base_url": defaultdict(list),
        "listing_url": defaultdict(list),
        "stem": defaultdict(list),
    }
    for key, cfg in cfgs.items():
        groups["base_url"][norm_url(cfg.get("base_url"))].append(key)
        lst = cfg.get("listing") if isinstance(cfg.get("listing"), dict) else {}
        urls = []
        for v in (lst.get("start_url"), lst.get("url_template")):
            urls += v if isinstance(v, list) else [v]
        for u in {norm_url(u) for u in urls if isinstance(u, str)}:
            groups["listing_url"][u].append(key)
        groups["stem"][key[3]].append(key)
        if str(cfg.get("country", "")).lower().replace(" ", "_") != key[2]:
            flag(
                "country_mismatch",
                key,
                f"yaml country='{cfg.get('country')}' folder='{key[2]}'",
            )

    def arts(k):
        return int(status.get(k, {}).get("article_count") or 0)

    dup_groups = []
    for kind, g in groups.items():
        for gid, keys in sorted(g.items()):
            if len(keys) < 2:
                continue
            if kind == "stem" and len({k[2] for k in keys}) < 2:
                continue
            keeper = max(keys, key=arts)
            dup_groups.append((kind, gid, keys, keeper))
            for k in keys:
                flag(
                    f"dup_{kind}",
                    k,
                    gid,
                    "KEEP" if k == keeper else f"drop? keeper={keeper[2]}/{keeper[3]}",
                )

    # 3. stale / empty / coverage vs status
    for key in sorted(cfgs):
        st = status.get(key)
        if st is None:
            flag("missing_from_status", key, "config has no status row")
        elif int(st["article_count"] or 0) == 0:
            flag("zero_articles", key, "0 articles")
        elif st["latest_date"] and date.fromisoformat(st["latest_date"]) < cutoff:
            flag("stale", key, f"last article {st['latest_date']}")
    for key in sorted(set(status) - set(cfgs)):
        flag("status_without_config", key, "status row has no config")

    # 4. collect failures (latest report per region) + chronic timeouts (last 3 reports)
    tkey = {(k[2], k[3]): k for k in cfgs}
    for region, reps in reports.items():
        name, rows = reps[-1]
        for (c, s), (stt, note) in rows.items():
            if stt == "FAIL":
                flag(
                    "collect_fail",
                    tkey.get((c, s), (region, "?", c, s)),
                    f"{name} {note}",
                )
        last3 = reps[-3:]
        if len(last3) == 3:
            for cs in rows:
                if all(r[1].get(cs, ("",))[0] == "TIMEOUT-KILLED" for r in last3):
                    flag(
                        "chronic_timeout",
                        tkey.get(cs, (region, "?", *cs)),
                        "TIMEOUT-KILLED in last 3 reports",
                    )

    # 5. skill/runner inconsistency
    skill = Path(".claude/skills/refresh-text-region")
    skill_par = re.findall(
        r"max[^\n]{0,20}\b(\d+)\b[^\n]{0,20}parallel",
        (skill / "SKILL.md").read_text(),
        re.I,
    )
    runner_par = re.findall(
        r'PARALLELISM="\$\{2:-(\d+)\}"',
        (skill / "scripts/launch_refresh.sh").read_text(),
    )

    # ---- write ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    md_path, csv_path = (
        OUT_DIR / f"config_audit_{stamp}.md",
        OUT_DIR / f"config_audit_{stamp}.csv",
    )
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0]) if flags else ["check"])
        w.writeheader()
        w.writerows(flags)

    checks = sorted({f["check"] for f in flags})
    regions = sorted({k[0] for k in cfgs} | {k[0] for k in status})
    cnt = defaultdict(int)
    for f in flags:
        cnt[(f["check"], f["region"])] += 1
    lines = [
        f"# Text config audit {stamp}",
        "",
        f"Configs: {len(live)} live ({len(cfgs)} parsed, {disabled} already `enabled: false`), "
        f"{len(zero)} `_0_*` files (not audited). Status: {len(status)} rows, "
        f"reference date {today}, stale = last article before {cutoff}.",
        f"Flagged rows (CSV): {csv_path.as_posix()}",
        "",
        "## Counts per check per region",
        "",
        "| check | " + " | ".join(regions) + " | total |",
        "|---|" + "---|" * (len(regions) + 1),
    ]
    for c in checks:
        row = [cnt[(c, r)] for r in regions]
        lines.append(f"| {c} | " + " | ".join(map(str, row)) + f" | {sum(row)} |")
    lines += [
        "",
        "Configs per region: "
        + ", ".join(f"{r}={sum(1 for k in cfgs if k[0] == r)}" for r in regions),
        "",
    ]

    def table(
        title,
        check,
        cols=(
            "region",
            "country",
            "source",
            "detail",
            "articles",
            "latest_date",
            "keeper",
        ),
    ):
        rows = [f for f in flags if f["check"] == check]
        lines.extend([f"## {title} ({len(rows)})", ""])
        if not rows:
            lines.extend(["none", ""])
            return
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for f in rows[:MAX_ROWS]:
            lines.append(
                "| " + " | ".join(str(f[c]).replace("|", "/") for c in cols) + " |"
            )
        if len(rows) > MAX_ROWS:
            lines.append(f"\n... {len(rows) - MAX_ROWS} more in the CSV")
        lines.append("")

    table("1. Schema failures", "schema")
    table("2a. Country field vs folder", "country_mismatch")
    lines += ["## 2b. Duplicate groups", ""]
    for kind in groups:
        gs = [g for g in dup_groups if g[0] == kind]
        one = [g for g in gs if len({k[2] for k in g[2]}) == 1]
        lines.append(f"- {kind}: {len(gs)} groups ({len(one)} within one country)")
    lines += [
        "",
        "Shown: listing_url groups and any group inside one country (real duplicates). "
        "base_url / stem groups across countries are usually regional sections; see CSV.",
        "",
        "| kind | key | members (articles) | keeper |",
        "|---|---|---|---|",
    ]
    shown = sorted(
        (
            g
            for g in dup_groups
            if g[0] == "listing_url" or len({k[2] for k in g[2]}) == 1
        ),
        key=lambda g: -len(g[2]),
    )
    for kind, gid, keys, keeper in shown[:MAX_ROWS]:
        mem = ", ".join(f"{k[0]}/{k[2]}/{k[3]} ({arts(k)})" for k in keys)
        lines.append(f"| {kind} | {gid} | {mem} | {keeper[2]}/{keeper[3]} |")
    if len(shown) > MAX_ROWS:
        lines.append(f"\n... {len(shown) - MAX_ROWS} more in the CSV")
    lines.append("")
    table("3a. Stale (> 90 d)", "stale")
    table("3b. Zero articles", "zero_articles")
    table("3c. Config missing from status", "missing_from_status")
    table("3d. Status without config", "status_without_config")
    table("4a. Failed in latest collect report", "collect_fail")
    table("4b. Timed out in each of last 3 reports", "chronic_timeout")
    lines += [
        "## 5. Skill vs runner",
        "",
        f"SKILL.md parallel mentions: {skill_par or 'none found'}; launch_refresh.sh default: {runner_par or 'none found'}.",
        "",
    ]
    md_path.write_text("\n".join(lines))
    print(f"wrote {md_path} and {csv_path}")
    for c in checks:
        print(
            f"{c}: {sum(cnt[(c, r)] for r in regions)}  "
            + " ".join(f"{r}={cnt[(c, r)]}" for r in regions if cnt[(c, r)])
        )


if __name__ == "__main__":
    main()
