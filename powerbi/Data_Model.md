# RetainIQ – Power BI Data Model

---

## Tables

| Table | Source File | Grain | Key Column(s) |
|-------|-------------|-------|---------------|
| `fact_orders` | `powerbi/output/fact_orders.csv` | 1 row per order item | order_id, order_item_id |
| `dim_customers` | `powerbi/output/dim_customers.csv` | 1 row per customer | customer_unique_id |
| `dim_products` | `powerbi/output/dim_products.csv` | 1 row per product | product_id |
| `dim_date` | `powerbi/output/dim_date.csv` | 1 row per calendar day | date |

---

## Column Reference

### fact_orders
| Column | Type | Description |
|--------|------|-------------|
| order_id | Text | Order identifier |
| order_item_id | Integer | Item sequence within order (1-based) |
| customer_unique_id | Text | Person identifier (FK → dim_customers) |
| product_id | Text | Product identifier (FK → dim_products) |
| seller_id | Text | Seller identifier |
| purchase_date | Date/Time | Order purchase timestamp |
| price | Decimal | Item price in BRL (revenue metric) |
| freight | Decimal | Freight value in BRL (excluded from revenue KPI) |
| review_score | Integer | 1–5 star review (deduplicated; median-imputed if missing) |
| delivery_days | Integer | Days from purchase to delivery |
| is_late | Integer | 1 = delivered after estimated date; 0 = on time |

### dim_customers
| Column | Type | Description |
|--------|------|-------------|
| customer_unique_id | Text | **Primary key** |
| recency | Integer | Days since last order (at data snapshot) |
| frequency | Integer | Number of distinct orders |
| monetary | Decimal | Total spend |
| r_score | Integer | Recency quartile score (1–4, 4=best) |
| f_score | Integer | Frequency quartile score (1–4) |
| m_score | Integer | Monetary quartile score (1–4) |
| rfm_score | Integer | r+f+m total (3–12) |
| rfm_segment | Text | Champions / Loyal / At Risk / Lost |
| customer_state | Text | Brazilian state code |
| customer_city | Text | Customer city |

### dim_products
| Column | Type | Description |
|--------|------|-------------|
| product_id | Text | **Primary key** |
| product_category_name | Text | Original Portuguese category |
| product_category_name_english | Text | English translation |
| product_weight_g | Integer | Weight in grams |
| product_length_cm | Integer | Length |
| product_height_cm | Integer | Height |
| product_width_cm | Integer | Width |

### dim_date
| Column | Type | Description |
|--------|------|-------------|
| date | Date | **Primary key** (YYYY-MM-DD) |
| year | Integer | Calendar year |
| quarter | Integer | 1–4 |
| month | Integer | 1–12 |
| month_name | Text | January … December |
| week | Integer | ISO week number |
| day_of_week | Integer | 0=Monday … 6=Sunday |
| day_name | Text | Monday … Sunday |
| is_weekend | Integer | 1 = weekend |
| year_month | Text | YYYY-MM (for charting) |

---

## Relationships

| From (Many) | To (One) | Cardinality | Cross-filter |
|-------------|----------|-------------|--------------|
| fact_orders[customer_unique_id] | dim_customers[customer_unique_id] | Many-to-One | Single |
| fact_orders[product_id] | dim_products[product_id] | Many-to-One | Single |
| fact_orders[purchase_date] *(date part)* | dim_date[date] | Many-to-One | Single |

> **Tip:** In Power BI, connect `fact_orders[purchase_date]` to `dim_date[date]`. Power BI will automatically truncate the datetime to date for the relationship. If it doesn't, create a calculated column `purchase_date_only = DATE(...)` in fact_orders.

---

## Star Schema Diagram (text)

```
              dim_date
              (date PK)
                 |
                 | Many-to-One
                 |
dim_customers ──── fact_orders ──── dim_products
(customer_unique_id PK)  (order_id, order_item_id grain)  (product_id PK)
```

Central fact table with three dimension tables — a clean star schema. No snowflake extensions needed.

---

## Power BI Import Steps

1. **Open** Power BI Desktop → **Get Data → Text/CSV**.
2. Import in this order (dimensions first, then fact):
   - `powerbi/output/dim_date.csv`
   - `powerbi/output/dim_customers.csv`
   - `powerbi/output/dim_products.csv`
   - `powerbi/output/fact_orders.csv`
3. In the **Transform Data** (Power Query) editor:
   - Set `fact_orders[purchase_date]` to **Date/Time** type.
   - Set `dim_date[date]` to **Date** type.
   - Set `fact_orders[price]`, `fact_orders[freight]` to **Decimal Number**.
   - Set `fact_orders[is_late]`, `fact_orders[review_score]` to **Whole Number**.
4. Click **Close & Apply**.
5. In **Model view**, create relationships as shown in the table above (drag and drop).
6. Verify cardinality shows **Many (*) → One (1)** on each relationship.
7. Add DAX measures from `DAX_Measures.md` to a **New Measure** in the fact_orders table.
8. Build pages following `Dashboard_Blueprint.md`.

---

## Notes

- All tables use only **delivered** orders — no cancelled, shipped, or processing orders.
- `customer_unique_id` is the person identifier; `customer_id` is a transaction-level ID and is intentionally excluded from the model.
- Revenue = `price` (item price only). `freight` is available but excluded from revenue KPIs to match the Streamlit app definition.
- Review scores are median-imputed for the ~5% of delivered orders that have no review.
