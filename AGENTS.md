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

BN sandbag and CO open labs are **signed**. Do not restart
[docs/NEXT_STAGE_SANDBAG_AND_CO.md](docs/NEXT_STAGE_SANDBAG_AND_CO.md) (that
ticket is the method, not the queue). BN-vs-2:1 post-draw Nash (Ring 1 / Ring 2)
stays **tabled**. HJ slowplay mixes are **tabled**.

Pins (fold-to-raise bound; 2:1 callers still **call**):

- **BN, 0% sandbag:** no legal pass; steal-weighted average open ≈ +$1.93–$1.94
- **BN, 100% seats 1–7:** JJ EV(open) ≈ **−$0.32**, \(p_{\mathrm{raise}}\) ≈ 0.573
- **BN, 100% seats 1–6 only** (CO never sandbags): JJ ≈ **−$0.016**,
  \(p_{\mathrm{raise}}\) ≈ 0.496. Uniform slowplay rate making all legal BN
  opens +EV ≈ **98%**. Lowest +EV BN open is **AA** (~+$0.18 even folding)
- **CO, 0% sandbag in 1–6:** open every legal class; JJ ≈ **+$1.44**. “Never
  slowplay” is **this lab only**
- **CO vs 100% 1–6 sandbag:** JJ/QQ/KK are −EV if they fold the raise. **JJ
  binds** at Bayes \(r^*\approx 79\%\) (QQ ~84%, KK ~87%). At 100%, KK+joker
  is +EV; QQ+joker ~0 (inside 1 SE); JJ+joker still −EV. Ace kickers all −EV

**Narrative next queue** (from [docs/research/INDEX.md](docs/research/INDEX.md)):

1. Ch.2 strong-draw call/raise/mix (§2.9) — CO representation + 19/22-out tail
2. Ch.5 CO bluff after BN open (return-to-actor; no legal CO opener)
3. Pair post-draw EV `d=3` vs `d=2`, then concealment (Ch.4 leftover)

**Read first:** [docs/research/INDEX.md](docs/research/INDEX.md) “Immediate
research queue,” then the chapter for the slice you take.

**Handoff checklist for new agents**

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-f76a` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. Take **one** INDEX queue item (Ch.2 §2.9, Ch.5 §5.2, or pair concealment)
5. Do not resume sandbag-rate search, HJ mixes, Ring 1 Nash, or UTG re-solve

Stages **A**, **B**, and **C** (draw grid + check mixes) are done.
Locked post-B / C draws:

- Two pair `d=1`, quads `d=1`, pairs `d=3`
- Fork still live: trips `d=2` (`tp1_tr2_q1`) vs trips `d=1` (`tp1_tr1_q1`)
- C result: **always check two pair** (all public `d`); always bet trips / boat+

Already done: [docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
Stage 0 beliefs in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).

Parent context: [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).
