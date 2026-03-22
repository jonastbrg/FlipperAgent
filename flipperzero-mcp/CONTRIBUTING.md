# Contributing to Flipper Zero MCP

Thank you for your interest in contributing to Flipper Zero MCP! This guide will help you get started.

## AI-Assisted Coding

This project is **pro-AI-assisted coding and engineering** - we encourage and welcome contributions that leverage AI tools like Claude Code, GitHub Copilot, ChatGPT, Cursor, or any other AI coding assistants. If you used AI assistance in your contribution, that's great! Please mention it in your pull request.

AI tools can be particularly helpful for:
- Generating boilerplate code for new modules
- Writing tests and test fixtures
- Refactoring and code improvements
- Documentation and docstring generation
- Debugging and error handling patterns

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Creating Modules](#creating-modules)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Keep discussions professional

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- Basic understanding of async Python
- Familiarity with Flipper Zero (helpful but not required)

### Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR-USERNAME/flipperzero-mcp.git
cd flipperzero-mcp

# Add upstream remote
git remote add upstream https://github.com/busse/flipperzero-mcp.git
```

## Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements.txt
```

## Creating Modules

### Module Structure

```
src/flipper_mcp/modules/mymodule/
├── __init__.py          # Export your module
├── module.py            # Main module implementation
├── helper.py            # Optional helper functions
└── templates/           # Optional templates
    └── example.py
```

### Module Template

```python
from typing import List, Any, Sequence
from mcp.types import Tool, TextContent
from ..base_module import FlipperModule

class MyModule(FlipperModule):
    """
    Brief description of your module.
    
    Features:
    - Feature 1
    - Feature 2
    """
    
    @property
    def name(self) -> str:
        """Unique module name (lowercase, no spaces)."""
        return "mymodule"
    
    @property
    def version(self) -> str:
        """Semantic version (major.minor.patch)."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """One-line description."""
        return "Does something awesome with Flipper Zero"
    
    def get_tools(self) -> List[Tool]:
        """Define MCP tools this module provides."""
        return [
            Tool(
                name="mymodule_action",
                description="Clear description of what this does",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "What this parameter does"
                        }
                    },
                    "required": ["param1"]
                }
            )
        ]
    
    async def handle_tool_call(
        self, tool_name: str, arguments: Any
    ) -> Sequence[TextContent]:
        """Handle tool execution."""
        if tool_name == "mymodule_action":
            # Your implementation here
            result = f"Did something with {arguments['param1']}"
            return [TextContent(type="text", text=result)]
        
        return [TextContent(
            type="text",
            text=f"Unknown tool: {tool_name}"
        )]
    
    def validate_environment(self) -> tuple[bool, str]:
        """Check if module can run."""
        # Optional: check firmware version, etc.
        return True, ""
```

### Module Best Practices

1. **Naming Convention**
   - Module names: lowercase, descriptive (e.g., `badusb`, `subghz`)
   - Tool names: `{module}_{action}` (e.g., `badusb_generate`)

2. **Documentation**
   - Clear docstrings for all classes and methods
   - Include usage examples
   - Document parameters and return values

3. **Error Handling**
   - Use try/except blocks
   - Return meaningful error messages
   - Never crash the entire server

4. **Safety**
   - Validate all inputs
   - Implement safety checks for dangerous operations
   - Use confirmation flags for destructive actions

5. **Testing**
   - Write unit tests for your module
   - Include integration tests if possible
   - Test error conditions

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=flipper_mcp

# Run specific test file
pytest tests/modules/test_mymodule.py

# Run with verbose output
pytest -v
```

### Writing Tests

```python
# tests/modules/test_mymodule.py

import pytest
from unittest.mock import Mock, AsyncMock
from flipper_mcp.modules.mymodule import MyModule

@pytest.fixture
def mock_flipper():
    """Create mock Flipper client."""
    client = Mock()
    client.storage = Mock()
    client.storage.read = AsyncMock(return_value="test data")
    return client

@pytest.mark.asyncio
async def test_mymodule_action(mock_flipper):
    """Test module action."""
    module = MyModule(mock_flipper)
    
    result = await module.handle_tool_call(
        "mymodule_action",
        {"param1": "test"}
    )
    
    assert len(result) == 1
    assert "test" in result[0].text
```

## Pull Request Process

### Before Submitting

1. **Update your fork**
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-module
   ```

3. **Make your changes**
   - Follow coding standards
   - Add tests
   - Update documentation

4. **Run tests**
   ```bash
   pytest
   black src/
   ruff check src/
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add MyModule for XYZ functionality"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/my-new-module
   ```

### Submitting PR

1. Go to GitHub and create a Pull Request
2. Fill out the PR template
3. Link any related issues
4. Wait for review

### PR Requirements

- [ ] Code follows project style
- [ ] Tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages are clear

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

```python
# Use Black formatter
black src/

# Use Ruff for linting
ruff check src/

# Type hints everywhere
def my_function(param: str) -> bool:
    return True
```

### Code Organization

```python
# Imports order:
# 1. Standard library
# 2. Third-party
# 3. Local

import asyncio
from typing import Any

from mcp.types import Tool

from ..base_module import FlipperModule
```

### Documentation Style

```python
def function(param: str) -> bool:
    """
    One-line summary.
    
    Longer description if needed.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When this happens
    """
    pass
```

## Module Submission Checklist

Before submitting a new module:

- [ ] Module follows naming conventions
- [ ] All tools use `{module}_{action}` naming
- [ ] Comprehensive docstrings
- [ ] Input validation implemented
- [ ] Safety checks for dangerous operations
- [ ] Unit tests written
- [ ] Integration tests (if applicable)
- [ ] README section added
- [ ] Example usage documented
- [ ] No external dependencies (or documented)

## Getting Help

- 💬 [GitHub Discussions](https://github.com/busse/flipperzero-mcp/discussions)
- 🐛 [Issue Tracker](https://github.com/busse/flipperzero-mcp/issues)
- 📧 Create an issue for questions

## Recognition

Contributors will be:
- Listed in README
- Credited in release notes
- Given credit in module documentation

Thank you for contributing! 🎉
