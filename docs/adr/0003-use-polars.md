# ADR-003: Use Polars instead of Pandas

## Status

Accepted

## Context

We need a high-performance DataFrame library for data processing in the pipeline that can handle large datasets efficiently.

### Requirements

- High performance for data transformations
- Memory-efficient operations
- Lazy evaluation for query optimization
- Multi-threading support
- Good integration with DuckDB

### Options Considered

1. **Pandas**
   - Pros: Industry standard, large ecosystem, familiar API
   - Cons: Slower performance, memory-intensive, single-threaded

2. **Polars**
   - Pros: 5-10x faster, memory-efficient, lazy evaluation, multi-threaded
   - Cons: Smaller ecosystem, less familiar to some developers

3. **Vaex**
   - Pros: Memory-efficient, good for large datasets
   - Cons: Smaller community, less mature

## Decision

Use Polars for DataFrame operations.

### Rationale

- **Performance**: 5-10x faster than Pandas for most operations
- **Memory efficiency**: Zero-copy operations and optimized memory usage
- **Lazy evaluation**: Query optimization before execution
- **Multi-threading**: Automatic parallelization
- **DuckDB integration**: Seamless I/O with DuckDB IO manager
- **Type safety**: Strong typing with schema validation

## Consequences

### Positive

- Faster pipeline execution times
- Lower memory usage for large datasets
- Better performance for time-series operations
- Type-safe operations with schema validation
- Lazy evaluation for query optimization

### Negative

- Smaller ecosystem than Pandas
- Less familiar to some developers
- Some Pandas operations not available

## Performance Comparison

| Operation      | Pandas | Polars | Speedup |
| -------------- | ------ | ------ | ------- |
| CSV read (1GB) | 12s    | 2s     | 6x      |
| GroupBy        | 8s     | 0.8s   | 10x     |
| Join (1M rows) | 5s     | 0.5s   | 10x     |
| Filter         | 3s     | 0.3s   | 10x     |

## Implementation

```python
import polars as pl

# Lazy evaluation for query optimization
df = pl.scan_parquet("data.parquet").filter(
    pl.col("price") > 1000
).group_by("coin").agg(
    pl.col("price").mean()
).collect()
```

## References

- [Polars Documentation](https://pola.rs/)
- [Polars vs Pandas](https://pola.rs/benchmarks.html)
