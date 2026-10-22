# Global Baseline Model (CA / US)

This directory contains global ASP baseline models for CA and US, trained on transaction data for the Top 30 products. The current version does not split the models by product family.

## How to Run

1. Open `global_baseline_model_CA_US.ipynb`.
2. Run all cells from top to bottom.
3. Review the generated files in `artifacts/`, including the validation comparison, final test metrics, predictions, product-level metrics, and feature importance.

The data is split chronologically into 70% training, 15% validation, and 15% testing rather than using a random split. The comparison includes a weighted-median benchmark, Ridge regression, Random Forest, and CatBoost with RMSE, MAE, Huber, and Quantile loss functions. Validation weighted MAE is the primary model-selection metric.

## Final Results

| Country | Recommended model | Test weighted MAE | Test weighted WAPE | Test R² |
|---|---:|---:|---:|---:|
| CA | CatBoost (RMSE loss) | 182.23 | 14.08% | 0.714 |
| US | Random Forest | 216.22 | 16.37% | 0.742 |

The training sample-weight formula is `clip(sqrt(order_units), 1, 5)`. Larger orders receive more weight, while the maximum weight is capped at 5 to prevent unusually large orders from dominating model training.

The leading feature importance values are:

- CA: cost per unit 58.57%, time trend 10.00%, product type 9.64%, and product line 8.90%.
- US: cost per unit 73.50%, product line 13.17%, product model 3.97%, and product type 2.56%.

These values represent predictive feature importance, not causal coefficients. They should not be interpreted as the price change caused by changing a feature. This baseline predicts historically realized ASP and is not a price-elasticity model. Estimating price elasticity would require additional information such as rejected quotes, offer history, controlled price variation, or pricing experiments.
