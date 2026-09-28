# RetainIQ – DAX Measures for Power BI

Paste these measures into the **fact_orders** table (or a dedicated `_Measures` table) in Power BI Desktop.

---

## 1. Core KPIs (matching Streamlit app)

```dax
-- 1a. Total Revenue (item price only, freight excluded)
Total Revenue =
    SUMX(fact_orders, fact_orders[price])

-- 1b. Total Orders (distinct order IDs)
Total Orders =
    DISTINCTCOUNT(fact_orders[order_id])

-- 1c. Average Order Value
Avg Order Value =
    DIVIDE([Total Revenue], [Total Orders])

-- 1d. Repeat Customer Rate (% of customers with > 1 order)
Repeat Customer Rate % =
    VAR _all_customers =
        DISTINCTCOUNT(fact_orders[customer_unique_id])
    VAR _repeat_customers =
        COUNTROWS(
            FILTER(
                SUMMARIZE(
                    fact_orders,
                    fact_orders[customer_unique_id],
                    "_order_count", DISTINCTCOUNT(fact_orders[order_id])
                ),
                [_order_count] > 1
            )
        )
    RETURN
        DIVIDE(_repeat_customers, _all_customers) * 100

-- 1e. Average Review Score
Avg Review Score =
    AVERAGE(fact_orders[review_score])

-- 1f. On-Time Delivery %
On-Time Delivery % =
    DIVIDE(
        COUNTROWS(FILTER(fact_orders, fact_orders[is_late] = 0)),
        COUNTROWS(fact_orders)
    ) * 100
```

---

## 2. Revenue MoM %

```dax
Revenue MoM % =
    VAR _current =
        [Total Revenue]
    VAR _prior =
        CALCULATE(
            [Total Revenue],
            DATEADD(dim_date[date], -1, MONTH)
        )
    RETURN
        DIVIDE(_current - _prior, _prior) * 100
```

---

## 3. Late Delivery %

```dax
Late Delivery % =
    DIVIDE(
        COUNTROWS(FILTER(fact_orders, fact_orders[is_late] = 1)),
        COUNTROWS(fact_orders)
    ) * 100
```

---

## 4. At-Risk Customers (count)

```dax
At-Risk Customers =
    CALCULATE(
        DISTINCTCOUNT(dim_customers[customer_unique_id]),
        dim_customers[rfm_segment] = "At Risk"
    )
```

---

## 5. Revenue at Stake (At-Risk customers' historical revenue)

```dax
Revenue at Stake =
    CALCULATE(
        [Total Revenue],
        FILTER(
            fact_orders,
            RELATED(dim_customers[rfm_segment]) = "At Risk"
        )
    )
```

> **Note:** `RELATED()` works when fact_orders[customer_unique_id] is linked to dim_customers[customer_unique_id] with a many-to-one relationship.

---

## 6. Supporting / Optional Measures

```dax
-- Total Freight
Total Freight =
    SUMX(fact_orders, fact_orders[freight])

-- Avg Delivery Days
Avg Delivery Days =
    AVERAGE(fact_orders[delivery_days])

-- Champion Revenue Share %
Champion Revenue % =
    DIVIDE(
        CALCULATE([Total Revenue], dim_customers[rfm_segment] = "Champions"),
        [Total Revenue]
    ) * 100

-- Lost Customer Count
Lost Customers =
    CALCULATE(
        DISTINCTCOUNT(dim_customers[customer_unique_id]),
        dim_customers[rfm_segment] = "Lost"
    )
```
