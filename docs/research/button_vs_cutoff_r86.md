# Frame: button vs cutoff at chart \(r=86\%\)

Slug: **`button_vs_cutoff_r86`**. Parent grid:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO open chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).
Polar endpoints (do not restart): [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md)
(\(r=0\%\)) and [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md)
(\(\sim 100\%\)). Sibling interior row: [button_vs_cutoff_r84.md](button_vs_cutoff_r84.md).

**How to point at this work:** `evaluate button_vs_cutoff_r86`

Code: `src/fivecarddraw/validation/button_vs_cutoff_r84_r86.py`.
CLI: `python -m fivecarddraw.validation.button_vs_cutoff_r84_r86 --rate 86`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_r86.json`.
Seed `20260910`, n_hu=**4000** per cell.

Out of scope: other chart thresholds (79, 84 is the sibling; 87, 90, 93, 96),
polar restarts, multi-raise Nash, live draw / post-draw Nash.

## Laboratory

Seats 1–6 passed. **CO never sandbags** AA+ / two pair+. CO opens the signed
chart band at \(r=86\%\):

- **AA or better** (always), **plus**
- **JJ with the joker only**, **QQ with an ace or the joker**, **KK any
  kicker** (class average still opens).

CO does **not** open JJ with only a physical ace (or bare JJ), nor QQ without
an ace-rank kicker. Bare KK still opens. Bug = ace / fill, not trips.

Vs the \(r=84\%\) sibling, the only CO change is **JJ ace-kicker drops out**.
KK remains fully in, so this band is only a little tighter.

## Product answers

| BN | Action vs \(r=86\%\) CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any flavor) | **Fold** | Honest call −$2.2 to −$2.6; P(win) ≈ 0.19–0.24. Flavors do not flip. |
| AA | **Fold** | Honest call **−$0.71** (SE $0.10). P(win) = **0.428**. Raise-cd **+$0.28** (SE $0.08, ~3.6 SE) — still +EV as a dog with pot odds, not a value raise. |
| Two pair (not aces-up) | **Raise** (thin) | Call +$0.59; raise-cd +$1.05; P(win) = **0.505** (~0.6 SE above ½). Locked leaf marks a favorite raise; a later tree can mix. |
| Aces-up / trips / trips of aces | **Raise** | Favorites; P(win) 0.69 / 0.75 / 0.89. |

**Headline.** Same qualitative chart as \(r=84\%\): **fold every one-pair
hand, including aces**; value-raise from two pair. Dropping JJ+ace (keep
JJ+joker, all KK, QQ ace/joker) moves AA further into dog territory
(P(win) 0.428 vs 0.455 at 84%). The 0% polar still *raises* AA; the tight
polar *folds* AA at P(win) 0.32. This row sits on the fold side, closer to
tight than to all-legal.

## Chart (n=4000, seed `20260910`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.511 (0.079) | −$2.103 (0.062) | 0.190 | **fold** |
| pair_J | joker | −$2.378 (0.081) | −$2.020 (0.063) | 0.198 | **fold** |
| pair_J | ace | −$2.539 (0.080) | −$2.047 (0.063) | 0.195 | **fold** |
| pair_Q | class | −$2.406 (0.081) | −$1.966 (0.064) | 0.203 | **fold** |
| pair_Q | joker | −$2.505 (0.080) | −$2.067 (0.062) | 0.193 | **fold** |
| pair_Q | ace | −$2.583 (0.081) | −$2.030 (0.063) | 0.197 | **fold** |
| pair_K | class | −$2.325 (0.085) | −$1.692 (0.067) | 0.231 | **fold** |
| pair_K | joker | −$2.232 (0.086) | −$1.587 (0.068) | 0.241 | **fold** |
| pair_K | ace | −$2.244 (0.085) | −$1.570 (0.068) | 0.243 | **fold** |
| pair_A | class | **−$0.707** (0.100) | **+$0.281** (0.078) | 0.428 | **fold** |
| two_pair | class | +$0.595 (0.108) | +$1.048 (0.079) | 0.505 | **raise** |
| two_pair_aces_up | class | +$3.133 (0.102) | +$2.895 (0.073) | 0.690 | **raise** |
| trips | class | +$4.054 (0.097) | +$3.475 (0.069) | 0.748 | **raise** |
| trips_A | class | +$5.893 (0.077) | +$4.853 (0.050) | 0.885 | **raise** |

No flavor flips a pair off fold. QQ+joker is not better than class QQ here
(BN holding the joker blocks CO’s entire joker-pair slice, including the
JJ+joker that is this band’s only remaining JJ).

## Combo mix facing BN jacks (same deals as the JJ row)

JJ+ace is gone (`pair_J_ace` = 0). JJ+joker is ~0.2%. All KK remains.

| CO bucket | Share |
| --- | ---: |
| pair_A | 28.1% |
| pair_K_bare | 13.2% |
| pair_K_ace / joker | 4.4% / 1.2% |
| pair_Q_ace / joker | 5.0% / 1.4% |
| pair_J_joker | 0.2% |
| two_pair | 20.4% |
| trips | 12.6% |
| two_pair_aces_up | 7.0% |
| straight+ | 6.8% |

AA’s own mix (BN blocks aces): pair_A 14.5%, two pair 30.2%, KK-bare 17.3%,
trips 15.6%. Honest call −$0.71 vs −$0.45 at 84%.

## Raise bound (no multi-raise tree)

Same locked leaves as the polar labs and the \(r=84\%\) sibling. AA raise-cd
is still +EV (~3.6 SE) because P(win) 0.428 > 40% into $10; published
**fold** because it is not a favorite and honest call is −EV. Two pair’s
P(win) = 0.505 is inside 1 SE of ½ — published **raise** because the locked
rule is P(win) > ½ and raise-cd +EV. Tight polar calls two pair; do not treat
0.505 as a fat value raise.

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
| **r=86%** | CO chart band | JJ joker only; QQ ace or joker; KK class-average open; AA+/two pair+ |
| **AA inflection** | Raise vs wide, fold vs this band | Fold; further from all-legal than \(r=84\%\) |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
