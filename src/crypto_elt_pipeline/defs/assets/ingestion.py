import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from io import StringIO

import airbyte as ab
import dagster as dg
import pandera.polars as pa
import polars as pl

# ------------------------------------------------------------------
# Suppress PyAirbyte logging chatter
# ------------------------------------------------------------------
logging.getLogger("airbyte").setLevel(logging.CRITICAL)
os.environ["AIRBYTE_LOG_LEVEL"] = "ERROR"

# ------------------------------------------------------------------
# Schema Definitions
# ------------------------------------------------------------------


class RawMarketChartSchema(pa.DataFrameModel):
    prices: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    market_caps: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})
    total_volumes: pl.List = pa.Field(dtype_kwargs={"inner": pl.List(pl.Float64)})

    class Config:
        strict = False


class ProcessedPriceSchema(pa.DataFrameModel):
    coin: str
    currency: str

    # DEFAULT: This expects Datetime("us") (Microseconds)
    timestamp: pl.Datetime = pa.Field()

    price: float = pa.Field(gt=0)
    market_cap: float = pa.Field(ge=0)
    volume: float = pa.Field(ge=0)


# ------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------


def fetch_coingecko_data(
    coin_id: str, vs_currency: str, days: int, context: dg.AssetExecutionContext
) -> pl.DataFrame:
    start_date = (datetime.now() - timedelta(days=days)).strftime("%d-%m-%Y")
    end_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")

    context.log.info(f"📡 Fetching {coin_id} data...")

    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            source = ab.get_source(
                "source-coingecko-coins",
                docker_image="airbyte/source-coingecko-coins:0.2.26",
                config={
                    "coin_id": coin_id,
                    "vs_currency": vs_currency,
                    "days": str(days),
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            source.check()
            source.select_streams(["market_chart"])
            records = list(source.get_records("market_chart"))

        if not records:
            raise ValueError(f"No records found for {coin_id}")

        return pl.DataFrame([dict(r) for r in records], strict=False)

    except Exception as e:
        context.log.error(f"❌ Extraction failed: {str(e)}")
        raise


# ------------------------------------------------------------------
# Asset Definition
# ------------------------------------------------------------------


@dg.asset(
    group_name="ingestion",
    kinds={"airbyte", "duckdb"},
    io_manager_key="io_manager",
    key_prefix=["raw"],
    metadata={
        "source": "CoinGecko API",
        "connector": "PyAirbyte (source-coingecko-coins)",
        "connector_version": "0.2.26",
        "dagster/storage_kind": "duckdb",
        "api_docs": dg.MetadataValue.url(
            "https://docs.airbyte.com/integrations/sources/coingecko-coins"
        ),
    },
    tags={
        "layer": "raw",
        "domain": "cryptocurrency",
    },
)
def bitcoin_prices(context: dg.AssetExecutionContext) -> pl.DataFrame:
    coin_id = "bitcoin"
    vs_currency = "usd"
    days = 7

    # 1. Extraction
    raw_df = fetch_coingecko_data(coin_id, vs_currency, days, context)

    # 2. Raw Validation
    try:
        RawMarketChartSchema.validate(raw_df)
    except pa.errors.SchemaError as e:
        context.log.error(f"❌ Raw schema validation failed: {e}")
        raise

    # 3. Transformation
    context.log.info("🔄 Processing nested lists...")
    flat_df = raw_df.explode(["prices", "market_caps", "total_volumes"])

    final_df = (
        flat_df.select(
            pl.lit(coin_id).cast(pl.String).alias("coin"),
            pl.lit(vs_currency).cast(pl.String).alias("currency"),
            # --- THE FIX ---
            # 1. Cast integer to Datetime("ms") -> Interprets the number correctly (2026...)
            # 2. Cast result to Datetime("us") -> Upconverts precision to Microseconds
            # Result: Correct Date + Correct Type for Pandera
            pl.col("prices")
            .list.get(0)
            .cast(pl.Int64)
            .cast(pl.Datetime("ms"))
            .cast(pl.Datetime("us"))
            .alias("timestamp"),
            pl.col("prices").list.get(1).cast(pl.Float64).round(8).alias("price"),
            pl.col("market_caps")
            .list.get(1)
            .cast(pl.Float64)
            .round(2)
            .alias("market_cap"),
            pl.col("total_volumes")
            .list.get(1)
            .cast(pl.Float64)
            .round(2)
            .alias("volume"),
        )
        .drop_nulls(subset=["price"])
        .unique(subset=["timestamp"], keep="last")
        .sort("timestamp")
    )

    # 4. Final Validation
    try:
        ProcessedPriceSchema.validate(final_df)
        context.log.info("✅ Final output validation passed")
    except pa.errors.SchemaError as e:
        context.log.error(f"❌ Output validation failed: {e}")
        raise

    # 5. Metadata
    context.add_output_metadata(
        metadata={
            "num_rows": final_df.height,
            "latest_price": float(final_df["price"].tail(1).item()),
            "data_preview": dg.MetadataValue.md(
                final_df.head(5).to_pandas().to_markdown()
            ),
        }
    )

    return final_df
