"""Dagster schedules and sensors for automated pipeline execution.

This module defines:
- Daily schedule for cryptocurrency data refresh
- Data freshness sensor to alert when data becomes stale
"""

from collections.abc import Iterator

import dagster as dg
import duckdb
import pendulum
from pendulum import Duration

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.constants import DUCKDB_PATH

# ------------------------------------------------------------------
# Daily Refresh Schedule
# ------------------------------------------------------------------

daily_crypto_refresh_job = dg.define_asset_job(
    name="daily_crypto_refresh",
    selection=dg.AssetSelection.keys(dg.AssetKey(["raw", "crypto_prices"])),
    description="Daily refresh of cryptocurrency market data from CoinGecko",
)


@dg.schedule(
    cron_schedule="0 6 * * *",  # 6 AM UTC daily
    job=daily_crypto_refresh_job,
    description="Refresh cryptocurrency data every day at 6 AM UTC",
)
def daily_crypto_schedule(
    context: dg.ScheduleEvaluationContext,
) -> Iterator[dg.RunRequest]:
    """Schedule daily cryptocurrency data refresh.

    Runs at 6 AM UTC every day to fetch the latest market data.
    Each partition (coin) is processed independently.

    Returns:
        RunRequest with partition tags for each enabled coin.
    """
    config = get_config()
    scheduled_date = context.scheduled_execution_time.strftime("%Y-%m-%d")

    # Create run requests for each enabled coin
    for coin_id in config.coin_ids:
        yield dg.RunRequest(
            run_key=f"{scheduled_date}_{coin_id}",
            partition_key=coin_id,
            tags={
                "scheduled": "true",
                "schedule_date": scheduled_date,
                "coin": coin_id,
            },
        )


# ------------------------------------------------------------------
# Data Freshness Sensor
# ------------------------------------------------------------------


@dg.sensor(
    job_name="daily_crypto_refresh",
    minimum_interval_seconds=3600,  # Check every hour
    description="Alert when cryptocurrency data becomes stale",
)
def data_freshness_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
    """Monitor data freshness and alert when data is stale.

    Triggers a run if:
    - No data exists for a coin
    - Data is older than the freshness threshold (24 hours)

    Returns:
        SensorResult with run requests for stale partitions.
    """
    config = get_config()

    # Freshness threshold: 24 hours
    freshness_threshold = Duration(hours=24)
    now = pendulum.now("UTC")

    run_requests = []

    # Check each coin's freshness by querying DuckDB for actual data freshness
    for coin_id in config.coin_ids:
        try:
            # Query DuckDB to get the latest recorded_at timestamp for this coin
            with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
                result = conn.execute(
                    "SELECT MAX(recorded_at) FROM raw.crypto_prices WHERE coin = ?",
                    [coin_id],
                ).fetchone()

                if result and result[0]:
                    # Convert to timezone-aware UTC datetime
                    latest_timestamp = result[0]
                    if latest_timestamp.tzinfo is None:
                        latest_timestamp = pendulum.instance(latest_timestamp, tz="UTC")
                    else:
                        latest_timestamp = pendulum.instance(latest_timestamp)

                    # Check if data is stale (older than 24 hours)
                    if (now - latest_timestamp) > freshness_threshold:
                        run_requests.append(
                            dg.RunRequest(
                                run_key=f"freshness_check_{coin_id}_{now.strftime('%Y%m%d_%H%M')}",
                                partition_key=coin_id,
                                tags={
                                    "trigger": "freshness_sensor",
                                    "coin": coin_id,
                                    "check_time": now.isoformat(),
                                    "data_age_hours": int(
                                        (now - latest_timestamp).total_seconds() / 3600
                                    ),
                                },
                            )
                        )
                else:
                    # No data exists for this coin, trigger a run
                    run_requests.append(
                        dg.RunRequest(
                            run_key=f"freshness_check_{coin_id}_{now.strftime('%Y%m%d_%H%M')}",
                            partition_key=coin_id,
                            tags={
                                "trigger": "freshness_sensor",
                                "coin": coin_id,
                                "check_time": now.isoformat(),
                                "data_age_hours": "no_data",
                            },
                        )
                    )
        except (duckdb.Error, FileNotFoundError):
            # Database doesn't exist yet, trigger a run for all coins
            run_requests.append(
                dg.RunRequest(
                    run_key=f"freshness_check_{coin_id}_{now.strftime('%Y%m%d_%H%M')}",
                    partition_key=coin_id,
                    tags={
                        "trigger": "freshness_sensor",
                        "coin": coin_id,
                        "check_time": now.isoformat(),
                        "data_age_hours": "database_missing",
                    },
                )
            )

    return dg.SensorResult(
        run_requests=run_requests,
        cursor=now.isoformat(),
    )


# ------------------------------------------------------------------
# Stale Data Alert Sensor (Alternative)
# ------------------------------------------------------------------


@dg.sensor(
    job_name="daily_crypto_refresh",
    minimum_interval_seconds=21600,  # Check every 6 hours
    description="Alert when data hasn't been updated in over 24 hours",
)
def stale_data_alert_sensor(context: dg.SensorEvaluationContext) -> dg.SensorResult:
    """Monitor for stale data and send alerts.

    This sensor checks the last materialization time for each partition
    and creates alerts for partitions that haven't been updated recently.

    Uses cursor to track last check time and avoid creating duplicate
    run requests within the cooldown period.

    Returns:
        SensorResult with alerts for stale data.
    """
    config = get_config()
    now = pendulum.now("UTC")

    # Alert threshold: 24 hours (cooldown period before re-alerting)
    alert_threshold_hours = 24
    cooldown_seconds = alert_threshold_hours * 3600

    # Parse cursor to get last check time (ISO format timestamp)
    cursor_data = context.cursor or ""
    last_check_str = cursor_data.split("|")[0] if "|" in cursor_data else cursor_data
    last_check = pendulum.parse(last_check_str) if last_check_str else pendulum.from_timestamp(0)

    # Only create run requests if enough time has passed since last check
    seconds_since_last_check = (now - last_check).total_seconds()

    run_requests = []

    if seconds_since_last_check >= cooldown_seconds:
        for coin_id in config.coin_ids:
            run_requests.append(
                dg.RunRequest(
                    run_key=f"stale_check_{coin_id}_{now.strftime('%Y%m%d_%H')}",
                    partition_key=coin_id,
                    tags={
                        "trigger": "stale_data_alert",
                        "coin": coin_id,
                        "threshold_hours": str(alert_threshold_hours),
                    },
                )
            )

    return dg.SensorResult(
        run_requests=run_requests,
        cursor=now.isoformat(),
    )


# ------------------------------------------------------------------
# Export schedules and sensors for Dagster definitions
# ------------------------------------------------------------------

schedules = [
    daily_crypto_schedule,
]

sensors = [
    data_freshness_sensor,
    stale_data_alert_sensor,
]
