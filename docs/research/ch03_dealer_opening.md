# Chapter 3 — Dealer (BN) opening and post-draw equity

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Headline findings; implementation detail lives in the handoff docs.

**Ledger role.** Claims the **only-BN-can-open / no caller** slice as solved, and owns showdown + M2 betting + **non-bluff EV by class × d** + **post-draw cap / 3-bet** + **Ring 1 bluff 3-bet indifference** for **BN vs 2:1 drawers**.

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

**Bluff delta comes next.** This table is the honest cell. Later work can add miss stabs, BN check-mixes (Stage C), and pair `d≠3` concealment, and report ΔEV against these numbers — not a new baseline. CO return-to-actor bluffs after a BN open live in [Ch.5 §5.2](ch05_later_seats.md). The §3.4 grid is **bet+1** (call the raise); 3-bet / cap is §3.5 and the Ring 1 bluff mix is §3.6 — **neither** is already in these cells.

---

## 3.5 Post-draw cap (bet + 3 raises)

On the raise node — BN has value-bet two pair+ and the 2:1 caller has raised with a made straight+ — full cap is four $4 increments each (pot **$38** vs today’s **$22** call-it-down). Combo-weighted P(node) ≈ **0.19** under locked draws.

CLI: `analyze-postdraw-cap`. Detail: [../NEXT_STAGE_POSTDRAW_CAP.md](../NEXT_STAGE_POSTDRAW_CAP.md). Fixture: `tests/fixtures/validation/postdraw_cap_summary.json`.

**BN vs the raise** (unilateral Δ vs a caller who caps SF and calls otherwise):

| BN final | Action | Δ 3-bet vs call |
| --- | --- | ---: |
| Two pair / trips | Call (no bluff 3-bet) | −4.28 |
| Straight | **Call** (broadway A is a thin 3-bet) | −1.81 |
| Flush (any high) | **3-bet** | +2.17 |
| Boat / quads / SF / five aces | **3-bet** | +3.47 |

**Caller vs a 3-bet:** fold a non-SF into BN boat+ (and, unilaterally, into BN flush+); cap SF. Do not cap a straight or flush into boats.

Call-it-down **understates** BN EV on this node for flush+ (node EV_bn −5.32 → about −5.00 if BN 3-bets flush+ and the caller still calls). It does not rewrite §3.4.

That value line is **not** Nash: vs a flush+ 3-bet, the caller’s best response is already fold non-SF, which then invites bluff 3-bets with two pair/trips. Ring 1 pins the mix that makes flushes indifferent (§3.6). Ring 2 (node Nash) is a later ticket: [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md).

---

## 3.6 Post-draw bluff 3-bet (Ring 1)

On the same raise node as §3.5, BN 3-bets flush+ always, calls straights, and 3-bets two pair/trips with frequency **β** (else **fold**). Caller SF caps; flushes are the call-vs-fold indifference target. Root-find, not hand-tune.

CLI: `analyze-postdraw-bluff`. Detail: [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md). Fixture: `tests/fixtures/validation/postdraw_bluff_summary.json`.

Seed 20260902, combo-weighted locked draws, 7,559 node deals:

| Quantity | Value |
| --- | ---: |
| β* = P(3-bet \| two pair or trips) | **0.0155** |
| α* = air share of 3-bets | **0.102** (solver; not the ~9% polar sketch) |
| Flush EV_call − EV_fold | **0.00** (indifferent) |
| Straight vs 3-bet | still **fold** |
| SF vs 3-bet | still **cap** |
| Node EV_bn at β* | −5.11 |
| Δ vs call-it-down | **+0.21** |
| Δ vs no-air flush+ 3-bet (fold non-SF) | **+0.26** |

Boat+-only value needs more air (α* = 0.15). Family-level flush indifference blends ace-high (prefer call) with lower flushes (prefer fold). §3.4 / §3.5 tables do **not** already include these bluff 3-bets.

---

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/showdown_matrix.py` | Showdown matrix |
| `src/fivecarddraw/validation/postdraw_betting_m2.py` | M2 face-pair grid + cap street helper |
| `src/fivecarddraw/validation/postdraw_nonbluff_ev.py` | Non-bluff class × d EV |
| `src/fivecarddraw/validation/postdraw_cap.py` | Post-draw 3-bet / cap on the raise node |
| `src/fivecarddraw/validation/bluff_indifference.py` | Reusable indifference helpers (`strategy_ev`, `indifference_root`) |
| `src/fivecarddraw/validation/postdraw_bluff.py` | Ring 1 polar 3-bet mix on the raise node |
| Matching fixtures + `tests/test_showdown_matrix.py`, `tests/test_postdraw_m2.py`, `tests/test_postdraw_nonbluff_ev.py`, `tests/test_postdraw_cap.py`, `tests/test_postdraw_bluff.py` | CI |
