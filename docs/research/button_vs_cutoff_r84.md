# Frame: button vs cutoff at chart \(r=84\%\)

Slug: **`button_vs_cutoff_r84`**. Parent grid:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO open chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).
Polar endpoints (do not restart): [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md)
(\(r=0\%\), all legal) and [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md)
(\(\sim 100\%\)). Sibling interior row: [button_vs_cutoff_r86.md](button_vs_cutoff_r86.md).

**How to point at this work:** `evaluate button_vs_cutoff_r84`

Code: `src/fivecarddraw/validation/button_vs_cutoff_r84_r86.py`.
CLI: `python -m fivecarddraw.validation.button_vs_cutoff_r84_r86 --rate 84`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r84.json`.
Seed `20260909`, n_hu=**4000** per cell.

Out of scope: other chart thresholds (79, 86 is the sibling; 87, 90, 93, 96),
polar restarts, multi-raise Nash, live draw / post-draw Nash.

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. **CO never sandbags**
AA+ / two pair+. CO opens exactly the signed chart band at \(r=84\%\):

- **AA or better** (always), **plus**
- **JJ with an ace or the joker**, **QQ with an ace or the joker**, **KK any
  kicker** (class average still opens).

CO does **not** open JJ or QQ without an ace-rank kicker (physical ace or
joker). Bare KK still opens. Bug = ace / fill, not a third rank: QQ+joker is
`pair_Q`, KK+joker is `pair_K`.

This is a **lookup row** for later seats when someone slowplays at 84%, not a
full late-position re-solve.

## Product answers

| BN | Action vs \(r=84\%\) CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any flavor) | **Fold** | Honest call −$1.8 to −$2.6; P(win) ≈ 0.18–0.28. Flavors do not flip. |
| AA | **Fold** | Honest call **−$0.45** (SE $0.10). P(win) = **0.455 < ½** — no longer a favorite (all-legal polar *raises* AA at P(win) 0.545). Raise-cd is **+$0.55** (SE $0.08, ~7 SE) as a dog with $10 pot odds (need 40%); that is **not** a published value raise on the locked leaf. |
| Two pair (not aces-up) | **Raise** | Call +$0.73; raise-cd +$1.17; P(win) = 0.516. Thin favorite vs this still-KK-heavy range. |
| Aces-up / trips / trips of aces | **Raise** | Favorites; P(win) 0.71 / 0.76 / 0.89. |

**Headline.** Dropping bare JJ/QQ (keep all KK) is already enough to **flip AA
from raise to fold** vs the 0% all-legal polar. AA is a dog (P(win) 0.455,
~5.7 SE below ½). Honest $6 call is −EV because CO value-bets two pair+.
Checkdown raise still prints as a dog with pot odds; the locked leaf (same as
the tight polar) does **not** value-raise a dog. Continue starts at two pair
(thin value raise); monsters raise.

## Chart (n=4000, seed `20260909`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.611 (0.078) | −$2.195 (0.061) | 0.180 | **fold** |
| pair_J | joker | −$2.486 (0.079) | −$2.083 (0.062) | 0.192 | **fold** |
| pair_J | ace | −$2.538 (0.079) | −$2.098 (0.062) | 0.190 | **fold** |
| pair_Q | class | −$2.368 (0.080) | −$1.864 (0.065) | 0.213 | **fold** |
| pair_Q | joker | −$2.188 (0.081) | −$1.725 (0.066) | 0.228 | **fold** |
| pair_Q | ace | −$2.222 (0.083) | −$1.740 (0.066) | 0.226 | **fold** |
| pair_K | class | −$2.044 (0.086) | −$1.310 (0.070) | 0.269 | **fold** |
| pair_K | joker | −$1.813 (0.088) | −$1.155 (0.071) | 0.284 | **fold** |
| pair_K | ace | −$2.106 (0.087) | −$1.298 (0.070) | 0.270 | **fold** |
| pair_A | class | **−$0.445** (0.099) | **+$0.546** (0.079) | 0.455 | **fold** |
| two_pair | class | +$0.730 (0.107) | +$1.165 (0.079) | 0.516 | **raise** |
| two_pair_aces_up | class | +$3.323 (0.099) | +$3.130 (0.072) | 0.713 | **raise** |
| trips | class | +$4.156 (0.095) | +$3.630 (0.067) | 0.763 | **raise** |
| trips_A | class | +$5.856 (0.077) | +$4.853 (0.050) | 0.885 | **raise** |

No joker/ace flavor flips a pair off fold. KK+joker is the least-bad low pair
(−$1.81) and is still ~21 SE below fold.

## Combo mix facing BN jacks (same deals as the JJ row)

Bare JJ/QQ are gone. All KK remains. Facing BN jacks:

| CO bucket | Share |
| --- | ---: |
| pair_A | 29.0% |
| pair_K_bare | 12.4% |
| pair_K_ace / joker | 4.8% / 1.2% |
| pair_Q_ace / joker | 4.1% / 1.0% |
| pair_J_ace / joker | 0.9% / 0.2% |
| two_pair | 20.6% |
| trips | 13.0% |
| two_pair_aces_up | 6.5% |
| straight+ | 6.3% |

One-pair (JJ/QQ flavors + all KK + AA) is still ~54%; two pair+ is ~46%.
That is much stronger than all-legal (large bare JJ/QQ mass) and still
weaker than the tight polar (QQ/KK **joker only**, no JJ). AA holding aces
blocks CO’s AA slice (AA mix: pair_A 13.9%, two pair 29.9%, KK-bare 16.7%)
and faces even more two pair — honest call −$0.45.

## Raise bound (no multi-raise tree)

Same locked leaves as the polar labs:

- A **dog** (JJ–AA) does not raise just because checkdown lost less than paying
  off two pair+ on the call line, and does not value-raise when P(win) < ½.
- A **favorite** (two pair here, aces-up, trips) with +EV raise-cd is marked
  **raise**.

AA is the edge vs the 0% polar: raise-cd is +EV (~7 SE) but P(win) = 0.455.
Published action is **fold**. A later raise tree (CO folding some KK, or 3-bet
trips+) can revisit the mix. Two pair is a thin favorite (P(win) 0.516);
tight polar *calls* two pair (P(win) 0.43).

## Accounting

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked `tp1_tr2_q1`) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: pairs d=3, two pair d=1, trips d=2, quads d=1. CO first, then BN.
Honest policy = `lead=never|stab=AA|raise=never`.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **r=84%** | CO chart band | JJ/QQ need ace or joker; KK class-average open; AA+/two pair+ |
| **AA inflection** | Raise vs wide, fold vs this band | Already on the fold side of the all-legal polar |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
