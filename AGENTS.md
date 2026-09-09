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

The **CO open chart**, polar BN-vs-CO labs, and the **threshold lookup** are
**signed**. Do not restart them. Do not evaluate the “soon” CO considerations
in the PR that only documents them.

**CO never sandbags** as the opener. The joker is an ace kicker, not trips.

Pins:

- **BN, 0% sandbag:** no legal pass; steal-weighted average open ≈ +$1.93–$1.94
- **BN, 100% seats 1–7:** JJ EV(open) ≈ **−$0.32**, \(p_{\mathrm{raise}}\) ≈ 0.573
- **BN, 100% seats 1–6 only** (CO never sandbags): JJ ≈ **−$0.016**; uniform
  \(r^*\approx 98\%\). Lowest +EV BN open is **AA** (~+$0.18 even folding)
- **CO open chart** (1–6 slowplay \(r\)): bare JJ +EV below ~79%; ace then
  joker buy higher bands. At 93%+ pass JJ even with the joker; at 96%+ KK
  needs the joker. Frame:
  [docs/research/cutoff_open_sandbag_v1.md](docs/research/cutoff_open_sandbag_v1.md)
- **BN vs CO lookup** (chart-range CO at table \(r\)):

| \(r\) | JJ–KK | AA | Two pair | Aces-up / trips |
| --- | --- | --- | --- | --- |
| 0% (all legal) | fold | **raise** | raise | raise |
| 79–86% | fold | **fold** | raise | raise |
| 87–96% / tight | fold | fold | **call** | raise |

Two flips: **AA** raise→fold at \(r=79\%\) (bare JJ out of CO). **Two pair**
raise→call at \(r=87\%\) (KK needs a blocker). 2:1 still **call** on the
all-legal polar. Ticket archive:
[docs/NEXT_STAGE_BN_VS_CO_GRID.md](docs/NEXT_STAGE_BN_VS_CO_GRID.md).

**Soon (do not start in this docs PR).** Ticket:
[docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md)

Extra cutoff considerations before we freeze the open chart:

1. **Range vs \(r\).** Real CO may open wider or tighter than the chart
   (especially under 79%). How much of each BN switch is **CO range** vs
   **trap rate** in 1–6?
2. **BN bluff-raises.** Shorts; air with blockers (joker + king, etc.). The
   published fold-JJ–KK line is a no-bluff bound. Do not mix-solve yet.
3. **CO reverse-blockers.** KK with Q and J cuts BN’s JJ/QQ; when BN
   continues they are more often ahead. Distinct from HJ Super System count.
4. **Two-pair rank and blockers.** Stop treating all non-aces-up two pair as
   one class. CO’s range is mostly two pair+.

**Then (still CO vs BN):**

1. **Multi-raise before the draw** when CO opens and BN raises.
2. **Draw and post-draw, BN vs CO.**

**After CO vs BN is finished:**

3. **HJ strategy**, including ideal sandbag rates with reverse-blockers
   (Super System “count”). Do not start HJ before CO vs BN.

**Toward the end (multiway start; do not expand until much later):**

4. **3:1 drawing hands** after a CO open **and** a BN call.
5. **3:1 and 4:1 inventory + joker split** (joker already with CO/BN vs still
   in the deck).

**Low priority until HJ is started:** Ch.2 §2.9, Ch.5 §5.2 CO bluff after BN
open, pair `d=3` vs `d=2` / concealment, Ring 1 Nash.

**Exploit leaks (through-line, every lab).** Baseline, what moves it, how to
respond. Examples: table not slowplaying enough → HJ may open any legal;
table always slowplaying → late seats fold lowest pairs.

**Read first:** this queue, then [docs/research/INDEX.md](docs/research/INDEX.md).

**Handoff checklist for new agents**

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-f76a` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. After this docs PR lands, take **one** item from
   [docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](docs/NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md).
   Do not evaluate those items in a queue-only PR.
5. Do not start HJ, 3:1/4:1 inventories, multi-raise, concealment, or Ring 1
   until the queue says so. Do not restart the open chart, polar BN labs, or
   the threshold lookup. No UTG re-solve.

Stages **A**, **B**, and **C** (draw grid + check mixes) are done.
Locked post-B / C draws:

- Two pair `d=1`, quads `d=1`, pairs `d=3`
- Fork still live: trips `d=2` (`tp1_tr2_q1`) vs trips `d=1` (`tp1_tr1_q1`)
- C result: **always check two pair** (all public `d`); always bet trips / boat+

Already done: [docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
Stage 0 beliefs in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).

Parent context: [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).
