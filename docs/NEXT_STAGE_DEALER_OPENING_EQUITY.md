# Next stage: dealer-seat opening equity validation data

**Status:** Planned handoff for a fresh agent. Do not trust current opening charts as strategy truth until this validation layer exists.

## Goal

Create **ground-truth (or near ground-truth) validation data** for opening decisions from the **dealer seat** at current stakes, to drive and accept future solver improvements.

At `$0.25` ante × 8 / `$2` small bet, when folded to the dealer, the decision is much smaller than UTG:

- 0 players left to act behind
- Jacks-or-better still required to open
- Open EV is mostly: steal the `$2` pot vs get called/raised by nobody (everyone already folded)

This seat should be **solvable to high confidence** and become the first acceptance fixture for the solver.

## Game constants (do not reinvent)

| Parameter | Value |
| --- | --- |
| Players | 8 |
| Ante | $0.25 (starting pot $2) |
| Small / big bet | $2 / $4 |
| Openers | Jacks or better |
| Bug | Ace, or complete straight / flush / SF |
| Blinds | None |
| Pre-draw action | UTG = left of dealer; dealer acts last |
| Sandbagging | Out of scope for this stage |

## Why dealer-first

1. **Smaller tree:** folded-to-dealer open is nearly a binary open/pass over open-legal hands (no multiway steal math).
2. **Known failure mode elsewhere:** current position-by-position opener is too loose UTG (e.g. QQ open 100%). See “Known combinatorial facts” below.
3. **Acceptance ladder:** lock dealer charts first → use them to calibrate response/raise models → only then revisit early seats.

## Deliverables for this stage

1. **Combo-weighted deal stats** (exact or Monte Carlo with card removal), written to `outputs/validation/`:
   - P(open-legal), P(JJ/QQ/KK/AA), P(two pair+), P(better than JJ/QQ)
   - With hero holding a given class (especially dealer open candidates)
2. **Dealer opening equity table** for open-legal abstract classes (at least: `pair_J`, `pair_Q`, `pair_K`, `pair_A`, `two_pair`, `trips+`, and strong bug draws if ever open-legal — draws usually are not):
   - EV(open) vs EV(pass=0) when folded to dealer
   - Steal always succeeds in the pure “folded to dealer” node; document any model of *prior* folds separately if needed
3. **Acceptance criteria (mathematical), checked in CI/tests**, for example:
   - Every open-legal made hand folded-to-dealer has EV(open) ≥ 0 (should win the antes)
   - Non-open-legal hands cannot open
   - Reported frequencies match enumeration within tolerance
4. **Machine-readable fixtures** (CSV/JSON) that future solver changes must not regress.

Optional stretch: compare dealer open frequencies from `solve-predraw` against the validation table and fail if they disagree beyond tolerance.

## Known combinatorial facts (from prior agent work)

Unconditional (full `C(53,5)` with bug):

| Event | ≈ Frequency |
| --- | --- |
| Open-legal (jacks or better) | 22.40% |
| Pair AA | 4.81% |
| Pair KK / QQ / JJ each | 3.13% |
| Two pair or better | 8.21% |
| Better than QQ (KK+ or two pair+) | 16.15% |
| Better than JJ (QQ+ or two pair+) | 19.27% |

Given hero holds QQ (card removal, sampled):

| Event | ≈ Probability |
| --- | --- |
| Random later hand already beats QQ | 13.4% |
| ≥1 of 7 behind already beats QQ | ~63.5% |
| All 7 not open-legal (opener-only steal) | ~19.4% |

**Implication for UTG (not this stage, but do not “fix” by loosening dealer):** opening QQ UTG 100% is not credible once raise frequency from dominating hands / big draws is modeled honestly. User critique: call-only is not “break-even/small loss,” and face-raise may be ~55% with steal ~20%, making QQ strongly −EV UTG. Future early-position work must use combo-weighted raise/call mixes, not sigmoid score proxies alone.

## Suggested implementation sketch

```
src/fivecarddraw/validation/
  deal_stats.py      # exact/MC frequencies
  dealer_open_ev.py  # folded-to-dealer EV by class
  report.py          # write outputs/validation/*
tests/test_dealer_validation.py  # acceptance criteria
```

CLI idea: `validate-dealer-open -o outputs/validation`

## Out of scope for this stage

- Re-solving full 8-seat opening charts
- Sandbagging
- Post-draw
- Full multiway Nash
- Changing ante:bet ratio

## Branching note

PR #1 (`Five-card draw pre-draw solver v1`) is **merged** to `main`. Start the next stage from updated `main` on a new branch, e.g. `cursor/dealer-open-validation-<suffix>`.
