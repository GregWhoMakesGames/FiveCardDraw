# Chapter 2 — Drawing callers that cannot open

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> This chapter owns the **inventory and procedures** for non-opening hands that still call (or later raise) an open.

**Ledger role.** Enables the “BN (or other opener) faces a good calling hand” slices. Absolute steal-into-drawer deal share is small; without this inventory, thin opens look better than they are.

---

## 2.1 Why this section exists

In jacks-or-better, many strong **drawing** hands are **illegal opens**: they are not a pair of jacks or better (and not a made straight or better). Examples an outsider would recognize:

- **Bug combo draws** — the bug plus three cards toward a straight or straight-flush (often 16–22 outs to straight+)
- **OESFD / four-flush-straight** — four cards that are both a flush draw and an open-ender (16 outs without the bug)

Those hands **cannot open**, but after someone else opens (often **BN**, seat 8, in our first laboratory) they often have the correct pot odds to **call**, and in some trees to **raise**. If a solver only models “made” continues, it will overvalue thin opens — especially from early seats (UTG…HJ).

---

## 2.2 Pot-odds rules of thumb (this stake)

Antes put **$2** in the middle. An open is a **$2** bet.

| Situation | Pot facing | To call | Pot odds | Equity needed | One-card outs rule (approx.) |
| --- | ---: | ---: | --- | ---: | --- |
| First drawing call vs open | $4 | $2 | 2:1 | ≥ 1/3 | **outs / 48 ≥ 1/3 → ≥ 16 outs** |
| Second call after one drawing call | $6 | $2 | 3:1 | ≥ 1/4 | **outs / 48 ≥ 1/4 → ≥ 12 outs** |

**Denominator 48, not 43.** Each player knows only their own five cards, so 48 cards are unknown. Using 43 would pretend other players’ hole cards are known missing from the draw deck. Card removal still matters for **whether two drawing hands can be dealt together** (especially: only one bug).

**What counts as an “out.”** Keep four cards, discard one, draw one; the completed five-card hand is category **straight or better**. (Side path: many of these keeps also have disjoint outs to exact face pairs JJ–AA — tracked separately for showdown, not for the 2:1 call threshold.)

---

## 2.3 Inventory findings (pinned)

From fixture `tests/fixtures/validation/draw_call_odds.json` (exact enumeration):

| Set | Combos | Breakdown |
| --- | ---: | --- |
| **2:1 callers** (outs ≥ 16) | **18,396** | Bug straight draw 11,772; bug SF draw 5,508; four-flush-straight (no bug) 1,116 |
| Outs histogram (2:1) | — | 16 outs: 15,552; 19: 2,088; 22: 756 |
| **3:1 candidates** (outs ≥ 12) | 54,792 | Includes FFS13 (4,224) and the 2:1 subset |

**Cascade (two drawing callers among seven seats behind an open):** adjusted rate ≈ **0.0308%** (`cascade_to_2` in `cascade_odds.json`). Combined “lone 16+ improves or cascade improves” beating AA+/two pair/trips (approx.) ≈ **1.54%**. Cascade is ~1% of that mass — optional in the first showdown matrix.

Unconditional \(P(\ge 1\) of 7 seats holds a 2:1 combo\() \approx 4.4\%\). See the [ledger](INDEX.md#solve-progress-ledger) for how that sits inside the BN-steal band.

---

## 2.4 Procedure A — Regenerate the full calling inventory

Use this when you need a human-readable report or to refresh outputs (fixtures are already checked in).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

analyze-draw-call-odds -o outputs/validation
analyze-cascade-odds --also-outputs
analyze-face-pair-outs --also-outputs

pytest -q tests/test_draw_call_odds.py tests/test_draw_call_odds_fixture.py \
         tests/test_cascade_odds.py tests/test_face_pair_outs.py
```

**What the analysis does internally** (`fivecarddraw.validation.draw_call_odds`):

1. `build_keep4_outs_table(list(range(53)), min_outs=12)` — enumerate structurally strong 4-card keeps; retain those with enough straight+ outs.
2. `expand_keeps_to_hands(...)` — attach a discard; **drop any hand that can open** jacks-or-better; require `outs/48` ≥ threshold.
3. Split **≥16 outs** (Stage A / 2:1) vs **≥12 outs** (Stage B / 3:1 candidates).
4. Coexistence / cascade helpers — can a second drawer be dealt beside a first (especially with only one bug)?

---

## 2.5 Procedure B — Ask whether one concrete hand is a 2:1 drawing call

Interactive pattern for debugging a specific five-card hand:

```python
from fivecarddraw.cards import card_from_id, hand_to_str, BUG_ID
from fivecarddraw.hand_rank import can_open_jacks_or_better
from fivecarddraw.validation.draw_call_odds import (
    outs_set,
    classify_draw,
    FIRST_CALL_MIN_OUTS,
    UNKNOWN_AFTER_HERO,
)

# Example from the 2:1 inventory: 2c 2d 3c 4c Bu (bug = 52).
# Replace with any five card_ids under study.
hand_ids = (0, 1, 4, 8, BUG_ID)
cards = tuple(card_from_id(i) for i in sorted(hand_ids))
print("hand", hand_to_str(cards))
print("can open?", can_open_jacks_or_better(cards))  # False for this example

# Try each discard; pick the keep that maximizes straight+ outs
best = None
pool = set(range(53))
for disc in hand_ids:
    keep = tuple(sorted(i for i in hand_ids if i != disc))
    live = outs_set(keep, pool) - {disc}
    n = len(live)
    if best is None or n > best[0]:
        best = (n, disc, keep, live)

n, disc, keep, outs = best
print("best discard", card_from_id(disc))
print("keep", hand_to_str(tuple(card_from_id(i) for i in keep)))
print("class", classify_draw(tuple(card_from_id(i) for i in keep)))
print("outs", n, "hit≈", round(n / UNKNOWN_AFTER_HERO, 4))
print("clears 2:1 call?", n >= FIRST_CALL_MIN_OUTS)
```

**Interpretation.** If the hand cannot open and `clears 2:1 call?` is true, this combo belongs in the primary calling column used by the showdown matrix and post-draw grids. If it only clears 12–15 outs, it is a **3:1 / cascade** candidate, not a default first caller.

---

## 2.6 Procedure C — Load the pinned 2:1 set for downstream EV

When building showdown or betting simulations, reuse the same inventory the fixtures lock:

```python
from fivecarddraw.validation.showdown_matrix import load_call_2to1_hands
from fivecarddraw.validation.cascade_odds import CALL_2TO1_COMBOS, load_cascade_odds

hands = load_call_2to1_hands(progress=False)
assert len(hands) == CALL_2TO1_COMBOS == 18_396

by_class: dict[str, int] = {}
for h in hands:
    by_class[h.draw_class] = by_class.get(h.draw_class, 0) + 1
print(by_class)

casc = load_cascade_odds()
print("cascade_to_2", casc["cascade_rates"]["cascade_to_2"])
print(
    "combined vs AA+ approx",
    casc["combined_vs_aa_plus"]["p_combined_beats_aa_plus_approx"],
)
```

`load_call_2to1_hands` rebuilds via `build_keep4_outs_table` + filter (`outs ≥ 16`); CI pins the counts so a logic regression fails pytest.

---

## 2.7 Procedure D — Face-pair side outs (optional, for showdown nuance)

Many 2:1 keeps can also hit **exactly** JJ/QQ/KK/AA with outs that **never overlap** their straight+ outs (fixture: 15,444 / 18,396 ≈ 84%).

```bash
analyze-face-pair-outs --also-outputs
pytest -q tests/test_face_pair_outs.py
```

```python
from fivecarddraw.validation.face_pair_outs import (
    load_face_pair_outs,
    face_pair_outs_for_hand,
)
from fivecarddraw.validation.showdown_matrix import load_call_2to1_hands
from fivecarddraw.cards import hand_to_str

data = load_face_pair_outs()
aa = data["sets"]["call_2to1"]["by_target"]["AA"]
print("AA outs_dist", aa["outs_dist"])  # e.g. {"3": 4680, "4": 8568}

# Find one drawer that also has face-pair outs
for hand in load_call_2to1_hands(progress=False):
    fp = face_pair_outs_for_hand(hand)
    if fp:
        print(hand_to_str(hand.cards), hand.draw_class, fp)
        break
```

Use this when asking whether a thin opener (JJ–KK) loses to a drawer who “only” makes a higher face pair — not when deciding the raw call threshold.

---

## 2.8 Raises, not only calls (status quo)

**Calls** are pinned by pot odds + outs as above. **Raises** with drawing hands are a separate EV question (semi-bluff / deny equity / build pot). Current validation focuses on **open + call only** into a $6 pot for post-draw grids. Do **not** treat the 18,396 set as an automatic raise range until §2.9 is done.

---

## 2.9 Next step — Call, raise, or mix with strong draws (planned)

**Priority:** do this **before** CO bluff-representation work in [Ch.5](ch05_later_seats.md). The value of *looking like* a strong draw depends on how often real strong draws **raise** vs **call**.

### Product question

Given a hand from the 2:1 inventory (bug SF / bug straight / four-flush-straight, outs ≥ 16), facing an open (BN laboratory first: seats 1–7 unable / BN open-legal), should that hand:

| Policy | Meaning |
| --- | --- |
| **Always call** | Pay $2 into $4; pot $6 into draw; no extra fold equity |
| **Always raise** | Build pot / deny BN’s price / sometimes fold out worse continues |
| **Mixed strategy** | Combo- or class-weighted mix of call and raise (and, rarely, fold if EV ≤ 0 after blockers) |

Answer with **combo-weighted EV** (and small grids), not intuition alone. Stratify at least by draw class and outs bucket (16 / 19 / 22).

### Why it matters for later chapters

1. **BN opener defense** (Ch.3–4) — raise frequency changes pot size, BN’s continue range, and post-draw stack-off shape.
2. **CO bluffs with weaker hands** (Ch.5) — after BN opens on the return-to-actor line, real draws call/raise; whether underpairs / high cards should ever do the same as a bluff depends on that value mix.

### Suggested investigation shape

1. Fix opener class grid (start: BN JJ–AA / two pair / trips / straight+; reuse showdown discard policies).
2. For each drawer combo (or stratified sample of the 18,396), compare EV(call) vs EV(raise) vs EV(fold) under pinned BN replies (fold / call / re-raise caps).
3. Report mixes by class × outs; pin whether any subclass is pure raise or pure call.
4. Refresh post-draw M2 / draw-mix assumptions if the pre-draw line is no longer “open + call only.”

### Out of scope for this step

- Multiway cascades (optional sensitivity only; ~0.03% deal rate)
- CO trash bluffs (Ch.5 — after this)
- Changing ante:bet

### Deliverables (when implemented)

- Code + CLI under `validation/` (e.g. draw raise/call grid)
- Fixture summary + pytest pins
- Update this section’s findings table and the [INDEX ledger](INDEX.md#solve-progress-ledger) status for the BN-vs-drawer slice

---

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/draw_call_odds.py` | Primary |
| `src/fivecarddraw/validation/cascade_odds.py` | Cascade rates |
| `src/fivecarddraw/validation/face_pair_outs.py` | Face-pair side outs |
| `tests/fixtures/validation/draw_call_odds.json` (and cascade / face-pair) | Pins |
| `tests/test_draw_call_odds*.py`, `test_cascade_odds.py`, `test_face_pair_outs.py` | CI |
