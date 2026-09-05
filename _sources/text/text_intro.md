# Economic Analysis with News Sources

New analytical techniques have increased the role of non-traditional data sources for economic analysis, including text-based data. This research explores the use of text-based data from news articles, using natural language processing (NLP), to fill key data gaps on economic sentiments and prices, offering insights into relevant economic trends across the East Asia and Pacific region.

## Data Sources

The East Asia and Pacific region hosts a substantial corpus of accessible English-based content from newspapers and international news platforms, providing an opportunity to generate timely, comprehensive indicators of economic and political trends. Specifically, local news outlets from East Asia and Pacific countries, complemented by regional sources such as the Pacific Islands News Association (PINA), ABC Australia (ABC AU), and Radio New Zealand (RNZ), were selected due to their robust coverage and reliability. We used web-scraping techniques to extract articles from the selected sources, before organizing the contents into structured datasets.

### Table 1: News Sources by Country

| Country | Newspaper/Media Source | Number of Articles | From |
|---------|------------------------|--------------------|----|
| Cambodia | Kampuchea Thmey Daily | 51,765 | 2017-07-25 |
| | Khmer Times | 74,219 | 1970-01-01 |
| China | Caixin Global | 4,542 | 2010-01-05 |
| | China Daily | 11,964 | 2014-03-28 |
| | People's Daily Online | 6,725 | 2024-09-13 |
| Fiji | Fiji Sun | 64,350 | 2008-05-27 |
| | Fiji Times | 3,988 | 2025-11-06 |
| | Fiji Village | 96,931 | 2007-07-01 |
| French Polynesia | Tahiti Infos | 50,416 | 2010-03-25 |
| Indonesia | Antara | 22,098 | 2025-09-23 |
| | Detik | 86,028 | 2024-07-23 |
| | Jakarta Post | 4,142 | 2025-02-24 |
| | Kompas | 355,175 | 2013-05-30 |
| | Tempo | 79,519 | 2003-07-21 |
| Japan | Japan News | 55,350 | 2022-04-29 |
| | Japan Today | 4,500 | 2012-09-27 |
| | The Asahi Shimbun | 12,777 | 2020-04-16 |
| Lao | Kpl | 15,836 | 2014-06-13 |
| | Pasaxon | 1,243 | 2023-09-26 |
| | The Laotian Times | 9,323 | 2016-06-03 |
| Malaysia | Kosmo | 104,074 | 2020-07-10 |
| | Malay Mail | 230,735 | 2013-06-18 |
| | The Edge | 50,964 | 2014-06-30 |
| Marshall Islands | MI Journal | 4,568 | 2015-01-02 |
| Mongolia | Dnn | 13,619 | 2014-05-03 |
| | UB Post | 936 | 2016-10-08 |
| New Caledonia | Les Nouvelles Caledoniennes | 3,901 | 2023-10-19 |
| New Zealand | Bay Of Plenty Times | 9,715 | 2023-01-29 |
| | Gisborne Herald | 9,082 | 2023-03-18 |
| | New Zealand Herald | 22,886 | 2025-06-10 |
| | Northern Advocate | 9,771 | 2022-08-28 |
| | Northland Age | 9,888 | 2012-04-02 |
| | Rnz | 949 | 2026-01-07 |
| | Rotorua Daily Post | 9,737 | 2022-09-09 |
| | Waikato News | 9,741 | 2022-10-04 |
| Pacific | Australian Broadcasting Corporation (ABC AU) | 12,612 | 2003-02-19 |
| | PINA | 49,998 | 2011-11-19 |
| | Radio New Zealand (RNZ) | 1,107 | 2014-03-13 |
| Palau | Island Times | 10,166 | 2016-06-03 |
| Papua New Guinea | PNG Business News | 3,576 | 2019-05-24 |
| | Post Courier | 53,534 | 2015-12-16 |
| | Wantok | 913 | 2020-06-18 |
| Philippines | Abante | 27,968 | 2020-05-12 |
| | Asia News Network | 3,162 | 2018-04-03 |
| | Inquirer | 51,380 | 1998-10-07 |
| | Philippine Star | 1,264 | 2024-12-22 |
| Samoa | Samoa Observer | 77,815 | 2012-01-01 |
| Singapore | The Independent | 19,253 | 2013-05-23 |
| | The Straits Times | 11,546 | 2024-09-15 |
| | Today Online | 616 | 2024-04-13 |
| | Zaobao | 10,563 | 2024-11-29 |
| Solomon Islands | SIBC | 11,052 | 2013-12-14 |
| | Solomon Star | 34,371 | 2014-04-10 |
| | Solomon Times | 22,976 | 2007-04-14 |
| | The Island Sun | 10,395 | 2017-09-01 |
| South Korea | Hankyoreh | 11,387 | 2025-07-08 |
| | Joongang | 49,778 | 2023-12-12 |
| | The Korea Herald | 19,384 | 2025-05-05 |
| | The Korea Times | 95,043 | 2006-12-07 |
| | Yonhap News Agency | 4,449 | 2026-01-04 |
| Thailand | Matichon | 140,117 | 2015-12-02 |
| | Nation Thailand | 17,420 | 2024-04-22 |
| Timor Leste | Dili Weekly | 2,892 | 2011-07-05 |
| | Tatoli | 5,237 | 2019-11-25 |
| Tonga | Matangi Tonga Online | 40,560 | 1997-11-04 |
| Vanuatu | Vanuatu Daily Post | 35,752 | 2014-04-08 |
| | Vanuatu Business Review (VBR) | 577 | 2020-04-27 |
| Vietnam | Dan Tri | 1,871 | 2025-10-02 |
| | Tuoi Tre | 37,199 | 1970-01-01 |
| | Vietnam News | 39,317 | 2004-06-21 |
| | Vietnamnet | 305,280 | 2004-01-21 |
| | Vnexpress | 1,389 | 2025-12-12 |
| **Total** | | **2,723,376** | |

## Methods

### Economic Policy Uncertainty (EPU) Index

One of the most influential applications of exploiting text data in economics is the Economic Policy Uncertainty (EPU) index first developed by {cite:t}`baker2016measuring`. In the initial application, an index of policy uncertainty was constructed based on analyzing the frequency of keywords related to economics, policy, and uncertainty in news articles. The authors found periods of elevated policy uncertainty to be strongly associated with declining in investment and employment, highlighting the negative impact of uncertainty on economic decision-making.

The construction of the EPU index follows a systematic approach where a news article must meet three criteria by containing at least one keyword from economic, policy, and uncertainty categories. Once the relevant news articles are identified, the EPU index is constructed through the following steps:

### Table 2: EPU Index Keywords

| Category      | Words |
| ----------- | ----------- |
| Economic     | "economy", "economic", "economics", "business", "finance", "financial"       |
| Policy   |     "government", "governmental", "authorities", "minister", "ministry","parliament", "parliamentary", "tax", "regulation", "legislation", "central bank", "imf", "international monetary fund",  "world bank" |
| Uncertainty |     "uncertain", "uncertainty", "uncertainties", "unknown", "unstable" "unsure", "undetermined", "risky", "risk", "not certain", "non-reliable", "fluctuations", "unpredictable" |

- Let $ X_{it} = \frac{\text{EPU news in newspaper } i \text{ at time } t}{\text{All scraped news in newspaper } i \text{ at time } t} $ and pre-defined $T_1$ to be the standardization and normalization period.
- Calculate the standard deviation $\sigma_i$ for each newspaper $i$ over $T_1$.
- Standardize $X_{it}$ by dividing by $\sigma_i$ for all time $t$, resulting in $ Y_{it} = \frac{X_{it}}{\sigma_i} $
- Compute the mean of $Y_{it}$ over all newspapers in each month to obtain $ Z_t = \text{mean}(Y_{it}) \text{ at } t $
- Compute $M$, the mean value of $Z_t$ over the period $T_1$
- Normalize the EPU index by multiplying $Z_t$ by $ \left( \frac{100}{M} \right) $ for $T_1$, resulting in the normalized EPU time-series index with a mean of 100 over $T_1$.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/epu_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/epu_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="500"></iframe>
</div>

### Topic-based EPU

The EPU index can also be computed for news sources related to specific policy topics. To qualify, articles need to contain at least one keyword in each of the four criteria, namely (1) Economy, (2) Uncertainty, (3) Policy, and (4) Policy Topic - a list of terms for a specific theme (labor, inflation, climate, food security). Because the sample of articles that meet this refined criteria decreases, a topic-based EPU is constructed at the quarterly time frequency.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/epu_topics_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/epu_topics_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="675"></iframe>
</div>

### Consumer Price Index (CPI) and Inflation

Once we have obtained the EPU index for each country and period, we use the result as an input to analyze and predict price movements. To do so, we obtain the [International Monetary Fund (IMF) Consumer Price Index (CPI) data](https://data.imf.org/en/datasets/IMF.STA:CPI) and apply a three-month moving average (MA3) to smooth the volatile directly measured inflation data. Subsequently, we conduct a regression analysis using variables selected through the cross-validated LASSO method, ensuring the inclusion of relevant variables while minimizing the risk of overfitting. To further prevent overfitting brought by the high-order polynomial, we limit the lag used in the analysis to a maximum of two, meaning for the next prediction, the model can only use past three months’ inflation information.

## Results

### Country-Specific Models

We use a training set of seven countries to evaluate the performance of the country-specific models. These are China, Fiji, Indonesia, Japan, Lao, Samoa, Solomon Islands, and Tonga. At the country level, Japan achieves the lowest RMSE at 0.11, indicating that the model’s predictions deviate by approximately 0.11 percentage points from the actual inflation values. Countries with the highest accuracy are Lao, Indonesia, and Samoa, achieving accuracies of 0.95, 0.88, and 0.84, respectively. Inflation volatility and the rapid alternation between deflation and inflation amongst countries reduce prediction accuracy.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/train_predictions_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/train_predictions_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="475"></iframe>
</div>

### Pooled Model

The pooled model using MA3 achieves an accuracy of approximately 83.1 percent of the time and deviation around 0.83 percentage points from the actual inflation. This means that, based on historical data and the constructed EPU indexes, the models correctly predicted inflationary or deflationary trends more than four out of five times.

For out-of-sample validation of the pooled model, we use a set of three countries: Philippines, South Korea, and Vietnam. Philippines achieves a RMSE of 0.14 and an accuracy of 92.91%. South Korea achieves a RMSE of 0.15 and an accuracy of 84.25%, and Vietnam achieves a RMSE of 0.17 and an accuracy of 88.43%.

<div style="display:flex;justify-content:flex-start;width:950px;margin-bottom:4px;">
  <a href="../interactive/text/out_of_bag_predictions_pic.html" target="_blank" style="font-size:0.8em;padding:3px 10px;border:1px solid #667eea;border-radius:4px;color:#667eea;text-decoration:none;">&#x2197; Open in new tab</a>
</div>
<div>
<iframe src="../interactive/text/out_of_bag_predictions_pic.html"
frameborder="0" marginwidth="0" marginheight="0" width="950" height="475"></iframe>
</div>

## Future Work

Future work will involve the development of a methodology that can interpolate quarterly CPI data to monthly values, bring lagged CPI data to the same time frequency as the EPU index, and generate inflation predictions on countries with no inflation data.

### Table 3: IMF CPI Data Availability by Country

| Country Name     | ISO3   | Frequency   | Last Reported   |
|:-----------------|:-------|:------------|:----------------|
| American Samoa   | ASM    | No Data     | No Data         |
| Guam             | GUM    | No Data     | No Data         |
| Marshall Islands | MHL    | No Data     | No Data         |
| New Zealand      | NZL    | Quarterly   | 2025-Q3         |
| Palau            | PLW    | Quarterly   | 2025-Q2         |
| Papua New Guinea | PNG    | Quarterly   | 2025-Q2         |
| Thailand         | THA    | Monthly     | 2025-M03        |
| Tonga            | TON    | Monthly     | 2025-M01        |
| Tuvalu           | TUV    | Quarterly   | 2012-Q2         |
| Vanuatu          | VUT    | Quarterly   | 2023-Q4         |
| Vietnam          | VNM    | Monthly     | 2025-M03        |
