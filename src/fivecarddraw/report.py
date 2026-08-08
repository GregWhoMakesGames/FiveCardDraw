"""CSV and console reporting for strategy tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table


console = Console()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def print_table(df: pd.DataFrame, title: str, max_rows: int = 40) -> None:
    table = Table(title=title, show_lines=False)
    for col in df.columns:
        table.add_column(str(col))
    view = df.head(max_rows)
    for _, row in view.iterrows():
        table.add_row(*[str(row[c]) for c in df.columns])
    if len(df) > max_rows:
        table.caption = f"Showing {max_rows} of {len(df)} rows"
    console.print(table)


def strategy_df_from_records(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)
