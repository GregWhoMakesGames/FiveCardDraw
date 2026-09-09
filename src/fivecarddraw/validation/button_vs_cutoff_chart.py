"""BN fold / call / raise vs CO at open-chart thresholds r = 87% and 90%.

Frames: ``button_vs_cutoff_r87`` / ``button_vs_cutoff_r90``
(docs/research/button_vs_cutoff_r87.md, button_vs_cutoff_r90.md).

This module owns **only** those two interior rows of
``docs/NEXT_STAGE_BN_VS_CO_GRID.md``. Other agents own 79 / 84 / 86 / 93 / 96.
Do **not** restart the polar 0% (all-legal) or ~100% (tight) labs from here.

Laboratory (same locked leaves as the polar BN-vs-CO labs):

- Seats 1–6 passed (sandbag-aware node as needed).
- CO (seat 7) never sandbags AA+ / two pair+. Joker = ace kicker, not trips.
- JJ / QQ / KK flavors follow the signed cutoff chart at that integer r.
- BN (seat 8) fold / call / raise vs that constructed range.
- No multi-raise tree, no live draw solver, no post-draw Nash.

Accounting (BN decision; ante sunk, fold = 0): fold 0; call = honest $6
street − $2; raise bound = checkdown $10 − $4 (CO always continues).

Draws: locked ``tp1_tr2_q1``. CO draws first, then BN. Action rule is the
tight polar's ``recommend_action`` (value-raise iff P(win) > 0.5 and
raise-cd +EV).
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

from fivecarddraw.cards import BUG_ID, card_from_id, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.button_vs_cutoff_tight import (
    CALL_INVEST,
    FOCUS_ROWS,
    FOLD_EV,
    RAISE_INVEST,
    RAISE_POT,
    ev_call_net,
    recommend_action,
    row_key,
    sample_bn_ids,
)
from fivecarddraw.validation.cutoff_open import (
    _cell_seed,
    _pair_rank_from_class,
    bn_value_continue_as_m2_drawer,
)
from fivecarddraw.validation.cutoff_open_sandbag import has_physical_ace
from fivecarddraw.validation.postdraw_betting_m2 import (
    PREDRAW_POT,
    _one_pair_rank,
)
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


DEFAULT_SEED = 20260909
DEFAULT_N_HU = 4_000
OWNED_RATES = (87, 90)

POLICY_PASS = "pass"
POLICY_JOKER_ONLY = "joker_only"
POLICY_ACE_OR_JOKER = "ace_or_joker"
POLICY_OPEN = "open"
FACE_PAIR_CLASSES = ("pair_J", "pair_Q", "pair_K")

# Hands used to pin the chart predicates (bug = ace kicker, not trips).
PAIR_J_JOKER = parse_hand("Jh Jd Bu 9s 7h")
PAIR_J_ACE = parse_hand("Jh Jd As 9s 7h")
PAIR_J_BARE = parse_hand("Jh Jd 9s 7h 4c")
PAIR_Q_JOKER = parse_hand("Qh Qd Bu 9s 7h")
PAIR_Q_ACE = parse_hand("Qh Qd As 9s 7h")
PAIR_Q_BARE = parse_hand("Qh Qd 9s 7h 4c")
PAIR_K_JOKER = parse_hand("Kh Kd Bu 9s 7h")
PAIR_K_ACE = parse_hand("Kh Kd As 9s 7h")
PAIR_K_BARE = parse_hand("Kh Kd 9s 7h 4c")

CHART_CO_BUCKETS = (
    "pair_J_joker",
    "pair_J_ace",
    "pair_Q_joker",
    "pair_Q_ace",
    "pair_K_joker",
    "pair_K_ace",
    "pair_A",
    "two_pair",
    "two_pair_aces_up",
    "trips",
    "straight_plus",
)


@dataclass(frozen=True, slots=True)
class CoRangeSpec:
    """CO opening range at one integer chart threshold (JJ/QQ/KK flavors)."""

    r_pct: int
    pair_J: str
    pair_Q: str
    pair_K: str

    @property
    def frame(self) -> str:
        return f"button_vs_cutoff_r{self.r_pct}"

    @property
    def policies(self) -> dict[str, str]:
        return {
            "pair_J": self.pair_J,
            "pair_Q": self.pair_Q,
            "pair_K": self.pair_K,
        }

    def policy_for(self, opener_class: str) -> str:
        if opener_class == "pair_J":
            return self.pair_J
        if opener_class == "pair_Q":
            return self.pair_Q
        if opener_class == "pair_K":
            return self.pair_K
        raise KeyError(opener_class)


# Signed chart rows this agent owns. AA+ / two pair+ always open.
RANGE_R87 = CoRangeSpec(
    r_pct=87,
    pair_J=POLICY_JOKER_ONLY,
    pair_Q=POLICY_ACE_OR_JOKER,
    pair_K=POLICY_ACE_OR_JOKER,
)
RANGE_R90 = CoRangeSpec(
    r_pct=90,
    pair_J=POLICY_JOKER_ONLY,
    pair_Q=POLICY_JOKER_ONLY,
    pair_K=POLICY_ACE_OR_JOKER,
)
RANGES: dict[int, CoRangeSpec] = {87: RANGE_R87, 90: RANGE_R90}


def spec_for(r_pct: int) -> CoRangeSpec:
    try:
        return RANGES[r_pct]
    except KeyError as exc:
        owned = ", ".join(str(r) for r in OWNED_RATES)
        raise ValueError(
            f"r={r_pct}% is not owned by this module (owned: {owned})"
        ) from exc


def frame_for(r_pct: int) -> str:
    return spec_for(r_pct).frame


def flavor_matches_policy(ids: Sequence[int], policy: str) -> bool:
    """Whether a *already classified* face pair is in-range under ``policy``."""
    if policy == POLICY_PASS:
        return False
    if policy == POLICY_OPEN:
        return True
    idset = set(ids)
    has_bug = BUG_ID in idset
    if policy == POLICY_JOKER_ONLY:
        return has_bug
    if policy == POLICY_ACE_OR_JOKER:
        return has_bug or has_physical_ace(ids)
    raise ValueError(f"unknown pair policy {policy!r}")


def is_premium_open(opener_class: str | None) -> bool:
    """AA / two pair / trips / straight+ — CO never sandbags these."""
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
    opener_class: str | None,
    ids: Sequence[int],
    spec: CoRangeSpec,
) -> bool:
    """True iff this combo is in CO's opening range at ``spec.r_pct``."""
    if opener_class is None:
        return False
    if is_premium_open(opener_class):
        return True
    if opener_class in FACE_PAIR_CLASSES:
        return flavor_matches_policy(ids, spec.policy_for(opener_class))
    return False


def co_chart_bucket(opener_class: str, ids: Sequence[int]) -> str:
    has_bug = BUG_ID in set(ids)
    has_ace = has_physical_ace(ids)
    if opener_class in FACE_PAIR_CLASSES:
        if has_bug:
            return f"{opener_class}_joker"
        if has_ace:
            return f"{opener_class}_ace"
        return f"{opener_class}_other"
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
    raise ValueError(f"not a chart-CO class: {opener_class!r}")


def range_include_text(spec: CoRangeSpec) -> str:
    bits = [
        "pair_A, two_pair, two_pair_aces_up, trips*, straight, flush, "
        "full_house, four_of_a_kind, straight_flush, five_aces"
    ]
    labels = {"pair_J": "JJ", "pair_Q": "QQ", "pair_K": "KK"}
    voices = {
        POLICY_JOKER_ONLY: "joker only",
        POLICY_ACE_OR_JOKER: "ace or joker",
        POLICY_OPEN: "any kicker",
        POLICY_PASS: "pass (never opens)",
    }
    for cls in FACE_PAIR_CLASSES:
        pol = spec.policy_for(cls)
        if pol != POLICY_PASS:
            bits.append(f"{labels[cls]} {voices[pol]}")
    return "; ".join(bits)


def range_exclude_text(spec: CoRangeSpec) -> str:
    labels = {"pair_J": "JJ", "pair_Q": "QQ", "pair_K": "KK"}
    bits: list[str] = []
    for cls in FACE_PAIR_CLASSES:
        pol = spec.policy_for(cls)
        name = labels[cls]
        if pol == POLICY_PASS:
            bits.append(f"{name} any kicker")
        elif pol == POLICY_JOKER_ONLY:
            bits.append(f"{name} without the joker (incl. ace kicker, no bug)")
        elif pol == POLICY_ACE_OR_JOKER:
            bits.append(f"{name} without ace kicker and without the joker")
        elif pol == POLICY_OPEN:
            continue
    bits.append("junk / under-jacks")
    return "; ".join(bits)


def sample_chart_co_ids(
    rng: random.Random,
    spec: CoRangeSpec,
    *,
    blocked: set[int],
    tries: int = 400,
) -> tuple[tuple[int, ...], str] | None:
    """Rejection-sample a combo-weighted CO five-set from the remainder."""
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(tries):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = classify_opener(tuple(card_from_id(i) for i in ids))
        if is_co_chart_open(cls, ids, spec):
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
class CellAccum:
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
        mix = {
            k: round(self.co_buckets.get(k, 0.0) / n, 5) for k in CHART_CO_BUCKETS
        }
        extra = {
            k: round(v / n, 5)
            for k, v in self.co_buckets.items()
            if k not in CHART_CO_BUCKETS
        }
        if extra:
            mix.update(extra)
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
    acc = CellAccum()
    for deal, co_ids in zip(deals, co_id_rows, strict=True):
        acc.add_with_ids(deal, co_ids)
    return acc.as_dict()


def generate_bn_vs_chart_co_deals_tracked(
    bn_class: str,
    spec: CoRangeSpec,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> tuple[list[NonbluffDeal], list[tuple[int, ...]]]:
    """HU: BN class/flavor × chart CO range. CO draws first, then BN."""
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
        sampled = sample_chart_co_ids(rng, spec, blocked=set(bn_ids))
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
    spec: CoRangeSpec,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    deals, _co_rows = generate_bn_vs_chart_co_deals_tracked(
        bn_class,
        spec,
        n_deals=n_deals,
        seed=seed,
        flavor=flavor,
        draw_policy=draw_policy,
    )
    return deals


def evaluate_bn_cell(
    bn_class: str,
    flavor: str,
    spec: CoRangeSpec,
    *,
    n_hu: int,
    seed: int,
) -> dict[str, Any]:
    cell_seed = _cell_seed(seed, "r", spec.r_pct, "hu", bn_class, flavor)
    deals, co_rows = generate_bn_vs_chart_co_deals_tracked(
        bn_class,
        spec,
        n_deals=n_hu,
        seed=cell_seed,
        flavor=flavor,
    )
    stats = evaluate_deals_with_co_ids(deals, co_rows)
    stats["bn_class"] = bn_class
    stats["flavor"] = flavor
    stats["key"] = row_key(bn_class, flavor)
    stats["r_pct"] = spec.r_pct
    stats["seed"] = cell_seed
    stats["n_requested"] = n_hu
    stats["locked_draws"] = {
        "name": LOCKED_BN_DRAW.name,
        "bn_d": LOCKED_BN_DRAW.n_draw_for(bn_class),
    }
    return stats


def _cell_job(item: tuple[int, str, str, int, int]) -> dict[str, Any]:
    r_pct, bn_class, flavor, n_hu, seed = item
    return evaluate_bn_cell(
        bn_class, flavor, spec_for(r_pct), n_hu=n_hu, seed=seed
    )


def derive_answers(rows: list[dict[str, Any]], spec: CoRangeSpec) -> dict[str, Any]:
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
        for k in ("pair_J", "pair_Q", "pair_K", "pair_A")
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
    aa_thin = bool(aa) and aa["recommend"]["thin_vs_fold"]
    return {
        "r_pct": spec.r_pct,
        "co_pair_policies": spec.policies,
        "jj_action": None if jj is None else act("pair_J"),
        "jj_ev_call": None if jj is None else jj["ev_call"],
        "jj_ev_raise_checkdown": None if jj is None else jj["ev_raise_checkdown"],
        "qq_action": None if qq is None else act("pair_Q"),
        "kk_action": None if kk is None else act("pair_K"),
        "aa_action": None if aa is None else act("pair_A"),
        "aa_ev_call": None if aa is None else aa["ev_call"],
        "aa_se_call": None if aa is None else aa["se_call"],
        "aa_ev_raise_checkdown": None if aa is None else aa["ev_raise_checkdown"],
        "aa_p_win": None if aa is None else aa["p_bn_wins_final"],
        "aa_thin_vs_fold": aa_thin,
        "two_pair_action": None if tp is None else act("two_pair"),
        "aces_up_action": None if au is None else act("two_pair_aces_up"),
        "trips_action": None if tr is None else act("trips"),
        "trips_A_action": None if tra is None else act("trips_A"),
        "low_pairs_fold": fold_pairs,
        "value_raise_classes": value_raise,
        "flavor_action_flips": flavor_flips,
        "jj_dominated_raise": bool(jj)
        and jj["p_bn_wins_final"] < 0.5
        and jj["recommend"]["action"] == "fold",
        "aa_value_raise": bool(aa) and aa["recommend"]["action"] == "raise",
        "aa_folds": bool(aa) and aa["recommend"]["action"] == "fold",
        "note": (
            f"Fold=0; call=honest $6 street − $2; raise=checkdown $10 − $4 "
            f"(CO always continues). CO at r={spec.r_pct}%: AA+/two pair+ plus "
            f"JJ {spec.pair_J.replace('_', ' ')}; QQ {spec.pair_Q.replace('_', ' ')}; "
            f"KK {spec.pair_K.replace('_', ' ')}. Not a polar 0%/100% lab."
        ),
    }


def _meta(spec: CoRangeSpec, *, n_hu: int, seed: int) -> dict[str, Any]:
    return {
        "seed": seed,
        "n_hu": n_hu,
        "r_pct": spec.r_pct,
        "frame": spec.frame,
        "matchup": (
            f"Seats 1–6 passed (sandbag-aware node as needed). CO opens the "
            f"r={spec.r_pct}% chart range (not all-legal, not the tight polar). "
            f"BN fold/call/raise vs that range. No multi-raise tree."
        ),
        "co_range": {
            "r_pct": spec.r_pct,
            "pair_J": spec.pair_J,
            "pair_Q": spec.pair_Q,
            "pair_K": spec.pair_K,
            "include": range_include_text(spec),
            "exclude": range_exclude_text(spec),
            "sandbag": "CO does not sandbag AA+/two pair+ — they open them",
            "bug": (
                "Joker is an ace, not trips. QQ+joker = two queens + ace "
                "kicker; KK+joker = two kings + ace kicker. Ace = physical ace "
                "kicker or the joker; joker only = the bug specifically."
            ),
        },
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
        "doc": f"docs/research/{spec.frame}.md",
        "regenerate": (
            f"analyze-button-vs-cutoff-chart --rates {spec.r_pct} "
            f"--n-hu 4000 --write-fixture"
        ),
        "parent_frames": [
            "button_vs_cutoff_all_legal",
            "button_vs_cutoff_tight",
            "cutoff_open_sandbag_v1",
        ],
        "out_of_scope": [
            "polar 0% all-legal lab (do not restart)",
            "polar ~100% tight lab (do not restart)",
            "r in {79, 84, 86, 93, 96} (other agents)",
            "multi-raise Nash",
            "live draw solver / post-draw Nash",
        ],
    }


def run_button_vs_cutoff_chart(
    r_pct: int,
    *,
    n_hu: int = DEFAULT_N_HU,
    seed: int = DEFAULT_SEED,
    rows: Sequence[tuple[str, str]] | None = None,
    progress: bool = True,
    workers: int | None = None,
) -> dict[str, Any]:
    spec = spec_for(r_pct)
    use = list(rows) if rows is not None else list(FOCUS_ROWS)
    jobs = [(spec.r_pct, cls, flav, n_hu, seed) for cls, flav in use]
    n_workers = workers if workers is not None else min(len(jobs), os.cpu_count() or 4)
    if progress:
        print(
            f"BN vs CO r={spec.r_pct}%: {len(jobs)} cells, n_hu={n_hu}, "
            f"workers={n_workers}"
        )
    if n_workers <= 1 or len(jobs) == 1:
        out_rows = [_cell_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            out_rows = list(pool.map(_cell_job, jobs))
    by_key = {r["key"]: r for r in out_rows}
    ordered = [by_key[row_key(c, f)] for c, f in use]
    answers = derive_answers(ordered, spec)
    return {
        "meta": _meta(spec, n_hu=n_hu, seed=seed),
        "by_row": ordered,
        "answers": answers,
    }


def run_owned_rates(
    *,
    rates: Sequence[int] | None = None,
    n_hu: int = DEFAULT_N_HU,
    seed: int = DEFAULT_SEED,
    rows: Sequence[tuple[str, str]] | None = None,
    progress: bool = True,
    workers: int | None = None,
) -> dict[int, dict[str, Any]]:
    use_rates = list(rates) if rates is not None else list(OWNED_RATES)
    return {
        r: run_button_vs_cutoff_chart(
            r,
            n_hu=n_hu,
            seed=seed,
            rows=rows,
            progress=progress,
            workers=workers,
        )
        for r in use_rates
    }


def default_fixture_path(r_pct: int) -> Path:
    spec = spec_for(r_pct)
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / f"{spec.frame}.json"
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
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(
    r_pct: int, path: Path | None = None
) -> dict[str, Any]:
    path = path or default_fixture_path(r_pct)
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    spec = spec_for(int(meta["r_pct"]))
    lines = [
        f"# BN vs CO at r = {spec.r_pct}%",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}, frame `{spec.frame}`.",
        "",
        f"CO range: JJ {spec.pair_J.replace('_', ' ')}; "
        f"QQ {spec.pair_Q.replace('_', ' ')}; "
        f"KK {spec.pair_K.replace('_', ' ')}; AA+/two pair+ always. "
        "CO never sandbags those. Joker = ace kicker, not trips.",
        "",
        "## Product answers",
        "",
        f"- JJ → **{a['jj_action']}** (call {a['jj_ev_call']:+.3f}, "
        f"raise-cd {a['jj_ev_raise_checkdown']:+.3f})",
        f"- QQ → **{a['qq_action']}**; KK → **{a['kk_action']}**",
        f"- AA → **{a['aa_action']}** (call {a['aa_ev_call']:+.3f} "
        f"SE {a['aa_se_call']:.3f}; raise-cd {a['aa_ev_raise_checkdown']:+.3f}; "
        f"P(win) {a['aa_p_win']:.3f}"
        f"{'; thin vs fold' if a['aa_thin_vs_fold'] else ''})",
        f"- Two pair → **{a['two_pair_action']}**; aces-up → "
        f"**{a['aces_up_action']}**; trips → **{a['trips_action']}**; "
        f"trips_A → **{a['trips_A_action']}**",
        f"- One-pair folds: {a['low_pairs_fold'] or 'none'}",
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


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description=(
            "BN fold/call/raise vs CO at chart r=87% and/or r=90% "
            "(owned rows only; does not restart polar labs)"
        )
    )
    p.add_argument(
        "--rates",
        type=str,
        default="87,90",
        help="Comma-separated integer percents (owned: 87,90)",
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("-o", "--output-dir", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_hu = 250 if args.quick else args.n_hu
    rates = [int(x.strip()) for x in args.rates.split(",") if x.strip()]
    unknown = [r for r in rates if r not in RANGES]
    if unknown:
        raise SystemExit(
            f"this module owns r in {list(OWNED_RATES)}; got {unknown}"
        )
    out_dir = args.output_dir or Path("outputs/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    for r_pct in rates:
        payload = run_button_vs_cutoff_chart(
            r_pct, n_hu=n_hu, seed=args.seed, progress=True, workers=args.workers
        )
        out = out_dir / f"{payload['meta']['frame']}.json"
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
        print(f"Answers r={spec_for(r_pct).r_pct}%:")
        print(
            f"  JJ {a['jj_action']}  call={a['jj_ev_call']}  "
            f"raise-cd={a['jj_ev_raise_checkdown']}"
        )
        print(
            f"  QQ {a['qq_action']}  KK {a['kk_action']}  "
            f"AA {a['aa_action']}  call={a['aa_ev_call']}  "
            f"p_win={a['aa_p_win']}"
        )
        print(
            f"  two_pair {a['two_pair_action']}  aces-up {a['aces_up_action']}  "
            f"trips {a['trips_action']}  trips_A {a['trips_A_action']}"
        )
        for row in payload["by_row"]:
            rec = row["recommend"]["action"]
            print(
                f"  {row['key']:<22} {rec:<6} call={row['ev_call']:+.3f} "
                f"({row['se_call']:.3f})  raise={row['ev_raise_checkdown']:+.3f} "
                f"({row['se_raise_checkdown']:.3f})  p_win={row['p_bn_wins_final']:.3f}"
            )


if __name__ == "__main__":
    main()
