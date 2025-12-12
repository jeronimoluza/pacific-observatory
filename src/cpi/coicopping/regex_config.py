import re
import nltk

# Download nltk stopwords if not already available
try:
    from nltk.corpus import stopwords
    STOPWORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download('stopwords')
    from nltk.corpus import stopwords
    STOPWORDS = set(stopwords.words("english"))

# Define units once - used across all regex patterns and extraction logic
COUNT_UNITS = ['can', 'cans', 'ct', 'pack', 'packs', 'piece', 'pieces', 'pk', 'pc', 'pcs', 'box', 'boxes', 'jar', 'jars', 'bag', 'bags']
AMOUNT_UNITS = ['g', 'gm', 'kg', 'lb', 'lbs', 'oz', 'ml', 'mls', 'l', 'litre', 'ltrs', 'ltr', 'gallon', 'gal', 'm', 'cm']

# Size-related words to remove
SIZE_WORDS = ['size', 'xl', 'large', 'medium', 'sz', 'small', 'xlong', 'approx', 'aprox']

# Additional packaging/count words to remove
ADDITIONAL_UNITS = ['case', 'carton', 'bunch', 'assorted', "assortment"]

# Extend STOPWORDS with size words, additional units, and count units
STOPWORDS.update(SIZE_WORDS)
STOPWORDS.update(ADDITIONAL_UNITS)
STOPWORDS.update(COUNT_UNITS)

# Build regex patterns from unit lists
COUNT_UNITS_PATTERN = '|'.join(COUNT_UNITS)
AMOUNT_UNITS_PATTERN = '|'.join(AMOUNT_UNITS)

# Regex patterns for quantity extraction
# Amount regex: captures weight/volume units
AMOUNT_REGEX = re.compile(
    rf"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*({AMOUNT_UNITS_PATTERN})\b",
    re.IGNORECASE
)

# Units regex: captures count units
# Updated: handles optional "per/" or "per " between number and unit (e.g., "6 per/ pack")
UNITS_REGEX = re.compile(
    rf"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:per\s*/?\s*)?({COUNT_UNITS_PATTERN})\b",
    re.IGNORECASE
)

# X-separator regex: captures "number x amount" or "number x units" patterns
# Handles: "30 x 105g", "3g x 2000", "(2000 x 1g)", "x 500", "x500", "250mls x 24"
# Captures: (first_number, first_unit, second_number, second_unit)
X_SEPARATOR_REGEX = re.compile(
    rf"(?:^|\s|\()\s*(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})?\s*(?:x|×)\s*(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})?",
    re.IGNORECASE
)

# Per/kg regex: captures "per/kg", "per kg", "per/ kg", "per /kg" with or without parentheses
PER_KG_REGEX = re.compile(
    r"\(?\s*per\s*/?\s*kg\s*\)?",
    re.IGNORECASE
)

# Per/each regex: captures "per/each", "per each", "per/ each", "per /each", "per ea", "(each)" with or without parentheses
# Note: Must be specific to "each" or "ea", not just any word after "per/"
PER_EACH_REGEX = re.compile(
    r"\(?\s*per\s*/?\s*(?:each|ea)\b\s*\)?|\(\s*each\s*\)",
    re.IGNORECASE
)

