# Algeria — price source inventory (menaap/north_africa)

_Inventory written: 2026-09-01_

Cold-start inventory. Final F&B sweep, MENAAP agent B. Algeria started this
pass at 3 food sources (`carrefour_dz` hypermarket, `coursesnet_dz`
supermarket, `superette_dz` supermarket) plus 4 pharmacy sources, out of 8
total. **No new food-and-beverage source was found this pass** — see dead
ends below. No WebSearch budget available this pass (session-wide cap
already exhausted by other parallel agents), so discovery was limited to
direct domain guesses off known Algerian retail/hypermarket brand names.

## Onboarded this pass

None.

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Numidis / Uno hypermarket | numidis.dz | DEAD — DNS leaks a private IP | `numidis.dz` resolves to `10.10.61.2` (RFC1918 private address) via public DNS (`8.8.8.8`) — genuinely unreachable from the internet, not a WAF or timeout. `www.numidis.dz` HTTPS also hard-times-out (30s+, no handshake). Numidis Group runs the "Uno" hypermarket chain, Algeria's #2 grocery brand after Carrefour — a real gap, but this domain cannot be reached. |
| Ardis (guessed Numidis-family name) | ardis.dz | DEAD — SERVFAIL | DNS SERVFAIL against 8.8.8.8; `ardis-dz.com` NXDOMAIN. No resolvable domain. |
| Uno (short-name guess) | uno.dz | DEAD — wrong site (domain squat) | Resolves 200 but serves Booking.com's own front-end (`og:site_name`/OG namespace = `booking_com`, `b_chrome` CSS classes) — an unrelated domain squat, not the Algerian hypermarket. |
| myshop.dz | myshop.dz | Non-actionable — store-builder SaaS, not a retailer | "Lance ta boutique en ligne en Algerie... Bientot disponible" (coming soon) — a Shopify-style store-builder platform, not itself a grocery retailer. |
| Jumia Algeria | jumia.dz | DEAD — Cloudflare (shared Jumia-tenant signature) | Same Cloudflare "Just a moment" wall as jumia.ma/jumia.bf/jumia.sl already in `known_blockers.md` — the fourth Jumia storefront to show this identical signature. Not re-probed with the full 3-profile+Playwright gate this pass (budget went to more promising Tunisia/Pakistan/Egypt leads). |
| Condor.dz | condor.dz | Off-topic — electronics, not food | Real, live site (Condor is a major Algerian electronics/appliance manufacturer-retailer) but not a grocery/food channel at all. Not pursued. |
| Ouedkniss | ouedkniss.com | Off-topic — general classifieds | Algeria's largest classifieds site (cars, real estate, electronics, jobs) — not a grocery-delivery marketplace and has no obvious seller directory for food retailers. Not pursued as a marketplace-directory candidate. |

## Dead ends worth remembering

- **A DNS resolution to a private/RFC1918 address is a distinct failure mode from NXDOMAIN, SERVFAIL, or a timeout — check for it explicitly.** `numidis.dz` looked like a plain connection timeout at the HTTP layer, but `dig`-ing it directly revealed the domain's own public DNS record points at `10.10.61.2`, meaning the operator's own infrastructure (perhaps an internal-only deployment, or a stale record) is unreachable from outside their network. No amount of TLS-profile cycling fixes this.
- **The obvious short-name domain guess for a well-known brand can be an unrelated squat, not a parked/expired page.** `uno.dz` returning a live 200 with real (but wrong) content — Booking.com's own assets — is a different, sneakier failure mode than the usual "parking lander" pattern; worth checking `og:site_name`/title before assuming a 200 means you found the target.
- **Without a fresh WebSearch budget, direct brand-name domain guessing off Algeria's known chain names (Numidis/Uno, Ardis, Family Store, Cevital-adjacent retail) hit a wall quickly** — none of the guessed domains for chains other than the already-covered Carrefour/coursesnet/superette resolved to a live, reachable, food-relevant storefront. A future pass with search budget should prioritize Algeria — it is the largest remaining MENAAP food gap on this sweep's worklist (3/8) with genuine untried candidates (Family Store, a Numidis storefront under a different domain, wholesale/fresh-market feeds) not yet exhausted, just not reachable via guessing alone.
