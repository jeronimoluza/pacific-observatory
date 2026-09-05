I'm building a fuel price monitoring pipeline that scrapes structured retail fuel price data
from government and state-enterprise sources across countries. I already cover East Asia &
Pacific. Now I need to find equivalent sources for:

**MENA + Afghanistan & Pakistan:**
Saudi Arabia, UAE, Kuwait, Qatar, Bahrain, Oman, Iraq, Iran, Jordan, Lebanon, Egypt,
Libya, Tunisia, Algeria, Morocco, Yemen, Syria, Afghanistan, Pakistan, Turkey, Israel,
Djibouti, West Bank & Gaza

For EACH country, I need you to find 1-3 sources of **retail fuel pump prices**
(gasoline, diesel, LPG/kerosene where available) that meet these criteria:

1. **Structured or semi-structured data** -- any of:
   - HTML tables on a government or state oil company website
   - Downloadable CSV / Excel / PDF files
   - REST API or JSON endpoint
   - PDF bulletins with tabular layout (parseable with pdfplumber or Tesseract OCR)
   - Image-based price announcements (parseable with Tesseract OCR)

2. **Official or semi-official sources preferred**, in this priority order:
   a. Energy ministry / petroleum authority / national statistics office
   b. State-owned oil company (e.g. ADNOC, Saudi Aramco, SONATRACH, PSO Pakistan)
   c. Price regulation body or consumer protection authority
   d. Reputable private aggregator (last resort)

3. **NOT GlobalPetrolPrices.com** -- I already have that as a fallback; I need primary sources.

4. For each source, provide:
   - **Country**
   - **Source name** (agency or company)
   - **URL** (the actual page or endpoint, not just the homepage)
   - **Data format** (HTML table, PDF, Excel, API/JSON, image+OCR, etc.)
   - **Update frequency** (daily, weekly, biweekly, monthly, quarterly)
   - **Products covered** (gasoline grades, diesel, LPG, kerosene)
   - **Language** (English, Arabic, Farsi, etc.) and whether an English version exists
   - **Scraping difficulty** (Easy / Medium / Hard) with brief justification
   - **Notes** (authentication required? Cloudflare? CAPTCHA? known quirks?)

For reference, here are the types of sources I already scrape successfully for EAP countries
(so you know what's feasible):

| Pattern | Example |
|---------|---------|
| Government CSV/Excel download | NZ MBIE weekly-table.csv, Australia AIP Excel |
| HTML table on ministry site | Lao State Fuel Company, Cambodia PTT |
| REST API (JSON) | Singapore SingStat, Mongolia NSO, Indonesia OTO |
| PDF bulletins parsed with pdfplumber | Fiji FCCC quarterly PDFs, Philippines DOE |
| Image-based price notices + Tesseract OCR | Tonga MTED (scanned PDF), Vietnam Petrolimex (JPG) |
| Playwright for JS-heavy sites | Japan ANRE, Myanmar Denko, Thailand Bangchak |
| Press-release scraping (text parsing) | Malaysia MOF, Australia ACCC quarterly reports |
| SOAP API | Thailand OR/PTTOR oil price service |
| WordPress REST API | Timor-Leste ANP daily fuel price |

Present your findings as a table grouped by country, then add a "Quick Wins" section
listing the 5-8 easiest sources to implement first (high structure, no auth, English or
simple HTML). Also flag any countries where prices are fully deregulated with no
centralized reporting -- I still want to know, but with a note that only private
aggregators may exist.

For subsidized/controlled-price countries (Saudi Arabia, Kuwait, Qatar, Bahrain, Oman,
UAE, Iran, Iraq, Algeria, Libya, Egypt), note whether prices change infrequently
(monthly/quarterly government decrees) -- these are still valuable even if updates are rare.
