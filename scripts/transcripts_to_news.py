"""Turn Studio Kalangou whisper transcripts into a text-pipeline news.csv.

One transcript = one daily radio bulletin = one "article". The filename carries
the date and a slug of the lead story; the body is the timestamped segments with
their timecodes stripped.

Usage:
    python scripts/transcripts_to_news.py <transcript_dir> <out_news_csv>
"""

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEG = re.compile(r"^\[\d{2}:\d{2}:\d{2}\.\d+ -> \d{2}:\d{2}:\d{2}\.\d+\]\s*")
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+?)\.faster-whisper-large-v3\.txt$")

CSV_COLUMNS = [
    "url",
    "title",
    "date",
    "body",
    "tags",
    "source",
    "country",
    "language",
    "_scraped_at",
]


def main() -> None:
    src_dir, out_csv = Path(sys.argv[1]), Path(sys.argv[2])
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    rows = []
    for f in sorted(src_dir.glob("*.txt")):
        m = NAME.match(f.name)
        if not m:
            print(f"skip (unparsed name): {f.name}")
            continue
        date, slug = m.group(1), m.group(2)
        body = " ".join(
            SEG.sub("", line).strip()
            for line in f.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        rows.append(
            {
                "url": f"studio_kalangou://{date}/{slug}",
                "title": slug.replace("-", " "),
                "date": date,
                "body": body,
                "tags": "",
                "source": "studio_kalangou",
                "country": "niger",
                "language": "fr",
                "_scraped_at": now,
            }
        )

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} rows -> {out_csv}")
    print(f"date range: {rows[0]['date']} .. {rows[-1]['date']}")
    print(f"mean body chars: {sum(len(r['body']) for r in rows) // len(rows)}")


if __name__ == "__main__":
    main()
