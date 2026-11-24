"""
Module A - Reference Price model: comparison, time-based validation, selection, final fit.

Target  : realized units-weighted ASP of the NEXT order week for a SKU (local currency),
          only for SKU-weeks with sales (no-sale weeks are unobserved, never price 0).
Learned : y = log(target ASP) - log(anchor), anchor = hierarchical shrinkage price
          (see reference_features.hierarchical_anchor).  Prediction = anchor * exp(y_hat).
Split   : chronological.  Last 12 target weeks = held-out TEST.  Three preceding 12-week
          blocks = rolling-origin VALIDATION folds (expanding training window).
          Model selection uses validation only; test is reported once.
Metric  : units-weighted MAPE (primary), plus unweighted MAPE, median APE, weighted MAE, bias.
Selection rule: candidates must be within 0.3 pp of the best model on BOTH mean validation
          wMAPE and worst-fold validation wMAPE (stability); the simplest candidate wins.

Usage:  python src/reference_model.py --countries US CA
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime
from itertools import product
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
import statsmodels
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference_features as rf  # noqa: E402

warnings.filterwarnings("ignore")

MODELS_DIR = rf.ROOT / "models"
VAL_DIR = rf.ROOT / "outputs" / "validation"
TEST_WEEKS, FOLD_WEEKS, N_FOLDS = 12, 12, 3
SELECTION_TOL = 0.003            # 0.3 percentage points of wMAPE
K_GRID_H = [3, 10, 30, 100, 300]
K_GRID_S = [1, 3, 10, 30, 100]
SEED = 42

RATIO_COLS = [c for c in rf.NUM_FEATURES if c.startswith("r")]
OTHER_NUM = [c for c in rf.NUM_FEATURES if c not in RATIO_COLS]
MIXED_FEATURES = ["r7", "r30", "r90", "rlife", "r_line", "r_prior",
                  "has7", "has30", "has90", "lu30", "days_since_last"]

# lower = simpler / more interpretable
SIMPLICITY = {"ASP7": 0, "ASP30": 0, "ASP90": 0, "Weighted_ASP": 1, "Hier_Smoothed": 1,
              "OLS": 2, "Ridge_a1": 2, "Ridge_a10": 2, "Ridge_a100": 2, "MixedLM_line": 3,
              "HistGB": 4, "LightGBM": 4, "LightGBM_L1": 4, "RandomForest": 5}


# =========================================================================== helpers
def target_log_ratio(df):
    return np.log(df["target_asp"].to_numpy()) - df["log_anchor"].to_numpy()


def train_weights(df):
    u = df["target_units"].to_numpy(dtype=float)
    return np.minimum(u, np.quantile(u, 0.99))


def cat_frame(df, levels):
    out = df[rf.NUM_FEATURES].copy()
    for c in rf.CAT_FEATURES:
        out[c] = pd.Categorical(df[c], categories=levels[c])
    return out


def metrics(actual, pred, units):
    a, p, w = (np.asarray(x, dtype=float) for x in (actual, pred, units))
    ape = np.abs(p - a) / a
    return {"n": len(a), "units": float(w.sum()),
            "wMAPE": float((w * ape).sum() / w.sum()),
            "MAPE": float(ape.mean()), "MdAPE": float(np.median(ape)),
            "wMAE": float((w * np.abs(p - a)).sum() / w.sum()),
            "wBias_log": float((w * np.log(p / a)).sum() / w.sum())}


def tune_anchor(raw):
    best = None
    for kh, ks in product(K_GRID_H, K_GRID_S):
        d = rf.hierarchical_anchor(raw, kh, ks)
        m = metrics(raw["target_asp"], np.exp(d["log_anchor"]), raw["target_units"])["wMAPE"]
        if best is None or m < best[2]:
            best = (kh, ks, m)
    return best


# =========================================================================== models
def linear_pipeline(est):
    pre = ColumnTransformer([
        ("ratio", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value=0.0)),
                            ("sc", StandardScaler())]), RATIO_COLS),
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), OTHER_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", drop=None), rf.CAT_FEATURES),
    ])
    return Pipeline([("pre", pre), ("est", est)])


def fit_model(name, tr):
    """Returns a dict 'bundle' with everything predict_model needs (pickle-friendly)."""
    levels = {c: sorted(tr[c].astype(str).unique()) for c in rf.CAT_FEATURES}
    y, w = target_log_ratio(tr), train_weights(tr)
    b = {"name": name, "cat_levels": levels}
    if name in ("ASP7", "ASP30", "ASP90", "Hier_Smoothed"):
        b["kind"] = "baseline"
    elif name == "Weighted_ASP":
        lb = np.log(tr[["base_asp7", "base_asp30", "base_asp90"]].to_numpy())
        best = None
        for w7 in np.arange(0, 1.0001, 0.05):
            for w30 in np.arange(0, 1.0001 - w7, 0.05):
                ww = np.array([w7, w30, max(0.0, 1 - w7 - w30)])
                m = metrics(tr["target_asp"], np.exp(lb @ ww), tr["target_units"])["wMAPE"]
                if best is None or m < best[1]:
                    best = (ww, m)
        b.update(kind="weighted", weights=best[0].round(2).tolist())
    elif name == "OLS" or name.startswith("Ridge"):
        est = LinearRegression() if name == "OLS" else Ridge(alpha=float(name.split("_a")[1]))
        pipe = linear_pipeline(est)
        pipe.fit(tr[rf.NUM_FEATURES + rf.CAT_FEATURES].assign(
            **{c: tr[c].astype(str) for c in rf.CAT_FEATURES}), y, est__sample_weight=w)
        b.update(kind="sklearn_linear", estimator=pipe)
    elif name == "MixedLM_line":
        d = tr[MIXED_FEATURES].fillna(0.0).assign(y=y, grp=tr["k_line"].values,
                                                    product_type=tr["product_type"].values,
                                                    segment=tr["segment"].values)
        formula = "y ~ " + " + ".join(MIXED_FEATURES) + " + C(product_type) + C(segment)"
        res = smf.mixedlm(formula, d, groups=d["grp"]).fit(method="lbfgs", reml=True)
        try:
            re = {k: float(v.iloc[0]) for k, v in res.random_effects.items()}
            re_var = float(res.cov_re.iloc[0, 0])
        except (ValueError, np.linalg.LinAlgError):
            # line-level variance estimated at 0 -> no partial-pooling gain; fixed effects only
            re, re_var = {}, 0.0
        b.update(kind="mixedlm", fe_params=res.fe_params.to_dict(), random_effects=re,
                 re_variance=re_var, formula=formula)
    elif name == "RandomForest":
        X = tr[rf.NUM_FEATURES].copy()
        for c in rf.CAT_FEATURES:
            X[c] = pd.Categorical(tr[c], categories=levels[c]).codes
        est = RandomForestRegressor(n_estimators=200, min_samples_leaf=20, max_features=0.5,
                                    max_samples=0.5, n_jobs=4, random_state=SEED)
        est.fit(X, y, sample_weight=w)
        b.update(kind="rf", estimator=est)
    elif name == "HistGB":
        est = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                            min_samples_leaf=50, l2_regularization=1.0, early_stopping=False,
                                            categorical_features="from_dtype", random_state=SEED)
        est.fit(cat_frame(tr, levels), y, sample_weight=w)
        b.update(kind="hgb", estimator=est)
    elif name.startswith("LightGBM"):
        est = lgb.LGBMRegressor(objective="l1" if name.endswith("L1") else "l2",
                                n_estimators=500, learning_rate=0.03, num_leaves=31,
                                min_child_samples=50, subsample=0.8, subsample_freq=1,
                                colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED,
                                n_jobs=4, verbose=-1, deterministic=True, force_row_wise=True)
        est.fit(cat_frame(tr, levels), y, sample_weight=w)
        b.update(kind="lgbm", estimator=est)
    else:
        raise ValueError(name)
    return b


def predict_model(b, df):
    """Predicted reference price (local currency) for a model frame."""
    name, kind = b["name"], b["kind"]
    anchor = np.exp(df["log_anchor"].to_numpy())
    if kind == "baseline":
        col = {"ASP7": "base_asp7", "ASP30": "base_asp30", "ASP90": "base_asp90",
               "Hier_Smoothed": "anchor"}[name]
        return df[col].to_numpy(dtype=float)
    if kind == "weighted":
        lb = np.log(df[["base_asp7", "base_asp30", "base_asp90"]].to_numpy())
        return np.exp(lb @ np.array(b["weights"]))
    if kind == "sklearn_linear":
        X = df[rf.NUM_FEATURES + rf.CAT_FEATURES].assign(**{c: df[c].astype(str) for c in rf.CAT_FEATURES})
        return anchor * np.exp(b["estimator"].predict(X))
    if kind == "mixedlm":
        fe = b["fe_params"]
        d = df[MIXED_FEATURES].fillna(0.0)
        yh = np.full(len(df), fe.get("Intercept", 0.0))
        for f in MIXED_FEATURES:
            yh += fe.get(f, 0.0) * d[f].to_numpy()
        for col in ("product_type", "segment"):
            for lvl in df[col].unique():
                key = f"C({col})[T.{lvl}]"
                if key in fe:
                    yh[df[col].to_numpy() == lvl] += fe[key]
        yh += df["k_line"].map(b["random_effects"]).fillna(0.0).to_numpy()
        return anchor * np.exp(yh)
    if kind == "rf":
        X = df[rf.NUM_FEATURES].copy()
        for c in rf.CAT_FEATURES:
            X[c] = pd.Categorical(df[c], categories=b["cat_levels"][c]).codes
        return anchor * np.exp(b["estimator"].predict(X))
    if kind in ("hgb", "lgbm"):
        return anchor * np.exp(b["estimator"].predict(cat_frame(df, b["cat_levels"])))
    raise ValueError(kind)


MODEL_NAMES = list(SIMPLICITY)


# =========================================================================== importance
def feature_importance(b, df):
    kind = b["kind"]
    if kind == "lgbm":
        est = b["estimator"]
        return pd.DataFrame({"feature": est.feature_name_,
                             "gain": est.booster_.feature_importance("gain"),
                             "splits": est.booster_.feature_importance("split")}) \
            .assign(gain_share=lambda x: x.gain / x.gain.sum()).sort_values("gain", ascending=False)
    if kind == "sklearn_linear":
        pipe = b["estimator"]
        names = pipe.named_steps["pre"].get_feature_names_out()
        return pd.DataFrame({"feature": names, "coef_standardized": pipe.named_steps["est"].coef_}) \
            .assign(abs_coef=lambda x: x.coef_standardized.abs()).sort_values("abs_coef", ascending=False)
    if kind == "rf":
        cols = rf.NUM_FEATURES + rf.CAT_FEATURES
        return pd.DataFrame({"feature": cols, "impurity_importance": b["estimator"].feature_importances_}) \
            .sort_values("impurity_importance", ascending=False)
    if kind == "mixedlm":
        return pd.DataFrame({"feature": list(b["fe_params"]), "coef": list(b["fe_params"].values())})
    if kind == "weighted":
        return pd.DataFrame({"feature": ["ASP7", "ASP30", "ASP90"], "weight": b["weights"]})
    return pd.DataFrame({"feature": ["anchor"], "note": ["no learned parameters"]})


# =========================================================================== pipeline
def dimension_table(pred_df, models):
    rows = []
    dims = {"overall": None, "product_type": "product_type", "segment": "segment",
            "segment_x_type": "seg_type", "history_bucket": "history_bucket"}
    pred_df = pred_df.assign(seg_type=pred_df["segment"] + " / " + pred_df["product_type"])
    for m in models:
        for dim, col in dims.items():
            groups = [("ALL", pred_df)] if col is None else pred_df.groupby(col)
            for g, sub in groups:
                rows.append({"model": m, "dimension": dim, "group": g,
                             **metrics(sub["target_asp"], sub[f"pred_{m}"], sub["target_units"])})
    return pd.DataFrame(rows)


def select_model(summary):
    best = summary["val_wMAPE_mean"].min()
    best_worst = summary["val_wMAPE_max"].min()
    cands = summary[(summary["val_wMAPE_mean"] <= best + SELECTION_TOL)
                    & (summary["val_wMAPE_max"] <= best_worst + SELECTION_TOL)].copy()
    cands["simplicity"] = cands["model"].map(SIMPLICITY)
    pick = cands.sort_values(["simplicity", "val_wMAPE_mean"]).iloc[0]
    best_name = summary.loc[summary["val_wMAPE_mean"].idxmin(), "model"]
    return pick["model"], best_name, best


def run_country(country):
    t0 = time.time()
    print(f"\n========== {country} ==========", flush=True)
    raw = rf.build_training_frame(country)
    weeks = np.sort(raw["ow"].unique())
    test_weeks = weeks[-TEST_WEEKS:]
    folds = [weeks[-TEST_WEEKS - FOLD_WEEKS * (i + 1): -TEST_WEEKS - FOLD_WEEKS * i] for i in range(N_FOLDS)][::-1]
    splits = [(f"val_fold{i + 1}", f) for i, f in enumerate(folds)] + [("test", test_weeks)]

    # anchor shrinkage constants: tuned only on data before the first validation fold
    kh, ks, kmape = tune_anchor(raw[raw["ow"] < folds[0][0]])
    print(f"anchor k_h={kh} k_s={ks} (pre-validation wMAPE {kmape:.4f})", flush=True)
    df = rf.make_model_frame(raw, kh, ks)
    print(f"rows={len(df)} skus={df.sku.nunique()} weeks {weeks[0]}..{weeks[-1]}  ({time.time() - t0:.0f}s)", flush=True)

    rows, test_pred = [], None
    for split, blk in splits:
        tr = df[df["ow"] < blk[0]]
        ev = df[df["ow"].isin(blk)].copy()
        for m in MODEL_NAMES:
            t1 = time.time()
            b = fit_model(m, tr)
            ev[f"pred_{m}"] = predict_model(b, ev)
            rows.append({"country": country, "split": split, "model": m,
                         "train_rows": len(tr), "eval_start": str(blk[0])[:10], "eval_end": str(blk[-1])[:10],
                         **metrics(ev["target_asp"], ev[f"pred_{m}"], ev["target_units"]),
                         "fit_seconds": round(time.time() - t1, 1)})
        print(f"  {split}: done ({time.time() - t0:.0f}s)", flush=True)
        if split == "test":
            test_pred = ev

    res = pd.DataFrame(rows)
    val = res[res["split"].str.startswith("val")]
    summary = val.groupby("model").agg(val_wMAPE_mean=("wMAPE", "mean"), val_wMAPE_std=("wMAPE", "std"),
                                       val_wMAPE_max=("wMAPE", "max"),
                                       val_MAPE_mean=("MAPE", "mean"), val_MdAPE_mean=("MdAPE", "mean"),
                                       val_wBias_mean=("wBias_log", "mean")).reset_index()
    tst = res[res["split"] == "test"].set_index("model")
    for c in ("wMAPE", "MAPE", "MdAPE", "wMAE", "wBias_log"):
        summary[f"test_{c}"] = summary["model"].map(tst[c])
    summary["simplicity_rank"] = summary["model"].map(SIMPLICITY)
    summary = summary.sort_values("val_wMAPE_mean")
    chosen, best_name, best_val = select_model(summary)
    print(summary.round(4).to_string(index=False), flush=True)
    print(f"best by validation: {best_name} ({best_val:.4f}); selected: {chosen}", flush=True)

    VAL_DIR.mkdir(parents=True, exist_ok=True)
    res.to_csv(VAL_DIR / f"model_comparison_folds_{country}.csv", index=False)
    summary.to_csv(VAL_DIR / f"model_comparison_summary_{country}.csv", index=False)
    dimension_table(test_pred, MODEL_NAMES).to_csv(VAL_DIR / f"test_by_dimension_{country}.csv", index=False)
    keep = ["sku", "product_name", "segment", "product_type", "product_family", "product_line", "ow",
            "history_bucket", "target_units", "target_asp", "anchor"] + [f"pred_{m}" for m in MODEL_NAMES]
    test_pred[keep].to_csv(VAL_DIR / f"test_predictions_{country}.csv", index=False)

    # ---- final fit on ALL labelled weeks (through the last complete week before AS_OF)
    final = fit_model(chosen, df)
    imp_frames = {chosen: feature_importance(final, df)}
    for extra in ("LightGBM", "Ridge_a10"):
        if extra != chosen:
            imp_frames[extra] = feature_importance(fit_model(extra, df), df)
    for m, f in imp_frames.items():
        f.to_csv(VAL_DIR / f"feature_importance_{m}_{country}.csv", index=False)

    srow = summary.set_index("model").loc[chosen]
    bundle = {
        **final,
        "country": country, "currency": rf.CURRENCY[country],
        "target": "next order-week units-weighted realized ASP (local currency); y = log(ASP/anchor)",
        "anchor_params": {"k_h": kh, "k_s": ks},
        "num_features": rf.NUM_FEATURES, "cat_features": rf.CAT_FEATURES,
        "as_of": str(rf.AS_OF.date()), "train_target_weeks": [str(weeks[0])[:10], str(weeks[-1])[:10]],
        "train_rows": len(df),
        "validation": {"val_wMAPE_mean": float(srow["val_wMAPE_mean"]), "val_wMAPE_std": float(srow["val_wMAPE_std"]),
                       "val_wMAPE_max": float(srow["val_wMAPE_max"]),
                       "test_wMAPE": float(srow["test_wMAPE"]), "test_MdAPE": float(srow["test_MdAPE"])},
        "selection": {"best_by_validation": best_name, "best_val_wMAPE": float(best_val),
                      "tolerance": SELECTION_TOL,
                      "rule": "simplest model within tolerance of the best mean AND best worst-fold validation wMAPE"},
        "versions": {"python": sys.version.split()[0], "sklearn": sklearn.__version__,
                     "lightgbm": lgb.__version__, "statsmodels": statsmodels.__version__,
                     "pandas": pd.__version__, "numpy": np.__version__},
        "created": datetime.now().isoformat(timespec="seconds"),
        "usage": "from reference_model import predict_reference_price; see module docstring",
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODELS_DIR / f"ref_price_{country}.pkl")
    with open(VAL_DIR / f"run_summary_{country}.json", "w") as fh:
        json.dump({k: v for k, v in bundle.items() if k not in ("estimator", "random_effects")},
                  fh, indent=2, default=str)
    print(f"saved models/ref_price_{country}.pkl  ({time.time() - t0:.0f}s total)", flush=True)
    return summary


def predict_reference_price(country, as_of=rf.AS_OF, bundle=None, lookback_days=90):
    """Reference price P0 for every SKU sold in the last `lookback_days` before `as_of` (a Sunday).

    Returns one row per SKU with ASP7/30/90, anchor and reference_price for the week starting as_of+1.
    """
    bundle = bundle or joblib.load(MODELS_DIR / f"ref_price_{country}.pkl")
    raw = rf.build_inference_frame(country, pd.Timestamp(as_of), lookback_days)
    df = rf.make_model_frame(raw, bundle["anchor_params"]["k_h"], bundle["anchor_params"]["k_s"])
    df["reference_price"] = predict_model(bundle, df)
    df["reference_model"] = bundle["name"]
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", nargs="+", default=["US", "CA"])
    args = ap.parse_args()
    for c in args.countries:
        run_country(c)
