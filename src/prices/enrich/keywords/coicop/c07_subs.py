"""Auto-generated sub_labels for COICOP class 07.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "07.1.1.1": (
        SubLabel(
            id="new-motor-cars-passenger-vans-station-wagons-estate-cars-spo",
            label="new motor cars, passenger vans, station wagons, estate cars, sport utility vehicles (SUVs), off-road vehicles, pickup trucks and the like with either two- or four-wheel drive",
            keywords_by_lang={
                "en": (
                    "new motor cars, passenger vans, station wagons, estate cars, sport utility vehicles (SUVs), off-road vehicles, pickup trucks and the like with either two- or four-wheel drive",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="new-racing-motor-vehicles-and-vehicles-for-shows",
            label="new racing motor vehicles and vehicles for shows",
            keywords_by_lang={
                "en": ("new racing motor vehicles and vehicles for shows",)
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
    "07.1.1.2": (
        SubLabel(
            id="used-or-second-hand-motor-cars-passenger-vans-station-wagons",
            label="used or second-hand motor cars, passenger vans, station wagons, estate cars, sport utility vehicles (SUVs), off-road vehicles, pickup trucks and the like with either two- or four-wheel drive",
            keywords_by_lang={
                "en": (
                    "used or second-hand motor cars, passenger vans, station wagons, estate cars, sport utility vehicles (SUVs), off-road vehicles, pickup trucks and the like with either two- or four-wheel drive",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="used-or-second-hand-racing-motor-vehicles-and-vehicles-for-s",
            label="used or second-hand racing motor vehicles and vehicles for shows",
            keywords_by_lang={
                "en": (
                    "used or second-hand racing motor vehicles and vehicles for shows",
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
    "07.1.2.0": (
        SubLabel(
            id="motor-scooters-mopeds-and-motorized-bicycles-with-combustion",
            label="motor scooters, mopeds and motorized bicycles with combustion engines",
            keywords_by_lang={
                "en": (
                    "motor scooters, mopeds and motorized bicycles with combustion engines",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="motorcycles-of-all-types-including-those-with-electric-motor",
            label="motorcycles of all types including those with electric motors",
            keywords_by_lang={
                "en": ("motorcycles of all types including those with electric motors",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sidecars",
            label="sidecars",
            keywords_by_lang={"en": ("sidecars",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="snowmobiles",
            label="snowmobiles",
            keywords_by_lang={"en": ("snowmobiles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="used-or-second-hand-motorcycles",
            label="used or second-hand motorcycles",
            keywords_by_lang={"en": ("used or second-hand motorcycles",)},
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
    "07.1.3.0": (
        SubLabel(
            id="bicycles-tricycles-and-other-cycles",
            label="bicycles, tricycles and other cycles",
            keywords_by_lang={"en": ("bicycles, tricycles and other cycles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cycle-rickshaws",
            label="cycle rickshaws",
            keywords_by_lang={"en": ("cycle rickshaws",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-bicycles-e-bikes-and-pedelecs",
            label="electric bicycles (e-bikes) and pedelecs",
            keywords_by_lang={"en": ("electric bicycles (e-bikes) and pedelecs",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-kick-scooters",
            label="electric kick scooters",
            keywords_by_lang={"en": ("electric kick scooters",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bicycle",
            label="bicycle",
            keywords_by_lang={"auto": ("bicycle",)},
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
    "07.1.4.0": (
        SubLabel(
            id="animal-drawn-vehicles",
            label="animal-drawn vehicles",
            keywords_by_lang={"en": ("animal-drawn vehicles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="animals-used-to-draw-vehicles-and-related-equipment-e-g-yoke",
            label="animals used to draw vehicles and related equipment (e.g., yokes, collars, harnesses, bridles, reins)",
            keywords_by_lang={
                "en": (
                    "animals used to draw vehicles and related equipment (e.g., yokes, collars, harnesses, bridles, reins)",
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
    "07.2.1.1": (
        SubLabel(
            id="new-used-or-retreaded-including-inner-tubes-for-cars-bicycle",
            label="new, used or retreaded, including inner tubes for cars, bicycles, motorcycles and so on",
            keywords_by_lang={
                "en": (
                    "new, used or retreaded, including inner tubes for cars, bicycles, motorcycles and so on",
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
    "07.2.1.2": (
        SubLabel(
            id="rims",
            label="rims",
            keywords_by_lang={"en": ("rims",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="spark-plugs-batteries-shock-absorbers-filters-pumps-and-othe",
            label="spark plugs, batteries, shock absorbers, filters, pumps and other parts for personal transport equipment",
            keywords_by_lang={
                "en": (
                    "spark plugs, batteries, shock absorbers, filters, pumps and other parts for personal transport equipment",
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
    "07.2.1.3": (
        SubLabel(
            id="global-positioning-system-gps-satellite-based-radionavigatio",
            label="Global Positioning System (GPS) (satellite-based radionavigation) equipment for personal transport",
            keywords_by_lang={
                "en": (
                    "Global Positioning System (GPS) (satellite-based radionavigation) equipment for personal transport",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bicycle-trailers-baskets-and-other-accessories",
            label="bicycle trailers, baskets and other accessories",
            keywords_by_lang={
                "en": ("bicycle trailers, baskets and other accessories",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="car-motorcycle-and-bicycle-seats-for-babies-and-children",
            label="car, motorcycle and bicycle seats for babies and children",
            keywords_by_lang={
                "en": ("car, motorcycle and bicycle seats for babies and children",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="chargers-for-electric-vehicles",
            label="chargers for electric vehicles",
            keywords_by_lang={"en": ("chargers for electric vehicles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="crash-helmets-equipped-with-cameras",
            label="crash helmets equipped with cameras",
            keywords_by_lang={"en": ("crash helmets equipped with cameras",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dash-cameras",
            label="dash cameras",
            keywords_by_lang={"en": ("dash cameras",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fire-extinguishers-for-transport-equipment",
            label="fire extinguishers for transport equipment",
            keywords_by_lang={"en": ("fire extinguishers for transport equipment",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hubcaps-if-purchased-separately",
            label="hubcaps, if purchased separately",
            keywords_by_lang={"en": ("hubcaps, if purchased separately",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="motorcycle-and-bicycle-crash-helmets",
            label="motorcycle and bicycle crash helmets",
            keywords_by_lang={"en": ("motorcycle and bicycle crash helmets",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="products-used-specifically-for-the-cleaning-and-maintenance-",
            label="products used specifically for the cleaning and maintenance of transport equipment, such as paints, chrome cleaners, sealing compounds and bodywork polishes; covers for motor cars, motorcycles and so on",
            keywords_by_lang={
                "en": (
                    "products used specifically for the cleaning and maintenance of transport equipment, such as paints, chrome cleaners, sealing compounds and bodywork polishes; covers for motor cars, motorcycles and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="snow-chains-roof-racks-cargo-roof-boxes",
            label="snow chains, roof racks, cargo roof boxes",
            keywords_by_lang={"en": ("snow chains, roof racks, cargo roof boxes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="car-cover",
            label="car cover",
            keywords_by_lang={"auto": ("car cover",)},
            allowed_bases=frozenset({"item"}),
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
    "07.2.2.1": (
        SubLabel(
            id="diesel-fuel",
            label="diesel fuel",
            keywords_by_lang={"en": ("diesel fuel",)},
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
    "07.2.2.2": (
        SubLabel(
            id="petrol-gasoline-in-north-america",
            label="petrol (gasoline in North America)",
            keywords_by_lang={"en": ("petrol (gasoline in North America)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="petrol-gasoline-blends-e-g-petrol-with-10-per-cent-ethanol-c",
            label="petrol/gasoline blends (e.g., petrol with 10 per cent ethanol content)",
            keywords_by_lang={
                "en": (
                    "petrol/gasoline blends (e.g., petrol with 10 per cent ethanol content)",
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
    "07.2.2.3": (
        SubLabel(
            id="electricity-used-as-fuel-for-personal-transport-when-priced-",
            label="electricity used as fuel for personal transport when priced separately from other electricity",
            keywords_by_lang={
                "en": (
                    "electricity used as fuel for personal transport when priced separately from other electricity",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hydrogen",
            label="hydrogen",
            keywords_by_lang={
                "en": (
                    "hydrogen",
                    "H2 fuel",
                    "Hydrogen fuel",
                    "hydrogen gas for vehicles",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="liquefied-petroleum-gas-lpg-natural-gas-compressed-natural-g",
            label="liquefied petroleum gas (LPG), natural gas (compressed natural gas (CNG)), liquefied natural gas (LNG), alcohol, biofuels (ethanol, methanol), methane and two-stroke mixtures",
            keywords_by_lang={
                "en": (
                    "liquefied petroleum gas (LPG), natural gas (compressed natural gas (CNG)), liquefied natural gas (LNG), alcohol, biofuels (ethanol, methanol), methane and two-stroke mixtures",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="two-stroke-mixture",
            label="2-stroke fuel",
            keywords_by_lang={
                "en": (
                    "2-stroke fuel",
                    "Two-stroke mixture",
                    "oil-gasoline mix",
                    "pre-mix fuel",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="biofuel-ethanol",
            label="Biofuel (ethanol)",
            keywords_by_lang={
                "en": (
                    "Biofuel (ethanol)",
                    "E85",
                    "bioethanol",
                    "ethanol",
                    "fuel ethanol",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cng",
            label="CNG",
            keywords_by_lang={
                "en": (
                    "CNG",
                    "Compressed natural gas (CNG)",
                    "compressed natural gas",
                    "natural gas vehicle fuel",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electricity-ev-charging",
            label="EV charging",
            keywords_by_lang={
                "en": (
                    "EV charging",
                    "Electricity for vehicles",
                    "car charging station electricity",
                    "electric vehicle fuel",
                    "public charging electricity",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lng",
            label="LNG",
            keywords_by_lang={
                "en": ("LNG", "Liquefied natural gas (LNG)", "liquefied natural gas")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lpg",
            label="LPG",
            keywords_by_lang={
                "en": (
                    "LPG",
                    "Liquefied petroleum gas (LPG)",
                    "autogas",
                    "liquefied petroleum gas",
                    "propane for cars",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="methanol",
            label="Methanol",
            keywords_by_lang={
                "en": ("Methanol", "fuel methanol", "methanol", "methyl alcohol")
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
    "07.2.2.4": (
        SubLabel(
            id="lubricants-brake-and-transmission-fluids-coolants-and-additi",
            label="lubricants, brake and transmission fluids, coolants and additives",
            keywords_by_lang={
                "en": (
                    "lubricants, brake and transmission fluids, coolants and additives",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="brake-fluid",
            label="Brake fluid",
            keywords_by_lang={
                "en": (
                    "Brake fluid",
                    "brake hydraulic fluid",
                    "dot 3 fluid",
                    "dot 4 fluid",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="engine-coolant",
            label="Engine coolant",
            keywords_by_lang={
                "en": (
                    "Engine coolant",
                    "antifreeze",
                    "engine coolant concentrate",
                    "radiator coolant",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="engine-oil",
            label="Engine oil",
            keywords_by_lang={
                "en": (
                    "Engine oil",
                    "crankcase oil",
                    "engine lubricant",
                    "lubricant oil",
                    "motor oil",
                    "synthetic oil",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fuel-additive",
            label="Fuel additive",
            keywords_by_lang={
                "en": (
                    "Fuel additive",
                    "fuel treatment",
                    "gasoline additive",
                    "injector cleaner",
                    "octane booster",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="grease",
            label="Grease",
            keywords_by_lang={
                "en": (
                    "Grease",
                    "bearing grease",
                    "chassis grease",
                    "lubricating grease",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="oil-additive",
            label="Oil additive",
            keywords_by_lang={
                "en": (
                    "Oil additive",
                    "engine oil supplement",
                    "oil stabilizer",
                    "oil treatment",
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
            id="transmission-fluid",
            label="Transmission fluid",
            keywords_by_lang={
                "en": (
                    "Transmission fluid",
                    "atf",
                    "automatic transmission fluid",
                    "gear oil",
                    "manual transmission gear oil",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.2.3.0": (
        SubLabel(
            id="installation-of-car-cameras",
            label="installation of car cameras",
            keywords_by_lang={"en": ("installation of car cameras",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="locksmith-services-for-cars",
            label="locksmith services for cars",
            keywords_by_lang={"en": ("locksmith services for cars",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-purchased-for-the-maintenance-and-repair-of-persona",
            label="services purchased for the maintenance and repair of personal transport equipment, such as fitting of parts and accessories, tyre changing, wheel balancing, breakdown services, oil changes, greasing and washing",
            keywords_by_lang={
                "en": (
                    "services purchased for the maintenance and repair of personal transport equipment, such as fitting of parts and accessories, tyre changing, wheel balancing, breakdown services, oil changes, greasing and washing",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="breakdown-recovery-service",
            label="Breakdown and towing service",
            keywords_by_lang={
                "en": (
                    "Breakdown and towing service",
                    "breakdown recovery",
                    "car rescue",
                    "roadside assistance",
                    "towing service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-locksmith-service",
            label="Car locksmith service",
            keywords_by_lang={
                "en": (
                    "Car locksmith service",
                    "auto locksmith",
                    "car key replacement service",
                    "vehicle unlocking service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-repair-general",
            label="Car repair service",
            keywords_by_lang={
                "en": (
                    "Car repair service",
                    "auto repair",
                    "car service",
                    "mechanic service",
                    "vehicle maintenance",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-wash-service",
            label="Car washing and detailing",
            keywords_by_lang={
                "en": (
                    "Car washing and detailing",
                    "auto detailing",
                    "car cleaning",
                    "car wash service",
                    "vehicle wash",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-accessory-installation",
            label="Installation of parts and accessories",
            keywords_by_lang={
                "en": (
                    "Installation of parts and accessories",
                    "accessory fitting",
                    "car camera installation",
                    "dashboard camera installation",
                    "fitting of parts",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="oil-change-service",
            label="Oil change and greasing",
            keywords_by_lang={
                "en": (
                    "Oil change and greasing",
                    "car greasing",
                    "engine oil change",
                    "lube service",
                    "oil service",
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
            id="tyre-changing-service",
            label="Tyre changing and balancing",
            keywords_by_lang={
                "en": (
                    "Tyre changing and balancing",
                    "tire change",
                    "tire mounting",
                    "tyre fitting",
                    "wheel alignment",
                    "wheel balancing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.2.4.1": (
        SubLabel(
            id="charges-for-the-rental-of-parking-spaces-in-parking-garages-",
            label="charges for the rental of parking spaces in parking garages (including valet service), such as those located in shopping centres, for a few hours or less",
            keywords_by_lang={
                "en": (
                    "charges for the rental of parking spaces in parking garages (including valet service), such as those located in shopping centres, for a few hours or less",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parking-meters-regardless-of-form-of-payment-e-g-attendant-o",
            label="parking meters, regardless of form of payment (e.g., attendant or through parking meter)",
            keywords_by_lang={
                "en": (
                    "parking meters, regardless of form of payment (e.g., attendant or through parking meter)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parking-permits-valid-for-designated-areas-e-g-residential-p",
            label="parking permits valid for designated areas (e.g., residential parking permits)",
            keywords_by_lang={
                "en": (
                    "parking permits valid for designated areas (e.g., residential parking permits)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-municipal-street-parking",
            label="rental of municipal street parking",
            keywords_by_lang={"en": ("rental of municipal street parking",)},
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
        SubLabel(
            id="parking-garage",
            label="Parking garage",
            keywords_by_lang={
                "en": (
                    "Parking garage",
                    "multi-storey car park",
                    "parking deck",
                    "parking structure",
                    "shopping centre parking",
                    "short-term parking",
                    "valet parking",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="parking-permit",
            label="Parking permit",
            keywords_by_lang={
                "en": (
                    "Parking permit",
                    "on-street parking permit",
                    "parking authorization",
                    "parking pass",
                    "resident parking permit",
                    "zone parking permit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="street-parking",
            label="Street parking",
            keywords_by_lang={
                "en": (
                    "Street parking",
                    "curbside parking",
                    "municipal parking",
                    "on-street parking",
                    "parking meter",
                    "pay-and-display",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.2.4.2": (
        SubLabel(
            id="bridge-tolls-tunnel-tolls-motorway-tolls-and-so-on",
            label="bridge tolls, tunnel tolls, motorway tolls and so on",
            keywords_by_lang={
                "en": ("bridge tolls, tunnel tolls, motorway tolls and so on",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="charges-for-rental-or-purchase-of-electronic-tags-and-toll-d",
            label="charges for rental or purchase of electronic tags and toll devices",
            keywords_by_lang={
                "en": (
                    "charges for rental or purchase of electronic tags and toll devices",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bridge-toll",
            label="Bridge toll",
            keywords_by_lang={
                "en": (
                    "Bridge toll",
                    "bridge charge",
                    "bridge crossing fee",
                    "bridge fee",
                    "bridge toll",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electronic-toll-tag",
            label="Electronic toll tag",
            keywords_by_lang={
                "en": (
                    "Electronic toll tag",
                    "e-toll tag",
                    "electronic toll tag",
                    "toll pass device",
                    "toll payment device",
                    "transponder",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="motorway-toll",
            label="Motorway toll",
            keywords_by_lang={
                "en": (
                    "Motorway toll",
                    "expressway toll",
                    "highway toll",
                    "motorway toll",
                    "toll road charge",
                    "turnpike toll",
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
                "en": (
                    "Other",
                    'Other",synonyms:[]}]}final_result{\n  "entries": [\n    {\n      "id": "bridge-toll",\n      "label": "Bridge toll",\n      "synonyms": ["bridge toll", "bridge charge", "bridge fee", "bridge crossing fee"]\n    },\n    {\n      "id": "tunnel-toll",\n      "label": "Tunnel toll",\n      "synonyms": ["tunnel toll", "tunnel charge", "tunnel fee", "tunnel crossing fee"]\n    },\n    {\n      "id": "motorway-toll",\n      "label": "Motorway toll",\n      "synonyms": ["motorway toll", "highway toll", "turnpike toll", "toll road charge", "expressway toll"]\n    },\n    {\n      "id": "electronic-toll-tag",\n      "label": "Electronic toll tag",\n      "synonyms": ["electronic toll tag", "toll pass device", "transponder", "e-toll tag", "toll payment device"]\n    },\n    {\n      "id": "_other",\n      "label": "Other",\n      "synonyms": []\n    }\n  ]\n}\n}\n*/\n// Re-running final_result due to internal error in formatting block.\n{\n  "entries": [\n    {\n      "id": "bridge-toll",\n      "label": "Bridge toll",\n      "synonyms": ["bridge toll", "bridge charge", "bridge fee", "bridge crossing fee"]\n    },\n    {\n      "id": "tunnel-toll",\n      "label": "Tunnel toll",\n      "synonyms": ["tunnel toll", "tunnel charge", "tunnel fee", "tunnel crossing fee"]\n    },\n    {\n      "id": "motorway-toll",\n      "label": "Motorway toll",\n      "synonyms": ["motorway toll", "highway toll", "turnpike toll", "toll road charge", "expressway toll"]\n    },\n    {\n      "id": "electronic-toll-tag",\n      "label": "Electronic toll tag",\n      "synonyms": ["electronic toll tag", "toll pass device", "transponder", "e-toll tag", "toll payment device"]\n    },\n    {\n      "id": "_other",\n      "label": "Other",\n      "synonyms": []\n    }\n  ]\n}',
                )
            },
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tunnel-toll",
            label="Tunnel toll",
            keywords_by_lang={
                "en": (
                    "Tunnel toll",
                    "tunnel charge",
                    "tunnel crossing fee",
                    "tunnel fee",
                    "tunnel toll",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.2.4.3": (
        SubLabel(
            id="charges-associated-with-the-transfer-of-vehicle-ownership",
            label="charges associated with the transfer of vehicle ownership",
            keywords_by_lang={
                "en": ("charges associated with the transfer of vehicle ownership",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="driving-lessons-driving-tests-and-driving-licences",
            label="driving lessons, driving tests and driving licences",
            keywords_by_lang={
                "en": ("driving lessons, driving tests and driving licences",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="driving-lessons-driving-tests-and-driving-licences-associate",
            label="driving lessons, driving tests and driving licences associated with recreational transport vehicles (mobile homes, boats, planes, etc.)",
            keywords_by_lang={
                "en": (
                    "driving lessons, driving tests and driving licences associated with recreational transport vehicles (mobile homes, boats, planes, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="roadworthiness-tests-and-emissions-control-tests",
            label="roadworthiness tests and emissions control tests",
            keywords_by_lang={
                "en": ("roadworthiness tests and emissions control tests",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vehicle-registration-fees",
            label="vehicle registration fees",
            keywords_by_lang={
                "en": (
                    "vehicle registration fees",
                    "Vehicle registration fees",
                    "car registration charge",
                    "license plate fee",
                    "vehicle registration fee",
                    "vehicle tax disc",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="driving-lessons",
            label="Driving lessons",
            keywords_by_lang={
                "en": (
                    "Driving lessons",
                    "driver training",
                    "driving instruction",
                    "driving lessons",
                    "driving school classes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="driving-licences",
            label="Driving licences",
            keywords_by_lang={
                "en": (
                    "Driving licences",
                    "driver license",
                    "driver's license issuance",
                    "driving licence",
                    "driving permit",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="driving-tests",
            label="Driving tests",
            keywords_by_lang={
                "en": (
                    "Driving tests",
                    "driver license test",
                    "driving test",
                    "practical driving exam",
                    "theory test",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="emissions-tests",
            label="Emissions control tests",
            keywords_by_lang={
                "en": (
                    "Emissions control tests",
                    "emissions test",
                    "exhaust emission test",
                    "smog check",
                    "tailpipe test",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="roadworthiness-tests",
            label="MOT test",
            keywords_by_lang={
                "en": (
                    "MOT test",
                    "Roadworthiness tests",
                    "annual vehicle check",
                    "car inspection",
                    "roadworthy test",
                    "vehicle inspection",
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
            id="ownership-transfer-fees",
            label="Ownership transfer fees",
            keywords_by_lang={
                "en": (
                    "Ownership transfer fees",
                    "car title transfer cost",
                    "transfer of title charge",
                    "vehicle ownership transfer fee",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.2.4.4": (
        SubLabel(
            id="fees-for-participation-in-car-bicycle-and-motorcycle-sharing",
            label="fees for participation in car-, bicycle- and motorcycle-sharing schemes",
            keywords_by_lang={
                "en": (
                    "fees for participation in car-, bicycle- and motorcycle-sharing schemes",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-of-personal-transport-equipment-without-driver-e-g-car-",
            label="hire of personal transport equipment without driver (e.g., car rental)",
            keywords_by_lang={
                "en": (
                    "hire of personal transport equipment without driver (e.g., car rental)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bicycle-rental",
            label="Bicycle rental",
            keywords_by_lang={
                "en": (
                    "Bicycle rental",
                    "bicycle hire",
                    "bicycle sharing scheme",
                    "bike hire",
                    "bike rental",
                    "bike share program",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-rental",
            label="Car rental",
            keywords_by_lang={
                "en": (
                    "Car rental",
                    "automobile leasing",
                    "car hire services",
                    "car rental",
                    "rent-a-car",
                    "vehicle hire",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="car-sharing",
            label="Car-sharing scheme",
            keywords_by_lang={
                "en": (
                    "Car-sharing scheme",
                    "car club",
                    "car pooling fees",
                    "car sharing",
                    "short-term car rental",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="motorcycle-rental",
            label="Motorcycle rental",
            keywords_by_lang={
                "en": (
                    "Motorcycle rental",
                    "motorbike rental",
                    "motorcycle hire",
                    "motorcycle sharing scheme",
                    "scooter rental",
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
    "07.3.1.1": (
        SubLabel(
            id="transport-of-accompanied-private-vehicles",
            label="transport of accompanied private vehicles",
            keywords_by_lang={"en": ("transport of accompanied private vehicles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-train-high-s",
            label="transport of persons and accompanied luggage by train, high-speed train and maglev",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by train, high-speed train and maglev",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="luggage-transport-fee",
            label="Accompanied luggage fee",
            keywords_by_lang={
                "en": (
                    "Accompanied luggage fee",
                    "baggage fee",
                    "checked luggage rail",
                    "extra luggage ticket",
                    "luggage transport",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="vehicle-transport-rail",
            label="Accompanied vehicle transport",
            keywords_by_lang={
                "en": (
                    "Accompanied vehicle transport",
                    "auto train service",
                    "car transport by rail",
                    "motorail ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="high-speed-train-ticket",
            label="High-speed train ticket",
            keywords_by_lang={
                "en": (
                    "High-speed train ticket",
                    "bullet train ticket",
                    "express train ticket",
                    "high-speed rail ticket",
                    "shinkansen ticket",
                    "tgv ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="maglev-ticket",
            label="Maglev train ticket",
            keywords_by_lang={
                "en": (
                    "Maglev train ticket",
                    "maglev ticket",
                    "magnetic levitation train ticket",
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
            id="train-ticket-standard",
            label="Train ticket (standard)",
            keywords_by_lang={
                "en": (
                    "Train ticket (standard)",
                    "passenger rail travel",
                    "rail ticket",
                    "train fare",
                    "train passage",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.1.2": (
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-rapid-transi",
            label="transport of persons and accompanied luggage by rapid transit (electric railways that operate on an exclusive right of way, which cannot be accessed by pedestrians or any other types of vehicles, and which is often grade-separated in tunnels or on elevated railways), light rail, underground, rubber-tyred metro and people mover",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by rapid transit (electric railways that operate on an exclusive right of way, which cannot be accessed by pedestrians or any other types of vehicles, and which is often grade-separated in tunnels or on elevated railways), light rail, underground, rubber-tyred metro and people mover",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-tram",
            label="transport of persons and accompanied luggage by tram",
            keywords_by_lang={
                "en": ("transport of persons and accompanied luggage by tram",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="commuter-rail-ticket",
            label="Commuter rail ticket",
            keywords_by_lang={
                "en": (
                    "Commuter rail ticket",
                    "commuter train fare",
                    "light rail ticket",
                    "regional rail ticket",
                    "urban rail pass",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="multi-ride-transit-pass",
            label="Multi-ride transit pass",
            keywords_by_lang={
                "en": (
                    "Multi-ride transit pass",
                    "commuter pass",
                    "day pass transit",
                    "monthly transit pass",
                    "transit card",
                    "weekly transit pass",
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
            id="subway-metro-ticket",
            label="Subway or Metro ticket",
            keywords_by_lang={
                "en": (
                    "Subway or Metro ticket",
                    "metro card",
                    "rapid transit fare",
                    "subway ticket",
                    "tube ticket",
                    "underground pass",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tram-ticket",
            label="Tram ticket",
            keywords_by_lang={
                "en": (
                    "Tram ticket",
                    "light rail fare",
                    "streetcar ticket",
                    "tram pass",
                    "tramway token",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.2.1": (
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-bus-trolleyb",
            label="transport of persons and accompanied luggage by bus, trolleybus, and coach",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by bus, trolleybus, and coach",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-share-taxi-a",
            label="transport of persons and accompanied luggage by share taxi, a vehicle for hire that may be characterized as a cross between a taxicab and a bus. This mode of transport is often utilized in developing countries. Share taxis are typically smaller in size than buses, ranging from four-seat cars to minibuses, and are often owner-operated. They usually operate without a timetable along a fixed or semi-fixed route and may stop anywhere along that route to pick up or drop off passengers.",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by share taxi, a vehicle for hire that may be characterized as a cross between a taxicab and a bus. This mode of transport is often utilized in developing countries. Share taxis are typically smaller in size than buses, ranging from four-seat cars to minibuses, and are often owner-operated. They usually operate without a timetable along a fixed or semi-fixed route and may stop anywhere along that route to pick up or drop off passengers.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bus-ticket",
            label="Bus ticket",
            keywords_by_lang={
                "en": (
                    "Bus ticket",
                    "bus fare",
                    "bus transport",
                    "coach fare",
                    "intercity bus ticket",
                    "public bus ticket",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="luggage-surcharge",
            label="Luggage surcharge",
            keywords_by_lang={
                "en": (
                    "Luggage surcharge",
                    "accompanied luggage transport",
                    "baggage fee",
                    "extra luggage charge",
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
            id="share-taxi-fare",
            label="Share taxi fare",
            keywords_by_lang={
                "en": (
                    "Share taxi fare",
                    "jitney ride",
                    "marshrutka fare",
                    "minibus taxi fare",
                    "para-transit fare",
                    "shared taxi ride",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="trolleybus-ticket",
            label="Trolleybus ticket",
            keywords_by_lang={
                "en": ("Trolleybus ticket", "trolleybus fare", "trolleybus service")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.2.2": (
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-taxi-and-hir",
            label="transport of persons and accompanied luggage by taxi and hired vehicle, with driver",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by taxi and hired vehicle, with driver",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-through-private",
            label="transport of persons and accompanied luggage through private arrangements, such as carpooling and ride sharing",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage through private arrangements, such as carpooling and ride sharing",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="carpooling-service",
            label="Carpooling service",
            keywords_by_lang={
                "en": (
                    "Carpooling service",
                    "carpool service",
                    "commuter carpooling",
                    "ride sharing scheme",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="chauffeur-service",
            label="Chauffeur service",
            keywords_by_lang={
                "en": (
                    "Chauffeur service",
                    "car with driver",
                    "chauffeured transport",
                    "hired vehicle with driver",
                    "limousine service",
                    "private car service",
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
            id="ride-hailing-service",
            label="Ride-hailing service",
            keywords_by_lang={
                "en": (
                    "Ride-hailing service",
                    "app-based ride service",
                    "ride booking service",
                    "ride-share",
                    "rideshare service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="taxi-service",
            label="Taxi service",
            keywords_by_lang={
                "en": (
                    "Taxi service",
                    "cab",
                    "cab service",
                    "taxi",
                    "taxi ride",
                    "taxicab service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.2.3": (
        SubLabel(
            id="inter-urban-and-intercity-school-bus-charter-services-operat",
            label="inter-urban and intercity school bus charter services operating by schedule",
            keywords_by_lang={
                "en": (
                    "inter-urban and intercity school bus charter services operating by schedule",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="local-school-bus-charter-services-with-driver",
            label="local school bus charter services, with driver",
            keywords_by_lang={
                "en": ("local school bus charter services, with driver",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transportation-of-pupils-by-school-bus-between-their-homes-a",
            label="transportation of pupils by school bus between their homes and school and between schools, including in rural areas",
            keywords_by_lang={
                "en": (
                    "transportation of pupils by school bus between their homes and school and between schools, including in rural areas",
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
        SubLabel(
            id="school-bus-charter",
            label="School bus charter",
            keywords_by_lang={
                "en": (
                    "School bus charter",
                    "chartered bus service for students",
                    "private school bus charter",
                    "school bus charter service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="school-bus-transportation",
            label="School bus transportation",
            keywords_by_lang={
                "en": (
                    "School bus transportation",
                    "pupil transport service",
                    "school bus service",
                    "school shuttle service",
                    "school transportation",
                    "student busing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.2.9": (
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-animal-drawn",
            label="transport of persons and accompanied luggage by animal-drawn vehicles, with driver",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by animal-drawn vehicles, with driver",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tuk-tuks-auto-and-cycle-rickshaws-and-motorcycles-serving-as",
            label="tuk-tuks, auto and cycle rickshaws and motorcycles serving as taxis",
            keywords_by_lang={
                "en": (
                    "tuk-tuks, auto and cycle rickshaws and motorcycles serving as taxis",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="animal-drawn-taxi",
            label="Animal-drawn transport taxi",
            keywords_by_lang={
                "en": (
                    "Animal-drawn transport taxi",
                    "carriage taxi service",
                    "hansom cab ride",
                    "horse-drawn carriage ride",
                    "rickshaw carriage",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cycle-rickshaw-service",
            label="Cycle rickshaw service",
            keywords_by_lang={
                "en": (
                    "Cycle rickshaw service",
                    "bike taxi ride",
                    "cycle rickshaw taxi",
                    "pedicab service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="motorcycle-taxi",
            label="Motorcycle taxi service",
            keywords_by_lang={
                "en": (
                    "Motorcycle taxi service",
                    "boda-boda ride",
                    "moto-taxi service",
                    "motorbike taxi ride",
                    "motorcycle taxi",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other passenger transport by road",
            keywords_by_lang={"en": ("Other passenger transport by road",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tuk-tuk-service",
            label="Tuk-tuk and auto rickshaw service",
            keywords_by_lang={
                "en": (
                    "Tuk-tuk and auto rickshaw service",
                    "auto rickshaw ride",
                    "motorized rickshaw service",
                    "three-wheeler taxi",
                    "tuk-tuk taxi",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.3.3.1": (
        SubLabel(
            id="domestic-air-passenger-transport-by-drone-and-multi-copter",
            label="domestic air passenger transport by drone and multi-copter",
            keywords_by_lang={
                "en": ("domestic air passenger transport by drone and multi-copter",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="domestic-scheduled-and-chartered-air-passenger-transport-ser",
            label="domestic scheduled and chartered air passenger transport services",
            keywords_by_lang={
                "en": (
                    "domestic scheduled and chartered air passenger transport services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="domestic-transport-of-persons-and-accompanied-luggage-by-aer",
            label="domestic transport of persons and accompanied luggage by aeroplane and helicopter",
            keywords_by_lang={
                "en": (
                    "domestic transport of persons and accompanied luggage by aeroplane and helicopter",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="charter-flight-domestic",
            label="Domestic charter flight",
            keywords_by_lang={
                "en": (
                    "Domestic charter flight",
                    "air taxi",
                    "chartered passenger flight",
                    "private charter flight",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="drone-air-taxi-domestic",
            label="Domestic drone passenger transport",
            keywords_by_lang={
                "en": (
                    "Domestic drone passenger transport",
                    "air taxi drone service",
                    "eVTOL passenger transport",
                    "passenger drone flight",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="helicopter-transport-domestic",
            label="Domestic helicopter transport",
            keywords_by_lang={
                "en": (
                    "Domestic helicopter transport",
                    "domestic heli-service",
                    "heli-shuttle",
                    "helicopter passenger service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="scheduled-flight-domestic",
            label="Domestic scheduled flight",
            keywords_by_lang={
                "en": (
                    "Domestic scheduled flight",
                    "commercial domestic flight",
                    "domestic flight",
                    "passenger air service",
                    "scheduled air travel",
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
    "07.3.3.2": (
        SubLabel(
            id="international-air-passenger-transport-by-drone-and-multi-cop",
            label="international air passenger transport by drone and multi-copter",
            keywords_by_lang={
                "en": (
                    "international air passenger transport by drone and multi-copter",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transportation-of-persons-and-accompanied-luggage-by-air-on-",
            label="transportation of persons and accompanied luggage by air on an international scheduled and chartered flight",
            keywords_by_lang={
                "en": (
                    "transportation of persons and accompanied luggage by air on an international scheduled and chartered flight",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="charter-flight-service",
            label="Charter flight service",
            keywords_by_lang={
                "en": (
                    "Charter flight service",
                    "air charter",
                    "chartered flight",
                    "chartered plane ticket",
                    "private charter flight",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="drone-passenger-transport",
            label="Drone passenger transport",
            keywords_by_lang={
                "en": (
                    "Drone passenger transport",
                    "air taxi drone",
                    "eVTOL passenger service",
                    "multicopter flight",
                    "passenger drone flight",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="international-flight-ticket",
            label="International flight ticket",
            keywords_by_lang={
                "en": (
                    "International flight ticket",
                    "airfare",
                    "airline ticket",
                    "flight booking",
                    "international flight",
                    "plane ticket",
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
    "07.3.4.0": (
        SubLabel(
            id="transport-of-accompanied-private-vehicles",
            label="transport of accompanied private vehicles",
            keywords_by_lang={"en": ("transport of accompanied private vehicles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-by-ship-boat-fe",
            label="transport of persons and accompanied luggage by ship, boat, ferry, hovercraft and hydrofoil",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage by ship, boat, ferry, hovercraft and hydrofoil",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="water-taxis",
            label="water taxis",
            keywords_by_lang={"en": ("water taxis",)},
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
    "07.3.5.0": (
        SubLabel(
            id="multiple-modes-of-transport-e-g-bus-tram-subway-ferry-as-cov",
            label="multiple modes of transport (e.g., bus, tram, subway, ferry) as covered by one ticket",
            keywords_by_lang={
                "en": (
                    "multiple modes of transport (e.g., bus, tram, subway, ferry) as covered by one ticket",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-accompanied-private-vehicles-as-covered-e-g-by-",
            label="transport of accompanied private vehicles (as covered, e.g., by a ticket for a combined train and ferry trip)",
            keywords_by_lang={
                "en": (
                    "transport of accompanied private vehicles (as covered, e.g., by a ticket for a combined train and ferry trip)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transport-of-persons-and-accompanied-luggage-via-two-or-more",
            label="transport of persons and accompanied luggage via two or more modes of transport when the expenditure cannot be apportioned between them",
            keywords_by_lang={
                "en": (
                    "transport of persons and accompanied luggage via two or more modes of transport when the expenditure cannot be apportioned between them",
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
    "07.3.6.0": (
        SubLabel(
            id="funicular-elevator-cable-car-and-chairlift-transport",
            label="funicular, elevator, cable car and chairlift transport",
            keywords_by_lang={
                "en": ("funicular, elevator, cable car and chairlift transport",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-porters-left-luggage-offices-related-to-storage-",
            label="services of porters, left-luggage offices (related to storage of travellers’ luggage for a limited period of time) and luggage forwarding offices",
            keywords_by_lang={
                "en": (
                    "services of porters, left-luggage offices (related to storage of travellers’ luggage for a limited period of time) and luggage forwarding offices",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="transporter-bridges-and-transport-elevators-including-inclin",
            label="transporter bridges and transport elevators including incline elevators",
            keywords_by_lang={
                "en": (
                    "transporter bridges and transport elevators including incline elevators",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="travel-agents-commissions-if-priced-separately",
            label="travel agents’ commissions, if priced separately",
            keywords_by_lang={
                "en": ("travel agents’ commissions, if priced separately",)
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
    "07.4.1.1": (
        SubLabel(
            id="letter-courier-services",
            label="letter courier services",
            keywords_by_lang={"en": ("letter courier services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mailbox-rentals",
            label="mailbox rentals",
            keywords_by_lang={"en": ("mailbox rentals",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="new-postage-stamps-and-other-pre-franked-postal-matter-e-g-p",
            label="new postage stamps and other pre-franked postal matter (e.g., pre-franked postcards, envelopes)",
            keywords_by_lang={
                "en": (
                    "new postage stamps and other pre-franked postal matter (e.g., pre-franked postcards, envelopes)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="letter-courier-service",
            label="Letter courier services",
            keywords_by_lang={
                "en": (
                    "Letter courier services",
                    "courier delivery",
                    "express delivery",
                    "letter delivery service",
                    "mail courier",
                    "postal service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="mailbox-rental",
            label="Mailbox rental",
            keywords_by_lang={
                "en": (
                    "Mailbox rental",
                    "mail forwarding service",
                    "po box rental",
                    "post office box rental",
                    "private mailbox rental",
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
            id="postage-stamps",
            label="Postage stamps",
            keywords_by_lang={
                "en": (
                    "Postage stamps",
                    "first class stamps",
                    "franked stamps",
                    "postage labels",
                    "postage stamps",
                    "stamps",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pre-franked-stationery",
            label="Pre-franked stationery",
            keywords_by_lang={
                "en": (
                    "Pre-franked stationery",
                    "postal stationery",
                    "pre-franked postcards",
                    "pre-paid envelopes",
                    "stamped envelopes",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "07.4.1.2": (
        SubLabel(
            id="parcel-delivery-services-incoming-and-outgoing-parcel-shipme",
            label="parcel delivery services (incoming and outgoing – parcel shipment and parcel home delivery)",
            keywords_by_lang={
                "en": (
                    "parcel delivery services (incoming and outgoing – parcel shipment and parcel home delivery)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parcel-delivery-services-for-goods-purchased-online",
            label="parcel delivery services for goods purchased online",
            keywords_by_lang={
                "en": ("parcel delivery services for goods purchased online",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="small-parcel-courier-services",
            label="small parcel courier services",
            keywords_by_lang={"en": ("small parcel courier services",)},
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
    "07.4.9.1": (
        SubLabel(
            id="removal-and-storage-services-including-of-furniture",
            label="removal and storage services, including of furniture",
            keywords_by_lang={
                "en": ("removal and storage services, including of furniture",)
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
    "07.4.9.2": (
        SubLabel(
            id="delivery-services-for-goods-e-g-furniture-supermarket-shoppi",
            label="delivery services for goods (e.g., furniture, supermarket shopping), when separately priced",
            keywords_by_lang={
                "en": (
                    "delivery services for goods (e.g., furniture, supermarket shopping), when separately priced",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="delivery-services-generally-provided-immediately-after-the-p",
            label="delivery services generally provided immediately after the purchase of an item or scheduled shortly thereafter",
            keywords_by_lang={
                "en": (
                    "delivery services generally provided immediately after the purchase of an item or scheduled shortly thereafter",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="local-delivery-of-purchased-items-such-as-takeout-meals-and-",
            label="local delivery of purchased items, such as takeout meals and prescription drugs",
            keywords_by_lang={
                "en": (
                    "local delivery of purchased items, such as takeout meals and prescription drugs",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="furniture-delivery",
            label="Furniture delivery",
            keywords_by_lang={
                "en": (
                    "Furniture delivery",
                    "furniture delivery service",
                    "furniture transport",
                    "home delivery for furniture",
                    "white glove delivery",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="courier-delivery-service",
            label="General courier service",
            keywords_by_lang={
                "en": (
                    "General courier service",
                    "delivery service",
                    "item delivery",
                    "local courier service",
                    "package delivery",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="grocery-delivery",
            label="Grocery delivery",
            keywords_by_lang={
                "en": (
                    "Grocery delivery",
                    "food delivery service",
                    "online grocery delivery",
                    "supermarket delivery",
                    "supermarket order delivery",
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
            id="prescription-delivery",
            label="Prescription delivery",
            keywords_by_lang={
                "en": (
                    "Prescription delivery",
                    "drug delivery",
                    "medicine delivery",
                    "pharmacy delivery service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="takeout-delivery",
            label="Takeout delivery",
            keywords_by_lang={
                "en": (
                    "Takeout delivery",
                    "courier service for meals",
                    "food delivery",
                    "meal delivery",
                    "restaurant food delivery",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
}
