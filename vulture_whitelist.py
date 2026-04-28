"""Vulture whitelist — symbols that appear unused but are dynamically referenced."""

# =============================================================================
# Dagster framework (decorators, asset specs, definitions)
# =============================================================================
_.defs  # @definitions in definitions.py — discovered by Dagster's root_module
_.resources  # @dg.definitions in defs/resources.py — discovered by load_from_defs_folder
_.crypto_prices  # @dg.asset in defs/assets/ingestion.py
_.check_schema_compatibility  # @dg.asset_check in defs/assets/ingestion.py
_.check_no_null_prices  # @dg.asset_check in defs/assets/ingestion.py
_.IngestionConfig  # dg.Config subclass — instantiated reflectively by Dagster
_.CRYPTO_PARTITIONS  # used as partitions_def= in @dg.asset decorator arg
_.coingecko_api  # dg.AssetSpec — discovered by load_from_defs_folder
_.streamlit_dashboard  # dg.AssetSpec — discovered by load_from_defs_folder
_.daily_crypto_schedule  # @dg.schedule — placed in schedules list
_.data_freshness_sensor  # @dg.sensor — placed in sensors list
_.daily_crypto_refresh_job  # dg.define_asset_job — referenced as job= in @dg.schedule
_.schedules  # module-level list — consumed by Definitions.merge()
_.sensors  # module-level list — consumed by Definitions.merge()
_.database_io_manager  # module-level DuckDBPolarsIOManager — placed in resources dict
_.dbt_resource  # module-level DbtCliResource — placed in resources dict
_.crypto_dbt_assets  # @dbt_assets — discovered by load_from_defs_folder
_.dbt_project  # DbtProject instance — used in @dbt_assets manifest= and DbtCliResource
_.CustomDagsterDbtTranslator  # subclass passed as dagster_dbt_translator= in @dbt_assets
_.translator_instance  # instance passed to @dbt_assets decorator

# =============================================================================
# FastAPI framework (routers, app, models)
# =============================================================================
_.app  # FastAPI instance — referenced by uvicorn api.main:app in justfile
_.router  # APIRouter instances — registered via app.include_router()
_.health_check  # @router.get endpoint — discovered by FastAPI routing
_.root  # @router.get endpoint — discovered by FastAPI routing
_.list_coins  # @router.get endpoint — discovered by FastAPI routing
_.get_candlesticks  # @router.get endpoint — discovered by FastAPI routing
_.get_latest_data  # @router.get endpoint — discovered by FastAPI routing
_.CandlestickData  # Pydantic model — used as response_model= in @router.get
_.CoinListResponse  # Pydantic model — used as response_model= in @router.get
_.HealthResponse  # Pydantic model — used as response_model= in @router.get

# =============================================================================
# Streamlit framework (invoked via `streamlit run` CLI)
# =============================================================================
_._create_connection  # @st.cache_resource — framework-managed caching
_.get_available_coins  # @st.cache_data — framework-managed caching
_.get_coin_colors  # @st.cache_data — framework-managed caching
_.get_market_data  # @st.cache_data — framework-managed caching
_.CACHE_TTL  # module-level constant — used as ttl= in @st.cache_data decorators
_.DEFAULT_DAYS  # module-level constant — used at Streamlit runtime
_.MA_PERIOD  # module-level constant — used at Streamlit runtime

# =============================================================================
# Pytest fixtures (discovered by pytest plugin system)
# =============================================================================
_.temp_db_path  # @pytest.fixture
_.crypto_db_with_data  # @pytest.fixture
_.sample_raw_market_data  # @pytest.fixture
_.mock_airbyte_source  # @pytest.fixture(autouse=True)

# =============================================================================
# Pandera schemas (used via .validate() reflectively)
# =============================================================================
_.RawMarketChartSchema  # pa.DataFrameModel — validated in validate_raw_data()
_.EnhancedMarketSchema  # pa.DataFrameModel — validated in validate_enhanced_data()

# =============================================================================
# Custom exceptions (raised and caught via except blocks)
# =============================================================================
_.RateLimitError  # raised in crypto_api.py, caught by callers
_.DataError  # raised in streamlit_dashboard/data.py, caught by callers

# =============================================================================
# Entry points (invoked via __name__ == "__main__" or CLI)
# =============================================================================
_.main  # entry point in dbt_project/scripts/generate_seed.py

# =============================================================================
# __all__ exports (define module public API)
# =============================================================================
_.__all__  # used in defs/__init__.py and api/__init__.py
