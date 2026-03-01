# ADR-001: Use DuckDB instead of PostgreSQL

## Status

Accepted

## Context

We need a database for local development that requires no setup, provides fast analytics, and can handle time-series cryptocurrency data efficiently.

### Requirements

- Zero setup for local development
- Fast aggregations for OHLC calculations
- Columnar storage for analytics
- Single-file database for easy versioning
- Support for SQL queries

### Options Considered

1. **PostgreSQL**
   - Pros: Industry standard, multi-user support, mature ecosystem
   - Cons: Requires server setup, row-oriented storage, complex installation

2. **SQLite**
   - Pros: Embedded, zero setup
   - Cons: Row-oriented, slow for analytics, limited SQL features

3. **DuckDB**
   - Pros: Embedded, columnar storage, fast aggregations, SQL-compatible
   - Cons: Not suitable for multi-user production

## Decision

Use DuckDB for embedded analytics database.

### Rationale

- **Zero setup**: No server installation or configuration needed
- **Columnar storage**: Optimized for analytics queries (OHLC aggregations)
- **Fast performance**: Vectorized execution with SIMD
- **Single file**: Easy to version control and backup
- **SQL compatible**: Works with dbt and standard SQL
- **Polars integration**: Seamless I/O with Polars DataFrames

## Consequences

### Positive

- Developers can start working immediately with `make pipeline`
- Fast query performance for time-series aggregations
- Easy to backup and version control database file
- Seamless integration with Polars I/O manager

### Negative

- Not suitable for multi-user production scenarios
- Limited ecosystem compared to PostgreSQL
- Need migration path for production deployment

## Migration Path

For production deployment, consider:

- PostgreSQL for multi-user access
- Snowflake/BigQuery for cloud analytics
- Keep DuckDB for local development and testing

## References

- [DuckDB Documentation](https://duckdb.org/)
- [Why DuckDB?](https://duckdb.org/2021/05/14/why-duckdb.html)
