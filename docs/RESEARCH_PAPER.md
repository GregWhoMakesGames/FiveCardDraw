# Approximate GTO Analysis of Fixed-Limit Five-Card Draw

**Working paper — draft outline with findings to date**

| Field | Value |
| --- | --- |
| Game | Fixed-limit five-card draw, **bug**, **jacks-or-better** to open, **eight ante-only** players |
| Stakes (v1) | $0.25 ante ($2 pot), $2 / $4 limit |
| Codebase | [`fivecarddraw`](../README.md) — Python toolkit + pinned validation fixtures |
| Audience | Researchers and poker-curious readers; assumes only basic poker (antes, betting rounds, drawing cards) |
| Status | Living document. §§1–2 are filled; §§3–5 are stubs pending further write-up |

**Companion technical notes** (agent handoffs; denser than this paper):

- [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md)
- [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md)
- [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md)
- [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md)
- [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md)

---

## Executive summary

This project builds a **reproducible, bottom-up** analysis of fixed-limit five-card draw with the bug under jacks-or-better opening rules. The long-term goal is an approximate game-theoretic (GTO) understanding of opening, calling, drawing, and post-draw betting — not a single black-box Nash solver for the full eight-player tree.

**Why the problem is hard.** Eight players, a 53-card deck (52 + bug), pre-draw and post-draw streets, and a public “cards drawn” signal create a decision space far larger than heads-up hold’em. Early-position opens face seven players behind; late-position “steals” look easy until drawing callers with huge outs enter the pot. A full multiway equilibrium is out of reach for v1, so we **slice** the game into validation ladders with exact or Monte Carlo ground truth, then expand seat by seat.

**What we have done so far.**

1. **Base engine** — hand evaluation with the bug, jacks-or-better legality, a coarse pre-draw abstraction (~384 buckets), and a position-by-position pre-draw solver that writes Super System–style charts. Those charts are a **pipeline**, not trusted strategy (early seats are known too loose).
2. **Drawing-call inventory** — exact enumeration of non-opening hands with enough one-card outs to call an open on pot odds (primarily **≥16 outs / 48** → 2:1). Result: **18,396** five-card combos (bug draws + four-flush-straight), plus cascade rates for a second drawing caller.
3. **Dealer / opener validation ladder** — showdown equity of fine-grained opener classes vs those 2:1 drawers; then a small post-draw betting grid (opener acts first); then a full grid of opener **draw-count** policies. Locked so far for the studied matchup: pairs draw three, two pair draw one, quads draw one; trips remain a fork (draw two vs draw one). Checking-range protection (Stage C) is the next code milestone.
4. **Belief tables** for how public draw counts reveal hand families — foundation for later “concealment” mixes.

**What this draft is for.** Give the author a single place to review the research arc; give outsiders a readable map of the game, the plan, and the findings — without requiring them to crawl five handoff docs.

**Central product claim (working).** Late position is the right place to start. Folding the first six seats into “cannot open” leaves a tractable opener-vs-drawing-caller problem on the button and cutoff. Solving those seats well — including post-draw play and, later, sandbagging — covers a clean laboratory of deals before we climb into early-position multiway chaos. Roughly **22%** of deals fold to the last two seats; the complementary **~78%** still involve an early open opportunity and remain future work.

---

## Table of contents

1. [Research roadmap: order of operations](#1-research-roadmap-order-of-operations)
2. [Drawing callers that cannot open](#2-drawing-callers-that-cannot-open)
3. [Dealer opening and post-draw equity *(stub / findings sketch)*](#3-dealer-opening-and-post-draw-equity)
4. [Opener draw mixes and range protection *(stub / findings sketch)*](#4-opener-draw-mixes-and-range-protection)
5. [Toward cutoff, player 5, and sandbagging *(planned)*](#5-toward-cutoff-player-5-and-sandbagging)
6. [Appendix A — Game rules at a glance](#appendix-a--game-rules-at-a-glance)
7. [Appendix B — Code map and CLIs](#appendix-b--code-map-and-clis)
8. [Appendix C — Document crosswalk](#appendix-c--document-crosswalk)

---

## 1. Research roadmap: order of operations

This section is the intended **sequence of research**, not a claim that every step is finished. Completed work is marked; later steps stay high-level on purpose.

### 1.1 Build base functionality (done — maintain forever)

**Goal.** Deterministic testing of probabilities and simulations so every later claim can be pinned in CI.

| Capability | Role |
| --- | --- |
| Cards + bug evaluation | Correct category ranking (five aces, SF, quads, …) |
| Jacks-or-better open check | Legal openers vs drawing-only hands |
| Deal / combo enumeration | Exact frequencies over \(C(53,5) = 2{,}869{,}685\) hands |
| Outs / keep-4 machinery | One-card improvement with documented denominator (/48 vs exact remaining deck) |
| Monte Carlo deal generators | Opener × disjoint caller deals with fixed seeds |
| Pytest fixtures under `tests/fixtures/validation/` | Lock numbers within tolerance |

Without this layer, “GTO charts” cannot be audited. With it, disagreements become bugs or model choices, not folklore.

### 1.2 Solve the button without sandbagging, including post-draw play (in progress)

**Why button first.** When the first seven seats pass, the dealer faces a pure open-or-pass decision for open-legal hands (steal the $2 ante pot). The *interesting* EV is not that steal — it is **opening into callers**, especially **non-opening drawing hands** that correctly call (and sometimes raise) because they have enough outs.

Work already on this ladder:

| Stage | Status | One-line result |
| --- | --- | --- |
| Drawing-call odds | Done | 18,396 combos clear 2:1 on outs/48 ≥ 1/3 |
| Cascade odds | Done | Second drawing caller is rare (~0.031% of deals) |
| Showdown matrix | Done | Fine opener classes × 2:1 drawer after documented draws |
| Post-draw M2 betting | Done | Default: check JJ–AA; drawer face-pair stabs stay narrow |
| Draw-count grid (A/B) | Done | Lock two pair `d=1`, quads `d=1`, pairs `d=3`; trips fork |
| Check-mix protection (C) | **Next** | Re-run under post-B draws (old fixture used two pair stand) |
| Pair concealment | After C | Only if post-draw EV still prefers pair `d=3` |

**Explicit v1 omission:** sandbagging (checking open-legal monsters hoping to raise later). Button strategy without sandbagging is still the right first equilibrium approximation.

### 1.3 Solve the cutoff the same way (planned)

Same template as the button: open/pass for open-legal classes, response vs open, then post-draw vs drawing continues — still **without** sandbagging in the first pass. The cutoff has one seat behind (the button), so open frequencies tighten relative to the dealer steal, but the drawing-caller technology carries over.

### 1.4 How much of the problem space is that?

Label the eight seats in dealing order left of the dealer: players **0…5** act first (the “early six”), then **cutoff (6)** and **button (7)**.

A coarse independent-events estimate uses the unconditional open-legal frequency ≈ **22.4%** (exact over all \(C(53,5)\) hands):

\[
P(\text{first 6 unable to open}) \approx (1 - 0.224)^6 \approx 0.218
\]

\[
1 - P(\text{first 6 unable to open}) \approx 0.782
\]

| Quantity | ≈ Value | Interpretation |
| --- | ---: | --- |
| \(P(\text{first 6 unable to open})\) | **22%** | Deals that fold to the **last two** seats (cutoff / button) — the late-position laboratory |
| \(1 - P(\text{first 6 unable to open})\) | **78%** | Deals where **at least one** of the first six *can* open — early/multiway mass still ahead |
| \(P(\text{all 7 unable to open})\) | **17%** | Pure dealer steal (everyone else lacks openers) |

**How to read this for the project.** Button + cutoff work targets the cleanest **~22%** of deals (folded to the last two), while building response and post-draw machinery needed everywhere. The complementary formula \(1 - P(\text{first 6 unable to open}) \approx 78\%\) is the **remaining** problem mass once late seats are understood. Card removal and position-dependent open policies will refine these percentages; treat 22% / 78% as planning numbers, not final theorem.

### 1.5 Plan the last two hands’ opening (planned write-up)

After button and cutoff validation numbers exist, consolidate:

- Which classes **open** for value vs steal
- Which classes **pass** despite being open-legal (if any, before sandbagging)
- How often the button faces a cutoff open vs a free steal
- How drawing-call ranges attach to each line

This becomes the “late-position chapter” outsiders can read without code.

### 1.6 Player 5: opening range and first sandbagging questions (planned)

Player **5** (seat index 5 in 0…7 order — the last of the “early six”) is where multiway pressure and **sandbagging** start to matter in earnest:

- What does player 5 open?
- Should any open-legal hands **check** hoping to play a bigger pot later?
- How do button/cutoff continue ranges change once player 5’s opens are credible?

We deliberately **do not** expand that plan here. The rule for this draft: finish the late-position non-sandbagging story and Stage C check protection before designing player-5 sandbag mixes.

### 1.7 Later (not scheduled in this draft)

- Full UTG / early-seat re-solve with combo-weighted raise pressure
- Multiway post-draw pots
- Ante:bet ratio sweeps
- Heavier equilibrium methods (e.g. CFR) on abstracted trees if grids stall

---

## 2. Drawing callers that cannot open

### 2.1 Why this section exists

In jacks-or-better, many strong **drawing** hands are **illegal opens**: they are not a pair of jacks or better (and not a made straight or better). Examples an outsider would recognize:

- **Bug combo draws** — the bug plus three cards toward a straight or straight-flush (often 16–22 outs to straight+)
- **OESFD / four-flush-straight** — four cards that are both a flush draw and an open-ender (16 outs without the bug)

Those hands **cannot open**, but after someone else opens they often have the correct pot odds to **call**, and in some trees to **raise**. If a solver only models “made” continues, it will overvalue thin opens — especially from early seats.

### 2.2 Pot-odds rules of thumb (this stake)

Antes put **$2** in the middle. An open is a **$2** bet.

| Situation | Pot facing | To call | Pot odds | Equity needed | One-card outs rule (approx.) |
| --- | ---: | ---: | --- | ---: | --- |
| First drawing call vs open | $4 | $2 | 2:1 | ≥ 1/3 | **outs / 48 ≥ 1/3 → ≥ 16 outs** |
| Second call after one drawing call | $6 | $2 | 3:1 | ≥ 1/4 | **outs / 48 ≥ 1/4 → ≥ 12 outs** |

**Denominator 48, not 43.** Each player knows only their own five cards, so 48 cards are unknown. Using 43 would pretend other players’ hole cards are known missing from the draw deck. Card removal still matters for **whether two drawing hands can be dealt together** (especially: only one bug).

**What counts as an “out.”** Keep four cards, discard one, draw one; the completed five-card hand is category **straight or better**. (Side path: many of these keeps also have disjoint outs to exact face pairs JJ–AA — tracked separately for showdown, not for the 2:1 call threshold.)

### 2.3 Inventory findings (pinned)

From fixture `tests/fixtures/validation/draw_call_odds.json` (exact enumeration):

| Set | Combos | Breakdown |
| --- | ---: | --- |
| **2:1 callers** (outs ≥ 16) | **18,396** | Bug straight draw 11,772; bug SF draw 5,508; four-flush-straight (no bug) 1,116 |
| Outs histogram (2:1) | — | 16 outs: 15,552; 19: 2,088; 22: 756 |
| **3:1 candidates** (outs ≥ 12) | 54,792 | Includes FFS13 (4,224) and the 2:1 subset |

**Cascade (two drawing callers among seven seats behind an open):** adjusted rate ≈ **0.0308%** (`cascade_to_2` in `cascade_odds.json`). Combined “lone 16+ improves or cascade improves” beating AA+/two pair/trips (approx.) ≈ **1.54%**. Cascade is ~1% of that mass — optional in the first showdown matrix.

### 2.4 Procedure A — Regenerate the full calling inventory

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

### 2.5 Procedure B — Ask whether one concrete hand is a 2:1 drawing call

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

### 2.6 Procedure C — Load the pinned 2:1 set for downstream EV

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

### 2.7 Procedure D — Face-pair side outs (optional, for showdown nuance)

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

### 2.8 Raises, not only calls

**Calls** are pinned by pot odds + outs as above. **Raises** with drawing hands are a separate EV question (semi-bluff / deny equity / build pot). Current validation focuses on **open + call only** into a $6 pot for post-draw grids. Raising draws remains on the roadmap once opener post-draw policies stabilize; do not treat the 18,396 set as an automatic raise range.

---

## 3. Dealer opening and post-draw equity

*Stub — expand in a later revision. Headline findings only.*

### 3.1 Folded-to-dealer sanity

Open-legal made hands: EV(open) ≈ +$2 ante pot; pass = 0. Non-open-legal hands cannot open.

### 3.2 Showdown vs 2:1 drawers

Fine opener rows (JJ / QQ / KK / AA / two pair / trips / straight / flush / …) vs the 18,396 callers after documented discard policies. Exact remaining deck once both hands known. CLI: `analyze-showdown-matrix`. Detail: [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md).

### 3.3 Post-draw betting (M2)

With pairs drawing three and opener acting first: **checking JJ–AA** beats leading for value against this drawer; face-pair stabs by the drawer should stay **narrow** (AA, maybe KK). CLI: `analyze-postdraw-m2`. Detail: [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md).

---

## 4. Opener draw mixes and range protection

*Stub — expand after Stage C re-run.*

### 4.1 Locked draw defaults (post Stage B)

| Class | Draw | Note |
| --- | --- | --- |
| Pair JJ–AA | **d=3** | Best improvement among pair options studied |
| Two pair | **d=1** | Dominant +EV lever in the 12-cell grid |
| Quads | **d=1** | EV-neutral vs stand; pollutes public d=1 |
| Other straight+ | Stand | Cannot join d=3 to “protect” pairs |
| Trips | **d=2** (primary) or **d=1** (unified) | Live fork for Stage C |

### 4.2 Stage C (next implementation)

Protect checking ranges by mixing strong finals into checks (not by standing with boats on d=3). Re-run under trips `d=2` (`tp1_tr2_q1`) and trips `d=1` (`tp1_tr1_q1`). Old C numbers used two pair **stand** — do not trust magnitudes. Detail: [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md).

### 4.3 After C — pair concealment

Only if post-draw EV still ranks pair `d=3` above `d=2`. Detail: [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md).

---

## 5. Toward cutoff, player 5, and sandbagging

*Planned — not started.*

1. Port button validation → **cutoff** (one seat behind).
2. Write the consolidated **last-two-seats opening** plan (§1.5).
3. Open **player 5**; introduce sandbagging hypotheses carefully.
4. Climb earlier seats only with raise-pressure and post-draw numbers in hand.

---

## Appendix A — Game rules at a glance

| Parameter | v1 default |
| --- | --- |
| Players | 8 |
| Ante | $0.25 each → $2 pot |
| Limit | $2 small bet / $4 big bet |
| Opening requirement | Pair of jacks or better (made) |
| Bug | Acts as ace, or completes straight / flush / straight-flush |
| Blinds | None |
| First to act pre-draw | Left of dealer (UTG) |
| Draw | In turn; number of cards discarded is **public** |
| Raise cap (solver) | Bet + 3 raises (optional bet+1 mode) |

**Sandbagging** means declining to open (or to bet) with a strong legal hand to disguise strength. It is **out of scope** for the current button ladder and for Stage C.

---

## Appendix B — Code map and CLIs

| CLI | Module | Purpose |
| --- | --- | --- |
| `solve-predraw` | `predraw/solve.py` | Coarse position-by-position pre-draw charts |
| `audit-abstraction` | `abstraction.py` | Bucket sanity |
| `analyze-draw-call-odds` | `validation/draw_call_odds.py` | 2:1 / 3:1 drawing-call inventory |
| `analyze-cascade-odds` | `validation/cascade_odds.py` | Second-caller cascade rates |
| `analyze-face-pair-outs` | `validation/face_pair_outs.py` | JJ–AA side outs among drawers |
| `analyze-showdown-matrix` | `validation/showdown_matrix.py` | Opener × drawer showdown |
| `analyze-postdraw-m2` | `validation/postdraw_betting_m2.py` | Face-pair bet/check/stab grid |
| `analyze-postdraw-draw-mixes` | `validation/postdraw_draw_mixes.py` | Draw-count A/B/C ladder |
| `analyze-opener-draw-beliefs` | `validation/opener_draw_beliefs.py` | Public-d belief tables |

Fixtures live under `tests/fixtures/validation/`. Generated markdown/JSON under `outputs/` is gitignored.

---

## Appendix C — Document crosswalk

| This paper | Detail doc |
| --- | --- |
| §1 Roadmap | `AGENTS.md` next-stage blurb; [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md) |
| §2 Drawing callers | Dealer equity doc; `draw_call_odds` / `cascade_odds` / `face_pair_outs` fixtures |
| §3 Showdown / M2 | [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md), [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md) |
| §4 Draw mixes / C | [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md), [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md) |
| §5 Later seats | *(not yet written)* |

---

## Revision notes

| Date | Change |
| --- | --- |
| 2026-09-01 | Initial draft: executive summary, TOC, full §§1–2, stubs §§3–5 |
