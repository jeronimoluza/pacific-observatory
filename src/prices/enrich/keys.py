import re

_NORM_RE = re.compile(r"[\W_]+", flags=re.UNICODE)


def norm_key(s) -> str:
    return _NORM_RE.sub(" ", str(s).lower()).strip()
