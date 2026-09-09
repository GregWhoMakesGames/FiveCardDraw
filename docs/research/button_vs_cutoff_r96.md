# Frame: button vs cutoff at chart r = 96%

Slug: **`button_vs_cutoff_r96`**. Parent: [INDEX.md](INDEX.md) research frames
(do not edit the index in this PR). Ticket:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
Sibling row: [button_vs_cutoff_r93.md](button_vs_cutoff_r93.md).
Tight polar (compare only; **do not edit**):
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md).
CO chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).

**How to point at this work:** `evaluate button_vs_cutoff_r96`

This file owns **r = 96%** only. Other agents own 79 / 84 / 86 / 87 / 90.
This is **not** a restart of the tight polar lab: same constructed CO
range, new seed, new fixture.

Code: `src/fivecarddraw/validation/button_vs_cutoff_r93_96.py` (wrapper
`button_vs_cutoff_r96.py`).
CLI: `analyze-button-vs-cutoff-r96`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r96.json`.
Seed `20260909`, n_hu=**4000** per cell (polar tight used `20260907`).

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. CO opens the
**signed chart range at r ≥ 96%**, which is the tight polar range:

- **AA or better** / two pair / trips / boats / straight+, **plus**
- **QQ with the joker**, **or** **KK with the joker**.

CO does **not** open JJ (any kicker), QQ without the joker, or KK without
the joker (including KK + physical ace). Predicate tests pin this equal
to `is_co_tight_open`.

**Bug rule.** The joker is an ace (or a straight/flush fill), **not** a
duplicate pair rank. QQ+joker = `pair_Q`. KK+joker = `pair_K`.

## Product answers

| BN | Action vs r=96% CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any joker or ace flavor) | **Fold** | Call −$2.5 to −$3.0; P(win) ≈ 0.17–0.20. Flavors do not flip the sign. |
| AA | **Fold** | Call **−$1.782** (SE $0.103, **17.3 SE** vs fold); P(win) ≈ 0.30. |
| Two pair (not aces-up) | **Call** (thin) | Call **+$0.127** (SE $0.114, **1.1 SE** vs fold); P(win) ≈ 0.43. Still a dog → not a value raise. |
| Aces-up | **Raise** | Call +$2.95; raise-cd +$2.23; P(win) ≈ 0.62. |
| Trips | **Raise** | Call +$4.34; raise-cd +$3.23; P(win) ≈ 0.72. |
| Trips of aces | **Raise** | Call +$6.21; raise-cd +$4.39; P(win) ≈ 0.84. |

**Headline.** r = 96% **matches the tight polar on every published action**:
fold JJ–AA, call two pair, raise aces-up / trips. AA is not close to a
call. Two pair is **still a thin call**, thinner here (1.1 SE) than the
polar’s ~1.9 SE — same sign, same rule, closer to fold than the polar
point estimate.

## Chart (n=4000, seed `20260909`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.708 (0.084) | −$2.192 (0.061) | 0.181 | **fold** |
| pair_J | joker | −$2.759 (0.086) | −$2.178 (0.061) | 0.182 | **fold** |
| pair_J | ace | −$2.962 (0.084) | −$2.255 (0.060) | 0.174 | **fold** |
| pair_Q | class | −$2.666 (0.086) | −$2.123 (0.062) | 0.188 | **fold** |
| pair_Q | joker | −$2.728 (0.086) | −$2.150 (0.061) | 0.185 | **fold** |
| pair_Q | ace | −$2.885 (0.084) | −$2.250 (0.060) | 0.175 | **fold** |
| pair_K | class | −$2.542 (0.086) | −$2.038 (0.063) | 0.196 | **fold** |
| pair_K | joker | −$2.669 (0.086) | −$2.105 (0.062) | 0.190 | **fold** |
| pair_K | ace | −$2.763 (0.086) | −$2.070 (0.062) | 0.193 | **fold** |
| pair_A | class | **−$1.782** (0.103) | −$1.009 (0.072) | 0.299 | **fold** |
| two_pair | class | **+$0.127** (0.114) | +$0.284 (0.078) | 0.428 | **call** |
| two_pair_aces_up | class | +$2.950 (0.112) | +$2.230 (0.077) | 0.623 | **raise** |
| trips | class | +$4.340 (0.104) | +$3.232 (0.071) | 0.723 | **raise** |
| trips_A | class | +$6.205 (0.088) | +$4.388 (0.058) | 0.839 | **raise** |

No joker/ace flavor flips a pair from fold to continue. Cell seeds (adler32
of `hu|96|class|flavor` off base `20260909`): pair_J `20726061`, pair_A
`20597296`, two_pair `20618169`.

## CO mix facing BN jacks

| CO bucket | Share |
| --- | ---: |
| pair_A | 37.7% |
| two_pair | 27.6% |
| trips | 16.4% |
| two_pair_aces_up | 7.1% |
| straight+ (incl. boats / quads) | 8.2% |
| pair_Q_joker | 1.6% |
| pair_K_joker | 1.3% |
| pair_K_ace | **0.0%** |
| pair_Q_ace | 0.0% |

Same shape as the tight polar’s mix facing jacks (pair_A 36.0%, two pair
27.9%, trips 16.4%, joker-pairs ~3% combined). pair_K_ace is identically
0 — KK needs the joker at this threshold.

## Vs tight polar (read-only)

Fixture comparison (`vs_tight`): **actions_match_tight = true**, no
mismatches on any FOCUS row.

| BN | r=96% call (SE) | tight polar call (SE) | Δ / SE |
| --- | ---: | ---: | ---: |
| JJ | −$2.708 (0.084) | −$2.851 (0.084) | +1.7 |
| AA | −$1.782 (0.103) | −$1.538 (0.105) | −2.4 |
| two pair | +$0.127 (0.114) | +$0.219 (0.115) | −0.8 |
| aces-up | +$2.950 (0.112) | +$3.012 (0.113) | −0.5 |
| trips | +$4.340 (0.104) | +$4.429 (0.103) | −0.9 |

Same range, different seed. AA’s 2.4 SE swing is sampling, not a range
change; both are ~15–17 SE below fold. Two pair stays a thin +EV call
on both seeds. **Do not edit** the polar file to “correct” the dime.

## Raise bound (no multi-raise tree)

Same rule as the polar labs. Two pair: both call and raise-cd are +EV vs
fold, P(win) = 0.43 < 0.5, published action **call**. Raise-cd (+$0.28)
is a slightly better numeric bound but is still a dog putting in extra.
At **1.1 SE** this is the thinnest two-pair call of the three tight-side
pins (polar 1.9 SE, r=93% 1.5 SE). A later multi-raise tree can flip it;
the lookup action is still call.

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
| **r = 96%** | Chart threshold | JJ pass; QQ joker only; KK joker only; always AA+ / two pair+ |
| **Tight polar range** | Same constructed CO range | `is_co_chart_open(..., 96) == is_co_tight_open` |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
| **Thin call** | Two pair | +EV vs fold, P(win) < 0.5, not a value raise |
