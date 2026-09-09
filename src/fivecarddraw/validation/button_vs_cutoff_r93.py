"""BN vs CO at chart r=93% (JJ pass; QQ joker only; KK ace or joker)."""

from fivecarddraw.validation.button_vs_cutoff_chart import main_for_r

FRAME = "button_vs_cutoff_r93"
R_PCT = 93


def main() -> None:
    main_for_r(R_PCT)


if __name__ == "__main__":
    main()
