# Frame: button vs cutoff at r = 90%

Slug: **`button_vs_cutoff_r90`**. Parent: [INDEX.md](INDEX.md) research frames.
Grid: [../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md). Polar
endpoints (do not restart): [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md)
(0%) and [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) (~100%).
Sibling row: [button_vs_cutoff_r87.md](button_vs_cutoff_r87.md).

**How to point at this work:** `evaluate button_vs_cutoff_r90`

This file is **only r = 90%**. Other agents own 79 / 84 / 86 / 93 / 96.

Code: `src/fivecarddraw/validation/button_vs_cutoff_chart.py`.
CLI: `analyze-button-vs-cutoff-chart --rates 90`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r90.json`.
Seed `20260909`, n_hu=**4000** per cell.

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. CO opens the signed
chart row at \(r=90\%\):

- **AA or better** (`pair_A`, two pair, trips, boat, quads, straight / flush /
  straight-flush / five aces as classified by `classify_opener`), **plus**
- **JJ with the joker only**,
- **QQ with the joker only** (ace kicker without the bug is **out**),
- **KK with an ace kicker or the joker**.

The 87% → 90% step is **QQ ace-kicker leaving the CO range**. CO still never
sandbags AA+ / two pair+. Joker = ace kicker, not trips.

Locked leaves match the polar labs: `tp1_tr2_q1`, honest $6 call, $10
raise-checkdown, CO always continues. No multi-raise, no live draw Nash.

## Product answers

| BN | Action vs r=90% CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any joker or ace flavor) | **Fold** | Call −$2.54 to −$2.93; P(win) ≈ 0.17–0.21. Flavors do not flip the sign. |
| **AA** | **Fold** | Call **−$1.504** (SE $0.102, ~15 SE); P(win) = 0.333. Worse than at 87% (QQ+ace gone). |
| Two pair (not aces-up) | **Call** | Call +$0.249 (SE $0.112, ~2.2 SE); P(win) = 0.449. Not a favorite → not a value raise. |
| Aces-up | **Raise** | Call +$3.08; raise-cd +$2.44; P(win) ≈ 0.64. |
| Trips | **Raise** | Call +$4.45; raise-cd +$3.45; P(win) ≈ 0.74. |
| Trips of aces | **Raise** | Call +$5.96; raise-cd +$4.36; P(win) ≈ 0.84. |

**Headline (AA).** Same qualitative line as r = 87% and the tight polar:
**fold every one-pair hand, including aces.** Dropping QQ+ace makes CO
stronger; AA’s call EV moves from −$1.25 (87%) to −$1.50 (90%), still far
from the all-legal raise. Continue starts at two pair (call); value-raise
starts at aces-up / trips.

## Chart (n=4000, seed `20260909`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.662 (0.083) | −$2.165 (0.061) | 0.183 | **fold** |
| pair_J | joker | −$2.705 (0.083) | −$2.195 (0.061) | 0.180 | **fold** |
| pair_J | ace | −$2.928 (0.081) | −$2.275 (0.060) | 0.172 | **fold** |
| pair_Q | class | −$2.683 (0.082) | −$2.150 (0.061) | 0.185 | **fold** |
| pair_Q | joker | −$2.682 (0.084) | −$2.148 (0.061) | 0.185 | **fold** |
| pair_Q | ace | −$2.712 (0.084) | −$2.066 (0.062) | 0.193 | **fold** |
| pair_K | class | −$2.682 (0.084) | −$2.035 (0.063) | 0.197 | **fold** |
| pair_K | joker | −$2.558 (0.087) | −$1.998 (0.063) | 0.200 | **fold** |
| pair_K | ace | −$2.535 (0.087) | −$1.867 (0.065) | 0.213 | **fold** |
| pair_A | class | **−$1.504** (0.102) | −$0.670 (0.075) | 0.333 | **fold** |
| two_pair | class | **+$0.249** (0.112) | +$0.488 (0.079) | 0.449 | **call** |
| two_pair_aces_up | class | +$3.079 (0.110) | +$2.444 (0.076) | 0.644 | **raise** |
| trips | class | +$4.449 (0.100) | +$3.445 (0.069) | 0.744 | **raise** |
| trips_A | class | +$5.959 (0.088) | +$4.360 (0.059) | 0.836 | **raise** |

No joker/ace flavor flips a pair from fold to continue.

## Why this range is a step tighter than 87%

Facing BN jacks (combo mix on the JJ class row):

| CO bucket | Share at 90% | Share at 87% (same BN class) |
| --- | ---: | ---: |
| pair_A | 34.8% | 31.1% |
| two_pair | 25.9% | 24.8% |
| trips | 15.0% | 14.9% |
| two_pair_aces_up | 7.5% | 7.7% |
| straight+ | 7.7% | 7.4% |
| pair_K_ace | 5.8% | 5.2% |
| pair_Q_joker | 1.6% | 1.7% |
| pair_K_joker | 1.4% | 1.1% |
| pair_J_joker | 0.4% | 0.4% |
| pair_Q_ace | **0** | 5.8% |

QQ+ace is the mass that left. Face-pair extras drop from ~14% to ~9%. AA
share facing BN jacks rises (31% → 35%). BN aces win 33% after locked draws
(vs 36% at 87%). Call −$1.50 is ~15 SE below fold. Raise-cd (−$0.67) is
still a dog.

## Raise bound (no multi-raise tree)

Same tight-polar `recommend_action`: value-raise iff P(win) > 0.5 and
raise-cd +EV. Two pair stays a **call** (P(win) = 0.449; call +$0.25 ~ 2.2
SE). Aces-up / trips value-raise.

## Accounting (no live draw solver)

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked `tp1_tr2_q1`) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: pairs d=3, two pair d=1, trips d=2, quads d=1. CO draws first,
then BN.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **r = 90%** | This lookup row | JJ joker only; QQ joker only; KK ace or joker; AA+/two pair+ |
| **QQ step** | 87% → 90% | QQ ace-kicker leaves; AA’s call EV gets worse |
| **AA inflection** | Raise vs a wide CO, fold vs a tight one | At 90% AA **folds** (same side as 87% and the tight polar) |
