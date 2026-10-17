"""NYC Listings Explorer — responsive, interactive single-page dashboard.

Run:
    pip install -r requirements.txt
    streamlit run listings_dashboard.py

Place listings_conservative_working_copy.csv beside this script or upload a CSV.
The dashboard does not modify source data or impute missing values.
"""
from pathlib import Path
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="NYC Listings | Data Snapshot",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Compact, responsive styling ----------
st.markdown(
    """
    <style>
      .block-container {max-width: 1400px; padding-top: 1.15rem; padding-bottom: 2.2rem;}
      h1 {letter-spacing: -0.045em; line-height: 1.08; margin-bottom: .25rem;}
      h2, h3 {letter-spacing: -0.025em;}
      .subtitle {color: #687386; margin: .2rem 0 1.1rem 0; font-size: 1rem;}
      .takeaway {background: #f4f7fb; border-left: 3px solid #64748b; padding: .65rem .8rem;
                 border-radius: 0 8px 8px 0; margin: .25rem 0 .65rem 0; color: #283548; font-size: .93rem;}
      .fineprint {color: #64748b; font-size: .82rem; line-height: 1.45;}
      [data-testid="stMetric"] {border: 1px solid #e4e9f1; padding: 12px 14px; border-radius: 12px; background: #fbfcfe;}
      [data-testid="stMetricLabel"] {color: #526174;}
      div[data-testid="stPlotlyChart"] {width: 100%;}
      @media (max-width: 700px) {
        .block-container {padding-left: 1rem; padding-right: 1rem; padding-top: .8rem;}
        h1 {font-size: 2rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner="Loading listings…")
def load_data(file_bytes: bytes) -> pd.DataFrame:
    # Keep IDs as text so large identifiers cannot lose precision.
    df = pd.read_csv(
        BytesIO(file_bytes),
        dtype={"id": "string", "host_id": "string", "host_profile_id": "string"},
        keep_default_na=True,
    )
    if "last_review" in df.columns:
        df["last_review"] = pd.to_datetime(df["last_review"], errors="coerce")
    for col in [
        "latitude", "longitude", "price", "minimum_nights", "number_of_reviews",
        "reviews_per_month", "calculated_host_listings_count", "availability_365",
        "number_of_reviews_ltm",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# ---------- Headline and data selection ----------
st.title("NYC Listings: patterns at a glance")
st.markdown(
    '<p class="subtitle">A focused view of listing activity, neighbourhood concentration, location, and unusual price–review combinations.</p>',
    unsafe_allow_html=True,
)

with st.expander("Filters & data source", expanded=True):
    uploaded = st.file_uploader("Upload listings CSV", type=["csv"], label_visibility="visible")
    default_path = Path(__file__).with_name("listings_conservative_working_copy.csv")
    if uploaded is not None:
        df = load_data(uploaded.getvalue())
        st.caption(f"Data source: {uploaded.name}")
    elif default_path.exists():
        df = load_data(default_path.read_bytes())
        st.caption(f"Data source: {default_path.name}")
    else:
        st.warning("Upload listings_conservative_working_copy.csv to begin.")
        st.stop()

    required = ["room_type", "neighbourhood", "price", "last_review"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error("Required columns not found: " + ", ".join(missing))
        st.stop()

    f1, f2, f3 = st.columns([1, 1.35, 1.5])
    room_values = sorted(df["room_type"].dropna().astype(str).unique().tolist())
    neighbourhood_values = sorted(df["neighbourhood"].dropna().astype(str).unique().tolist())
    with f1:
        selected_rooms = st.multiselect("Room type", room_values, default=room_values)
    with f2:
        selected_neighbourhoods = st.multiselect(
            "Neighbourhood", neighbourhood_values, default=neighbourhood_values
        )
    with f3:
        dates = df["last_review"].dropna()
        if not dates.empty:
            min_date, max_date = dates.min().date(), dates.max().date()
            selected_dates = st.date_input(
                "Last-review date range",
                value=(min_date, max_date), min_value=min_date, max_value=max_date,
            )
        else:
            selected_dates = None

# Apply the date range consistently across the dashboard. Undated listings are excluded.
filtered = df.copy()
filtered = filtered[filtered["room_type"].astype("string").isin(selected_rooms)]
filtered = filtered[filtered["neighbourhood"].astype("string").isin(selected_neighbourhoods)]
if selected_dates and isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered = filtered[
        filtered["last_review"].notna()
        & (filtered["last_review"].dt.date >= start_date)
        & (filtered["last_review"].dt.date <= end_date)
    ]

# ---------- KPI strip ----------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Listings in view", f"{len(filtered):,}")
valid_price = filtered["price"].dropna()
k2.metric("Median listed price", f"{valid_price.median():,.0f}" if not valid_price.empty else "—")
valid_nights = filtered["minimum_nights"].dropna() if "minimum_nights" in filtered else pd.Series(dtype=float)
k3.metric("Median minimum stay", f"{valid_nights.median():,.0f} nights" if not valid_nights.empty else "—")
valid_rate = filtered["reviews_per_month"].dropna() if "reviews_per_month" in filtered else pd.Series(dtype=float)
k4.metric("Median reviews / month", f"{valid_rate.median():.2f}" if not valid_rate.empty else "—")

st.markdown(
    '<p class="fineprint">Viewer note: the date filter excludes listings without a recorded last-review date. Missing prices and review rates are omitted only from charts that need them; the map omits invalid coordinates. No minimum neighbourhood/month sample-size cutoff is applied. Price currency is not specified in the source.</p>',
    unsafe_allow_html=True,
)
st.divider()

# Shared plotly settings: responsive charts and interactive hover tooltips.
common_layout = dict(template="plotly_white", margin=dict(l=8, r=8, t=18, b=8), font=dict(size=12))

# ---------- 1. Monthly trend ----------
st.subheader("1 · Monthly trend")
trend = filtered.dropna(subset=["last_review"]).copy()
if not trend.empty:
    trend["review_month"] = trend["last_review"].dt.to_period("M").dt.to_timestamp()
    monthly = trend.groupby("review_month", as_index=False).size().rename(columns={"size": "listings"})
    monthly = monthly.sort_values("review_month")
    fig = px.line(
        monthly, x="review_month", y="listings", markers=True,
        labels={"review_month": "Month of last review", "listings": "Listings"},
        custom_data=["review_month", "listings"],
    )
    fig.update_traces(hovertemplate="Month: %{x|%b %Y}<br>Listings: %{y:,}<extra></extra>", line=dict(width=3))
    fig.update_layout(**common_layout, height=330, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False})
    peak = monthly.loc[monthly["listings"].idxmax()]
    st.markdown(
        f'<div class="takeaway"><b>Takeaway:</b> The busiest last-review month in this view is {peak["review_month"].strftime("%B %Y")} ({int(peak["listings"]):,} listings).</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{len(trend):,} listings with a recorded last-review date. This counts listings by their last-review month, not every review submitted in that month.")
else:
    st.info("No dated listings match these filters.")
st.divider()

# ---------- 2. Top neighbourhoods ----------
st.subheader("2 · Top neighbourhoods")
top_n = (
    filtered.groupby("neighbourhood", dropna=True).size().sort_values(ascending=False)
    .head(10).rename("listings").reset_index().sort_values("listings", ascending=True)
)
if not top_n.empty:
    fig = px.bar(
        top_n, x="listings", y="neighbourhood", orientation="h",
        labels={"listings": "Listings", "neighbourhood": "Neighbourhood"},
        text="listings", hover_data={"listings": ":,", "neighbourhood": True},
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False, hovertemplate="%{y}<br>Listings: %{x:,}<extra></extra>")
    fig.update_layout(**common_layout, height=max(320, 32 * len(top_n) + 70), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False})
    top = top_n.iloc[-1]
    share = 100 * int(top["listings"]) / len(filtered) if len(filtered) else 0
    st.markdown(
        f'<div class="takeaway"><b>Takeaway:</b> {top["neighbourhood"]} leads this filtered view with {int(top["listings"]):,} listings ({share:.1f}% of listings in view).</div>',
        unsafe_allow_html=True,
    )
    st.caption("Top 10 neighbourhoods by listing count; hover a bar for its exact count.")
else:
    st.info("No neighbourhood records match these filters.")
st.divider()

# ---------- 3. Geographic distribution ----------
st.subheader("3 · Geographic distribution")
coords = filtered.dropna(subset=["latitude", "longitude"]).copy()
coords = coords[coords["latitude"].between(-90, 90) & coords["longitude"].between(-180, 180)]
if not coords.empty:
    hover_cols = [c for c in ["room_type", "neighbourhood", "price", "number_of_reviews"] if c in coords.columns]
    fig = px.scatter_mapbox(
        coords, lat="latitude", lon="longitude", color="room_type",
        hover_name="name" if "name" in coords.columns else None,
        hover_data=hover_cols, zoom=9, height=440, mapbox_style="open-street-map",
        labels={"room_type": "Room type", "price": "Listed price", "number_of_reviews": "Reviews"},
    )
    fig.update_traces(marker={"size": 7, "opacity": 0.72})
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title_text="Room type")
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False, "scrollZoom": False})
    pct = 100 * len(coords) / len(filtered) if len(filtered) else 0
    st.markdown(
        f'<div class="takeaway"><b>Takeaway:</b> {pct:.1f}% of listings in this view have valid coordinates and appear on the map; use hover to inspect individual listings.</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Mapped {len(coords):,} listings with valid latitude/longitude. Point density reflects listings in this dataset, not population density.")
else:
    st.info("No valid coordinates match these filters.")
st.divider()

# ---------- 4. Surprise chart ----------
st.subheader("4 · Surprise chart")
st.markdown("<p class='subtitle'>Price versus review activity — look for unusual combinations to investigate, not automatic data errors.</p>", unsafe_allow_html=True)
scatter = filtered.dropna(subset=["price", "reviews_per_month"]).copy()
scatter = scatter[(scatter["price"] > 0) & (scatter["reviews_per_month"] >= 0)]
if not scatter.empty:
    hover_cols = [c for c in ["neighbourhood", "room_type", "minimum_nights", "number_of_reviews"] if c in scatter.columns]
    fig = px.scatter(
        scatter, x="price", y="reviews_per_month", color="room_type",
        hover_name="name" if "name" in scatter.columns else None,
        hover_data=hover_cols,
        labels={"price": "Listed price (currency unspecified)", "reviews_per_month": "Reviews per month", "room_type": "Room type"},
        opacity=0.68,
    )
    fig.update_traces(marker={"size": 8}, hovertemplate="%{hovertext}<br>Price: %{x:,.0f}<br>Reviews/month: %{y:.2f}<extra></extra>")
    fig.update_layout(**common_layout, height=430, legend_title_text="Room type")
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False})
    unusual = scatter.loc[scatter["reviews_per_month"].idxmax()]
    listing_name = str(unusual.get("name", "Listing"))
    st.markdown(
        f'<div class="takeaway"><b>Takeaway:</b> The highest recorded review rate in this view is {unusual["reviews_per_month"]:.2f} reviews/month (listed price {unusual["price"]:,.0f}); verify context before treating it as an anomaly.</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{len(scatter):,} listings shown; records need both a positive listed price and a nonnegative reviews/month value. Hover points for listing details.")
else:
    st.info("No records with both a positive price and a nonnegative review rate match these filters.")

st.markdown("---")
st.markdown(
    '<p class="fineprint">Method: filters apply to all four charts and KPI cards. Missing values are not filled. Extreme values remain visible where they meet chart requirements; they are prompts for review, not proof of an error. The original CSV is not changed.</p>',
    unsafe_allow_html=True,
)
