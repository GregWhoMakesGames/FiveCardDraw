# Frame: button vs cutoff, range vs trap rate

Slug: **`button_vs_cutoff_range_vs_r`**. Parent: [INDEX.md](INDEX.md). Ticket
item 1: [../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](../NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md).
Signed lookup (do not restart):
[../NEXT_STAGE_BN_VS_CO_GRID.md](../NEXT_STAGE_BN_VS_CO_GRID.md). Polar
endpoints: [button_vs_cutoff_all_legal.md](button_vs_cutoff_all_legal.md),
[button_vs_cutoff_tight.md](button_vs_cutoff_tight.md). Chart:
[cutoff_open_sandbag_v1.md](cutoff_open_sandbag_v1.md). Interior HU rows:
[button_vs_cutoff_r79.md](button_vs_cutoff_r79.md),
[button_vs_cutoff_r86.md](button_vs_cutoff_r86.md),
[button_vs_cutoff_r87.md](button_vs_cutoff_r87.md).

**How to point at this work:** `evaluate button_vs_cutoff_range_vs_r`

Code: `src/fivecarddraw/validation/button_vs_cutoff_range_vs_r.py`.
CLI: `python -m fivecarddraw.validation.button_vs_cutoff_range_vs_r` (or
`analyze-button-vs-cutoff-range-vs-r`).
Fixture: `tests/fixtures/validation/button_vs_cutoff_range_vs_r.json`.

This frame **reuses locked BN-vs-CO leaves**. It does not rebuild post-draw
Nash, restart the open chart, restart the polar labs, or mix-solve a raise
tree. CO never sandbags as the opener. The joker is an ace kicker, not trips.

## Product answers

The signed lookup couples table slowplay \(r\) to the *ideal* CO chart range,
then reads BN’s HU action vs that range. Real CO may open **wider** than \(r\)
allows or **tighter** despite a low sandbag rate (especially under 79%, where
the chart still says open every legal). BN’s node has two knobs:

1. **CO range** — which jacks+ combos actually opened.
2. **Trap rate** — \(P(\)seats 1–6 still have a slowplay trap and raise the
   open\()\), the same calibrated \(p(r)\) curve as the CO chart (world
   `co_vs_seats_1_6`, JJ class-average kappa).

Hold one fixed, vary the other.

| Switch | Range-only (chart range, trap \(=0\)) | Trap-only (wrong range, table \(r\)) | Who flips it? |
| --- | --- | --- | --- |
| **AA** raise→fold at 79% | r79 CO, trap 0: **fold** | all-legal CO, trap 79%: **raise** | **CO range** |
| **Two pair** raise→call at 87% | r87 CO, trap 0: **call** | r86 CO, trap 87%: **raise** | **CO range** |

**Headline.** Both published switches are **CO range**, not 1–6 trap rate.
Cutting bare JJ (r79 chart) is enough to fold AA even with nobody trapping.
KK needing a blocker (r87 chart) is enough to take two pair off the value-raise
even with nobody trapping. A too-loose CO at a high table \(r\) still gets
**raised** by AA / two pair on the no-multi-raise bound. A too-tight CO at
\(r=0\) already looks like the tight polar (fold AA, call two pair). **No
lookup row.**

## Method (locked leaves)

Signed BN-vs-CO labs are HU vs the constructed range after seats 1–6 passed.
Trap weight at that node is **0**. Range-only cells *are* those fixtures.

Trap mix, primary product (no multi-raise):

\[
\mathrm{EV}_{\mathrm{call}}(\mathrm{range},r)=(1-p(r))\,\mathrm{EV}_{\mathrm{call}}^{\mathrm{HU}}(\mathrm{range})+p(r)\,\mathrm{trap\_call}.
\]

The raise line stays the HU \( \$10 \) checkdown vs CO. A 1–6 3-bet after BN
raises is the later multi-raise ticket, not this mix. \(P(\mathrm{win})\) stays
HU vs CO. Action uses the tight polar’s `recommend_action` (value-raise iff
favorite and raise-cd +EV).

\(p(r)\) is `calibrated_p_raise_at_rate` with kappa from the locked JJ 40k pin
(\(p_{\mathrm{MC}}(1)/p_{\mathrm{ind}}(1)\)). Planning numbers (BN AA would
block some HJ aces, so true \(p\) is a touch lower):

| \(r\) | \(p_{\mathrm{ind}}\) | \(p_{\mathrm{trap}}\) |
| ---: | ---: | ---: |
| 0% | 0 | 0 |
| 79% | 0.409 | **0.419** |
| 86% | 0.435 | 0.445 |
| 87% | 0.438 | **0.449** |
| 100% | 0.482 | 0.494 |

Two trap-call leaves, because AA / two pair **do not assume fold** in
`sandbag_v1`:

| Leaf | Value | Role |
| --- | --- | --- |
| **fold_bound** | −$2 | Even folding the 1–6 raise after the $2 call (JJ–KK line; pessimistic for AA / two pair) |
| **tight_proxy** | tight-polar HU call | Optimistic vs-trap street (trap set is two pair+ / HJ aces, *stronger* than tight CO) |

## AA raise→fold (\(r=0\%\) all-legal → \(r=79\%\))

Locked HU: all-legal AA **raise** (call +$0.275, raise-cd +$1.454, P(win) =
0.545). r79 AA **fold** (call −$0.242, P(win) = 0.491).

| CO range | trap \(r\) | EV call mixed (fold_bound) | EV raise-cd (HU) | P(win) HU | Action |
| --- | ---: | ---: | ---: | ---: | --- |
| all-legal | 0% | +$0.275 | +$1.454 | 0.545 | **raise** |
| all-legal | 79% | −$0.678 | +$1.454 | 0.545 | **raise** |
| r79 chart | 0% | −$0.242 | +$0.910 | 0.491 | **fold** |
| r79 chart | 79% | −$0.978 | +$0.910 | 0.491 | **fold** |
| tight | 0% | −$1.538 | −$0.836 | 0.316 | **fold** |

Chart-range at the wrong \(r\): the r79 range folds AA with **zero** trap.
Non-chart range at a known \(r\): all-legal at 79% still value-raises (the
call line goes −EV; the raise line does not, and AA is still a favorite vs
that range). Under 79%, the chart *is* all-legal; opening tighter than that
(tight polar at trap 0) folds AA — again range, not trap.

Trap-only cannot flip AA on this bound because a value-raise does not need
the call line. Fold-to-3-bet (−$4 on the raise line) *would* fold AA at
\(p\approx 0.42\) (mixed raise ≈ −$0.83). That is multi-raise, out of scope.

## Two pair raise→call (\(r=86\%\) → \(r=87\%\))

Locked HU: r86 two pair **raise** (call +$0.595, raise-cd +$1.048, P(win) =
0.505). r87 two pair **call** (call +$0.318, raise-cd +$0.635, P(win) =
0.464). The only CO change at that cut is **KK needs ace or joker**.

| CO range | trap \(r\) | EV call mixed (fold_bound) | EV raise-cd (HU) | P(win) HU | Action |
| --- | ---: | ---: | ---: | ---: | --- |
| r86 chart | 0% | +$0.595 | +$1.048 | 0.505 | **raise** |
| r86 chart | 87% | −$0.570 | +$1.048 | 0.505 | **raise** |
| r87 chart | 0% | +$0.318 | +$0.635 | 0.464 | **call** |
| r87 chart | 87% | −$0.722 | +$0.635 | 0.464 | fold (bound only) |
| all-legal | 87% | −$0.499 | +$1.488 | 0.549 | **raise** |
| tight | 0% | +$0.219 | +$0.320 | 0.432 | **call** |

Chart-range at the wrong \(r\): r87 CO at trap 0 already **calls**. Trap-only
(r86 CO, still a favorite at P(win) = 0.505) still **raises**. A too-loose
all-legal CO at table 87% still gets raised.

**Matching fold_bound at r=87%.** Mixing −$2 into the thin +$0.32 call makes
call −EV, so `recommend_action` prints **fold**. That is the even-folding
bound, not two pair’s line (`sandbag_v1` walk: AA / two pair do not assume
fold). **tight_proxy** on the same cell stays **call** (mixed +$0.274). This
is not a new lookup threshold and is not a sign flip of raise→call. Do not
add a row.

## What a leak does (exploit through-line)

| Leak | AA | Two pair |
| --- | --- | --- |
| CO opens all-legal at high \(r\) (wider than the chart) | still **raise** | still **raise** |
| CO opens the r79/r87/tight range at \(r=0\) (tighter than the chart under 79%) | **fold** | **call** at r87/tight; still **raise** at r79 |
| Table traps a lot, CO still wide | no AA/two-pair flip without a 3-bet tree | same |

Baseline (chart-range CO, HU, no bluff-raise): the signed lookup. What moves
it: **CO’s actual JJ/QQ/KK policy**, not \(p_{\mathrm{raise}}\) on the call
line. How to respond: if CO is dumping bare JJ, treat the node as all-legal
and keep raising AA; if CO is already on the r79 cut, fold AA even when the
early six never trap.

## Out of scope

Items 2–4 of the considerations ticket (BN bluff-raises, Super System count,
two-pair rank). Multi-raise, draw/post-draw, HJ, 3:1/4:1, concealment, Ring 1,
UTG re-solve. Fold-to-3-bet is recorded on each cross cell as
`fold_threebet_action` and is **not** product.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Range-only** | Chart CO range, trap \(=0\) | The signed HU lab for that range |
| **Trap-only** | Polar / neighboring range at table \(r\) | Call line mixed with \(p(r)\); raise stays HU |
| **fold_bound** | Even fold the 1–6 raise | −$2 after the $2 call |
| **tight_proxy** | Optimistic vs-trap call | Tight-polar HU call EV |
| **No lookup row** | Signed grid unchanged | Neither switch is a trap-rate flip |
