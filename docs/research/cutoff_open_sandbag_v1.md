# Frame: cutoff open vs sandbag v1 (seats 1–6)

Slug: **`cutoff_open_sandbag_v1`**. Parent: [INDEX.md](INDEX.md) research frames.
0% lab: [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md).
BN analog: [button_open_sandbag_v1.md](button_open_sandbag_v1.md) world `seats_1_6_only`.
Ticket: [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md).

CO (seat 7) acts after seats 1–6 passed. BN has **not** acted. Seats **1–6**
sandbag the v1 set at rate \(r\) and **always raise** a CO open; **CO never
sandbags** (CO is the opener). Contrast: the 0% lab (nobody in 1–6 has an
open-legal) where opening every legal class was +EV.

**How to point at this work:** `evaluate cutoff_open_sandbag_v1`

Code: `src/fivecarddraw/validation/cutoff_open_sandbag.py` (world
`co_vs_seats_1_6` in `sandbag_v1.py`); chart:
`src/fivecarddraw/validation/cutoff_open_chart.py`. Fixture:
`tests/fixtures/validation/cutoff_open_sandbag_v1.json` (`open_chart`).
CLI: `python -m fivecarddraw.validation.cutoff_open_sandbag --write-chart`
(reuses locked 0%/100% pins; `--write-fixture` / `--write-blockers` are
the signed endpoints — do not re-run them as the product).

## Opening chart (play this)

**CO never sandbags.** Open two pair+, boats, and CO aces. The chart below
is only for **JJ / QQ / KK** vs seats 1–6 slowplay rate \(r\) (v1 set:
1–5 two pair+; HJ two pair+ **and** aces; they always raise; CO folds
the raise for −$2). Bug = ace kicker, **not** trips.

Playable integer bands (Bayes \(r^*\) rounded to 1%). Ace = physical ace
kicker **or** the joker; “joker only” means the bug specifically.

| Slowplay \(r\) | JJ | QQ | KK |
| --- | --- | --- | --- |
| \(r < 79\%\) | open | open | open |
| 79–84% | ace or joker | open | open |
| 84–86% | ace or joker | ace or joker | open |
| 86–87% | joker only | ace or joker | open |
| 87–90% | joker only | ace or joker | ace or joker |
| 90–93% | joker only | joker only | ace or joker |
| 93–96% | **pass** | joker only | ace or joker |
| \(r \ge 96\%\) | **pass** | joker only | joker only |

Voice of the thresholds:

- If players are slowplaying **79%** of the time, don't open **JJ** unless you have an ace.
- If players are slowplaying **86%**, don't open JJ at all unless you have a joker.
- If players are slowplaying **93%** or more, pass JJ even with the joker.
- If players are slowplaying **84%** of the time, don't open **QQ** unless you have an ace.
- If players are slowplaying **90%**, don't open QQ at all unless you have a joker. At 100%, QQ+joker is +EV inside 1 SE (coin-flip, not a blowout).
- If players are slowplaying **87%** of the time, don't open **KK** unless you have an ace.
- If players are slowplaying **96%**, don't open KK at all unless you have a joker. At 100%, KK+joker stays +EV (+$0.047).

Never-slowplay (open every legal, including bare JJ) remains the **0% lab
only**. At table \(r\) above ~79%, that pin does not survive for JJ.

Exact Bayes \(r^*\) (calibrated independent-seat curve; class average =
40k pin, ace/joker = 10k + reweighted \(L\); seed `20260907`):

| Flavor | \(L\) | \(p(1)\) | EV(100%) | \(r^*\) | playable |
| --- | ---: | ---: | ---: | ---: | ---: |
| JJ class avg | +$1.435 | 0.4938 | −$0.261 | **0.787** | 79% |
| JJ + ace | +$1.460 | 0.4665 | −$0.154 | 0.864 | 86% |
| JJ + joker | +$1.521 | 0.4534 | −$0.075 | 0.931 | 93% |
| QQ class avg | +$1.551 | 0.4928 | −$0.199 | 0.840 | 84% |
| QQ + ace | +$1.560 | 0.4701 | −$0.114 | 0.902 | 90% |
| QQ + joker | +$1.614 | 0.4455 | +$0.004 | 1.003 | through 100% |
| KK class avg | +$1.678 | 0.5012 | −$0.166 | 0.872 | 87% |
| KK + ace | +$1.691 | 0.4718 | −$0.050 | 0.958 | 96% |
| KK + joker | +$1.737 | 0.4523 | **+$0.047** | 1.042 | through 100% |

Grid: \(r\) every 5% plus the integer thresholds. Sign change for bare JJ
sits between 78% (+$0.010) and 79% (−$0.004). Interior seeded MC at
\(r=0.5\) (n=400) sits between 0 and \(p(1)\); the chart itself is the
calibrated Bayes curve, not a new 40k run.

## Product answers (0% / 100% endpoints)

| Class | \(L\) (0% leaf) | \(p_{\mathrm{raise}}\) (100%) | EV(100%) | \(p^*\) | \(r\) that flips (Bayes) | linear \(p^*/p(1)\) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pair_J | **+$1.435** | **0.4938** (SE 0.00250) | **−$0.261** | 0.4178 | **0.787** | 0.846 |
| pair_Q | +$1.551 | 0.4928 (SE 0.00250) | −$0.199 | 0.4368 | 0.840 | 0.886 |
| pair_K | +$1.678 | 0.5012 (SE 0.00250) | −$0.166 | 0.4562 | 0.872 | 0.910 |

1. **JJ at 100% sandbag is −EV** vs pass = 0 (fold-to-raise bound).
2. **JJ at 0% sandbag is +EV** — reused, not rebuilt: **+$1.44** from
   `cutoff_open_no_sandbagging` (fixture `ev_open=1.43502`).
3. Break-even \(p^*=L/(L+2)\approx 0.418\). Calibrated Bayes \(r^*\approx\mathbf{0.79}\)
   (linear \(p^*/p(1)\approx 0.85\)). Same sign for QQ and KK; **binding class is
   JJ** (lowest \(r^*\)).

**What this does to “CO opens every legal / never slowplays.”** That pin is
**lab-dependent**. It is the 0% sandbag laboratory (seats 1–6 have no
open-legal). It is **not** a claim that opening JJ stays +EV when 1–6 bury
the v1 set and always raise. At 100% that open is −$0.26 vs pass; CO would
rather pass JJ than open-and-fold. This PR does **not** retune CO’s own
slowplay of two pair+ / aces — that was a different question in the 0% lab
(still: do not sandbag those on CO when 1–6 cannot open).

**CO analog of the button’s 98%.** BN’s uniform \(r\lesssim 98\%\) was the
rate that made **every** legal button open +EV (QQ/KK bound). Here **JJ
binds**: Bayes \(r^*\approx\mathbf{79\%}\) (linear 85%). QQ 84% / KK 87%.
If seats 1–6 slowplay below ~79%, opening any of JJ/QQ/KK from CO is +EV
on this fold-to-raise mix.

Hijack slowplay mixes are **tabled** (not ready to pin an ideal \(r_{\mathrm{HJ}}\)).

Q3 (flag only): if CO stops opening JJ–KK, HJ’s v1 aces-sandbag pin is the
same inconsistency the BN 1–6-only walk flagged. Do not iterate the set here.

## Singleton blockers (JJ/QQ/KK + joker, ace kicker)

The bug is an **ace** (or a straight/flush fill), **not** a duplicate of
the pair rank. **pair_X + joker** = two physical cards of that rank + bug
as ace kicker, still `pair_X`. One face card + bug is ace-high (not an
opener). A physical ace kicker is the same ace-rank blocker without
removing the bug from the deck. Matched kickers: two of the pair rank +
`9s 7h`, fifth card \(4c\) / `Bu` / `As`.

Exact remaining \(C(48,5)=1{,}712{,}304\):

| Remaining | JJ | JJ+joker | JJ+ace | QQ | QQ+joker | QQ+ace | KK | KK+joker | KK+ace |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| two pair+ | 143,533 | 132,590 | 140,111 | 144,057 | 132,877 | 140,779 | 144,753 | **133,259** | 141,667 |
| pair_A | 98,266 | **64,548** | 63,009 | 98,266 | **64,548** | 63,009 | 98,266 | **64,548** | 63,009 |
| aces-up | 22,730 | **14,688** | 14,688 | 22,730 | **14,688** | 14,688 | 22,730 | **14,688** | 14,688 |
| straight | 11,741 | 6,281 | 12,482 | 12,265 | 6,568 | 13,150 | 12,961 | **6,950** | 14,038 |
| HJ set | 241,799 | 197,138 | 203,120 | 242,323 | 197,425 | 203,788 | 243,019 | **197,807** | 204,676 |

AA / aces-up cuts are **rank-independent** on these kickers (joker-as-ace
and a singleton ace remove the same aces). Two pair+ and straights still
move with the pair rank. The joker also cuts 2:1 almost to zero (almost
all 18,396 2:1 combos hold the bug). A singleton ace matches the AA /
aces-up cut but leaves 2:1 and most straights in the deck.

Fold-to-raise mix at **100%** 1–6 sandbag (n=10,000 flavor MC, n_leaf=8,000
behind-probs, seed `20260907`). Class-average rows are the locked 40k pins
(not re-run). \(L_{\mathrm{rew}}\) reweights steal / 2:1 / BN mix; street
EVs stay that class’s 0% cells. \(\mathrm{SE}(\mathrm{EV})\approx\mathrm{SE}(p)\times(L+2)\).

| Flavor | \(p_{\mathrm{raise}}\) (SE) | \(L\) avg | \(L_{\mathrm{rew}}\) | EV(100%) rew | vs 0 | \(p^*_{\mathrm{rew}}\) | \(r^*_{\mathrm{rew}}\) |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| pair_J class avg | 0.4938 (0.00250) | +$1.435 | — | **−$0.261** | −EV | 0.418 | 0.787 |
| JJ + joker | **0.4534** (0.00498) | +$1.435 | +$1.521 | **−$0.075** | −EV (~4 SE) | 0.432 | 0.931 |
| JJ + ace | 0.4665 (0.00499) | +$1.435 | +$1.460 | **−$0.154** | −EV | 0.422 | 0.864 |
| pair_Q class avg | 0.4928 (0.00250) | +$1.551 | — | **−$0.199** | −EV | 0.437 | 0.840 |
| QQ + joker | **0.4455** (0.00497) | +$1.551 | +$1.614 | **+$0.004** | **+EV inside 1 SE** (\(\mathrm{SE}\approx\$0.018\)) | 0.447 | 1.003 |
| QQ + ace | 0.4701 (0.00499) | +$1.551 | +$1.560 | **−$0.114** | −EV | 0.438 | 0.902 |
| pair_K class avg | 0.5012 (0.00250) | +$1.678 | — | **−$0.166** | −EV | 0.456 | 0.872 |
| KK + joker | **0.4523** (0.00498) | +$1.678 | +$1.737 | **+$0.047** | **+EV** | 0.465 | 1.042 |
| KK + ace | 0.4718 (0.00499) | +$1.678 | +$1.691 | **−$0.050** | −EV | 0.458 | 0.958 |

KK+joker conservative (average \(L\)) is still **+$0.014**, inside ~1 SE
of zero — same pin as before. QQ+joker reweighted is a coin-flip through
zero; do not treat it as a blowout. JJ+joker stays **−EV** even after the
steal/2:1 reweight (\(p_{\mathrm{raise}}=0.453\) still above \(p^*\approx 0.432\)).

**User expectation vs pins.** “Joker in hand → any of JJ/QQ/KK is +EV at
100%” **does not hold**: only **KK+joker** is clearly +EV; **QQ+joker** is
+EV inside 1 SE; **JJ+joker** is −$0.075. “Ace kicker → all three approach
break-even” is **directionally true vs the class average** (each ace-kicker
EV is closer to 0 than the 40k row) but **none** is inside 1 SE of zero.
KK+ace (−$0.05) is the closest; JJ+ace (−$0.15) is still a clear fold vs
pass. Ace kickers never flip the 100% mix: they block AA / aces-up like
the bug-as-ace, but they do not remove 2:1, so \(p_{\mathrm{raise}}\) stays
above each class’s \(p^*\).

CLI: `python -m fivecarddraw.validation.cutoff_open_sandbag --write-blockers`.

### Why CO ranks KK > QQ > JJ while BN 1–6-only looked reversed

Decompose \(\Delta\mathrm{EV}=(1-p)L+p(-2)\) into a leaf piece (hold \(p\))
and a \(p_{\mathrm{raise}}\) piece (hold \(L\)). No new HU grid.

**CO** 0% leaves already strictly increase JJ < QQ < KK
(`cutoff_open_summary.json`): +$1.435 / +$1.551 / +$1.678. Steal rates are
similar (~75%); 2:1 is a small slice (~4%). The gap is **BN still to act**
(\(P(\mathrm{BN\ legal})\approx 21\%\)). Higher pair wins more of the HU vs
BN’s jacks+ range:

| CO class | P(steal) | P(vs 2:1) | P(BN legal) | vs_bn_legal P(win) | EV_street vs BN | \(L\) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pair_J | 0.755 | 0.035 | 0.210 | **0.203** | **+$1.48** | +$1.435 |
| pair_Q | 0.755 | 0.040 | 0.205 | **0.281** | **+$1.99** | +$1.551 |
| pair_K | 0.745 | 0.043 | 0.212 | **0.372** | **+$2.68** | +$1.678 |

At 100% sandbag the same order survives. KK vs JJ: leaf piece
\(+\$0.123\) (hold JJ’s \(p\)) vs \(p_{\mathrm{raise}}\) piece **−$0.027**
(KK’s slightly *higher* raise rate). Leaf dominates; \(p_{\mathrm{raise}}\)
actually favors JJ. Fixture: `blockers.ranking_co_vs_bn`.

**Button** 1–6-only leaves were almost identical (~+$1.93) because
folded-to-BN is steal-dominated (reused 6.9% 2:1 mix, not a 21% BN-behind
street). Pins (`sandbag_v1_seats_1_6_only.json` Q2): JJ leaf +$1.936
(\(\mathrm{EV}_{bn}=+3.0755\)), QQ **+$1.928** (\(\mathrm{EV}_{bn}=+2.9615\),
the weaker locked cell), KK +$1.937. Raise rates 0.4959 / 0.4987 / 0.5003
sit within \(z<1.3\) of each other (QQ−JJ \(z\approx 0.78\), KK−JJ
\(z\approx 1.24\)). That ranking was **MC noise + QQ’s weaker \(\mathrm{EV}_{bn}\)**
— not a published JJ > QQ > KK theorem. See
[button_open_sandbag_v1.md](button_open_sandbag_v1.md) 1–6-only Q2.

## Sandbag-set v1 in this world

| Seats | 100% pass, then always raise CO |
| --- | --- |
| 1–5 | Two pair or better (LJ still opens AA) |
| 6 (HJ) | Two pair+ **and** pair_A |
| 7 (CO) | **Does not sandbag** — this is the opener |
| 8 (BN) | **Not in \(p_{\mathrm{raise}}\)** — BN’s calls/opens vs a CO open already sit in \(L\) |

Voluntary open = jacks-or-better minus that seat’s sandbag-set. Given 1–6
passed, they have no voluntary opener.

## How EV is determined (no live draw / post-draw Nash)

There is **no** simulation of draw choice or post-draw betting in this mix.
No CO vs BN vs sandbagger tree. Pieces:

| Branch | What is true | CO JJ/QQ/KK payoff |
| --- | --- | --- |
| **Raise** | ≥1 of 1–6 has the sandbag-set | They always raise; CO **folds** → **−$2** |
| **No-raise** | Nobody in 1–6 has the sandbag-set either ⇒ **no open-legal in 1–6** | Same as 0% CO open: leaf \(L\) |

Accounting:

\[\mathrm{EV}(\mathrm{open})=(1-p_{\mathrm{raise}})\,L + p_{\mathrm{raise}}\,(-2),\qquad \mathrm{EV}(\mathrm{pass})=0.\]

**No-raise leaf \(L\)** is the locked [cutoff_open_no_sandbagging](cutoff_open_no_sandbagging.md)
EV(open) for that class. Inside that 0% number (already computed; **do not
rebuild**):

- **Steal** when the pot is taken down uncontested: **+$2** (antes).
- **2:1 drawing callers:** call, don’t raise. Street EV when called is a
  **locked** combo-weighted number from the post-draw **non-bluff** grid
  (pairs \(d=3\) vs the 2:1 mix) — Monte Carlo showdown after **fixed**
  draws, not Nash (`postdraw_nonbluff_ev_summary.json` / §3.4), with the CO
  lab’s draw-order split (1–6 caller first; BN-as-2:1 caller, CO first).
- **BN still to act:** in that lab BN opens every legal if CO passes and
  **calls** every legal if CO opens. The HU CO-vs-BN-legal street is a locked
  honest-policy number (pairs \(d=3\)), not a sandbagger street.
- Fold to a raise after opening: **−$2** (this frame’s raise branch only).

Do **not** claim a full CO vs BN vs sandbagger post-draw tree. Do **not** mix
the BN-style leaf \(2+p_{\mathrm{call}}(\mathrm{EV}_{bn}-4)\) here: that leaf
is folded-to-BN with no legal in 1–7. CO’s \(L\) includes BN behind
(\(P(\mathrm{BN\ legal})\approx 21\%\)), which is why JJ’s 0% open is +$1.44
rather than BN’s +$1.94.

## \(P(\mathrm{raise}\mid 1\text{–}6\text{ passed, CO holds pair}_X)\)

Predicates reuse `classify_opener`. Inventory from showdown-matrix combo
counts (same as the 1–6-only writeup):

| Set | Combos | Unconditional \(p\) |
| --- | ---: | ---: |
| Not open-legal \(p_j\) | 2,226,804 | 0.7760 |
| Two pair+ \(p_s^{1-5}\) | 235,697 | 0.0821 |
| HJ sandbag-set \(p_s^{\mathrm{HJ}}\) | 373,601 | 0.1302 |

**Independent-seat planning** (no CO cards), \(r=1\):

\[
p(1)=1-\Bigl(\frac{p_j}{p_j+p_s^{1-5}}\Bigr)^{5}\frac{p_j}{p_j+p_s^{\mathrm{HJ}}}=\mathbf{0.4822}.
\]

Same closed form as BN `seats_1_6_only` (CO contributes \(P(\mathrm{neither}\mid\mathrm{passed})=1\)).
CO pair_J blocked (2,000 × 50, seed `20260907`): **0.4842**. Jacks block
voluntary pair_J more than two pair+ / aces.

**Seeded 8-way deal MC** (condition CO `pair_X`, condition 1–6 have no
voluntary opener, **BN unrestricted**, measure ≥1 sandbag-set in 1–6):

| Pin | pair_J | pair_Q | pair_K |
| --- | ---: | ---: | ---: |
| \(n\) (conditioned) | 40,000 | 40,000 | 40,000 |
| seed | 20260907 | 20260907 | 20260907 |
| CO-class deals before 1–6 filter | 87,859 | 88,461 | 87,902 |
| Full 53-card shuffles | 2,801,845 | 2,819,973 | 2,837,802 |
| \(n_{\mathrm{raise}}\) | 19,751 | 19,711 | 20,048 |
| \(p_{\mathrm{raise}}\) | **0.493775** | **0.492775** | **0.501200** |
| SE | 0.00250 | 0.00250 | 0.00250 |
| \(P(\)CO holds the bug \(\mid\) cond.\()\) | 0.062 | 0.061 | 0.063 |

Histogram of sandbag-set seats given passed (JJ): 0 → 20,249; 1 → 14,612;
2 → 4,400; 3+ → 739.

The joint is a bit *higher* than the independent product (κ = \(p_{\mathrm{MC}}(1)/p_{\mathrm{ind}}(1)\)
≈ **1.024** for JJ): one seat’s junk leaves the rest richer in two pair+.
BN is random here (not filtered to no open-legal), unlike the folded-to-BN
lab — that is why this \(p_{\mathrm{raise}}\) is **not** copied from BN
1–6-only’s 0.496.

## Rate mix \(p(r)\) and break-even \(r^*\)

Independent seats at sandbag frequency \(r\):

\[
p(r)=1-\prod_{i\in\{1..5\}}\frac{p_j}{p_j+r\,p_s^{1-5}}\cdot\frac{p_j}{p_j+r\,p_s^{\mathrm{HJ}}}.
\]

Calibrate to the deal-MC at \(r=1\) with constant ratio
\(p_{\mathrm{cal}}(r)=\kappa\,p_{\mathrm{ind}}(r)\), \(\kappa=p_{\mathrm{MC}}(1)/p_{\mathrm{ind}}(1)\).
Invert \(p_{\mathrm{cal}}(r^*)=p^*\). Also report naive linear
\(r_{\mathrm{lin}}=p^*/p_{\mathrm{MC}}(1)\). Bayes sits **below** linear
(near \(r=1\) the curve is concave: a given drop in \(p\) needs a larger drop
in \(r\) than the chord from 0). Binding class = **pair_J**.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **100% raise** | Evaluate CO JJ/QQ/KK vs always-raise 1–6 sandbaggers | Folded-to-CO posterior includes sandbag-set; they raise; CO folds for −$2 |
| **No-raise leaf \(L\)** | Reuse 0% CO open | No sandbag-set in 1–6 ⇒ same steal + 2:1 + BN-behind mix |
| **Never slowplay** | 0% lab pin | Open every legal when 1–6 have **no** open-legal; **not** this 100% mix |
