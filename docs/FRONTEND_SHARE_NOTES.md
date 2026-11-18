# Frontend share notes

Backend handoff for Flutter. Repo: `chachinger-api` `main` @ `c936587`.

Related docs:

- [FRONTEND_SHEET_FIELD_MAPPINGS.md](./FRONTEND_SHEET_FIELD_MAPPINGS.md)
- [FRONTEND_API_CLARIFICATIONS.md](./FRONTEND_API_CLARIFICATIONS.md)
- [FRONTEND_MISSION_CRITICAL_HANDOFF.md](./FRONTEND_MISSION_CRITICAL_HANDOFF.md)
- [FRONTEND_API_GUIDE.md](./FRONTEND_API_GUIDE.md) §13 (next-route %)

---

## A. Enhanced Sheet tokens (implemented)

Weighted tokens are locked to Lookup **`segment*count`** (not Tab 13 ES-031 weight-first).

| Token | Meaning |
|---|---|
| `1*138` | segment **1**, weight/count **138** |
| `2*7` | segment **2**, weight/count **7** |
| `13` | segment **13**, weight **1** |

| Contract field | Value |
|---|---|
| `PARSER_VERSION` | `0.3.0` |
| `token_format` | `segment_count_v1` |
| `source_schema_version` | Workbook / schema id only — **not** token orientation |

### Flutter actions

1. Split workbook cells on `;` (trim) into a `string[]` **before** POST.  
   `"1*138; 2*95"` → `["1*138", "2*95"]`
2. Prefer sending on `POST /sessions/{id}/enhanced-sheet`:

```json
{
  "row_8": ["1*138", "2*95", "7"],
  "token_format": "segment_count_v1",
  "source_schema_version": "UNKNOWN"
}
```

3. Expect on response: `parser_version: "0.3.0"`, `token_format: "segment_count_v1"`.
4. Omitting `token_format` still works on the new server (segment-first by default). Sending it is preferred so older servers **422** instead of silently misreading tokens.
5. Unmapped segment ordinals are skipped server-side (no invented click ranges). Do not hard-cap at 33/97 on the client for rejection.

### Unchanged constraints

- BELOW BASE workaround (`below_base` not in `active_postures`) stays as-is.
- Execute bets from **`posture` + `next_bet_amount`** only.
- No client PRESS/MAX request; **`AUTHORITY_CAP` is not implemented**.
- No manual `.xlsx` import; do not flip production feature flags from the app.

---

## B. Next-route `exposure_pct` / `risk_pct` (clarification — no new code)

These are **not** probabilities of financial loss and **not** “chance of finishing the route without a hit.”

| Field | Meaning |
|---|---|
| `exposure_pct` | Route wager ÷ **budget** × 100, rounded to 0.1 |
| `risk_pct` | Same wager ÷ **`current_balance`** × 100, rounded to 0.1 |

**Route wager** = sum of posture bets on the Entertainment map for that route’s click range (cumulative from click 1). Switched-off postures use the nearest-active rule.

### Route click ranges (cumulative)

| `route_id` | Clicks used for wager |
|---|---|
| `early` | 1–18 |
| `mid` | 1–33 |
| `deep` | 1–54 |
| `extreme_deep` | 1–70 |

### Ladder when bets are not quoted

Risk Unit factors of `budget / 100` (cent-rounded):

| Posture | Factor |
|---|---|
| BASE | 0.40 |
| PRESS | 1.00 |
| MAX | 1.40 |

### Data source

**No historical spin records.** Inputs: static Entertainment zone map, budget, live balance, bet ladder, `active_postures` (+ optional `below_base`).

Bridge, safety, mission WBA, and “authorized extra clicks” **do not** enter these two percentages.

### Recalculation

Recomputed on every next-route read (not stored):

- Spin result that opens next-play continuation
- `GET /sessions/{id}/next-route`
- `POST /sessions/{id}/next-route/quote`
- `POST /sessions/{id}/next-route` (select)

### “72.3%” relationship

There is **no** fixed factor converting Exposure into Risk.

Closest constant in code: **73.20** = full **96-click** map priced at RU units `(0.40, 1.00, 1.40)`. That is a full-map RU shape, **not** used on next-route cards (capped at 70 → extreme_deep ≈ **52.6%** of budget with RU).

Ignoring rounding:

`risk_pct / exposure_pct ≈ budget / current_balance`

### Example (live formula)

`reference` for budget **890** (session-budget RU):

```json
{
  "budget": 890.0,
  "base": 3.56,
  "press": 8.9,
  "max": 12.46,
  "source": "session_budget"
}
```

Early (1–18) wager = **140.62** → `exposure_pct` = **15.8**.  
If `current_balance` = **585.92** → `risk_pct` = **24.0**.

| Route | Wager | Exposure (budget 890) |
|---|---|---|
| early | 140.62 | **15.8%** |
| mid | 267.00 | **30.0%** |
| deep | 379.14 | **42.6%** |
| extreme_deep | 468.14 | **52.6%** |

Note: older guide sample showing early `exposure_pct: 21.4` is **illustrative / outdated** vs this RU math.

Display server-sent `%` values; do not invent a client-side formula.

---

## C. What we need from Flutter

1. Read the mapping + clarifications docs; adopt `segment*count` and prefer `token_format: "segment_count_v1"`.
2. Render `exposure_pct` / `risk_pct` from the API as provided.
3. Verify against **staging** before relying on mission engine / new parser in production builds.

Propose app implementation changes after reading this note and the linked docs.
