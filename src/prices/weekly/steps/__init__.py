"""Registered weekly steps. PX-10..PX-13, PX-21 and PX-25 add theirs here."""

from prices.weekly.step import Step

STEPS: dict[str, Step] = {
    # Runs nothing: exercises mount check, disk gate, the unit and STATUS end to end.
    "noop": Step("noop", "256M", lambda ctx: ["true"]),
}
