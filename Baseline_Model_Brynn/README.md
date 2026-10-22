# Global Baseline Price Model (CA / US)

This directory contains the leakage-free global baseline price model for the Top 30 products in Canada and the United States. CA and US are modeled separately; weights are shared across products within each country and are not split by product family.

## Final Model

The candidate blended formula was:

```text
Forward7DayASP = w30 × ProductASP30
               + w90 × ProductASP90
               + wf  × FamilyAdjustedPrice
```

where:

```text
FamilyAdjustedPrice = ProductASP90 × (PeerASP30 / PeerASP90)
```

Family peers exclude the target product. All features use data through the day before the scoring date, and the target is the unit-weighted ASP over the next seven calendar days.

After two expanding-window validation folds, none of the blended candidates met the acceptance rule of improving over ASP30-only in both folds with at least 2% average improvement. The official baseline therefore falls back to:

```text
CA Price = 1.0000 × ASP30 + 0.0000 × ASP90 + 0.0000 × FamilyAdjustedPrice
US Price = 1.0000 × ASP30 + 0.0000 × ASP90 + 0.0000 × FamilyAdjustedPrice
```

This `1/0/0` result is an intentional model-selection outcome, not a failed optimization. The additional signals did not provide sufficiently stable out-of-time improvement.

## Validation Design

- Fold 1: train through FY25Q4; validate on FY26Q1–FY26Q2.
- Fold 2: train through FY26Q2; validate on FY26Q3–FY26Q4.
- Final test: train through FY26Q4; evaluate on FY27Q1.
- FY27Q2 is incomplete and is reported only as a shadow evaluation.

The candidates were ASP30-only, ASP90-only, a fixed 50/30/20 blend, three constrained learned-weight objectives, and a dynamic shrinkage formula. Static weights were constrained to be nonnegative and sum to one.

The selection metric was:

```text
Balanced MAE = 0.5 × unweighted MAE + 0.5 × unit-weighted MAE
```

This prevents high-volume observations from completely controlling the model while still reflecting business volume.

## Rolling-Validation Result

| Country | Selected model | Average validation balanced MAE | Best alternative | Alternative improvement | Decision |
|---|---:|---:|---:|---:|---|
| CA | ASP30-only | 126.08 | ASP30-only | 0.00% | Keep ASP30-only |
| US | ASP30-only | 112.17 | Dynamic shrinkage | 1.28% | Reject: below 2% and not better in both folds |

## Holdout Results

| Country | Period | Eligible product-days | Balanced MAE | Unit-weighted MAE | R² |
|---|---:|---:|---:|---:|---:|
| CA | FY27Q1 test | 322 | 333.41 | 368.95 | 0.254 |
| US | FY27Q1 test | 516 | 255.11 | 266.27 | 0.632 |
| CA | FY27Q2 shadow | 1,004 | 131.76 | 102.21 | 0.793 |
| US | FY27Q2 shadow | 1,011 | 130.19 | 102.60 | 0.899 |

The weak CA FY27Q1 result is a material stability warning. That period contains only 322 eligible product-days and shows substantial temporal drift. The baseline should not be described as production-ready for CA without additional history, peer-universe expansion, and drift investigation.

## Files

- `weighted_asp_formula_baseline.ipynb`: corrected daily-panel construction, rolling validation, model selection, and final evaluation.
- `global_baseline_model_CA_US.ipynb`: secondary machine-learning benchmark; it is not the official weighted-ASP baseline.
- `artifacts/corrected_backtest_comparison.csv`: all candidate results by validation fold.
- `artifacts/corrected_weight_stability.csv`: learned coefficients and dynamic parameters by fold.
- `artifacts/corrected_model_selection.csv`: acceptance-gate results.
- `artifacts/corrected_final_model_summary.csv`: FY27Q1 test and FY27Q2 shadow metrics.
- `artifacts/corrected_final_predictions.csv`: product-day predictions.
- `artifacts/corrected_model_conclusion.json`: machine-readable final conclusion.

## How to Run

1. Place the CA and US Top 30 transaction files in `Top 30 Product for US-CA/`.
2. Open `weighted_asp_formula_baseline.ipynb`.
3. Run all cells from top to bottom.
4. Review the regenerated `corrected_*` files in `artifacts/`.

## Limitations and Next Step

- Family peers currently come only from the selected Top 30 products. The next meaningful improvement is to calculate peer signals from the full eligible product universe.
- Products without sufficient product and peer history are excluded; production requires a cold-start fallback.
- Family-specific or product-type weights should be introduced only after peer diagnostics and rolling-validation gates are passed.
- The model predicts a defensible historical price baseline, not a causal or profit-maximizing price.
- A true price optimizer requires offered prices, accepted and rejected quotes, promotions, inventory, competitor pricing, and demand-response data.
