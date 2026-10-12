# Policy step (SKILL step 4)

One Sonnet agent per region x tracker. Research rules, workbook schema, taxonomy, country scope (SAR excludes AFG/PAK, EAP includes the 12-PIC view): `.claude/skills/update-fuel-crisis-policy/` and `.claude/skills/update-food-security-policy/` (`references/master_prompt.md`). This file covers only the corpus pass and the hand-off.

## Inputs the orchestrator gives each agent
Region, tracker (`fuel` | `food`), the merged run ids, a scratch out-dir root unique to region and tracker, and a WebSearch budget (session cap about 200 divided by agent count).

## (a) Corpus pass over this refresh's NEW articles
A staged run dir has the same layout as `data/text`, so `--data-root` points the scan at the delta. For each merged run, in order, with `OUT=<scratch>/<run_id>`:

1. `po text policy-discover --region <r> --data-root ~/text_staging/<run_id> --out-dir $OUT`
2. `po text policy-slice --region <r> --out-dir $OUT --old 0 --recent <N>` (every delta article is recent; N = a count above the candidate total so nothing is sampled out)
3. `po text policy-shard --region <r> --data-root ~/text_staging/<run_id> --out-dir $OUT`
4. Extract: the agent reads each shard itself and writes `$OUT/findings/<r>/shard_NN.jsonl` per `src/text/policy/extract_prompt.md` (judgement is the agent's; no classifier scripts).
5. `po text policy-assemble --region <r> --out-dir $OUT`; read its dropped-name report.
6. `po text policy-merge-workbook --region <r> --tracker <t> --out-dir $OUT --append`: writes a dated workbook edition with the new rows as Provenance=corpus. `--append` is required: every workbook already holds corpus rows from 2026-09-25, and without it the step SKIPs.

Zero candidates for a run: skip its steps 2-6 and say so. The staged dirs exist until the user runs the printed `rm`.

## (b) WebSearch pass
Then research per the tracker skill's master_prompt for measures the corpus missed, adding rows with Provenance=websearch to the same dated edition. Stay in the search budget; prefer countries where (a) found nothing.

## Agent return
One line: `<region> <tracker>: corpus <n> new rows, websearch <m> new rows, workbook <path>`. Row detail lives in the workbook; the orchestrator builds the step 6 summary from its Provenance column.
