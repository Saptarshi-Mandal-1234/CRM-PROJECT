# RetainIQ – E-commerce CRM Decision Dashboard
# Streamlit single-file app: backend + frontend + analysis
# Revenue = item price (freight excluded from revenue, shown separately where relevant)

import os, warnings
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="RetainIQ", page_icon="📊", layout="wide")

# ── Constants ─────────────────────────────────────────────────────────────────
KAGGLE_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
RFM_LABELS  = ["Champions", "Loyal", "At Risk", "Lost"]

# ── Data loading (cached) ─────────────────────────────────────────────────────
@st.cache_data
def load_data(data_dir: str):
    """Load, join, and clean all CSV files. Returns master DataFrame."""
    needed = {
        "orders":       "olist_orders_dataset.csv",
        "items":        "olist_order_items_dataset.csv",
        "customers":    "olist_customers_dataset.csv",
        "reviews":      "olist_order_reviews_dataset.csv",
        "products":     "olist_products_dataset.csv",
        "translation":  "product_category_name_translation.csv",
    }
    missing = [v for v in needed.values() if not os.path.exists(f"{data_dir}/{v}")]
    if missing:
        return None, missing

    orders   = pd.read_csv(f"{data_dir}/{needed['orders']}")
    items    = pd.read_csv(f"{data_dir}/{needed['items']}")
    cust     = pd.read_csv(f"{data_dir}/{needed['customers']}")
    reviews  = pd.read_csv(f"{data_dir}/{needed['reviews']}")
    products = pd.read_csv(f"{data_dir}/{needed['products']}")
    trans    = pd.read_csv(f"{data_dir}/{needed['translation']}")

    # Delivered orders only
    orders = orders[orders["order_status"] == "delivered"].copy()

    # Parse dates
    for col in ["order_purchase_timestamp", "order_delivered_customer_date",
                "order_estimated_delivery_date"]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    # Delivery metrics
    orders["delivery_days"] = (
        orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"]
    ).dt.days
    orders["is_late"] = (
        orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"]
    )

    # Join customers (use customer_unique_id to identify persons)
    orders = orders.merge(cust[["customer_id", "customer_unique_id", "customer_state"]],
                          on="customer_id", how="left")

    # Deduplicate reviews: keep highest score per order
    reviews_dedup = (reviews.sort_values("review_score", ascending=False)
                            .drop_duplicates("order_id")[["order_id", "review_score"]])

    # Join items + products + translation
    products = products.merge(trans, on="product_category_name", how="left")
    items = items.merge(products[["product_id", "product_category_name_english"]], 
                        on="product_id", how="left")
    items["category"] = items["product_category_name_english"].fillna("unknown")

    # Aggregate items to order level (sum price & freight per order)
    items_agg = items.groupby("order_id").agg(
        revenue=("price", "sum"),
        freight=("freight_value", "sum"),
        category=("category", lambda x: x.mode().iloc[0] if len(x) > 0 else "unknown")
    ).reset_index()

    # Master join
    df = orders.merge(items_agg, on="order_id", how="inner")
    df = df.merge(reviews_dedup, on="order_id", how="left")
    df["purchase_month"] = df["order_purchase_timestamp"].dt.to_period("M")

    return df, []

# ── RFM segmentation ──────────────────────────────────────────────────────────
def compute_rfm(df: pd.DataFrame):
    snapshot = df["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
    rfm = df.groupby("customer_unique_id").agg(
        recency=("order_purchase_timestamp", lambda x: (snapshot - x.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("revenue", "sum")
    ).reset_index()

    rfm["r_score"] = pd.qcut(rfm["recency"],  4, labels=[4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 4,
                              labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"],  4, labels=[1, 2, 3, 4]).astype(int)
    rfm["rfm_total"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

    def label(row):
        if row["rfm_total"] >= 10:        return "Champions"
        if row["rfm_total"] >= 7:         return "Loyal"
        if row["rfm_total"] >= 5:         return "At Risk"
        return "Lost"

    rfm["segment"] = rfm.apply(label, axis=1)
    return rfm

# ── Forecast helper (linear trend, no external deps) ─────────────────────────
def linear_forecast(series: pd.Series, n: int = 3):
    x = np.arange(len(series))
    m, b = np.polyfit(x, series.values, 1)
    future_x = np.arange(len(series), len(series) + n)
    return m * future_x + b

# ── AI Advisor ────────────────────────────────────────────────────────────────
def ai_brief(stats: dict) -> str:
    """Return executive brief from LLM if key exists, else rule-based template."""
    prompt = (
        "You are a CRM strategy consultant. Given these e-commerce metrics, "
        "write a 3-sentence executive brief and 3 concrete action points.\n\n"
        f"Metrics: {stats}"
    )
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("No API key")
        model = os.environ.get("LLM_MODEL", "claude-3-haiku-20240307")
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception:
        # Rule-based fallback
        rr  = stats.get("repeat_rate", 0)
        rev = stats.get("total_revenue", 0)
        otd = stats.get("on_time_pct", 0)
        ar_rev = stats.get("at_risk_revenue", 0)
        return (
            f"**Executive Brief (Auto-generated)**\n\n"
            f"Revenue stands at **R$ {rev:,.0f}** with a repeat-customer rate of **{rr:.1f}%**, "
            f"indicating significant headroom to grow loyalty. "
            f"On-time delivery is **{otd:.1f}%** — late deliveries directly suppress review scores "
            f"and future orders. "
            f"**R$ {ar_rev:,.0f}** in revenue is held by At-Risk customers who have not repurchased recently.\n\n"
            f"**Action Points**\n"
            f"1. 🚚 Prioritise logistics partners in high-latency states to push on-time delivery above 95%.\n"
            f"2. 🔁 Launch a re-engagement campaign for At-Risk customers (email + discount) to protect "
            f"the R$ {ar_rev:,.0f} revenue at stake.\n"
            f"3. 📦 Audit low-review categories; negotiate SLAs with sellers or remove chronic underperformers."
        )

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ RetainIQ Controls")
data_dir = st.sidebar.text_input("Data folder path", value="data")
df_raw, missing = load_data(data_dir)

if missing:
    st.error(
        f"**Missing data files:** {missing}\n\n"
        f"Download the dataset from [Kaggle]({KAGGLE_URL}), extract all CSVs into a folder "
        f"called **`data/`** in the project root, then refresh."
    )
    st.stop()

# Sidebar filters
min_d = df_raw["order_purchase_timestamp"].min().date()
max_d = df_raw["order_purchase_timestamp"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
# Guard: user may select only one end of the range — treat as full range until both ends chosen
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    dr_start, dr_end = date_range[0], date_range[1]
else:
    dr_start, dr_end = min_d, max_d

all_states = sorted(df_raw["customer_state"].dropna().unique())
sel_states = st.sidebar.multiselect("States", all_states, default=all_states)
all_cats = sorted(df_raw["category"].dropna().unique())
sel_cats = st.sidebar.multiselect("Categories", all_cats, default=all_cats)

# Apply filters
df = df_raw[
    (df_raw["order_purchase_timestamp"].dt.date >= dr_start) &
    (df_raw["order_purchase_timestamp"].dt.date <= dr_end) &
    (df_raw["customer_state"].isin(sel_states)) &
    (df_raw["category"].isin(sel_cats))
].copy()

# Opportunity slider
repeat_lift = st.sidebar.slider("Repeat rate lift (pp)", 1, 20, 5,
                                help="Estimate extra revenue if repeat rate rises by this many percentage points")

# ── Compute core KPIs ────────────────────────────────────────────────────────
total_revenue   = df["revenue"].sum()
total_orders    = df["order_id"].nunique()
avg_order_value = total_revenue / total_orders if total_orders else 0
avg_review      = df["review_score"].mean()
on_time_pct     = (1 - df["is_late"].mean()) * 100

# Repeat customers: customer_unique_id with >1 distinct order
order_counts    = df.groupby("customer_unique_id")["order_id"].nunique()
repeat_rate     = (order_counts > 1).mean() * 100

rfm = compute_rfm(df)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1 – EXECUTIVE OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
page = st.sidebar.radio("Navigate", ["Executive Overview",
                                      "Customer & Sales Analysis",
                                      "Risk, Opportunity & AI Advisor"])

if page == "Executive Overview":
    st.title("📊 Executive Overview")
    st.caption("Revenue = item price only (freight excluded). Delivered orders only.")

    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c1.metric("💰 Total Revenue",       f"R$ {total_revenue:,.0f}")
    c2.metric("🛒 Total Orders",         f"{total_orders:,}")
    c3.metric("🧾 Avg Order Value",      f"R$ {avg_order_value:,.2f}")
    c4.metric("🔁 Repeat Customer Rate", f"{repeat_rate:.1f}%")
    c5.metric("⭐ Avg Review Score",     f"{avg_review:.2f} / 5")
    c6.metric("🚚 On-time Delivery",     f"{on_time_pct:.1f}%")

    st.divider()
    st.subheader("Key Insight")
    low_otd   = on_time_pct < 90
    low_rev   = repeat_rate < 10
    insight = []
    if low_otd:
        insight.append(f"⚠️ On-time delivery is **{on_time_pct:.1f}%** — below the 90% target. "
                        "Late deliveries correlate with lower review scores and reduce repeat purchase intent.")
    if low_rev:
        insight.append(f"⚠️ Only **{repeat_rate:.1f}%** of customers repurchase. "
                        "A 5pp improvement could unlock significant incremental revenue.")
    if not insight:
        insight.append(f"✅ Operations are healthy. Focus on growing the **{repeat_rate:.1f}%** "
                        "repeat rate to compound revenue without new acquisition spend.")
    for i in insight:
        st.info(i)

    # Monthly revenue mini-chart
    monthly = df.groupby("purchase_month")["revenue"].sum().reset_index()
    monthly["month_str"] = monthly["purchase_month"].astype(str)
    fig = px.area(monthly, x="month_str", y="revenue",
                  title="Monthly Revenue (delivered orders)",
                  labels={"month_str": "Month", "revenue": "Revenue (R$)"})
    fig.update_layout(height=280, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2 – CUSTOMER & SALES ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Customer & Sales Analysis":
    st.title("📈 Customer & Sales Analysis")

    # Monthly revenue + 3-month linear forecast
    monthly = (df.groupby("purchase_month")["revenue"].sum()
                 .reset_index().sort_values("purchase_month"))
    monthly["month_str"] = monthly["purchase_month"].astype(str)
    forecast_vals = linear_forecast(monthly["revenue"], n=3)
    last_month = monthly["purchase_month"].iloc[-1]
    future_months = [(last_month + i).strftime("%Y-%m") for i in range(1, 4)]

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=monthly["month_str"], y=monthly["revenue"],
                                   mode="lines+markers", name="Actual"))
    fig_trend.add_trace(go.Scatter(x=future_months, y=forecast_vals,
                                   mode="lines+markers", name="Forecast (linear estimate)",
                                   line=dict(dash="dash", color="orange")))
    fig_trend.update_layout(title="Monthly Revenue + 3-Month Linear Trend Estimate",
                            height=320, margin=dict(t=40, b=20),
                            xaxis_title="Month", yaxis_title="Revenue (R$)")
    st.plotly_chart(fig_trend, use_container_width=True)
    st.caption("⚠️ Forecast is a linear trend estimate only — not a causal model. Use for directional planning.")

    col1, col2 = st.columns(2)

    # Top 10 categories by revenue
    with col1:
        top_cat = (df.groupby("category")["revenue"].sum()
                     .nlargest(10).reset_index()
                     .sort_values("revenue"))
        fig_cat = px.bar(top_cat, x="revenue", y="category", orientation="h",
                         title="Top 10 Categories by Revenue",
                         labels={"revenue": "Revenue (R$)", "category": "Category"})
        fig_cat.update_layout(height=340, margin=dict(t=40, b=20))
        st.plotly_chart(fig_cat, use_container_width=True)

    # Top 10 states by revenue
    with col2:
        top_state = (df.groupby("customer_state")["revenue"].sum()
                       .nlargest(10).reset_index()
                       .sort_values("revenue"))
        fig_state = px.bar(top_state, x="revenue", y="customer_state", orientation="h",
                           title="Top 10 States by Revenue",
                           labels={"revenue": "Revenue (R$)", "customer_state": "State"})
        fig_state.update_layout(height=340, margin=dict(t=40, b=20))
        st.plotly_chart(fig_state, use_container_width=True)

    # Late delivery vs review score
    st.subheader("Driver: Late Delivery → Review Score")
    late_review = df.groupby("is_late")["review_score"].mean().reset_index()
    late_review["Delivery"] = late_review["is_late"].map({True: "Late", False: "On Time"})
    fig_late = px.bar(late_review, x="Delivery", y="review_score", color="Delivery",
                      title="Avg Review Score: On-Time vs Late Deliveries",
                      labels={"review_score": "Avg Review Score"},
                      color_discrete_map={"On Time": "#2ecc71", "Late": "#e74c3c"})
    fig_late.update_layout(height=280, margin=dict(t=40, b=20), showlegend=False)
    st.plotly_chart(fig_late, use_container_width=True)
    on_time_score = df[~df["is_late"]]["review_score"].mean()
    late_score    = df[df["is_late"]]["review_score"].mean()
    st.info(f"**Fact:** On-time orders average **{on_time_score:.2f}★** vs **{late_score:.2f}★** for late. "
            f"→ **Insight:** Late delivery costs ~{on_time_score - late_score:.2f} review points per order. "
            f"→ **Action:** Identify high-latency seller–state pairs and re-route or penalise.")

    # RFM segments
    st.subheader("RFM Customer Segments")
    seg_summary = rfm.merge(
        df.groupby("customer_unique_id")["revenue"].sum().reset_index(),
        on="customer_unique_id", how="left"
    )
    seg_agg = seg_summary.groupby("segment").agg(
        customers=("customer_unique_id", "count"),
        revenue=("revenue", "sum")
    ).reset_index()
    seg_agg["revenue_share"] = (seg_agg["revenue"] / seg_agg["revenue"].sum() * 100).round(1)

    col3, col4 = st.columns(2)
    with col3:
        fig_seg_cnt = px.pie(seg_agg, names="segment", values="customers",
                             title="Segment Size (# Customers)",
                             color="segment",
                             color_discrete_map={"Champions":"#2ecc71","Loyal":"#3498db",
                                                  "At Risk":"#f39c12","Lost":"#e74c3c"})
        fig_seg_cnt.update_layout(height=300, margin=dict(t=40, b=20))
        st.plotly_chart(fig_seg_cnt, use_container_width=True)
    with col4:
        fig_seg_rev = px.pie(seg_agg, names="segment", values="revenue",
                             title="Segment Revenue Share",
                             color="segment",
                             color_discrete_map={"Champions":"#2ecc71","Loyal":"#3498db",
                                                  "At Risk":"#f39c12","Lost":"#e74c3c"})
        fig_seg_rev.update_layout(height=300, margin=dict(t=40, b=20))
        st.plotly_chart(fig_seg_rev, use_container_width=True)

    st.dataframe(seg_agg.rename(columns={"customers": "Customers", "revenue": "Revenue (R$)",
                                          "revenue_share": "Revenue Share (%)"}), hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3 – RISK, OPPORTUNITY & AI ADVISOR
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Risk, Opportunity & AI Advisor":
    st.title("🚨 Risk, Opportunity & AI Advisor")

    # ── Risk Flags ────────────────────────────────────────────────────────────
    st.subheader("🔴 Risk Flags")

    # Declining months (last 3 months trend)
    monthly = (df.groupby("purchase_month")["revenue"].sum()
                 .reset_index().sort_values("purchase_month"))
    if len(monthly) >= 3:
        last3 = monthly["revenue"].iloc[-3:].values
        declining = all(last3[i] > last3[i+1] for i in range(2))
        if declining:
            st.error(f"📉 Revenue has declined for 3 consecutive months "
                     f"(last 3: R$ {last3[0]:,.0f} → R$ {last3[1]:,.0f} → R$ {last3[2]:,.0f})")
        else:
            st.success("✅ No 3-month consecutive revenue decline detected.")

    # Low-review categories
    low_review_cats = (df.groupby("category")["review_score"].mean()
                         .reset_index().query("review_score < 3.5")
                         .sort_values("review_score"))
    if not low_review_cats.empty:
        st.warning(f"⭐ **{len(low_review_cats)} categories** have avg review < 3.5: "
                   f"{', '.join(low_review_cats['category'].tolist()[:5])}"
                   f"{'...' if len(low_review_cats) > 5 else ''}")

    # High late-delivery states
    late_by_state = (df.groupby("customer_state")["is_late"].mean() * 100).reset_index()
    late_by_state.columns = ["state", "late_pct"]
    high_late_states = late_by_state[late_by_state["late_pct"] > 20].sort_values("late_pct", ascending=False)
    if not high_late_states.empty:
        st.warning(f"🚚 **{len(high_late_states)} states** have >20% late deliveries: "
                   f"{', '.join(high_late_states['state'].tolist()[:5])}")

    # At-risk customers
    at_risk_ids = rfm[rfm["segment"] == "At Risk"]["customer_unique_id"]
    at_risk_rev = df[df["customer_unique_id"].isin(at_risk_ids)]["revenue"].sum()
    at_risk_cnt = len(at_risk_ids)
    st.error(f"👥 **{at_risk_cnt:,} At-Risk customers** represent **R$ {at_risk_rev:,.0f}** revenue at stake.")

    # ── Opportunity Estimate ─────────────────────────────────────────────────
    st.subheader("💡 Opportunity Estimate")
    unique_customers   = df["customer_unique_id"].nunique()
    current_repeaters  = int((order_counts > 1).sum())
    lift_customers     = int(unique_customers * repeat_lift / 100)
    opp_revenue        = lift_customers * avg_order_value
    st.info(
        f"**Assumption:** If repeat-customer rate rises by **{repeat_lift} percentage points** "
        f"({lift_customers:,} additional repeaters from {unique_customers:,} total customers), "
        f"at the current avg order value of **R$ {avg_order_value:,.2f}**, "
        f"estimated additional revenue = **R$ {opp_revenue:,.0f}**.\n\n"
        f"_(This is a first-order estimate. Actual uplift depends on campaign cost, churn, and order cadence.)_"
    )

    # ── Action Table ─────────────────────────────────────────────────────────
    st.subheader("📋 Action Table")
    # Pre-compute review gap so it's not nested inside a dict literal
    _on_time_score = df[~df["is_late"]]["review_score"].mean()
    _late_score    = df[ df["is_late"]]["review_score"].mean()
    _review_gap    = _on_time_score - _late_score
    actions = pd.DataFrame([
        {"Fact": f"Repeat rate is {repeat_rate:.1f}%",
         "Insight": "Most customers buy once and leave",
         "Risk / Opportunity": f"R$ {opp_revenue:,.0f} incremental revenue at +{repeat_lift}pp",
         "Action": "Launch post-purchase email sequence with 2nd-order incentive",
         "Est. Impact": f"+{repeat_lift}pp repeat rate → R$ {opp_revenue:,.0f}"},
        {"Fact": f"On-time delivery is {on_time_pct:.1f}%",
         "Insight": f"Late orders score ~{_review_gap:.2f}★ lower than on-time orders",
         "Risk / Opportunity": "Low scores reduce future conversions",
         "Action": "Re-route shipments in top-3 late states; enforce SLA with sellers",
         "Est. Impact": "+0.3–0.5★ avg review; 5–10% churn reduction"},
        {"Fact": f"{at_risk_cnt:,} At-Risk customers",
         "Insight": "High recency gap — haven't bought in 60–120 days",
         "Risk / Opportunity": f"R$ {at_risk_rev:,.0f} revenue at stake",
         "Action": "Targeted re-engagement campaign (personalised discount + product rec)",
         "Est. Impact": f"Recover 20–30% → R$ {at_risk_rev*0.25:,.0f}"},
        {"Fact": f"{len(low_review_cats)} categories under 3.5★",
         "Insight": "Structural quality or expectation mismatch",
         "Risk / Opportunity": "Category-level churn + marketplace reputation risk",
         "Action": "Audit seller quality in these categories; improve product descriptions",
         "Est. Impact": "+0.2–0.4★; reduces returns and negative reviews"},
    ])
    st.dataframe(actions, use_container_width=True, hide_index=True)

    # ── AI Advisor ────────────────────────────────────────────────────────────
    st.subheader("🤖 AI Advisor")
    if st.button("Generate Executive Brief"):
        stats = {
            "total_revenue":   round(total_revenue, 0),
            "total_orders":    total_orders,
            "avg_order_value": round(avg_order_value, 2),
            "repeat_rate":     round(repeat_rate, 2),
            "on_time_pct":     round(on_time_pct, 2),
            "avg_review":      round(avg_review, 2),
            "at_risk_count":   at_risk_cnt,
            "at_risk_revenue": round(at_risk_rev, 0),
            "low_review_cats": len(low_review_cats),
        }
        with st.spinner("Generating brief…"):
            brief = ai_brief(stats)
        st.markdown(brief)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.caption("ℹ️ No ANTHROPIC_API_KEY found — showing rule-based brief. "
                       "Set the env var to enable LLM generation.")
