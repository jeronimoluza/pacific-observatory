#!/usr/bin/env python3
"""PreToolUse Bash guard: deny destructive ops and ask on mv under data/,
outputs/. Creating objects is allowed. Parses each simple command in the
pipeline; string-level guard (not a sandbox) — `cd data && rm x` is a known
blind spot, documented in DESIGN.md."""
import json
import re
import sys

PROTECTED = re.compile(r"(?:^|[\s=('\"])(?:\./)?(?:data|outputs)/")
DESTRUCTIVE = {"rm", "rmdir", "unlink"}


def _hits_protected(segment: str) -> bool:
    return bool(PROTECTED.search(segment))


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return
    decision = reason = None
    for segment in re.split(r"&&|\|\||;|\|", cmd):
        toks = segment.strip().split()
        if not toks:
            continue
        prog = toks[0]
        if prog in DESTRUCTIVE and _hits_protected(segment):
            decision = "deny"
            reason = f"destructive '{prog}' on data/ or outputs/ is blocked"
            break
        if prog == "find" and "-delete" in toks and _hits_protected(segment):
            decision = "deny"
            reason = "find -delete on data/ or outputs/ is blocked"
            break
        if prog == "mv" and _hits_protected(segment):
            decision = "ask"
            reason = "mv touching data/ or outputs/ needs confirmation"
    if decision:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": decision,
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
