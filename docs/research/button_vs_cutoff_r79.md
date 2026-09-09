# Frame: button vs cutoff, CO open at r = 79%

Slug: **`button_vs_cutoff_r79`**. Parent: [INDEX.md](INDEX.md) research frames
(do not edit INDEX in this PR — merge wars). Ticket:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md). Polar
endpoints (signed; do not restart):
[button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md),
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md). CO chart:
[cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).

**How to point at this work:** `evaluate button_vs_cutoff_r79`

Code: `src/fivecarddraw/validation/button_vs_cutoff_r79.py`.
CLI: `python -m fivecarddraw.validation.button_vs_cutoff_r79` (or
`analyze-button-vs-cutoff-r79`).
Fixture: `tests/fixtures/validation/button_vs_cutoff_r79.json`.
Seed `20260909`, n_hu=4k, n_2to1=2k.

This is **one interior row** of the BN-vs-CO lookup (r = 79%). Other agents
own 84 / 86 / 87 / 90 / 93 / 96. Polar 0% and ~100% are already signed.

Out of scope: multi-raise Nash, live draw solver, post-draw Nash, HJ mixes,
restarting the polar labs or the CO open chart.

## Product answers

1. **CO range at r = 79%.** CO never sandbags two pair+ / aces. Opens every
   AA+ / two pair+ combo, **every QQ**, **every KK**, and **JJ only with ace
   or joker** (physical ace kicker or the bug). Bare JJ is out. Bug = ace
   kicker, not trips.
2. **Fold JJ, QQ, KK, and AA.** Honest $6 call is −EV vs fold for every
   one-pair class, including aces (AA **−$0.24**, SE $0.096, ~2.5 SE).
3. **AA does not raise.** This is the inflection vs the all-legal polar
   (r = 0% raises AA). Vs this range P(win) = **0.491** — not a favorite, so
   matching checkdowns do not value-raise. Raise-cd is +$0.91 vs fold
   (checkdown avoids paying off two pair+), but that is the dog putting in
   extra, not a value raise. Tight-rule `recommend_action` also marks
   **fold** (`value_raise` is false).
4. **Value-raise two pair, aces-up, trips+.** Two pair is still a favorite
   (P(win) = 0.545); raise-cd beats call-cd. That is **not** the tight polar
   (tight *calls* two pair as a dog). Aces-up / trips+ are fat.
5. **2:1 drawing hands call, do not raise.** Honest call **+$1.13**. No air
   to fold; P(win) ≈ 0.32.

**Headline.** Cutting only bare JJ from CO’s open is already enough to flip
BN aces from **raise** (all-legal) to **fold** (this row / tight). Two pair
has not flipped yet — it still raises.

## Accounting (BN’s decision)

Antes are already in ($2). Fold = **0** relative to this node. CO’s open
makes the pot $4; BN calls $2 (pot $6 into the draw) or raises to $4 (CO
always calls → pot $10). Same locked leaves as the polar labs.

| Line | Pot into draw | BN invested | EV vs fold |
| --- | ---: | ---: | --- |
| Fold | — | $0 more | **0** |
| Call | $6 | $2 | \(\mathrm{EV}_{\mathrm{street}}-2\) (honest locked leaf) |
| Raise, CO always continues | $10 | $4 | checkdown \(10p+5t-4\) |

Locked draws: `tp1_tr2_q1` (pairs \(d=3\), two pair \(d=1\), trips \(d=2\),
quads \(d=1\)). Draw order: CO first, BN last. Honest policy =
`lead=never|stab=AA|raise=never`. Published actions use
`button_vs_cutoff.decide_action` (matching checkdowns). Fold equity vs air
is identically 0 — the range is still 100% jacks-or-better.

## Chart (n=4000 made / 2000 2:1, seed 20260909)

SE is the SE of the mean. Fold = 0 exactly.

| BN class | Action | EV fold | EV call honest (SE) | EV call-cd | EV raise-cd (SE) | P(win) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pair_J | **fold** | 0 | −2.381 (0.078) | −0.818 | −2.030 (0.063) | 0.197 |
| pair_Q | **fold** | 0 | −2.187 (0.082) | −0.622 | −1.702 (0.067) | 0.230 |
| pair_K | **fold** | 0 | −1.592 (0.087) | −0.065 | −0.775 (0.074) | 0.323 |
| pair_A | **fold** | 0 | −0.242 (0.096) | **+0.946** | +0.910 (0.079) | 0.491 |
| two_pair | **raise** | 0 | +0.905 (0.105) | +1.272 | +1.452 (0.079) | 0.545 |
| two_pair_aces_up | **raise** | 0 | +3.180 (0.096) | +2.347 | +3.245 (0.071) | 0.725 |
| trips+ | **raise** | 0 | +5.727 (0.091) | +3.143 | +4.571 (0.055) | 0.857 |
| 2:1 draws | **call** | 0 | +1.129 (0.130) | −0.085 | −0.807 (0.104) | 0.319 |

`trips+` = trips / trips_K / trips_A / straight+ (combo-weighted).
`two_pair` is the non-aces-up class.

## Why AA folds after dropping only bare JJ

Facing BN aces, CO’s own AA mass is blocked. Combo mix on the AA row:

| CO bucket | Share |
| --- | ---: |
| two_pair | 25.1% |
| pair_K | 18.7% |
| pair_Q | 18.6% |
| pair_A | 12.6% |
| trips | 11.0% |
| pair_J (ace or joker only) | 4.4% |
| two_pair_aces_up | 2.6% |
| straight+ / boats | ~6% |

The all-legal polar still had a large *bare* JJ slice for AA to beat. Here
that slice is gone; what remains of one-pair is mostly QQ/KK (class
average) plus a thin ace/joker-JJ tail. BN aces are then a small dog
(P(win) = 0.491) and the honest $6 street is −EV because pairs pay off CO
two pair+. Checkdown call is +$0.95 — the extraction, not the showdown, is
what makes the honest call miss.

## Vs the signed polars (actions only)

| BN | all-legal (r=0%) | **this row (r=79%)** | tight (r≈100%) |
| --- | --- | --- | --- |
| JJ / QQ / KK | fold | **fold** | fold |
| AA | **raise** | **fold** | fold |
| two pair | raise | **raise** | call (thin) |
| aces-up / trips+ | raise | **raise** | raise |
| 2:1 | call | **call** | (not in that chart) |

AA’s raise→fold flip is already done at the first interior threshold. Two
pair’s raise→call flip is **not** — still a value raise here.

## Where it is close / later work

1. **AA is the knife.** Honest call −$0.24 is ~2.5 SE below fold (not inside
   2 SE). Raise-cd − call-cd = −$0.036 (inside 2 SE on that *difference*,
   P(win) = 0.491). The polar `decide_action` helper flags
   `close_raise_vs_call` but does not set `needs_later_tree` on a **fold**.
   A Stage C street that *checks* two pair would move the honest call up;
   a raise tree where CO can 3-bet trips+ would eat the dime of raise-cd.
   Do not treat AA-fold as GTO vs a checking range.
2. **KK checkdown call is −$0.07** (inside 2 SE of 0). Honest call is
   −$1.59 because CO value-bets two pair+. Same Stage C caveat as the
   all-legal KK row. Flagged `needs_later_tree`.
3. **Two pair value-raise is thin-ish** (raise-cd − call-cd ≈ +$0.18, same
   shape as all-legal). Sign is many SE; a raise tree can still revisit.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **r = 79%** | First interior CO-chart threshold | JJ needs ace or joker; QQ/KK still class-average opens |
| **AA inflection** | Does BN still raise aces? | **No** — fold, matching tight, unlike all-legal |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
| **No air** | Fold equity vs junk | Identically 0; range is still 100% jacks+ |
