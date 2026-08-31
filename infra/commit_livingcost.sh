#!/bin/bash
# Commit the livingcost benchmark extractor in template-repo.
#
# This session is worktree-isolated to pacific-observatory, and the harness
# refuses any git command aimed at the template-repo checkout -- via `cd`,
# `-C`, or `--git-dir` alike. The edits are applied and tested; only the commit
# needs a shell that is not worktree-isolated.
#
#   bash infra/commit_livingcost.sh
#
# Run this FIFTH, after commit_offer_scope.sh, commit_bysource_tier.sh,
# commit_nextdata_tier.sh and commit_classifieds_tier.sh. All of them edit
# archived_bysource.py, so committing out of order carries the others' work
# under the wrong message.
#
# Nothing under data/, outputs/ or openspec/ is staged, and no Co-Authored-By
# trailer is added.
set -eu

REPO=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "on $BRANCH -- creating a branch rather than committing to it"
  git checkout -b cc-livingcost-benchmark
fi

git add \
  src/prices/price_scraping/archived_livingcost.py \
  src/prices/price_scraping/archived_bysource.py \
  tests/unit/prices/test_archived_livingcost.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(parse): livingcost city baskets as a benchmark, not as observations

These rows are not observed retail prices and must not be pooled with the
rest of the corpus. livingcost.org publishes crowd-sourced and modelled
estimates for a basket of about fifty items per city, already converted to US
dollars. They are useful as a benchmark to compare a measured series against,
and the source key is the only thing separating them from a measurement, so
the warning lives at the top of the module as well as here.

The source was refused in the previous sweep on the basis that every figure it
carried was a modelled city aggregate. That was measured on the wrong part of
the page: the aggregates are real, but each capture also carries an item table
-- milk, bread, a cappuccino, a haircut, a monthly transport ticket, rent per
apartment size -- which is a named good at a price and exactly what a benchmark
needs.

Only single-city pages are read ("Cost of Living in Blankenberge | Belgium").
The comparison pages print two figures per row under two city column headers,
and attributing a column to the wrong city would file New York's cappuccino
under Mashhad for no gain over a single-city capture. They abstain. That is a
real cost: single-city pages are the whole of the 2020 sample but only 3 of 20
held-out 2025 captures, so this reads a shrinking share of the source.

Rows are selected by shape rather than by CSS class. An item row is "label, one
price" and carries two cells; the cost-of-living summary (label, one person,
family) and the nearest-cities widget (distance, city, monthly budget) both
carry three, so a two-cell rule excludes them without naming them. The class
that first looked semantic here, `table-str`, turned out to be a truncation
artifact of the diagnostic that printed it -- the real class is Bootstrap's
`table-striped`, which is styling and would not survive a redesign.

Two further exclusions, both measured:

- `Monthly salary after tax` and `GDP per capita` sit inside the item tables
  and have the item shape exactly. Only their labels distinguish them.
- Two captures carry a US-states table whose rows are "Alabama | $1,234":
  two cells and a dollar figure, indistinguishable by shape from an item. Every
  genuine item label on this site is emoji-prefixed, on all 30 single-city
  captures spanning 2020 to 2025, and the state rows are not, so the prefix is
  required rather than merely stripped.

Measured on held-out captures, including the 2023 era nothing had sampled:
49.0 rows per single-city capture in each of 2023, 2024 and 2025, 49 distinct
item labels, and all 539 banked figures appear in the page's own text. Weighted
by era share and by the single-city share within each era, that is roughly
800k benchmark rows.
MSG

git --no-pager log --stat -1
