# Next stage: post-draw cap (bet + 3 raises) when both make straight+

**Status:** Not started. The non-bluff EV grid, M2, and draw-mixes streets are
**bet + one raise only.** They do **not** model BN 3-bet / caller cap.

**Product question:** After BN value-bets two pair+ and the 2:1 caller raises
with a made straight+, should BN **reraise (3-bet, then maybe call a cap)** or
**just call**? Fine-split by final category and, inside category, by rank
(7-high straight vs queen-high flush, etc.).

Parent: [NEXT_STAGE_NONBLUFF_EV.md](NEXT_STAGE_NONBLUFF_EV.md),
[POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md).
Game cap in `GameConfig.max_raises = 3` (pre-draw already uses this; post-draw
validation does not).

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
2. BN **flush** 3-bets for value vs caller straights; still loses to SF (case 2).
   Queen-high vs ace-high flush may change 3-bet vs call.
3. BN **boat+** always 3-bets; caller should not cap a non-SF into that.
4. Calling it down (today) **understates** BN EV for flush+ and **overstates**
   it for thin straights if they would 3-bet into flushes.

---

## Deliverables

1. Street helper with `max_raises=3` (default M2 path stays `1`)
2. CLI + `outputs/validation/` tables + checked-in summary fixture
3. Pytest: pot math at cap; 3-bet vs call Δ for a nut BN vs a straight caller;
   coarse pins that BN straights do not auto-3-bet if the numbers say so
4. Short findings in this doc + [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md) §3.5
5. Do **not** claim the non-bluff class × *d* table already includes cap EV

---

## Out of scope

- Bluff 3-bets with two pair / trips / missed draws
- Changing M2 face-pair knobs or pair draw counts
- Pre-draw raising draws (Ch.2 §2.9)
- Multiway; UTG; sandbagging
- Replacing `HandValue` ordering (already correct)

---

## Handoff checklist

1. On `main` (or rebase this ticket): `pip install -e ".[dev]" && pytest -q`
2. Read `play_deal` in `postdraw_betting_m2.py` (the raise branch) and
   `GameConfig.max_raises`
3. Implement cap street + fine buckets; keep `max_raises=1` as the default for
   existing CLIs
4. Condition on BN-bet ∩ caller-straight+; do not re-grid all class × *d*
5. Update Ch.3 §3.5 with 3-bet vs call recommendations by fine hand
