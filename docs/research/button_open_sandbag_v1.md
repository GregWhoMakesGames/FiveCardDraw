# Frame: button open, sandbag v1 (100%)

Slug: **`button_open_sandbag_v1`**. Parent: [INDEX.md](INDEX.md) research frames.
Ticket: [../NEXT_STAGE_SANDBAG_AND_CO.md](../NEXT_STAGE_SANDBAG_AND_CO.md).

BN (seat 8) acts after seats 1–7 pass. Seats 1–7 **always** pass the v1
sandbag-set and **always raise** if BN opens. Contrast:
[button_open_no_sandbagging.md](button_open_no_sandbagging.md) (0% sandbag).

**How to point at this work:** `evaluate button_open_sandbag_v1`

## Sandbag-set v1 (locked for this frame)

| Seats | Pass instead of opening |
| --- | --- |
| 1–7 | Two pair or better |
| 6 (HJ) and 7 (CO) **also** | Pair of aces |

LJ (seat 5) still opens aces. (v1 pin was corrected from LJ+CO to HJ+CO; the
deal-MC plan is unchanged.) Voluntary open = jacks-or-better minus that set.

## Product question — **yes, opening JJ is −EV**

If seats 1–7 sandbag that set 100% and always raise a BN open, and BN always
folds JJ to a raise, **opening JJ is −EV vs pass = 0**.

| Piece | Value |
| --- | ---: |
| \(p_{\mathrm{raise}}\) (8-way deal MC) | **0.5730** |
| No-raise leaf (reused 0% sandbag JJ open) | **+$1.936** |
| \((1-p)\times\) no-raise leaf | +$0.827 |
| \(p\times(-2)\) fold JJ to the raise | −$1.146 |
| **EV(open JJ)** | **−$0.319** |
| EV(pass) | 0 |

Break-even \(p_{\mathrm{raise}}\) vs the reused leaf is \(1.936/(1.936+2)\approx 0.492\).
The measured raise rate sits **~0.08** above that line (about 33 SE of the
40k-deal MC). Sign is not close.

Code: `src/fivecarddraw/validation/sandbag_v1.py`. Fixture:
`tests/fixtures/validation/sandbag_v1.json`. CLI:
`python -m fivecarddraw.validation.sandbag_v1 --write-fixture`.

## Method

Folded-to-BN under 100% sandbag: seats 1–7 passed ⇒ none has a *voluntary*
opener (jacks+ minus that seat’s sandbag-set).

| Branch | What is true | BN JJ payoff |
| --- | --- | --- |
| **Raise** | ≥1 of 1–7 still has a sandbag-set hand | Always raise; BN folds JJ → **−$2** |
| **No-raise** | Nobody in 1–7 has sandbag-set either ⇒ **no open-legal in 1–7** | Same as 0% sandbag JJ open |

Out of scope (not in this number): Ring 1, multiway raise caps, BN *calling*
the raise, sandbag rates other than 0% vs 100%.

### No-raise leaf (reused, not rebuilt)

Do **not** rebuild post-draw Nash. The no-raise leaf is the locked
[button_open_no_sandbagging](button_open_no_sandbagging.md) JJ open:

\[\mathrm{EV}(\mathrm{open})=\;2 + p_{\mathrm{call}}\,(\mathrm{EV}_{\mathrm{bn}}-4).\]

- \(\mathrm{EV}_{\mathrm{bn}}=+3.0755\) — §3.4 non-bluff, **pair_J \(d=3\)**,
  vs the full 2:1 mix (`postdraw_nonbluff_ev_summary.json`; docs round to +3.08).
- \(p_{\mathrm{call}}=6.9\%\) — that frame’s 150k-deal check
  \(P(\)any of 1–7 is 2:1 \(\mid\) 1–7 all unable). Independent planning there
  was 6.0% (BN no bug). 2:1 first callers still **call**, they do not raise.
- Steal = +$2 when nobody calls. Pass = 0.

That pins the leaf at **+$1.936** (6.0% call would be +$1.945; same sign on
the mix). ~6% of pair_J combos hold the bug, which would pull \(p_{\mathrm{call}}\)
slightly down toward the 0.3–0.5% bug-in-BN band and make the leaf a few cents
better — not enough to flip EV(open) at \(p_{\mathrm{raise}}\approx 0.57\).

### \(P(\mathrm{raise}\mid 7\text{ passed, BN holds pair_J})\)

Predicates reuse `classify_opener` (`two_pair` / `two_pair_aces_up` / trips+ vs
`pair_A`). Inventory from the showdown-matrix combo counts:

| Set | Combos | Unconditional \(p\) |
| --- | ---: | ---: |
| Open-legal | 642,881 | 0.2240 |
| Two pair+ (seats 1–7 sandbag) | 235,697 | 0.0821 |
| Pair_A (HJ/CO also sandbag) | 137,904 | 0.0481 |
| HJ/CO sandbag-set | 373,601 | 0.1302 |
| Not open-legal | 2,226,804 | 0.7760 |

**Independent-seat planning** (no BN cards): \(P(N\mid\text{passed})\) is
0.9043 on seats 1–5 and 0.8563 on HJ/CO → \(p_{\mathrm{raise}}=1-0.9043^{5}\cdot 0.8563^{2}=\mathbf{0.5566}\).

**Same product with BN pair_J blocked** (2,000 pair_J × 50 remaining 5-sets,
seed `20260907`): jack/bug removal barely moves it → **0.5595**. BN pair_J
blocks other pair_J (voluntary, already conditioned out) more than two pair+
or aces.

**Seeded 8-way deal MC** (condition BN `pair_J`, condition 1–7 have no
voluntary opener, measure ≥1 sandbag-set):

| Pin | Value |
| --- | ---: |
| \(n\) (conditioned deals) | **40,000** |
| seed | **20260907** |
| BN pair_J deals before the voluntary filter | 96,215 |
| Full 53-card shuffles | 3,076,761 |
| \(n_{\mathrm{raise}}\) | 22,921 |
| \(p_{\mathrm{raise}}\) | **0.573025** (SE 0.00247) |
| \(P(\)BN holds the bug \(\mid\) conditioned\()\) | 0.064 |

The joint is a bit *higher* than the independent product: one seat’s junk
leaves the rest of the deck richer in sandbag-set cards, so the “all neither”
event is rarer than \(p^{7}\). Histogram of sandbag-set seats given passed:
0 → 17,079; 1 → 15,690; 2 → 5,802; 3+ → 1,429.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **100% raise** | Evaluate BN JJ vs always-raise sandbaggers | Folded-to-BN posterior includes sandbag-set hands; they raise; BN folds JJ for −$2 |
| **No-raise leaf** | Reuse 0% sandbag JJ open | No sandbag-set in 1–7 ⇒ same steal + 2:1 mix as the no-sandbag frame |

Ring / Line / Stage C aliases stay in `button_open_no_sandbagging` (tabled Nash).

## 1–6-only world (CO never sandbags)

Follow-up laboratory: seats **1–6** sandbag the v1 set 100% and always raise a
BN open; **CO never sandbags** (opens every legal hand). Folded-to-BN therefore
means 1–6 have no voluntary opener **and CO has no open-legal** — CO monsters
already opened, so they never sit in this node. Same accounting: pass = 0;
fold to a raise after opening = **−$2**; no-raise leaf reuses the 0% sandbag
steal + 6.9% 2:1 mix (`EV_leaf = 2 + 0.069*(EV_bn−4)`). Do not rebuild Nash.

Code world: `seats_1_6_only` in `sandbag_v1.py`. Fixture:
`tests/fixtures/validation/sandbag_v1_seats_1_6_only.json`. CLI:
`python -m fivecarddraw.validation.sandbag_v1 --world seats_1_6_only --write-fixture`
(add `--walk` for Q2).

Sandbag-set in this world:

| Seats | 100% pass, then always raise BN |
| --- | --- |
| 1–6 | Two pair or better |
| 6 (HJ) **also** | Pair of aces |
| 7 (CO) | **Does not sandbag** — opens all legal |
| 5 (LJ) | Two pair+ only (still opens AA) |

The 7-seat JJ −EV pin above is unchanged.

### Q1 — is opening JJ +EV?

**No. Opening JJ is still −EV**, but the mix is close. Removing CO from the
sandbag set drops \(p_{\mathrm{raise}}\) from Agent A’s **0.573** to **0.496**.

| Piece | Value |
| --- | ---: |
| Independent-seat planning (no BN cards) | 0.4822 |
| Independent, BN pair_J blocked (2,000 × 50, seed `20260907`) | 0.4842 |
| \(p_{\mathrm{raise}}\) (8-way deal MC) | **0.495925** (SE 0.00250) |
| No-raise leaf (reused 0% sandbag JJ open) | **+$1.936** |
| Break-even \(p_{\mathrm{raise}}\) vs that leaf | 0.4919 |
| \((1-p)\times\) no-raise leaf | +$0.976 |
| \(p\times(-2)\) fold JJ to the raise | −$0.992 |
| **EV(open JJ)** | **−$0.016** |
| EV(pass) | 0 |

Pin: \(n=40{,}000\) conditioned deals, seed **20260907**. BN pair_J deals before
the voluntary / CO-legal filter: 113,922. Full shuffles: 3,641,686.
\(n_{\mathrm{raise}}=19{,}837\). Histogram of sandbag-set seats given passed:
0 → 20,163; 1 → 14,783; 2 → 4,247; 3+ → 807.

The joint is again a bit *higher* than the independent product (junk in one
seat leaves the rest richer in two pair+). Versus Agent A, one fewer sandbag
seat **and** CO’s monsters already filtered out both cut \(p_{\mathrm{raise}}\).
The leftover rate still sits **~0.004** (~1.6 SE) above break-even. Sign is
−EV, not a blowout. 6.0% call instead of 6.9% still −EV (−$0.012).

### Q2 — lowest +EV BN open (same lab)

BN **folds JJ, QQ, and KK** to a sandbag raise (−$2). Per-class \(p_{\mathrm{raise}}\)
uses that class’s blockers; no-raise leaves use §3.4 locked draws + the same
6.9% 2:1 mix. Same \(n=40{,}000\), seed **20260907**.

| BN class | Locked d | EV_bn | Leaf | \(p_{\mathrm{raise}}\) (SE) | Raise policy | EV(open) |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| pair_J | 3 | +3.0755 | +$1.936 | 0.4959 (0.00250) | fold | **−$0.016** |
| pair_Q | 3 | +2.9615 | +$1.928 | 0.4987 (0.00250) | fold | **−$0.031** |
| pair_K | 3 | +3.0935 | +$1.937 | 0.5003 (0.00250) | fold | **−$0.032** |
| pair_A | 3 | +2.607 | +$1.904 | 0.4414 (0.00248) | **fold bound** | **+$0.181** |

JJ / QQ / KK raise rates sit within ~2 SE of each other; none clears 0.
**Lowest +EV class is pair_A (AA).**

AA does **not** assume fold as the real line. The number above is a cheap
bound: *even folding AA to the sandbag raise* is already +EV vs pass, because
BN’s aces block HJ’s buried AA (and aces-up two pair), so \(p_{\mathrm{raise}}\)
drops ~0.05 below the JJ–KK band and below AA’s 0.488 break-even. A
call-the-raise vs two-pair+ street is not needed to sign the floor; no
raise-tree Nash. (The reused 6.9% 2:1 \(p_{\mathrm{call}}\) is conservative for
AA: this node has the bug in BN 38.6% of the time, which would cut drawers
and push the no-raise leaf toward +$2.)

Walk stops at AA. Two pair / trips were not required to sign the floor.

### Q3 (flag only — do not iterate the sandbag set here)

If BN stops opening JJ–KK, AA is no longer behind BN’s whole opening range, so
HJ sandbagging AA (the v1 aces pin, originally HJ+CO) is inconsistent. **Revisit
that pin later.** This PR does not retune sandbag frequencies.


