# Reply to client — Mission route exposure & API contract

Thank you for the detailed follow-up. We agree with the intended outcome:

**The exposure shown to the user must price the same route and wager instructions the engine will actually authorize and execute.**

The formulas previously shared correctly describe **what the API returns today**. They do **not** yet fully satisfy the Mission-mode contract you described. Below is our point-by-point response and proposed next step.

---

## Current state

### Entertainment / current next-route cards

Today’s `exposure_pct` / `risk_pct` cards are priced from the **static Entertainment zone map**, using the quoted ladder or the budget-derived Risk Unit ladder (BASE 0.40 / PRESS 1.00 / MAX 1.40 of budget÷100).

That path is valid for **Entertainment-style pocket routes** (`early` / `mid` / `deep` / `extreme_deep`). It is **not** the Mission engine’s final safety-adjusted regional wager map.

### Mission engine (partially available, separate surface)

When the mission engine is enabled, the API already exposes decision fields such as:

- continuation / Hard Exit authority
- planned vs live wager authority
- bridge state
- per-spin `posture` / `next_bet_amount`

It does **not** yet return a full per-click regional wager map on the next-route cards, nor Mission-priced exposure calculated from that map.

---

## Point-by-point response

### 1. Mode / source for these cards

| Mode | Today | Agreed direction |
|---|---|---|
| Entertainment | Cards use the Entertainment map | Keep Entertainment calculations tied to Entertainment guidance |
| Mission | Cards are **not** yet priced from Mission decision output | When Mission is the active source, cards must use Mission decision output |

### 2. Mission exposure numerator

**Today:** not implemented as “sum of authorized Mission dollars through the endpoint.”

**Agreed target** for Mission mode:

- **Total Planned Route Wager** = sum of the actual dollar wager on every authorized click from the start of the next play through that option’s last playable click, including:
  - BELOW BASE bridge wagers
  - BASE / PRESS / MAX regions
  - authorized pre-entry / re-arm
  - approved extra clicks
  - after active safety reductions / ceilings
- Exclude first-click-not-played, unsupported extensions, and safety-prohibited wagers

Then:

- **Planned Budget Exposure (%)** = Total Planned Route Wager ÷ Selected Budget × 100  
- **Planned Balance Exposure (%)** = Total Planned Route Wager ÷ Current Available Balance × 100  

**Selected Budget:** we will lock this in the contract as the budget shown/confirmed for that next-play quote (not a silent mix of session vs next-play). We recommend defining it as the **confirmed next-play / quoted budget** when present, otherwise `session_budget`.

### 3. “Risk” label

Agreed. The current calculation is **not** probability of loss or chance of reaching an endpoint without a hit.

- Display / contract label should be **Planned Balance Exposure**
- Suggested explanatory text you provided is appropriate
- Historical occurrence percentages, if shown separately, keep their own labels, matching criteria, and sample sizes

### 4. Authorized route boundaries

- Fixed ranges **1–18 / 1–33 / 1–54 / 1–70** may remain **Entertainment presets**
- They must **not** replace Mission qualified targets or dynamic Hard Exit

For Mission mode (agreed; **requires backend work**):

- Generate options from the current qualified target queue
- Show each option’s actual endpoint
- Cost Click 1 through that endpoint
- Preserve bridge and regional wager differences
- Do not offer an option beyond continuation authority
- If no qualified route remains, show Hard Exit — not a selectable continuation
- Selecting a deeper option must not invent permission to continue farther or raise wagers

### 5. BELOW BASE and posture substitution

**Already in execution today (partial):**

- BELOW BASE executes only when amount is confirmed **and** `below_base` is in `active_postures`; otherwise spins execute BASE
- Nearest-active posture substitution exists for ladder resolution on the Entertainment map path

**Still required for the Mission cost/exposure contract:**

- Include BELOW BASE bridge dollars in the **route cost / exposure** payload
- Document substitution so it never:
  - raises above the region’s final authorized ceiling
  - converts a bridge into PRESS or MAX
  - restores aggression prohibited by safety
- If no compatible wager is available → request valid setup or block progression; do **not** silently substitute a higher wager

### 6. Quote vs confirmed ladder

**Today:** `reference.source` is only `session_budget` or `quoted_bets` — not a full confirmed/preliminary flag.

**Agreed:**

- Exposure must use the same dollar ladder that will execute
- Unconfirmed figures labeled **preliminary**
- Recalculate after the user confirms or changes wagers, and before Begin Play
- RU-derived suggestions may propose a ladder, but must not overwrite confirmed amounts without an explicit setup change

### 7. Checkpoints

**Not currently supported** as the full package described (actual coin-in, settled balance, recovery, Watch / Continue / Hard Exit at checkpoints, checkpoint persistence).

This is a **separate workstream**, not a small label or formula tweak on the current cards.

### 8. Decision version / stale quotes

**Today:** mission decision payloads already carry `decision_id` and version stamps on the decision object.

**Not yet:** binding that version onto route cards and quotes, and rejecting route select / Begin Play when stale.

**Agreed as required** for the revised contract. Missing/zero denominators must not invent a misleading percentage; values above 100% must not be hidden by capping the display at 100%.

### 9–10. Screenshot reproduction and implementation evidence

We can reproduce Entertainment-path percentages from budget, balance, ladder, and the static map for a given session.

We **cannot** yet produce a Mission worked example with regional click ranges, per-click dollars, and Mission-priced exposures until the Mission pricing contract is implemented. That evidence pack (worked Mission example, tests, updated screenshots) will follow the contract + staging build.

---

## Capability matrix

| Capability | Status |
|---|---|
| Entertainment map exposure / balance-share cards | **Available today** |
| Budget, balance, quoted or RU ladder on next-route | **Available today** |
| Mission decision authority fields (continuation / Hard Exit / spin posture) | **Partially available** |
| Mission-priced cards from final safety-adjusted wager map | **Requires backend changes** |
| Per-click / regional dollar map + total planned route cost | **Requires backend changes** |
| Dynamic Mission endpoints on route options | **Requires backend changes** |
| Confirmed vs preliminary wager flag | **Requires backend changes** |
| Decision-version stale rejection on select / Begin Play | **Requires backend changes** |
| Full checkpoint integration | **Not currently supported** (new workstream) |

---

## Proposed next steps (before Flutter changes)

1. Agree the **API contract** for Mission-mode route cards (decision version, endpoints, regional/per-click map, totals, both exposures, ladder confirmation state).
2. Keep Entertainment cards on the existing path until Mission-priced cards are ready.
3. Implement Mission pricing + stale-decision checks behind the existing mission feature flag (**staging first**; no production flag flip until verified).
4. Treat **checkpoints** as a follow-on contract after route/exposure authority is locked.
5. Flutter implementation only after we share a sample Mission response and staging verification.

We will **not** substitute another rule silently. Where the current architecture conflicts with this ask (Entertainment-priced cards vs Mission authority), Entertainment behavior stays explicit, and Mission pricing becomes the authoritative path for Mission mode.

Please confirm you want us to proceed with drafting the Mission route / exposure API contract next.
