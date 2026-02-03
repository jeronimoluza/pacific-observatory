import re
from dateutil.parser import parse
from datetime import datetime, timedelta


def handle_mixed_dates(date: str, pattern="\d+"):
    try:
        date = parse(date)
    except Exception:
        if "ago" in date:
            now = datetime.now()
            number = int(re.findall(pattern, date)[0])
            if "min" in date:
                date = now - timedelta(minutes=number)
            elif "hr" in date or "hour" in date:
                date = now - timedelta(hours=number)
    finally:
        return date
