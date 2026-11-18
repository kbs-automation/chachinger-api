# Mission route / exposure API contract

**Repo:** `chachinger-api` `main` @ `47c5dcd`  
**Migration:** `0008_mission_route_quotes` (`pending_quote`, route id length 40)  
**Flag:** Mission cards require `MISSION_CRITICAL_ENGINE=true` **and** a stored route plan (enhanced-sheet).

Entertainment path stays on the static pocket map. Mission path uses the safety-adjusted wager map.

---

## Endpoints

| Call | Method | Path |
|---|---|---|
| Next-route offer | `GET` | `/api/v1/sessions/{id}/next-route` |
| Quote / reprice | `POST` | `/api/v1/sessions/{id}/next-route/quote` |
| Select route | `POST` | `/api/v1/sessions/{id}/next-route` |

All return `NextRouteResponse` (same shape).

### Quote body

```json
{
  "budget": 1000,
  "base": 5,
  "press": 10,
  "max": 20,
  "below_base": 2,
  "active_postures": ["below_base", "base", "press", "max"],
  "start_click": 1
}
```

- Omit ladder → RU preliminary ladder from budget / session budget.  
- Send `base`+`press`+`max` together → `ladder_status: "confirmed"`.  
- `start_click` optional (default 1; use next unplayed click for remaining cost).

### Select body

```json
{
  "route_id": "mission_to_13",
  "decision_id": "d5393dca-695f-4427-a7bc-ee6cd476d672"
}
```

`decision_id` recommended for Mission. Mismatch / stale → `409` `stale_decision`.

---

## Mode split

| `pricing_source` | When | Cards |
|---|---|---|
| `entertainment` | Flag off, or no mission route plan | `early` / `mid` / `deep` / `extreme_deep` — **no** `end_click` / `regions` |
| `mission_critical` | Flag on **and** route plan with targets | `mission_to_{end_click}` with regions + exposures |

## Selected budget

`reference.budget` = quote `budget` if sent, else `session_budget`.  
Planned Budget Exposure denominator.

## Ladder status

| Value | Meaning |
|---|---|
| `preliminary` | RU / suggested — not Begin Play confirmation |
| `confirmed` | Client sent base/press/max on quote |

## Mission route ids

`mission_to_{end_click}` — e.g. `mission_to_13`. Max length 40. Persisted on `pending_route` / play `route` after migration `0008`.

## Field reference (`NextRouteResponse`)

| Field | Entertainment | Mission |
|---|---|---|
| `pricing_source` | `entertainment` | `mission_critical` |
| `ladder_status` | preliminary/confirmed | same |
| `decision_id` | usually null | from last mission decision |
| `engine_version` / `config_version` / `parser_version` | null | stamped |
| `reference.*` | yes | yes (+ `below_base` when used) |
| `routes[].route_id` | pocket id | `mission_to_*` |
| `routes[].end_click` / `start_click` / `pricing_scope` | null | set |
| `routes[].regions` | null | set |
| `routes[].total_planned_wager` | may be present | set |
| `routes[].planned_*_exposure_pct` | may be present | set |
| `routes[].exposure_pct` | budget exposure | same |
| `routes[].risk_pct` | **Planned Balance Exposure** | same |
| `offer_meta` | e.g. `{ "start_click": 1 }` | same |
| `decision` | optional mission decision object when flag on | prefer for UX authority |

### `regions[]` item

`kind`, `start_click`, `end_click`, `posture`, `amount`, `clicks`, `subtotal`, `safety_reason` (nullable).

## Stale quote

Select / Begin Play must align with the offer’s `decision_id` / persisted `pending_quote`.  
Mismatch → **`409 stale_decision`** → refresh quote.

---

## 1) Entertainment next-route — sample response

`GET .../next-route` after a completed play, mission plan absent / entertainment pricing.

Schema-accurate sample from live engine (budget = balance = 890, RU ladder):

```json
{
  "can_continue": true,
  "block_reason": null,
  "completed_play_number": 1,
  "next_play_number": 2,
  "next_cycle_number": 1,
  "prompt": "Choose Play-2 Budget",
  "selected_route": null,
  "reference": {
    "budget": 890.0,
    "base": 3.56,
    "press": 8.9,
    "max": 12.46,
    "below_base": null,
    "source": "session_budget",
    "ladder_status": "preliminary"
  },
  "routes": [
    {
      "route_id": "early",
      "heading": "EARLY POCKET DETECTED",
      "detail": "Continue through the early pocket only on the next play.",
      "exposure_pct": 15.8,
      "risk_pct": 15.8,
      "end_click": null,
      "start_click": null,
      "pricing_scope": null,
      "total_planned_wager": 140.62,
      "planned_budget_exposure_pct": 15.8,
      "planned_balance_exposure_pct": 15.8,
      "regions": null
    },
    {
      "route_id": "mid",
      "heading": "MID POCKETS DETECTED",
      "detail": "Continue through mid pockets only on the next play.",
      "exposure_pct": 30.0,
      "risk_pct": 30.0,
      "end_click": null,
      "start_click": null,
      "pricing_scope": null,
      "total_planned_wager": 267.0,
      "planned_budget_exposure_pct": 30.0,
      "planned_balance_exposure_pct": 30.0,
      "regions": null
    },
    {
      "route_id": "deep",
      "heading": "DEEP POCKETS DETECTED",
      "detail": "Continue through deep pockets only on the next play.",
      "exposure_pct": 42.6,
      "risk_pct": 42.6,
      "end_click": null,
      "start_click": null,
      "pricing_scope": null,
      "total_planned_wager": 379.14,
      "planned_budget_exposure_pct": 42.6,
      "planned_balance_exposure_pct": 42.6,
      "regions": null
    },
    {
      "route_id": "extreme_deep",
      "heading": "EXTREME DEEP POCKETS DETECTED",
      "detail": "Continue through extreme deep pockets on the next play.",
      "exposure_pct": 52.6,
      "risk_pct": 52.6,
      "end_click": null,
      "start_click": null,
      "pricing_scope": null,
      "total_planned_wager": 468.14,
      "planned_budget_exposure_pct": 52.6,
      "planned_balance_exposure_pct": 52.6,
      "regions": null
    }
  ],
  "decision": null,
  "pricing_source": "entertainment",
  "ladder_status": "preliminary",
  "decision_id": null,
  "engine_version": null,
  "config_version": null,
  "parser_version": null,
  "offer_meta": { "start_click": 1 }
}
```

---

## 2) Mission next-route — sample response

After enhanced-sheet stored a route plan; `GET .../next-route` (or quote without ladder → preliminary).  
Below: **confirmed quote shape** also used for GET when the same ladder is applied in tests.

```json
{
  "can_continue": true,
  "block_reason": null,
  "completed_play_number": 1,
  "next_play_number": 2,
  "next_cycle_number": 1,
  "prompt": "Choose Play-2 Budget",
  "selected_route": null,
  "reference": {
    "budget": 1000.0,
    "base": 5.0,
    "press": 10.0,
    "max": 20.0,
    "below_base": 2.0,
    "source": "quoted_bets",
    "ladder_status": "confirmed"
  },
  "routes": [
    {
      "route_id": "mission_to_13",
      "heading": "MISSION TARGET TO CLICK 13",
      "detail": "Authorized through this Mission endpoint.",
      "exposure_pct": 15.2,
      "risk_pct": 15.2,
      "end_click": 13,
      "start_click": 1,
      "pricing_scope": "full_route",
      "total_planned_wager": 152.0,
      "planned_budget_exposure_pct": 15.2,
      "planned_balance_exposure_pct": 15.2,
      "regions": [
        {
          "kind": "bridge",
          "start_click": 1,
          "end_click": 4,
          "posture": "below_base",
          "amount": 2.0,
          "clicks": 4,
          "subtotal": 8.0,
          "safety_reason": null
        },
        {
          "kind": "pre_entry",
          "start_click": 5,
          "end_click": 6,
          "posture": "below_base",
          "amount": 2.0,
          "clicks": 2,
          "subtotal": 4.0,
          "safety_reason": null
        },
        {
          "kind": "target",
          "start_click": 7,
          "end_click": 13,
          "posture": "max",
          "amount": 20.0,
          "clicks": 7,
          "subtotal": 140.0,
          "safety_reason": null
        }
      ]
    },
    {
      "route_id": "mission_to_49",
      "heading": "MISSION TARGET TO CLICK 49",
      "detail": "Authorized through this Mission endpoint.",
      "exposure_pct": 30.4,
      "risk_pct": 30.4,
      "end_click": 49,
      "start_click": 1,
      "pricing_scope": "full_route",
      "total_planned_wager": 304.0,
      "planned_budget_exposure_pct": 30.4,
      "planned_balance_exposure_pct": 30.4,
      "regions": [
        {
          "kind": "bridge",
          "start_click": 1,
          "end_click": 4,
          "posture": "below_base",
          "amount": 2.0,
          "clicks": 4,
          "subtotal": 8.0,
          "safety_reason": null
        },
        {
          "kind": "pre_entry",
          "start_click": 5,
          "end_click": 6,
          "posture": "below_base",
          "amount": 2.0,
          "clicks": 2,
          "subtotal": 4.0,
          "safety_reason": null
        },
        {
          "kind": "target",
          "start_click": 7,
          "end_click": 13,
          "posture": "max",
          "amount": 20.0,
          "clicks": 7,
          "subtotal": 140.0,
          "safety_reason": null
        },
        {
          "kind": "bridge",
          "start_click": 14,
          "end_click": 39,
          "posture": "below_base",
          "amount": 2.0,
          "clicks": 26,
          "subtotal": 52.0,
          "safety_reason": null
        },
        {
          "kind": "target",
          "start_click": 40,
          "end_click": 49,
          "posture": "press",
          "amount": 10.0,
          "clicks": 10,
          "subtotal": 100.0,
          "safety_reason": null
        }
      ]
    }
  ],
  "decision": null,
  "pricing_source": "mission_critical",
  "ladder_status": "confirmed",
  "decision_id": "d5393dca-695f-4427-a7bc-ee6cd476d672",
  "engine_version": "0.3.0-tab11",
  "config_version": "0.3.0",
  "parser_version": "0.3.0",
  "offer_meta": { "start_click": 1 }
}
```

Note: on a real session with the flag on, `decision` may also be populated from `last_decision`.

---

## 3) Mission quote — request + response

**Request**

```http
POST /api/v1/sessions/{session_id}/next-route/quote
```

```json
{
  "budget": 1000,
  "base": 5,
  "press": 10,
  "max": 20,
  "below_base": 2,
  "active_postures": ["below_base", "base", "press", "max"]
}
```

**Response:** same Mission shape as §2 (`pricing_source: "mission_critical"`, `ladder_status: "confirmed"`, `reference.source: "quoted_bets"`).  
Persists `pending_quote` when no play is in progress.

---

## 4) Mission route selection — request + response

**Request**

```http
POST /api/v1/sessions/{session_id}/next-route
```

```json
{
  "route_id": "mission_to_13",
  "decision_id": "d5393dca-695f-4427-a7bc-ee6cd476d672"
}
```

**Response:** same as the Mission offer, with:

```json
{
  "selected_route": "mission_to_13",
  "pricing_source": "mission_critical",
  "decision_id": "d5393dca-695f-4427-a7bc-ee6cd476d672",
  "routes": [ "...same mission cards..." ]
}
```

Begin Play then uses `pending_route` + `pending_quote` for Mission `click_cap` = endpoint (e.g. 13).

---

## Safety downgrade example (Mission costing)

Same sheet/ladder with containment: `mission_to_13` total **26.0** → **2.6%** (target region safety-adjusted; see `tests/test_mission_route_pricing.py`).

---

## Staging checklist (ops)

| Item | Code on `main` | Staging (ops must confirm) |
|---|---|---|
| Commit `47c5dcd` deployed | Yes (git) | **Confirm deploy** |
| Alembic `0008` applied | In repo | **Confirm `alembic upgrade head`** |
| `MISSION_CRITICAL_ENGINE=true` | Config flag | **Confirm env** |
| `pending_quote` column | Model + migration | **After 0008** |
| `mission_to_*` route ids | App + DB length 40 | **After 0008** |

Until staging has **deploy + 0008 + flag**, Flutter will still see Entertainment-shaped cards there. Use this contract + harness samples to implement against; verify once staging is ready.

Handoff summary: [FRONTEND_MISSION_PRICING_HANDOFF.md](./FRONTEND_MISSION_PRICING_HANDOFF.md).
