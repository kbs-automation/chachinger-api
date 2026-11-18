# Confirmation reply — pricing split & checkpoints

Thank you. We confirm the same direction, with your clarifications accepted.

---

## Confirmed

1. **Entertainment** — keep today’s Entertainment-map pricing. Percentages are planned wager exposure, not loss probability.

2. **Mission** — cards will quote the Mission-authorized destination/endpoint and the final dollar wager per included click (after posture, BELOW BASE, depth limits, and safety), using the same confirmed ladder and the same decision/configuration/financial snapshot as execution. Bridge and re-arm clicks included where authorized. No Entertainment endpoints for Mission routes. No silent higher-wager substitution.

3. **Full-route vs remaining cost** — before play: quote from click 1. During play: continuation quotes show remaining planned cost from the next unplayed click; already-wagered amounts stay separate. Recalculate when route, confirmed wagers, balance, budget, or safety state changes. Reject stale quotes before accepting the affected selection.

4. **Percentage definitions** — unchanged:
   - Planned Budget Exposure = planned route wager ÷ selected budget × 100  
   - Planned Balance Exposure = planned route wager ÷ current balance × 100  
   If the UI keeps the word “Risk,” it means planned balance exposure only.

5. **Checkpoints** — separate workstream from Mission card pricing, but existing required checkpoint protection must not be removed, bypassed, or postponed in Mission execution while we build the new cards.

6. **Mobile/API** — Mission API sample first (including one bridge/BELOW BASE example and one safety-downgrade example), then Flutter Mission pricing UI changes.

**Direction confirmed:** Entertainment stays; Mission gets engine-aligned pricing; checkpoint protection remains a required, separately tracked integration.

---

## Checkpoint enforcement — what exists today

| Item | Status today |
|---|---|
| Full checkpoint product (pause spins, collect settled balance, recovery from actual coin-in/payouts/deposits, Watch / Continue / Hard Exit at checkpoint, persist checkpoint state) | **Not implemented** as an API/product surface |
| Mission safety inputs that can reduce wager authority (e.g. containment / PCS-unstable style ceilings on the Mission path) | **Partial** — used inside Mission wager/safety logic, not a player-facing checkpoint flow |
| Hard Exit / play or session stop that blocks further spins | **Available** on existing play/session rules |
| Route cards using planned wagers vs checkpoints using actual settled figures | **Agreed principle** — cards ≠ checkpoints; neither replaces the other |

So: we are **not** turning off any live Mission safety/Hard Exit behavior to ship Mission card pricing. What is still missing is the **full checkpoint integration** you described (settled-balance checkpoint UX/API). That remains required and separately tracked.

---

## Delivery sequence

| Step | Delivery | Notes |
|---|---|---|
| **A** | Mission route/exposure API contract + sample JSON | Includes bridge/BELOW BASE example and safety-downgrade example |
| **B** | Backend Mission-priced cards (staging, behind mission flag) | Entertainment path unchanged |
| **C** | Flutter Mission pricing UI after sample + staging check | No Mission display change before API sample |
| **D** | Checkpoint integration (separate track) | Actual settled wagers/balances; Continue / Watch / Hard Exit; does not replace route-card planned exposure |

Steps A–C do not remove or bypass checkpoint requirements. Step D delivers the full checkpoint product and wires it so Mission execution keeps the required protection.

---

## Next action from our side

Proceed to draft the Mission API sample (bridge/BELOW BASE + safety downgrade), then implement Mission-aligned card pricing on staging while Entertainment remains as-is and checkpoint work stays on its own track.
