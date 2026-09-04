# Exploratory Data Analysis (EDA) – Business & Pricing Intelligence Foundation

## 1. Purpose of EDA

The purpose of this Exploratory Data Analysis (EDA) is to understand the structure, quality, behavior, and business patterns present in the historical data.

For our **Pricing Intelligence Dashboard**, EDA provides the business foundation required to understand:

- How the business is performing
- Which products and product categories drive revenue and margin
- How performance changes over time
- How different customer segments behave
- Where unusual patterns or business issues exist
- Which business questions require further investigation
- What data is reliable enough to support future pricing intelligence capabilities

The EDA is intentionally **business-focused and descriptive**.

---

# 2. EDA-to-Dashboard Framework

The EDA follows the progression below:

**Data Quality**
→ **Business Metrics**
→ **Product & Segment Performance**
→ **Financial Performance**
→ **Time Trends**
→ **Returns & Cancellations**
→ **Patterns & Relationships**
→ **Business Questions**
→ **Pricing Intelligence Requirements**

The objective is to move from:

> **What does the data contain?**

to:

> **What is happening in the business?**

and ultimately:

> **What should the Pricing Intelligence Dashboard help users understand and investigate?**

---

# 3. Data Loading and Consolidation

## What we assess

The 14 quarterly datasets are combined into a single analytical dataset covering the available fiscal periods.

The merged dataset allows us to analyze the business consistently across all available quarters.

## Why is this necessary for the Pricing Intelligence Dashboard?

A pricing intelligence dashboard should not be based on an isolated quarter.

Users need to understand both:

- Current business performance
- Historical performance and trends

Combining all available periods allows us to establish a historical baseline that can later support forecasting, benchmarking, and other intelligence capabilities.

## How do we assess it?

We verify:

- Number of files loaded
- Number of records
- Number of columns
- Date coverage
- Fiscal-period coverage
- Consistency of columns across files

## What can we infer?

We can determine:

- The historical coverage available for analysis
- Whether data exists consistently across fiscal periods
- Whether some quarters contain significantly more or fewer records

A sudden change in record volume may represent a real business change or a data-quality/data-pipeline issue.

## Business value

Creates a single source of analytical data for the dashboard and prevents users from making decisions based only on one period.

## Stakeholder questions

- Does each row represent an order, order line, invoice, or another business event?
- Are all quarters complete?
- Were there changes in the data-generation process across fiscal years?
- Are there known periods with incomplete data?

---

# 4. Dataset Structure and Data Types

## What we assess

We review:

- Column names
- Data types
- Number of observations
- Categorical variables
- Numerical variables
- Date fields

## Why is this necessary?

The dashboard will eventually combine multiple business dimensions such as:

- Products
- Product lines
- Product families
- Segments
- Time
- Revenue
- Units
- Cost
- Margin
- Returns
- Cancellations

Understanding the structure of the data tells us what dimensions can be used for dashboard filtering, drill-downs, and comparisons.

## How do we assess it?

Review:

- `df.shape`
- `df.columns`
- `df.dtypes`
- Sample records
- Unique values

## What can we infer?

We can determine the granularity and analytical dimensions available in the dataset.

For example:

`product_name → product_line → product_family`

provides multiple levels of product analysis.

## Business value

Helps define the structure of the eventual dashboard and ensures that visualizations are based on valid business dimensions.

## Stakeholder questions

- What is the official hierarchy between product, product line, family, and family group?
- Which dimensions do business users normally use for reporting?
- Which dimensions should be available as dashboard filters?
- Are any fields derived rather than sourced directly from operational systems?

---

# 5. Data Quality Analysis

## What we assess

We analyze:

- Missing values
- Duplicate records
- Data types
- Unique values
- Invalid dates
- Extreme observations

## Why is this necessary?

A Pricing Intelligence Dashboard must provide trustworthy information.

If revenue, cost, margin, product, or transaction data is incomplete or duplicated, dashboard KPIs can be misleading.

This becomes even more important when future AI capabilities use the same data.

## How do we assess it?

We calculate:

- Missing count
- Missing percentage
- Unique values
- Duplicate count
- Duplicate percentage
- Invalid date records
- Outlier counts

We should also compare data quality across fiscal periods where appropriate.

## What can we infer?

Examples:

- High missingness in cost may affect margin analysis.
- Duplicate records may artificially inflate revenue.
- Missing return dates may simply mean the transaction was not returned.
- A sudden increase in missing data in one quarter may indicate a pipeline issue.

## Business value

Improves confidence in dashboard KPIs and reduces the risk of building AI recommendations on unreliable data.

## Stakeholder questions

- Which fields are considered authoritative?
- Are missing values expected for certain transaction types?
- How should missing cost or margin values be handled?
- Can duplicate-looking records represent legitimate business events?
- Were there any system migrations or data changes during FY24–FY27?

---

# 6. Duplicate Analysis

## Why is this necessary?

Duplicate transactions can inflate:

- Revenue
- Units
- Cost
- Margin
- Product performance

This could make a product or category appear more successful than it actually is.

## How do we assess it?

Calculate:

- Exact duplicate count
- Duplicate percentage
- Duplicates by fiscal period if necessary

## What can we infer?

A very low duplicate rate increases confidence in aggregate metrics.

A high duplicate rate requires investigation before using the data for business decisions.

## Business value

Protects the accuracy of dashboard KPIs.

## Stakeholder questions

- What is the unique identifier for a transaction?
- Are repeated product/order rows expected?
- Which fields define a unique business transaction?

---

# 7. Missing Value Analysis

## Why is this necessary?

Different types of missingness have different business meanings.

For example:

- Missing `return_date` may indicate no return.
- Missing `reason_of_return` may be expected when there was no return.
- Missing `cost` could be a genuine data problem.

Therefore, missing values should not automatically be treated as errors.

## How do we assess it?

Review:

- Missing percentage by column
- Missingness by fiscal period
- Missingness in key business metrics
- Missingness in categorical dimensions

## What can we infer?

We can distinguish between:

- Expected business missingness
- Potential data-quality problems

## Business value

Ensures dashboard metrics correctly interpret missing business events rather than treating every missing value as a data error.

## Stakeholder questions

- What does a null value mean for each field?
- Are missing values expected?
- Are there business rules governing when a field is populated?

---

# 8. Overall Business Metrics

## What we assess

We establish baseline KPIs:

- Total Revenue
- Total Order Units
- Total Invoice Quantity
- Total Cost
- Total Margin
- Average Revenue per Record
- Average Units per Record
- Average Cost per Record
- Average Margin per Record
- Overall Margin %

## Why is this necessary for the Pricing Intelligence Dashboard?

The dashboard needs a baseline view of business performance before users drill into products, segments, or time periods.

These KPIs provide the top-level context for every subsequent analysis.

## How do we assess it?

Calculate overall metrics and then compare them across:

- Fiscal periods
- Products
- Product lines
- Product families
- Segments

## What can we infer?

We can establish:

- Overall business scale
- Revenue performance
- Cost structure
- Margin performance
- Volume

These become the baseline against which future changes can be evaluated.

## Business value

Provides executives and business users with an immediate snapshot of business performance.

## Stakeholder questions

- Which KPIs are most important to leadership?
- Is revenue, margin, units, or another KPI the primary success measure?
- Are there target values for these metrics?
- Should dashboard KPIs show actuals, targets, or both?

---

# 9. Revenue Distribution Analysis

## What we assess

We use:

- Histograms
- Boxplots
- Mean
- Median
- Percentiles
- IQR/outlier analysis

## Why is this necessary?

Total revenue does not tell us how revenue is distributed across transactions.

A small number of unusually large transactions could significantly influence total revenue.

## How do we assess trends?

Compare:

- Mean vs median
- Distribution across fiscal periods
- Largest transactions
- Revenue outliers

## What can we infer?

If revenue is highly right-skewed, most transactions may be relatively small while a small number of transactions contribute substantial revenue.

This may indicate:

- Bulk transactions
- Enterprise orders
- High-value products
- Different transaction types

## Business value

Helps the dashboard provide context around averages and prevents users from interpreting average transaction values without understanding the distribution.

## Stakeholder questions

- What causes unusually large transactions?
- Are large transactions expected?
- Are they associated with specific products or customer segments?
- Should bulk transactions be analyzed separately?

---

# 10. Units Analysis

## Why is this necessary?

Revenue represents financial value, while units represent business volume.

A product with high unit volume may not necessarily be a top revenue contributor.

## How do we assess it?

Analyze units by:

- Product
- Product line
- Product family
- Segment
- Fiscal period

Also compare:

**Revenue vs Units**

## What can we infer?

We can identify:

- Volume leaders
- Revenue leaders
- Products that perform strongly on both measures
- Products where volume and financial contribution differ

## Business value

Allows dashboard users to understand whether business performance is primarily volume-driven or concentrated in higher-value transactions.

## Stakeholder questions

- Which products are volume drivers?
- Are high-volume products strategically important?
- Are unit fluctuations seasonal?
- Are there bulk-order effects?

---

# 11. Cost and Margin Analysis

## Why is this necessary?

Revenue alone does not provide a complete view of business performance.

Two products can generate similar revenue but contribute very different margins.

Understanding cost and margin is therefore essential for a dashboard focused on business and pricing intelligence.

## How do we assess it?

Analyze:

- Cost
- Margin
- Margin %
- Revenue vs Margin
- Margin by product
- Margin by product line
- Margin by product family
- Margin by segment
- Margin over time

## What can we infer?

We can identify:

### High Revenue + High Margin

Strong overall contributors.

### High Revenue + Low Margin

Important revenue contributors that may require further investigation.

### Low Revenue + High Margin %

Smaller contributors with relatively strong economics.

### Low Revenue + Low Margin

Potentially weaker business contributors.

## Business value

Provides a more complete picture of business performance than revenue alone.

## Stakeholder questions

- What causes margin differences across products?
- Are some product lines intentionally lower-margin?
- How is cost calculated?
- Are there cost components not captured in the dataset?
- Are there known cost changes over time?

---

# 12. Outlier Analysis

## Why is this necessary?

Outliers can represent either:

1. Genuine business events
2. Data-quality issues

Both need to be understood before the data is used for dashboard insights or future modeling.

## How do we assess it?

Use:

- Boxplots
- IQR method
- Percentiles
- Extreme-value analysis

for:

- Revenue
- Units
- Cost
- Margin

## What can we infer?

Outliers may represent:

- Bulk orders
- Enterprise transactions
- Exceptional business events
- Data-entry problems
- Duplicate records

## Business value

Prevents extreme observations from distorting KPIs, visualizations, and future predictive models.

## Stakeholder questions

- Are extreme transactions legitimate?
- What constitutes a bulk order?
- Should exceptional transactions be included in forecasting?
- Are there known data-entry issues?

---

# 13. Product Performance Analysis

## Why is this necessary?

Products are one of the most important dimensions in a Pricing Intelligence Dashboard.

Users need to understand which products drive:

- Revenue
- Units
- Cost
- Margin

## How do we assess it?

Create product-level summaries and rank products by:

- Revenue
- Units
- Margin

Visualize the top products.

## What can we infer?

We can identify:

- Revenue leaders
- Volume leaders
- Margin leaders
- Underperforming products
- Concentration among products

## Business value

Enables users to quickly identify which products have the greatest business impact.

## Stakeholder questions

- Why are certain products consistently strong?
- Are top products growing or declining?
- Are some products strategically important despite low revenue?
- Are there products being launched or discontinued?

---

# 14. Product Revenue vs Margin

## Why is this necessary?

A product's revenue contribution and margin contribution may differ significantly.

This analysis helps identify products that generate substantial sales but relatively lower margin.

## How do we assess it?

Create a scatter plot:

**X-axis → Revenue**

**Y-axis → Margin**

Use units as an additional visual dimension if appropriate.

## What can we infer?

The visualization can identify:

- High-revenue/high-margin products
- High-revenue/low-margin products
- Low-revenue/high-margin products
- Low-revenue/low-margin products

## Business value

Helps users move beyond revenue-only analysis and understand the financial quality of product performance.

## Stakeholder questions

- Why do certain high-revenue products have lower margins?
- Are low-margin products strategically important?
- Are there structural cost differences?
- Are certain product categories naturally lower-margin?

---

# 15. Product Line Analysis

## Why is this necessary?

Product-level analysis can be too granular for senior business users.

Product lines provide a higher-level portfolio view.

## How do we assess it?

Compare product lines using:

- Revenue
- Units
- Cost
- Margin
- Number of products
- Margin %

## What can we infer?

We can identify:

- Largest product lines
- Highest-margin product lines
- High-volume product lines
- Portfolio concentration

## Business value

Allows dashboard users to move from individual product performance to portfolio-level performance.

## Stakeholder questions

- Which product lines are strategic priorities?
- Are some product lines intentionally lower-margin?
- Are product lines managed independently?
- What explains differences between product lines?

---

# 16. Product Family Analysis

## Why is this necessary?

Product families provide another level of aggregation.

They help determine whether performance is driven by individual products or by broader product categories.

## How do we assess it?

Compare:

- Revenue
- Units
- Cost
- Margin
- Product count
- Margin %

## What can we infer?

If multiple products within the same family perform similarly, the underlying business driver may be category-level rather than product-specific.

## Business value

Provides a broader portfolio perspective for dashboard users.

## Stakeholder questions

- How are product families defined?
- Are products within a family substitutes?
- Are there meaningful differences between families?
- Are family-level trends more important than SKU-level trends?

---

# 17. Segment Analysis

## Why is this necessary?

Different customer segments may contribute differently to:

- Revenue
- Units
- Cost
- Margin

Understanding these differences helps users understand where business performance is concentrated.

## How do we assess it?

Compare segments on:

- Revenue
- Units
- Cost
- Margin
- Margin %
- Fiscal trends

## What can we infer?

We can identify:

- Largest revenue segments
- Highest-margin segments
- Volume-heavy segments
- Segment growth or decline

## Business value

Supports differentiated business analysis and helps dashboard users understand performance across major customer groups.

## Stakeholder questions

- How are segments defined?
- Which segments are strategic priorities?
- Do different segments have different commercial strategies?
- What explains performance differences between segments?

---

# 18. Fiscal Period Analysis

## Why is this necessary?

The dashboard should help users understand whether business performance is:

- Growing
- Declining
- Stable
- Seasonal
- Volatile

Historical fiscal periods provide the foundation for future forecasting.

## How do we assess it?

Analyze:

- Revenue by fiscal period
- Units by fiscal period
- Cost by fiscal period
- Margin by fiscal period

## What can we infer?

Examples:

- Consistent revenue growth
- Declining margins
- Seasonal peaks
- Unusual quarters
- Increasing volatility

## Business value

Creates the historical trend context required for future forecasting and business planning.

## Stakeholder questions

- What happened during unusually strong or weak quarters?
- Are there known seasonal patterns?
- Were there product launches?
- Were there supply constraints?
- Were there major business changes?

---

# 19. Monthly Trend Analysis

## Why is this necessary?

Quarterly analysis can hide shorter-term patterns.

For example, the same quarterly revenue could result from:

- Stable monthly performance
- Strong growth during the final month
- A significant mid-quarter decline

Monthly analysis reveals these patterns.

## How do we assess it?

Plot monthly:

- Revenue
- Units
- Cost
- Margin

## What can we infer?

We can identify:

- Seasonality
- Short-term growth
- Sudden drops
- Revenue spikes
- Recovery patterns

## Business value

Provides more granular trend visibility and establishes a stronger foundation for future forecasting.

## Stakeholder questions

- What causes monthly peaks?
- Are there seasonal demand cycles?
- Are holidays or promotions responsible for spikes?
- Are there supply constraints during specific months?

---

# 20. Returns Analysis

## Why is this necessary?

Reported revenue does not always represent the final business outcome if products are subsequently returned.

Returns can affect:

- Revenue
- Units
- Margin
- Product performance

## How do we assess it?

Analyze:

- Return rate
- Return reasons
- Returns by product line
- Returns over time

## What can we infer?

For example:

A product line may generate high revenue but also experience an unusually high return rate.

This creates an important business investigation.

## Business value

Adds an additional dimension to product performance and helps users understand potential product or operational issues.

## Stakeholder questions

- What are the main reasons for returns?
- Are high return rates expected for certain products?
- How do returns affect reported revenue?
- How do returns affect margin?
- Are return rates measured by orders or units?

---

# 21. Cancellation Analysis

## Why is this necessary?

Cancellations represent transactions that did not ultimately proceed.

Understanding cancellation behavior helps distinguish reported demand from completed business.

## How do we assess it?

Analyze:

- Cancellation rate
- Cancellation reasons
- Cancellations by product line
- Cancellation trends over time

## What can we infer?

High cancellation levels may indicate:

- Inventory issues
- Product availability problems
- Customer changes
- Operational problems
- Order-processing issues

## Business value

Helps identify lost business and operational friction that may otherwise be hidden by aggregate revenue metrics.

## Stakeholder questions

- Why are orders cancelled?
- Who initiates cancellations?
- Are cancellations mostly customer-driven or operational?
- Do certain products experience higher cancellation rates?
- Are cancellation reasons consistently recorded?

---

# 22. Existing Price Tier Analysis

## Important Scope Note

The existing `price_tier` field can be analyzed descriptively, but this EDA does **not** create pricing logic.

We are not calculating:

- Optimal price
- Price elasticity
- Price recommendations
- Dynamic pricing
- Price optimization

## Why is this useful for the Pricing Intelligence Dashboard?

The existing price tier provides business context that may later help stakeholders understand how current business classifications relate to revenue, units, cost, and margin.

## How do we assess it?

Compare existing price tiers on:

- Revenue
- Units
- Cost
- Margin
- Margin %

## What can we infer?

We can determine whether different existing tiers are associated with different business outcomes.

This is an observation, not a pricing recommendation.

## Business value

Provides a baseline understanding of the organization's existing pricing classifications before any future pricing intelligence is developed.

## Stakeholder questions

- How are price tiers currently defined?
- Who owns the definitions?
- Are tiers based on product characteristics, commercial agreements, or another rule?
- How frequently are tiers changed?
- Are these tiers actively used in business decisions?

---

# 23. Segment × Product Line Analysis

## Why is this necessary?

Analyzing segment and product line separately may hide important relationships.

A product line that performs strongly overall may perform differently across individual segments.

## How do we assess it?

Create a pivot table and heatmap:

**Rows → Segment**

**Columns → Product Line**

**Values → Revenue**

The same analysis can later be repeated for:

- Units
- Margin

## What can we infer?

We can identify:

- Product-line concentration within segments
- Segment-specific product performance
- Strong and weak segment/product combinations

## Business value

Helps dashboard users drill down from overall business performance into more specific business combinations.

## Stakeholder questions

- Why do certain segments perform strongly in particular product lines?
- Are there segment-specific product strategies?
- Are certain products more important to specific segments?
- Are there cross-sell or substitution patterns?

---

# 24. Product Performance Over Time

## Why is this necessary?

A product's overall performance does not tell us whether it is:

- Growing
- Declining
- Stable
- Volatile

The dashboard should provide both **performance level and performance trajectory**.

## How do we assess it?

For selected top products, plot:

**Fiscal Period → Revenue**

The same approach can be applied to:

- Units
- Margin

## What can we infer?

We can identify:

- Growth products
- Declining products
- Stable products
- Seasonal products
- Volatile products

## Business value

Provides early visibility into product lifecycle and performance changes and creates a foundation for future forecasting.

## Stakeholder questions

- What explains major product growth or decline?
- Were products launched or discontinued?
- Are supply issues affecting performance?
- Are changes seasonal or structural?
- Are there external market factors influencing the trend?

---

# 25. Correlation Analysis

## Why is this necessary?

Correlation analysis helps us understand relationships between important numerical variables before developing more advanced analytical models.

## How do we assess it?

Analyze relationships among:

- Revenue
- Units
- Invoice quantity
- Cost
- Margin
- Tax
- Invoice revenue

using a correlation matrix and heatmap.

## What can we infer?

Examples:

- Strong revenue-unit relationship may indicate volume is an important driver of revenue.
- Strong cost-revenue relationship may indicate costs scale with transaction value.
- Strong revenue-margin relationship may indicate larger transactions contribute more margin.

However:

> **Correlation does not imply causation.**

## Business value

Helps identify relationships worth investigating and can later inform feature selection for predictive analytics.

## Stakeholder questions

- Do these relationships match business expectations?
- What operational factors explain them?
- Are important explanatory variables missing from the dataset?
- Which relationships are actionable?

---

# 26. Business Trend Interpretation Framework

For every major visualization, we should follow the same analytical logic:

### Step 1 — What do we observe?

Example:

> Revenue increased significantly in FY26.

### Step 2 — Is the trend consistent?

Compare:

- Previous quarters
- Product lines
- Segments
- Products

### Step 3 — Where is the change coming from?

Drill down into:

- Products
- Product lines
- Product families
- Segments

### Step 4 — What other metrics changed?

Compare:

- Units
- Cost
- Margin
- Returns
- Cancellations

### Step 5 — What could explain the trend?

Generate hypotheses rather than assumptions.

### Step 6 — What should we ask stakeholders?

Validate the hypothesis with business experts.

### Step 7 — What dashboard capability could support this?

Translate the finding into a potential dashboard requirement.

---

# 27. Example: Turning EDA into Product Requirements

Suppose the EDA shows:

> Revenue increased 20%, but margin increased only 5%.

### EDA observation

Revenue is growing faster than margin.

### Business question

What is causing the difference between revenue growth and margin growth?

### Possible hypotheses

- Cost increased
- Product mix changed
- High-margin products declined
- Low-margin products increased
- Certain segments grew faster

### Stakeholder questions

- Did product mix change?
- Were there cost increases?
- Did any major products decline?
- Did segment mix change?
- Were there operational changes?

### Potential dashboard requirement

The dashboard could eventually allow users to:

**Revenue Growth → Product Mix → Margin Impact**

This is how EDA findings can directly influence product design.

---

# 28. EDA Findings → Dashboard Capabilities

| EDA Finding | Potential Dashboard Capability |
|---|---|
| Revenue changes over time | Revenue trend dashboard |
| Margin changes over time | Margin trend visualization |
| Product concentration | Top product contribution view |
| Product performance differences | Product comparison dashboard |
| Product-line differences | Product-line performance view |
| Segment differences | Segment performance view |
| Revenue vs margin differences | Revenue-margin quadrant |
| Monthly seasonality | Trend and seasonality visualization |
| Return-rate differences | Returns monitoring |
| Cancellation patterns | Cancellation monitoring |
| Data-quality problems | Data-quality indicators |
| Product growth/decline | Product trend monitoring |
| Existing price-tier differences | Price-tier descriptive view |
| Strong variable relationships | Analytical drill-downs |
| Unexpected changes | Alerts/anomaly investigation |

---

# 29. Stakeholder Discovery Questions Based on EDA

The EDA should ultimately generate questions for business stakeholders rather than simply produce charts.

## Business Performance

- What KPIs are most important to leadership?
- Is revenue or margin the primary business objective?
- What constitutes strong or weak performance?
- Are there predefined targets?

## Product

- Which products are strategically important?
- Which products are expected to grow?
- Which products are declining?
- Are products launched or discontinued during the analyzed period?

## Product Portfolio

- Which product lines are strategic priorities?
- How are product families defined?
- Are products within a family substitutes or complementary?

## Segment

- How are segments defined?
- Which segments are most important?
- Do different segments have different commercial strategies?

## Financial Performance

- What explains major margin differences?
- What cost components are included?
- Are there known cost changes over time?

## Returns

- What causes returns?
- Which return reasons are considered controllable?
- How do returns affect financial reporting?

## Cancellations

- Why are orders cancelled?
- Are cancellations customer-driven or operational?
- Are certain products disproportionately affected?

## Time Trends

- What explains unusually strong or weak quarters?
- What seasonality does the business expect?
- What events cause monthly spikes?

## Existing Pricing Structure

- How are existing price tiers defined?
- Who manages them?
- How often are they changed?
- How are they used in current decision-making?

---

# 30. Business Value of the EDA

The EDA provides value at three levels.

## Level 1 — Data Confidence

We determine whether the data is sufficiently reliable for analytical use.

**Data quality → Missing values → Duplicates → Outliers**

## Level 2 — Business Understanding

We understand the major drivers of business performance.

**Revenue → Units → Cost → Margin → Products → Product Lines → Families → Segments**

## Level 3 — Intelligence Foundation

We identify patterns and questions that can support future capabilities.

**Trends → Relationships → Anomalies → Business hypotheses → Stakeholder validation**

This creates a foundation for future pricing intelligence rather than prematurely building pricing logic into the EDA.

---

# 31. What the EDA Should Ultimately Answer

The EDA should help us answer five major questions:

### 1. Is the data reliable?

Can we trust the metrics displayed on the dashboard?

### 2. What is happening in the business?

Are revenue, units, cost, and margin growing, declining, or fluctuating?

### 3. Where is performance coming from?

Which products, product lines, product families, and segments are driving performance?

### 4. What patterns require investigation?

Where do we see unusual trends, outliers, returns, cancellations, or financial differences?

### 5. What should the Pricing Intelligence Dashboard help users investigate?

Which metrics, filters, drill-downs, trends, comparisons, and alerts would make these business questions easier to answer?

---
