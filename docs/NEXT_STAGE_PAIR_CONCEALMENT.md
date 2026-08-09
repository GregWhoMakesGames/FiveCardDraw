# Next stage: pair concealment vs Exploit-d3 (after Step 0 beliefs)

**Status:** Step 0 **done** (belief tables checked in). Steps 1–4 not started.

**Read first:**

1. This doc (plan + Step 0 results)
2. [NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md) — prior A→B→C
   (note: Stage C “check two pair” conflated pat d=0 with d=3 improvements; do not
   repeat that mistake)
3. [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md)

Parent: [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md).

---

## Product question

When the opener holds **one pair**, is \(d\in\{1,2\}\) ever +EV vs \(d=3\) because
it conceals strength (drawer sees public \(d\)), even though improvement is worse?

Rank intuition to test: **JJ** benefits most from \(d=3\) improvement vs drawer
QQ/KK/AA; **AA** benefits less (already beats/ties face-pair stabs; loses to
straight+ anyway).

Same template later for trips / two pair / quads.

---

## Step 0 — DONE (stored)

**Code:** `src/fivecarddraw/validation/opener_draw_beliefs.py`  
**CLI:** `analyze-opener-draw-beliefs`  
**Fixture:** `tests/fixtures/validation/opener_draw_beliefs.json`  
**Tests:** `tests/test_opener_draw_beliefs.py`  
**Local writeup:** `outputs/validation/opener_draw_beliefs.md` (gitignored)

```bash
pip install -e ".[dev]"
analyze-opener-draw-beliefs --n-per-cell 4000 --write-fixture
pytest -q tests/test_opener_draw_beliefs.py
```

### What is stored

| Artifact | Meaning |
| --- | --- |
| `beliefs_by_policy` | Exact \(P(d)\), \(P(\text{family}\mid d)\), \(P(\text{class}\mid d=3)\) under pure draw policies |
| `finals_by_class_d` | MC \(P(\text{final category})\) for JJ/AA (all d), QQ/KK (d=3,2), two pair / trips / quads |
| `highlights` | d=3 “nakedness” under pairs→d3/d2/d1/stand |

### Headline from Step 0

- Opener inventory mass is ~**63% pairs**, 22% two pair, 10% trips, 5% other
  straight+, 0.13% quads.
- Under **pairs always d=3** (trips d=2, two pair stand, quads d=1):
  - \(P(d=3)\approx 0.633\) and **\(P(\text{pair family}\mid d=3)=1\)** — fully naked.
  - \(d=2\) is 100% trips; \(d=1\) is 100% quads (rare); \(d=0\) is ~81% two pair /
    ~19% other straight+.
- Diverting **all** pairs to d=2 / d=1 / stand sets \(P(d=3)=0\).
- After d=3, JJ stays one pair ~71%; AA ~67% (AA improves slightly more). Full
  finals tables are in the fixture for Step 1.

Do **not** re-enumerate inventories for Step 0; reuse the fixture.

---

## Remaining plan (for next agent)

**Prerequisite:** finish opener-draw-mixes **Step C** under `tp1_tr2_q1` and
`tp1_tr1_q1` first ([NEXT_STAGE_OPENER_DRAW_MIXES.md](NEXT_STAGE_OPENER_DRAW_MIXES.md)).

### Step 1 — Pair rank × draw: showdown-only

Per `pair_J`…`pair_A` × \(d\in\{0,1,2,3\}\): win/tie/lose vs drawer **final family**
(miss / face pair / straight+). Confirm JJ vs AA improvement asymmetry.
Also pin that aggregate / per-rank showdown still has **`d=3` ≥ `d=2`** (boat+ and
win) before claiming concealment must overcome a large improvement gap.

### Step 2 — Concealment EV (main)

First quantify **post-draw EV** of pure pair `d=3` vs `d=2` (and `d=1`) under the
chosen background draw + check policy from Step C — confirm the assumption that
`d=3` is higher EV than `d=2` for single pairs with betting, not only showdown.

Background forks (pairs still mostly `d=3`):

- trips `d=2`, two pair `d=1`, quads `d=1` — optional later pair mixes into `d=2`
- trips `d=1`, two pair `d=1`, quads `d=1` — two-pair concealment on `d=1` without
  moving pairs off `d=3`

Pair knobs: pure d; rank-split (JJ–QQ d=3, KK/AA mix off d=3).

Drawer: **Exploit-d3** = face-pair stab only when public d=3; passive on other d.
All opener check mixes **keyed by public d** (never average d=0 pat checks into
d=3 protection).

### Step 3 — Two pair / trips / quads same template

### Step 4 — Joint vector + per-d check mixes only on masses that appear on that d

### Out of scope

Full CFR; mixing straight+ into d>0; UTG re-solve; treating pat two-pair checks
as d=3 protection.

---

## Handoff checklist

1. Pull branch / main with belief fixture
2. `pip install -e ".[dev]" && pytest -q`
3. Read Step 0 fixture highlights; start at **Step 1**
4. Reuse `postdraw_draw_mixes` / `opener_draw_beliefs`; do not redo Step 0
