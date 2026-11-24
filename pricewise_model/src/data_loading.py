"""
Pricewise - shared data loading (used by the Reference Price and the Elasticity code).

Reads valid_US / valid_CA and creates two DuckDB temp tables with one consistent definition:

  tx        one row per transaction line in scope:
            sku, d (order_date), u (order_units), rev, cost (local currency), hierarchy fields
  sku_attr  one row per SKU: modal segment / type / family / sub-family / line / model / name,
            first_d (first observed sale)

Conventions (Phase-1 audit):
  * Scope: segment in (Enterprise, Personal), product_type in (Notebook, Workstations, Desktop),
    revenue > 0, order_units > 0, order_date <= AS_OF (2026-08-23; the week of 2026-08-24 is
    incomplete because only invoiced lines are in the data).
  * Units = order_units (identical to invoice_quantity on 99.99% of rows, never null).
  * US amounts in USD (`revenue`, `cost`).
  * CA amounts in CAD: `invoice_revenue_country_currency`, except rows whose implied FX deviates
    > 5% from that day's median FX (corrupted CAD field, ~0.6% of CA rows), which are rebuilt as
    revenue_usd * daily median FX. CA cost (USD in the raw data) uses the same daily FX.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "processed_data"     # valid_US.csv, valid_CA.csv
PQ_DIR = ROOT / "data" / "processed"           # Parquet copies (created on first use)

AS_OF = pd.Timestamp("2026-08-23")              # Sunday; last complete order week = 2026-08-17
SEGMENTS = ("Enterprise", "Personal")
PRODUCT_TYPES = ("Notebook", "Workstations", "Desktop")
CURRENCY = {"US": "USD", "CA": "CAD"}
FX_TOLERANCE = 0.05


def connect(memory_limit: str = "2GB") -> duckdb.DuckDBPyConnection:
    """DuckDB connection that spills to the OS temp dir, never into the project folder."""
    tmp = Path(tempfile.gettempdir()) / "pricewise_duckdb"
    return duckdb.connect(config={"temp_directory": str(tmp), "memory_limit": memory_limit,
                                  "preserve_insertion_order": False})


def ensure_parquet(country: str, con: duckdb.DuckDBPyConnection) -> Path:
    """Convert the raw CSV to Parquet once (fast columnar reads afterwards)."""
    pq = PQ_DIR / f"valid_{country}.parquet"
    if not pq.exists():
        PQ_DIR.mkdir(parents=True, exist_ok=True)
        csv = RAW_DIR / f"valid_{country}.csv"
        con.execute(f"COPY (SELECT * FROM read_csv('{csv}', header=true, sample_size=-1)) "
                    f"TO '{pq}' (FORMAT parquet, COMPRESSION zstd)")
    return pq


def load_base_tables(con: duckdb.DuckDBPyConnection, country: str, as_of: pd.Timestamp = AS_OF) -> None:
    """Create temp tables `tx` and `sku_attr` for one country."""
    pq = ensure_parquet(country, con)
    if country == "CA":
        fx_join = f"""LEFT JOIN (
              SELECT order_date AS fx_d, median(invoice_revenue_country_currency / revenue) AS fx_day
              FROM read_parquet('{pq}')
              WHERE revenue > 0 AND invoice_revenue_country_currency > 0
              GROUP BY 1) fx ON r.order_date = fx.fx_d"""
        rev = f"""CASE WHEN r.invoice_revenue_country_currency > 0
                        AND abs(r.invoice_revenue_country_currency / r.revenue / fx.fx_day - 1) <= {FX_TOLERANCE}
                       THEN r.invoice_revenue_country_currency
                       ELSE r.revenue * fx.fx_day END"""
        cost = "r.cost * fx.fx_day"
    elif country == "US":
        fx_join, rev, cost = "", "r.revenue", "r.cost"
    else:
        raise ValueError(country)

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE tx AS
        SELECT r.product_id AS sku, r.order_date AS d, r.order_units AS u,
               {rev} AS rev, {cost} AS cost,
               r.segment, r.product_type, r.product_family, r.product_sub_family,
               r.product_line, r.product_model, r.product_name, r.price_tier
        FROM read_parquet('{pq}') r {fx_join}
        WHERE r.segment IN {SEGMENTS} AND r.product_type IN {PRODUCT_TYPES}
          AND r.revenue > 0 AND r.order_units > 0
          AND r.order_date <= DATE '{as_of.date()}'
    """)
    # Static SKU attributes = modal value (hierarchy fields are ~static; a few SKUs moved line).
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sku_attr AS
        SELECT sku,
               mode(segment) AS segment, mode(product_type) AS product_type,
               coalesce(mode(product_family), 'UNKNOWN') AS product_family,
               coalesce(mode(product_sub_family), 'UNKNOWN') AS product_sub_family,
               coalesce(mode(product_line), 'UNKNOWN') AS product_line,
               coalesce(mode(product_model), 'UNKNOWN') AS product_model,
               mode(product_name) AS product_name,
               min(d) AS first_d
        FROM tx GROUP BY sku
    """)
