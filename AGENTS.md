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
[docs/NEXT_STAGE_SANDBAG_AND_CO.md](docs/NEXT_STAGE_SANDBAG_AND_CO.md) (method
archive). CO **does not sandbag** (0% lab). Use the 0%/100% pins below as
inputs to the next grid; do not re-run those two endpoints as the product.

Pins (fold-to-raise bound; 2:1 callers still **call**):

- **BN, 0% sandbag:** no legal pass; steal-weighted average open ≈ +$1.93–$1.94
- **BN, 100% seats 1–7:** JJ EV(open) ≈ **−$0.32**, \(p_{\mathrm{raise}}\) ≈ 0.573
- **BN, 100% seats 1–6 only** (CO never sandbags): JJ ≈ **−$0.016**,
  \(p_{\mathrm{raise}}\) ≈ 0.496. Uniform slowplay rate making all legal BN
  opens +EV ≈ **98%**. Lowest +EV BN open is **AA** (~+$0.18 even folding)
- **CO, 0% sandbag in 1–6:** open every legal class; JJ ≈ **+$1.44**. “Never
  slowplay” is **this lab only** (CO as opener still never sandbags)
- **CO vs 100% 1–6 sandbag:** JJ/QQ/KK are −EV if they fold the raise. **JJ
  binds** at Bayes \(r^*\approx 79\%\) (QQ ~84%, KK ~87%). At 100%, KK+joker
  is +EV; QQ+joker ~0 (inside 1 SE); JJ+joker still −EV. Ace kickers all −EV

**Narrative next queue** (CO+BN first, then HJ; finish one before starting the
next). Goal after 1–4: CO+BN mostly worked out.

1. **Done. CO open chart** — JJ 79/86/93, QQ 84/90, KK 87/96 (ace / joker thresholds); CO does not sandbag. [cutoff_open_sandbag_v1.md](docs/research/cutoff_open_sandbag_v1.md).
2. **BN vs a CO open.** Which hands BN calls; which hands BN raises.
3. **Multi-raise before the draw.** Effect of a raise war when CO opens and BN
   raises (caps, fold/continue for each).
4. **Draw and post-draw, BN vs CO.** Continue the HU laboratory after the
   pre-draw line is known.
5. **HJ strategy** (only after 1–4). Which hands HJ opens; which hands, and at
   what frequency, HJ slowplays.

**After HJ is started** (not before): deceptive play, strong-draw call/raise
mix (Ch.2 §2.9), CO bluff after BN open (Ch.5 §5.2), and strong-pair draw /
post-draw optimization (pair `d=3` vs `d=2`, concealment, Ring 1). Those are
**low priority** until CO+BN then HJ are underway.

**Exploit leaks (through-line, every lab).** Keep a baseline, then say what
moves it and how to respond. Examples: if the table is not slowplaying
enough, HJ may open any legal hand; if the table always slowplays, late seats
fold their lowest pairs. Eventual guidance shape: baseline GTO-ish line;
what influences it; how to exploit {too-wide caller, too much slowplay, …}.

**Read first:** this queue, then [docs/research/INDEX.md](docs/research/INDEX.md)
and the CO sandbag frame
[docs/research/cutoff_open_sandbag_v1.md](docs/research/cutoff_open_sandbag_v1.md).

**Handoff checklist for new agents**

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-f76a` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. Item 1 (CO open chart) is **done** in
   [docs/research/cutoff_open_sandbag_v1.md](docs/research/cutoff_open_sandbag_v1.md).
   Take **item 2** (BN vs a CO open) unless a later item is assigned. One
   item per PR.
5. Do not start HJ before CO+BN items 1–4. Do not start Ch.2 §2.9,
   concealment, or Ring 1 Nash until HJ has started. Do not restart the
   signed 0%/100% sandbag endpoints. No UTG re-solve.

Stages **A**, **B**, and **C** (draw grid + check mixes) are done.
Locked post-B / C draws:

- Two pair `d=1`, quads `d=1`, pairs `d=3`
- Fork still live: trips `d=2` (`tp1_tr2_q1`) vs trips `d=1` (`tp1_tr1_q1`)
- C result: **always check two pair** (all public `d`); always bet trips / boat+

Already done: [docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
Stage 0 beliefs in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).

Parent context: [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).
