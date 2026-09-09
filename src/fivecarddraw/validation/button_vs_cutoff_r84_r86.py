"""BN fold / call / raise vs CO at open-chart thresholds r = 84% and 86%.

Frames: ``button_vs_cutoff_r84``, ``button_vs_cutoff_r86``.
Parent grid: ``docs/NEXT_STAGE_BN_VS_CO_GRID.md``.
CO chart: ``docs/research/cutoff_open_sandbag_v1.md``.

This module owns **only** those two interior rows. Polar labs (0% all-legal,
~100% tight) and the other chart thresholds (79, 87, 90, 93, 96) are other
agents. Do not restart those products from here.

Laboratory (same locked leaves as the polar BN-vs-CO frames):

- Seats 1–6 passed (sandbag-aware node as needed).
- CO (seat 7) opens AA+ / two pair+ always, and JJ/QQ/KK per the chart
  band. CO **never sandbags** AA+ / two pair+.
- BN (seat 8) fold / call / raise vs that range. No multi-raise, no live
  draw Nash, no post-draw Nash.

Bug = ace kicker (or fill), **not** a third rank.

Accounting (BN decision; ante sunk; fold = 0):

- Call = honest $6 street (BN as drawer) − $2
- Raise bound = checkdown $10 − $4; CO always continues

Draws: locked ``tp1_tr2_q1``. CO draws first, then BN.
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
    FOLD_EV,
    FOCUS_ROWS,
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


DEFAULT_N_HU = 4_000
DEFAULT_SEED_R84 = 20260909
DEFAULT_SEED_R86 = 20260910

PAIR_J_JOKER = parse_hand("Jh Jd Bu 9s 7h")
PAIR_J_ACE = parse_hand("Jh Jd As 7h 4c")
PAIR_J_BARE = parse_hand("Jh Jd 9s 7h 4c")
PAIR_Q_JOKER = parse_hand("Qh Qd Bu 9s 7h")
PAIR_Q_ACE = parse_hand("Qh Qd As 7h 4c")
PAIR_Q_BARE = parse_hand("Qh Qd 9s 7h 4c")
PAIR_K_JOKER = parse_hand("Kh Kd Bu 9s 7h")
PAIR_K_ACE = parse_hand("Kh Kd As 7h 4c")
PAIR_K_BARE = parse_hand("Kh Kd 9s 7h 4c")

CO_BUCKETS = (
    "pair_J_joker",
    "pair_J_ace",
    "pair_J_bare",
    "pair_Q_joker",
    "pair_Q_ace",
    "pair_Q_bare",
    "pair_K_joker",
    "pair_K_ace",
    "pair_K_bare",
    "pair_A",
    "two_pair",
    "two_pair_aces_up",
    "trips",
    "straight_plus",
)


@dataclass(frozen=True, slots=True)
class ChartRateSpec:
    """One interior CO open-chart threshold."""

    rate_pct: int
    seed: int
    jj: str
    qq: str
    kk: str
    frame: str
    doc: str

    @property
    def rate(self) -> float:
        return self.rate_pct / 100.0

    @property
    def pair_policies(self) -> dict[str, str]:
        return {"pair_J": self.jj, "pair_Q": self.qq, "pair_K": self.kk}


RATE_R84 = ChartRateSpec(
    rate_pct=84,
    seed=DEFAULT_SEED_R84,
    jj=POLICY_ACE_OR_JOKER,
    qq=POLICY_ACE_OR_JOKER,
    kk=POLICY_OPEN_ALWAYS,
    frame="button_vs_cutoff_r84",
    doc="docs/research/button_vs_cutoff_r84.md",
)
RATE_R86 = ChartRateSpec(
    rate_pct=86,
    seed=DEFAULT_SEED_R86,
    jj=POLICY_JOKER_ONLY,
    qq=POLICY_ACE_OR_JOKER,
    kk=POLICY_OPEN_ALWAYS,
    frame="button_vs_cutoff_r86",
    doc="docs/research/button_vs_cutoff_r86.md",
)
OWNED_RATES: dict[int, ChartRateSpec] = {
    84: RATE_R84,
    86: RATE_R86,
}


def spec_for(rate_pct: int) -> ChartRateSpec:
    if rate_pct not in OWNED_RATES:
        owned = ", ".join(str(k) for k in sorted(OWNED_RATES))
        raise ValueError(
            f"this module owns r ∈ {{{owned}}} only; got r={rate_pct}"
        )
    return OWNED_RATES[rate_pct]


def pair_has_ace_or_joker(ids: Sequence[int]) -> bool:
    return BUG_ID in set(ids) or has_physical_ace(ids)


def pair_has_joker(ids: Sequence[int]) -> bool:
    return BUG_ID in set(ids)


def pair_opens_under_policy(ids: Sequence[int], policy: str) -> bool:
    if policy == POLICY_OPEN_ALWAYS:
        return True
    if policy == POLICY_ACE_OR_JOKER:
        return pair_has_ace_or_joker(ids)
    if policy == POLICY_JOKER_ONLY:
        return pair_has_joker(ids)
    if policy == POLICY_PASS:
        return False
    raise ValueError(f"unknown pair policy {policy!r}")


def _cls_of_ids(ids: Sequence[int]) -> str | None:
    return classify_opener(tuple(card_from_id(i) for i in ids))


def is_co_chart_open(
    opener_class: str | None,
    ids: Sequence[int],
    spec: ChartRateSpec,
) -> bool:
    """AA+ / two pair+ always; JJ/QQ/KK follow the chart band. No sandbag."""
    if opener_class is None:
        return False
    if opener_class in spec.pair_policies:
        return pair_opens_under_policy(ids, spec.pair_policies[opener_class])
    if opener_class == "pair_A":
        return True
    if opener_class in TWO_PAIR_CLASSES:
        return True
    if opener_class in TRIPS_CLASSES:
        return True
    if opener_class in STRAIGHT_PLUS_CLASSES:
        return True
    return False


def co_chart_bucket(opener_class: str, ids: Sequence[int]) -> str:
    if opener_class in ("pair_J", "pair_Q", "pair_K"):
        s = set(ids)
        if BUG_ID in s:
            return f"{opener_class}_joker"
        if has_physical_ace(ids):
            return f"{opener_class}_ace"
        return f"{opener_class}_bare"
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
    spec: ChartRateSpec,
    *,
    blocked: set[int],
    tries: int = 800,
) -> tuple[tuple[int, ...], str] | None:
    """Rejection-sample a combo-weighted CO five-set in this chart band."""
    pool = [i for i in range(53) if i not in blocked]
    if len(pool) < 5:
        return None
    for _ in range(tries):
        ids = tuple(sorted(rng.sample(pool, 5)))
        cls = _cls_of_ids(ids)
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
        mix = {k: round(self.co_buckets.get(k, 0.0) / n, 5) for k in CO_BUCKETS}
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


def generate_bn_vs_chart_co_deals_tracked(
    bn_class: str,
    spec: ChartRateSpec,
    *,
    n_deals: int,
    seed: int,
    flavor: str = "class",
    draw_policy=LOCKED_BN_DRAW,
) -> tuple[list[NonbluffDeal], list[tuple[int, ...]]]:
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
    spec: ChartRateSpec,
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


def evaluate_deals_with_co_ids(
    deals: Sequence[NonbluffDeal], co_id_rows: Sequence[Sequence[int]]
) -> dict[str, Any]:
    acc = CellAccum()
    for deal, co_ids in zip(deals, co_id_rows, strict=True):
        acc.add_with_ids(deal, co_ids)
    return acc.as_dict()


def evaluate_bn_cell(
    bn_class: str,
    flavor: str,
    spec: ChartRateSpec,
    *,
    n_hu: int,
    seed: int,
) -> dict[str, Any]:
    cell_seed = _cell_seed(seed, "hu", spec.rate_pct, bn_class, flavor)
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
    stats["seed"] = cell_seed
    stats["n_requested"] = n_hu
    stats["rate_pct"] = spec.rate_pct
    stats["locked_draws"] = {
        "name": LOCKED_BN_DRAW.name,
        "bn_d": LOCKED_BN_DRAW.n_draw_for(bn_class),
    }
    return stats


def _cell_job(item: tuple[int, str, str, int, int]) -> dict[str, Any]:
    rate_pct, bn_class, flavor, n_hu, seed = item
    return evaluate_bn_cell(
        bn_class, flavor, spec_for(rate_pct), n_hu=n_hu, seed=seed
    )


def derive_answers(rows: list[dict[str, Any]], spec: ChartRateSpec) -> dict[str, Any]:
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
    aa_thin = False
    if aa is not None:
        rec = aa["recommend"]
        aa_thin = bool(rec.get("thin_vs_fold") or rec.get("thin_vs_runner_up"))
    return {
        "rate_pct": spec.rate_pct,
        "co_jj": spec.jj,
        "co_qq": spec.qq,
        "co_kk": spec.kk,
        "jj_action": None if jj is None else act("pair_J"),
        "jj_ev_call": None if jj is None else jj["ev_call"],
        "jj_ev_raise_checkdown": None if jj is None else jj["ev_raise_checkdown"],
        "qq_action": None if qq is None else act("pair_Q"),
        "kk_action": None if kk is None else act("pair_K"),
        "aa_action": None if aa is None else act("pair_A"),
        "aa_ev_call": None if aa is None else aa["ev_call"],
        "aa_ev_raise_checkdown": None if aa is None else aa["ev_raise_checkdown"],
        "aa_p_win": None if aa is None else aa["p_bn_wins_final"],
        "aa_thin": aa_thin,
        "two_pair_action": None if tp is None else act("two_pair"),
        "aces_up_action": None if au is None else act("two_pair_aces_up"),
        "trips_action": None if tr is None else act("trips"),
        "trips_A_action": None if tra is None else act("trips_A"),
        "low_pairs_fold": fold_pairs,
        "value_raise_classes": value_raise,
        "flavor_action_flips": flavor_flips,
        "note": (
            f"Fold=0; call=honest $6 street − $2; raise=checkdown $10 − $4 "
            f"(CO always continues). r={spec.rate_pct}% CO: JJ {spec.jj}, "
            f"QQ {spec.qq}, KK {spec.kk}; AA+/two pair+ always. CO never "
            "sandbags. Polar 0%/100% labs are not this frame."
        ),
    }


def _co_range_meta(spec: ChartRateSpec) -> dict[str, Any]:
    return {
        "rate_pct": spec.rate_pct,
        "jj": spec.jj,
        "qq": spec.qq,
        "kk": spec.kk,
        "always": "pair_A, two_pair, two_pair_aces_up, trips*, straight+",
        "sandbag": "CO does not sandbag AA+ / two pair+ — they open them",
        "bug": (
            "Joker is an ace, not trips. pair_X+joker = two of that rank + "
            "ace kicker. Ace = physical ace kicker or the joker."
        ),
        "chart": "cutoff_open_sandbag_v1 opening chart; this row only",
    }


def run_button_vs_cutoff_rate(
    spec: ChartRateSpec,
    *,
    n_hu: int = DEFAULT_N_HU,
    seed: int | None = None,
    rows: Sequence[tuple[str, str]] | None = None,
    progress: bool = True,
    workers: int | None = None,
) -> dict[str, Any]:
    use_seed = spec.seed if seed is None else seed
    use = list(rows) if rows is not None else list(FOCUS_ROWS)
    jobs = [(spec.rate_pct, cls, flav, n_hu, use_seed) for cls, flav in use]
    n_workers = workers if workers is not None else min(len(jobs), os.cpu_count() or 4)
    if progress:
        print(
            f"BN vs CO r={spec.rate_pct}%: {len(jobs)} cells, n_hu={n_hu}, "
            f"workers={n_workers}, seed={use_seed}"
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
        "meta": {
            "seed": use_seed,
            "n_hu": n_hu,
            "frame": spec.frame,
            "rate_pct": spec.rate_pct,
            "matchup": (
                f"Seats 1–6 passed. CO opens the r={spec.rate_pct}% chart "
                f"range (JJ {spec.jj}; QQ {spec.qq}; KK {spec.kk}; AA+/two "
                "pair+). BN fold/call/raise vs that range. No multi-raise "
                "tree. Not the 0% all-legal or ~100% tight polar labs."
            ),
            "co_range": _co_range_meta(spec),
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
            "doc": spec.doc,
            "regenerate": (
                "python -m fivecarddraw.validation.button_vs_cutoff_r84_r86 "
                f"--rate {spec.rate_pct} --n-hu 4000 --write-fixture"
            ),
            "out_of_scope": [
                "r ∈ {79, 87, 90, 93, 96} — other agents",
                "polar 0% all-legal / ~100% tight restarts",
                "multi-raise Nash",
                "live draw solver / post-draw Nash",
            ],
        },
        "by_row": ordered,
        "answers": answers,
    }


def default_fixture_path(spec: ChartRateSpec) -> Path:
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
    spec = spec_for(int(payload["meta"]["rate_pct"]))
    path = path or default_fixture_path(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    slim = {
        "meta": payload["meta"],
        "by_row": payload["by_row"],
        "answers": payload["answers"],
    }
    path.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    return path


def load_summary_fixture(
    spec: ChartRateSpec, path: Path | None = None
) -> dict[str, Any]:
    path = path or default_fixture_path(spec)
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown_summary(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = payload["answers"]
    meta = payload["meta"]
    lines = [
        f"# BN vs CO at r={meta['rate_pct']}%",
        "",
        f"Seed `{meta['seed']}`, n_hu={meta['n_hu']}.",
        "",
        f"CO: JJ `{a['co_jj']}`; QQ `{a['co_qq']}`; KK `{a['co_kk']}`.",
        "",
        "## Product answers",
        "",
        f"- JJ → **{a['jj_action']}** (call {a['jj_ev_call']:+.3f}, "
        f"raise-cd {a['jj_ev_raise_checkdown']:+.3f})",
        f"- QQ → **{a['qq_action']}**; KK → **{a['kk_action']}**; "
        f"AA → **{a['aa_action']}** "
        f"(call {a['aa_ev_call']:+.3f}, raise-cd {a['aa_ev_raise_checkdown']:+.3f}, "
        f"P(win) {a['aa_p_win']:.3f})",
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
        description=(
            "BN fold/call/raise vs CO at chart r=84% or r=86% "
            "(interior rows only; not polar labs)"
        )
    )
    p.add_argument(
        "--rate",
        type=int,
        required=True,
        choices=sorted(OWNED_RATES),
        help="Chart threshold percent (84 or 86)",
    )
    p.add_argument("--n-hu", type=int, default=DEFAULT_N_HU)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("-o", "--output", type=Path, default=None)
    p.add_argument("--write-fixture", action="store_true")
    args = p.parse_args()
    spec = spec_for(args.rate)
    n_hu = 250 if args.quick else args.n_hu
    payload = run_button_vs_cutoff_rate(
        spec, n_hu=n_hu, seed=args.seed, progress=True, workers=args.workers
    )
    out = args.output or Path(f"outputs/validation/{spec.frame}.json")
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
    print(f"r={spec.rate_pct}% answers:")
    print(
        f"  JJ {a['jj_action']}  call={a['jj_ev_call']}  "
        f"raise-cd={a['jj_ev_raise_checkdown']}"
    )
    print(
        f"  QQ {a['qq_action']}  KK {a['kk_action']}  AA {a['aa_action']}  "
        f"aa_call={a['aa_ev_call']}  aa_p_win={a['aa_p_win']}"
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
