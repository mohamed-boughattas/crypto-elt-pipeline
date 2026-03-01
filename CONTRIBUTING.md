# Contributing to Crypto ELT Pipeline

Thank you for considering contributing to the Crypto ELT Pipeline! This document outlines our contribution guidelines and processes.

## 🤝 How to Contribute

### Reporting Issues

We use GitHub Issues to track bugs, feature requests, and discussions. When reporting an issue:

1. **Search existing issues** first to avoid duplicates
2. **Use descriptive titles** that summarize the problem
3. **Provide detailed information** including:
   - Environment details (OS, Python version, uv version)
   - Steps to reproduce the issue
   - Expected vs. actual behavior
   - Error messages and stack traces (if applicable)
   - Screenshots (for UI-related issues)

**Issue Template:**

```markdown
## Description

[Brief description of the issue]

## Environment

- OS: [e.g., macOS 13.0]
- Python: [e.g., 3.12.0]
- uv: [e.g., 0.5.0]
- Docker: [e.g., 24.0.0]

## Steps to Reproduce

1. [Step 1]
2. [Step 2]
3. [Step 3]

## Expected Behavior

[What you expected to happen]

## Actual Behavior

[What actually happened]

## Additional Context

[Any additional context, logs, or screenshots]
```

### Feature Requests

For new features or enhancements:

1. **Check existing issues** to see if it's already being discussed
2. **Create a new issue** with the `enhancement` label
3. **Provide a clear description** of the feature and its benefits
4. **Include use cases** and examples where applicable

### Pull Requests

We welcome pull requests! Here's how to contribute:

#### 1. Fork and Clone

```bash
# Fork the repository on GitHub
git clone https://github.com/YOUR_USERNAME/crypto-elt-pipeline.git
cd crypto-elt-pipeline
```

#### 2. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

#### 3. Make Your Changes

- Follow the existing code style and patterns
- Add tests for new functionality
- Update documentation as needed
- Ensure all existing tests still pass

#### 4. Test Your Changes

```bash
# Run the test suite
make test

# Run linting and formatting
make lint

# Test the full pipeline
make pipeline
```

#### 5. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add new feature description"
# or
git commit -m "fix: resolve specific issue"
```

#### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
# Then create a Pull Request on GitHub
```

## 📝 Code Style Guidelines

### Python Code

- **Formatter**: Ruff (configured in `pyproject.toml`)
- **Run formatting**: `make lint`
- **Pre-commit hooks**: Automatically format code before commits

### SQL Code (dbt models)

- **Linter**: SQLFluff (configured in `dbt_project/.sqlfluff`)
- **Run linting**: `cd dbt_project && uv run sqlfluff lint models/`
- **Auto-fix**: `cd dbt_project && uv run sqlfluff fix models/`

### Commit Message Format

We follow conventional commit format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance tasks

**Examples:**

```text
feat: add Bollinger Bands calculation to Gold layer
fix: resolve connection timeout in PyAirbyte extraction
docs: update setup guide with Docker troubleshooting
```

## 🧪 Testing Guidelines

### Test Structure

- Tests are located in the `tests/` directory
- Use pytest for test execution
- Follow naming conventions: `test_*.py`, `Test*`, `test_*()`

### Writing Tests

1. **Unit tests** for isolated functionality
2. **Integration tests** for data flow validation
3. **Schema tests** for data contract validation
4. **Use fixtures** for shared test data (in `conftest.py`)

### Test Categories

- **Configuration tests**: Path validation, project structure
- **Schema tests**: Pandera validation for data contracts
- **Ingestion tests**: Data transformations, incremental loading
- **Data quality tests**: Business logic validation
- **Database tests**: DuckDB operations, data fetching

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/test_config.py -v

# Run specific test
uv run pytest tests/test_config.py::TestConfig::test_load_config_exists -v
```

## 📚 Documentation Guidelines

### Documentation Structure

- **README.md**: Project overview and quick start
- **docs/**: Detailed documentation
  - `system-design.md`: Architecture documentation
  - `data-modeling.md`: Data modeling details
  - `setup-guide.md`: Installation and configuration
  - `testing.md`: Testing strategy and guidelines

### Writing Documentation

- Use clear, concise language
- Include code examples where helpful
- Use emojis and formatting for better readability
- Update existing documentation when making changes
- Add new documentation for significant features

### API Documentation

- FastAPI automatically generates OpenAPI documentation
- Add docstrings to API endpoints
- Include examples in endpoint descriptions

## 🔧 Development Workflow

### Local Development Setup

```bash
# 1. Install dependencies
make setup

# 2. Run pre-commit setup
uv run pre-commit install

# 3. Start development
make dev  # Launches Dagster UI
```

### Development Commands

```bash
# Run pipeline for testing
make pipeline

# Launch dashboard
make dashboard

# Run API server
make api

# Check code quality
make lint

# Run tests
make test

# Clean up (preserves history)
make clean

# Full cleanup
make deep-clean
```

### Debugging

- Use Dagster UI for pipeline debugging: `http://localhost:3000`
- Check logs in `.dagster_home/logs/`
- Use `make status` for pipeline health checks
- Enable verbose logging for detailed debugging

## 🚀 Release Process

### Versioning

We use semantic versioning:

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
- Increment MAJOR for breaking changes
- Increment MINOR for new features
- Increment PATCH for bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update changelog (if maintained)
3. Run full test suite: `make test`
4. Test pipeline end-to-end: `make start`
5. Create release on GitHub
6. Update documentation if needed

## 🤔 Getting Help

### Resources

- **Issues**: Search existing issues or create new ones
- **Documentation**: Check the `docs/` directory
- **Code comments**: Look for inline documentation

### Communication

- Use GitHub Issues for bug reports and feature requests
- Use GitHub Discussions for questions and general discussions
- Be respectful and constructive in all interactions

## 📋 Contribution Checklist

Before submitting a pull request, ensure:

- [ ] Code follows the project's style guidelines
- [ ] Self-review of the code is completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Corresponding changes to documentation have been made
- [ ] Changes generate no new warnings
- [ ] New and existing unit tests pass locally
- [ ] Any dependent changes have been merged and published

## 🙏 Recognition

Contributors will be recognized in:

- Project README (if significant contributions)
- Release notes
- Special thanks in documentation

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

**Thank you for contributing to the Crypto ELT Pipeline! 🎉**

For questions or discussions about contributing, please open an issue or join the discussion on GitHub.
