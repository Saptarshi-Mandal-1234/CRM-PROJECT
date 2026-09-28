# RetainIQ

> A Python decision dashboard that turns e-commerce CRM data (customers, orders, payments, reviews) into revenue and retention actions.

**Business Question:** Where should management spend retention and delivery-improvement budget to protect and grow revenue?

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://crm-project-kdenz3kyr9f3wxdewy7s4u.streamlit.app/)

🚀 **Live App:** [https://crm-project-kdenz3kyr9f3wxdewy7s4u.streamlit.app/](https://crm-project-kdenz3kyr9f3wxdewy7s4u.streamlit.app/)

---

## Tech Stack

| Layer | Library |
|---|---|
| Dashboard | Streamlit 1.64 |
| Data wrangling | Pandas 3.x, NumPy 2.x |
| Charts | Plotly 7.x |
| AI Advisor (optional) | Anthropic SDK (claude-3-haiku) |

---

## Dataset

Download the **Brazilian E-Commerce Public Dataset by Olist** from Kaggle:  
<https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>

Extract all CSV files into a folder named **`data/`** in the project root:

```
data/
  olist_customers_dataset.csv
  olist_order_items_dataset.csv
  olist_order_payments_dataset.csv
  olist_order_reviews_dataset.csv
  olist_orders_dataset.csv
  olist_products_dataset.csv
  olist_sellers_dataset.csv
  product_category_name_translation.csv
```

> **Note:** The app auto-downloads the dataset from GitHub Release assets on first load — no manual setup needed when using the live app.

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Set API key for AI Advisor
#    export ANTHROPIC_API_KEY=sk-ant-...
#    export LLM_MODEL=claude-3-haiku-20240307   # optional, this is the default

# 3. Launch the dashboard
streamlit run retainiq_app.py
```

The sidebar lets you change the data folder path if your CSVs live elsewhere.

---

## Dashboard Pages

| Page | Contents |
|---|---|
| **Executive Overview** | 6 KPIs + monthly revenue area chart + key insight |
| **Customer & Sales Analysis** | Revenue trend + 3-month forecast, top categories/states, late delivery vs review score, RFM segments |
| **Risk, Opportunity & AI Advisor** | Risk flags, opportunity estimate slider, action table, AI executive brief |

---

## Key Design Decisions

- **Revenue = item price only** (freight excluded); clearly labelled throughout.
- **Delivered orders only** — cancelled/shipped orders excluded from all metrics.
- **`customer_unique_id`** used to identify persons (not `customer_id`).
- Reviews deduplicated: highest score per order retained.
- RFM segmentation: Champions / Loyal / At Risk / Lost using quartile scoring.
- Forecast: linear trend only — labelled as an estimate, not a causal model.
- AI Advisor degrades gracefully to rule-based template when no API key is set.
