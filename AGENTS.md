# Agent notes

## Cursor Cloud specific instructions

### What this repo is

Python toolkit for approximate GTO analysis of fixed-limit five-card draw (bug, jacks-or-better, 8 ante-only players). v1 is **pre-draw only**.

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Standard commands

See [README.md](README.md) for `pytest`, `solve-predraw`, `audit-abstraction`, and `python -m fivecarddraw.bench`.

### Non-obvious run notes

- First solve builds an abstraction over all `C(53,5)` hands (~1.5–2 minutes) and caches labels/weights in `outputs/abstraction_cache.json`. Later solves reuse the cache unless `--rebuild-abstraction` is passed.
- Opening → response → raise-tree stages are much faster than abstraction build once the cache exists.
- `outputs/` is gitignored; regenerate locally with `solve-predraw -o outputs`.
- Raise cap: `--max-raises 3` (default, bet+3) vs `--max-raises 1` (smaller tree). Comparison CSV is written automatically.
- Solver is **position-by-position approximate GTO**, not full 8-way Nash. No sandbagging in v1. Equity uses abstracted strength/draw scores, not full remaining-deck enumeration each decision.
- Hand eval is pure Python in v1; `python -m fivecarddraw.bench` documents the aspirational Numba target (≥2e6/s) vs current throughput.
- **Do not treat current opening CSVs as correct strategy.** Early-position opens are known to be too loose vs combo-weighted domination/raise pressure (see validation doc).

### Research overview (human-readable)

[docs/research/INDEX.md](docs/research/INDEX.md) — executive summary, seats 1–8
(UTG…BN), solve-progress ledger, and chapter TOC. Chapters live as separate
files under `docs/research/` (one agent / one chapter preferred). Prefer the
index when explaining the project; keep stage handoffs below for implementation
detail.

### Next stage (implementation agents)

Default code milestone is pair post-draw EV `d=3` vs `d=2` (then concealment)
in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).
Stage C check mixes are done under post-B draws
([docs/NEXT_STAGE_OPENER_DRAW_MIXES.md](docs/NEXT_STAGE_OPENER_DRAW_MIXES.md)).

**Narrative next queue** (research paper): (1) Ch.2 strong-draw call/raise/mix,
(2) Ch.5 CO bluff after BN open (return-to-actor; weaker than strong draws),
(3) post-draw bluff 3-bet **Ring 1** on the cap node
([docs/NEXT_STAGE_POSTDRAW_BLUFF.md](docs/NEXT_STAGE_POSTDRAW_BLUFF.md); do not
start Ring 2 first) — see [docs/research/INDEX.md](docs/research/INDEX.md)
“Immediate research queue.”

**Read first for concealment code:** [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md)

Stages **A**, **B**, and **C** are done (12-cell draw grid + check mixes).
Locked post-B / C draws:

- Two pair `d=1`, quads `d=1`, pairs `d=3`
- Fork still live: trips `d=2` (`tp1_tr2_q1`) vs trips `d=1` (`tp1_tr1_q1`)
- C result: **always check two pair** (all public `d`); always bet trips / boat+
- Next: verify pair post-draw EV `d=3` vs `d=2` before `pair_d≠3` mixes
  (see [NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md))
- Do **not** redo Stage C or fold the cap/3-bet street into the M2 check grid

Already done: [docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
Stage 0 beliefs in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).

Parent context: [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).

### Handoff checklist for new agents

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-f76a` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. Read `docs/NEXT_STAGE_PAIR_CONCEALMENT.md`; verify pair EV `d=3` vs `d=2` first
5. Do not redo Stage C, start `pair_d≠3` mixes before that EV table, or UTG re-solve
