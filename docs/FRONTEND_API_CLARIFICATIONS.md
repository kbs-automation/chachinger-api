# Frontend clarification answers (with real request/response)

Answers to the four blockers. Captured from the **running API test harness** with `MISSION_CRITICAL_ENGINE=true` (same code as `main`). No app/feature-flag changes assumed on your side.

---

## 1. BELOW BASE execution

**Setup used:** engine on, sheet with front+later targets so opening region plans BELOW BASE, app sends `active_postures: ["base","press","max"]` only (never `below_base`).

### 1a — `live_final_authority` planned as below_base, amount set, `below_base` **not** in `active_postures`

**Request (start play):**

```http
POST /api/v1/sessions/{session_id}/plays
```

```json
{
  "confirmed_base": 5,
  "confirmed_press": 10,
  "confirmed_max": 20,
  "confirmed_below_base": 2,
  "active_postures": ["base", "press", "max"]
}
```

**Response (start-play) — real:**

```json
{
  "play_id": "4e003875-5a1f-440e-a91d-a6a240a5b456",
  "status": "active",
  "posture": "base",
  "next_bet_amount": 5.0,
  "play_progress_pct": 0,
  "play_number": 1,
  "cycle_number": 1,
  "click_cap": 96,
  "current_balance": 1000.0,
  "session_budget": 1000.0,
  "confirmed_below_base": 2.0
}
```

**Response (first spin) — real:**

```json
{
  "spin_id": "b38456e8-f552-4d95-b385-0a06432a0855",
  "posture": "base",
  "next_bet_amount": 5.0,
  "play_progress_pct": 1,
  "play_number": 1,
  "cycle_number": 1,
  "at_hard_exit_cap": false,
  "current_balance": 995.0,
  "redirect": "continue",
  "planned_band_authority": "below_base",
  "live_final_authority": "below_base",
  "continuation_authority": "extended",
  "bridge_state": "off"
}
```

**Answer:** Yes — same as mapping note §6 for **execution**: spin/start-play return **`posture: "base"`** and **`next_bet_amount: confirmed_base` (5.0)**.  
That holds even when the engine’s authority fields still say `below_base` (see `planned_band_authority` / `live_final_authority` on the spin). **Bet what `posture` + `next_bet_amount` say.**

### 1b — `confirmed_below_base` omitted/null

**Request:**

```json
{
  "confirmed_base": 5,
  "confirmed_press": 10,
  "confirmed_max": 20,
  "active_postures": ["base", "press", "max"]
}
```

**Start-play — real:**

```json
{
  "play_id": "10415e73-0cd8-43ab-ba96-e6eed63c7312",
  "status": "active",
  "posture": "base",
  "next_bet_amount": 5.0,
  "confirmed_below_base": null,
  "click_cap": 96,
  "current_balance": 1000.0,
  "session_budget": 1000.0,
  "play_number": 1,
  "cycle_number": 1,
  "play_progress_pct": 0
}
```

**Spin — real:**

```json
{
  "spin_id": "754127cc-03ac-45f9-8115-25328bd5c45b",
  "posture": "base",
  "next_bet_amount": 5.0,
  "play_progress_pct": 1,
  "at_hard_exit_cap": false,
  "current_balance": 995.0,
  "redirect": "continue",
  "planned_band_authority": "below_base",
  "live_final_authority": "base",
  "continuation_authority": "extended",
  "bridge_state": "off"
}
```

### 1c — Reject / silent / flag?

| Behavior | What happens |
|---|---|
| Reject request? | **No** (201 / 200) |
| Fall back? | **Yes, for execution** → `posture`/`next_bet_amount` use BASE |
| Flagged? | Partially: spin may still show `planned_band_authority: "below_base"`. Enhanced-sheet decision notes can include `below_base_planned_without_amount_execute_base`. There is **no** dedicated error code for this fallback. |

### 1d — Exact field names

Use: **`posture`**, **`next_bet_amount`** (samples above).

---

## 2. Authoritative posture per spin

### 2a — `posture` vs `live_final_authority`

**Use `posture` + `next_bet_amount` to place the bet.**

They **can differ** (see 1a): engine authority can stay `below_base` while executable `posture` is remapped to `base` because `below_base` ∉ `active_postures`.

| Field | Role |
|---|---|
| `posture` + `next_bet_amount` | **Authoritative for execution** (what was locked on the spin) |
| `live_final_authority` / `planned_band_authority` | Engine WBA/safety view (guidance/audit); do not override `posture` when they disagree |

### 2b — Recalculated every click?

**Yes.** Each `POST /plays/{id}/spins` recomputes authority for the next internal click from the stored route plan (target / pre-entry / bridge / after END_CLICK). Authority can change when:

- entering **pre_entry** (re-arm),
- entering an **active target**,
- **after** a target’s END_CLICK (gap → bridge / below_base plan) — aligned with terminal-click keep, then expire (TB-061 / WBA-080).

### 2c — Sample sequence (bridge → target → after expiry)

Unit path on the same sheet shape (7–13 front MAX, later 40+; no below_base amount → live execute base on bridges):

```json
{
  "sequence": [
    { "click": 1,  "planned_band_authority": "below_base", "live_final_authority": "base", "bridge_state": "off" },
    { "click": 5,  "planned_band_authority": "base",       "live_final_authority": "base", "bridge_state": "pre_entry" },
    { "click": 7,  "planned_band_authority": "max",        "live_final_authority": "max",  "bridge_state": "off" },
    { "click": 10, "planned_band_authority": "max",        "live_final_authority": "max",  "bridge_state": "off" },
    { "click": 13, "planned_band_authority": "max",        "live_final_authority": "max",  "bridge_state": "off" },
    { "click": 14, "planned_band_authority": "below_base", "live_final_authority": "base", "bridge_state": "active" },
    { "click": 20, "planned_band_authority": "below_base", "live_final_authority": "base", "bridge_state": "active" }
  ]
}
```

**First live spin response** (opening click on that play; Entertainment P1 map may still apply until P2+ with route plan — P1 entertainment click 1 is often MAX):

```json
{
  "spin_id": "…",
  "posture": "max",
  "next_bet_amount": 20.0,
  "redirect": "continue",
  "planned_band_authority": "…",
  "live_final_authority": "…",
  "continuation_authority": "extended",
  "bridge_state": "…"
}
```

Note: **Play-1** with `p1_mode_active` still uses the P1 zone map for `posture`. Mission WBA click sequence above applies to **P2+** once `route_plan` is stored and P1 is off. For P2+ spins, expect `posture` to track the sequence pattern above (with BASE fallback when below_base is not executable).

---

## 3. Weighted token orientation (critical)

### Final decision

**Follow the Lookup sheet: segment-first.** Tab 13 ES-031 weight-first is **superseded**.

Reason: real Lookup values (`1*138; 2*95; …`) put descending frequencies after `*`; segment range is 1–33, so 138 cannot be a segment ID. Lookup row-10 annotation matches (`2*7` = segment 2 appeared 7 times).

`PARSER_VERSION` bumped to **0.2.0**.

### Server result (real `tokens.py` run)

| Input (Lookup, split on `;`) | Expected segment-first | **Server result (segment_id / weight)** |
|---|---|---|
| `1*138; 2*95; 3*74; 4*64` | 1/138, 2/95, 3/74, 4/64 | **1/138, 2/95, 3/74, 4/64** |
| `1*6; 4*7; 2*7; 11; 25; 3*3` | 1/6, 4/7, 2/7, 11/1, 25/1, 3/3 | **1/6, 4/7, 2/7, 11/1, 25/1, 3/3** |
| `2*7;4*7` | 2/7, 4/7 | **2/7, 4/7** |

```json
{
  "row_4": [
    { "raw": "1*138", "segment_id": 1, "weight": 138 },
    { "raw": "2*95", "segment_id": 2, "weight": 95 },
    { "raw": "3*74", "segment_id": 3, "weight": 74 },
    { "raw": "4*64", "segment_id": 4, "weight": 64 }
  ],
  "row_8": [
    { "raw": "1*6", "segment_id": 1, "weight": 6 },
    { "raw": "4*7", "segment_id": 4, "weight": 7 },
    { "raw": "2*7", "segment_id": 2, "weight": 7 },
    { "raw": "11", "segment_id": 11, "weight": 1 },
    { "raw": "25", "segment_id": 25, "weight": 1 },
    { "raw": "3*3", "segment_id": 3, "weight": 3 }
  ],
  "row_10": [
    { "raw": "2*7", "segment_id": 2, "weight": 7 },
    { "raw": "4*7", "segment_id": 4, "weight": 7 }
  ]
}
```

### 3a — Which orientation? Tested on real Lookup?

- **Segment-first** (`A*B` → segment_id=A, weight=B), locked to **Lookup**.
- **Yes** — real Lookup strings locked in `tests/test_lookup_token_orientation.py`.

### 3b — `1*138`

- Parsed as **segment 1, weight 138** (in-band). No out-of-range segment invented.

### 3c — Single written rule + test

**Rule:** In `A*B`, **A = segment_id**, **B = weight/count**. Plain `N` → segment_id=N, weight=1. Split workbook cells on `;` into a JSON string array before POST.

**Parser test:** `api/tests/test_lookup_token_orientation.py`.

---

## 4. PRESS authorization

### Current API fact

- **`POST /plays/{id}/spins` has no body** — client cannot request PRESS/MAX on a spin.
- **`POST /sessions/{id}/plays`** accepts only bet ladder + optional `active_postures` / `confirmed_below_base` — **no requested posture field**.
- Server **assigns** `posture` / `next_bet_amount`.

### 4a–4d answers

| Question | Answer |
|---|---|
| 4a Player “requests PRESS” while live is BASE? | **There is no such request today.** Nothing to reject or downgrade. |
| 4b Field / error code? | **N/A** — no `AUTHORITY_CAP` / no posture-command error. |
| 4c Is `AUTHORITY_CAP` implemented? | **No** — not in code. Workbook EX-011 / checklist ER-042 are **not** implemented as a client command surface. |
| 4d MAX / after HARD EXIT? | Same: no client posture command. After session/play hard exit, further spins get **`409`** (`session_not_active` / `play_not_active`), not an authority-cap payload. |

**Example — spin has no request posture (only response):**

```http
POST /api/v1/plays/{play_id}/spins
Authorization: Bearer …
```

```json
{
  "spin_id": "…",
  "posture": "base",
  "next_bet_amount": 5.0,
  "redirect": "continue",
  "planned_band_authority": "below_base",
  "live_final_authority": "base",
  "continuation_authority": "extended",
  "bridge_state": "off"
}
```

If you need EX-011 “user asked PRESS, server caps to BASE”, that requires a **new** request field (e.g. `requested_posture`) — not present now. Confirm if you want that designed next.

---

## Summary for Flutter (no code change required on your side yet)

1. **Execute** with `posture` + `next_bet_amount` only; your BELOW BASE workaround (never send `below_base` in `active_postures`) yields **BASE bets** even when authority fields say `below_base`.
2. Authority fields are recalculated per spin on P2+ with a route plan; sequence changes across pre-entry / target / post-expiry bridge.
3. Tokens are **segment-first (Lookup)** — `1*138` → segment 1, weight 138. ES-031 weight-first is superseded (`PARSER_VERSION` 0.2.0).
4. **No** client PRESS/MAX request or `AUTHORITY_CAP` yet.

Repro harness (optional): `pytest -s tests/_clarify_frontend_examples.py` and `tests/test_lookup_token_orientation.py`.
