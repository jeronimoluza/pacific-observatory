## Data

The project relies on a harmonized dataset of consumer prices collected from online supermarkets across multiple countries. Data are obtained through systematic web scraping of retailer websites, following category hierarchies down to individual product pages. The resulting dataset captures posted retail prices at high frequency and is designed to support cross-country and over-time price analysis.

Number of price observations (registers) and unique products per country and data source.

| Country          | Source/Supermarket   |   Number of Registers |   Number of Unique Products |
|:-----------------|:---------------------|----------------------:|----------------------------:|
| Australia        | ALDI Australia       |                 24925 |                        5292 |
| Fiji             | MH Online            |                 22018 |                        3918 |
| Fiji             | RB Patel             |                  4513 |                         588 |
| Papua New Guinea | FoodPro              |                  2174 |                         162 |
| Samoa            | Samoa Market         |                  2892 |                         305 |
| Tonga            | Molisi               |                  1526 |                         346 |
| Vanuatu          | Dynamic Vanuatu      |                  8731 |                        1209 |

The unit of observation is a **product–store–date** price. For each observation, the dataset includes the product name, posted price, retailer-provided category (when available), and the timestamp of data collection. Prices are collected on a weekly basis, and each product URL is additionally queried against the Internet Archive’s Wayback Machine to retrieve historical price observations when available. This approach allows partial reconstruction of past price trajectories and increases temporal coverage beyond the start date of live scraping.

Historical data coverage through Internet Archive's Wayback Machine, showing when scraping started and temporal depth.

| Country          | Source/Supermarket   | Date Scraping Initiated   |   Items with Wayback Data |   Months of Data (with Wayback) |
|:-----------------|:---------------------|:--------------------------|--------------------------:|--------------------------------:|
| Australia        | ALDI Australia       | 2025-11-19                |                      1427 |                              10 |
| Fiji             | MH Online            | 2025-11-05                |                      1712 |                              53 |
| Fiji             | RB Patel             | 2025-11-14                |                       373 |                              44 |
| Papua New Guinea | FoodPro              | 2025-11-10                |                       133 |                              28 |
| Samoa            | Samoa Market         | 2025-11-18                |                       235 |                              24 |
| Tonga            | Molisi               | 2025-11-13                |                       105 |                               8 |
| Vanuatu          | Dynamic Vanuatu      | 2025-11-18                |                         0 |                               3 |

Raw prices are not directly comparable across products due to differences in package sizes, bundle offers, and units of measurement. To address this, all prices are standardized into **unit values** (e.g. price per kilogram, liter, or other relevant base unit). Quantity and packaging information is parsed from product descriptions and used to compute comparable unit prices. These standardized unit values form the basis for all subsequent price analysis and index construction.

Examples showing how raw prices are converted to standardized unit values for comparability.

| Product Name                                   |   Price | Amount   |   Units |   Unit Value |
|:-----------------------------------------------|--------:|:---------|--------:|-------------:|
| Gourmet Boerewors Sausage 500G                 |  nan    | 500 g    |       1 |      40      |
| Protein Oat Bars Choc Chip Coconut 5 Pack 200G |  nan    | 200 g    |       5 |       4.49   |
| Premium Foods Noodles Thin 250G                |    2.89 | 250 g    |       1 |      11.56   |
| Island Sun Rice 40Lb Green Bag                 |  nan    | 40 lb    |       1 |       2.7905 |
| Peking Duck Breast 380G                        |  nan    | 380 g    |       1 |      31.5526 |

Products are assigned to consumption categories using an LLM-assisted classification process aligned with the COICOP framework. Classification inputs include product names and retailer categories where available. This enables aggregation of prices across products and retailers and supports the construction of price indices at different levels of consumption classification.

Examples of product classification using the COICOP (Classification of Individual Consumption by Purpose) framework.


### COICOP Classification Examples

Examples of product classification using the COICOP (Classification of Individual Consumption by Purpose) framework.

| Product Name                                        | COICOP Code (Level 1) | COICOP Title (Level 1)                     | COICOP Code (Level 4) | COICOP Title (Level 4)                                    |
|:---------------------------------------------------|----------------------:|:-------------------------------------------|:----------------------|:----------------------------------------------------------|
| Export Gold Can 330Ml                               |                    02 | Alcoholic beverages, tobacco and narcotics | 02.1.3.0              | Beer (ND)                                                 |
| Yellowfin Tuna Chunks With Triple Chilli In Oil 95G |                    01 | Food and non-alcoholic beverages           | 01.1.3.3              | Fish preparations (ND)                                    |
| Nestle Milo Nuggets 25G                             |                    01 | Food and non-alcoholic beverages           | 01.1.8.5              | Chocolate, cocoa and cocoa-based food products (ND)       |
| Limoncello Spritz Mixer                             |                    02 | Alcoholic beverages, tobacco and narcotics | 02.1.9.0              | Other alcoholic beverages (ND)                            |
| Tang Litro Strawberry 25G                           |                    01 | Food and non-alcoholic beverages           | 01.2.1.0              | Fruit and vegetable juices (ND)                           |

Number of unique products per consumption category (COICOP Level 1) across countries.

| Total | COICOP Code (Level 1) | COICOP Title (Level 1)                                             | Australia | Fiji | Papua New Guinea | Samoa | Tonga | Vanuatu |
|------:|----------------------:|:-------------------------------------------------------------------|----------:|-----:|-----------------:|------:|------:|--------:|
|  8137 |                    01 | Food and non-alcoholic beverages                                   |      3580 | 2796 |              162 |   221 |   301 |    1077 |
|  1209 |                    13 | Personal care, social protection and miscellaneous goods and services |       300 |  788 |                0 |    45 |    44 |      32 |
|  1142 |                    05 | Furnishings, household equipment and routine household maintenance |       523 |  525 |                0 |    30 |     1 |      63 |
|   542 |                    09 | Recreation, sport and culture                                      |       427 |  110 |                0 |     4 |     0 |       1 |
|   395 |                    02 | Alcoholic beverages, tobacco and narcotics                         |       217 |  141 |                0 |     3 |     0 |      34 |
|   157 |                    06 | Health                                                              |        76 |   79 |                0 |     2 |     0 |       0 |
|   130 |                    03 | Clothing and footwear                                              |       128 |    2 |                0 |     0 |     0 |       0 |
|    73 |                    08 | Information and communication                                      |        26 |   47 |                0 |     0 |     0 |       0 |
|    24 |                    07 | Transport                                                          |        14 |   10 |                0 |     0 |     0 |       0 |
|     9 |                    04 | Housing, water, electricity, gas and other fuels                   |         1 |    8 |                0 |     0 |     0 |       0 |
|     2 |                    12 | Insurance and financial services                                   |         0 |    0 |                0 |     0 |     0 |       2 |
