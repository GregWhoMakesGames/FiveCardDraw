# Frame: button open, no sandbagging

Slug: **`button_open_no_sandbagging`**. Parent: [INDEX.md](INDEX.md) research frames.

BN (seat 8) opened. Nobody sandbagged. The laboratory is BN vs drawing callers (usually one 2:1 keep-4). This is the current top-level slice for post-draw work and for button opening EV.

**How to point at a step**

- Specific: `evaluate button_open_no_sandbagging Ring 2`
- Short, when recent work is already in this frame: `evaluate Ring 2`

Mint a **new frame file** when the laboratory changes (UTG, sandbagging, CO return-to-actor). Add a row to the INDEX frames table. Do not reuse these aliases in a different frame.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Stage C** | Evaluate BN always checking two pair | Post-draw, two pair checks; trips+ still bets. Raise node is no longer two pair+. |
| **pre-C lab** | Evaluate leftover-fold polar mix while two pair still bets | Old node: two pair bets. 3-bet with frequency β, else fold. Pinned; not the current street. |
| **Ring 1** | Evaluate flush-indifference β on the raise node | Polar mix so caller flushes are call/fold indifferent. Held knobs; not Nash. On the current street this is **trips-only** air. |
| **Ring 2** | Evaluate raise-node Nash | Both sides mix. No held polar knobs. After Ring 1. |
| **Line 1** | Evaluate the BN trips-draw to post-draw action | Public \(d \in \{2,3\}\). Unimproved trips are the air. |
| **Line 2** | Evaluate the BN stand-pat post-draw action | Public \(d = 0\). No trips air; flush call vs a no-air flush+ 3-bet is already pinned. |

Detail tickets: [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md), [../NEXT_STAGE_POSTDRAW_CAP.md](../NEXT_STAGE_POSTDRAW_CAP.md), [../POSTDRAW_STRATEGY_TREE.md](../POSTDRAW_STRATEGY_TREE.md). Narrative: [ch03_dealer_opening.md](ch03_dealer_opening.md) §3.5–3.6, [ch04_draw_mixes.md](ch04_draw_mixes.md).

---

## Joker blockers and BN open/pass

**Strong drawing hand** here means a **2:1 first-call** combo from [Ch.2](ch02_drawing_callers.md): 18,396 hands (bug straight draw 11,772; bug SF draw 5,508; four-flush-straight with no bug 1,116). Those sets are disjoint from open-legal. Code: `bn_bug_conditioned_2to1_rates()` in `cascade_odds.py`.

A given seat’s five cards are uniform over \(C(53,5)\). Conditioning only on whether BN (seat 8) holds the bug is a closed form. The “any of seats 1–7” column uses independent seats \(1-(1-p)^7\); two 2:1 hands in the same deal is ~0.03% (cascade), so the union is not sensitive to that.

| BN holds the bug? | P(one seat is 2:1) | P(any of seats 1–7 is 2:1) |
| --- | ---: | ---: |
| Yes | \(1{,}116 / C(52,5) = 0.0429\%\) | **0.300%** |
| No | \(0.703\%\) | **4.82%** |
| Unconditional (ledger) | \(18{,}396 / C(53,5) = 0.641\%\) | **4.40%** |

Almost all 2:1 mass holds the bug (17,280 / 18,396). If BN has it, seats 1–7 can only show the 1,116 no-bug four-flush-straights.

**Folded-to-BN (no sandbagging).** Seats 1–7 with jacks+ would already have opened, so the open/pass node is richer in 2:1 among the hands that *can* still be out there. Independent planning with the enumerated open-legal split (bug: 106,781 / 270,725 ≈ 39.4%; no bug: 536,100 / 2,598,960 ≈ 20.6%) gives P(any 2:1 | 1–7 all unable, BN no bug) ≈ **6.0%**. A 150k-deal check sat near **6.9%** (bug-draw mass concentrates a bit when jacks+ are absent). With the bug in BN’s hand the same event is still ~**0.3–0.5%**.

### Open/pass given those odds

Antes put **$2** in the pot. Pass = 0; a naked steal is **+$2**. If a 2:1 hand calls, the post-draw node has $6 in the pot and §3.4 reports EV_bn as BN’s share of that street (`EV_bn + EV_caller = 6`). Net vs pass when called is **EV_bn − $2**, so

\[\mathrm{EV}(\mathrm{open}) = 2 + p\,(\mathrm{EV}_{\mathrm{bn}} - 4).\]

The weakest pinned non-bluff cells (locked draws, vs the full 2:1 mix) are still above the $2 steal-when-called line by enough that **even \(p=1\) stays +EV**: two pair \(d=1\) EV_bn \(+2.10\); pair-A \(d=3\) \(+2.61\); pair-J \(d=3\) \(+3.08\). At the ~5–7% call rates above, the steal dominates.

**Q3: no. There are no legal BN hands that should pass** in this frame, assuming first callers are the 2:1 set, no sandbagging, and the §3.4 / Stage C street we already have.

**Pre-draw line is locked: those 2:1 hands call, they do not raise.** No-sandbagging means BN’s range is 100% jacks+. A raise then has no fold equity worth pricing, and the 16-out majority (15,552 / 18,396) has 16/48 ≈ 33% into a $10 pot after BN continues (needs 40%). That is why every BN-vs-2:1 grid in this frame is open + call only. [Ch.2 §2.9](ch02_drawing_callers.md) stays on the queue for CO representation (and the thin 19/22-out tail), not as a way to un-open a BN hand.

### Still open in this frame (todo)

| Item | Why it is still open |
| --- | --- |
| **Ring 1** (Line 1 trips-air β) | Needed for post-draw EV vs 2:1, not for the steal-vs-call open/pass sign |
| EV vs FFS-only vs bug-draw-only | Blocker-split of §3.4; not required to sign open/pass at these \(p\) |
