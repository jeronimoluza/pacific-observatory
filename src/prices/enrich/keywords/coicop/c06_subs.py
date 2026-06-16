"""Auto-generated sub_labels for COICOP class 06.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "06.1.1.1": (
        SubLabel(
            id="all-medicines-including-branded-and-generic-products-used-to",
            label="all medicines, including branded and generic products, used to prevent, diagnose and treat illnesses, diseases and injuries",
            keywords_by_lang={
                "en": (
                    "all medicines, including branded and generic products, used to prevent, diagnose and treat illnesses, diseases and injuries",
                )
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fluids-required-for-dialysis-as-well-as-gases-used-in-health",
            label="fluids required for dialysis, as well as gases used in health care, such as oxygen, when purchased by the patient directly",
            keywords_by_lang={
                "en": (
                    "fluids required for dialysis, as well as gases used in health care, such as oxygen, when purchased by the patient directly",
                )
            },
            allowed_bases=frozenset({"volume", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medicinal-soap",
            label="medicinal soap",
            keywords_by_lang={
                "en": ("medicinal soap", "Medicinal Soap", "medicated soap")
            },
            allowed_bases=frozenset({"count", "item", "mass"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pharmaceutical-preparations-used-to-treat-illnesses-diseases",
            label="pharmaceutical preparations used to treat illnesses, diseases and injuries (e.g., extemporaneous ointments, syrups, capsules and other galenic substances prepared on prescription)",
            keywords_by_lang={
                "en": (
                    "pharmaceutical preparations used to treat illnesses, diseases and injuries (e.g., extemporaneous ointments, syrups, capsules and other galenic substances prepared on prescription)",
                )
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="service-fees-charged-by-pharmacists-for-dispensing-medicines",
            label="service fees charged by pharmacists for dispensing medicines",
            keywords_by_lang={
                "en": ("service fees charged by pharmacists for dispensing medicines",)
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vaccines-hormones-oral-contraceptives-and-other-pharmaceutic",
            label="vaccines, hormones, oral contraceptives and other pharmaceutical products used to prevent, diagnose and treat illnesses, diseases and injuries",
            keywords_by_lang={
                "en": (
                    "vaccines, hormones, oral contraceptives and other pharmaceutical products used to prevent, diagnose and treat illnesses, diseases and injuries",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vitamin-and-mineral-supplements",
            label="vitamin and mineral supplements",
            keywords_by_lang={"en": ("vitamin and mineral supplements",)},
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="antiseptic-disinfectant",
            label="antiseptic disinfectant",
            keywords_by_lang={"auto": ("antiseptic disinfectant",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cold-flu-remedy",
            label="cold flu remedy",
            keywords_by_lang={"auto": ("cold flu remedy",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="digestive-remedy",
            label="digestive remedy",
            keywords_by_lang={"auto": ("digestive remedy",)},
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medicated-balm-patch",
            label="medicated balm patch",
            keywords_by_lang={"auto": ("medicated balm patch",)},
            allowed_bases=frozenset({"count", "item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pain-relief",
            label="pain relief",
            keywords_by_lang={"auto": ("pain relief",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="prescription-medicine",
            label="prescription medicine",
            keywords_by_lang={"auto": ("prescription medicine",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="throat-lozenge",
            label="throat lozenge",
            keywords_by_lang={"auto": ("throat lozenge",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="topical-cream",
            label="topical cream",
            keywords_by_lang={"auto": ("topical cream",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="traditional-medicine",
            label="traditional medicine",
            keywords_by_lang={"auto": ("traditional medicine",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vitamins",
            label="vitamins",
            keywords_by_lang={"auto": ("vitamins",)},
            allowed_bases=frozenset({"count", "item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cough-lozenges",
            label="Cough Lozenges",
            keywords_by_lang={
                "en": ("Cough Lozenges", "cough drops", "throat lozenges")
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medicinal-ointments",
            label="Medicinal Ointments",
            keywords_by_lang={
                "en": ("Medicinal Ointments", "medicated cream", "therapeutic ointment")
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="oral-contraceptives",
            label="Oral Contraceptives",
            keywords_by_lang={
                "en": (
                    "Oral Contraceptives",
                    "birth control pills",
                    "contraceptive pills",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="oxygen-supplies",
            label="Oxygen Supplies",
            keywords_by_lang={
                "en": ("Oxygen Supplies", "medical oxygen", "oxygen tank")
            },
            allowed_bases=frozenset({"volume", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pain-relief-tablets",
            label="Pain Relief Tablets",
            keywords_by_lang={
                "en": ("Pain Relief Tablets", "analgesic tablets", "painkillers")
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vaccines",
            label="Vaccines",
            keywords_by_lang={
                "en": ("Vaccines", "immunization shots", "vaccination doses")
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vitamin-supplements",
            label="Vitamin Supplements",
            keywords_by_lang={
                "en": (
                    "Vitamin Supplements",
                    "mineral supplements",
                    "multivitamins",
                    "vitamin pills",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.1.2": (
        SubLabel(
            id="herbs-herbal-materials-herbal-preparations-and-finished-herb",
            label="herbs, herbal materials, herbal preparations and finished herbal products that contain, as active ingredients, parts of plants, other plant materials or combinations thereof which are generally used in traditional and complementary medicine",
            keywords_by_lang={
                "en": (
                    "herbs, herbal materials, herbal preparations and finished herbal products that contain, as active ingredients, parts of plants, other plant materials or combinations thereof which are generally used in traditional and complementary medicine",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="homeopathic-medicines-prepared-in-accordance-with-a-homeopat",
            label="homeopathic medicines prepared in accordance with a homeopathic manufacturing procedure described in a pharmacopeia in official use or in other official documents and which may contain a number of homeopathic preparations",
            keywords_by_lang={
                "en": (
                    "homeopathic medicines prepared in accordance with a homeopathic manufacturing procedure described in a pharmacopeia in official use or in other official documents and which may contain a number of homeopathic preparations",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="herbal-extract-essence",
            label="Herbal Extract Essence",
            keywords_by_lang={
                "en": (
                    "Herbal Extract Essence",
                    "concentrated herb drink",
                    "herbal essence",
                    "liquid herbal supplement",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="herbal-tea-drinks",
            label="Herbal Tea Drinks",
            keywords_by_lang={
                "en": (
                    "Herbal Tea Drinks",
                    "herb drink",
                    "herbal infusion",
                    "herbal tea",
                    "中草藥茶",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="herbal-telon-oil",
            label="Herbal Telon Oil",
            keywords_by_lang={
                "en": (
                    "Herbal Telon Oil",
                    "baby herbal oil",
                    "cajeput oil blend",
                    "minyak telon",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="herbal-topical-oil",
            label="Herbal Topical Oil",
            keywords_by_lang={
                "en": (
                    "Herbal Topical Oil",
                    "essential oil blend",
                    "herbal massage oil",
                    "therapeutic oil",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="herbal-warming-patch",
            label="Herbal Warming Patch",
            keywords_by_lang={
                "en": (
                    "Herbal Warming Patch",
                    "herbal heat pad",
                    "mugwort patch",
                    "yomogi patch",
                    "よもぎ温座パット",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="homeopathic-spray",
            label="Homeopathic Spray",
            keywords_by_lang={
                "en": (
                    "Homeopathic Spray",
                    "flower essence spray",
                    "homeopathic remedy",
                    "oral spray",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.2.1": (
        SubLabel(
            id="diagnostic-equipment-for-self-testing-and-medical-equipment-",
            label="diagnostic equipment for self-testing and medical equipment sold over the counter for personal use outside a health facility or institution",
            keywords_by_lang={
                "en": (
                    "diagnostic equipment for self-testing and medical equipment sold over the counter for personal use outside a health facility or institution",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-diagnostic-products-purchased-over-the-internet-for-",
            label="medical diagnostic products purchased over the Internet for personal use",
            keywords_by_lang={
                "en": (
                    "medical diagnostic products purchased over the Internet for personal use",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pregnancy-testing-kits-thermometers-glucose-meters-blood-pre",
            label="pregnancy testing kits; thermometers, glucose meters, blood pressure meters and other devices used in point-of-care testing, baby scales and so on",
            keywords_by_lang={
                "en": (
                    "pregnancy testing kits; thermometers, glucose meters, blood pressure meters and other devices used in point-of-care testing, baby scales and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="thermometer",
            label="thermometer",
            keywords_by_lang={"auto": ("thermometer",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="baby-scale",
            label="Baby Scale",
            keywords_by_lang={"en": ("Baby Scale", "infant scale", "ベビースケール")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bath-thermometer",
            label="Bath Thermometer",
            keywords_by_lang={
                "en": ("Bath Thermometer", "water thermometer", "湯温計")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="blood-pressure-monitor",
            label="Blood Pressure Monitor",
            keywords_by_lang={
                "en": (
                    "Blood Pressure Monitor",
                    "blood pressure meter",
                    "sphygmomanometer",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="digital-thermometer",
            label="Digital Thermometer",
            keywords_by_lang={"en": ("Digital Thermometer", "thermometer", "体温計")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="glucose-meter",
            label="Glucose Meter",
            keywords_by_lang={
                "en": ("Glucose Meter", "blood glucose monitor", "glucometer")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pregnancy-test-kit",
            label="Pregnancy Test Kit",
            keywords_by_lang={
                "en": ("Pregnancy Test Kit", "ovulation test", "pregnancy test")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pulse-oximeter",
            label="Pulse Oximeter",
            keywords_by_lang={"en": ("Pulse Oximeter", "oxygen monitor")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sars-cov-2-test-kit",
            label="SARS-CoV-2 Test Kit",
            keywords_by_lang={
                "en": ("SARS-CoV-2 Test Kit", "antigen test", "covid test kit")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="skin-analyzer",
            label="Skin Analyzer",
            keywords_by_lang={
                "en": ("Skin Analyzer", "skin checker", "skin moisture tester")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.2.2": (
        SubLabel(
            id="condoms-and-other-mechanical-contraceptive-devices-masks-med",
            label="condoms and other mechanical contraceptive devices, masks, medicinal stockings (e.g., compression stockings), medicinal gloves, insecticide-treated mosquito nets and so on",
            keywords_by_lang={
                "en": (
                    "condoms and other mechanical contraceptive devices, masks, medicinal stockings (e.g., compression stockings), medicinal gloves, insecticide-treated mosquito nets and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="face-mask",
            label="face mask",
            keywords_by_lang={"auto": ("face mask",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="plasters",
            label="plasters",
            keywords_by_lang={"auto": ("plasters",)},
            allowed_bases=frozenset({"count", "item", "length"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="compression-stockings",
            label="Compression Stockings",
            keywords_by_lang={
                "en": (
                    "Compression Stockings",
                    "elastic stockings",
                    "medicinal stockings",
                    "support hosiery",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="condoms",
            label="Condoms",
            keywords_by_lang={"en": ("Condoms", "condom", "ถุงยางอนามัย", "避孕套")},
            allowed_bases=frozenset({"count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="diaphragms",
            label="Diaphragms",
            keywords_by_lang={
                "en": ("Diaphragms", "cervical cap", "contraceptive device")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="disposable-medical-gloves",
            label="Disposable Medical Gloves",
            keywords_by_lang={
                "en": (
                    "Disposable Medical Gloves",
                    "examination gloves",
                    "medicinal gloves",
                    "ถุงมือแพทย์",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="insecticide-treated-mosquito-nets",
            label="Insecticide-treated Mosquito Nets",
            keywords_by_lang={
                "en": (
                    "Insecticide-treated Mosquito Nets",
                    "bed net",
                    "mosquito netting",
                    "มุ้งกันยุง",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="surgical-masks",
            label="Surgical Masks",
            keywords_by_lang={
                "en": ("Surgical Masks", "face mask", "respirator mask", "口罩")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.2.3": (
        SubLabel(
            id="inhalers-syringes-humidifiers-nebulizers-hot-bags-ice-packs-",
            label="inhalers, syringes, humidifiers, nebulizers, hot bags, ice packs, first-aid kits, bandages and so on",
            keywords_by_lang={
                "en": (
                    "inhalers, syringes, humidifiers, nebulizers, hot bags, ice packs, first-aid kits, bandages and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-humidifier-health",
            label="Electric Health Humidifier",
            keywords_by_lang={
                "en": ("Electric Health Humidifier", "humidifier", "medical humidifier")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="first-aid-kit",
            label="First Aid Kit",
            keywords_by_lang={
                "en": ("First Aid Kit", "emergency kit", "first aid box")
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hot-cold-therapy-pack",
            label="Hot Cold Therapy Pack",
            keywords_by_lang={
                "en": ("Hot Cold Therapy Pack", "gel pack", "hot bag", "ice pack")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hypodermic-syringe",
            label="Hypodermic Syringe",
            keywords_by_lang={
                "en": ("Hypodermic Syringe", "insulin syringe", "syringe")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-bandage-tape",
            label="Medical Bandage Tape",
            keywords_by_lang={
                "en": (
                    "Medical Bandage Tape",
                    "adhesive tape",
                    "bandage",
                    "gauze bandage",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-inhaler-spacer",
            label="Medical Inhaler Spacer",
            keywords_by_lang={
                "en": (
                    "Medical Inhaler Spacer",
                    "asthma spacer",
                    "inhaler device",
                    "inhaler spacer",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-nebulizer-device",
            label="Medical Nebulizer Device",
            keywords_by_lang={
                "en": (
                    "Medical Nebulizer Device",
                    "mesh nebulizer",
                    "nebuliser",
                    "nebulizer",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pill-cutter-crusher",
            label="Pill Cutter Crusher",
            keywords_by_lang={
                "en": (
                    "Pill Cutter Crusher",
                    "medication crusher",
                    "pill cutter",
                    "pill splitter",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.3.1": (
        SubLabel(
            id="corrective-eyeglasses-spectacles-for-low-vision-and-short-an",
            label="corrective eyeglasses (spectacles) for low vision; and short- and long-distance spectacles",
            keywords_by_lang={
                "en": (
                    "corrective eyeglasses (spectacles) for low vision; and short- and long-distance spectacles",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ocular-prostheses-e-g-glass-eyes-and-contact-lenses",
            label="ocular prostheses (e.g., glass eyes) and contact lenses",
            keywords_by_lang={
                "en": ("ocular prostheses (e.g., glass eyes) and contact lenses",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="white-canes",
            label="white canes",
            keywords_by_lang={
                "en": (
                    "white canes",
                    "White Canes",
                    "blind cane",
                    "mobility aid cane",
                    "walking cane for blind",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="contact-lenses",
            label="Contact Lenses",
            keywords_by_lang={
                "en": (
                    "Contact Lenses",
                    "hard contact lenses",
                    "soft contact lenses",
                    "度ありカラコン",
                    "隱形眼鏡",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="corrective-spectacles",
            label="Corrective Spectacles",
            keywords_by_lang={
                "en": (
                    "Corrective Spectacles",
                    "optical frames",
                    "prescription glasses",
                    "メガネ",
                    "眼镜",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="ocular-prostheses",
            label="Ocular Prostheses",
            keywords_by_lang={
                "en": (
                    "Ocular Prostheses",
                    "artificial eye",
                    "glass eye",
                    "prosthetic eye",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="reading-glasses",
            label="Reading Glasses",
            keywords_by_lang={
                "en": (
                    "Reading Glasses",
                    "magnifying spectacles",
                    "ハズキルーペ",
                    "老眼鏡",
                    "老花眼鏡",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="spectacle-accessories",
            label="Spectacle Accessories",
            keywords_by_lang={
                "en": (
                    "Spectacle Accessories",
                    "glasses case",
                    "lens cleaning cloth",
                    "spectacle chain",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.3.2": (
        SubLabel(
            id="cleaning-adjustment-and-batteries-if-not-priced-separately-f",
            label="cleaning, adjustment and batteries if not priced separately from the product",
            keywords_by_lang={
                "en": (
                    "cleaning, adjustment and batteries if not priced separately from the product",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="digital-hearing-aids",
            label="digital hearing aids",
            keywords_by_lang={"en": ("digital hearing aids",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="behind-the-ear-hearing-aid",
            label="Behind-the-ear Hearing Aid",
            keywords_by_lang={
                "en": (
                    "Behind-the-ear Hearing Aid",
                    "bte hearing aid",
                    "耳かけ型補聴器",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hearing-aid-battery",
            label="Hearing Aid Battery",
            keywords_by_lang={
                "en": ("Hearing Aid Battery", "zinc-air battery", "補聴器用電池")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hearing-aid-cleaning-kit",
            label="Hearing Aid Cleaning Kit",
            keywords_by_lang={
                "en": (
                    "Hearing Aid Cleaning Kit",
                    "hearing aid wax guard",
                    "補聴器メンテナンスキット",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hearing-aid-domes-tubing",
            label="Hearing Aid Domes and Tubing",
            keywords_by_lang={
                "en": ("Hearing Aid Domes and Tubing", "ear mold", "補聴器用ドーム")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hearing-aid-programming-device",
            label="Hearing Aid Programming Device",
            keywords_by_lang={
                "en": (
                    "Hearing Aid Programming Device",
                    "hearing aid programmer",
                    "補聴器設定機器",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="in-the-ear-hearing-aid",
            label="In-the-ear Hearing Aid",
            keywords_by_lang={
                "en": ("In-the-ear Hearing Aid", "ite hearing aid", "耳あな型補聴器")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.3.3": (
        SubLabel(
            id="absorbent-incontinence-products-including-diapers-for-ageing",
            label="absorbent incontinence products, including diapers for ageing populations",
            keywords_by_lang={
                "en": (
                    "absorbent incontinence products, including diapers for ageing populations",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="chairs-for-shower-bath-and-toilet-handrails-and-grab-bars",
            label="chairs for shower, bath and toilet, handrails and grab bars",
            keywords_by_lang={
                "en": ("chairs for shower, bath and toilet, handrails and grab bars",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="crutches",
            label="crutches",
            keywords_by_lang={"en": ("crutches",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="leg-and-hand-prostheses-including-implants-spinal-belts-and-",
            label="leg and hand prostheses, including implants; spinal belts; and spinal, braces, including neck braces (also known as cervical collars)",
            keywords_by_lang={
                "en": (
                    "leg and hand prostheses, including implants; spinal belts; and spinal, braces, including neck braces (also known as cervical collars)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="orthoses-braces-splints-and-other-artificial-external-device",
            label="orthoses (braces, splints and other artificial external devices serving to support the leg, spine, neck or hand)",
            keywords_by_lang={
                "en": (
                    "orthoses (braces, splints and other artificial external devices serving to support the leg, spine, neck or hand)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="portable-ramps",
            label="portable ramps",
            keywords_by_lang={"en": ("portable ramps",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pressure-relief-mattresses-and-special-beds",
            label="pressure relief mattresses and special beds",
            keywords_by_lang={"en": ("pressure relief mattresses and special beds",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rollators-walking-frames-walkers-and-standing-frames",
            label="rollators, walking frames/walkers and standing frames",
            keywords_by_lang={
                "en": ("rollators, walking frames/walkers and standing frames",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="therapeutic-diabetic-neuropathic-and-orthopaedic-footwear-an",
            label="therapeutic (diabetic, neuropathic and orthopaedic) footwear; and trusses and supports",
            keywords_by_lang={
                "en": (
                    "therapeutic (diabetic, neuropathic and orthopaedic) footwear; and trusses and supports",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="walkers-and-walking-sticks-and-canes-for-mobility",
            label="walkers, and walking sticks and canes for mobility",
            keywords_by_lang={
                "en": ("walkers, and walking sticks and canes for mobility",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wheelchairs-powered-or-manual-with-or-without-cushions",
            label="wheelchairs, powered or manual, with or without cushions",
            keywords_by_lang={
                "en": ("wheelchairs, powered or manual, with or without cushions",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="orthopaedic-support",
            label="orthopaedic support",
            keywords_by_lang={"auto": ("orthopaedic support",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="bathroom-assistive-device",
            label="Bathroom Assistive Device",
            keywords_by_lang={
                "en": (
                    "Bathroom Assistive Device",
                    "grab bar",
                    "shower chair",
                    "toilet aid",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="crutch",
            label="Crutch",
            keywords_by_lang={"en": ("Crutch", "crutches", "muleta")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="incontinence-product",
            label="Incontinence Product",
            keywords_by_lang={
                "en": (
                    "Incontinence Product",
                    "absorbent pad",
                    "diapers",
                    "diapers for adults",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="joint-orthosis",
            label="Joint Orthosis",
            keywords_by_lang={
                "en": (
                    "Joint Orthosis",
                    "knee brace",
                    "knee support",
                    "splint",
                    "膝サポーター",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="manual-wheelchair",
            label="Manual Wheelchair",
            keywords_by_lang={"en": ("Manual Wheelchair", "kursi roda", "wheelchair")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="orthopedic-footwear",
            label="Orthopedic Footwear",
            keywords_by_lang={
                "en": (
                    "Orthopedic Footwear",
                    "diabetic shoes",
                    "insoles",
                    "orthopaedic shoes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pressure-relief-surface",
            label="Pressure Relief Surface",
            keywords_by_lang={
                "en": (
                    "Pressure Relief Surface",
                    "pressure relief mattress",
                    "special bed",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="spinal-support",
            label="Spinal Support",
            keywords_by_lang={
                "en": (
                    "Spinal Support",
                    "back brace",
                    "korset perut",
                    "lumbar belt",
                    "spinal belt",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="walking-frame",
            label="Walking Frame",
            keywords_by_lang={
                "en": ("Walking Frame", "alat bantu jalan", "rollator", "walker")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.1.4.0": (
        SubLabel(
            id="cleaning-repair-rental-and-maintenance-of-medical-diagnostic",
            label="cleaning, repair, rental and maintenance of medical diagnostic products for personal use and of assistive products for vision, hearing, mobility and daily living (e.g., rental of medical alarms for in-home use)",
            keywords_by_lang={
                "en": (
                    "cleaning, repair, rental and maintenance of medical diagnostic products for personal use and of assistive products for vision, hearing, mobility and daily living (e.g., rental of medical alarms for in-home use)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.1.1": (
        SubLabel(
            id="immunization-and-vaccination-services-as-a-component-of-mate",
            label="immunization and vaccination services as a component of maternal care and childcare",
            keywords_by_lang={
                "en": (
                    "immunization and vaccination services as a component of maternal care and childcare",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tourism-and-travel-related-vaccination-as-well-as-all-other-",
            label="tourism and travel-related vaccination as well as all other types of compulsory or voluntary immunization and vaccination services",
            keywords_by_lang={
                "en": (
                    "tourism and travel-related vaccination as well as all other types of compulsory or voluntary immunization and vaccination services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.1.9": (
        SubLabel(
            id="all-other-medical-services-provided-before-symptoms-appear",
            label="all other medical services provided before symptoms appear",
            keywords_by_lang={
                "en": ("all other medical services provided before symptoms appear",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="diagnostic-imaging-services-and-medical-laboratory-services-",
            label="diagnostic imaging services and medical laboratory services (e.g., mammogram testing) needed for the provision of preventive services when those imaging and laboratory services are priced jointly with the time and skills of personnel",
            keywords_by_lang={
                "en": (
                    "diagnostic imaging services and medical laboratory services (e.g., mammogram testing) needed for the provision of preventive services when those imaging and laboratory services are priced jointly with the time and skills of personnel",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="family-planning-and-counselling-including-genetic-counsellin",
            label="family planning and counselling (including genetic counselling)",
            keywords_by_lang={
                "en": (
                    "family planning and counselling (including genetic counselling)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="general-and-routine-check-up-services-including-as-related-t",
            label="general and routine check-up services, including as related to child growth and development",
            keywords_by_lang={
                "en": (
                    "general and routine check-up services, including as related to child growth and development",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="identification-of-genetic-abnormalities",
            label="identification of genetic abnormalities",
            keywords_by_lang={"en": ("identification of genetic abnormalities",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="prenatal-and-postnatal-care-services",
            label="prenatal and postnatal care services",
            keywords_by_lang={"en": ("prenatal and postnatal care services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="screening-diagnostic-tests-and-medical-examinations-performe",
            label="screening, diagnostic tests and medical examinations performed for the purpose of detecting communicable and non-communicable diseases (e.g., malaria, tuberculosis, breast cancer, cervical cancer, colorectal cancer, prostate cancer, diabetes and HIV/AIDS) before symptoms appear",
            keywords_by_lang={
                "en": (
                    "screening, diagnostic tests and medical examinations performed for the purpose of detecting communicable and non-communicable diseases (e.g., malaria, tuberculosis, breast cancer, cervical cancer, colorectal cancer, prostate cancer, diabetes and HIV/AIDS) before symptoms appear",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.2.1": (
        SubLabel(
            id="routine-preventive-dental-check-ups",
            label="routine preventive dental check-ups",
            keywords_by_lang={"en": ("routine preventive dental check-ups",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.2.9": (
        SubLabel(
            id="aesthetic-dentistry-services",
            label="aesthetic dentistry services",
            keywords_by_lang={"en": ("aesthetic dentistry services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="all-cost-concerning-dentures-including-the-fitting-costs",
            label="all cost concerning dentures (including the fitting costs)",
            keywords_by_lang={
                "en": ("all cost concerning dentures (including the fitting costs)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="all-other-dental-services-that-do-not-require-an-overnight-s",
            label="all other dental services that do not require an overnight stay (excluding preventive dental services)",
            keywords_by_lang={
                "en": (
                    "all other dental services that do not require an overnight stay (excluding preventive dental services)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.3.1": (
        SubLabel(
            id="all-components-of-the-curative-care-of-illnesses-and-the-tre",
            label="all components of the curative care of illnesses and the treatment of injury, surgery performed, diagnostic and therapeutic procedures, and obstetric services, as long as those components do not involve an overnight stay",
            keywords_by_lang={
                "en": (
                    "all components of the curative care of illnesses and the treatment of injury, surgery performed, diagnostic and therapeutic procedures, and obstetric services, as long as those components do not involve an overnight stay",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="all-health-products-e-g-assistive-medical-pharmaceutical-and",
            label="all health products (e.g., assistive, medical, pharmaceutical and therapeutic) needed to deliver outpatient curative and rehabilitative services that are not separately priced from the services of the provider (e.g., specialist, physician, nurse or another type of health-care practitioner)",
            keywords_by_lang={
                "en": (
                    "all health products (e.g., assistive, medical, pharmaceutical and therapeutic) needed to deliver outpatient curative and rehabilitative services that are not separately priced from the services of the provider (e.g., specialist, physician, nurse or another type of health-care practitioner)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="outpatient-curative-and-rehabilitative-services-irrespective",
            label="outpatient curative and rehabilitative services irrespective of the type of provider, whether a specialist, physician or another type of health professional (e.g., a nurse or a midwife)",
            keywords_by_lang={
                "en": (
                    "outpatient curative and rehabilitative services irrespective of the type of provider, whether a specialist, physician or another type of health professional (e.g., a nurse or a midwife)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="outpatient-curative-and-rehabilitative-services-provided-in-",
            label="outpatient curative and rehabilitative services provided in any setting such as a hospital without including an overnight stay, or an individual consulting facility (e.g., a private office), a group consulting facility, the patient’s home or any other non-hospital setting, including on the street",
            keywords_by_lang={
                "en": (
                    "outpatient curative and rehabilitative services provided in any setting such as a hospital without including an overnight stay, or an individual consulting facility (e.g., a private office), a group consulting facility, the patient’s home or any other non-hospital setting, including on the street",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="physical-psychological-and-speech-therapy-which-includes-the",
            label="physical, psychological and speech therapy, which includes the services of chiropractors; physiotherapists and physical therapists; speech therapists; audiologists; and inhalation and respiratory therapists, among others",
            keywords_by_lang={
                "en": (
                    "physical, psychological and speech therapy, which includes the services of chiropractors; physiotherapists and physical therapists; speech therapists; audiologists; and inhalation and respiratory therapists, among others",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.2.3.2": (
        SubLabel(
            id="all-health-products-e-g-assistive-medical-pharmaceutical-and",
            label="all health products (e.g., assistive, medical, pharmaceutical and therapeutic), diagnostic imaging services and medical laboratory services needed for the delivery of outpatient services priced jointly with the service of the provider (specialist, physician, nurse or another type of health-care practitioner)",
            keywords_by_lang={
                "en": (
                    "all health products (e.g., assistive, medical, pharmaceutical and therapeutic), diagnostic imaging services and medical laboratory services needed for the delivery of outpatient services priced jointly with the service of the provider (specialist, physician, nurse or another type of health-care practitioner)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-and-nursing-services-designed-to-maintain-persons-in",
            label="medical and nursing services designed to maintain persons (including the elderly and persons with disabilities) in their own home",
            keywords_by_lang={
                "en": (
                    "medical and nursing services designed to maintain persons (including the elderly and persons with disabilities) in their own home",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-medical-services-delivered-to-maintain-persons-in-their-",
            label="non-medical services delivered to maintain persons in their own home that are integrated into a package of care services and priced jointly with the other services",
            keywords_by_lang={
                "en": (
                    "non-medical services delivered to maintain persons in their own home that are integrated into a package of care services and priced jointly with the other services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="nursing-care-delivered-at-home-including-care-aimed-at-retar",
            label="nursing care delivered at home, including care aimed at retarding or reducing deterioration or maintaining functionality (e.g., nasogastric feeding) and care provided for the management of chronic diseases (e.g., administration of psychiatric prescription medications)",
            keywords_by_lang={
                "en": (
                    "nursing care delivered at home, including care aimed at retarding or reducing deterioration or maintaining functionality (e.g., nasogastric feeding) and care provided for the management of chronic diseases (e.g., administration of psychiatric prescription medications)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-medical-day-care-centres-including-serv",
            label="services provided by medical day-care centres, including services for the elderly and persons with disabilities",
            keywords_by_lang={
                "en": (
                    "services provided by medical day-care centres, including services for the elderly and persons with disabilities",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="treatment-in-hospitals-provided-in-the-course-of-home-based-",
            label="treatment in hospitals, provided in the course of home-based long-term care, which does not entail an overnight stay (e.g., dialysis)",
            keywords_by_lang={
                "en": (
                    "treatment in hospitals, provided in the course of home-based long-term care, which does not entail an overnight stay (e.g., dialysis)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.3.1.0": (
        SubLabel(
            id="all-medical-services-required-to-deliver-inpatient-care-duri",
            label="all medical services required to deliver inpatient care during an overnight stay even if separately priced (e.g., laboratory tests, diagnostic imaging services);",
            keywords_by_lang={
                "en": (
                    "all medical services required to deliver inpatient care during an overnight stay even if separately priced (e.g., laboratory tests, diagnostic imaging services);",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="beauty-treatments-performed-in-a-hospital-e-g-cosmetic-surge",
            label="beauty treatments performed in a hospital (e.g., cosmetic surgery, other than reconstructive)",
            keywords_by_lang={
                "en": (
                    "beauty treatments performed in a hospital (e.g., cosmetic surgery, other than reconstructive)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="curative-and-rehabilitative-services-provided-for-treatment-",
            label="curative and rehabilitative services provided for treatment and/or care (including dental treatment and/or care) that requires an overnight stay, as delivered by all types of providers (e.g., hospitals, nursing care facilities and facilities that, while classified as ambulatory care providers, occasionally perform procedures requiring overnight accommodation; alcohol and drug rehabilitation facilities (other than licensed hospitals); mental health convalescent homes and hospitals; and other types of health facilities located within an establishment that accommodates patients who require an overnight stay;",
            keywords_by_lang={
                "en": (
                    "curative and rehabilitative services provided for treatment and/or care (including dental treatment and/or care) that requires an overnight stay, as delivered by all types of providers (e.g., hospitals, nursing care facilities and facilities that, while classified as ambulatory care providers, occasionally perform procedures requiring overnight accommodation; alcohol and drug rehabilitation facilities (other than licensed hospitals); mental health convalescent homes and hospitals; and other types of health facilities located within an establishment that accommodates patients who require an overnight stay;",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medicines-and-health-products-medical-assistive-needed-in-th",
            label="medicines and health products (medical, assistive) needed in the delivery of inpatient services during the overnight stay, even if separately priced from the inpatient care services",
            keywords_by_lang={
                "en": (
                    "medicines and health products (medical, assistive) needed in the delivery of inpatient services during the overnight stay, even if separately priced from the inpatient care services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="patient-accommodation-services-including-meal-service-and-cl",
            label="patient accommodation services including meal service and cleaning, even if separately priced from the inpatient care services; and the hosting of the patient’s relatives, if indispensable, also if separately priced",
            keywords_by_lang={
                "en": (
                    "patient accommodation services including meal service and cleaning, even if separately priced from the inpatient care services; and the hosting of the patient’s relatives, if indispensable, also if separately priced",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.3.2.0": (
        SubLabel(
            id="all-medical-services-needed-for-the-delivery-of-inpatient-ca",
            label="all medical services needed for the delivery of inpatient care services during an overnight stay (e.g., laboratory tests, diagnostic imaging services)",
            keywords_by_lang={
                "en": (
                    "all medical services needed for the delivery of inpatient care services during an overnight stay (e.g., laboratory tests, diagnostic imaging services)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medicines-and-health-products-medical-assistive-needed-in-th",
            label="medicines and health products (medical, assistive) needed in the delivery of inpatient services during an overnight stay",
            keywords_by_lang={
                "en": (
                    "medicines and health products (medical, assistive) needed in the delivery of inpatient services during an overnight stay",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="patient-accommodation-services-including-meal-service-and-cl",
            label="patient accommodation services including meal service and cleaning, even if separately priced from the impatient long-term care services; and services associated with the hosting of a patient’s relatives, if indispensable, during the patient’s overnight stay, also if separately priced",
            keywords_by_lang={
                "en": (
                    "patient accommodation services including meal service and cleaning, even if separately priced from the impatient long-term care services; and services associated with the hosting of a patient’s relatives, if indispensable, during the patient’s overnight stay, also if separately priced",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-medical-retirement-homes-for-the-elderly-and-med",
            label="services of medical retirement homes for the elderly and medical residences for persons with disabilities",
            keywords_by_lang={
                "en": (
                    "services of medical retirement homes for the elderly and medical residences for persons with disabilities",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-nursing-homes-rest-homes-offering-nursing-care",
            label="services of nursing homes; rest homes offering nursing care",
            keywords_by_lang={
                "en": ("services of nursing homes; rest homes offering nursing care",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-palliative-care-facilities-for-the-terminally-il",
            label="services of palliative care facilities for the terminally ill",
            keywords_by_lang={
                "en": ("services of palliative care facilities for the terminally ill",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-residential-mental-retardation-facilities-and-me",
            label="services of residential mental retardation facilities; and mental health and substance abuse facilities for chronic patients (e.g., those with dementia)",
            keywords_by_lang={
                "en": (
                    "services of residential mental retardation facilities; and mental health and substance abuse facilities for chronic patients (e.g., those with dementia)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-skilled-nursing-facilities",
            label="services of skilled nursing facilities",
            keywords_by_lang={"en": ("services of skilled nursing facilities",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-teaching-nursing-homes",
            label="services of teaching nursing homes",
            keywords_by_lang={"en": ("services of teaching nursing homes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-medical-convalescent-homes-and-convales",
            label="services provided by medical convalescent homes and convalescent hospitals; homes for the elderly offering nursing care; inpatient care hospices",
            keywords_by_lang={
                "en": (
                    "services provided by medical convalescent homes and convalescent hospitals; homes for the elderly offering nursing care; inpatient care hospices",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.4.1.0": (
        SubLabel(
            id="diagnostic-imaging-services-including-all-diagnostic-imaging",
            label="diagnostic imaging services including all diagnostic imaging methods (i.e. CT, MRI, sonography); imagining diagnosis comprises a variety of services that employ imaging technology, such as X-rays and radiation for the diagnosis and monitoring of patients",
            keywords_by_lang={
                "en": (
                    "diagnostic imaging services including all diagnostic imaging methods (i.e. CT, MRI, sonography); imagining diagnosis comprises a variety of services that employ imaging technology, such as X-rays and radiation for the diagnosis and monitoring of patients",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-medical-analysis-laboratories-e-g-urine-blood-te",
            label="services of medical analysis laboratories (e.g., urine/blood tests)",
            keywords_by_lang={
                "en": (
                    "services of medical analysis laboratories (e.g., urine/blood tests)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "06.4.2.0": (
        SubLabel(
            id="ambulance-services-for-individuals-with-or-without-emergency",
            label="ambulance services for individuals, with or without emergency rescue",
            keywords_by_lang={
                "en": (
                    "ambulance services for individuals, with or without emergency rescue",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-emergency-transportation-by-airplane-or-other-types-",
            label="medical emergency transportation by airplane or other types of vehicles, whether or not they have been specially adapted for medical purposes",
            keywords_by_lang={
                "en": (
                    "medical emergency transportation by airplane or other types of vehicles, whether or not they have been specially adapted for medical purposes",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-transport-services-memberships",
            label="medical transport services memberships",
            keywords_by_lang={"en": ("medical transport services memberships",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
}
