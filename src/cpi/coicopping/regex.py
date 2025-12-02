import re
# Regex patterns for quantity extraction
# Amount regex: captures weight/volume (g, gm, kg, lb, lbs, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm)
AMOUNT_REGEX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(g|gm|kg|lb|lbs|oz|ml|mls|l|litre|ltrs|ltr|gallon|gal|m|cm)\b",
    re.IGNORECASE
)

# Units regex: captures count units (can, cans, pack, packs, piece, pieces, pcs, box, boxes, jar, jars, bag, bags)
UNITS_REGEX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(can|cans|pack|packs|piece|pieces|pcs|box|boxes|jar|jars|bag|bags|)\b",
    re.IGNORECASE
)

# Regex to find "(per/kg)" or "(per kg)" variations
PER_KG_REGEX = re.compile(r'\(per\s*/\s*kg\)|\(per\s*kg\)', re.IGNORECASE)

# Regex to find "(per/each)" or "(per each)" variations
PER_EACH_REGEX = re.compile(r'\(per\s*/\s*each\)|\(per\s*each\)', re.IGNORECASE)

