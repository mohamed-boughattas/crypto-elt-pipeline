# ADR-002: Use Dagster instead of Airflow

## Status

Accepted

## Context

We need an orchestration tool for our ELT pipeline that supports asset-based workflows, automatic lineage tracking, and native Python development.

### Requirements

- Asset-based orchestration (focus on "what to build" not "what to do")
- Automatic data lineage tracking
- Native Python development (no Docker for orchestration)
- First-class partitioning support
- Built-in testing support
- Good developer experience

### Options Considered

1. **Airflow**
   - Pros: Industry standard, large community, mature ecosystem
   - Cons: Task-centric, manual lineage, requires Docker for DAGs, complex setup

2. **Prefect**
   - Pros: Modern, code-first, good DX
   - Cons: Smaller community, less mature than Dagster

3. **Dagster**
   - Pros: Asset-centric, auto lineage, native Python, partitioning, built-in testing
   - Cons: Smaller community than Airflow

## Decision

Use Dagster for pipeline orchestration.

### Rationale

- **Asset-centric**: Focus on data assets rather than tasks
- **Automatic lineage**: Built-in data lineage tracking
- **Native Python**: No Docker required for orchestration
- **Partitioning**: First-class support for multi-coin processing
- **Testing**: Built-in testing framework and asset materialization
- **IO Managers**: Flexible storage backends (DuckDB, S3, etc.)

## Consequences

### Positive

- Clear data lineage visualization in Dagster UI
- Easy to test individual assets
- Natural partitioning for multi-coin processing
- No Docker setup for orchestration
- Type-safe configuration with Pydantic

### Negative

- Smaller community than Airflow
- Less mature ecosystem
- Steeper learning curve for task-centric developers

## Implementation

```python
@dg.asset(
    partitions_def=CRYPTO_PARTITIONS,
    io_manager_key="io_manager",
)
def crypto_prices(context, config) -> pl.DataFrame:
    """Asset definition for cryptocurrency prices."""
    # Asset logic here
```

## References

- [Dagster Documentation](https://docs.dagster.io/)
- [Asset-based orchestration](https://docs.dagster.io/concepts/assets/asset-automation)
