# 🧪 Testing Guide

Comprehensive guide to testing the Crypto ELT Pipeline.

---

## 🎯 Testing Philosophy

This project follows a pragmatic testing approach:

- **Unit tests** for core business logic and data transformations
- **Schema validation tests** for data contracts
- **Integration tests** for critical data flows

Tests are designed to be:

- **Fast**: Run in seconds, not minutes
- **Isolated**: No external dependencies required
- **Deterministic**: Same input → same output

---

## 🚀 Running Tests

### Prerequisites

Ensure you have the development dependencies installed:

```bash
make setup
```

### Run All Tests

```bash
make test
```

Or directly with pytest:

```bash
uv run pytest tests/ -v
```

### Run with Coverage

```bash
make test-cov
```

This generates a coverage report showing which code is tested.

---

## 📁 Test Structure

```text
tests/
├── __init__.py           # Package marker
├── conftest.py           # Shared fixtures
├── test_constants.py     # Tests for path constants (13 tests)
├── test_schemas.py       # Tests for Pandera schemas
├── test_ingestion.py     # Tests for data transformations
├── test_data_quality.py  # Tests for data quality validation
└── test_integration.py   # End-to-end integration tests
```

**Total: 86 tests**

### Enhanced Test Coverage

- **Rate Limiting Tests**: Verify exponential backoff and error handling
- **Caching Tests**: Validate cache functionality and performance improvements
- **Memory Management Tests**: Ensure no memory leaks in data processing
- **Error Handling Tests**: Comprehensive validation of user feedback mechanisms
- **Data Quality Gates**: Multi-layered validation from ingestion to Gold layer

---

## 🧪 Test Categories

### 1. Constants Tests (`test_constants.py`)

Tests for project path configuration:

```python
class TestProjectPaths:
    def test_project_root_exists(self):
        """Verify PROJECT_ROOT points to a valid directory."""
        assert PROJECT_ROOT.exists()

    def test_duckdb_path_format(self):
        """Verify DUCKDB_PATH ends with .duckdb extension."""
        assert str(DUCKDB_PATH).endswith(".duckdb")
```

### 2. Schema Tests (`test_schemas.py`)

Tests for Pandera data validation schemas:

```python
class TestRawMarketChartSchema:
    def test_missing_prices_column_fails(self):
        """Verify missing prices column raises SchemaError."""
        df = pl.DataFrame({
            "market_caps": [[[1700000000000.0, 850000000000.0]]],
            "total_volumes": [[[1700000000000.0, 25000000000.0]]],
        })
        with pytest.raises(SchemaError):
            RawMarketChartSchema.validate(df)
```

### 3. Ingestion Tests (`test_ingestion.py`)

Tests for data ingestion logic including incremental loading, merging, and resampling:

```python
class TestIngestionConfig:
    """Tests for IngestionConfig."""

    def test_default_values(self):
        """Verify default configuration values come from config file."""
        config = IngestionConfig()
        assert config.get_vs_currency() == "usd"
        assert config.get_days_to_fetch() == 30


class TestCryptoPartitions:
    def test_partition_keys(self):
        """Verify expected partition keys exist."""
        keys = CRYPTO_PARTITIONS.get_partition_keys()
        assert "bitcoin" in keys
        assert "ethereum" in keys


class TestCalculateDaysToFetch:
    """Tests for incremental loading logic."""

    def test_no_existing_data(self):
        """When no existing data, should return default days."""
        result = calculate_days_to_fetch(None, 30)
        assert result == 30

    def test_recent_data(self):
        """When data is recent, should fetch only 1 day."""
        recent_timestamp = pendulum.now("UTC").subtract(hours=1)
        result = calculate_days_to_fetch(recent_timestamp, 30)
        assert result == 1


class TestMergeData:
    """Tests for data merging and deduplication."""

    def test_deduplication(self):
        """Should deduplicate by recorded_at, keeping new data."""
        merged = merge_data(existing_df, new_df)
        assert merged.height == 1
        assert merged["price"].item() == new_price  # New data wins


class TestResampleToHourly:
    """Tests for hourly resampling."""

    def test_uses_last_price(self):
        """Should use last price in the hour (closing price)."""
        result = resample_to_hourly(df_with_5min_data)
        assert result["price"].item() == last_price_in_hour


class TestRateLimiting:
    """Tests for API rate limiting and error handling."""

    def test_exponential_backoff(self):
        """Verify exponential backoff with jitter works correctly."""
        # Test that retries increase delay exponentially
        # Test that jitter prevents thundering herd
        pass

    def test_rate_limit_error_handling(self):
        """Verify RateLimitError is properly caught and handled."""
        # Test that RateLimitError triggers retry logic
        # Test that user gets proper feedback
        pass
```

### 4. Integration Tests (`test_integration.py`)

End-to-end tests that verify the complete data flow:

```python
@pytest.mark.integration
class TestDataFlow:
    def test_ohlc_consistency(self, db_connection):
        """Verify OHLC values are logically consistent."""
        df = db_connection.execute(
            "SELECT * FROM mart.fct_crypto_candlesticks"
        ).pl()

        # High should be >= Low
        assert (df["high_price"] >= df["low_price"]).all()
```

**Note:** Integration tests require a local database and are skipped in CI.

### 5. Data Quality Tests (`test_data_quality.py`)

Comprehensive data quality validation tests:

```python
class TestDataQualityGates:
    def test_data_integrity_constraints(self):
        """Verify data integrity constraints are enforced."""
        # Check for duplicate records
        # Verify referential integrity
        pass

class TestSchemaValidation:
    def test_raw_schema_validation(self):
        """Verify raw data schema matches expected structure."""
        pass

class TestDataQualityMonitoring:
    def test_data_drift_detection(self):
        """Detect changes in data distribution over time."""
        pass
```

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

## 📊 Coverage Goals

| Module                           | Target Coverage |
| -------------------------------- | --------------- |
| `constants.py`                   | 100%            |
| `ingestion.py` (transformations) | 80%             |
| Schema validation                | 90%             |

Check current coverage:

```bash
uv run pytest tests/ --cov=src/crypto_elt_pipeline --cov-report=term-missing
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
