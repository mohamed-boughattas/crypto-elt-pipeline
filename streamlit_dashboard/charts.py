"""Chart creation and visualization utilities.

This module provides functions for creating various charts and visualizations
for the cryptocurrency dashboard.

Note: These functions are optimized for Polars DataFrames to avoid
unnecessary Pandas conversions for better performance.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots


def _to_pandas_if_needed(df: pl.DataFrame) -> pd.DataFrame:
    """Convert Polars DataFrame to Pandas if needed for Plotly.

    Plotly's express and graph_objects work more reliably with Pandas.
    This is a necessary conversion for now.
    """
    return df.to_pandas()


def create_candlestick_chart(
    df: pl.DataFrame,
    coin: str,
    coin_color: str,
    show_bollinger_bands: bool = True,
    show_volume: bool = True,
    show_title: bool = True,
) -> go.Figure:
    """Create an interactive candlestick chart with optional Bollinger Bands.

    Args:
        df: DataFrame with OHLCV data
        coin: Coin identifier for title
        coin_color: Color for the coin
        show_bollinger_bands: Whether to show Bollinger Bands
        show_volume: Whether to show volume bars

    Returns:
        Plotly figure object
    """
    # Create subplots
    rows = 2 if show_volume else 1
    row_heights = [0.7] if not show_volume else [0.7, 0.3]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=("Price Chart", "Volume") if show_volume else ("Price Chart",),
    )

    # Candlestick chart
    # Always use green for bullish (price up) and red for bearish (price down)
    fig.add_trace(
        go.Candlestick(
            x=df["trade_date"],
            open=df["open_price"],
            high=df["high_price"],
            low=df["low_price"],
            close=df["close_price"],
            name="OHLC",
            increasing_line_color="#22c55e",  # Green for bullish
            decreasing_line_color="#ef4444",  # Red for bearish
        ),
        row=1,
        col=1,
    )

    # Add SMA lines if available
    if "sma_7" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=df["sma_7"],
                mode="lines",
                name="SMA 7",
                line={"color": "#22c55e", "width": 1.5},
            ),
            row=1,
            col=1,
        )

    if "sma_25" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=df["sma_25"],
                mode="lines",
                name="SMA 25",
                line={"color": "#ef4444", "width": 1.5},
            ),
            row=1,
            col=1,
        )

    # Add Bollinger Bands if available and requested
    if show_bollinger_bands and "bb_upper" in df.columns and "bb_lower" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=df["bb_upper"],
                mode="lines",
                name="BB Upper",
                line={"color": "rgba(255, 255, 255, 0.3)", "width": 1},
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=df["bb_lower"],
                mode="lines",
                name="Bollinger Bands",
                line={"color": "rgba(255, 255, 255, 0.3)", "width": 1},
                fill="tonexty",
                fillcolor="rgba(255, 255, 255, 0.1)",
            ),
            row=1,
            col=1,
        )

    # Add volume bars if requested
    if show_volume and "daily_volume" in df.columns:
        # Use green for bullish (close >= open) and red for bearish
        colors = [
            "#22c55e" if df["close_price"].iloc[i] >= df["open_price"].iloc[i] else "#ef4444"
            for i in range(len(df))
        ]

        fig.add_trace(
            go.Bar(
                x=df["trade_date"],
                y=df["daily_volume"],
                name="Volume",
                marker_color=colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    # Update layout
    title_text = f"{coin.title()} - OHLC Candlestick Chart" if show_title else ""

    fig.update_layout(
        title=title_text,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=600,
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

    fig.update_xaxes(title_text="Date", row=rows, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    if show_volume:
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig


def create_rsi_chart(df: pl.DataFrame) -> go.Figure:
    """Create an RSI chart.

    Args:
        df: DataFrame with RSI data

    Returns:
        Plotly figure object
    """
    fig = go.Figure()

    # RSI line
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["rsi"],
            mode="lines",
            name="RSI",
            line={"color": "#9b59b6", "width": 2},
        )
    )

    # Overbought line (70)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="Overbought")
    # Oversold line (30)
    fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", annotation_text="Oversold")

    # Fill overbought area
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=[70] * len(df),
            mode="lines",
            line_color="rgba(0,0,0,0)",
            showlegend=False,
            hoverinfo="skip",
        ),
    )

    fig.update_layout(
        title="Relative Strength Index (RSI)",
        template="plotly_dark",
        height=300,
        yaxis_title="RSI",
        xaxis_title="Date",
        yaxis_range=[0, 100],
    )

    return fig


def create_volatility_chart(df: pl.DataFrame) -> go.Figure:
    """Create a volatility chart with average reference line.

    Args:
        df: DataFrame with volatility data

    Returns:
        Plotly figure object
    """
    # Calculate average volatility for reference line
    avg_vol = df["volatility_pct"].mean()

    fig = px.bar(
        df,
        x="trade_date",
        y="volatility_pct",
        title="Daily Volatility (%)",
        template="plotly_dark",
        color_discrete_sequence=["#F7931A"],
    )

    # Add average line for reference
    fig.add_hline(
        y=avg_vol,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {avg_vol:.2f}%",
        annotation_position="top right",
    )

    fig.update_layout(
        height=300,
        xaxis_title="Date",
        yaxis_title="Volatility (%)",
        showlegend=False,
    )

    return fig


def create_price_comparison_chart(df: pl.DataFrame, coins: list[str]) -> go.Figure:
    """Create a normalized price comparison chart for multiple coins.

    Args:
        df: DataFrame with price data
        coins: List of coin identifiers

    Returns:
        Plotly figure object
    """
    # Normalize prices to start at 100 for comparison
    normalized_df = df.with_columns(
        [(pl.col("close_price") / pl.col("close_price").first() * 100).alias("normalized_price")]
    )

    fig = px.line(
        normalized_df,
        x="trade_date",
        y="normalized_price",
        color="coin",
        title="Normalized Price Comparison (Base = 100)",
        template="plotly_dark",
    )

    fig.update_layout(
        height=400,
        xaxis_title="Date",
        yaxis_title="Normalized Price",
    )

    return fig
