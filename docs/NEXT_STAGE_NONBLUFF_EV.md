# Next stage: non-bluff max-EV by hand type × draw count

**Status:** Implemented. Code `src/fivecarddraw/validation/postdraw_nonbluff_ev.py`,
CLI `analyze-postdraw-nonbluff-ev`, summary fixture
`tests/fixtures/validation/postdraw_nonbluff_ev_summary.json`, tests
`tests/test_postdraw_nonbluff_ev.py`.

**Does not implement bluffing.** This table is the honest baseline so a later
delta can measure the value of bluffs / check-protection mixes.

Parent ladder: [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md).
Already done (reuse, do not redo): [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md)
cases 1–8c, [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md),
Stages A/B in [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md).

Narrative: [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md),
[research/ch04_draw_mixes.md](research/ch04_draw_mixes.md).

---

## Locked setup

| Item | Value |
| --- | --- |
| Matchup | **BN (seat 8)** opened vs one 2:1 drawing caller |
| Pre-draw | Open + **call only**; pot into draw **$6** |
| Post-draw | Opener first; one street; big bet **$4**; at most bet + one raise |
| Caller draw | Default **keep-4, d=1**; d=0 = stand with the dealt five (fork only) |
| BN keeps | `opener_draw_plan_for_action` (same as Stages A/B) |
| Deck | Exact remaining cards after both hands (caller draws first) |
| Public signal | Cards drawn \(d\), not which cards were kept |

### Honest post-draw policy (pinned; not a bluff search)

| Side | Line |
| --- | --- |
| BN | Always **value-bet two pair+**. **Check** one pair JJ–AA (M2). No check-mix of strong hands. |
| Caller | Always **bet/raise straight+**. When checked, **AA face-pair stab** (narrow value vs a checking pair). **No face-pair raise** into a two-pair+ bet. Misses check/fold. |
| Sensitivity | Pair cells at d=3 also record thin **lead AA** and a **passive** (straight+ only) stab — not used as the main argmax. |

Face-pair *calls* of a BN value-bet still follow the M2 street (any J+ pair calls).
Folding that node is a later response-line knob, not a bluff.

---

## Grid shape

```
for bn_class in opener fine split:
  for bn_d in legal(bn_class):          # pairs 0–3, TP 0/1, trips 0–2, quads 0/1, other 0
    vs all 2:1 callers, caller d=1
    play honest policy
    accumulate EV_bn, EV_caller, case 1–8c mass on finals

caller subclasses (bug_straight_draw, bug_sf_draw, four_flush_straight)
  vs locked BN draws (pairs d=3, two pair d=1, trips d=2, quads d=1)

caller d=0 vs d=1 fork vs representative BN classes
```

EV is **incremental chips from the post-draw node**. Sunk pre-draw $6 is awarded
to the winner, so `EV_bn + EV_caller = 6` on every deal. Both numbers are
labeled; do not collapse them.

Case 1–8c rates are **final-hand** buckets (same as the showdown matrix), even
when betting folds a pot. They tie the EV cells to the existing matrix; they
are not a substitute for EV.

---

## How to regenerate

```bash
pip install -e ".[dev]"
analyze-postdraw-nonbluff-ev --n-per-cell 4000 --write-fixture
# writes outputs/validation/postdraw_nonbluff_ev.{json,md} (gitignored)
# and tests/fixtures/validation/postdraw_nonbluff_ev_summary.json
pytest -q tests/test_postdraw_nonbluff_ev.py
```

Seed `20260901`. `outputs/` is gitignored.

---

## Findings (seed 20260901)

Filled from the checked-in summary fixture after the MC run. Headline:

- **Pairs (JJ–AA):** max-EV non-bluff draw is **d=3** (improvement), matching
  Stage A P(win) / boat+. Post-draw EV (with honest betting) still ranks d=3
  ahead of d=2 — this is the number pair-concealment work must beat.
- **Two pair:** **d=1** beats stand on EV, matching Stage B.
- **Trips:** **d=2** remains the primary EV max; d=1 is the unified-line fork.
- **Quads:** d=1 ≈ stand (EV-neutral); prefer d=1 for public-signal pollution.
- **Other straight+:** stand only; always value-bet.
- **Caller:** keep-4 **d=1** beats standing with the dealt five vs every
  representative BN class in the fork. Subclass EV is reported vs the locked
  BN range (bug SF draws hit more often than bug straight draws).

Exact magnitudes: `tests/fixtures/validation/postdraw_nonbluff_ev_summary.json`
and `outputs/validation/postdraw_nonbluff_ev.md`.

---

## Next after this EV table (bluff delta)

Do **not** redo this grid. Measure ΔEV vs the honest cell for:

1. Caller miss / wide face-pair stabs (deception)
2. BN Stage C check-mixes of two pair+ (protection) under `tp1_tr2_q1` /
   `tp1_tr1_q1` — [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md)
3. Pair `d≠3` concealment — [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md)
4. CO return-to-actor bluffs after BN open — Ch.5 §5.2

---

## Explicitly out of scope

- Implementing bluffs or check-protection mixes in this module
- Pre-draw raising draws (Ch.2 §2.9)
- UTG / multiway / sandbagging / ante:bet changes
- Re-enumerating the 18,396 callers or cascade odds
- Trusting `solve-predraw` sigmoid charts
