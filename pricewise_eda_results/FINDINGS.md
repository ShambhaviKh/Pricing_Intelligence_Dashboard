# PriceWise: recent product and pricing findings

Generated from the configured CSV input files. Scope: enterprise; shipped invoice records.
Transaction = input row; duplicates retained. Countries are analyzed separately; currency basis is not verified.

## CA: 2026-03-02 through 2026-09-01 (inclusive)
- Eligible six-month transaction rows: 164,802; unique products: 1,418.
- Overall portfolio: 30 products. Family portfolio: 26 products across 5 families. Overlap: 14; union: 42 products.
- Highest-transaction product: CMEG685 (LIBERTY INTEGRAL JUNCTION (FKA)), 74,755 transactions; resolved family: Product Family Fusion Echo.
- Overall portfolio share of recorded transactions: 61.9%; share of signed revenue: 11.1% (interpret negative credits carefully).
- Selected products passing provisional recent-data checks: 34/42. This is not operational price approval.
- Family slots unavailable: 4; overall slots unavailable: 0.
- Selected products with conflicting family assignments: 0.
- Selected products with declining units versus the previous 30 days: 15; undefined growth comparison: 1.
- Products missing at least one illustrative baseline component: 5. Do not silently substitute a family average.

### Selected families

| Family | Transactions | Selected products | Unfilled slots |
|---|---:|---:|---:|
| Product Family Fusion Echo | 79,939 | 2 | 4 |
| Product Family Romeo Iris | 49,028 | 6 | 0 |
| Product Family Knight Thrive | 11,803 | 6 | 0 |
| Product Family Frame Road | 8,269 | 6 | 0 |
| Product Family Solar Peak | 6,432 | 6 | 0 |

### Product review priorities

- CMEG685: invalid recent price basis.
- KEZB478: invalid recent price basis.
- 27WH3132DN: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- 49TH570PJS: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- 99FL811XLB: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- 16T0MJI6WJ: few recent transactions; few active sales days.
- 10TBMCG2LC: few recent transactions; few active sales days; stale sales.
- 27SSNJJ2HT: few recent transactions; few active sales days; stale sales; invalid recent price basis.

### Pricing interpretation

- ASP is realized revenue / order units, not list price. Investigate signed credits, zero-priced shipping/services and bulk contracts before suggesting a price change.
- Family price context mixes products; compare product type/tier and family-to-product ASP ratios before using the illustrative 50/30/20 baseline.
- .99-ending incidence is observed transaction ASP only. It does not prove list-price endings or customer preference.
- Orange-shaded trend months are partial. Calendar-day normalization does not validate daily feed completeness.
- Declining recorded sales is not proven excess inventory. Returns are an unlinked same-window flow ratio, not a cohort return rate.

## US: 2026-03-04 through 2026-09-03 (inclusive)
- Eligible six-month transaction rows: 892,300; unique products: 1,865.
- Overall portfolio: 30 products. Family portfolio: 29 products across 5 families. Overlap: 15; union: 44 products.
- Highest-transaction product: CMEG685 (LIBERTY INTEGRAL JUNCTION (FKA)), 282,270 transactions; resolved family: Product Family Fusion Echo.
- Overall portfolio share of recorded transactions: 60.6%; share of signed revenue: 14.0% (interpret negative credits carefully).
- Selected products passing provisional recent-data checks: 36/44. This is not operational price approval.
- Family slots unavailable: 1; overall slots unavailable: 0.
- Selected products with conflicting family assignments: 0.
- Selected products with declining units versus the previous 30 days: 19; undefined growth comparison: 1.
- Products missing at least one illustrative baseline component: 5. Do not silently substitute a family average.

### Selected families

| Family | Transactions | Selected products | Unfilled slots |
|---|---:|---:|---:|
| Product Family Fusion Echo | 419,411 | 5 | 1 |
| Product Family Romeo Iris | 264,252 | 6 | 0 |
| Product Family Frame Road | 63,566 | 6 | 0 |
| Product Family Knight Thrive | 53,257 | 6 | 0 |
| Product Family Solar Peak | 42,788 | 6 | 0 |

### Product review priorities

- CMEG685: invalid recent price basis.
- 27WH3132DN: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- 18FS8100BR: stale sales.
- 16CHOUW4TD: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- 55C97203QD: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- KEZB478: invalid recent price basis.
- 02CAMJV4NR: few recent transactions; few active sales days; stale sales; invalid recent price basis.
- RYOT483: few recent transactions; few active sales days; stale sales; invalid recent price basis.

### Pricing interpretation

- ASP is realized revenue / order units, not list price. Investigate signed credits, zero-priced shipping/services and bulk contracts before suggesting a price change.
- Family price context mixes products; compare product type/tier and family-to-product ASP ratios before using the illustrative 50/30/20 baseline.
- .99-ending incidence is observed transaction ASP only. It does not prove list-price endings or customer preference.
- Orange-shaded trend months are partial. Calendar-day normalization does not validate daily feed completeness.
- Declining recorded sales is not proven excess inventory. Returns are an unlinked same-window flow ratio, not a cohort return rate.

## Next decisions

Confirm revenue/cost/margin currency basis; confirm ship_date as invoice-event proxy and data completeness date; agree the family mapping and scope of non-hardware products; approve recent-data thresholds. Use fixed tier/margin rules and the documented ±2% daily and ±10% monthly limits only after reference prices and costs are validated.

No causal demand response, optimized stakeholder weights, realized revenue uplift, or inventory reduction is estimated in this EDA. These require additional data and evaluation.