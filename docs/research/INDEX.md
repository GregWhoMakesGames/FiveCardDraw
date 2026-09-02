# Research paper — index

**Approximate GTO analysis of fixed-limit five-card draw** (bug, jacks-or-better, eight ante-only).

This folder is the **human-readable research paper**, split into chapters so parallel agents can edit different sections with fewer merge conflicts. Start here.

| Field | Value |
| --- | --- |
| Stakes (v1) | $0.25 ante ($2 pot), $2 / $4 limit |
| Codebase | [`fivecarddraw`](../../README.md) |
| Audience | Researchers and poker-curious readers (basic poker OK) |
| Status | Living document. Ch.1–2 filled; Ch.3 non-bluff EV + cap; Ch.4 Stage C (always check two pair); Ch.5 planned |

**Technical handoffs** (implementation detail, denser than chapters):

- [../NEXT_STAGE_DEALER_OPENING_EQUITY.md](../NEXT_STAGE_DEALER_OPENING_EQUITY.md)
- [../NEXT_STAGE_SHOWDOWN_MATRIX.md](../NEXT_STAGE_SHOWDOWN_MATRIX.md)
- [../POSTDRAW_M2_FACE_PAIR_GRID.md](../POSTDRAW_M2_FACE_PAIR_GRID.md)
- [../NEXT_STAGE_OPENER_DRAW_MIXES.md](../NEXT_STAGE_OPENER_DRAW_MIXES.md)
- [../NEXT_STAGE_PAIR_CONCEALMENT.md](../NEXT_STAGE_PAIR_CONCEALMENT.md)
- [../NEXT_STAGE_NONBLUFF_EV.md](../NEXT_STAGE_NONBLUFF_EV.md)
- [../NEXT_STAGE_POSTDRAW_CAP.md](../NEXT_STAGE_POSTDRAW_CAP.md)
- [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md)

---

## Executive summary

This project builds a **reproducible, bottom-up** analysis of fixed-limit five-card draw with the bug under jacks-or-better opening rules. The long-term goal is an approximate game-theoretic (GTO) understanding of opening, calling, drawing, and post-draw betting — not a single black-box Nash solver for the full eight-player tree.

**Why the problem is hard.** Eight players, a 53-card deck (52 + bug), pre-draw and post-draw streets, and a public “cards drawn” signal create a decision space far larger than heads-up hold’em. Early-position opens face seven players behind; late-position steals look easy until drawing callers with huge outs enter the pot. We **slice** the game into validation ladders with exact or Monte Carlo ground truth, then expand seat by seat — and we track **what fraction of deals** each slice covers (see [Solve-progress ledger](#solve-progress-ledger)).

**What we have done so far.** Base engine + pre-draw pipeline (charts not trusted); drawing-call inventory (18,396 2:1 combos); dealer opener showdown / post-draw betting / draw-count grids; **non-bluff EV by class × d**; post-draw **cap / 3-bet vs call** on the raise node; **Stage C check mixes** (always check two pair under `tp1_tr2_q1` / `tp1_tr1_q1`); public-draw belief tables.

**Central claim (working).** Late position is the right laboratory. Seat naming and the progressive deal-share breakdown live in this index so every chapter uses the same language.

---

## Seat map (human docs)

Use **seats 1–8** in all research prose. Code may still use 0-based indices internally.

| Seat | Hold’em name | Role in this paper |
| ---: | --- | --- |
| 1 | **UTG** | First to act pre-draw (left of dealer) |
| 2 | **UTG+1** | |
| 3 | **UTG+2** | |
| 4 | **UTG+3** | |
| 5 | **LJ** | Lojack |
| 6 | **HJ** | Hijack — last of the “early six” |
| 7 | **CO** | Cutoff — last two with BN |
| 8 | **BN** | Button / dealer — acts last pre-draw |

**Early six** = seats 1–6 (UTG…HJ). **Last two** = seats 7–8 (CO, BN).

---

## Table of contents

| Ch. | File | Topic | Suggested owner |
| ---: | --- | --- | --- |
| 1 | [ch01_roadmap.md](ch01_roadmap.md) | Order of operations + deal-share framing | Roadmap / coordination |
| 2 | [ch02_drawing_callers.md](ch02_drawing_callers.md) | Non-opening draws; **next: call/raise/mix** (§2.9) | Drawing-call validation |
| 3 | [ch03_dealer_opening.md](ch03_dealer_opening.md) | BN opening + post-draw equity (incl. cap) | Dealer / showdown / M2 |
| 4 | [ch04_draw_mixes.md](ch04_draw_mixes.md) | Opener draw mixes + check protection (C done) | Draw mixes / concealment next |
| 5 | [ch05_later_seats.md](ch05_later_seats.md) | CO open climb; **CO bluff after BN open** (§5.2); HJ | Later seats |
| A | [appendix_a_rules.md](appendix_a_rules.md) | Game rules | Shared (rare edits) |
| B | [appendix_b_code.md](appendix_b_code.md) | Code map / CLIs | Shared (rare edits) |
| C | [appendix_c_crosswalk.md](appendix_c_crosswalk.md) | Doc crosswalk | Shared (rare edits) |

Legacy path [`../RESEARCH_PAPER.md`](../RESEARCH_PAPER.md) redirects here.

---

## Solve-progress ledger

Independent-events planning numbers use unconditional open-legal frequency \(p \approx 0.224\) (exact over \(C(53,5)\)). Card removal will refine these; treat as **planning**, not theorem.

### Coarse split (still useful)

| Slice | Formula | ≈ % of deals | Meaning |
| --- | --- | ---: | --- |
| Folded to last two | \(P(\text{seats 1–6 unable}) \approx (1-p)^6\) | **22%** | Action reaches CO/BN |
| Someone in early six *can* open | \(1 - (1-p)^6\) | **78%** | Early / multiway mass ahead |

### Granular split of the ~22% (folded to CO/BN)

Seats 1–6 unable partitions into three disjoint cases:

| Slice | Formula | ≈ % | Status | Home chapter |
| --- | --- | ---: | --- | --- |
| **No legal opens** | \((1-p)^8\) — all eight seats lack openers | **13.1%** | **Solved** (no open betting; typically redeal / dead hand under house rules) | Ch.1 |
| **Only BN can open** | \((1-p)^7 \cdot p\) — seats 1–7 unable, BN open-legal | **3.8%** | Split further below | Ch.3 |
| **CO can open** (BN may or may not) | \((1-p)^6 \cdot p\) — seats 1–6 unable, CO open-legal | **4.9%** | Planned with CO solve | Ch.5 |

These three sum to the ~22% folded-to-last-two mass.

### Split of “only BN can open” (~3.8%)

After seats 1–7 lack openers and BN has an open-legal hand, BN’s open faces the seven hands behind — none open-legal, but some may still be **2:1 drawing calls** (Ch.2 inventory). Open-legal and 2:1 sets are disjoint. Let \(p_{\mathrm{open}} \approx 0.224\), \(p_{2:1} \approx 18{,}396 / C(53,5) \approx 0.00641\), \(q_{\mathrm{neither}} = 1 - p_{\mathrm{open}} - p_{2:1}\). Independent-seat planning:

| Slice | Formula (planning) | ≈ % of *all* deals | Status | Home chapter |
| --- | --- | ---: | --- | --- |
| BN can open (steal), **nobody** has 2:1 call odds | \(q_{\mathrm{neither}}^{7} \cdot p_{\mathrm{open}}\) | **~3.6%** | **Solved** for open-legal made hands: EV(open) ≈ +$2 ante pot | Ch.3 § folded-to-BN sanity |
| BN can open (steal), **≥1** seat has a good calling hand (2:1 outs) | \(\bigl[(1-p_{\mathrm{open}})^{7} - q_{\mathrm{neither}}^{7}\bigr] \cdot p_{\mathrm{open}}\) | **~0.20%** | **In progress** — inventory + showdown + M2 + non-bluff EV + **Stage C** (always check two pair) done; bluff delta / pair concealment next | Ch.2 + Ch.3–4 |

Unconditional \(P(\ge 1\) of 7 seats is a 2:1 caller\() \approx 4.4\%\). The steal-into-drawer band is much smaller because it also requires seats 1–7 all non-open-legal **and** BN open-legal — still the strategically important laboratory for thin opens.

### How to read “percent of the game solved”

1. **No legal opens (~13.1%)** — solved.
2. **Steal with no drawing caller (~3.6%)** — solved for “always open made jacks+.”
3. **Steal into a 2:1 drawer (~0.21%)** — the active BN laboratory (Ch.2–4). Absolute deal share is small; **strategic importance is large** (this is what makes thin opens lose).
4. **CO live after early six fold (~4.9%)** — next seat after BN template.
5. **Early six can open (~78%)** — remaining mountain.

Update the **Status** column in this ledger when a chapter’s owner claims a slice solved — prefer editing **only this table** in `INDEX.md`, not copying percentages into chapter bodies.

### Immediate research queue

| Order | Work | Chapter | Blocks |
| ---: | --- | --- | --- |
| 1 | Strong draws: call vs raise vs mix (combo-weighted EV) | [Ch.2 §2.9](ch02_drawing_callers.md) | CO represent-bluffs |
| 2 | CO bluff after BN open (return-to-actor: CO passed with no legal opener; others fold) — call/raise with underpair / high card? | [Ch.5 §5.2](ch05_later_seats.md) | Needs #1 for value-range shape |
| 3 | Pair post-draw EV `d=3` vs `d=2`, then concealment (Ch.4 leftover) | [Ch.4](ch04_draw_mixes.md) / [../NEXT_STAGE_PAIR_CONCEALMENT.md](../NEXT_STAGE_PAIR_CONCEALMENT.md) | Stage C done; do not redo check mixes |
| 3b | Post-draw **bluff 3-bet Ring 1** (indifference on the cap node) | [Ch.3 §3.5](ch03_dealer_opening.md) / [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md) | Needs cap street; **Ring 1 before Ring 2** |
| 4 | CO open/pass; HJ sandbagging | Ch.5 | After #2 template exists |

### Later (low priority)

| Work | Chapter | Notes |
| --- | --- | --- |
| Trips `d=1` kicker: highest vs non-face / lowest | [Ch.4](ch04_draw_mixes.md) | v1 keeps highest-rank (bug=ace). Hypothesis: a face kicker is more often already in the 2:1 caller, so fewer boat outs remain. After Stage C. Detail: [../NEXT_STAGE_OPENER_DRAW_MIXES.md](../NEXT_STAGE_OPENER_DRAW_MIXES.md) |

---

## Parallel agents (fewer conflicts)

**Yes — split chapters into separate files** (this layout). Practical rules:

1. **One agent → one chapter file** (plus its matching code module / fixture if any). Avoid two agents editing the same `.md` in one PR wave.
2. **Shared facts live only in this `INDEX.md`:** seat map, solve-progress ledger, TOC ownership table. Chapters **link here** instead of restating percentages or seat indices.
3. **Appendices** are rarely edited; bump them in a dedicated docs PR if CLIs change.
4. **Code ownership mirrors chapters** where possible (e.g. Ch.2 ↔ `validation/draw_call_odds.py` + cascade / face-pair; Ch.4 ↔ `postdraw_draw_mixes.py`). Don’t “fix” unrelated fixtures in the same PR.
5. **Handoff docs** under `docs/NEXT_STAGE_*.md` stay as implementation tickets; chapters are the narrative. Agents updating numbers should refresh the chapter **and** the ledger row, not only the handoff doc.
6. Prefer **short PRs** scoped to one chapter + its tests over mega-diffs across Ch.1–5.

---

## Revision notes

| Date | Change |
| --- | --- |
| 2026-09-02 | Stage C re-run: always check two pair under `tp1_tr2_q1` / `tp1_tr1_q1` |
| 2026-09-02 | Later queue: trips `d=1` kicker rank (highest vs non-face) after Stage C |
| 2026-09-01 | Non-bluff EV by BN class × d vs 2:1 caller (Ch.3 §3.4); bluff delta next |
| 2026-09-01 | Initial monolithic `RESEARCH_PAPER.md` |
| 2026-09-01 | Split into `docs/research/` chapters; seats 1–8 + hold’em names; granular solve-progress ledger; parallel-agent notes |
| 2026-09-01 | Document next queue: Ch.2 call/raise/mix; Ch.5 CO bluff after BN open |
| 2026-09-01 | Pin §5.2 return-to-actor (CO passed with no legal opener); clarify bluff = call/raise with less than strong draws |
| 2026-09-02 | Post-draw bluff 3-bet Ring 1 handoff (flush indifference on the cap node) |
