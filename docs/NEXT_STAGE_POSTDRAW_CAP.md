# Next stage: post-draw cap (bet + 3 raises) when both make straight+

**Status:** Raise node re-filtered under **Stage C** (BN checks two pair;
bets trips+). Two 3-bet lines are first-class (`d=2∪d=3` vs `d=0`).
Code `src/fivecarddraw/validation/postdraw_cap.py`, CLI `analyze-postdraw-cap`.
M2 / non-bluff class × d tables stay the honest always-bet-two-pair
**bet+1** cells — they are not rewritten.
Strategy tree: [POSTDRAW_STRATEGY_TREE.md](POSTDRAW_STRATEGY_TREE.md).
Findings in this doc and [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md) §3.5.

**Product question:** After BN value-bets **trips+** (Stage C: two pair
checks) and the 2:1 caller raises with a made straight+, should BN
**reraise (3-bet, then maybe call a cap)** or **just call**? Fine-split by
final category, public \(d\) (Line 1 vs Line 2), and rank.

Parent: [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md)
(`play_deal` is already on `main`). Honest class × d EV baseline:
[NEXT_STAGE_NONBLUFF_EV.md](NEXT_STAGE_NONBLUFF_EV.md) (open PR if not yet on
`main`). Game cap in `GameConfig.max_raises = 3` (pre-draw already uses this;
post-draw validation does not).

---

## Denied: current post-draw tree is bet + 1 raise

Pinned in `postdraw_betting_m2.play_deal` (reused by non-bluff EV):

1. BN bets $4 (two pair+), or checks one pair.
2. Caller **raises** straight+ (puts in $8); else calls a face pair or folds a miss.
3. BN **calls or folds**. There is **no 3-bet**, no 4-bet, no cap.

Max pot on that line: $6 + $4 + $8 + $4 = **$22** (each side $8 post-draw).
Full cap (bet + 3 raises = four $4 increments each): $6 + $32 = **$38**
(each side $16 post-draw). Winner Δ vs today’s call-it-down: **+$8**.

`DEFAULT_CONFIG.max_raises = 3` is the **pre-draw** cap. Post-draw validation
never reads it.

---

## Why the deep tree is small but expensive

Honest policies already in the grid:

| Side | Bets | Raises a bet |
| --- | --- | --- |
| BN | two pair+ (including all straight+) | **never** (no 3-bet implemented) |
| Caller | straight+ when checked; AA face-stab | **straight+ only** (no face-pair raise) |

A raise war therefore requires:

- BN **bets** → final is two pair or better, **and**
- Caller **raises** → final is **straight+**.

Two pair / trips facing that raise are **behind** a raising straight+ range.
Honest play there is **call or fold**, not 3-bet. The 3-bet/cap question is
almost entirely:

**Both players have at least a straight** (showdown cases 1, 2, 3, 3b),
or BN has a boat+ vs caller’s straight+ (still case 1 / 4b-style).

Caller 2:1 keeps (bug SF / bug straight / FFS16) almost never make boats or
quads. Expected **caller** value hands on this line:

- straight
- flush
- straight flush

Expected **BN** value hands that might 3-bet:

- straight, flush, full house, quads, straight flush, five aces

Mass is modest (caller completes ~34%; BN also needs two pair+ and then a
straight+ overlap). Pots are the biggest on the street. Do **not** skip this
because the cell is rare.

---

## What to reuse (do not redo)

| Artifact | Use |
| --- | --- |
| `play_deal` / MixDeal generator | Deal through the draw; **extend** the street, do not fork a third simulator |
| Showdown cases 1, 2, 3, 3b | Both-straight+ buckets |
| `HandValue` | Already ordered: five aces > SF > quads > boat > flush > straight; tiebreaks are high card / flush ranks / boat ranks |
| Non-bluff EV grid | Baseline EV when BN **calls** the raise (today’s policy) |
| 2:1 caller inventory | Same 18,396; keep-4 d=1 |

Do **not** re-run the full class × *d* grid, Stage C, pair concealment, or
pre-draw raise trees.

---

## Suggested computation

Restrict to deals where the current street would already raise:

```
BN bets (two pair+) AND caller final is straight+
  → node: BN faces a raise, $4 to call, pot $18
```

At that node, under **honest** (no bluff 3-bets with two pair/trips):

| BN final | Candidate actions vs raise |
| --- | --- |
| two pair / trips | **Call only** (behind; 3-bet is a bluff — out of scope unless cheap) |
| straight | Call vs 3-bet, maybe cap-call; split by **straight high** (wheel … broadway) |
| flush | Call vs 3-bet; split by **flush high** (and second card if mass allows) |
| boat / quads / SF / five aces | 3-bet for value (almost always ahead of caller’s straight/flush) |

Caller vs a 3-bet (honest):

| Caller final | Candidate |
| --- | --- |
| straight | Call vs cap; often **behind** a BN 3-bet (BN’s 3-bet range is flush+) |
| flush | Call vs cap; ahead of BN straights, behind boats/SF |
| SF | Cap for value |

Report **labeled** EV_bn and EV_caller, same post-draw incremental chips
(`sum = $6` still holds if both can invest more). Also report:

- Node mass P(BN bets ∩ caller straight+) by BN starting class
- P(BN wins | that node) by fine bucket (this is cases 1 vs 2 vs 3)
- ΔEV of 3-bet vs call for each BN bucket
- ΔEV of caller cap vs call vs BN’s 3-bet

### Fine buckets (minimum)

Use `HandValue.category` + `tiebreak`, not the coarse showdown-matrix row names.

BN:

- `straight_{high}` for high in {5 (wheel), 6, …, 14 (broadway)}
- `flush_{high}` for high in {J, Q, K, A} (merge low flushes if rare)
- `full_house`, `four_of_a_kind`, `straight_flush`, `five_aces`

Caller:

- `straight_{high}`, `flush_{high}`, `straight_flush`

If a cell is empty or n < ~50, merge adjacent highs rather than inventing
policy. Exact remaining-deck draws once both hole cards are known (same as
showdown matrix). MC with a high sample on this **conditional** node is OK.

### Street to implement (bet + 3)

After BN bet and caller raise (today’s `drawer_raise`):

1. BN: fold / call / **3-bet** ($4 more to make it 3 bets; actually +$8 to raise the raise — pin the chip math to `StreetState` / `max_raises=3`).
2. Caller vs 3-bet: fold / call / **cap** (4th increment).
3. BN vs cap: fold / call (no 5th bet).

Pin chip increments against a unit test: four $4 bets each → pot $38.

Prefer extending `play_deal` with an optional `max_raises=1` default so M2 /
non-bluff fixtures **do not move**. New CLI e.g. `analyze-postdraw-cap` with
its own fixture.

---

## Hypotheses to confirm or refute

1. BN **straight** should usually **call** a raise, not 3-bet: caller’s raise
   range is straight/flush/SF, and many 2:1 keeps are flush-heavy (FFS + bug SF).
   **Confirmed** at the family level (Δ = −1.81). Ace-high (broadway) is a thin
   exception (Δ = +0.35) vs a calling range; wheel–jack-high should not 3-bet.
2. BN **flush** 3-bets for value vs caller straights; still loses to SF (case 2).
   Queen-high vs ace-high flush may change 3-bet vs call.
   **Confirmed** 3-bet for all flush highs including `flush_low` / Q / K / A
   (Δ ≈ +1.7 to +2.6). Rank does **not** flip the decision vs a calling range.
3. BN **boat+** always 3-bets; caller should not cap a non-SF into that.
   **Confirmed** (boat+ Δ = +3.47). Caller straight/flush should **fold** (not
   cap) vs a boat+ 3-bet; SF caps.
4. Calling it down (today) **understates** BN EV for flush+ and **overstates**
   it for thin straights if they would 3-bet into flushes.
   **Confirmed** in direction: on the node, call-it-down EV_bn = −5.32;
   flush+ 3-bet / cap-SF = −5.00 (Δ = +0.33). Thin straights that 3-bet lose
   extra. This does **not** rewrite the class × d table.

**Equilibrium caveat.** Unilateral caller EV vs a BN **flush+** 3-bet says
straight *and* flush should **fold** (only SF continues). If the caller
actually folds that wide, BN’s flush 3-bet stops getting paid by worse and
joint node EV collapses to ≈ call-it-down (`flush+ / fold_straight_cap_sf`
Δ = +0.02). The recommended line below holds the handoff’s **calling**
responder (cap SF, call rest) for BN’s 3-bet/call choice, then reports the
caller’s best response separately.

---

## Deliverables

1. Street helper with `max_raises=3` (default M2 path stays `1`) — **done**
2. CLI `analyze-postdraw-cap` + `outputs/validation/` tables + fixture
   `tests/fixtures/validation/postdraw_cap_summary.json` — **done**
3. Pytest: pot math at cap; nut BN vs straight Δ; BN straights do not auto-3-bet
4. Findings in this section + [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md) §3.5
5. The non-bluff class × *d* table is still bet+1 (explicitly excluded)

---

## Findings (seed 20260902, Stage C street)

Combo-weighted locked BN draws (`tp1_tr2_q1`) vs all 2:1, caller keep-4 d=1:
**40,000** deals, **3,612** on the Stage C raise node (P = **0.0903**).
Pre-C (two pair always bets) was 7,559 / 0.189. Unimproved two pair on the
node: **0**. Extra per-class deals fill fine buckets. Unilateral BN Δ holds
caller at **cap SF / call rest**.

Full cap pot is **$38** (four $4 bets each + $6). Call-it-down on this node is
a **$22** showdown.

### Two 3-bet lines (public \(d\) is observed)

| Line | Public \(d\) | n | BN on node | 3-bet value | 3-bet air | Flush vs no-air flush+ |
| --- | --- | ---: | --- | --- | --- | --- |
| **1 — trips draw** | 2 ∪ 3 | 2,569 | trips 2,258 / boat+ 273 / rare S,F | Boat+ | Unimproved **trips** | **fold** |
| **2 — pat straight+** | 0 | 750 | S 470 / F 174 / boat+ 106 | Flush + rare starting boat+ | **None** | **call** (EV −7.45 vs fold −8.00, n=66) |
| *(not a bluff line)* | 1 | 293 | boat+ 293 | Nuts (boats/quads) | None | **fold** |

Line 1 is 71% of the post-C node; line 2 is 21%; `d=1` is 8%. Two pair that
*boated* still appear in class mass (`p_bn_bets` ≈ 0.08–0.10) but as
`boat_plus`, not as two-pair air.

### BN vs the raise (extra-weighted; value line)

| BN final | n | P(win) | EV call | EV 3-bet | Δ | Action |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| trips | 5,852 | 0.00 | −8.00 | −12.27 | −4.27 | **call** (no bluff 3-bet) |
| two pair | 0 | — | — | — | — | **not on node** (Stage C check) |
| straight | 1,907 | 0.30 | −1.08 | −2.89 | −1.81 | **call** |
| flush | 1,567 | 0.82 | +10.08 | +12.25 | +2.17 | **3-bet** |
| boat+ | 6,545 | 0.94 | +12.71 | +16.18 | +3.47 | **3-bet** |

Fine split unchanged in direction: every flush high 3-bets. Straights:
wheel–J **call**; broadway A **thin 3-bet** (Δ = +0.35); Q-high ≈ 0.
Boats / quads / SF / five aces all 3-bet. These Δs are vs a *calling*
responder and do not rewrite the class × d table.

### Caller vs a 3-bet, by line

**Do not quote the pooled “fold all flushes vs flush+” row.** That table
still exists in the fixture (extra-weighted, mixes boats from draws into
pat flushes) and still says fold. The caller sees \(d\):

| Caller | Line 1 (`d=2,3`) vs flush+ | Line 2 (`d=0`) vs flush+ | Any line vs boat+ |
| --- | --- | --- | --- |
| straight | fold | fold | fold |
| flush | **fold** (drawing dead to boats) | **call** | fold |
| SF / boat+ | cap | cap | cap |

On `d=0`, ace-high flush vs a pat flush+ 3-bet also prefers call in the
fine table. Mixing cap vs call with flushes is still OPEN.

### Joint node EV (combo-weighted, Stage C node)

Call-it-down EV_bn = **−2.40** (was −5.32 when unimproved two pair sat on
the node and lost every time). Best measured joint vs a calling/capping
caller is **3-bet flush+** (EV_bn −1.52 to −1.71 depending on whether
flushes cap). 3-betting all straight+ is still worse than flush+ because
thin straights pay off flushes.

**Do not substitute these for the non-bluff class × d cells.** Cap EV is a
delta on this rare-but-expensive node only.

---

## Stage C re-filter (done)

The old fixture assumed BN **always bets two pair+** (`p_bn_bets = 1`;
P(node) = 0.189). That street is retired for cap/3-bet work. The checked-in
fixture is the Stage C filter:

- Node = BN trips+ (auto-bet) ∩ caller straight+.
- Unimproved two pair **check**; they never 3-bet.
- Reports split by public \(d\) and grouped as Line 1 / Line 2.
- `d0_flush_prefers_call_vs_flush_plus` is **true**.

M2 / non-bluff fixtures stay the honest always-bet-two-pair cells. Forward
street for cap and Ring 1 is Stage C. Bluff work:
[NEXT_STAGE_POSTDRAW_BLUFF.md](NEXT_STAGE_POSTDRAW_BLUFF.md).

---

## Next: bluff 3-bet (Ring 1)

Honest flush+ 3-bet vs a folding caller is **not** equilibrium on Line 1,
and Line 2 has **no trips air**. First bluff-library ticket: mix **trips**
as air on Line 1 until **flushes** are indifferent; on Line 2 report flush
call ≥ fold vs a no-air flush+ 3-bet (already measured) and do not invent
β. Do **not** start bucketed Nash until that fixture exists —
[NEXT_STAGE_POSTDRAW_BLUFF.md](NEXT_STAGE_POSTDRAW_BLUFF.md).

---

## Out of scope

- Bluff 3-bets with two pair / trips / missed draws
- Changing M2 face-pair knobs or pair draw counts
- Pre-draw raising draws (Ch.2 §2.9)
- Multiway; UTG; sandbagging
- Replacing `HandValue` ordering (already correct)

---

## Handoff checklist (this ticket — done)

1. `play_deal` default `max_raises=1`; cap path uses `StreetState` / `max_raises=3`
2. `analyze-postdraw-cap` conditions on Stage C BN-bet (trips+) ∩ caller-straight+
3. Fixture + Ch.3 §3.5 updated under Stage C; two lines modeled; class × d table not rewritten
4. Next **cap** ticket is Ring 1 ([NEXT_STAGE_POSTDRAW_BLUFF.md](NEXT_STAGE_POSTDRAW_BLUFF.md)). Pair concealment stays a separate Ch.4 ticket. Do not fold the cap street into the M2 Stage C grid.
