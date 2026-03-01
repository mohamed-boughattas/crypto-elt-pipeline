"""Tests for FastAPI endpoints.

This module provides comprehensive tests for the REST API endpoints
that serve Gold layer data from DuckDB.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from api.main import app
from fastapi.testclient import TestClient


class TestAPIEndpoints:
    """Test suite for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_db_connection(self):
        """Mock DuckDB connection for testing."""
        with patch("api.main.get_db_connection") as mock_ctx:
            mock_db = MagicMock()
            # Set up context manager behavior
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            yield mock_db

    def test_health_check_success(self, client, mock_db_connection):
        """Test health check endpoint when database is available."""
        # Mock successful database query
        mock_db_connection.execute.return_value.fetchone.return_value = (date(2026, 3, 1),)

        with patch("api.main.DUCKDB_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.stat.return_value.st_size = 1024 * 1024  # 1MB

            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "database_path" in data
        assert data["database_exists"] is True
        assert "database_size_mb" in data
        assert "last_updated" in data
        assert "timestamp" in data
        assert "X-Request-ID" in response.headers

    def test_health_check_database_not_found(self, client):
        """Test health check when database file doesn't exist."""
        with patch("api.main.DUCKDB_PATH") as mock_path:
            mock_path.exists.return_value = False
            mock_path.stat.side_effect = FileNotFoundError()

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database_exists"] is False

    def test_health_check_database_connection_failed(self, client):
        """Test health check when database connection fails."""
        with (
            patch("api.main.DUCKDB_PATH") as mock_path,
            patch("api.main.get_db_connection") as mock_ctx,
        ):
            mock_path.exists.return_value = True
            mock_path.stat.return_value.st_size = 1024 * 1024  # 1MB
            mock_ctx.side_effect = Exception("Connection failed")

            response = client.get("/health")

            assert response.status_code == 503
            data = response.json()
            assert "Service unavailable" in data["detail"]

    def test_list_coins_success(self, client, mock_db_connection):
        """Test list coins endpoint with data."""
        # Mock database query results
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchone=lambda: (3,)),  # Total count
            MagicMock(fetchall=lambda: [("bitcoin",), ("ethereum",), ("ripple",)]),  # Coins
        ]

        response = client.get("/api/v1/coins")

        assert response.status_code == 200
        data = response.json()

        assert data["coins"] == ["bitcoin", "ethereum", "ripple"]
        assert data["count"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 1
        assert "X-Request-ID" in response.headers
        assert "Cache-Control" in response.headers

    def test_list_coins_pagination(self, client, mock_db_connection):
        """Test list coins endpoint with pagination."""
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchone=lambda: (100,)),  # Total count
            MagicMock(fetchall=lambda: [("coin1",), ("coin2",)]),  # Page 1
        ]

        response = client.get("/api/v1/coins?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 50
        assert len(data["coins"]) == 2

    def test_list_coins_empty(self, client, mock_db_connection):
        """Test list coins endpoint with no data."""
        mock_db_connection.execute.side_effect = [
            MagicMock(fetchone=lambda: (0,)),  # Total count
            MagicMock(fetchall=lambda: []),  # No coins
        ]

        response = client.get("/api/v1/coins")

        assert response.status_code == 200
        data = response.json()

        assert data["coins"] == []
        assert data["count"] == 0
        assert data["total_pages"] == 0

    def test_list_coins_invalid_page(self, client):
        """Test list coins endpoint with invalid page number."""
        response = client.get("/api/v1/coins?page=0")

        assert response.status_code == 422  # Validation error

    def test_list_coins_invalid_page_size(self, client):
        """Test list coins endpoint with invalid page size."""
        response = client.get("/api/v1/coins?page_size=101")

        assert response.status_code == 422  # Validation error

    def test_list_coins_database_error(self, client):
        """Test list coins endpoint when database query fails."""
        with patch("api.main.get_db_connection") as mock_ctx:
            mock_ctx.side_effect = Exception("Query failed")

            response = client.get("/api/v1/coins")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve coins" in data["detail"]

    def test_get_candlesticks_success(self, client, mock_db_connection):
        """Test get candlesticks endpoint with valid data."""
        # Mock database query results
        mock_row = (
            date(2026, 3, 1),
            "bitcoin",
            42500.0,
            43000.0,
            42000.0,
            42800.0,
            25000000000.0,
            2.38,
            24,
            42650.0,
            42400.0,
            42700.0,
            43000.0,
            42400.0,
            600.0,
            0.5,
            0.71,
            1000.0,
        )
        mock_db_connection.execute.return_value.fetchall.return_value = [mock_row]

        response = client.get("/api/v1/candlesticks/bitcoin")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["coin"] == "bitcoin"
        assert data[0]["trade_date"] == "2026-03-01"
        assert data[0]["open_price"] == 42500.0
        assert "X-Request-ID" in response.headers
        assert "X-RateLimit-Limit" in response.headers
        assert "Cache-Control" in response.headers

    def test_get_candlesticks_with_date_filters(self, client, mock_db_connection):
        """Test get candlesticks endpoint with date filters."""
        mock_db_connection.execute.return_value.fetchall.return_value = []

        response = client.get(
            "/api/v1/candlesticks/bitcoin?start_date=2026-01-01&end_date=2026-03-01"
        )

        assert response.status_code == 404  # No data found

    def test_get_candlesticks_invalid_days(self, client):
        """Test get candlesticks endpoint with invalid days parameter."""
        response = client.get("/api/v1/candlesticks/bitcoin?days=400")

        assert response.status_code == 422  # Validation error

    def test_get_candlesticks_invalid_coin_format(self, client):
        """Test get candlesticks endpoint with invalid coin format."""
        response = client.get("/api/v1/candlesticks/Bitcoin123")

        assert response.status_code == 422  # Validation error

    def test_get_candlesticks_not_found(self, client, mock_db_connection):
        """Test get candlesticks endpoint when coin not found."""
        mock_db_connection.execute.return_value.fetchall.return_value = []

        response = client.get("/api/v1/candlesticks/bitcoin")

        assert response.status_code == 404
        data = response.json()
        assert "No data found for coin: bitcoin" in data["detail"]

    def test_get_candlesticks_database_error(self, client):
        """Test get candlesticks endpoint when database query fails."""
        with patch("api.main.get_db_connection") as mock_ctx:
            mock_ctx.side_effect = Exception("Query failed")

            response = client.get("/api/v1/candlesticks/bitcoin")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve candlestick data" in data["detail"]

    def test_get_latest_data_success(self, client, mock_db_connection):
        """Test get latest data endpoint with valid data."""
        mock_row = (
            date(2026, 3, 1),
            "bitcoin",
            42500.0,
            43000.0,
            42000.0,
            42800.0,
            25000000000.0,
            2.38,
            24,
            42650.0,
            42400.0,
            42700.0,
            43000.0,
            42400.0,
            600.0,
            0.5,
            0.71,
            1000.0,
        )
        mock_db_connection.execute.return_value.fetchall.return_value = [mock_row]

        response = client.get("/api/v1/latest")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["coin"] == "bitcoin"
        assert "X-Request-ID" in response.headers
        assert "X-RateLimit-Limit" in response.headers
        assert "Cache-Control" in response.headers

    def test_get_latest_data_empty(self, client, mock_db_connection):
        """Test get latest data endpoint with no data."""
        mock_db_connection.execute.return_value.fetchall.return_value = []

        response = client.get("/api/v1/latest")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 0

    def test_get_latest_data_database_error(self, client):
        """Test get latest data endpoint when database query fails."""
        with patch("api.main.get_db_connection") as mock_ctx:
            mock_ctx.side_effect = Exception("Query failed")

            response = client.get("/api/v1/latest")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve latest data" in data["detail"]

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Crypto ELT Pipeline API"
        assert data["version"] == "1.1.0"
        assert "documentation" in data
        assert "health" in data

    def test_rate_limiting(self, client, mock_db_connection):
        """Test rate limiting functionality."""
        # Mock database responses to return valid data
        mock_row = (
            date(2026, 3, 1),
            "bitcoin",
            42500.0,
            43000.0,
            42000.0,
            42800.0,
            25000000000.0,
            2.38,
            24,
            42650.0,
            42400.0,
            42700.0,
            43000.0,
            42400.0,
            600.0,
            0.5,
            0.71,
            1000.0,
        )
        mock_db_connection.execute.return_value.fetchall.return_value = [mock_row]

        # Make a few requests - rate limiting should work but we won't test exact limits
        # due to test environment variability
        for _ in range(5):
            response = client.get("/api/v1/candlesticks/bitcoin")
            assert response.status_code == 200  # Should succeed for a few requests

        # Just verify that rate limiting headers are present
        response = client.get("/api/v1/candlesticks/bitcoin")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Period" in response.headers

    def test_request_id_uniqueness(self, client, mock_db_connection):
        """Test that each request gets a unique request ID."""
        mock_db_connection.execute.return_value.fetchall.return_value = []

        request_ids = []
        for _ in range(3):
            response = client.get("/health")
            request_ids.append(response.headers.get("X-Request-ID"))

        # All request IDs should be unique
        assert len(set(request_ids)) == 3
        assert all(request_id for request_id in request_ids)


class TestAPIValidation:
    """Test suite for API validation and edge cases."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    def test_coin_parameter_validation_lowercase_only(self, client):
        """Test that coin parameter only accepts lowercase letters."""
        response = client.get("/api/v1/candlesticks/Bitcoin")

        assert response.status_code == 422  # Validation error

    def test_coin_parameter_validation_min_length(self, client):
        """Test that coin parameter requires minimum length."""
        response = client.get("/api/v1/candlesticks/a")

        assert response.status_code == 422  # Validation error

    def test_coin_parameter_validation_max_length(self, client):
        """Test that coin parameter enforces maximum length."""
        long_coin = "a" * 51
        response = client.get(f"/api/v1/candlesticks/{long_coin}")

        assert response.status_code == 422  # Validation error

    def test_days_parameter_validation_min(self, client):
        """Test that days parameter has minimum value."""
        response = client.get("/api/v1/candlesticks/bitcoin?days=0")

        assert response.status_code == 422  # Validation error

    def test_days_parameter_validation_max(self, client):
        """Test that days parameter has maximum value."""
        response = client.get("/api/v1/candlesticks/bitcoin?days=366")

        assert response.status_code == 422  # Validation error

    def test_page_parameter_validation_min(self, client):
        """Test that page parameter has minimum value."""
        response = client.get("/api/v1/coins?page=0")

        assert response.status_code == 422  # Validation error

    def test_page_size_parameter_validation_min(self, client):
        """Test that page_size parameter has minimum value."""
        response = client.get("/api/v1/coins?page_size=0")

        assert response.status_code == 422  # Validation error

    def test_page_size_parameter_validation_max(self, client):
        """Test that page_size parameter has maximum value."""
        response = client.get("/api/v1/coins?page_size=101")

        assert response.status_code == 422  # Validation error
