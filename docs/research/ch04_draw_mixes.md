# Chapter 4 — Opener draw mixes and range protection

> Seat map and solve-progress ledger: **[INDEX.md](INDEX.md)**.

**Ledger role.** Continues the **BN vs 2:1 drawer** laboratory: public draw counts and check mixes that protect weak `d=3` pair lines.

---

## 4.1 Locked draw defaults (post Stage B)

| Class | Draw | Note |
| --- | --- | --- |
| Pair JJ–AA | **d=3** | Best improvement among pair options studied |
| Two pair | **d=1** | Dominant +EV lever in the 12-cell grid |
| Quads | **d=1** | EV-neutral vs stand; pollutes public d=1 |
| Other straight+ | Stand | Cannot join d=3 to “protect” pairs |
| Trips | **d=2** (primary) or **d=1** (unified) | Live fork. `d=1` keep is highest-rank kicker (v1 pin); lowest / non-face kicker is a later EV question |

Non-bluff **post-draw EV** (honest betting, not just P(win)) is more subtle than Stage A’s improvement tables: **standing** is the chip-max non-bluff line for pairs (drawing three raises P(win) but the extra two pair+ auto-bets pay off ~34% straight+). Stages A/B still **lock pairs at d=3** so they do not pollute public d=0. Among drawing options, pair **d=3 ≥ d=2** for AA and JJ — that chip delta is the number concealment mixes must beat. Two pair **d=1** and trips **d=2** remain the EV maxima. CLI: `analyze-postdraw-nonbluff-ev`. Detail: [../NEXT_STAGE_NONBLUFF_EV.md](../NEXT_STAGE_NONBLUFF_EV.md) and [Ch.3 §3.4](ch03_dealer_opening.md).

---

## 4.2 Stage C — checking-range protection (done)

Protect checking ranges by mixing strong finals into checks, not by standing with boats on d=3. Re-run under trips `d=2` (`tp1_tr2_q1`) and trips `d=1` (`tp1_tr1_q1`). Street is still M2 (bet + at most one raise). Mixes are keyed by public `d`.

**Result (n = 20,000, seed 20260809).** Both forks agree: **always check two pair** (all public `d`); always bet trips and boat+. Vs drawer AA face-stab, never raise:

| Policy (C-primary) | Opener EV | Drawer stab Δ |
| --- | ---: | ---: |
| Always bet two pair+ | 2.781 | −0.419 |
| Check 30% of two pair | 2.893 | −1.092 |
| Check 100% of two pair | **3.147** | **−2.003** |

C-unified baseline EV 2.766 / best 3.133; same mix. Vs AA+KK, baseline drawer Δ **+0.70** flips to **−1.38** when all two pair checks.

Two pair also appears on public `d=3` (pair improvements), so a global two-pair check beats a `d=1`-only override. Detail: [../NEXT_STAGE_OPENER_DRAW_MIXES.md](../NEXT_STAGE_OPENER_DRAW_MIXES.md).

**Cap / 3-bet follow-on.** Checking two pair means those hands never face a caller raise, so they are not 3-bet bluff candidates. The pre-C cap node (two pair+ bets ∩ caller straight+) and the pooled “fold all flushes” BR are stale. Next: [../NEXT_STAGE_POSTDRAW_BLUFF.md](../NEXT_STAGE_POSTDRAW_BLUFF.md).

---

## 4.3 After C — pair concealment

Non-bluff post-draw EV already ranks pair `d=3` above `d=2` (Ch.3 §3.4). Concealment mixes still wait on a dedicated `d=3` vs `d=2` EV confirm. Detail: [../NEXT_STAGE_PAIR_CONCEALMENT.md](../NEXT_STAGE_PAIR_CONCEALMENT.md).

---

## Code ownership (for parallel agents)

| Path | Role |
| --- | --- |
| `src/fivecarddraw/validation/postdraw_draw_mixes.py` | A/B/C ladder |
| `src/fivecarddraw/validation/opener_draw_beliefs.py` | Public-d beliefs (Stage 0) |
| Matching fixtures + tests | CI |
