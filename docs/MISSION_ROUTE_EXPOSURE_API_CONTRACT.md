# Mission route / exposure API contract (draft)

**Status:** Backend implementation in progress (staging / mission flag).  
**Entertainment path:** unchanged — static pocket map + RU/quoted ladder.

## Mode split

| `pricing_source` | When | Numerator |
|---|---|---|
| `entertainment` | No mission route plan, or mission flag off | Entertainment zone map through fixed end |
| `mission_critical` | Mission flag on **and** stored route plan with qualified targets | Final safety-adjusted Mission wager map |

## Selected budget

`reference.budget` = quoted next-play budget if the client sent `budget` on quote; otherwise `session.session_budget`.  
Used as the Planned Budget Exposure denominator.

## Ladder status

| `ladder_status` | Meaning |
|---|---|
| `preliminary` | Suggested / session RU ladder — not yet the Begin Play confirmation |
| `confirmed` | Client sent base/press/max on quote (or session confirmed ladder used explicitly) |

## Mission route ids

`mission_to_{end_click}` — e.g. `mission_to_13`.  
Endpoint = that click. Option must not exceed continuation / last live target end.

## Card fields (Mission)

- `route_id`, `heading`, `detail`
- `end_click` — authorized endpoint  
- `start_click` — 1 before play; next unplayed click for remaining quotes  
- `pricing_scope` — `full_route` | `remaining`  
- `total_planned_wager`  
- `planned_budget_exposure_pct` (alias of exposure math)  
- `planned_balance_exposure_pct` (same meaning as legacy `risk_pct`)  
- `exposure_pct` / `risk_pct` — retained for compatibility (`risk_pct` = planned balance exposure)  
- `regions[]` — click ranges with posture, dollar amount, click count, subtotal  
- `decision_id`, version stamps on the offer

## Stale quote

Select / Begin Play must send or match the offer’s `decision_id`. Mismatch → `409 stale_decision`.

## Samples

See appendix: bridge/BELOW BASE and safety downgrade.

### Sample A — bridge + BELOW BASE (Mission)

**Live engine output** (budget/balance 1000; ladder 5/10/20 + below_base 2; segments 2+6 → ends 13 and 49):

`mission_to_13` total **152.0** → Planned Budget/Balance Exposure **15.2%**

| Region | Clicks | Posture | Amount | Subtotal |
|---|---|---|---|---|
| bridge | 1–4 | below_base | 2 | 8 |
| pre_entry | 5–6 | below_base | 2 | 4 |
| target | 7–13 | max | 20 | 140 |

### Sample B — safety downgrade (containment)

Same inputs with `SafetyState(containment=True)`. Target MAX is safety-adjusted; with BELOW BASE active, BASE resolves to BELOW BASE dollars (never raises aggression).

`mission_to_13` total **26.0** → **2.6%**

| Region | Clicks | Posture | Amount | Subtotal |
|---|---|---|---|---|
| bridge | 1–4 | below_base | 2 | 8 |
| pre_entry | 5–6 | below_base | 2 | 4 |
| target | 7–13 | below_base | 2 | 14 (`safety_adjusted`) |

Locked in `tests/test_mission_route_pricing.py`.
