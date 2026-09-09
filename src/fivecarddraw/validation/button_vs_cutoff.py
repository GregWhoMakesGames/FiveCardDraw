"""Button fold / call / raise vs a cutoff that opens every legal hand.

Frame: ``button_vs_cutoff_all_legal``
(docs/research/button_vs_cutoff_all_legal.md).

Laboratory (range 1 only — do not compute a tight CO range here):

- Seats 1–6 unable (folded-to-CO node from the 0% sandbag lab).
- CO (seat 7) opens **100% of legal hands** (jacks-or-better). Signed pin:
  ``cutoff_open_no_sandbagging``. CO does **not** sandbag.
- BN (seat 8) is next. Rough fold / call / raise — **not** a raise tree,
  live draw solver, or post-draw Nash.

Accounting at BN's decision (antes already in):

- Fold / pass = **0** (sunk $2 ante pot; CO takes it if BN folds).
- CO open makes the pot $4; BN calls $2 (pot $6 into draw) or raises.
- Raise bound: CO's range is 100% jacks+, so there is **no junk / air**
  to fold out. CO always continues (calls the raise). Check down a $10
  pot (BN invested $4). Fold equity vs air is identically 0.

Locked leaves: ``tp1_tr2_q1`` draws + honest non-bluff post-draw on the
**call** line (same HU cells as ``cutoff_open``). Bug = ace / fill, not a
third rank (KK+joker is pair of kings + ace kicker).
"""

from __future__ import annotations

import json
import math
import random
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import card_from_id
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.cutoff_open import (
    bn_value_continue_as_m2_drawer,
    sample_class_ids,
    sample_open_legal_ids,
)
from fivecarddraw.validation.draw_call_odds import DrawHandResult
from fivecarddraw.validation.postdraw_betting_m2 import (
    ANTE_POT,
    PREDRAW_POT,
    _face_pair_rank,
    _one_pair_rank,
    _sample_disjoint_caller,
)
from fivecarddraw.validation.postdraw_draw_mixes import opener_draw_plan_for_action
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    play_honest_deal,
)
from fivecarddraw.validation.showdown_matrix import (
    OPENER_CLASSES,
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    classify_opener,
    load_call_2to1_hands,
)


DEFAULT_SEED = 20260908
DEFAULT_N_HU = 4_000
DEFAULT_N_2TO1 = 2_000

FOLD_EV = 0.0
BN_CALL_INVEST = 2.0
BN_RAISE_INVEST = 4.0
CALL_POT = PREDRAW_POT  # $6 = $2 antes + $2 CO + $2 BN
RAISE_POT = ANTE_POT + 2.0 * BN_RAISE_INVEST  # $10 = $2 + $4 CO + $4 BN
CO_P_FOLD_AIR = 0.0  # range is 100% legal
CLOSE_SE = 2.0

CO_SEAT = 7
BN_SEAT = 8

# Product chart rows. ``trips_plus`` = trips / trips_K / trips_A / straight+.
# ``two_to_one`` is the Ch.2 2:1 drawing set (optional cheap bound).
MADE_SPECS = (
    "pair_J",
    "pair_Q",
    "pair_K",
    "pair_A",
    "two_pair",
    "two_pair_aces_up",
    "trips_plus",
)
DRAW_SPEC = "two_to_one"
FOCUS_SPECS = MADE_SPECS + (DRAW_SPEC,)

TRIPS_PLUS_CLASSES = TRIPS_CLASSES + STRAIGHT_PLUS_CLASSES


def _cell_seed(base: int, *parts: object) -> int:
    payload = "|".join(str(p) for p in parts)
    return (base + (zlib.adler32(payload.encode("utf-8")) % 1_000_003)) % (2**31)


def _pair_rank_from_class(cls: str) -> int | None:
    return {"pair_J": 11, "pair_Q": 12, "pair_K": 13, "pair_A": 14}.get(cls)


def mean_se(xs: Sequence[float]) -> tuple[float, float]:
    """Sample mean and SE of the mean (sd / sqrt(n))."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var / n)


def checkdown_ev_bn(*, won: bool, tied: bool, pot: float) -> float:
    if won:
        return pot
    if tied:
        return pot / 2.0
    return 0.0


def decide_action(
    *,
    ev_call_honest: float,
    se_call_honest: float,
    ev_call_cd: float,
    se_call_cd: float,
    ev_raise_cd: float,
    se_raise_cd: float,
    se_raise_minus_call_cd: float,
) -> dict[str, Any]:
    """Rough chart: fold vs honest $6 call; raise vs call on matching checkdowns.

    Honest call includes post-draw on the $6 leaf (pairs pay off CO two pair+;
    monsters stab). Raise-checkdown has no post-draw, so comparing it to honest
    call would make trips+ look like a call. Raise vs call therefore uses
    checkdown vs checkdown (no fold equity vs air — CO is 100% legal).
    """
    close_call_fold = abs(ev_call_honest) <= CLOSE_SE * se_call_honest
    close_raise_fold = abs(ev_raise_cd) <= CLOSE_SE * se_raise_cd
    close_raise_call = (
        abs(ev_raise_cd - ev_call_cd) <= CLOSE_SE * se_raise_minus_call_cd
    )
    close_call_cd_fold = abs(ev_call_cd) <= CLOSE_SE * se_call_cd

    if ev_call_honest <= 0.0 and ev_raise_cd <= 0.0:
        action = "fold"
        reason = "honest $6 call and raise-checkdown both ≤ 0 vs fold"
    elif ev_raise_cd > ev_call_cd and (ev_raise_cd > 0.0 or ev_call_honest > 0.0):
        action = "raise"
        reason = (
            "checkdown raise beats checkdown call (P(win) ≳ 1/2) with CO "
            "always continuing; value/protection vs jacks+, not a bluff"
        )
    elif ev_call_honest > 0.0:
        action = "call"
        reason = "honest $6 call is +EV; checkdown does not justify a value raise"
    else:
        action = "fold"
        reason = "honest call ≤ 0; raise-cd not clearly better than calling"

    needs_later = False
    later_note = ""
    if action == "fold" and (close_call_fold or close_raise_fold or close_call_cd_fold):
        needs_later = True
        later_note = (
            "close to call/raise within 2 SE; multi-raise or draw work may move it"
        )
    elif action == "call" and close_raise_call:
        needs_later = True
        later_note = (
            "raise vs call is within 2 SE on checkdown; $10 post-draw / CO "
            "folding a legal hand is later work"
        )
    elif action == "raise" and close_raise_call:
        needs_later = True
        later_note = "raise-cd only barely beats call-cd; confirm with a raise tree"
    elif action == "call" and close_call_fold:
        needs_later = True
        later_note = "honest call is within 2 SE of 0; fold remains live"

    return {
        "action": action,
        "reason": reason,
        "close_call_vs_fold": close_call_fold,
        "close_raise_vs_fold": close_raise_fold,
        "close_raise_vs_call": close_raise_call,
        "needs_later_tree": needs_later,
        "later_note": later_note,
    }


def sample_trips_plus_ids(
    rng: random.Random, *, blocked: set[int] | None = None
) -> tuple[tuple[int, ...], str] | None:
    blocked = blocked or set()
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    plus = set(TRIPS_PLUS_CLASSES)
    for _ in range(8_000):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = classify_opener(tuple(card_from_id(i) for i in ids))
        if cls in plus:
            return ids, cls
    return None


def sample_bn_hand(
    spec: str, rng: random.Random, *, blocked: set[int] | None = None
) -> tuple[tuple[int, ...], str] | None:
    """Return ``(ids, fine_class)`` for a BN chart spec."""
    if spec == "trips_plus":
        return sample_trips_plus_ids(rng, blocked=blocked)
    if spec in OPENER_CLASSES:
        ids = sample_class_ids(spec, rng, blocked=blocked)
        if ids is None:
            return None
        return ids, spec
    raise ValueError(f"unknown BN spec {spec!r}")


def _deal_from_ids(
    *,
    co_ids: Sequence[int],
    co_cls: str,
    bn_ids: Sequence[int],
    bn_cls: str,
    rem: list[int],
    draw_policy=LOCKED_BN_DRAW,
    bn_is_2to1: bool = False,
    bn_keep: Sequence | None = None,
) -> NonbluffDeal:
    co_cards = tuple(card_from_id(i) for i in co_ids)
    bn_cards = tuple(card_from_id(i) for i in bn_ids)
    co_n = draw_policy.n_draw_for(co_cls)
    co_plan = opener_draw_plan_for_action(co_cards, co_cls, co_n)
    if bn_is_2to1:
        bn_n = 1
        keep = tuple(bn_keep) if bn_keep is not None else bn_cards[:4]
    else:
        bn_n = draw_policy.n_draw_for(bn_cls)
        bn_plan = opener_draw_plan_for_action(bn_cards, bn_cls, bn_n)
        keep = bn_plan.keep
        bn_n = bn_plan.n_draw
    need = co_plan.n_draw + bn_n
    if len(rem) < need:
        raise ValueError("not enough cards to draw")
    # CO opened: draws first (left of dealer). BN last.
    co_draw = rem[: co_plan.n_draw]
    bn_draw = rem[co_plan.n_draw : need]
    co_final = evaluate_hand((*co_plan.keep, *(card_from_id(i) for i in co_draw)))
    bn_final = evaluate_hand((*keep, *(card_from_id(i) for i in bn_draw)))
    if bn_is_2to1:
        face = _face_pair_rank(bn_final)
        sp = bn_final.category >= HandCategory.STRAIGHT
        caller_class = "all_2to1"
    else:
        sp, face = bn_value_continue_as_m2_drawer(bn_final)
        caller_class = bn_cls
    return NonbluffDeal(
        opener_class=co_cls,
        caller_class=caller_class,
        d=co_plan.n_draw,
        caller_d=bn_n,
        opener_start_pair=_pair_rank_from_class(co_cls),
        opener_final=co_final,
        drawer_final=bn_final,
        opener_final_pair=_one_pair_rank(co_final),
        drawer_final_pair=face,
        drawer_straight_plus=sp,
        opener_two_pair_plus=co_final.category >= HandCategory.TWO_PAIR,
    )


def generate_bn_vs_co_legal_deals(
    spec: str,
    *,
    n_deals: int,
    seed: int,
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    """HU: BN ``spec`` × CO all-legal. CO draws first, then BN."""
    rng = random.Random(seed)
    deals: list[NonbluffDeal] = []
    tries = 0
    while len(deals) < n_deals and tries < n_deals * 80:
        tries += 1
        sampled = sample_bn_hand(spec, rng)
        if sampled is None:
            continue
        bn_ids, bn_cls = sampled
        co = sample_open_legal_ids(rng, blocked=set(bn_ids))
        if co is None:
            continue
        co_ids, co_cls = co
        left = [i for i in range(53) if i not in bn_ids and i not in co_ids]
        rng.shuffle(left)
        try:
            deals.append(
                _deal_from_ids(
                    co_ids=co_ids,
                    co_cls=co_cls,
                    bn_ids=bn_ids,
                    bn_cls=bn_cls,
                    rem=left,
                    draw_policy=draw_policy,
                )
            )
        except ValueError:
            continue
    return deals


def generate_bn_2to1_vs_co_legal_deals(
    callers: Sequence[DrawHandResult],
    *,
    n_deals: int,
    seed: int,
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    """BN is a 2:1 keep-4 caller; CO is a uniform legal opener."""
    rng = random.Random(seed)
    deals: list[NonbluffDeal] = []
    tries = 0
    while len(deals) < n_deals and tries < n_deals * 80:
        tries += 1
        co = sample_open_legal_ids(rng, blocked=set())
        if co is None:
            continue
        co_ids, co_cls = co
        caller = _sample_disjoint_caller(callers, set(co_ids), rng)
        if caller is None:
            continue
        bn_ids = tuple(sorted(c.card_id for c in caller.cards))
        left = [
            i
            for i in range(53)
            if i not in co_ids and i not in bn_ids
        ]
        rng.shuffle(left)
        try:
            deals.append(
                _deal_from_ids(
                    co_ids=co_ids,
                    co_cls=co_cls,
                    bn_ids=bn_ids,
                    bn_cls="all_2to1",
                    rem=left,
                    draw_policy=draw_policy,
                    bn_is_2to1=True,
                    bn_keep=caller.keep,
                )
            )
        except ValueError:
            continue
    return deals


@dataclass(slots=True)
class SpecAccum:
    n: float = 0.0
    call_honest_xs: list[float] = field(default_factory=list)
    call_cd_xs: list[float] = field(default_factory=list)
    raise_xs: list[float] = field(default_factory=list)
    diff_cd_xs: list[float] = field(default_factory=list)
    wins: float = 0.0
    ties: float = 0.0
    co_classes: Counter[str] = field(default_factory=Counter)
    bn_classes: Counter[str] = field(default_factory=Counter)
    street_bn_xs: list[float] = field(default_factory=list)

    def add(self, deal: NonbluffDeal) -> None:
        ev_co, ev_bn, _flags = play_honest_deal(deal, HONEST_POLICY)
        # ev_co + ev_bn = PREDRAW_POT (net from post-draw start).
        _ = ev_co
        won = deal.drawer_final > deal.opener_final
        tied = deal.drawer_final == deal.opener_final
        ev_call_honest = ev_bn - BN_CALL_INVEST
        ev_call_cd = (
            checkdown_ev_bn(won=won, tied=tied, pot=CALL_POT) - BN_CALL_INVEST
        )
        ev_raise = checkdown_ev_bn(won=won, tied=tied, pot=RAISE_POT) - BN_RAISE_INVEST
        self.n += 1.0
        self.call_honest_xs.append(ev_call_honest)
        self.call_cd_xs.append(ev_call_cd)
        self.raise_xs.append(ev_raise)
        self.diff_cd_xs.append(ev_raise - ev_call_cd)
        self.street_bn_xs.append(ev_bn)
        if won:
            self.wins += 1.0
        elif tied:
            self.ties += 1.0
        self.co_classes[deal.opener_class] += 1
        self.bn_classes[deal.caller_class] += 1

    def as_dict(self) -> dict[str, Any]:
        n = int(self.n) or 1
        ev_call, se_call = mean_se(self.call_honest_xs)
        ev_call_cd, se_call_cd = mean_se(self.call_cd_xs)
        ev_raise, se_raise = mean_se(self.raise_xs)
        ev_diff, se_diff = mean_se(self.diff_cd_xs)
        ev_street, se_street = mean_se(self.street_bn_xs)
        p_win = self.wins / n
        p_tie = self.ties / n
        decision = decide_action(
            ev_call_honest=ev_call,
            se_call_honest=se_call,
            ev_call_cd=ev_call_cd,
            se_call_cd=se_call_cd,
            ev_raise_cd=ev_raise,
            se_raise_cd=se_raise,
            se_raise_minus_call_cd=se_diff,
        )
        return {
            "n": float(n),
            "ev_fold": FOLD_EV,
            "ev_call": round(ev_call, 5),
            "se_call": round(se_call, 5),
            "ev_call_checkdown": round(ev_call_cd, 5),
            "se_call_checkdown": round(se_call_cd, 5),
            "ev_raise_checkdown": round(ev_raise, 5),
            "se_raise_checkdown": round(se_raise, 5),
            "ev_raise_minus_call_cd": round(ev_diff, 5),
            "se_raise_minus_call_cd": round(se_diff, 5),
            "ev_street_bn": round(ev_street, 5),
            "se_street_bn": round(se_street, 5),
            "p_bn_wins_final": round(p_win, 5),
            "p_tie_final": round(p_tie, 5),
            "p_co_wins_final": round((n - self.wins - self.ties) / n, 5),
            "p_co_folds_air": CO_P_FOLD_AIR,
            "co_class_mix": {
                k: round(v / n, 5) for k, v in self.co_classes.most_common()
            },
            "bn_class_mix": {
                k: round(v / n, 5) for k, v in self.bn_classes.most_common()
            },
            **decision,
        }


def evaluate_deals(deals: Sequence[NonbluffDeal]) -> dict[str, Any]:
    acc = SpecAccum()
    for deal in deals:
        acc.add(deal)
    return acc.as_dict()


def evaluate_bn_spec(
    spec: str,
    *,
    n_deals: int,
    seed: int,
    callers: Sequence[DrawHandResult] | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    if progress:
        print(f"  {spec}: n={n_deals}…")
    if spec == DRAW_SPEC:
        if not callers:
            raise ValueError("two_to_one requires loaded 2:1 callers")
        deals = generate_bn_2to1_vs_co_legal_deals(
            callers, n_deals=n_deals, seed=seed
        )
    else:
        deals = generate_bn_vs_co_legal_deals(spec, n_deals=n_deals, seed=seed)
    row = evaluate_deals(deals)
    row["bn_spec"] = spec
    row["seed"] = seed
    row["kind"] = "draw_2to1" if spec == DRAW_SPEC else "made"
    return row


def derive_answers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = {r["bn_spec"]: r for r in rows}
    chart = {spec: by[spec]["action"] for spec in by}
    fold_equity_note = (
        "CO opens 100% of legal hands (no junk). A BN raise has no fold "
        "equity vs air; raise is a value/protection question vs jacks+."
    )
    close = [r["bn_spec"] for r in rows if r.get("needs_later_tree")]
    made_fold = [r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "fold"]
    made_call = [r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "call"]
    made_raise = [r["bn_spec"] for r in rows if r["kind"] == "made" and r["action"] == "raise"]
    return {
        "fold_equity_vs_air": 0.0,
        "fold_equity_note": fold_equity_note,
        "chart": chart,
        "made_fold": made_fold,
        "made_call": made_call,
        "made_raise": made_raise,
        "close_or_needs_later": close,
        "pair_J_action": None if "pair_J" not in by else by["pair_J"]["action"],
        "pair_J_ev_call": None if "pair_J" not in by else by["pair_J"]["ev_call"],
        "pair_A_action": None if "pair_A" not in by else by["pair_A"]["action"],
        "two_pair_action": None if "two_pair" not in by else by["two_pair"]["action"],
        "trips_plus_action": None if "trips_plus" not in by else by["trips_plus"]["action"],
        "two_to_one_action": None if "two_to_one" not in by else by["two_to_one"]["action"],
    }


def run_button_vs_cutoff(
    *,
    n_hu: int = DEFAULT_N_HU,
    n_2to1: int = DEFAULT_N_2TO1,
    seed: int = DEFAULT_SEED,
    specs: Sequence[str] | None = None,
    progress: bool = True,
    callers: Sequence[DrawHandResult] | None = None,
    include_draws: bool = True,
) -> dict[str, Any]:
    use = list(specs) if specs else list(FOCUS_SPECS)
    if not include_draws:
        use = [s for s in use if s != DRAW_SPEC]
    need_draws = DRAW_SPEC in use
    if need_draws and callers is None:
        if progress:
            print("Loading 2:1 callers…")
        callers = load_call_2to1_hands(progress=progress)
    rows: list[dict[str, Any]] = []
    for spec in use:
        n = n_2to1 if spec == DRAW_SPEC else n_hu
        rows.append(
            evaluate_bn_spec(
                spec,
                n_deals=n,
                seed=_cell_seed(seed, spec),
                callers=callers,
                progress=progress,
            )
        )
    answers = derive_answers(rows)
    return {
        "meta": {
            "seed": seed,
            "n_hu": n_hu,
            "n_2to1": n_2to1,
            "frame": "button_vs_cutoff_all_legal",
            "co_range": "cutoff_open_no_sandbagging (open 100% legal; no sandbag)",
            "matchup": (
                "Seats 1–6 unable. CO opens every legal hand. BN fold / call / "
                "raise vs that open. Raise: CO always continues (no air)."
            ),
            "accounting": {
                "fold": FOLD_EV,
                "antes_already_in": ANTE_POT,
                "co_open_pot": ANTE_POT + BN_CALL_INVEST,
                "call_invest": BN_CALL_INVEST,
                "call_pot": CALL_POT,
                "call_net": "EV_street_bn - $2 (honest $6 leaf)",
                "call_checkdown_net": "checkdown $6 - $2 (fair vs raise-cd)",
                "raise_invest": BN_RAISE_INVEST,
                "raise_pot": RAISE_POT,
                "raise_net": "checkdown $10 - $4; CO always calls",
                "p_co_folds_air": CO_P_FOLD_AIR,
            },
            "draw_order": "CO first, then BN (BN last)",
            "locked_draws": {
                "name": LOCKED_BN_DRAW.name,
                "pair_d": LOCKED_BN_DRAW.pair_d,
                "two_pair_d": LOCKED_BN_DRAW.two_pair_d,
                "trips_d": LOCKED_BN_DRAW.trips_d,
                "quads_d": LOCKED_BN_DRAW.quads_d,
            },
            "honest_policy": HONEST_POLICY.key,
            "bug": "ace or straight/flush fill; not a third rank (KK+joker = pair_K)",
            "out_of_scope": [
                "tight CO range (AA+ / QQ-KK+joker) — other agent",
                "CO open/slowplay product chart",
                "multi-raise Nash",
                "live draw solver / post-draw Nash",
            ],
            "doc": "docs/research/button_vs_cutoff_all_legal.md",
            "regenerate": (
                "python -m fivecarddraw.validation.button_vs_cutoff "
                "--n-hu 4000 --n-2to1 2000 --write-fixture"
            ),
            "parent_frame": "cutoff_open_no_sandbagging",
        },
        "by_spec": rows,
        "answers": answers,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "button_vs_cutoff_all_legal.json"
    )


def write_summary_fixture(payload: dict[str, Any], path: Path | None = None) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "by_spec": payload["by_spec"],
        "answers": payload["answers"],
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    lines = [
        "# Button vs cutoff, all-legal CO open",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}, n_2to1={meta['n_2to1']}.",
        "",
        a["fold_equity_note"],
        "",
        f"Chart: `{a['chart']}`",
        "",
        "| BN spec | action | EV fold | EV call honest (SE) | EV call-cd | EV raise-cd (SE) | P(win) | later? |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in payload["by_spec"]:
        later = "yes" if r.get("needs_later_tree") else "no"
        lines.append(
            f"| {r['bn_spec']} | **{r['action']}** | {r['ev_fold']:+.2f} | "
            f"{r['ev_call']:+.3f} ({r['se_call']:.3f}) | "
            f"{r.get('ev_call_checkdown', 0):+.3f} | "
            f"{r['ev_raise_checkdown']:+.3f} ({r['se_raise_checkdown']:.3f}) | "
            f"{r['p_bn_wins_final']:.3f} | {later} |"
        )
    lines += ["", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "BN fold/call/raise vs CO opening every legal hand "
            "(range 1; no sandbag; no raise tree)"
        )
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--n-2to1", type=int, default=DEFAULT_N_2TO1)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--no-draws", action="store_true")
    p.add_argument(
        "--specs",
        type=str,
        default=None,
        help="Comma-separated BN specs (default: pairs, two_pair, trips_plus, 2:1)",
    )
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_hu, n_2to1 = args.n_hu, args.n_2to1
    if args.quick:
        n_hu, n_2to1 = 250, 150
    specs = (
        [c.strip() for c in args.specs.split(",") if c.strip()]
        if args.specs
        else None
    )
    payload = run_button_vs_cutoff(
        n_hu=n_hu,
        n_2to1=n_2to1,
        seed=args.seed,
        specs=specs,
        progress=True,
        include_draws=not args.no_draws,
    )
    out = args.output or Path("outputs/validation/button_vs_cutoff_all_legal.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    md = out.with_suffix(".md")
    write_markdown_summary(payload, md)
    print(f"Wrote {md}")
    if args.write_fixture:
        fix = write_summary_fixture(payload)
        print(f"Wrote fixture {fix}")
    a = payload["answers"]
    print()
    print("Chart:", a["chart"])
    print(a["fold_equity_note"])
    for r in payload["by_spec"]:
        flag = "  [close]" if r.get("needs_later_tree") else ""
        print(
            f"  {r['bn_spec']:<18} {r['action']:<6}  "
            f"call={r['ev_call']:+.3f}±{r['se_call']:.3f}  "
            f"call_cd={r.get('ev_call_checkdown', 0):+.3f}  "
            f"raise={r['ev_raise_checkdown']:+.3f}±{r['se_raise_checkdown']:.3f}  "
            f"p_win={r['p_bn_wins_final']:.3f}{flag}"
        )


if __name__ == "__main__":
    main()
