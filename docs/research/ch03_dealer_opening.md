# Chapter 3 — Dealer (BN) opening and post-draw equity

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Headline findings; implementation detail lives in the handoff docs.

**Ledger role.** Claims the **only-BN-can-open / no caller** slice as solved, and owns showdown + M2 betting + **non-bluff EV by class × d** for **BN vs 2:1 drawers**.

---

## 3.1 Folded-to-BN sanity (solved slice)

When seats 1–7 cannot open and BN holds an open-legal made hand with **no** 2:1 drawing caller behind: EV(open) ≈ +$2 ante pot; pass = 0. Non-open-legal hands cannot open.

This closes the “naked steal” band in the [ledger](INDEX.md#solve-progress-ledger).

---

## 3.2 Showdown vs 2:1 drawers

Fine opener rows (JJ / QQ / KK / AA / two pair / trips / straight / flush / …) vs the 18,396 callers after documented discard policies. Exact remaining deck once both hands known. CLI: `analyze-showdown-matrix`. Detail: [../NEXT_STAGE_SHOWDOWN_MATRIX.md](../NEXT_STAGE_SHOWDOWN_MATRIX.md).

Caller inventory and procedures: [Ch.2](ch02_drawing_callers.md).

---

## 3.3 Post-draw betting (M2)

With pairs drawing three and opener (BN) acting first: **checking JJ–AA** beats leading for value against this drawer; face-pair stabs by the drawer should stay **narrow** (AA, maybe KK). CLI: `analyze-postdraw-m2`. Detail: [../POSTDRAW_M2_FACE_PAIR_GRID.md](../POSTDRAW_M2_FACE_PAIR_GRID.md).

---

## 3.4 Non-bluff max-EV by class × cards drawn

Heads-up laboratory: BN opened, one 2:1 caller (call-only pre-draw → pot $6; big bet $4; BN first). Honest line: BN value-bets two pair+ and **checks** one pair; caller value-bets/raises straight+, stabs **AA** when checked, never raises a face pair. **No bluffs and no check-protection mixes.**

CLI: `analyze-postdraw-nonbluff-ev`. Detail: [../NEXT_STAGE_NONBLUFF_EV.md](../NEXT_STAGE_NONBLUFF_EV.md). Fixture: `tests/fixtures/validation/postdraw_nonbluff_ev_summary.json`.

**Best non-bluff draw (BN EV vs the 2:1 set, caller keep-4 d=1; seed 20260901, 4k deals/cell):**

| BN class | Chip-max d | EV_bn | Honest post-draw |
| --- | ---: | ---: | --- |
| Pair JJ–AA | **stand (d=0)** | JJ +3.56 / AA +2.68 | Check the pair; bet if it improves to two pair+ |
| Two pair | **d=1** | +2.10 | Always value-bet |
| Trips | **d=2** (d=1 unified-line fork) | +2.33 | Always value-bet |
| Quads | stand ≈ **d=1** (prefer d=1 for signal) | ~+8.4 | Always value-bet |
| Straight | Stand | +3.80 | Always value-bet (loses some case-2 pots) |
| Flush+ | Stand | +7.8 to +8.5 | Always value-bet |

**Pairs nuance.** Drawing three **raises P(win)** (JJ 0.59 → 0.62) but **lowers chips**, because improved two pair+ auto-bet into the caller’s ~34% straight+. Stages A/B still lock pairs at **d=3** so they do not pollute public d=0 with pat straight+. Among drawing options, d=3 still ≥ d=2 for AA/JJ — that is the concealment bar.

Caller keep-4 **d=1** beats standing with the dealt five (ΔEV_caller about +$2–4 vs representative BN classes). EV is reported for **both** seats (`EV_bn + EV_caller = $6` sunk pot). Case 1–8c mass is attached to the same deals as a link to §3.2, not as a substitute for EV.

**Bluff delta comes next.** This table is the honest cell. Later work can add miss stabs, BN check-mixes (Stage C), and pair `d≠3` concealment, and report ΔEV against these numbers — not a new baseline. CO return-to-actor bluffs after a BN open live in [Ch.5 §5.2](ch05_later_seats.md).

---

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/showdown_matrix.py` | Showdown matrix |
| `src/fivecarddraw/validation/postdraw_betting_m2.py` | M2 face-pair grid |
| `src/fivecarddraw/validation/postdraw_nonbluff_ev.py` | Non-bluff class × d EV |
| Matching fixtures + `tests/test_showdown_matrix.py`, `tests/test_postdraw_m2.py`, `tests/test_postdraw_nonbluff_ev.py` | CI |
