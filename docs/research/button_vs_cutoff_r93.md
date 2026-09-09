# Frame: button vs cutoff at chart r = 93%

Slug: **`button_vs_cutoff_r93`**. Parent: [INDEX.md](INDEX.md) research frames
(do not edit the index in this PR). Ticket:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
Sibling row: [button_vs_cutoff_r96.md](button_vs_cutoff_r96.md).
Tight polar (compare only; **do not edit**):
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md).
CO chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).

**How to point at this work:** `evaluate button_vs_cutoff_r93`

This file owns **r = 93%** only. Other agents own 79 / 84 / 86 / 87 / 90.
Do not restart the 0% / ~100% polar labs.

Code: `src/fivecarddraw/validation/button_vs_cutoff_chart.py` (wrapper
`button_vs_cutoff_r93.py`).
CLI: `analyze-button-vs-cutoff-r93`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r93.json`.
Seed `20260909`, n_hu=**4000** per cell (polar method; different seed from
the tight polar’s `20260907`).

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. CO opens the
**signed chart range at r = 93%**:

- **AA or better** / two pair / trips / boats / straight+ (CO never sandbags
  these), **plus**
- **QQ with the joker**, **or** **KK with a physical ace kicker or the joker**.

CO does **not** open JJ (any kicker), QQ without the joker (including a
physical ace kicker), or KK with neither an ace nor the joker.

The only constructed difference vs r = 96% / the tight polar is the
**KK + ace** slice (no joker). Facing BN jacks that slice is **5.5%** of
CO’s range; QQ-ace is 0% (joker-only).

**Bug rule.** The joker is an ace (or a straight/flush fill), **not** a
duplicate pair rank. QQ+joker = `pair_Q`. KK+joker = `pair_K`. KK+ace
(physical ace, no bug) is still `pair_K`.

## Product answers

| BN | Action vs r=93% CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any joker or ace flavor) | **Fold** | Call −$2.5 to −$2.9; P(win) ≈ 0.17–0.20. Flavors do not flip the sign. |
| AA | **Fold** | Call **−$1.695** (SE $0.101, **16.8 SE** vs fold); P(win) ≈ 0.32. Already on the tight-polar side of the AA inflection. |
| Two pair (not aces-up) | **Call** (thin) | Call **+$0.165** (SE $0.112, **1.5 SE** vs fold); P(win) ≈ 0.44. Still a dog → not a value raise. |
| Aces-up | **Raise** | Call +$3.37; raise-cd +$2.60; P(win) ≈ 0.66. |
| Trips | **Raise** | Call +$4.31; raise-cd +$3.32; P(win) ≈ 0.73. |
| Trips of aces | **Raise** | Call +$6.13; raise-cd +$4.44; P(win) ≈ 0.84. |

**Headline.** Adding KK+ace (~5.5% facing jacks) does **not** move AA off
fold, and does **not** fatten two pair into a value raise. AA is closer to
**fold** than to a call by a wide margin. Two pair is **still a thin call**
(1.5 SE; polar tight was ~1.9 SE).

## Chart (n=4000, seed `20260909`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.771 (0.082) | −$2.245 (0.060) | 0.175 | **fold** |
| pair_J | joker | −$2.757 (0.083) | −$2.190 (0.061) | 0.181 | **fold** |
| pair_J | ace | −$2.929 (0.081) | −$2.290 (0.060) | 0.171 | **fold** |
| pair_Q | class | −$2.695 (0.083) | −$2.192 (0.061) | 0.181 | **fold** |
| pair_Q | joker | −$2.527 (0.085) | −$2.027 (0.063) | 0.197 | **fold** |
| pair_Q | ace | −$2.857 (0.082) | −$2.240 (0.060) | 0.176 | **fold** |
| pair_K | class | −$2.652 (0.085) | −$2.095 (0.062) | 0.190 | **fold** |
| pair_K | joker | −$2.463 (0.087) | −$1.958 (0.064) | 0.204 | **fold** |
| pair_K | ace | −$2.603 (0.086) | −$1.985 (0.063) | 0.202 | **fold** |
| pair_A | class | **−$1.695** (0.101) | −$0.804 (0.074) | 0.320 | **fold** |
| two_pair | class | **+$0.165** (0.112) | +$0.443 (0.079) | 0.444 | **call** |
| two_pair_aces_up | class | +$3.365 (0.109) | +$2.595 (0.075) | 0.659 | **raise** |
| trips | class | +$4.309 (0.102) | +$3.322 (0.070) | 0.732 | **raise** |
| trips_A | class | +$6.131 (0.087) | +$4.442 (0.057) | 0.844 | **raise** |

No joker/ace flavor flips a pair from fold to continue. Cell seeds (adler32
of `hu|93|class|flavor` off base `20260909`): pair_J `20973555`, pair_A
`20844790`, two_pair `20472447`.

## CO mix facing BN jacks

| CO bucket | Share |
| --- | ---: |
| pair_A | 33.6% |
| two_pair | 26.5% |
| trips | 15.2% |
| two_pair_aces_up | 8.0% |
| straight+ (incl. boats / quads) | 8.4% |
| pair_K_ace | **5.5%** |
| pair_K_joker | 1.4% |
| pair_Q_joker | 1.3% |
| pair_Q_ace | 0.0% |

The 5.5% KK+ace mass is the whole difference vs r = 96% / tight polar
(those files have pair_K_ace = 0). It is not enough to make BN aces a
call: AA call EV is still −$1.70.

## Vs tight polar (read-only)

[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) is the ~100% polar
(AA+ plus QQ/KK+joker). **Actions match** that file: fold JJ–AA, call two
pair, raise aces-up / trips. Magnitudes, this seed:

| BN | r=93% call (SE) | tight polar call (SE) |
| --- | ---: | ---: |
| AA | −$1.695 (0.101) | −$1.538 (0.105) |
| two pair | +$0.165 (0.112) | +$0.219 (0.115) |

AA is **more** negative here than the polar point estimate (still fold
either way). Two pair is a **thinner** call (1.5 SE vs ~1.9 SE). Different
seed + the extra KK+ace slice; do not treat the dime as a new theorem.

Vs the all-legal polar, AA raised. At r = 93% it already **folds**. The
inflection is at a looser CO range than this row.

## Raise bound (no multi-raise tree)

Same rule as the polar labs. A dog (JJ–AA, two pair) does not raise just
because checkdown lost less than paying off two pair+ on the call line.
A favorite (aces-up, trips) with +EV raise-cd is marked **raise** for
value. Two pair: both call and raise-cd are +EV vs fold, P(win) = 0.44
< 0.5, published action **call**. A later multi-raise tree can revisit
the mix.

## Accounting (no live draw solver)

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked `tp1_tr2_q1`) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: pairs d=3, two pair d=1, trips d=2, quads d=1. CO draws first,
then BN. Honest post-draw policy matches the CO-vs-BN HU lab.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **r = 93%** | Chart threshold | JJ pass; QQ joker only; KK ace or joker; always AA+ / two pair+ |
| **KK+ace slice** | Extra vs tight polar | `pair_K` with a physical ace kicker, no joker (~5.5% facing JJ) |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
| **Thin call** | Two pair | +EV vs fold, P(win) < 0.5, not a value raise |
