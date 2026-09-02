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

## Findings (seed 20260901, 4000 deals/cell)

EV is incremental chips from the post-draw node (`EV_bn + EV_caller = $6`). Honest
policy: `lead=never|stab=AA|raise=never`.

### BN best non-bluff draw vs all 2:1 (caller d=1)

| BN class | Chip-max d | EV_bn | EV_caller | Notes |
| --- | ---: | ---: | ---: | --- |
| pair_J | **0** | +3.56 | +2.45 | d=3 EV +3.08; P(win) 0.59→0.62 while EV **falls** |
| pair_Q | **0** | +3.49 | +2.51 | d=3 +2.96 |
| pair_K | **0** | +3.60 | +2.40 | d=3 +3.09 |
| pair_A | **0** | +2.68 | +3.32 | d=3 +2.61 (within ~1 SE of stand); thin lead-AA +2.69 |
| two_pair | **1** | +2.10 | +3.90 | stand +1.62 |
| two_pair_aces_up | **1** | +2.08 | +3.92 | stand +1.75 |
| trips | **2** | +2.33 | +3.67 | d=1 +2.14; stand +1.81 |
| trips_K | **1** | +2.26 | +3.74 | d=2 +2.09 (fork noise; keep both) |
| trips_A | **2** | +2.41 | +3.59 | |
| straight | **0** | +3.80 | +2.20 | Loses to completed flush/SF (case 2) |
| flush | **0** | +7.79 | −1.79 | Beats drawer straight+ (case 1) |
| full_house / quads / SF / five aces | **0** | ~+8.4–8.5 | ~−2.4 | Quads d=1 Δ=−0.11 (EV-neutral; prefer d=1 for signal) |

**Pairs: chips vs win rate.** Under this honest line, **standing is the chip-max
non-bluff draw** for JJ–AA. Drawing three raises showdown P(win) (JJ 0.59 → 0.62)
but the extra two-pair+ hands **auto-bet** and pay off the caller’s ~34%
straight+ (raise/call). That is why Stage A’s “d=3 best improvement” does not
automatically mean d=3 best **EV**.

**Do not put pairs on public d=0 in the range.** Pat straight+ must stand; mixing
pairs into d=0 pollutes that line. Stages A/B still **lock pairs at d=3** for
construction. Among drawing options, **d=3 ≥ d=2** for AA and JJ (the
concealment bar). Pair `d≠3` mixes remain after the dedicated concealment ticket.

**Two pair / trips / quads** match A/B: two pair **d=1** (+0.48 vs stand); trips
**d=2** primary vs **d=1** unified fork; quads d=1 ≈ stand.

### Caller

Keep-4 **d=1** beats standing with the dealt five by **+$2.2 to +$4.1** EV_caller
vs representative BN classes. Subclass EV_caller vs the locked BN range
(`tp1_tr2_q1`): bug SF draw **+3.66**, four-flush-straight **+3.24**, bug
straight draw **+3.08** (SF draws hit more often).

### Case 1–8c

Same deals attach showdown-matrix case mass (final hands, not betting folds).
Example: pair_J d=3 case **8c** ≈ 0.33 (JJ loses to drawer straight+). Straight
BN EV is much lower than flush BN EV because of case **2**.


---

## Next after this EV table (bluff delta)

Do **not** redo this grid. Measure ΔEV vs the honest cell for:

1. **Post-draw cap / BN 3-bet vs call** when both have straight+ — **done**
   ([NEXT_STAGE_POSTDRAW_CAP.md](NEXT_STAGE_POSTDRAW_CAP.md)); §3.4 cells stay bet+1
2. **Post-draw bluff 3-bet Ring 1** (flush indifference on that node) —
   [NEXT_STAGE_POSTDRAW_BLUFF.md](NEXT_STAGE_POSTDRAW_BLUFF.md). Ring 2 Nash waits.
3. Caller miss / wide face-pair stabs (deception)
4. BN Stage C check-mixes of two pair+ (protection) under `tp1_tr2_q1` /
   `tp1_tr1_q1` — **done** ([NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md));
   always check two pair
5. Pair `d≠3` concealment — [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md)
   (verify pair EV `d=3` vs `d=2` first)
6. CO return-to-actor bluffs after BN open — Ch.5 §5.2

---

## Explicitly out of scope

- Implementing bluffs or check-protection mixes in this module
- Pre-draw raising draws (Ch.2 §2.9)
- UTG / multiway / sandbagging / ante:bet changes
- Re-enumerating the 18,396 callers or cascade odds
- Trusting `solve-predraw` sigmoid charts
