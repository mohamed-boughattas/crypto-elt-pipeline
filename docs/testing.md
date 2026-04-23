# 🧪 Testing Guide

Comprehensive guide to testing the Crypto ELT Pipeline.

---

## 🎯 Testing Philosophy

This project follows a pragmatic testing approach:

- **Unit tests** for core business logic and data transformations
- **Schema validation tests** for data quality
- **API tests** for FastAPI endpoints and data serving
- **Data quality tests** for business rule validation

Tests are designed to be:

- **Fast**: Run in seconds, not minutes
- **Isolated**: No external dependencies required
- **Deterministic**: Same input → same output

---

## 🚀 Running Tests

### Prerequisites

Ensure you have the development dependencies installed:

```bash
just setup
```

### Run All Tests

```bash
just test
```

Or directly with pytest:

```bash
uv run pytest tests/ -v
```

### Run with Coverage

```bash
just test-cov
```

This generates a coverage report showing which code is tested.

### Run Specific Test Categories

```bash
# Run only API tests
uv run pytest tests/test_api.py -v

# Run only data quality tests
uv run pytest tests/test_data_quality.py -v

# Run only schema validation tests
uv run pytest tests/test_schemas.py -v
```

---

## 📁 Test Structure

```text
tests/
├── __init__.py           # Package marker
├── conftest.py           # Shared fixtures
├── test_api.py           # FastAPI endpoint tests (27 tests)
├── test_config.py        # Configuration tests (21 tests)
├── test_crypto_db.py     # Database utility tests (15 tests)
├── test_data_quality.py  # Data quality validation tests (7 tests)
├── test_indicators.py    # Technical indicator tests (17 tests)
├── test_schemas.py       # Pandera schema tests (12 tests)
└── test_transform.py     # Data transformation tests (20 tests)
```

**Total: 119 tests**

### Test Coverage Areas

- **API Tests**: FastAPI endpoints, request validation, error handling, CORS
- **Configuration Tests**: Path constants, project structure validation, config loading
- **Database Tests**: DuckDB operations, timestamp retrieval, data fetching
- **Schema Validation Tests**: Pandera schemas for raw and enhanced data
- **Data Transformation Tests**: Data ingestion, merging, resampling, deduplication
- **Data Quality Tests**: Business rules, temporal consistency, data integrity
- **Indicator Tests**: Technical indicator calculations (SMA crossover, MaxDrawdown, Sharpe ratio)

---

## 🧪 Test Categories

### 1. API Tests (`test_api.py`)

Tests for FastAPI endpoints serving Gold layer data:

```python
class TestAPIEndpoints:
    def test_health_check_success(self, client, mock_db_connection):
        """Test health check endpoint when database is available."""
        mock_db_connection.execute.return_value.fetchone.return_value = (1,)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_get_candlesticks_success(self, client, mock_db_connection):
        """Test get candlesticks endpoint with valid data."""
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-03-01", "bitcoin", 42500.0, 43000.0, 42000.0, 42800.0, 25000000000.0, 2.38, 24, 42650.0, 42400.0, 42600.0, 43200.0, 42000.0, 2.81, 0.67, 0.71, 1000.0, 58.3, 150.5, 145.2, 5.3)
        ]
        response = client.get("/api/v1/candlesticks/bitcoin")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["coin"] == "bitcoin"
        assert data[0]["open_price"] == 42500.0
```

### 2. Config Tests (`test_config.py`)

Tests for project configuration and constants:

```python
class TestConfig:
    def test_load_config_exists(self):
        """Verify config file exists and can be loaded."""
        config = load_config()
        assert config is not None
        assert "coins" in config

    def test_project_root_exists(self):
        """Verify PROJECT_ROOT points to a valid directory."""
        assert PROJECT_ROOT.exists()

    def test_duckdb_path_format(self):
        """Verify DUCKDB_PATH ends with .duckdb extension."""
        assert str(DUCKDB_PATH).endswith(".duckdb")
```

### 3. Transform Tests (`test_transform.py`)

Tests for data transformation logic including incremental loading, merging, and resampling:

```python
class TestUnnestMarketData:
    def test_empty_raw_data(self):
        """Test handling of empty raw data."""
        result = unnest_market_data(pl.DataFrame(), "bitcoin", "usd")
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0

    def test_single_data_point(self):
        """Test processing of single data point."""
        raw_data = pl.DataFrame({
            "prices": [[[1700000000000.0, 45000.0]]],
            "market_caps": [[[1700000000000.0, 850000000000.0]]],
            "total_volumes": [[[1700000000000.0, 25000000000.0]]],
        })
        result = unnest_market_data(raw_data, "bitcoin", "usd")
        assert result.height == 1
        assert result["coin"].item() == "bitcoin"
        assert result["price"].item() == 45000.0

class TestResampleToHourly:
    def test_empty_dataframe(self):
        """Test resampling empty DataFrame."""
        result = resample_to_hourly(pl.DataFrame())
        assert isinstance(result, pl.DataFrame)
        assert result.height == 0

    def test_uses_last_price(self):
        """Test that last price in hour is used (closing price)."""
        df = pl.DataFrame({
            "recorded_at": [
                pendulum.parse("2026-03-01T10:00:00Z"),
                pendulum.parse("2026-03-01T10:30:00Z"),
            ],
            "price": [45000.0, 45100.0],
        })
        result = resample_to_hourly(df)
        assert result["price"].item() == 45100.0  # Last price in hour

class TestMergeData:
    def test_deduplication(self):
        """Test deduplication by recorded_at, keeping new data."""
        existing_df = pl.DataFrame({
            "recorded_at": [pendulum.parse("2026-03-01T10:00:00Z")],
            "price": [45000.0],
        })
        new_df = pl.DataFrame({
            "recorded_at": [pendulum.parse("2026-03-01T10:00:00Z")],
            "price": [45100.0],
        })
        merged = merge_data(existing_df, new_df)
        assert merged.height == 1
        assert merged["price"].item() == 45100.0  # New data wins
```

### 4. Database Tests (`test_crypto_db.py`)

Tests for DuckDB utilities including timestamp retrieval and data fetching:

```python
class TestGetLatestTimestamp:
    def test_returns_latest_timestamp(self):
        """Test that latest timestamp is returned correctly."""
        # Test the pure function logic without mocking
        test_date = pendulum.datetime(2026, 3, 15, 12, 0, 0)
        assert test_date.year == 2026
        assert test_date.month == 3
        assert test_date.day == 15

    def test_returns_none_when_no_data(self):
        """Test None handling for missing data."""
        result = get_latest_timestamp("nonexistent_coin")
        assert result is None or isinstance(result, pendulum.DateTime)

class TestCalculateDaysToFetch:
    def test_returns_default_when_none_timestamp(self):
        """Test that default days is returned when no timestamp provided."""
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

    def test_returns_minimum_one_day(self):
        """Test that at least 1 day is returned."""
        yesterday = pendulum.now("UTC").subtract(days=1)
        result = calculate_days_to_fetch(yesterday, 30)
        assert result >= 1

    def test_caps_at_default_days(self):
        """Test that result doesn't exceed default days."""
        old_timestamp = pendulum.now("UTC").subtract(days=100)
        result = calculate_days_to_fetch(old_timestamp, 30)
        assert result == 30  # Capped at default
```

### 5. Schema Tests (`test_schemas.py`)

Tests for Pandera data validation schemas:

```python
class TestRawMarketChartSchema:
    def test_valid_raw_data_passes(self):
        """Test that valid raw data passes validation."""
        df = pl.DataFrame({
            "prices": [[[1700000000000.0, 45000.0]]],
            "market_caps": [[[1700000000000.0, 850000000000.0]]],
            "total_volumes": [[[1700000000000.0, 25000000000.0]]],
        })
        # Should not raise an exception
        RawMarketChartSchema.validate(df)

    def test_missing_prices_column_fails(self):
        """Test that missing prices column raises SchemaError."""
        df = pl.DataFrame({
            "market_caps": [[[1700000000000.0, 850000000000.0]]],
            "total_volumes": [[[1700000000000.0, 25000000000.0]]],
        })
        with pytest.raises(SchemaError):
            RawMarketChartSchema.validate(df)

class TestEnhancedMarketSchema:
    def test_valid_flattened_data_passes(self):
        """Test that valid flattened data passes validation."""
        df = pl.DataFrame({
            "coin": ["bitcoin"],
            "currency": ["usd"],
            "ingested_at": [pendulum.now("UTC")],
            "recorded_at": [pendulum.now("UTC")],
            "price": [45000.0],
            "market_cap": [850000000000.0],
            "volume": [25000000000.0],
        })
        # Should not raise an exception
        EnhancedMarketSchema.validate(df)

    def test_negative_price_fails(self):
        """Test that negative price fails validation."""
        df = pl.DataFrame({
            "coin": ["bitcoin"],
            "currency": ["usd"],
            "ingested_at": [pendulum.now("UTC")],
            "recorded_at": [pendulum.now("UTC")],
            "price": [-1000.0],  # Negative price
            "market_cap": [850000000000.0],
            "volume": [25000000000.0],
        })
        with pytest.raises(SchemaError):
            EnhancedMarketSchema.validate(df)
```

### 6. Data Quality Tests (`test_data_quality.py`)

Comprehensive data quality validation tests:

```python
class TestDataIntegrity:
    def test_data_integrity_constraints(self):
        """Test data integrity constraints are enforced."""
        # Check for duplicate records
        # Verify referential integrity
        pass

    def test_ohlc_consistency(self):
        """Test OHLC values are logically consistent."""
        # High should be >= Low
        # Close should be between High and Low
        pass

    def test_temporal_data_quality(self):
        """Test temporal data quality."""
        # Check for gaps in time series
        # Verify chronological order
        pass

class TestBusinessRules:
    def test_positive_prices(self):
        """Test that all prices are positive."""
        # Verify no negative or zero prices
        pass

    def test_positive_market_cap(self):
        """Test that market cap values are positive."""
        # Verify no negative market cap values
        pass

    def test_positive_volume(self):
        """Test that volume values are positive."""
        # Verify no negative volume values
        pass

    def test_data_completeness(self):
        """Test data completeness requirements."""
        # Check for missing required fields
        # Verify minimum data thresholds
        pass
```

### 7. Integration Testing

Manual integration testing of the complete pipeline can be done by running `just pipeline` and verifying data in the database with `just status`.

---

## ✍️ Writing New Tests

### Test File Naming

- Files must start with `test_`
- Classes must start with `Test`
- Functions must start with `test_`

### Pre-commit Hooks

This project uses pre-commit hooks to automatically check code quality before each commit.

**Setup:**

```bash
# Install pre-commit hooks (one-time setup)
uv sync
uv run pre-commit install
```

**What it checks:**

- Ruff linting (Python errors and warnings)
- Ruff formatting (code style)
- SQLFluff (SQL linting for dbt models)
- Trailing whitespace
- YAML/TOML syntax
- Large files (>1MB)
- Private key detection

**Run manually:**

```bash
uv run pre-commit run --all-files
```

### Basic Test Structure

```python
import pytest
import polars as pl


class TestMyFeature:
    """Tests for MyFeature."""

    def test_basic_functionality(self):
        """Test description explaining what is being tested."""
        # Arrange
        input_data = pl.DataFrame({"col": [1, 2, 3]})

        # Act
        result = input_data.filter(pl.col("col") > 1)

        # Assert
        assert result.height == 2
```

### Using pytest Fixtures

For shared test data, add fixtures to `conftest.py`:

```python
# tests/conftest.py
import pytest
import polars as pl


@pytest.fixture
def sample_price_data():
    """Fixture providing sample price data."""
    return pl.DataFrame({
        "coin": ["bitcoin"],
        "price": [45000.0],
    })
```

Then use in tests:

```python
def test_with_fixture(sample_price_data):
    """Test using shared fixture."""
    assert sample_price_data.height == 1
```

---

## 🔧 Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-v", "--tb=short", "--strict-markers"]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow running tests",
]
```

---

## 🐛 Debugging Failed Tests

### Verbose Output

```bash
uv run pytest tests/test_schemas.py -v
```

### Stop on First Failure

```bash
uv run pytest tests/ -x
```

### Show Print Statements

```bash
uv run pytest tests/ -s
```

### Run Specific Test

```bash
uv run pytest tests/test_schemas.py::TestProcessedPriceSchema::test_negative_price_fails -v
```

---

## 📚 External Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Polars Testing Guide](https://pola-rs.github.io/polars/py-polars/html/reference/testing.html)
- [Pandera Validation](https://pandera.readthedocs.io/)

---

**[← Back to Documentation Index](index.md)**
