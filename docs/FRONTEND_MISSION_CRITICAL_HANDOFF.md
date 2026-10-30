# CHA3535 Mission-Critical API — Frontend Handoff

Backend points **4 and 5** (workbook WBA, Hard Exit, decision contract) are on GitHub `main` (`f275493` and related). This document is the integration contract for Flutter.

Related:

- [FRONTEND_API_GUIDE.md](./FRONTEND_API_GUIDE.md) §15
- [FRONTEND_SHEET_FIELD_MAPPINGS.md](./FRONTEND_SHEET_FIELD_MAPPINGS.md) — confirmed `row_17` / density / tokens / pockets / BELOW BASE

---

## 1. API documentation

| Resource | Location |
|---|---|
| Narrative guide | `docs/FRONTEND_API_GUIDE.md` §15 |
| Live OpenAPI | https://chachinger-api.kindlebit.com/openapi.json |
| Interactive docs | https://chachinger-api.kindlebit.com/docs (when not production-locked) |
| Endpoint | `POST /api/v1/sessions/{session_id}/enhanced-sheet` |
| Schemas | `EnhancedSheetRequest`, `EnhancedSheetResponse`, `MissionDecisionOut` |

**Auth:** `Authorization: Bearer <access_token>`

---

## 2. Feature flag

Server env: `MISSION_CRITICAL_ENGINE` (default **`false`**).

| Flag | Behavior |
|---|---|
| `false` | Pocket routes + `posture` / `redirect` only. `decision` is `null`. Enhanced-sheet returns **409**. |
| `true` | Workbook-driven `decision`. Submit Enhanced Sheet after Play Complete. |

Deploy also needs Alembic through **0007** (`enhanced_sheet`, `route_plan`, `last_decision`).

### How Flutter detects the flag

There is **no public player config endpoint** yet. Detect as follows:

1. Call `POST .../enhanced-sheet`.
2. **`409` `mission_engine_disabled`** → flag **off** → legacy / pocket UI.
3. **`200`** with `decision.source === "mission_critical"` → flag **on**.
4. On next-route / spin-result: `decision == null` → treat as legacy.

Optional future: `GET /api/v1/meta` with `{ "mission_critical_engine": true/false }` — not shipped yet.

---

## 3. Required flow (flag on)

1. Complete a play that can continue (qualifying result).
2. **`POST /sessions/{id}/enhanced-sheet`** with Enhanced Excel cell JSON (+ play context for Weak Recompression).
3. Bind Play Complete UI to **`decision`** (`guidance_key`, `primary_action`, `live_final_authority`).
4. Pocket route cards may remain secondary for budget/exposure if product wants them.
5. On P2+ spins, use **`live_final_authority` / `posture`** from the server — do not invent posture from local maps.

---

## 4. Complete valid request example

All body fields are optional individually, but for a useful **`ready`** decision you need core structure (**`row_8` and/or `row_9`**, plus **`row_10`** preferred). Unknown fields are **rejected** (`extra: forbid`).

```http
POST /api/v1/sessions/{session_id}/enhanced-sheet
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "row_2": ["S1", "S2"],
  "row_4": ["2", "3"],
  "row_5": ["2"],
  "row_7": 3,
  "row_8": ["2", "2*8", "6"],
  "row_9": ["2", "6"],
  "row_10": ["2"],
  "token_format": "segment_count_v1",
  "row_17": 31,
  "row_18": 42,
  "row_19": ["7-13", "60-69"],
  "primary_density_pct": 55.0,
  "secondary_density_pct": 22.5,
  "density_sample_n": 12,
  "density_strength": "STRONG",
  "pockets": ["70-80", "100-117"],
  "source_schema_version": "enhanced-excel-v1",
  "prev_ending_click": 31,
  "prev_multiplier": 21.0,
  "prior_ending_click": 118
}
```

### Field reference

| Field | Type | Notes |
|---|---|---|
| `row_2` | `string[] \| null` | Completed-play segment history (not click list) |
| `row_4`, `row_5` | `string[] \| null` | Broad envelope / corroborators |
| `row_7` | `int \| null` | Play-number anchor |
| `row_8`, `row_9` | `string[] \| null` | Route backbone. Tokens: `"13"` or weighted `"2*8"` → segment **2**, weight **8** (Lookup segment-first; weight is not a click) |
| `row_10` | `string[] \| null` | Attack-first candidate (does **not** define Hard Exit by itself) |
| `row_17` | `int \| null` | Sheet previous ending click |
| `row_18` | `number \| null` | Density / true-click anchor |
| `row_19` | `string[] \| null` | Ranges `"7-13"` or `"13"` — refine only; cannot create deep chase alone |
| `primary_density_pct` | `number \| null` | Omit/null if missing — **do not send `0` to mean missing** |
| `secondary_density_pct` | `number \| null` | |
| `density_sample_n` | `int \| null` | |
| `density_strength` | `string \| null` | e.g. `STRONG`, `WATCH`; unknown → `UNKNOWN` |
| `pockets` | `string[] \| null` | e.g. `"70-80"` |
| `source_schema_version` | `string \| null` | Workbook/schema id; use `UNKNOWN` if unsure |
| `prev_ending_click` | `int \| null` | **Just-completed** play ending click |
| `prev_multiplier` | `number \| null` | **Just-completed** play multiplier |
| `prior_ending_click` | `int \| null` | **Play before last** (CFG-160 Weak Recompression PREV) |

---

## 5. Response shape

```json
{
  "input_quality": "ready",
  "warnings": [],
  "conflicts": [],
  "parser_version": "0.3.0",
  "decision": { }
}
```

### `decision` fields (bind Flutter here)

| Field | Values / meaning |
|---|---|
| `source` | `mission_critical` \| `legacy_pocket_compat` |
| `continuation_authority` | `none` \| `limited` \| `extended` \| `deep_burn` — **how far** |
| `hard_exit_state` | `normal` \| `hard_exit_watch` \| `hard_exit_pending` \| `hard_exit` |
| `final_action` | `continue` \| `exit` |
| `primary_action` | `continue` \| `continue_controlled` \| `exit_machine` |
| `guidance_key` | Tab-26 key: `ui_001_continue` … `ui_015_manual_exit` |
| `planned_band_authority` | Pre-safety: `below_base` \| `base` \| `press` \| `max` \| null |
| `live_final_authority` | **Show & execute this** (after safety) |
| `bridge_state` | `off` \| `active` \| `pre_entry` |
| `exit_reason` | string \| null |
| `input_quality` | `ready` \| `degraded` \| `invalid` |
| `legacy_route_id` | Optional pocket id while UI still shows route cards |
| `engine_version` / `config_version` / `parser_version` | Audit stamps |
| `decision_id` / `calculated_at` / `notes` | Idempotency / debug |

**Rule:** continuation and wager are independent. A deep route can be `deep_burn` while `live_final_authority` is `below_base`. Never infer one from the other.

### Spin fields (flag on)

Also returned on spin register:

- `posture`
- `planned_band_authority`
- `live_final_authority`
- `continuation_authority`
- `bridge_state`

---

## 6. Response examples

### 6.1 `mission_critical` success (`ready`)

```json
{
  "input_quality": "ready",
  "warnings": [],
  "conflicts": [],
  "parser_version": "0.3.0",
  "decision": {
    "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "source": "mission_critical",
    "continuation_authority": "extended",
    "hard_exit_state": "normal",
    "final_action": "continue",
    "primary_action": "continue",
    "guidance_key": "ui_003_extended_route",
    "planned_band_authority": "below_base",
    "live_final_authority": "below_base",
    "bridge_state": "active",
    "exit_reason": null,
    "input_quality": "ready",
    "engine_version": "0.3.0-tab11",
    "config_version": "0.3.0",
    "parser_version": "0.3.0",
    "calculated_at": "2026-10-27T12:00:00+00:00",
    "legacy_route_id": null,
    "notes": [
      "input_quality=ready",
      "targets=2",
      "bridges=1",
      "wba:bridge_survival"
    ]
  }
}
```

### 6.2 Legacy mode (flag off)

```json
HTTP/1.1 409 Conflict
{
  "detail": {
    "code": "mission_engine_disabled",
    "message": "Enable MISSION_CRITICAL_ENGINE to submit Enhanced Sheet data"
  }
}
```

On Play Complete / next-route when flag off: `decision` is `null` (use pocket `continuation` only).

When flag is on but **no sheet** was stored yet, next-route may return `source: "legacy_pocket_compat"`. Prefer submitting the sheet first.

### 6.3 `input_quality: invalid`

```json
{
  "input_quality": "invalid",
  "warnings": ["missing_core_rows_8_9_10"],
  "conflicts": [],
  "parser_version": "0.3.0",
  "decision": {
    "decision_id": "…",
    "source": "mission_critical",
    "continuation_authority": "none",
    "hard_exit_state": "hard_exit",
    "final_action": "exit",
    "primary_action": "exit_machine",
    "guidance_key": "ui_009_no_qualified_route",
    "planned_band_authority": null,
    "live_final_authority": null,
    "bridge_state": "off",
    "exit_reason": "no_supported_route",
    "input_quality": "invalid",
    "engine_version": "0.3.0-tab11",
    "config_version": "0.3.0",
    "parser_version": "0.3.0",
    "calculated_at": "…",
    "legacy_route_id": null,
    "notes": ["input_quality=invalid", "warn:missing_core_rows_8_9_10"]
  }
}
```

Row 17 vs completed-play conflict example: `conflicts: ["row_17_prev_click_mismatch"]`.

**Flutter:** EXIT / retry sheet entry — **no invented bets**.

### 6.4 `input_quality: degraded`

```json
{
  "input_quality": "degraded",
  "warnings": ["incomplete_core_corroboration"],
  "conflicts": [],
  "parser_version": "0.3.0",
  "decision": {
    "decision_id": "…",
    "source": "mission_critical",
    "continuation_authority": "limited",
    "hard_exit_state": "normal",
    "final_action": "continue",
    "primary_action": "continue",
    "guidance_key": "ui_002_short_route",
    "planned_band_authority": "base",
    "live_final_authority": "base",
    "bridge_state": "off",
    "exit_reason": null,
    "input_quality": "degraded",
    "engine_version": "0.3.0-tab11",
    "config_version": "0.3.0",
    "parser_version": "0.3.0",
    "calculated_at": "…",
    "legacy_route_id": null,
    "notes": ["input_quality=degraded", "warn:incomplete_core_corroboration"]
  }
}
```

### 6.5 HARD EXIT

```json
{
  "input_quality": "ready",
  "warnings": [],
  "conflicts": [],
  "parser_version": "0.3.0",
  "decision": {
    "decision_id": "…",
    "source": "mission_critical",
    "continuation_authority": "none",
    "hard_exit_state": "hard_exit",
    "final_action": "exit",
    "primary_action": "exit_machine",
    "guidance_key": "ui_010_hard_exit",
    "planned_band_authority": null,
    "live_final_authority": null,
    "bridge_state": "off",
    "exit_reason": "final_target_exhausted",
    "input_quality": "ready",
    "engine_version": "0.3.0-tab11",
    "config_version": "0.3.0",
    "parser_version": "0.3.0",
    "calculated_at": "…",
    "legacy_route_id": null,
    "notes": []
  }
}
```

**Flutter:** if `final_action === "exit"` or `primary_action === "exit_machine"` → **EXIT MACHINE** only (never CONTINUE + EXIT together).

---

## 7. Sheet data source

The API accepts **JSON cell values only**. There is **no** Excel upload endpoint today, and the backend does **not** invent sheet rows.

| Option | Status |
|---|---|
| User / coach enters values in-app → app POSTs JSON | Supported now |
| App parses a local `.xlsx` → POSTs JSON | Supported now (client-side parse) |
| Backend receives Excel / partner feed into the session | **Not built yet** |

Product must choose the UX path until an upload/partner feed exists.

---

## 8. Degraded input — exact Flutter behavior

| Quality | Flutter behavior |
|---|---|
| `ready` | Normal decision UI |
| `degraded` | Still use `decision` if `final_action === "continue"`. Follow `live_final_authority` + `primary_action` / `guidance_key`. Expect more conservative posture (often BASE). Optional soft notice: “Limited sheet data — playing controlled.” **Do not** invent MAX/PRESS client-side. |
| `invalid` | EXIT / retry sheet. **No bets.** |

Do **not** treat degraded as invalid unless `final_action === "exit"`.

---

## 9. BELOW BASE (still applies)

- Do **not** put `below_base` in `active_postures` on every P2+ start.
- Omit `confirmed_below_base` unless BELOW BASE is intentionally enabled.
- With mission engine on, bridges/unsupported gaps are planned as **BELOW BASE** by the server. If no amount is confirmed, execution may fall back to BASE while planned stays `below_base`.

Valid spin postures: `base`, `press`, `max`, `below_base` (when enabled). `early_attack` is in the schema but not emitted. Bridge/HER are **not** posture strings.

---

## 10. Play Complete UI checklist

- [ ] Result block (click, multiplier, bet used, win, balance)
- [ ] `guidance_key` → locked Tab-26 copy
- [ ] `primary_action` → CONTINUE / CONTINUE CONTROLLED / EXIT MACHINE
- [ ] `live_final_authority` → displayed posture
- [ ] No raw rows / HER / DFR / history on main screen
- [ ] No conflicting actions (e.g. MAX + HARD EXIT)
- [ ] Pocket cards optional / secondary

---

## 11. Staging / live deploy status

Checked against **https://chachinger-api.kindlebit.com** (host used by the app):

| Check | Result |
|---|---|
| OpenAPI lists `POST /api/v1/sessions/{session_id}/enhanced-sheet` | **Yes — route is deployed** |
| Schemas present | **Yes** |
| Unauthenticated call | `401 not_authenticated` (route exists) |
| `MISSION_CRITICAL_ENGINE=true` on host | **Not confirmed externally** (defaults **false**; likely still off until ops sets env) |
| Migration **0007** applied | **Confirm on host:** `alembic current` should include `0007` |

### Ops checklist before E2E

1. Set `MISSION_CRITICAL_ENGINE=true` on staging first.
2. Confirm `alembic current` → `0007` (or `head`).
3. Smoke-test authenticated `enhanced-sheet` → `200` + `source: "mission_critical"`.
4. Coordinate Flutter E2E with backend.

---

## 12. What we need from Flutter

1. Confirm you can call `enhanced-sheet` after Play Complete.
2. Wire UI to `decision` when `source === "mission_critical"`.
3. Tell us when ready for flag-on on staging/live for joint retest.

---

## 13. Repo

https://github.com/kbs-automation/chachinger-api — `main` includes mission decision contract + workbook WBA / Tab 11 coverage (`0620d7e`, `f275493`).
