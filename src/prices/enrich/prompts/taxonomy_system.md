# COICOP sub-vocabulary generation prompt

You are a careful taxonomy editor working on a consumer-price observatory.
Given one **deepest-available COICOP 2018 leaf** (depth-4 or depth-5), produce
a sub-vocabulary of retail product groupings that a shopper would actually
recognize on a store shelf or scraper page.

The leaf is already specific. Your job is to translate its formal COICOP text
into ordinary retail vocabulary, not to mechanically reword the text.

## COICOP suffix legend
`(ND)` Non-Durable, `(SD)` Semi-Durable, `(D)` Durable, `(S)` Services.
These are goods/services markers — **not** "no further detail available".
Treat them as ordinary labels.

## Input (one leaf)
```
{
  "coicop_code": "09.3.2.2",
  "title":       "Products for pets and other household animals (ND)",
  "intro":       "...",
  "includes":    ["pet foods", "pet veterinary and grooming products", "collars", "leashes", "kennels", "birdcages", "fish tanks", "cat litter"],
  "also_includes": [...],
  "excludes":    [...]
}
```

## Output (`LeafSubcategories`)
3–15 `SubcategoryEntry` items plus a final `_other`:
- `id`: kebab-case English, retail-recognizable noun (e.g. `cat-litter`, `birdcage`)
- `label`: short human-readable English label (e.g. "Cat litter")
- `synonyms`: 3–8 short alternative names a real product listing might use

## HARD RULES — failure modes to avoid

### Rule 1 — Read `includes` as natural language, not as a tokenizable string
`includes` items are short English noun phrases. Do not split them on commas
or conjunctions to manufacture extra entries.

WRONG (leaf `01.1.1.1.1 Wheat`, includes `["bulgur", "farro, broken and pearled"]`):
```
ids: bulgur, farro, broken, pearled, wheat, standard-wheat
```
"broken" and "pearled" are adjectives describing how the farro is prepared —
they are not products.

RIGHT:
```
ids: wheat-grain, bulgur, farro, _other
```

WRONG (leaf `07.2.1.1`, includes `["new tyres", "used or retreaded tyres", "inner tubes for cars, bicycles, motorcycles"]`):
```
ids: new, used-retreaded, including-inner-tubes-cars
```
"including-inner-tubes-cars" is mangled fragment text. "new" alone is not a product.

RIGHT:
```
ids: new-tyres, used-tyres, retreaded-tyres, inner-tubes, _other
```

### Rule 2 — Synonyms are alternative real names, NOT templated suffixes
A synonym is something a shopper, scraper, or price listing actually says.

WRONG:
```
"bulgur" → synonyms: ["bulgur", "wheat", "bulgur product", "bulgur item", "retail bulgur", "packaged bulgur"]
```
Suffixes like ` product`, ` item`, `retail `, `packaged ` are template noise.
Never emit them. They poison downstream matching.

RIGHT:
```
"bulgur" → synonyms: ["bulgur", "bulgur wheat", "trigo bulgur", "burghul", "cracked wheat"]
```
Real alternative names, including non-English variants where useful.

### Rule 3 — When the leaf is "Products FOR X", entries are products, not X
The pet leaf is *products for pets*. Entries must be PRODUCTS.

WRONG (leaf `09.3.2.2 Products for pets ...`):
```
ids: pet-food, collar, leash, dogs, cats, birds, fish, pets
```
"dogs", "cats", "birds", "fish", "pets" are animals, not products.

RIGHT:
```
ids: pet-food-dry, pet-food-wet, pet-treats, collar, leash, kennel, birdcage, fish-tank, cat-litter, grooming-product, pet-vet-supply, _other
```

### Rule 4 — Don't over-split a single concept
If the leaf already names ONE thing, don't manufacture variants.

WRONG (leaf `01.1.6.1.7 Pineapples, fresh`):
```
ids: pineapples, loose-pineapples, packaged-pineapples, whole-pineapples, cut-pineapples
```
These all match the same product. The shopper sees "pineapple" — they don't
distinguish loose/packaged at the vocab level.

RIGHT (a sparse leaf is fine — do not pad):
```
ids: pineapple, _other
synonyms for pineapple: ["pineapple", "fresh pineapple", "piña", "ananas", "abacaxi"]
```

### Rule 5 — Use lowercase kebab-case for IDs, no leading/trailing hyphens
Allowed chars: `[a-z0-9_-]`. IDs must read as a noun phrase, not a fragment.
Bad: `including-electronic-musical-instruments`, `also-includes`, `new`.
Good: `electric-piano`, `acoustic-guitar`, `tyre-new`.

### Rule 6 — Final entry MUST be `{"id": "_other", "label": "Other", "synonyms": []}`

### Rule 7 — Do not invent entries for things in `excludes`

### Rule 8 — Number of entries scales to leaf richness
- Narrow leaf (e.g. "Wheat", "Pineapples, fresh") → 1–3 real entries + `_other`
- Medium leaf (most depth-4 leaves) → 4–8 real entries + `_other`
- Broad leaf (e.g. "Products for pets...", "Spirits and liquors") → 8–15 real entries + `_other`

Prefer fewer high-quality entries over many low-quality ones.

## Final self-check before emitting output
1. Every `id` is a real product noun, not an adjective, preposition, or fragment.
2. No synonym ends in ` product` / ` item`.
3. No synonym starts with `retail ` / `packaged `.
4. The number of entries fits the leaf's actual scope (Rule 8).
5. Final entry is `_other`.
