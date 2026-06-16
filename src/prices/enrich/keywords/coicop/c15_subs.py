"""Auto-generated sub_labels for COICOP class 15.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "15.1.0.0": (
        SubLabel(
            id="actual-rentals",
            label="Actual rentals",
            keywords_by_lang={
                "en": (
                    "Actual rentals",
                    "actual rentals",
                    "rent payments",
                    "rental fees",
                    "tenant rent",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="maintenance-services",
            label="Housing maintenance services",
            keywords_by_lang={
                "en": (
                    "Housing maintenance services",
                    "handyman services for housing",
                    "housing maintenance",
                    "minor repairs services",
                    "property maintenance",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="imputed-rentals",
            label="Imputed rentals",
            keywords_by_lang={
                "en": (
                    "Imputed rentals",
                    "imputed rentals",
                    "notional rent",
                    "owner-occupied rent",
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
    "15.2.1.0": (
        SubLabel(
            id="allergy-medicine",
            label="Allergy medication",
            keywords_by_lang={
                "en": (
                    "Allergy medication",
                    "allergy relief",
                    "allergy tablets",
                    "antihistamine",
                    "hay fever relief",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cold-flu-remedy",
            label="Cold and flu remedies",
            keywords_by_lang={
                "en": (
                    "Cold and flu remedies",
                    "cold and flu relief",
                    "cold medicine",
                    "cough syrup",
                    "decongestant",
                    "flu medicine",
                )
            },
            allowed_bases=frozenset({"count", "item", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="digestive-health-medicine",
            label="Digestive health medicine",
            keywords_by_lang={
                "en": (
                    "Digestive health medicine",
                    "antacids",
                    "anti-diarrhoeal medication",
                    "digestive aids",
                    "heartburn relief",
                    "laxatives",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="eye-ear-care-medicine",
            label="Eye and ear care medicine",
            keywords_by_lang={
                "en": (
                    "Eye and ear care medicine",
                    "ear drops",
                    "ear wax removal drops",
                    "eye drops",
                    "eye wash",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="first-aid-supplies",
            label="First aid supplies",
            keywords_by_lang={
                "en": (
                    "First aid supplies",
                    "antiseptic spray",
                    "bandages",
                    "first aid kits",
                    "gauze",
                    "plasters",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other pharmaceutical products",
            keywords_by_lang={"en": ("Other pharmaceutical products",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pain-relief-medication",
            label="Pain relief medication",
            keywords_by_lang={
                "en": (
                    "Pain relief medication",
                    "analgesics",
                    "pain relief syrup",
                    "pain relief tablets",
                    "painkillers",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="skin-care-medication",
            label="Skin care medication",
            keywords_by_lang={
                "en": (
                    "Skin care medication",
                    "antiseptic cream",
                    "dermatological treatment",
                    "eczema cream",
                    "medicated ointment",
                    "topical creams",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vitamins-supplements",
            label="Vitamins and supplements",
            keywords_by_lang={
                "en": (
                    "Vitamins and supplements",
                    "dietary supplements",
                    "herbal supplements",
                    "mineral supplements",
                    "multivitamins",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.2.0": (
        SubLabel(
            id="bandage-dressing",
            label="Bandages and dressings",
            keywords_by_lang={
                "en": (
                    "Bandages and dressings",
                    "adhesive bandage",
                    "bandage",
                    "gauze",
                    "medical tape",
                    "plaster",
                    "sterile dressing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="disinfectant-antiseptic",
            label="Disinfectants and antiseptics",
            keywords_by_lang={
                "en": (
                    "Disinfectants and antiseptics",
                    "antiseptic",
                    "disinfectant spray",
                    "hydrogen peroxide",
                    "iodine",
                    "rubbing alcohol",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="first-aid-kit",
            label="First aid kits",
            keywords_by_lang={
                "en": (
                    "First aid kits",
                    "emergency kit",
                    "first aid kit",
                    "medical kit",
                    "travel first aid kit",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hot-cold-pack",
            label="Hot and cold packs",
            keywords_by_lang={
                "en": (
                    "Hot and cold packs",
                    "cold pack",
                    "gel pack",
                    "hot pack",
                    "ice pack",
                    "thermal compress",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-test-kit",
            label="Medical diagnostic test kits",
            keywords_by_lang={
                "en": (
                    "Medical diagnostic test kits",
                    "blood glucose test strips",
                    "diagnostic kit",
                    "home test kit",
                    "pregnancy test",
                    "test kit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="thermometer",
            label="Medical thermometers",
            keywords_by_lang={
                "en": (
                    "Medical thermometers",
                    "digital thermometer",
                    "ear thermometer",
                    "forehead thermometer",
                    "infrared thermometer",
                    "thermometer",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="support-brace",
            label="Orthopedic supports and braces",
            keywords_by_lang={
                "en": (
                    "Orthopedic supports and braces",
                    "ankle support",
                    "compression sleeve",
                    "knee brace",
                    "support brace",
                    "wrist brace",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other", "Other medical products")},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.3.0": (
        SubLabel(
            id="glucometers",
            label='Blood glucose meters",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Blood glucose meters",synonyms:[',
                    'blood sugar monitor",',
                    'glucometer",',
                    'glucose test meter",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="blood-pressure-monitors",
            label='Blood pressure monitors",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Blood pressure monitors",synonyms:[',
                    'bp machine",',
                    'digital blood pressure monitor",',
                    'sphygmomanometer",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hearing-aids",
            label='Hearing aids",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Hearing aids",synonyms:[',
                    'auditory implant",',
                    'behind-the-ear aid",',
                    'hearing aid",',
                    'in-the-ear aid",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-cushions",
            label='Medical cushions and supports",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Medical cushions and supports",synonyms:[',
                    'medical pillow",',
                    'orthopaedic cushion",',
                    'pressure relief cushion",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mobility-aids",
            label='Mobility aids",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Mobility aids",synonyms:[',
                    'cane",',
                    'crutches",',
                    'rollator",',
                    'walker",',
                    'walking stick",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nebulizers",
            label='Nebulizers and inhalers",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Nebulizers and inhalers",synonyms:[',
                    'asthma nebulizer",',
                    'medical inhaler",',
                    'nebulizer",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="orthopaedic-braces",
            label='Orthopaedic braces and supports",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Orthopaedic braces and supports",synonyms:[',
                    'ankle support",',
                    'back brace",',
                    'knee brace",',
                    'orthopaedic support",',
                    'wrist support",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={
                "en": ("Other", 'Other therapeutic appliances",synonyms:[]}]}')
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wheelchairs",
            label='Wheelchairs",synonyms:[',
            keywords_by_lang={
                "en": (
                    'Wheelchairs",synonyms:[',
                    'electric wheelchair",',
                    'manual wheelchair",',
                    'powered mobility scooter",',
                    'wheelchair accessory",',
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.4.0": (
        SubLabel(
            id="allied-health-service",
            label="Allied health service",
            keywords_by_lang={
                "en": (
                    "Allied health service",
                    "clinical psychology service",
                    "occupational therapy",
                    "physiotherapy service",
                    "podiatry service",
                    "speech therapy",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="general-practitioner-visit",
            label="GP visit",
            keywords_by_lang={
                "en": (
                    "GP visit",
                    "General practitioner visit",
                    "doctor office visit",
                    "family doctor visit",
                    "primary care consultation",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-diagnostic-test",
            label="Medical diagnostic test",
            keywords_by_lang={
                "en": (
                    "Medical diagnostic test",
                    "blood test",
                    "diagnostic imaging",
                    "lab test",
                    "medical scan",
                    "medical screening",
                    "x-ray service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="medical-injection-vaccination",
            label="Medical injection or vaccination",
            keywords_by_lang={
                "en": (
                    "Medical injection or vaccination",
                    "flu shot service",
                    "therapeutic injection",
                    "travel vaccination",
                    "vaccination service",
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
            id="outpatient-surgery",
            label="Outpatient surgery",
            keywords_by_lang={
                "en": (
                    "Outpatient surgery",
                    "ambulatory procedure",
                    "day surgery",
                    "minor surgery",
                    "outpatient procedure",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="specialist-consultation",
            label="Specialist consultation",
            keywords_by_lang={
                "en": (
                    "Specialist consultation",
                    "consultant appointment",
                    "medical specialist service",
                    "specialist visit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.5.0": (
        SubLabel(
            id="dental-checkup",
            label="Dental checkup",
            keywords_by_lang={
                "en": (
                    "Dental checkup",
                    "dental cleaning",
                    "dental exam",
                    "preventive dental care",
                    "prophylaxis",
                    "routine dental exam",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-crown-bridge",
            label="Dental crown or bridge",
            keywords_by_lang={
                "en": (
                    "Dental crown or bridge",
                    "dental bridge",
                    "dental crown",
                    "dental prosthetics",
                    "tooth cap",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-extraction",
            label="Dental extraction",
            keywords_by_lang={
                "en": (
                    "Dental extraction",
                    "tooth extraction",
                    "tooth removal",
                    "wisdom tooth extraction",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-filling",
            label="Dental filling",
            keywords_by_lang={
                "en": (
                    "Dental filling",
                    "amalgam filling",
                    "composite filling",
                    "dental restoration",
                    "tooth filling",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-braces",
            label="Orthodontic treatment",
            keywords_by_lang={
                "en": (
                    "Orthodontic treatment",
                    "aligners",
                    "dental braces",
                    "orthodontics",
                    "teeth straightening",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other dental services",
            keywords_by_lang={"en": ("Other dental services",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-root-canal",
            label="Root canal treatment",
            keywords_by_lang={
                "en": (
                    "Root canal treatment",
                    "endodontic treatment",
                    "root canal",
                    "root canal therapy",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dental-whitening",
            label="Teeth whitening",
            keywords_by_lang={
                "en": (
                    "Teeth whitening",
                    "dental whitening",
                    "professional whitening",
                    "teeth bleaching",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.6.0": (
        SubLabel(
            id="acupuncture-services",
            label="Acupuncture services",
            keywords_by_lang={
                "en": (
                    "Acupuncture services",
                    "acupuncture",
                    "acupuncturist visit",
                    "alternative therapy",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="audiology-services",
            label="Audiology services",
            keywords_by_lang={
                "en": (
                    "Audiology services",
                    "audiologist visit",
                    "audiology",
                    "hearing assessment",
                    "hearing test",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="chiropractic-services",
            label="Chiropractic services",
            keywords_by_lang={
                "en": (
                    "Chiropractic services",
                    "chiropractic adjustment",
                    "chiropractic care",
                    "chiropractor",
                    "spine therapy",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nutrition-counseling",
            label="Nutrition counseling",
            keywords_by_lang={
                "en": (
                    "Nutrition counseling",
                    "dietary advice",
                    "dietitian services",
                    "nutritional counseling",
                    "nutritionist visit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="occupational-therapy",
            label="Occupational therapy",
            keywords_by_lang={
                "en": (
                    "Occupational therapy",
                    "occupational therapist visit",
                    "occupational therapy",
                    "ot services",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="optometry-services",
            label="Optometry services (non-optical)",
            keywords_by_lang={
                "en": (
                    "Optometry services (non-optical)",
                    "eye exam",
                    "optometrist visit",
                    "optometry",
                    "vision test",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other outpatient paramedical services",
            keywords_by_lang={"en": ("Other outpatient paramedical services",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="physiotherapy",
            label="Physiotherapy",
            keywords_by_lang={
                "en": (
                    "Physiotherapy",
                    "physical therapy",
                    "physio",
                    "physiotherapist visit",
                    "physiotherapy",
                    "rehabilitation services",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="podiatry-services",
            label="Podiatry services",
            keywords_by_lang={
                "en": (
                    "Podiatry services",
                    "chiropody",
                    "foot care services",
                    "podiatrist",
                    "podiatry",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="psychotherapy-counseling",
            label="Psychotherapy and counseling",
            keywords_by_lang={
                "en": (
                    "Psychotherapy and counseling",
                    "counseling services",
                    "mental health counseling",
                    "psychologist visit",
                    "psychotherapy",
                    "talk therapy",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="speech-therapy",
            label="Speech therapy",
            keywords_by_lang={
                "en": (
                    "Speech therapy",
                    "speech and language therapy",
                    "speech pathology",
                    "speech therapist visit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.7.0": (
        SubLabel(
            id="diagnostic-imaging-and-testing",
            label="Diagnostic imaging and testing",
            keywords_by_lang={
                "en": (
                    "Diagnostic imaging and testing",
                    "ct scan",
                    "hospital diagnostic test",
                    "hospital lab test",
                    "hospital radiology service",
                    "mri scan",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="emergency-department-services",
            label="ER visit",
            keywords_by_lang={
                "en": (
                    "ER visit",
                    "Emergency department services",
                    "casualty department service",
                    "emergency admission",
                    "emergency room service",
                    "urgent care hospital service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="inpatient-hospital-care",
            label="Inpatient hospital care",
            keywords_by_lang={
                "en": (
                    "Inpatient hospital care",
                    "hospital admission",
                    "inpatient care",
                    "inpatient treatment",
                    "overnight hospital stay",
                    "ward care",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="maternity-services",
            label="Maternity services",
            keywords_by_lang={
                "en": (
                    "Maternity services",
                    "childbirth care",
                    "hospital maternity care",
                    "labor and delivery service",
                    "obstetric hospital service",
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
            id="outpatient-hospital-services",
            label="Outpatient hospital services",
            keywords_by_lang={
                "en": (
                    "Outpatient hospital services",
                    "ambulatory care",
                    "consultation service",
                    "day patient service",
                    "hospital outpatient clinic",
                    "outpatient care",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="rehabilitation-services",
            label="Rehabilitation services",
            keywords_by_lang={
                "en": (
                    "Rehabilitation services",
                    "hospital rehabilitation",
                    "in-hospital physiotherapy",
                    "physical rehabilitation service",
                    "post-operative rehab",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="surgical-services",
            label="Surgical services",
            keywords_by_lang={
                "en": (
                    "Surgical services",
                    "hospital surgery",
                    "in-hospital surgical procedure",
                    "operation service",
                    "theatre service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.2.8.0": (
        SubLabel(
            id="medical-consultation",
            label="GP appointment",
            keywords_by_lang={
                "en": (
                    "GP appointment",
                    "Medical consultation",
                    "clinical consultation",
                    "doctor visit",
                    "medical checkup",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="laboratory-test",
            label="Laboratory test",
            keywords_by_lang={
                "en": (
                    "Laboratory test",
                    "blood test",
                    "diagnostic test",
                    "medical lab services",
                    "pathology services",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nursing-care",
            label="Nursing care",
            keywords_by_lang={
                "en": (
                    "Nursing care",
                    "community nursing",
                    "district nursing",
                    "home nursing service",
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
            id="public-health-screening",
            label="Public health screening",
            keywords_by_lang={
                "en": (
                    "Public health screening",
                    "health screening program",
                    "preventive health check",
                    "wellness screening",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vaccination-service",
            label="Vaccination service",
            keywords_by_lang={
                "en": (
                    "Vaccination service",
                    "flu shot clinic",
                    "immunization service",
                    "vaccine administration",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.3.1.0": (
        SubLabel(
            id="gym-membership",
            label="Gym and fitness club memberships",
            keywords_by_lang={
                "en": (
                    "Gym and fitness club memberships",
                    "exercise studio membership",
                    "fitness club access",
                    "gym membership",
                    "health club pass",
                    "personal training session",
                )
            },
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="leisure-activity-fee",
            label="Leisure activity fees",
            keywords_by_lang={
                "en": (
                    "Leisure activity fees",
                    "activity participation fee",
                    "amusement arcade fee",
                    "billiards table rental",
                    "recreational venue admission",
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
            id="recreational-club-fee",
            label="Recreational club fees",
            keywords_by_lang={
                "en": (
                    "Recreational club fees",
                    "bridge club fees",
                    "recreational membership",
                    "social club fee",
                    "yacht club fees",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="recreational-facility-hire",
            label="Recreational facility hire",
            keywords_by_lang={
                "en": (
                    "Recreational facility hire",
                    "bowling alley lane hire",
                    "court rental",
                    "pitch hire",
                    "skating rink admission",
                    "sports field rental",
                    "swimming pool entry",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="event-ticket-sporting",
            label="Sporting event tickets",
            keywords_by_lang={
                "en": (
                    "Sporting event tickets",
                    "game admission",
                    "match tickets",
                    "sporting spectator fee",
                    "sports event tickets",
                    "stadium tickets",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-lesson",
            label="Sports lessons and coaching",
            keywords_by_lang={
                "en": (
                    "Sports lessons and coaching",
                    "golf lessons",
                    "private sports lesson",
                    "sports coaching",
                    "sports instruction",
                    "swimming lessons",
                    "tennis coaching",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.3.2.0": (
        SubLabel(
            id="cinema-ticket",
            label="Cinema tickets",
            keywords_by_lang={
                "en": (
                    "Cinema tickets",
                    "cinema entry",
                    "film screening fee",
                    "movie theatre admission",
                    "movie ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="historical-site-admission",
            label="Historical site admissions",
            keywords_by_lang={
                "en": (
                    "Historical site admissions",
                    "archaeological site ticket",
                    "castle admission",
                    "heritage site entry",
                    "monument entrance fee",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="museum-admission",
            label="Museum and gallery admissions",
            keywords_by_lang={
                "en": (
                    "Museum and gallery admissions",
                    "art gallery entry",
                    "exhibition pass",
                    "museum admission fees",
                    "museum membership",
                    "museum ticket",
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
            id="theatre-concert-ticket",
            label="Theatre and concert tickets",
            keywords_by_lang={
                "en": (
                    "Theatre and concert tickets",
                    "ballet ticket",
                    "concert ticket",
                    "live performance admission",
                    "musical show ticket",
                    "opera ticket",
                    "theatre ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="zoo-botanical-garden-admission",
            label="Zoo and botanical garden admissions",
            keywords_by_lang={
                "en": (
                    "Zoo and botanical garden admissions",
                    "aquarium admission",
                    "botanical garden entry",
                    "nature park entrance fee",
                    "zoo ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.1.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pre-primary-school-tuition",
            label="Pre-primary school tuition",
            keywords_by_lang={
                "en": (
                    "Pre-primary school tuition",
                    "daycare education services",
                    "kindergarten tuition",
                    "nursery school fees",
                    "pre-k fees",
                    "preschool tuition",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="primary-school-tuition",
            label="Primary school tuition",
            keywords_by_lang={
                "en": (
                    "Primary school tuition",
                    "elementary school tuition",
                    "grade school tuition",
                    "primary education costs",
                    "primary school fees",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.2.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="secondary-education-ancillary-services",
            label="Secondary education ancillary services",
            keywords_by_lang={
                "en": (
                    "Secondary education ancillary services",
                    "educational support services",
                    "school guidance counseling",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="secondary-school-exam-fees",
            label="Secondary school examination fees",
            keywords_by_lang={
                "en": (
                    "Secondary school examination fees",
                    "certification exam fees",
                    "exam registration fees",
                    "standardized test fees for schools",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="secondary-school-tuition",
            label="Secondary school tuition",
            keywords_by_lang={
                "en": (
                    "Secondary school tuition",
                    "high school tuition",
                    "middle school fees",
                    "secondary education fees",
                    "secondary school enrollment fees",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tutoring-services",
            label="Tutoring services",
            keywords_by_lang={
                "en": (
                    "Tutoring services",
                    "academic tutoring",
                    "homework help",
                    "private tutoring",
                    "subject coaching",
                    "supplementary education",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.3.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="post-secondary-bridge-course",
            label="Post-secondary bridge courses",
            keywords_by_lang={
                "en": (
                    "Post-secondary bridge courses",
                    "academic bridging program",
                    "bridge program",
                    "foundation course",
                    "preparatory course",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="specialized-adult-education",
            label="Specialized adult education",
            keywords_by_lang={
                "en": (
                    "Specialized adult education",
                    "adult professional development",
                    "non-tertiary education service",
                    "specialized trade training",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vocational-training-programs",
            label="Vocational training programs",
            keywords_by_lang={
                "en": (
                    "Vocational training programs",
                    "certificate program",
                    "professional certification",
                    "technical training course",
                    "trade school program",
                    "vocational training",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.4.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.5.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.4.6.0": (
        SubLabel(
            id="_other",
            label="Other",
            keywords_by_lang={"en": ("Other",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "15.5.0.0": (
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
