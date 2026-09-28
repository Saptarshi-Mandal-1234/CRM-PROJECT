# prepare_powerbi_data.py
# Standalone script: reads data/*.csv, writes clean Power BI-ready CSVs to powerbi/output/
# Outputs: fact_orders.csv, dim_customers.csv, dim_products.csv, dim_date.csv
# Run from project root: python powerbi/prepare_powerbi_data.py

import os
import sys
import pandas as pd
import numpy as np

DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load raw CSVs ──────────────────────────────────────────────────────────────
print("Loading CSVs...")
orders   = pd.read_csv(f"{DATA_DIR}/olist_orders_dataset.csv")
items    = pd.read_csv(f"{DATA_DIR}/olist_order_items_dataset.csv")
cust     = pd.read_csv(f"{DATA_DIR}/olist_customers_dataset.csv")
reviews  = pd.read_csv(f"{DATA_DIR}/olist_order_reviews_dataset.csv")
products = pd.read_csv(f"{DATA_DIR}/olist_products_dataset.csv")
trans    = pd.read_csv(f"{DATA_DIR}/product_category_name_translation.csv")

# ── Filter: delivered orders only ─────────────────────────────────────────────
orders = orders[orders["order_status"] == "delivered"].copy()

# Parse dates
date_cols = ["order_purchase_timestamp", "order_delivered_customer_date",
             "order_estimated_delivery_date"]
for col in date_cols:
    orders[col] = pd.to_datetime(orders[col], errors="coerce")

# Delivery metrics
orders["delivery_days"] = (
    orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"]
).dt.days
orders["is_late"] = (
    orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"]
).astype(int)   # 1 = late, 0 = on time

# ── Deduplicate reviews: keep highest score per order ─────────────────────────
reviews_dedup = (
    reviews.sort_values("review_score", ascending=False)
           .drop_duplicates("order_id")[["order_id", "review_score"]]
)

# ── Join customers ─────────────────────────────────────────────────────────────
orders = orders.merge(
    cust[["customer_id", "customer_unique_id", "customer_state",
          "customer_city", "customer_zip_code_prefix"]],
    on="customer_id", how="left"
)

# ── Build fact_orders ──────────────────────────────────────────────────────────
# One row per order item (items is already one row per item)
fact = items.copy()

# Add order-level fields
fact = fact.merge(
    orders[["order_id", "customer_unique_id", "order_purchase_timestamp",
            "delivery_days", "is_late"]],
    on="order_id", how="inner"          # inner = only delivered orders
)

# Add review
fact = fact.merge(reviews_dedup, on="order_id", how="left")

# Rename / select columns
fact = fact.rename(columns={
    "order_purchase_timestamp": "purchase_date",
    "price":                    "price",
    "freight_value":            "freight",
    "review_score":             "review_score",
})

fact_orders = fact[[
    "order_id", "order_item_id", "customer_unique_id", "product_id", "seller_id",
    "purchase_date", "price", "freight", "review_score", "delivery_days", "is_late"
]].copy()

# Handle nulls
fact_orders["review_score"] = fact_orders["review_score"].fillna(
    fact_orders["review_score"].median()
)
fact_orders["delivery_days"] = fact_orders["delivery_days"].fillna(
    fact_orders["delivery_days"].median()
)
fact_orders["is_late"] = fact_orders["is_late"].fillna(0).astype(int)

# Remove duplicate items (same order_id + order_item_id)
fact_orders = fact_orders.drop_duplicates(["order_id", "order_item_id"])

print(f"  fact_orders: {len(fact_orders):,} rows")
fact_orders.to_csv(f"{OUTPUT_DIR}/fact_orders.csv", index=False)

# ── Build dim_customers (with RFM) ────────────────────────────────────────────
# Aggregate per customer from fact
snapshot = fact_orders["purchase_date"].max() + pd.Timedelta(days=1)

rfm_base = (
    fact_orders.groupby("customer_unique_id")
    .agg(
        recency=("purchase_date",  lambda x: (snapshot - pd.to_datetime(x).max()).days),
        frequency=("order_id",     "nunique"),
        monetary=("price",         "sum")
    )
    .reset_index()
)

rfm_base["r_score"] = pd.qcut(rfm_base["recency"],  4, labels=[4, 3, 2, 1]).astype(int)
rfm_base["f_score"] = pd.qcut(rfm_base["frequency"].rank(method="first"), 4,
                               labels=[1, 2, 3, 4]).astype(int)
rfm_base["m_score"] = pd.qcut(rfm_base["monetary"],  4, labels=[1, 2, 3, 4]).astype(int)
rfm_base["rfm_score"] = rfm_base["r_score"] + rfm_base["f_score"] + rfm_base["m_score"]

def segment(row):
    if row["rfm_score"] >= 10: return "Champions"
    if row["rfm_score"] >= 7:  return "Loyal"
    if row["rfm_score"] >= 5:  return "At Risk"
    return "Lost"

rfm_base["rfm_segment"] = rfm_base.apply(segment, axis=1)

# Merge with customer location (last known state)
cust_loc = (
    orders[["customer_unique_id", "customer_state", "customer_city"]]
    .drop_duplicates("customer_unique_id")
)
dim_customers = rfm_base.merge(cust_loc, on="customer_unique_id", how="left")

print(f"  dim_customers: {len(dim_customers):,} rows")
dim_customers.to_csv(f"{OUTPUT_DIR}/dim_customers.csv", index=False)

# ── Build dim_products ────────────────────────────────────────────────────────
products_full = products.merge(trans, on="product_category_name", how="left")
dim_products = products_full[[
    "product_id", "product_category_name", "product_category_name_english",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"
]].drop_duplicates("product_id").copy()

dim_products["product_category_name_english"] = (
    dim_products["product_category_name_english"].fillna("unknown")
)

print(f"  dim_products: {len(dim_products):,} rows")
dim_products.to_csv(f"{OUTPUT_DIR}/dim_products.csv", index=False)

# ── Build dim_date ─────────────────────────────────────────────────────────────
min_date = fact_orders["purchase_date"].min()
max_date = fact_orders["purchase_date"].max()
date_range = pd.date_range(
    start=str(min_date)[:10],
    end=str(max_date)[:10],
    freq="D"
)
dim_date = pd.DataFrame({"date": date_range})
dim_date["year"]        = dim_date["date"].dt.year
dim_date["quarter"]     = dim_date["date"].dt.quarter
dim_date["month"]       = dim_date["date"].dt.month
dim_date["month_name"]  = dim_date["date"].dt.strftime("%B")
dim_date["week"]        = dim_date["date"].dt.isocalendar().week.astype(int)
dim_date["day_of_week"] = dim_date["date"].dt.dayofweek      # 0=Mon
dim_date["day_name"]    = dim_date["date"].dt.strftime("%A")
dim_date["is_weekend"]  = (dim_date["day_of_week"] >= 5).astype(int)
dim_date["year_month"]  = dim_date["date"].dt.strftime("%Y-%m")
dim_date["date"]        = dim_date["date"].dt.strftime("%Y-%m-%d")

print(f"  dim_date: {len(dim_date):,} rows")
dim_date.to_csv(f"{OUTPUT_DIR}/dim_date.csv", index=False)

print("\nAll Power BI tables written to powerbi/output/")
print("Tables: fact_orders, dim_customers, dim_products, dim_date")
