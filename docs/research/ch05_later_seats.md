# Chapter 5 — Toward cutoff, hijack, and sandbagging

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Planned — not started. **Prerequisite:** finish [Ch.2 §2.9](ch02_drawing_callers.md) (strong draws: call / raise / mix) before CO represent-bluffs.

**Ledger role.** Owns the **CO can open (~4.9%)** slice after seats 1–6 fold, then climbs into the **early-six can open (~78%)** mass starting at **HJ (seat 6)**. Also owns **CO continue lines as a non-opener** when BN has opened.

---

## 5.1 High-level seat climb

1. Finish Ch.2 raise/call mixes for strong draws (blocks credibility of bluffs below).
2. Port BN validation → **CO (seat 7)** open/pass when seats 1–6 fold (CO can open ~4.9%).
3. Write the consolidated **last-two-seats (CO + BN) opening** plan ([Ch.1 §1.5](ch01_roadmap.md)).
4. Study **CO bluff-representation** when CO *cannot* open (§5.2).
5. Open **HJ (seat 6)**; introduce sandbagging hypotheses carefully.
6. Climb earlier seats (LJ → UTG) only with raise-pressure and post-draw numbers in hand.

Do not begin UTG re-solve while BN-vs-drawer and CO represent work are still open, unless product explicitly re-prioritizes.

---

## 5.2 Next step — CO bluff-representing a strong draw (planned)

### Line under study

| Seat | Action / holding |
| --- | --- |
| Seats 1–6 (UTG…HJ) | Fold / cannot open |
| **BN (seat 8)** | **Opens** (open-legal) |
| **CO (seat 7)** | Holds a **non-open-legal** weak hand: **pair below JJ**, or a **high-card** hand (no strong Ch.2 draw) |

**Product question:** Should CO ever **bluff** by **calling or raising** and then **drawing one**, to **represent** a strong one-card drawing hand (bug SF / OESFD / etc. from Ch.2)?

Motivation: once Ch.2 establishes how often real strong draws call vs raise, CO’s trash can try to mimic that public story (especially the public `d=1` draw). Without a credible raise/call mix among true draws, the bluff is easier to punish.

### Rules pin (do before coding)

Pre-draw order is UTG → … → CO → BN. CO normally acts **before** BN’s open. Document explicitly which of these the study uses:

1. **Return-to-actor model** — CO passed when first to act among the last two; BN opens; CO still gets a chance to call/raise the open; or
2. **Alternate framing** — an earlier seat opened and CO cold-calls/raises (not the BN-steal line); or
3. **Other house rule** — pin to `GameConfig` / response solver semantics.

Product intent is (1) or the nearest rules-faithful equivalent: **CO continues without openers, as a bluff, after BN has opened and the early six are gone.**

### Candidate CO holdings (non-draws)

| Bucket | Examples | Draw action if continuing |
| --- | --- | --- |
| Underpair | 22–TT | Typically draw 3 for real equity — **bluff line instead forces draw 1** to look like a keep-4 draw |
| High card / no pair | Ace-high, king-high, etc. | Same: natural improvement ≠ one-card straight+ story |

Compare EV of:

- Fold (default)
- Call + draw 1 (represent)
- Raise + draw 1 (represent)
- Honest lines (e.g. call/fold + draw 3 with underpair) as baselines

### Dependence on Ch.2 §2.9

| If strong draws mostly… | Then CO represent-bluff… |
| --- | --- |
| Call | Call-bluffs are the main story; raise-bluffs look like made hands or errors |
| Raise | Raise-bluffs pick up fold equity vs BN; call-bluffs look weak |
| Mix by class/outs | CO should match the **same mix shape** on the public line (especially `d=1`) |

### Out of scope for the first CO bluff grid

- Full CO open/pass chart for open-legal hands (separate §5.1 item)
- Multiway pots
- Sandbagging open-legal monsters on CO
- HJ/UTG

### Deliverables (when implemented)

- Scenario doc pin (rules model) + EV grid code/CLI
- Fixture + pytest
- Findings in this chapter; ledger note if a new deal-share slice is claimed
