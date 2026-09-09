# Frame: button vs cutoff at r = 87%

Slug: **`button_vs_cutoff_r87`**. Parent: [INDEX.md](INDEX.md) research frames.
Grid: [../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md). Polar
endpoints (do not restart): [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md)
(0%) and [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) (~100%).
Sibling row: [button_vs_cutoff_r90.md](button_vs_cutoff_r90.md).

**How to point at this work:** `evaluate button_vs_cutoff_r87`

This file is **only r = 87%**. Other agents own 79 / 84 / 86 / 93 / 96.

Code: `src/fivecarddraw/validation/button_vs_cutoff_chart.py`.
CLI: `analyze-button-vs-cutoff-chart --rates 87`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r87.json`.
Seed `20260909`, n_hu=**4000** per cell.

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. **CO does not open
all legal hands** and does not play the tight polar either. CO opens exactly
the signed chart row at \(r=87\%\):

- **AA or better** (`pair_A`, two pair, trips, boat, quads, straight / flush /
  straight-flush / five aces as classified by `classify_opener`), **plus**
- **JJ with the joker only**,
- **QQ with an ace kicker or the joker**,
- **KK with an ace kicker or the joker**.

CO does **not** open bare JJ (including a physical ace without the bug), QQ
without ace/joker, or KK without ace/joker. CO **does not sandbag** AA+ / two
pair+ — they open them.

**Bug rule.** The joker is an ace (or a straight/flush fill), **not** a
duplicate pair rank. QQ+joker = two queens + ace kicker (`pair_Q`). Ace =
physical ace kicker **or** the joker; “joker only” means the bug specifically.

Locked leaves match the polar labs: `tp1_tr2_q1`, honest $6 call, $10
raise-checkdown, CO always continues. No multi-raise, no live draw Nash.

## Product answers

| BN | Action vs r=87% CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any joker or ace flavor) | **Fold** | Call −$2.29 to −$2.78; P(win) ≈ 0.18–0.23. Flavors do not flip the sign. |
| **AA** | **Fold** | Call **−$1.250** (SE $0.103, ~12 SE); P(win) = 0.360. Not thin. Behind two pair+ / tied with CO’s remaining AA mass. |
| Two pair (not aces-up) | **Call** | Call +$0.318 (SE $0.111, ~2.9 SE); P(win) = 0.464. Not a favorite → not a value raise. |
| Aces-up | **Raise** | Call +$3.13; raise-cd +$2.56; P(win) ≈ 0.66. |
| Trips | **Raise** | Call +$4.27; raise-cd +$3.40; P(win) = 0.74. |
| Trips of aces | **Raise** | Call +$6.11; raise-cd +$4.54; P(win) ≈ 0.85. |

**Headline (AA).** At 87% the constructed CO range is **already strong enough
that BN folds aces**. Vs the signed all-legal polar, AA value-raises; vs the
tight polar, AA folds. This interior row sits on the **fold** side of that
inflection, ~12 SE below fold, so the raise→fold flip for AA is **below** 87%
(the 79 / 84 / 86 rows). Do not treat 87% as the crossing.

## Chart (n=4000, seed `20260909`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.763 (0.080) | −$2.208 (0.061) | 0.179 | **fold** |
| pair_J | joker | −$2.495 (0.083) | −$2.033 (0.063) | 0.197 | **fold** |
| pair_J | ace | −$2.783 (0.080) | −$2.248 (0.060) | 0.175 | **fold** |
| pair_Q | class | −$2.514 (0.084) | −$1.992 (0.063) | 0.201 | **fold** |
| pair_Q | joker | −$2.487 (0.085) | −$2.028 (0.063) | 0.197 | **fold** |
| pair_Q | ace | −$2.641 (0.084) | −$2.040 (0.063) | 0.196 | **fold** |
| pair_K | class | −$2.292 (0.086) | −$1.708 (0.066) | 0.229 | **fold** |
| pair_K | joker | −$2.342 (0.087) | −$1.698 (0.067) | 0.230 | **fold** |
| pair_K | ace | −$2.329 (0.088) | −$1.645 (0.067) | 0.235 | **fold** |
| pair_A | class | **−$1.250** (0.103) | −$0.400 (0.076) | 0.360 | **fold** |
| two_pair | class | **+$0.318** (0.111) | +$0.635 (0.079) | 0.464 | **call** |
| two_pair_aces_up | class | +$3.125 (0.108) | +$2.564 (0.075) | 0.656 | **raise** |
| trips | class | +$4.268 (0.100) | +$3.400 (0.069) | 0.740 | **raise** |
| trips_A | class | +$6.107 (0.084) | +$4.538 (0.056) | 0.854 | **raise** |

No joker/ace flavor flips a pair from fold to continue. BN holding the joker
blocks CO’s JJ/QQ/KK+joker slice and some AA (bug-as-ace); that is a few dimes
for JJ (least-bad at −$2.49) and is still ~30 SE below fold.

## Why AA folds here

Facing BN jacks (combo mix on the JJ class row):

| CO bucket | Share |
| --- | ---: |
| pair_A | 31.1% |
| two_pair | 24.8% |
| trips | 14.9% |
| two_pair_aces_up | 7.7% |
| straight+ (incl. boats / quads) | 7.4% |
| pair_Q_ace | 5.8% |
| pair_K_ace | 5.2% |
| pair_Q_joker | 1.7% |
| pair_K_joker | 1.1% |
| pair_J_joker | 0.4% |

Face-pair extras (JJ joker + QQ/KK ace-or-joker) are ~14% of this range —
more than the tight polar’s ~3% joker-pairs, far less than an all-legal
JJ/QQ/KK mass. AA still wins only 36% after locked draws. Call −$1.25 is
worse than fold by ~12 SE. Raise-cd (−$0.40) loses *less* than the stacked
honest call but is still −EV; P(win) = 0.36 ≪ 0.5, so it is **not** a value
raise.

Facing BN aces the remaining CO AA mass drops (blockers) and two pair rises
(~37%), which is the domination story: BN aces are often drawing into two
pair+ or splitting remaining AA.

## Raise bound (no multi-raise tree)

Same rule as the tight polar (`recommend_action`):

- A **dog** does not raise just because checkdown lost less than paying off
  two pair+ on the call line.
- A **favorite** (aces-up, trips) with +EV raise-cd is marked **raise** for
  value even when the $6 honest-call number is higher.

Two pair: both call and raise-cd are +EV vs fold, P(win) = 0.464 < 0.5,
published action is **call**. Raise-cd (+$0.64) is the better numeric bound
but is still a dog putting in extra.

## Accounting (no live draw solver)

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked `tp1_tr2_q1`) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: pairs d=3, two pair d=1, trips d=2, quads d=1. CO draws first,
then BN. Honest post-draw policy matches the polar HU cells (opener is
still CO).

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **r = 87%** | This lookup row | JJ joker only; QQ ace or joker; KK ace or joker; AA+/two pair+ |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
| **AA inflection** | Raise vs a wide CO, fold vs a tight one | At 87% AA **folds** (the crossing is a lower r) |
