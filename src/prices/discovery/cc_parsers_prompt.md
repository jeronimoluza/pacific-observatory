You are the unattended {{WEEK}} Common Crawl parser stage on a8, started by cron. No human is
watching: never wait for input, never ask questions. Decide, note the decision in the summary,
and continue.

Input: `{{OUT}}/cc/needs_parser.txt` (sources whose archived pages mostly did not parse) and
`{{OUT}}/cc/cc_summary.md`. Saved misses: `{{OUT}}/cc/misses/`. Work in this worktree
(`~/po-worktrees/discovery-onboard`, branch `prices/discovery-onboard`); scratch in
`~/scratch/cc_parsers/{{WEEK}}/`.

CLI (run from `src/`):
`PO_CC_INDEX_DIR=/mnt/backup5tb/cc_index ~/venv/bin/python -c "import sys;sys.argv=['po','prices','cc-weekly']+sys.argv[1:];from cli import main;main()" <args>`

1. Sample: write each listed stem to `~/scratch/cc_parsers/{{WEEK}}/<stem>.txt`, then
   `<CLI> --sources <that file> --retry-misses {{OUT}}/cc/misses --sample-misses 40
   --data-root /home/jeronimoluza/po/data/prices --work ~/scratch/cc_parsers/{{WEEK}}/samples`.
   Pages land as `samples/<stem>/NNN.html` + `index.jsonl`, spread across eras.
2. Budget: at most 10 sources, largest miss count first. One Opus worker per source
   (`model: opus`), 4 in parallel. Give each worker steps 3-5 and the rules below.
3. Worker: read files 000-019 (the training half). Decide first whether these pages carry the
   product's own price in the HTML at all. If they do not (not product pages, price rendered by
   JavaScript, login wall, out-of-stock shells), write no parser: verdict `dead` with the reason.
4. Otherwise write `src/prices/price_scraping/archived_weekly/<stem>.py` exposing
   `extract(html: str, url: str) -> list[dict]`. Build each row with
   `from ..archived import price_row` (`price_row(name, price, url, currency)`; returns None to
   reject) and `normalize_price`. Parse with `lxml.html.fromstring`, after stripping a leading
   `<?xml ...?>` declaration: lxml rejects a str that carries one, and the tier swallows the error,
   so the parser silently returns nothing (W41, manxinspirations_im). Read
   `archived_spar_zw.py` and `archived_bysource.py` for the house style (those take an lxml doc
   and return one row; yours take the HTML string and return a list). The currency is the
   source manifest's `currency:`; never read it from the page. Module docstring: what the
   archived markup looks like, with a short HTML excerpt, and which eras it covers.
5. Verify on the held-out half, files 020-039: `<CLI> --check ~/scratch/cc_parsers/{{WEEK}}/samples/<stem>`.
   Then open 5 priced held-out pages and confirm each row's price is that product's own current
   price (not a struck-through, list, member, per-unit, shipping or related-product price) and
   its name is that product's name. Any wrong row: fix and re-check, or abstain on that layout.
   Verdict `fixed` only with zero wrong rows in the spot check and a held-out priced share that
   clearly beats 0; otherwise `partial` (still keep it if every spot-checked row is right) or
   `dead`. Report: train priced, held-out priced, spot-check result, eras covered.

Rules for everyone:
- Abstain rather than guess: a wrong price is worse than a missing one, because nothing
  downstream can detect it.
- Touch only `src/prices/price_scraping/archived_weekly/<stem>.py` files. Never edit other
  code, configs, `countries.yaml` or `regions.yaml`. Never delete files. Never write tests.
- No WebSearch, no ddgs, no live-site fetching: the archived samples are the whole input.

When every worker is done:
- Run `--check` over `~/scratch/cc_parsers/{{WEEK}}/samples` once more with all parsers in place.
- Commit only the new `archived_weekly/*.py` files for `fixed` and `partial` sources, one commit
  (`feat(prices/cc): archived parsers for N weekly sources ({{WEEK}})`), no attribution lines,
  then `git push origin prices/discovery-onboard`. Never push any other branch, never merge.
- Write `{{OUT}}/parsers_fixed.txt`: the committed stems, one per line (the wrapper then re-runs
  their saved misses with `--retry-misses` and lands what they recover).
- Write `{{OUT}}/cc_parsers_summary.md`: source | verdict | train priced | held-out priced |
  spot check | eras | notes; the commit hash; and decisions a human should review.
