"""Auto-generated sub_labels for COICOP class 04.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "04.1.1.0": (
        SubLabel(
            id="payments-by-households-occupying-a-room-in-a-hotel-or-boardi",
            label="payments by households occupying a room in a hotel or boarding house as their main residence",
            keywords_by_lang={
                "en": (
                    "payments by households occupying a room in a hotel or boarding house as their main residence",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rentals-actually-paid-by-tenants-or-subtenants-occupying-fur",
            label="rentals actually paid by tenants or subtenants occupying furnished or unfurnished premises as their main residence",
            keywords_by_lang={
                "en": (
                    "rentals actually paid by tenants or subtenants occupying furnished or unfurnished premises as their main residence",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="apartment-rent",
            label="apartment rent",
            keywords_by_lang={"auto": ("apartment rent",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="boarding-house-rent",
            label="Boarding house rental payment",
            keywords_by_lang={
                "en": (
                    "Boarding house rental payment",
                    "boarding house rent",
                    "lodging rent",
                    "room rent",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="residential-rent-furnished",
            label="Furnished rental payment",
            keywords_by_lang={
                "en": (
                    "Furnished rental payment",
                    "furnished apartment rent",
                    "furnished rent",
                    "rental payment with furniture",
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
            id="sublet-payment",
            label="Sublet rental payment",
            keywords_by_lang={
                "en": ("Sublet rental payment", "sublease payment", "subtenancy rent")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="residential-rent-unfurnished",
            label="Unfurnished rental payment",
            keywords_by_lang={
                "en": (
                    "Unfurnished rental payment",
                    "apartment rent",
                    "house rent",
                    "monthly rent",
                    "tenancy payment",
                    "unfurnished rent",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.1.2.1": (
        SubLabel(
            id="rentals-actually-paid-for-secondary-residences",
            label="rentals actually paid for secondary residences",
            keywords_by_lang={
                "en": ("rentals actually paid for secondary residences",)
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
            id="secondary-residence-rent",
            label="Secondary residence rent",
            keywords_by_lang={
                "en": (
                    "Secondary residence rent",
                    "holiday home rent",
                    "holiday rental payment",
                    "seasonal residence rent",
                    "second home rent",
                    "vacation home rental",
                    "weekend house rent",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.1.2.2": (
        SubLabel(
            id="garage-rentals-in-connection-with-the-dwelling",
            label="garage rentals in connection with the dwelling",
            keywords_by_lang={
                "en": ("garage rentals in connection with the dwelling",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rentals-of-self-storage-units",
            label="rentals of self-storage units",
            keywords_by_lang={"en": ("rentals of self-storage units",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="garage-rental",
            label="Garage rental",
            keywords_by_lang={
                "en": (
                    "Garage rental",
                    "garage rental",
                    "parking garage lease",
                    "residential garage rent",
                    "storage garage rental",
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
            id="self-storage-unit",
            label="Self-storage unit",
            keywords_by_lang={
                "en": (
                    "Self-storage unit",
                    "mini storage",
                    "personal storage unit",
                    "self-storage unit",
                    "storage locker",
                    "storage unit rental",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.2.1.0": (
        SubLabel(
            id="imputed-rentals-of-owners-occupying-their-main-residence",
            label="imputed rentals of owners occupying their main residence",
            keywords_by_lang={
                "en": ("imputed rentals of owners occupying their main residence",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="imputed-rental-main-residence",
            label="Imputed rental of main residence",
            keywords_by_lang={
                "en": (
                    "Imputed rental of main residence",
                    "housing consumption for owners",
                    "implicit rent for housing",
                    "imputed rent",
                    "owner rental valuation",
                    "owner-occupier rent",
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
    "04.2.2.0": (
        SubLabel(
            id="imputed-garage-rentals-in-connection-with-the-dwelling",
            label="imputed garage rentals in connection with the dwelling",
            keywords_by_lang={
                "en": ("imputed garage rentals in connection with the dwelling",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="imputed-rentals-for-secondary-residences",
            label="imputed rentals for secondary residences",
            keywords_by_lang={"en": ("imputed rentals for secondary residences",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="imputed-rentals-of-storage-units",
            label="imputed rentals of storage units",
            keywords_by_lang={"en": ("imputed rentals of storage units",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="garage-rental-imputed",
            label="Imputed garage rental",
            keywords_by_lang={
                "en": (
                    "Imputed garage rental",
                    "garage rental value",
                    "imputed parking rental value",
                    "imputed rent for parking space",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="secondary-residence-rental-imputed",
            label="Imputed rental for secondary residences",
            keywords_by_lang={
                "en": (
                    "Imputed rental for secondary residences",
                    "holiday home rental value",
                    "imputed rent secondary dwelling",
                    "imputed rental income secondary residence",
                    "secondary home imputed rent",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="storage-unit-rental-imputed",
            label="Imputed storage unit rental",
            keywords_by_lang={
                "en": (
                    "Imputed storage unit rental",
                    "imputed rent for self-storage",
                    "imputed storage rental value",
                    "rental value of storage unit",
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
    "04.3.1.1": (
        SubLabel(
            id="door-fittings-power-sockets-and-wiring-flex",
            label="door fittings, power sockets and wiring flex",
            keywords_by_lang={"en": ("door fittings, power sockets and wiring flex",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fitted-carpets-and-linoleum",
            label="fitted carpets and linoleum",
            keywords_by_lang={"en": ("fitted carpets and linoleum",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="products-and-materials-such-as-paints-and-varnishes-renderin",
            label="products and materials such as paints and varnishes, renderings, wallpapers, fabric wall coverings, windowpanes, plaster, cement, putty, wallpaper pastes and so on, purchased for minor maintenance and repair of dwellings",
            keywords_by_lang={
                "en": (
                    "products and materials such as paints and varnishes, renderings, wallpapers, fabric wall coverings, windowpanes, plaster, cement, putty, wallpaper pastes and so on, purchased for minor maintenance and repair of dwellings",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="small-plumbing-items-pipes-taps-joints-etc-surfacing-materia",
            label="small plumbing items (pipes, taps, joints, etc.), surfacing materials (floorboards, ceramic tiles, etc.) and brushes and scrapers for paint, varnish and wallpaper",
            keywords_by_lang={
                "en": (
                    "small plumbing items (pipes, taps, joints, etc.), surfacing materials (floorboards, ceramic tiles, etc.) and brushes and scrapers for paint, varnish and wallpaper",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="plumbing-fittings",
            label="plumbing fittings",
            keywords_by_lang={"auto": ("plumbing fittings",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="door-hardware",
            label="Door fittings and hardware",
            keywords_by_lang={
                "en": (
                    "Door fittings and hardware",
                    "door fittings",
                    "door handle",
                    "door hinge",
                    "door latch",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electrical-fixture",
            label="Electrical fixtures and wiring",
            keywords_by_lang={
                "en": (
                    "Electrical fixtures and wiring",
                    "electrical cable",
                    "electrical outlet",
                    "power socket",
                    "wall plug",
                    "wiring flex",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="flooring-material",
            label="Flooring and surfacing materials",
            keywords_by_lang={
                "en": (
                    "Flooring and surfacing materials",
                    "ceramic tiles",
                    "fitted carpet",
                    "floor tiles",
                    "floorboards",
                    "laminate flooring",
                    "linoleum flooring",
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
            id="paint-varnish",
            label="Paint and varnish",
            keywords_by_lang={
                "en": (
                    "Paint and varnish",
                    "emulsion paint",
                    "interior paint",
                    "lacquer",
                    "paint",
                    "primer",
                    "varnish",
                    "wood stain",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="painting-tool",
            label="Painting and decorating tools",
            keywords_by_lang={
                "en": (
                    "Painting and decorating tools",
                    "decorating tool",
                    "paint brush",
                    "paint roller",
                    "paint scraper",
                    "wallpaper brush",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="plumbing-fitting",
            label="Plumbing fixtures and fittings",
            keywords_by_lang={
                "en": (
                    "Plumbing fixtures and fittings",
                    "faucets",
                    "pipe connectors",
                    "pipes",
                    "plumbing joints",
                    "taps",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="building-surface-material",
            label="Surface and repair materials",
            keywords_by_lang={
                "en": (
                    "Surface and repair materials",
                    "cement",
                    "filler",
                    "plaster",
                    "putty",
                    "rendering material",
                    "wall compound",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wallpaper-adhesive",
            label="Wallpaper and accessories",
            keywords_by_lang={
                "en": (
                    "Wallpaper and accessories",
                    "fabric wall covering",
                    "wall adhesive",
                    "wall covering",
                    "wallpaper",
                    "wallpaper paste",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="window-glass",
            label="Windowpanes and glazing supplies",
            keywords_by_lang={
                "en": (
                    "Windowpanes and glazing supplies",
                    "glass pane",
                    "glazing material",
                    "windowpane",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.3.1.2": (
        SubLabel(
            id="door-phones-for-dwellings",
            label="door phones for dwellings",
            keywords_by_lang={"en": ("door phones for dwellings",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fire-extinguishers",
            label="fire extinguishers",
            keywords_by_lang={"en": ("fire extinguishers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="small-surveillance-and-security-equipment-for-individual-dwe",
            label="small surveillance and security equipment for individual dwellings (smoke detectors, security alarms, and security and surveillance cameras)",
            keywords_by_lang={
                "en": (
                    "small surveillance and security equipment for individual dwellings (smoke detectors, security alarms, and security and surveillance cameras)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="door-lock",
            label="door lock",
            keywords_by_lang={"auto": ("door lock",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="security-camera",
            label="security camera",
            keywords_by_lang={"auto": ("security camera",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="surveillance-camera",
            label="CCTV camera",
            keywords_by_lang={
                "en": (
                    "CCTV camera",
                    "IP camera",
                    "Surveillance camera",
                    "home monitor camera",
                    "security camera",
                    "wifi camera",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="door-phone",
            label="Door phone",
            keywords_by_lang={
                "en": (
                    "Door phone",
                    "door intercom",
                    "doorbell camera",
                    "intercom system",
                    "video doorbell",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fire-extinguisher",
            label="Fire extinguisher",
            keywords_by_lang={
                "en": (
                    "Fire extinguisher",
                    "dry chemical extinguisher",
                    "handheld fire extinguisher",
                    "home fire extinguisher",
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
            id="security-alarm-system",
            label="Security alarm system",
            keywords_by_lang={
                "en": (
                    "Security alarm system",
                    "alarm system",
                    "burglar alarm",
                    "home security alarm",
                    "intrusion alarm",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="smoke-detector",
            label="Smoke detector",
            keywords_by_lang={
                "en": (
                    "Smoke detector",
                    "fire alarm detector",
                    "fire detector",
                    "smoke alarm",
                    "smoke sensor",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.3.2.0": (
        SubLabel(
            id="locksmith-services",
            label="locksmith services",
            keywords_by_lang={"en": ("locksmith services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="security-services",
            label="security services",
            keywords_by_lang={"en": ("security services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-plumbers-electricians-carpenters-glaziers-painte",
            label="services of plumbers, electricians, carpenters, glaziers, painters, decorators, floor polishers, etc., engaged to carry out minor maintenance and repair of the dwelling",
            keywords_by_lang={
                "en": (
                    "services of plumbers, electricians, carpenters, glaziers, painters, decorators, floor polishers, etc., engaged to carry out minor maintenance and repair of the dwelling",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-related-to-laying-of-fitted-carpets-and-linoleum",
            label="services related to laying of fitted carpets and linoleum;",
            keywords_by_lang={
                "en": ("services related to laying of fitted carpets and linoleum;",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="carpentry-service",
            label="Carpentry services",
            keywords_by_lang={
                "en": (
                    "Carpentry services",
                    "carpenter",
                    "furniture repair",
                    "joinery services",
                    "woodwork repair",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="security-service-dwelling",
            label="Dwelling security services",
            keywords_by_lang={
                "en": (
                    "Dwelling security services",
                    "alarm monitoring service",
                    "home security patrol",
                    "home security service",
                    "security system maintenance",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="electrical-service",
            label="Electrical services",
            keywords_by_lang={
                "en": (
                    "Electrical services",
                    "electrical installation services",
                    "electrical maintenance",
                    "electrical repair",
                    "electrician",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="flooring-installation-service",
            label="Flooring installation services",
            keywords_by_lang={
                "en": (
                    "Flooring installation services",
                    "carpet laying service",
                    "floor polishing",
                    "flooring contractor",
                    "linoleum laying",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="glazing-service",
            label="Glazing services",
            keywords_by_lang={
                "en": (
                    "Glazing services",
                    "glass replacement",
                    "glazier",
                    "window pane repair",
                    "window repair",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="locksmith-service",
            label="Locksmith services",
            keywords_by_lang={
                "en": (
                    "Locksmith services",
                    "emergency lock opening",
                    "key cutting service",
                    "lock repair",
                    "locksmith",
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
            id="painting-decorating-service",
            label="Painting and decorating services",
            keywords_by_lang={
                "en": (
                    "Painting and decorating services",
                    "decorator",
                    "interior painting service",
                    "painter",
                    "wallpapering services",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="plumbing-service",
            label="Plumbing services",
            keywords_by_lang={
                "en": (
                    "Plumbing services",
                    "emergency plumber",
                    "leaky pipe repair",
                    "plumber",
                    "plumbing repair",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.1.1": (
        SubLabel(
            id="all-charges-usually-included-in-the-bills-paid-by-households",
            label="all charges usually included in the bills paid by households, including meter installation charges and rentals, and volumetric or fixed charges for consumption of water delivered through mains, except for steam and hot water",
            keywords_by_lang={
                "en": (
                    "all charges usually included in the bills paid by households, including meter installation charges and rentals, and volumetric or fixed charges for consumption of water delivered through mains, except for steam and hot water",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="associated-expenditures-such-as-meter-rentals-cost-of-meter-",
            label="associated expenditures, such as meter rentals, cost of meter readings, standing charges and so on",
            keywords_by_lang={
                "en": (
                    "associated expenditures, such as meter rentals, cost of meter readings, standing charges and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mains-water-bill",
            label="Mains water supply",
            keywords_by_lang={
                "en": (
                    "Mains water supply",
                    "household water consumption",
                    "mains water service",
                    "tap water charges",
                    "water bill",
                    "water utility bill",
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
            id="water-meter-service-charge",
            label="Water meter service and rental charges",
            keywords_by_lang={
                "en": (
                    "Water meter service and rental charges",
                    "meter installation charge",
                    "meter rental",
                    "meter standing charge",
                    "water meter reading fee",
                    "water service fee",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.1.2": (
        SubLabel(
            id="payment-for-services-provided-at-a-public-standpost-or-fount",
            label="payment for services provided at a public standpost or fountain and by water vendors (e.g., via tanker truck or cart)",
            keywords_by_lang={
                "en": (
                    "payment for services provided at a public standpost or fountain and by water vendors (e.g., via tanker truck or cart)",
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
            id="water-standpost-fountain-supply",
            label="Water from public standpost or fountain",
            keywords_by_lang={
                "en": (
                    "Water from public standpost or fountain",
                    "communal tap water",
                    "fountain water service",
                    "public standpipe water",
                    "public water point supply",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="water-vendor-service",
            label="Water vendor services (tanker/cart)",
            keywords_by_lang={
                "en": (
                    "Water vendor services (tanker/cart)",
                    "bulk water delivery",
                    "delivered water service",
                    "water cart service",
                    "water delivery by truck",
                    "water tanker supply",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.2.0": (
        SubLabel(
            id="recycling-fees-paid-by-households",
            label="recycling fees paid by households",
            keywords_by_lang={"en": ("recycling fees paid by households",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="refuse-collection-and-disposal",
            label="refuse collection and disposal",
            keywords_by_lang={"en": ("refuse collection and disposal",)},
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
            id="recycling-fee",
            label="Recycling fee",
            keywords_by_lang={
                "en": (
                    "Recycling fee",
                    "household recycling levy",
                    "recycling charge",
                    "recycling tax",
                    "waste recycling fee",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="refuse-collection-service",
            label="Refuse collection service",
            keywords_by_lang={
                "en": (
                    "Refuse collection service",
                    "bin collection",
                    "garbage pickup",
                    "refuse disposal",
                    "rubbish collection",
                    "trash collection",
                    "waste collection",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.3.1": (
        SubLabel(
            id="payments-made-to-the-sanitation-or-water-provider-or-the-mun",
            label="payments made to the sanitation or water provider or the municipality for services related to the collection, transport and disposal of sewage by means of sewer systems and its disposal",
            keywords_by_lang={
                "en": (
                    "payments made to the sanitation or water provider or the municipality for services related to the collection, transport and disposal of sewage by means of sewer systems and its disposal",
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
            id="sewage-collection-fee",
            label="Sewage collection fee",
            keywords_by_lang={
                "en": (
                    "Sewage collection fee",
                    "sanitary sewer fee",
                    "sewage disposal charge",
                    "sewer line fee",
                    "sewerage service charge",
                    "wastewater collection service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.3.2": (
        SubLabel(
            id="communal-toilets-and-pay-toilets",
            label="communal toilets and pay toilets",
            keywords_by_lang={"en": ("communal toilets and pay toilets",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-to-empty-and-evacuate-liquid-waste-excreta-and-wast",
            label="services to empty and evacuate liquid waste (excreta and wastewater) by means of on-site sanitation systems (pit latrines, septic tanks and/or soak pits) and clean them",
            keywords_by_lang={
                "en": (
                    "services to empty and evacuate liquid waste (excreta and wastewater) by means of on-site sanitation systems (pit latrines, septic tanks and/or soak pits) and clean them",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="latrine-emptying",
            label="Latrine and soak pit cleaning",
            keywords_by_lang={
                "en": (
                    "Latrine and soak pit cleaning",
                    "latrine pumping",
                    "latrine waste removal",
                    "pit cleaning service",
                    "pit latrine emptying",
                    "soak pit cleaning",
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
            id="public-toilet-access",
            label="Public and pay toilets",
            keywords_by_lang={
                "en": (
                    "Public and pay toilets",
                    "communal toilet service",
                    "pay toilet access",
                    "pay-per-use toilet",
                    "public restroom access",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="septic-tank-emptying",
            label="Septic tank emptying and cleaning",
            keywords_by_lang={
                "en": (
                    "Septic tank emptying and cleaning",
                    "septic service",
                    "septic tank cleaning",
                    "septic tank pumping",
                    "septic tank suction service",
                    "wastewater evacuation",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.4.1": (
        SubLabel(
            id="co-proprietor-charges-for-caretaking-gardening-stairwell-cle",
            label="co-proprietor charges for caretaking, gardening, stairwell cleaning, heating and lighting, maintenance of lifts and refuse disposal chutes, pool cleaning, etc., in multi-occupied buildings",
            keywords_by_lang={
                "en": (
                    "co-proprietor charges for caretaking, gardening, stairwell cleaning, heating and lighting, maintenance of lifts and refuse disposal chutes, pool cleaning, etc., in multi-occupied buildings",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="caretaking-service",
            label="Caretaking services",
            keywords_by_lang={
                "en": (
                    "Caretaking services",
                    "building concierge service",
                    "building management services",
                    "caretaking",
                    "residential building staff",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="communal-heating-lighting",
            label="Communal heating and lighting charges",
            keywords_by_lang={
                "en": (
                    "Communal heating and lighting charges",
                    "building common area electricity",
                    "communal building heating costs",
                    "shared utility charges",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gardening-service",
            label="Gardening services for communal areas",
            keywords_by_lang={
                "en": (
                    "Gardening services for communal areas",
                    "building landscaping services",
                    "common area groundskeeping",
                    "communal gardening",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="general-building-maintenance",
            label="General multi-occupancy building maintenance",
            keywords_by_lang={
                "en": (
                    "General multi-occupancy building maintenance",
                    "building repair fund charges",
                    "building upkeep contributions",
                    "common area maintenance fees",
                    "strata fees",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lift-maintenance",
            label="Lift and elevator maintenance",
            keywords_by_lang={
                "en": (
                    "Lift and elevator maintenance",
                    "elevator inspection service",
                    "elevator maintenance service",
                    "lift repair charges",
                    "lift servicing",
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
            id="refuse-disposal-service",
            label="Refuse disposal and chute maintenance",
            keywords_by_lang={
                "en": (
                    "Refuse disposal and chute maintenance",
                    "bin area maintenance",
                    "communal waste management",
                    "trash chute service",
                    "waste disposal charges",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="stairwell-cleaning",
            label="Stairwell and hallway cleaning",
            keywords_by_lang={
                "en": (
                    "Stairwell and hallway cleaning",
                    "building lobby cleaning",
                    "common area cleaning",
                    "communal corridor cleaning",
                    "stairwell cleaning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pool-maintenance",
            label="Swimming pool maintenance service",
            keywords_by_lang={
                "en": (
                    "Swimming pool maintenance service",
                    "communal pool cleaning",
                    "pool maintenance charges",
                    "swimming pool servicing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.4.4.9": (
        SubLabel(
            id="landscaping-and-cleaning-of-the-dwelling-s-surrounding-groun",
            label="landscaping and cleaning of the dwelling’s surrounding grounds",
            keywords_by_lang={
                "en": (
                    "landscaping and cleaning of the dwelling’s surrounding grounds",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="measurement-of-background-radiation-and-the-content-of-harmf",
            label="measurement of background radiation and the content of harmful substances inside the dwelling",
            keywords_by_lang={
                "en": (
                    "measurement of background radiation and the content of harmful substances inside the dwelling",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="road-and-sidewalk-cleaning-and-chimney-sweeping",
            label="road and sidewalk cleaning and chimney sweeping",
            keywords_by_lang={
                "en": ("road and sidewalk cleaning and chimney sweeping",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="snow-removal",
            label="snow removal",
            keywords_by_lang={"en": ("snow removal",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="chimney-sweeping-service",
            label="Chimney sweeping",
            keywords_by_lang={
                "en": (
                    "Chimney sweeping",
                    "chimney maintenance",
                    "chimney sweep",
                    "flue cleaning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="environmental-safety-testing",
            label="Environmental and safety testing",
            keywords_by_lang={
                "en": (
                    "Environmental and safety testing",
                    "air quality testing",
                    "harmful substance testing",
                    "home hazard inspection",
                    "radiation testing",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="landscaping-service",
            label="Landscaping and grounds maintenance",
            keywords_by_lang={
                "en": (
                    "Landscaping and grounds maintenance",
                    "garden maintenance",
                    "gardening service",
                    "groundskeeping",
                    "lawn care service",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="_other",
            label="Other dwelling services",
            keywords_by_lang={"en": ("Other dwelling services",)},
            allowed_bases=frozenset({"count", "item", "mass", "volume"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cleaning-service-outdoor",
            label="Outdoor cleaning services",
            keywords_by_lang={
                "en": (
                    "Outdoor cleaning services",
                    "driveway cleaning",
                    "exterior cleaning",
                    "road cleaning service",
                    "sidewalk cleaning",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="snow-removal-service",
            label="Snow removal",
            keywords_by_lang={
                "en": (
                    "Snow removal",
                    "ice removal",
                    "snow clearing",
                    "snow ploughing",
                    "snow shovelling",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.5.1.0": (
        SubLabel(
            id="associated-expenditure-such-as-meter-rentals-cost-of-meter-r",
            label="associated expenditure, such as meter rentals, cost of meter readings, standing charges, etc.",
            keywords_by_lang={
                "en": (
                    "associated expenditure, such as meter rentals, cost of meter readings, standing charges, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="charges-for-self-produced-energy-i-e-in-some-countries-house",
            label="charges for self-produced energy (i.e., in some countries, households that self-produce more electricity than they consume are charged storage costs if they transmit that surplus electricity back into the electricity supply grid)",
            keywords_by_lang={
                "en": (
                    "charges for self-produced energy (i.e., in some countries, households that self-produce more electricity than they consume are charged storage costs if they transmit that surplus electricity back into the electricity supply grid)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electricity-from-all-sources-coal-solar-hydro-etc",
            label="electricity from all sources (coal, solar, hydro, etc.)",
            keywords_by_lang={
                "en": ("electricity from all sources (coal, solar, hydro, etc.)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electricity-supply",
            label="Electricity supply",
            keywords_by_lang={
                "en": (
                    "Electricity supply",
                    "electric power",
                    "electricity",
                    "grid electricity",
                    "household electricity",
                    "power supply",
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
            id="electricity-standing-charges",
            label="Standing charges and meter fees",
            keywords_by_lang={
                "en": (
                    "Standing charges and meter fees",
                    "fixed electricity fee",
                    "meter reading fee",
                    "meter rental",
                    "service charge",
                    "standing charge",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "04.5.2.1": (
        SubLabel(
            id="associated-expenditure-such-as-meters-rentals-cost-of-meter-",
            label="associated expenditure, such as meters rentals, cost of meter readings, standing charges, etc.",
            keywords_by_lang={
                "en": (
                    "associated expenditure, such as meters rentals, cost of meter readings, standing charges, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="natural-gas-and-town-gas-delivered-through-gas-networks",
            label="natural gas and town gas delivered through gas networks",
            keywords_by_lang={
                "en": ("natural gas and town gas delivered through gas networks",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gas-meter-service",
            label="Gas meter service charges",
            keywords_by_lang={
                "en": (
                    "Gas meter service charges",
                    "gas network access fee",
                    "gas standing charge",
                    "meter reading fee",
                    "meter rental",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="natural-gas-supply",
            label="Natural gas supply",
            keywords_by_lang={
                "en": (
                    "Natural gas supply",
                    "domestic gas supply",
                    "mains gas",
                    "natural gas",
                    "piped gas",
                    "town gas",
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
    "04.5.2.2": (
        SubLabel(
            id="associated-expenditure-such-as-rental-or-purchase-of-storage",
            label="associated expenditure, such as rental or purchase of storage containers, standing charges, etc.",
            keywords_by_lang={
                "en": (
                    "associated expenditure, such as rental or purchase of storage containers, standing charges, etc.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="liquefied-hydrocarbons-butane-propane-etc-delivered-in-stora",
            label="liquefied hydrocarbons (butane, propane, etc.) delivered in storage containers",
            keywords_by_lang={
                "en": (
                    "liquefied hydrocarbons (butane, propane, etc.) delivered in storage containers",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="butane-gas",
            label="Butane gas",
            keywords_by_lang={
                "en": (
                    "Butane gas",
                    "LPG butane",
                    "butane",
                    "butane canister",
                    "butane cylinder",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gas-cylinder-purchase",
            label="Gas cylinder purchase",
            keywords_by_lang={
                "en": (
                    "Gas cylinder purchase",
                    "empty gas cylinder",
                    "gas bottle purchase",
                    "refillable gas cylinder",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="gas-cylinder-rental",
            label="Gas cylinder rental",
            keywords_by_lang={
                "en": (
                    "Gas cylinder rental",
                    "cylinder lease",
                    "gas bottle rental",
                    "gas cylinder deposit",
                    "gas tank rental",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="lpg-fuel",
            label="LPG",
            keywords_by_lang={
                "en": (
                    "LPG",
                    "LPG fuel",
                    "cooking gas",
                    "liquefied petroleum gas",
                    "liquid propane gas",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="propane-gas",
            label="LPG propane",
            keywords_by_lang={
                "en": (
                    "LPG propane",
                    "Propane gas",
                    "propane",
                    "propane cylinder",
                    "propane tank",
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
    "04.5.3.0": (
        SubLabel(
            id="alcohol-for-fireplaces",
            label="alcohol for fireplaces",
            keywords_by_lang={"en": ("alcohol for fireplaces",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="biofuels-for-domestic-use",
            label="biofuels for domestic use",
            keywords_by_lang={"en": ("biofuels for domestic use",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="domestic-heating-lighting-and-cooking-fuel-oils",
            label="domestic heating, lighting and cooking fuel oils",
            keywords_by_lang={
                "en": ("domestic heating, lighting and cooking fuel oils",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="biofuel-domestic",
            label="Biofuel for home use",
            keywords_by_lang={
                "en": (
                    "Biofuel for home use",
                    "bio-ethanol fuel",
                    "biofuel",
                    "domestic biofuel",
                    "renewable home fuel",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fireplace-alcohol",
            label="Fireplace alcohol fuel",
            keywords_by_lang={
                "en": (
                    "Fireplace alcohol fuel",
                    "bio-ethanol for fireplaces",
                    "ethanol fuel",
                    "fireplace alcohol",
                    "gel fuel for fireplaces",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="heating-oil",
            label="Heating oil",
            keywords_by_lang={
                "en": (
                    "Heating oil",
                    "domestic heating oil",
                    "fuel oil for furnaces",
                    "heating oil",
                    "home heating oil",
                    "kerosene",
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
    "04.5.4.1": (
        SubLabel(
            id="coal",
            label="coal",
            keywords_by_lang={
                "en": (
                    "coal",
                    "Coal",
                    "anthracite",
                    "bituminous coal",
                    "lump coal",
                    "mineral coal",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="coal-briquettes",
            label="coal briquettes",
            keywords_by_lang={
                "en": (
                    "coal briquettes",
                    "Coal briquettes",
                    "coal bricks",
                    "compressed coal",
                    "fuel briquettes",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="peat",
            label="peat",
            keywords_by_lang={
                "en": ("peat", "Peat", "dried peat", "peat fuel", "turf")
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="peat-briquettes",
            label="peat briquettes",
            keywords_by_lang={
                "en": (
                    "peat briquettes",
                    "Peat briquettes",
                    "compressed peat turf",
                    "peat bricks",
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
    "04.5.4.2": (
        SubLabel(
            id="fuelwood-in-the-form-of-billets-faggots-logs-or-twigs-or-in-",
            label="fuelwood, in the form of billets, faggots, logs or twigs, or in similar forms",
            keywords_by_lang={
                "en": (
                    "fuelwood, in the form of billets, faggots, logs or twigs, or in similar forms",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="non-agglomerated-sawdust-and-wood-waste-and-scrap",
            label="non-agglomerated sawdust and wood waste and scrap",
            keywords_by_lang={
                "en": ("non-agglomerated sawdust and wood waste and scrap",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sawdust-and-wood-waste-and-scrap-agglomerated-in-briquettes-",
            label="sawdust and wood waste and scrap agglomerated in briquettes and pellets or in similar forms",
            keywords_by_lang={
                "en": (
                    "sawdust and wood waste and scrap agglomerated in briquettes and pellets or in similar forms",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wood-in-the-form-of-chips-or-particles",
            label="wood in the form of chips or particles",
            keywords_by_lang={"en": ("wood in the form of chips or particles",)},
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
    "04.5.4.3": (
        SubLabel(
            id="charcoal-briquettes",
            label="charcoal briquettes",
            keywords_by_lang={"en": ("charcoal briquettes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="charcoal-briquettes-for-barbecuing",
            label="charcoal briquettes for barbecuing",
            keywords_by_lang={"en": ("charcoal briquettes for barbecuing",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shell-and-nut-charcoal",
            label="shell and nut charcoal",
            keywords_by_lang={"en": ("shell and nut charcoal",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wood-and-bamboo-charcoal",
            label="wood and bamboo charcoal",
            keywords_by_lang={"en": ("wood and bamboo charcoal",)},
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
    "04.5.4.9": (
        SubLabel(
            id="coke",
            label="coke",
            keywords_by_lang={
                "en": (
                    "coke",
                    "Coke (fuel)",
                    "coal coke",
                    "industrial coke",
                    "metallurgical coke",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-biomass-n-e-c-such-as-waste-from-agricultural-producti",
            label="other biomass n.e.c., such as waste from agricultural production (e.g., wheat and nutshells) and dry animal dung",
            keywords_by_lang={
                "en": (
                    "other biomass n.e.c., such as waste from agricultural production (e.g., wheat and nutshells) and dry animal dung",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-types-of-briquettes",
            label="other types of briquettes",
            keywords_by_lang={"en": ("other types of briquettes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="animal-dung-fuel",
            label="Animal dung fuel",
            keywords_by_lang={
                "en": (
                    "Animal dung fuel",
                    "dry animal dung",
                    "dung cakes",
                    "manure fuel bricks",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="biomass-fuel",
            label="Biomass fuel",
            keywords_by_lang={
                "en": (
                    "Biomass fuel",
                    "agricultural waste fuel",
                    "biofuel pellets",
                    "biomass fuel",
                    "crop residue fuel",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fuel-briquettes",
            label="Fuel briquettes",
            keywords_by_lang={
                "en": (
                    "Fuel briquettes",
                    "briquettes",
                    "compressed fuel blocks",
                    "firewood briquettes",
                    "fuel bricks",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nutshell-fuel",
            label="Nutshell fuel",
            keywords_by_lang={
                "en": (
                    "Nutshell fuel",
                    "nut husk fuel",
                    "nutshell biomass",
                    "solid nut fuel",
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
    "04.5.5.0": (
        SubLabel(
            id="associated-expenditure-such-as-meter-rentals-of-cost-of-mete",
            label="associated expenditure, such as meter rentals of, cost of meter readings, standing charges and so on",
            keywords_by_lang={
                "en": (
                    "associated expenditure, such as meter rentals of, cost of meter readings, standing charges and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hot-water-and-steam-purchased-from-district-heating-plants",
            label="hot water and steam purchased from district heating plants",
            keywords_by_lang={
                "en": ("hot water and steam purchased from district heating plants",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ice-used-for-cooling-and-refrigeration-purposes",
            label="ice used for cooling and refrigeration purposes",
            keywords_by_lang={
                "en": ("ice used for cooling and refrigeration purposes",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="district-cooling-service",
            label="District cooling service",
            keywords_by_lang={
                "en": (
                    "District cooling service",
                    "central cooling service",
                    "chilled water supply",
                    "district cooling",
                    "district cooling charges",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="district-heating-service",
            label="District heating service",
            keywords_by_lang={
                "en": (
                    "District heating service",
                    "central heating service",
                    "district heating",
                    "district heating charges",
                    "hot water supply",
                    "steam heating",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="energy-metering-services",
            label="Energy metering services",
            keywords_by_lang={
                "en": (
                    "Energy metering services",
                    "heating meter supply fee",
                    "meter reading fee",
                    "meter rental",
                    "standing charges for heating",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="industrial-ice",
            label="Industrial ice",
            keywords_by_lang={
                "en": (
                    "Industrial ice",
                    "bulk ice for cooling",
                    "commercial cooling ice",
                    "industrial ice blocks",
                    "refrigeration ice",
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
}
