"""Unit tests for the Hebrew / Thai / Arabic-Persian measure surfaces.

Same defect class as the Cyrillic one (see test_extract_cyrillic_units.py): the
M/P-class unit vocab held only latin (and zh) spellings, so an Israeli, Thai,
Yemeni, Jordanian, Iraqi, Libyan, Sudanese, Egyptian, Afghan or Iranian product
name stated its pack size in a script `VALUE_UNIT` could not read, and the row
fell through to `pricing_basis="item"` -- priced per PIECE, not per kg / litre.

Measured on a 288,147-row modulo-stride corpus sample: 533 Hebrew rows, 112
Thai rows and 838 Arabic/Persian rows flip from `item` to `mass`/`volume`, and
280 of them are classified rows that pass the layer-1 uv_gate.

The value half needed no change: Python's `\\d` and `float()` both accept
Arabic-Indic / Persian digits, so a Persian-numeral gram figure already parses.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang=None, country=""):
    return extract(name, None, country, lang)


@pytest.mark.parametrize(
    "name, expected_basis, expected_av, expected_su",
    [
        # --- Hebrew ---------------------------------------------------------
        ("קווקר 500 גרם", "mass", 0.5, "kg"),
        ("אמנטל שוויצרי פרוס 150 גר", "mass", 0.15, "kg"),
        ("קפה גולד 200 ג", "mass", 0.2, "kg"),
        ('קולגייט - משחת שיניים מקס פרש 100 מ"ל', "volume", 0.1, "lt"),
        ("יין פרדיגמה 750 מל", "volume", 0.75, "lt"),
        ("חלב של פעם מלא 1 ל", "volume", 1.0, "lt"),
        ('סוכר לבן 1 ק"ג ROSE', "mass", 1.0, "kg"),
        # --- Thai -----------------------------------------------------------
        ("ตราเด็กสมบูรณ์ ซอสโชยุ 250 กรัม", "mass", 0.25, "kg"),
        ("ลองบีช น้ําสตรอเบอร์รี่ผสมเนื้อ 900 มล.", "volume", 0.9, "lt"),
        ("ดั๊กคิง เนื้อเป็ดบดผสมกึ๋นแช่แข็ง 1 กก.", "mass", 1.0, "kg"),
        ("โหลแก้วสูญญากาศสี่เหลี่ยม 2 ลิตร", "volume", 2.0, "lt"),
        # --- Arabic / Persian -----------------------------------------------
        ("ريتاج باكينغ بودر 100 جرام", "mass", 0.1, "kg"),
        ("اندومي نودلز بنكهة الخضار-70 جم", "mass", 0.07, "kg"),
        ("لبنة المشروع Almashrou Labaneh – 200 غرام", "mass", 0.2, "kg"),
        ("ايس تي ليبتون ليمون 320مل", "volume", 0.32, "lt"),
        ("زيت دوار الشمس 1 لتر", "volume", 1.0, "lt"),
        ("سكر الاسرة 5كغم", "mass", 5.0, "kg"),
        ("برنج معراج 25 کیلو گرم", "mass", 25.0, "kg"),
        ("ماکارونی فرمی گندمی سمیرا 500 گرم", "mass", 0.5, "kg"),
        # Persian-numeral value: `\d` and float() already accept these digits.
        ("قرص شیرین کننده بدون قند کامور وزن ۲۰۰ گرم", "mass", 0.2, "kg"),
    ],
)
def test_script_measure_is_read(name, expected_basis, expected_av, expected_su):
    sf = _ex(name)
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.standard_unit == expected_su


@pytest.mark.parametrize(
    "name, expected_av, expected_mult",
    [
        ('שישיית בירה פרוני 6*330 מ"ל', 0.330, 6),
        ("פולפה טבעית יכין 400 גר*3", 0.400, 3),
        ("بسكويت ديمه سادة 12×45غم", 0.045, 12),
        ("كرتون فيمتو وادان 12*710 مل", 0.710, 12),
        ("ทาโร ปลาสวรรค์ รสบาร์บีคิว 30 กรัม x6", 0.030, 6),
    ],
)
def test_script_multipack(name, expected_av, expected_mult):
    sf = _ex(name)
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.count == 1
    assert sf.multiplier == expected_mult


def test_abbreviations_need_a_word_boundary():
    """`مل` and `ג` are prefixes of ordinary words in their scripts; the
    trailing \\b is what keeps them from firing inside one."""
    # ملعقة = "spoon"; the `مل` prefix must not read as millilitres.
    assert _ex("صلصة 3 ملعقة").pricing_basis == "item"


def test_latin_names_are_untouched():
    sf = _ex("Coca Cola 330ml 24 Pack", lang="en")
    assert (sf.pricing_basis, sf.amount_value, sf.multiplier) == ("volume", 0.33, 24)
