import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="Portfolio Metrics Dashboard", layout="wide", page_icon="📊")

# =================================================================
# THEME / STYLING  (Looker Studio inspired palette)
# =================================================================
COLOR_SPEND = "#4285F4"   # blue
COLOR_SALES = "#34A853"   # green
COLOR_ACOS = "#EA4335"    # red
COLOR_ROAS = "#9334E6"    # purple
COLOR_TREND = "#F9AB00"   # amber

GROUP_COLORS = {
    "CBT": "#4285F4",
    "Exclusive": "#9334E6",
    "Ageing": "#F9AB00",
    "FBA": "#34A853",
}

st.markdown(
    """
    <style>
    .stApp { background-color: #F8F9FA; }
    h1, h2, h3 { color: #202124; font-family: 'Google Sans', 'Segoe UI', sans-serif; }
    .kpi-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px 18px 14px 18px;
        box-shadow: 0 1px 3px rgba(60,64,67,0.15), 0 1px 2px rgba(60,64,67,0.10);
        border-top: 4px solid var(--accent);
        text-align: left;
    }
    .kpi-label {
        font-size: 12.5px;
        color: #5F6368;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        color: #202124;
    }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Portfolio-Wise PPC Metrics Dashboard")
st.caption("Sponsored Products Advertised Product Report — grouped by Portfolio type")

# =================================================================
# Data load
# =================================================================
# Different Amazon report exports use slightly different column names/
# suffixes (e.g. "Spend" vs "Spend - converted"). These are the accepted
# variants, in priority order, for each canonical field we need.
BASE_REQUIRED_COLS = ["Date", "Portfolio name", "Country", "Impressions", "Clicks"]
SPEND_CANDIDATES = ["Spend - converted", "Spend"]
SALES_CANDIDATES = ["7 Day Total Sales - converted", "7 Day Total Sales"]

def resolve_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(f"Missing expected column for {label}: tried {candidates}")

@st.cache_data
def load_data(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    # Normalize column names (some exports have trailing/leading whitespace,
    # e.g. "7 Day Total Sales ")
    df.columns = [str(c).strip() for c in df.columns]

    missing_base = [c for c in BASE_REQUIRED_COLS if c not in df.columns]
    if missing_base:
        raise ValueError(f"Missing expected column(s): {missing_base}")

    spend_col = resolve_column(df, SPEND_CANDIDATES, "Spend")
    sales_col = resolve_column(df, SALES_CANDIDATES, "7 Day Total Sales")

    # Standardize to canonical names used throughout the rest of the app
    df = df.rename(columns={spend_col: "Spend - converted", sales_col: "7 Day Total Sales - converted"})

    df["Date"] = pd.to_datetime(df["Date"])
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

# =================================================================
# Portfolio grouping logic
# =================================================================
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

# =================================================================
# Sidebar controls
# =================================================================
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

# =================================================================
# Base filtered dataset (FBA-classified rows, selected countries)
# =================================================================
base = df[df["Country"].isin(selected_countries)].copy()
base = base[base["Group"].notna()]

if base.empty:
    st.warning("No FBA-prefixed portfolio data found for the selected country/countries.")
    st.stop()

# =================================================================
# Build group metrics table
# =================================================================
def build_group_table(data: pd.DataFrame) -> pd.DataFrame:
    agg = data.groupby("Group").agg(
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
        Spend=("Spend - converted", "sum"),
        Sales=("7 Day Total Sales - converted", "sum"),
    )
    agg = agg.reindex(GROUP_ORDER).fillna(0)

    agg["ACOS %"] = (agg["Spend"] / agg["Sales"].replace(0, np.nan) * 100).round(2)
    agg["ROAS"] = (agg["Sales"] / agg["Spend"].replace(0, np.nan)).round(2)
    agg["CTR %"] = (agg["Clicks"] / agg["Impressions"].replace(0, np.nan) * 100).round(2)
    agg["Spend"] = agg["Spend"].round(2)
    agg["Sales"] = agg["Sales"].round(2)

    return agg[["Impressions", "Clicks", "CTR %", "Spend", "Sales", "ACOS %", "ROAS"]]

table = build_group_table(base)

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

# =================================================================
# KPI cards (TOTAL row)
# =================================================================
st.subheader(f"Overview — {', '.join(selected_countries)}")

t = totals.iloc[0]
kpis = [
    ("IMPRESSIONS", f"{t['Impressions']:,.0f}", COLOR_SPEND),
    ("CLICKS", f"{t['Clicks']:,.0f}", COLOR_SPEND),
    ("SPEND", f"${t['Spend']:,.2f}", COLOR_SPEND),
    ("SALES", f"${t['Sales']:,.2f}", COLOR_SALES),
    ("ACOS", f"{t['ACOS %']:.2f}%", COLOR_ACOS),
    ("ROAS", f"{t['ROAS']:.2f}", COLOR_ROAS),
]
cols = st.columns(len(kpis))
for c, (label, value, color) in zip(cols, kpis):
    c.markdown(
        f"""
        <div class="kpi-card" style="--accent:{color};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# =================================================================
# Group metrics table
# =================================================================
st.subheader("Metrics by Portfolio Group")

def highlight_total(row):
    return ["font-weight:700; background-color:#F1F3F4" if row.name == "TOTAL" else "" for _ in row]

styled = (
    full_table.style
    .format({
        "Impressions": "{:,.0f}",
        "Clicks": "{:,.0f}",
        "CTR %": "{:.2f}%",
        "Spend": "${:,.2f}",
        "Sales": "${:,.2f}",
        "ACOS %": "{:.2f}%",
        "ROAS": "{:.2f}",
    })
    .background_gradient(subset=["ACOS %"], cmap="RdYlGn_r")
    .background_gradient(subset=["ROAS"], cmap="RdYlGn")
    .apply(highlight_total, axis=1)
)
st.dataframe(styled, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Spend by Group**")
    fig = go.Figure(go.Bar(
        x=table.index, y=table["Spend"],
        marker_color=[GROUP_COLORS[g] for g in table.index],
        text=table["Spend"].map(lambda v: f"${v:,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(
        template="plotly_white", height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Spend ($)",
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("**ROAS by Group**")
    fig = go.Figure(go.Bar(
        x=table.index, y=table["ROAS"],
        marker_color=[GROUP_COLORS[g] for g in table.index],
        text=table["ROAS"].map(lambda v: f"{v:.2f}"),
        textposition="outside",
    ))
    fig.update_layout(
        template="plotly_white", height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="ROAS",
    )
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Which portfolios fall into each group?"):
    for g in GROUP_ORDER:
        names = sorted(base[base["Group"] == g]["Portfolio name"].unique())
        st.markdown(f"**{g}** ({len(names)}): {', '.join(names) if names else '—'}")

st.caption(
    "Grouping rule: only portfolios whose name starts with 'FBA' are included. "
    "Names containing 'CBT' → CBT, 'Exclusive' → Exclusive, 'LTSF'/'Ageing' → Ageing, "
    "all remaining FBA-prefixed portfolios → FBA."
)

st.divider()

# =================================================================
# Trend section — group filter
# =================================================================
st.header("📈 Spend vs Sales vs ACOS Trend")

trend_group = st.selectbox(
    "Portfolio group for trend view",
    options=["All groups (combined)"] + GROUP_ORDER,
    index=0,
)

if trend_group == "All groups (combined)":
    trend_df = base.copy()
else:
    trend_df = base[base["Group"] == trend_group].copy()

if trend_df.empty:
    st.info("No data available for this selection.")
    st.stop()

def combo_chart(x, spend, sales, acos, title, x_title, trendline_acos=None):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=x, y=spend, name="Spend", marker_color=COLOR_SPEND, opacity=0.85),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=x, y=sales, name="Sales", marker_color=COLOR_SALES, opacity=0.85),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=acos, name="ACOS %", mode="lines+markers",
            line=dict(color=COLOR_ACOS, width=3),
            marker=dict(size=6),
        ),
        secondary_y=True,
    )
    if trendline_acos is not None:
        fig.add_trace(
            go.Scatter(
                x=x, y=trendline_acos, name="ACOS Trendline", mode="lines",
                line=dict(color=COLOR_TREND, width=2, dash="dash"),
            ),
            secondary_y=True,
        )

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        height=420,
        title=title,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
        hovermode="x unified",
    )
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text="Amount ($)", secondary_y=False)
    fig.update_yaxes(title_text="ACOS (%)", secondary_y=True, showgrid=False)
    return fig

# -----------------------------------------------------------------
# Day-wise trend
# -----------------------------------------------------------------
st.subheader("Day-wise Trend")

daily = (
    trend_df.groupby(trend_df["Date"].dt.date)
    .agg(Spend=("Spend - converted", "sum"), Sales=("7 Day Total Sales - converted", "sum"))
    .reset_index()
    .rename(columns={"Date": "Day"})
    .sort_values("Day")
)
daily["ACOS %"] = (daily["Spend"] / daily["Sales"].replace(0, np.nan) * 100).round(2)

fig_daily = combo_chart(
    x=daily["Day"], spend=daily["Spend"], sales=daily["Sales"], acos=daily["ACOS %"],
    title="Daily Spend vs Sales vs ACOS", x_title="Date",
)
st.plotly_chart(fig_daily, use_container_width=True)

# -----------------------------------------------------------------
# Week-wise trend  (Week 1 = day 1-7 ... Week 5 = day 29 onward)
# -----------------------------------------------------------------
st.subheader("Week-wise Trend")

wk = trend_df.copy()
min_date = wk["Date"].min().normalize()
wk["Day_Number"] = (wk["Date"].dt.normalize() - min_date).dt.days + 1
wk["Week"] = np.minimum(((wk["Day_Number"] - 1) // 7) + 1, 5)
wk["Week"] = "Week " + wk["Week"].astype(int).astype(str)

weekly = (
    wk.groupby("Week")
    .agg(Spend=("Spend - converted", "sum"), Sales=("7 Day Total Sales - converted", "sum"))
    .reset_index()
)
# Ensure correct week ordering (Week 1, Week 2, ... Week 5)
weekly["order"] = weekly["Week"].str.extract(r"(\d+)").astype(int)
weekly = weekly.sort_values("order").drop(columns="order").reset_index(drop=True)
weekly["ACOS %"] = (weekly["Spend"] / weekly["Sales"].replace(0, np.nan) * 100).round(2)

# Linear trendline on ACOS across weeks
if len(weekly) >= 2 and weekly["ACOS %"].notna().sum() >= 2:
    x_idx = np.arange(len(weekly))
    valid = weekly["ACOS %"].notna()
    coeffs = np.polyfit(x_idx[valid], weekly.loc[valid, "ACOS %"], 1)
    trend_vals = np.polyval(coeffs, x_idx)
else:
    trend_vals = None

fig_weekly = combo_chart(
    x=weekly["Week"], spend=weekly["Spend"], sales=weekly["Sales"], acos=weekly["ACOS %"],
    title="Weekly Spend vs Sales vs ACOS (Week 1–4 = 7-day blocks, Week 5 = Day 29+)",
    x_title="Week", trendline_acos=trend_vals,
)
st.plotly_chart(fig_weekly, use_container_width=True)

with st.expander("Weekly breakdown (table)"):
    st.dataframe(
        weekly.style.format({"Spend": "${:,.2f}", "Sales": "${:,.2f}", "ACOS %": "{:.2f}%"}),
        use_container_width=True,
    )

st.caption(
    "Week bucketing: Day 1 = earliest date in the current selection. "
    "Week 1 = Day 1–7, Week 2 = Day 8–14, Week 3 = Day 15–21, Week 4 = Day 22–28, "
    "Week 5 = Day 29 onward (all remaining days)."
)
