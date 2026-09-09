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
| `analyze-postdraw-cap` | `validation/postdraw_cap.py` | Post-draw 3-bet / cap on the raise node | Ch.3 |
| `analyze-postdraw-bluff` | `validation/postdraw_bluff.py` | Pre-C polar bluff 3-bet (else fold) | Ch.3 |
| `analyze-cutoff-open` | `validation/cutoff_open.py` | CO open/pass with BN behind (0% sandbag in 1–6) | Ch.5 |
| `analyze-cutoff-open-sandbag` | `validation/cutoff_open_sandbag.py` | CO vs 1–6 sandbag rate; `--write-blockers` / `--write-chart` | Ch.5 |
| `analyze-button-vs-cutoff` | `validation/button_vs_cutoff.py` | BN fold/call/raise vs CO opening every legal hand (range 1) | Ch.5 |
| `analyze-button-vs-cutoff-tight` | `validation/button_vs_cutoff_tight.py` | BN fold/call/raise vs tight CO (AA+ plus QQ/KK+joker) | Ch.5 |
| `analyze-button-vs-cutoff-range-vs-r` | `validation/button_vs_cutoff_range_vs_r.py` | Decompose AA / two-pair switches into CO range vs 1–6 trap rate | Ch.5 |
| `analyze-opener-draw-beliefs` | `validation/opener_draw_beliefs.py` | Public-d belief tables | Ch.4 |

Fixtures live under `tests/fixtures/validation/`. Generated markdown/JSON under `outputs/` is gitignored.
