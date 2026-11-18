# Frontend handoff — Mission route pricing (next-route cards)

Backend: `chachinger-api` `main` (Mission pricing path).  
Requires migration **`0008`** and `MISSION_CRITICAL_ENGINE=true` on staging to see Mission cards.

Related: [MISSION_ROUTE_EXPOSURE_API_CONTRACT.md](./MISSION_ROUTE_EXPOSURE_API_CONTRACT.md)

---

## Mode split (do not mix)

| Mode | When | What to show |
|---|---|---|
| **Entertainment** | `pricing_source` is null/`entertainment`, or no mission route plan | Existing pocket cards (`early` / `mid` / `deep` / `extreme_deep`). Same RU/quoted % as before. **Do not show click ranges.** |
| **Mission** | `pricing_source: "mission_critical"` | Cards priced from Mission-authorized dollars and endpoints. |

Entertainment UI stays as-is. Change Mission pricing displays only after this contract.

---

## New / important response fields

On `GET/POST .../next-route` and `POST .../next-route/quote`:

| Field | Meaning |
|---|---|
| `pricing_source` | `entertainment` \| `mission_critical` |
| `ladder_status` | `preliminary` (RU / suggested) \| `confirmed` (client sent base/press/max) |
| `decision_id` | Bind quote → select → Begin Play |
| `engine_version` / `config_version` / `parser_version` | Mission stamps |
| `reference.budget` | **Selected budget** for Planned Budget Exposure (quoted budget if sent, else session budget) |
| `reference.ladder_status` | Same preliminary/confirmed idea on the ladder |

### Mission card fields

| Field | Meaning |
|---|---|
| `route_id` | `mission_to_{end_click}` e.g. `mission_to_13` |
| `end_click` | Authorized endpoint (show this) |
| `start_click` | 1 = full route; higher = remaining from next unplayed click |
| `pricing_scope` | `full_route` \| `remaining` |
| `total_planned_wager` | Sum of authorized dollars |
| `planned_budget_exposure_pct` | total ÷ selected budget × 100 |
| `planned_balance_exposure_pct` | total ÷ current balance × 100 |
| `exposure_pct` | Same as planned budget exposure (compat) |
| `risk_pct` | **Planned Balance Exposure** (not loss probability) |
| `regions[]` | kind, click range, posture, amount, clicks, subtotal, optional `safety_reason` |

Suggested “Risk” helper text:

> Planned wagers through this route’s endpoint as a percentage of your current balance. Actual wagering may be lower if the play completes or a checkpoint ends it earlier.

---

## Flutter actions

1. Branch UI on `pricing_source`.
2. Mission: render endpoint, regions, total planned wager, both exposures; use `planned_balance_exposure_pct` (or label `risk_pct` as Planned Balance Exposure).
3. Prefer sending a **confirmed** ladder on quote before Begin Play; treat `ladder_status: preliminary` as estimates.
4. On select: `POST .../next-route` with `{ "route_id": "mission_to_13", "decision_id": "<from offer>" }`.
5. On `409 stale_decision` → refresh quote; do not Begin Play on stale cards.
6. Remaining cost: quote with `start_click` = next unplayed click while a play is active (`pricing_scope: remaining`). Already-wagered amounts are not in that total.
7. Do **not** price Mission screens from Entertainment map or invent client-side %.

---

## Worked examples (live engine)

Budget/balance **1000**, ladder **5 / 10 / 20**, below_base **2**, front target through click **13**:

**A — Bridge + BELOW BASE:** total **152** → **15.2%** budget & balance  
**B — Containment safety:** total **26** → **2.6%**

Details in the contract doc.

---

## Checkpoints

Still a **separate** workstream. Planned route cards ≠ checkpoint actuals. Do not remove any existing Mission safety/Hard Exit behavior while adopting these cards.

---

## Ops note

Staging needs alembic **`0008`** (`pending_quote`, longer route ids) before Mission select/Begin Play will persist correctly.
