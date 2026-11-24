"""
Module A - Reference Price: feature construction.

Builds, for every (SKU, forecast origin), leakage-free features computed only from
transactions with order_date <= origin:

  * SKU ASP7 / ASP30 / ASP90 / lifetime ASP (units-weighted: sum revenue / sum order_units)
  * transaction / unit counts per window, days since last sale, 90-day price dispersion
  * product-hierarchy ASP90 at Type -> Family -> Sub-family -> Line -> Model
  * a hierarchical-shrinkage "anchor" price that every model predicts relative to

Data loading (scope, units, USD/CAD handling, AS_OF) lives in data_loading.py and is shared
with the elasticity code. Conventions (all established in the Phase-1 audit):
  * Time axis = ORDER week (Monday start) derived from order_date.  `week_begin` in the
    raw data is the SHIP week and is not used.
  * Units = order_units (identical to invoice_quantity on 99.99% of rows, never null/<=0).
  * US prices in USD (`revenue`).  CA prices in CAD: `invoice_revenue_country_currency`,
    except rows whose implied FX deviates >5% from that day's median FX (corrupted CAD
    field, ~0.6% of CA rows) which are rebuilt as revenue_usd * daily median FX.
    CA cost (USD in the raw data) is converted with the same daily FX.
  * AS_OF = 2026-08-23 (Sunday).  Orders after that are incomplete because the data only
    contains invoiced lines, so the week of 2026-08-24 is excluded.
  * No seasonality variables (month / quarter / holiday) and no product-age / lifecycle
    variables by design for v1: the Reference Price uses ASP history + product hierarchy
    only. Age and seasonality are reserved for the demand (units) model.
  * A week with no sales has no observed price: it is never used as a target and is
    never treated as price 0.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

import data_loading as dl
from data_loading import AS_OF, CURRENCY, ROOT, connect  # noqa: F401  (re-exported for reference_model)

WARMUP_DAYS = 91                             # first target week needs >= 91 days of history
LEVELS = ["type", "family", "subfam", "line", "model"]   # coarse -> fine
WINDOWS = (7, 30, 90)

# Feature lists used by the models
NUM_FEATURES = [
    "r7", "r30", "r90", "rlife",
    "r_type", "r_family", "r_subfam", "r_line", "r_model", "r_prior",
    "log_anchor", "lu7", "lu30", "lu90", "ltx30",
    "days_since_last", "cv90",
    "has7", "has30", "has90", "has_life",
]
CAT_FEATURES = ["product_type", "segment", "product_family"]


# --------------------------------------------------------------------------- loading
def prepare_tables(con: duckdb.DuckDBPyConnection, country: str, as_of: pd.Timestamp = AS_OF) -> None:
    """Shared tx / sku_attr tables (data_loading.py) + Reference-Price-specific helper tables."""
    dl.load_base_tables(con, country, as_of)
    # Nested keys by construction (Line is concatenated under Sub-family, etc.)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sku_attr AS
        SELECT *,
               segment || '|' || product_type AS k_type,
               segment || '|' || product_type || '|' || product_family AS k_family,
               segment || '|' || product_type || '|' || product_family || '|' || product_sub_family AS k_subfam,
               segment || '|' || product_type || '|' || product_family || '|' || product_sub_family
                       || '|' || product_line AS k_line,
               segment || '|' || product_type || '|' || product_family || '|' || product_sub_family
                       || '|' || product_line || '|' || product_model AS k_model
        FROM sku_attr
    """)

    # Daily SKU aggregates and running totals (for O(1) window sums via ASOF joins)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sku_cum AS
        WITH daily AS (
            SELECT sku, d, sum(u) AS u, sum(rev) AS rev, count(*) AS tx, sum(cost) AS cost,
                   sum(u * ln(rev / u)) AS slp, sum(u * ln(rev / u) * ln(rev / u)) AS slp2
            FROM tx GROUP BY sku, d)
        SELECT sku, d,
               sum(u)    OVER w AS cu,   sum(rev)  OVER w AS crev, sum(tx)   OVER w AS ctx,
               sum(cost) OVER w AS ccost, sum(slp) OVER w AS cslp, sum(slp2) OVER w AS cslp2
        FROM daily
        WINDOW w AS (PARTITION BY sku ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    """)

    for lvl in LEVELS:
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE lvl_cum_{lvl} AS
            WITH daily AS (
                SELECT a.k_{lvl} AS key, t.d, sum(t.u) AS u, sum(t.rev) AS rev
                FROM tx t JOIN sku_attr a USING (sku) GROUP BY 1, 2)
            SELECT key, d, sum(u) OVER w AS cu, sum(rev) OVER w AS crev
            FROM daily
            WINDOW w AS (PARTITION BY key ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        """)

    # Weekly (order-week) SKU table: targets and count of prior sales weeks (reporting only)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sku_week AS
        SELECT sku, CAST(date_trunc('week', d) AS DATE) AS ow,
               sum(u) AS u, sum(rev) AS rev, sum(cost) AS cost, count(*) AS tx
        FROM tx GROUP BY 1, 2
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sku_wcum AS
        SELECT sku, CAST(ow + INTERVAL 6 DAY AS DATE) AS week_end,
               row_number() OVER (PARTITION BY sku ORDER BY ow) AS n_weeks
        FROM sku_week
    """)


# --------------------------------------------------------------------------- raw features
def build_raw_features(con: duckdb.DuckDBPyConnection, origins: pd.DataFrame) -> pd.DataFrame:
    """origins: DataFrame with columns sku, o (origin date = last day of known data) + any extras.

    Returns window ASPs / counts / hierarchy ASPs computed strictly from order_date <= o.
    """
    g = origins.copy()
    g["o"] = pd.to_datetime(g["o"]).dt.date
    for w in WINDOWS:
        g[f"o{w}"] = (pd.to_datetime(g["o"]) - pd.Timedelta(days=w)).dt.date
    g["row_id"] = np.arange(len(g))
    con.register("orig_df", g)
    con.execute("CREATE OR REPLACE TEMP TABLE orig AS SELECT * FROM orig_df")
    con.unregister("orig_df")

    cols = ["cu", "crev", "ctx", "ccost", "cslp", "cslp2"]
    sel, joins = [], []
    for tag, oc in [("0", "o")] + [(str(w), f"o{w}") for w in WINDOWS]:
        sel += [f"c{tag}.{c} AS {c}_{tag}" for c in cols]
        joins.append(f"ASOF LEFT JOIN sku_cum c{tag} ON g.sku = c{tag}.sku AND g.{oc} >= c{tag}.d")
    sel.append("c0.d AS last_d")
    lvl_sel, lvl_joins = [], []
    for lvl in LEVELS:
        for tag, oc in [("0", "o"), ("90", "o90")]:
            a = f"l_{lvl}_{tag}"
            lvl_sel += [f"{a}.cu AS {lvl}_cu_{tag}", f"{a}.crev AS {lvl}_crev_{tag}"]
            lvl_joins.append(f"ASOF LEFT JOIN lvl_cum_{lvl} {a} ON a.k_{lvl} = {a}.key AND g.{oc} >= {a}.d")

    sql = f"""
        SELECT g.*, a.segment, a.product_type, a.product_family, a.product_sub_family,
               a.product_line, a.product_model, a.product_name, a.first_d,
               a.k_type, a.k_family, a.k_subfam, a.k_line, a.k_model,
               wc.n_weeks AS hist_weeks,
               {", ".join(sel + lvl_sel)}
        FROM orig g
        JOIN sku_attr a ON g.sku = a.sku
        ASOF LEFT JOIN sku_wcum wc ON g.sku = wc.sku AND g.o >= wc.week_end
        {" ".join(joins)}
        {" ".join(lvl_joins)}
    """
    df = con.execute(sql).df().sort_values("row_id").reset_index(drop=True)

    out = df.copy()
    z = lambda c: out[c].fillna(0.0)
    for w in WINDOWS:
        out[f"u{w}"] = z("cu_0") - z(f"cu_{w}")
        out[f"rev{w}"] = z("crev_0") - z(f"crev_{w}")
        out[f"tx{w}"] = z("ctx_0") - z(f"ctx_{w}")
        out[f"asp{w}"] = np.where(out[f"u{w}"] > 0, out[f"rev{w}"] / out[f"u{w}"].where(out[f"u{w}"] > 0), np.nan)
    out["u_life"] = z("cu_0")
    out["asp_life"] = np.where(out["u_life"] > 0, z("crev_0") / out["u_life"].where(out["u_life"] > 0), np.nan)
    cost90 = z("ccost_0") - z("ccost_90")
    out["unit_cost90"] = np.where(out["u90"] > 0, cost90 / out["u90"].where(out["u90"] > 0), np.nan)
    m = (z("cslp_0") - z("cslp_90")) / out["u90"].where(out["u90"] > 0)
    v = (z("cslp2_0") - z("cslp2_90")) / out["u90"].where(out["u90"] > 0) - m ** 2
    out["cv90"] = np.sqrt(np.clip(v, 0, None))

    for lvl in LEVELS:
        u = z(f"{lvl}_cu_0") - z(f"{lvl}_cu_90")
        r = z(f"{lvl}_crev_0") - z(f"{lvl}_crev_90")
        out[f"u90_{lvl}"] = u
        out[f"asp90_{lvl}"] = np.where(u > 0, r / u.where(u > 0), np.nan)

    o = pd.to_datetime(out["o"])
    out["days_since_last"] = (o - pd.to_datetime(out["last_d"])).dt.days.clip(upper=365)
    out["hist_weeks"] = out["hist_weeks"].fillna(0)

    drop = [c for c in out.columns if c.startswith(("cu_", "crev_", "ctx_", "ccost_", "cslp"))
            or "_cu_" in c or "_crev_" in c or c in ("o7", "o30", "o90")]
    return out.drop(columns=drop)


# --------------------------------------------------------------------------- anchor + model features
def hierarchical_anchor(df: pd.DataFrame, k_h: float, k_s: float) -> pd.DataFrame:
    """Hierarchical shrinkage in log space.

    prior_type = log ASP90(Type);  for each finer level L:
        prior_L = (n_L * log ASP90_L + k_h * prior_parent) / (n_L + k_h),  n_L = units in 90 days
    SKU:   base = shrink(ASP90_sku, u90, prior_model)   (or 50/50 lifetime ASP vs prior if no 90d sales)
           A    = shrink(ASP30, u30, base) then shrink(ASP7, u7, .) with weight k_s
    Returns df with columns log_prior (model-level prior) and log_anchor.
    """
    out = df.copy()
    lp = np.log(out["asp90_type"])
    lp = lp.fillna(np.nanmedian(lp))
    for lvl in LEVELS[1:]:
        n = out[f"u90_{lvl}"].fillna(0).to_numpy()
        la = np.log(out[f"asp90_{lvl}"]).to_numpy()
        lp = np.where(n > 0, (n * np.nan_to_num(la) + k_h * lp) / (n + k_h), lp)
    out["log_prior"] = lp

    def shrink(u, asp, parent, k):
        u = u.fillna(0).to_numpy()
        la = np.nan_to_num(np.log(asp.to_numpy()))
        return np.where(u > 0, (u * la + k * parent) / (u + k), parent)

    life = np.log(out["asp_life"]).to_numpy()
    base_nohist = np.where(np.isfinite(life), 0.5 * np.nan_to_num(life) + 0.5 * lp, lp)
    base = shrink(out["u90"], out["asp90"], base_nohist, k_s)
    a = shrink(out["u30"], out["asp30"], base, k_s)
    a = shrink(out["u7"], out["asp7"], a, k_s)
    out["log_anchor"] = a
    return out


def make_model_frame(raw: pd.DataFrame, k_h: float, k_s: float) -> pd.DataFrame:
    """Add anchor and the anchor-relative features consumed by every model."""
    df = hierarchical_anchor(raw, k_h, k_s)
    la = df["log_anchor"]
    rel = lambda s: np.log(s) - la
    df["r7"], df["r30"], df["r90"] = rel(df["asp7"]), rel(df["asp30"]), rel(df["asp90"])
    df["rlife"] = rel(df["asp_life"])
    for lvl in LEVELS:
        df[f"r_{lvl}"] = rel(df[f"asp90_{lvl}"])
    df["r_prior"] = df["log_prior"] - la
    df["lu7"], df["lu30"], df["lu90"] = np.log1p(df["u7"]), np.log1p(df["u30"]), np.log1p(df["u90"])
    df["ltx30"] = np.log1p(df["tx30"])
    df["has7"] = (df["u7"] > 0).astype(int)
    df["has30"] = (df["u30"] > 0).astype(int)
    df["has90"] = (df["u90"] > 0).astype(int)
    df["has_life"] = (df["u_life"] > 0).astype(int)

    # Fallback-filled ASP baselines (used by baseline models and reporting)
    prior = np.exp(df["log_prior"])
    life = df["asp_life"].fillna(prior)
    df["base_asp90"] = df["asp90"].fillna(life)
    df["base_asp30"] = df["asp30"].fillna(df["base_asp90"])
    df["base_asp7"] = df["asp7"].fillna(df["base_asp30"])
    df["anchor"] = np.exp(la)

    hw = df["hist_weeks"]
    df["history_bucket"] = np.select(
        [hw == 0, hw < 4, hw < 13], ["0 (cold start)", "1-3 wks", "4-12 wks"], "13+ wks")
    return df


# --------------------------------------------------------------------------- public builders
def build_training_frame(country: str, as_of: pd.Timestamp = AS_OF,
                         con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """One row per SKU x order-week WITH sales (target observed); origin = previous Sunday.

    Target = units-weighted realized ASP of that order week (local currency).
    """
    con = con or connect()
    prepare_tables(con, country, as_of)
    data_start = pd.Timestamp(con.execute("SELECT min(d) FROM tx").fetchone()[0])
    first_target = data_start + pd.Timedelta(days=WARMUP_DAYS)
    first_target = first_target + pd.Timedelta(days=(7 - first_target.weekday()) % 7)   # next Monday
    last_target = as_of - pd.Timedelta(days=6)                                         # Monday of last full week
    tgt = con.execute(f"""
        SELECT sku, ow, u AS target_units, rev AS target_rev, rev / u AS target_asp,
               cost / u AS target_unit_cost, tx AS target_tx
        FROM sku_week
        WHERE ow >= DATE '{first_target.date()}' AND ow <= DATE '{last_target.date()}'
    """).df()
    tgt["o"] = pd.to_datetime(tgt["ow"]) - pd.Timedelta(days=1)
    raw = build_raw_features(con, tgt)
    raw["country"] = country
    raw["currency"] = CURRENCY[country]
    return raw


def build_inference_frame(country: str, as_of: pd.Timestamp = AS_OF, lookback_days: int = 90,
                          con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    """One row per SKU with sales in (as_of - lookback_days, as_of]; origin = as_of (a Sunday).

    The model then predicts the realized ASP of the week starting as_of + 1 day.
    """
    con = con or connect()
    prepare_tables(con, country, as_of)
    skus = con.execute(f"""
        SELECT DISTINCT sku FROM tx WHERE d > DATE '{(as_of - pd.Timedelta(days=lookback_days)).date()}'
    """).df()
    skus["o"] = as_of
    raw = build_raw_features(con, skus)
    raw["country"] = country
    raw["currency"] = CURRENCY[country]
    return raw
