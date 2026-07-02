#!/usr/bin/env python3
"""PreToolUse Bash guard: deny destructive ops and ask on mv under data/,
outputs/. Creating objects is allowed. Parses each simple command in the
pipeline; string-level guard (not a sandbox) — `cd data && rm x` is a known
blind spot, documented in .planning/base_items_candidate_green/DESIGN.md."""
import json
import re
import sys

DESTRUCTIVE = {"rm", "rmdir", "unlink"}
WRAPPERS = {
    "sudo",
    "env",
    "command",
    "nice",
    "nohup",
    "stdbuf",
    "setsid",
    "ionice",
    "doas",
    "time",
}
_PROTECTED_ARG = re.compile(r"(?:^|/)(?:data|outputs)(?:/|$)")


def _strip_arg(arg: str) -> str:
    arg = arg.strip("'\"")
    arg = re.sub(r"^\d*(?:>>|>|<)", "", arg)  # drop redirect prefix (2>, >, >>, <)
    if arg.startswith("./"):
        arg = arg[2:]
    return arg


def _hits_protected(toks: list[str]) -> bool:
    return any(_PROTECTED_ARG.search(_strip_arg(t)) for t in toks)


def _identify_prog(toks: list[str]) -> str | None:
    i = 0
    while i < len(toks):
        tok = toks[i]
        if re.fullmatch(r"\w+=.*", tok):  # env-assignment prefix
            i += 1
            continue
        if tok in WRAPPERS:
            i += 1
            if tok == "env":  # env may be followed by WORD=... assignments
                while i < len(toks) and re.fullmatch(r"\w+=.*", toks[i]):
                    i += 1
            continue
        return tok
    return None


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
        prog = _identify_prog(toks)
        if prog is None:
            continue
        if prog in DESTRUCTIVE and _hits_protected(toks):
            decision = "deny"
            reason = f"destructive '{prog}' on data/ or outputs/ is blocked"
            break
        if prog == "find" and "-delete" in toks and _hits_protected(toks):
            decision = "deny"
            reason = "find -delete on data/ or outputs/ is blocked"
            break
        if prog == "mv" and _hits_protected(toks):
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
