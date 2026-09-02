# Chapter 1 — Research roadmap: order of operations

> Shared seat map and deal-share ledger: **[INDEX.md](INDEX.md)**.  
> Do not restate percentages here — link the ledger and describe *what we do* in each slice.

This chapter is the intended **sequence of research**, not a claim that every step is finished.

---

## 1.1 Build base functionality (done — maintain forever)

**Goal.** Deterministic testing of probabilities and simulations so every later claim can be pinned in CI.

| Capability | Role |
| --- | --- |
| Cards + bug evaluation | Correct category ranking (five aces, SF, quads, …) |
| Jacks-or-better open check | Legal openers vs drawing-only hands |
| Deal / combo enumeration | Exact frequencies over \(C(53,5) = 2{,}869{,}685\) hands |
| Outs / keep-4 machinery | One-card improvement with documented denominator (/48 vs exact remaining deck) |
| Monte Carlo deal generators | Opener × disjoint caller deals with fixed seeds |
| Pytest fixtures under `tests/fixtures/validation/` | Lock numbers within tolerance |

Without this layer, “GTO charts” cannot be audited. With it, disagreements become bugs or model choices, not folklore.

**Solve share:** enables every later row in the [solve-progress ledger](INDEX.md#solve-progress-ledger); does not itself close a deal-share slice.

---

## 1.2 Solve the button (BN, seat 8) without sandbagging, including post-draw play (in progress)

**Why BN first.** When seats 1–7 pass, the button faces open-or-pass for open-legal hands (steal the $2 ante pot). The *interesting* EV is not the naked steal — it is **opening into callers**, especially **non-opening drawing hands** that correctly call (and sometimes raise) because they have enough outs ([Ch.2](ch02_drawing_callers.md)).

Map onto the ledger:

| Ledger slice | Chapter work |
| --- | --- |
| No legal opens (~13%) | Trivial / house redeal — **solved** |
| Only BN can open, no 2:1 caller | Folded-to-BN sanity: open made jacks+ for +$2 — **solved** ([Ch.3](ch03_dealer_opening.md)) |
| Only BN can open, ≥1 good calling hand | Drawing inventory + showdown + post-draw + draw mixes — **in progress** (Ch.2–4) |

Work already on the hard BN ladder:

| Stage | Status | One-line result |
| --- | --- | --- |
| Drawing-call odds | Done | 18,396 combos clear 2:1 on outs/48 ≥ 1/3 |
| Cascade odds | Done | Second drawing caller is rare (~0.031% of deals) |
| Showdown matrix | Done | Fine opener classes × 2:1 drawer after documented draws |
| Post-draw M2 betting | Done | Default: check JJ–AA; drawer face-pair stabs stay narrow |
| Draw-count grid (A/B) | Done | Lock two pair `d=1`, quads `d=1`, pairs `d=3`; trips fork |
| Check-mix protection (C) | **Next** | Re-run under post-B draws (old fixture used two pair stand) |
| Pair concealment | After C | Only if post-draw EV still prefers pair `d=3` |

**Explicit v1 omission:** sandbagging (checking open-legal monsters hoping to raise later).

---

## 1.3 Solve the cutoff (CO, seat 7) the same way (planned)

Same template as BN: open/pass for open-legal classes, response vs open, then post-draw vs drawing continues — still **without** sandbagging in the first pass. CO has one seat behind (BN), so open frequencies tighten relative to the dealer steal, but the drawing-caller technology carries over.

**Ledger slice:** “CO can open” after seats 1–6 unable (~4.9%) plus CO-open lines inside the early-six mass later.

**Also planned (after Ch.2 raise/call mixes):** return-to-actor line — CO passed for lack of a legal opener; BN opens; others fold; should CO ever **call/raise with less than a strong draw** as a bluff? See [Ch.5 §5.2](ch05_later_seats.md).

---

## 1.4 Deal-share framing (read the ledger)

Coarse and granular percentages, formulas, and “percent of the game solved” narrative live in the **[solve-progress ledger](INDEX.md#solve-progress-ledger)** so every chapter and agent shares one table.

Summary for this roadmap:

1. Close **no legal opens** and **naked BN steals** first (already done).
2. Finish **BN vs 2:1 drawers** (Ch.2–4) — small absolute %, high strategic leverage.
3. Port the template to **CO**, then climb to **HJ (seat 6)** and earlier seats (~78% early-six mass).

---

## 1.5 Plan the last two hands’ opening (planned write-up)

After BN and CO validation numbers exist, consolidate in [Ch.5](ch05_later_seats.md) / a short late-position note:

- Which classes **open** for value vs steal on CO and BN
- Which classes **pass** despite being open-legal (if any, before sandbagging)
- How often BN faces a CO open vs a free steal
- How drawing-call ranges attach to each line

---

## 1.6 Hijack (HJ, seat 6): opening range and first sandbagging questions (planned)

Seat **6 (HJ)** is where multiway pressure and **sandbagging** start to matter in earnest:

- What does HJ open?
- Should any open-legal hands **check** hoping to play a bigger pot later?
- How do CO/BN continue ranges change once HJ opens are credible?

Do **not** expand that plan until late-position non-sandbagging work is done (Stage C check protection is done). Detail TBD in [Ch.5](ch05_later_seats.md).

---

## 1.7 Immediate research queue (ordered)

1. **Ch.2 §2.9** — Strong draws: always call, always raise, or mix (BN-open laboratory first).
2. **Ch.5 §5.2** — After BN opens (CO had passed with no legal opener; others fold): call/raise with less than a strong draw as a bluff? (depends on §2.9).
3. Pair concealment (Ch.4 leftover) after the `d=3` vs `d=2` EV confirm; Ch.3 bluff 3-bet Ring 1 **after Stage C** (trips-only air, split by public \(d\)).
4. CO open/pass chart; then HJ sandbagging.

## 1.8 Later (not scheduled in this draft)

- Full UTG / early-seat re-solve with combo-weighted raise pressure
- Multiway post-draw pots
- Ante:bet ratio sweeps
- Heavier equilibrium methods (e.g. CFR) on abstracted trees if grids stall
