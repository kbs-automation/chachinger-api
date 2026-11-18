# Simple summary for client — Mission exposure vs today’s cards

## What you asked for

The percentages on the route cards should show the **real cost of the route the engine will actually let the player follow** — same wagers, same endpoint, same safety limits.

---

## What happens today

| Area | Today |
|---|---|
| Route cards | Priced from the **Entertainment** pocket map (fixed depths like early / mid / deep) |
| Mission engine | Already helps decide **authority** on spins (continue / exit, posture, bridges) |
| Gap | Card percentages and Mission authority are **not yet the same calculation** |

So the formulas we explained earlier are correct for **today’s cards**, but they do **not** yet fully match Mission-authorized play.

---

## What we agree to do

**Keep Entertainment as-is** for Entertainment guidance.

**For Mission mode, change the cards so they use Mission data:**

1. Real route endpoints from Mission targets / Hard Exit  
2. Dollar cost from the final allowed wager map (including BELOW BASE bridges and safety cuts)  
3. Exposure = that cost ÷ budget, and ÷ current balance  
4. Same wager ladder for the quote and for real play  
5. Same decision version from quote → route choice → Begin Play (reject if out of date)

**Checkpoints** (pause, settled balance, Continue / Watch / Hard Exit during play) are a **separate later phase**. They are not required to fix the card pricing first.

---

## Simple impact

| Who | Impact |
|---|---|
| **Players in Entertainment** | Little change |
| **Players in Mission** | Cards and % will match what they are actually allowed to bet and how far they may go |
| **App (Flutter)** | Wait for the new Mission card/API shape before changing Mission screens |
| **Backend** | New Mission pricing path for cards; keep Entertainment path separate |

---

## What we need from you

Please confirm:

1. Entertainment cards stay on the current method.  
2. Mission cards move to Mission-authorized pricing (as above).  
3. Checkpoints are Phase 2.  
4. Flutter Mission UI changes only after we share the agreed API sample and staging check.

Once you confirm, we will draft the Mission route/exposure API contract next (before app implementation).
