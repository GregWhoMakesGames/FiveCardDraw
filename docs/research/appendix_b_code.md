# Appendix B — Code map and CLIs

| CLI | Module | Purpose | Typical chapter |
| --- | --- | --- | --- |
| `solve-predraw` | `predraw/solve.py` | Coarse position-by-position pre-draw charts | Pipeline |
| `audit-abstraction` | `abstraction.py` | Bucket sanity | Pipeline |
| `analyze-draw-call-odds` | `validation/draw_call_odds.py` | 2:1 / 3:1 drawing-call inventory | Ch.2 |
| `analyze-cascade-odds` | `validation/cascade_odds.py` | Second-caller cascade rates | Ch.2 |
| `analyze-face-pair-outs` | `validation/face_pair_outs.py` | JJ–AA side outs among drawers | Ch.2 |
| `analyze-showdown-matrix` | `validation/showdown_matrix.py` | Opener × drawer showdown | Ch.3 |
| `analyze-postdraw-m2` | `validation/postdraw_betting_m2.py` | Face-pair bet/check/stab grid | Ch.3 |
| `analyze-postdraw-draw-mixes` | `validation/postdraw_draw_mixes.py` | Draw-count A/B/C ladder | Ch.4 |
| `analyze-postdraw-nonbluff-ev` | `validation/postdraw_nonbluff_ev.py` | Non-bluff EV by class × d | Ch.3–4 |
| `analyze-opener-draw-beliefs` | `validation/opener_draw_beliefs.py` | Public-d belief tables | Ch.4 |

Fixtures live under `tests/fixtures/validation/`. Generated markdown/JSON under `outputs/` is gitignored.
