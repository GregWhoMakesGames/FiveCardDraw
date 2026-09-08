"""BN fold / call / raise vs a *tight* CO open (range 2).

Frame: ``button_vs_cutoff_tight``
(docs/research/button_vs_cutoff_tight.md).

Laboratory. Seats 1–6 have passed (sandbag-aware node). CO (seat 7) opens a
**constructed** range, not all-legal:

  - AA or better (``pair_A``, two pair, trips, boat, quads, straight / flush /
    straight-flush / five aces as classified by ``classify_opener``), **plus**
  - QQ with the joker, **or** KK with the joker.

CO does **not** open JJ (any kicker), QQ without the joker, or KK without the
joker. CO does not sandbag the hands in this range. The range is a hypothesis
consistent with the 100% sandbag flavor pins; this module does **not** prove
the CO open chart.

BN (seat 8) faces the unraised open. Bound: fold / call / raise vs that CO
range only. No multi-raise tree, no live draw solver, no 1–6 check-raise mix.

Accounting (BN decision node; ante already sunk, fold = 0):

  - Fold = 0
  - Call = honest $6 street (BN as drawer) − $2
  - Raise bound = checkdown on a $10 pot (CO always continues; BN invested $4)

Draws: locked ``tp1_tr2_q1`` (pairs d=3, two pair d=1, trips d=2, quads d=1).
CO draws first, then BN. Honest post-draw policy matches the CO-vs-BN HU lab
(invert the seats: opener is still CO).
"""

from __future__ import annotations

import json
import math
import os
import random
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from fivecarddraw.cards import BUG_ID, card_from_id, parse_hand
from fivecarddraw.hand_rank import HandCategory, evaluate_hand
from fivecarddraw.validation.cutoff_open import (
    _cell_seed,
    _pair_rank_from_class,
    bn_value_continue_as_m2_drawer,
)
from fivecarddraw.validation.cutoff_open import (
    sample_class_ids as sample_opener_class_ids,
)
from fivecarddraw.validation.cutoff_open_sandbag import sample_class_ids_forced
from fivecarddraw.validation.postdraw_draw_mixes import opener_draw_plan_for_action
from fivecarddraw.validation.postdraw_nonbluff_ev import (
    HONEST_POLICY,
    LOCKED_BN_DRAW,
    NonbluffDeal,
    play_honest_deal,
)
from fivecarddraw.validation.postdraw_betting_m2 import (
    PREDRAW_POT,
    _one_pair_rank,
)
from fivecarddraw.validation.showdown_matrix import (
    STRAIGHT_PLUS_CLASSES,
    TRIPS_CLASSES,
    TWO_PAIR_CLASSES,
    classify_opener,
)


DEFAULT_SEED = 20260907
DEFAULT_N_HU = 4_000
FOLD_EV = 0.0
CALL_INVEST = 2.0
RAISE_INVEST = 4.0
RAISE_POT = 10.0  # $2 ante + $4 CO + $4 BN; CO always continues
FRAME = "button_vs_cutoff_tight"

# Bug is an ace kicker, not a duplicate pair rank.
PAIR_Q_JOKER = parse_hand("Qh Qd Bu 9s 7h")
PAIR_K_JOKER = parse_hand("Kh Kd Bu 9s 7h")
PAIR_Q_NO_JOKER = parse_hand("Qh Qd 9s 7h 4c")
PAIR_K_NO_JOKER = parse_hand("Kh Kd 9s 7h 4c")
PAIR_J_JOKER = parse_hand("Jh Jd Bu 9s 7h")

TIGHT_CO_BUCKETS = (
    "pair_A",
    "pair_Q_joker",
    "pair_K_joker",
    "two_pair",
    "two_pair_aces_up",
    "trips",
    "straight_plus",
)

# Hero rows: class averages plus joker / ace flavors where blockers can flip.
FOCUS_ROWS: tuple[tuple[str, str], ...] = (
    ("pair_J", "class"),
    ("pair_J", "joker"),
    ("pair_J", "ace"),
    ("pair_Q", "class"),
    ("pair_Q", "joker"),
    ("pair_Q", "ace"),
    ("pair_K", "class"),
    ("pair_K", "joker"),
    ("pair_K", "ace"),
    ("pair_A", "class"),
    ("two_pair", "class"),
    ("two_pair_aces_up", "class"),
    ("trips", "class"),
    ("trips_A", "class"),
)


def _ids_of_cards(cards) -> tuple[int, ...]:
    return tuple(sorted(c.card_id for c in cards))


def _cls_of_ids(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


def is_co_tight_open(opener_class: str | None, ids: Sequence[int]) -> bool:
    """Range 2: AA+ plus QQ+joker or KK+joker. Not JJ; not QQ/KK without bug."""
    if opener_class is None:
        return False
    if opener_class == "pair_J":
        return False
    if opener_class == "pair_Q":
        return BUG_ID in set(ids)
    if opener_class == "pair_K":
        return BUG_ID in set(ids)
    if opener_class == "pair_A":
        return True
    if opener_class in TWO_PAIR_CLASSES:
        return True
    if opener_class in TRIPS_CLASSES:
        return True
    if opener_class in STRAIGHT_PLUS_CLASSES:
        return True
    return False


def co_tight_bucket(opener_class: str, ids: Sequence[int]) -> str:
    if opener_class == "pair_Q":
        return "pair_Q_joker"
    if opener_class == "pair_K":
        return "pair_K_joker"
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
    raise ValueError(f"not a tight-CO class: {opener_class!r} ids={list(ids)}")


def sample_tight_co_ids(
    rng: random.Random, *, blocked: set[int], tries: int = 400
) -> tuple[tuple[int, ...], str] | None:
    """Rejection-sample a combo-weighted tight CO five-set from the remainder."""
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(tries):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = _cls_of_ids(ids)
        if is_co_tight_open(cls, ids):
            assert cls is not None
            return ids, cls
    return None


def sample_bn_ids(
    bn_class: str,
    flavor: str,
    rng: random.Random,
) -> tuple[int, ...] | None:
    if flavor == "class":
        return sample_opener_class_ids(bn_class, rng)
    if flavor == "joker":
        return sample_class_ids_forced(bn_class, rng, require_bug=True)
    if flavor == "ace":
        return sample_class_ids_forced(
            bn_class, rng, require_physical_ace=True
        )
    raise ValueError(f"unknown flavor {flavor!r}")


def row_key(bn_class: str, flavor: str) -> str:
    if flavor == "class":
        return bn_class
    return f"{bn_class}_{flavor}"


def ev_call_net(ev_bn_street: float) -> float:
    """Call: street chips from the $6 pot minus the $2 call."""
    return ev_bn_street - CALL_INVEST


def ev_raise_checkdown(*, p_bn_win: float, p_tie: float) -> float:
    """Raise bound: CO always continues; check down a $10 pot (BN invested $4)."""
    street = RAISE_POT * p_bn_win + (RAISE_POT / 2.0) * p_tie
    return street - RAISE_INVEST


def recommend_action(
    *,
    ev_call: float,
    ev_raise: float,
    se_call: float = 0.0,
    se_raise: float = 0.0,
) -> dict[str, Any]:
    """Argmax of fold=0 / call / raise-checkdown. Flag thin gaps (< 1 SE)."""
    scored = (
        ("fold", FOLD_EV, 0.0),
        ("call", ev_call, se_call),
        ("raise", ev_raise, se_raise),
    )
    best_name, best_ev, best_se = max(scored, key=lambda t: t[1])
    second_name, second_ev, second_se = max(
        (t for t in scored if t[0] != best_name), key=lambda t: t[1]
    )
    gap = best_ev - second_ev
    gap_se = math.sqrt(best_se**2 + second_se**2)
    thin = gap_se > 0.0 and gap < gap_se
    vs_fold_se = best_se if best_name != "fold" else 0.0
    vs_fold_thin = best_name != "fold" and vs_fold_se > 0.0 and abs(best_ev) < vs_fold_se
    return {
        "action": best_name,
        "ev_best": round(best_ev, 5),
        "runner_up": second_name,
        "gap_vs_runner_up": round(gap, 5),
        "thin_vs_runner_up": thin,
        "thin_vs_fold": vs_fold_thin,
        "call_plus_ev_vs_fold": ev_call > FOLD_EV,
        "raise_plus_ev_vs_fold": ev_raise > FOLD_EV,
        "raise_beats_call": ev_raise > ev_call,
    }


def _se_mean(sum_x: float, sum_x2: float, n: float) -> float:
    if n < 2.0:
        return 0.0
    mean = sum_x / n
    var = max(0.0, (sum_x2 - n * mean * mean) / (n - 1.0))
    return math.sqrt(var / n)


def generate_bn_vs_tight_co_deals(
    bn_class: str,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> list[NonbluffDeal]:
    """HU: BN class/flavor × tight CO range. CO draws first, then BN."""
    deals, _co_rows = generate_bn_vs_tight_co_deals_tracked(
        bn_class,
        n_deals=n_deals,
        seed=seed,
        flavor=flavor,
        draw_policy=draw_policy,
    )
    return deals


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
        self.co_buckets[co_tight_bucket(deal.opener_class, co_ids)] += 1.0
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
            ev_call=ev_call, ev_raise=ev_raise, se_call=se_call, se_raise=se_raise
        )
        mix = {k: round(self.co_buckets.get(k, 0.0) / n, 5) for k in TIGHT_CO_BUCKETS}
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


def generate_bn_vs_tight_co_deals_tracked(
    bn_class: str,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> tuple[list[NonbluffDeal], list[tuple[int, ...]]]:
    """Same as ``generate_bn_vs_tight_co_deals`` but keeps CO hole cards for mix."""
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
        sampled = sample_tight_co_ids(rng, blocked=set(bn_ids))
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


def evaluate_bn_cell(
    bn_class: str,
    flavor: str,
    *,
    n_hu: int,
    seed: int,
) -> dict[str, Any]:
    deals, co_rows = generate_bn_vs_tight_co_deals_tracked(
        bn_class,
        n_deals=n_hu,
        seed=_cell_seed(seed, "hu", bn_class, flavor),
        flavor=flavor,
    )
    stats = evaluate_deals_with_co_ids(deals, co_rows)
    stats["bn_class"] = bn_class
    stats["flavor"] = flavor
    stats["key"] = row_key(bn_class, flavor)
    stats["seed"] = _cell_seed(seed, "hu", bn_class, flavor)
    stats["n_requested"] = n_hu
    stats["locked_draws"] = {
        "name": LOCKED_BN_DRAW.name,
        "bn_d": LOCKED_BN_DRAW.n_draw_for(bn_class),
    }
    return stats


def _cell_job(item: tuple[str, str, int, int]) -> dict[str, Any]:
    bn_class, flavor, n_hu, seed = item
    return evaluate_bn_cell(bn_class, flavor, n_hu=n_hu, seed=seed)


def derive_answers(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "jj_action": None if jj is None else act("pair_J"),
        "jj_ev_call": None if jj is None else jj["ev_call"],
        "jj_ev_raise_checkdown": None if jj is None else jj["ev_raise_checkdown"],
        "qq_action": None if qq is None else act("pair_Q"),
        "kk_action": None if kk is None else act("pair_K"),
        "aa_action": None if aa is None else act("pair_A"),
        "two_pair_action": None if tp is None else act("two_pair"),
        "aces_up_action": None if au is None else act("two_pair_aces_up"),
        "trips_action": None if tr is None else act("trips"),
        "trips_A_action": None if tra is None else act("trips_A"),
        "low_pairs_fold": fold_pairs,
        "value_raise_classes": value_raise,
        "flavor_action_flips": flavor_flips,
        "jj_dominated_raise": bool(jj) and jj["ev_raise_checkdown"] < jj["ev_call"],
        "note": (
            "Fold=0; call=honest $6 street − $2; raise=checkdown $10 − $4 "
            "(CO always continues). Tight CO = AA+ plus QQ/KK with the joker. "
            "Not an all-legal CO open."
        ),
    }


def run_button_vs_cutoff_tight(
    *,
    n_hu: int = DEFAULT_N_HU,
    seed: int = DEFAULT_SEED,
    rows: Sequence[tuple[str, str]] | None = None,
    progress: bool = True,
    workers: int | None = None,
) -> dict[str, Any]:
    use = list(rows) if rows is not None else list(FOCUS_ROWS)
    jobs = [(cls, flav, n_hu, seed) for cls, flav in use]
    n_workers = workers if workers is not None else min(len(jobs), os.cpu_count() or 4)
    if progress:
        print(f"BN vs tight CO: {len(jobs)} cells, n_hu={n_hu}, workers={n_workers}")
    out_rows: list[dict[str, Any]]
    if n_workers <= 1 or len(jobs) == 1:
        out_rows = [_cell_job(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            out_rows = list(pool.map(_cell_job, jobs))
    # Preserve FOCUS_ROWS order.
    by_key = {r["key"]: r for r in out_rows}
    ordered = [by_key[row_key(c, f)] for c, f in use]
    answers = derive_answers(ordered)
    return {
        "meta": {
            "seed": seed,
            "n_hu": n_hu,
            "frame": FRAME,
            "matchup": (
                "Seats 1–6 passed (sandbag-aware node as needed). CO opens "
                "AA+ plus QQ+joker or KK+joker (not all-legal). BN fold/call/"
                "raise vs that range. No multi-raise tree."
            ),
            "co_range": {
                "include": (
                    "pair_A, two_pair, two_pair_aces_up, trips*, straight, "
                    "flush, full_house, four_of_a_kind, straight_flush, "
                    "five_aces, pair_Q with joker, pair_K with joker"
                ),
                "exclude": (
                    "pair_J any kicker, pair_Q without joker, pair_K without joker"
                ),
                "sandbag": "CO does not sandbag these hands — they open them",
                "hypothesis": (
                    "Consistent with 100% sandbag flavor pins "
                    "(KK+joker +EV; QQ+joker ~0; JJ+joker still −EV; "
                    "ace kickers −EV). Not a proof of the CO open chart."
                ),
                "bug": (
                    "Joker is an ace, not trips. QQ+joker = two queens + ace "
                    "kicker; KK+joker = two kings + ace kicker."
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
            "doc": "docs/research/button_vs_cutoff_tight.md",
            "regenerate": (
                "analyze-button-vs-cutoff-tight --n-hu 4000 --write-fixture"
            ),
        },
        "by_row": ordered,
        "answers": answers,
    }


def default_fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "validation"
        / "button_vs_cutoff_tight.json"
    )


def write_summary_fixture(
    payload: dict[str, Any], path: Path | None = None
) -> Path:
    path = path or default_fixture_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "by_row": payload["by_row"],
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
        "# BN vs tight CO open (range 2)",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}.",
        "",
        "## Product answers",
        "",
        f"- JJ → **{a['jj_action']}** (call {a['jj_ev_call']:+.3f}, "
        f"raise-cd {a['jj_ev_raise_checkdown']:+.3f})",
        f"- QQ → **{a['qq_action']}**; KK → **{a['kk_action']}**; "
        f"AA → **{a['aa_action']}**",
        f"- Two pair → **{a['two_pair_action']}**; aces-up → "
        f"**{a['aces_up_action']}**; trips → **{a['trips_action']}**; "
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


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="BN fold/call/raise vs tight CO open (AA+ plus QQ/KK+joker)"
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    n_hu = 250 if args.quick else args.n_hu
    payload = run_button_vs_cutoff_tight(
        n_hu=n_hu, seed=args.seed, progress=True, workers=args.workers
    )
    out = args.output or Path("outputs/validation/button_vs_cutoff_tight.json")
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
    print("Answers:")
    print(
        f"  JJ {a['jj_action']}  call={a['jj_ev_call']}  "
        f"raise-cd={a['jj_ev_raise_checkdown']}"
    )
    print(
        f"  QQ {a['qq_action']}  KK {a['kk_action']}  AA {a['aa_action']}"
    )
    print(
        f"  two_pair {a['two_pair_action']}  aces-up {a['aces_up_action']}  "
        f"trips {a['trips_action']}  trips_A {a['trips_A_action']}"
    )
    for r in payload["by_row"]:
        rec = r["recommend"]["action"]
        print(
            f"  {r['key']:<22} {rec:<6} call={r['ev_call']:+.3f} "
            f"({r['se_call']:.3f})  raise={r['ev_raise_checkdown']:+.3f} "
            f"({r['se_raise_checkdown']:.3f})  p_win={r['p_bn_wins_final']:.3f}"
        )


if __name__ == "__main__":
    main()
