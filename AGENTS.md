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

BN sandbag, CO 0%/100% pins, the **CO open chart**, and two **polar** BN-vs-CO
labs are **signed**. Do not restart them. Do not start new analysis in the
PR that lands this rollup — queue only.

**CO never sandbags** as the opener. The joker is an ace kicker, not trips.

Pins (fold-to-raise / polar BN):

- **BN, 0% sandbag:** no legal pass; steal-weighted average open ≈ +$1.93–$1.94
- **BN, 100% seats 1–7:** JJ EV(open) ≈ **−$0.32**, \(p_{\mathrm{raise}}\) ≈ 0.573
- **BN, 100% seats 1–6 only** (CO never sandbags): JJ ≈ **−$0.016**; uniform
  \(r^*\approx 98\%\). Lowest +EV BN open is **AA** (~+$0.18 even folding)
- **CO open chart** (1–6 slowplay \(r\)): bare JJ +EV below ~79%; ace then
  joker buy higher bands. At 93%+ pass JJ even with the joker; at 96%+ KK
  needs the joker. QQ+joker at 100% is +EV inside 1 SE; KK+joker stays +EV.
  Frame: [docs/research/cutoff_open_sandbag_v1.md](docs/research/cutoff_open_sandbag_v1.md)
- **BN vs all-legal CO** (\(r=0\%\)): fold JJ–KK; value-raise AA / two pair /
  trips+; 2:1 call. No air. Frame:
  [docs/research/button_vs_cutoff_all_legal.md](docs/research/button_vs_cutoff_all_legal.md)
- **BN vs tight CO** (\(r\approx 100\%\); AA+ plus QQ/KK+joker): fold
  JJ–**AA**; call two pair (thin); raise aces-up / trips. Frame:
  [docs/research/button_vs_cutoff_tight.md](docs/research/button_vs_cutoff_tight.md)

The interesting inflection is **AA**: raise vs a wide cutoff, fold vs a tight
one. That is what the next grid is for.

**Up next (parallel, after this lands on `main`).** Ticket:
[docs/NEXT_STAGE_BN_VS_CO_GRID.md](docs/NEXT_STAGE_BN_VS_CO_GRID.md)

BN {fold, call, raise} by class at every CO-chart threshold
\(r \in \{79, 84, 86, 87, 90, 93, 96\}\)\). Map \(r\) → CO opening range
(from the chart) → BN action table. A human will not pin \(r\) to 1%; the
lookup is so later seats can read “someone slowplayed, so CO’s range is X,
so BN does Y” without resimulating last two. Polar endpoints 0% and ~100%
are already signed — fill the interior. One threshold per PR is OK.

**Then (still CO vs BN, sequential — not parallel with the grid until the
lookup exists):**

1. **Multi-raise before the draw** when CO opens and BN raises.
2. **Draw and post-draw, BN vs CO.** After the grid + these two, CO+BN is
   mostly worked out.

**After CO vs BN is finished:**

3. **HJ strategy**, including **ideal sandbag rates with reverse-blockers**
   (Super System “count,” to be refined). Which hands HJ opens; which hands
   and frequencies HJ slowplays. Do not start this before CO vs BN.

**Toward the end (multiway start; do not expand until much later):**

4. **3:1 drawing hands** — calling in seats 1–6 after a CO open **and** a BN
   call is a better price than the 2:1 (BN-open) lab. Inventory only at
   first; no multiway post-draw tree.
5. **3:1 and 4:1 draw inventory + joker split.** Which hands those are;
   odds a player holds one given the joker already dealt (to CO or BN)
   vs still in the deck. That rates how often the CO-open + BN-call node
   picks up a drawing call from 1–6.

**Low priority until HJ is started:** deceptive play, Ch.2 §2.9 strong-draw
mix, Ch.5 §5.2 CO bluff after BN open, pair `d=3` vs `d=2` / concealment,
Ring 1 Nash.

**Exploit leaks (through-line, every lab).** Baseline, what moves it, how to
respond. Examples: table not slowplaying enough → HJ may open any legal;
table always slowplaying → late seats fold lowest pairs. Eventual shape:
baseline line; what influences it; how to exploit {too-wide caller, too
much slowplay, …}.

**Read first:** this queue, then [docs/research/INDEX.md](docs/research/INDEX.md).

**Handoff checklist for new agents**

1. `git fetch origin main && git checkout main && git pull origin main`
2. Create `cursor/<short-name>-f76a` (or the suffix required by the run)
3. `pip install -e ".[dev]" && pytest -q`
4. After this rollup is on `main`, take the **threshold grid** (one \(r\) or
   the whole table). Ticket:
   [docs/NEXT_STAGE_BN_VS_CO_GRID.md](docs/NEXT_STAGE_BN_VS_CO_GRID.md)
5. Do not start HJ, reverse-blockers, 3:1/4:1 inventories, multi-raise,
   concealment, or Ring 1 until the queue says so. Do not restart signed
   0%/100% sandbag endpoints, the CO open chart, or the two polar BN labs.
   No UTG re-solve.

Stages **A**, **B**, and **C** (draw grid + check mixes) are done.
Locked post-B / C draws:

- Two pair `d=1`, quads `d=1`, pairs `d=3`
- Fork still live: trips `d=2` (`tp1_tr2_q1`) vs trips `d=1` (`tp1_tr1_q1`)
- C result: **always check two pair** (all public `d`); always bet trips / boat+

Already done: [docs/POSTDRAW_M2_FACE_PAIR_GRID.md](docs/POSTDRAW_M2_FACE_PAIR_GRID.md),
[docs/NEXT_STAGE_SHOWDOWN_MATRIX.md](docs/NEXT_STAGE_SHOWDOWN_MATRIX.md),
Stage 0 beliefs in [docs/NEXT_STAGE_PAIR_CONCEALMENT.md](docs/NEXT_STAGE_PAIR_CONCEALMENT.md).

Parent context: [docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md](docs/NEXT_STAGE_DEALER_OPENING_EQUITY.md).
