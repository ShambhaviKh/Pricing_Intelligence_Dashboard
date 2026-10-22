# Global Baseline Model (CA / US)

This directory contains global ASP baseline models for CA and US, trained on transaction data for the Top 30 products. The current version does not split the models by product family.

## How to Run

1. Open `weighted_asp_formula_baseline.ipynb` for the final weighted-ASP formula, or `global_baseline_model_CA_US.ipynb` for the machine-learning benchmark comparison.
2. Run the selected notebook from top to bottom.
3. Review the generated files in `artifacts/`, including the validation comparison, final test metrics, predictions, product-level metrics, and feature importance.

The data is split chronologically into 70% training, 15% validation, and 15% testing rather than using a random split. The comparison includes a weighted-median benchmark, Ridge regression, Random Forest, and CatBoost with RMSE, MAE, Huber, and Quantile loss functions. Validation weighted MAE is the primary model-selection metric.

## Final Weighted-ASP Price Formula

The final directly usable baseline formula is:

```text
Predicted Price = w30 × ASP30 + w90 × ASP90 + wf × ASPf
```

The signals are defined as follows:

- `ASP30`: the same product's trailing 30-day unit-weighted ASP.
- `ASP90`: the same product's trailing 90-day unit-weighted ASP.
- `ASPf`: the same product family's trailing 90-day unit-weighted ASP.

All rolling values exclude the current day. The model uses one global set of weights per country and does not estimate separate weights by product family.

The final weights, refitted on training plus validation data, are:

```text
CA Price = 0.7676 × ASP30 + 0.0000 × ASP90 + 0.2324 × ASPf
US Price = 0.9130 × ASP30 + 0.0795 × ASP90 + 0.0075 × ASPf
```

| Country | Selected training loss | w30 | w90 | wf | Test weighted MAE | Test weighted WAPE | Test R² |
|---|---:|---:|---:|---:|---:|---:|---:|
| CA | MSE | 0.7676 | 0.0000 | 0.2324 | 175.50 | 13.45% | 0.620 |
| US | Huber | 0.9130 | 0.0795 | 0.0075 | 178.24 | 13.52% | 0.725 |

The near-zero CA `w90` indicates that ASP90 did not provide additional validation value after ASP30 and ASPf were included. The US result is also dominated by ASP30, with smaller contributions from ASP90 and ASPf.

## Weight-Estimation Objective

Let `y_i` be the observed ASP, `ŷ_i = f(x_i)` be the predicted ASP, and

```text
s_i = clip(sqrt(order_units_i), 1, 5)
```

The three price weights satisfy:

```text
w30 >= 0, w90 >= 0, wf >= 0
w30 + w90 + wf = 1
```

CA selected weighted MSE as the training objective:

```text
L_CA = sum_i s_i(y_i - ŷ_i)^2 / sum_i s_i
```

US selected weighted Huber loss with `delta = 100`:

```text
e_i = y_i - ŷ_i
Huber(e_i) = 0.5e_i^2                         if |e_i| <= 100
             100(|e_i| - 50)                 otherwise
L_US = sum_i s_i Huber(e_i) / sum_i s_i
```

In these equations, `s_i = clip(sqrt(order_units_i), 1, 5)` is the observation weight and is different from the formula coefficients `w30`, `w90`, and `wf`.

MAE, MSE, and Huber variants are compared on the validation period using weighted MAE:

```text
L_selection = sum_i s_i|y_i - ŷ_i| / sum_i s_i
```

The selected loss is refitted on training plus validation data. The test set is then used once for final evaluation and is not used to select the weights or loss function.

## Machine-Learning Benchmark Results

| Country | Recommended model | Test weighted MAE | Test weighted WAPE | Test R² |
|---|---:|---:|---:|---:|
| CA | CatBoost (RMSE loss) | 182.23 | 14.08% | 0.714 |
| US | Random Forest | 216.22 | 16.37% | 0.742 |

Larger orders receive more weight, while the maximum weight is capped at 5 to prevent unusually large orders from dominating model training.

The leading feature importance values are:

- CA: cost per unit 58.57%, time trend 10.00%, product type 9.64%, and product line 8.90%.
- US: cost per unit 73.50%, product line 13.17%, product model 3.97%, and product type 2.56%.

These values represent predictive feature importance, not causal coefficients. They should not be interpreted as the price change caused by changing a feature. This baseline predicts historically realized ASP and is not a price-elasticity model. Estimating price elasticity would require additional information such as rejected quotes, offer history, controlled price variation, or pricing experiments.
