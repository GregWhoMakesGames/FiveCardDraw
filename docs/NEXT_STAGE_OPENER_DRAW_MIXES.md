# Next stage: opener draw-count mixes + protected checking ranges

**Status:** Stages **A** and **B** done (full 12-cell draw grid). Stage **C** must
be **re-run** under the post-B draw defaults below — the checked-in C fixture used
`two_pair_d=0` (stand) and is **not** the policy we carry forward.

Code `src/fivecarddraw/validation/postdraw_draw_mixes.py`, CLI
`analyze-postdraw-draw-mixes`, summary fixture
`tests/fixtures/validation/postdraw_draw_mixes_summary.json`, tests
`tests/test_postdraw_draw_mixes.py`. Regen A/B/C with
`analyze-postdraw-draw-mixes --n-deals 20000 --write-fixture` after C is updated.

**Read first (in order):**

1. [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md) — locked
   opener-first post-draw betting when the opener **draws three**
2. [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md) — showdown equity
   vs the 2:1 drawing caller
3. This doc — A/B findings, narrowed draw fork, then **Step C** (next work)

Parent ladder: [NEXT_STAGE_DEALER_OPENING_EQUITY.md](NEXT_STAGE_DEALER_OPENING_EQUITY.md).

Related (do not start until C is done under the new draws):
[NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md).

---

## Already solved (reuse; do not redo)

| Artifact | Takeaway |
| --- | --- |
| `showdown_matrix` | HU showdown vs 2:1 callers after pinned non-breaking draws |
| `postdraw_betting_m2` | With pairs always `d=3`, two pair stand, trips `d=2`, straight+ stand: **default check JJ–AA**; lead AA only as a thin reply to narrow drawer stabs; drawer face-pair stab/raise should stay **narrow** |
| `postdraw_draw_mixes` A+B | Mechanical tables + full 12-cell draw EV grid (this doc) |
| `postdraw_draw_mixes` C (old) | Check-mix numbers exist but used **two pair stand** — treat as qualitative only until re-run |

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

**Most pat straight+ must stand** (straight, flush, full house, straight flush,
five aces). Those hands cannot join `d=3` to balance pair draws.

**Exception — four of a kind may draw one:** discard the kicker, keep the quads.
That does not break the hand. Against this calling range the drawer cannot make
four of a kind, so there is no showdown downside to the redraw, and the public
`d=1` line picks up a nutted combo that helps protect openers who draw one with
two pair / trips / pairs. Prefer **always** `d=1` with quads (EV-neutral in B;
signal value only).

Protection of pair `d=3` lines must still come from **other** draw counts and/or
**post-draw check mixes**, not from standing with a straight while drawing three
with JJ.

---

## Findings (seed 20260809)

### A — Draw mechanical tables

| Class | Action | Result |
| --- | --- | --- |
| Pair AA | d=3 vs d∈{0,1,2} | **d=3 best** showdown win (~0.673) and boat+ (~0.018) |
| Two pair | d=1 vs stand | boat+ **0 → 0.086**; win **0.667 → 0.681** |
| Trips | d=2 vs stand | boat+ **0 → 0.101**; win **0.643 → 0.697** (d=1 boat+ 0.086) |
| Quads | d=1 vs stand | win **≈ equal** (0.976 vs 0.978); d=1 sometimes → five aces |

Pair draw-1 **cannot** make boat+ (keep pair + two kickers, one card in). Pair
draw-2 still makes boat+ (~0.012 for AA; ~0.010 aggregate JJ–AA).

### B — Draw defaults under M2 betting (check one pair; AA stab)

Full factorial grid with pairs fixed at `d=3`:

- quads \(d \in \{0,1\}\)
- trips \(d \in \{0,1,2\}\)
- two pair \(d \in \{0,1\}\)

→ **12 policies**.

| quads | trips | two pair | Δ EV vs M2 | d=1 rate | d=2 rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | −0.065 | 0 | 0 |
| 0 | 0 | 1 | +0.075 | 0.214 | 0 |
| 0 | 1 | 0 | −0.014 | 0.099 | 0 |
| 0 | 1 | 1 | +0.125 | 0.313 | 0 |
| 0 | 2 | 0 | **0** (M2) | 0 | 0.099 |
| 0 | 2 | 1 | **+0.140** | 0.214 | 0.099 |
| 1 | 0 | 0 | −0.065 | 0.001 | 0 |
| 1 | 0 | 1 | +0.075 | 0.215 | 0 |
| 1 | 1 | 0 | −0.014 | 0.100 | 0 |
| 1 | 1 | 1 | +0.125 | 0.314 | 0 |
| 1 | 2 | 0 | 0 | 0.001 | 0.099 |
| 1 | 2 | 1 | **+0.140** | 0.215 | 0.099 |

### B decision (locked for C)

1. **Quads `d=0` vs `d=1`:** disregard as an EV fork — ΔEV identical within MC
   noise. Prefer **`d=1`** only for public-signal pollution.
2. **Two pair:** keep **`d=1`** (dominant +EV lever in the grid).
3. **Only real fork left:** trips **`d=2`** vs **`d=1`** (with two pair `d=1`,
   quads `d=1`, pairs still `d=3` for now):

| Cell | Name | Δ EV | Public lines |
| --- | --- | ---: | --- |
| trips `d=2` | `tp1_tr2_q1` | **+0.140** | d=1 ≈ 21.5% (TP+quads); **d=2 ≈ 9.9%** (trips) |
| trips `d=1` | `tp1_tr1_q1` | **+0.125** | d=1 ≈ 31.4% (TP+trips+quads); **d=2 = 0** |

**Product direction (after C; pair EV still to verify):**

Both trips forks are live strategies under locked two pair `d=1` / quads `d=1` /
pairs `d=3` for Stage C:

| Strategy | Trips | Intent |
| --- | --- | --- |
| **Keep trips `d=2`** (`tp1_tr2_q1`) | Higher B EV (+0.140) | Leaves a public `d=2` lane; pairs *could* later mix into `d=2` for concealment while still allowing pair boat+ |
| **Unify trips `d=1`** (`tp1_tr1_q1`) | Give up ~0.014 B EV | Strengthens / conceals **two pair** on a single public `d=1` line with trips+quads, while **leaving single pairs on `d=3`** (no requirement that pairs join `d=1`) |

Run C under **both**. Neither fork requires moving pairs off `d=3` in C.

**Open verification (done in non-bluff EV grid):** Stage A showdown ranks aggregate JJ–AA
`d=3` ahead of `d=2` on P(win) / boat+. Post-draw **EV** under honest betting still
has pair `d=3` ≥ `d=2` for AA and JJ, but **standing (d=0) is the chip-max**
non-bluff line — drawing creates two pair+ that auto-bet into ~34% straight+.
Keep pairs on **d=3 for range construction** (cannot pollute public d=0).
See [NEXT_STAGE_NONBLUFF_EV.md](NEXT_STAGE_NONBLUFF_EV.md).
Pair `d=1` remains worse on improvement (zero boat+). Concealment mixes still wait until after C.

### C — Checking-range protection (stale fixture note)

The checked-in C run used draw = quads `d=1`, pairs `d=3`, **two pair stand**,
trips `d=2`. Against narrow drawer AA face-stabs:

- Baseline (always bet two pair+): drawer AA face-stab Δ already **−0.42**
- Check 30% / 100% of two pair raised opener EV and deepened stab losses

**Do not trust those magnitudes under `two_pair_d=1`.** Re-run per Step C below.
Pat straight+ still cannot join `d=3`.

### Recommendation table (post-B)

| Class | Draw action | Post-draw bet/check | Notes |
| --- | --- | --- | --- |
| Four of a kind | **d=1** | Bet value (C may thin-check) | EV-neutral vs stand; pollutes d=1 |
| Other straight+ | Stand only | Always bet | Cannot join d=3 |
| Trips | **d=2** (primary) or **d=1** (unified) | C: bet/check mixes | Fork for C; d=2 leaves concealment lane |
| Two pair | **d=1** | C: bet/check mixes | Locked from B |
| Pair JJ–AA | **d=3** for C | Check (M2); thin AA lead | Pair off-d=3 is concealment work *after* C |

---

## Goal of this stage

Answer, with combo-weighted EV (and small grids / mixes), when the opener should:

| Starting class | Candidate draw actions |
| --- | --- |
| **Trips** | draw 2 (default keep trips), draw 1, stand pat |
| **Two pair** | draw 1 (keep both pairs, discard kicker), stand pat |
| **One pair JJ–AA** | draw 3 (default), draw 2, draw 1, stand pat |
| **Four of a kind** | draw 1 (keep quads, discard kicker; **preferred**), stand pat |
| **Other straight+** (straight, flush, full house, SF, five aces) | stand pat only |

Then, **conditional on public \(d\)**, choose post-draw bet vs check (opener
first), and the drawer’s stab/raise replies — especially whether the opener can
make “bet when checked to” with face pairs **unprofitable or indifferent** by
**checking a mix of strong and weak** hands.

### Product hypothesis to test

> Pat straight / flush / boat / SF cannot join `d=3`, so the opener cannot
> protect pair draws by mixing those monsters into draw-three. **Quads can join
> `d=1`** (discard kicker) with no showdown cost vs this caller, which helps
> protect the draw-one line. Separately, by **checking** a mix of strong finals
> (e.g. some two pair / trips / boats / quads after `d\in\{0,1,2\}`) with weak
> one-pair checks, the opener can protect the checking range, reduce the
> drawer’s stab EV, and raise overall opener EV vs the M2 “always bet two pair+”
> baseline.

Confirm or refute with numbers under the **post-B draw defaults**. Old C
results (two pair stand) are suggestive only.

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
| Four of a kind | `d=1` | Keep quads; discard kicker (**baseline: prefer this**) |
| Four of a kind | `d=0` | Stand |
| Other straight+ | `d=0` only | Straight / flush / boat / SF / five aces always stand |

Breaking the made hand (e.g. discarding one pair of two pair, or discarding a
quad) is **out of scope** unless M1-style improvement tables show a clear
exception — default to non-breaking. Quads `d=1` is **not** breaking.

### Public buckets to report separately

Always stratify results by public \(d\):

- `d=3` — nearly pure “was one pair” when pairs stay d=3
- `d=2` — trips-looking under `tp1_tr2_q1`; **empty** under `tp1_tr1_q1`
- `d=1` — two pair / trips-d=1 / quads / (later: pair d=1)
- `d=0` — pat straight+ only once two pair no longer stands

---

## Investigation ladder (do in order)

### A — Draw mechanical tables (no betting change) — DONE

### B — Baseline post-draw with new draw defaults — DONE

Full 12-cell grid; narrowed to trips `d=2` vs `d=1` with two pair `d=1`, quads
`d=1`. See **B decision** above.

### C — Checking-range protection grid (NEXT — re-run)

**For the next agent.** Do not re-do A/B. Do not start pair-concealment mixes
(`pair_d≠3`) here — that is [NEXT_STAGE_PAIR_CONCEALMENT.md](NEXT_STAGE_PAIR_CONCEALMENT.md)
after C.

#### Draw policies to hold fixed (two C runs)

| Run | `two_pair_d` | `trips_d` | `quads_d` | `pair_d` | Why |
| --- | ---: | ---: | ---: | ---: | --- |
| **C-primary** | 1 | **2** | 1 | 3 | Max B EV; public `d=2` lane (optional later pair conceal) |
| **C-unified** | 1 | **1** | 1 | 3 | Give ~0.014 EV to unify/conceal two pair on `d=1`; pairs stay `d=3` |

Use `stage_b_draw_policy(1, 2, 1)` and `stage_b_draw_policy(1, 1, 1)` (or
equivalents). **Replace** the old Stage C default `B_QUADS_D1` (`two_pair_d=0`).

#### Betting search (same spirit as old C; re-measure)

Fix drawer to the interesting narrow band from M2 (straight+ always; face-pair
stab `AA` and `AA+KK`; raise similarly narrow or off). Opener one-pair: **check**
(M2 default); optional thin AA lead only as a sensitivity.

Search opener **check mixes** of strong finals (not draw mixes of pairs):

1. After each public \(d\), fraction of **two pair / trips / boat+** that
   **check** instead of auto-betting (still checking many one-pair hands).
2. Prefer reporting mixes **conditional on \(d\)** when mass differs (under
   C-primary, two pair lives on `d=1`, trips on `d=2` — do not conflate with pat
   `d=0` two pair from the old fixture).

Report for each candidate:

- Opener EV (all deals; by starting class; by public \(d\))
- Drawer stab frequency and face-pair stab Δ (stab EV − check-down EV) when
  opener checks
- Whether face-pair stab is ≤ 0 (unprofitable) or near 0 (indifferent)
- EV lost on strong hands by checking vs gain from worse/fewer stabs
- Smallest helpful two-pair (and trips) check fractions under each draw fork

#### Implementation notes

- Reuse `run_stage_c` / `CheckMix` / `play_mix_deal`; change the draw policy
  argument(s) to the two cells above; optionally loop both in one CLI run.
- Refresh fixture + pytest pins when numbers move.
- Update this doc’s Findings **C** section with the new magnitudes.
- Out of scope for C: pair `d∈{0,1,2}` mixes; UTG re-solve; sandbagging
  straight+ into `d>0`.

### D — Response lines (only as needed)

Reuse M2 call-down ideas when the drawer bets/raises. Re-tune only if check
mixes change the bet-into range enough that matched thresholds break.

---

## Deliverables

1. Code under `src/fivecarddraw/validation/` (`postdraw_draw_mixes.py`) + CLI —
   A/B done; C needs draw-policy update
2. Fixture summary JSON under `tests/fixtures/validation/` — refresh after C
3. `pytest` pins (tolerance OK for MC)
4. Short markdown in `outputs/validation/` (gitignored) + this doc’s Findings C
5. Clear recommendation table — update after C re-run

---

## Explicitly out of scope

- Full multiway; cascade FFS13 unless product asks
- Pre-draw raises / sandbagging
- Mixing straight / flush / boat / SF / five aces into `d>0` (those must stand)
- Treating quads `d=1` as “breaking” — it is allowed and encouraged for `d=1`
  protection
- Full CFR equilibrium on the whole tree (optional later if grids stall)
- UTG open re-solve
- Pair concealment EV (`pair_d≠3`) — after C; see PAIR_CONCEALMENT doc

---

## How to regenerate

```bash
pip install -e ".[dev]"
analyze-postdraw-draw-mixes --n-deals 20000 --write-fixture
pytest -q tests/test_postdraw_draw_mixes.py
```

`outputs/` is gitignored. The **summary fixture** is checked in (seed `20260809`,
6k deals/A-cell, 20k deals B/C). After C is re-run under `tp1_tr2_q1` /
`tp1_tr1_q1`, refresh the fixture and rewrite Findings C.
