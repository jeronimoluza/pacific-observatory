# Source Tree Standards

These are the shared standards for keeping `src/` maintainable without adding bureaucracy.

## Core Standards

- Prefer working code, tests, and commands over planning structures.
- Keep shared docs small and operational.
- Use the nearest README or module doc for detailed local truth.
- Delete stale docs when they stop helping.
- Avoid adding new directory layers unless they hold real code.

## Documentation Standards

- `src/README.md` should stay a short navigation guide.
- `src/docs/*.md` should cover only cross-cutting guidance that is still actively useful.
- Local docs should explain real commands, outputs, and caveats.
- If a change affects how people run or find code, update the nearest relevant doc in the same change.

## Verification Standards

- Validate with the smallest command, test, or smoke check that proves the change.
- Do not broaden verification just to satisfy documentation structure.
- If a doc describes a command, make sure the command still works.

## Anti-Patterns

- Writing migration plans without code moving.
- Creating duplicate roadmaps across subtrees.
- Keeping docs that describe an idealized structure instead of the current one.
- Requiring metadata or sidecars everywhere when only one workflow needs them.
