"""Filter audit logs to isolate clinician actions for each visit."""

from __future__ import annotations

import argparse
from time import time
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd

SIGNATURE_ACTIVITIES = [
    "UCNNOTE_SIGNATCE",  # NOTE: Typo exists in source EHR system - do not "fix"
    "UCNNOTE_SIGN",
    "UCNNOTE_PEND",
]

STRONG_ACTIVITIES = [
    "VISIT_DIAGNOSES",
    "MR_CHIEF_COMPLAINT_FILED",
    "MR_VITALS_FILED",
    "MR_ENC_ORDERS",
    "MR_FOLLOWUP_FILED",
]

DEFAULT_WEIGHT = 0
WEIGHTS = {"SIGNATURE": 1, "STRONG": 1, "DEFAULT": DEFAULT_WEIGHT}


def build_activity_weight_map() -> Dict[str, int]:
    """Construct a lookup of metric description to weight."""

    weight_map: Dict[str, int] = {}
    weight_map.update({activity: WEIGHTS["SIGNATURE"] for activity in SIGNATURE_ACTIVITIES})
    weight_map.update({activity: WEIGHTS["STRONG"] for activity in STRONG_ACTIVITIES})
    return weight_map


def filter_audit_log_by_winning_provider(
    log_file: Path,
    output_file: Path,
    *,
    ties_output: Optional[Path] = None,
    keep_winning_column: bool = False,
) -> None:
    """Filter the audit log so only the winning provider's actions remain.

    Parameters
    ----------
    log_file
        Path to the raw audit log containing at least `CSN`, `USER_ID`, and `METRIC_DESC` columns.
    output_file
        Destination CSV containing actions from the winning provider per visit.
    ties_output
        Optional CSV path to record visits whose top scores result in ties.
    keep_winning_column
        Retains the `winning_provider` helper column in the filtered output when True.
    """

    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError as exc:  # pragma: no cover - CLI feedback only
        raise SystemExit(f"Error: log file '{log_file}' not found") from exc

    required_columns = {"CSN", "USER_ID", "METRIC_DESC"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise SystemExit(f"Error: log file missing required column(s): {missing}")

    activity_weights = build_activity_weight_map()
    df["__weight"] = df["METRIC_DESC"].map(activity_weights).fillna(WEIGHTS["DEFAULT"])

    scores = (
        df.groupby(["CSN", "USER_ID"], as_index=False)["__weight"].sum().rename(columns={"__weight": "score"})
    )
    scores["max_score"] = scores.groupby("CSN")["score"].transform("max")
    winners = scores[scores["score"] == scores["max_score"]].copy()
    winners["tie"] = winners.groupby("CSN")["USER_ID"].transform("size") > 1

    tie_rows = winners[winners["tie"]]
    unique_winners = winners[~winners["tie"]].copy()
    winning_map = dict(zip(unique_winners["CSN"], unique_winners["USER_ID"]))

    df["winning_provider"] = df["CSN"].map(winning_map)
    filtered_df = df[df["USER_ID"] == df["winning_provider"]].copy()

    if not keep_winning_column:
        filtered_df.drop(columns=["winning_provider"], inplace=True)

    filtered_df.drop(columns=["__weight"], inplace=True)

    # Overwrite protection: back up existing output files
    if output_file.exists():
        backup = output_file.with_suffix(f".{int(time())}.bak")
        output_file.rename(backup)
        print(f"Warning: Backed up existing file to {backup}")

    filtered_df.to_csv(output_file, index=False)

    if ties_output is not None:
        tie_export = tie_rows[["CSN", "USER_ID", "score"]].sort_values(["CSN", "USER_ID"])
        if tie_export.empty:
            ties_output.write_text("CSN,USER_ID,score\n", encoding="utf-8")
        else:
            # Overwrite protection for ties output as well
            if ties_output.exists():
                backup = ties_output.with_suffix(f".{int(time())}.bak")
                ties_output.rename(backup)
                print(f"Warning: Backed up existing file to {backup}")

            tie_export.to_csv(ties_output, index=False)

    unresolved_visits = tie_rows["CSN"].nunique()
    resolved_visits = unique_winners["CSN"].nunique()

    print(f"Filtered log saved to {output_file}")
    print(f"Resolved visits: {resolved_visits}")
    print(f"Visits requiring manual review due to ties: {unresolved_visits}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter audit logs to isolate the winning provider per visit")
    parser.add_argument("log_file", type=Path, help="Path to the raw audit log CSV")
    parser.add_argument("output_file", type=Path, help="Path to write the filtered audit log CSV")
    parser.add_argument(
        "--ties-output",
        type=Path,
        dest="ties_output",
        default=None,
        help="Optional CSV file to capture visits with tied winning scores",
    )
    parser.add_argument(
        "--keep-winning-provider",
        action="store_true",
        help="Retain the helper 'winning_provider' column in the filtered output",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    filter_audit_log_by_winning_provider(
        args.log_file,
        args.output_file,
        ties_output=args.ties_output,
        keep_winning_column=args.keep_winning_provider,
    )


if __name__ == "__main__":
    main()
