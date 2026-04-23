"""Technical indicator calculations for cryptocurrency analysis."""

import polars as pl


def calculate_sma_crossover_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Calculate SMA crossover signals (Golden Cross / Death Cross).

    Args:
        df: DataFrame with sma_7 and sma_25 columns

    Returns:
        DataFrame with crossover_signal column added
    """
    return df.with_columns(
        pl.when(pl.col("sma_7") > pl.col("sma_25"))
        .then(pl.lit("Golden Cross 🟢"))
        .otherwise(pl.lit("Death Cross 🔴"))
        .alias("crossover_signal")
    )


def calculate_max_drawdown(prices: pl.Series) -> float:
    """Calculate maximum drawdown percentage."""
    if len(prices) < 2:
        return 0.0
    running_max = prices.cum_max()
    if running_max.min() <= 0:
        return 0.0
    drawdown = (running_max - prices) / running_max * 100
    return drawdown.max()


def calculate_sharpe_ratio(returns: pl.Series, risk_free_rate: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio."""
    if len(returns) < 2:
        return 0.0
    returns = returns.drop_nulls()
    if len(returns) < 2:
        return 0.0
    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf
    mean_excess = excess_returns.mean()
    std_returns = excess_returns.std(ddof=0)
    if std_returns == 0:
        return 0.0
    return float((mean_excess / std_returns) * (252**0.5))
