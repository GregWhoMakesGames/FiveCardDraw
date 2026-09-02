# Chapter 4 — Opener draw mixes and range protection

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.  
> Stub — expand after Stage C re-run.

**Ledger role.** Continues the **BN vs 2:1 drawer** laboratory: public draw counts and check mixes that protect weak `d=3` pair lines.

---

## 4.1 Locked draw defaults (post Stage B)

| Class | Draw | Note |
| --- | --- | --- |
| Pair JJ–AA | **d=3** | Best improvement among pair options studied |
| Two pair | **d=1** | Dominant +EV lever in the 12-cell grid |
| Quads | **d=1** | EV-neutral vs stand; pollutes public d=1 |
| Other straight+ | Stand | Cannot join d=3 to “protect” pairs |
| Trips | **d=2** (primary) or **d=1** (unified) | Live fork for Stage C. `d=1` keep is highest-rank kicker (v1 pin); lowest / non-face kicker is a later EV question |

Non-bluff **post-draw EV** (honest betting, not just P(win)) is more subtle than Stage A’s improvement tables: **standing** is the chip-max non-bluff line for pairs (drawing three raises P(win) but the extra two pair+ auto-bets pay off ~34% straight+). Stages A/B still **lock pairs at d=3** so they do not pollute public d=0. Among drawing options, pair **d=3 ≥ d=2** for AA and JJ — that chip delta is the number concealment mixes must beat. Two pair **d=1** and trips **d=2** remain the EV maxima. CLI: `analyze-postdraw-nonbluff-ev`. Detail: [../NEXT_STAGE_NONBLUFF_EV.md](../NEXT_STAGE_NONBLUFF_EV.md) and [Ch.3 §3.4](ch03_dealer_opening.md).

---

## 4.2 Stage C (next implementation)

Protect checking ranges by mixing strong finals into checks (not by standing with boats on d=3). Re-run under trips `d=2` (`tp1_tr2_q1`) and trips `d=1` (`tp1_tr1_q1`). Old C numbers used two pair **stand** — do not trust magnitudes. Detail: [../NEXT_STAGE_OPENER_DRAW_MIXES.md](../NEXT_STAGE_OPENER_DRAW_MIXES.md).

---

## 4.3 After C — pair concealment

Non-bluff post-draw EV already ranks pair `d=3` above `d=2` (Ch.3 §3.4). Concealment mixes are still **after C**. Detail: [../NEXT_STAGE_PAIR_CONCEALMENT.md](../NEXT_STAGE_PAIR_CONCEALMENT.md).

---

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/postdraw_draw_mixes.py` | A/B/C ladder |
| `src/fivecarddraw/validation/opener_draw_beliefs.py` | Public-d beliefs (Stage 0) |
| Matching fixtures + tests | CI |
