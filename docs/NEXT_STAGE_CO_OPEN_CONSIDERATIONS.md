# Next stage: CO open considerations (range vs \(r\), BN bluffs, reverse-blockers, two-pair rank)

**Status: plan only. Do not compute in this ticket.** Parent:
[research/INDEX.md](research/INDEX.md). Living queue: [AGENTS.md](../AGENTS.md).

The BN-vs-CO **threshold grid** is signed (lookup below). These four questions
are **soon**, still in the CO vs BN era, **before** HJ mixes. They are extra
considerations the cutoff should have before we treat the open chart as
finished. Do not start multi-raise or draw/post-draw as a way to skip them.

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

The single table maps \(r\) → *ideal* CO range → BN action. Real CO may not
play that range: **wider** than \(r\) allows, or **tighter** despite a low
sandbag rate (especially **under 79%**, where the chart still says open every
legal).

BN’s response should depend on **both**:

- the **range** CO is actually opening, and
- \(P(\)seats 1–6 still have a slowplay trap\()\).

**Question.** How much of each switch (AA raise→fold; two pair raise→call) is
**CO range** vs **trap rate**? Hold one factor fixed and vary the other
(chart-range at the wrong \(r\); non-chart range at a known \(r\)).

Out of scope here: computing that grid. Method when started: reuse locked
BN-vs-CO leaves; do not rebuild post-draw Nash.

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

## 3. CO reverse-blockers (Super System count, negative)

This **is** Super System’s “count,” with the **sign flipped**.

A **sandbag** wants someone else to *open* so they can raise. Holding
**AAAKQ** (aces-up with KQ) makes a later legal open very unlikely: it
blocks strong two pair and legal one-pairs. Count is **positive** → better
to **open** than to bury, because the trap has nothing to raise.

A **CO opener** would rather **steal the antes** than play a bigger pot
out of position with a marginal holding. They want to **block BN’s
continuing range**. Count is **negative**. Example: KK with a queen and a
jack makes BN **JJ and QQ** less likely (fewer legal opens behind). When BN
*does* call or raise, the remaining continue range is stronger — more often
ahead of that KK.

The open chart already used **joker / ace** as trap-blockers in 1–6 (cutting
slowplay raises). Rank blockers on BN’s openers are the other half of the
same count. Today BN **folds JJ–KK to any CO open** on the no-bluff grid, so
the effect may be small until item 2 (bluff-raises) or item 4 (two-pair
splits) is live.

HJ still applies the **positive** count when we get there (after CO vs BN).
Do not wait for HJ to study the **negative** count at CO.

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
