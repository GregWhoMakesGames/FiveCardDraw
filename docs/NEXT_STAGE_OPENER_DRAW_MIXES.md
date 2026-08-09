# Next stage: opener draw-count mixes + protected checking ranges

**Status:** Handoff for a fresh agent. Do **not** redo the showdown matrix or the
M2 `d=3` face-pair lead/stab/raise grid — those are done.

**Read first (in order):**

1. [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md) — what is already
   locked for opener-first post-draw betting when the opener **draws three**
2. [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md) — showdown equity
   vs the 2:1 drawing caller
3. This doc — extend **draw policy** beyond `d=3` and study **checking-range
   protection**

Parent ladder: [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md).

---

## Already solved (reuse; do not redo)

| Artifact | Takeaway |
| --- | --- |
| `showdown_matrix` | HU showdown vs 2:1 callers after pinned non-breaking draws |
| `postdraw_betting_m2` | With pairs always `d=3`, two pair stand, trips `d=2`, straight+ stand: **default check JJ–AA**; lead AA only as a thin reply to narrow drawer stabs; drawer face-pair stab/raise should stay **narrow** |

### Locked game facts that still apply

- Pre-draw: open + **call only**; pot into draw **$6**; post-draw big bet **$4**
- **Opener acts first** after the draw
- Drawer: 2:1 range, always keep-4 / draw 1
- No sandbagging of open-illegal hands; no UTG re-solve
- Public signal is **cards drawn** \(d \in \{0,1,2,3\}\), not which cards were kept

### Why `d=3` is special (product note)

Drawing three is the only line that puts the opener on a **small pre-draw class
set**: JJ / QQ / KK / AA (before improvement). After the draw that hand is still
usually one pair, else trips / two pair / boat / quads / five aces.

Rare bug+ace paths into straight/flush after drawing three to a pair exist but
are uncommon enough to **disregard in v1** of this stage (especially since many
2:1 callers already hold the bug). Document if you measure otherwise; do not
block the main grid on them.

**Pat straight+ must stand.** Those hands cannot be mixed into `d=3` to “balance”
pair draws. Protection of pair lines must come from **other** draw counts and/or
from **post-draw check mixes**, not from standing pat with a straight while
drawing three with JJ.

---

## Goal of this stage

Answer, with combo-weighted EV (and small grids / mixes), when the opener should:

| Starting class | Candidate draw actions |
| --- | --- |
| **Trips** | draw 2 (default keep trips), draw 1, stand pat |
| **Two pair** | draw 1 (keep both pairs, discard kicker), stand pat |
| **One pair JJ–AA** | draw 3 (default), draw 2, draw 1, stand pat |

Then, **conditional on public \(d\)**, choose post-draw bet vs check (opener
first), and the drawer’s stab/raise replies — especially whether the opener can
make “bet when checked to” with face pairs **unprofitable or indifferent** by
**checking a mix of strong and weak** hands.

### Product hypothesis to test

> Because pat straight+ cannot join the `d=3` bucket, the opener cannot protect
> pair draws by mixing monsters into draw-three. But by **checking** a mix of
> strong finals (e.g. some two pair / trips / boats after `d\in\{0,1,2\}`) with
> weak one-pair checks, the opener can protect the checking range, reduce the
> drawer’s stab EV, and raise overall opener EV vs the M2 “always bet two pair+”
> baseline.

Confirm or refute with numbers. If true, report the smallest mixes that work
(e.g. “check 30% of trips after `d=2`”, “check all two pair after stand”, …).

---

## Suggested computation shape

Keep the M2 deal generator / accounting (`postdraw_betting_m2.py`) as the base.
Extend; do not fork a second unrelated simulator.

```
for opener_hand in class:
  choose draw action a in legal set for class   # may be mixed
  drawer always draws 1
  deal from exact remaining deck
  observe public d
  opener first: bet or check (policy may depend on class, final hand, d)
  drawer responds (straight+ value; face-pair stab/raise knobs; misses fold/check)
  accumulate opener EV from post-draw node
```

### Legal keeps (v1 — pin explicitly)

| Class | Action | Keep rule |
| --- | --- | --- |
| Pair | `d=3` | Keep the pair |
| Pair | `d=2` | Keep pair + best kicker (define “best”: highest rank; pin in code) |
| Pair | `d=1` | Keep pair + two kickers (pin which two) |
| Pair | `d=0` | Stand with full five |
| Two pair | `d=1` | Keep both pairs; discard kicker |
| Two pair | `d=0` | Stand |
| Trips | `d=2` | Keep trips; discard two kickers |
| Trips | `d=1` | Keep trips + one kicker (pin which) |
| Trips | `d=0` | Stand |
| Straight+ | `d=0` only | Always stand |

Breaking the made hand (e.g. discarding one pair of two pair) is **out of
scope** unless M1-style improvement tables show a clear exception — default to
non-breaking.

### Public buckets to report separately

Always stratify results by public \(d\):

- `d=3` — nearly pure “was one pair” (M2 already covers betting here)
- `d=2` — trips-looking (but pairs drawing two can pollute)
- `d=1` — two-pair-looking / pair-drawing-one / trips-drawing-one
- `d=0` — pat: straight+ plus any standing two pair / trips / pairs

The point of pair `d\in\{0,1,2\}` and trips/two-pair deviations is partly to
**pollute** these signals and to feed strong hands into check ranges after those
\(d\) values.

---

## Investigation ladder (do in order)

### A — Draw mechanical tables (no betting change)

For each starting class × draw action, vs 2:1 callers with card removal:

- \(P(\text{final category})\) — still one pair / two pair / trips / boat+ / (ignore rare straight+ from pair+bug unless mass is surprising)
- Showdown \(P(\text{win/tie/lose})\) vs drawer
- Especially: \(P(\text{boat+})\) for two pair `d=1` and trips `d=2` vs stand

Deliverable: fixture or `outputs/validation/` table + short markdown. This is
the improvement half of the tradeoff (same spirit as showdown matrix case 3/4).

### B — Baseline post-draw with new draw defaults

Pick a single draw policy vector (e.g. trips always `d=2`, two pair always
`d=1` or always stand, pairs always `d=3`) and reuse M2 betting
(always bet two pair+; one-pair lead/check grid). Compare opener EV to the
checked-in M2 summary. This isolates **draw choice** before mixing checks.

### C — Checking-range protection grid (main goal)

Fix drawer to the interesting narrow band from M2 (straight+ always; face-pair
stab `AA` or `AA+KK`; raise similarly narrow). Then search opener mixes:

1. **Draw mixes** by class (frequencies on the rows in the goal table).
2. **Check mixes** after each \(d\): fraction of two pair / trips / boat+ that
   **check** instead of auto-betting (paired with still checking many one-pair
   hands).

Report for each candidate:

- Opener EV (all deals; and conditional on starting class)
- Drawer stab frequency and stab EV when opener checks
- Whether face-pair stab is ≤ 0 EV for the drawer (unprofitable) or near 0
  (indifferent) under the protected check range
- How much EV is lost on strong hands by checking them vs the gain from fewer /
  worse stabs

### D — Response lines (only as needed)

Reuse M2 call-down ideas when the drawer bets/raises. Re-tune only if check
mixes change the bet-into range enough that matched thresholds break.

---

## Deliverables

1. Code under `src/fivecarddraw/validation/` (e.g. extend `postdraw_betting_m2.py`
   or add `postdraw_draw_mixes.py`) + CLI
2. Fixture summary JSON under `tests/fixtures/validation/` for key EV cells
3. `pytest` pins (tolerance OK for MC)
4. Short markdown in `outputs/validation/` (gitignored) + update this doc’s
   **Status** when done
5. Clear recommendation table:

   | Class | Draw action | Post-draw bet/check | Notes |

---

## Explicitly out of scope

- Full multiway; cascade FFS13 unless product asks
- Pre-draw raises / sandbagging
- Mixing pat straight+ into `d>0` (illegal for these hands under “don’t break /
  don’t discard winners”)
- Full CFR equilibrium on the whole tree (optional later if grids stall)
- UTG open re-solve

---

## Handoff checklist

1. Merge or rebase onto `main` including showdown matrix + M2 docs/fixtures
2. `pip install -e ".[dev]" && pytest -q`
3. Read M2 findings before inventing new betting defaults
4. Implement A → B → C; stop at a recommendation table
5. Do **not** expand into full UTG strategy work
