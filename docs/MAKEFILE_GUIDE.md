# Makefile Quick Reference

This project uses a Makefile for common operations, similar to npm scripts.

## Quick Start

```bash
# See all available commands
make help

# First-time setup
make setup              # Install deps + create .env

# Test your setup
make test-connection    # Quick connectivity check
```

## Common Workflows

### 1. Development Workflow

```bash
# Format your code
make format

# Run linters
make lint

# Run tests
make test

# All checks at once (like CI)
make ci
```

### 2. Testing Before Processing

```bash
# Preview what would happen (5 submissions)
make preview-5

# Preview more submissions
make preview-10

# Custom dry run
make dry-run LIMIT=20
```

### 3. Processing Data

```bash
# Process small batch
make process-10

# Process medium batch
make process-50

# Process everything (with confirmation)
make full-run
```

### 4. Custom Commands

```bash
# Custom arguments
make attach-products ARGS="--limit 100 --report my_report.csv"

# Different profile
make attach-products ARGS="--profile aggressive --no-confirm"

# Specific limit with dry-run
make dry-run LIMIT=50
```

## Command Reference

### Setup Commands

| Command | Description |
|---------|-------------|
| `make install` | Install production dependencies |
| `make install-dev` | Install development dependencies |
| `make setup` | Full setup (deps + .env) |

### Development Commands

| Command | Description |
|---------|-------------|
| `make test` | Run tests with coverage |
| `make lint` | Run ruff + mypy |
| `make format` | Format code with ruff |
| `make type-check` | Run mypy only |
| `make clean` | Remove generated files |
| `make ci` | Run all checks (format, lint, test) |

### Testing Commands

| Command | Description |
|---------|-------------|
| `make test-connection` | Test MongoDB + Pipedrive |
| `make preview-5` | Preview 5 submissions (dry-run) |
| `make preview-10` | Preview 10 submissions (dry-run) |
| `make dry-run LIMIT=N` | Preview N submissions |

### Processing Commands

| Command | Description |
|---------|-------------|
| `make process-10` | Process 10 submissions |
| `make process-50` | Process 50 submissions |
| `make full-run` | Process all (with confirmation) |

### Profile Commands

| Command | Description |
|---------|-------------|
| `make profile-conservative` | Test conservative profile |
| `make profile-aggressive` | Test aggressive profile |
| `make profile-migration` | Test migration profile |

### Utility Commands

| Command | Description |
|---------|-------------|
| `make report` | Generate test report |
| `make clean-reports` | Clean old reports |
| `make logs` | Show recent logs |
| `make validate` | Validate configuration |

## Variables

You can pass variables to make commands:

```bash
# Custom limit for dry-run
make dry-run LIMIT=100

# Custom arguments for attach-products
make attach-products ARGS="--verbose --limit 50"
```

## Examples

### Development Cycle

```bash
# 1. Make changes to code
vim src/product_linker.py

# 2. Format
make format

# 3. Check types
make type-check

# 4. Run tests
make test

# 5. Test with real data
make preview-5
```

### First Time Processing

```bash
# 1. Setup
make setup
nano .env  # Edit credentials

# 2. Test connection
make test-connection

# 3. Preview
make preview-10

# 4. Process small batch
make process-10

# 5. Check results in Pipedrive
# ...

# 6. Process all
make full-run
```

### Daily Operations

```bash
# Morning: Check what needs processing
make preview-10

# Process batch
make process-50

# Check reports
ls -la reports/
```

### Troubleshooting

```bash
# Verbose dry run
make attach-products ARGS="--dry-run --limit 5 --verbose"

# Validate config
make validate

# Check logs
make logs
```

## Tips

### Use Tab Completion

```bash
make <TAB><TAB>    # See all available commands
```

### Chain Commands

```bash
# Format, lint, and test
make format lint test

# Setup and test
make setup test-connection
```

### Color Output

The Makefile uses colored output:
- 🟦 **Cyan**: Info messages
- 🟩 **Green**: Success messages
- 🟨 **Yellow**: Warning messages

## Comparison to npm scripts

If you're used to npm, here's the mapping:

| npm | make |
|-----|------|
| `npm install` | `make install` |
| `npm run dev` | `make dry-run` |
| `npm test` | `make test` |
| `npm run lint` | `make lint` |
| `npm run format` | `make format` |
| `npm run build` | _N/A_ |
| `npm start` | `make full-run` |

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run checks
  run: make ci

- name: Validate config
  run: make validate
```

```groovy
// Jenkins example
stage('Test') {
    steps {
        sh 'make ci'
    }
}
```

## Creating Your Own Commands

Add to Makefile:

```makefile
my-custom-command:
	@echo "Running custom command..."
	python -m src.main attach-products --custom-args

.PHONY: my-custom-command  # Add to .PHONY at top
```

Then use:

```bash
make my-custom-command
```

## Help

```bash
# Always available
make help

# Or just
make
```