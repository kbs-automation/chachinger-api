# Enhanced Sheet Field Mappings — Confirmed for Flutter

Written confirmation of API/parsing details before the Enhanced Sheet data-entry workflow.  
**No backend code changes** in this note — mappings follow workbook **Tab 13 (ES-*)** and the current server (`api/app/engine/mission/`).

Related:

- [FRONTEND_MISSION_CRITICAL_HANDOFF.md](./FRONTEND_MISSION_CRITICAL_HANDOFF.md)
- [FRONTEND_API_GUIDE.md](./FRONTEND_API_GUIDE.md) §15

---

## 1. `row_17`

| Source | Meaning |
|---|---|
| **ES-007 (controlling)** | Actual **completed ending click** from the previous play (integer) |
| Lookup sheet label “Spins (match plays)” | **Not** the API contract meaning |

**Flutter mapping**

- Send the just-completed play’s ending click as:
  - `row_17` (sheet value), and
  - `prev_ending_click` (authoritative engine value), ideally the **same number**.
- **ES-053:** if `row_17` ≠ `prev_ending_click` → `conflicts: ["row_17_prev_click_mismatch"]`, `input_quality: "invalid"`.

If Lookup truly stores spin-count in that cell, **do not** put it in `row_17`. Put the ending click instead (or request an owner change to ES-007).

---

## 2. `row_18` and density

| Workbook content | API field | Conversion |
|---|---|---|
| Row 18 density/output anchor | `row_18` | Single **number** (**ES-008**). Not a range. |
| Range like `0-10` | — | **Not** `row_18`. That is range/metadata (**ES-020**). No `primary_density_range` field yet — omit from API. |
| Primary density `0.6` (fraction) | `primary_density_pct` | Send **`60.0`** (percent 0–100). If sheet shows `60` / `60%`, send `60`. |
| Secondary / combined % | `secondary_density_pct` | Same: percent number, e.g. `22.5`. |
| Missing secondary | — | **Omit** field or `null`. **ES-054:** null ≠ zero — **do not** send `0` for “missing”. |

Also optional:

- `density_strength`: e.g. `"STRONG"`, `"WATCH"`
- `density_sample_n`: integer, or omit/null

---

## 3. Weighted tokens

**Decision (final):** **Lookup sheet segment-first** — not Tab 13 ES-031 weight-first.

**Rule:** In `A*B`, **A = segment_id**, **B = weight/count**. Plain `N` → segment_id=N, weight=1.  
(`PARSER_VERSION` **0.2.0**.)

| Token | Parsed as |
|---|---|
| `"1*138"` | `segment_id = 1`, `weight = 138` |
| `"2*8"` | `segment_id = 2`, `weight = 8` (not click 16) |
| `"13"` | `segment_id = 13`, `weight = 1` |

**Workbook string `1*138; 2*95`:** split before POST:

```json
["1*138", "2*95"]
```

→ segment **1** weight 138, segment **2** weight 95.

**API shape:** JSON **array of strings**. Split on `;` (trim) in Flutter **before** POST.  
A single string `"1*138; 2*95"` will **not** parse as two tokens.

Example:

```json
"row_8": ["1*138", "2*95", "7"]
```

Implementation: `api/app/engine/mission/tokens.py`.  
Why Lookup wins: real frequencies (`1*138`, …) put counts after `*`; segment range is 1–33, so 138 cannot be a segment ID. ES-031 operand order is superseded.

---

## 4. `row_2` and pockets

### `row_2` (ES-001)

- Rolling list of up to **four** completed-play **segment identifiers**, in play order.
- **Not** a click list.

One workbook cell → split tokens, then:

```json
"row_2": ["segA", "segB"]
```

Single token:

```json
"row_2": ["138"]
```

### `pockets` (ES-024)

- Array of click ranges, e.g. `"7-17"`, `"100-117"`.
- Current API has **one** list: `pockets` (no primary/secondary fields yet).
- **Send both** primary and secondary pockets in that array when available:

```json
"pockets": ["7-17", "100-117"]
```

Category split is required long-term by ES-024 but not exposed in this API version; combining into `pockets` is the approved interim mapping.

---

## 5. Schema version

**Yes — accepted.**

```json
"source_schema_version": "UNKNOWN"
```

Server default: `source_schema_version or "UNKNOWN"` (**ES-063**). Prefer a real workbook/schema id when known.

---

## 6. BELOW BASE (spin posture and amount)

Implementation: `pipeline.py` (planned → live), `get_posture`, `bet_for_posture`.

| Situation | Decision `planned` / notes | Spin `posture` | Spin amount |
|---|---|---|---|
| Engine selects BELOW BASE **and** `confirmed_below_base` set **and** `"below_base"` ∈ `active_postures` | `below_base` | `below_base` | `confirmed_below_base` |
| Engine selects BELOW BASE but **no** confirmed amount | may still plan `below_base` | **`base`** | **`confirmed_base`** |
| Amount set but **`below_base` omitted** from `active_postures` | may still plan `below_base` | **`base`** (not executable) | **`confirmed_base`** |

### Answers

1. **When BELOW BASE is selected but no amount is confirmed:** spin returns posture **`base`** and amount **`confirmed_base`** (execution fallback; decision may still show planned `below_base`).
2. **If `below_base` is omitted from `active_postures`:** the engine may still **plan** BELOW BASE for bridges, but spins **will not** execute `below_base` — they resolve to **`base`**.

To actually play BELOW BASE, send **both**:

- `confirmed_below_base`, and  
- `"below_base"` in `active_postures`  

(or omit `active_postures` and send the amount so the ladder auto-includes it).

---

## Quick conversion cheat sheet

| Sheet / Lookup | Send to API |
|---|---|
| Ending click 31 | `"row_17": 31`, `"prev_ending_click": 31` |
| Density fraction 0.6 | `"primary_density_pct": 60.0` |
| Density range `0-10` | Do not put in `row_18`; omit range for now |
| Missing secondary density | omit / `null` (not `0`) |
| `1*138; 2*95` | `["1*138", "2*95"]` |
| One row_2 cell | `["token"]` or split list |
| Primary + secondary pockets | one `pockets: ["7-17", "100-117"]` |
| No schema version | `"source_schema_version": "UNKNOWN"` |

---

## Open product risks (not API blockers)

1. Lookup “Spins (match plays)” vs **ES-007** click meaning for row 17 — owner should align sheets if labels conflict.  
2. Fraction vs percent for density — **percent on the wire**.  
3. Pocket primary/secondary collapsed into one `pockets[]` until API adds categories.

Flutter may proceed with the data-entry workflow using these mappings.
