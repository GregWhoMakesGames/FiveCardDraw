# Next stage: BN sandbag probe + CO open/pass (parallel)

**Status:** Plan only. Do **not** compute the product answers in this ticket.
Parent: [research/INDEX.md](research/INDEX.md). Frames:
[research/button_open_sandbag_v1.md](research/button_open_sandbag_v1.md),
[research/cutoff_open_no_sandbagging.md](research/cutoff_open_no_sandbagging.md).

**Tabled.** Further Nash on the BN-vs-2:1 post-draw street (Ring 1 / Ring 2,
concealment) is frozen. Steal-weighted BN open EV is already known to nickels;
that work does not block these two questions.

Two agents may run **in parallel** after the shared pin below. They must not
edit the same chapter file. `INDEX.md` frames table: each agent adds **only
their own row** if it is missing; do not rewrite the other frame’s row.

---

## Shared pin (both agents copy; do not restyle)

Seats: 1 UTG … 5 **LJ**, 6 HJ, 7 **CO**, 8 BN.

**Sandbag-set v1** (100% pass these; refine later with data):

| Seats | Sandbag (do not open) |
| --- | --- |
| 1–7 | Two pair or better |
| 5 (LJ) and 7 (CO) **also** | Pair of aces |

HJ (seat 6) does **not** add aces in v1. Reuse `classify_opener` in
`showdown_matrix.py` (`two_pair` / `two_pair_aces_up` / trips+ vs `pair_A`).

**Voluntary opener v1** = open-legal minus that seat’s sandbag-set.
Under 100% sandbag, a seat opens iff it has a voluntary opener.

**Accounting (already pinned).** Pass = 0; fold to a raise after opening = **−$2**;
naked steal = **+$2**. 2:1 first callers still **call** (they do not raise) when
the opener’s range is jacks+.

---

## Agent A — `evaluate button_open_sandbag_v1`

**Question.** Relative to 0% sandbag (already done): if seats 1–7 sandbag the
v1 set **100%** of the time and **always raise** when BN opens, and BN **always
folds JJ** to a raise, is opening JJ −EV?

**Do not** answer QQ/KK/AA unless JJ is clearly signed and the extra classes are
free from the same deals.

### Method

1. **Decompose the folded-to-BN node** under 100% sandbag:
   - Seats 1–7 passed ⇒ none of them has a *voluntary* opener.
   - **Raise branch:** ≥1 of 1–7 still has a sandbag-set hand → they raise →
     BN folds JJ → **−$2**.
   - **No-raise branch:** none of 1–7 has a sandbag-set hand either ⇒ 1–7 have
     **no open-legal hands at all**. That leaf is the old
     `button_open_no_sandbagging` JJ open (steal + 2:1 call mix). **Reuse**
     locked-draw §3.4 JJ, do not rebuild post-draw Nash.
2. **Estimate** `P(raise | 7 passed, BN holds JJ)` with card removal (BN’s jacks
   block). Independent-seat planning first, then a seeded 8-way deal MC
   (condition BN is `pair_J`; condition 1–7 have no voluntary opener; measure
   fraction with ≥1 sandbag-set). Pin n and seed.
3. Mix: `EV = (1−p_raise) * EV_JJ_no_sandbag_open + p_raise * (−2)`.
   Compare to pass = 0. Report the sign and the two pieces, not a full range
   chart.
4. **Out of scope:** Ring 1, multiway raise caps, BN calling the raise,
   sandbag frequencies other than 0% (done) and 100% (this ticket).

### Code / docs ownership

- New: `src/fivecarddraw/validation/sandbag_v1.py` (seat predicates + deal MC)
- Frame: `docs/research/button_open_sandbag_v1.md` (findings live here)
- Tests + fixture under `tests/fixtures/validation/`
- May **read** `cascade_odds.py` / §3.4 JJ EV; do **not** edit
  `postdraw_nonbluff_ev.py` or Ch.5

---

## Agent B — `evaluate cutoff_open_no_sandbagging`

**Questions.** Seats 1–6 unable (0% sandbag, same as the BN steal lab). CO has
a legal hand. BN behind still opens **every** legal hand if CO passes, and
**continues** (v1: always call, never fold a legal) if CO opens.

1. Should CO open every legal class, or is **JJ** (then higher if needed) −EV
   because BN is behind?
2. Should CO ever **sandbag** (pass a sandbag-set hand) given steal EV when BN
   has no legal opener vs P(BN is legal)?

### Method

Pin two differences vs the BN lab, then EV by CO class (start **JJ**, then AA /
two pair if the mix is cheap):

**(a) BN behind.** Given CO’s cards, P(BN open-legal), P(BN is 2:1), P(≥1 of
seats 1–6 is 2:1). Reuse `p_one_seat_2to1` / deal MC with CO’s hand blocked.

**(b) Draw order.** Draw starts left of dealer; BN draws **last**.

| Matchup | Who draws first |
| --- | --- |
| BN opened, seat 1–6 2:1 called | Caller (already how M2 samples) |
| CO opened, BN called | **CO**, then BN |

Post-draw **betting** in the BN-vs-2:1 grids assumed opener first. For HU
CO vs BN, left-of-dealer first live player is CO, so opener-first betting
matches this matchup. Document that; do not silently reuse BN-as-last-to-act
draw sampling when BN is the caller.

**If CO opens (v1 branches):**

| BN / others | Leaf |
| --- | --- |
| BN not legal, no 2:1 in 1–6 or BN | Steal +$2 |
| BN not legal, 2:1 calls (1–6 and/or BN) | CO vs 2:1; CO draws first vs a BN 2:1 caller; vs a 1–6 caller the drawer still draws first. Reuse §3.4 as a **bound** only if draw order matches; otherwise resimulate that cell. |
| BN legal (calls) | **New** HU: CO class × BN open-legal range. Need a showdown / non-bluff post-draw grid (locked draws). This is the expensive new piece. |

**If CO passes a legal hand:**

| BN | Leaf |
| --- | --- |
| BN not legal | Dead hand / no steal → **0** (this is the cost of sandbagging) |
| BN legal, opens | Return-to-actor: CO may call/raise. For JJ that is “pass then face an open”; for two pair+ that is true sandbag. v1: if CO would have folded JJ to a BN open, passing JJ is 0 vs BN-legal and 0 vs BN-weak — strictly worse than opening unless the open-vs-BN-legal leaf is worse than 0. |

Sign **open vs pass** for JJ first. Sandbag (two pair+ / LJ-CO aces) is a second
table: open (risk BN legal) vs pass (give up steal, play vs BN open later).
Do not wait for Agent A’s 100% early-seat sandbag world; this frame is 0%
sandbag in seats 1–6.

### Code / docs ownership

- New: `src/fivecarddraw/validation/cutoff_open.py` (and a post-draw helper
  if CO-vs-BN needs its own sampler — do **not** overwrite `postdraw_nonbluff_ev.py`;
  wrap or copy the deal loop with a `drawer_is_bn` flag)
- Frame: `docs/research/cutoff_open_no_sandbagging.md`
- Narrative findings: [research/ch05_later_seats.md](research/ch05_later_seats.md) §5.1
- Tests + fixture
- Do **not** edit Agent A’s sandbag MC module except to **import** the shared
  seat predicates if Agent A lands first; otherwise duplicate the 15-line
  predicate from this pin and reconcile later

---

## Parallelism

| | Agent A (BN sandbag) | Agent B (CO open) |
| --- | --- | --- |
| Needs the other’s **result**? | No. No-raise leaf is the old BN JJ EV. | No. 0% sandbag in 1–6; BN always opens legal. |
| Shared code | `classify_opener`, steal/−$2 accounting, 2:1 inventory | Same |
| Likely collisions | `INDEX.md` (one row), `sandbag_v1.py` if both write it | `INDEX.md`, `ch05_later_seats.md`, new CO modules |
| Safe | A does not touch Ch.5 or CO post-draw | B does not touch BN sandbag MC or Ch.3 §3.4 fixtures |

**Verdict: yes, parallel**, if Agent A owns `sandbag_v1.py` + the sandbag frame,
Agent B owns CO modules + Ch.5 §5.1, and neither rewrites `postdraw_nonbluff_ev.py`.

If only one agent is available: do **A first** (smaller: mix two leaves, no new
post-draw street). B is the larger build (CO vs BN made-hand EV).
