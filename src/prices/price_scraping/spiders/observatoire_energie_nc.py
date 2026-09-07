"""Official New Caledonia energy tariff bulletin."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import scrapy


_PRICE_AT_END_RE = re.compile(
    r":\s*([0-9][0-9\s]*(?:,[0-9]+)?)\s*(?:f\.?\s*cfp(?:/[a-z]+)?)?\s*$",
    re.I,
)
_ENUM_RE = re.compile(r"^\d+\s*[deg°]\)\s*", re.I)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def _slug(text: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return _SLUG_RE.sub("-", ascii_text.lower()).strip("-")


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _price(text: str) -> str:
    return text.replace(" ", "").replace(",", ".")


def _unit(text: str, fallback: str | None = None) -> str | None:
    lowered = text.lower()
    if "f.cfp/l" in lowered:
        return "f.cfp/l"
    if "f.cfp/kg" in lowered:
        return "f.cfp/kg"
    if "f.cfp/kva/an" in lowered:
        return "f.cfp/kVA/an"
    if "f.cfp/kwh" in lowered:
        return "f.cfp/kWh"
    if "f.cfp/mois" in lowered:
        return "f.cfp/mois"
    if "f.cfp" in lowered:
        return "f.cfp"
    return fallback


def _category(line: str, section: str | None) -> str:
    lowered = f"{section or ''} {line}".lower()
    if any(term in lowered for term in ("essence", "gazole", "carburant")):
        return "Fuel maximum retail tariff"
    if any(term in lowered for term in ("gaz butane", "bouteille", "vrac")):
        return "Gas maximum tariff"
    return "Electricity tariff"


class ObservatoireEnergieNcSpider(scrapy.Spider):
    name = "observatoire_energie_nc"
    allowed_domains = ["observatoire-energie.gouv.nc"]
    start_urls = ["https://observatoire-energie.gouv.nc/public/home/"]
    currency = "XPF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        date_label = _clean(response.css("#newsDatabase span.little.blue::text").get())
        raw_texts = response.css("#newsDatabase p ::text").getall()
        lines = [
            _clean(part)
            for text in raw_texts
            for part in text.splitlines()
            if _clean(part)
        ]

        period = None
        section = None
        measure = None
        measure_unit = None
        seen = set()

        for line in lines:
            lowered = line.lower()
            plain_lowered = _plain(line).lower()
            if plain_lowered.startswith("prix maximum de vente au detail des carburants"):
                period = "1er au 30 septembre 2026"
                section = "Carburants"
                measure = None
                measure_unit = None
                continue
            if plain_lowered.startswith("prix maximum de vente du gaz butane"):
                period = "1er aout au 30 septembre 2026"
                section = "Gaz butane"
                measure = None
                measure_unit = None
            if plain_lowered.startswith("tarifs de vente de l'electricite"):
                period = "1er juillet au 30 septembre 2026"
                section = "Electricite"
                measure = None
                measure_unit = None
                continue
            if plain_lowered.startswith("tarifs de la distribution"):
                measure = line
                measure_unit = None
                continue
            if plain_lowered.startswith("tarifs du transport"):
                section = "Transport electricite"
                measure = None
                measure_unit = None
                continue
            if plain_lowered.startswith("redevance pour entretien"):
                section = "Redevance compteurs"
                measure = None
                measure_unit = None
                continue

            match = _PRICE_AT_END_RE.search(line)
            if line.startswith("- ") and not any(
                term in lowered for term in ("essence", "gazole", "bouteille")
            ):
                section = line[2:].rstrip(":")
                measure = None
                measure_unit = None
                if not match:
                    continue

            if not match:
                if "f.cfp/" in lowered:
                    measure = line.rstrip(":")
                    measure_unit = _unit(line)
                continue

            label = line[: match.start()].rstrip(" :")
            label = label[2:] if label.startswith("- ") else label
            label = _ENUM_RE.sub("", label)
            price = _price(match.group(1))
            unit = _unit(line, measure_unit)
            category = _category(line, section)

            if category == "Electricity tariff":
                pieces = [section, measure, label]
                product_name = "Observatoire Energie NC - " + " - ".join(
                    piece for piece in pieces if piece
                )
            else:
                product_name = f"Observatoire Energie NC - {label}"
            if period:
                product_name = f"{product_name} ({period})"

            product_id = _slug(f"{product_name}-{unit or ''}-{price}")
            if product_id in seen:
                continue
            seen.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": category,
                "price": price,
                "price_text": line,
                "currency": self.currency,
                "available": True,
                "unit": unit or "tariff",
                "source_date_label": date_label or None,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
