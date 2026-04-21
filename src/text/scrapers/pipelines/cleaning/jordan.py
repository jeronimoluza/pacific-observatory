"""Cleaning functions for Jordanian newspapers."""

import re
from .registry import register_cleaner

_ARABIC_MONTHS = {
    "يناير": 1,
    "كانون الثاني": 1,
    "فبراير": 2,
    "شباط": 2,
    "مارس": 3,
    "آذار": 3,
    "أبريل": 4,
    "إبريل": 4,
    "نيسان": 4,
    "مايو": 5,
    "أيار": 5,
    "يونيو": 6,
    "حزيران": 6,
    "يوليو": 7,
    "تموز": 7,
    "أغسطس": 8,
    "آب": 8,
    "سبتمبر": 9,
    "أيلول": 9,
    "أكتوبر": 10,
    "تشرين الأول": 10,
    "نوفمبر": 11,
    "تشرين الثاني": 11,
    "ديسمبر": 12,
    "كانون الأول": 12,
}


@register_cleaner
def clean_addustour_date(date_str: str) -> str:
    """Parse Ad-Dustour Arabic date to YYYY-MM-DD.

    Input example: 'نشر في:الخميس 16 نيسان/أبريل 2026. 11:55 مـساءً'
    """
    if not date_str:
        return date_str

    year_match = re.search(r"(20\d{2})", date_str)
    if not year_match:
        return date_str
    year = year_match.group(1)

    month = None
    for name, num in _ARABIC_MONTHS.items():
        if name in date_str:
            month = num
            break

    if month is None:
        return date_str

    day_match = re.search(r"(\d{1,2})\s", date_str)
    if not day_match:
        return date_str
    day = int(day_match.group(1))

    return f"{year}-{month:02d}-{day:02d}"
