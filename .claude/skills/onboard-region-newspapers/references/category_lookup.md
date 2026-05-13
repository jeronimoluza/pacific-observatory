# WordPress Category Lookup

The category filter rule (national → economy/politics → latest fallback) is the most important quality lever for these scrapers. Get the IDs right and you get on-topic articles; get them wrong and you'll capture sports/lifestyle noise.

## How to look up category IDs

Every WP site exposes its category list at:

```
<base_url>/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug,count
```

Returns an array of:
```json
[
  {"id": 6, "name": "News", "slug": "news", "count": 2762},
  {"id": 12, "name": "Business", "slug": "business", "count": 25567},
  ...
]
```

Use a one-liner to inspect the most-populated categories:

```bash
curl -sL --max-time 8 -A "Mozilla/5.0" \
  "<base>/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug,count" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for c in sorted(d, key=lambda x: -x.get('count', 0))[:15]:
    print(f'  id={c[\"id\"]:>5}  count={c[\"count\"]:>6}  slug={c[\"slug\"]:<24}  name={c[\"name\"]}')"
```

For sites with `?rest_route=` form (Lesotho Times pattern):

```
<base>/?rest_route=/wp/v2/categories&per_page=100&_fields=id,name,slug,count
```

## Selection rule

Pick category IDs in this priority order, including up to 5 IDs total:

1. **National news** — slugs like `news`, `national`, `local-news`, `<country>-news`, `top-stories`, `headlines`
2. **Economy/business** — slugs like `economy`, `business`, `markets`, `finance`, `economic-news`, `companies`
3. **Politics/government** — slugs like `politics`, `government`, `political`, `elections`
4. **Latest/general** (fallback only if 1-3 produce <2 IDs) — `latest`, `general`, `actualites`, `a-la-une`

**Skip these** even if they have high counts:
- `sport`, `sports`, `local-sports`, `world-soccer`, `cricket`, `rugby`, `pst`, `goal-diggers`
- `entertainment`, `lifestyle`, `arts`, `arts-culture`, `celebs`, `music`, `showbiz`, `culture`
- `epaper`, `e-paper`, `newsletter`, `cartoons`, `weekly-cartoon`
- `world`, `africa`, `international`, `news-world` (off-country, dilutes signal)
- `opinion`, `opinions`, `editorials`, `columnists`, `thought-leader` (commentary, not reporting)
- `crime` (relevant but tends to dominate; include only if no national category)
- `motoring`, `health`, `agriculture`, `mining`, `technology` (vertical, not core EPU signal)

## Multi-language site shortcuts

Categories named in the source language follow the same selection rule:

| Language | National | Economy | Politics | Latest |
|---|---|---|---|---|
| French | `national`, `actualité`, `actualites`, `a-la-une`, `infos` | `economie`, `economy`, `affaires` | `politique` | `actualites`, `a-la-une`, `dernieres-news` |
| Portuguese | `nacional`, `noticias` | `economia`, `negocios` | `politica` | `ultimas`, `a-nao-perder` |
| Spanish | `nacional`, `noticias` | `economia`, `negocios` | `politica` | `ultimas`, `actualidad` |
| Arabic | `محليات`, `اخبار` (transliterated slugs vary) | `اقتصاد`, `economy` | `سياسة` | `أخبار`, `latest` |
| Swahili | `habari`, `taifa` | `uchumi`, `biashara` | `siasa` | `habari` |

When in doubt, sort categories by `count` and pick the top non-blacklisted ones.

## Encoding multiple categories in the URL template

WordPress accepts comma-separated IDs:

```yaml
url_template: "https://example.com/wp-json/wp/v2/posts?per_page=100&page={page}&categories=3,12,23"
```

Order doesn't matter for filtering but matters for URL hashing on some CDNs — keep IDs in numeric order to maximize cache hits if you re-run.

## Sanity check before committing

After picking IDs, verify with a quick curl:

```bash
curl -sL --max-time 8 -A "Mozilla/5.0" \
  "<base>/wp-json/wp/v2/posts?per_page=3&categories=<your-IDs>&_fields=id,date,link,title" \
  | python3 -m json.tool | head -20
```

You should see 3 posts with on-topic-looking titles. If you see lifestyle/sports/etc. content, recheck your IDs against the category list.

## Examples from prior runs (battle-tested)

For reuse / cross-checking when onboarding a similar site:

| Source | URL | Categories used | Reason |
|---|---|---|---|
| Mail & Guardian SA | mg.co.za | `3,12,23` | National(162k), Business(25k), Politics(4k) |
| The Citizen SA | citizen.co.za | `131,111,76912,135961` | South Africa(35k), News(28k), Business(12k), Politics(12k) |
| Sunday Standard BW | sundaystandard.info | `5,6,20,24,27` | News(10k), Business(7k), Politics(122), Government(89), Economy(56) |
| Premium Times NG | premiumtimesng.com | `3,60` | News(17k), Headlines(31k) — drop `_fields` to avoid CDN block |
| ThisDay NG | thisdaylive.com | `1,7568` | Nigeria(190k), Business(59k) |
| BusinessDay NG | businessday.ng | `1046,1023,1007` | Companies(20k), Economy(8k), Analysis(6k) |
| MyJoyOnline GH | myjoyonline.com | `17,101,2,4` | News(190k), National(148k), Business(44k), Economy(29k) |
| Lesotho Times | lestimes.com (rest_route form) | `3,15,6` | News(10k), Local News(8k), Business(1k) |
| The Namibian | namibian.com.na | `6,157,2675` | News(2.7k), National(1.4k), Economic news(100) |
| News Diggers ZM | diggers.news | `1,5,10` | Local(27k), Business(5k), Courts(4k) |
| ZimEye | zimeye.net | `1,5` | National(118k), Business(4.7k) |
| Le Quotidien SN | lequotidien.sn | `53,60` | Actualités(18k), Economie(6k) |

These IDs are stable for the foreseeable future — copy directly if you're re-running these sources, but always re-fetch for new sources.
