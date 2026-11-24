"""
Pricewise - price elasticity, seasonality and event lift (US / CA).

One regression per country on the SKU x order-week panel (weeks with sales):

    log(units) = SKU level
               + week effect[Segment x Type, week]       <- seasonality + events live here
               + lifecycle[Segment x Type, weeks since first sale]
               + elasticity * log(price)

1. ELASTICITY is identified only from SKUs priced differently from their peers IN THE
   SAME WEEK; everything common to that week (November, Black Friday, ...) goes into the
   week effect instead. Estimated at Segment x Type, Family and SKU level; each level is
   shrunk toward its parent (empirical Bayes), so sparse SKUs borrow from their Family.
2. The WEEK EFFECTS, re-estimated after removing the price effect, are split into
     seasonality = month-of-year factor (average month = 1.00), fiscal-year level removed
     event lift  = named event weeks vs. the normal level of their month.

Data   : data/processed/valid_{US,CA}.parquet (= valid_US.csv / valid_CA.csv), order weeks
         through AS_OF (2026-08-23). Order weeks 2025-09-29 .. 2025-12-29 are EXCLUDED: in
         Oct-Dec 2025 the data holds only 2-3 customers per country (vs. 60-430 before and
         after) and 60-85% fewer transactions in every product type - a data gap, not demand. Units = order_units; single orders > 20 units are
         negotiated bulk deals and excluded. Price = weekly median transaction unit price,
         US in USD, CA in CAD (FX handling in data_loading.py).
SKUs   : elasticity is ESTIMATED on every SKU with >= 4 sales weeks (all history).
         `recent_30d` = SKU sold in the 30 days to AS_OF (same list as the Reference Price
         output). Recent SKUs with < 4 sales weeks get their Segment x Type elasticity.
Outputs: outputs/elasticity/elasticity_{C}.csv, seasonality_{C}.csv, events_{C}.csv
         models/elasticity_{C}.pkl

Usage  : python src/elasticity_seasonality.py --countries US CA
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_loading as dl  # noqa: E402

OUT_DIR = dl.ROOT / "outputs" / "elasticity"
MODELS_DIR = dl.ROOT / "models"
BULK_MAX = 20
RECENT_DAYS = 30
RECENT_COL = f"recent_{RECENT_DAYS}d"
MIN_WEEKS_PANEL = 4      # fewer weeks: no within-SKU price variation to learn from
MIN_WEEKS_SKU = 12       # own SKU estimate needs >= 12 sales weeks ...
MIN_SD_SKU = 0.03        # ... and >= 3% residual price variation
MIN_SKUS_FAMILY = 10     # Family estimate needs >= 10 SKUs
AGE_BINS = [-1, 0, 1, 2, 3, 7, 12, 25, 51, 10_000]
DATA_GAP_WEEKS = ("2025-09-29", "2025-12-29")   # first / last order-week Monday excluded
LEFT_CENSOR_WEEKS = 8    # SKUs first seen in the first 8 weeks of data are treated as mature
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ============================================================================ data
def load_panel(country):
    con = dl.connect()
    dl.load_base_tables(con, country)         # tx: local-currency rev, units; sku_attr
    d = con.execute(f"""
        SELECT t.sku, CAST(date_trunc('week', t.d) AS DATE) AS ow,
               sum(t.u) AS units, median(t.rev / t.u) AS price,
               a.segment, a.product_type, a.product_family, a.first_d
        FROM tx t JOIN sku_attr a USING (sku)
        WHERE t.u <= {BULK_MAX}
        GROUP BY ALL""").df()
    attrs = con.execute("SELECT sku, product_name, segment, product_type, product_family FROM sku_attr").df()
    recent = set(con.execute(f"""SELECT DISTINCT sku FROM tx
                                WHERE d > DATE '{dl.AS_OF.date()}' - INTERVAL {RECENT_DAYS} DAY""").df()["sku"])
    d["ow"] = pd.to_datetime(d["ow"])
    d = d[~d["ow"].between(*pd.to_datetime(DATA_GAP_WEEKS))].copy()
    d["seg_type"] = d["segment"] + " / " + d["product_type"]
    first_d = pd.to_datetime(d["first_d"])
    first_week = first_d.dt.to_period("W-SUN").dt.start_time
    d["age_bin"] = pd.cut(((d["ow"] - first_week).dt.days // 7).clip(lower=0), AGE_BINS, labels=False)
    # SKUs already on sale when the data starts are not new launches: their first OBSERVED sale
    # is just the data start. Treat them as mature (oldest age bin) - otherwise the lifecycle
    # control mistakes them for launches and distorts the Apr-Jun 2023 week effects.
    censored = first_d < first_d.min() + pd.Timedelta(weeks=LEFT_CENSOR_WEEKS)
    d.loc[censored, "age_bin"] = len(AGE_BINS) - 2
    d["y"], d["x"] = np.log(d["units"]), np.log(d["price"])
    d = d[d.groupby("sku")["ow"].transform("size") >= MIN_WEEKS_PANEL].reset_index(drop=True)
    d["st_week"] = d["seg_type"] + "|" + d["ow"].dt.strftime("%Y-%m-%d")
    d["st_age"] = d["seg_type"] + "|" + d["age_bin"].astype(str)
    return d, attrs, recent


# ============================================================================ fixed effects
def fit_fixed_effects(d, v, keys=("sku", "st_week", "st_age"), tol=1e-7, max_iter=1000):
    """Backfitting: v = sum of one effect per key + residual. Returns {key: effect per row}."""
    codes = {k: pd.factorize(d[k])[0] for k in keys}
    comp = {k: np.zeros(len(d)) for k in keys}
    for _ in range(max_iter):
        moved = 0.0
        for k, c in codes.items():
            r = v - (sum(comp.values()) - comp[k])
            new = (np.bincount(c, weights=r) / np.bincount(c))[c]
            moved = max(moved, np.max(np.abs(new - comp[k])))
            comp[k] = new
        if moved < tol:
            break
    return comp


# ============================================================================ elasticity
def slope(x, y, cluster=None):
    """OLS slope through the origin with HC1 (or cluster-robust) standard error."""
    sxx = np.sum(x * x)
    b = np.sum(x * y) / sxx
    s = x * (y - b * x)
    if cluster is not None:
        s = pd.Series(s).groupby(cluster).sum().to_numpy()
    g = len(s)
    return b, np.sqrt(g / max(g - 1, 1) * np.sum(s ** 2)) / sxx


def between_variance(b, se):
    """DerSimonian-Laird tau^2: how much true effects differ between groups."""
    b, se = np.asarray(b, float), np.asarray(se, float)
    ok = np.isfinite(b) & np.isfinite(se) & (se > 0)
    b, w = b[ok], 1 / se[ok] ** 2
    if len(b) < 3:
        return 0.0
    q = np.sum(w * (b - np.sum(w * b) / np.sum(w)) ** 2)
    return max(0.0, (q - (len(b) - 1)) / (np.sum(w) - np.sum(w ** 2) / np.sum(w)))


def shrink(b, se, parent, tau2):
    """Weighted average of own estimate and parent: more noise -> closer to parent."""
    w = np.where(np.isfinite(b) & np.isfinite(se), tau2 / (tau2 + se ** 2), 0.0)
    return np.where(w > 0, w * b + (1 - w) * parent, parent), w


def estimate_elasticity(d):
    xr, yr = d["x_r"].to_numpy(), d["y_r"].to_numpy()
    b_country, _ = slope(xr, yr, d["sku"].to_numpy())

    def by_group(cols, min_skus=0, min_weeks=0, min_sd=0.0, clustered=True):
        rows = []
        for key, g in d.groupby(cols):
            key = key if isinstance(key, tuple) else (key,)
            x, y = g["x_r"].to_numpy(), g["y_r"].to_numpy()
            ok = g["sku"].nunique() >= min_skus and len(g) >= min_weeks and np.std(x) >= min_sd
            b, se = slope(x, y, g["sku"].to_numpy() if clustered else None) if ok else (np.nan, np.nan)
            rows.append(dict(zip(cols, key), raw=b, se=se, n_skus=g["sku"].nunique(), n_weeks=len(g)))
        return pd.DataFrame(rows)

    st = by_group(["seg_type"])
    st["elasticity"], _ = shrink(st["raw"], st["se"], b_country, between_variance(st["raw"], st["se"]))

    fam = by_group(["seg_type", "product_family"], min_skus=MIN_SKUS_FAMILY)
    fam.loc[fam["product_family"] == "UNKNOWN", ["raw", "se"]] = np.nan
    fam["parent"] = fam["seg_type"].map(st.set_index("seg_type")["elasticity"])
    tau = between_variance(fam["raw"] - fam["parent"], fam["se"])
    fam["elasticity"], _ = shrink(fam["raw"], fam["se"], fam["parent"], tau)
    fam["has_own"] = fam["raw"].notna()

    sku = by_group(["sku"], min_weeks=MIN_WEEKS_SKU, min_sd=MIN_SD_SKU, clustered=False)
    sku = sku.merge(d.groupby("sku")[["seg_type", "product_family"]].first().reset_index(), on="sku")
    sku = sku.merge(fam[["seg_type", "product_family", "elasticity", "has_own"]]
                    .rename(columns={"elasticity": "parent", "has_own": "family_has_own"}),
                    on=["seg_type", "product_family"], how="left")
    sku["elasticity"], sku["w"] = np.nan, 0.0
    for s, g in sku.groupby("seg_type"):            # tau^2 per Segment x Type
        tau = between_variance(g["raw"] - g["parent"], g["se"])
        sku.loc[g.index, "elasticity"], sku.loc[g.index, "w"] = shrink(g["raw"], g["se"], g["parent"], tau)
    sku["level"] = np.where(sku["raw"].notna(), "SKU",
                            np.where(sku["family_has_own"], "Family", "Segment x Type"))
    return b_country, st, fam, sku


# ============================================================================ seasonality / events
def event_weeks(year):
    """Monday of the order week for each named event in a calendar year."""
    monday = lambda dt: dt - pd.Timedelta(days=dt.weekday())
    nov1 = pd.Timestamp(year, 11, 1)
    thanksgiving = nov1 + pd.Timedelta(days=(3 - nov1.weekday()) % 7 + 21)   # 4th Thursday
    return {
        "Black Friday week": monday(thanksgiving + pd.Timedelta(days=1)),
        "Cyber Monday week": monday(thanksgiving + pd.Timedelta(days=4)),
        "Christmas week": monday(pd.Timestamp(year, 12, 25)),
        "New Year week": monday(pd.Timestamp(year, 1, 1)),
        # Lenovo fiscal quarters end Jun / Sep / Dec / Mar; Dec coincides with New Year week
        "Fiscal quarter-end week (Jun/Sep/Mar)": [monday(pd.Timestamp(year, m, 1) + pd.offsets.MonthEnd(0))
                                                 for m in (3, 6, 9)],
    }


def decompose_week_effects(wk):
    """wk: seg_type, ow, g (log week effect). Returns (seasonality, events) tables."""
    years = range(wk["ow"].dt.year.min(), wk["ow"].dt.year.max() + 1)
    flags = {}
    for yv in years:
        for ev, wkdays in event_weeks(yv).items():
            for w in (wkdays if isinstance(wkdays, list) else [wkdays]):
                flags[w] = ev
    names = list(event_weeks(2024))
    season_rows, event_rows = [], []
    for st, w in wk.groupby("seg_type"):
        w = w.sort_values("ow").reset_index(drop=True)
        mid = w["ow"] + pd.Timedelta(days=3)                  # month of the week's Thursday
        w["month"] = mid.dt.month
        w["fy"] = np.where(w["month"] >= 4, mid.dt.year + 1, mid.dt.year)
        w["event"] = w["ow"].map(flags)
        M = pd.get_dummies(w["month"]).reindex(columns=range(1, 13), fill_value=0).to_numpy(float)
        F = pd.get_dummies(w["fy"], drop_first=True).to_numpy(float)
        E = np.column_stack([(w["event"] == e).to_numpy(float) for e in names])
        X = np.column_stack([M, F, E])
        coef, *_ = np.linalg.lstsq(X, w["g"].to_numpy(), rcond=None)
        m = coef[:12] - coef[:12].mean()
        fy_eff = (F @ coef[12:12 + F.shape[1]]) if F.shape[1] else 0.0
        e_coef = coef[12 + F.shape[1]:]
        resid = w["g"].to_numpy() - X @ coef

        # month factor per fiscal year (only complete fiscal years) -> stability check
        clean = w["g"].to_numpy() - fy_eff - E @ e_coef
        per_fy = {}
        for fy, g in w.assign(c=clean).groupby("fy"):
            if g["month"].nunique() == 12:
                mm = g.groupby("month")["c"].mean()
                per_fy[f"FY{str(fy)[-2:]}"] = np.exp(mm - mm.mean())
        for i in range(12):
            row = {"seg_type": st, "month": i + 1, "month_name": MONTHS[i], "seasonal_factor": np.exp(m[i])}
            for k, v in per_fy.items():
                row[k] = v.get(i + 1, np.nan)
            season_rows.append(row)

        for j, e in enumerate(names):
            idx = np.where(w["event"] == e)[0]
            # each occurrence = event effect + that week's own residual
            each = "; ".join(f"{w.loc[i, 'ow']:%Y-%m-%d}: {np.exp(e_coef[j] + resid[i]):.2f}" for i in idx)
            event_rows.append({"seg_type": st, "event": e, "lift": np.exp(e_coef[j]),
                               "n_weeks": len(idx), "each_occurrence": each})
    return pd.DataFrame(season_rows), pd.DataFrame(event_rows)


def reliability(country, segment, level):
    out = np.where(segment == "Enterprise", "medium", "low")
    if country == "CA":
        out = np.where(segment == "Personal", "low (unstable in 2026)", out)
    return np.where((level == "Segment x Type") & (out == "medium"), "low", out)


# ============================================================================ run
def run(country):
    d, attrs, recent = load_panel(country)

    # 1) elasticity: residualise log units and log price on all fixed effects
    d["y_r"] = d["y"] - sum(fit_fixed_effects(d, d["y"].to_numpy()).values())
    d["x_r"] = d["x"] - sum(fit_fixed_effects(d, d["x"].to_numpy()).values())
    b_country, st, fam, sku = estimate_elasticity(d)

    # 2) week effects with the price effect removed (Segment x Type elasticity), and without
    beta = d["seg_type"].map(st.set_index("seg_type")["elasticity"]).to_numpy()
    tables = {}
    for tag, v in [("net", d["y"].to_numpy() - beta * d["x"].to_numpy()), ("raw", d["y"].to_numpy())]:
        g = fit_fixed_effects(d, v)["st_week"]
        wk = d.assign(g=g).groupby(["seg_type", "ow"], as_index=False)["g"].first()
        tables[tag] = decompose_week_effects(wk)
    season, events = tables["net"]
    season["factor_incl_price_effect"] = tables["raw"][0]["seasonal_factor"].to_numpy()
    events.insert(3, "lift_incl_price_effect", tables["raw"][1]["lift"].to_numpy())

    # 3) one row per SKU: estimated SKUs + recent SKUs too sparse to be in the panel
    out = attrs.merge(sku[["sku", "n_weeks", "raw", "se", "w", "elasticity", "level"]], on="sku", how="left")
    out = out[out["elasticity"].notna() | out["sku"].isin(recent)].copy()
    st_e = st.set_index("seg_type")["elasticity"]
    miss = out["elasticity"].isna()
    out.loc[miss, "elasticity"] = (out["segment"] + " / " + out["product_type"])[miss].map(st_e)
    out.loc[miss, "level"] = "Segment x Type"
    out["n_weeks"] = out["n_weeks"].fillna(0).astype(int)
    out[RECENT_COL] = out["sku"].isin(recent)
    out["reliability"] = reliability(country, out["segment"].to_numpy(), out["level"].to_numpy())
    out.insert(0, "country", country)
    out = out.rename(columns={"raw": "sku_own_estimate", "se": "sku_own_se", "w": "weight_on_own_estimate"})
    out = out.sort_values([RECENT_COL, "n_weeks", "sku"], ascending=[False, False, True])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.round(4).to_csv(OUT_DIR / f"elasticity_{country}.csv", index=False)
    season.round(3).to_csv(OUT_DIR / f"seasonality_{country}.csv", index=False)
    events.round(3).to_csv(OUT_DIR / f"events_{country}.csv", index=False)
    joblib.dump({"country": country, "country_elasticity": b_country, "segment_type": st, "family": fam,
                 "sku": out, "seasonality": season, "events": events,
                 "settings": {"BULK_MAX": BULK_MAX, "RECENT_DAYS": RECENT_DAYS, "as_of": str(dl.AS_OF.date()),
                              "excluded_weeks": DATA_GAP_WEEKS}},
                MODELS_DIR / f"elasticity_{country}.pkl")

    print(f"\n===== {country}: panel {len(d)} SKU-weeks, {d.sku.nunique()} SKUs; country elasticity {b_country:.2f}")
    print(st[["seg_type", "elasticity", "n_skus"]].round(2).to_string(index=False))
    r = out[out[RECENT_COL]]
    print(f"{RECENT_COL} SKUs: {len(r)}; by level {r['level'].value_counts().to_dict()}; "
          f"median elasticity {r['elasticity'].median():.2f}")
    return out, season, events


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", nargs="+", default=["US", "CA"])
    for c in ap.parse_args().countries:
        run(c)
