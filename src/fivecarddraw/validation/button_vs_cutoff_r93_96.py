"""BN fold / call / raise vs CO's chart-threshold opening range.

Frames: ``button_vs_cutoff_r93`` / ``button_vs_cutoff_r96``.
Ticket: docs/NEXT_STAGE_BN_VS_CO_GRID.md. Polar method locked in
``button_vs_cutoff_tight`` (do not restart 0%/100% labs here).

This module owns **only** r ∈ {93, 96}%. Other agents own 79 / 84 / 86 /
87 / 90. Passing any other r raises.

CO never sandbags AA+ / two pair+. JJ/QQ/KK follow the signed open chart:

  - r = 93%: JJ pass; QQ joker only; KK ace or joker
  - r = 96%: JJ pass; QQ joker only; KK joker only
             (same constructed range as the tight polar)

Bug = ace kicker, not a duplicate pair rank. No multi-raise, no live
draw / post-draw Nash. Same locked leaves as the polar labs.
"""

from __future__ import annotations

import json
import math
import os
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import BUG_ID, card_from_id
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_tight import (
    CALL_INVEST,
    DEFAULT_N_HU,
    FOLD_EV,
    FOCUS_ROWS,
    RAISE_INVEST,
    RAISE_POT,
    ev_call_net,
    ev_raise_checkdown,
    recommend_action,
    row_key,
    sample_bn_ids,
)
from fivecarddraw.validation.cutoff_open import (
    _cell_seed,
    _pair_rank_from_class,
    bn_value_continue_as_m2_drawer,
)
from fivecarddraw.validation.cutoff_open_chart import (
    POLICY_ACE_OR_JOKER,
    POLICY_JOKER_ONLY,
    POLICY_OPEN_ALWAYS,
    POLICY_PASS,
)
from fivecarddraw.validation.cutoff_open_sandbag import has_physical_ace
from fivecarddraw.validation.postdraw_betting_m2 import PREDRAW_POT, _one_pair_rank
from fivecarddraw.validation.postdraw_draw_mixes import opener_draw_plan_for_action
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    play_honest_deal,
)
from fivecarddraw.validation.showdown_matrix import (
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    classify_opener,
)


# Grid rows: different seed from the polar tight lab (20260907).
DEFAULT_SEED = 20260909
OWNED_R_PCTS = (93, 96)

# CO pair policies at the integer chart thresholds this module owns.
CHART_PAIR_POLICIES: dict[int, dict[str, str]] = {
    93: {
        "pair_J": POLICY_PASS,
        "pair_Q": POLICY_JOKER_ONLY,
        "pair_K": POLICY_ACE_OR_JOKER,
    },
    96: {
        "pair_J": POLICY_PASS,
        "pair_Q": POLICY_JOKER_ONLY,
        "pair_K": POLICY_JOKER_ONLY,
    },
}

PAIR_POLICY_CLASSES = ("pair_J", "pair_Q", "pair_K")

CHART_CO_BUCKETS = (
    "pair_A",
    "pair_Q_joker",
    "pair_Q_ace",
    "pair_K_joker",
    "pair_K_ace",
    "two_pair",
    "two_pair_aces_up",
    "trips",
    "straight_plus",
)

FRAME_BY_R = {
    93: "button_vs_cutoff_r93",
    96: "button_vs_cutoff_r96",
}

DOC_BY_R = {
    93: "docs/research/button_vs_cutoff_r93.md",
    96: "docs/research/button_vs_cutoff_r96.md",
}


def assert_owned_r(r_pct: int) -> int:
    if r_pct not in CHART_PAIR_POLICIES:
        raise ValueError(
            f"this module owns r in {OWNED_R_PCTS} only; got r={r_pct}. "
            "Do not compute 79/84/86/87/90 here."
        )
    return r_pct


def pair_policies_at(r_pct: int) -> dict[str, str]:
    return dict(CHART_PAIR_POLICIES[assert_owned_r(r_pct)])


def pair_flavor_opens(ids: Sequence[int], policy: str) -> bool:
    """Whether a JJ/QQ/KK five-set opens under a chart pair policy."""
    has_bug = BUG_ID in set(ids)
    ace = has_physical_ace(ids)
    if policy == POLICY_PASS:
        return False
    if policy == POLICY_OPEN_ALWAYS:
        return True
    if policy == POLICY_JOKER_ONLY:
        return has_bug
    if policy == POLICY_ACE_OR_JOKER:
        return has_bug or ace
    raise ValueError(f"unknown pair policy {policy!r}")


def is_always_open_made(opener_class: str | None) -> bool:
    """AA / two pair / trips / boats / straight+ — CO never sandbags these."""
    if opener_class is None:
        return False
    if opener_class == "pair_A":
        return True
    if opener_class in TWO_PAIR_CLASSES:
        return True
    if opener_class in TRIPS_CLASSES:
        return True
    if opener_class in STRAIGHT_PLUS_CLASSES:
        return True
    return False


def is_co_chart_open(
    opener_class: str | None, ids: Sequence[int], r_pct: int
) -> bool:
    """CO opening range at chart threshold ``r_pct`` (93 or 96)."""
    policies = pair_policies_at(r_pct)
    if opener_class is None:
        return False
    if opener_class in PAIR_POLICY_CLASSES:
        return pair_flavor_opens(ids, policies[opener_class])
    return is_always_open_made(opener_class)


def co_chart_bucket(opener_class: str, ids: Sequence[int]) -> str:
    """Mix bucket for a CO five-set that already passed ``is_co_chart_open``."""
    has_bug = BUG_ID in set(ids)
    ace = has_physical_ace(ids)
    if opener_class == "pair_Q":
        if has_bug:
            return "pair_Q_joker"
        if ace:
            return "pair_Q_ace"
        return "pair_Q"
    if opener_class == "pair_K":
        if has_bug:
            return "pair_K_joker"
        if ace:
            return "pair_K_ace"
        return "pair_K"
    if opener_class == "pair_J":
        if has_bug:
            return "pair_J_joker"
        if ace:
            return "pair_J_ace"
        return "pair_J"
    if opener_class == "pair_A":
        return "pair_A"
    if opener_class == "two_pair":
        return "two_pair"
    if opener_class == "two_pair_aces_up":
        return "two_pair_aces_up"
    if opener_class in TRIPS_CLASSES:
        return "trips"
    if opener_class in STRAIGHT_PLUS_CLASSES:
        return "straight_plus"
    raise ValueError(f"not a chart-CO class: {opener_class!r} ids={list(ids)}")


def sample_chart_co_ids(
    rng: random.Random,
    r_pct: int,
    *,
    blocked: set[int],
    tries: int = 400,
) -> tuple[tuple[int, ...], str] | None:
    """Rejection-sample a combo-weighted CO five-set from the remainder."""
    assert_owned_r(r_pct)
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(tries):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = classify_opener(tuple(card_from_id(i) for i in ids))
        if is_co_chart_open(cls, ids, r_pct):
            assert cls is not None
            return ids, cls
    return None


def _se_mean(sum_x: float, sum_x2: float, n: float) -> float:
    if n < 2.0:
        return 0.0
    mean = sum_x / n
    var = max(0.0, (sum_x2 - n * mean * mean) / (n - 1.0))
    return math.sqrt(var / n)


@dataclass(slots=True)
class ChartCellAccum:
    n: float = 0.0
    ev_bn_street: float = 0.0
    ev_bn_street2: float = 0.0
    ev_call: float = 0.0
    ev_call2: float = 0.0
    ev_raise: float = 0.0
    ev_raise2: float = 0.0
    bn_wins: float = 0.0
    ties: float = 0.0
    co_buckets: Counter[str] = field(default_factory=Counter)
    co_has_bug: float = 0.0

    def add_with_ids(self, deal: NonbluffDeal, co_ids: Sequence[int]) -> None:
        ev_co, ev_bn, _flags = play_honest_deal(deal, HONEST_POLICY)
        _ = ev_co
        if deal.drawer_final > deal.opener_final:
            win, tie = 1.0, 0.0
        elif deal.drawer_final == deal.opener_final:
            win, tie = 0.0, 1.0
        else:
            win, tie = 0.0, 0.0
        call_net = ev_call_net(ev_bn)
        raise_net = RAISE_POT * win + (RAISE_POT / 2.0) * tie - RAISE_INVEST
        self.n += 1.0
        self.ev_bn_street += ev_bn
        self.ev_bn_street2 += ev_bn * ev_bn
        self.ev_call += call_net
        self.ev_call2 += call_net * call_net
        self.ev_raise += raise_net
        self.ev_raise2 += raise_net * raise_net
        self.bn_wins += win
        self.ties += tie
        self.co_buckets[co_chart_bucket(deal.opener_class, co_ids)] += 1.0
        if BUG_ID in set(co_ids):
            self.co_has_bug += 1.0

    def as_dict(self) -> dict[str, Any]:
        n = self.n or 1.0
        p_win = self.bn_wins / n
        p_tie = self.ties / n
        ev_call = self.ev_call / n
        ev_raise = self.ev_raise / n
        se_call = _se_mean(self.ev_call, self.ev_call2, self.n)
        se_raise = _se_mean(self.ev_raise, self.ev_raise2, self.n)
        rec = recommend_action(
            ev_call=ev_call,
            ev_raise=ev_raise,
            se_call=se_call,
            se_raise=se_raise,
            p_bn_win=p_win,
        )
        mix = {k: round(self.co_buckets.get(k, 0.0) / n, 5) for k in CHART_CO_BUCKETS}
        return {
            "n": self.n,
            "ev_fold": FOLD_EV,
            "ev_bn_street": round(self.ev_bn_street / n, 5),
            "se_bn_street": round(
                _se_mean(self.ev_bn_street, self.ev_bn_street2, self.n), 5
            ),
            "ev_call": round(ev_call, 5),
            "se_call": round(se_call, 5),
            "ev_raise_checkdown": round(ev_raise, 5),
            "se_raise_checkdown": round(se_raise, 5),
            "p_bn_wins_final": round(p_win, 5),
            "p_tie_final": round(p_tie, 5),
            "p_co_wins_final": round(1.0 - p_win - p_tie, 5),
            "p_co_has_bug": round(self.co_has_bug / n, 5),
            "co_mix": mix,
            "recommend": rec,
        }


def evaluate_deals_with_co_ids(
    deals: Sequence[NonbluffDeal], co_id_rows: Sequence[Sequence[int]]
) -> dict[str, Any]:
    acc = ChartCellAccum()
    for deal, co_ids in zip(deals, co_id_rows, strict=True):
        acc.add_with_ids(deal, co_ids)
    return acc.as_dict()


def generate_bn_vs_chart_co_deals_tracked(
    bn_class: str,
    r_pct: int,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> tuple[list[NonbluffDeal], list[tuple[int, ...]]]:
    """HU: BN class/flavor × chart CO range. CO draws first, then BN."""
    assert_owned_r(r_pct)
    rng = random.Random(seed)
    deals: list[NonbluffDeal] = []
    co_rows: list[tuple[int, ...]] = []
    tries = 0
    cap = max(n_deals * 80, 8_000)
    while len(deals) < n_deals and tries < cap:
        tries += 1
        bn_ids = sample_bn_ids(bn_class, flavor, rng)
        if bn_ids is None:
            continue
        sampled = sample_chart_co_ids(rng, r_pct, blocked=set(bn_ids))
        if sampled is None:
            continue
        co_ids, co_cls = sampled
        left = [i for i in range(53) if i not in bn_ids and i not in co_ids]
        rng.shuffle(left)
        co_cards = tuple(card_from_id(i) for i in co_ids)
        bn_cards = tuple(card_from_id(i) for i in bn_ids)
        co_n = draw_policy.n_draw_for(co_cls)
        bn_n = draw_policy.n_draw_for(bn_class)
        co_plan = opener_draw_plan_for_action(co_cards, co_cls, co_n)
        bn_plan = opener_draw_plan_for_action(bn_cards, bn_class, bn_n)
        need = co_plan.n_draw + bn_plan.n_draw
        if len(left) < need:
            continue
        co_draw = left[: co_plan.n_draw]
        bn_draw = left[co_plan.n_draw : need]
        co_final = evaluate_hand(
            (*co_plan.keep, *(card_from_id(i) for i in co_draw))
        )
        bn_final = evaluate_hand(
            (*bn_plan.keep, *(card_from_id(i) for i in bn_draw))
        )
        sp, face = bn_value_continue_as_m2_drawer(bn_final)
        deals.append(
            NonbluffDeal(
                opener_class=co_cls,
                caller_class=bn_class,
                d=co_plan.n_draw,
                caller_d=bn_plan.n_draw,
                opener_start_pair=_pair_rank_from_class(co_cls),
                opener_final=co_final,
                drawer_final=bn_final,
                opener_final_pair=_one_pair_rank(co_final),
                drawer_final_pair=face,
                drawer_straight_plus=sp,
                opener_two_pair_plus=co_final.category >= HandCategory.TWO_PAIR,
            )
        )
        co_rows.append(co_ids)
    return deals, co_rows


def generate_bn_vs_chart_co_deals(
    bn_class: str,
    r_pct: int,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    deals, _co_rows = generate_bn_vs_chart_co_deals_tracked(
        bn_class,
        r_pct,
        n_deals=n_deals,
        seed=seed,
        flavor=flavor,
        draw_policy=draw_policy,
    )
    return deals


def evaluate_bn_cell(
    bn_class: str,
    flavor: str,
    r_pct: int,
    *,
    n_hu: int,
    seed: int,
) -> dict[str, Any]:
    deals, co_rows = generate_bn_vs_chart_co_deals_tracked(
        bn_class,
        r_pct,
        n_deals=n_hu,
        seed=_cell_seed(seed, "hu", r_pct, bn_class, flavor),
        flavor=flavor,
    )
    stats = evaluate_deals_with_co_ids(deals, co_rows)
    stats["bn_class"] = bn_class
    stats["flavor"] = flavor
    stats["key"] = row_key(bn_class, flavor)
    stats["r_pct"] = r_pct
    stats["seed"] = _cell_seed(seed, "hu", r_pct, bn_class, flavor)
    stats["n_requested"] = n_hu
    stats["locked_draws"] = {
        "name": LOCKED_BN_DRAW.name,
        "bn_d": LOCKED_BN_DRAW.n_draw_for(bn_class),
    }
    return stats


def _cell_job(item: tuple[str, str, int, int, int]) -> dict[str, Any]:
    bn_class, flavor, r_pct, n_hu, seed = item
    return evaluate_bn_cell(bn_class, flavor, r_pct, n_hu=n_hu, seed=seed)


def _co_range_meta(r_pct: int) -> dict[str, Any]:
    policies = pair_policies_at(r_pct)
    include = [
        "pair_A",
        "two_pair",
        "two_pair_aces_up",
        "trips*",
        "straight, flush, full_house, four_of_a_kind, straight_flush, five_aces",
    ]
    exclude = []
    if policies["pair_Q"] == POLICY_JOKER_ONLY:
        include.append("pair_Q with joker")
        exclude.append("pair_Q without joker")
        exclude.append("pair_Q ace kicker without joker")
    if policies["pair_K"] == POLICY_JOKER_ONLY:
        include.append("pair_K with joker")
        exclude.append("pair_K without joker")
        exclude.append("pair_K ace kicker without joker")
    elif policies["pair_K"] == POLICY_ACE_OR_JOKER:
        include.append("pair_K with joker")
        include.append("pair_K with physical ace kicker")
        exclude.append("pair_K without ace or joker")
    if policies["pair_J"] == POLICY_PASS:
        exclude.append("pair_J any kicker")
    return {
        "r_pct": r_pct,
        "pair_policies": policies,
        "include": ", ".join(include),
        "exclude": ", ".join(exclude),
        "sandbag": "CO does not sandbag AA+ / two pair+ — they open them",
        "bug": (
            "Joker is an ace, not trips. QQ+joker = two queens + ace kicker; "
            "KK+joker = two kings + ace kicker. Ace = physical ace kicker."
        ),
        "matches_tight_polar": r_pct == 96,
    }


def derive_answers(rows: list[dict[str, Any]], r_pct: int) -> dict[str, Any]:
    by = {r["key"]: r for r in rows}

    def act(key: str) -> str:
        return by[key]["recommend"]["action"]

    jj = by.get("pair_J")
    qq = by.get("pair_Q")
    kk = by.get("pair_K")
    aa = by.get("pair_A")
    tp = by.get("two_pair")
    au = by.get("two_pair_aces_up")
    tr = by.get("trips")
    tra = by.get("trips_A")
    fold_pairs = [
        k
        for k in ("pair_J", "pair_Q", "pair_K")
        if k in by and by[k]["recommend"]["action"] == "fold"
    ]
    value_raise = [
        k
        for k in ("two_pair_aces_up", "trips", "trips_A")
        if k in by and by[k]["recommend"]["action"] == "raise"
    ]
    flavor_flips = []
    for cls in ("pair_J", "pair_Q", "pair_K"):
        base = by.get(cls)
        if base is None:
            continue
        base_act = base["recommend"]["action"]
        for flav in ("joker", "ace"):
            row = by.get(f"{cls}_{flav}")
            if row is None:
                continue
            if row["recommend"]["action"] != base_act:
                flavor_flips.append(
                    {
                        "class": cls,
                        "flavor": flav,
                        "class_action": base_act,
                        "flavor_action": row["recommend"]["action"],
                        "class_ev_call": base["ev_call"],
                        "flavor_ev_call": row["ev_call"],
                    }
                )
    aa_vs_fold_se = None if aa is None else abs(aa["ev_call"]) / aa["se_call"]
    tp_vs_fold_se = None if tp is None else abs(tp["ev_call"]) / tp["se_call"]
    mix_aa = None if aa is None else aa["co_mix"]
    return {
        "r_pct": r_pct,
        "jj_action": None if jj is None else act("pair_J"),
        "jj_ev_call": None if jj is None else jj["ev_call"],
        "jj_ev_raise_checkdown": None if jj is None else jj["ev_raise_checkdown"],
        "qq_action": None if qq is None else act("pair_Q"),
        "kk_action": None if kk is None else act("pair_K"),
        "aa_action": None if aa is None else act("pair_A"),
        "aa_ev_call": None if aa is None else aa["ev_call"],
        "aa_se_call": None if aa is None else aa["se_call"],
        "aa_p_win": None if aa is None else aa["p_bn_wins_final"],
        "aa_vs_fold_se": None if aa_vs_fold_se is None else round(aa_vs_fold_se, 2),
        "two_pair_action": None if tp is None else act("two_pair"),
        "two_pair_ev_call": None if tp is None else tp["ev_call"],
        "two_pair_se_call": None if tp is None else tp["se_call"],
        "two_pair_p_win": None if tp is None else tp["p_bn_wins_final"],
        "two_pair_vs_fold_se": None if tp_vs_fold_se is None else round(tp_vs_fold_se, 2),
        "two_pair_thin_call": bool(tp)
        and act("two_pair") == "call"
        and tp["p_bn_wins_final"] < 0.5,
        "aces_up_action": None if au is None else act("two_pair_aces_up"),
        "trips_action": None if tr is None else act("trips"),
        "trips_A_action": None if tra is None else act("trips_A"),
        "low_pairs_fold": fold_pairs,
        "value_raise_classes": value_raise,
        "flavor_action_flips": flavor_flips,
        "jj_dominated_raise": bool(jj)
        and jj["p_bn_wins_final"] < 0.5
        and jj["recommend"]["action"] == "fold",
        "aa_closer_to_fold": bool(aa) and aa["recommend"]["action"] == "fold",
        "co_mix_on_aa_row": mix_aa,
        "pair_K_ace_share_on_aa_row": None
        if mix_aa is None
        else mix_aa.get("pair_K_ace", 0.0),
        "pair_K_joker_share_on_aa_row": None
        if mix_aa is None
        else mix_aa.get("pair_K_joker", 0.0),
        "note": (
            f"Fold=0; call=honest $6 street − $2; raise=checkdown $10 − $4 "
            f"(CO always continues). CO range at r={r_pct}% from the signed "
            "open chart. Polar method; not a live Nash."
        ),
    }


def compare_to_tight(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Action / EV deltas vs the signed tight polar fixture. Read-only."""
    from fivecarddraw.validation.button_vs_cutoff_tight import load_summary_fixture

    tight = load_summary_fixture()
    tight_by = {r["key"]: r for r in tight["by_row"]}
    deltas: list[dict[str, Any]] = []
    action_mismatches: list[str] = []
    for row in rows:
        key = row["key"]
        other = tight_by.get(key)
        if other is None:
            continue
        act = row["recommend"]["action"]
        oact = other["recommend"]["action"]
        if act != oact:
            action_mismatches.append(key)
        se = row["se_call"] or 1.0
        deltas.append(
            {
                "key": key,
                "action": act,
                "tight_action": oact,
                "ev_call": row["ev_call"],
                "tight_ev_call": other["ev_call"],
                "delta_ev_call": round(row["ev_call"] - other["ev_call"], 5),
                "delta_ev_call_over_se": round(
                    (row["ev_call"] - other["ev_call"]) / se, 2
                ),
                "p_win": row["p_bn_wins_final"],
                "tight_p_win": other["p_bn_wins_final"],
            }
        )
    return {
        "tight_frame": tight["meta"]["frame"],
        "tight_seed": tight["meta"]["seed"],
        "tight_n_hu": tight["meta"]["n_hu"],
        "action_mismatches": action_mismatches,
        "actions_match_tight": action_mismatches == [],
        "by_key": deltas,
    }


def run_button_vs_cutoff_chart(
    r_pct: int,
    *,
    n_hu: int = DEFAULT_N_HU,
    seed: int = DEFAULT_SEED,
    rows: Sequence[tuple[str, str]] | None = None,
    progress: bool = True,
    workers: int | None = None,
    compare_tight: bool | None = None,
) -> dict[str, Any]:
    assert_owned_r(r_pct)
    use = list(rows) if rows is not None else list(FOCUS_ROWS)
    jobs = [(cls, flav, r_pct, n_hu, seed) for cls, flav in use]
    n_workers = workers if workers is not None else min(len(jobs), os.cpu_count() or 4)
    if progress:
        print(
            f"BN vs CO r={r_pct}%: {len(jobs)} cells, n_hu={n_hu}, "
            f"workers={n_workers}"
        )
    out_rows: list[dict[str, Any]]
    if n_workers <= 1 or len(jobs) == 1:
        out_rows = [_cell_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            out_rows = list(pool.map(_cell_job, jobs))
    by_key = {r["key"]: r for r in out_rows}
    ordered = [by_key[row_key(c, f)] for c, f in use]
    answers = derive_answers(ordered, r_pct)
    do_cmp = compare_tight if compare_tight is not None else (r_pct == 96)
    tight_cmp = compare_to_tight(ordered) if do_cmp else None
    if tight_cmp is not None:
        answers["vs_tight"] = {
            "actions_match_tight": tight_cmp["actions_match_tight"],
            "action_mismatches": tight_cmp["action_mismatches"],
        }
    policies = pair_policies_at(r_pct)
    return {
        "meta": {
            "seed": seed,
            "n_hu": n_hu,
            "r_pct": r_pct,
            "frame": FRAME_BY_R[r_pct],
            "matchup": (
                f"Seats 1–6 passed (sandbag-aware node as needed). CO opens "
                f"the r={r_pct}% chart range (JJ {policies['pair_J']}; "
                f"QQ {policies['pair_Q']}; KK {policies['pair_K']}; "
                "always AA+ / two pair+). BN fold/call/raise vs that range. "
                "No multi-raise tree. Not a restart of the 0%/100% polar labs."
            ),
            "co_range": _co_range_meta(r_pct),
            "accounting": {
                "fold": FOLD_EV,
                "call": "EV_bn_street - $2 (pot $6 into draw, honest policy)",
                "raise_bound": (
                    "checkdown $10 pot − $4; CO always continues "
                    "(no fold equity, no multi-raise)"
                ),
                "call_invest": CALL_INVEST,
                "raise_invest": RAISE_INVEST,
                "raise_pot": RAISE_POT,
                "predraw_pot": PREDRAW_POT,
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
            "doc": DOC_BY_R[r_pct],
            "regenerate": (
                f"analyze-button-vs-cutoff-r{r_pct} --n-hu 4000 --write-fixture"
            ),
            "polar_method": (
                "Same locked leaves as button_vs_cutoff_tight / "
                "button_vs_cutoff_all_legal. This is not a re-run of those "
                "polar fixtures."
            ),
        },
        "by_row": ordered,
        "answers": answers,
        "vs_tight": tight_cmp,
    }


def default_fixture_path(r_pct: int) -> Path:
    assert_owned_r(r_pct)
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / f"button_vs_cutoff_r{r_pct}.json"
    )


def write_summary_fixture(
    payload: dict[str, Any], path: Path | None = None
) -> Path:
    r_pct = int(payload["meta"]["r_pct"])
    path = path or default_fixture_path(r_pct)
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "by_row": payload["by_row"],
        "answers": payload["answers"],
        "vs_tight": payload.get("vs_tight"),
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(r_pct: int, path: Path | None = None) -> dict[str, Any]:
    path = path or default_fixture_path(r_pct)
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    r_pct = meta["r_pct"]
    lines = [
        f"# BN vs CO open at chart r={r_pct}%",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}.",
        "",
        "## Product answers",
        "",
        f"- JJ → **{a['jj_action']}** (call {a['jj_ev_call']:+.3f}, "
        f"raise-cd {a['jj_ev_raise_checkdown']:+.3f})",
        f"- QQ → **{a['qq_action']}**; KK → **{a['kk_action']}**; "
        f"AA → **{a['aa_action']}** (call {a['aa_ev_call']:+.3f} SE "
        f"{a['aa_se_call']:.3f}, {a['aa_vs_fold_se']} SE vs fold)",
        f"- Two pair → **{a['two_pair_action']}** (call {a['two_pair_ev_call']:+.3f} "
        f"SE {a['two_pair_se_call']:.3f}, P(win)={a['two_pair_p_win']:.3f}; "
        f"thin={a['two_pair_thin_call']})",
        f"- Aces-up → **{a['aces_up_action']}**; trips → **{a['trips_action']}**; "
        f"trips_A → **{a['trips_A_action']}**",
        f"- Low pairs that fold: {a['low_pairs_fold'] or 'none'}",
        f"- Value raises: {a['value_raise_classes'] or 'none'}",
        "",
        "## By row",
        "",
        "| BN | flavor | n | EV call (SE) | EV raise-cd (SE) | P(win) | action |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in payload["by_row"]:
        lines.append(
            f"| {r['bn_class']} | {r['flavor']} | {int(r['n'])} | "
            f"{r['ev_call']:+.3f} ({r['se_call']:.3f}) | "
            f"{r['ev_raise_checkdown']:+.3f} ({r['se_raise_checkdown']:.3f}) | "
            f"{r['p_bn_wins_final']:.3f} | {r['recommend']['action']} |"
        )
    lines += ["", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main_for_r(r_pct: int, argv: Sequence[str] | None = None) -> None:
    import argparse

    assert_owned_r(r_pct)
    p = argparse.ArgumentParser(
        description=(
            f"BN fold/call/raise vs CO chart range at r={r_pct}% "
            "(polar method; no multi-raise)"
        )
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args(argv)
    n_hu = 250 if args.quick else args.n_hu
    payload = run_button_vs_cutoff_chart(
        r_pct, n_hu=n_hu, seed=args.seed, progress=True, workers=args.workers
    )
    out = args.output or Path(f"outputs/validation/button_vs_cutoff_r{r_pct}.json")
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
    print(f"Answers r={r_pct}%:")
    print(
        f"  JJ {a['jj_action']}  call={a['jj_ev_call']}  "
        f"raise-cd={a['jj_ev_raise_checkdown']}"
    )
    print(
        f"  QQ {a['qq_action']}  KK {a['kk_action']}  AA {a['aa_action']}  "
        f"call={a['aa_ev_call']} ({a['aa_vs_fold_se']} SE vs fold)"
    )
    print(
        f"  two_pair {a['two_pair_action']}  thin={a['two_pair_thin_call']}  "
        f"call={a['two_pair_ev_call']} ({a['two_pair_vs_fold_se']} SE vs fold)  "
        f"aces-up {a['aces_up_action']}  trips {a['trips_action']}"
    )
    if payload.get("vs_tight"):
        vt = payload["vs_tight"]
        print(
            f"  vs tight polar: actions_match={vt['actions_match_tight']} "
            f"mismatches={vt['action_mismatches']}"
        )
    for r in payload["by_row"]:
        rec = r["recommend"]["action"]
        print(
            f"  {r['key']:<22} {rec:<6} call={r['ev_call']:+.3f} "
            f"({r['se_call']:.3f})  raise={r['ev_raise_checkdown']:+.3f} "
            f"({r['se_raise_checkdown']:.3f})  p_win={r['p_bn_wins_final']:.3f}"
        )


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="BN vs CO chart range (owned rows r=93 and r=96 only)"
    )
    p.add_argument("--r", type=int, required=True, choices=list(OWNED_R_PCTS))
    args, rest = p.parse_known_args()
    main_for_r(args.r, argv=rest)


if __name__ == "__main__":
    main()
