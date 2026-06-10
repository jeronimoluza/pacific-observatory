# EAP multi-country sources and COICOP coverage gaps

## Multi-country sources

| Source                                             |                                               Countries in panel | COICOP coverage                                                 | Cadence                              | Usefulness                                | Notes                                                                                                       |
| -------------------------------------------------- | ---------------------------------------------------------------: | --------------------------------------------------------------- | ------------------------------------ | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| World Bank ICP 2021                                |             Broad country coverage; many but not all territories | PPPs, price-level indices, 45 expenditure headings              | Benchmark cycle, plus extrapolations | Very high for PPP baseline                | Best harmonized PPP source; not current monthly prices. ([World Bank][41])                                  |
| IMF CPI dataset                                    |                                             Many panel economies | CPI all-items, divisions where available, weights/contributions | Monthly/quarterly                    | High for inflation, weak for price levels | Not SKU-level; good harmonized index source. ([IMF Data][1])                                                |
| OECD CPI database                                  | Australia, New Zealand, Japan, South Korea; maybe partner series | COICOP 1999 and COICOP 2018 where available                     | Monthly/quarterly                    | High for comparable CPI                   | Better for advanced economies. ([OECD][42])                                                                 |
| ADB ICP / Key Indicators                           |                                           Asia-Pacific economies | ICP PPPs, CPI/inflation                                         | Annual/benchmark                     | High for EAP PPP context                  | ADB covers Asia-Pacific ICP component. ([Asian Development Bank][43])                                       |
| Pacific Data Hub / SPC / PRISM                     |                         Pacific Island countries and territories | CPI/inflation datasets                                          | Annual/monthly depending source      | High for Pacific CPI backfill             | Pacific Data Hub has CSV economy datasets including CPI/inflation. ([pacificdata.org][44])                  |
| ASEANstats                                         |                                                  ASEAN countries | Inflation/CPI indicators                                        | Annual/monthly depending table       | Medium                                    | API/XLS endpoints available; less granular than NSO sources. ([data.aseanstats.org][45])                    |
| WFP/HDX food prices                                |                    Selected Southeast Asia and Pacific countries | 01 food staples                                                 | Monthly/daily depending country      | High for food PPP/inflation               | Not full COICOP; good fallback for food. Indonesia example uses BPS/PIHPS sources. ([data.humdata.org][46]) |
| Shopee / Lazada regional storefronts               |   Indonesia, Malaysia, Philippines, Singapore, Thailand, Vietnam | 03, 05, 06, 08, 09, 13; some 01/02                              | Daily                                | High but anti-bot heavy                   | Strong SKU IDs; requires careful crawling/ToS review.                                                       |
| Watsons / Guardian regional                        |           HK, Singapore, Malaysia, Philippines, Thailand, Taiwan | 06 OTC health, 13 personal care                                 | Daily                                | High for pharmacy/personal care           | Country storefronts are comparable but anti-bot varies.                                                     |
| GrabFood / foodpanda / Deliveroo                   |                                    Many SEA/HK/Singapore markets | 11 restaurant meals                                             | Daily                                | High but anti-bot/API risk                | Often app/API gated; use only where public web menus load.                                                  |
| Booking / Agoda                                    |                              Most countries with tourism markets | 11 accommodation                                                | Daily                                | Medium                                    | Global source, not national; good for city hotel rates, poor for domestic representativeness.               |
| Netflix / Spotify / Apple / Google country pricing |                                       Most countries/territories | 09 recreation/digital services                                  | Annual/irregular                     | Medium                                    | Good standardized digital-service item; some territories inherit US/French/Australian pricing.              |

## COICOP coverage gaps

This gap table lists countries where I did **not** find a strong **country-specific, public, machine-readable price-level source** for that division in this pass. I exclude pure CPI-index coverage from "price-level source" unless the source also publishes average prices.

| COICOP division                                                      | Countries with material gaps                                                                                                                                      |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 01 Food and non-alcoholic beverages                                  | North Korea; Kiribati, Marshall Islands, FSM, Nauru, Palau, Tuvalu, CNMI, Timor-Leste have no strong public SKU-level supermarket source; CPI only in many cases. |
| 02 Alcoholic beverages, tobacco and narcotics                        | North Korea; Brunei alcohol mostly not applicable/public; most Pacific microstates lack SKU-level alcohol/tobacco sources beyond CPI.                             |
| 03 Clothing and footwear                                             | North Korea; most Pacific microstates; Lao PDR and Timor-Leste weak; official CPI only.                                                                           |
| 04 Housing, water, electricity, gas and other fuels                  | North Korea; housing/rent listing gaps in most Pacific microstates; utilities usually available but not always machine-readable.                                  |
| 05 Furnishings, household equipment and maintenance                  | North Korea; most Pacific microstates; Lao PDR/Timor-Leste weak outside small retail candidates.                                                                  |
| 06 Health                                                            | North Korea; most Pacific microstates; Lao PDR/Timor-Leste weak; Cambodia/Myanmar depend on pharmacy/e-commerce validation.                                       |
| 07 Transport                                                         | North Korea; Pacific microstates often have fuel/utility data but weak public transport/vehicle price data; Timor-Leste weak.                                     |
| 08 Information and communication                                     | North Korea; otherwise many countries have telco tariff pages, but machine-readable structure varies.                                                             |
| 09 Recreation, sport and culture                                     | North Korea; most Pacific microstates; Lao PDR/Timor-Leste weak; often only digital subscriptions or e-commerce proxies.                                          |
| 10 Education services                                                | North Korea; most Pacific microstates; many countries have university tuition pages but not centralized machine-readable datasets.                                |
| 11 Restaurants and accommodation services                            | North Korea; most Pacific microstates; Lao PDR/Timor-Leste weak; food-delivery/hotel portals exist but are often global, JS-heavy, or anti-bot.                   |
| 12 Insurance and financial services                                  | North Korea; almost all Pacific microstates; Lao PDR, Myanmar, Timor-Leste weak. Bank fee PDFs exist in larger markets but insurance quote comparability is poor. |
| 13 Personal care, social protection and miscellaneous goods/services | North Korea; most Pacific microstates; Lao PDR/Timor-Leste weak; larger markets covered by pharmacies/supermarkets/e-commerce.                                    |

[1]: https://data.imf.org/en/datasets/IMF.STA%3ACPI "CPI - IMF Data - International Monetary Fund"
[2]: https://www.stats.gov.cn/english/PressRelease/202504/t20250414_1959290.html "Consumer Price Index for March 2025"
[3]: https://www.censtatd.gov.hk/en/scode270.html "C&SD : Consumer Prices"
[4]: https://www.stat.go.jp/english/data/kouri/index.html "Retail Price Survey - Statistics Bureau"
[5]: https://www.e-stat.go.jp/en/stat-search/files?stat_infid=000040315794 "Consumer Price Index 18 COICOP Group Index for Japan ..."
[6]: https://www.dsec.gov.mo/en-US/Statistic?id=1 "Statistics -- Statistics and Census Service"
[7]: https://dsbb.imf.org/sdds/dqaf-base/country/MNG/category/CPI00 "DQAF View : Mongolia - Price index: consumer prices - SDDS"
[8]: https://kosis.kr/eng/ "KOSIS KOrean Statistical Information Service"
[9]: https://www.oilpriceapi.com/gasoline-prices/asia/south-korea "South Korea Gasoline Prices | Petrol Price Today"
[10]: https://eng.dgbas.gov.tw/News_Content.aspx?n=4438&s=234870 "The Price Indices for April 2025"
[11]: https://www.doc.as.gov/resource-center "Resource Center | ASDOC"
[12]: https://www.aspower.com/rates.html "Billing Rates"
[13]: https://www.eia.gov/states/AQ/overview "US Energy Information Administration - American Samoa"
[14]: https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release "Consumer Price Index, Australia, March 2026"
[15]: https://www.statsfiji.gov.fj/statistics/economic-statistics/prices/ "Consumer Price Index"
[16]: https://pcreee.org/publication/fiji-wholesale-and-retail-fuel-prices-2026 "Fiji Wholesale and Retail Fuel Prices 2026"
[17]: https://bsp.guam.gov/cpi/ "CPI - The Bureau of Statistics and Plans Guam"
[18]: https://nso.gov.ki/statistics/economy/cpi/ "Consumer Price Index"
[19]: https://rmi-data.sprep.org/dataset/consumer-price-index "Consumer Price Index | Republic of the Marshall Islands ..."
[20]: https://stats.gov.fm/topics/economic-statistics/consumer-price-index/ "Consumer Price Index"
[21]: https://stats.gov.nr/category/statistics/economic-statistics/ "Economic Statistics"
[22]: https://tradingeconomics.com/new-caledonia/consumer-price-index-cpi "New Caledonia Consumer Price Index Cpi"
[23]: https://www.stats.govt.nz/topics/food-price-index/ "Food price index"
[24]: https://www.palaugov.pw/executive-branch/ministries/finance/budgetandplanning/consumer-price-index-cpi/ "Consumer Price Index (CPI) – PalauGov.pw"
[25]: https://www.nso.gov.pg/statistics/economy/consumer-price-index/ "Consumer Price Index | National Statistical Office"
[26]: https://www.sbs.gov.ws/cpi/ "Consumer Price Index"
[27]: https://statistics.gov.sb/category/statistics/economic-statistics/consumer-price-index/ "Consumer Price Index"
[28]: https://tongastats.gov.to/statistics/economics/consumer-price-index/ "Consumer Price Index"
[29]: https://stats.gov.tv/category/economics/consumer-price-index/ "Consumer Price Index"
[30]: https://vbos.gov.vu/ "Vanuatu Bureau of Statistics"
[31]: https://deps.mofe.gov.bn/wp-content/uploads/2026/01/Yearly-Consumer-Price-Index.xlsx "Yearly - Department of Economic Planning and Statistics"
[32]: https://nis.gov.kh/en/consumer-price-index/ "Consumer Price Index"
[33]: https://www.bi.go.id/hargapangan "PIHPS"
[34]: https://laosis.lsb.gov.la/majorIndicators.do "Major Indicators - Lao Statistics Bureau"
[35]: https://open.dosm.gov.my/data-catalogue/pricecatcher "PriceCatcher: Transactional Records - OpenDOSM"
[36]: https://www.csostat.gov.mm/MonthlyPublication/PriceAnalysis "Prices | Analysis"
[37]: https://www.dti.gov.ph/konsyumer/e-presyo/ "e-Presyo."
[38]: https://www.singstat.gov.sg/find-data/explore-data-themes/economy-prices/consumer-price-index/our-data-explained "Our Data Explained - Consumer Price Index"
[39]: https://data.gov.sg/datasets "data.gov.sg"
[40]: https://www.nso.gov.vn/en/cpi/ "CPI – National Statistics Office of Vietnam"
[41]: https://www.worldbank.org/en/programs/icp "International Comparison Program (ICP)"
[42]: https://www.oecd.org/en/data/insights/data-explainers/2024/07/consumer-price-indices-frequently-asked-questions-faqs.html "Consumer Price Indices: Frequently Asked Questions (FAQs)"
[43]: https://www.adb.org/what-we-do/data/icp "International Comparison Program (ICP) for Asia and the Pacific"
[44]: https://pacificdata.org/data/dataset/ "Dataset"
[45]: https://data.aseanstats.org/api/indicator/detail/AST.STC.TBL.8/0 "ASEANstats"
[46]: https://data.humdata.org/dataset/wfp-food-prices-for-indonesia "Indonesia - Food Prices | Humanitarian Dataset | HDX"
