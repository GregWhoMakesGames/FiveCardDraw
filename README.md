# FiveCardDraw

Research toolkit for approximate GTO analysis of **fixed-limit five-card draw** with the **bug**, **jacks-or-better** to open, and **eight ante-only** players.

v1 solves **pre-draw only** (opening → call/raise vs open → raise/re-raise trees) using a position-by-position equilibrium approximation, and writes Super System–style CSV tables.

## Game (v1 defaults)

| Parameter | Value |
| --- | --- |
| Players | 8 |
| Ante | $0.25 each (pot $2) |
| Limit | $2 / $4 |
| Openers | Jacks or better |
| Bug | Ace, or complete straight / flush / straight-flush |
| Blinds | None (ante-only) |
| Pre-draw action | Left of dealer first |
| Raise cap | Bet + 3 raises (`--max-raises 1` for bet+1) |

**Not in v1:** sandbagging, post-draw play, full 8-way Nash, ante:bet ratio sweeps.

**Important:** Current solver charts are a working pipeline, not verified strategy.

**Start here for the research arc:** [docs/research/INDEX.md](docs/research/INDEX.md)
(executive summary, seat map, solve-progress ledger, and chapter TOC).
Chapters are split under `docs/research/` so parallel agents can edit different
sections with fewer conflicts. Legacy redirect: [docs/RESEARCH_PAPER.md](docs/RESEARCH_PAPER.md).

Validation fixtures cover drawing-call odds, showdown matrix, opener-first
post-draw face-pair betting, opener draw-count / check-mix protection, and
non-bluff EV by class × draw count — see
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
[docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_OPENER_DRAW_MIXES.md](docs/NEXT_STAGE_OPENER_DRAW_MIXES.md),
[docs/NEXT_STAGE_NONBLUFF_EV.md](docs/NEXT_STAGE_NONBLUFF_EV.md), and
[docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q
```

## Run pre-draw solve

```bash
solve-predraw -o outputs
# or:
python -m fivecarddraw.predraw.solve -o outputs
```

Useful flags:

- `--max-raises 3` (default) or `1` for a smaller tree
- `--rebuild-abstraction` to ignore `outputs/abstraction_cache.json`
- `--quiet` for less console output

### Outputs

| File | Contents |
| --- | --- |
| `outputs/opening_by_seat.csv` | Open/Pass (and mixes) by seat × bucket |
| `outputs/opening_chart_readable.csv` | Super System–style class × seat actions |
| `outputs/opening_summary.csv` | Aggregate open % by seat |
| `outputs/call_raise_vs_open.csv` | Fold/Call/Raise including non-opening draws |
| `outputs/raise_tree.csv` | Facing raise / re-raise / cap lines |
| `outputs/raise_cap_comparison.csv` | bet+3 vs bet+1 row counts |
| `outputs/abstraction_audit.txt` | Bucket count + AA852/AAT43/AAQ85 checks |
| `outputs/solve_meta.json` | Config, timings, listed approximations |

### Performance (measured on Cloud Agent VM)

| Stage | Typical time |
| --- | --- |
| Abstraction build (2.87M hands) | ~90–100s (then cached) |
| Opening + response + raise tree | ~1–2s with cache |
| Bucket count | ~384 (target: a few hundred) |

Progress bars (via `tqdm`) show stage completion and ETA while solving.

## Abstraction audit only

```bash
audit-abstraction
```

## Hand-eval microbench

```bash
python -m fivecarddraw.bench
```

Target (aspirational with Numba later): ≥ 2e6 hands/sec. Pure Python is acceptable for v1 chart generation.

## Approximations (read this)

1. **Position-by-position** policies, not a single multiway Nash equilibrium.
2. **No sandbagging** — open-legal hands open or pass; they do not check strong hands.
3. **Equity model** uses abstracted strength/draw scores vs ranges (sigmoid), not full deal enumeration every decision.
4. **Count / blockers** adjust opponent open frequency; they do not yet rebuild full remaining-deck distributions.
5. Architecture is ready for later post-draw heads-up, then multiway, then heavier equilibrium under the same bucket model.

## Project layout

```
src/fivecarddraw/
  cards.py hand_rank.py rules.py abstraction.py report.py bench.py
  predraw/opening.py response.py raise_tree.py solve.py model.py
tests/
outputs/          # generated (gitignored)
```
