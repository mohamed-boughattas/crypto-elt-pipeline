import dagster as dg

# Upstream: The external API we consume
coingecko_api = dg.AssetSpec(
    key="coingecko_api",
    group_name="Sources",
    description="External CoinGecko REST API providing raw crypto market data",
    metadata={"url": "https://www.coingecko.com/en/api"},
)

# Downstream: The dashboard that visualizes our data
streamlit_dashboard = dg.AssetSpec(
    key="streamlit_dashboard",
    group_name="Dashboards",
    kinds={"python"},
    description="Streamlit UI for crypto market analysis",
    deps=dg.AssetKey(["mart", "fct_crypto_candlesticks"]),  # Name of Gold dbt model
    metadata={"url": "http://localhost:8501"},
)
