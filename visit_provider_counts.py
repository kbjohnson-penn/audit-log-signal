"""Summarize visits per provider from a filtered audit log."""

from __future__ import annotations

import argparse
from time import time
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


def count_visits_per_user(log_file: Path, *, output_file: Optional[Path] = None) -> pd.Series:
    """Return the number of unique visits per user sorted descending.

    Parameters
    ----------
    log_file
        CSV containing at least `CSN` and `USER_ID` columns.
    output_file
        Optional CSV path for persisting the counts.
    """

    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError as exc:  # pragma: no cover - CLI feedback only
        raise SystemExit(f"Error: file '{log_file}' not found") from exc

    required_columns = {"CSN", "USER_ID"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise SystemExit(f"Error: file missing required column(s): {missing}")

    visit_counts = df.groupby("USER_ID")["CSN"].nunique().sort_values(ascending=False)

    if output_file is not None:
        # Overwrite protection: back up existing output file
        if output_file.exists():
            backup = output_file.with_suffix(f".{int(time())}.bak")
            output_file.rename(backup)
            print(f"Warning: Backed up existing file to {backup}")

        visit_counts.rename("visit_count").to_frame().to_csv(output_file)

    return visit_counts


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count visits per provider from a filtered audit log")
    parser.add_argument("log_file", type=Path, help="Path to the filtered audit log CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path to write visit counts",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    visit_counts = count_visits_per_user(args.log_file, output_file=args.output)

    print("Number of visits per user (sorted):")
    print(visit_counts)


if __name__ == "__main__":
    main()
