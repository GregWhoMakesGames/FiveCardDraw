"""Simple performance benchmarks for hand evaluation."""

from __future__ import annotations

import random
import time

from fivecarddraw.cards import full_deck
from fivecarddraw.hand_rank import evaluate_hand


def bench_hand_eval(n: int = 200_000) -> dict:
    deck = full_deck(include_bug=True)
    rng = random.Random(42)
    hands = []
    for _ in range(n):
        hands.append(tuple(rng.sample(deck, 5)))

    t0 = time.perf_counter()
    for h in hands:
        evaluate_hand(h)
    elapsed = time.perf_counter() - t0
    rate = n / elapsed if elapsed > 0 else float("inf")
    return {"hands": n, "seconds": elapsed, "hands_per_sec": rate}


def main() -> None:
    result = bench_hand_eval()
    print(
        f"evaluated {result['hands']} hands in {result['seconds']:.3f}s "
        f"({result['hands_per_sec']:.0f} hands/sec)"
    )
    target = 2_000_000
    if result["hands_per_sec"] >= target:
        print(f"PASS: meets target {target:.0f}/s")
    else:
        print(
            f"NOTE: below aspirational Numba target {target:.0f}/s; "
            f"pure-Python eval is OK for v1 verification "
            f"(current {result['hands_per_sec']:.0f}/s)"
        )


if __name__ == "__main__":
    main()
