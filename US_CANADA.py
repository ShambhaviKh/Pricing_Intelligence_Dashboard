#!/usr/bin/env python3
"""Export US and Canada valid sales sorted by order_date (ascending).

Place in Capstone/data and run in PyCharm. Reads data/output/clean_data.csv
(or data/clean_data.csv). Preserves all qualifying transactions including duplicates.
"""
from __future__ import annotations

import csv
import heapq
import tempfile
from contextlib import ExitStack
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
INPUT_OPTIONS = [DATA_DIR / 'output' / 'clean_data.csv', DATA_DIR / 'clean_data.csv']
OUTPUT_DIR = DATA_DIR / 'output'
CHUNK_SIZE = 100_000
REQUIRED = {'segment', 'order_status', 'document_type', 'document_category',
            'revenue', 'order_units', 'country', 'order_date'}


def normalize(series):
    return series.astype('string').str.strip().str.casefold()


def parse_order_date(series):
    text = series.astype('string').str.strip()
    parsed = pd.to_datetime(text, format='%Y-%m-%d', errors='coerce')
    fallback = parsed.isna() & text.ne('') & text.notna()
    if fallback.any():
        parsed.loc[fallback] = pd.to_datetime(
            text.loc[fallback], format='%m/%d/%Y', errors='coerce'
        )
    return parsed


def main():
    source = next((p for p in INPUT_OPTIONS if p.is_file()), None)
    if source is None:
        raise FileNotFoundError('Place clean_data.csv in data/output/ or data/')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pieces = {'US': [], 'CA': []}
    counts = {'US': 0, 'CA': 0}
    scanned = 0
    excluded_invalid_dates = 0
    fields = None
    piece_no = 0
    print('Reading:', source, flush=True)

    with tempfile.TemporaryDirectory(prefix='lenovo_order_date_') as temp_dir:
        for batch in pd.read_csv(source, chunksize=CHUNK_SIZE, dtype='string',
                                 keep_default_na=False, encoding='utf-8-sig'):
            scanned += len(batch)
            batch.columns = batch.columns.str.strip().str.lower()
            if batch.columns.duplicated().any():
                raise ValueError('Duplicate column names in input')
            missing = REQUIRED - set(batch.columns)
            if missing:
                raise ValueError(f'Missing columns: {sorted(missing)}')
            if fields is None:
                fields = list(batch.columns)
            elif set(batch.columns) != set(fields):
                raise ValueError('Input column schema changed across chunks')
            batch = batch[fields].copy()
            revenue = pd.to_numeric(batch['revenue'], errors='coerce')
            units = pd.to_numeric(batch['order_units'], errors='coerce')
            country = batch['country'].astype('string').str.strip().str.upper()
            mask = (normalize(batch['segment']).eq('enterprise')
                    & normalize(batch['order_status']).eq('ships')
                    & normalize(batch['document_type']).eq('invoice')
                    & normalize(batch['document_category']).eq('standard invoice')
                    & revenue.gt(0) & units.gt(0)
                    & country.isin(['US', 'CA']))
            selected = batch.loc[mask].copy()
            if selected.empty:
                continue
            selected['country'] = country.loc[selected.index]
            parsed = parse_order_date(selected['order_date'])
            excluded_invalid_dates += int(parsed.isna().sum())
            selected = selected.loc[parsed.notna()].copy()
            if selected.empty:
                continue
            selected['order_date'] = parsed.loc[selected.index].dt.strftime('%Y-%m-%d')
            for c in ('US', 'CA'):
                part = selected.loc[selected['country'].eq(c), fields]
                if part.empty:
                    continue
                part = part.sort_values('order_date', kind='stable')
                path = Path(temp_dir) / f'{c}_{piece_no:06d}.csv'
                piece_no += 1
                part.to_csv(path, index=False, encoding='utf-8')
                pieces[c].append(path)
                counts[c] += len(part)

        if fields is None:
            raise ValueError('Input CSV is empty')
        for c in ('US', 'CA'):
            target = OUTPUT_DIR / f'{c}_valid_sales_all_transactions.csv'
            with ExitStack() as stack:
                iterators = []
                for path in pieces[c]:
                    handle = stack.enter_context(path.open('r', newline='', encoding='utf-8'))
                    reader = csv.DictReader(handle)
                    iterators.append(((row['order_date'], row) for row in reader))
                # key ensures equal dates never trigger comparisons between dictionaries.
                merged = heapq.merge(*iterators, key=lambda pair: pair[0])
                with target.open('w', newline='', encoding='utf-8') as output:
                    writer = csv.DictWriter(output, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(row for _, row in merged)
            print(f'{c}: {counts[c]:,} rows -> {target}', flush=True)

    print(f'Done. Scanned {scanned:,} rows; excluded {excluded_invalid_dates:,} '
          'otherwise-qualified rows with invalid order_date.', flush=True)
    print('Sorted ascending by order_date. No duplicate rows removed.', flush=True)


if __name__ == '__main__':
    main()
