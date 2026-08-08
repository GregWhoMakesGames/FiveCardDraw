# Next stage: dealer-seat opening equity validation data

**Status:** Calling-draw pot odds / cascade / face-pair outs implemented (see `tests/fixtures/validation/` and PR #3). Showdown matrix + M2 face-pair post-draw grid: [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md), [POSTDRAW_M2_FACE_PAIR_GRID.md](POSTDRAW_M2_FACE_PAIR_GRID.md).

## Goal

Create **ground-truth (or near ground-truth) validation data** for **dealer-seat opening hand classes** at current stakes, including **post-draw equity vs drawing callers**, to drive and accept future solver improvements.

Dealer-first remains the right ladder rung: late-position openers are the simplest credible range to treat as “the opener,” and at `$0.25` / `$2-$4` the folded-to-dealer open decision is small — but **validation of opener equity against calls is not pre-draw-only** (see below).

## Game constants (do not reinvent)

| Parameter | Value |
| --- | --- |
| Players | 8 |
| Ante | $0.25 (starting pot $2) |
| Small / big bet | $2 / $4 |
| Openers | Jacks or better |
| Bug | Ace, or complete straight / flush / SF |
| Blinds | None |
| Pre-draw action | UTG = left of dealer; dealer acts last |
| Draw | Starts left of dealer; typically **one-card** draws for the bug SF/flush/straight hands under study |
| Sandbagging | Out of scope for this stage |

## Critical design requirements (from product owner)

### 1. This stage is not pre-draw-only

We must analyze **drawing hands that cannot open** (jacks-or-better illegal) but have correct pot odds / equity to **call** (and sometimes raise) an open — especially bug-assisted 16+ out straight / flush / straight-flush draws.

**Nuance for the implementer (do not skip):**

| Node | Pre-draw enough? | Notes |
| --- | --- | --- |
| Folded-to-dealer: open vs pass | Yes, almost trivial | Nobody left behind; open-legal made hands steal `$2`. Still write this sanity fixture. |
| **Opener equity vs callers** (validation data for future solver) | **No** | Callers include non-opening draws. Their value is realized **after the draw**. EV / equity tables for dealer opening classes vs those ranges **must** model draw improvement. |

So: keep a tiny folded-to-dealer open/pass table, but the **main** deliverable is post-draw equity of dealer opening classes against drawing (and made) continue ranges.

### 2. Split opener classes finely above one pair — especially trips+

Do **not** collapse all `trips+` (or all “strong made”) into one bucket for this validation work.

**Why:** Bug-assisted calling draws are primarily trying to make **straights, flushes, and straight-flushes**. They only rarely “win” by backing into a weak pair (bug-ace, KK/QQ/JJ) that happens to beat a thin dealer open. Therefore:

- Dealer opening a **pat straight or flush** is always +EV in the folded-to-dealer steal node, and vs draws the relevant question is draw-completion equity (and redraws), not pair-vs-pair.
- Those same pat hands **change post-draw equity of callers a lot** vs when the opener has JJ–AA or two pair / trips.
- Validation tables must report equity **separately** at least for:

  - `pair_J`, `pair_Q`, `pair_K`, `pair_A` (keep distinct; face pairs block different outs)
  - `two_pair` (optionally aces-up / kings-up vs other)
  - `trips` (ace trips / king trips / other — separate if mass allows)
  - `straight`, `flush`, `full_house`, `quads` / `straight_flush` / `five_aces` as separate rows

Coarse solver abstraction (few hundred buckets) may remain for the old `solve-predraw` path; **validation fixtures should be finer for made categories above one pair.**

### 3. One-card draw improvement + card removal are mandatory

For drawing continue hands, compute **P(improve after drawing one card)** (and resulting hand category distribution), **conditioned on the opener’s hole cards**.

Card removal is essential:

- Opener with **QQ/KK/AA/JJ** (and suited structure) **blocks** high cards and often blocks the best flush/straight/SF outs.
- Equity of a “22-out” style bug SF draw vs QQ is **not** the same as vs a rag two pair or vs a pat flush.
- Implementation must remove opener cards (and caller cards) from the remaining deck before enumerating or sampling the draw card(s).

Minimum API shape (suggested):

```text
equity_after_one_card_draw(opener_hand, caller_hand) -> {
  p_caller_wins, p_tie, p_opener_wins,
  caller_improve_dist,  # e.g. sf / flush / straight / pair / none
}
```

Aggregate by opener class × caller class with combo weights.

## Why dealer-first

1. Dealer opening classes are a clean “opener range” prototype without UTG multiway steal chaos.
2. Folded-to-dealer open/pass is an easy sanity fixture.
3. HU (or single-caller) post-draw equity opener-vs-draw is still tractable with enumeration/MC + card removal.
4. Known failure mode elsewhere: current opener is too loose UTG (e.g. QQ open 100%). Do not “fix” early seats until opener-vs-draw post-draw numbers exist.

## Deliverables

Write under `outputs/validation/` (gitignored) and pin checked-in **fixtures** under e.g. `tests/fixtures/validation/` for CI.

1. **Deal stats** (exact or MC, with card removal where hero hand fixed):
   - Unconditional open-legal / JJ / QQ / KK / AA / two pair+ / better-than-JJ / better-than-QQ
   - Conditional on hero holding each dealer opener class above
2. **Folded-to-dealer open/pass sanity table**
   - Open-legal made hands: EV(open) = +starting pot (antes); pass = 0
   - Non-open-legal: cannot open
3. **Main: post-draw equity matrix**
   - Rows: dealer opener classes (fine split for trips+)
   - Columns: caller classes — at least:
     - bug SF / flush / straight draws (bin by outs if possible)
     - other continue hands you need for acceptance
   - Cells: combo-weighted P(win/tie/lose) after **one-card** draw for the caller (and stand-pat or appropriate discard policy for opener — document assumptions explicitly, e.g. pat hands stand pat; one-pair draws one–three kickers — state chosen policy)
4. **Draw improvement tables** with card removal:
   - For each opener class × draw class: distribution of caller’s final hand after one card
5. **Acceptance tests** (`pytest`) that lock the above within tolerance
6. Optional: flag disagreements vs current `solve-predraw` dealer row (informational; do not “fix” by trusting the old sigmoid model)

## Assumptions to document in code/README for this stage

Be explicit; wrong discard policies create false equity:

- Caller draw policy for the studied draws: hold 4 to a SF/flush/straight + bug, draw **one**
- Opener discard policy by class (stand pat on straight+; define two pair / trips / one pair)
- Showdown after draw; no further betting in the **first** equity fixtures (add bet/raise layers later if needed)
- Heads-up opener vs one caller for the core matrix (multiway later)

## Known combinatorial facts (from prior agent work)

Unconditional (full `C(53,5)` with bug):

| Event | ≈ Frequency |
| --- | --- |
| Open-legal (jacks or better) | 22.40% |
| Pair AA | 4.81% |
| Pair KK / QQ / JJ each | 3.13% |
| Two pair or better | 8.21% |
| Better than QQ (KK+ or two pair+) | 16.15% |
| Better than JJ (QQ+ or two pair+) | 19.27% |

Given hero holds QQ (card removal, sampled):

| Event | ≈ Probability |
| --- | --- |
| Random later hand already beats QQ | 13.4% |
| ≥1 of 7 behind already beats QQ | ~63.5% |
| All 7 not open-legal (opener-only steal) | ~19.4% |

**UTG note (later stage):** User critique — call-only is not “break-even/small loss”; with steal ~20% and face-raise ~55%, QQ UTG is strongly −EV. Future early-position work needs combo-weighted raise/call mixes **and** these post-draw opener-vs-draw numbers.

## Suggested implementation sketch

```
src/fivecarddraw/validation/
  deal_stats.py           # frequencies + card removal
  draw_equity.py          # one-card draw enumeration/MC with removal
  opener_classes.py       # fine trips+/straight/flush splits for fixtures
  dealer_sanity.py        # folded-to-dealer open/pass
  report.py               # outputs/validation/* + fixture writers
tests/test_dealer_validation.py
tests/fixtures/validation/
```

CLI idea: `validate-dealer-open -o outputs/validation`

## Out of scope for this stage

- Re-solving full 8-seat opening charts as “truth”
- Sandbagging
- Full multiway post-draw betting equilibrium
- Changing ante:bet ratio
- Trusting sigmoid score-vs-range equity from `predraw/model.py` for acceptance

## Branching note

PR #1 (solver v1) is **merged** to `main`. Merge handoff-doc PRs first if needed, then start implementation from updated `main` on e.g. `cursor/dealer-open-validation-<suffix>`.
