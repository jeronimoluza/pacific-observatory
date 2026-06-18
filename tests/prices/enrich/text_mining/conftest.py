import pandas as pd
import pytest

# products_input.parquet column set (see prices.enrich.stages.prepare.prepare_input):
# product_name_original, category, country, currency, lang, channel,
# declared_coicop_codes, price, n_rows
PRODUCTS_INPUT_COLUMNS = [
    "product_name_original",
    "category",
    "country",
    "currency",
    "lang",
    "channel",
    "declared_coicop_codes",
    "price",
    "n_rows",
]

# gold column set (data/prices/enrich/gold/gold_labels.parquet):
# product_name, coicop_code_gold (dotted), country, language,
# sub_label_gold, basis_gold, val_gold
GOLD_COLUMNS = [
    "product_name",
    "coicop_code_gold",
    "country",
    "language",
    "sub_label_gold",
    "basis_gold",
    "val_gold",
]


# Each tuple is one corpus row carrying the products_input fields. Several rows
# carry a parseable structural span (mass / volume / count / multipack / promo);
# several carry none. All five script families are present, plus a Han-only vs
# kana-present pair so downstream segmenter routing is exercised deterministically.
_CORPUS_ROWS = [
    # Latin English — structural spans present
    (
        "Coca-Cola 1.5L x6",
        "beverages",
        "philippines",
        "PHP",
        "en",
        "supermarket",
        "01.2.2",
        240.0,
        12,
    ),
    (
        "T-shirt 5.6oz",
        "apparel",
        "philippines",
        "PHP",
        "en",
        "hypermarket",
        "03.1.2",
        450.0,
        3,
    ),
    (
        "Tide Detergent 2kg",
        "household",
        "philippines",
        "PHP",
        "en",
        "supermarket",
        "05.6.1",
        320.0,
        7,
    ),
    (
        "Promo 3+1 Instant Noodles",
        "food",
        "philippines",
        "PHP",
        "en",
        "supermarket",
        "01.1.1",
        55.0,
        9,
    ),
    # Latin English — no structural span
    (
        "Fresh Lettuce",
        "produce",
        "philippines",
        "PHP",
        "en",
        "supermarket",
        "01.1.7",
        30.0,
        4,
    ),
    (
        "Hand Soap",
        "household",
        "philippines",
        "PHP",
        "en",
        "aggregator",
        "12.1.3",
        89.0,
        2,
    ),
    # SE-Asian Latin (whitespace-segmented): Indonesian
    (
        "Minyak Goreng 1L",
        "food",
        "indonesia",
        "IDR",
        "id",
        "supermarket",
        "01.1.5",
        18000.0,
        6,
    ),
    (
        "Beras Premium 5kg",
        "food",
        "indonesia",
        "IDR",
        "id",
        "hypermarket",
        "01.1.1",
        65000.0,
        5,
    ),
    # Malay
    (
        "Susu Tepung 900g",
        "food",
        "malaysia",
        "MYR",
        "ms",
        "supermarket",
        "01.1.4",
        28.0,
        4,
    ),
    ("Roti Gardenia", "food", "malaysia", "MYR", "ms", "supermarket", "01.1.1", 3.5, 8),
    # Vietnamese
    (
        "Nuoc Mam 500ml",
        "food",
        "vietnam",
        "VND",
        "vi",
        "supermarket",
        "01.1.9",
        32000.0,
        3,
    ),
    (
        "Ca Phe Goi",
        "beverages",
        "vietnam",
        "VND",
        "vi",
        "aggregator",
        "01.2.1",
        5000.0,
        2,
    ),
    # Tagalog
    (
        "Bigas 25kg",
        "food",
        "philippines",
        "PHP",
        "tl",
        "wetmarket",
        "01.1.1",
        1450.0,
        6,
    ),
    (
        "Itlog Dosena",
        "food",
        "philippines",
        "PHP",
        "tl",
        "wetmarket",
        "01.1.4",
        95.0,
        4,
    ),
    # Han (Chinese) — structural spans (zh)
    (
        "可口可乐 500g 6入",
        "beverages",
        "china",
        "CNY",
        "zh",
        "supermarket",
        "01.2.2",
        18.0,
        10,
    ),
    ("酱油 1L", "food", "china", "CNY", "zh", "hypermarket", "01.1.9", 12.5, 5),
    # Han-only, no kana (zh) — must route to jieba, not fugashi
    ("白米 五公斤", "food", "china", "CNY", "zh", "supermarket", "01.1.1", 60.0, 7),
    ("洗发水", "household", "china", "CNY", "zh", "aggregator", "12.1.3", 25.0, 3),
    # Kana present (Japanese) — Han+kana mix, must route to fugashi
    (
        "コカ・コーラ 500ml 6本",
        "beverages",
        "japan",
        "JPY",
        "ja",
        "supermarket",
        "01.2.2",
        600.0,
        9,
    ),
    ("醤油 1リットル", "food", "japan", "JPY", "ja", "supermarket", "01.1.9", 350.0, 4),
    ("おにぎり 鮭", "food", "japan", "JPY", "ja", "supermarket", "01.1.1", 130.0, 6),
    ("食パン 6枚", "food", "japan", "JPY", "ja", "supermarket", "01.1.1", 158.0, 5),
    # Thai (th)
    ("น้ำมันพืช 1 ลิตร", "food", "thailand", "THB", "th", "supermarket", "01.1.5", 55.0, 8),
    (
        "ข้าวสาร 5 กิโลกรัม",
        "food",
        "thailand",
        "THB",
        "th",
        "hypermarket",
        "01.1.1",
        180.0,
        4,
    ),
    ("นมกล่อง", "beverages", "thailand", "THB", "th", "aggregator", "01.1.4", 12.0, 3),
    # Korean (ko)
    (
        "코카콜라 500ml 6개",
        "beverages",
        "korea",
        "KRW",
        "ko",
        "supermarket",
        "01.2.2",
        4800.0,
        11,
    ),
    ("간장 1L", "food", "korea", "KRW", "ko", "hypermarket", "01.1.9", 5200.0, 5),
    ("쌀 10kg", "food", "korea", "KRW", "ko", "supermarket", "01.1.1", 38000.0, 6),
    ("계란 30구", "food", "korea", "KRW", "ko", "supermarket", "01.1.4", 7900.0, 4),
    ("두부", "food", "korea", "KRW", "ko", "wetmarket", "01.1.7", 1500.0, 2),
]


# tiny_gold rows span >=3 distinct COICOP leaves (01.1.1.0.1, 01.2.2.0.1,
# 01.1.5.0.1, 03.1.2.0.1) so MI contingency tables are non-degenerate.
_GOLD_ROWS = [
    # product_name, coicop_code_gold, country, language, sub_label_gold, basis_gold, val_gold
    ("White Rice 5kg", "01.1.1.0.1", "philippines", "en", "rice", "mass", 5.0),
    ("Bigas 25kg", "01.1.1.0.1", "philippines", "tl", "rice", "mass", 25.0),
    ("白米 五公斤", "01.1.1.0.1", "china", "zh", "rice", "mass", 5.0),
    (
        "Coca-Cola 1.5L x6",
        "01.2.2.0.1",
        "philippines",
        "en",
        "soft_drink",
        "volume",
        1.5,
    ),
    (
        "コカ・コーラ 500ml 6本",
        "01.2.2.0.1",
        "japan",
        "ja",
        "soft_drink",
        "volume",
        0.5,
    ),
    ("코카콜라 500ml 6개", "01.2.2.0.1", "korea", "ko", "soft_drink", "volume", 0.5),
    ("Minyak Goreng 1L", "01.1.5.0.1", "indonesia", "id", "cooking_oil", "volume", 1.0),
    ("น้ำมันพืช 1 ลิตร", "01.1.5.0.1", "thailand", "th", "cooking_oil", "volume", 1.0),
    ("T-shirt 5.6oz", "03.1.2.0.1", "philippines", "en", "tshirt", "item", 1.0),
    ("Cotton T-shirt", "03.1.2.0.1", "malaysia", "ms", "tshirt", "item", 1.0),
]


@pytest.fixture
def tiny_corpus() -> pd.DataFrame:
    """In-memory ~30-row multilingual corpus mirroring products_input.parquet.

    Spans Latin (en/id/ms/vi/tl), Han (zh), Kana (ja), Thai (th), and Hangul
    (ko). Several rows carry a parseable structural span; several do not.
    Deterministic — no randomness, no network, no file reads.
    """
    return pd.DataFrame(_CORPUS_ROWS, columns=PRODUCTS_INPUT_COLUMNS)


@pytest.fixture
def tiny_gold() -> pd.DataFrame:
    """In-memory ~10-row gold-shaped frame spanning >=3 COICOP leaves.

    Deterministic — no randomness, no network, no file reads.
    """
    return pd.DataFrame(_GOLD_ROWS, columns=GOLD_COLUMNS)
