
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Daisy Scout", page_icon="🌼", layout="wide")

DATA_PROFILES = "data/profiles.csv"
DATA_SAMPLE = "data/sample_candidates.csv"

DEFAULT_COST = {
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
    return pd.Series({
        "Billable lb": billable_lb,
        "Landed Cost TWD": landed_cost_twd,
        "Shopee Net TWD": shopee_net_twd,
        "Estimated Profit TWD": estimated_profit_twd,
        "Required Price for Target Profit": required_price_twd,
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

    score += CATEGORY_SCORE.get(row.get("Daisy Category", "Other"), 0)

    if to_bool(row.get("Amazon Choice", False)):
        score += 3; reasons.append("Amazon Choice")
    if to_bool(row.get("Best Seller", False)):
        score += 4; reasons.append("Best Seller")
    if to_bool(row.get("New Release", False)):
        score += 5; reasons.append("New Release")
    if to_bool(row.get("Movers & Shakers", False)):
        score += 4; reasons.append("Movers & Shakers")

    score = min(100, score)
    if score >= 80:
        decision = "A - Research / Consider Launch"
    elif score >= 65:
        decision = "B - Watch / Check Pricing"
    elif score >= 50:
        decision = "C - Only if Strategic"
    else:
        decision = "D - Reject"

    return pd.Series({"Opportunity Score": score, "Decision": decision, "Reason": "; ".join(reasons[:8])})

def apply_prefilter(df, filters):
    work = df.copy()
    for c in ["Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating", "BSR"]:
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0)
    mask = (
        (work["Amazon Price USD"] >= filters["min_price"]) &
        (work["Amazon Price USD"] <= filters["max_price"]) &
        (work["Weight lb"] <= filters["max_weight"]) &
        (work["Amazon Reviews"] >= filters["min_reviews"]) &
        (work["Amazon Rating"] >= filters["min_rating"])
    )
    if filters["max_bsr"] > 0:
        mask = mask & ((work["BSR"] == 0) | (work["BSR"] <= filters["max_bsr"]))
    return work[mask].copy()

st.title("🌼 Daisy Scout v0.2")
st.caption("Profiles + Amazon candidate filtering + Shopee manual market check + profit decision.")

profiles = pd.read_csv(DATA_PROFILES)

with st.sidebar:
    st.header("Cost Settings")
    cfg = {
        "tax_rate": st.number_input("US tax rate", value=DEFAULT_COST["tax_rate"], format="%.5f"),
        "air_rate_per_lb": st.number_input("Air freight USD/lb", value=DEFAULT_COST["air_rate_per_lb"]),
        "min_billable_lb": st.number_input("Minimum billable lb", value=DEFAULT_COST["min_billable_lb"]),
        "exchange_rate": st.number_input("Exchange rate", value=DEFAULT_COST["exchange_rate"]),
        "shopee_fee": st.number_input("Shopee fee", value=DEFAULT_COST["shopee_fee"], format="%.3f"),
        "target_profit": st.number_input("Target profit TWD", value=DEFAULT_COST["target_profit"], step=100),
    }

tab_profile, tab_candidates, tab_results, tab_shopee = st.tabs(["1) Search Profile", "2) Candidate Input", "3) Results", "4) Shopee Checklist"])

with tab_profile:
    st.subheader("Search Profile")
    selected = st.selectbox("Choose a saved profile", profiles["Profile Name"].tolist())
    profile = profiles[profiles["Profile Name"] == selected].iloc[0].to_dict()

    st.write("Defaults are editable before filtering.")
    col1, col2, col3 = st.columns(3)
    with col1:
        min_price = st.number_input("Min Amazon Price USD", value=float(profile.get("Min Price", 20)))
        max_price = st.number_input("Max Amazon Price USD", value=float(profile.get("Max Price", 250)))
    with col2:
        max_weight = st.number_input("Max Weight lb", value=float(profile.get("Max Weight", 3)))
        min_reviews = st.number_input("Min Amazon Reviews", value=int(profile.get("Min Reviews", 300)))
    with col3:
        min_rating = st.number_input("Min Rating", value=float(profile.get("Min Rating", 4.2)))
        max_bsr = st.number_input("Max BSR (0 = ignore)", value=int(profile.get("Max BSR", 5000)))

    st.markdown("### Amazon Source / Entry Point")
    st.write("Source means where to start researching on Amazon, not a product category.")
    sources = st.multiselect(
        "Sources",
        ["Best Sellers", "New Releases", "Movers & Shakers", "Most Wished For", "Gift Ideas", "Amazon Search"],
        default=[s.strip() for s in str(profile.get("Sources", "Best Sellers,New Releases")).split(",") if s.strip()]
    )

    st.markdown("### Amazon Department / Category")
    department = st.text_input("Amazon Department", value=str(profile.get("Amazon Department", "")))
    category = st.text_input("Amazon Category", value=str(profile.get("Amazon Category", "")))
    amazon_url = st.text_input("Amazon source/category URL", value=str(profile.get("Amazon URL", "")))
    if amazon_url:
        st.link_button("Open Amazon Source Page", amazon_url)

    st.session_state["filters"] = {
        "min_price": min_price, "max_price": max_price, "max_weight": max_weight,
        "min_reviews": min_reviews, "min_rating": min_rating, "max_bsr": max_bsr,
        "sources": sources, "department": department, "category": category,
        "amazon_url": amazon_url
    }

with tab_candidates:
    st.subheader("Candidate Products")
    st.write("V0.2: upload or manually enter Amazon candidates. V0.3 will add Amazon source import options.")
    uploaded = st.file_uploader("Upload candidate CSV", type=["csv"])
    df = pd.read_csv(uploaded) if uploaded else pd.read_csv(DATA_SAMPLE)

    required_cols = [
        "Product Name", "Amazon URL", "Amazon Price USD", "Weight lb",
        "Amazon Reviews", "Amazon Rating", "BSR", "Daisy Category",
        "Amazon Choice", "Best Seller", "New Release", "Movers & Shakers",
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
            "Movers & Shakers": st.column_config.CheckboxColumn("Movers & Shakers"),
        }
    )
    st.session_state["candidates"] = edited

with tab_results:
    st.subheader("Filtered & Scored Results")
    candidates = st.session_state.get("candidates", pd.read_csv(DATA_SAMPLE))
    filters = st.session_state.get("filters", {"min_price":20, "max_price":250, "max_weight":3, "min_reviews":300, "min_rating":4.2, "max_bsr":5000})
    prefiltered = apply_prefilter(candidates, filters)
    st.write(f"Candidates before filter: {len(candidates)} | after filter: {len(prefiltered)}")

    if len(prefiltered) == 0:
        st.warning("No candidates passed the profile filters.")
    else:
        work = prefiltered.copy()
        for c in ["Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating", "Target Shopee Price TWD", "Shopee Seller Count", "Shopee Highest Sold", "BSR"]:
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0)
        out = pd.concat([work.reset_index(drop=True), work.apply(lambda r: calc(r, cfg), axis=1).reset_index(drop=True)], axis=1)
        out = pd.concat([out, out.apply(score, axis=1)], axis=1).sort_values(["Opportunity Score", "Estimated Profit TWD"], ascending=[False, False])
        st.dataframe(out[[
            "Decision", "Opportunity Score", "Product Name", "Daisy Category",
            "Amazon Price USD", "Weight lb", "Amazon Reviews", "Amazon Rating", "BSR",
            "Target Shopee Price TWD", "Landed Cost TWD", "Estimated Profit TWD",
            "Required Price for Target Profit", "Shopee Seller Count", "Shopee Highest Sold",
            "Reason", "Amazon URL"
        ]], use_container_width=True)
        st.download_button("Download Results CSV", out.to_csv(index=False).encode("utf-8-sig"), "daisy_scout_v02_results.csv", "text/csv")

with tab_shopee:
    st.subheader("Shopee Manual Market Check")
    st.write("""
V0.2 intentionally avoids Shopee scraping.

For each candidate that passes Amazon filters:
1. Search exact English product name.
2. Search Chinese generic keyword.
3. Search brand + product type.
4. Record lowest price, median price, seller count, highest sold, and whether it is exact same model.
5. Enter those values in Candidate Input.
    """)
    st.success("Goal: Daisy Scout filters Amazon first, so you only check Shopee for better candidates.")
