# The `recover` route — bulk re-probe of everything we already wrote off

**Run this first on any coverage-gap complaint.** Before discovery, before search,
before spending a probe budget on candidates nobody has ever seen.

A recovered host has **zero discovery cost**. The domain is already known, already
classified, already in an inventory. And re-probing 400 hosts costs roughly what
re-probing 4 costs, because you read a summary, not 400 responses. Nothing else in
this skill has that shape.

Takes no country argument. It walks the recheck view.

## Why the queue is full of false skips

The store it inherited recorded a dead end as a markdown bullet and a win as a YAML
file, so verdicts were never comparable and never aged. Measured on this corpus:

| When | Finding |
|---|---|
| 2026-08-17 | 279-domain triage produced 112 `SKIP_WAF` verdicts from bare `curl` + a browser UA. Re-probing with `curl_cffi` alone recovered a large share on the first lever — including Cloudflare Turnstile *and* Akamai sites. |
| 2026-09-06 | 16 of 26 hosts in one shard returned a clean 200 while filed as blocked. |
| 2026-09-12 | 11 of 125 retried hosts returned 200 on `chrome150` / `chrome131_android` after 403-ing on `chrome120`/`chrome124`. `rewe_de` shipped only because of that retry. |
| 2026-09-17 | 45 of 50 hosts from the migrated `blocked-unspecified` shard returned clean 200s in **33 seconds**; 16 had an open platform catalog endpoint. |

Of the 2,204 hosts in the log at migration, **288 carry a lever** and 1,516 carry a
date. The rest are verdicts whose evidence is unrecoverable — which is the definition
of a hypothesis, not a finding.

## The queue

```bash
python scripts/probe_log.py recheck --count
python scripts/probe_log.py recheck --class blocked-unspecified --limit 50
```

The view is `verdict != ok AND NOT shipped AND (lever_tried IS NULL OR recheck_after <= today)`.
It sorts never-really-tested hosts first — a host with no lever recorded has never been
tested at all, only guessed at.

`recheck_after` defaults to probed_at + 6 months on any non-ok verdict. An undated
verdict rechecks immediately, because a July verdict and a September verdict were
indistinguishable to a grep in the old file and that is what made it untrustworthy.

## Sharded by blocker class, because the classes have different economics

| Shard | Workers | Pause | Why |
|---|---|---|---|
| `unreachable-fast` | 16 | 0 s | NXDOMAIN and dead origins re-probe at full speed. Pure profit when one comes back. |
| `blocked-unspecified` | 8 | 0.5 s | The false-skip reservoir. Highest yield. |
| `no-catalog` / `app-only` / `out-of-scope` | 8 | 0.5 s | Structural verdicts, but storefronts do launch. |
| `cdn-edge` / `needs-work` | 6 | 1 s | Real edge posture; worth a gentler hand. |
| `waf-hardened-paced` | 2 | 4 s | **Must be paced.** `handla.ica.se` probed clean in isolation and then failed three acceptance runs against a challenge triggered by the campaign's own traffic from one IP. An unpaced sweep here re-confirms blocks that are really just our own request volume. |

## Running it

Always on a8. A backgrounded `&` over ssh dies with the connection, and the harness
cannot see remote processes — it will never notify.

```bash
ssh a8 'cd ~/po/.claude/skills/onboard-price-sources && \
  setsid nohup ~/venv/bin/python scripts/recover_sweep.py \
    --class blocked-unspecified --run-id rec1 --limit 400 \
    > /tmp/rec1.log 2>&1 </dev/null &'
```

`--dry-run` probes without appending. **Dry-run one 50-host shard before any full
sweep** and compare the verdicts against what the log claimed. 50 hosts is enough to
separate "the inherited verdicts are wrong at scale" from "my prober is misconfigured",
and at full scale those two look identical.

## What the sweeper does per host

Walks the TLS ladder `chrome124 → chrome120 → safari17_0 → firefox133`, stops at the
first 200 over 2 KB, then fingerprints the platform against the endpoints in
`../platform_fingerprints.md` (WooCommerce Store API, Shopify `products.json`, Magento
REST, nopCommerce). It records the lever that worked and the tell it saw, so a recovered
host arrives already ranked.

A 200 is **access, not enumerability**, and an open platform API is **not a priced
catalog**. Both gates still apply — see `probe.md`. The sweep's job is to hand you a
shortlist, not a verdict.

## Then

Promote anything returning 200 straight into **Phase 2.5** (`discover.md`) — classify it
along the four axes and continue normally. It skips Phases 0.5, 1 and 2 entirely: the
candidate was already found, the country is already known, and discovery has nothing left
to add.

Log every result, recovered or re-confirmed. A host reading `blocked` in July and `ok`
in September is the most valuable row in the store: it is the evidence that this route
works, and the measurement of how fast verdicts decay. Nothing is ever compacted.
