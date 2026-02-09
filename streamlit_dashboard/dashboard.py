"""
Bitcoin Market Intelligence Dashboard
Tech Stack: CoinGecko -> Dagster -> dbt -> DuckDB -> Streamlit
"""

import os
from datetime import datetime

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- DASHBOARD PARAMETERS ---
CACHE_TTL = 3600  # Cache data for 1 hour
DISPLAY_DAYS = 30  # Historical lookback period
MA_PERIOD = 3  # Moving Average window (days)
BITCOIN_ORANGE = "#F7931A"

# --- PAGE SETTINGS ---
st.set_page_config(
    page_title="Bitcoin Market Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- UI STYLING ---
st.markdown(
    """
    <style>
    /* Hide default sidebar controls */
    [data-testid="collapsedControl"] { display: none; }
    
    /* Analysis card styling */
    .analysis-box {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--background-color);
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #F7931A;
        margin-bottom: 20px;
    }
    .analysis-box h4 { margin-top: 0; color: var(--text-color); }
    .bullish { color: #22c55e; font-weight: bold; }
    .bearish { color: #ef4444; font-weight: bold; }
    
    /* Metric card backgrounds */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--background-color);
        padding: 15px;
        border-radius: 8px;
    }
    
    /* Header layout */
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    .title-with-logo { display: flex; align-items: center; gap: 15px; }
    .bitcoin-logo {
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #F7931A 0%, #FFA726 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: bold;
        color: white;
        box-shadow: 0 4px 6px rgba(247, 147, 26, 0.3);
        flex-shrink: 0;
    }
    .dashboard-title { font-size: 2.5rem; font-weight: 600; margin: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- DATA INFRASTRUCTURE ---
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Establishes a cached, read-only connection to the DuckDB warehouse."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    db_path = os.path.join(project_root, "data", "crypto.duckdb")

    if not os.path.exists(db_path):
        st.error(f"❌ Database not found at: {db_path}")
        st.info("💡 Generate data first: `cd dbt_project && dbt run`")
        st.stop()

    try:
        return duckdb.connect(db_path, read_only=True)
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


conn = get_connection()


@st.cache_data(ttl=CACHE_TTL)
def get_market_data(days: int = DISPLAY_DAYS) -> pd.DataFrame:
    """Fetches Bitcoin OHLCV and volatility from the dbt mart layer."""
    try:
        query = f"""
            SELECT 
                date_day,
                CAST(open_price AS FLOAT) as open_price,
                CAST(high_price AS FLOAT) as high_price,
                CAST(low_price AS FLOAT) as low_price,
                CAST(close_price AS FLOAT) as close_price,
                CAST(daily_volume AS FLOAT) as daily_volume,
                CAST(volatility_pct AS FLOAT) as volatility_pct
            FROM mart.fct_daily_btc_candlesticks
            WHERE date_day >= current_date - interval '{days} days' 
            ORDER BY date_day ASC
        """
        df = conn.execute(query).df()

        if df.empty:
            st.warning("⚠️ No data found in mart.fct_daily_btc_candlesticks.")
            st.info("💡 Ensure your Dagster pipeline has materialized the assets.")
            st.stop()

        return df

    except Exception as e:
        st.error(f"❌ Query execution failed: {e}")
        st.stop()


# --- APP HEADER ---
st.markdown(
    """
    <div class="header-container">
        <div class="title-with-logo">
            <div class="bitcoin-logo">₿</div>
            <h1 class="dashboard-title">Bitcoin Market Dashboard</h1>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Global manual refresh button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄", help="Clear cache and reload data"):
        st.cache_data.clear()
        st.rerun()

# --- DATA PROCESSING ---
df = get_market_data(DISPLAY_DAYS)

# Compute Technical Indicators
df["MA"] = df["close_price"].rolling(window=MA_PERIOD, min_periods=1).mean()
df["Direction"] = df.apply(
    lambda x: "Bullish ▲" if x["close_price"] >= x["open_price"] else "Bearish ▼",
    axis=1,
)
df["daily_change_pct"] = (df["close_price"] - df["open_price"]) / df["open_price"] * 100

# Metadata / Refreshed status
num_days = len(df)
st.markdown(
    f"**Analysis Period:** {df['date_day'].min().strftime('%Y-%m-%d')} to {df['date_day'].max().strftime('%Y-%m-%d')} "
    f"(**{num_days} days**)"
)
st.caption(f"Last data sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- KEY PERFORMANCE INDICATORS ---
latest = df.iloc[-1]
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Price", f"${latest['close_price']:,.2f}")

with col2:
    st.metric("📈 24h High", f"${latest['high_price']:,.2f}")

with col3:
    st.metric("📉 24h Low", f"${latest['low_price']:,.2f}")

with col4:
    # Human-readable volume formatting
    if latest["daily_volume"] > 1e9:
        volume_display = f"{latest['daily_volume'] / 1e9:.2f}B"
    elif latest["daily_volume"] > 1e6:
        volume_display = f"{latest['daily_volume'] / 1e6:.0f}M"
    else:
        volume_display = (
            f"{latest['daily_volume']:,.0f}" if latest["daily_volume"] > 0 else "N/A"
        )
    st.metric("📊 Volume", volume_display)

with col5:
    st.metric("🔥 Volatility", f"{latest['volatility_pct']:.2f}%")

st.markdown("---")

# --- MARKET ANALYSIS SECTION ---
st.header("📊 Market Insights")

avg_vol = df["volatility_pct"].mean()
bull_days = len(df[df["Direction"].str.contains("Bullish")])
bear_days = len(df) - bull_days
period_return = (
    (latest["close_price"] - df.iloc[0]["close_price"]) / df.iloc[0]["close_price"]
) * 100

col_left, col_right = st.columns(2)

with col_left:
    # Trend Analysis
    trend_color = "#22c55e" if latest["close_price"] > latest["MA"] else "#ef4444"
    trend_text = "BULLISH 📈" if latest["close_price"] > latest["MA"] else "BEARISH 📉"

    # Sentiment Distribution Chart
    sentiment_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Bullish", "Bearish"],
                values=[bull_days, bear_days],
                marker=dict(colors=["#22c55e", "#ef4444"]),
                hole=0.4,
                textinfo="percent",
                textfont=dict(size=14, color="white"),
                hovertemplate="%{label}: %{value} days<extra></extra>",
            )
        ]
    )
    sentiment_fig.update_layout(
        showlegend=False,
        height=150,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.markdown(
        f"""
        <div class="analysis-box">
            <h4>🎯 Trend & Momentum</h4>
            <p><strong>Signal ({MA_PERIOD}-Day MA):</strong> <span style="color: {trend_color}; font-weight: bold">{trend_text}</span></p>
            <ul>
                <li>Current Price: <strong>${latest["close_price"]:,.2f}</strong></li>
                <li>Moving Average: <strong>${latest["MA"]:,.2f}</strong></li>
                <li>Period Return: <strong style="color: {"#22c55e" if period_return > 0 else "#ef4444"}">{period_return:+.2f}%</strong></li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**⚖️ Price Direction Split**")
    col_chart, col_text = st.columns([1, 2])
    with col_chart:
        st.plotly_chart(
            sentiment_fig, use_container_width=True, config={"displayModeBar": False}
        )
    with col_text:
        st.markdown(
            f"""
            <div style="padding: 10px;">
                <p><span class="bullish">🟢 Bullish Days:</span> <strong>{bull_days} ({(bull_days / num_days) * 100:.1f}%)</strong></p>
                <p><span class="bearish">🔴 Bearish Days:</span> <strong>{bear_days} ({(bear_days / num_days) * 100:.1f}%)</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

with col_right:
    # Volatility Risk Stats
    st.markdown(
        f"""
        <div class="analysis-box">
            <h4>📈 Risk Metrics</h4>
            <ul>
                <li>Avg Daily Volatility: <strong>{avg_vol:.2f}%</strong></li>
                <li>Max Period Volatility: <strong>{df["volatility_pct"].max():.2f}%</strong></li>
                <li>Min Period Volatility: <strong>{df["volatility_pct"].min():.2f}%</strong></li>
                <li>Price Std Dev: <strong>${df["close_price"].std():,.2f}</strong></li>
            </ul>
            <p style="margin-top: 10px; font-size: 0.9em; color: #666;">
                💡 Swing intensity: <strong>{"High" if avg_vol > 5 else "Moderate" if avg_vol > 2 else "Low"}</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# --- MAIN OHLC CHART ---
col_header, col_toggle = st.columns([5, 2])
with col_header:
    st.header("📈 Market Price (OHLC)")
with col_toggle:
    show_ma = st.checkbox(f"Show {MA_PERIOD}-Day MA", value=True)

fig = go.Figure()
# Candlestick Trace
fig.add_trace(
    go.Candlestick(
        x=df["date_day"],
        open=df["open_price"],
        high=df["high_price"],
        low=df["low_price"],
        close=df["close_price"],
        name="OHLC",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    )
)

if show_ma:
    fig.add_trace(
        go.Scatter(
            x=df["date_day"],
            y=df["MA"],
            mode="lines",
            name="Moving Average",
            line=dict(color="#F7931A", width=2.5),
        )
    )

fig.update_layout(
    height=500,
    template="plotly_white",
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    yaxis_title="USD",
    margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

# Legend Helper
c1, c2, c3 = st.columns(3)
c1.markdown("🟢 **Bullish** (Close > Open)")
c2.markdown("🔴 **Bearish** (Close < Open)")
if show_ma:
    c3.markdown("🟠 **Trend line**")

st.markdown("---")

# --- SECONDARY ANALYTICS ---
st.header("📉 Risk & Volume")
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Volatility Trend")
    fig_vol = px.line(df, x="date_day", y="volatility_pct")
    fig_vol.add_hline(
        y=avg_vol,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {avg_vol:.2f}%",
    )
    fig_vol.update_traces(line_color="#F7931A")
    fig_vol.update_layout(height=350, template="plotly_white", showlegend=False)
    st.plotly_chart(fig_vol, use_container_width=True)

with col_r:
    st.subheader("Daily Volume")
    fig_volume = px.bar(df, x="date_day", y="daily_volume")
    fig_volume.update_traces(marker_color="#1f77b4")
    fig_volume.update_layout(height=350, template="plotly_white", showlegend=False)
    st.plotly_chart(fig_volume, use_container_width=True)

st.markdown("---")

# --- PERFORMANCE WRAP-UP ---
st.header("🏆 Period Performance")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Period High (Close)", f"${df['close_price'].max():,.2f}")
with col2:
    st.metric("Period Low (Close)", f"${df['close_price'].min():,.2f}")
with col3:
    st.metric("Avg Price", f"${df['close_price'].mean():,.2f}")
with col4:
    total_vol = df["daily_volume"].sum()
    st.metric(
        "Total Volume",
        f"{total_vol / 1e9:.1f}B" if total_vol > 1e9 else f"{total_vol / 1e6:.0f}M",
    )

st.markdown("---")

# --- RAW DATA ACCESS ---
st.header("📋 Data Explorer")
with st.expander("📊 View Detailed Time-Series", expanded=False):
    table_df = df[
        [
            "date_day",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "daily_change_pct",
            "volatility_pct",
            "daily_volume",
            "Direction",
        ]
    ].copy()
    table_df = table_df.sort_values("date_day", ascending=False).rename(
        columns={
            "date_day": "Date",
            "open_price": "Open",
            "high_price": "High",
            "low_price": "Low",
            "close_price": "Close",
            "daily_change_pct": "Change %",
            "volatility_pct": "Vol %",
            "daily_volume": "Volume",
            "Direction": "Dir",
        }
    )

    def style_dir(val):
        color = "#22c55e" if "Bullish" in str(val) else "#ef4444"
        return f"color: {color}; font-weight: bold"

    st.dataframe(
        table_df.style.format(
            {
                "Open": "${:,.2f}",
                "High": "${:,.2f}",
                "Low": "${:,.2f}",
                "Close": "${:,.2f}",
                "Change %": "{:+.2f}%",
                "Vol %": "{:.2f}%",
                "Volume": "{:,.0f}",
            }
        ).applymap(style_dir, subset=["Dir"]),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

# CSV Export functionality
st.download_button(
    label="📥 Export to CSV",
    data=df.to_csv(index=False),
    file_name=f"btc_data_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
