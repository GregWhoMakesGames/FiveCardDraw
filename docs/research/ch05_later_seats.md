# Chapter 5 — Toward cutoff, hijack, and sandbagging

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Planned — not started. **Prerequisite:** finish [Ch.2 §2.9](ch02_drawing_callers.md) (strong draws: call / raise / mix) before CO bluffs with weaker hands.

**Ledger role.** Owns the **CO can open (~4.9%)** slice after seats 1–6 fold, then climbs into the **early-six can open (~78%)** mass starting at **HJ (seat 6)**. Also owns **CO continue lines as a non-opener** when BN has opened.

---

## 5.1 High-level seat climb

1. Finish Ch.2 raise/call mixes for strong draws (defines the real continue range CO might bluff into).
2. Port BN validation → **CO (seat 7)** open/pass when seats 1–6 fold (CO can open ~4.9%).
3. Write the consolidated **last-two-seats (CO + BN) opening** plan ([Ch.1 §1.5](ch01_roadmap.md)).
4. Study **CO bluffs with weaker-than-draw hands** after BN opens (§5.2).
5. Open **HJ (seat 6)**; introduce sandbagging hypotheses carefully.
6. Climb earlier seats (LJ → UTG) only with raise-pressure and post-draw numbers in hand.

Do not begin UTG re-solve while BN-vs-drawer and CO bluff work are still open, unless product explicitly re-prioritizes.

---

## 5.2 Next step — CO bluffing after BN opens (planned)

### Locked rules model: return-to-actor

Pre-draw order is UTG → … → **CO → BN**.

**Return-to-actor model (this study):**

1. Seats 1–6 (UTG…HJ) fold / cannot open.
2. **CO** is first to act among the remaining seats and **passes because CO does not have a legal opener** (not a sandbag of an open-legal hand).
3. **BN** opens (open-legal).
4. **All other players fold** — action is heads-up: BN (opener) vs CO.
5. Action **returns to CO**, who may now **fold, call, or raise** despite having been unable to open.

That pin is locked for §5.2. Do not use alternate cold-call framings unless product revisits this section.

### Investigation

In this heads-up return-to-actor line we already expect (and will quantify in [Ch.2 §2.9](ch02_drawing_callers.md)) that **strong drawing hands** — bug SF / bug straight / four-flush-straight, etc. — **call and/or raise**.

**Question:** should CO ever **call and/or raise with less** as a **bluff** — i.e. with hands that are **not** those strong draws?

Candidate “less” holdings:

| Bucket | Examples | Notes |
| --- | --- | --- |
| Underpair | 22–TT | Cannot open; weak showdown value vs BN’s open-legal range |
| High card / no pair | Ace-high, king-high, etc. | Cannot open; even weaker |

Compare EV of fold (default) vs call vs raise for those buckets, using the Ch.2 strong-draw continue policy as the **value** part of CO’s range (so bluffs, if any, are balanced against real draws). Optional later: whether a bluff continue should **draw one** to match the public `d=1` story of keep-4 draws.

### Dependence on Ch.2 §2.9

| If strong draws mostly… | Then CO bluffs with “less”… |
| --- | --- |
| Call | Call-bluffs are the natural disguise; raise-bluffs look like made strength or errors |
| Raise | Raise-bluffs gain fold equity vs BN; call-bluffs look like the weak side of the draw range |
| Mix by class/outs | Bluff frequencies should follow the **same mix shape** as true draws on this line |

Without §2.9, we do not know what “representing a draw” even means on this street.

### Out of scope for the first CO bluff grid

- Full CO open/pass chart for open-legal hands (separate §5.1 item)
- Multiway pots (someone besides CO continues vs BN)
- Sandbagging open-legal monsters on CO
- HJ/UTG

### Deliverables (when implemented)

- EV grid code/CLI for return-to-actor HU: BN open → CO fold/call/raise by holding bucket
- Fixture + pytest
- Findings in this chapter; ledger note if a new deal-share slice is claimed
