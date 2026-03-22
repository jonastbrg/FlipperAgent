# Contributing to FlipperAgent

Thanks for your interest in contributing. FlipperAgent is an open-source autonomous red team agent and we welcome contributions -- new tool modules, skills, bug fixes, documentation, and tests.

## Getting Started

### Prerequisites

| Requirement | Install | Notes |
|---|---|---|
| Python 3.10+ | `brew install python@3.12` | Pre-installed on macOS |
| Flipper Zero | [shop.flipperzero.one](https://shop.flipperzero.one) | USB-C connection, for hardware testing |
| jq | `brew install jq` | Required for ralph-loop skill |

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/FlipperAgent.git
cd FlipperAgent

# Set up the MCP server
cd flipperzero-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install bleak

# Run tests (no hardware required)
pytest

# Run with stub mode (no Flipper needed for development)
FLIPPER_MCP_ALLOW_STUB_MODE=1 python -m flipper_mcp.cli.main
```

### Running Tests

```bash
cd flipperzero-mcp

# All tests
pytest

# With coverage
pytest --cov=flipper_mcp --cov-report=term-missing

# Specific module
pytest tests/modules/test_badusb.py

# Integration tests (requires hardware)
pytest tests/integration/ -v
```

## Development Guidelines

### Module Pattern

Every MCP tool module follows the same structure:

```
flipperzero-mcp/src/flipper_mcp/modules/your_module/
  __init__.py     # exports the module class
  module.py       # FlipperModule subclass with tool definitions
```

Each module:

1. Subclasses `FlipperModule` from `core/registry.py`
2. Defines tools via `get_tools()` returning a list of `mcp.types.Tool` objects
3. Handles tool calls in `handle_tool_call(name, arguments)`
4. Uses `CLIBridge.run_cli()` for Flipper CLI commands
5. Uses `ProtobufRPC` for protobuf-based operations
6. Classifies risk for each tool (add entries to `core/risk.py:TOOL_RISK_MAP`)

### Risk Classification

Every new tool must have an entry in `TOOL_RISK_MAP` in `core/risk.py`:

| Level | Criteria | Examples |
|-------|----------|---------|
| **LOW** | Read-only, no RF emission, no external state change | Scanning, reading, listing, querying |
| **MEDIUM** | Local state change, limited-range output, active probing | Writing files, GPIO output, IR transmit |
| **HIGH** | RF transmission, device control, credential testing, HID injection | Sub-GHz TX, BLE write, BadUSB execute |
| **BLOCKED** | Never allow automatically | Reserved for path validation only |

### CLI Input Safety

If your module sends commands to the Flipper CLI:

- Always use `CLIBridge.run_cli(command)` -- never write directly to the transport
- CLI input is automatically sanitized (shell metacharacters stripped)
- Handle `CLICommandError` for Flipper-reported errors
- Handle `asyncio.TimeoutError` for commands that take too long

### Code Style

- Follow PEP 8 and the project's existing patterns
- Use `black` for formatting (line length 100)
- Use `ruff` for linting
- Use type annotations (enforced by `mypy`)
- Keep functions focused -- one function, one responsibility
- Docstrings on all public methods

```bash
# Format and lint
black src/ tests/
ruff check src/ tests/
mypy src/
```

### Commit Messages

Write clear, imperative-mood commit messages:

```
Add NFC tag cloning support to nfc module

Implements nfc_clone tool that reads a tag and writes its data to a
blank tag. Adds MEDIUM risk classification. Includes unit tests for
data format validation.
```

## What to Contribute

### High-Value Contributions

- **New tool modules** -- e.g., MouseJacker (NRF24), Marauder WiFi scanner integration, packet crafting
- **Skills** -- methodology guides for new attack categories (e.g., Zigbee, Z-Wave, CAN bus)
- **CLI command fixes** -- some Flipper CLI commands have firmware-version-specific syntax; fixes for SubGHz, NFC, and RFID commands are especially welcome
- **Transport backends** -- WiFi and Bluetooth transports need testing and hardening
- **Test coverage** -- unit tests for modules, integration tests for hardware operations

### Bug Fixes Welcome

- SubGHz CLI syntax mismatch on firmware 1.4.3
- RFID CLI command (`lfrfid` vs `rfid`)
- NFC field returning ASCII art instead of structured data
- CLI bridge RPC re-entry failures after long-running commands

### Documentation

- Flipper firmware version compatibility tables
- Protocol-specific attack guides
- Hardware setup guides for ESP32 Marauder and NRF24

## Submitting Changes

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement** your changes following the guidelines above

3. **Test** your changes:
   - Run `pytest` for unit tests
   - If adding a tool: add a risk classification entry and at least one test
   - If touching hardware interaction: test with a real Flipper if possible

4. **Push** your branch and open a Pull Request against `main`

5. **In the PR description**, include:
   - What the change does and why
   - How you tested it (stub mode, real hardware, or both)
   - Risk classification for any new tools
   - Screenshots or logs if relevant

### PR Guidelines

- One feature or fix per PR
- Keep PRs focused and reviewable (under 500 lines when possible)
- Do not commit API keys, credentials, or secrets
- Do not commit `findings/`, `campaigns/`, or `engagement_state.json` (these are gitignored)
- Reference related issues (e.g., "Closes #42")

## Reporting Bugs

Open a GitHub issue with:

- Steps to reproduce
- Expected vs actual behavior
- Flipper firmware version and OS
- Relevant tool output or error messages
- Whether using USB, WiFi, or stub mode

## Code of Conduct

Be respectful and constructive. We are building security tools for authorized research -- act accordingly. Harassment, trolling, and sharing of unauthorized attack data will not be tolerated.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](../LICENSE).
