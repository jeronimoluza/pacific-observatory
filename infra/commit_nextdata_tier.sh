#!/bin/bash
# Commit the __NEXT_DATA__ tier and the emart_kr / yahoo_shopping_tw extractors
# in template-repo.
#
# This session is worktree-isolated to pacific-observatory, and the harness
# refuses any git command aimed at the template-repo checkout -- via `cd`,
# `-C`, or `--git-dir` alike. The edits are applied and tested; only the commit
# needs a shell that is not worktree-isolated.
#
#   bash infra/commit_nextdata_tier.sh
#
# Run this THIRD. infra/commit_offer_scope.sh commits the microdata Offer-scope
# fix and infra/commit_bysource_tier.sh the per-source tier; this change edits
# archived_bysource.py on top of the latter, so committing it first would carry
# that work along under the wrong message.
#
# Nothing under data/, outputs/ or openspec/ is staged, and no Co-Authored-By
# trailer is added.
set -eu

REPO=/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
cd "$REPO"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "on $BRANCH -- creating a branch rather than committing to it"
  git checkout -b cc-nextdata-tier
fi

git add \
  src/prices/price_scraping/archived_nextdata.py \
  src/prices/price_scraping/archived_emart.py \
  src/prices/price_scraping/archived_yahoo_tw.py \
  src/prices/price_scraping/archived_bysource.py \
  src/prices/cc_warc_fetcher.py \
  tests/unit/prices/test_archived_nextdata.py

PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -F - <<'MSG'
infra(parse): read the Pages Router blob, and two sources measured wrong

`rows_from_next_flight` reads only `self.__next_f`, the App Router's streaming
payload. The static Pages Router blob in `<script id="__NEXT_DATA__">` was
unread, and across 3,415 cached captures it is 7x commoner: 4.6% of pages
against 0.6%. Every one of those was banked as a miss.

Placement is the append slot, after microdata. It was first put ahead of
microdata on the argument that a payload outranks a partial microdata summary;
measured over the 2,142 cached captures that reach that part of the chain the
two tiers never once read the same page -- 68 payload only, 98 microdata only,
zero both -- so the claim bought nothing and the placement that cannot regress
a page which parses today is free.

The tier walks the parsed object tree for an object carrying both a name-like
and a price-like field, the same signal the flight tier uses, because the paths
are per-source and per-era: `.props.pageProps.product` on kurly.com and
prisma.fi, `.query.data.mainContent.records[].allMeta` on liverpool.com.mx,
`.props.pageProps.pageData.items[]` on drogasil.com.br. Keying on a path would
need a registry that goes stale every time a site rebuilds.

Three guards come from defects measured while writing it. Each scored perfectly
clean until the samples were read:

- `value` and `amount` are excluded from the price-key list. They are what a
  payload calls anything at all, and admitting them banked "Size (g)" at 100.0
  and "Alto" at 40.0 -- product specification attributes. A price key that
  could equally hold a shoe width is not a price key.
- Payload units are reconciled against what the page renders as money.
  prisma.fi publishes `finalPrice: 2000` for a book it displays as 20,00 EUR;
  nothing inside the payload distinguishes that from liverpool.com.mx's
  `minimumPromoPrice: '7939'`, which really is 7,939 pesos. The check settles
  the page's scale rather than each row's fate: dropping uncorroborated rows
  instead cost liverpool 28 of 30 pages, because that payload carries the price
  precisely when the page does not render it, and the money the page does
  render is a delivery-threshold banner.
- Objects reached through a `related`/`recommend`/`similar` key are skipped.
  agrofy.com.ar carries 11 unrelated cars under `merchantRelatedProducts`, and
  attributing them to this URL writes a series that moves when the rail does.

emart_kr and yahoo_shopping_tw get per-source extractors. On both, the field
whose class name makes it the obvious choice is the wrong one:

- emart's `cdtl_price` sits inside `.cdtl_card_price` and is a bank-card
  conditional price. Measured on one capture: 55,016 and 56,810 against a
  최적가 of 59,800, exactly 0.92x and 0.95x, each labelled with the issuer and
  the spend threshold that unlocks it. Banking those would write a discount
  conditional on holding a specific Korean credit card into a national price
  series. The extractor reads 최적가, and takes its name from `<title>` because
  the `h1` is present but empty on every capture inspected.
- yahoo_shopping_tw's legacy template prints 建議售價, the struck-through
  suggested retail price, in class `price`, and the charged figure in
  `.priceinfo` -- $2,680 against $2,412, $30,900 against $23,900. A third
  `price` element holds a cart total of zero and `rprice` an instalment (402 is
  exactly one sixth of 2,412). Its 2019 template instead carries a single
  figure under a build-hashed `HeroInfo__mainPrice___*`, matched on the stem
  because the hash changes whenever the site is rebuilt.

Measured on 99 held-out captures none of this code was written against: 90
rows, and every banked price is rendered on its own page -- 0 of 90 unshown.
Per capture, emart_kr 0.80 corpus-wide, yahoo_shopping_tw 0.90 in 2019 and
1.00 in the legacy era, liverpool_mx 0.93 through the existing microdata tier
in 2018 and 1.00 through this one in 2025.

Against each source's whole-corpus miss volume and era mix that projects to
roughly 73k rows for emart_kr, 154k for yahoo_shopping_tw, and 249k for
liverpool_mx, which needs no new per-source code at all -- 195k of it was
already reachable and simply never refetched.

The one-decimal case in the money parser was found by the fetch driver's test,
not by the tier's own: slicing the decimal part by offset turned `6.6` into the
string `..6` and raised out of the tier, which stops the driver rather than
abstaining. The groups are matched rather than sliced now, and both that shape
and the thousands-separated one are pinned.
MSG

git --no-pager log --stat -1
