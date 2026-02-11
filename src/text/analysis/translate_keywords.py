"""
Translate English keywords to all supported languages using googletrans.

Only translates missing keys, files, and language folders — existing
translations are never overwritten.

Outputs translated keyword files to src/text/analysis/keywords/ with the format:
    {"category": {"english_term": "translated_term", ...}, ...}

English files are copied as-is (flat lists).

Usage:
    poetry run python src/text/analysis/translate_keywords.py
"""

import asyncio
import json
from pathlib import Path

from googletrans import Translator
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
KEYWORDS_DIR = _SCRIPT_DIR / "keywords"

# Delay between API calls to avoid rate limiting (seconds)
DELAY_BETWEEN_CALLS = 0.5

# ---------------------------------------------------------------------------
# Language mapping: folder_name -> googletrans language code
# ---------------------------------------------------------------------------
FOLDER_TO_GTRANS = {
    "chinese_simplified": "zh-cn",
    "chinese_traditional": "zh-tw",
    "fijian": "fij",
    "filipino": "fil",
    "fr": "fr",
    "hindi": "hi",
    "indo": "id",
    "japanese": "ja",
    "km": "km",
    "korean": "ko",
    "lao": "lo",
    "malay": "ms",
    "maori": "mi",
    "marshallese": "mah",
    "mn": "mn",
    "samoan": "sm",
    "tamil": "ta",
    "tetum": "tet",
    "thai": "th",
    "tok_pisin": "tpi",
    "tongan": "ton",
    "vietnamese": "vi",
}

# Languages not supported by googletrans — translations for these must be
# generated manually using AI and the English keywords as a reference.
UNSUPPORTED_LANGUAGES = {
    "bislama",
    "palauan",
    "solomon_islands_pijin",
}

# Per-language custom Google Translate service URLs
FOLDER_SERVICE_URLS = {
    "fijian": ["translate.google.com.fj"],
}

# Terms that must keep the English value (proper nouns, acronyms, brands).
# Matched case-insensitively against the English key.
PROPER_NOUNS = {
    # Acronyms / initialisms
    "imf",
    "ibrd",
    "ida",
    "ifc",
    "adb",
    "afdb",
    "idb",
    "ebrd",
    "oecd",
    "ilo",
    "who",
    "wto",
    "un",
    "fdi",
    "cpi",
    "gdp",
    "forex",
    "s&p",
    "pboc",
    "mofcom",
    "cpc",
    "ccp",
    "ndrc",
    "ustr",
    "mps",
    "covid",
    "covid-19",
    # Brand / org names
    "fitch",
    "moody's",
    "moody\u2019s",
    "standard and poor's",
    "standard & poor's",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_json(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Ensure trailing newline
    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n")


def _count_missing(en_data: dict, existing_data: dict) -> int:
    """Count English terms not yet present as keys in existing_data."""
    count = 0
    for category, en_terms in en_data.items():
        existing_cat = existing_data.get(category, {})
        for term in en_terms:
            if term not in existing_cat:
                count += 1
    return count


# ---------------------------------------------------------------------------
# Core translation
# ---------------------------------------------------------------------------
def _get_translator(folder_name: str) -> Translator:
    """Return a Translator with a custom service_url if configured."""
    service_urls = FOLDER_SERVICE_URLS.get(folder_name)
    if service_urls:
        return Translator(service_urls=service_urls)
    return Translator()


async def _translate_term(translator: Translator, term: str, lang_code: str) -> str:
    """Translate a single English term to the target language."""
    try:
        result = await translator.translate(term, src="en", dest=lang_code)
        return result.text if result and result.text else term
    except Exception as e:
        print(f"\n  ⚠ Translation error for '{term}' → {lang_code}: {e}")
        return term


async def translate_keywords() -> int:
    """
    Incremental check: translate only missing English terms in keywords/.

    Discovers all .json files in keywords/en/ and ensures every key
    exists in every language folder. Existing translations are never
    overwritten.

    Returns the number of newly translated terms.
    """
    en_dir = KEYWORDS_DIR / "en"
    if not en_dir.exists():
        print(f"Error: English source directory not found: {en_dir}")
        return 0

    # Discover all JSON files from the English source-of-truth folder
    json_files = sorted(p.name for p in en_dir.glob("*.json"))
    if not json_files:
        print(f"Error: No JSON files found in {en_dir}")
        return 0

    # Load English data
    en_data = {}
    for jf in json_files:
        en_data[jf] = load_json(en_dir / jf)

    # Inform user about unsupported languages
    if UNSUPPORTED_LANGUAGES:
        print(
            f"\nNote: The following languages are not supported by googletrans "
            f"and will be skipped: {', '.join(sorted(UNSUPPORTED_LANGUAGES))}."
            f"\nTranslations for these languages should be generated using AI "
            f"and the English keywords as a reference.\n"
        )

    # Count total missing across all languages
    total_missing = 0
    for folder_name in FOLDER_TO_GTRANS:
        lang_dir = KEYWORDS_DIR / folder_name
        for jf in json_files:
            existing_path = lang_dir / jf
            existing = load_json(existing_path) if existing_path.exists() else {}
            total_missing += _count_missing(en_data[jf], existing)

    if total_missing == 0:
        print("✓ All translations are up to date.")
        return 0

    print(f"Found {total_missing} missing translations. Translating...")
    pbar = tqdm(total=total_missing, desc="Translating missing", unit="term")
    translated_count = 0

    for folder_name, lang_code in FOLDER_TO_GTRANS.items():
        lang_dir = KEYWORDS_DIR / folder_name
        lang_dir.mkdir(parents=True, exist_ok=True)
        translator = _get_translator(folder_name)

        for jf in json_files:
            existing_path = lang_dir / jf
            existing = load_json(existing_path) if existing_path.exists() else {}
            changed = False

            for category, en_terms in en_data[jf].items():
                if category not in existing:
                    existing[category] = {}
                cat_dict = existing[category]

                for term in en_terms:
                    if term not in cat_dict:
                        if term.lower() in PROPER_NOUNS:
                            cat_dict[term] = term
                        else:
                            translation = await _translate_term(
                                translator, term, lang_code
                            )
                            cat_dict[term] = translation
                            await asyncio.sleep(DELAY_BETWEEN_CALLS)
                        translated_count += 1
                        changed = True
                        pbar.update(1)

            if changed:
                save_json(existing, existing_path)

    pbar.close()
    print(f"✓ Translated {translated_count} missing terms.")
    return translated_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(translate_keywords())
