"""`po text source-health`: probe every enabled text config's listing URLs, keep a probe
history, and (with --mark) disable sources confirmed dead.

A single run never disables anything. A source is CONFIRMED dead when its last two probes
both failed with not_found / dns_dead / hijacked and the first failure is at least 6 h
older than the last probe; until then it is PROVISIONAL. forbidden / cloudflare / timeout
/ conn_error / server_error are only listed (watch list), never disabled.

State (gitignored): data/text/_health/source_health.json. Run outputs (probes.csv,
summary.md): logs/text/_health/<UTC stamp>/ unless --out.
"""

from __future__ import annotations

import asyncio
import collections
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

CONFIGS = Path("src/text/configs")
STATE_FILE = Path("data/text/_health/source_health.json")
DEAD = {"not_found", "dns_dead", "hijacked"}
WATCH = {"forbidden", "cloudflare", "timeout", "conn_error", "server_error"}
CONFIRM_GAP = timedelta(hours=6)
_DISABLED = re.compile(r"^enabled:\s*false\b", re.I | re.M)
FMT = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> str:
    return datetime.now(timezone.utc).strftime(FMT)


def enabled_configs(region=None, country=None, source=None, keys=None) -> list[Path]:
    out = []
    for f in sorted(CONFIGS.glob("*/*/*/*.yaml")):
        reg, _, ctry, stem = f.parts[-4], f.parts[-3], f.parts[-2], f.stem
        if stem.startswith("_") or _DISABLED.search(f.read_text()):
            continue
        if (
            (region and reg != region)
            or (country and ctry != country)
            or (source and stem != source)
        ):
            continue
        if keys is not None and _key(f) not in keys:
            continue
        out.append(f)
    return out


def _key(f: Path) -> str:
    return "/".join(f.parts[-4:-1] + (f.stem,))


async def _run(configs: list[Path], concurrency: int) -> list[dict]:
    import httpx
    import yaml

    from text.source_health import (
        TIMEOUT,
        Prober,
        lang_scripts,
        listing_urls,
        rest_route_variant,
    )

    country_scripts = collections.defaultdict(
        set
    )  # every script any config of a country uses
    for f in CONFIGS.glob("*/*/*/*.yaml"):
        m = re.search(r"^language:\s*(\S+)", f.read_text(), re.M)
        country_scripts[f.parts[-2]] |= lang_scripts(m.group(1)) if m else set()
    prober = Prober(concurrency)
    today = datetime.now(timezone.utc)
    rows = []

    async def one(client, f):
        cfg = yaml.safe_load(f.read_text()) or {}
        cfg["_country_scripts"] = frozenset(country_scripts[f.parts[-2]])
        urls = listing_urls(cfg, today)
        probes = [await prober.probe(client, u, role, cfg) for role, u in urls]
        for (
            p
        ) in probes:  # WP REST blocked at /wp-json/: does ?rest_route= still answer?
            alt = (
                rest_route_variant(p.url)
                if p.status in ("not_found", "forbidden", "empty_listing")
                else ""
            )
            if alt:
                q = await prober.probe(client, alt, p.role, cfg)
                p.detail += f"; ?rest_route= variant {q.status}"
        good = [p for p in probes if p.status == "ok"]
        src_status = (
            "ok" if good else (probes[0].status if probes else "no_listing_url")
        )
        for p in probes or [None]:
            rows.append(
                {
                    "key": _key(f),
                    "region": f.parts[-4],
                    "country": f.parts[-2],
                    "source": f.stem,
                    "language": cfg.get("language", ""),
                    "listing_type": (cfg.get("listing") or {}).get("type", ""),
                    "role": p.role if p else "",
                    "url": p.url if p else "",
                    "status": p.status if p else src_status,
                    "http": p.http if p else "",
                    "final_url": p.final_url if p else "",
                    "detail": p.detail if p else "",
                    "source_status": src_status,
                    "probed_at": _now(),
                }
            )
        done = len({r["key"] for r in rows})
        if done % 100 == 0:
            click.echo(f"  {done}/{len(configs)} sources probed", err=True)

    limits = httpx.Limits(max_connections=concurrency * 2)
    async with httpx.AsyncClient(
        timeout=TIMEOUT, follow_redirects=True, limits=limits
    ) as client:
        await asyncio.gather(*(one(client, f) for f in configs))
    return rows


def update_state(state: dict, rows: list[dict]) -> None:
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r["key"], r)
    for key, r in by.items():
        s = state.setdefault(
            key,
            {
                "last_ok": None,
                "first_fail": None,
                "consecutive_fails": 0,
                "history": [],
            },
        )
        st, ts = r["source_status"], r["probed_at"]
        s.update(status=st, url=r["url"], detail=r["detail"], last_probe=ts)
        s["history"] = (s["history"] + [[ts, st]])[-12:]
        if st == "ok":
            s.update(last_ok=ts, first_fail=None, consecutive_fails=0)
        else:
            s["first_fail"] = s["first_fail"] or ts
            s["consecutive_fails"] += 1


def verdict(s: dict) -> str:
    """confirmed | provisional | watch | ok for one state entry."""
    st = s.get("status")
    if st == "ok":
        return "ok"
    if st not in DEAD:
        return "watch"
    last2 = [h[1] for h in s["history"][-2:]]
    span = datetime.strptime(s["last_probe"], FMT) - datetime.strptime(
        s["first_fail"], FMT
    )
    if len(last2) == 2 and all(x in DEAD for x in last2) and span >= CONFIRM_GAP:
        return "confirmed"
    return "provisional"


def write_outputs(out: Path, rows: list[dict], state: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "probes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    srcs = {r["key"]: r for r in rows}
    by_status = collections.Counter(r["source_status"] for r in srcs.values())
    by_region = collections.defaultdict(collections.Counter)
    for r in srcs.values():
        by_region[r["region"]][r["source_status"]] += 1
    statuses = sorted(by_status, key=lambda s: -by_status[s])
    lines = [
        f"# text source health {_now()}",
        "",
        f"{len(srcs)} sources, {len(rows)} URLs",
        "",
        "| region | " + " | ".join(statuses) + " |",
        "|---" * (len(statuses) + 1) + "|",
    ]
    for reg in sorted(by_region):
        lines.append(
            f"| {reg} | " + " | ".join(str(by_region[reg][s]) for s in statuses) + " |"
        )
    lines.append(
        "| **all** | " + " | ".join(str(by_status[s]) for s in statuses) + " |"
    )
    for v in ("confirmed", "provisional", "watch"):
        keys = sorted(k for k in srcs if k in state and verdict(state[k]) == v)
        lines += ["", f"## {v} ({len(keys)})", ""]
        for k in keys:
            s = state[k]
            lines.append(
                f"- {k} | {s['status']} | {s['url']} | {s['detail']} | first_fail {s['first_fail']} | last {s['last_probe']}"
            )
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def mark(state: dict, configs_dir: Path = CONFIGS) -> list[str]:
    """Write `enabled: false` + disabled_reason under `name:` of every confirmed source."""
    marked = []
    for key, s in sorted(state.items()):
        if verdict(s) != "confirmed":
            continue
        f = configs_dir / f"{key}.yaml"
        if not f.exists():
            continue
        text = f.read_text()
        if _DISABLED.search(text):
            continue
        fails = [h[0] for h in s["history"] if h[1] != "ok"]
        reason = (
            f"source-health {s['last_probe'][:10]}: {s['status']} on {s['url']} ({s['detail']}); "
            f"failing since {s['first_fail']}, probes {', '.join(fails[-3:])}. "
            "Re-enable when the URL answers (`po text source-health --source <key>`)."
        )
        reason = reason.replace('"', "'")
        new = re.sub(r"^enabled:.*\n", "", text, flags=re.M)
        new = re.sub(
            r"^(name:.*\n)",
            lambda m: m.group(1) + f'enabled: false\ndisabled_reason: "{reason}"\n',
            new,
            count=1,
            flags=re.M,
        )
        if new == text or "disabled_reason" not in new:
            new = f'enabled: false\ndisabled_reason: "{reason}"\n' + text
        f.write_text(new)
        marked.append(key)
    return marked


@click.command("source-health")
@click.option("--region", default=None)
@click.option("--country", default=None)
@click.option("--source", "-s", default=None, help="Config stem")
@click.option(
    "--failing-only",
    is_flag=True,
    help="Re-probe only sources failing in the state file",
)
@click.option(
    "--mark",
    "do_mark",
    is_flag=True,
    help="Disable CONFIRMED dead sources (enabled: false)",
)
@click.option("--concurrency", default=8, show_default=True)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=None,
    help="Run output dir (default logs/text/_health/<UTC stamp>)",
)
@click.option(
    "--state-file",
    type=click.Path(path_type=Path),
    default=STATE_FILE,
    show_default=True,
)
def source_health(
    region, country, source, failing_only, do_mark, concurrency, out, state_file
):
    """Probe listing/sitemap/RSS/API URLs of enabled text sources and classify them."""
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    keys = (
        {k for k, s in state.items() if s.get("status") != "ok"}
        if failing_only
        else None
    )
    configs = enabled_configs(region, country, source, keys)
    click.echo(
        f"  probing {len(configs)} sources (concurrency {concurrency})", err=True
    )
    rows = asyncio.run(_run(configs, concurrency)) if configs else []
    update_state(state, rows)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=1, sort_keys=True))
    out = out or Path("logs/text/_health") / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%MZ"
    )
    if rows:
        write_outputs(out, rows, state)
        click.echo((out / "summary.md").read_text().split("\n## ")[0])
    v = collections.Counter(
        verdict(state[r["key"]]) for r in {r["key"]: r for r in rows}.values()
    )
    click.echo(
        f"  verdicts: {dict(v)}  -> {out}/probes.csv, {out}/summary.md, state {state_file}"
    )
    if do_mark:
        marked = mark(state)
        click.echo(
            f"  marked {len(marked)} confirmed-dead configs enabled: false"
            + "".join(f"\n    {k}" for k in marked)
        )
