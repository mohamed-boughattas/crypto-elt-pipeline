# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Crypto ELT Pipeline project.

## What are ADRs?

Architecture Decision Records (ADRs) document significant architectural decisions. Each ADR describes:

1. **Context**: What is the issue that we're facing that drives this decision?
2. **Decision**: What is the change that we're proposing and/or doing?
3. **Consequences**: What becomes easier or more difficult to do because of this change?

## Why ADRs?

ADRs provide several benefits:

- **Historical context**: Understand why decisions were made
- **Onboarding**: Help new team members understand the architecture
- **Consistency**: Ensure decisions are documented and reviewed
- **Communication**: Share architectural thinking with stakeholders

## ADR Index

| ADR                                 | Title                                                      | Status   | Date       |
| ----------------------------------- | ---------------------------------------------------------- | -------- | ---------- |
| [ADR-001](0001-use-duckdb.md)       | Use DuckDB instead of PostgreSQL                           | Accepted | 2026-01-01 |
| [ADR-002](0002-use-dagster.md)      | Use Dagster instead of Airflow                             | Accepted | 2026-01-01 |
| [ADR-003](0003-use-polars.md)       | Use Polars instead of Pandas                               | Accepted | 2026-01-01 |
| [ADR-004](0004-use-local-dg-cli.md) | Use Local dg CLI instead of Docker Compose for Development | Accepted | 2026-01-01 |

## ADR Template

```markdown
# ADR-XXX: [Title]

## Status

[Proposed | Accepted | Deprecated | Superseded]

## Context

[What is the issue that we're facing that drives this decision?]

## Decision

[What is the change that we're proposing and/or doing?]

## Consequences

- [Positive consequences]
- [Negative consequences]

## References

[Links to relevant documentation, discussions, etc.]
```

## Creating a New ADR

1. Copy the template above
2. Create a new file with the next number (e.g., `0004-new-decision.md`)
3. Fill in the content following the template
4. Update this README's index
5. Submit for review
