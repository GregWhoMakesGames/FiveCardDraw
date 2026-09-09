# Frame: button vs cutoff, all-legal CO open (range 1)

Slug: **`button_vs_cutoff_all_legal`**. Parent: [INDEX.md](INDEX.md) research frames.
CO open pin: [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md).

Seats 1–6 unable. CO (seat 7) opens **every legal hand** (jacks-or-better) and
does **not** sandbag. BN (seat 8) is next. This is **range 1** only — the
signed `cutoff_open_no_sandbagging` range. A tight CO range (AA+ / QQ–KK with
a joker) is a different agent.

**How to point at this work:** `evaluate button_vs_cutoff_all_legal`

Code: `src/fivecarddraw/validation/button_vs_cutoff.py`.
CLI: `python -m fivecarddraw.validation.button_vs_cutoff` (or
`analyze-button-vs-cutoff`).
Fixture: `tests/fixtures/validation/button_vs_cutoff_all_legal.json`.
Seed `20260908`, n_hu=4k, n_2to1=2k.

Out of scope (do not start here): multi-raise Nash, live draw solver,
post-draw Nash, CO open/slowplay product chart.

## Product answers

1. **No fold equity vs air.** CO’s range is 100% jacks+. There is no junk to
   fold out. A BN raise is a **value / protection** question vs jacks+, not a
   bluff. The “CO folds junk” raise bound is identical to “CO always
   continues,” because there is no junk. \(p_{\mathrm{CO\ fold\ air}}=0\).
2. **Fold JJ, QQ, KK.** Honest $6 call is −EV vs fold (JJ **−$2.29**, QQ
   **−$1.71**, KK **−$1.10**). Raise-checkdown is also ≤ 0.
3. **Value-raise AA, two pair, trips+.** Checkdown raise beats checkdown call
   (P(win) ≳ ½) with CO always continuing. AA / plain two pair are **thin**
   (~+$0.18 of raise vs call on checkdown). Aces-up and trips+ are fat.
4. **2:1 drawing hands call, do not raise.** Honest call **+$1.44**. Raise has
   no air to fold and loses on checkdown (P(win) ≈ 0.35; 16/48 into a $10 pot
   still needs ~40%). Same qualitative line as the BN-open lab, for a
   different reason: there the opener was 100% jacks+; **here the opener is
   also 100% jacks+**.

## Accounting (BN’s decision)

Antes are already in ($2). Fold = **0** relative to this node (CO steals the
antes if BN folds). CO’s open makes the pot $4; BN calls $2 (pot $6 into the
draw) or raises to $4 (CO always calls → pot $10).

| Line | Pot into draw | BN invested | EV vs fold |
| --- | ---: | ---: | --- |
| Fold | — | $0 more | **0** |
| Call | $6 | $2 | \(\mathrm{EV}_{\mathrm{street}}-2\) (honest locked leaf) |
| Raise, CO always continues | $10 | $4 | checkdown \(10p+5t-4\) |

Call vs fold uses the **honest** $6 street (pairs pay off CO two pair+; made
hands stab). Raise vs call uses **matching checkdowns** so trips+ is not
compared as “honest $6 extraction vs $10 showdown.” Bug = ace / fill, not a
third rank: KK+joker is `pair_K`.

Locked draws: `tp1_tr2_q1` (pairs \(d=3\), two pair \(d=1\), trips \(d=2\),
quads \(d=1\)). Draw order: CO first, BN last. Honest policy =
`lead=never|stab=AA|raise=never` (same HU cells as the CO 0% lab).

## Chart (n=4000 made / 2000 2:1, seed 20260908)

SE is the SE of the mean. Fold = 0 exactly.

| BN class | Action | EV fold | EV call honest (SE) | EV call-cd | EV raise-cd (SE) | P(win) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pair_J | **fold** | 0 | −2.294 (0.078) | −0.785 | −1.975 (0.064) | 0.203 |
| pair_Q | **fold** | 0 | −1.713 (0.082) | −0.263 | −1.105 (0.072) | 0.290 |
| pair_K | **fold** | 0 | −1.099 (0.087) | **+0.291** | −0.183 (0.077) | 0.382 |
| pair_A | **raise** | 0 | +0.275 (0.094) | +1.272 | +1.454 (0.079) | 0.545 |
| two_pair | **raise** | 0 | +0.724 (0.101) | +1.293 | +1.488 (0.079) | 0.549 |
| two_pair_aces_up | **raise** | 0 | +3.246 (0.093) | +2.455 | +3.425 (0.069) | 0.743 |
| trips+ | **raise** | 0 | +5.464 (0.091) | +3.138 | +4.564 (0.055) | 0.856 |
| 2:1 draws | **call** | 0 | +1.436 (0.131) | +0.094 | −0.510 (0.107) | 0.349 |

`trips+` = trips / trips_K / trips_A / straight+ (combo-weighted). `two_pair`
is the non-aces-up class (same split as the CO open lab).

## Sanity vs the CO 0% HU cell

[cutoff_open_no_sandbagging](cutoff_open_no_sandbagging.md) pins CO JJ vs BN’s
**legal range**: EV_street(CO) = $1.48, P(CO wins) ≈ 0.20. The reverse cell
here — BN JJ vs CO’s legal range — has P(BN wins) = **0.203**. Same street,
roles flipped; draw-order edge is small at this n. We still resimulate
BN-class × CO-range rather than inverting a CO-class × BN-range row.

## Where it is close / later work

Nothing in the fixture is inside 2 SE of a decision threshold, but three
places still want the raise tree / Stage C street:

1. **KK (and QQ) vs a checking two-pair street.** Checkdown call for KK is
   **+$0.29**; honest call is **−$1.10** because CO value-bets two pair+ and
   BN’s pair pays off. Stage C always *checks* two pair. That would move KK
   toward a call. Do not treat KK-fold as GTO vs a checking range.
2. **AA / plain two pair value-raise is thin.** Raise-cd − call-cd ≈ +$0.18
   (≈ 6 SE at n=4k, so the *sign* is not noise) but a raise tree where CO
   can fold JJ or 3-bet trips+ can eat that dime.
3. **2:1 call-cd is only +$0.09.** Honest call prints because made draws
   extract post-draw. A CO that continues more aggressively post-draw could
   shrink that. Raise stays wrong on this bound (no air; P(win) 0.35 < 0.40
   into $10).

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Range 1** | Evaluate BN vs CO opening every legal hand | This file. No sandbag. No tight range. |
| **No air** | Evaluate a BN raise’s fold equity vs this CO range | Identically 0; raise is value/protection |

Range 2 (tight CO) is **not** this frame.
