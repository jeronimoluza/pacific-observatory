"""
The module provides a series of text preprocessing supporting utils.

Last modified:
    2024-02-05
"""

import re
from typing import List, Dict, Tuple, Union
from functools import lru_cache
import pandas as pd
import json
from pathlib import Path
import ahocorasick

# Languages where words flow without spaces (no \b word boundary)
NON_SPACE_DELIMITED = frozenset(
    {
        "thai",
        "km",
        "lao",
        "chinese_simplified",
        "chinese_traditional",
        "japanese",
        "arabic",
        "farsi",
        "hebrew",
        "urdu",
    }
)

# Map short ISO codes (used in some YAML configs) to canonical keyword directory names.
LANGUAGE_ALIASES: dict[str, str] = {
    "ar": "arabic",
    "fa": "farsi",
    "he": "hebrew",
    "az": "azerbaijani",
    "be": "belarusian",
    "bg": "bulgarian",
    "bs": "bosnian",
    "hr": "croatian",
    "hy": "armenian",
    "ka": "georgian",
    "kk": "kazakh",
    "ky": "kyrgyz",
    "me": "montenegrin",
    "mk": "macedonian",
    "pl": "polish",
    "ro": "romanian",
    "ru": "russian",
    "sq": "albanian",
    "sr": "serbian",
    "tg": "tajik",
    "tk": "turkmen",
    "tr": "turkish",
    "uk": "ukrainian",
    "uz": "uzbek",
}


def _build_keyword_pattern(terms: list, language: str = "en") -> str:
    """Build a regex pattern for keyword matching, respecting language word boundaries."""
    escaped = "|".join(re.escape(term) for term in terms)
    if language in NON_SPACE_DELIMITED:
        return "(" + escaped + ")"
    return r"\b(" + escaped + r")\b"


def is_in_word_list(row: str, terms: list, language: str = "en") -> bool:
    """
    Check if any of the given terms are present in the input row.

    Args:
        row (str): The input row to search for terms in.
        terms (list): A list of terms to search for in the row.
        language (str): Language code. For non-space-delimited languages,
            word boundary matching (\\b) is omitted.

    Returns:
        bool: True if any of the terms are found in the row, False otherwise.
    """
    pattern = _build_keyword_pattern(terms, language)
    return bool(re.search(pattern, str(row), re.IGNORECASE))


def count_keywords_in_text(text: str, terms: list, language: str = "en") -> int:
    """
    Count total keyword occurrences in text (for intensity calculations).

    Args:
        text: Input text to search.
        terms: List of keywords to count.
        language: Language code. For non-space-delimited languages,
            word boundary matching (\\b) is omitted.

    Returns:
        Total count of keyword matches.
    """
    if not text or not terms:
        return 0
    pattern = _build_keyword_pattern(terms, language)
    matches = re.findall(pattern, str(text), re.IGNORECASE)
    return len(matches)


def _build_automaton(terms: list) -> ahocorasick.Automaton:
    """Build an Aho-Corasick automaton from a list of lowercased keywords."""
    A = ahocorasick.Automaton()
    for term in terms:
        A.add_word(term.lower(), term.lower())
    A.make_automaton()
    return A


@lru_cache(maxsize=256)
def get_automaton(terms_tuple: tuple, language: str = "en") -> ahocorasick.Automaton:
    """
    Get a cached Aho-Corasick automaton for a set of terms.

    Args:
        terms_tuple: Tuple of keyword strings (must be tuple for hashability).
        language: Language code (unused in automaton build, kept for cache key).

    Returns:
        Compiled Aho-Corasick automaton.
    """
    return _build_automaton(list(terms_tuple))


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    """
    Check if the match at text[start:end] falls on word boundaries.

    Mimics regex \\b behaviour: the character immediately before start
    and immediately after end-1 must not be alphanumeric/underscore.
    """
    if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        return False
    if end < len(text) and (text[end].isalnum() or text[end] == "_"):
        return False
    return True


def match_keywords(text: str, terms: list, language: str = "en") -> Tuple[bool, int]:
    """
    Check keyword presence and count matches in a single pass using Aho-Corasick.

    For space-delimited languages (English, French, etc.), word-boundary checks
    are applied to each match. For non-space-delimited languages (Thai, Chinese,
    Khmer, etc.), pure substring matching is used.

    Args:
        text: Input text to search (should already be lowercased).
        terms: List of keywords to match.
        language: Language code.

    Returns:
        Tuple of (has_any_match: bool, match_count: int).
    """
    if not text or not terms:
        return (False, 0)

    text_str = str(text)
    automaton = get_automaton(tuple(terms), language)
    check_boundaries = language not in NON_SPACE_DELIMITED

    # Collect all valid matches as (start, end) tuples
    matches = []
    for end_idx, term in automaton.iter(text_str):
        start_idx = end_idx - len(term) + 1
        end_pos = end_idx + 1
        if check_boundaries:
            if not _is_word_boundary(text_str, start_idx, end_pos):
                continue
        matches.append((start_idx, end_pos))

    if not matches:
        return (False, 0)

    # Resolve overlapping matches to mimic regex alternation behaviour:
    # sort by start position, then by length descending (prefer longest),
    # then greedily keep non-overlapping matches.
    matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
    count = 0
    last_end = -1
    for start, end in matches:
        if start >= last_end:
            count += 1
            last_end = end

    return (count > 0, count)


def sent_to_words(sentences: List[str]):
    """
    Converts sentences into a list of words, performing simple preprocessing.

    Args:
        sentences: A list of sentences to be converted.

    Yields:
        A generator yielding lists of words extracted from each sentence after preprocessing.
    """
    from gensim.utils import simple_preprocess

    for sentence in sentences:
        sentence = re.sub(r"\s", " ", sentence).strip()
        yield (simple_preprocess(str(sentence), deacc=True))


def lemmatize_sent(sent, nlp, allowed_postags=["NOUN", "ADJ", "VERB", "ADV"]):  # noqa: B006
    """
    Lemmatizes words in a sentence based on allowed part-of-speech tags.

    Args:
        sent: The sentence represented as a list of words.
        nlp: An instance of spacy's language model.
        allowed_postags: List of part-of-speech tags allowed for lemmatization.

    Returns:
        A list of lemmatized words filtered by allowed part-of-speech tags.
    """
    doc = nlp(" ".join(sent))
    return [token.lemma_ for token in doc if token.pos_ in allowed_postags]


def make_phrases(texts: List[str], phrases_model):
    """
    Apply phrase models to texts to detect and join multi-word expressions.

    Args:
        texts: List of tokenized texts.
        phrases_model: A Phraser model that detects phrases.

    Returns:
        A list of texts with phrases detected and joined.
    """
    return [phrases_model[doc] for doc in texts]


def preprocess_text(
    texts: List[str],
    stopwords: List[str],
    bigram_mod,
    trigram_mod,
    nlp,
):
    """
    Preprocesses texts by removing stopwords, applying bigram and trigram models, and lemmatizing.

    Args:
        texts: List of texts to preprocess.
        stopwords: List of stopwords to remove.
        bigram_mod: Bigram Phraser model.
        trigram_mod: Trigram Phraser model.
        nlp: An instance of spacy's language model for lemmatization.

    Returns:
        A list of preprocessed and lemmatized texts.
    """
    from gensim.utils import simple_preprocess

    texts_no_stopwords = [
        [word for word in simple_preprocess(str(doc)) if word not in stopwords]
        for doc in texts
    ]
    print("Stopwords has been done.")
    texts_bigrams = make_phrases(texts_no_stopwords, bigram_mod)
    texts_trigrams = make_phrases(texts_bigrams, trigram_mod)
    texts_lemmatized = [lemmatize_sent(doc, nlp) for doc in texts_trigrams]

    return texts_lemmatized


def generate_continous_df(
    checked_df: pd.DataFrame, min_date: str, max_date: str, freq="MS"
):
    """
    Generates a continuous date range dataframe and merges it with an existing dataframe.

    Args:
        checked_df: The dataframe to merge with the continuous date range.
        min_date: The start date for the continuous date range.
        max_date: The end date for the continuous date range.
        freq: The frequency of the dates to generate, defaults to 'MS' (month start).

    Returns:
        A dataframe with a continuous date range merged with the existing dataframe.

    Raises:
        ValueError: If 'date' column is not found in the checked dataframe.
    """
    dates_range = pd.date_range(start=min_date, end=max_date, freq=freq)
    dates_df = pd.DataFrame(dates_range, columns=["date"])
    if "date" in checked_df.columns:
        checked_df["date"] = pd.to_datetime(checked_df["date"], format="mixed")
        checked_df = dates_df.merge(checked_df, how="left", on="date").fillna(0)
        return checked_df
    else:
        raise ValueError("cannot find `date` column in dataframe being checked.")


_FALLBACK_WARNED: set[tuple[str, str]] = set()


def _resolve_keywords_dir(language: str, filename: str) -> Path:
    """
    Resolve the directory for a keyword file, preferring keywords_new/ over keywords/.

    Lookup order:
        1. keywords_new/{language}/{filename}
        2. keywords/{language}/{filename}
        3. keywords_new/en/{filename}
        4. keywords/en/{filename}

    Emits a one-shot stderr warning per (language, filename) when falling back
    to English so missing per-language keyword sets surface during builds.
    """
    import sys

    language = LANGUAGE_ALIASES.get(language, language)
    base = Path(__file__).parent
    for kw_dir_name in ("keywords_new", "keywords"):
        lang_dir = base / kw_dir_name / language
        if (lang_dir / filename).exists():
            return lang_dir
    key = (language, filename)
    if key not in _FALLBACK_WARNED:
        _FALLBACK_WARNED.add(key)
        print(
            f"WARNING: no {filename} for language '{language}'; falling back to English. "
            f"Generate per-language keywords with the `translate-english-keywords` skill.",
            file=sys.stderr,
        )
    for kw_dir_name in ("keywords_new", "keywords"):
        en_dir = base / kw_dir_name / "en"
        if (en_dir / filename).exists():
            return en_dir
    raise FileNotFoundError(
        f"{filename} not found for language '{language}' in keywords_new/ or keywords/"
    )


def _extract_terms(value):
    """
    Extract a flat term list from a category value.

    Handles both formats:
        - list: ["term1", "term2"]  (English / legacy)
        - dict: {"en_term": "translation", ...}  (new translated format)
    """
    if isinstance(value, dict):
        return list(value.values())
    return value


def load_topics_words(
    additional_name: Union[str, None] = None,
    language: str = "en",
) -> Dict[str, Union[List[str], Dict[str, List[str]]]]:
    """
    Load topic words from per-language keyword files.

    Args:
        additional_name (Union[str, None]): Optional name of additional topic category
            (e.g., 'job', 'inflation'). If provided, returns only that category's terms.
        language (str): Language code (e.g., 'en', 'km', 'zh'). Defaults to 'en' for English.
            If the language is not found, falls back to 'en'.

    Returns:
        Dict containing:
        - If additional_name is None: Dict with keys 'economic', 'policy', 'uncertainty'
        - If additional_name is provided: List of terms for that topic category

    Raises:
        FileNotFoundError: If keyword files are not found.
        KeyError: If additional_name is provided but not found in topics.json.
    """
    if additional_name is None:
        lang_dir = _resolve_keywords_dir(language, "epu.json")
        epu_path = lang_dir / "epu.json"
        with open(epu_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {cat: _extract_terms(val) for cat, val in raw.items()}
    else:
        lang_dir = _resolve_keywords_dir(language, "topics.json")
        topics_path = lang_dir / "topics.json"
        with open(topics_path, "r", encoding="utf-8") as f:
            topics_data = json.load(f)
        if additional_name not in topics_data:
            raise KeyError(
                f"additional_name '{additional_name}' not found in {topics_path}. "
                f"Available options: {list(topics_data.keys())}"
            )
        return _extract_terms(topics_data[additional_name])


def load_all_groups(
    source_file: str = "topics", language: str = "en"
) -> Dict[str, List[str]]:
    """
    Load all keyword groups from topics.json or actors.json.

    Args:
        source_file: Base name of the JSON file ('topics' or 'actors').
        language: Language code. Falls back to 'en' if not found.

    Returns:
        Dict mapping group names to keyword lists.
    """
    filename = f"{source_file}.json"
    lang_dir = _resolve_keywords_dir(language, filename)
    filepath = lang_dir / filename
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {group: _extract_terms(val) for group, val in raw.items()}


def generate_news_statistics_table(country_folder: Path) -> str:
    """
    Generate a markdown table with news statistics by country and newspaper/media source.

    Reads news.csv files from the country folder structure and generates a formatted
    markdown table showing:
    - Country name
    - Newspaper/Media source
    - Number of articles (formatted with thousands separator)
    - Earliest article date (YYYY-MM-DD format, or "N/A" if no data)

    Args:
        country_folder (Path): Path to the folder containing country subdirectories,
            each with newspaper subdirectories containing news.csv files.

    Returns:
        str: A formatted markdown table with news statistics.

    Example:
        >>> from pathlib import Path
        >>> country_folder = Path("data/news")
        >>> table = generate_news_statistics_table(country_folder)
        >>> print(table)
    """
    # Dictionary to store data: {country: {newspaper: {count, min_date}}}
    data_by_country = {}
    total_articles = 0

    # Loop through country folders
    for country_folder_path in country_folder.iterdir():
        if not country_folder_path.is_dir():
            continue

        country = country_folder_path.name

        # Find all newspaper folders with news.csv files
        for newspaper_folder in country_folder_path.iterdir():
            if not newspaper_folder.is_dir():
                continue

            newspaper = newspaper_folder.name
            news_file = newspaper_folder / "news.csv"

            if not news_file.exists():
                continue

            try:
                # Read the CSV file
                df = pd.read_csv(news_file, encoding="utf-8")

                if df.empty:
                    continue

                # Get count and earliest date
                article_count = len(df)
                total_articles += article_count

                # Parse date column and find minimum (earliest) date
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    min_date = df["date"].min()
                    min_date_str = (
                        min_date.strftime("%Y-%m-%d") if pd.notna(min_date) else "N/A"
                    )
                else:
                    min_date_str = "N/A"

                # Determine if this is ABC AU or RNZ based on newspaper folder name
                is_abc_au = newspaper.startswith("abc_au_")
                is_rnz = newspaper.startswith("rnz_")

                # If ABC AU or RNZ, add to "pacific" country instead of original country
                target_country = "pacific" if (is_abc_au or is_rnz) else country

                # Store data
                if target_country not in data_by_country:
                    data_by_country[target_country] = {}

                data_by_country[target_country][newspaper] = {
                    "count": article_count,
                    "min_date": min_date_str,
                }

            except Exception as e:
                print(f"Warning: Could not process {news_file}: {e}")
                continue

    # Mapping for specific newspaper display names
    newspaper_display_names = {
        "people_s_daily_online": "People's Daily Online",
        "matangi_tonga": "Matangi Tonga Online",
        "mi_journal": "MI Journal",
        "pina": "PINA",
        "png_business_news": "PNG Business News",
        "sibc": "SIBC",
        "today": "Today Online",
        "ub_post": "UB Post",
        "vbr": "Vanuatu Business Review (VBR)",
    }

    # Sort countries and newspapers
    sorted_countries = sorted(data_by_country.keys())

    # Build markdown table
    lines = []
    lines.append("| Country | Newspaper/Media Source | Number of Articles | From |")
    lines.append("|---------|------------------------|--------------------|----|")

    for country in sorted_countries:
        newspapers = sorted(data_by_country[country].keys())

        # Create a list of display items (name, count, min_date)
        display_items = []
        abc_au_total = 0
        abc_au_min_date = None
        rnz_total = 0
        rnz_min_date = None

        for newspaper in newspapers:
            info = data_by_country[country][newspaper]

            # Group ABC AU newspapers
            if newspaper.startswith("abc_au_"):
                abc_au_total += info["count"]
                if abc_au_min_date is None or info["min_date"] < abc_au_min_date:
                    abc_au_min_date = info["min_date"]
            # Group RNZ newspapers
            elif newspaper.startswith("rnz_"):
                rnz_total += info["count"]
                if rnz_min_date is None or info["min_date"] < rnz_min_date:
                    rnz_min_date = info["min_date"]
            # Other newspapers
            else:
                display_items.append((newspaper, info["count"], info["min_date"]))

        # Add grouped ABC AU and RNZ to display items
        if abc_au_total > 0:
            display_items.append(
                (
                    "Australian Broadcasting Corporation (ABC AU)",
                    abc_au_total,
                    abc_au_min_date,
                )
            )
        if rnz_total > 0:
            display_items.append(("Radio New Zealand (RNZ)", rnz_total, rnz_min_date))

        # Sort all display items alphabetically
        display_items.sort(key=lambda x: x[0].lower())

        # Display all items for this country
        is_first_row = True
        # Format country name: replace underscores with spaces and capitalize
        formatted_country = country.replace("_", " ").title()

        for newspaper, count, min_date in display_items:
            count_str = f"{count:,}"
            date_str = min_date if min_date else "N/A"

            # Format newspaper name
            # Check if it's a display name (ABC AU or RNZ)
            if newspaper.startswith(
                "Australian Broadcasting Corporation"
            ) or newspaper.startswith("Radio New Zealand"):
                formatted_newspaper = newspaper
            # Check if it has a specific mapping
            elif newspaper in newspaper_display_names:
                formatted_newspaper = newspaper_display_names[newspaper]
            # Otherwise, replace underscores with spaces and capitalize
            else:
                formatted_newspaper = newspaper.replace("_", " ").title()

            if is_first_row:
                lines.append(
                    f"| {formatted_country} | {formatted_newspaper} | {count_str} | {date_str} |"
                )
                is_first_row = False
            else:
                lines.append(f"| | {formatted_newspaper} | {count_str} | {date_str} |")

    # Add total row
    total_str = f"{total_articles:,}"
    lines.append(f"| **Total** | | **{total_str}** | |")

    # Print summary counts
    num_countries = len(sorted_countries)
    num_sources = sum(len(v) for v in data_by_country.values())
    print(f"Countries: {num_countries} | Sources (newspapers): {num_sources}")

    return "\n".join(lines)


if __name__ == "__main__":
    from pathlib import Path

    country_folder = Path(
        "data/text"
    )  # Path to country folders with newspaper subdirectories
    table = generate_news_statistics_table(country_folder)
    print(table)
