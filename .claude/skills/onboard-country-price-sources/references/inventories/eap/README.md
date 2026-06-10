# EAP price-source inventory

Pre-verified discovery seed for the `onboard-country-price-sources` skill.
One file per country; `_aggregators.md` holds cross-country aggregators + COICOP gap notes.

## Origin

I used the uploaded markdown as the specification for this inventory.

This is a **verified first-pass inventory**, not a production scraper spec. I separated **official/statistical sources** from **retailer/portal crawl candidates**. Some official CPI tables are not absolute price levels; they are still useful for inflation/nowcasting, but weaker for PPP unless paired with ICP/retailer prices. IMF CPI publishes national CPI indexes, detailed division indexes, weights, and contributions where available; World Bank ICP 2021 publishes PPPs and price-level indicators across 45 expenditure headings for 176 economies; OECD has CPI data under COICOP 1999 and COICOP 2018 where available. ([IMF Data][1])
