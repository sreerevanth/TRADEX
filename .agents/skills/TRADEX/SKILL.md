```markdown
# TRADEX Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the TRADEX Python codebase. You'll learn how to structure files, write and organize code, follow commit message standards, and implement and run tests according to repository best practices.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `trade_engine.py`, `order_manager.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import calculate_fee
    from ..models import Trade
    ```

### Export Style
- Use **named exports** (explicitly define what is exported from a module).
  - Example:
    ```python
    __all__ = ['TradeEngine', 'OrderManager']
    ```

### Commit Messages
- Use **conventional commit** format.
- Prefix with `feat` for new features.
  - Example:
    ```
    feat: add order matching logic to trade engine
    ```

## Workflows

### Feature Development
**Trigger:** When adding a new feature or module  
**Command:** `/feature-dev`

1. Create a new Python file using snake_case naming.
2. Implement the feature using relative imports as needed.
3. Define `__all__` in the module for named exports.
4. Write or update associated test files (see Testing Patterns).
5. Commit changes using the conventional commit format:
    ```
    feat: <short description of the feature>
    ```

### Testing
**Trigger:** When verifying code correctness  
**Command:** `/run-tests`

1. Locate or create test files following the `*.test.*` naming pattern.
2. Write tests for new or updated features.
3. Run tests using your preferred Python test runner (framework is unspecified).
4. Review and fix any failing tests.

## Testing Patterns

- Test files follow the `*.test.*` naming convention.
  - Example: `trade_engine.test.py`
- The specific test framework is not enforced; use standard Python testing practices.
- Place tests alongside the code or in a dedicated test directory as appropriate.

Example test file:
```python
# trade_engine.test.py

from .trade_engine import TradeEngine

def test_order_matching():
    engine = TradeEngine()
    # ... test logic ...
    assert engine.match_orders() == expected_result
```

## Commands
| Command         | Purpose                               |
|-----------------|---------------------------------------|
| /feature-dev    | Start a new feature development cycle  |
| /run-tests      | Run all tests in the codebase         |
```
