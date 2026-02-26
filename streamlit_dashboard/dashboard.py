"""
Crypto Market Intelligence Dashboard
Tech Stack: CoinGecko -> Dagster -> dbt -> DuckDB -> Polars -> Streamlit

This dashboard uses Polars for high-performance data processing,
consistent with the rest of the pipeline.

Features:
- Single coin analysis with OHLC candlesticks
- RSI technical indicator
- Dark/Light theme toggle
- Advanced risk metrics (Sharpe ratio, Max Drawdown)
"""

from pathlib import Path

import duckdb
import pendulum
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from plotly.subplots import make_subplots

from crypto_elt_pipeline.config import get_config

# --- DASHBOARD PARAMETERS ---
CACHE_TTL = 3600  # Cache data for 1 hour
DEFAULT_DAYS = 30  # Historical lookback period
MA_PERIOD = 7  # Moving Average window (days)
RSI_PERIOD = 14  # RSI calculation period

# Coin branding colors (loaded from centralized config)
COIN_COLORS = get_config().coin_colors

# --- PAGE SETTINGS ---
st.set_page_config(
    page_title="Crypto Market Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- THEME MANAGEMENT ---
def get_theme_styles() -> str:
    """Generate CSS styles for dark theme."""
    return """
    <style>
    /* Dark Theme */
    [data-testid="collapsedControl"] { display: none; }

    .analysis-box {
        background-color: #1e1e2e;
        border: 1px solid #2d2d3d;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #F7931A;
        margin-bottom: 20px;
    }
    .analysis-box h4 { margin-top: 0; color: #e0e0e0; }
    .bullish { color: #22c55e; font-weight: bold; }
    .bearish { color: #ef4444; font-weight: bold; }

    div[data-testid="stMetric"] {
        background-color: #1e1e2e;
        border: 1px solid #2d2d3d;
        padding: 15px;
        border-radius: 8px;
    }

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
    .dashboard-title { font-size: 2.5rem; font-weight: 600; margin: 0; color: #e0e0e0; }

    .rsi-overbought { color: #ef4444; }
    .rsi-oversold { color: #22c55e; }

    /* Custom metric styling */
    .metric-label { color: #888; font-size: 0.9em; }
    .metric-value { color: #e0e0e0; font-size: 1.5em; font-weight: bold; }
    </style>
    """


# --- DATA INFRASTRUCTURE ---
@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Establishes a cached, read-only connection to the DuckDB warehouse."""
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "data" / "crypto.duckdb"

    if not db_path.exists():
        st.error(f"❌ Database not found at: {db_path}")
        st.info("💡 Generate data first: `make pipeline`")
        st.stop()

    try:
        return duckdb.connect(str(db_path), read_only=True)
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


conn = get_connection()


@st.cache_data(ttl=CACHE_TTL)
def get_available_coins() -> list:
    """Fetches list of available coins from the database."""
    try:
        query = "SELECT DISTINCT coin FROM mart.fct_crypto_candlesticks ORDER BY coin"
        df = conn.execute(query).pl()
        return df["coin"].to_list()
    except Exception:
        return ["bitcoin"]  # Fallback


AVAILABLE_COINS = get_available_coins()

# --- SIDEBAR CONTROLS ---
st.sidebar.header("⚙️ Dashboard Controls")

# Apply dark theme styles
st.markdown(get_theme_styles(), unsafe_allow_html=True)

# Coin selection
selected_coin = st.sidebar.selectbox(
    "Select Cryptocurrency",
    options=AVAILABLE_COINS,
    index=AVAILABLE_COINS.index("bitcoin") if "bitcoin" in AVAILABLE_COINS else 0,
)

# Date range selection
start_date = st.sidebar.date_input(
    "Start Date", pendulum.now("UTC").date() - pendulum.duration(days=DEFAULT_DAYS)
)
end_date = st.sidebar.date_input("End Date", pendulum.now("UTC").date())

if start_date > end_date:
    st.sidebar.error("Start date must be before end date")
    st.stop()

# Technical indicators toggles
st.sidebar.markdown("---")
st.sidebar.markdown("**📊 Technical Indicators**")
show_rsi = st.sidebar.checkbox("Show RSI", value=True)
show_sma_crossover = st.sidebar.checkbox("Show SMA Crossover", value=True)
show_volume_overlay = st.sidebar.checkbox("Show Volume Bars", value=True)
show_bollinger_bands = st.sidebar.checkbox("Show Bollinger Bands", value=True)


# --- TECHNICAL INDICATOR FUNCTIONS ---
def calculate_rsi(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
    """Calculate Relative Strength Index (RSI).

    RSI measures the speed and magnitude of recent price changes
    to evaluate overbought or oversold conditions.

    Args:
        df: DataFrame with close_price column
        period: RSI calculation period (default 14)

    Returns:
        DataFrame with rsi column added
    """
    if df.is_empty() or df.height < period:
        return df.with_columns(pl.lit(None).alias("rsi"))

    # Calculate price changes
    df = df.with_columns(pl.col("close_price").diff().alias("price_change"))

    # Separate gains and losses
    df = df.with_columns(
        [
            pl.when(pl.col("price_change") > 0)
            .then(pl.col("price_change"))
            .otherwise(0)
            .alias("gain"),
            pl.when(pl.col("price_change") < 0)
            .then(pl.col("price_change").abs())
            .otherwise(0)
            .alias("loss"),
        ]
    )

    # Calculate average gains and losses using EMA-like approach
    df = df.with_columns(
        [
            pl.col("gain").rolling_mean(window_size=period, min_samples=period).alias("avg_gain"),
            pl.col("loss").rolling_mean(window_size=period, min_samples=period).alias("avg_loss"),
        ]
    )

    # Calculate RS and RSI
    df = df.with_columns(
        [
            pl.when(pl.col("avg_loss") == 0)
            .then(100.0)
            .otherwise(100 - (100 / (1 + pl.col("avg_gain") / pl.col("avg_loss"))))
            .alias("rsi")
        ]
    )

    # Clean up intermediate columns
    return df.drop(["price_change", "gain", "loss", "avg_gain", "avg_loss"])


def calculate_sma_crossover_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate SMA crossover signals (Golden Cross / Death Cross).

    Golden Cross: SMA(7) crosses above SMA(25) - Bullish signal
    Death Cross: SMA(7) crosses below SMA(25) - Bearish signal

    Args:
        df: DataFrame with sma_7 and sma_25 columns

    Returns:
        DataFrame with crossover_signal column added
    """
    df = df.with_columns(
        [
            pl.when(pl.col("sma_7") > pl.col("sma_25"))
            .then(pl.lit("Golden Cross 🟢"))
            .otherwise(pl.lit("Death Cross 🔴"))
            .alias("crossover_signal")
        ]
    )
    return df


def calculate_max_drawdown(prices: pl.Series) -> float:
    """Calculate maximum drawdown percentage.

    Max drawdown measures the largest peak-to-trough decline
    in the value of an investment.

    Args:
        prices: Series of closing prices

    Returns:
        Maximum drawdown as a positive percentage
    """
    if len(prices) < 2:
        return 0.0

    # Calculate running maximum
    running_max = prices.cum_max()
    # Calculate drawdown at each point
    drawdown = (running_max - prices) / running_max * 100
    # Return maximum drawdown
    return drawdown.max()


def calculate_sharpe_ratio(returns: pl.Series, risk_free_rate: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio.

    Sharpe ratio measures risk-adjusted return.

    Args:
        returns: Series of daily returns
        risk_free_rate: Annual risk-free rate (default 0%)

    Returns:
        Annualized Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0

    # Filter out null values
    returns = returns.drop_nulls()
    if len(returns) < 2:
        return 0.0

    # Daily risk-free rate
    daily_rf = risk_free_rate / 252

    # Calculate excess returns
    excess_returns = returns - daily_rf

    # Calculate Sharpe ratio (annualized)
    mean_excess = excess_returns.mean()
    std_returns = excess_returns.std()

    if std_returns == 0:
        return 0.0

    # Annualize (sqrt(252) for daily to annual)
    return float((mean_excess / std_returns) * (252**0.5))


@st.cache_data(ttl=CACHE_TTL)
def get_market_data(coin: str, start: pendulum.Date, end: pendulum.Date) -> pl.DataFrame:
    """Fetches OHLCV and volatility from the dbt mart layer for a specific coin.

    Args:
        coin: Cryptocurrency identifier (e.g., 'bitcoin')
        start: Start date for the analysis period
        end: End date for the analysis period

    Returns:
        Polars DataFrame with OHLCV data and computed metrics

    Raises:
        DataError: If data is unavailable or stale, with user-friendly message.
    """
    try:
        query = """
            SELECT
                trade_date,
                coin,
                open_price,
                high_price,
                low_price,
                close_price,
                daily_volume,
                volatility_pct,
                sma_7,
                sma_25,
                bb_middle,
                bb_upper,
                bb_lower,
                bb_width,
                bb_position
            FROM mart.fct_crypto_candlesticks
            WHERE coin = $1
            AND trade_date >= $2
            AND trade_date <= $3
            ORDER BY trade_date ASC
        """
        df = conn.execute(query, [coin, str(start), str(end)]).pl()

        if df.is_empty():
            raise DataError(
                f"No data available for {coin.upper()} in the selected period. "
                "Please run the pipeline first: `make pipeline`"
            )

        # Check for stale data (no data in last 48 hours)
        latest_date = df["trade_date"].max()
        if latest_date:
            days_since_update = (pendulum.now("UTC").date() - latest_date).days
            if days_since_update > 2:
                st.warning(
                    f"⚠️ Data may be stale. Last update: {latest_date} ({days_since_update} days ago). "
                    "Run `make pipeline` to refresh."
                )

        return df

    except DataError:
        raise  # Re-raise DataError with user-friendly message
    except Exception as e:
        raise DataError(
            f"Unable to load data for {coin.upper()}. "
            "Please check if the pipeline has been run and the database exists."
        ) from e


class DataError(Exception):
    """Custom exception for data-related errors with user-friendly messages."""

    pass


# --- APP HEADER ---
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

# Global manual refresh button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄", help="Clear cache and reload data"):
        st.cache_data.clear()
        st.rerun()

# --- SINGLE COIN ANALYSIS ---
# Get data for the primary selected coin
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

# Add computed columns using Polars expressions
df = df.with_columns(
    [
        # Use SMA from dbt if available, otherwise calculate
        pl.col("sma_7")
        .fill_null(pl.col("close_price").rolling_mean(window_size=MA_PERIOD, min_samples=1))
        .alias("MA"),
        # Direction: Bullish if close >= open, else Bearish
        pl.when(pl.col("close_price") >= pl.col("open_price"))
        .then(pl.lit("Bullish ▲"))
        .otherwise(pl.lit("Bearish ▼"))
        .alias("Direction"),
        # Daily change percentage
        ((pl.col("close_price") - pl.col("open_price")) / pl.col("open_price") * 100).alias(
            "daily_change_pct"
        ),
        # Daily returns for Sharpe ratio
        pl.col("close_price").pct_change().alias("daily_return"),
    ]
)

# Calculate RSI if enabled
if show_rsi:
    df = calculate_rsi(df, RSI_PERIOD)

# Calculate SMA crossover signals if enabled
if show_sma_crossover:
    df = calculate_sma_crossover_signals(df)

# Metadata / Refreshed status
num_days = df.height
min_date = df["trade_date"].min()
max_date = df["trade_date"].max()
st.markdown(f"**Analysis Period:** {min_date} to {max_date} (**{num_days} days**)")
st.caption(f"Last data sync: {pendulum.now('UTC').strftime('%Y-%m-%d %H:%M:%S')}")

# --- KEY PERFORMANCE INDICATORS ---
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

    # RSI indicator in KPI row
if show_rsi and "rsi" in df.columns:
    rsi_value = latest.get("rsi")
    if rsi_value is not None:
        rsi_status = "Overbought" if rsi_value > 70 else "Oversold" if rsi_value < 30 else "Neutral"
        rsi_color = "#ef4444" if rsi_value > 70 else "#22c55e" if rsi_value < 30 else "#888888"
        st.markdown(
            f"<span style='color:{rsi_color}; font-weight:bold;'>RSI: {rsi_value:.1f} ({rsi_status})</span>",
            unsafe_allow_html=True,
        )

# Bollinger Bands indicator in KPI row
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

# --- MARKET ANALYSIS SECTION ---
st.header("📊 Market Insights")

# Calculate aggregate statistics using Polars
agg_stats = df.select(
    [
        pl.col("volatility_pct").mean().alias("avg_vol"),
        pl.col("volatility_pct").max().alias("max_vol"),
        pl.col("volatility_pct").min().alias("min_vol"),
        pl.col("close_price").std().alias("price_std"),
    ]
).row(0, named=True)

avg_vol = agg_stats["avg_vol"]

# Calculate advanced risk metrics
max_drawdown = calculate_max_drawdown(df["close_price"])
sharpe_ratio = calculate_sharpe_ratio(df["daily_return"])

# Count bullish/bearish days using Polars
direction_counts = df.group_by("Direction").len()
bull_days = (
    direction_counts.filter(pl.col("Direction").str.contains("Bullish")).select("len").item()
    if direction_counts.height > 0
    else 0
)
bear_days = num_days - bull_days

# Calculate period return
first_close = df["close_price"].head(1).item()
last_close = df["close_price"].tail(1).item()
period_return = ((last_close - first_close) / first_close) * 100

col_left, col_right = st.columns(2)

with col_left:
    # Trend Analysis
    trend_color = "#22c55e" if latest["close_price"] > latest["MA"] else "#ef4444"
    trend_text = "BULLISH 📈" if latest["close_price"] > latest["MA"] else "BEARISH 📉"

    # SMA Crossover signal
    crossover_signal = latest.get("crossover_signal", "N/A") if show_sma_crossover else None

    # Sentiment Distribution Chart
    text_color = "white"
    sentiment_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Bullish", "Bearish"],
                values=[bull_days, bear_days],
                marker={"colors": ["#22c55e", "#ef4444"]},
                hole=0.4,
                textinfo="percent",
                textfont={"size": 14, "color": text_color},
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
    # Risk Metrics with advanced calculations
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

# --- MAIN OHLC CHART WITH RSI AND VOLUME ---
col_header, col_toggle = st.columns([5, 2])
with col_header:
    st.header("📈 Market Price (OHLC)")
with col_toggle:
    show_ma = st.checkbox(f"Show {MA_PERIOD}-Day MA", value=True)

# Convert to Pandas for Plotly
df_plot = df.to_pandas()

# Determine number of subplots
num_rows = 2 if show_rsi and "rsi" in df.columns else 1
if show_volume_overlay:
    num_rows = 3 if show_rsi else 2

# Create subplot with RSI and Volume
if num_rows > 1:
    row_heights = [0.5, 0.25, 0.25] if num_rows == 3 else [0.7, 0.3]
    subplot_titles = (
        ["Price", "Volume", "RSI"]
        if num_rows == 3
        else ["Price", "RSI"]
        if show_rsi
        else ["Price", "Volume"]
    )

    fig = make_subplots(
        rows=num_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.20,
        row_heights=row_heights[:num_rows],
        subplot_titles=subplot_titles[:num_rows],
    )

    # Candlestick Trace
    fig.add_trace(
        go.Candlestick(
            x=df_plot["trade_date"],
            open=df_plot["open_price"],
            high=df_plot["high_price"],
            low=df_plot["low_price"],
            close=df_plot["close_price"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )

    if show_ma:
        fig.add_trace(
            go.Scatter(
                x=df_plot["trade_date"],
                y=df_plot["MA"],
                mode="lines",
                name="Moving Average",
                line={"color": "#F7931A", "width": 2.5},
            ),
            row=1,
            col=1,
        )

    # Bollinger Bands overlay
    if show_bollinger_bands and "bb_upper" in df_plot.columns and "bb_lower" in df_plot.columns:
        # Upper band
        fig.add_trace(
            go.Scatter(
                x=df_plot["trade_date"],
                y=df_plot["bb_upper"],
                mode="lines",
                name="BB Upper",
                line={"color": "#FF6B6B", "width": 1, "dash": "dot"},
                showlegend=True,
            ),
            row=1,
            col=1,
        )

        # Lower band
        fig.add_trace(
            go.Scatter(
                x=df_plot["trade_date"],
                y=df_plot["bb_lower"],
                mode="lines",
                name="BB Lower",
                line={"color": "#FF6B6B", "width": 1, "dash": "dot"},
                showlegend=True,
                fill="tonexty",  # Fill between upper and lower bands
                fillcolor="rgba(255, 107, 107, 0.1)",  # Light red fill
            ),
            row=1,
            col=1,
        )

        # Middle band (20-day SMA)
        if "bb_middle" in df_plot.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_plot["trade_date"],
                    y=df_plot["bb_middle"],
                    mode="lines",
                    name="BB Middle (20 SMA)",
                    line={"color": "#4ECDC4", "width": 2},
                    showlegend=True,
                ),
                row=1,
                col=1,
            )

    current_row = 2

    # Volume bars
    if show_volume_overlay:
        colors = [
            "#22c55e" if c >= o else "#ef4444"
            for c, o in zip(df_plot["close_price"], df_plot["open_price"], strict=True)
        ]
        fig.add_trace(
            go.Bar(
                x=df_plot["trade_date"],
                y=df_plot["daily_volume"],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
            ),
            row=current_row,
            col=1,
        )
        fig.update_yaxes(title_text="Volume", row=current_row, col=1)
        current_row = 3

    # RSI Trace
    if show_rsi and "rsi" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot["trade_date"],
                y=df_plot["rsi"],
                mode="lines",
                name="RSI",
                line={"color": "#636EFA", "width": 2},
            ),
            row=current_row,
            col=1,
        )

        # RSI overbought/oversold lines
        fig.add_hline(
            y=70,
            line_dash="dash",
            line_color="#ef4444",
            row=current_row,
            col=1,
            annotation_text="Overbought",
        )
        fig.add_hline(
            y=30,
            line_dash="dash",
            line_color="#22c55e",
            row=current_row,
            col=1,
            annotation_text="Oversold",
        )
        fig.add_hline(y=50, line_dash="dot", line_color="#888888", row=current_row, col=1)
        fig.update_yaxes(title_text="RSI", row=current_row, col=1)

    fig.update_layout(
        height=700 if num_rows == 3 else 600,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    fig.update_yaxes(title_text="USD", row=1, col=1)

else:
    # Original chart without RSI or Volume
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df_plot["trade_date"],
            open=df_plot["open_price"],
            high=df_plot["high_price"],
            low=df_plot["low_price"],
            close=df_plot["close_price"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )
    )

    if show_ma:
        fig.add_trace(
            go.Scatter(
                x=df_plot["trade_date"],
                y=df_plot["MA"],
                mode="lines",
                name="Moving Average",
                line={"color": "#F7931A", "width": 2.5},
            )
        )

    fig.update_layout(
        height=500,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        yaxis_title="USD",
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

st.plotly_chart(fig, width="stretch")

# Legend Helper
c1, c2, c3, c4 = st.columns(4)
c1.markdown("🟢 **Bullish** (Close > Open)")
c2.markdown("🔴 **Bearish** (Close < Open)")
if show_ma:
    c3.markdown("🟠 **Trend line**")
if show_bollinger_bands:
    c4.markdown("🔵 **Bollinger Bands**")

st.markdown("---")

# --- SECONDARY ANALYTICS ---
st.header("📉 Risk & Volume")
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Volatility Trend")
    fig_vol = px.line(df_plot, x="trade_date", y="volatility_pct")
    fig_vol.add_hline(
        y=avg_vol,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {avg_vol:.2f}%",
    )
    fig_vol.update_traces(line_color="#F7931A")
    fig_vol.update_layout(
        height=350,
        template="plotly_dark",
        showlegend=False,
    )
    st.plotly_chart(fig_vol, width="stretch")

with col_r:
    st.subheader("Daily Volume")
    fig_volume = px.bar(df_plot, x="trade_date", y="daily_volume")
    fig_volume.update_traces(marker_color="#1f77b4")
    fig_volume.update_layout(
        height=350,
        template="plotly_dark",
        showlegend=False,
    )
    st.plotly_chart(fig_volume, width="stretch")

st.markdown("---")

# --- PERFORMANCE WRAP-UP ---
st.header("🏆 Period Performance")

# Calculate stats using Polars
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
        "Total Volume",
        f"{total_vol / 1e9:.1f}B" if total_vol > 1e9 else f"{total_vol / 1e6:.0f}M",
    )

st.markdown("---")

# --- RAW DATA ACCESS ---
st.header("📋 Data Explorer")
with st.expander("📊 View Detailed Time-Series", expanded=False):
    # Select and rename columns using Polars
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

    table_df = df.select(display_cols).sort("trade_date", descending=True)

    # Rename columns for display
    rename_map = {
        "trade_date": "Date",
        "open_price": "Open",
        "high_price": "High",
        "low_price": "Low",
        "close_price": "Close",
        "daily_change_pct": "Change %",
        "volatility_pct": "Vol %",
        "daily_volume": "Volume",
        "Direction": "Dir",
        "rsi": "RSI",
        "crossover_signal": "Signal",
    }
    table_df = table_df.rename({k: v for k, v in rename_map.items() if k in table_df.columns})

    # Convert to Pandas for Streamlit display with styling
    table_pd = table_df.to_pandas()

    def style_dir(val):
        color = "#22c55e" if "Bullish" in str(val) else "#ef4444"
        return f"color: {color}; font-weight: bold"

    format_dict = {
        "Open": "${:,.2f}",
        "High": "${:,.2f}",
        "Low": "${:,.2f}",
        "Close": "${:,.2f}",
        "Change %": "{:+.2f}%",
        "Vol %": "{:.2f}%",
        "Volume": "{:,.0f}",
    }
    if "RSI" in table_pd.columns:
        format_dict["RSI"] = "{:.1f}"

    styled_table = table_pd.style.format(format_dict)
    if "Dir" in table_pd.columns:
        styled_table = styled_table.map(style_dir, subset=["Dir"])

    st.dataframe(
        styled_table,
        width="stretch",
        hide_index=True,
        height=400,
    )

# CSV Export functionality
st.download_button(
    label="📥 Export to CSV",
    data=df.write_csv(),
    file_name=f"{selected_coin}_data_{pendulum.now('UTC').strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
