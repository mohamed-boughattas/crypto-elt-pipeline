# 📚 Documentation

Technical documentation for the Bitcoin Analysis Pipeline.

---

## 📖 Available Documentation

### [📐 Architecture](system-design.md)

System design, component breakdown, and data flow.

**Topics covered:**

- PyAirbyte extraction layer
- Dagster orchestration
- dbt transformations (Medallion architecture)
- DuckDB storage with Polars
- Technology choices & rationale

---

### [🗂️ Data Modeling](data-modeling.md)

Medallion architecture implementation and dbt models.

**Topics covered:**

- Bronze layer (raw data)
- Silver layer (cleaned data)
- Gold layer (business metrics)
- OHLC candlestick calculations
- Incremental materialization strategy

---

### [🚀 Setup Guide](setup-guide.md)

Detailed installation and configuration steps.

**Topics covered:**

- Prerequisites
- Installation steps
- Environment setup
- First pipeline run
- Verification steps

---

## 🎯 Quick Navigation

| What you want to do | Where to look |
| --------------------- | --------------- |
| Understand the system | [Architecture](system-design.md) |
| Install and run | [Setup Guide](setup-guide.md) |
| Learn data transformations | [Data Modeling](data-modeling.md) |

---

## 📚 External Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [dbt Documentation](https://docs.getdbt.com/)
- [PyAirbyte Getting Started](https://docs.airbyte.com/using-airbyte/pyairbyte/getting-started)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Polars User Guide](https://pola-rs.github.io/polars/)

---

**[← Back to Main README](../README.md)**
