# Frame: button vs tight cutoff open (range 2)

Slug: **`button_vs_cutoff_tight`**. Parent: [INDEX.md](INDEX.md) research frames.
0% all-legal CO lab: [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md)
(invert the seats: that file is CO vs BN *legal*; this file is BN vs a
**constructed** CO range). Flavor pins that motivate the range:
[cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) (joker / ace section).

**How to point at this work:** `evaluate button_vs_cutoff_tight`

Another agent owns BN vs **all-legal** CO. This file is **only range 2**.
Do not paste that agent's numbers here.

Code: `src/fivecarddraw/validation/button_vs_cutoff_tight.py`.
CLI: `analyze-button-vs-cutoff-tight`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_tight.json`.
Seed `20260907`, n_hu=**4000** per cell.

## Laboratory

Seats 1–6 passed under the sandbag-aware node as needed. **CO does not open
all legal hands.** CO opens exactly:

- **AA or better** (`pair_A`, two pair, trips, boat, quads, straight / flush /
  straight-flush / five aces as classified by `classify_opener`), **plus**
- **QQ with the joker**, or **KK with the joker**.

CO does **not** open JJ (any kicker), QQ without the joker, or KK without the
joker. CO **does not sandbag** the hands in this range — they open them.

This range is a **hypothesis** consistent with the 100% sandbag flavor pins
(KK+joker +EV at 100%; QQ+joker ~0 inside 1 SE; JJ+joker still −EV; ace
kickers −EV). This frame does **not** prove the CO open chart. It asks what
BN should do **if** CO plays this range.

**Bug rule.** The joker is an ace (or a straight/flush fill), **not** a
duplicate pair rank. QQ+joker = two queens + ace kicker (`pair_Q`).
KK+joker = two kings + ace kicker (`pair_K`).

## Product answers

| BN | Action vs tight CO | Why |
| --- | --- | --- |
| JJ / QQ / KK (any joker or ace flavor) | **Fold** | Call −$2.5 to −$2.9; P(win) ≈ 0.17–0.20. Flavors do not flip the sign. |
| AA | **Fold** | Call −$1.54 (SE $0.11); P(win) ≈ 0.32. Behind two pair+ / tied with CO’s AA mass. |
| Two pair (not aces-up) | **Call** (thin) | Call +$0.22 (SE $0.12, ~1.9 SE); P(win) ≈ 0.43. Not a favorite → not a value raise. |
| Aces-up | **Raise** | Call +$3.01; raise-cd +$2.26; P(win) ≈ 0.63. |
| Trips | **Raise** | Call +$4.43; raise-cd +$3.27; P(win) ≈ 0.73. |
| Trips of aces | **Raise** | Call +$6.35; raise-cd +$4.48; P(win) ≈ 0.85. |

**Headline.** This CO range is **much stronger** than an all-legal open: the
JJ/QQ/KK (no joker) mass is gone, and the two joker-pairs are only ~3% of
what remains. BN should **fold every one-pair hand**, including aces.
Continue starts at two pair (call); value-raise starts at aces-up / trips.

## Chart (n=4000, seed `20260907`)

Fold = 0. Call = honest $6 street − $2. Raise-cd = checkdown $10 − $4
(CO always continues). SE is the sample SE of the mean.

| BN | flavor | EV(call) (SE) | EV(raise-cd) (SE) | P(win) | action |
| --- | --- | ---: | ---: | ---: | --- |
| pair_J | class | −$2.851 (0.084) | −$2.255 (0.060) | 0.175 | **fold** |
| pair_J | joker | −$2.855 (0.084) | −$2.263 (0.060) | 0.174 | **fold** |
| pair_J | ace | −$2.914 (0.084) | −$2.272 (0.060) | 0.173 | **fold** |
| pair_Q | class | −$2.845 (0.083) | −$2.272 (0.060) | 0.173 | **fold** |
| pair_Q | joker | −$2.689 (0.086) | −$2.120 (0.062) | 0.188 | **fold** |
| pair_Q | ace | −$2.799 (0.085) | −$2.178 (0.061) | 0.182 | **fold** |
| pair_K | class | −$2.642 (0.085) | −$2.078 (0.062) | 0.192 | **fold** |
| pair_K | joker | −$2.474 (0.088) | −$2.007 (0.063) | 0.199 | **fold** |
| pair_K | ace | −$2.743 (0.086) | −$2.092 (0.062) | 0.191 | **fold** |
| pair_A | class | −$1.538 (0.105) | −$0.836 (0.074) | 0.316 | **fold** |
| two_pair | class | **+$0.219** (0.115) | +$0.320 (0.078) | 0.432 | **call** |
| two_pair_aces_up | class | +$3.012 (0.113) | +$2.258 (0.077) | 0.626 | **raise** |
| trips | class | +$4.429 (0.103) | +$3.265 (0.070) | 0.727 | **raise** |
| trips_A | class | +$6.345 (0.086) | +$4.480 (0.057) | 0.848 | **raise** |

No joker/ace flavor flips a pair from fold to continue. QQ+joker is the
least-bad low pair (−$2.69 vs −$2.85 class) and is still ~31 SE below fold.
BN holding the joker *blocks* CO’s entire QQ+joker / KK+joker slice (the
weakest ~3%) and also some AA (bug-as-ace). Those two effects roughly
cancel for JJ; they help QQ/KK a few dimes, not enough to call.

## Why this range is much stronger

An all-legal CO open still has a large JJ/QQ/KK (no joker) mass. Range 2
drops those and keeps AA, two pair+, and only the two joker-pairs. Combo
mix facing BN jacks (same deals as the JJ row):

| CO bucket | Share |
| --- | ---: |
| pair_A | 36.0% |
| two_pair | 27.9% |
| trips | 16.4% |
| two_pair_aces_up | 8.4% |
| straight+ (incl. boats / quads) | 8.5% |
| pair_Q_joker | 1.5% |
| pair_K_joker | 1.5% |

BN’s jacks win ~17% after locked draws. Calling an honest two-pair+ bet
then losing stacks extra: call EV ≈ −$2.85, worse than just losing the
$2 call. Raise-cd (−$2.26) loses *less* than that stacked call — checkdown
avoids paying off post-draw — but both are crushed by fold. Raising JJ
into AA+ is **not** a value raise (P(win) ≪ 0.5). That is the domination
story: the raise line is a dog, not a bluff-catcher, vs this range.

Vs a wide (all-legal) CO open the same BN jacks would be up against a
much larger one-pair mass. This file does not quote that agent’s numbers;
the qualitative contrast is that **BN should fold more low pairs** here,
and should fold **aces** as well.

## Raise bound (no multi-raise tree)

Call EV is an honest $6 street (BN as drawer). Raise EV is a **$10
checkdown** with CO always continuing. Those are not the same pot:

- A **dog** (JJ–AA, two pair) does not raise just because checkdown lost
  less than paying off two pair+ on the call line.
- A **favorite** (aces-up, trips) with +EV raise-cd is marked **raise**
  for value even when the $6 honest-call number is higher. Building the
  pot as a favorite is the bound we want; true raise-then-honest would
  sit above checkdown.

Two pair is the edge: both call and raise-cd are +EV vs fold, P(win) =
0.43 < 0.5, call is **+$0.22 ~ 1.9 SE**. Published action is **call**.
Raise-cd (+$0.32) is a slightly better numeric bound but is still a dog
putting in extra; do not treat it as a value raise. A later multi-raise
tree can revisit the mix.

Fold equity vs QQ/KK+joker is **not** in the raise bound. Those two
classes are ~3% of this tight range; folding them would not save JJ.

Seats 1–6 check-raising after BN acts is out of scope (would only make
calling worse). This is the unraised-CO-open HU leaf.

## Accounting (no live draw solver)

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked `tp1_tr2_q1`) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: pairs d=3, two pair d=1, trips d=2, quads d=1. CO draws first,
then BN. Honest post-draw policy matches the CO-vs-BN HU lab (opener is
still CO; BN two pair+ continues as an AA-strength drawer, not the raw
M2 fold).

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Range 2** | Tight CO open | AA+ plus QQ+joker / KK+joker; not all-legal |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
| **Value raise** | Favorite continue | P(win) > 0.5 and raise-cd +EV (aces-up / trips) |
