"""Auto-generated sub_labels for COICOP class 08.

Source: keywords/coicop/_sub_labels.parquet (slug vocabulary),
        data/prices/_enrich/_tier_b_index*/ (allowed_bases bootstrap).
Regenerate via $CLAUDE_JOB_DIR/generate_subs_sidecars.py.
"""

from __future__ import annotations

from prices.enrich.keywords.types import SubLabel

SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]] = {
    "08.1.1.0": (
        SubLabel(
            id="telephones-telefax-and-telephone-answering-machines-and-tele",
            label="telephones, telefax and telephone answering machines, and telephone loudspeakers",
            keywords_by_lang={
                "en": (
                    "telephones, telefax and telephone answering machines, and telephone loudspeakers",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cordless-telephone",
            label="Cordless telephone",
            keywords_by_lang={
                "en": (
                    "Cordless telephone",
                    "DECT phone",
                    "home cordless phone",
                    "wireless phone",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="fixed-telephone",
            label="Fixed telephone",
            keywords_by_lang={
                "en": (
                    "Fixed telephone",
                    "corded phone",
                    "desk phone",
                    "landline phone",
                    "wired telephone",
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
            id="telefax-machine",
            label="Telefax machine",
            keywords_by_lang={
                "en": ("Telefax machine", "fax machine", "standalone fax")
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="telephone-answering-machine",
            label="Telephone answering machine",
            keywords_by_lang={
                "en": (
                    "Telephone answering machine",
                    "answering machine",
                    "call recorder",
                    "voice mail machine",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="telephone-loudspeaker",
            label="Telephone loudspeaker",
            keywords_by_lang={
                "en": (
                    "Telephone loudspeaker",
                    "conference speakerphone",
                    "external phone speaker",
                    "phone speakerphone",
                )
            },
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
    ),
    "08.1.2.0": (
        SubLabel(
            id="mobile-telephone-handsets-including-multifunctional-devices",
            label="mobile telephone handsets, including multifunctional devices",
            keywords_by_lang={
                "en": ("mobile telephone handsets, including multifunctional devices",)
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="smartphones",
            label="smartphones",
            keywords_by_lang={"en": ("smartphones",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="smartphone",
            label="smartphone",
            keywords_by_lang={"auto": ("smartphone",)},
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
    "08.1.3.1": (
        SubLabel(
            id="desktop-computers-and-laptops",
            label="desktop computers and laptops",
            keywords_by_lang={"en": ("desktop computers and laptops",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="tablets",
            label="tablets",
            keywords_by_lang={"en": ("tablets",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="telefax-and-telephone-answering-facilities-of-personal-compu",
            label="telefax and telephone-answering facilities of personal computers",
            keywords_by_lang={
                "en": (
                    "telefax and telephone-answering facilities of personal computers",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="laptop",
            label="laptop",
            keywords_by_lang={"auto": ("laptop",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="tablet",
            label="tablet",
            keywords_by_lang={"auto": ("tablet",)},
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
    "08.1.3.2": (
        SubLabel(
            id="3-d-printers",
            label="3-D printers",
            keywords_by_lang={"en": ("3-D printers",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="calculators-including-pocket-calculators",
            label="calculators, including pocket calculators",
            keywords_by_lang={"en": ("calculators, including pocket calculators",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="printers-photocopiers-scanners-monitors-projectors-augmented",
            label="printers, photocopiers, scanners, monitors, projectors, augmented-reality and virtual-reality head mounts, modems, routers, network switches and the like, keyboards, mouses and digitizers",
            keywords_by_lang={
                "en": (
                    "printers, photocopiers, scanners, monitors, projectors, augmented-reality and virtual-reality head mounts, modems, routers, network switches and the like, keyboards, mouses and digitizers",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toner-and-ink-cartridges-laser-printer-drums-typewriter-ribb",
            label="toner and ink cartridges, laser printer drums, typewriter ribbons",
            keywords_by_lang={
                "en": (
                    "toner and ink cartridges, laser printer drums, typewriter ribbons",
                )
            },
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="typewriters-and-word-processors-device",
            label="typewriters and word processors (device)",
            keywords_by_lang={"en": ("typewriters and word processors (device)",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="web-cameras",
            label="web cameras.",
            keywords_by_lang={"en": ("web cameras.",)},
            allowed_bases=frozenset({"item", "count"}),
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="toner-cartridge",
            label="toner cartridge",
            keywords_by_lang={"auto": ("toner cartridge",)},
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
    "08.1.4.0": (
        SubLabel(
            id="audio-and-video-systems-for-cars",
            label="audio and video systems for cars",
            keywords_by_lang={"en": ("audio and video systems for cars",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="digital-media-players",
            label="digital media players",
            keywords_by_lang={"en": ("digital media players",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="headphones-earplugs-and-wireless-including-bluetooth-headset",
            label="headphones, earplugs and wireless, including Bluetooth headsets",
            keywords_by_lang={
                "en": (
                    "headphones, earplugs and wireless, including Bluetooth headsets",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="portable-and-non-portable-cd-players",
            label="portable and non-portable CD players",
            keywords_by_lang={"en": ("portable and non-portable CD players",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="portable-and-non-portable-sound-players",
            label="portable and non-portable sound players",
            keywords_by_lang={"en": ("portable and non-portable sound players",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="radio-receivers-radio-sets-digital-radio-sets-internet-radio",
            label="radio receivers (radio sets, digital radio sets, Internet radio sets, satellite radio sets, car radios, radio clocks, two-way radios, walkie-talkies, and amateur radio receivers and transmitters)",
            keywords_by_lang={
                "en": (
                    "radio receivers (radio sets, digital radio sets, Internet radio sets, satellite radio sets, car radios, radio clocks, two-way radios, walkie-talkies, and amateur radio receivers and transmitters)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="set-top-boxes-satellite-receivers-internet-protocol-televisi",
            label="set-top boxes, satellite receivers, Internet Protocol television receivers and television converter boxes",
            keywords_by_lang={
                "en": (
                    "set-top boxes, satellite receivers, Internet Protocol television receivers and television converter boxes",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="stereo-equipment-and-cd-radio-cassette-recorders",
            label="stereo equipment and CD radio cassette recorders",
            keywords_by_lang={
                "en": ("stereo equipment and CD radio cassette recorders",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="television-sets-video-cassette-players-and-recorders-digital",
            label="television sets, video cassette players and recorders, digital video recorders (DVRs), DVD players, Blu-ray players, streaming boxes and television aerials of all types",
            keywords_by_lang={
                "en": (
                    "television sets, video cassette players and recorders, digital video recorders (DVRs), DVD players, Blu-ray players, streaming boxes and television aerials of all types",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="turntables-tuners-amplifiers-cassette-decks-microphones-and-",
            label="turntables, tuners, amplifiers, cassette decks, microphones and speakers, disc jockey (DJ) equipment and karaoke systems",
            keywords_by_lang={
                "en": (
                    "turntables, tuners, amplifiers, cassette decks, microphones and speakers, disc jockey (DJ) equipment and karaoke systems",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="headphones",
            label="headphones",
            keywords_by_lang={"auto": ("headphones",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="speaker",
            label="speaker",
            keywords_by_lang={"auto": ("speaker",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="television",
            label="television",
            keywords_by_lang={"auto": ("television",)},
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
    "08.1.5.0": (
        SubLabel(
            id="blu-ray-discs-recordable-bd-r-and-recordable-erasable-bd-re",
            label="Blu-ray discs recordable (BD-R) and recordable erasable (BD-RE)",
            keywords_by_lang={
                "en": (
                    "Blu-ray discs recordable (BD-R) and recordable erasable (BD-RE)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="dvds-recordable-dvd-r-and-rewritable-dvd-rw",
            label="DVDs recordable (DVD-R) and rewritable (DVD-RW)",
            keywords_by_lang={
                "en": ("DVDs recordable (DVD-R) and rewritable (DVD-RW)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="secure-digital-sd-cards-compactflash-cf-cards-and-so-on",
            label="Secure digital (SD) cards, CompactFlash (CF) cards and so on",
            keywords_by_lang={
                "en": ("Secure digital (SD) cards, CompactFlash (CF) cards and so on",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="usb-keys-and-usb-flash-drives",
            label="USB keys and USB flash drives",
            keywords_by_lang={"en": ("USB keys and USB flash drives",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="audiotapes-audio-cassettes-and-digital-audiotapes-dat",
            label="audiotapes, audio cassettes and digital audiotapes (DAT)",
            keywords_by_lang={
                "en": ("audiotapes, audio cassettes and digital audiotapes (DAT)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="compact-discs-recordable-cd-r-and-rewritable-cd-rw",
            label="compact discs recordable (CD-R) and rewritable (CD-RW)",
            keywords_by_lang={
                "en": ("compact discs recordable (CD-R) and rewritable (CD-RW)",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="external-hard-drives-solid-state-drives-and-network-attached",
            label="external hard drives, solid-state drives and network attached storage (NAS)",
            keywords_by_lang={
                "en": (
                    "external hard drives, solid-state drives and network attached storage (NAS)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="magnetic-data-tapes",
            label="magnetic data tapes",
            keywords_by_lang={"en": ("magnetic data tapes",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-magnetic-recording-media",
            label="other magnetic recording media",
            keywords_by_lang={"en": ("other magnetic recording media",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-optical-recording-media",
            label="other optical recording media",
            keywords_by_lang={"en": ("other optical recording media",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-recording-media-phase-change-recording-media-holograph",
            label="other recording media (phase-change recording media, holographic recording media, molecular recording media, etc.)",
            keywords_by_lang={
                "en": (
                    "other recording media (phase-change recording media, holographic recording media, molecular recording media, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-cassettes",
            label="video cassettes",
            keywords_by_lang={"en": ("video cassettes",)},
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
    "08.1.9.1": (
        SubLabel(
            id="baby-monitors",
            label="baby monitors",
            keywords_by_lang={"en": ("baby monitors",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="e-book-readers",
            label="e-book readers",
            keywords_by_lang={"en": ("e-book readers",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="fitness-trackers-and-other-wearable-devices-e-g-smartglasses",
            label="fitness trackers and other wearable devices (e.g., smartglasses) that, in general, do not work without a smartphone or tablet connection",
            keywords_by_lang={
                "en": (
                    "fitness trackers and other wearable devices (e.g., smartglasses) that, in general, do not work without a smartphone or tablet connection",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="smartwatches",
            label="smartwatches",
            keywords_by_lang={"en": ("smartwatches",)},
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
    "08.1.9.2": (
        SubLabel(
            id="chargers-batteries-for-information-and-communication-equipme",
            label="chargers, batteries for information and communication equipment, cables, power banks, docking stations, covers, cases, cradles and mounts",
            keywords_by_lang={
                "en": (
                    "chargers, batteries for information and communication equipment, cables, power banks, docking stations, covers, cases, cradles and mounts",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="computer-components-for-example-processors-internal-hard-dri",
            label="computer components, for example, processors, internal hard drives, solid-state drives, motherboards, memory, DVD drives, hard drives",
            keywords_by_lang={
                "en": (
                    "computer components, for example, processors, internal hard drives, solid-state drives, motherboards, memory, DVD drives, hard drives",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cable",
            label="cable",
            keywords_by_lang={"auto": ("cable",)},
            allowed_bases=frozenset({"item", "length"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="charger",
            label="charger",
            keywords_by_lang={"auto": ("charger",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="device-battery",
            label="device battery",
            keywords_by_lang={"auto": ("device battery",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="device-mount",
            label="device mount",
            keywords_by_lang={"auto": ("device mount",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="phone-case",
            label="phone case",
            keywords_by_lang={"auto": ("phone case",)},
            allowed_bases=frozenset({"item", "count"}),
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="power-bank",
            label="power bank",
            keywords_by_lang={"auto": ("power bank",)},
            allowed_bases=None,
            role="synonym",
            numeric_id=None,
        ),
        SubLabel(
            id="screen-protector",
            label="screen protector",
            keywords_by_lang={"auto": ("screen protector",)},
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
    "08.2.0.0": (
        SubLabel(
            id="computer-software-packages-comprising-for-example-operating-",
            label="computer software packages, comprising, for example, operating systems, applications and programming languages",
            keywords_by_lang={
                "en": (
                    "computer software packages, comprising, for example, operating systems, applications and programming languages",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="software-subscriptions-and-use-of-online-software",
            label="software subscriptions and use of online software",
            keywords_by_lang={
                "en": ("software subscriptions and use of online software",)
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
    "08.3.1.0": (
        SubLabel(
            id="installation-and-subscription-costs-associated-with-personal",
            label="installation and subscription costs associated with personal telephone equipment",
            keywords_by_lang={
                "en": (
                    "installation and subscription costs associated with personal telephone equipment",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="local-regional-national-and-international-calls",
            label="local, regional, national and international calls",
            keywords_by_lang={
                "en": ("local, regional, national and international calls",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="telephone-calls-made-from-a-private-line-or-from-a-public-li",
            label="telephone calls made from a private line; or from a public line (public telephone box, post office cabin, etc.)",
            keywords_by_lang={
                "en": (
                    "telephone calls made from a private line; or from a public line (public telephone box, post office cabin, etc.)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="telephone-calls-made-from-hotels-caf-s-restaurants-and-so-on",
            label="telephone calls made from hotels, cafés, restaurants and so on",
            keywords_by_lang={
                "en": (
                    "telephone calls made from hotels, cafés, restaurants and so on",
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
    "08.3.2.0": (
        SubLabel(
            id="additional-calling-features-such-as-voice-mail-and-call-disp",
            label="additional calling features, such as voice mail and call display, whether separately priced from or bundled with mobile service",
            keywords_by_lang={
                "en": (
                    "additional calling features, such as voice mail and call display, whether separately priced from or bundled with mobile service",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="costs-of-telephone-equipment-if-included-in-subscription-cos",
            label="costs of telephone equipment if included in subscription costs",
            keywords_by_lang={
                "en": (
                    "costs of telephone equipment if included in subscription costs",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="local-regional-national-and-international-calls-including-vo",
            label="local, regional, national and international calls, including voice and video calls",
            keywords_by_lang={
                "en": (
                    "local, regional, national and international calls, including voice and video calls",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mobile-telephone-voice-and-messaging-plans-that-include-limi",
            label="mobile telephone voice and messaging plans that include limited data",
            keywords_by_lang={
                "en": (
                    "mobile telephone voice and messaging plans that include limited data",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mobile-telephone-voice-text-and-data-plans",
            label="mobile telephone voice, text and data plans",
            keywords_by_lang={"en": ("mobile telephone voice, text and data plans",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="mobile-telephones-included-in-a-prepaid-or-post-paid-package",
            label="mobile telephones included in a (prepaid or post-paid) package, generally tied to a specific operator for a certain period of time, if not separately priced",
            keywords_by_lang={
                "en": (
                    "mobile telephones included in a (prepaid or post-paid) package, generally tied to a specific operator for a certain period of time, if not separately priced",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="other-mobile-telephone-services-n-e-c",
            label="other mobile telephone services n.e.c.",
            keywords_by_lang={"en": ("other mobile telephone services n.e.c.",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscription-fees-for-messaging-services-including-voice-tex",
            label="subscription fees for messaging services, including voice, text (SMS), multimedia content (MMS) and so on",
            keywords_by_lang={
                "en": (
                    "subscription fees for messaging services, including voice, text (SMS), multimedia content (MMS) and so on",
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
    "08.3.3.0": (
        SubLabel(
            id="internet-access-services-provided-by-operators-of-wired-wire",
            label="Internet access services provided by operators of wired, wireless or satellite infrastructure",
            keywords_by_lang={
                "en": (
                    "Internet access services provided by operators of wired, wireless or satellite infrastructure",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="activation-and-installation-fees-and-monthly-rates",
            label="activation and installation fees and monthly rates",
            keywords_by_lang={
                "en": ("activation and installation fees and monthly rates",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="cloud-storage-file-hosting-and-web-hosting-services",
            label="cloud storage, file hosting and web hosting services",
            keywords_by_lang={
                "en": ("cloud storage, file hosting and web hosting services",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscriptions-for-email-services",
            label="subscriptions for email services",
            keywords_by_lang={"en": ("subscriptions for email services",)},
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
    "08.3.4.0": (
        SubLabel(
            id="packages-bundling-together-telephony-internet-and-television",
            label="packages bundling together telephony, Internet and television services",
            keywords_by_lang={
                "en": (
                    "packages bundling together telephony, Internet and television services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="packages-comprising-any-combination-of-telecommunications-se",
            label="packages comprising any combination of telecommunications services",
            keywords_by_lang={
                "en": (
                    "packages comprising any combination of telecommunications services",
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
    "08.3.5.0": (
        SubLabel(
            id="rental-of-internet-access-provision-equipment",
            label="rental of Internet access provision equipment",
            keywords_by_lang={"en": ("rental of Internet access provision equipment",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-telegraphy-telex-and-telefax-equipment",
            label="rental of telegraphy, telex and telefax equipment",
            keywords_by_lang={
                "en": ("rental of telegraphy, telex and telefax equipment",)
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-telephones-telefax-machines-telephone-answering-ma",
            label="rental of telephones, telefax machines, telephone-answering machines and telephone loudspeakers",
            keywords_by_lang={
                "en": (
                    "rental of telephones, telefax machines, telephone-answering machines and telephone loudspeakers",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-wireless-telephone-equipment",
            label="rental of wireless telephone equipment",
            keywords_by_lang={"en": ("rental of wireless telephone equipment",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-maintenance-and-rental-of-all-information-and-communi",
            label="repair, maintenance and rental of all information and communication equipment, including the cost of materials if the materials are not separately priced",
            keywords_by_lang={
                "en": (
                    "repair, maintenance and rental of all information and communication equipment, including the cost of materials if the materials are not separately priced",
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
    "08.3.9.1": (
        SubLabel(
            id="fees-licenses-for-access-to-reception-of-public-television-o",
            label="fees/licenses for access to/reception of public television or radio broadcasts or the possession of a television set or radio",
            keywords_by_lang={
                "en": (
                    "fees/licenses for access to/reception of public television or radio broadcasts or the possession of a television set or radio",
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
    "08.3.9.2": (
        SubLabel(
            id="online-videorecorder-services-web-based-digital-videorecorde",
            label="online videorecorder services (web-based digital videorecorder (DVR) services)",
            keywords_by_lang={
                "en": (
                    "online videorecorder services (web-based digital videorecorder (DVR) services)",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="rental-of-cds-video-tapes-dvds-blu-ray-discs-software-exclud",
            label="rental of CDs, video tapes, DVDs, Blu-ray discs, software (excluding game software) or download with subscription of audio-visual content",
            keywords_by_lang={
                "en": (
                    "rental of CDs, video tapes, DVDs, Blu-ray discs, software (excluding game software) or download with subscription of audio-visual content",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="streaming-services-film-and-music",
            label="streaming services (film and music)",
            keywords_by_lang={"en": ("streaming services (film and music)",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscription-to-cable-television-satellite-television-intern",
            label="subscription to cable television, satellite television, Internet Protocol television (IPTV), and pay television",
            keywords_by_lang={
                "en": (
                    "subscription to cable television, satellite television, Internet Protocol television (IPTV), and pay television",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="subscription-to-television-via-decoders-and-rental-of-decode",
            label="subscription to television via decoders and rental of decoders",
            keywords_by_lang={
                "en": (
                    "subscription to television via decoders and rental of decoders",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="video-on-demand-vod-services",
            label="video on demand (VOD) services",
            keywords_by_lang={"en": ("video on demand (VOD) services",)},
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
    "08.3.9.9": (
        SubLabel(
            id="provision-of-nomadic-voice-over-internet-protocol-voip-servi",
            label="provision of nomadic voice over Internet Protocol (VoIP) services",
            keywords_by_lang={
                "en": (
                    "provision of nomadic voice over Internet Protocol (VoIP) services",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="repair-rental-and-installation-of-equipment-for-the-receptio",
            label="repair, rental, and installation of equipment for the reception, recording and reproduction of sound and vision",
            keywords_by_lang={
                "en": (
                    "repair, rental, and installation of equipment for the reception, recording and reproduction of sound and vision",
                )
            },
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="software-installation-services",
            label="software installation services",
            keywords_by_lang={"en": ("software installation services",)},
            allowed_bases=None,
            role="anchor",
            numeric_id=None,
        ),
        SubLabel(
            id="telegraphy-telex-and-telefax-services",
            label="telegraphy, telex and telefax services",
            keywords_by_lang={"en": ("telegraphy, telex and telefax services",)},
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
