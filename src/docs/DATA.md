# Source Tree Data

This file keeps the shared data stance for `src/` practical.

## Shared Rules

- Never delete data in `data/` casually.
- Keep existing data layouts until there is a concrete, working reason to change them.
- Document important outputs near the code that produces them.
- Use metadata, manifests, or checks only when they solve a real maintenance problem.
- Avoid introducing repo-wide artifact rules that active pipelines are not already following.

## Working Guidance

- Raw collection outputs and source evidence should be treated conservatively.
- Normalized, analytical, and published outputs can vary by area; do not force one storage pattern across all domains.
- Prefer explicit local docs for real schemas, paths, and retention behavior.
- If a new artifact becomes important to downstream work, document it where that workflow lives.

## What This File Does Not Do

- It does not require universal sidecar files.
- It does not define one schema model for every domain.
- It does not replace local data notes in `src/text/`, `src/cpi/`, or other active areas.
