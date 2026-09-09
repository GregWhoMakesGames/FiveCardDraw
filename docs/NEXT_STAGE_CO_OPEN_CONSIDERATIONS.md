# Next stage: CO open considerations (range vs \(r\), BN bluffs, reverse-blockers, two-pair rank)

**Status: item 1 signed** ([research/button_vs_cutoff_range_vs_r.md](research/button_vs_cutoff_range_vs_r.md));
items 2–4 still soon. Parent: [research/INDEX.md](research/INDEX.md). Living
queue: [AGENTS.md](../AGENTS.md).

The BN-vs-CO **threshold grid** is signed (lookup below). Item 1 of these
four questions is **signed**. Items 2–4 are still **soon**, still in the CO
vs BN era, **before** HJ mixes. They are extra considerations the cutoff
should have before we treat the open chart as finished. Do not start
multi-raise or draw/post-draw as a way to skip them.

Signed lookup (BN vs a CO who plays the chart range at table slowplay \(r\)):

| \(r\) | JJ–KK | AA | Two pair | Aces-up / trips |
| --- | --- | --- | --- | --- |
| 0% (all legal) | fold | **raise** | raise | raise |
| 79–86% | fold | **fold** | raise | raise |
| 87–96% / tight | fold | fold | **call** | raise |

Two flips: **AA** leaves the raise as soon as bare JJ is out of CO (\(r=79\%\)).
**Two pair** leaves the raise once KK also needs a blocker (\(r=87\%\)).

---

## 1. Range vs slowplay rate (decomposition)

**Status: signed.** Frame:
[research/button_vs_cutoff_range_vs_r.md](research/button_vs_cutoff_range_vs_r.md).

Both published switches are **CO range**, not 1–6 trap rate. Chart-range at
trap \(=0\) already folds AA (r79) and calls two pair (r87). All-legal CO at
table \(r=79\%\) still value-raises AA; r86 CO at \(r=87\%\) still
value-raises two pair. Too-tight CO under 79% (tight polar at trap 0) folds
AA / calls two pair — also range. **No lookup row.**

Primary mix: fold-bound −$2 on the **call** line only; raise stays HU (no
multi-raise). The even-folding bound can turn the thin r87 two-pair *call*
negative; that is not two pair’s line (`sandbag_v1`). tight_proxy keeps
**call**. Fold-to-3-bet on the raise line would flip trap-only AA / two pair
and is the later multi-raise ticket.

---

## 2. BN bluff-raises (qualitative only until scheduled)

We have almost no pre-draw bluff work. BN-vs-CO so far is fold / call /
value-raise with **no** raise as a bluff. Polar all-legal even has **no air**
in CO, so a BN raise was value/protection vs jacks+.

**Question, not an answer.** If BN can raise a **weaker** hand, how does that
change the button line we just published?

Candidates (do not mix-solve yet):

- **One pair below the value-raise bar** — not only AA vs a wide CO, but
  JJ–KK where we currently fold.
- **Shorts** — underpairs hoping to improve on the draw.
- **Air with blockers** — e.g. joker + a king, cutting CO’s monsters,
  aces-up, AA, and KK.

A bluff-raise that sometimes works would mean the published “fold JJ–KK
always” line is a **no-bluff bound**. It would also change what CO must
continue with, and therefore which CO opens are +EV. Park a full tree until
this ticket is scheduled; do not smuggle it into multi-raise.

---

## 3. Count (Super System) — sign is the line, not the seat

Super System’s count was originally a **sandbagging** tool. Convention here:

- Count is **negative for sandbagging.** A trap wants someone else to *open*
  so they can raise. High count (blocking later legal opens and strong two
  pair) is **bad** for burying.
- Count is **positive for stealing.** An opener who would rather take the
  antes than play a bigger pot with a marginal hand wants to **block the
  continue range**.

**Do not assign the sign by seat alone.** The same seat can want high or low
count depending on **hand strength and the line** (bury vs steal vs value-open
hoping to get action).

Examples (do not compute in this ticket):

- **BN with trips** who *opens* is often hoping someone in 1–6 **sandbagged
  two pair**. `55543` vs `555KB` block different cards. One flavor can make
  a raise they still beat (and can reraise) more likely; the other can
  starve that action. That is not “button = steal, so count is always
  positive.”
- **BN with JJ** would be glad of **JJAKQ**: it blocks a lot of sandbag
  hands. The holding is also **stronger as a play** — if raised, discard the
  extra jack and draw to the straight; drawing one **looks like two pair**,
  which can push a weak two-pair sandbagger off, and a miss can still
  bluff post-draw. Count, disguised draw, and bluff all sit on the same
  hand.
- **HJ** might bury to raise a CO/BN open, or open a weak **KK** hoping CO
  and BN do **not** continue with a low two pair. Count is not good or bad
  for HJ until you know which line that holding is on.

The open chart already used **joker / ace** as blockers on 1–6 *traps*
(cutting slowplay raises). Rank blockers on the player *behind* (KK with
Q and J vs BN’s JJ/QQ) are the other half of the same count. Today BN
**folds JJ–KK to any CO open** on the no-bluff grid, so the CO-steal side
may look small until item 2 (bluff-raises) or item 4 (two-pair splits)
is live.

### Unknowns to investigate (do not start here)

Add these as separate follow-ups when item 3 is scheduled. One unknown per
PR is fine.

1. **Sign by class × line, not by seat.** For each of BN / CO / HJ, pin when
   high count helps a *sandbag*, a *steal*, and a *value open that wants a
   raise* (trips hoping to reraise two pair). Confirm the Super System
   convention: negative for sandbagging, positive for stealing.
2. **BN trips flavors.** Compare `55543` vs `555KB` (and close kin): which
   blockers raise \(P(\)a 1–6 sandbag raises a two pair BN still beats\()\)?
3. **BN JJAKQ as a package.** Blocking sandbags + discarding the jack to a
   straight if raised + one-card draw looking like two pair + miss-bluff.
   How much of the EV is count vs the draw/disguise?
4. **HJ count is hand-dependent.** Same seat: sandbag-to-raise-CO/BN vs
   weak KK hoping late seats do not continue. Do not publish a single HJ
   count sign.

HJ strategy (after CO vs BN) still uses this count; it does not get a
different definition.

---

## 4. Two-pair rank and blockers

We have been treating **two pair below aces-up as one class**. CO’s relevant
opens are now **mostly two pair and better**, so that lump is too coarse.

**Question.** How strong is the two-pair (KK-up vs 33-up, etc.), and with
what **blocker cards**? Split the class before we freeze CO opening or BN
call/raise on “two pair.”

Do not start pair-concealment draw mixes here (`d=3` vs `d=2` stays after HJ).

---

## Parallelism / ownership

One PR per item is OK. New frame files; do not rewrite polar product answers
or the signed lookup table except to add a row if a factor actually flips a
sign. INDEX: add **only your row**.

Reuse: `button_vs_cutoff*.py`, `cutoff_open_chart.py`, sandbag worlds.
No UTG re-solve, no HJ mixes, no 3:1/4:1 inventory in this ticket.
