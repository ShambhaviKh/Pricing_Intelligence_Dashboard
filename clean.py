#!/usr/bin/env python3
"""Merge quarterly synthesized_*.csv into clean_data.csv, standardizing dates and price_tier only.
Place in Capstone/data alongside all quarterly CSV files, then run in PyCharm.
Requires pandas. Preserves all records (including exact duplicates), original columns and source_file.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "clean_data.csv"
CHUNK_SIZE = 100_000
DATE_COLUMNS = ("order_date", "ship_date", "return_date", "week_begin")
MISSING_MARKERS = {"", "nan", "nat", "none", "null", "n/a"}
RANGE_PATTERN = re.compile(r"^(\d+)-(\d+)$")
PLUS_PATTERN = re.compile(r"^(\d+)\+$")

def fix_price_tier(value):
    if pd.isna(value) or str(value).strip().casefold() in MISSING_MARKERS:
        return pd.NA
    text = str(value).strip()
    normalized = re.sub(r"\s+", "", text.replace("$", "").replace(",", ""))
    normalized = re.sub(r"[–—−‐‑‒]", "-", normalized)
    match = RANGE_PATTERN.fullmatch(normalized)
    if match:
        low, high = map(int, match.groups())
        return f"{low}-{high}" if low <= high else text
    match = PLUS_PATTERN.fullmatch(normalized)
    if match:
        return f"{int(match.group(1))}+"
    return text  # Unknown values retained for review.

def fix_date(series):
    text = series.astype("string").str.strip()
    text = text.mask(text.str.casefold().isin(MISSING_MARKERS))
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    iso = text.str.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", na=False)
    us = text.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", na=False)
    parsed.loc[iso] = pd.to_datetime(text.loc[iso], format="%Y-%m-%d", errors="coerce")
    parsed.loc[us] = pd.to_datetime(text.loc[us], format="%m/%d/%Y", errors="coerce")
    invalid = text.notna() & parsed.isna()
    return parsed.dt.strftime("%Y-%m-%d"), invalid, text[invalid]

def main():
    files = sorted(DATA_DIR.glob("synthesized_*.csv"))
    if not files:
        raise FileNotFoundError(f"No synthesized_*.csv found in {DATA_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Temporary file avoids overwriting an existing successful output on failure.
    temporary = OUTPUT_DIR / "clean_data.inprogress.csv"
    if temporary.exists():
        raise FileExistsError(f"Remove or rename leftover temporary file: {temporary}")
    fields = None
    total = 0
    bad_dates = Counter()
    bad_date_examples = Counter()
    tier_before = Counter()
    tier_after = Counter()
    first = True
    try:
        for file in files:
            print(f"Reading {file.name}...", flush=True)
            for batch in pd.read_csv(file, chunksize=CHUNK_SIZE, dtype="string",
                                     keep_default_na=False, encoding="utf-8-sig"):
                batch.columns = batch.columns.str.strip().str.lower()
                if batch.columns.duplicated().any():
                    raise ValueError(f"Duplicate columns in {file.name}")
                if fields is None:
                    fields = list(batch.columns)
                    if "source_file" in fields:
                        raise ValueError("source_file already exists in input")
                    required = set(DATE_COLUMNS) | {"price_tier"}
                    if required - set(fields):
                        raise ValueError(f"Missing required columns: {sorted(required - set(fields))}")
                if set(batch.columns) != set(fields):
                    raise ValueError(f"Column mismatch in {file.name}")
                batch = batch[fields].copy()
                for col in DATE_COLUMNS:
                    standardized, invalid, examples = fix_date(batch[col])
                    bad_dates[col] += int(invalid.sum())
                    bad_date_examples.update((col, str(x)) for x in examples.head(30))
                    # Keep unparseable original date text rather than silently losing information.
                    batch[col] = standardized.mask(invalid, batch[col])
                tier_before.update(batch["price_tier"].fillna("<MISSING>").value_counts().to_dict())
                batch["price_tier"] = batch["price_tier"].map(fix_price_tier).astype("string")
                tier_after.update(batch["price_tier"].fillna("<MISSING>").value_counts().to_dict())
                batch["source_file"] = file.name
                batch.to_csv(temporary, mode="w" if first else "a", header=first,
                             index=False, encoding="utf-8", na_rep="")
                first = False
                total += len(batch)
        temporary.replace(OUTPUT_FILE)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise

    audit = pd.DataFrame([
        {"raw_value": raw, "count": n, "cleaned_value": fix_price_tier(raw)}
        for raw, n in tier_before.items()
    ])
    audit.to_csv(OUTPUT_DIR / "price_tier_audit.csv", index=False)
    pd.DataFrame([
        {"column": col, "original_value": value, "sample_occurrences": n}
        for (col, value), n in bad_date_examples.items()
    ], columns=["column", "original_value", "sample_occurrences"]).to_csv(
        OUTPUT_DIR / "invalid_date_examples.csv", index=False
    )
    print(f"\nDone: {total:,} rows -> {OUTPUT_FILE}")
    print("Unparseable nonempty dates (original strings retained):", dict(bad_dates))
    print("Final price_tier values:", dict(tier_after))
    print("All transactions preserved, including duplicates; no sales filtering applied.")
    print("File is concatenated by quarter, not globally sorted by date.")

if __name__ == "__main__":
    main()
