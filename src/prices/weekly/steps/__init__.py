"""Registered weekly steps. PX-10..PX-13, PX-21 and PX-25 add theirs here.

A step's runner lives in its own module here and is started as `python -m`; this
file only names it, so building a plan imports none of them.
"""

from prices.weekly.step import Step
from prices.weekly.steps._common import py_argv

STEPS: dict[str, Step] = {
    # Runs nothing: exercises mount check, disk gate, the unit and STATUS end to end.
    "noop": Step("noop", "256M", lambda ctx: ["true"]),
    # PX-10. prepare admits countries by bytes in flight; japan alone is ~13 GB resident.
    "enrich": Step(
        "enrich", "20G", lambda ctx: py_argv("prices.weekly.steps.enrich", ctx)
    ),
    # PX-11
    "fx": Step("fx", "2G", lambda ctx: py_argv("prices.weekly.steps.fx", ctx)),
    # PX-12. Rents nothing: stops at the need list, universe and pod plan.
    "embed": Step(
        "embed", "12G", lambda ctx: py_argv("prices.weekly.steps.embed", ctx)
    ),
}
