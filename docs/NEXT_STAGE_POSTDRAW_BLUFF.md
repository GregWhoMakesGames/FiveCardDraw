# Next stage: post-draw bluff 3-bet (Ring 1 indifference)

**Status:** Not started. Do **Ring 1 first**. Stage C (always check two pair)
**changes the node and the air pool** — read
[After Stage C](#after-stage-c-two-pair-never-reaches-this-line) before
coding. Do not start Ring 2 (bucketed Nash) until Ring 1 has a checked-in
fixture and the per-`d` indifference numbers are pinned.

**Product question:** On the raise node, if the caller folds a straight or
flush to a BN **value** 3-bet, BN is incentivized to bluff 3-bet some **trips**
that did not improve. (Two pair never bets after Stage C, so it never 3-bets.)
What mix makes the **marginal** caller (expected: flush) indifferent between
**calling and folding** the 3-bet — **conditional on public \(d\)**?

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
gets a fold is about **+14** EV_bn vs **−8** for calling and losing at $22.
That invites air. As air enters the 3-bet range, flushes gain equity and
start to call. The mix that stops the loop is the indifference frequency
below — not “bluff 0%” and not “bluff 100%.”

A **single** \(\alpha\) cannot make every caller hand indifferent to fold,
call, **and** cap. Ring 1 asks only: make **flushes** indifferent to
**call vs fold**. Report whether straights still fold and whether SF still
caps. That is the textbook polar model.

---

## After Stage C: two pair never reaches this line

Stage C ([NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md)):
BN **always checks two pair** (all public \(d\)); always bets trips and boat+.
The checked-in cap fixture still uses the pre-C street (`p_bn_bets = 1` for
two pair; node = BN two pair+ ∩ caller straight+). **Do not reuse that node
definition or the pooled “fold all flushes” best response.**

### Does α / β change?

Definitions (same as Ring 1 below):

- \(\alpha\) = bluff **share of 3-bets** = mass(air 3-bets) / mass(all 3-bets)
- \(\beta\) = P(3-bet | air candidate)

**α is a property of the 3-bet range, not of the candidate pool.** Flush
indifference is pot odds (\(4/30 \approx 13.3\%\)) vs residual equity against
the **value** portion of the 3-bet. Removing two pair from the *candidates*
does not, by itself, change the target α: you 3-bet a **larger fraction of
the remaining trips** (β up) so that air is still ~α of 3-bets.

That “α stays, β rises” story is true **only inside one information set**
with an unchanged value range. After Stage C it is the wrong picture for
two reasons:

1. **Two pair leaves the node entirely** (they check). Air candidates on a
   BN-bet line are **trips that did not boat** — not two pair ∪ trips.
   Combo-weighted cap mass (seed 20260902, 7,559 node deals) plus Stage A
   finals: ~3,985 unimproved two pair drop off; remaining air ≈ **2,260
   trips**; remaining flush+ value ≈ **820**. In a still-pooled node,
   β among trips is about **3×** the old β among two pair ∪ trips. α is
   unchanged *in that pooled model*.
2. **Public \(d\) splits the value range**, so α itself is not one number.
   The cap’s “flush has ~5% equity vs flush+” and the ~9% textbook α mix
   boats from *draws* into the same 3-bet as pat flushes. The caller sees
   \(d\).

### Two lines that can 3-bet (both missed)

The cap / Ring 1 draft treated one pooled raise node. These are different
info sets:

| Line | BN start → public \(d\) | After C, BN bets with | 3-bet value | 3-bet air | Caller vs a 3-bet |
| --- | --- | --- | --- | --- | --- |
| **1 — trips draw** | Trips `d=2` (or `d=1` unified); pairs `d=3` that made trips | Unimproved trips, or boat+ | Boat+ from that draw | Unimproved **trips** only | Flush is drawing dead to boats. Fold-non-SF is plausible; α nearer full pot odds (~13%) |
| **2 — pat straight+** | Straight / flush / rare boat+ **stand** (`d=0`) | The pat hand | Flush + rare starting boat+ | **None** (no trips/two pair on `d=0`) | BN is usually a straight or flush, rarely better than a flush. **Do not fold all flushes.** Call (or mix) at least some flushes; straights still lose to flush+ |

C-primary extras (not a third bluff line):

- **`d=1`:** two pair that *improved* to boat+, plus quads. Unimproved two
  pair **checks**. A 3-bet here is almost always nuts. Fold non-SF.
- **`d=3`:** same structure as line 1 (pair → trips air vs pair → boat
  value). Two pair from pairs checks.

Line 1 is the only remaining **bluff** 3-bet. Line 2 is a **value** 3-bet
whose caller strategy was inferred from a boat-heavy pooled range and is
likely too tight.

Ring 1 must solve α / β **per public \(d\)** (at least `d=0` vs `d∈{2,3}`;
prefer `d=0,1,2,3`). Bluff bucket is **trips**, not two pair / trips.
Redefine the raise node as Stage C betting: BN bets trips+ / boat+ (not
two pair) ∩ caller straight+.

---

## Ring 1 (do this; lock these knobs)

Condition on the raise node **after Stage C**: BN **bets** (trips or boat+;
two pair checks) ∩ caller straight+ (raises). Reuse `play_raise_node`,
`family_bucket`, and the locked-range generator. **Rewrite** `on_raise_node`
(or pass a Stage C bet flag) — the cap helper still treats two pair as a
bet. Split the sample by public \(d\). Do **not** re-grid class × d.

### BN strategy (polar, per public \(d\))

| Bucket | Action |
| --- | --- |
| flush, boat+ (FH / quads / SF / five aces) | **Always 3-bet** (value). Sensitivity: also report boat+ only. |
| straight | **Always call** (Ring 1 does not mix broadway A). |
| trips (unimproved) | Mix: 3-bet with frequency **β(d)** on lines where trips bet (`d=2` primary, `d=3` from pairs; `d=1` if unified). Else call. |
| two pair | **Not on this node** (Stage C check). Do not put them in β. |

Report both, **per \(d\)** (and a pooled number only as a footnote):

- **β(d)** = P(3-bet | trips, public \(d\))
- **α(d)** = bluff share of 3-bets = mass(trips 3-bets) / mass(all 3-bets) on that \(d\)

Solve for the **β(d)** (hence α(d)) that sets caller-flush
\(EV_{\text{call}} = EV_{\text{fold}}\) on the combo-weighted node sample
**restricted to that \(d\)**. Root-find; do not hand-tune. On \(d=0\) the
air mass is ~0 — report that flush indifference is **not** reachable by
trips bluffs, and give flush EV_call vs EV_fold vs a pure flush+ 3-bet.

### Caller strategy (held while searching β)

| Bucket | Action |
| --- | --- |
| straight flush (family `boat_plus` that is SF; pin SF via `fine_bucket` / category) | **Cap** |
| flush | **Call or fold** — this is the indifference target **on \(d\) where BN has air**. On \(d=0\), hypothesis: **call** (or mix) vs a flush-heavy pat 3-bet; do not start from fold-all. |
| straight | Call or fold as a **report**, not a search knob. Hypothesis: still **fold** on \(d>0\) at flush-indifferent β; also fold on \(d=0\) (behind flush+). |

BN vs a cap: **value calls, bluffs fold** (trips fold a cap; flush+ calls).
No 5th bet.

### Chip pins

After BN 3-bet: pot $26, $4 to call. `pot_odds_to_call(26, 4) == 4/30`.
Caller fold EV_bn / EV_caller from `play_raise_node(..., caller_vs_3bet="fold")`
must match the cap unit tests (BN +14 / caller −8 when the steal works).

Use combo-weighted locked deals (`tp1_tr2_q1`, caller keep-4 d=1) as the
**mass** sample, with Stage C betting (check two pair). Extra per-class
deals may fill thin flush cells; label them. Same seed family as cap
(`20260902`) is fine if the *generator* is unchanged — the **bet filter**
must change.

### What to print

- β*(d), α*(d), n in each family **and** each public \(d\)
- Caller flush EV_fold, EV_call, EV_cap at β*(d) (EV_call ≈ EV_fold where air exists)
- Caller straight EV_fold vs EV_call at β*(d) (pure fold or not)
- On \(d=0\): flush EV vs a no-air flush+ 3-bet (expect call ≥ fold)
- Node EV_bn at β* vs (a) call-it-down and (b) honest flush+ 3-bet / cap-SF
  **with no air** — this is the bluff delta (do not use the pre-C node mass 0.189)
- Sensitivity: value range = boat+ only (flushes do not 3-bet)

---

## Ring 2 (not yet)

Bucketed Nash on each public-\(d\) node: BN and caller mix by family,
actions {call, 3-bet} × {fold, call, cap}. Fictitious play or tiny CFR on
`play_raise_node` payoffs.

**Do not start Ring 2** until Ring 1’s fixture is on the branch and the
hypotheses below are confirmed or refuted in that fixture. Ring 1 already
**conditions on public \(d\)** (Stage C made that mandatory). Ring 2 is a
later ticket that should import Ring 1’s library, not a rewrite — it can
add mixes by family *inside* each \(d\).

---

## Function library (build in Ring 1, keep)

Put helpers where later bluff tickets can import them (new module e.g.
`src/fivecarddraw/validation/bluff_indifference.py`, used by a thin
`postdraw_bluff.py` CLI). Do **not** fork `play_deal`.

| Helper | Contract |
| --- | --- |
| Node sample | Raise-node deals (cap generator + **Stage C bet filter**; split by `deal.d`) |
| `strategy_ev(deals, bn_mix, caller_mix)` | Mean EV_bn, EV_caller via `play_raise_node` |
| `indifference_root(deals, value_buckets, bluff_buckets, catcher_bucket)` | β (or α) s.t. catcher \(EV_{\text{call}}-EV_{\text{fold}}=0\) |
| `best_response(deals, opponent_mix)` | Argmax action per own family bucket |
| Pot-odds pin | `pot_odds_to_call(26, 4) == 4/30` |

`best_response` can wait until the end of Ring 1 (useful as a check: at β*,
flush BR is mix/indifferent; straight BR is fold). Do not implement CFR in
Ring 1.

---

## What to reuse (do not redo)

| Artifact | Use |
| --- | --- |
| `play_raise_node` / `CapPolicy` / `StreetState` | Payoffs; max_raises=3 |
| `family_bucket`, `fine_bucket` | Same labels as cap |
| `on_raise_node` | **Stale** (assumes two pair bets). Filter: trips or boat+ ∩ caller straight+ |
| Locked range + 2:1 keep-4 | Same 18,396; `LOCKED_BN_DRAW` |
| Cap fixture numbers | Honest no-air baseline for the delta |
| `pot_odds_to_call` | Break-even equity |

Do **not** re-run the class × d grid, Stage C, pair concealment, M2 knobs,
or pre-draw trees.

---

## Hypotheses to confirm or refute (Ring 1)

1. On **\(d\in\{2,3\}\)** (trips air vs boat+ value) there exists β*(d) ∈ (0, 1)
   making **flush** call EV equal fold EV (tolerance ~0.05 chips).
2. At that β*, **straights still fold** (call EV < fold EV).
3. α*(d) is pot odds vs residual flush equity **on that \(d\)**. The old
   pooled ~9% (5% equity vs mixed flush+) does **not** apply on `d=2`/`d=3`
   (flush vs boats ≈ 0 → α nearer **13%**) or on `d=0` (flush vs mostly
   flushes → much more equity, and **no trips air**). **Compute per \(d\);
   do not pin 9%.**
4. Bluff delta vs honest no-air value 3-bet is **positive** for BN on the
   *trips-draw* lines (small), and vs call-it-down still positive. Do not
   average in `d=0`.
5. Boat+-only value 3-bets need **more** air to make flushes indifferent
   where the value range still includes flushes (`d=0`). On `d=2`/`d=3`
   value is already boat-heavy.
6. On **`d=0`**, caller flushes **prefer call** (or mix) vs a no-air flush+
   3-bet — the pooled “fold all flushes” BR does not survive the pat line.

---

## Deliverables

1. Indifference helpers + Ring 1 CLI (e.g. `analyze-postdraw-bluff`)
2. `outputs/validation/` tables + checked-in summary fixture
3. Pytest: pot odds 4/30; steal EV when caller folds; β* exists and flushes
   are indifferent; straights fold-or-not as the numbers say; cap path still
   `max_raises=1` by default for M2 / non-bluff
4. Short findings in this doc + [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md)
   (new §3.6, or a paragraph under §3.5 — do not rewrite §3.4 / §3.5 tables)
5. Do **not** claim the non-bluff class × d table or the cap value table
   already includes bluff 3-bets

---

## Out of scope (Ring 1)

- Ring 2 Nash / CFR (family mixes *inside* each already-split \(d\))
- Mixing BN straights (broadway A stays a cap-module footnote)
- Splitting aces-up vs small two pair (two pair is off the node)
- Putting two pair back into β (they check; they are not air on this line)
- Bluff 3-bets with missed draws / one pair (not on this node: BN did not bet)
- Caller mixing cap vs call with flushes (report EV_cap; do not solve it)
- Miss / face-pair stabs; re-running Stage C; pair concealment
- Multiway; UTG; sandbagging; pre-draw (Ch.2 §2.9); CO return-to-actor (Ch.5 §5.2)
- Replacing `HandValue` ordering

---

## Handoff checklist

1. Cap street is on the branch you start from (`play_raise_node`,
   `analyze-postdraw-cap`). `pip install -e ".[dev]" && pytest -q`
2. Implement **only Ring 1** + the library table above
3. Reuse the raise-node generator; do not re-grid class × d
4. Pin β*(d), α*(d), flush indifference on trips-draw lines, `d=0` flush
   call-or-fold, straight fold/call, bluff delta vs no-air value 3-bet
5. Update this doc + Ch.3; then stop. Ring 2 is a follow-up ticket.
