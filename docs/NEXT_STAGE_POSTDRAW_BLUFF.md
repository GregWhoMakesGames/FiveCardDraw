# Next stage: post-draw bluff 3-bet (Ring 1 indifference)

**Status:** Ring 1 implemented (`src/fivecarddraw/validation/bluff_indifference.py`,
CLI `analyze-postdraw-bluff`). Fixture
`tests/fixtures/validation/postdraw_bluff_summary.json`. Polar leftover for
two pair/trips is **fold**. Do **not** start Ring 2 until a later ticket;
this branch stops at the pinned indifference.

**Product question:** On the raise node, if the caller folds a straight or
flush to a BN **flush+** 3-bet, BN is incentivized to bluff 3-bet some two
pair / trips. What mix makes the **marginal** caller (expected: flush)
indifferent between **calling and folding** the 3-bet?

Parent (honest value line, no bluff 3-bets):
[NEXT_STAGE_POSTDRAW_CAP.md](NEXT_STAGE_POSTDRAW_CAP.md) and
[research/ch03_dealer_opening.md](research/ch03_dealer_opening.md) §3.5.
Call-it-down baseline: [NEXT_STAGE_NONBLUFF_EV.md](NEXT_STAGE_NONBLUFF_EV.md)
(§3.4 cells stay bet+1; this ticket is a **bluff delta on the cap node**).

This is the first slice of a reusable bluff-question library. Later streets
(miss stabs, CO return-to-actor) should call the same indifference helpers,
not a third street simulator.

---

## Why the honest line is not equilibrium

Cap findings (seed 20260902, combo-weighted raise node):

| Fact | Number |
| --- | --- |
| P(raise node) under locked BN draws | 0.189 |
| Pot after BN 3-bet, $4 to caller | **$26** (break-even call equity \(4/30 \approx 13.3\%\)) |
| Full cap pot | $38 |
| Vs BN **flush+** 3-bet, no air | caller **straight** fold (call EV −12 vs fold −8) |
| | caller **flush** fold (call EV −10.5 vs fold −8, ~5% equity) |
| | caller SF / boat_plus **cap** |
| Honest BN vs a *calling* responder | 3-bet flush+, call straights / two pair / trips |

If the caller actually folds non-SF, a two-pair/trips **bluff 3-bet** that
gets a fold is about **+14** EV_bn vs **−4** for folding the raise (or **−8**
for calling and losing at $22). Calling is strictly dominated: two pair/trips
are drawing dead to a straight+ raiser and need ~18% equity to call $4 into
$18. Ring 1 leftover is therefore **fold**, not call. As air enters the 3-bet
range, flushes gain equity and start to call. The mix that stops the loop is
the indifference frequency below — not “bluff 0%” and not “bluff 100%.”

A **single** \(\alpha\) cannot make every caller hand indifferent to fold,
call, **and** cap. Ring 1 asks only: make **flushes** indifferent to
**call vs fold**. Report whether straights still fold and whether SF still
caps. That is the textbook polar model.

---

## Ring 1 (do this; lock these knobs)

Condition on the **same raise node** as the cap module: BN two pair+ (bets)
∩ caller straight+ (raises). Reuse `on_raise_node`, `play_raise_node`,
`family_bucket`, and the locked-range generator. Do **not** re-grid class × d.

### BN strategy (polar)

| Bucket | Action |
| --- | --- |
| flush, boat+ (FH / quads / SF / five aces) | **Always 3-bet** (value). Sensitivity: also report boat+ only. |
| straight | **Always call** (Ring 1 does not mix broadway A). |
| two pair / trips | Mix: 3-bet with frequency **β** (uniform in the family). **Else fold.** |

Report both:

- **β** = P(3-bet | two pair or trips)
- **α** = bluff share of 3-bets = mass(two pair/trips 3-bets) / mass(all 3-bets)

Solve for the **β** (hence α) that sets caller-flush \(EV_{\text{call}} = EV_{\text{fold}}\)
on the combo-weighted node sample. Root-find; do not hand-tune.

### Caller strategy (held while searching β)

| Bucket | Action |
| --- | --- |
| straight flush (family `boat_plus` that is SF; pin SF via `fine_bucket` / category) | **Cap** |
| flush | **Call or fold** — this is the indifference target |
| straight | Call or fold as a **report**, not a search knob. Hypothesis: still **fold** at flush-indifferent β. |

BN vs a cap: **value calls, bluffs fold** (two pair/trips fold a cap; flush+
calls). No 5th bet.

### Chip pins

After BN 3-bet: pot $26, $4 to call. `POT_ODDS_TO_CALL(26, 4) == 4/30`.
Caller fold EV_bn / EV_caller from `play_raise_node(..., caller_vs_3bet="fold")`
must match the cap unit tests (BN +14 / caller −8 when the steal works).

Use combo-weighted locked deals (`tp1_tr2_q1`, caller keep-4 d=1) as the
**mass** sample. Extra per-class deals may fill thin flush cells; label them.
Same seed family as cap (`20260902`) is fine if the generator is unchanged.

### What to print

- β*, α*, n in each family
- Caller flush EV_fold, EV_call, EV_cap at β* (EV_call ≈ EV_fold)
- Caller straight EV_fold vs EV_call at β* (pure fold or not)
- Node EV_bn at β* vs (a) call-it-down and (b) honest flush+ 3-bet / else-fold
  two pair / cap-SF **with no air** — this is the bluff-only delta (leftover
  fold is already in both the polar mix and that no-air line)
- Sensitivity: value range = boat+ only (flushes do not 3-bet)

---

## Ring 2 (not yet)

Bucketed Nash on this node: BN and caller mix by family (optionally split by
public \(d\)), actions {fold, call, 3-bet} × {fold, call, cap}. Fictitious play or
tiny CFR on `play_raise_node` payoffs.

**Do not start Ring 2** until Ring 1’s fixture is on the branch and the
hypotheses below are confirmed or refuted in that fixture. Ring 2 is a later
ticket that should import Ring 1’s library, not a rewrite.

---

## Function library (build in Ring 1, keep)

Put helpers where later bluff tickets can import them (new module e.g.
`src/fivecarddraw/validation/bluff_indifference.py`, used by a thin
`postdraw_bluff.py` CLI). Do **not** fork `play_deal`.

| Helper | Contract |
| --- | --- |
| Node sample | Raise-node deals (reuse cap generator / `on_raise_node`) |
| `COMPUTE_STRATEGY_EV(deals, bn_mix, caller_mix)` | Mean EV_bn, EV_caller via `play_raise_node` |
| `INDIFFERENCE_ROOT(deals, value_buckets, bluff_buckets, catcher_bucket)` | β (or α) s.t. catcher \(EV_{\text{call}}-EV_{\text{fold}}=0\) |
| `BEST_RESPONSE(deals, opponent_mix)` | Argmax action per own family bucket |
| Pot-odds pin | `POT_ODDS_TO_CALL(26, 4) == 4/30` |

`BEST_RESPONSE` can wait until the end of Ring 1 (useful as a check: at β*,
flush BR is mix/indifferent; straight BR is fold). Do not implement CFR in
Ring 1.

---

## What to reuse (do not redo)

| Artifact | Use |
| --- | --- |
| `play_raise_node` / `CapPolicy` / `StreetState` | Payoffs; max_raises=3 |
| `on_raise_node`, `family_bucket`, `fine_bucket` | Same node and labels as cap |
| Locked range + 2:1 keep-4 | Same 18,396; `LOCKED_BN_DRAW` |
| Cap fixture numbers | Honest no-air baseline for the delta |
| `POT_ODDS_TO_CALL` | Break-even equity |

Do **not** re-run the class × d grid, Stage C, pair concealment, M2 knobs,
or pre-draw trees.

---

## Hypotheses to confirm or refute (Ring 1)

1. There exists β* ∈ (0, 1) making **flush** call EV equal fold EV
   (tolerance ~0.05 chips). **Confirmed** (β* = 0.0155; Δ = 0.00 chips).
2. At that β*, **straights still fold** (call EV < fold EV). **Confirmed**
   (call −8.74 vs fold −8.00). SF still caps.
3. α* is on the order of pot odds vs residual flush equity: with ~5% flush
   equity vs a pure flush+ value range, polar math suggests
   α ≈ (0.133 − 0.05) / (1 − 0.05) ≈ **9%** of 3-bets are air. **Compute
   it; do not pin 9% until the root-find says so.** **Computed: α* = 0.1016
   (~10.2%),** not the 9% sketch (sketch used a round 5% residual; the
   sample’s flush equity vs flush+ is a bit lower).
4. Bluff delta vs honest no-air flush+ 3-bet is **positive** for BN on the
   node (small), and vs call-it-down still positive. **Confirmed** vs the
   same caller as Ring 1 (fold non-SF, cap SF) **with leftover fold**:
   Δ = **+0.21** vs no-air flush+ 3-bet / else-fold two pair,
   **+3.45** vs call-it-down (almost all of that is folding trash instead
   of calling it). Vs the cap-module *calling* responder (cap SF / call
   rest, no air, leftover fold, EV_bn −1.71) β* is **−0.17** — that line
   already gets paid by calling flushes, so adding air while making
   flushes indifferent is not a raise on *that* EV. The polar question is
   the folding-catcher world.
5. Boat+-only value 3-bets need **more** air to make flushes indifferent
   (flushes are drawing dead to boats). **Confirmed** (α* = 0.153 vs 0.102).

---

## Findings (seed 20260902, Ring 1)

Combo-weighted locked BN draws (`tp1_tr2_q1`), 40,000 deals, **7,559** on
the raise node (same generator/seed as the cap fixture). Extra per-class
deals fill fine flush cells and are **labeled**; they do not enter β*.

Root-find: flush EV_call = EV_fold on the 3-bet subtree (fold is −8).
Leftover two pair/trips **fold** the raise (−4), not call (−8). β* did
not move (it is set on the 3-bet subtree).

| Quantity | Value |
| --- | ---: |
| β* = P(3-bet \| two pair or trips) | **0.0155** |
| α* = air share of 3-bets | **0.1016** |
| Leftover two pair / trips | **fold** |
| BN value 3-bets (flush+) | 851 |
| BN two pair / trips (bluff candidates) | 6,205 |
| Caller flush (catcher) | 1,530 |
| Flush EV_fold / EV_call / EV_cap at β* | −8.00 / −8.00 / −11.28 |
| Straight EV_fold / EV_call | −8.00 / −8.74 (**fold**) |
| SF/boat+ vs 3-bet | **cap** |
| Node EV_bn at β* | **−1.88** |
| vs call-it-down (−5.32) | **+3.45** |
| vs no-air flush+ 3-bet, else-fold, fold non-SF (−2.09) | **+0.21** |
| vs no-air flush+ / else-fold / cap-SF / call rest (−1.71) | −0.17 (different caller) |
| Boat+-only value: β* / α* | 0.0195 / **0.153** |

Family-level flush indifference is a **blend**: labeled extra cells show
ace-high flushes still prefer call (Δ ≈ +1.58) while jack-and-under prefer
fold (Δ ≈ −3.5 to −3.7). Ring 1 does not split flush ranks.

BN best-response *vs this held caller* (fold catchers, cap SF) still
wants to 3-bet two pair/trips (3-bet EV +12.3 vs fold −4 vs call −8) and
even straights (steals print); boats are slightly happier calling because
only SF continues. Fold beats call by **$4** on two pair/trips — that is
why leftover is fold. Ring 1 does **not** follow the always-3-bet BR —
value stays flush+, straights stay call, air is only the β* mix. That
tension is Ring 2.

**Do not substitute these for the §3.4 class × d cells or the §3.5 cap
value table.** Those remain no-air / bet+1.

CLI: `analyze-postdraw-bluff`. Library:
`src/fivecarddraw/validation/bluff_indifference.py`
(`COMPUTE_STRATEGY_EV`, `INDIFFERENCE_ROOT`, `BEST_RESPONSE`, `POT_ODDS_TO_CALL`).

---

## Deliverables

1. Indifference helpers + Ring 1 CLI (`analyze-postdraw-bluff`) — **done**
2. `outputs/validation/` tables + checked-in summary fixture — **done**
3. Pytest: pot odds 4/30; steal EV when caller folds; β* exists and flushes
   are indifferent; straights fold; cap path still `max_raises=1` by default
   for M2 / non-bluff — **done**
4. Short findings in this doc + [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md)
   §3.6 — **done** (do not rewrite §3.4 / §3.5 tables)
5. Do **not** claim the non-bluff class × d table or the cap value table
   already includes bluff 3-bets — **stated**

---

## Out of scope (Ring 1)

- Ring 2 Nash / CFR / public-\(d\) info sets
- Mixing BN straights (broadway A stays a cap-module footnote)
- Splitting two pair vs trips, or aces-up vs small two pair
- Bluff 3-bets with missed draws / one pair (not on this node: BN did not bet)
- Caller mixing cap vs call with flushes (report EV_cap; do not solve it)
- Miss / face-pair stabs; Stage C check-mix; pair concealment
- Multiway; UTG; sandbagging; pre-draw (Ch.2 §2.9); CO return-to-actor (Ch.5 §5.2)
- Replacing `HandValue` ordering

---

## Handoff checklist (Ring 1 — done)

1. Cap street is on the branch (`play_raise_node`, `analyze-postdraw-cap`)
2. Ring 1 library + CLI + fixture pinned (β* = 0.0155, α* = 0.1016)
3. Raise-node generator reused; class × d grid not re-run
4. Flushes indifferent; straights fold; SF caps; leftover two pair/trips
   **fold**; bluff-only delta vs no-air else-fold = +0.21, vs call-it-down
   = +3.45 (mostly folding trash)
5. This doc + Ch.3 §3.6 updated. **Stop.** Ring 2 is a follow-up ticket.
