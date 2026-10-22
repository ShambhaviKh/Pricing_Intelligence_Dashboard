# Global Baseline Model（CA / US）

本目录使用 Top 30 产品交易数据，分别训练 CA 和 US 的 global ASP baseline；当前版本不按 product family 拆分模型。

## 如何运行

1. 打开 `global_baseline_model_CA_US.ipynb`。
2. 从上到下运行全部单元格。
3. 结果会写入 `artifacts/`，包括验证集对比、最终测试指标、预测值、分产品指标及特征权重。

数据按日期切分为 70% train、15% validation、15% test，而非随机切分。模型比较包括 weighted median、Ridge、Random Forest，以及使用 RMSE、MAE、Huber、Quantile loss 的 CatBoost。主选择指标为 validation weighted MAE。

## 最终结论

| Country | 推荐模型 | Test weighted MAE | Test weighted WAPE | Test R² |
|---|---:|---:|---:|---:|
| CA | CatBoost（RMSE loss） | 182.23 | 14.08% | 0.714 |
| US | Random Forest | 216.22 | 16.37% | 0.742 |

训练样本权重统一为：`clip(sqrt(order_units), 1, 5)`。即大订单权重更高，但最高限制为 5，避免极端大单主导模型。

主要特征权重：

- CA：cost/unit 58.57%、时间趋势 10.00%、product type 9.64%、product line 8.90%。
- US：cost/unit 73.50%、product line 13.17%、product model 3.97%、product type 2.56%。

这些特征权重是预测重要性，不是因果系数，也不能解释为“改变某字段会使价格变化多少”。该 baseline 预测历史成交 ASP，不等同于价格弹性模型；后者还需要 rejected quotes、offer history 或实验价格变化等数据。

