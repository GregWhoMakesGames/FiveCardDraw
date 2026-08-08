# Next stage: dealer vs drawing-caller showdown matrix

**Status:** Implemented — see `src/fivecarddraw/validation/showdown_matrix.py`,
`tests/fixtures/validation/showdown_matrix.json`, CLI `analyze-showdown-matrix`.
Calling-draw pot odds / cascade / face-pair outs are on `main` (merged PR #3).
Reuse `tests/fixtures/validation/`.

**Do not** re-solve full 8-seat opens. Stay on dealer-opener × drawing-caller **post-draw showdown** probabilities.

---

## Already solved (reuse; do not redo)

Checked in under `src/fivecarddraw/validation/` and `tests/fixtures/validation/`:

| Artifact | Contents |
| --- | --- |
| `draw_call_odds.py` + `draw_call_odds.json` | 2:1 callers (outs/48 ≥ 1/3 → ≥16 outs): **18,396** combos (bug 17,280 + FFS16 1,116). 3:1 candidates (≥12 outs): includes FFS13 **4,224**. |
| `cascade_odds.py` + `cascade_odds.json` | Cascade-to-2 among 7 seats ≈ **0.0308%** (A′+B′+C/2). Combined lone-16+ + cascade beat-AA+ approx ≈ **1.543%**. Cascade is ~1% of that mass — **optional** in the first showdown matrix. |
| `face_pair_outs.py` + `face_pair_outs.json` | Among 2:1 callers, **15,444 (84%)** can draw to exact one pair JJ/QQ/KK/AA; outs **never** overlap straight+ outs for these keeps. Fine buckets by draw class × target × out count. |

### Locked approximations

- **Outs denominator:** always **/48** (independent events). Not /43.
- **Card removal:** coexistence / blockers (esp. one bug), not shrinking the denominator.
- **Cascade suit haircuts:** 15% bug↔FFS, 12% FFS↔FFS.
- **Stakes:** `$0.25` ante × 8, `$2/$4`, jacks-or-better, bug = ace or complete straight/flush/SF.
- CLIs: `analyze-draw-call-odds`, `analyze-cascade-odds`, `analyze-face-pair-outs`.
- `pytest -q` pins the fixtures.

### Caller sets to use as columns

1. **2:1 primary:** bug SF/straight draws + FFS16 (the 18,396).
2. **Face-pair side path:** same hands’ JJ/QQ/KK/AA one-card outs (see fixture).
3. **Cascade FFS13:** defer unless product asks; deal rate is tiny.

---

## Goal of this stage

For **dealer opening classes** (fine split above one pair — see `docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md`), estimate **showdown outcomes vs one drawing caller** after both take their draw actions (documented discard policies).

Product-owner case list (expanded with confirmed adds):

### Pat / made straight+ dealer

| ID | Case | Notes |
| --- | --- | --- |
| **1** | Dealer starts **straight or better**, beats drawer who improves to **straight+** | e.g. higher straight, flush > straight, boat > flush, etc. |
| **2** | Dealer starts **straight or better**, **loses** to drawer who improves to **straight+** | e.g. flush over straight, SF over boat |
| **1b** | Dealer starts **straight or better**, beats drawer who improves only to a **face pair** (or otherwise not straight+) | Necessary complement: pair-only improve loses to all pat straight+ |
| *(discount)* | Exact chops on straight/flush/SF | Rare; omit or lump |

### Dealer improves from below straight

| ID | Case | Notes |
| --- | --- | --- |
| **3** | Dealer starts **&lt; straight**, improves to **straight+**, **beats or ties** drawer who also improves to **straight+** | Need discard policy for two pair / trips / one pair |
| **3b** *(helpful)* | Same setup but dealer **loses** to drawer’s better straight+ | Symmetric to 2 |

### Dealer two pair / trips (stronger than AA, weaker than straight)

| ID | Case | Notes |
| --- | --- | --- |
| **4** | Dealer **two pair / trips**, stands (no improve), **beats** drawer who improves only to a **pair** | |
| **4b** | Dealer **two pair / trips**, stands, **loses** to drawer who improves to **straight+** | **Required** (product: “A”) — main draw equity vs medium made hands |

### Dealer one pair JJ–AA vs drawer face-pair improves

| ID | Case | Notes |
| --- | --- | --- |
| **5** | Dealer **AA** beats or ties drawer → pair J+ | Include chops AA vs AA |
| **6** | Dealer **KK** beats or ties drawer → pair J+ | |
| **7** | Dealer **QQ** beats or ties drawer → pair J+ | |
| **8** | Dealer **JJ** **ties** drawer → JJ | JJ never *beats* a jacks-or-better pair |
| **5b–7b** *(helpful)* | Dealer KK/QQ/JJ **loses** to drawer’s **higher** face pair (esp. bug→AA over KK/QQ/JJ) | Extra calculated rows; use `face_pair_outs` |
| **5c–8c** | Dealer JJ–AA **loses** to drawer who hits **straight+** | **Required** (same “A” as 4b) |

### Explicitly out of scope for this matrix

- **Drawer completely misses** (no straight+, no relevant pair): they lose showdown; no separate bucket. Bluff value later.
- Full multiway / 3-caller cascades (optional later; ~0.03% deal rate).
- Sandbagging; UTG re-solve; changing ante:bet.

---

## Suggested computation shape

Heads-up: fix dealer class (combo-weighted), sample or enumerate disjoint caller from 2:1 set (and optionally weight by seat / call frequency later).

```
for dealer_hand in class:
  for caller_hand in disjoint_2to1_callers:
    apply discard policies
    enumerate or MC one-card draws (outs/48 mindset; exact: remaining deck after both hands = 43 cards — use exact removal for showdown once both holdings are known)
    classify final categories → accumulate win/tie/lose into cases 1–8 (+b rows)
```

**Important nuance:** Pot-odds calling used **/48** as an approximation. For **validation showdown** with both hands known, prefer **exact remaining-deck** draws (card removal of both hole cards). Document which you use.

### Discard policies (must document; wrong policy → false equity)

| Side | Class | Policy (v1 proposal — confirm if unsure) |
| --- | --- | --- |
| Caller | bug SF / flush / straight draws, FFS | Hold 4, draw **one** (already used in fixtures) |
| Dealer | straight+ | **Stand pat** |
| Dealer | two pair | Stand pat (or draw one — pick one and pin) |
| Dealer | trips | Draw two / stand — pick and pin |
| Dealer | one pair JJ–AA | Draw 1–3 kickers — pick a simple rule (e.g. draw 3 always) and pin |

No further betting in this fixture (showdown after draw only), matching the parent validation doc.

### Opener class rows (fine split)

At least: `pair_J`, `pair_Q`, `pair_K`, `pair_A`, `two_pair` (± aces-up), `trips` (± ace/king), `straight`, `flush`, `full_house`, `quads` / `straight_flush` / `five_aces`.

---

## Deliverables

1. Code under `src/fivecarddraw/validation/` (e.g. `showdown_matrix.py`) + CLI.
2. Fixture JSON under `tests/fixtures/validation/` with case probabilities (and combo weights).
3. `pytest` pins for the main cells (tolerance OK for MC).
4. Short markdown table in `outputs/validation/` (gitignored) for humans.
5. Update this doc’s status when done.

---

## Handoff checklist

1. Merge or rebase onto updated `main` (include PR #3 validation fixtures if not merged).
2. `pip install -e ".[dev]" && pytest -q`
3. Read `face_pair_outs` / `cascade_odds` / `draw_call_odds` fixtures before inventing new caller lists.
4. Implement showdown matrix cases **1, 1b, 2, 3, 4, 4b, 5–8, 5c–8c**; add **5b–7b** if cheap.
5. Do **not** expand into full UTG strategy re-solve.
