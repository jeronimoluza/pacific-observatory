"""
CaribeShop DM (Dominica) -- the CaribeEats-operated general-goods storefront
for Roseau (backend.caribeeats.com/api/business/caribeshop-dm).

The largest catalogue on any platform serving Dominica: 6,206 SKUs across 15
categories, verified live 2026-09-05.

Deliberately NOT food-led, and onboarded anyway. The 2026-09-01 pass probed
this business and rejected it for an F&B-scoped sweep because "Foods &
Beverages" is only 483 of 6,206 rows (~8%) against Personal Care (3,544),
OTC (825), Beauty & Health (365), Household (341). That rejection was
correct for a sweep whose bar was "food-LED". It is the wrong call for a
division-01/02 coverage brief in a country that has six division-01/02
leaves in total: 483 genuine grocery SKUs at Dominican shelf prices is real
division-01 coverage, and the remaining 5,700 rows are real division-05/06/12
coverage that Dominica has none of either. `channel: marketplace` records
what it actually is rather than dressing it up as a supermarket.

Currency: the payload reports USD (its Roseau sibling `island-liquor-dominica`
reports XCD). Left to the payload, as the shared base does -- the same
USD-vs-XCD split was independently confirmed as REAL, not a platform bug, on
the St Kitts / Nevis businesses this pass (median price ratio against an
XCD sibling's shared SKUs came out at 1/2.70, the exact peg).
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class CaribeshopDmSpider(CaribeEatsBaseSpider):
    name = "caribeshop_dm"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "caribeshop-dm"
