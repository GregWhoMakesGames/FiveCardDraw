# Frame: cutoff open, no sandbagging (seats 1–6)

Slug: **`cutoff_open_no_sandbagging`**. Parent: [INDEX.md](INDEX.md) research frames.
Ticket: [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md).
Narrative: [ch05_later_seats.md](ch05_later_seats.md) §5.1.

Seats 1–6 cannot open (0% sandbag). CO (seat 7) holds a legal hand. BN (seat 8)
is behind and, in v1, opens every legal hand if CO passes and calls every legal
hand if CO opens.

**How to point at this work:** `evaluate cutoff_open_no_sandbagging`

Code: `src/fivecarddraw/validation/cutoff_open.py`. CLI: `analyze-cutoff-open`.
Fixture: `tests/fixtures/validation/cutoff_open_summary.json`. Seed `20260907`,
n_prob=20k, n_hu=4k, n_2to1=2k.

## Product answers

1. **Open every legal class, including JJ.** EV(open JJ) = **+$1.44** vs pass = 0.
   QQ / KK / AA / two pair are also +EV (table below). None of these classes is
   −EV because BN is behind.
2. **CO should not sandbag** two pair+ or aces. Steal when BN has no legal opener
   (~72–77%) is **+$2**; P(BN legal) is only ~19–24%. Best pass line (call or
   raise-checkdown vs BN’s open) is **+$0.27 (AA)** / **+$0.36 (two pair)** —
   well below opening.

## What differs from the BN steal lab

1. **BN behind** can be open-legal (or 2:1).
2. **Draw order** if CO opens and BN calls: CO draws before BN. If a seat 1–6
   2:1 called, that caller draws first (same as M2 / §3.4). Post-draw betting
   in HU CO vs BN: left-of-dealer first live is CO, so opener-first matches.
   Fixed draw counts make the *set* of cards order-invariant; the BN-caller
   2:1 cell is still resimulated.

## v1 pins

| Item | Pin |
| --- | --- |
| Seats 1–6 | 0% sandbag (HJ still opens AA) |
| BN if CO passes | Opens every legal |
| BN if CO opens | Always *calls* every legal (does not fold, does not raise) |
| Accounting | Pass = 0; steal = +$2; fold to raise after opening = −$2 |
| Sandbag-set on CO | Two pair or better, and pair of aces |
| JJ if CO passed | Fold to a BN open (pass EV = 0 vs BN-legal too) |
| Draws | Locked `tp1_tr2_q1` (pairs d=3, two pair d=1, trips d=2, quads d=1) |
| Post-draw | Honest non-bluff; made-hand BN two pair+ continues (not the raw 2:1 M2 fold) |

## Behind CO (deal MC, 20k deals / class)

P(BN open-legal) is the unconditional ~22% with CO’s blockers. Steal is the
mass. Independent-seat `p_one_seat_2to1` (bug split) is planning only; the MC
is the pin.

| CO class | P(steal) | P(vs 2:1) | P(BN legal) | P(BN is 2:1) | P(≥1 of 1–6 is 2:1) |
| --- | ---: | ---: | ---: | ---: | ---: |
| pair_J | 0.755 | 0.035 | 0.210 | 0.005 | 0.030 |
| pair_Q | 0.755 | 0.040 | 0.205 | 0.006 | 0.033 |
| pair_K | 0.745 | 0.043 | 0.212 | 0.007 | 0.037 |
| pair_A | 0.775 | 0.031 | 0.194 | 0.005 | 0.026 |
| two_pair | 0.724 | 0.037 | 0.239 | 0.007 | 0.031 |

AA’s lower P(BN legal) and higher steal rate is the bug-as-ace / ace-blocker
split (p_co_has_bug ≈ 0.39 vs ~0.06 for JJ).

## Street EVs (locked draws, $6 pot into draw)

If CO opens: steal +$2; vs 2:1 net = EV_street − $2; vs BN legal net = EV_street − $2.
Mixture: \(0.75 \times 2 + 0.04 \times (\mathrm{EV}_{2:1}-2) + 0.21 \times (\mathrm{EV}_{\mathrm{BN}}-2)\).

| CO class | EV vs 2:1 (caller first / CO first) | §3.4 bound | EV vs BN legal | EV(open) | EV(pass) |
| --- | ---: | ---: | ---: | ---: | ---: |
| pair_J | 3.02 / 2.97 | 3.08 | **1.48** | **+1.44** | 0 (fold) |
| pair_Q | 3.08 / 3.17 | 2.96 | 1.99 | +1.55 | 0 (fold) |
| pair_K | 3.04 / 2.96 | 3.09 | 2.68 | +1.68 | 0 (fold) |
| pair_A | 2.53 / 2.57 | 2.61 | 2.53 | **+1.67** | best pass **+0.27** (raise-cd) |
| two_pair | 2.49 / 2.04 | 2.10 | 3.36 | **+1.79** | best pass **+0.36** (raise-cd) |

JJ vs BN’s open-legal range is a **losing** $6 street (EV 1.48 < 2, P(win) ≈ 0.20).
Calling after a pass would be −$0.11. Opening is still +$1.44 because the steal
is ~75%. Even a disaster street of $0 vs BN legal would leave open at
\(0.75 \times 2 + 0.21 \times (-2) \approx +1.08\). P(BN legal) would need to
exceed ~50% before a total loss flipped the sign; blockers keep it ~21%.

Vs 2:1, caller-first JJ/AA sit on the §3.4 cells; CO-first (BN as the 2:1) is
within a dime of that for pairs. Two pair’s n=2k CO-first cell is noisier
(p_vs_2to1 is only ~4%, so a $0.50 street error moves the mix by ~2¢).

## Sandbag table (Q2)

Pass a sandbag-set hand: BN not legal → **0** (forgone steal); BN legal →
return-to-actor. Pass-then-**call** is the same HU as open-vs-legal, so it
cannot beat open (the steal leftover is strictly positive). Pass-then-**raise**
is bounded by checkdown on a $10 pot (CO invested $4).

| Class | EV(open) | Pass-fold | Pass-call | Pass-raise-cd | Open − best pass |
| --- | ---: | ---: | ---: | ---: | ---: |
| pair_A | +1.67 | 0 | +0.10 | +0.27 | **+1.39** |
| two_pair | +1.79 | 0 | +0.32 | +0.36 | **+1.42** |

Do not sandbag on CO in this frame.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **CO JJ open** | Evaluate CO opening jacks with BN behind | Steal vs BN-legal HU vs 2:1; **+$1.44 vs pass** |
| **CO sandbag** | Evaluate CO passing two pair+ / aces | Give up steal when BN is weak; **not +EV** vs opening |
