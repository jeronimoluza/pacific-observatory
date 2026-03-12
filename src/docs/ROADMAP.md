# Source Tree Roadmap

This roadmap is intentionally small. The current direction is to improve the code we already run instead of designing a larger structure around it.

## Direction

- Keep `src/` centered on the current working domains: `text/`, `cpi/`, and `tourism/`.
- Make the shared docs useful enough to help navigation, but not heavy enough to slow work down.
- Fix real workflow pain in active pipelines before proposing new structure.

## Near-Term Focus

- Stabilize and simplify the working paths in `src/text/`, `src/cpi/fuel_prices/`, and `src/cpi/price_scraping/`.
- Keep commands and verification close to the code that uses them.
- Remove planning docs that describe systems we are not actually running.

## Longer-Term Rule

- Revisit structural changes only after repeated evidence that the current layout is blocking active work.

## Not The Plan

- No speculative migration tree.
- No universal sidecar or contract rollout by default.
- No rename or reorganization without active code moving with it.
