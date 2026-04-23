"""Dagster schedules and sensors for automated pipeline execution.

This module defines:
- Daily schedule for cryptocurrency data refresh
- Data freshness sensor to alert when data becomes stale
"""

from collections.abc import Iterator

import dagster as dg
import pendulum
from pendulum import Duration

from crypto_elt_pipeline.config import get_config
from crypto_elt_pipeline.utils.crypto_db import get_latest_timestamp

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

    Note: Uses direct DuckDB connection for sensor independence.
    Sensors run on their own schedule and need direct DB access.

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
        latest_ts = get_latest_timestamp(coin_id)
        if latest_ts is None or (now - latest_ts) > freshness_threshold:
            data_age = int((now - latest_ts).total_seconds() / 3600) if latest_ts else "no_data"
            run_requests.append(
                dg.RunRequest(
                    run_key=f"freshness_check_{coin_id}_{now.strftime('%Y%m%d_%H')}",
                    partition_key=coin_id,
                    tags={
                        "trigger": "freshness_sensor",
                        "coin": coin_id,
                        "check_time": now.isoformat(),
                        "data_age_hours": data_age,
                    },
                )
            )

    return dg.SensorResult(
        run_requests=run_requests,
        cursor=now.isoformat(),
    )


schedules = [
    daily_crypto_schedule,
]

sensors = [
    data_freshness_sensor,
]
