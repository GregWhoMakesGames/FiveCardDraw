# Frame: button open, no sandbagging

Slug: **`button_open_no_sandbagging`**. Parent: [INDEX.md](INDEX.md) research frames.

BN (seat 8) opened. Nobody sandbagged. The laboratory is BN vs drawing callers (usually one 2:1 keep-4). This is the current top-level slice for post-draw work and for button opening EV.

**How to point at a step**

- Specific: `evaluate button_open_no_sandbagging Ring 2`
- Short, when recent work is already in this frame: `evaluate Ring 2`

Mint a **new frame file** when the laboratory changes (UTG, sandbagging, CO return-to-actor). Add a row to the INDEX frames table. Do not reuse these aliases in a different frame.

## Aliases in this frame

| Alias | Human-readable name | What it actually is |
| --- | --- | --- |
| **Stage C** | Evaluate BN always checking two pair | Post-draw, two pair checks; trips+ still bets. Raise node is no longer two pair+. |
| **pre-C lab** | Evaluate leftover-fold polar mix while two pair still bets | Old node: two pair bets. 3-bet with frequency β, else fold. Pinned; not the current street. |
| **Ring 1** | Evaluate flush-indifference β on the raise node | Polar mix so caller flushes are call/fold indifferent. Held knobs; not Nash. On the current street this is **trips-only** air. |
| **Ring 2** | Evaluate raise-node Nash | Both sides mix. No held polar knobs. After Ring 1. |
| **Line 1** | Evaluate the BN trips-draw to post-draw action | Public \(d \in \{2,3\}\). Unimproved trips are the air. |
| **Line 2** | Evaluate the BN stand-pat post-draw action | Public \(d = 0\). No trips air; flush call vs a no-air flush+ 3-bet is already pinned. |

Detail tickets: [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md), [../NEXT_STAGE_POSTDRAW_CAP.md](../NEXT_STAGE_POSTDRAW_CAP.md), [../POSTDRAW_STRATEGY_TREE.md](../POSTDRAW_STRATEGY_TREE.md). Narrative: [ch03_dealer_opening.md](ch03_dealer_opening.md) §3.5–3.6, [ch04_draw_mixes.md](ch04_draw_mixes.md).
