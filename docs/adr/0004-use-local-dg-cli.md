# ADR-004: Use Local dg CLI instead of Docker Compose for Development

## Status

Accepted

## Date

2026-01-01

## Context

We need to decide on the development environment setup for the Crypto ELT Pipeline project. The project currently uses local execution with Dagster's `dg` CLI, but we're considering whether to switch to a Docker Compose setup for better environment consistency.

### Requirements

- **Fast development iteration**: Quick feedback loops for development and testing
- **Resource efficiency**: Minimal overhead for local development
- **DuckDB compatibility**: Seamless integration with embedded database
- **Learning focus**: Emphasis on data engineering concepts over infrastructure
- **Portfolio presentation**: Professional demonstration of modern data stack
- **Environment consistency**: Reliable setup across different developer machines

### Options Considered

1. **Local Execution with dg CLI** (Current)
   - Pros: Fast iteration, minimal overhead, direct debugging, DuckDB compatibility
   - Cons: Potential environment differences, requires Python/uv setup

2. **Docker Compose Setup**
   - Pros: Environment consistency, production parity, dependency isolation
   - Cons: Slower development, resource overhead, DuckDB file access complexity

3. **Hybrid Approach**
   - Pros: Best of both worlds, local dev + containerized CI/CD
   - Cons: More complex setup, maintenance overhead

## Decision

Use Local dg CLI for development environment instead of Docker Compose.

### Rationale

**Primary Factors:**

1. **DuckDB Architecture Mismatch**: DuckDB is designed as an embedded, single-file database that works best with direct file system access. Docker Compose introduces volume mount complexity and potential file locking issues.

2. **Development Speed Priority**: This is a learning/portfolio project where rapid iteration and experimentation are more valuable than production-grade infrastructure.

3. **Modern Tooling Stack**: The current setup with `uv`, `dg CLI`, and Makefile provides excellent developer experience without container overhead.

4. **Industry Trend**: Modern data engineering teams are moving toward local development with containerized production, not containerized development.

**Secondary Factors:**

- **Resource Efficiency**: Local execution uses fewer system resources
- **Debugging Experience**: Direct access to logs, debugger, and IDE integration
- **Learning Focus**: Keeps emphasis on data engineering rather than DevOps
- **Already Working**: Current setup is functional and well-documented

## Consequences

### Positive

- **Fast Development Cycles**: No container rebuilds, instant feedback
- **Better DuckDB Integration**: Direct file access, no volume mount complexity
- **Simplified Architecture**: Matches the embedded nature of DuckDB
- **Enhanced Debugging**: Full IDE integration and direct log access
- **Resource Efficiency**: Lower memory and CPU overhead
- **Modern Tooling**: Demonstrates current best practices (uv, dg CLI)

### Negative

- **Environment Variability**: Potential differences between developer machines
- **Python Setup Required**: Developers need Python and uv installed
- **Less Production Parity**: Development environment differs from production
- **Limited Infrastructure Learning**: Less exposure to container orchestration

### Mitigations

- **Comprehensive Documentation**: Excellent setup guide in `docs/setup-guide.md`
- **Makefile Automation**: Simplified commands for common operations
- **Pre-commit Hooks**: Consistent code quality enforcement
- **Production Deployment Guide**: Separate documentation for production setup

## Migration Path

### Current State

- Local development with `dg` CLI
- DuckDB embedded database
- uv for dependency management
- Makefile for automation

### Future Enhancements (Optional)

1. **CI/CD Containerization**: Use Docker in GitHub Actions for consistent testing
2. **Production Deployment**: Docker Compose or Kubernetes for production environments
3. **Development Environment Scripts**: Optional Docker setup for developers who prefer containers

### Rollback Plan

If Docker Compose becomes necessary in the future:

1. Create `docker-compose.yml` with Dagster, DuckDB, and dependencies
2. Update Makefile to support both local and Docker execution
3. Add volume mounts for DuckDB database file
4. Update documentation accordingly

## References

- [Dagster dg CLI Documentation](https://docs.dagster.io/deployment/dagster-cli)
- [DuckDB Embedded Database](https://duckdb.org/)
- [uv Package Manager](https://docs.astral.sh/uv/)
- [Modern Data Engineering Development Practices](https://dagster.io/blog/local-development)
- [DuckDB vs Containerized Databases](https://duckdb.org/2021/05/14/why-duckdb.html)
