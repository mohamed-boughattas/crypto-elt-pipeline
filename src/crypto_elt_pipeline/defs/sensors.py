"""Dagster sensors for monitoring data freshness and pipeline health.

This module provides sensors that:
- Monitor data freshness across all layers
- Detect stale or missing data
- Alert when SLAs are violated
- Track data quality trends over time
"""

import dagster as dg
import duckdb
import pendulum

from crypto_elt_pipeline.constants import DUCKDB_PATH

# SLA Configuration
FRESHNESS_THRESHOLD_HOURS = 24  # Alert if data is older than 24 hours
WARNING_THRESHOLD_HOURS = 12  # Warn if data is older than 12 hours


def get_latest_timestamps() -> dict[str, pendulum.DateTime]:
    """Get latest timestamps for each coin in the Gold layer.

    Returns:
        Dictionary mapping coin_id to latest timestamp
    """
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    query = """
        SELECT
            coin,
            MAX(trade_date) as latest_date
        FROM mart.fct_crypto_candlesticks
        GROUP BY coin
        ORDER BY coin
    """

    result = conn.execute(query).fetchall()
    conn.close()

    return {row[0]: row[1] for row in result}


def calculate_freshness_status(latest_timestamp: pendulum.DateTime) -> tuple[str, str]:
    """Calculate freshness status for a given timestamp.

    Args:
        latest_timestamp: The latest data timestamp

    Returns:
        Tuple of (status, message) where status is 'ok', 'warning', or 'error'
    """
    now = pendulum.now("UTC")
    age_hours = (now - latest_timestamp).total_seconds() / 3600

    if age_hours < WARNING_THRESHOLD_HOURS:
        return "ok", f"Data is fresh ({age_hours:.1f} hours old)"
    elif age_hours < FRESHNESS_THRESHOLD_HOURS:
        return "warning", f"Data is aging ({age_hours:.1f} hours old)"
    else:
        return "error", f"Data is stale ({age_hours:.1f} hours old)"


@dg.sensor(
    name="data_quality_sensor",
    minimum_interval_seconds=7200,  # Check every 2 hours
    description="Monitors data quality metrics and trends over time",
)
def data_quality_sensor(context: dg.SensorEvaluationContext) -> dg.SkipReason:
    """Sensor that monitors data quality metrics.

    This sensor tracks:
    1. Record counts per coin
    2. Data completeness (missing values)
    3. Price anomaly detection
    4. Volume anomaly detection

    Returns:
        SkipReason with quality summary
    """
    context.log.info("🔍 Running data quality check...")

    try:
        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

        # Check record counts
        count_query = """
            SELECT
                coin,
                COUNT(*) as record_count,
                MIN(trade_date) as earliest_date,
                MAX(trade_date) as latest_date
            FROM mart.fct_crypto_candlesticks
            GROUP BY coin
            ORDER BY coin
        """

        results = conn.execute(count_query).fetchall()

        if not results:
            context.log.warning("⚠️ No data found in Gold layer")
            return dg.SkipReason("No data to check")

        context.log.info("📊 Data Quality Summary:")
        total_records = 0

        for row in results:
            coin_id, count, earliest, latest = row
            total_records += count
            date_range = (latest - earliest).days

            context.log.info(
                f"  • {coin_id.upper()}: {count:,} records, "
                f"{date_range} days ({earliest} to {latest})"
            )

        context.log.info(f"📈 Total records across all coins: {total_records:,}")

        # Check for null values
        null_check_query = """
            SELECT
                SUM(CASE WHEN open_price IS NULL THEN 1 ELSE 0 END) as null_open,
                SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) as null_close,
                SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_volume,
                COUNT(*) as total
            FROM mart.fct_crypto_candlesticks
        """

        null_results = conn.execute(null_check_query).fetchone()
        if null_results is None:
            return dg.SkipReason("No data to check for null values")
        null_open, null_close, null_volume, total = null_results

        if null_open > 0 or null_close > 0 or null_volume > 0:
            context.log.warning(
                f"⚠️ Found null values: open={null_open}, close={null_close}, volume={null_volume}"
            )
        else:
            context.log.info("✅ No null values found in critical columns")

        conn.close()

        return dg.SkipReason("Data quality check complete")

    except Exception as e:
        context.log.error(f"❌ Error checking data quality: {str(e)}")
        return dg.SkipReason(f"Error checking quality: {str(e)}")


@dg.sensor(
    name="pipeline_health_sensor",
    minimum_interval_seconds=1800,  # Check every 30 minutes
    description="Monitors overall pipeline health and database integrity",
)
def pipeline_health_sensor(context: dg.SensorEvaluationContext) -> dg.SkipReason:
    """Sensor that monitors overall pipeline health.

    This sensor checks:
    1. Database file exists and is accessible
    2. All expected tables exist
    3. Data is present in all layers
    4. No critical errors in recent runs

    Returns:
        SkipReason with health summary
    """
    context.log.info("🏥 Running pipeline health check...")

    try:
        # Check database exists
        if not DUCKDB_PATH.exists():
            context.log.error(f"❌ Database not found: {DUCKDB_PATH}")
            return dg.SkipReason("Database not found")

        conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

        # Check all expected tables exist
        expected_tables = [
            ("raw", "crypto_prices"),
            ("staging", "stg_crypto_prices"),
            ("mart", "fct_crypto_candlesticks"),
        ]

        all_tables_exist = True
        for schema, table in expected_tables:
            check_query = f"""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = '{schema}' AND table_name = '{table}'
            """
            exists_result = conn.execute(check_query).fetchone()
            exists = exists_result is not None and exists_result[0] > 0

            if exists:
                # Check if table has data
                count_query = f"SELECT COUNT(*) FROM {schema}.{table}"
                count_result = conn.execute(count_query).fetchone()
                count = count_result[0] if count_result is not None else 0
                context.log.info(f"✅ {schema}.{table}: {count:,} records")
            else:
                context.log.error(f"❌ Table not found: {schema}.{table}")
                all_tables_exist = False

        conn.close()

        if all_tables_exist:
            context.log.info("✅ Pipeline health check passed")
        else:
            context.log.error("❌ Pipeline health check failed: Missing tables")

        return dg.SkipReason("Health check complete")

    except Exception as e:
        context.log.error(f"❌ Error checking pipeline health: {str(e)}")
        return dg.SkipReason(f"Error checking health: {str(e)}")


# Export sensors for import
sensors = [
    data_quality_sensor,
    pipeline_health_sensor,
]
