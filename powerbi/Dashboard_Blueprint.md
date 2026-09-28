# RetainIQ – Power BI Dashboard Blueprint

Three pages mirroring the Streamlit app. Each section lists visuals, fields, slicers, and the Fact → Insight → Risk/Opportunity → Action callout text.

---

## Page 1 – Executive Overview

### Slicers
| Slicer | Field | Type |
|--------|-------|------|
| Date range | dim_date[date] | Between date picker |
| State | dim_customers[customer_state] | Dropdown multi-select |
| Category | dim_products[product_category_name_english] | Dropdown multi-select |

### Visuals

| # | Visual Type | Title | Axis / Field | Value | Notes |
|---|-------------|-------|--------------|-------|-------|
| 1 | Card | Total Revenue | — | [Total Revenue] | Format: R$ #,0 |
| 2 | Card | Total Orders | — | [Total Orders] | Format: #,0 |
| 3 | Card | Avg Order Value | — | [Avg Order Value] | Format: R$ #,0.00 |
| 4 | Card | Repeat Customer Rate | — | [Repeat Customer Rate %] | Format: 0.0% |
| 5 | Card | Avg Review Score | — | [Avg Review Score] | Format: 0.00 |
| 6 | Card | On-Time Delivery % | — | [On-Time Delivery %] | Format: 0.0% |
| 7 | Area/Line Chart | Monthly Revenue Trend | X: dim_date[year_month] | Y: [Total Revenue] | Sort by year_month ascending |

### Fact → Insight → Risk/Opportunity → Action Text Box
> **Fact:** Repeat rate is ~3% and on-time delivery is ~92%.
> **Insight:** The business is acquisition-heavy; late deliveries directly reduce review scores.
> **Risk/Opportunity:** Low repeat rate = high CAC dependency; late deliveries suppress future orders.
> **Action:** Invest in post-purchase retention sequences AND logistics SLA enforcement.

---

## Page 2 – Customer & Sales Analysis

### Slicers
Same as Page 1 (apply cross-page or duplicate).

### Visuals

| # | Visual Type | Title | Axis / Field | Value | Notes |
|---|-------------|-------|--------------|-------|-------|
| 1 | Line Chart | Monthly Revenue + Forecast | X: dim_date[year_month] | Y: [Total Revenue] | Add analytics pane forecast (3 months, linear) |
| 2 | Bar Chart (Horizontal) | Top 10 Categories by Revenue | Y: dim_products[product_category_name_english] | X: [Total Revenue] | Top N filter = 10, sort desc |
| 3 | Bar Chart (Horizontal) | Top 10 States by Revenue | Y: dim_customers[customer_state] | X: [Total Revenue] | Top N filter = 10, sort desc |
| 4 | Clustered Bar | Late Delivery vs Review Score | X: fact_orders[is_late] (0/On-Time, 1/Late) | Y: [Avg Review Score] | Rename 0→On-Time, 1→Late in model |
| 5 | Donut Chart | RFM Segment Size | Legend: dim_customers[rfm_segment] | Values: Count of customer_unique_id | Colors: Champions=green, Loyal=blue, At Risk=orange, Lost=red |
| 6 | Donut Chart | RFM Revenue Share | Legend: dim_customers[rfm_segment] | Values: [Total Revenue] | Same colour scheme |
| 7 | Table | RFM Summary | Rows: dim_customers[rfm_segment] | Cols: Customer Count, Revenue, Revenue % | Conditional formatting on Revenue |

### Fact → Insight → Risk/Opportunity → Action Text Box
> **Fact:** Late orders score ~0.5–1 star lower on average. At-Risk and Lost customers hold a large share of past revenue.
> **Insight:** Delivery quality is a direct lever on review scores and repeat intent.
> **Risk/Opportunity:** Dormant At-Risk revenue is recoverable at lower cost than new acquisition.
> **Action:** (1) Re-engage At-Risk customers with personalised campaigns. (2) Fix delivery in high-latency states.

---

## Page 3 – Risk, Opportunity & AI Advisor

### Slicers
Same as Page 1. Add:

| Slicer | Field | Type |
|--------|-------|------|
| RFM Segment | dim_customers[rfm_segment] | Single-select tile |

### Visuals

| # | Visual Type | Title | Axis / Field | Value | Notes |
|---|-------------|-------|--------------|-------|-------|
| 1 | KPI Card | At-Risk Customers | — | [At-Risk Customers] | Red accent |
| 2 | KPI Card | Revenue at Stake | — | [Revenue at Stake] | Red accent |
| 3 | KPI Card | Late Delivery % | — | [Late Delivery %] | Amber accent |
| 4 | Bar Chart | Late Delivery % by State | Y: dim_customers[customer_state] | X: [Late Delivery %] | Top 10 worst, sorted desc; add reference line at 20% |
| 5 | Bar Chart | Avg Review Score by Category | Y: dim_products[product_category_name_english] | X: [Avg Review Score] | Bottom 10; conditional color below 3.5 = red |
| 6 | Card | Opportunity Revenue (manual) | — | Manually computed text box | "If repeat rate +5pp → est. R$ X extra" — use a What-if parameter for lift |
| 7 | Table | Action Table | Columns: Fact, Insight, Risk/Opportunity, Action, Est. Impact | Static or populated via a metadata table | Load `action_table` as a static CSV if desired |
| 8 | Text Box | Executive Summary | — | — | Paste rule-based or LLM-generated text |

### What-If Parameter for Opportunity Estimate
1. In Power BI Desktop → **Modeling → New Parameter** → name: `Repeat Rate Lift pp`, range 1–20, increment 1, default 5.
2. Create measure:
```dax
Opportunity Revenue =
    VAR _lift_customers =
        ROUND(DISTINCTCOUNT(fact_orders[customer_unique_id]) * [Repeat Rate Lift pp Value] / 100, 0)
    RETURN
        _lift_customers * [Avg Order Value]
```
3. Add a Card visual with [Opportunity Revenue].

### Fact → Insight → Risk/Opportunity → Action Text Box
> **Fact:** At-Risk segment and high-latency states are quantified above.
> **Insight:** Most risk is concentrated in a few states and categories — targeted action is possible.
> **Risk/Opportunity:** R$ X revenue at stake (At-Risk) + R$ Y opportunity from +5pp repeat rate.
> **Action:** Prioritise logistics in top-3 late states; run re-engagement for At-Risk; audit bottom-5 categories.
