# Next stage: BN vs CO lookup at open-chart thresholds

**Status: signed — do not restart.** Lookup is in [AGENTS.md](../AGENTS.md).
Code frames landed as stacked PRs off `main` (`button_vs_cutoff_r79` … `r96`).
Next work: [NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md](NEXT_STAGE_CO_OPEN_CONSIDERATIONS.md)
(plan only). Parent: [research/INDEX.md](research/INDEX.md).

Polar endpoints:

| \(r\) | CO range | BN pin | Frame |
| --- | --- | --- | --- |
| 0% (all legal) | every jacks+ | fold JJ–KK; raise AA / two pair / trips+; 2:1 call | [button_vs_cutoff_all_legal.md](research/button_vs_cutoff_all_legal.md) |
| ~100% (tight) | AA+ plus QQ/KK+joker | fold JJ–**AA**; call two pair (thin); raise aces-up / trips | [button_vs_cutoff_tight.md](research/button_vs_cutoff_tight.md) |

Interior (chart-range CO): **AA folds from \(r=79\%\) up.** **Two pair** still
raises through 86%, **calls** from 87%. Two flips, not seven.

| \(r\) | JJ–KK | AA | Two pair | Aces-up / trips |
| --- | --- | --- | --- | --- |
| 0% | fold | **raise** | raise | raise |
| 79–86% | fold | **fold** | raise | raise |
| 87–96% / tight | fold | fold | **call** | raise |

A human will not pin \(r\) to 1%. Later seats **look this up** when someone
slowplays instead of resimulating last two.

## CO range at each threshold (from the signed chart)

CO always opens AA+ / two pair+. JJ/QQ/KK:

| \(r\) | JJ | QQ | KK |
| ---: | --- | --- | --- |
| \(<79\) | open | open | open |
| 79 | ace or joker | open | open |
| 84 | ace or joker | ace or joker | open |
| 86 | joker only | ace or joker | open |
| 87 | joker only | ace or joker | ace or joker |
| 90 | joker only | joker only | ace or joker |
| 93 | pass | joker only | ace or joker |
| \(\ge 96\) | pass | joker only | joker only |

96% matches the tight polar (QQ/KK need the joker; JJ never opens).

Do not restart this ticket. Out of scope: HJ, the four CO-open considerations
(range vs \(r\), BN bluffs, reverse-blockers, two-pair rank), multi-raise,
3:1/4:1 inventories, UTG re-solve.
