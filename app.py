
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Daisy Scout", page_icon="🌼", layout="wide")

st.title("🌼 Daisy Scout v0.1")
st.caption("Semi-automatic product opportunity screener for Daisy's Breeze.")

DEFAULTS = {
    "tax_rate": 0.08875,
    "air_rate_per_lb": 5.25,
    "min_billable_lb": 3.0,
    "exchange_rate": 31.9,
    "shopee_fee": 0.13,
    "target_profit": 1200,
}

CATEGORY_SCORE = {
    "Kindle / E-reader": 15,
    "Disney / IP": 15,
    "Parent Tech": 15,
    "Education Tech": 15,
    "US Exclusive / Limited": 10,
    "General Electronics": 5,
    "Other": 0,
}

def to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ["true", "yes", "y", "1", "是"]

def calc(row, cfg):
    amazon_price = float(row.get("Amazon Price USD", 0) or 0)
    weight = float(row.get("Weight lb", 0) or 0)
    target_price = float(row.get("Target Shopee Price TWD", 0) or 0)
    billable_lb = max(weight, cfg["min_billable_lb"])
    landed_cost_twd = ((amazon_price * (1 + cfg["tax_rate"])) + billable_lb * cfg["air_rate_per_lb"]) * cfg["exchange_rate"]
    shopee_net_twd = target_price * (1 - cfg["shopee_fee"])
    estimated_profit_twd = shopee_net_twd - landed_cost_twd
    required_price_twd = (landed_cost_twd + cfg["target_profit"]) / (1 - cfg["shopee_fee"])
    profit_margin = estimated_profit_twd / target_price if target_price else 0
    return pd.Series({
        "Billable lb": billable_lb,
        "Landed Cost TWD": landed_cost_twd,
        "Shopee Net TWD": shopee_net_twd,
        "Estimated Profit TWD": estimated_profit_twd,
        "Required Price for Target Profit": required_price_twd,
        "Profit Margin": profit_margin,
    })

def score(row):
    score = 0
    reasons = []

    profit = float(row.get("Estimated Profit TWD", 0) or 0)
    if profit >= 1800:
        score += 30; reasons.append("Strong profit")
    elif profit >= 1200:
        score += 25; reasons.append("Good profit")
    elif profit >= 800:
        score += 15; reasons.append("Acceptable profit")
    elif profit >= 0:
        score += 5; reasons.append("Low profit")
    else:
        reasons.append("Negative profit")

    sellers = float(row.get("Shopee Seller Count", 0) or 0)
    if sellers == 0:
        reasons.append("Shopee seller count missing/zero")
    elif sellers <= 3:
        score += 25; reasons.append("Very low Shopee competition")
    elif sellers <= 10:
        score += 20; reasons.append("Low Shopee competition")
    elif sellers <= 20:
        score += 12; reasons.append("Medium Shopee competition")
    else:
        score += 3; reasons.append("High Shopee competition")

    sold = float(row.get("Shopee Highest Sold", 0) or 0)
    if sold >= 100:
        score += 20; reasons.append("Strong Shopee demand")
    elif sold >= 20:
        score += 15; reasons.append("Some Shopee demand")
    elif sold >= 1:
        score += 8; reasons.append("Weak but present Shopee demand")
    else:
        reasons.append("No Shopee sold signal yet")

    reviews = float(row.get("Amazon Reviews", 0) or 0)
    rating = float(row.get("Amazon Rating", 0) or 0)
    if reviews >= 2000 and rating >= 4.4:
        score += 15; reasons.append("Strong Amazon validation")
    elif reviews >= 500 and rating >= 4.2:
        score += 12; reasons.append("Good Amazon validation")
    elif reviews >= 100 and rating >= 4.0:
        score += 7; reasons.append("Some Amazon validation")
    else:
        reasons.append("Weak Amazon validation")

    weight = float(row.get("Weight lb", 0) or 0)
    if weight <= 1:
        score += 10; reasons.append("Excellent weight")
    elif weight <= 3:
        score += 8; reasons.append("Within 3 lb air minimum")
    elif weight <= 5:
        score += 4; reasons.append("Acceptable weight")
    else:
        reasons.append("Heavy item")

    category = row.get("Daisy Category", "Other")
    score += CATEGORY_SCORE.get(category, 0)

    if to_bool(row.get("Amazon Choice", False)):
        score += 3; reasons.append("Amazon Choice")
    if to_bool(row.get("Best Seller", False)):
        score += 4; reasons.append("Best Seller")
    if to_bool(row.get("New Release", False)):
        score += 5; reasons.append("New Release")

    score = min(100, score)
    if score >= 80:
        decision = "A - Research / Consider Launch"
    elif score >= 65:
        decision = "B - Watch / Check Pricing"
    elif score >= 50:
        decision = "C - Only if Strategic"
    else:
        decision = "D - Reject"

    return pd.Series({
        "Opportunity Score": score,
        "Decision": decision,
        "Reason": "; ".join(reasons[:7])
    })

with st.sidebar:
    st.header("Cost Settings")
    cfg = {
        "tax_rate": st.number_input("US tax rate", value=DEFAULTS["tax_rate"], format="%.5f"),
        "air_rate_per_lb": st.number_input("Air freight USD/lb", value=DEFAULTS["air_rate_per_lb"]),
        "min_billable_lb": st.number_input("Minimum billable lb", value=DEFAULTS["min_billable_lb"]),
        "exchange_rate": st.number_input("Exchange rate", value=DEFAULTS["exchange_rate"]),
        "shopee_fee": st.number_input("Shopee fee", value=DEFAULTS["shopee_fee"], format="%.3f"),
        "target_profit": st.number_input("Target profit TWD", value=DEFAULTS["target_profit"], step=100),
    }

st.subheader("Candidate Input")
uploaded = st.file_uploader("Upload CSV, or use sample data", type=["csv"])

if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("sample_candidates.csv")

required_cols = [
    "Product Name", "Amazon URL", "Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating",
    "Daisy Category", "Amazon Choice", "Best Seller", "New Release",
    "Shopee Keyword", "Target Shopee Price TWD", "Shopee Seller Count", "Shopee Highest Sold"
]

for c in required_cols:
    if c not in df.columns:
        df[c] = ""

edited = st.data_editor(
    df[required_cols],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Amazon URL": st.column_config.LinkColumn("Amazon URL"),
        "Daisy Category": st.column_config.SelectboxColumn("Daisy Category", options=list(CATEGORY_SCORE.keys())),
        "Amazon Choice": st.column_config.CheckboxColumn("Amazon Choice"),
        "Best Seller": st.column_config.CheckboxColumn("Best Seller"),
        "New Release": st.column_config.CheckboxColumn("New Release"),
    }
)

if st.button("Analyze Opportunities", type="primary"):
    work = edited.copy()
    for c in ["Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating", "Target Shopee Price TWD", "Shopee Seller Count", "Shopee Highest Sold"]:
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0)

    calcs = work.apply(lambda r: calc(r, cfg), axis=1)
    out = pd.concat([work.reset_index(drop=True), calcs.reset_index(drop=True)], axis=1)
    scores = out.apply(score, axis=1)
    out = pd.concat([out, scores], axis=1).sort_values(["Opportunity Score", "Estimated Profit TWD"], ascending=[False, False])

    st.subheader("Results")
    st.dataframe(
        out[[
            "Decision", "Opportunity Score", "Product Name", "Daisy Category",
            "Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating",
            "Target Shopee Price TWD", "Landed Cost TWD", "Estimated Profit TWD",
            "Required Price for Target Profit", "Shopee Seller Count", "Shopee Highest Sold",
            "Reason", "Amazon URL"
        ]],
        use_container_width=True
    )

    st.download_button(
        "Download Results CSV",
        out.to_csv(index=False).encode("utf-8-sig"),
        file_name="daisy_scout_results.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("V0.1 does not scrape Amazon or Shopee. Amazon candidates are entered/uploaded manually; Shopee competition is entered manually after your market check.")
