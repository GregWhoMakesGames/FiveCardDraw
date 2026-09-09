# Next stage: BN vs CO lookup at open-chart thresholds

**Status: plan only. Do not compute in this ticket.** Land the review
rollup on `main` first. Parent: [research/INDEX.md](research/INDEX.md).
Living queue: [AGENTS.md](../AGENTS.md).

Polar endpoints are **signed** (do not restart):

| \(r\) | CO range | BN pin | Frame |
| --- | --- | --- | --- |
| 0% (all legal) | every jacks+ | fold JJ–KK; raise AA / two pair / trips+; 2:1 call | [button_vs_cutoff_all_legal.md](research/button_vs_cutoff_all_legal.md) |
| ~100% (tight) | AA+ plus QQ/KK+joker | fold JJ–**AA**; call two pair (thin); raise aces-up / trips | [button_vs_cutoff_tight.md](research/button_vs_cutoff_tight.md) |

The **inflection** (AA raises vs a wide cutoff and folds vs a tight one) is
the product. Fill the interior with a lookup, not a full late-position
re-solve each time someone slowplays.

## Product

For each chart threshold \(r \in \{79, 84, 86, 87, 90, 93, 96\}\)%:

1. Read CO’s opening range off
   [cutoff_open_sandbag_v1.md](research/cutoff_open_sandbag_v1.md) (CO never
   sandbags two pair+ / aces; JJ/QQ/KK flavors follow the band).
2. Compute BN **fold / call / raise** by class vs that range, same locked
   leaves as the polar labs (no multi-raise, no live draw/post-draw Nash).
3. Write one row of a lookup: \(r\) → CO range → BN action table.

A human will not pin \(r\) to 1%. The table is so later seats can **look up**
behavior when an earlier player slowplays, instead of resimulating CO+BN.

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

## Parallelism

After this lands on `main`, agents **may** split by \(r\) (one threshold per
PR) or own the whole grid in one PR. Do not edit the polar frame files’
product answers. New frame or a grid sibling is fine; add **one INDEX row**.

Out of scope here: HJ mixes, reverse-blockers, multi-raise, 3:1/4:1
inventories, UTG re-solve.

Reuse: `validation/button_vs_cutoff.py`,
`validation/button_vs_cutoff_tight.py`, `cutoff_open_chart.py`.
