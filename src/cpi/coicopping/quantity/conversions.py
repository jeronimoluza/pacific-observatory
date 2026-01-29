"""
Unit conversion constants and mappings for standardizing measurements.

Provides conversion factors to convert various units of measurement to standard units:
- Weight: to kilogram (kg)
- Volume: to litre (lt)
- Length: to metre (mt)
"""

# Weight conversions to kg
WEIGHT_TO_KG = {
    "kg": 1.0,
    "g": 0.001,
    "gm": 0.001,
    "oz": 0.0283495,  # 1 oz = 28.3495 g
    "lb": 0.453592,  # 1 lb = 453.592 g
    "lbs": 0.453592,
}

# Volume conversions to litre (lt)
VOLUME_TO_LT = {
    "l": 1.0,
    "litre": 1.0,
    "ltr": 1.0,
    "ltrs": 1.0,
    "ml": 0.001,
    "mls": 0.001,
    "gallon": 3.78541,  # 1 US gallon = 3.78541 litres
    "gal": 3.78541,
}

# Length conversions to metre (mt)
LENGTH_TO_MT = {
    "m": 1.0,
    "cm": 0.01,
    "ft": 0.3048,  # 1 ft = 0.3048 m
    "feet": 0.3048,
    "in": 0.0254,  # 1 inch = 0.0254 m
    "inch": 0.0254,
    "inches": 0.0254,
}

# Combined mapping: unit -> (conversion_factor, standard_unit)
UNIT_CONVERSIONS = {}
for unit, factor in WEIGHT_TO_KG.items():
    UNIT_CONVERSIONS[unit] = (factor, "kg")
for unit, factor in VOLUME_TO_LT.items():
    UNIT_CONVERSIONS[unit] = (factor, "lt")
for unit, factor in LENGTH_TO_MT.items():
    UNIT_CONVERSIONS[unit] = (factor, "mt")
