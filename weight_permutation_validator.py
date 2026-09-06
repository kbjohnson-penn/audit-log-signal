"""Enumerate weight permutations that uniquely assign visits to clinicians."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Dict, Sequence, Tuple, Optional
from time import time

import pandas as pd

# ---------------------------------------------------------------------------
# Simple configuration – tweak values here if your file names or columns differ
# ---------------------------------------------------------------------------
DATA_FILE = Path("audit_log.csv")
OUTPUT_FILE = Path("successful_weights.txt")
VISIT_COL = "CSN"
USER_COL = "USER_ID"
ACTIVITY_COL = "METRIC_DESC"
MAX_WEIGHT = 10  # explore weights 0..MAX_WEIGHT for each category

# Populate provider IDs and expected visit counts if you want to enforce a
# specific distribution. Leave the dictionary empty to accept any tie-free match.
EXPECTED_DISTRIBUTION: Dict[str, int] = {
    # "provider_id": visit_count,
}

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

CATEGORIES = ["SIGNATURE", "STRONG", "DEFAULT"]


def load_audit_log() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise SystemExit(f"Error: audit log '{DATA_FILE}' not found")

    df = pd.read_csv(DATA_FILE)
    required_columns = {VISIT_COL, USER_COL, ACTIVITY_COL}
    missing = required_columns.difference(df.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise SystemExit(f"Error: audit log missing required column(s): {missing_str}")

    category_map: Dict[str, str] = {
        **{activity: "SIGNATURE" for activity in SIGNATURE_ACTIVITIES},
        **{activity: "STRONG" for activity in STRONG_ACTIVITIES},
    }
    df = df.copy()
    df["CATEGORY"] = df[ACTIVITY_COL].map(category_map).fillna("DEFAULT")
    return df


def prepare_visit_user_matrix(df: pd.DataFrame) -> pd.DataFrame:
    counts = (
        df.groupby([VISIT_COL, USER_COL, "CATEGORY"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=CATEGORIES, fill_value=0)
        .reset_index()
    )
    return counts


def evaluate_weights(
    counts_df: pd.DataFrame,
    weights: Sequence[int],
    target_distribution: Optional[Dict[str, int]],
) -> Tuple[bool, bool]:
    """Return (success, has_ties) for the given weight triple."""

    weighted = (
        counts_df[["SIGNATURE", "STRONG", "DEFAULT"]]
        .to_numpy()
        .dot(weights)
    )

    scoring = counts_df[[VISIT_COL, USER_COL]].copy()
    scoring["score"] = weighted

    max_scores = scoring.groupby(VISIT_COL)["score"].transform("max")
    winners = scoring[scoring["score"] == max_scores]

    tie_mask = winners.groupby(VISIT_COL)[USER_COL].transform("size") > 1
    if tie_mask.any():
        return False, True

    assigned = winners.set_index(VISIT_COL)[USER_COL]
    if target_distribution is None:
        return True, False

    distribution = assigned.value_counts()
    success = distribution.to_dict() == target_distribution
    return success, False


def main() -> None:
    df = load_audit_log()
    counts_df = prepare_visit_user_matrix(df)

    target_distribution = EXPECTED_DISTRIBUTION or None

    successful_weights: list[Tuple[int, int, int]] = []
    total_combinations = (MAX_WEIGHT + 1) ** 3 - 1
    print(f"Testing {total_combinations} combinations (0..{MAX_WEIGHT}) excluding (0, 0, 0)...")

    for weights in itertools.product(range(MAX_WEIGHT + 1), repeat=3):
        if weights == (0, 0, 0):
            continue

        success, has_ties = evaluate_weights(counts_df, weights, target_distribution)
        if success and not has_ties:
            successful_weights.append(weights)

    # Overwrite protection: back up existing output file before writing
    if OUTPUT_FILE.exists():
        backup = OUTPUT_FILE.with_suffix(f".{int(time())}.bak")
        OUTPUT_FILE.rename(backup)
        print(f"Warning: Backed up existing file to {backup}")

    OUTPUT_FILE.write_text("signature,strong,default\n", encoding="utf-8")
    with OUTPUT_FILE.open("a", encoding="utf-8") as handle:
        for weights in successful_weights:
            handle.write(f"{weights[0]},{weights[1]},{weights[2]}\n")

    print("--- Permutation Summary ---")
    total_successful = len(successful_weights)
    print(f"Total successful combinations: {total_successful}")

    if total_successful:
        # Category importance (manuscript Table 1): successful combinations in which a
        # category's weight is ZERO. The grid holds (MAX_WEIGHT + 1) ** 2 - 1 such
        # combinations per category. (An earlier version reported "> 0" for DEFAULT.)
        per_category = (MAX_WEIGHT + 1) ** 2 - 1
        signature_zero = sum(1 for w in successful_weights if w[0] == 0)
        strong_zero = sum(1 for w in successful_weights if w[1] == 0)
        default_zero = sum(1 for w in successful_weights if w[2] == 0)

        print(f"Successful combinations with the category weight set to 0 (of {per_category} in the grid):")
        print(f"- Signature weight = 0: {signature_zero}")
        print(f"- Strong weight = 0: {strong_zero}")
        print(f"- Default weight = 0: {default_zero}  (default weight > 0: {total_successful - default_zero})")

        minimal = min(successful_weights, key=lambda w: (sum(w), w))
        print(f"Minimal successful combination: {minimal}")
        preview = ", ".join(str(w) for w in successful_weights[:5])
        print(f"Example successful combinations: {preview}")
    else:
        print("No successful combinations identified.")


if __name__ == "__main__":
    main()
