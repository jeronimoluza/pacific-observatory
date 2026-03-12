# Shared Source Docs

`src/docs/` holds shared, human-facing guidance for the source tree. Read these docs from broad to local: start in `src/README.md`, use the pipeline and CLI notes here, then drop into area-specific READMEs and local docs.

## What Belongs Here

- Cross-cutting concepts that apply across more than one domain.
- The production-facing language for stages and commands.
- Working guidance that helps people navigate the repo before they need implementation details.

## What Does Not Belong Here

- Source-specific selectors, parser rules, or one-off schemas.
- Deep flags that only make sense inside one local workflow.
- Speculative planning notes that are not tied to active code paths.

## Reading Order

- `src/docs/PIPELINE.md` - the shared `collect -> normalize -> enrich -> analyze -> publish` model.
- `src/docs/CLI.md` - the target public `po` command surface for the main workflows.
- `src/text/docs/` - text-specific details once you are inside the text pipeline.
- `src/cpi/README.md` - the price-atlas implementation entry point.
- `src/cpi/fuel_prices/README.md`, `src/cpi/price_scraping/README.md`, `src/cpi/coicopping/README.md`, and `src/cpi/price_index/README.md` - deeper price-atlas internals.

## Supporting Notes

- `src/docs/DATA.md` - shared stance on how to treat raw, normalized, analytical, and published artifacts.
- `src/docs/STANDARDS.md` - lightweight maintenance and verification rules that still apply across areas.
- `src/docs/CONTRACT.md` - boundary between shared docs and local docs.
- `src/docs/ROADMAP.md` and `src/docs/TASKS.md` - temporary shared planning notes; keep them thin or remove them when they stop helping.

## Working Rule

If a note stops helping people understand or run the pipeline, trim it, move it closer to the code that owns it, or delete it.
