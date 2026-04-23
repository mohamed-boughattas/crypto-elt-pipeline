"""Tests for technical indicator calculations."""

import polars as pl
from streamlit_dashboard.indicators import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sma_crossover_signals,
)


class TestCalculateSmaCrossoverSignals:
    """Tests for SMA crossover signal calculation."""

    def _make_df(self, sma_7: list[float], sma_25: list[float]) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "sma_7": sma_7,
                "sma_25": sma_25,
            }
        )

    def test_golden_cross_signal(self):
        """When SMA7 > SMA25, should return Golden Cross."""
        df = self._make_df([110, 115, 120], [100, 105, 110])
        result = calculate_sma_crossover_signals(df)
        assert "Golden Cross" in result["crossover_signal"][-1]

    def test_death_cross_signal(self):
        """When SMA7 < SMA25, should return Death Cross."""
        df = self._make_df([90, 85, 80], [100, 105, 110])
        result = calculate_sma_crossover_signals(df)
        assert "Death Cross" in result["crossover_signal"][-1]

    def test_crossover_transitions(self):
        """Signal changes from Death to Golden at crossover point."""
        df = self._make_df([100, 105, 110, 115], [110, 110, 110, 105])
        result = calculate_sma_crossover_signals(df)
        signals = result["crossover_signal"].to_list()
        assert "Death Cross" in signals[0]
        assert "Golden Cross" in signals[-1]


class TestCalculateMaxDrawdown:
    """Tests for maximum drawdown calculation."""

    def test_normal_case(self):
        """Normal up-and-down price series."""
        prices = pl.Series([100, 110, 105, 95, 100, 120])
        result = calculate_max_drawdown(prices)
        assert result > 0

    def test_single_price(self):
        """Single price returns 0."""
        prices = pl.Series([100.0])
        result = calculate_max_drawdown(prices)
        assert result == 0.0

    def test_empty_series(self):
        """Empty series returns 0."""
        prices = pl.Series([], dtype=pl.Float64)
        result = calculate_max_drawdown(prices)
        assert result == 0.0

    def test_continuously_rising(self):
        """No drawdown in continuously rising prices."""
        prices = pl.Series([100, 105, 110, 115, 120])
        result = calculate_max_drawdown(prices)
        assert result == 0.0

    def test_all_negative_prices(self):
        """Prices at or below zero returns 0."""
        prices = pl.Series([0.0, 0.0, 0.0])
        result = calculate_max_drawdown(prices)
        assert result == 0.0

    def test_drop_then_recover(self):
        """Drawdown is measured from running max."""
        prices = pl.Series([100, 120, 80, 110])
        result = calculate_max_drawdown(prices)
        assert result > 0


class TestCalculateSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_normal_returns(self):
        """Normal positive returns."""
        returns = pl.Series([0.01, 0.02, -0.01, 0.015, 0.005])
        result = calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_zero_std(self):
        """Zero standard deviation returns 0."""
        returns = pl.Series([0.01, 0.01, 0.01, 0.01])
        result = calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_single_return(self):
        """Single return returns 0."""
        returns = pl.Series([0.05])
        result = calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_empty_returns(self):
        """Empty returns returns 0."""
        returns = pl.Series([], dtype=pl.Float64)
        result = calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_null_values_dropped(self):
        """Null values are dropped before calculation."""
        returns = pl.Series([0.01, None, 0.02, None, 0.015])
        result = calculate_sharpe_ratio(returns)
        assert isinstance(result, float)

    def test_all_null_returns(self):
        """All null returns after dropping returns 0."""
        returns = pl.Series([None, None, None])
        result = calculate_sharpe_ratio(returns)
        assert result == 0.0

    def test_negative_risk_free_rate(self):
        """Negative risk-free rate is handled."""
        returns = pl.Series([0.01, 0.02, 0.015])
        result = calculate_sharpe_ratio(returns, risk_free_rate=-0.01)
        assert isinstance(result, float)

    def test_custom_risk_free_rate(self):
        """Custom risk-free rate affects excess returns."""
        returns = pl.Series([0.01, 0.02, 0.015])
        result_no_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.0)
        result_with_rf = calculate_sharpe_ratio(returns, risk_free_rate=0.01)
        assert result_with_rf < result_no_rf
