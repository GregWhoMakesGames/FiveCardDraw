"""BN vs CO at chart r=96% (JJ pass; QQ/KK joker only — tight polar range)."""

from fivecarddraw.validation.button_vs_cutoff_chart import main_for_r

FRAME = "button_vs_cutoff_r96"
R_PCT = 96


def main() -> None:
    main_for_r(R_PCT)


if __name__ == "__main__":
    main()
