"""Auto-generated sub_labels for COICOP class 09.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "09.1.1.1": (
        SubLabel(
            id="materials-purchased-by-households-with-the-intention-of-unde",
            label="materials purchased by households with the intention of undertaking maintenance and repairs themselves",
            keywords_by_lang={
                "en": (
                    "materials purchased by households with the intention of undertaking maintenance and repairs themselves",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="still-cameras-movie-cameras-and-sound-recording-cameras-film",
            label="still cameras, movie cameras and sound-recording cameras, film and slide projectors, enlargers and film processing equipment",
            keywords_by_lang={
                "en": (
                    "still cameras, movie cameras and sound-recording cameras, film and slide projectors, enlargers and film processing equipment",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-cameras-including-camcorders-and-action-cameras",
            label="video cameras, including camcorders and action cameras",
            keywords_by_lang={
                "en": ("video cameras, including camcorders and action cameras",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="still-camera",
            label="still camera",
            keywords_by_lang={"auto": ("still camera",)},
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
    "09.1.1.2": (
        SubLabel(
            id="camera-specific-batteries-and-chargers",
            label="camera-specific batteries and chargers",
            keywords_by_lang={"en": ("camera-specific batteries and chargers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="materials-purchased-by-households-with-the-intention-of-unde",
            label="materials purchased by households with the intention of undertaking maintenance and repairs themselves",
            keywords_by_lang={
                "en": (
                    "materials purchased by households with the intention of undertaking maintenance and repairs themselves",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parts-and-accessories-for-photographic-and-cinematographic-e",
            label="parts and accessories for photographic and cinematographic equipment and optical instruments such as screens, viewers, lenses (including zoom lenses), flash attachments, filters, exposure meters and so on",
            keywords_by_lang={
                "en": (
                    "parts and accessories for photographic and cinematographic equipment and optical instruments such as screens, viewers, lenses (including zoom lenses), flash attachments, filters, exposure meters and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="photographic-developer-and-photographic-paper",
            label="photographic developer and photographic paper",
            keywords_by_lang={"en": ("photographic developer and photographic paper",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="unexposed-photographic-and-cinematographic-films",
            label="unexposed photographic and cinematographic films",
            keywords_by_lang={
                "en": ("unexposed photographic and cinematographic films",)
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
    "09.1.1.3": (
        SubLabel(
            id="binoculars-microscopes-telescopes-and-compasses",
            label="binoculars, microscopes, telescopes and compasses",
            keywords_by_lang={
                "en": ("binoculars, microscopes, telescopes and compasses",)
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
    "09.1.2.1": (
        SubLabel(
            id="camper-vans-caravans-and-trailers",
            label="camper vans, caravans and trailers",
            keywords_by_lang={"en": ("camper vans, caravans and trailers",)},
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
    "09.1.2.2": (
        SubLabel(
            id="aeroplanes-microlight-aircraft-gliders-hang-gliders-and-hot-",
            label="aeroplanes, microlight aircraft, gliders, hang gliders and hot-air balloons",
            keywords_by_lang={
                "en": (
                    "aeroplanes, microlight aircraft, gliders, hang gliders and hot-air balloons",
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
    "09.1.2.3": (
        SubLabel(
            id="boats-yachts-outboard-motors-sails-jet-skis-rigging-and-supe",
            label="boats, yachts, outboard motors, sails, jet skis, rigging and superstructures",
            keywords_by_lang={
                "en": (
                    "boats, yachts, outboard motors, sails, jet skis, rigging and superstructures",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="canoes-kayaks-windsurfing-boards-and-so-on",
            label="canoes, kayaks, windsurfing boards and so on",
            keywords_by_lang={"en": ("canoes, kayaks, windsurfing boards and so on",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sea-diving-equipment",
            label="sea diving equipment",
            keywords_by_lang={"en": ("sea diving equipment",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="vessels-for-recreation-sailboats-sailboards-water-sport-boar",
            label="vessels for recreation, sailboats, sailboards, water-sport boards",
            keywords_by_lang={
                "en": (
                    "vessels for recreation, sailboats, sailboards, water-sport boards",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="water-sport-equipment-and-related-accessories",
            label="water sport equipment and related accessories",
            keywords_by_lang={"en": ("water sport equipment and related accessories",)},
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
    "09.1.2.4": (
        SubLabel(
            id="horses-and-ponies-horse-and-pony-drawn-vehicles-and-camels-a",
            label="horses and ponies, horse- and pony-drawn vehicles, and camels and dromedaries, and related equipment (harnesses, bridles, reins, saddles, etc.), purchased for recreational purposes",
            keywords_by_lang={
                "en": (
                    "horses and ponies, horse- and pony-drawn vehicles, and camels and dromedaries, and related equipment (harnesses, bridles, reins, saddles, etc.), purchased for recreational purposes",
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
    "09.1.2.9": (
        SubLabel(
            id="billiards-tables-ping-pong-tables-pinball-machines-gaming-ma",
            label="billiards tables, ping-pong tables, pinball machines, gaming machines and so on",
            keywords_by_lang={
                "en": (
                    "billiards tables, ping-pong tables, pinball machines, gaming machines and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="electric-skateboards-self-balancing-unicycles-and-other-elec",
            label="electric skateboards, self-balancing unicycles and other electric recreational scooters",
            keywords_by_lang={
                "en": (
                    "electric skateboards, self-balancing unicycles and other electric recreational scooters",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="golf-carts",
            label="golf carts",
            keywords_by_lang={"en": ("golf carts",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="large-garden-swimming-pools-above-ground",
            label="large garden swimming pools (above ground)",
            keywords_by_lang={"en": ("large garden swimming pools (above ground)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-major-recreational-durables-n-e-c",
            label="other major recreational durables n.e.c.",
            keywords_by_lang={"en": ("other major recreational durables n.e.c.",)},
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
    "09.2.1.1": (
        SubLabel(
            id="electronic-games",
            label="electronic games",
            keywords_by_lang={"en": ("electronic games",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="game-applications",
            label="game applications",
            keywords_by_lang={"en": ("game applications",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gamepads-joysticks-racing-wheels-and-other-video-gaming-acce",
            label="gamepads, joysticks, racing wheels and other video gaming accessories",
            keywords_by_lang={
                "en": (
                    "gamepads, joysticks, racing wheels and other video gaming accessories",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-game-computers",
            label="video game computers",
            keywords_by_lang={"en": ("video game computers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-game-consoles",
            label="video game consoles",
            keywords_by_lang={"en": ("video game consoles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-game-software-for-game-consoles-computers-tablets-and-",
            label="video game software (for game consoles, computers, tablets and smartphones, on media such as CD-ROMs, cartridges, DVDs, Blu-ray discs and flash drives or available from the Internet)",
            keywords_by_lang={
                "en": (
                    "video game software (for game consoles, computers, tablets and smartphones, on media such as CD-ROMs, cartridges, DVDs, Blu-ray discs and flash drives or available from the Internet)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="game-console",
            label="game console",
            keywords_by_lang={"auto": ("game console",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="video-game-software",
            label="video game software",
            keywords_by_lang={"auto": ("video game software",)},
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
    "09.2.1.2": (
        SubLabel(
            id="disguises",
            label="disguises",
            keywords_by_lang={"en": ("disguises",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dolls",
            label="dolls",
            keywords_by_lang={"en": ("dolls",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="joke-toys",
            label="joke toys",
            keywords_by_lang={"en": ("joke toys",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="masks",
            label="masks",
            keywords_by_lang={"en": ("masks",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="modelling-clay",
            label="modelling clay",
            keywords_by_lang={"en": ("modelling clay",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="models-and-replicas-of-planes-boats-trains-and-so-on",
            label="models and replicas of planes, boats, trains and so on",
            keywords_by_lang={
                "en": ("models and replicas of planes, boats, trains and so on",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="novelties",
            label="novelties",
            keywords_by_lang={"en": ("novelties",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-collection-items-coins-medals-minerals-zoological-and-",
            label="other collection items (coins, medals, minerals, zoological and botanical specimens, etc.) and other hobby tools and articles, n.e.c.",
            keywords_by_lang={
                "en": (
                    "other collection items (coins, medals, minerals, zoological and botanical specimens, etc.) and other hobby tools and articles, n.e.c.",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="puzzles",
            label="puzzles",
            keywords_by_lang={"en": ("puzzles",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="remote-controlled-toy-cars-ships-planes-and-aerial-vehicles",
            label="remote controlled toy cars, ships, planes and aerial vehicles",
            keywords_by_lang={
                "en": ("remote controlled toy cars, ships, planes and aerial vehicles",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="requisites-for-stamp-collecting-practised-as-a-hobby-used-or",
            label="requisites for stamp-collecting practised as a hobby (used or cancelled postage stamps, stamp albums, etc.)",
            keywords_by_lang={
                "en": (
                    "requisites for stamp-collecting practised as a hobby (used or cancelled postage stamps, stamp albums, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="soft-toys-teddy-bears-and-so-on",
            label="soft toys, teddy bears and so on",
            keywords_by_lang={"en": ("soft toys, teddy bears and so on",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toy-cars-including-toy-trains-toy-bicycles-and-tricycles",
            label="toy cars, including toy trains, toy bicycles and tricycles",
            keywords_by_lang={
                "en": ("toy cars, including toy trains, toy bicycles and tricycles",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toy-construction-sets",
            label="toy construction sets",
            keywords_by_lang={"en": ("toy construction sets",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toy-instruments",
            label="toy instruments",
            keywords_by_lang={"en": ("toy instruments",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="traditional-games-for-example-card-games-parlour-games-board",
            label="traditional games, for example, card games, parlour games, board games, chess sets",
            keywords_by_lang={
                "en": (
                    "traditional games, for example, card games, parlour games, board games, chess sets",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="board-game",
            label="board game",
            keywords_by_lang={"auto": ("board game",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="collectible-figure",
            label="collectible figure",
            keywords_by_lang={"auto": ("collectible figure",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="construction-toy",
            label="construction toy",
            keywords_by_lang={"auto": ("construction toy",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="craft-kit",
            label="craft kit",
            keywords_by_lang={"auto": ("craft kit",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="educational-toy",
            label="educational toy",
            keywords_by_lang={"auto": ("educational toy",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="soft-toy",
            label="soft toy",
            keywords_by_lang={"auto": ("soft toy",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toy-vehicle",
            label="toy vehicle",
            keywords_by_lang={"auto": ("toy vehicle",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="board-and-card-games",
            label="Board And Card Games",
            keywords_by_lang={
                "en": (
                    "Board And Card Games",
                    "card games",
                    "chess sets",
                    "parlour games",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="construction-toys",
            label="Construction Toys",
            keywords_by_lang={
                "en": ("Construction Toys", "building blocks", "toy construction sets")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="costumes-and-masks",
            label="Costumes And Masks",
            keywords_by_lang={"en": ("Costumes And Masks", "disguises", "party masks")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dolls-and-plush-toys",
            label="Dolls And Plush Toys",
            keywords_by_lang={
                "en": (
                    "Dolls And Plush Toys",
                    "mini plush",
                    "soft toys",
                    "squishmallows",
                    "teddy bears",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="hobby-collection-items",
            label="Hobby Collection Items",
            keywords_by_lang={
                "en": (
                    "Hobby Collection Items",
                    "collectible coins",
                    "hobby tools",
                    "stamp albums",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="modelling-materials",
            label="Modelling Materials",
            keywords_by_lang={
                "en": ("Modelling Materials", "modelling clay", "play dough")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="musical-toy-instruments",
            label="Musical Toy Instruments",
            keywords_by_lang={
                "en": ("Musical Toy Instruments", "toy guitar", "toy piano")
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
            id="puzzles-and-mind-games",
            label="Puzzles And Mind Games",
            keywords_by_lang={
                "en": ("Puzzles And Mind Games", "jigsaw puzzles", "wooden puzzles")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="toy-vehicles",
            label="Toy Vehicles",
            keywords_by_lang={
                "en": (
                    "Toy Vehicles",
                    "remote control cars",
                    "toy cars",
                    "toy planes",
                    "toy trains",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "09.2.1.3": (
        SubLabel(
            id="christmas-trees",
            label="Christmas trees",
            keywords_by_lang={"en": ("Christmas trees",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="festoons",
            label="festoons",
            keywords_by_lang={"en": ("festoons",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fireworks-and-rockets",
            label="fireworks and rockets",
            keywords_by_lang={"en": ("fireworks and rockets",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="holiday-decorations-for-christmas-easter-diwali-eid-hanukkah",
            label="holiday decorations (for Christmas, Easter, Diwali, Eid, Hanukkah and other celebrations)",
            keywords_by_lang={
                "en": (
                    "holiday decorations (for Christmas, Easter, Diwali, Eid, Hanukkah and other celebrations)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="holiday-decoration",
            label="holiday decoration",
            keywords_by_lang={"auto": ("holiday decoration",)},
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
    ),
    "09.2.2.1": (
        SubLabel(
            id="firearms-and-ammunition-other-weapons-and-body-armour-for-hu",
            label="firearms and ammunition, other weapons, and body armour for hunting, sport and personal protection",
            keywords_by_lang={
                "en": (
                    "firearms and ammunition, other weapons, and body armour for hunting, sport and personal protection",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fishing-rods-and-other-fishing-equipment",
            label="fishing rods and other fishing equipment",
            keywords_by_lang={"en": ("fishing rods and other fishing equipment",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="game-specific-footwear-ski-boots-football-boots-golfing-shoe",
            label="game-specific footwear (ski boots, football boots, golfing shoes and other such footwear fitted with ice skates, rollers, spikes, studs, etc.)",
            keywords_by_lang={
                "en": (
                    "game-specific footwear (ski boots, football boots, golfing shoes and other such footwear fitted with ice skates, rollers, spikes, studs, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="game-specific-sportswear-ski-suits-etc",
            label="game-specific sportswear (ski suits, etc.)",
            keywords_by_lang={"en": ("game-specific sportswear (ski suits, etc.)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="gymnastic-physical-education-and-sporting-equipment-such-as-",
            label="gymnastic, physical education and sporting equipment, such as balls, shuttlecocks, nets, rackets, bats, skis, golf clubs, discuses and javelins",
            keywords_by_lang={
                "en": (
                    "gymnastic, physical education and sporting equipment, such as balls, shuttlecocks, nets, rackets, bats, skis, golf clubs, discuses and javelins",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-protective-sports-gear-such-as-life-jackets-boxing-glo",
            label="other protective sports gear, such as life jackets, boxing gloves, sport gloves, body padding, shin guards, goggles, belts, supports",
            keywords_by_lang={
                "en": (
                    "other protective sports gear, such as life jackets, boxing gloves, sport gloves, body padding, shin guards, goggles, belts, supports",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="parachutes-paragliders-and-other-skydiving-equipment",
            label="parachutes, paragliders and other skydiving equipment",
            keywords_by_lang={
                "en": ("parachutes, paragliders and other skydiving equipment",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="protective-sports-headgear",
            label="protective sports headgear",
            keywords_by_lang={"en": ("protective sports headgear",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="skateboards-kickboards-smart-balance-wheels-and-hover-boards",
            label="skateboards, kickboards, smart balance wheels and hover boards",
            keywords_by_lang={
                "en": (
                    "skateboards, kickboards, smart balance wheels and hover boards",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="walking-sticks-and-canes-for-recreational-purposes-e-g-hikin",
            label="walking sticks and canes for recreational purposes (e.g., hiking and tracking)",
            keywords_by_lang={
                "en": (
                    "walking sticks and canes for recreational purposes (e.g., hiking and tracking)",
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
    "09.2.2.2": (
        SubLabel(
            id="global-positioning-system-gps-satellite-based-radionavigatio",
            label="Global Positioning System (GPS) (satellite-based radionavigation positioning) equipment for boating and hiking",
            keywords_by_lang={
                "en": (
                    "Global Positioning System (GPS) (satellite-based radionavigation positioning) equipment for boating and hiking",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="equipment-for-beach-and-open-air-games-such-as-bowls-croquet",
            label="equipment for beach and open-air games, such as bowls, croquet, flying disc games, and volleyball and inflatable boats, rafts and swimming pools",
            keywords_by_lang={
                "en": (
                    "equipment for beach and open-air games, such as bowls, croquet, flying disc games, and volleyball and inflatable boats, rafts and swimming pools",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tents-sleeping-bags-backpacks-for-camping-air-mattresses-inf",
            label="tents, sleeping bags, backpacks for camping, air mattresses, inflating pumps, camping stoves and gas, barbecues and other camping accessories",
            keywords_by_lang={
                "en": (
                    "tents, sleeping bags, backpacks for camping, air mattresses, inflating pumps, camping stoves and gas, barbecues and other camping accessories",
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
    "09.3.1.1": (
        SubLabel(
            id="decorative-garden-materials",
            label="decorative garden materials",
            keywords_by_lang={"en": ("decorative garden materials",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="lawn-turf-specially-treated-soils-for-ornamental-gardens-and",
            label="lawn turf, specially treated soils for ornamental gardens and horticultural preparations",
            keywords_by_lang={
                "en": (
                    "lawn turf, specially treated soils for ornamental gardens and horticultural preparations",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pots-and-pot-holders",
            label="pots and pot holders",
            keywords_by_lang={"en": ("pots and pot holders",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="soil-peat-and-fertilizers-pesticides-composts",
            label="soil, peat and fertilizers, pesticides, composts",
            keywords_by_lang={
                "en": ("soil, peat and fertilizers, pesticides, composts",)
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
    "09.3.1.2": (
        SubLabel(
            id="cut-flowers",
            label="cut flowers",
            keywords_by_lang={"en": ("cut flowers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="flower-seeds-and-bulbs",
            label="flower seeds and bulbs",
            keywords_by_lang={"en": ("flower seeds and bulbs",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="indoor-flowers-natural-and-artificial-whether-in-a-vase-or-n",
            label="indoor flowers, natural and artificial, whether in a vase or not",
            keywords_by_lang={
                "en": (
                    "indoor flowers, natural and artificial, whether in a vase or not",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="indoor-plants-natural-and-artificial",
            label="indoor plants, natural and artificial",
            keywords_by_lang={"en": ("indoor plants, natural and artificial",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="natural-and-artificial-flowers-and-wreaths-for-decoration-of",
            label="natural and artificial flowers and wreaths for decoration of burial places",
            keywords_by_lang={
                "en": (
                    "natural and artificial flowers and wreaths for decoration of burial places",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="outdoor-flowers",
            label="outdoor flowers",
            keywords_by_lang={"en": ("outdoor flowers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="outdoor-plants",
            label="outdoor plants",
            keywords_by_lang={"en": ("outdoor plants",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="seeds-bulbs-and-tubers-for-planting",
            label="seeds, bulbs and tubers for planting",
            keywords_by_lang={"en": ("seeds, bulbs and tubers for planting",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="shrubs",
            label="shrubs",
            keywords_by_lang={"en": ("shrubs",)},
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
    "09.3.2.1": (
        SubLabel(
            id="purchase-of-pets",
            label="purchase of pets",
            keywords_by_lang={"en": ("purchase of pets",)},
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
    "09.3.2.2": (
        SubLabel(
            id="feed-and-veterinary-products-for-animals-used-for-transporta",
            label="feed and veterinary products for animals used for transportation, own consumption or recreation",
            keywords_by_lang={
                "en": (
                    "feed and veterinary products for animals used for transportation, own consumption or recreation",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-foods-pet-veterinary-and-grooming-products-collars-leash",
            label="pet foods, pet veterinary and grooming products, collars, leashes, kennels, birdcages, fish tanks, cat litter",
            keywords_by_lang={
                "en": (
                    "pet foods, pet veterinary and grooming products, collars, leashes, kennels, birdcages, fish tanks, cat litter",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-food-dry",
            label="pet food dry",
            keywords_by_lang={"auto": ("pet food dry",)},
            allowed_bases=frozenset({"item", "mass"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-treats",
            label="pet treats",
            keywords_by_lang={"auto": ("pet treats",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="wet-pet-food",
            label="wet pet food",
            keywords_by_lang={"auto": ("wet pet food",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cat-food",
            label="Cat Food",
            keywords_by_lang={
                "en": ("Cat Food", "canned cat food", "cat food", "cat meal")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dog-food",
            label="Dog Food",
            keywords_by_lang={
                "en": ("Dog Food", "dog food", "dog meal", "dog roll", "puppy food")
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
            id="pet-collars-and-leashes",
            label="Pet Collars and Leashes",
            keywords_by_lang={
                "en": ("Pet Collars and Leashes", "dog collar", "harness", "pet leash")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-grooming-products",
            label="Pet Grooming Products",
            keywords_by_lang={
                "en": (
                    "Pet Grooming Products",
                    "pet conditioner",
                    "pet spritz",
                    "puppy shampoo",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-housing-and-containment",
            label="Pet Housing and Containment",
            keywords_by_lang={
                "en": ("Pet Housing and Containment", "birdcage", "fish tank", "kennel")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-pest-control-products",
            label="Pet Pest Control Products",
            keywords_by_lang={
                "en": (
                    "Pet Pest Control Products",
                    "flea treatment",
                    "frontline",
                    "tick prevention",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pet-supplements-treats",
            label="Pet Treats and Supplements",
            keywords_by_lang={
                "en": (
                    "Pet Treats and Supplements",
                    "milky stick",
                    "pet snacks",
                    "pet treat",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="small-animal-food",
            label="Small Animal Food",
            keywords_by_lang={
                "en": (
                    "Small Animal Food",
                    "guinea pig food",
                    "rabbit food",
                    "rodent feed",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "09.4.1.0": (
        SubLabel(
            id="hire-of-photographic-and-cinematographic-equipment-and-optic",
            label="hire of photographic and cinematographic equipment and optical instruments",
            keywords_by_lang={
                "en": (
                    "hire of photographic and cinematographic equipment and optical instruments",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-of-photographic-and-cinematographic-equipment-and-opt",
            label="repair of photographic and cinematographic equipment and optical instruments",
            keywords_by_lang={
                "en": (
                    "repair of photographic and cinematographic equipment and optical instruments",
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
    "09.4.2.1": (
        SubLabel(
            id="hire-of-camper-vans-and-caravans",
            label="hire of camper vans and caravans",
            keywords_by_lang={"en": ("hire of camper vans and caravans",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="maintenance-and-repair-of-camper-vans-and-caravans",
            label="maintenance and repair of camper vans and caravans",
            keywords_by_lang={
                "en": ("maintenance and repair of camper vans and caravans",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="winter-lay-up-of-camper-vans-and-caravans",
            label="winter lay-up of camper vans and caravans",
            keywords_by_lang={"en": ("winter lay-up of camper vans and caravans",)},
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
    "09.4.2.2": (
        SubLabel(
            id="hire-of-major-recreational-durables-as-listed-under-09-1-2-2",
            label="hire of major recreational durables, as listed under 09.1.2.2, 09.1.2.3, 09.1.2.4 and 09.1.2.9",
            keywords_by_lang={
                "en": (
                    "hire of major recreational durables, as listed under 09.1.2.2, 09.1.2.3, 09.1.2.4 and 09.1.2.9",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="winter-lay-up-of-boats-yachts-and-so-on-hangar-services-for-",
            label="winter lay-up of boats, yachts and so on; hangar services for private planes; and marina services for boats",
            keywords_by_lang={
                "en": (
                    "winter lay-up of boats, yachts and so on; hangar services for private planes; and marina services for boats",
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
    "09.4.3.1": (
        SubLabel(
            id="hire-of-game-software-i-e-games-contained-on-cds-dvds-blu-ra",
            label="hire of game software (i.e., games contained on CDs, DVDs, Blu-ray discs, etc.)",
            keywords_by_lang={
                "en": (
                    "hire of game software (i.e., games contained on CDs, DVDs, Blu-ray discs, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscriptions-to-game-software-and-applications",
            label="subscriptions to game software and applications",
            keywords_by_lang={
                "en": ("subscriptions to game software and applications",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscriptions-to-play-online-games-for-video-game-network-se",
            label="subscriptions to play online games, for video game network services and for cloud gaming services",
            keywords_by_lang={
                "en": (
                    "subscriptions to play online games, for video game network services and for cloud gaming services",
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
    "09.4.3.2": (
        SubLabel(
            id="hire-and-repair-of-toys-and-hobby-related-articles",
            label="hire and repair of toys and hobby-related articles",
            keywords_by_lang={
                "en": ("hire and repair of toys and hobby-related articles",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-and-repair-of-video-game-consoles-and-other-video-game-",
            label="hire and repair of video game consoles and other video game-related equipment",
            keywords_by_lang={
                "en": (
                    "hire and repair of video game consoles and other video game-related equipment",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-of-toys-and-games",
            label="hire of toys and games",
            keywords_by_lang={"en": ("hire of toys and games",)},
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
    "09.4.4.0": (
        SubLabel(
            id="hire-and-repair-of-sporting-camping-and-open-air-recreationa",
            label="hire and repair of sporting, camping and open-air recreational equipment",
            keywords_by_lang={
                "en": (
                    "hire and repair of sporting, camping and open-air recreational equipment",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-of-beach-umbrellas-and-deckchairs",
            label="hire of beach umbrellas and deckchairs",
            keywords_by_lang={"en": ("hire of beach umbrellas and deckchairs",)},
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
    "09.4.5.0": (
        SubLabel(
            id="pet-boarding-services-and-pet-day-care-services",
            label="pet boarding services and pet day-care services.",
            keywords_by_lang={
                "en": ("pet boarding services and pet day-care services.",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="veterinary-and-hosting-services-for-household-animals-such-a",
            label="veterinary and hosting services for household animals, such as animals used for transportation, own consumption or recreation",
            keywords_by_lang={
                "en": (
                    "veterinary and hosting services for household animals, such as animals used for transportation, own consumption or recreation",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="veterinary-and-other-pet-services-such-as-grooming-tattooing",
            label="veterinary and other pet services, such as grooming, tattooing and training",
            keywords_by_lang={
                "en": (
                    "veterinary and other pet services, such as grooming, tattooing and training",
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
    "09.4.6.1": (
        SubLabel(
            id="arcade-games",
            label="arcade games",
            keywords_by_lang={"en": ("arcade games",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dancing-establishment-and-nightclub-entrance-fees",
            label="dancing establishment and nightclub entrance fees",
            keywords_by_lang={
                "en": ("dancing establishment and nightclub entrance fees",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="out-of-school-lessons-as-provided-to-individuals-and-groups-",
            label="out-of-school lessons, as provided to individuals and groups, in bridge, chess, sewing, cooking and other activities",
            keywords_by_lang={
                "en": (
                    "out-of-school lessons, as provided to individuals and groups, in bridge, chess, sewing, cooking and other activities",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pinball-and-other-games-for-adults-excluding-games-of-chance",
            label="pinball and other games for adults, excluding games of chance",
            keywords_by_lang={
                "en": ("pinball and other games for adults, excluding games of chance",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="recreational-and-sporting-services-provided-at-fairgrounds-a",
            label="recreational and sporting services provided at fairgrounds and amusement parks",
            keywords_by_lang={
                "en": (
                    "recreational and sporting services provided at fairgrounds and amusement parks",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="roundabouts-see-saws-and-other-playground-facilities-for-chi",
            label="roundabouts, see-saws and other playground facilities for children",
            keywords_by_lang={
                "en": (
                    "roundabouts, see-saws and other playground facilities for children",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-mountain-guides-tour-guides-and-so-on",
            label="services provided by mountain guides, tour guides and so on",
            keywords_by_lang={
                "en": ("services provided by mountain guides, tour guides and so on",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="water-park-services",
            label="water-park services",
            keywords_by_lang={"en": ("water-park services",)},
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
    "09.4.6.2": (
        SubLabel(
            id="boating-related-navigational-aid-services",
            label="boating-related navigational aid services",
            keywords_by_lang={"en": ("boating-related navigational aid services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cable-car-and-chairlift-transport-at-ski-resorts-and-holiday",
            label="cable-car and chairlift transport at ski resorts and holiday centres",
            keywords_by_lang={
                "en": (
                    "cable-car and chairlift transport at ski resorts and holiday centres",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fees-for-membership-in-fishermen-s-and-hunters-clubs",
            label="fees for membership in fishermen’s and hunters’ clubs",
            keywords_by_lang={
                "en": ("fees for membership in fishermen’s and hunters’ clubs",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fees-for-sports-title-and-sports-category-certificates",
            label="fees for sports title and sports category certificates",
            keywords_by_lang={
                "en": ("fees for sports title and sports category certificates",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hunting-and-fishing-licences",
            label="hunting and fishing licences",
            keywords_by_lang={"en": ("hunting and fishing licences",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="out-of-school-lessons-as-provided-to-individuals-and-groups-",
            label="out-of-school lessons, as provided to individuals and groups, in aerobics, skating, skiing, swimming and other sports",
            keywords_by_lang={
                "en": (
                    "out-of-school lessons, as provided to individuals and groups, in aerobics, skating, skiing, swimming and other sports",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="paid-fishing",
            label="paid fishing",
            keywords_by_lang={"en": ("paid fishing",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="recreational-and-sporting-services-provided-at-skating-rinks",
            label="recreational and sporting services provided at skating rinks, swimming pools, golf courses, gymnasiums, fitness centres, tennis courts, squash courts, bowling alleys and shooting ranges",
            keywords_by_lang={
                "en": (
                    "recreational and sporting services provided at skating rinks, swimming pools, golf courses, gymnasiums, fitness centres, tennis courts, squash courts, bowling alleys and shooting ranges",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="ski-slopes-ski-lifts-and-the-like",
            label="ski slopes, ski lifts and the like",
            keywords_by_lang={"en": ("ski slopes, ski lifts and the like",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-club-and-fitness-centre-memberships-fees",
            label="sports club and fitness centre memberships fees",
            keywords_by_lang={
                "en": ("sports club and fitness centre memberships fees",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sports-competition-participation-fees",
            label="sports competition participation fees",
            keywords_by_lang={"en": ("sports competition participation fees",)},
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
    "09.4.6.3": (
        SubLabel(
            id="admission-tickets-to-live-sporting-events-such-as-football-g",
            label="admission tickets to live sporting events, such as football games, hockey games, ice-skating competitions, ski competitions, soccer games, tennis matches, horse-racing, motor-racing, track cycling (at velodromes) and so on",
            keywords_by_lang={
                "en": (
                    "admission tickets to live sporting events, such as football games, hockey games, ice-skating competitions, ski competitions, soccer games, tennis matches, horse-racing, motor-racing, track cycling (at velodromes) and so on",
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
    "09.4.7.0": (
        SubLabel(
            id="online-games-of-chance",
            label="online games of chance",
            keywords_by_lang={"en": ("online games of chance",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="service-charges-associated-with-lotteries-bookmakers-totaliz",
            label="service charges associated with lotteries, bookmakers, totalizators, casinos and other gambling establishments, gaming machines, bingo halls, sale of scratch cards, sweepstakes and so on",
            keywords_by_lang={
                "en": (
                    "service charges associated with lotteries, bookmakers, totalizators, casinos and other gambling establishments, gaming machines, bingo halls, sale of scratch cards, sweepstakes and so on",
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
    "09.5.1.0": (
        SubLabel(
            id="musical-instruments-of-all-sizes-including-electronic-musica",
            label="musical instruments of all sizes, including electronic musical instruments, such as pianos, organs, violins, guitars, drums, trumpets, clarinets, flutes, recorders, harmonicas and so on",
            keywords_by_lang={
                "en": (
                    "musical instruments of all sizes, including electronic musical instruments, such as pianos, organs, violins, guitars, drums, trumpets, clarinets, flutes, recorders, harmonicas and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="replacement-parts-for-musical-instruments",
            label="replacement parts for musical instruments",
            keywords_by_lang={"en": ("replacement parts for musical instruments",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="guitar",
            label="guitar",
            keywords_by_lang={"auto": ("guitar",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="instrument-parts",
            label="instrument parts",
            keywords_by_lang={"auto": ("instrument parts",)},
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
    "09.5.2.0": (
        SubLabel(
            id="downloads-of-music-and-films",
            label="downloads of music and films",
            keywords_by_lang={"en": ("downloads of music and films",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="recorded-tapes-cd-roms-dvds-blu-ray-discs-gramophone-records",
            label="recorded tapes, CD-ROMs, DVDs, Blu-ray discs, gramophone records and flash drives, reproducing sound and picture material",
            keywords_by_lang={
                "en": (
                    "recorded tapes, CD-ROMs, DVDs, Blu-ray discs, gramophone records and flash drives, reproducing sound and picture material",
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
    "09.6.1.0": (
        SubLabel(
            id="art-and-music-festivals",
            label="art and music festivals",
            keywords_by_lang={"en": ("art and music festivals",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="music-dancing-and-artistic-performance",
            label="music, dancing and artistic performance",
            keywords_by_lang={"en": ("music, dancing and artistic performance",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-of-musicians-clowns-performers-for-private-entertai",
            label="services of musicians, clowns, performers for private entertainments",
            keywords_by_lang={
                "en": (
                    "services of musicians, clowns, performers for private entertainments",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-cinemas",
            label="services provided by cinemas",
            keywords_by_lang={"en": ("services provided by cinemas",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-circuses-sound-and-light-son-et-lumi-re",
            label="services provided by circuses, sound and light (son et lumière) and other shows",
            keywords_by_lang={
                "en": (
                    "services provided by circuses, sound and light (son et lumière) and other shows",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-concert-and-music-venues",
            label="services provided by concert and music venues",
            keywords_by_lang={"en": ("services provided by concert and music venues",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-theatres-and-opera-houses",
            label="services provided by theatres and opera houses",
            keywords_by_lang={
                "en": ("services provided by theatres and opera houses",)
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
    "09.6.2.0": (
        SubLabel(
            id="services-provided-by-libraries",
            label="services provided by libraries",
            keywords_by_lang={"en": ("services provided by libraries",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-museums-art-galleries-exhibitions-histo",
            label="services provided by museums, art galleries, exhibitions, historical monuments and archaeologic sites",
            keywords_by_lang={
                "en": (
                    "services provided by museums, art galleries, exhibitions, historical monuments and archaeologic sites",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-national-parks-zoological-and-botanical",
            label="services provided by national parks, zoological and botanical gardens and aquaria",
            keywords_by_lang={
                "en": (
                    "services provided by national parks, zoological and botanical gardens and aquaria",
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
    "09.6.3.0": (
        SubLabel(
            id="online-photographic-services",
            label="online photographic services",
            keywords_by_lang={"en": ("online photographic services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="photographic-services-provided-by-non-specialized-shops-e-g-",
            label="photographic services provided by non-specialized shops (e.g., supermarkets, consumer electronic stores, etc.)",
            keywords_by_lang={
                "en": (
                    "photographic services provided by non-specialized shops (e.g., supermarkets, consumer electronic stores, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="services-provided-by-photographers-such-as-portrait-photogra",
            label="services provided by photographers, such as portrait photography, event photography and video production (e.g., for weddings), film developing, print processing and enlarging",
            keywords_by_lang={
                "en": (
                    "services provided by photographers, such as portrait photography, event photography and video production (e.g., for weddings), film developing, print processing and enlarging",
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
    "09.6.9.0": (
        SubLabel(
            id="art-dance-music-and-photography-classes-in-a-classroom-setti",
            label="art, dance, music and photography classes (in a classroom setting or via e-learning)",
            keywords_by_lang={
                "en": (
                    "art, dance, music and photography classes (in a classroom setting or via e-learning)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="bookbinding-services",
            label="bookbinding services",
            keywords_by_lang={"en": ("bookbinding services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hire-and-repair-of-musical-instruments",
            label="hire and repair of musical instruments",
            keywords_by_lang={"en": ("hire and repair of musical instruments",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-the-premises-of-cultural-venues-for-amateur-music-",
            label="rental of the premises of cultural venues for amateur music group rehearsals and weddings and other celebrations",
            keywords_by_lang={
                "en": (
                    "rental of the premises of cultural venues for amateur music group rehearsals and weddings and other celebrations",
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
    "09.7.1.1": (
        SubLabel(
            id="education-textbooks-school-academic-manuals-etc-in-any-form-",
            label="education textbooks (school/academic manuals, etc.) in any form, complete or in excerpts, and on any media (including electronic formats and as photocopies)",
            keywords_by_lang={
                "en": (
                    "education textbooks (school/academic manuals, etc.) in any form, complete or in excerpts, and on any media (including electronic formats and as photocopies)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="encyclopaedias-and-dictionaries",
            label="encyclopaedias and dictionaries",
            keywords_by_lang={"en": ("encyclopaedias and dictionaries",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="academic-textbook",
            label="academic textbook",
            keywords_by_lang={"auto": ("academic textbook",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="childrens-learning-book",
            label="childrens learning book",
            keywords_by_lang={"auto": ("childrens learning book",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="exam-prep-book",
            label="exam prep book",
            keywords_by_lang={"auto": ("exam prep book",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="language-learning-book",
            label="language learning book",
            keywords_by_lang={"auto": ("language learning book",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="school-textbook",
            label="school textbook",
            keywords_by_lang={"auto": ("school textbook",)},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="dictionary",
            label="Dictionary",
            keywords_by_lang={"en": ("Dictionary", "lexicon", "thesaurus", "辞書")},
            allowed_bases=frozenset({"item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="encyclopedia",
            label="Encyclopedia",
            keywords_by_lang={"en": ("Encyclopedia", "encyclopaedia", "reference set")},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="exam-preparation-book",
            label="Exam Preparation Book",
            keywords_by_lang={
                "en": (
                    "Exam Preparation Book",
                    "test prep study guide",
                    "試験問題集",
                    "過去問",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="language-learning-textbook",
            label="Language Learning Textbook",
            keywords_by_lang={
                "en": (
                    "Language Learning Textbook",
                    "english learner book",
                    "jlpt prep book",
                    "えいご絵じてん",
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
            id="primary-school-textbook",
            label="Primary School Textbook",
            keywords_by_lang={
                "en": (
                    "Primary School Textbook",
                    "grade school manual",
                    "primary workbook",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="secondary-school-textbook",
            label="Secondary School Textbook",
            keywords_by_lang={
                "en": (
                    "Secondary School Textbook",
                    "academic manual",
                    "high school text",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tracing-practice-book",
            label="Tracing Practice Book",
            keywords_by_lang={
                "en": ("Tracing Practice Book", "handwriting book", "writing workbook")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "09.7.1.9": (
        SubLabel(
            id="art-books",
            label="art books",
            keywords_by_lang={"en": ("art books",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="atlases",
            label="atlases",
            keywords_by_lang={"en": ("atlases",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="children-s-books-and-scrapbooks-albums-and-colouring-books-f",
            label="children’s books and scrapbooks, albums and colouring books for children",
            keywords_by_lang={
                "en": (
                    "children’s books and scrapbooks, albums and colouring books for children",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fiction-and-non-fiction-books",
            label="fiction and non-fiction books",
            keywords_by_lang={"en": ("fiction and non-fiction books",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="musical-scores",
            label="musical scores",
            keywords_by_lang={"en": ("musical scores",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-books-in-any-form-complete-or-in-excerpts-and-on-any-m",
            label="other books in any form, complete or in excerpts, and on any media (including electronic formats and as photocopies)",
            keywords_by_lang={
                "en": (
                    "other books in any form, complete or in excerpts, and on any media (including electronic formats and as photocopies)",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="religious-books",
            label="religious books",
            keywords_by_lang={"en": ("religious books",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="scrapbooks-and-albums-for-children",
            label="scrapbooks and albums for children",
            keywords_by_lang={"en": ("scrapbooks and albums for children",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="travel-guides",
            label="travel guides",
            keywords_by_lang={"en": ("travel guides",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="business-finance-book",
            label="business finance book",
            keywords_by_lang={"auto": ("business finance book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="children-book",
            label="children book",
            keywords_by_lang={"auto": ("children book",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="cookbook",
            label="cookbook",
            keywords_by_lang={"auto": ("cookbook",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fiction-book",
            label="fiction book",
            keywords_by_lang={"auto": ("fiction book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="health-book",
            label="health book",
            keywords_by_lang={"auto": ("health book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="history-politics-book",
            label="history politics book",
            keywords_by_lang={"auto": ("history politics book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="language-learning-book",
            label="language learning book",
            keywords_by_lang={"auto": ("language learning book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="nonfiction-book",
            label="nonfiction book",
            keywords_by_lang={"auto": ("nonfiction book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="parenting-book",
            label="parenting book",
            keywords_by_lang={"auto": ("parenting book",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="self-help-book",
            label="self help book",
            keywords_by_lang={"auto": ("self help book",)},
            allowed_bases=frozenset({"item", "count"}),
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
    "09.7.2.1": (
        SubLabel(
            id="newspaper-subscriptions-digital-access",
            label="newspaper subscriptions (digital access)",
            keywords_by_lang={"en": ("newspaper subscriptions (digital access)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="newspaper-subscriptions-home-delivery",
            label="newspaper subscriptions (home-delivery)",
            keywords_by_lang={"en": ("newspaper subscriptions (home-delivery)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="newspapers-in-all-electronic-formats",
            label="newspapers in all electronic formats",
            keywords_by_lang={"en": ("newspapers in all electronic formats",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="newspapers-purchased-at-kiosks",
            label="newspapers purchased at kiosks",
            keywords_by_lang={"en": ("newspapers purchased at kiosks",)},
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
    "09.7.2.2": (
        SubLabel(
            id="business-and-political-magazines",
            label="business and political magazines",
            keywords_by_lang={"en": ("business and political magazines",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="children-s-magazines",
            label="children’s magazines",
            keywords_by_lang={"en": ("children’s magazines",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="hobby-and-leisure-magazines",
            label="hobby and leisure magazines",
            keywords_by_lang={"en": ("hobby and leisure magazines",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="lifestyle-magazines",
            label="lifestyle magazines",
            keywords_by_lang={"en": ("lifestyle magazines",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="magazine-and-periodical-subscriptions-home-delivery",
            label="magazine and periodical subscriptions (home delivery)",
            keywords_by_lang={
                "en": ("magazine and periodical subscriptions (home delivery)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="magazines-and-periodical-subscriptions-digital-access",
            label="magazines and periodical subscriptions (digital access)",
            keywords_by_lang={
                "en": ("magazines and periodical subscriptions (digital access)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="magazines-and-periodicals-in-all-electronic-formats",
            label="magazines and periodicals in all electronic formats",
            keywords_by_lang={
                "en": ("magazines and periodicals in all electronic formats",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="television-magazines",
            label="television magazines",
            keywords_by_lang={"en": ("television magazines",)},
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
    "09.7.3.0": (
        SubLabel(
            id="catalogues-and-advertising-material",
            label="catalogues and advertising material",
            keywords_by_lang={"en": ("catalogues and advertising material",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="greeting-cards-and-visiting-cards-announcement-and-message-c",
            label="greeting cards and visiting cards, announcement and message cards",
            keywords_by_lang={
                "en": (
                    "greeting cards and visiting cards, announcement and message cards",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="maps-and-globes",
            label="maps and globes",
            keywords_by_lang={"en": ("maps and globes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="posters-picture-postcards-calendars",
            label="posters, picture postcards, calendars",
            keywords_by_lang={"en": ("posters, picture postcards, calendars",)},
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
    "09.7.4.0": (
        SubLabel(
            id="drawing-and-painting-materials-such-as-canvas-card-paints-cr",
            label="drawing and painting materials, such as canvas, card, paints, crayons, pastels and brushes",
            keywords_by_lang={
                "en": (
                    "drawing and painting materials, such as canvas, card, paints, crayons, pastels and brushes",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="drawing-paper",
            label="drawing paper",
            keywords_by_lang={"en": ("drawing paper",)},
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="educational-materials-such-as-exercise-books",
            label="educational materials, such as exercise books",
            keywords_by_lang={"en": ("educational materials, such as exercise books",)},
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="paper-punches-paper-cutters-paper-scissors-office-glues-and-",
            label="paper punches, paper cutters, paper scissors, office glues and adhesives, staplers and staples, paper clips, drawing pins and so on",
            keywords_by_lang={
                "en": (
                    "paper punches, paper cutters, paper scissors, office glues and adhesives, staplers and staples, paper clips, drawing pins and so on",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="pens-pencils-fountain-pens-ballpoint-pens-felt-tip-pens-inks",
            label="pens, pencils, fountain pens, ballpoint pens, felt-tip pens, inks, erasers, pencil sharpeners and so on",
            keywords_by_lang={
                "en": (
                    "pens, pencils, fountain pens, ballpoint pens, felt-tip pens, inks, erasers, pencil sharpeners and so on",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="postcards-envelopes-and-other-postal-matter-not-pre-franked",
            label="postcards, envelopes and other postal matter, not pre-franked",
            keywords_by_lang={
                "en": ("postcards, envelopes and other postal matter, not pre-franked",)
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="slide-rules-geometry-instruments-slates-chalks-and-pencil-bo",
            label="slide rules, geometry instruments, slates, chalks and pencil boxes",
            keywords_by_lang={
                "en": (
                    "slide rules, geometry instruments, slates, chalks and pencil boxes",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="stencils-carbon-paper-inking-pads-correcting-fluids-and-so-o",
            label="stencils, carbon paper, inking pads, correcting fluids and so on",
            keywords_by_lang={
                "en": (
                    "stencils, carbon paper, inking pads, correcting fluids and so on",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="wrapping-paper",
            label="wrapping paper",
            keywords_by_lang={
                "en": ("wrapping paper", "Wrapping Paper", "gift wrap", "wrapping roll")
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="writing-pads-envelopes-account-books-diaries-and-so-on",
            label="writing pads, envelopes, account books, diaries and so on",
            keywords_by_lang={
                "en": ("writing pads, envelopes, account books, diaries and so on",)
            },
            allowed_bases=frozenset({"count", "item"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="marker",
            label="marker",
            keywords_by_lang={"auto": ("marker",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="notebook",
            label="notebook",
            keywords_by_lang={"auto": ("notebook",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pen",
            label="pen",
            keywords_by_lang={"auto": ("pen",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pencil",
            label="pencil",
            keywords_by_lang={"auto": ("pencil",)},
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="geometry-instruments",
            label="Geometry Instruments",
            keywords_by_lang={
                "en": (
                    "Geometry Instruments",
                    "compasses",
                    "protractors",
                    "rulers",
                    "slide rules",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="office-binding-and-fastening-tools",
            label="Office Binding And Fastening Tools",
            keywords_by_lang={
                "en": (
                    "Office Binding And Fastening Tools",
                    "drawing pins",
                    "paper clips",
                    "staplers",
                    "staples",
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
            id="painting-and-drawing-supplies",
            label="Painting And Drawing Supplies",
            keywords_by_lang={
                "en": (
                    "Painting And Drawing Supplies",
                    "canvas",
                    "crayons",
                    "paints",
                    "pastels",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="paper-cutting-and-punching-tools",
            label="Paper Cutting And Punching Tools",
            keywords_by_lang={
                "en": (
                    "Paper Cutting And Punching Tools",
                    "paper cutters",
                    "paper punches",
                    "paper scissors",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="pens-and-pencils",
            label="Pens And Pencils",
            keywords_by_lang={
                "en": (
                    "Pens And Pencils",
                    "ballpoint pen",
                    "felt-tip pen",
                    "fountain pen",
                    "mechanical pencil",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="writing-accessories",
            label="Writing Accessories",
            keywords_by_lang={
                "en": (
                    "Writing Accessories",
                    "correcting fluid",
                    "erasers",
                    "inks",
                    "pencil sharpeners",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="writing-paper-products",
            label="Writing Paper Products",
            keywords_by_lang={
                "en": (
                    "Writing Paper Products",
                    "diaries",
                    "envelopes",
                    "exercise books",
                    "writing pads",
                )
            },
            allowed_bases=frozenset({"count", "item"}),
            role="synonym",
            numeric_id=None,
        ),
    ),
    "09.8.0.0": (
        SubLabel(
            id="all-inclusive-holidays-or-tours-that-provide-for-travel-food",
            label="all-inclusive holidays or tours that provide for travel, food, accommodation, guides and so on",
            keywords_by_lang={
                "en": (
                    "all-inclusive holidays or tours that provide for travel, food, accommodation, guides and so on",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="excursion-tours-including-transport-and-guide",
            label="excursion tours, including transport and guide",
            keywords_by_lang={
                "en": ("excursion tours, including transport and guide",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="sport-and-recreation-camps-for-children-as-well-as-for-adult",
            label="sport and recreation camps for children as well as for adults (usually during summer holidays), which include catering and accommodation as well as activities",
            keywords_by_lang={
                "en": (
                    "sport and recreation camps for children as well as for adults (usually during summer holidays), which include catering and accommodation as well as activities",
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
}
