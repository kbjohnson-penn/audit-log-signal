# From Noise to Signal: A Rule-Based Approach to Isolating Provider Actions from De-Identified EHR Audit Log Data

## Project Overview
This repository accompanies the manuscript “From Noise to Signal: A Rule-Based Approach to Isolating Provider Actions from De-Identified EHR Audit Log Data.” It implements the transparent, rule-based workflow that recovers the primary clinician for each visit from noisy, de-identified audit logs spanning multiple users and time windows. The scripts mirror the paper’s demonstration that simple, interpretable rules reproduce the known distribution of 85 visits across 13 clinicians in the Observer Repository cohort.

## Repository Structure
- `provider_activity_filter.py` – Scores audit log events with the (signature=1, strong=1, default=0) weights, selects the unique top-scoring provider per visit, and exports a clinician-filtered audit log. Optional outputs include a tie report and retention of the helper `winning_provider` column for downstream validation.
- `visit_provider_counts.py` – Summarizes the filtered log by counting unique visits per `USER_ID`, matching the ground-truth distribution reported in the study.
- `weight_permutation_validator.py` – Runs an exhaustive grid search over all integer weight combinations (0…MAX) for the signature/strong/default categories, keeps every combination that assigns each visit to a single top-scoring user with no ties (and, when `EXPECTED_DISTRIBUTION` is populated, also reproduces the expected number of visits per provider ID), and writes the successful `(signature,strong,default)` triples to `successful_weights.txt`. The shipped `successful_weights.txt` was produced with the study's confirmed distribution populated.

## Installation
Install runtime dependencies using the project’s PEP 621 metadata in `pyproject.toml`:

```bash
pip install .
```

For development tools (pytest, black, mypy):

```bash
pip install .[dev]
```

## Data Requirements
All scripts expect audit log CSV files with:
- `CSN` – Encounter identifier (override in the scripts if your column differs).
- `USER_ID` – De-identified user identifier (same note as above).
- `METRIC_DESC` – Event/action descriptor.
- Timestamps and additional columns are preserved as-is for secondary analyses.

## Usage
### 1. Isolate visit-specific clinician activity
```bash
python provider_activity_filter.py audit_log.csv audit_log_filtered.csv \
    --ties-output audit_log_ties.csv
```
- Signature actions (`UCNNOTE_SIGNATCE`, `UCNNOTE_SIGN`, `UCNNOTE_PEND`) and strong visit actions (`VISIT_DIAGNOSES`, `MR_CHIEF_COMPLAINT_FILED`, `MR_VITALS_FILED`, `MR_ENC_ORDERS`, `MR_FOLLOWUP_FILED`) receive a weight of 1; all others default to 0.
- The script returns the clinician-filtered log, a summary of resolved versus tied visits, and (optionally) a CSV of visits requiring manual review because of scoring ties.
 - Safety: when an output path already exists, the script creates a timestamped `.bak` backup before writing.

### 2. Verify visit distribution
```bash
python visit_provider_counts.py audit_log_filtered.csv --output visit_counts.csv
```
- Prints a sorted tally of unique visits per clinician to the console.
- When `--output` is supplied, writes the counts to a CSV for record keeping or figure generation.
 - Safety: if `--output` already exists, a timestamped `.bak` backup is created before writing.

### 3. Enumerate weight combinations (exhaustive grid search)
```bash
python weight_permutation_validator.py
```
- Open the script and adjust the configuration block at the top if your file names, column names, or weight ceiling differ.
- Populate `EXPECTED_DISTRIBUTION` with a dictionary of `{ "provider_id": visit_count }` pairs to restrict the successful list to a confirmed distribution; leave it empty to return every tie-free combination. The manuscript's results were generated with the distribution populated (13 provider IDs; visit counts 21, 14, 14, 8, 7, 6, 5, 3, 3, 1, 1, 1, 1); the IDs are not distributed with this repository.
- Successful combinations are written to `successful_weights.txt` (with a timestamped `.bak` backup if the file exists) and a summary is printed to the console: the total, the minimal combination, and, for each category, the number of successful combinations in which that category's weight is zero (the manuscript's Table 1).

## Results reported in the manuscript
With the Observer audit log and the confirmed distribution populated, `weight_permutation_validator.py` reports:
- 207 of 1,330 weight combinations (15.6%) reproduce the confirmed provider distribution with no tied visits (shipped as `successful_weights.txt`).
- The minimal successful combination is `(1, 1, 0)`.
- Successful combinations with the category weight set to zero (of 120 such combinations per category in the grid): Signature 0, Strong 4, Default 57. The other 150 successful combinations give the Default category a weight of 1 to 3; none give it more than 3.