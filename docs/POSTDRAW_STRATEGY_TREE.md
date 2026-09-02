# Post-draw strategy tree (BN vs one 2:1 drawer)

Status snapshot after Stage C. Locked vs open is marked on each node.
Parent chapters: [research/ch03_dealer_opening.md](research/ch03_dealer_opening.md),
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

Raise node (this ticket) = BN BET ∩ caller STRAIGHT+
  Pre-C (stale):  included unimproved two pair. P(node) ≈ 0.189
  Stage C:        two pair never bets. Air = unimproved trips only.

                    public d
                   /   |    \    \
                 d=0  d=1   d=2  d=3
                  |    |     |    |
               LINE 2  nuts  LINE 1 LINE 1
               pat     boats trips  pair→trips
               S/F/rare  quads draw   / boats
               boats
```

## The two 3-bet lines

After BN bets and the caller raises, pot $18, $4 to BN.

### Line 1 — trips draw (`d=2`, and `d=3` from pairs)

BN started trips (or a pair that made trips). Public draw is not zero.

| BN final | First action | vs raise | Notes |
| --- | --- | --- | --- |
| Boat+ | Bet | **3-bet** (value) | Locked from cap |
| Trips (missed) | Bet | Call (honest) or mix **β** bluff 3-bet | Ring 1 OPEN |
| Two pair | — | not here | Stage C check |

Caller vs a 3-bet on this line: BN is boat+ or a trips bluff. Flush is
drawing dead to boats. Fold-non-SF is the polar hypothesis. α nearer pot
odds (~13%). **Not solved yet** (Ring 1).

### Line 2 — pat straight+ (`d=0`)

BN stood. No trips or two pair on this public line.

| BN final | First action | vs raise | Notes |
| --- | --- | --- | --- |
| Flush / boat+ | Bet | **3-bet** (value) | Locked from cap |
| Straight | Bet | **Call** (broadway A thin 3-bet) | Locked |
| Trips / two pair | — | not here | They do not stand |

Caller vs a 3-bet: BN is usually a straight or flush, rarely a starting
boat. **Do not fold all flushes.** This BR was inferred from a pooled
flush+ range that mixed in boats from *draws*. Re-measure on `d=0` only
(this cap re-run). Mixing cap vs call with flushes is still OPEN.

### `d=1` (not a third bluff line)

Two pair that *boated* plus quads. Unimproved two pair checked. A 3-bet
is almost always nuts. Caller fold-non-SF.

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
| Raise-node filter | **This ticket:** Stage C (trips+ bets) |
| Node mass / joint EV / caller BR **pooled** | Re-run under C; do not quote 0.189 / fold-all-flush |
| Node + caller BR **by public d** | **This ticket** |
| BN 3-bet flush+ / boat+; call straights / trips | Value line **locked**; trips bluff OPEN |
| Line 1 α / β (trips bluff 3-bet) | **OPEN** — Ring 1 |
| Line 2 caller flush call vs fold on d=0 | **This ticket measures**; mix/Nash OPEN |
| Cap / 5th street; Ring 2 node Nash | **OPEN** |
| Pair concealment; Ch.2 raise/call; CO bluff | **OPEN** (other tickets) |

---

## Chip pins (unchanged)

| Node | Pot | To call |
| --- | ---: | ---: |
| After BN bet + caller raise | $18 | $4 |
| After BN 3-bet | $26 | $4 (break-even 4/30 ≈ 13.3%) |
| Full cap | $38 | — |
