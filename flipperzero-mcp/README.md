# Flipper Zero MCP Server

Modular Model Context Protocol (MCP) server for interacting with a Flipper Zero from MCP-capable clients (including Claude Desktop).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- Modular architecture: functionality is provided by modules under `src/flipper_mcp/modules/`
- Multiple transports: USB and WiFi are implemented; Bluetooth is present as a stub transport
- Protobuf RPC support (nanopb-delimited framing) with generated protobuf code committed in `src/flipper_mcp/core/protobuf_gen/`
- Built-in modules:
  - `systeminfo`: connection/device/SD-card status
  - `badusb`: generate, validate, store, and execute BadUSB scripts (requires SD card for file operations)
  - `music`: save/play songs using Flipper Music Format (FMF) (requires SD card)

## Documentation

- `docs/index.md`: documentation hub
- `docs/claude_setup.md`: Claude Desktop setup (kept up to date)
- `docs/wifi_dev_board.md`: **WiFi Dev Board setup, architecture, and protobuf RPC over WiFi**
- `firmware/tcp_uart_bridge/README.md`: WiFi Dev Board TCP↔UART bridge firmware (“flirmware”)
- `docs/modules/`: built-in module documentation
- `docs/core/`: core server documentation

## Installation

```bash
git clone https://github.com/busse/flipperzero-mcp.git
cd flipperzero-mcp
```

## Quick start

```bash
pip install -e .
flipper-mcp
```

The server communicates over stdio (MCP) and will auto-discover built-in modules at startup.

### Quick start with Claude Desktop (USB-only)

1. Connect your Flipper Zero via USB.
2. Add **one** MCP server entry to Claude Desktop config:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\\Claude\\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "flipper-zero": {
      "command": "python3",
      "args": ["-m", "flipper_mcp.cli.main"],
      "cwd": "/path/to/flipperzero-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "FLIPPER_TRANSPORT": "usb"
      }
    }
  }
}
```

3. Restart Claude Desktop and ask: “What tools do you have available?”

## Configuration

The CLI currently uses environment variables for configuration:

- `FLIPPER_TRANSPORT`: `auto` (default), `usb`, `wifi`, `bluetooth`/`ble`
- `FLIPPER_PORT`: override the USB serial device path (only used for `usb`)
- `FLIPPER_WIFI_HOST`: Flipper WiFi dev board host/IP (only used for `wifi`)
- `FLIPPER_WIFI_PORT`: Flipper WiFi dev board TCP port (only used for `wifi`)
- `FLIPPER_DEBUG`: enable protobuf RPC debug logging (`1`, `true`, `yes`, `on`)
- `FLIPPER_FORCE_START_RPC_SESSION`: force sending `start_rpc_session` on connect (`1`, `true`, `yes`, `on`)
- `FLIPPER_MCP_ALLOW_STUB_MODE`: **DEV ONLY**. If enabled (`1`, `true`, `yes`, `on`), the server will run in stub mode when it cannot connect to hardware. Default: disabled.

### Default behavior (recommended): one MCP config, USB-first with optional WiFi fallback

By default (`FLIPPER_TRANSPORT` unset), the server uses **auto mode**:

- It **tries USB first**
- If USB is not available and `FLIPPER_WIFI_HOST` is set, it **falls back to WiFi**

Examples:

```bash
# Use a specific USB port
export FLIPPER_TRANSPORT=usb
export FLIPPER_PORT=/dev/ttyACM0
flipper-mcp

# Use WiFi transport
export FLIPPER_TRANSPORT=wifi
export FLIPPER_WIFI_HOST=192.168.1.1
export FLIPPER_WIFI_PORT=8080
flipper-mcp

# Auto mode (default): try USB, fall back to WiFi if FLIPPER_WIFI_HOST is set
export FLIPPER_WIFI_HOST=192.168.1.100
export FLIPPER_WIFI_PORT=8080
flipper-mcp
```

## Using with Claude Desktop

See `docs/claude_setup.md`.

## Available tools (built-in)

### connection (health/recovery)

- `flipper_connection_health` (authoritative transport + protobuf-RPC health)
- `flipper_connection_reconnect` (disconnect/connect, then health)

### systeminfo

- `systeminfo_get`

### badusb

- `badusb_list`
- `badusb_read`
- `badusb_generate`
- `badusb_validate`
- `badusb_write`
- `badusb_delete`
- `badusb_diff`
- `badusb_rename`
- `badusb_execute` (requires `confirm=true`)
- `badusb_workflow`

### music

- `music_get_format`
- `music_play`

## Contributing

We welcome contributions! This project is **pro-AI-assisted coding and engineering** - we encourage and welcome contributions that leverage AI tools like Claude Code, GitHub Copilot, ChatGPT, Cursor, or any other AI coding assistants. If you used AI assistance in your contribution, that's great! Please mention it in your pull request.

See `CONTRIBUTING.md` and `docs/module_development.md`.

## License

MIT License - see `LICENSE`.
