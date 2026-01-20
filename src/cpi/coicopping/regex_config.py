import re
import nltk

# Download nltk stopwords if not already available
try:
    from nltk.corpus import stopwords

    STOPWORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords")
    from nltk.corpus import stopwords

    STOPWORDS = set(stopwords.words("english"))

# Define units once - used across all regex patterns and extraction logic
COUNT_UNITS = [
    "can",
    "cans",
    "ct",
    "count",
    "pack",
    "packs",
    "piece",
    "pieces",
    "pk",
    "pc",
    "pcs",
    "box",
    "boxes",
    "jar",
    "jars",
    "bag",
    "bags",
    "roll",
    "rolls",
    "sheet",
    "sheets",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "sachet",
    "sachets",
    "stick",
    "sticks",
    "bar",
    "bars",
    "bottle",
    "bottles",
    "tube",
    "tubes",
    "serving",
    "servings",
    "dose",
    "doses",
]
AMOUNT_UNITS = [
    "g",
    "gm",
    "kg",
    "lb",
    "lbs",
    "oz",
    "ml",
    "mls",
    "l",
    "litre",
    "ltrs",
    "ltr",
    "gallon",
    "gal",
    "m",
    "cm",
    "ft",
    "feet",
    "in",
    "inch",
    "inches",
]

# Size-related words to remove
SIZE_WORDS = [
    "size",
    "xl",
    "large",
    "medium",
    "sz",
    "small",
    "xlong",
    "approx",
    "aprox",
]

# Additional packaging/count words to remove
ADDITIONAL_UNITS = ["case", "carton", "bunch", "assorted", "assortment"]

# Extend STOPWORDS with size words, additional units, and count units
STOPWORDS.update(SIZE_WORDS)
STOPWORDS.update(ADDITIONAL_UNITS)
STOPWORDS.update(COUNT_UNITS)

# Build regex patterns from unit lists
COUNT_UNITS_PATTERN = "|".join(COUNT_UNITS)
AMOUNT_UNITS_PATTERN = "|".join(AMOUNT_UNITS)

# Regex patterns for quantity extraction
# Amount regex: captures weight/volume units
# Handles: "9kg", "9-15kg", "9kg-15kg"
AMOUNT_REGEX = re.compile(
    rf"(\d+(?:\.\d+)?)\s*(?:{AMOUNT_UNITS_PATTERN})?\s*-\s*(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})\b|(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})\b",
    re.IGNORECASE,
)

# Units regex: captures count units
# Updated: handles optional "per/" or "per " between number and unit (e.g., "6 per/ pack")
# Handles: "6 pack", "6-10 pack", "6 pack-10 pack"
UNITS_REGEX = re.compile(
    rf"(\d+(?:\.\d+)?)\s*(?:{COUNT_UNITS_PATTERN})?\s*-\s*(\d+(?:\.\d+)?)\s*(?:per\s*/?\s*)?({COUNT_UNITS_PATTERN})\b|(\d+(?:\.\d+)?)\s*(?:per\s*/?\s*)?({COUNT_UNITS_PATTERN})\b",
    re.IGNORECASE,
)

# X-separator regex: captures "number x amount" or "number x units" patterns
# Handles: "30 x 105g", "3g x 2000", "(2000 x 1g)", "x 500", "x500", "250mls x 24"
# Captures: (first_number, first_unit, second_number, second_unit)
X_SEPARATOR_REGEX = re.compile(
    rf"(?:^|\s|\()\s*(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})?\s*(?:x|×)\s*(\d+(?:\.\d+)?)\s*({AMOUNT_UNITS_PATTERN})?",
    re.IGNORECASE,
)

# Per/kg regex: captures "per/kg", "per kg", "per/ kg", "per /kg" with or without parentheses
PER_KG_REGEX = re.compile(r"\(?\s*per\s*/?\s*kg\s*\)?", re.IGNORECASE)

# Per/each regex: captures "per/each", "per each", "per/ each", "per /each", "per ea", "(each)" with or without parentheses
# Note: Must be specific to "each" or "ea", not just any word after "per/"
PER_EACH_REGEX = re.compile(
    r"\(?\s*per\s*/?\s*(?:each|ea)\b\s*\)?|\(\s*each\s*\)", re.IGNORECASE
)

# =============================================================================
# PROMOTION AND BUNDLE DETECTION
# =============================================================================

# Keywords that indicate promotional or bundle products
PROMOTION_KEYWORDS = [
    "2 in 1",
    "3 in 1",
    "4 in 1",
    "5 in 1",
    "6 in 1",
    "bundle",
    "combo",
    "deal",
    # "carton" removed - often refers to packaging, not promotions
    "bulk",
    "bonus",
    # Note: "free" is handled specially with false positive detection
    "free",
    "promo",
    # "special" removed - too common in product names
    "offer",
    "save",
    "value pack",
    "multi-pack",
    "multipack",
    "family pack",
    # "economy" removed - often a product line, not promotion
    # "mega" removed - often a brand name or size descriptor
    # "jumbo" removed - often a size descriptor, not promotion
    "twin pack",
    "twin-pack",
    "triple pack",
    "triple-pack",
]

# Regex patterns for promotional products
PROMOTION_PATTERNS = [
    r"\bbuy\s+\d+\s+get\s+\d+\b",  # "buy 2 get 1"
    r"\d+\s+for\s+\$?\d+",  # "3 for $10"
    r"\bget\s+\d+\s+free\b",  # "get 1 free"
    r"\b\d+%\s*off\b",  # "20% off"
    r"\bsave\s+\$?\d+",  # "save $5"
    r"\+\s*\d+\s*%?\s*(?:extra|free|bonus)\b",  # "+50% extra"
    r"\bextra\s+\d+\s*%?\b",  # "extra 50%"
]

# Compile promotion patterns
PROMOTION_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in PROMOTION_PATTERNS]

# =============================================================================
# ADDITIVE PATTERNS (bonus quantities)
# =============================================================================

# Patterns that indicate additive/bonus quantities
ADDITIVE_PATTERNS = [
    r"\+\s*\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|mls|l|oz|lb)\b",  # "+50g", "+ 100ml"
    r"\bbonus\s+\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|mls|l|oz|lb)?\b",  # "bonus 50g"
    r"\bextra\s+\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|mls|l|oz|lb|%)\b",  # "extra 100g"
    r"\bfree\s+\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|mls|l|oz|lb)?\b",  # "free 50g"
    r"\+\s*\d+\s*%\s*(?:free|extra|bonus|more)?\b",  # "+25% free"
    r"\b\d+(?:\.\d+)?\s*%\s*(?:free|extra|bonus|more)\b",  # "25% extra"
]

# =============================================================================
# RANGE PATTERN
# =============================================================================

# Generic range pattern for detecting ranges in product names
RANGE_PATTERN = r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|mls|l|oz|lb|pack|packs|pc|pcs|piece|pieces)?\b"

# =============================================================================
# FOOD COUNT KEYWORDS
# =============================================================================

# Keywords that indicate food items typically sold by count (eggs, bread, etc.)
# These are used to determine if count-only products should be classified as resolved
FOOD_COUNT_KEYWORDS = [
    # Eggs
    "egg",
    "eggs",
    # Bread and baked goods
    "bread",
    "loaf",
    "loaves",
    "bun",
    "buns",
    # Note: "roll/rolls" removed - too ambiguous (bread rolls vs paper rolls)
    # "bread rolls" will still match on "bread"
    "bagel",
    "bagels",
    "croissant",
    "croissants",
    "muffin",
    "muffins",
    "donut",
    "donuts",
    "doughnut",
    "doughnuts",
    "pastry",
    "pastries",
    "scone",
    "scones",
    # Fruits (commonly sold by count)
    "apple",
    "apples",
    "orange",
    "oranges",
    "banana",
    "bananas",
    "avocado",
    "avocados",
    "lemon",
    "lemons",
    "lime",
    "limes",
    "mango",
    "mangoes",
    "mangos",
    "coconut",
    "coconuts",
    "pineapple",
    "pineapples",
    "papaya",
    "papayas",
    "watermelon",
    "watermelons",
    "melon",
    "melons",
    "kiwi",
    "kiwis",
    "peach",
    "peaches",
    "pear",
    "pears",
    "plum",
    "plums",
    "grapefruit",
    "grapefruits",
    # Vegetables (commonly sold by count)
    "onion",
    "onions",
    "potato",
    "potatoes",
    "tomato",
    "tomatoes",
    "cucumber",
    "cucumbers",
    "lettuce",
    "cabbage",
    "cabbages",
    "corn",
    "eggplant",
    "eggplants",
    "pepper",
    "peppers",
    "capsicum",
    "capsicums",
    "carrot",
    "carrots",
    "garlic",
    "head",  # head of lettuce/cabbage
    # Other food items
    "pie",
    "pies",
    "cake",
    "cakes",
    "cookie",
    "cookies",
    "biscuit",
    "biscuits",
    "tart",
    "tarts",
    "pizza",
    "pizzas",
    "wrap",
    "wraps",
    "tortilla",
    "tortillas",
    "burger",
    "burgers",
    "patty",
    "patties",
    "sausage",
    "sausages",
    "chicken",  # whole chicken
    "turkey",
    "duck",
]
