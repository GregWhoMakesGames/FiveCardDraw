# Post-draw strategy tree (BN vs one 2:1 drawer)

Status snapshot after the Stage C cap re-filter. Locked vs open is marked
on each node. Parent chapters:
[research/ch03_dealer_opening.md](research/ch03_dealer_opening.md),
[research/ch04_draw_mixes.md](research/ch04_draw_mixes.md).

```
Pre-draw (locked for this laboratory)
  BN opens (made jacks+). One 2:1 caller calls. Others fold.
  Pot $6 into the draw. No pre-draw raise.  [Ch.2 §2.9 call/raise/mix is OPEN]

Draw (locked post-B / C)
  Pairs JJ–AA          d=3
  Two pair             d=1
  Trips                d=2 primary  /  d=1 unified fork (still live)
  Quads                d=1
  Other straight+      stand (d=0)
  Caller               keep-4 / d=1
  [Pair d≠3 concealment is OPEN — after d=3 vs d=2 EV confirm]

Post-draw first action — Stage C street (locked)
  BN trips / boat+ / pat straight+     BET $4
  BN two pair                          CHECK          ← Stage C
  BN one pair                          CHECK          ← M2
  Caller, if BN bet and caller made straight+     RAISE $8
  Caller, if BN checked
      straight+                        BET $4 (stab)
      AA face pair                     BET $4 (narrow stab)
      miss / weaker                    CHECK

Raise node = BN BET ∩ caller STRAIGHT+
  Pre-C (retired for cap):  unimproved two pair sat here. P = 0.189 (7,559 / 40k)
  Stage C (current):        two pair never bets. P = 0.0903 (3,612 / 40k)
                            Air = unimproved trips only. two_pair_on_node_n = 0

                    public d          n     share    air?
                   /   |    \    \
                 d=0  d=1   d=2  d=3
                 750   293  1299 1270
                 21%    8%   36%  35%
                  |     |     |    |
               LINE 2  nuts  LINE 1 LINE 1
               pat     boats trips  pair→trips
               S/F/    quads draw   / boats
               rare
               boats
               no air  no air  trips  trips
                               1155   1103
```

## The two 3-bet lines (measured)

After BN bets and the caller raises, pot $18, $4 to BN. Seed 20260902,
combo-weighted locked draws (`tp1_tr2_q1`).

### Line 1 — trips draw (`d=2` ∪ `d=3`) — n = 2,569 (71% of node)

BN started trips (or a pair that made trips). Public draw is not zero.

| BN final | n on line | First action | vs raise | Status |
| --- | ---: | --- | --- | --- |
| Trips (missed) | 2,258 | Bet | Call (honest) or mix **β** bluff 3-bet | Value line **locked**; β **OPEN** (Ring 1) |
| Boat+ | 273 | Bet | **3-bet** (value) | Locked |
| Straight / flush | 38 | Bet | Call / 3-bet as family table | Rare (pair → made S/F) |
| Two pair | 0 | — | not here | Stage C check |

Caller vs a **no-air** flush+ 3-bet on this line: those 3-bets are boats.
Flush is drawing dead. Measured BR: straight **fold**, flush **fold**,
SF **cap**. Fold-non-SF is the polar hypothesis. α nearer pot odds (~13%).
**β / α not solved** (Ring 1).

### Line 2 — pat straight+ (`d=0`) — n = 750 (21% of node)

BN stood. No trips or two pair on this public line.

| BN final | n on line | First action | vs raise | Status |
| --- | ---: | --- | --- | --- |
| Straight | 470 | Bet | **Call** (broadway A thin 3-bet) | Locked |
| Flush | 174 | Bet | **3-bet** (value) | Locked |
| Boat+ | 106 | Bet | **3-bet** (value) | Locked |
| Trips / two pair | 0 | — | not here | They do not stand |

Caller vs a flush+ 3-bet: BN is usually a straight or flush (470+174),
rarely a starting boat (106). Measured BR vs flush+: straight **fold**,
flush **call** (EV −7.45 vs fold −8.00, n=66), SF **cap**.
**Do not fold all flushes.** Mixing cap vs call, and Nash, still OPEN.
There is **no trips air**, so Ring 1 cannot set flush indifference with β.

### `d=1` (not a third bluff line) — n = 293 (8% of node)

Two pair that *boated* plus quads. Unimproved two pair checked. BN family
on the node is 100% `boat_plus`. A 3-bet is almost always nuts. Caller
fold-non-SF (measured).

---

## What is determined vs open

| Piece | Status |
| --- | --- |
| Draw defaults (pairs d=3, two pair d=1, trips fork, quads d=1, pat stand) | **Locked** |
| Check one pair (M2) | **Locked** |
| Always check two pair (Stage C) | **Locked** |
| Always bet trips / boat+ / pat straight+ | **Locked** |
| Caller raise straight+; AA stab when checked | **Locked** |
| M2 / non-bluff class × d **numbers** | Honest cell: two pair still *bets*. Not rewritten. Forward street is C. |
| Raise-node filter | **Locked:** Stage C (trips+ bets). P(node)=0.0903 |
| Node mass / joint EV **by public d** | **Locked** (this fixture) |
| Pooled “fold all flushes” as a single BR | **Retired.** Quote Line 1 / Line 2 instead. |
| BN 3-bet flush+ / boat+; call straights / trips | Value line **locked**; trips bluff OPEN |
| Line 1 caller flush vs no-air flush+ | **fold** (measured) |
| Line 2 caller flush vs no-air flush+ | **call** (measured) |
| Line 1 α / β (trips bluff 3-bet) | **OPEN** — Ring 1 |
| Line 2 flush mix / Nash | **OPEN** (call ≥ fold is pinned; mix not solved) |
| Cap / 5th street; Ring 2 node Nash | **OPEN** |
| Pair concealment; Ch.2 raise/call; CO bluff | **OPEN** (other tickets) |

---

## Chip pins (unchanged)

| Node | Pot | To call |
| --- | ---: | ---: |
| After BN bet + caller raise | $18 | $4 |
| After BN 3-bet | $26 | $4 (break-even 4/30 ≈ 13.3%) |
| Full cap | $38 | — |

Joint EV on the Stage C node (combo-weighted): call-it-down EV_bn = **−2.40**;
honest flush+ 3-bet / cap-SF = **−1.71**.
