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

### Next stage (start here on a fresh agent)

**Read first:** [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md)

Build dealer-seat opening equity **validation fixtures** and mathematical acceptance tests. This is **not pre-draw-only**: must include one-card draw improvement for non-opening drawing callers, fine-grained trips+/straight/flush opener splits, and **card removal**. Branch from updated `main`. Prefer a new Cloud Agent chat so context stays small.

### Handoff checklist for new agents

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-14c6` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. Implement validation per the next-stage doc; do not expand into full UTG re-solve until dealer fixtures exist
