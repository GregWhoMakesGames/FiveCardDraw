# Chapter 3 — Dealer (BN) opening and post-draw equity

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Stub — expand in a later revision. Headline findings only.

**Ledger role.** Claims the **only-BN-can-open / no caller** slice as solved, and owns showdown + M2 betting for **BN vs 2:1 drawers**.

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

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/showdown_matrix.py` | Showdown matrix |
| `src/fivecarddraw/validation/postdraw_betting_m2.py` | M2 face-pair grid |
| Matching fixtures + `tests/test_showdown_matrix.py`, `tests/test_postdraw_m2.py` | CI |
