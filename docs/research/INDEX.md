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
- [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md)
- [../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md)
- [../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md)

**How we name work.** [INDEX](#research-frames) holds the **frame**. Each frame has its own alias table so “Ring 2” does not float free of *which laboratory*. CO open chart, polar BN-vs-CO labs, and the **threshold lookup** are **signed**. Next work is the [soon CO-open considerations](#immediate-research-queue). Living handoff: [AGENTS.md](../../AGENTS.md).

---

## Executive summary

This project builds a **reproducible, bottom-up** analysis of fixed-limit five-card draw with the bug under jacks-or-better opening rules. The long-term goal is an approximate game-theoretic (GTO) understanding of opening, calling, drawing, and post-draw betting — not a single black-box Nash solver for the full eight-player tree.

**Why the problem is hard.** Eight players, a 53-card deck (52 + bug), pre-draw and post-draw streets, and a public “cards drawn” signal create a decision space far larger than heads-up hold’em. Early-position opens face seven players behind; late-position steals look easy until drawing callers with huge outs enter the pot. We **slice** the game into validation ladders with exact or Monte Carlo ground truth, then expand seat by seat — and we track **what fraction of deals** each slice covers (see [Solve-progress ledger](#solve-progress-ledger)).

**What we have done so far.** Base engine + pre-draw pipeline (charts not trusted); drawing-call inventory (18,396 2:1 combos); dealer opener showdown / post-draw betting / draw-count grids; **non-bluff EV by class × d**; **Stage C check mixes** (always check two pair); post-draw **cap / 3-bet** on the Stage C raise node, split into **two 3-bet lines** by public \(d\); public-draw belief tables.

**Central claim (working).** Late position is the right laboratory. Seat naming and the progressive deal-share breakdown live in this index so every chapter uses the same language.

---

## Research frames

A **frame** is the laboratory (who opened, sandbagging on/off, whose EV we want). **Aliases** (Ring 1, Line 2, Stage C) live *inside* a frame so they stay short in chat.

Say `evaluate button_open_no_sandbagging Ring 2` when the frame might be wrong. `evaluate Ring 2` is enough when recent work is already in that file.

| Frame (slug) | File | Laboratory |
| --- | --- | --- |
| **button_open_no_sandbagging** | [button_open_no_sandbagging.md](button_open_no_sandbagging.md) | BN opened; no sandbagging. Vs-draw Nash **tabled**. |
| **button_open_sandbag_v1** | [button_open_sandbag_v1.md](button_open_sandbag_v1.md) | BN open vs 100% two-pair+ (HJ/CO aces) sandbag; 1–6-only follow-up: CO never sandbags. |
| **cutoff_open_no_sandbagging** | [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md) | Seats 1–6 unable; CO open/pass with BN behind. **v1 signed (0% sandbag):** open all legal (JJ +$1.44); no sandbag. |
| **cutoff_open_sandbag_v1** | [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) | CO vs 1–6 sandbag rate. **Open chart:** JJ/QQ/KK × {avg, ace, joker}. Bare JJ +EV below ~79%; at 100% only KK+joker is clearly +EV. CO does not sandbag. |
| **button_vs_cutoff_all_legal** | [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md) | Seats 1–6 unable; CO opens 100% legal (no sandbag). BN fold/call/raise vs that open. **No air.** Fold JJ–KK; value-raise AA / two pair / trips+; 2:1 call. |
| **button_vs_cutoff_tight** | [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) | BN fold/call/raise vs a **tight** CO open (AA+ plus QQ/KK+joker). Range 2; not all-legal. Fold JJ–AA; call two pair (thin); raise aces-up / trips. |

Mint a new frame file when the laboratory changes. Add a row here. Do not reuse Ring / Stage / Line aliases from one frame in another without a new table.

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
| — | [button_open_no_sandbagging.md](button_open_no_sandbagging.md) | Frame aliases (Ring / Line / Stage C); Nash tabled | Frozen vs-draw |
| — | [button_open_sandbag_v1.md](button_open_sandbag_v1.md) | 100% sandbag raise vs BN JJ; 1–6-only \(r^*\approx 98\%\) | **Signed** |
| — | [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md) | CO open/pass with BN behind (0% sandbag in 1–6) | **Signed (v1)** |
| — | [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) | CO open chart (slowplay × blockers) + 0%/100% pins; JJ binds ~79% | **Signed** |
| — | [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md) | BN vs all-legal CO open: fold JJ–KK, raise AA+ | Polar range 1 |
| — | [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) | BN vs tight CO open (AA+ / QQ·KK+joker): fold JJ–AA | Polar range 2 |
| 4 | [ch04_draw_mixes.md](ch04_draw_mixes.md) | Opener draw mixes + check protection (C done) | Draw mixes / concealment next |
| 5 | [ch05_later_seats.md](ch05_later_seats.md) | CO open climb; **CO bluff after BN open** (§5.2); HJ | Agent B / later |
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
| **CO can open** (BN may or may not) | \((1-p)^6 \cdot p\) — seats 1–6 unable, CO open-legal | **4.9%** | **Signed (v1):** open all legal (JJ **+$1.44** vs pass); no CO sandbag | Ch.5 |

These three sum to the ~22% folded-to-last-two mass.

### Split of “only BN can open” (~3.8%)

After seats 1–7 lack openers and BN has an open-legal hand, BN’s open faces the seven hands behind — none open-legal, but some may still be **2:1 drawing calls** (Ch.2 inventory). Open-legal and 2:1 sets are disjoint. Let \(p_{\mathrm{open}} \approx 0.224\), \(p_{2:1} \approx 18{,}396 / C(53,5) \approx 0.00641\), \(q_{\mathrm{neither}} = 1 - p_{\mathrm{open}} - p_{2:1}\). Independent-seat planning:

| Slice | Formula (planning) | ≈ % of *all* deals | Status | Home chapter |
| --- | --- | ---: | --- | --- |
| BN can open (steal), **nobody** has 2:1 call odds | \(q_{\mathrm{neither}}^{7} \cdot p_{\mathrm{open}}\) | **~3.6%** | **Solved** for open-legal made hands: EV(open) ≈ +$2 ante pot | Ch.3 § folded-to-BN sanity |
| BN can open (steal), **≥1** seat has a good calling hand (2:1 outs) | \(\bigl[(1-p_{\mathrm{open}})^{7} - q_{\mathrm{neither}}^{7}\bigr] \cdot p_{\mathrm{open}}\) | **~0.20%** | **In progress** — inventory + showdown + M2 + non-bluff EV + **Stage C** (always check two pair) done; bluff delta / pair concealment next | Ch.2 + Ch.3–4 |

Unconditional \(P(\ge 1\) of 7 seats is a 2:1 caller\() \approx 4.4\%\). Split on the bug (independent seats): **0.300%** if BN holds it, **4.82%** if not — [button_open_no_sandbagging.md](button_open_no_sandbagging.md). The steal-into-drawer band is much smaller because it also requires seats 1–7 all non-open-legal **and** BN open-legal — still the strategically important laboratory for thin opens.

### How to read “percent of the game solved”

1. **No legal opens (~13.1%)** — solved.
2. **Steal with no drawing caller (~3.6%)** — solved for “always open made jacks+.”
3. **Steal into a 2:1 drawer (~0.21%)** — the active BN laboratory (Ch.2–4). Absolute deal share is small; **strategic importance is large** (this is what makes thin opens lose).
4. **CO live after early six fold (~4.9%)** — **signed (v1, 0% sandbag in 1–6):** open every legal class; do not sandbag two pair+ / CO aces ([cutoff_open_no_sandbagging](cutoff_open_no_sandbagging.md)). **Open chart** vs 1–6 slowplay: bare JJ +EV below ~79%; at 100% only KK+joker is clearly +EV ([cutoff_open_sandbag_v1](cutoff_open_sandbag_v1.md)).
5. **Early six can open (~78%)** — remaining mountain.

Update the **Status** column in this ledger when a chapter’s owner claims a slice solved — prefer editing **only this table** in `INDEX.md`, not copying percentages into chapter bodies.

### Immediate research queue

Living order is in [AGENTS.md](../../AGENTS.md). The threshold lookup is **signed**. Soon work is four CO-open considerations (plan only — do not evaluate in a queue PR). Finish CO vs BN before HJ. Multiway 3:1/4:1 work is toward the end.

| Order | Work | Chapter | Blocks |
| ---: | --- | --- | --- |
| — | **Done.** CO open chart: bare JJ below ~79%; ace until 86/90/96% (JJ/QQ/KK); joker until 93% (JJ) / through 100% (QQ coin-flip, KK +EV). CO does not sandbag. | [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) | Do not restart |
| — | **Done.** BN vs all-legal CO: fold JJ–KK; raise AA+; 2:1 call. No air. | [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md) | Polar \(r=0\%\) |
| — | **Done.** BN vs tight CO (AA+ / QQ·KK+joker): fold JJ–AA; call two pair; raise aces-up / trips | [button_vs_cutoff_tight.md](button_vs_cutoff_tight.md) | Polar \(r\approx 100\%\) |
| — | **Done.** BN vs CO lookup at chart \(r\): AA folds from 79%; two pair calls from 87%. Two flips, not seven. | [../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md) | Do not restart |
| 1 | **Soon:** range vs \(r\) — how much of each BN switch is CO range vs 1–6 trap rate? (CO may not play the chart.) | [../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md) | Plan only in the queue PR |
| 2 | **Soon:** BN bluff-raises (shorts; air with blockers). Fold-JJ–KK is a no-bluff bound. | same ticket | After or with #1; no mix-solve in the queue PR |
| 3 | **Soon:** CO reverse-blockers — Super System count, **negative** (steal, block BN). Sandbag count is positive (want an open to raise). | same ticket | BN still folds JJ–KK on the no-bluff grid |
| 4 | **Soon:** two-pair rank and blockers (stop lumping non-aces-up two pair) | same ticket | CO range is mostly two pair+ |
| 5 | Multi-raise before the draw (CO opens, BN raises) | [Ch.5](ch05_later_seats.md) | After the soon items |
| 6 | Draw and post-draw, BN vs CO | [Ch.5](ch05_later_seats.md) / Ch.3–4 grids | After #5 |
| 7 | HJ: which hands open; ideal sandbag rates with reverse-blockers (Super System “count”) | [Ch.5](ch05_later_seats.md) | After CO vs BN |
| 8 | 3:1 drawing hands after CO open **and** BN call. Inventory only; no multiway tree yet | [Ch.2](ch02_drawing_callers.md) | Toward the end |
| 9 | 3:1 and 4:1 inventory + joker-dealt vs not (CO or BN holds it) | [Ch.2](ch02_drawing_callers.md) | With #8; toward the end |
| — | Exploit leaks (through-line): too little slowplay → HJ may open any legal; too much → late seats fold lowest pairs. Baseline + what moves it + how to respond | all frames | Every lab |
| A | **Done.** BN vs 100% 1–7: JJ −$0.32. 1–6-only: JJ −$0.016; uniform \(r^*\approx 98\%\) | [button_open_sandbag_v1.md](button_open_sandbag_v1.md) | Do not restart |
| B | **Done.** CO 0% sandbag: open all legal (JJ +$1.44) | [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md) | Do not restart |
| B2 | **Done.** CO vs 1–6 100% sandbag flavor pins (input to the open chart) | [cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md) | Do not restart |

### Later (after HJ is started)

| Work | Chapter | Notes |
| --- | --- | --- |
| Strong draws: call vs raise vs mix (combo-weighted EV) | [Ch.2 §2.9](ch02_drawing_callers.md) | CO representation + 19/22-out tail. BN no-sandbag lab is already **call-only** |
| CO bluff after BN open (return-to-actor: CO passed with no legal opener) | [Ch.5 §5.2](ch05_later_seats.md) | Needs §2.9 for value-range shape |
| Pair post-draw EV `d=3` vs `d=2`, then concealment | [Ch.4](ch04_draw_mixes.md) / [../NEXT_STAGE_PAIR_CONCEALMENT.md](../NEXT_STAGE_PAIR_CONCEALMENT.md) | Stage C done; do not redo check mixes |
| BN-vs-2:1 post-draw Nash (Ring 1 / Ring 2) | [button_open_no_sandbagging](button_open_no_sandbagging.md) | Steal-weighted open EV is already ± a dime |
| Trips `d=1` kicker: highest vs non-face / lowest | [Ch.4](ch04_draw_mixes.md) | v1 keeps highest-rank (bug=ace). Detail: [../NEXT_STAGE_OPENER_DRAW_MIXES.md](../NEXT_STAGE_OPENER_DRAW_MIXES.md) |

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
| 2026-09-09 | Threshold lookup **signed** (AA folds from 79%; two pair calls from 87%). Soon: range vs \(r\), BN bluff-raises, CO reverse-blockers, two-pair rank. |
| 2026-09-08 | Queue: next is BN-vs-CO lookup at chart thresholds {79,84,86,87,90,93,96}. HJ reverse-blockers after CO vs BN. 3:1/4:1 draw inventories toward the end. |
| 2026-09-08 | **CO open chart:** if the table slowplays 79%, don't open JJ unless you have an ace; at 86% JJ needs the joker; at 93% pass JJ. QQ: 84% ace / 90% joker (100% coin-flip). KK: 87% ace / 96% joker (100% +EV). CO never sandbags. |
| 2026-09-08 | BN vs **all-legal** CO open: **fold JJ–KK**; value-raise AA / two pair / trips+; 2:1 call. No air. ([button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md)) |
| 2026-09-08 | BN vs **tight** CO open (range 2: AA+ plus QQ/KK+joker): **fold JJ–AA**; call two pair (thin); **raise aces-up / trips**. ([button_vs_cutoff_tight.md](button_vs_cutoff_tight.md)) |
| 2026-09-08 | Next queue: CO slowplay×blockers chart → BN vs CO (call/raise, multi-raise, draw/post-draw) → HJ. Ch.2 §2.9 / concealment after HJ starts. Exploit leaks are a through-line. |
| 2026-09-08 | CO JJ/QQ/KK joker and ace kickers at 100% sandbag: **KK+joker +EV** (+$0.047); **QQ+joker +$0.004 inside 1 SE**; **JJ+joker still −EV** (−$0.075). Ace kickers all −EV. CO KK>QQ>JJ is the ~21% BN-behind street; BN 1–6-only “JJ best” was leaf noise + QQ’s weaker EV_bn (\(z<1.3\)). HJ mixes tabled. |
| 2026-09-08 | CO KK+joker (bug as ace kicker) is **+EV at 100%** 1–6 sandbag (\(p_{\mathrm{raise}}=0.452\), reweighted EV +$0.05). Ace kicker without the bug stays −EV. Binding slowplay rate for JJ/QQ/KK remains **~79%** (JJ). HJ mixes tabled. |
| 2026-09-07 | CO vs 1–6 sandbag rate: JJ/QQ/KK **−EV at 100%** (JJ −$0.26, \(p_{\mathrm{raise}}=0.494\)); 0% leaf reused (+$1.44). Bayes \(r^*\approx 0.79\) (JJ binding). Never-slowplay is the 0% lab only. ([cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md)) |
| 2026-09-07 | 1–6-only sandbag (CO never sandbags): JJ still −EV (−$0.016, \(p_{\mathrm{raise}}=0.496\)); QQ/KK also −EV; lowest +EV BN open is AA (+$0.18 even folding the raise). Q3 flag: revisit HJ aces-sandbag if BN stops opening JJ–KK. |
| 2026-09-07 | `button_open_sandbag_v1`: opening JJ is −EV (−$0.32) vs 100% two-pair+ / HJ-CO aces sandbag + always raise; \(p_{\mathrm{raise}}=0.573\) (n=40k, seed 20260907). No-raise leaf reused §3.4 pair_J d=3 + 6.9% 2:1 call |
| 2026-09-07 | CO open/pass (0% sandbag in 1–6): open all legal, JJ **+$1.44** vs pass; do not sandbag AA / two pair ([cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md)) |
| 2026-09-07 | Sandbag-set v1 aces: **HJ+CO**, not LJ+CO (plan-only correction; method unchanged) |
| 2026-09-07 | Parallel next: BN 100% sandbag JJ probe + CO open/pass. BN-vs-2:1 Nash tabled. Ticket [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md) |
| 2026-09-07 | Average BN open ≈ +$1.94: steal +$2 on ~95%, §3.4 called street +$0.80 vs pass on ~5% (leak ~6¢ vs always-steal) |
| 2026-09-07 | BN no-sandbag lab: 2:1 hands call, do not raise (16/48 fails 4/10 if BN continues). Open/pass leftover is not §2.9 |
| 2026-09-07 | BN joker split: P(any of 1–7 is 2:1) = 0.300% / 4.82% (has bug / not). No legal BN pass in this frame |
| 2026-09-07 | Frames in INDEX; Ring / Line / Stage aliases in [button_open_no_sandbagging.md](button_open_no_sandbagging.md). Pre-C merge helper is `MERGE_TWO_PAIR_TRIPS` |
| 2026-09-07 | Land pre-C bluff library + leftover-fold pin (Ch.3 §3.6; β* = 0.0155, node EV −1.88). Stage C Ring 1 still open |
| 2026-09-02 | Cap raise node re-filtered under Stage C: P(node)=0.0903; Line 1 flush folds / Line 2 flush calls vs no-air flush+ |
| 2026-09-02 | Stage C re-run: always check two pair under `tp1_tr2_q1` / `tp1_tr1_q1` |
| 2026-09-02 | Later queue: trips `d=1` kicker rank (highest vs non-face) after Stage C |
| 2026-09-01 | Non-bluff EV by BN class × d vs 2:1 caller (Ch.3 §3.4); bluff delta next |
| 2026-09-01 | Initial monolithic `RESEARCH_PAPER.md` |
| 2026-09-01 | Split into `docs/research/` chapters; seats 1–8 + hold’em names; granular solve-progress ledger; parallel-agent notes |
| 2026-09-01 | Document next queue: Ch.2 call/raise/mix; Ch.5 CO bluff after BN open |
| 2026-09-01 | Pin §5.2 return-to-actor (CO passed with no legal opener); clarify bluff = call/raise with less than strong draws |
| 2026-09-02 | Post-draw bluff 3-bet Ring 1 handoff (flush indifference on the cap node) |
