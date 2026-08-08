# Post-draw M2: opener-first face-pair betting grid

**Status:** Implemented. Code `src/fivecarddraw/validation/postdraw_betting_m2.py`,
CLI `analyze-postdraw-m2`, summary fixture
`tests/fixtures/validation/postdraw_m2_grid_summary.json`, tests
`tests/test_postdraw_m2.py`.

Parent showdown work: [NEXT_STAGE_SHOWDOWN_MATRIX.md](NEXT_STAGE_SHOWDOWN_MATRIX.md).

This is **not** a full post-draw Nash solve. It is a small policy grid that
probes three knobs after the draw when the pre-draw line is open + call only.

---

## Locked setup

| Item | Value |
| --- | --- |
| Matchup | Dealer opener vs one 2:1 drawing caller (bug draws + FFS16) |
| Pre-draw | Open + **call only** (no raise); pot into draw **$6** |
| Drawer draw | Always keep-4, draw 1 |
| Opener draw | Non-breaking defaults: pairs **d=3**, trips **d=2**, two pair **stand**, straight+ **stand** |
| Post-draw | **Opener acts first**; one street; big bet **$4**; at most bet + one raise |
| Sandbagging | Out of scope |
| Deck | Exact remaining cards after both hands (caller draws first, then opener) |

### Non-knob behavior (pinned)

- Opener **always** value-bets two pair / trips / straight+ after the draw.
- Drawer **always** bets/raises straight+ for value; misses check or fold.
- Face-pair **call-downs** match the aggression threshold: if the drawer
  stabs/raises with rank ≥ \(r\), the opener calls a one-pair hand iff its
  pair rank ≥ \(r\) (and always continues with two pair+).

### Knobs searched (60 policies)

1. **Opener lead** with final one pair JJ–AA: `never`, `AA`, `AA+KK`, `AA..QQ`, `AA..JJ`
2. **Drawer stab** when checked to (face pair): `never`, `AA`, `AA+KK`, `AA..JJ`
3. **Drawer raise** when bet into (face pair): `never`, `AA`, `AA+KK`

Straight+ aggression is always on, so “stab=never” still shows ~34% stab rate
from completed draws alone.

---

## How to regenerate

```bash
pip install -e ".[dev]"
analyze-postdraw-m2 --n-deals 25000   # writes outputs/validation/postdraw_m2_grid.{json,md}
pytest -q tests/test_postdraw_m2.py
```

`outputs/` is gitignored. The **summary fixture** is checked in and pinned by
pytest; refresh it only when intentionally re-baselining the MC run
(seed `20260808`, 25 000 deals).

---

## Findings (seed 20260808, 25k deals)

EV below is **opener net chips from the post-draw node** on deals where the
opener still has a jacks-or-better **one pair after drawing 3** (~11k of the
25k deals). Higher is better for the opener.

### 1. Default: check JJ–AA

Against a drawer who only auto-bets straight+ when checked to (“passive”
face-pair policy), **every** one-pair lead threshold loses EV vs checking:

| Opener lead | EV (d=3 one-pair) | Δ vs never |
| --- | ---: | ---: |
| never | +3.666 | — |
| AA only | +3.291 | **−0.375** |
| AA+KK | +2.960 | −0.706 |
| AA..QQ | +2.586 | −1.080 |
| AA..JJ | +2.206 | **−1.461** |

Leading bloates pots into straight+ raises more than it earns from folding out
misses. **Do not lead JJ–QQ for value** in this model.

### 2. Thin exception: lead AA only vs narrow stabs

If the drawer stabs checks with **AA only** (no face-pair raises), leading AA
is roughly break-even to slightly better than checking (**+0.040** EV on d=3
nodes). Same order of magnitude for AA+KK stabs (**+0.035**).

Interpretation: AA leads pick up folds from hands that would not stab (misses,
weaker face pairs), while checking cedes the betting lead to narrow AA stabs.

If the drawer stabs **wide** (`AA..JJ`), lead vs check collapses to the same
EV under matched call-downs — leading does not rescue you.

### 3. Drawer stab width matters more than opener lead

| Drawer stab when checked to | Stab rate | Opener EV if never leads |
| --- | ---: | ---: |
| never (straight+ only) | 0.3434 | +3.666 |
| AA | 0.3905 | +3.252 |
| AA+KK | 0.3917 | +2.903 |
| AA..JJ | 0.4133 | +2.206 |

Narrow face-pair stabs (AA, maybe KK) are the interesting region. Wide J+
stabs are a blunt EV tax on the opener.

### 4. Raising face pairs into a strong-heavy bet range donates

When the opener **checks one pair** and only bets two pair+, the live betting
range is strong-heavy. Drawer face-pair **raises** then pay off two pair+ /
boats.

Raising thin face pairs is more coherent only if the opener is often **leading
pairs** (bet range includes JJ–AA). In the grid, opener EV on “all deals”
rises when the drawer raises AA/KK into strong-heavy bets — i.e. that raise
knob helps the opener / hurts the drawer.

### 5. Coupled story

1. Opener checks one pair → betting range stays strong.
2. Drawer should keep face-pair stab/raise **narrow** (AA, maybe KK), not every JJ+.
3. Opener only considers leading **AA** if that narrow stab appears; still does
   not auto-bet JJ–QQ.

---

## Tests

| Test | What it locks |
| --- | --- |
| `test_policy_grid_size` | 5×4×3 = 60 policies |
| `test_check_check_showdown_ev_when_opener_wins` | Check-check accounting: win pot $6 |
| `test_aa_lead_gets_fold_from_miss` | AA lead vs miss fold: net +$6 |
| `test_fixture_summary_patterns` | Checked-in sweep numbers + qualitative deltas (lead AA vs passive &lt; 0, lead J+ worse, lead AA vs AA-stab ≥ 0) |

Unit tests do **not** re-run the 25k-deal MC. Pattern pins use the summary
fixture with modest absolute tolerance on stored floats.

---

## Out of scope / next

- Mixing two-pair stand vs draw-1 for concealment
- Full post-draw CFR / belief equilibrium (M3–M4)
- Multiway; pre-draw raises; sandbagged pat hands in the caller range
- Changing ante:bet or UTG open strategy from these numbers alone
