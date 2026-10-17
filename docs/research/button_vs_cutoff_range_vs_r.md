# Frame: what actually changes BN’s line vs a cutoff open

Slug: **`button_vs_cutoff_range_vs_r`**. Parent: [INDEX.md](INDEX.md).

**How to point at this work:** `evaluate button_vs_cutoff_range_vs_r`

Code: `src/fivecarddraw/validation/button_vs_cutoff_range_vs_r.py`.
CLI: `analyze-button-vs-cutoff-range-vs-r`.
Fixture: `tests/fixtures/validation/button_vs_cutoff_range_vs_r.json`.

Signed lookup (unchanged):
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO open chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).
Polar labs: [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md),
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md).

CO never sandbags as the opener. The joker is an ace kicker, not trips. This
file reuses locked numbers; it does not rebuild post-draw strategy.

## In short

We already have a table for the button facing a cutoff open:

| When early seats slowplay this often | BN with aces | BN with two pair |
| --- | --- | --- |
| Never (0%) | **raise** | raise |
| 79–86% | **fold** | raise |
| 87% and up | fold | **call** |

The table’s left column is “how often seats 1–6 bury a strong hand.” When that
rate goes up, **two** things tend to move together:

1. **Cutoff opens tighter.** The open chart drops weak jacks, then queens,
   then kings. At 0% cutoff opens every legal hand. At 79% it stops opening
   bare jacks. At 87% kings need an ace or the joker.
2. **Someone in seats 1–6 is more likely to wake up and raise** after cutoff
   opens (a slowplay trap).

The old table could not tell those apart. This lab asks a simple question:

**When the button’s line changes, is that because cutoff’s hand is stronger,
or because a trap behind is more likely?**

**Answer: because cutoff’s hand is stronger.** How often the early seats trap
barely moves the button’s *action* here. The published table stays as-is.

## What we ran

Take the locked button-vs-cutoff results (already computed for “cutoff opens
this set of hands, then heads-up”). Then mix in trap chance as a second
knob, one at a time:

- **Same cutoff hands, more trapping.** Example: cutoff still opens every
  legal hand, but seats 1–6 trap 79% of the time.
- **Tighter cutoff hands, no trapping.** Example: cutoff has already dropped
  bare jacks, but nobody in 1–6 is trapping.

If the button’s action changes in the first experiment, trapping did it. If
it changes in the second, cutoff’s opening hands did it.

A button raise that then gets three-bet by a trap is a later ticket
(multi-raise). Here a raise is still “play heads-up vs cutoff.” A call can
get raised by a trap; we mix that in.

## Aces

Published change: **raise** when cutoff is wide → **fold** once cutoff stops
opening bare jacks.

| Cutoff opens | Early seats trapping? | Button with aces |
| --- | --- | --- |
| Every legal hand | No | **raise** |
| Every legal hand | Yes (79%) | still **raise** |
| No bare jacks (the 79% chart) | No | **fold** |
| Tight (aces+ / QQ·KK with the joker) | No | **fold** |

Dropping bare jacks from cutoff is enough to fold aces, even if nobody traps.
Leaving cutoff wide and turning traps on is **not** enough: aces are still a
favorite vs that wide range, so the button still raises.

Practical read: if cutoff is dumping any jacks, keep raising aces. If cutoff
is already skipping bare jacks, fold aces even at a table that never
slowplays.

## Two pair

Published change: **raise** → **call** once cutoff’s kings need an ace or the
joker.

| Cutoff opens | Early seats trapping? | Button with two pair |
| --- | --- | --- |
| Kings still any kicker (86% chart) | No | **raise** |
| Kings still any kicker | Yes (87%) | still **raise** |
| Kings need ace/joker (87% chart) | No | **call** |
| Every legal hand | Yes (87%) | still **raise** |
| Tight polar | No | **call** |

Again the published change is cutoff getting stronger (kings leaving unless
they have a blocker). Trapping on top of the *wider* 86% range does not take
two pair off the raise — it is still a small favorite.

There is a thin extra effect that is **not** that published change: two pair’s
call vs the already-tight 87% cutoff is only about +$0.32. If you then assume
the button *folds* whenever a trap raises, that call goes negative. We do not
treat that as the line. Two pair is not a hand you auto-fold to a raise, and a
kinder “play vs the trap” estimate stays a call (~+$0.27). So the table does
not get a new fold row.

## If cutoff leaks

| What cutoff actually does | Button aces | Button two pair |
| --- | --- | --- |
| Opens every legal hand even when the table traps a lot (too loose) | **raise** | **raise** |
| Opens tight even when the table never traps (too tight) | **fold** | **call** |
| Follows the chart | the signed table | the signed table |

Watch **which hands cutoff opens**, not how often 1–6 buried something, to
decide aces and two pair on this street.

Trap rate still matters for *whether cutoff should open* in the first place
(that is the open chart: bare jacks die near 79% because they get raised too
often). This file is only: cutoff already opened; now what does the button
do?

## Numbers (same leaves as the polar / chart labs)

Trap chance on the locked curve: 0% → 0; 79% → 0.419; 87% → 0.449; 100% →
0.494.

Aces vs all-legal cutoff: call +$0.275, raise-checkdown +$1.454, P(win) =
0.545 (**raise**). Aces vs the 79% cutoff: call −$0.242, P(win) = 0.491
(**fold**). Mixing 79% trap into the all-legal *call* makes call −$0.68; the
raise is still +$1.45, so the action stays raise.

Two pair vs 86% cutoff: P(win) = 0.505 (**raise**). Vs 87% cutoff: P(win) =
0.464, call +$0.318 (**call**).

Locked draws and accounting match the earlier labs (fold = 0; call = honest
$6 street − $2; raise = $10 checkdown − $4; cutoff always continues; no
three-bet tree).

## Out of scope

Button bluff-raises, Super System count, splitting two-pair ranks, multi-raise
before the draw, draw/post-draw, hijack, 3:1/4:1, concealment, Ring 1, UTG
re-solve. Do not restart the open chart, the polar labs, or the threshold
lookup.
