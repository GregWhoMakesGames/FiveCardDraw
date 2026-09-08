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
`co_vs_seats_1_6` in `sandbag_v1.py`). Fixture:
`tests/fixtures/validation/cutoff_open_sandbag_v1.json`. CLI:
`python -m fivecarddraw.validation.cutoff_open_sandbag --write-fixture`
(or `analyze-cutoff-open-sandbag`).

## Product answers

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

## Singleton blockers (KK + joker, ace kicker)

The bug is an **ace** (or a straight/flush fill), not a duplicate king.
**KK with a joker** = two physical kings + bug as ace kicker, still
`pair_K`. One king + bug is ace-high (not an opener). A physical ace
kicker is the same rank-blocker without removing the bug from the deck.

Exact remaining \(C(48,5)=1{,}712{,}304\) with matched kickers
(`Kh Kd 9s 7h` + \(4c\) / `Bu` / `As`):

| Remaining bucket | Two kings | KK + joker | KK + ace |
| --- | ---: | ---: | ---: |
| two pair+ | 144,753 | **133,259** | 141,667 |
| pair_A | 98,266 | **64,548** | 63,009 |
| aces-up | 22,730 | **14,688** | 14,688 |
| straight | 12,961 | **6,950** | 14,038 |
| HJ set (two pair+ and AA) | 243,019 | **197,807** | 204,676 |

The joker cuts 2:1 almost to zero (almost all 18,396 2:1 combos hold the
bug) **and** cuts monsters / AA / aces-up. A singleton ace matches the
AA / aces-up cut but leaves 2:1 and most straights in the deck.

Fold-to-raise mix at **100%** 1–6 sandbag (n=10,000, seed `20260907`):

| Flavor | \(p_{\mathrm{raise}}\) (SE) | Leaf \(L\) | EV(100%) |
| --- | ---: | ---: | ---: |
| pair_K class average | 0.5012 (0.00250) | +$1.678 | **−$0.166** |
| KK + joker, average \(L\) | **0.4523** (0.00498) | +$1.678 | **+$0.014** |
| KK + joker, steal/2:1 reweight | 0.4523 (0.00498) | **+$1.737** | **+$0.047** |
| KK + ace kicker, average \(L\) | 0.4718 (0.00499) | +$1.678 | **−$0.057** |
| KK + ace kicker, reweight | 0.4718 (0.00499) | +$1.691 | **−$0.050** |

**Yes: opening KK with the joker is +EV at 100% slowplay in front**, on
the reweighted 0% leaf (steal ≈ 80%, \(p_{\mathrm{vs\ 2:1}}\approx 0.24\%\)
vs the class-average 4.3% / 74.5% steal). The conservative class-average
leaf is only **+$0.014**, inside ~1 SE of zero (\(\mathrm{SE}(p)\times(L+2)\approx \$0.018\))
— do not treat that bound as a blowout. \(r^*>1\): even 100% sandbag stays
+EV once the bug is in the hand.

A **physical ace kicker without the joker does not flip** the 100% mix
(still −EV). It blocks AA / aces-up like the bug-as-ace, but it does not
remove 2:1 or as many two-pair+ combos, so \(p_{\mathrm{raise}}=0.472\)
stays above KK’s \(p^*\approx 0.456\).

CLI: `python -m fivecarddraw.validation.cutoff_open_sandbag --write-blockers`.

## Sandbag-set v1 in this world

| Seats | 100% pass, then always raise CO |
| --- | --- |
| 1–5 | Two pair or better |
| 6 (HJ) | Two pair+ **and** pair_A |
| 7 (CO) | **Does not sandbag** — this is the opener |
| 5 (LJ) | Two pair+ only (still opens AA) |
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
