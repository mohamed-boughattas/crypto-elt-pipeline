"""
Bitcoin Market Dashboard
A comprehensive analytics dashboard for Bitcoin market data.
Data Pipeline: CoinGecko API → Dagster → dbt → DuckDB → Streamlit
"""

import os
from datetime import datetime

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- CONFIGURATION ---
CACHE_TTL = 3600  # 1 hour
DISPLAY_DAYS = 30  # Query more days to get at least 7 with data
MA_PERIOD = 3  # Shorter MA for limited data
BITCOIN_ORANGE = "#F7931A"

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Bitcoin Market Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CUSTOM CSS ---
st.markdown(
    """
    <style>
    /* Hide sidebar controls */
    [data-testid="collapsedControl"] { display: none; }
    
    .analysis-box {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--background-color);
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #F7931A;
        margin-bottom: 20px;
    }
    .analysis-box h4 { 
        margin-top: 0; 
        color: var(--text-color); 
    }
    .bullish { 
        color: #22c55e; 
        font-weight: bold; 
    }
    .bearish { 
        color: #ef4444; 
        font-weight: bold; 
    }
    
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--background-color);
        padding: 15px;
        border-radius: 8px;
    }
    
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    
    .title-with-logo {
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
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
    
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: 600;
        margin: 0;
        color: var(--text-color);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- DATABASE CONNECTION ---
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Create a cached read-only connection to the DuckDB database.

    Returns:
        duckdb.DuckDBPyConnection: Database connection object

    Raises:
        SystemExit: If connection fails
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    db_path = os.path.join(project_root, "data", "crypto.duckdb")

    if not os.path.exists(db_path):
        st.error(f"❌ Database not found at: {db_path}")
        st.info("💡 Run your dbt models first: `cd dbt_project && dbt run`")
        st.stop()

    try:
        return duckdb.connect(db_path, read_only=True)
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


conn = get_connection()


# --- DATA FETCHING ---
@st.cache_data(ttl=CACHE_TTL)
def get_market_data(days: int = DISPLAY_DAYS) -> pd.DataFrame:
    """
    Fetch Bitcoin OHLCV data from the DuckDB mart layer.

    Args:
        days: Number of days of historical data to fetch

    Returns:
        pd.DataFrame: Market data with OHLCV and volatility metrics

    Raises:
        SystemExit: If query fails or returns no data
    """
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
            st.warning("⚠️ No data available in the database.")
            st.info("💡 Run your data pipeline: Dagster → dbt → DuckDB")
            st.stop()

        return df

    except Exception as e:
        st.error(f"❌ Query failed: {e}")
        st.stop()


# --- HEADER WITH LOGO AND REFRESH BUTTON ---
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

# Refresh button in top right
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄", help="Refresh data"):
        st.cache_data.clear()
        st.rerun()

# --- LOAD AND PROCESS DATA ---
df = get_market_data(DISPLAY_DAYS)

# Calculate technical indicators
df["MA"] = df["close_price"].rolling(window=MA_PERIOD, min_periods=1).mean()
df["Direction"] = df.apply(
    lambda x: "Bullish ▲" if x["close_price"] >= x["open_price"] else "Bearish ▼",
    axis=1,
)
df["daily_change_pct"] = (df["close_price"] - df["open_price"]) / df["open_price"] * 100

# --- DATE RANGE INFO ---
num_days = len(df)
st.markdown(
    f"**Analysis Period:** {df['date_day'].min().strftime('%Y-%m-%d')} to {df['date_day'].max().strftime('%Y-%m-%d')} "
    f"(**{num_days} days**)"
)
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# --- TOP METRICS ---
latest = df.iloc[-1]

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💰 Current Price",
        f"${latest['close_price']:,.2f}",
        help="Latest closing price from most recent trading day",
    )

with col2:
    st.metric(
        "📈 24h High",
        f"${latest['high_price']:,.2f}",
        help="Highest price in the last 24 hours",
    )

with col3:
    st.metric(
        "📉 24h Low",
        f"${latest['low_price']:,.2f}",
        help="Lowest price in the last 24 hours",
    )

with col4:
    if latest["daily_volume"] > 1e9:
        volume_display = f"{latest['daily_volume'] / 1e9:.2f}B"
    elif latest["daily_volume"] > 1e6:
        volume_display = f"{latest['daily_volume'] / 1e6:.0f}M"
    elif latest["daily_volume"] > 0:
        volume_display = f"{latest['daily_volume']:,.0f}"
    else:
        volume_display = "N/A"

    st.metric("📊 Volume", volume_display, help="Total trading volume for the day")

with col5:
    st.metric(
        "🔥 Volatility",
        f"{latest['volatility_pct']:.2f}%",
        help="Daily price swing: (High - Low) / Low",
    )

st.markdown("---")

# --- MARKET ANALYSIS ---
st.header("📊 Market Analysis")

avg_vol = df["volatility_pct"].mean()
bull_days = len(df[df["Direction"].str.contains("Bullish")])
bear_days = len(df) - bull_days
price_change_period = (
    (latest["close_price"] - df.iloc[0]["close_price"])
    / df.iloc[0]["close_price"]
    * 100
)

col_left, col_right = st.columns(2)

with col_left:
    trend_color = "#22c55e" if latest["close_price"] > latest["MA"] else "#ef4444"
    trend_text = "BULLISH 📈" if latest["close_price"] > latest["MA"] else "BEARISH 📉"

    # Create sentiment pie chart
    sentiment_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Bullish", "Bearish"],
                values=[bull_days, bear_days],
                marker=dict(colors=["#22c55e", "#ef4444"]),
                hole=0.4,
                textinfo="percent",
                textfont=dict(size=14, color="white"),
                hovertemplate="%{label}: %{value} days<br>%{percent}<extra></extra>",
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
                <li>{MA_PERIOD}-Day Average: <strong>${latest["MA"]:,.2f}</strong></li>
                <li>Period Return: <strong style="color: {"#22c55e" if price_change_period > 0 else "#ef4444"}">{price_change_period:+.2f}%</strong></li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Add sentiment split with visual
    st.markdown("**⚖️ Market Sentiment Split**")
    col_chart, col_text = st.columns([1, 2])

    with col_chart:
        st.plotly_chart(
            sentiment_fig, use_container_width=True, config={"displayModeBar": False}
        )

    with col_text:
        bull_pct = (bull_days / num_days) * 100
        bear_pct = (bear_days / num_days) * 100
        st.markdown(
            f"""
        <div style="padding: 10px;">
            <p style="margin: 5px 0;"><span class="bullish">🟢 Bullish:</span> <strong>{bull_days} days ({bull_pct:.1f}%)</strong></p>
            <p style="margin: 5px 0;"><span class="bearish">🔴 Bearish:</span> <strong>{bear_days} days ({bear_pct:.1f}%)</strong></p>
        </div>
        """,
            unsafe_allow_html=True,
        )

with col_right:
    st.markdown(
        f"""
        <div class="analysis-box">
            <h4>📈 Risk & Volatility</h4>
            <ul>
                <li>Average Daily Volatility: <strong>{avg_vol:.2f}%</strong></li>
                <li>Maximum Volatility: <strong>{df["volatility_pct"].max():.2f}%</strong></li>
                <li>Minimum Volatility: <strong>{df["volatility_pct"].min():.2f}%</strong></li>
                <li>Standard Deviation: <strong>${df["close_price"].std():,.2f}</strong></li>
            </ul>
            <p style="margin-top: 10px; font-size: 0.9em; color: #666;">
                💡 Average intraday swing of <strong>{avg_vol:.2f}%</strong> indicates {"high" if avg_vol > 5 else "moderate" if avg_vol > 2 else "low"} volatility
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# --- MAIN CANDLESTICK CHART ---
col_header, col_toggle = st.columns([5, 2])

with col_header:
    st.header("📈 Price Chart")

with col_toggle:
    show_ma = st.checkbox(
        f"Show {MA_PERIOD}-Day Moving Average",
        value=True,
        help=f"Toggle {MA_PERIOD}-day moving average line on chart",
    )

fig = go.Figure()

# Candlestick
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

# Moving Average (conditional)
if show_ma:
    fig.add_trace(
        go.Scatter(
            x=df["date_day"],
            y=df["MA"],
            mode="lines",
            name=f"{MA_PERIOD}-Day MA",
            line=dict(color="#F7931A", width=2.5),
            hovertemplate=f"{MA_PERIOD}-Day MA: $%{{y:,.2f}}<extra></extra>",
        )
    )

fig.update_layout(
    height=500,
    template="plotly_white",
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    yaxis_title="Price (USD)",
    xaxis_title="Date",
    margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

st.plotly_chart(fig, use_container_width=True)

# Legend
if show_ma:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🟢 **Bullish Candle** - Close ≥ Open")
    with col2:
        st.markdown("🔴 **Bearish Candle** - Close < Open")
    with col3:
        st.markdown(f"🟠 **{MA_PERIOD}-Day MA** - Trend line")
else:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("🟢 **Bullish Candle** - Close ≥ Open")
    with col2:
        st.markdown("🔴 **Bearish Candle** - Close < Open")

st.markdown("---")

# --- SECONDARY CHARTS ---
st.header("📉 Volatility & Volume Analysis")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Daily Volatility Percentage")
    fig_vol = px.line(
        df,
        x="date_day",
        y="volatility_pct",
        labels={"volatility_pct": "Volatility %", "date_day": "Date"},
    )
    fig_vol.add_hline(
        y=avg_vol,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {avg_vol:.2f}%",
        annotation_position="right",
    )
    fig_vol.update_traces(line_color="#F7931A")
    fig_vol.update_layout(height=350, template="plotly_white", showlegend=False)
    st.plotly_chart(fig_vol, use_container_width=True)

with col_right:
    st.subheader("Daily Trading Volume")
    fig_volume = px.bar(
        df,
        x="date_day",
        y="daily_volume",
        labels={"daily_volume": "Volume", "date_day": "Date"},
    )
    fig_volume.update_traces(marker_color="#1f77b4")
    fig_volume.update_layout(height=350, template="plotly_white", showlegend=False)
    st.plotly_chart(fig_volume, use_container_width=True)

st.markdown("---")

# --- PERFORMANCE SUMMARY ---
st.header("🏆 Performance Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        f"{num_days}-Day High",
        f"${df['close_price'].max():,.2f}",
        help="Highest closing price in the period",
    )

with col2:
    st.metric(
        f"{num_days}-Day Low",
        f"${df['close_price'].min():,.2f}",
        help="Lowest closing price in the period",
    )

with col3:
    st.metric(
        "Average Price",
        f"${df['close_price'].mean():,.2f}",
        help="Mean closing price over the period",
    )

with col4:
    total_volume = df["daily_volume"].sum()
    volume_display = (
        f"{total_volume / 1e9:.1f}B"
        if total_volume > 1e9
        else f"{total_volume / 1e6:.0f}M"
    )
    st.metric("Total Volume", volume_display, help="Cumulative trading volume")

st.markdown("---")

# --- DATA TABLE ---
st.header("📋 Historical Data Explorer")

with st.expander("📊 View OHLC Time-Series Data", expanded=False):
    # Prepare display dataframe
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

    table_df = table_df.sort_values("date_day", ascending=False)
    table_df = table_df.rename(
        columns={
            "date_day": "Date",
            "open_price": "Open",
            "high_price": "High",
            "low_price": "Low",
            "close_price": "Close",
            "daily_change_pct": "Change %",
            "volatility_pct": "Volatility %",
            "daily_volume": "Volume",
            "Direction": "Direction",
        }
    )

    # Apply styling
    def highlight_direction(val):
        if "Bullish" in str(val):
            return "color: #22c55e; font-weight: bold"
        elif "Bearish" in str(val):
            return "color: #ef4444; font-weight: bold"
        return ""

    styled_df = table_df.style.format(
        {
            "Open": "${:,.2f}",
            "High": "${:,.2f}",
            "Low": "${:,.2f}",
            "Close": "${:,.2f}",
            "Change %": "{:+.2f}%",
            "Volatility %": "{:.2f}%",
            "Volume": "{:,.0f}",
        }
    ).apply(lambda x: [highlight_direction(v) for v in x], subset=["Direction"])

    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=400)

# --- DOWNLOAD BUTTON ---
csv = df.to_csv(index=False)
st.download_button(
    label="📥 Download Full Dataset (CSV)",
    data=csv,
    file_name=f"bitcoin_market_data_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
    help="Download all market data as CSV file",
)
