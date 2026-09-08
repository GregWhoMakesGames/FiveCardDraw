# Frame: button vs tight cutoff open (range 2)

Slug: **`button_vs_cutoff_tight`**. Parent: [INDEX.md](INDEX.md) research frames.
0% all-legal CO lab: [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md)
(invert the seats: that file is CO vs BN legal; this file is BN vs a
**constructed** CO range). Flavor pins that motivate the range:
[cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) (joker / ace section).

**How to point at this work:** `evaluate button_vs_cutoff_tight`

Another agent owns BN vs **all-legal** CO. This file is **only range 2**.
Do not paste that agent's numbers here.

Code: `src/fivecarddraw/validation/button_vs_cutoff_tight.py`.
CLI: `analyze-button-vs-cutoff-tight`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_tight.json`.
Seed `20260907`, n_hu=4000.

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

*Filled after the seeded HU grid. Placeholder until `--write-fixture`.*

| BN | flavor | action vs tight CO | EV(call) | EV(raise-cd) |
| --- | --- | --- | ---: | ---: |
| pair_J | class / joker / ace | TBD |  |  |
| pair_Q | class / joker / ace | TBD |  |  |
| pair_K | class / joker / ace | TBD |  |  |
| pair_A | class | TBD |  |  |
| two_pair | class | TBD |  |  |
| two_pair_aces_up | class | TBD |  |  |
| trips / trips_A | class | TBD |  |  |

## Why this range is much stronger

An all-legal CO open still has a large JJ/QQ/KK (no joker) mass. Range 2
drops those and keeps AA, two pair+, and only the two joker-pairs. BN's
jacks are often **dominated**; BN should **fold more low pairs** than vs a
wide CO open. Raise is a different story too: raising JJ into AA+ is
usually dominated by calling (or folding). Trips+ / aces-up may raise for
value. Bound only — no multi-raise tree.

## Accounting (no multi-raise, no live draw solver)

| Action | Leaf |
| --- | --- |
| **Fold** | 0 (ante sunk) |
| **Call** | Honest $6 street (BN as drawer, locked draws) − $2 |
| **Raise bound** | Checkdown on a $10 pot − $4; CO always continues |

Draws: locked `tp1_tr2_q1` (pairs d=3, two pair d=1, trips d=2, quads d=1).
CO draws first, then BN. Honest post-draw policy matches the CO-vs-BN HU
lab (opener is still CO). Fold equity vs QQ/KK+joker is **not** in the
raise bound; those two classes are a small slice of this tight range.

Seats 1–6 check-raising after BN acts is out of scope (would only make
calling worse). This is the unraised-CO-open HU leaf.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Range 2** | Tight CO open | AA+ plus QQ+joker / KK+joker; not all-legal |
| **Raise-cd** | Raise bound | Checkdown $10, CO always continues |
