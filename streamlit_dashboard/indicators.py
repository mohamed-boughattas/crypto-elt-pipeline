"""Technical indicator calculations for cryptocurrency analysis.

This module provides functions for calculating various technical indicators
including RSI, SMA crossovers, and risk metrics.
"""

import polars as pl
import streamlit as st


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

    # Calculate average gains and losses using Wilder's smoothing method
    # This uses exponential moving average with alpha = 1/period
    def wilder_smoothing(series: pl.Series, period: int) -> list[float]:
        """Apply Wilder's smoothing (modified EMA) to a series."""
        values = series.to_list()
        if not values:
            return []

        alpha = 1 / period
        result = [values[0]] if values else []

        for i in range(1, len(values)):
            smoothed = alpha * values[i] + (1 - alpha) * result[-1]
            result.append(smoothed)

        return result

    # Apply Wilder's smoothing
    gain_values = wilder_smoothing(df["gain"], period)
    loss_values = wilder_smoothing(df["loss"], period)

    df = df.with_columns(
        [
            pl.Series(name="avg_gain", values=gain_values),
            pl.Series(name="avg_loss", values=loss_values),
        ]
    )

    # Calculate RS and RSI
    df = df.with_columns(
        [
            pl.when(pl.col("avg_loss") == 0)
            .then(100.0)
            .when(pl.col("avg_loss").abs() < 1e-10)  # Handle near-zero
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

    # Guard against zero running_max (bad data edge case)
    if running_max.min() <= 0:
        return 0.0

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
    # Use population std (ddof=0) for financial calculations
    std_returns = excess_returns.std(ddof=0)

    if std_returns == 0:
        return 0.0

    # Annualize (sqrt(252) for daily to annual)
    return float((mean_excess / std_returns) * (252**0.5))


def _calculate_ema(prices: list[float], period: int) -> list[float]:
    """Calculate EMA manually using exponential smoothing.

    Args:
        prices: List of price values
        period: EMA period

    Returns:
        List of EMA values
    """
    if not prices:
        return []

    multiplier = 2 / (period + 1)
    # Initialize EMA with the first price
    ema = [prices[0]]

    for price in prices[1:]:
        # EMA = Price(t) * k + EMA(y) * (1 - k)
        # where k = 2/(N+1)
        current_ema = (price * multiplier) + (ema[-1] * (1 - multiplier))
        ema.append(current_ema)

    return ema


def calculate_macd(
    df: pl.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> pl.DataFrame:
    """Calculate Moving Average Convergence Divergence (MACD).

    MACD is a trend-following momentum indicator that shows the relationship
    between two moving averages of a security's price.

    Formula:
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) of MACD Line
        Histogram = MACD Line - Signal Line

    Interpretation:
        - MACD > Signal: Bullish (potential buy signal)
        - MACD < Signal: Bearish (potential sell signal)
        - Crossover: Signal changes direction

    Args:
        df: DataFrame with close_price column
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal EMA period (default 9)

    Returns:
        DataFrame with macd, macd_signal, and macd_histogram columns added
    """
    if df.is_empty():
        return df.with_columns(
            [
                pl.lit(None).alias("macd"),
                pl.lit(None).alias("macd_signal"),
                pl.lit(None).alias("macd_histogram"),
            ]
        )

    # Validate input data
    if "close_price" not in df.columns:
        st.warning("⚠️ close_price column not found for MACD calculation")
        return df.with_columns(
            [
                pl.lit(None).alias("macd"),
                pl.lit(None).alias("macd_signal"),
                pl.lit(None).alias("macd_histogram"),
            ]
        )

    # Filter out null prices
    df_valid = df.filter(pl.col("close_price").is_not_null())
    if df_valid.is_empty():
        st.warning("⚠️ No valid price data available for MACD calculation")
        return df.with_columns(
            [
                pl.lit(None).alias("macd"),
                pl.lit(None).alias("macd_signal"),
                pl.lit(None).alias("macd_histogram"),
            ]
        )

    # Get close prices as list for EMA calculation
    close_prices = df_valid["close_price"].to_list()

    # Calculate EMAs using module-level function
    fast_ema_values = _calculate_ema(close_prices, fast_period)
    slow_ema_values = _calculate_ema(close_prices, slow_period)

    # Calculate MACD line
    macd_values = [fast - slow for fast, slow in zip(fast_ema_values, slow_ema_values, strict=True)]

    # Calculate Signal line (EMA of MACD)
    # Only calculate signal if we have enough MACD values
    if len(macd_values) >= signal_period:
        signal_values = _calculate_ema(macd_values, signal_period)
    else:
        signal_values = [None] * len(macd_values)

    # Calculate Histogram
    histogram_values = []
    for i, macd in enumerate(macd_values):
        if i < len(signal_values) and signal_values[i] is not None:
            histogram = macd - signal_values[i]
            histogram_values.append(histogram)
        else:
            histogram_values.append(None)

    # Create a mapping from the valid data back to the original DataFrame
    # This ensures we maintain the original row order and structure
    macd_series = pl.Series(name="macd", values=macd_values)
    signal_series = pl.Series(name="macd_signal", values=signal_values)
    histogram_series = pl.Series(name="macd_histogram", values=histogram_values)

    # Add the MACD columns to the valid data first
    df_valid = df_valid.with_columns([macd_series, signal_series, histogram_series])

    # Merge back with original DataFrame to maintain structure
    # Use a left join to preserve all original rows
    df_result = df.join(
        df_valid.select(["trade_date", "coin", "macd", "macd_signal", "macd_histogram"]),
        on=["trade_date", "coin"],
        how="left",
    )

    return df_result
