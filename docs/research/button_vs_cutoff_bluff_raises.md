# Frame: can the button raise weaker than the published value bar?

Slug: **`button_vs_cutoff_bluff_raises`**. Parent: [INDEX.md](INDEX.md).
Ticket item 2:
[../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md).

Signed no-bluff lookup:
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md).
CO open chart: [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md).
Polar labs: [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md),
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md).
What already moves the value line:
[button_vs_cutoff_range_vs_r.md](button_vs_cutoff_range_vs_r.md).

**How to point at this work:** `evaluate button_vs_cutoff_bluff_raises`

This file is a **question frame**. It does not mix-solve, does not rebuild
post-draw strategy, and does not change the signed lookup. CO never sandbags
as the opener. The joker is an ace kicker, not trips.

Reuse later (do not restart): `button_vs_cutoff*.py`,
`cutoff_open_chart.py`, sandbag worlds. No new CLI in this PR.

## In short

When the button faces a cutoff open, the published line is fold / call /
value-raise only. Cutoff always stays in. A raise is then “is the button a
favorite on a bigger pot?” Under that rule the button **always folds jacks,
queens, and kings**. Aces raise only while cutoff is still opening every
legal hand. Two pair raises until cutoff’s kings need a blocker.

That table is what the button does if a raise is **never** allowed to make
cutoff fold. It is a **no-bluff bound**, not a claim that a weaker raise is
impossible.

**Question:** if the button may raise a weaker hand — hoping cutoff folds
some of the open, or hoping to improve on the draw — how does that published
line change?

Do not answer with a mix. Name the candidate hands. Name the two things a
working bluff would move: **what cutoff continues with**, and **which cutoff
opens stay profitable**. Park the tree that would measure them.

## Why today’s raise cannot be a bluff

Every locked BN-vs-CO cell uses the same raise leaf:

- Cutoff’s range is still jacks-or-better (all-legal, chart-range, or tight).
- There is no junk in that range, so fold equity vs air is **identically 0**.
- Cutoff **always calls** the raise. Pot into the draw is $10. Button has
  put in $4. Fold at this node is 0 (antes already in; cutoff takes them if
  the button folds).

So a raise with a dog is not a bluff. It is just a bigger pot as a
dog. That is why jacks / queens / kings fold even vs the widest cutoff
(all-legal: jacks P(win) = 0.203, raise-checkdown **−$1.98**; kings P(win) =
0.382, raise-checkdown **−$0.18**). Kings are closest and still not a
favorite.

Two-to-one drawing hands already make the same point from the other side:
they **call** (+$1.44 honest on all-legal) and they **do not raise**, because
there is nothing to fold and P(win) ≈ 0.35 is short of the ~40% a $10
checkdown needs. A weaker draw needs fold equity even more.

A bluff-raise is a **different laboratory**. Cutoff must have a fold-or-call
decision facing the first raise. That decision is the tree this file parks.
It is **not** the later multi-raise ticket (cutoff open, button raise, then a
trap or cutoff three-bet). Do not smuggle the first continue into that tree,
and do not start draw / post-draw as a way around it.

## Candidates (three buckets; do not mix)

Look at these separately. Do not glue them into one bluff range. Do not
solve frequencies.

### 1. One pair below the value-raise bar

Not only aces vs a wide cutoff. The published table already folds **jacks,
queens, and kings** against every chart range, including the all-legal polar
where aces still raise.

Locked no-fold-equity numbers, all-legal cutoff, cutoff always continues:

| Button | Honest call | Raise-checkdown | P(win) | Published |
| --- | ---: | ---: | ---: | --- |
| Jacks | −$2.29 | −$1.98 | 0.203 | **fold** |
| Queens | −$1.71 | −$1.11 | 0.290 | **fold** |
| Kings | −$1.10 | −$0.18 | 0.382 | **fold** |
| Aces | +$0.28 | +$1.45 | 0.545 | **raise** (value) |

Vs a tight cutoff those one-pair calls are around −$2.5 to −$2.9, P(win) ≈
0.17–0.20, and **aces fold too**. Joker or ace flavors on jacks / queens /
kings did not flip fold to call on that grid.

Aces vs all-legal are **not** a bluff: they are a thin favorite. They become
a candidate weaker-raise only once the table has already folded them
(\(r \ge 79\%\)), i.e. once they are no longer a value raise. The question
is the hands we **already fold**, especially kings (closest on the bound)
and then queens / jacks.

Questions, not answers:

- If cutoff starts folding bare jacks to a raise, do kings (then queens)
  beat fold? Jacks themselves are not close on today’s leaf.
- Does that happen only vs a **wide** cutoff, where jacks are still in the
  open? Vs a tight cutoff there is almost no weak one-pair left to fold
  out (tight polar: queens/kings with the joker are ~3% of what remains).
- Would a joker or ace on the button’s pair flip a *bluff*-raise even though
  it did not flip a call? Those cards block cutoff’s continue (aces, joker
  pairs, some two pair) rather than blocking the jacks you want to fold.

### 2. Shorts / underpairs

Pairs below jacks (twos through tens). They cannot open. They are not on the
published chart: today they fold to a cutoff open, and that fold is a large
part of cutoff’s steal.

If the button raises them, it is a semi-bluff: fold out cutoff’s worst
one-pair, or draw three and sometimes make trips. Showdown vs cutoff’s
jacks+ is worse than a face pair. Draw shape is the same as a face pair
(\(d=3\)). They do not block cutoff’s jacks / queens / kings the way a
matching face pair does.

Two-to-one draws are already a better drawing continue than an underpair,
and they still do not raise without fold equity. So an underpair raise is
not “like a 2:1 raise.” It needs cutoff to fold something, or it is just a
bigger pot with a worse hand.

Questions, not answers:

- Is any underpair a better bluff than folded jacks–kings because it is
  cheaper to give up when called? Or is it strictly worse, because it loses
  to the one-pair cutoff *keeps*?
- These hands currently **give cutoff the steal**. A raise converts a +$2
  steal into a raised pot. That is a different cost than raising a legal
  pair that was going to fold a $0 node anyway.
- Public \(d=3\) after a called underpair is a weak story. Do not start
  draw / post-draw here to chase that.

### 3. Air with blockers

Not a pair. Cannot open. Example from the ticket: **joker plus a king**.
One king and the bug is ace-high, not a pair of kings (the joker is an ace
kicker / fill, not a duplicate rank). If called, showdown is usually dead
unless the draw hits.

What that holding **removes from cutoff**:

- The bug: cutoff cannot have queens-or-kings-with-joker, aces with
  bug-as-ace, or a bug fill.
- One king: fewer kings, fewer king-up two pair, fewer trips of kings.

What it does **not** remove: cutoff’s jacks and queens — the hands you most
want to fold out. Blocking the continue and not blocking the fold is the
shape of a steal-side bluff. Item 3 (Super System count) will care about
the same cards for burying vs stealing. Do not compute count here; do not
assign a seat-wide sign.

Other flavors to name later, not compute: joker plus an ace (cuts cutoff
aces and every bug-pair; cuts kings less); joker plus a queen; king-high or
ace-high with no joker (weaker blocker, same empty showdown).

Questions, not answers:

- Is joker-plus-king the right first air candidate because it cuts cutoff’s
  strongest one-pair and the joker-pairs that survive even at a tight table?
- At \(r = 0\%\) cutoff still opens a lot of bare jacks. Those are the
  fold-outs. At \(r \ge 93\%\) cutoff has already passed jacks; at \(r \ge
  96\%\) the leftover one-pair is aces plus queens/kings with the joker.
  There may be **nothing left a bluff can fold**. If bluff-raises exist at
  all, they may live only vs a wide cutoff — the same place aces are already
  a value raise.
- How empty is too empty? Naked king-high without the joker blocks less and
  redraws worse.

## What a working bluff would do to cutoff

Today cutoff’s continue range facing a button raise is **everything that
opened**. The 0% open lab was built with “button calls every legal, never
raises.” The sandbag chart prices “fold to a 1–6 trap raise” as **−$2**.
Neither leaf is “button sometimes raises as a bluff, and cutoff may fold
the open.”

If some weaker button raises start working, three things move together:

1. **Cutoff has to fold some opens.** Otherwise there is no fold equity and
   the bluff is just lighting $4. The first hands to consider folding are
   the same ones already closest to pass on the open chart: bare jacks, then
   queens, then kings without a blocker.

2. **Cutoff’s *called* range gets stronger.** The button’s value raises
   (aces vs a wide cutoff; two pair through 86%; aces-up; trips) then face
   fewer jacks. Thin value can flip: aces vs all-legal and two pair vs 86%
   are already close. That is how a bluff-raise can change the **published
   value line**, not only add extra raising hands. The signed lookup does
   not get a new row until a tree actually flips a sign. That is unlikely
   from this frame alone; aces-up / trips staying a raise is especially
   unlikely.

3. **Which cutoff opens stay +EV.** Bare jacks at 0% are **+$1.44** vs pass
   mostly because the button has no legal ~75% of the time and cutoff
   steals +$2. When the button *is* legal, the 0% lab has the button
   **call**. Two leaks would eat that:

   - Legal button hands that currently fold (jacks–kings) or thin-value
     raise (aces) start raising more often: cutoff plays a bigger pot as a
     dog, or folds for −$2.
   - Illegal button hands that currently **fold and give the steal**
     (shorts, air) start raising: steal pots become raised pots. That is
     the larger mass.

   Direction, not a new chart: opening bare jacks gets worse, so the 79%
   “pass bare jacks” threshold could move **down**. Do not recompute the
   open chart here. Do not freeze it until this is measured. That is why
   this file sits before hijack and before multi-raise.

Item 1 still stands on the no-bluff grid: the aces / two-pair *action*
flips because cutoff’s opening hands get tighter, not because seats 1–6
trap more. A later three-bet tree could still let trapping matter. A
bluff-raise tree is a different knob: the extra raises come from **the
button**, including hands that were stealing cutoff’s antes.

## What would not change until a tree says so

- Aces-up and trips as a raise.
- Jacks through kings as a fold **if cutoff never folds a legal open**
  (today’s bound).
- Item 1’s tightness-vs-trap split of the published aces / two-pair flips.

A bluff that only works when cutoff still folds jacks would matter most at
**wide** cutoff (\(r = 0\%\) and just under 79%). That is also where aces
are already a value raise. So the first published cell a bluff might move
is kings / queens vs all-legal, not a new aces row on the signed table.

## Parked

- Mix-solving raise frequencies.
- The full fold / call / three-bet tree after the button raises (the
  multi-raise ticket).
- Draw and post-draw as a skip.
- Hijack, 3:1 / 4:1 inventories, concealment, Ring 1, UTG re-solve.
- Restarting the open chart, the polar labs, the threshold lookup, or
  range-vs-\(r\).

**First measurement, when scheduled.** Give cutoff a fold-or-call vs the
raise. Keep the locked draws and the existing polar / chart ranges. Test
**one** candidate bucket against **one** cutoff range. All-legal is the
obvious first range: that is where fold-outs still exist. Do not mix the
three buckets. Do not open a three-bet node to “finish” the continue.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **No-bluff bound** | Published BN vs CO table | Fold / call / value-raise with cutoff always continuing |
| **Bluff-raise** | Button raises weaker than the value bar | Not a favorite if cutoff always continues; needs fold equity or a draw |
| **Short** | Underpair | Twos through tens; cannot open; today part of cutoff’s steal |
| **Air with blockers** | No pair, chosen cards | e.g. joker + king: ace-high, not a pair; cuts cutoff’s kings / bug hands |
| **First continue** | Cutoff fold-or-call vs the raise | Parked here; not the multi-raise / three-bet tree |
