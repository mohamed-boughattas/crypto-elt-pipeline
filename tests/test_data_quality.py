"""Comprehensive data quality tests for the crypto ELT pipeline.

This module implements data quality gates that ensure:
- Data integrity and consistency
- Business rule validation
- Temporal data quality
- Cross-system consistency
- Performance and reliability metrics
"""

import pendulum
import polars as pl

from crypto_elt_pipeline.defs.assets.ingestion import (
    EnhancedMarketSchema,
    RawMarketChartSchema,
    unnest_market_data,
)


class TestDataQualityGates:
    """Comprehensive data quality validation tests."""

    def test_data_integrity_constraints(self):
        """Test core data integrity constraints."""
        # Test with valid data
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Test all integrity constraints
        assert not result.is_empty()
        assert result["price"].min() > 0  # No negative prices
        assert result["market_cap"].min() > 0  # No negative market caps
        assert result["volume"].min() > 0  # No negative volumes
        assert result["coin"].n_unique() == 1  # Single coin per partition
        assert result["currency"].n_unique() == 1  # Single currency per partition

    def test_business_rule_validation(self):
        """Test business rule validation for cryptocurrency data."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50], [1700003600000.0, 45100.25]],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Business rule: Market cap should generally correlate with price
        # (not a strict rule, but should be reasonable)
        price_ratio = result["market_cap"].mean() / result["price"].mean()
        assert 10000000 < price_ratio < 100000000  # Reasonable market cap to price ratio

        # Business rule: Volume should be substantial for major cryptocurrencies
        assert result["volume"].mean() > 1000000  # At least $1M average daily volume

    def test_temporal_data_quality(self):
        """Test temporal data quality and consistency."""
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [
                        [1700000000000.0, 45000.50],  # 2023-11-14 22:13:20
                        [1700003600000.0, 45100.25],  # 2023-11-14 23:13:20
                        [1700007200000.0, 45200.00],  # 2023-11-15 00:13:20
                    ],
                ],
                "market_caps": [
                    [
                        [1700000000000.0, 850000000000.0],
                        [1700003600000.0, 852000000000.0],
                        [1700007200000.0, 853000000000.0],
                    ],
                ],
                "total_volumes": [
                    [
                        [1700000000000.0, 25000000000.0],
                        [1700003600000.0, 25500000000.0],
                        [1700007200000.0, 26000000000.0],
                    ],
                ],
            },
            strict=False,
        )

        result = unnest_market_data(raw_df, "bitcoin", "usd")

        # Temporal consistency: timestamps should be in chronological order
        timestamps = result["recorded_at"].to_list()
        assert timestamps == sorted(timestamps)

        # Temporal consistency: no duplicate timestamps
        assert result["recorded_at"].n_unique() == result.height

        # Temporal range: should be reasonable time range
        time_range = timestamps[-1] - timestamps[0]
        assert time_range.total_seconds() > 0  # At least some time difference
        assert time_range.total_seconds() < 86400 * 365  # Less than 1 year

    def test_cross_system_consistency(self):
        """Test consistency across different data sources and transformations."""
        # Test that the same raw data produces consistent results
        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        # Run transformation multiple times
        result1 = unnest_market_data(raw_df, "bitcoin", "usd")
        result2 = unnest_market_data(raw_df, "bitcoin", "usd")

        # Results should have same data except for ingested_at timestamp
        # Compare all columns except ingested_at
        data_columns = ["coin", "currency", "recorded_at", "price", "market_cap", "volume"]
        assert result1.select(data_columns).equals(result2.select(data_columns))

        # Schema should be consistent
        assert list(result1.columns) == list(result2.columns)
        assert result1.schema == result2.schema

    def test_performance_metrics(self):
        """Test performance and reliability metrics."""
        # Create larger dataset to test performance
        timestamps = [1700000000000.0 + i * 3600000.0 for i in range(100)]  # 100 hours
        prices = [45000.0 + i * 100.0 for i in range(100)]
        market_caps = [850000000000.0 + i * 1000000000.0 for i in range(100)]
        volumes = [25000000000.0 + i * 100000000.0 for i in range(100)]

        raw_df = pl.DataFrame(
            {
                "prices": [[list(x) for x in zip(timestamps, prices, strict=True)]],
                "market_caps": [[list(x) for x in zip(timestamps, market_caps, strict=True)]],
                "total_volumes": [[list(x) for x in zip(timestamps, volumes, strict=True)]],
            },
            strict=False,
        )

        import time

        start_time = time.time()
        result = unnest_market_data(raw_df, "bitcoin", "usd")
        end_time = time.time()

        # Performance: should process 100 data points quickly
        processing_time = end_time - start_time
        assert processing_time < 1.0  # Should complete in under 1 second

        # Correctness: should produce expected number of records
        assert result.height == 100

        # Memory efficiency: should not have excessive memory usage
        assert result["price"].dtype == pl.Float64
        assert result["market_cap"].dtype == pl.Float64
        assert result["volume"].dtype == pl.Float64


class TestSchemaValidation:
    """Test schema validation for data contracts."""

    def test_raw_schema_validation(self):
        """Test validation of raw nested data structure."""
        # Valid raw data
        valid_raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        # Should pass validation
        try:
            RawMarketChartSchema.validate(valid_raw_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert validation_passed

        # Invalid raw data - missing prices
        invalid_raw_df = pl.DataFrame(
            {
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        # Should fail validation
        try:
            RawMarketChartSchema.validate(invalid_raw_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert not validation_passed

    def test_enhanced_schema_validation(self):
        """Test validation of flattened market data."""
        # Valid flattened data
        valid_flattened_df = pl.DataFrame(
            {
                "coin": ["bitcoin", "bitcoin"],
                "currency": ["usd", "usd"],
                "ingested_at": [pendulum.now("UTC"), pendulum.now("UTC")],
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 14, 23, 13, 20, tz="UTC"),
                ],
                "price": [45000.50, 45100.25],
                "market_cap": [850000000000.0, 852000000000.0],
                "volume": [25000000000.0, 25500000000.0],
            }
        )

        # Should pass validation
        try:
            EnhancedMarketSchema.validate(valid_flattened_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert validation_passed

        # Invalid flattened data - negative price
        invalid_flattened_df = pl.DataFrame(
            {
                "coin": ["bitcoin"],
                "currency": ["usd"],
                "ingested_at": [pendulum.now("UTC")],
                "recorded_at": [pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC")],
                "price": [-100.0],  # Invalid: negative price
                "market_cap": [850000000000.0],
                "volume": [25000000000.0],
            }
        )

        # Should fail validation
        try:
            EnhancedMarketSchema.validate(invalid_flattened_df)
            validation_passed = True
        except Exception:
            validation_passed = False
        assert not validation_passed


class TestDataQualityMonitoring:
    """Test data quality monitoring and alerting capabilities."""

    def test_data_drift_detection(self):
        """Test detection of data drift and anomalies."""
        # Normal data
        normal_df = pl.DataFrame(
            {
                "coin": ["bitcoin"] * 10,
                "currency": ["usd"] * 10,
                "ingested_at": [pendulum.now("UTC")] * 10,
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC")
                    + pendulum.duration(hours=i)
                    for i in range(10)
                ],
                "price": [45000.0 + i * 100.0 for i in range(10)],
                "market_cap": [850000000000.0 + i * 1000000000.0 for i in range(10)],
                "volume": [25000000000.0 + i * 100000000.0 for i in range(10)],
            }
        )

        # Anomalous data - extreme price spike
        anomalous_df = normal_df.clone()
        anomalous_df = anomalous_df.with_columns(
            pl.when(pl.col("price") > 45500.0)
            .then(pl.lit(1000000.0))  # Extreme anomaly
            .otherwise(pl.col("price"))
            .alias("price")
        )

        # Normal data should pass basic quality checks
        assert normal_df["price"].std() < 500.0  # Reasonable volatility

        # Anomalous data should be detected
        assert anomalous_df["price"].std() > 10000.0  # Extreme volatility detected

    def test_data_completeness_checks(self):
        """Test data completeness and missing data detection."""
        # Complete data
        complete_df = pl.DataFrame(
            {
                "coin": ["bitcoin"] * 5,
                "currency": ["usd"] * 5,
                "ingested_at": [pendulum.now("UTC")] * 5,
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC")
                    + pendulum.duration(hours=i)
                    for i in range(5)
                ],
                "price": [45000.0, 45100.0, 45200.0, 45300.0, 45400.0],
                "market_cap": [
                    850000000000.0,
                    851000000000.0,
                    852000000000.0,
                    853000000000.0,
                    854000000000.0,
                ],
                "volume": [
                    25000000000.0,
                    25100000000.0,
                    25200000000.0,
                    25300000000.0,
                    25400000000.0,
                ],
            }
        )

        # Missing data simulation
        incomplete_df = complete_df.clone()
        incomplete_df = incomplete_df.with_columns(
            pl.when(pl.col("price") > 45200.0)
            .then(None)  # Missing values
            .otherwise(pl.col("price"))
            .alias("price")
        )

        # Complete data should have no nulls
        assert complete_df.null_count().sum_horizontal().sum() == 0

        # Incomplete data should have nulls detected
        null_count = incomplete_df.null_count().sum_horizontal().sum()
        assert null_count > 0

    def test_data_consistency_across_partitions(self):
        """Test consistency of data across different partitions."""
        # Simulate data for different coins
        bitcoin_data = pl.DataFrame(
            {
                "coin": ["bitcoin"] * 3,
                "currency": ["usd"] * 3,
                "ingested_at": [pendulum.now("UTC")] * 3,
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 14, 23, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 15, 0, 13, 20, tz="UTC"),
                ],
                "price": [45000.0, 45100.0, 45200.0],
                "market_cap": [850000000000.0, 851000000000.0, 852000000000.0],
                "volume": [25000000000.0, 25100000000.0, 25200000000.0],
            }
        )

        ethereum_data = pl.DataFrame(
            {
                "coin": ["ethereum"] * 3,
                "currency": ["usd"] * 3,
                "ingested_at": [pendulum.now("UTC")] * 3,
                "recorded_at": [
                    pendulum.datetime(2023, 11, 14, 22, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 14, 23, 13, 20, tz="UTC"),
                    pendulum.datetime(2023, 11, 15, 0, 13, 20, tz="UTC"),
                ],
                "price": [2500.0, 2510.0, 2520.0],
                "market_cap": [300000000000.0, 301000000000.0, 302000000000.0],
                "volume": [15000000000.0, 15100000000.0, 15200000000.0],
            }
        )

        # Combine data
        combined_df = pl.concat([bitcoin_data, ethereum_data])

        # Each coin should have consistent structure
        for coin in combined_df["coin"].unique():
            coin_data = combined_df.filter(pl.col("coin") == coin)
            assert coin_data["currency"].n_unique() == 1
            assert coin_data["price"].min() > 0
            assert coin_data["market_cap"].min() > 0
            assert coin_data["volume"].min() > 0

        # Timestamps should be consistent across coins
        bitcoin_timestamps = set(bitcoin_data["recorded_at"].to_list())
        ethereum_timestamps = set(ethereum_data["recorded_at"].to_list())
        assert bitcoin_timestamps == ethereum_timestamps  # Same time periods


class TestErrorHandling:
    """Test error handling and recovery mechanisms."""

    def test_graceful_error_handling(self):
        """Test graceful handling of various error conditions."""
        # Test with completely invalid data
        invalid_raw_df = pl.DataFrame(
            {
                "prices": [
                    "invalid_data",  # Should be list of lists
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        # Should handle gracefully and provide meaningful error
        try:
            result = unnest_market_data(invalid_raw_df, "bitcoin", "usd")
            # If it doesn't raise an error, it should return empty with correct schema
            assert result.is_empty() or result.height == 0
        except Exception as e:
            # Should provide meaningful error message about data structure
            assert "Data length mismatch" in str(e)

    def test_concurrent_access_safety(self):
        """Test thread safety and concurrent access patterns."""
        import concurrent.futures

        raw_df = pl.DataFrame(
            {
                "prices": [
                    [[1700000000000.0, 45000.50]],
                ],
                "market_caps": [
                    [[1700000000000.0, 850000000000.0]],
                ],
                "total_volumes": [
                    [[1700000000000.0, 25000000000.0]],
                ],
            },
            strict=False,
        )

        results = []
        errors = []

        def process_data():
            try:
                result = unnest_market_data(raw_df, "bitcoin", "usd")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_data) for _ in range(5)]
            concurrent.futures.wait(futures)

        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 5

        # All results should be identical (excluding ingested_at timestamp)
        data_columns = ["coin", "currency", "recorded_at", "price", "market_cap", "volume"]
        for result in results[1:]:
            assert results[0].select(data_columns).equals(result.select(data_columns))
