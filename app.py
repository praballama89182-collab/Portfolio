import streamlit as st
import pandas as pd

st.set_page_config(page_title="Portfolio Metrics Dashboard", layout="wide")

st.title("📊 Portfolio-Wise PPC Metrics Dashboard")
st.caption("Sponsored Products Advertised Product Report — grouped by Portfolio type")

# ---------------------------------------------------------------
# Data load
# ---------------------------------------------------------------
REQUIRED_COLS = [
    "Portfolio name", "Country", "Impressions", "Clicks",
    "Spend - converted", "7 Day Total Sales - converted",
]

@st.cache_data
def load_data(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected column(s): {missing}")
    return df

uploaded = st.sidebar.file_uploader(
    "Upload Sponsored Products Advertised Product Report (.xlsx)",
    type=["xlsx"],
)

if uploaded is None:
    st.info("👈 Upload the Sponsored Products Advertised Product Report to get started.")
    st.stop()

try:
    df = load_data(uploaded)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

# ---------------------------------------------------------------
# Portfolio grouping logic
# ---------------------------------------------------------------
def classify_portfolio(portfolio):
    """Bucket FBA-prefixed portfolios into CBT / Exclusive / Ageing / FBA (remaining).
    Non-FBA portfolios are excluded (returns None)."""
    if pd.isna(portfolio):
        return None
    p = str(portfolio).strip()
    pu = p.upper()
    if not pu.startswith("FBA"):
        return None
    if "CBT" in pu:
        return "CBT"
    if "EXCLUSIVE" in pu:
        return "Exclusive"
    if "LTSF" in pu or "AGEING" in pu or "AGING" in pu:
        return "Ageing"
    return "FBA"

df["Group"] = df["Portfolio name"].apply(classify_portfolio)

GROUP_ORDER = ["CBT", "Exclusive", "Ageing", "FBA"]

# ---------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------
countries_available = sorted(df["Country"].dropna().unique().tolist())
default_countries = [c for c in countries_available if c == "United States"] or countries_available

selected_countries = st.sidebar.multiselect(
    "Marketplace / Country",
    options=countries_available,
    default=default_countries,
)

if not selected_countries:
    st.warning("Select at least one country from the sidebar.")
    st.stop()

# ---------------------------------------------------------------
# Build metrics table
# ---------------------------------------------------------------
def build_group_table(data: pd.DataFrame, countries: list[str]) -> pd.DataFrame:
    d = data[data["Country"].isin(countries)]
    d = d[d["Group"].notna()]

    agg = d.groupby("Group").agg(
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
        Spend=("Spend - converted", "sum"),
        Sales=("7 Day Total Sales - converted", "sum"),
    )
    agg = agg.reindex(GROUP_ORDER).fillna(0)

    agg["ACOS %"] = (agg["Spend"] / agg["Sales"].replace(0, pd.NA) * 100).round(2)
    agg["ROAS"] = (agg["Sales"] / agg["Spend"].replace(0, pd.NA)).round(2)
    agg["CTR %"] = (agg["Clicks"] / agg["Impressions"].replace(0, pd.NA) * 100).round(2)
    agg["Spend"] = agg["Spend"].round(2)
    agg["Sales"] = agg["Sales"].round(2)

    agg = agg[["Impressions", "Clicks", "CTR %", "Spend", "Sales", "ACOS %", "ROAS"]]
    return agg

table = build_group_table(df, selected_countries)

# Totals row (combined across the 4 groups)
totals = pd.DataFrame({
    "Impressions": [table["Impressions"].sum()],
    "Clicks": [table["Clicks"].sum()],
    "Spend": [table["Spend"].sum()],
    "Sales": [table["Sales"].sum()],
}, index=["TOTAL"])
totals["ACOS %"] = (totals["Spend"] / totals["Sales"] * 100).round(2)
totals["ROAS"] = (totals["Sales"] / totals["Spend"]).round(2)
totals["CTR %"] = (totals["Clicks"] / totals["Impressions"] * 100).round(2)
totals = totals[["Impressions", "Clicks", "CTR %", "Spend", "Sales", "ACOS %", "ROAS"]]

full_table = pd.concat([table, totals])

# ---------------------------------------------------------------
# Display
# ---------------------------------------------------------------
st.subheader(f"Metrics by Portfolio Group — {', '.join(selected_countries)}")

st.dataframe(
    full_table.style.format({
        "Impressions": "{:,.0f}",
        "Clicks": "{:,.0f}",
        "CTR %": "{:.2f}%",
        "Spend": "${:,.2f}",
        "Sales": "${:,.2f}",
        "ACOS %": "{:.2f}%",
        "ROAS": "{:.2f}",
    }),
    use_container_width=True,
)

# ---------------------------------------------------------------
# Quick visual comparison
# ---------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Spend by Group**")
    st.bar_chart(table["Spend"])
with col2:
    st.markdown("**ROAS by Group**")
    st.bar_chart(table["ROAS"])

with st.expander("Which portfolios fall into each group?"):
    d = df[df["Country"].isin(selected_countries)]
    d = d[d["Group"].notna()]
    for g in GROUP_ORDER:
        names = sorted(d[d["Group"] == g]["Portfolio name"].unique())
        st.markdown(f"**{g}** ({len(names)}): {', '.join(names) if names else '—'}")

st.caption(
    "Grouping rule: only portfolios whose name starts with 'FBA' are included. "
    "Names containing 'CBT' → CBT, 'Exclusive' → Exclusive, 'LTSF'/'Ageing' → Ageing, "
    "all remaining FBA-prefixed portfolios → FBA."
)
