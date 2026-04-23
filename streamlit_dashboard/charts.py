"""Chart creation and visualization utilities using Polars-native operations."""

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots


def create_candlestick_chart(
    df: pl.DataFrame,
    coin: str,
    show_bollinger_bands: bool = True,
    show_volume: bool = True,
    show_title: bool = True,
) -> go.Figure:
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

    fig.add_trace(
        go.Candlestick(
            x=df["trade_date"],
            open=df["open_price"],
            high=df["high_price"],
            low=df["low_price"],
            close=df["close_price"],
            name="OHLC",
            increasing_line_color="#22c55e",
            decreasing_line_color="#ef4444",
        ),
        row=1,
        col=1,
    )

    if "sma_7" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=df["sma_7"].to_list(),
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
                y=df["sma_25"].to_list(),
                mode="lines",
                name="SMA 25",
                line={"color": "#ef4444", "width": 1.5},
            ),
            row=1,
            col=1,
        )

    if show_bollinger_bands and "bb_upper" in df.columns and "bb_lower" in df.columns:
        bb_upper = df["bb_upper"].to_list()
        bb_lower = df["bb_lower"].to_list()

        fig.add_trace(
            go.Scatter(
                x=df["trade_date"],
                y=bb_upper,
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
                y=bb_lower,
                mode="lines",
                name="Bollinger Bands",
                line={"color": "rgba(255, 255, 255, 0.3)", "width": 1},
                fill="tonexty",
                fillcolor="rgba(255, 255, 255, 0.1)",
            ),
            row=1,
            col=1,
        )

    if show_volume and "daily_volume" in df.columns:
        bullish = (df["close_price"] >= df["open_price"]).to_list()
        colors = ["#22c55e" if b else "#ef4444" for b in bullish]

        fig.add_trace(
            go.Bar(
                x=df["trade_date"],
                y=df["daily_volume"].to_list(),
                name="Volume",
                marker_color=colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

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


def create_volume_chart(df: pl.DataFrame) -> go.Figure:
    bullish = (df["close_price"] >= df["open_price"]).to_list()
    colors = ["#22c55e" if b else "#ef4444" for b in bullish]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["trade_date"],
            y=df["daily_volume"].to_list(),
            marker_color=colors,
            showlegend=False,
        )
    )
    fig.update_layout(
        height=350,
        template="plotly_dark",
        showlegend=False,
        xaxis_title="Date",
        yaxis_title="Volume",
    )
    return fig


def create_rsi_chart(df: pl.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["rsi"].to_list(),
            mode="lines",
            name="RSI",
            line={"color": "#9b59b6", "width": 2},
        )
    )

    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", annotation_text="Oversold")

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
    avg_vol = df["volatility_pct"].mean()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["trade_date"],
            y=df["volatility_pct"].to_list(),
            marker_color="#F7931A",
            showlegend=False,
        )
    )
    fig.add_hline(
        y=avg_vol,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Avg: {avg_vol:.2f}%",
        annotation_position="top right",
    )
    fig.update_layout(
        height=300,
        template="plotly_dark",
        showlegend=False,
        xaxis_title="Date",
        yaxis_title="Volatility (%)",
    )
    return fig
