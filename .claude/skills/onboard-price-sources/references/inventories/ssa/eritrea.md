# Eritrea

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass)

Before this pass: 0 manifests of any kind. **Result: 0 shipped — and the one
open thread the previous pass left is now CLOSED.**

## The Asbeza thread is closed: it is Ethiopian, not Eritrean

The 2026-09-01 file's single live lead was the "Asbeza" grocery-delivery app
(`com.ecwid.ShopAt.Asbeza`), whose guessed `asbeza.com` served a parking page.
It asked for "one more WebSearch-budget pass specifically to find its real
domain before writing this off".

That search was run. The real domain is **`asbeza.net`, and Asbeza operates in
Addis Ababa, Ethiopia — not Asmara, Eritrea.** Its own about page describes it
as "Ethiopia's first grocery delivery service", delivering from stores in
Addis. The previous inventory had attributed an Ethiopian company to Eritrea.
There is no Eritrean Asbeza to find.

**Do not re-chase this lead.**

## Bonus lead for another country

`asbeza.net` (Ecwid-hosted) and `mohasbeza.com` are both live Ethiopian
grocery storefronts. Ethiopia currently sits at 5 sources / 2 food and is on
the Tier C list of the search-starved plan — these two are free candidates for
whoever runs Ethiopia next. Recorded here because this is where they were
found; they belong in `ssa/ethiopia.md` when that pass happens.

## Verdict: structural absence, now with evidence

No delivery marketplace (Jumia / Glovo / Bolt / Yango) lists Eritrea, and no
independent e-commerce domain was found for the physical Asmara grocers
(Day-To-Day Discount, Family Supermarket) that directory sites list. Combined
with Eritrea's single state-run ISP and very low internet penetration, this is
a genuine structural absence rather than a search gap — and unlike the
2026-09-01 pass, that conclusion no longer rests on an unresolved lead.

## Next steps

- None. Do not spend further discovery budget on Eritrean online retail; it
  does not exist. Revisit only if the telecom sector liberalises.
_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Eritrea had **zero** manifests of any kind before this pass (0
food, 0 total).

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Asbeza | Google Play `com.ecwid.ShopAt.Asbeza` | **DEAD — domain squatted/parked** | App listing shows it's built on Ecwid (a hosted storefront SaaS). Direct-guessed `asbeza.com` resolves but serves a domain-parking/consent-manager landing page (no product markup, no mention of Ecwid, no title) — not the real storefront. The actual Ecwid subdomain or custom domain was not found (WebSearch quota was exhausted session-wide before it could be searched properly — this is a gap to close on the next pass, not a confirmed dead end for the app itself). |
| Day-To-Day Discount, Family Supermarket (Asmara) | (no domains found) | **NOT PROBED — no web presence found** | Physical grocery stores surfaced via `evendo.com`/`goafricaonline.com` directory listings; no independent e-commerce presence found. |

No delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in Eritrea —
none of the usual pan-African aggregators list the country. This is
consistent with Eritrea's structurally isolated internet/telecom sector
(single state-run ISP, very low penetration) rather than a search gap: prior
knowledge strongly suggests there is no functioning online retail sector
inside the country. Treat as a likely **structural absence**, but the Asbeza
app is an open thread — worth one more WebSearch-budget pass specifically to
find its real domain before writing this off completely.

---

## UPDATE 2026-09-01 (second pass) — Asbeza lead CLOSED. It is ETHIOPIAN, not Eritrean.

The pass above left the Asbeza app (`com.ecwid.ShopAt.Asbeza`) as "an open thread
— worth one more WebSearch-budget pass specifically to find its real domain". That
search was run, and it resolves the thread in the negative:

**Asbeza is an Addis Ababa (Ethiopia) grocery-delivery service, not an Eritrean
one.** Its real domains are `asbeza.net` and `asbeza.et` — both live (HTTP 200,
~78 KB, Ecwid fingerprint confirmed via `curl_cffi impersonate=chrome124`), both
describing "Ethiopia's first online grocery delivery service ... in Addis Ababa",
with a Facebook page located in Addis Ababa. The earlier pass inferred Eritrea
from the app name; *asbeza* (አስቤዛ) is simply the Amharic word for groceries, and
Amharic is an Ethiopian language. The parked `asbeza.com` it probed was a
red herring unrelated to either country.

With the only open thread closed, the pass above's structural read is now the
settled verdict: **Eritrea has no online retail sector** (single state-run ISP,
minimal internet penetration, no pan-African delivery marketplace lists the
country). Treat as a **structural absence**, not a search gap. Do not re-sweep
Eritrea for grocery e-commerce.

Spillover lead for another country: `asbeza.net` is a live, unblocked Ecwid
storefront and Ecwid exposes a documented open storefront API. Ethiopia already
clears the coverage bar (5 manifests), so this is low priority — but it is a
free, verified candidate if Ethiopian food depth is ever wanted.
