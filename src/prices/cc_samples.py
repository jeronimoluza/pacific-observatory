"""Keep a few archived pages per year so a broken parser can be repaired offline.

Nothing else in the pipeline retains raw HTML -- ``_save_item`` writes only the
extracted fields -- so diagnosing "why did this source stop parsing in 2021"
otherwise means a second Common Crawl pass just to look at a page. The WARC
byte fetch is the expensive part of a run, and paying it twice to *diagnose*
before paying it a third time to *fix* is the cost this avoids.

Only pages that extracted nothing are kept. A page that parsed needs no
repair, so storing it buys nothing, and the consequence is that disk use
scales with how broken the corpus is: a source whose parser works everywhere
stores zero bytes.

Samples are capped per year rather than per source because the failure being
chased is almost always a site redesign, which is a boundary in time. Three
pages either side of it is enough to write a selector against; three thousand
is not more enough.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Dict

DEFAULT_PER_YEAR = 3
# Archived product pages run 50-200 KB. The tail past this is inlined base64
# images and analytics payloads, which no parser reads.
DEFAULT_MAX_BYTES = 400_000


class SampleKeeper:
    """Thread-safe, resumable per-year cap on retained HTML."""

    def __init__(
        self,
        root: Path,
        per_year: int = DEFAULT_PER_YEAR,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.root = Path(root)
        self.per_year = per_year
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}
        self._scanned = False

    def _scan(self) -> None:
        """Count what a previous run already kept, so reruns do not re-fill."""
        if self._scanned:
            return
        self._scanned = True
        if not self.root.exists():
            return
        for child in self.root.iterdir():
            if child.is_dir():
                self._counts[child.name] = sum(1 for _ in child.glob("*.html"))

    def offer(self, html: str, url: str, timestamp: str) -> bool:
        """Retain this page if its year still has room. Returns whether it was."""
        year = str(timestamp)[:4]
        if len(year) != 4 or not year.isdigit():
            return False
        with self._lock:
            self._scan()
            if self._counts.get(year, 0) >= self.per_year:
                return False
            self._counts[year] = self._counts.get(year, 0) + 1
            year_dir = self.root / year
            year_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(f"{url}{timestamp}".encode()).hexdigest()[:16]
            path = year_dir / f"{timestamp}_{digest}.html"
            with open(path, "w", encoding="utf-8", errors="replace") as fh:
                fh.write(html[: self.max_bytes])
            # The filename cannot carry the URL, and the URL is what tells a
            # parser author which template the page is.
            with open(self.root / "manifest.jsonl", "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {"url": url, "timestamp": timestamp, "file": path.name},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        return True
