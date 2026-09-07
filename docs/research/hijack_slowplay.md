# Frame: hijack slowplay mix vs BN open-everything

Slug: **`hijack_slowplay`**. Parent: [INDEX.md](INDEX.md) research frames.
Ticket: [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md).
Upstream pins: [cutoff_open_no_sandbagging.md](cutoff_open_no_sandbagging.md),
[button_open_sandbag_v1.md](button_open_sandbag_v1.md) (1–6-only world).

**How to point at this work:** `evaluate hijack_slowplay`

Code: `src/fivecarddraw/validation/hijack_slowplay.py`. CLI:
`analyze-hijack-slowplay` / `python -m fivecarddraw.validation.hijack_slowplay`.
Fixture: `tests/fixtures/validation/hijack_slowplay.json`. Seed `20260907`,
n_equity=2k, n_mc=40k (BN `pair_J`).

v1 is **position-by-position approximate GTO**, not full 8-way Nash. This
frame does not retune the sandbag *set* (Q3) and does not claim BN
open-everything is Nash — only whether HJ’s mix pushes total slowplay
through the ~98% line that made 100% early-six sandbag sit just over
BN’s fold-to-raise break-even.

## Product answers

1. **CO never-slowplay: confirmed.** Laboratory
   `cutoff_open_no_sandbagging` (seats 1–6 unable / 0% sandbag; BN opens
   every legal if CO passes and calls every legal if CO opens). Fixture
   `cutoff_open_summary.json` on `cursor/cutoff-open-no-sandbagging-6cf1`
   (`ee78fc7`):
   - Open every legal class, including JJ: EV(open JJ) = **+$1.435**
     (docs **+$1.44**) vs pass 0.
   - CO should **not** sandbag two pair+ or aces: open − best pass =
     **+$1.394 (AA)** / **+$1.423 (two pair)** (docs **+$1.39–$1.42**).
   Best pass is raise-checkdown vs BN’s open (+$0.27 / +$0.36), not 0.
   That is the “never slowplay” pin. This PR does not re-solve the CO tree.

2. **100% HJ slowplay is not optimal.** After 1–5 passed, with the
   hypothesis stack below, **AA and two pair slowplay**; **aces-up, trips,
   and straight+ open**. Mass-weighted \(r_{\mathrm{HJ}}^*\approx 0.655\),
   not 1.

3. **Yes — the mix drops total slowplay by ~8.3%** (from 100% to
   \(r_{\mathrm{tot}}\approx 0.917\)), past the 2% / 98% target, and
   \(p_{\mathrm{raise}}\) at that mix is **0.463 (MC)** vs BN’s
   fold-to-raise break-even **0.492**. That **supports** the temporary
   hypothesis that BN opens every legal hand. It is not a Nash claim.

## Laboratory (locked)

| Seat | Policy in this frame |
| --- | --- |
| 1–5 | 100% sandbag **two pair+**; LJ still **opens AA**; they **raise** an HJ open |
| 6 HJ | Decision: open fraction \(q=1-r\) vs slowplay \(r\) (pass, then raise if CO or BN opens). Sandbag-set = two pair+ **and AA** |
| 7 CO | **Never sandbags** (opens every legal) |
| 8 BN | Opens every legal (temporary hypothesis) |

Folded-to-BN with CO never sandbagging still means CO has **no open-legal**.
Seats 1–5 are the remaining early-sandbag mass.

**World-0 sensitivity (CO pin’s “1–6 unable”).** If 1–5 had no open-legal
at all they would **not** raise an HJ open. That world **overstates
EV(open)** for HJ monsters: AA world-0 EV(open) ≈ **+$1.42**, two pair ≈
**+$1.67** — both would *open* if 1–5 never raised. The hypothesis stack
is the primary number because sandbaggers who already passed **do** raise.
Do not hide that: AA/two pair slowplay *because* of the 1–5 raise, not
because steal EV is small.

## Accounting and tree approximations

Same pins as CO/BN: pass = 0 when the pot is never opened; steal = +$2;
fold to a raise after opening = −$2. No post-draw Nash rebuild; locked
`tp1_tr2_q1` draws; §3.4 vs 2:1; pair_A / two_pair vs-legal **open**
streets reused from the CO-vs-BN honest non-bluff HU.

| Node | What v1 does here |
| --- | --- |
| HJ opens, CO/BN legal | They **call** (v1; they do not raise). Steal vs 2:1 vs legal mix as in the CO lab, with two seats behind. |
| HJ opens, 1–5 sandbag-set | They **raise**. HJ takes the best of fold −$2 and **call-checkdown** on a $10 pot. No 3-bet Nash. |
| HJ slowplays, CO or BN opens | HJ **raises**; EV is raise-checkdown \(10 p_{\mathrm{win}}-4\), times \(P(\)CO or BN legal\()\). **No fold equity** vs JJ–KK (conservative for slowplay). |

If CO/BN folded JJ–KK to the slowplay raise, slowplay would look even
better. If 1–5 did not raise, AA/two pair would open (world-0).

## Per-class EV (hypothesis: 1–5 raise)

Class-blocked independent planning for \(P(\)1–5 raise\(\mid\)passed\()\) and
\(P(\)CO or BN legal\()\); 2k-deal locked-draw showdown equity vs
two pair+ (continue) and vs open-legal (slowplay \(p_{\mathrm{win}}\) for
classes without a CO HU cell).

| HJ class | EV(open) world-0 | EV(open) hyp | EV(slowplay) | \(r^*\) |
| --- | ---: | ---: | ---: | ---: |
| pair_A | +$1.42 | **+$0.31** | **+$0.51** | **1** (slowplay) |
| two_pair | +$1.67 | **+$0.42** | **+$0.63** | **1** (slowplay) |
| two_pair_aces_up | +$2.11 | **+$1.91** | +$1.26 | **0** (open) |
| trips | +$2.22 | **+$2.38** | +$1.58 | **0** (open) |
| straight_plus | +$2.59 | **+$3.41** | +$2.14 | **0** (open) |

100% slowplay would require EV(slowplay) ≥ EV(open) on the sandbag-set.
It fails for aces-up and stronger. AA and two pair are ~20¢ slowplay
favorites; the gap is a street-approximation, not a Nash indifference.
v1 does not mix those for exploitation — it takes the sign.

HJ sandbag-set mass: AA 36.9%, two pair 28.6%, aces-up 8.5%, trips (all)
17.0%, straight+ 9.0%. Mass-weighted
\(r_{\mathrm{HJ}}^*=0.369+0.286=\mathbf{0.655}\).

## Total rate vs BN

CO never sandbags. Independent planning (no BN cards), writeup pins
\(p_j=0.7760\), \(p_s^{1-5}=0.0821\), \(p_s^{\mathrm{HJ}}=0.1302\):

\[
p_{\mathrm{raise}}(r_{1-5}, r_{\mathrm{HJ}})
= 1 - \left(\frac{p_j}{p_j+r_{1-5}p_s^{1-5}}\right)^5
\left(\frac{p_j}{p_j+r_{\mathrm{HJ}}p_s^{\mathrm{HJ}}}\right)
\]

\[
r_{\mathrm{tot}}
= (5\cdot 0.0821\cdot r_{1-5} + 0.1302\cdot r_{\mathrm{HJ}})
/ (5\cdot 0.0821 + 0.1302)
\]

with \(r_{1-5}=1\). A 2% drop means \(r_{\mathrm{tot}}\le 0.98\), i.e.
\(r_{\mathrm{HJ}}\lesssim 0.917\). If \(r_{\mathrm{HJ}}=0\),
\(r_{\mathrm{tot}}\approx 0.759\). If \(r_{\mathrm{HJ}}=1\), the 2% test
fails.

| Mix | \(r_{\mathrm{HJ}}\) | \(r_{\mathrm{tot}}\) | independent \(p_{\mathrm{raise}}\) | MC \(p_{\mathrm{raise}}\) (BN pair_J, 40k, seed 20260907) |
| --- | ---: | ---: | ---: | ---: |
| All 100% (1–6-only pin) | 1 | 1 | 0.482 | **0.496** |
| This frame \(r^*\) | **0.655** | **0.917** | 0.455 | **0.463** (SE 0.0025) |
| HJ never slowplays | 0 | 0.759 | 0.395 | — |

BN JJ/QQ/KK fold-to-raise break-even is \(p_{\mathrm{raise}}\approx 0.492\).
At 100% sandbag in 1–6, MC 0.496 sits just over that line (~−$0.02).
Linear/Bayes near \(r=1\): **uniform \(r\lesssim 98\%\)** makes every
legal BN open +EV under fold-to-raise. The HJ mix lands at
\(r_{\mathrm{tot}}=0.917\) (an **8.3%** drop, well past 2%) and MC
\(p_{\mathrm{raise}}=0.463<0.492\). Joint enrichment vs independent is
still ~0.008 here (0.455→0.463), not enough to recross 0.492.

**Yes:** HJ’s optimum drops total slowplay by ≥2% and thereby supports
BN opening every legal hand — **conditional on this stack** (CO never
sandbags; 1–5 still 100% two pair+; BN still folds JJ–KK to a raise).

## Q3 flag (do not iterate here)

If BN actually stops opening JJ–KK, AA is no longer behind BN’s whole
opening range, so HJ burying AA is inconsistent. Same flag as the
1–6-only writeup. This PR does not retune the sandbag set.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **HJ slowplay** | Pass two pair+ / AA, raise CO/BN | \(r\) on the v1 HJ sandbag-set after 1–5 passed |
| **2% test** | Does \(r_{\mathrm{HJ}}^*\) push \(r_{\mathrm{tot}}\) through 98%? | Mass-weighted 1–6 slowplay vs BN; target \(r_{\mathrm{tot}}\le 0.98\) |
| **BN open-everything** | Temporary hypothesis | Every legal BN open +EV if fold-to-raise \(p_{\mathrm{raise}}\lesssim 0.492\) |

Ring / Line / Stage C aliases stay in `button_open_no_sandbagging`.
