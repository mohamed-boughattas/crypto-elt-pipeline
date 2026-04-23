"""Crypto Market Intelligence Dashboard."""

import io

import pendulum
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from streamlit_dashboard.charts import (
    create_candlestick_chart,
    create_rsi_chart,
    create_volatility_chart,
    create_volume_chart,
)
from streamlit_dashboard.config import DEFAULT_DAYS, MA_PERIOD, get_theme_styles, init_page_config
from streamlit_dashboard.data import (
    DataError,
    check_gold_layer_ready,
    get_available_coins,
    get_coin_colors,
    get_market_data,
)
from streamlit_dashboard.indicators import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sma_crossover_signals,
)

init_page_config()
st.markdown(get_theme_styles(), unsafe_allow_html=True)

st.sidebar.header("⚙️ Dashboard Controls")

AVAILABLE_COINS = get_available_coins()
selected_coin = st.sidebar.selectbox(
    "Select Cryptocurrency",
    options=AVAILABLE_COINS,
    index=AVAILABLE_COINS.index("bitcoin") if "bitcoin" in AVAILABLE_COINS else 0,
)

start_date = st.sidebar.date_input(
    "Start Date", pendulum.now("UTC").date() - pendulum.duration(days=DEFAULT_DAYS)
)
end_date = st.sidebar.date_input("End Date", pendulum.now("UTC").date())

if start_date > end_date:
    st.sidebar.error("Start date must be before end date")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("**📊 Technical Indicators**")
show_rsi = st.sidebar.checkbox("Show RSI", value=True)
show_sma_crossover = st.sidebar.checkbox("Show SMA Crossover", value=True)
show_volume_overlay = st.sidebar.checkbox("Show Volume Bars", value=True)
show_bollinger_bands = st.sidebar.checkbox("Show Bollinger Bands", value=True)
show_macd = st.sidebar.checkbox("Show MACD", value=True)

COIN_COLORS = get_coin_colors()
coin_title = selected_coin.title()
logo_char = "₿" if selected_coin == "bitcoin" else selected_coin[0].upper()
logo_color = COIN_COLORS.get(selected_coin, "#888888")

st.markdown(
    f"""
    <div class="header-container">
        <div class="title-with-logo">
            <div class="bitcoin-logo" style="background: linear-gradient(135deg, {logo_color} 0%, #FFA726 100%);">{logo_char}</div>
            <h1 class="dashboard-title">{coin_title} Market Dashboard</h1>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄", help="Clear cache and reload data"):
        st.cache_data.clear()
        st.rerun()

if not check_gold_layer_ready():
    st.stop()

try:
    df = get_market_data(selected_coin, start_date, end_date)
except DataError as e:
    st.error(str(e))
    with st.expander("Need help?"):
        st.markdown("""
        **Quick Start:**
        1. Run `make pipeline` to fetch and process data
        2. Refresh this page

        **Troubleshooting:**
        - Ensure Docker is running (required for PyAirbyte)
        - Check if `data/crypto.duckdb` exists
        """)
    st.stop()

df = df.with_columns(
    [
        pl.col("sma_7")
        .fill_null(pl.col("close_price").rolling_mean(window_size=MA_PERIOD, min_samples=1))
        .alias("MA"),
        pl.when(pl.col("close_price") >= pl.col("open_price"))
        .then(pl.lit("Bullish ▲"))
        .otherwise(pl.lit("Bearish ▼"))
        .alias("Direction"),
        pl.col("close_price").pct_change().alias("daily_return"),
    ]
)

if df.is_empty():
    st.warning("No data available for the selected period")
    st.stop()

if show_sma_crossover:
    df = calculate_sma_crossover_signals(df)

num_days = df.height
min_date = df["trade_date"].min()
max_date = df["trade_date"].max()
st.markdown(f"**Analysis Period:** {min_date} to {max_date} (**{num_days} days**)")
st.caption(f"Last data sync: {pendulum.now('UTC').strftime('%Y-%m-%d %H:%M:%S')}")

latest = df.row(-1, named=True)
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Price", f"${latest['close_price']:,.2f}")

with col2:
    st.metric("📈 24h High", f"${latest['high_price']:,.2f}")

with col3:
    st.metric("📉 24h Low", f"${latest['low_price']:,.2f}")

with col4:
    volume = latest["daily_volume"]
    if volume > 1e9:
        volume_display = f"{volume / 1e9:.2f}B"
    elif volume > 1e6:
        volume_display = f"{volume / 1e6:.0f}M"
    else:
        volume_display = f"{volume:,.0f}" if volume > 0 else "N/A"
    st.metric("📊 Volume", volume_display)

with col5:
    st.metric("🔥 Volatility", f"{latest['volatility_pct']:.2f}%")

    if show_rsi and "rsi" in df.columns:
        rsi_value = latest.get("rsi")
        if rsi_value is not None:
            rsi_status = (
                "Overbought" if rsi_value > 70 else "Oversold" if rsi_value < 30 else "Neutral"
            )
            rsi_color = "#ef4444" if rsi_value > 70 else "#22c55e" if rsi_value < 30 else "#888888"
            st.markdown(
                f"<span style='color:{rsi_color}; font-weight:bold;'>RSI: {rsi_value:.1f} ({rsi_status})</span>",
                unsafe_allow_html=True,
            )

if show_bollinger_bands and "bb_width" in df.columns:
    bb_width_value = latest.get("bb_width")
    if bb_width_value is not None:
        bb_status = (
            "High Volatility"
            if bb_width_value > 10
            else "Low Volatility"
            if bb_width_value < 3
            else "Normal Volatility"
        )
        bb_color = (
            "#ef4444" if bb_width_value > 10 else "#22c55e" if bb_width_value < 3 else "#888888"
        )
        st.markdown(
            f"<span style='color:{bb_color}; font-weight:bold;'>BB Width: {bb_width_value:.2f}% ({bb_status})</span>",
            unsafe_allow_html=True,
        )

st.markdown("---")

st.header("📊 Market Insights")

agg_stats = df.select(
    [
        pl.col("volatility_pct").mean().alias("avg_vol"),
        pl.col("volatility_pct").max().alias("max_vol"),
        pl.col("volatility_pct").min().alias("min_vol"),
        pl.col("close_price").std().alias("price_std"),
    ]
).row(0, named=True)

avg_vol = agg_stats["avg_vol"]
max_drawdown = calculate_max_drawdown(df["close_price"])
sharpe_ratio = calculate_sharpe_ratio(df["daily_return"])

direction_counts = df.group_by("Direction").len()
bull_days = (
    direction_counts.filter(pl.col("Direction").str.contains("Bullish")).select("len").item()
    if direction_counts.height > 0
    else 0
)
bear_days = num_days - bull_days

first_close = df["close_price"].head(1).item()
last_close = df["close_price"].tail(1).item()
period_return = ((last_close - first_close) / first_close) * 100 if first_close > 0 else 0.0

col_left, col_right = st.columns(2)

with col_left:
    trend_color = "#22c55e" if latest["close_price"] > latest["MA"] else "#ef4444"
    trend_text = "BULLISH 📈" if latest["close_price"] > latest["MA"] else "BEARISH 📉"

    crossover_signal = latest.get("crossover_signal", "N/A") if show_sma_crossover else None

    sentiment_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Bullish", "Bearish"],
                values=[bull_days, bear_days],
                marker={"colors": ["#22c55e", "#ef4444"]},
                hole=0.4,
                textinfo="percent",
                textfont={"size": 14, "color": "white"},
                hovertemplate="%{label}: %{value} days<extra></extra>",
            )
        ]
    )
    sentiment_fig.update_layout(
        showlegend=False,
        height=150,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    crossover_html = (
        f"<li>SMA Crossover: <strong>{crossover_signal}</strong></li>" if crossover_signal else ""
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
            {f"<p><strong>SMA Crossover:</strong> {crossover_signal}</p>" if crossover_signal else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**⚖️ Price Direction Split**")
    col_chart, col_text = st.columns([1, 2])
    with col_chart:
        st.plotly_chart(sentiment_fig, width="stretch", config={"displayModeBar": False})
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
    st.markdown(
        f"""
        <div class="analysis-box">
            <h4>📈 Risk Metrics</h4>
            <ul>
                <li>Avg Daily Volatility: <strong>{avg_vol:.2f}%</strong></li>
                <li>Max Drawdown: <strong>{max_drawdown:.2f}%</strong></li>
                <li>Sharpe Ratio: <strong>{sharpe_ratio:.2f}</strong></li>
                <li>Price Std Dev: <strong>${agg_stats["price_std"]:,.2f}</strong></li>
            </ul>
            <p style="margin-top: 10px; font-size: 0.9em; color: #666;">
                💡 Risk Level: <strong>{"High" if avg_vol > 5 else "Moderate" if avg_vol > 2 else "Low"}</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

st.header("📈 OHLC Candlestick Chart")
fig = create_candlestick_chart(
    df=df,
    coin=selected_coin,
    show_bollinger_bands=show_bollinger_bands,
    show_volume=show_volume_overlay,
    show_title=False,
)
st.plotly_chart(fig, width="stretch")

c1, c2 = st.columns(2)
c1.markdown("🟢 **Bullish** (Close > Open)")
c2.markdown("🔴 **Bearish** (Close < Open)")

st.markdown("---")

st.header("📉 Risk & Volume")
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Volatility Trend")
    st.plotly_chart(create_volatility_chart(df), width="stretch")

with col_r:
    st.subheader("Daily Volume")
    st.plotly_chart(create_volume_chart(df), width="stretch")

st.markdown("---")

if show_rsi:
    st.header("📊 RSI Indicator")
    st.plotly_chart(create_rsi_chart(df), width="stretch")

    rsi_col1, rsi_col2, rsi_col3 = st.columns(3)
    rsi_col1.markdown("🟢 **Oversold** (RSI < 30)")
    rsi_col2.markdown("🔴 **Overbought** (RSI > 70)")
    rsi_col3.markdown("⚪ **Neutral** (30-70)")

if show_macd and "macd" in df.columns:
    st.markdown("---")
    st.header("📈 MACD Indicator")

    macd_df = df.filter(
        pl.col("macd").is_not_null()
        & pl.col("macd_signal").is_not_null()
        & pl.col("macd_histogram").is_not_null()
    )

    if not macd_df.is_empty():
        macd_fig = go.Figure()

        macd_fig.add_trace(
            go.Scatter(
                x=macd_df["trade_date"].to_list(),
                y=macd_df["macd"].to_list(),
                mode="lines",
                name="MACD Line",
                line={"color": "#2196F3", "width": 2},
                hovertemplate="MACD: %{y:.4f}<extra></extra>",
            )
        )

        macd_fig.add_trace(
            go.Scatter(
                x=macd_df["trade_date"].to_list(),
                y=macd_df["macd_signal"].to_list(),
                mode="lines",
                name="Signal Line",
                line={"color": "#FF9800", "width": 2},
                hovertemplate="Signal: %{y:.4f}<extra></extra>",
            )
        )

        histogram_vals = macd_df["macd_histogram"].to_list()
        macd_colors = ["#22c55e" if x > 0 else "#ef4444" for x in histogram_vals]
        macd_fig.add_trace(
            go.Bar(
                x=macd_df["trade_date"].to_list(),
                y=histogram_vals,
                name="Histogram",
                marker_color=macd_colors,
                opacity=0.6,
                hovertemplate="Histogram: %{y:.4f}<extra></extra>",
            )
        )

        macd_fig.add_hline(
            y=0, line_dash="dash", line_color="white", opacity=0.5, annotation_text="Zero Line"
        )

        macd_fig.update_layout(
            title="MACD (12, 26, 9)",
            xaxis_title="Date",
            yaxis_title="Value",
            hovermode="x unified",
            height=350,
            template="plotly_dark",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )

        st.plotly_chart(macd_fig, width="stretch")

        macd_col1, macd_col2, macd_col3 = st.columns(3)
        macd_col1.markdown("🔵 **MACD Line** (Fast EMA - Slow EMA)")
        macd_col2.markdown("🟠 **Signal Line** (EMA of MACD)")
        macd_col3.markdown("🟢 **Bullish** / 🔴 **Bearish** Histogram")

        latest_macd = macd_df["macd"].tail(1).item()
        latest_signal = macd_df["macd_signal"].tail(1).item()
        latest_histogram = macd_df["macd_histogram"].tail(1).item()

        st.markdown("**📊 MACD Interpretation:**")
        interpretation_col1, interpretation_col2, interpretation_col3 = st.columns(3)

        with interpretation_col1:
            st.markdown(
                f"{'🟢' if latest_histogram > 0 else '🔴'} **Bullish Momentum**: Histogram = {latest_histogram:.4f}"
            )

        with interpretation_col2:
            st.markdown(
                f"{'🟢' if latest_macd > latest_signal else '🔴'} **MACD {'Above' if latest_macd > latest_signal else 'Below'} Signal**: {latest_macd:.4f} {('>' if latest_macd > latest_signal else '<')} {latest_signal:.4f}"
            )

        with interpretation_col3:
            st.markdown(
                f"{'🟢' if latest_macd > 0 else '🔴'} **MACD {'Positive' if latest_macd > 0 else 'Negative'}**: {latest_macd:.4f}"
            )
    else:
        st.warning("⚠️ Insufficient data for MACD calculation. Need at least 35 days of data.")

st.markdown("---")

st.header("🏆 Period Performance")

perf_stats = df.select(
    [
        pl.col("close_price").max().alias("max_close"),
        pl.col("close_price").min().alias("min_close"),
        pl.col("close_price").mean().alias("avg_close"),
        pl.col("daily_volume").sum().alias("total_volume"),
    ]
).row(0, named=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Period High (Close)", f"${perf_stats['max_close']:,.2f}")
with col2:
    st.metric("Period Low (Close)", f"${perf_stats['min_close']:,.2f}")
with col3:
    st.metric("Avg Price", f"${perf_stats['avg_close']:,.2f}")
with col4:
    total_vol = perf_stats["total_volume"]
    st.metric(
        "Total Volume", f"{total_vol / 1e9:.1f}B" if total_vol > 1e9 else f"{total_vol / 1e6:.0f}M"
    )

st.markdown("---")

st.header("📋 Data Explorer")
with st.expander("📊 View Detailed Time-Series", expanded=False):
    display_cols = [
        pl.col("trade_date"),
        pl.col("open_price"),
        pl.col("high_price"),
        pl.col("low_price"),
        pl.col("close_price"),
        pl.col("daily_change_pct"),
        pl.col("volatility_pct"),
        pl.col("daily_volume"),
        pl.col("Direction"),
    ]
    if show_rsi and "rsi" in df.columns:
        display_cols.append(pl.col("rsi"))
    if show_sma_crossover and "crossover_signal" in df.columns:
        display_cols.append(pl.col("crossover_signal"))

    display_df = df.select(display_cols)

    st.dataframe(
        display_df.to_pandas(),
        width="stretch",
        hide_index=True,
    )

    export_format = st.radio(
        "Export Format",
        ["CSV", "Parquet"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if export_format == "CSV":
        csv = display_df.to_pandas().to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"{selected_coin}_market_data.csv",
            mime="text/csv",
        )
    else:
        buffer = io.BytesIO()
        display_df.write_parquet(buffer)
        parquet_bytes = buffer.getvalue()
        st.download_button(
            label="📥 Download Parquet",
            data=parquet_bytes,
            file_name=f"{selected_coin}_market_data.parquet",
            mime="application/octet-stream",
            help="Parquet format - smaller file size, faster loading, native Polars format",
        )
