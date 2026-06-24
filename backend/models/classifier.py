import re
import io
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# These are the data types our classifier can detect
LONG_TRIANGLE = "long_triangle"
WIDE_TRIANGLE = "wide_triangle"
POLICY_LEVEL = "policy_level"
CLAIMS_LEVEL = "claims_level"
UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    data_type: str
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    reasons: list[str]  # why the agent made this decision
    warnings: list[str]  # anything suspicious noticed during classification
    row_count: int
    column_count: int
    detected_columns: dict  # maps role -> actual column name found
    entity_col: Optional[str] = None        # grouping/entity column (e.g. GRCODE, company_id)
    triangle_nature: Optional[str] = None   # "cumulative", "incremental", or None if indeterminate
    is_cas_format: bool = False             # True if the file matches the CAS Loss Reserving DB schema


class DataClassifier:
    """
    Examines a tabular actuarial file and determines what kind of data it contains.
    Produces a ClassificationResult with confidence level and human-readable reasons.
    """

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.file_path: Optional[Path] = None

    def classify(self, file_path: str) -> ClassificationResult:
        """
        Main entry point. Given a file path, reads the file and returns
        a ClassificationResult describing what kind of actuarial data it contains.
        """
        self.file_path = Path(file_path)
        self.df = self._load_file()
        return self._run_classification()

    def classify_from_bytes(self, file_bytes: bytes, filename: str) -> ClassificationResult:
        """
        Alternative entry point for when raw file bytes are available (e.g. from an
        HTTP upload), avoiding a round-trip write to disk.
        Accepts the raw bytes and the original filename (used only to determine the
        file format from its extension).
        """
        suffix = Path(filename).suffix.lower()
        try:
            if suffix == ".csv":
                self.df = pd.read_csv(io.BytesIO(file_bytes))
            elif suffix in [".xlsx", ".xls"]:
                self.df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                self.df = None
        except Exception as e:
            print(f"[DataClassifier] Failed to parse file bytes: {e}")
            self.df = None
        return self._run_classification()

    def _run_classification(self) -> ClassificationResult:
        """
        Shared classification pipeline used by both classify() and classify_from_bytes().
        Assumes self.df has already been populated (or is None on failure).
        """
        # If file couldn't be loaded, return early with UNKNOWN
        if self.df is None:
            return ClassificationResult(
                data_type=UNKNOWN,
                confidence="LOW",
                reasons=["File could not be loaded or parsed."],
                warnings=[],
                row_count=0,
                column_count=0,
                detected_columns={},
            )

        row_count = len(self.df)
        column_count = len(self.df.columns)

        # Ground level: detect column roles and entity grouping
        column_signals, entity_col = self._detect_column_signals()
        print("[DEBUG] Column signals detected:")
        for data_type, matches in column_signals.items():
            print(f"  {data_type}: {matches}")
        if entity_col:
            print(f"[DEBUG] Entity column detected: {entity_col}")

        # Ground level: detect if this is a known CAS format file
        is_cas_format = self._fingerprint_cas_format()
        if is_cas_format:
            print("[DEBUG] CAS Loss Reserving Database format fingerprinted.")

        # Ground level: detect cumulative vs incremental triangle values
        loss_col = column_signals.get(LONG_TRIANGLE, {}).get("loss")
        ay_col = column_signals.get(LONG_TRIANGLE, {}).get("ay")
        lag_col = column_signals.get(LONG_TRIANGLE, {}).get("lag")
        triangle_nature = self._check_cumulative_or_incremental(loss_col, ay_col, lag_col)
        if triangle_nature:
            print(f"[DEBUG] Triangle nature detected: {triangle_nature}")

        # Intermediate level: determine long vs wide shape
        shape, shape_warnings = self._detect_triangle_shape(column_signals)

        return self._score_classification(
            column_signals, shape, shape_warnings, row_count, column_count,
            entity_col, triangle_nature, is_cas_format
        )

    def _load_file(self) -> Optional[pd.DataFrame]:
        """
        Reads the file into a DataFrame based on its extension.
        Returns None if the file cannot be loaded.
        """
        if self.file_path is None:
            raise ValueError("file_path must be set before calling _load_file().")
        try:
            suffix = self.file_path.suffix.lower()

            if suffix == ".csv":
                return pd.read_csv(self.file_path)
            elif suffix in [".xlsx", ".xls"]:
                return pd.read_excel(self.file_path)
            else:
                return None

        except Exception as e:
            print(f"[DataClassifier] Failed to load file: {e}")
            return None

    def _fingerprint_cas_format(self) -> bool:
        """
        Checks whether the loaded DataFrame matches the well-known CAS Loss Reserving
        Database schema (Meyers & Shi, 2011). That schema has a fixed set of columns:
            GRCODE, GRNAME, AccidentYear, DevelopmentYear, DevelopmentLag,
            IncurLoss_*, CumPaidLoss_*, BulkLoss_*, EarnedPremDIR_*, ...

        Returns True only when the column overlap is strong enough to be a confident
        fingerprint match (at least 4 of the 6 core columns present).
        """
        if self.df is None:
            return False

        # Core columns that uniquely identify the CAS format
        CAS_CORE_COLUMNS = {
            "grcode", "grname", "accidentyear", "developmentyear",
            "developmentlag", "incurloss", "cumpaidloss"
        }
        cols_lower = {re.sub(r'[_\s-]', '', col).lower() for col in self.df.columns}

        # Count how many CAS core column stems appear in the actual headers
        matches = sum(
            1 for cas_col in CAS_CORE_COLUMNS
            if any(cas_col in actual_col for actual_col in cols_lower)
        )
        return matches >= 4

    def _check_cumulative_or_incremental(
        self,
        loss_col: Optional[str],
        ay_col: Optional[str],
        lag_col: Optional[str],
    ) -> Optional[str]:
        """
        Inspects the actual loss values in a long-format triangle to determine
        whether they are cumulative (each value >= prior diagonal) or incremental
        (each value represents only that period's movement, may be negative).

        This matters because Chain Ladder and most reserving methods require
        cumulative data. Feeding incremental data without conversion is a
        common source of silent errors.

        Returns:
            "cumulative"   — values consistently increase along development axis.
            "incremental"  — values are non-monotone or frequently negative.
            None           — not enough information to determine (missing columns,
                             insufficient rows, or mixed signals).
        """
        if self.df is None or loss_col is None or ay_col is None or lag_col is None:
            return None

        try:
            # Work on a clean subset with no nulls in key columns
            subset = self.df[[ay_col, lag_col, loss_col]].dropna()
            if len(subset) < 4:
                return None  # too few rows to judge

            # Sort by (accident year, development lag) to trace development paths
            subset = subset.sort_values([ay_col, lag_col])

            monotone_count = 0
            non_monotone_count = 0

            for _, group in subset.groupby(ay_col):
                values = group[loss_col].values
                if len(values) < 2:
                    continue
                # Check each consecutive pair along the development axis
                for i in range(1, len(values)):
                    if values[i] >= values[i - 1]:
                        monotone_count += 1
                    else:
                        non_monotone_count += 1

            total = monotone_count + non_monotone_count
            if total == 0:
                return None

            monotone_ratio = monotone_count / total

            # Cumulative: >= 90% of consecutive pairs are non-decreasing
            if monotone_ratio >= 0.90:
                return "cumulative"
            # Incremental: >= 40% of consecutive pairs decrease (typical for incremental data)
            elif monotone_ratio < 0.60:
                return "incremental"
            else:
                return None  # mixed signals — do not guess

        except Exception as e:
            print(f"[DataClassifier] Could not determine triangle nature: {e}")
            return None

    def _detect_entity_column(self) -> Optional[str]:
        """
        Scans for a column that groups rows into independent entities such as
        companies, lines of business, or portfolios (e.g. GRCODE, company_id,
        entity, line_of_business).

        A valid entity column must:
        - Match known entity-role vocabulary via regex.
        - Contain low-cardinality values relative to the total row count
          (i.e. fewer than 20% of rows are unique entities).
        - NOT be the accident year column (already handled separately).
        """
        if self.df is None:
            return None

        entity_pattern = re.compile(
            r'\b(grcode|gr[\s_-]*code|company[\s_-]*id|company[\s_-]*code|entity|'
            r'group[\s_-]*code|insurer|carrier|lob|line[\s_-]*of[\s_-]*business|'
            r'segment|portfolio|source|book)\b',
            re.IGNORECASE
        )
        # Columns that should NOT be mistaken for entity columns
        exclude_pattern = re.compile(
            r'\b(accident[\s_-]*year|origin[\s_-]*year|ay|development|lag|loss|paid|incurred)\b',
            re.IGNORECASE
        )

        for col in self.df.columns:
            col_str = str(col).strip()
            if entity_pattern.search(col_str) and not exclude_pattern.search(col_str):
                n_unique = self.df[col].nunique()
                n_rows = len(self.df)
                # Entity columns have low cardinality — far fewer unique values than rows
                if n_unique > 1 and n_unique < max(2, n_rows * 0.2):
                    return col_str

        return None

    def _detect_column_signals(self) -> tuple[dict, Optional[str]]:
        """
        Scans column names using regular expressions and verifies column
        contents to ensure robust keyword signals without false positives.
        Also detects the entity/grouping column if one exists.
        Returns a tuple of (column_signals_dict, entity_col_name).
        """
        if self.df is None:
            raise ValueError(
                "df must be loaded before calling _detect_column_signals()."
            )

        ay_pattern = re.compile(r'(ay|accident[\s_-]*year|origin[\s_-]*year|accidentyear|originyear|origin)', re.IGNORECASE)
        dev_pattern = re.compile(r'(dy|dev[\s_-]*year|development[\s_-]*year|dev[\s_-]*lag|development[\s_-]*lag|devyear|developmentyear|devlag|developmentlag|lag|age|period)', re.IGNORECASE)
        loss_pattern = re.compile(r'(loss|paid|incurred|payment|claim[\s_-]*amount|incremental|cumulative)', re.IGNORECASE)

        policy_patterns = [
            re.compile(r'\b(policy|premium|exposure|sum[\s_-]*insured|inception|expiry|renewal|underwriting)\b', re.IGNORECASE),
            re.compile(r'\b(insured|coverage|policyholder)\b', re.IGNORECASE)
        ]

        claims_patterns = [
            re.compile(r'\b(claim[\s_-]*id|claim[\s_-]*number|claim[\s_-]*no|claimant|loss[\s_-]*date|report[\s_-]*date|settlement[\s_-]*date)\b', re.IGNORECASE),
            re.compile(r'\b(reserve|ibnr|open|closed|status)\b', re.IGNORECASE)
        ]

        detected_triangle = {}
        detected_policy = {}
        detected_claims = {}

        for col in self.df.columns:
            col_str = str(col).strip()

            # 1. Check for Triangle indicators
            if ay_pattern.search(col_str):
                # Verify that values look like years (e.g. 1900-2100 or datetimes)
                non_nulls = self.df[col].dropna()
                if not non_nulls.empty:
                    first_val = non_nulls.iloc[0]
                    if pd.api.types.is_numeric_dtype(non_nulls):
                        if non_nulls.min() > 1900 and non_nulls.max() < 2100:
                            detected_triangle["accident_year"] = col_str
                    elif isinstance(first_val, str) or pd.api.types.is_datetime64_any_dtype(non_nulls):
                        detected_triangle["accident_year"] = col_str

            elif dev_pattern.search(col_str):
                # Verify that values are small integers
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    non_nulls = self.df[col].dropna()
                    if not non_nulls.empty and non_nulls.min() >= 0 and non_nulls.max() <= 360:
                        detected_triangle["development_lag"] = col_str

            elif loss_pattern.search(col_str):
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    detected_triangle["loss_value"] = col_str

            # 2. Check for Policy-level indicators
            for pat in policy_patterns:
                if pat.search(col_str):
                    detected_policy[col_str] = col_str

            # 3. Check for Claims-level indicators
            for pat in claims_patterns:
                if pat.search(col_str):
                    detected_claims[col_str] = col_str

        # Build triangle signals dict
        triangle_signals = {}
        if "accident_year" in detected_triangle:
            triangle_signals["ay"] = detected_triangle["accident_year"]
        if "development_lag" in detected_triangle:
            triangle_signals["lag"] = detected_triangle["development_lag"]
        if "loss_value" in detected_triangle:
            triangle_signals["loss"] = detected_triangle["loss_value"]

        # Check if we have wide columns (purely numeric or ending in months/years)
        wide_col_pattern = re.compile(r'^\d+\s*(m|months|lags|years|yrs)?$', re.IGNORECASE)
        wide_cols_detected = []
        for col in self.df.columns:
            if wide_col_pattern.match(str(col).strip()):
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    wide_cols_detected.append(str(col))

        wide_triangle_signals = dict(triangle_signals)
        if wide_cols_detected:
            wide_triangle_signals["wide_lags"] = wide_cols_detected

        # Detect entity/grouping column separately
        entity_col = self._detect_entity_column()

        return {
            LONG_TRIANGLE: triangle_signals,
            WIDE_TRIANGLE: wide_triangle_signals,
            POLICY_LEVEL: detected_policy,
            CLAIMS_LEVEL: detected_claims,
        }, entity_col

    def _detect_triangle_shape(
        self, column_signals: dict
    ) -> tuple[Optional[str], list[str]]:
        """
        Determines whether triangle data is long or wide format based on:
        1. Whether specific column names are purely numeric or represent months (for WIDE format)
        2. Whether the accident year repeats and is accompanied by a dev lag column (for LONG format)
        """
        if self.df is None:
            raise ValueError(
                "df must be loaded before calling _detect_triangle_shape()."
            )
            
        warnings = []
        
        # Check if we have columns that look like wide triangle development columns (e.g. "12", "24", "12 months")
        wide_col_pattern = re.compile(r'^\d+\s*(m|months|lags|years|yrs)?$', re.IGNORECASE)
        wide_matching_cols = []
        for col in self.df.columns:
            if wide_col_pattern.match(str(col).strip()):
                # Verify that it is numeric data (to exclude headers matching numeric IDs)
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    wide_matching_cols.append(col)

        # If we have 3 or more numerical/lag-like columns, it is very likely a WIDE triangle
        if len(wide_matching_cols) >= 3:
            return WIDE_TRIANGLE, warnings

        # Fallback to checking accident year repetition for long triangles
        accident_year_col = column_signals.get(LONG_TRIANGLE, {}).get("ay")
        if accident_year_col is None:
            # Look up standard accident year names if not detected in signals
            columns_lower = {col.lower().strip(): col for col in self.df.columns}
            for key in ["accidentyear", "accident_year", "ay", "origin_year", "origin"]:
                if key in columns_lower:
                    accident_year_col = columns_lower[key]
                    break

        if accident_year_col is None:
            return None, warnings

        value_counts = self.df[accident_year_col].value_counts()
        avg_repeats = value_counts.mean()

        # A typical single triangle's development periods rarely exceed ~20
        REASONABLE_MAX_DEV_PERIODS = 20

        if avg_repeats > 1.5:
            # Verify if we also have a lag column to confirm LONG_TRIANGLE
            if "lag" in column_signals.get(LONG_TRIANGLE, {}):
                shape_result = LONG_TRIANGLE
            else:
                shape_result = LONG_TRIANGLE
                warnings.append("Detected repeating origin periods, but no development lag column was identified.")
                
            if avg_repeats > REASONABLE_MAX_DEV_PERIODS:
                warnings.append(
                    f"Accident year values repeat an average of {avg_repeats:.0f} times, "
                    f"which exceeds a typical single triangle's development period count. "
                    f"This file may contain multiple stacked entities (e.g. companies) "
                    f"rather than a single triangle. Recommend entity-level inspection."
                )
        else:
            shape_result = WIDE_TRIANGLE

        return shape_result, warnings

    def _score_classification(
        self,
        column_signals: dict,
        shape: Optional[str],
        shape_warnings: list[str],
        row_count: int,
        column_count: int,
        entity_col: Optional[str] = None,
        triangle_nature: Optional[str] = None,
        is_cas_format: bool = False,
    ) -> ClassificationResult:
        """
        Combines all signals into a final classification decision.
        Applies the minimum viable triangle gate and enriches reasons
        with cumulative/incremental and CAS format findings.
        """
        reasons = []
        warnings = list(shape_warnings)  # carry forward any shape-detection warnings

        # Count how many keyword matches each candidate type received
        match_counts = {
            data_type: len(matches) for data_type, matches in column_signals.items()
        }

        # Sort candidates by match count, highest first
        ranked = sorted(match_counts.items(), key=lambda item: item[1], reverse=True)
        top_type, top_count = ranked[0]
        second_type, second_count = ranked[1] if len(ranked) > 1 else (None, 0)

        # No meaningful signal at all
        if top_count == 0:
            return ClassificationResult(
                data_type=UNKNOWN,
                confidence="LOW",
                reasons=[
                    "No recognizable column signals found for any known data type."
                ],
                warnings=warnings,
                row_count=row_count,
                column_count=column_count,
                detected_columns={},
            )

        # ── Minimum viable triangle gate (Medium Priority) ──────────────────────
        # A triangle classification requires at minimum an accident year column
        # AND at least one numeric loss column. Without both, demote to UNKNOWN.
        if top_type in [LONG_TRIANGLE, WIDE_TRIANGLE]:
            has_ay = "ay" in column_signals.get(LONG_TRIANGLE, {})
            has_loss = (
                "loss" in column_signals.get(LONG_TRIANGLE, {})
                or "wide_lags" in column_signals.get(WIDE_TRIANGLE, {})
            )
            if not has_ay or not has_loss:
                missing = []
                if not has_ay:
                    missing.append("accident/origin year column")
                if not has_loss:
                    missing.append("numeric loss/value column")
                warnings.append(
                    f"Triangle classification rejected: missing required column(s): "
                    f"{', '.join(missing)}. A valid triangle needs both an origin year "
                    f"and at least one numeric loss column."
                )
                return ClassificationResult(
                    data_type=UNKNOWN,
                    confidence="LOW",
                    reasons=["Failed minimum viable triangle validation."],
                    warnings=warnings,
                    row_count=row_count,
                    column_count=column_count,
                    detected_columns={},
                )

        # A tie between LONG_TRIANGLE and WIDE_TRIANGLE is expected, not ambiguous --
        # they share keyword lists by design. Shape detection breaks this tie.
        triangle_tie = {top_type, second_type} == {LONG_TRIANGLE, WIDE_TRIANGLE}

        # Close tie between top two candidates -- genuine ambiguity, don't guess
        if second_count > 0 and (top_count - second_count) <= 1 and not triangle_tie:
            warnings.append(
                f"Column signals were ambiguous between '{top_type}' ({top_count} matches) "
                f"and '{second_type}' ({second_count} matches)."
            )
            return ClassificationResult(
                data_type=UNKNOWN,
                confidence="LOW",
                reasons=[
                    f"Top candidates '{top_type}' and '{second_type}' were too close to call."
                ],
                warnings=warnings,
                row_count=row_count,
                column_count=column_count,
                detected_columns={},
            )

        if triangle_tie:
            reasons.append(
                f"Column signals tied between 'long_triangle' and 'wide_triangle' "
                f"({top_count} matches each) -- expected, since shape determines this distinction."
            )

        reasons.append(
            f"'{top_type}' had the strongest column signal match ({top_count} keywords/keys)."
        )

        # If the leading candidate is a triangle type, cross-check against shape detection
        if top_type in [LONG_TRIANGLE, WIDE_TRIANGLE]:
            if shape == top_type:
                confidence = "HIGH"
                reasons.append(
                    f"Shape detection confirmed '{shape}', agreeing with column signals."
                )
            elif shape is not None and shape != top_type:
                confidence = "MEDIUM"
                reasons.append(
                    f"Shape detection suggested '{shape}', which disagrees with column-signal "
                    f"leader '{top_type}'. Using shape detection result as more reliable."
                )
                top_type = shape  # structural evidence outweighs keyword guessing
            else:
                confidence = "MEDIUM"
                reasons.append(
                    "Shape detection was inconclusive; relying on column signals alone."
                )
        else:
            # Policy or claims level -- shape detection doesn't apply, so cap confidence
            confidence = "MEDIUM"
            reasons.append("No structural cross-check available for this data type.")

        # ── CAS format fingerprint (Low Priority) ───────────────────────────────
        if is_cas_format:
            confidence = "HIGH"  # CAS format is an unambiguous fingerprint — upgrade confidence
            reasons.append(
                "CAS Loss Reserving Database format fingerprinted. Confidence upgraded to HIGH."
            )

        # ── Cumulative vs incremental nature (Medium Priority) ───────────────────
        if triangle_nature == "cumulative":
            reasons.append(
                "Loss values are cumulative (monotonically non-decreasing along development axis). "
                "Compatible with Chain Ladder and standard reserving methods."
            )
        elif triangle_nature == "incremental":
            warnings.append(
                "Loss values appear to be INCREMENTAL, not cumulative. "
                "Most reserving methods (Chain Ladder, BF) require cumulative data. "
                "Convert to cumulative before building the triangle."
            )

        # ── Entity column ────────────────────────────────────────────────────────
        if entity_col:
            reasons.append(f"Entity/grouping column detected: '{entity_col}'.")

        return ClassificationResult(
            data_type=top_type,
            confidence=confidence,
            reasons=reasons,
            warnings=warnings,
            row_count=row_count,
            column_count=column_count,
            detected_columns=column_signals.get(top_type, {}),
            entity_col=entity_col,
            triangle_nature=triangle_nature,
            is_cas_format=is_cas_format,
        )
