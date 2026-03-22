# `core.transport`

Transports implement the byte-oriented connection to the Flipper device.

## Implementations

- `AutoTransport`: selects a transport at runtime (USB-first, WiFi fallback when configured)
- `USBTransport`: serial over USB CDC (auto-detects Flipper VID:PID when possible)
- `WiFiTransport`: TCP socket transport (host/port are configured via the server config dict)
- `BluetoothTransport`: stub transport (not implemented)

## Selecting a transport

The default server entry point (`flipper_mcp.core.server.main`) reads environment variables and builds a config dict.

- `FLIPPER_TRANSPORT`: `auto` (default), `usb`, `wifi`, `bluetooth`/`ble`
- `FLIPPER_PORT`: USB serial device path override (only used for `usb`)
- `FLIPPER_WIFI_HOST`: WiFi Dev Board host/IP (only used for `wifi`, or when `auto` falls back)
- `FLIPPER_WIFI_PORT`: WiFi Dev Board TCP port (only used for `wifi`, or when `auto` falls back)

### AutoTransport policy (recommended)

Auto mode is designed so you can keep a **single** MCP client config:

- Try **USB** first
- If USB fails, only try **WiFi** if a host was explicitly configured (`FLIPPER_WIFI_HOST` set)

## Per-transport config knobs

These are provided via the server config dict (see `src/flipper_mcp/core/server.py`).

### USBTransport

- `port` (string): device path (auto-detected when absent)
- `baudrate` (int): defaults to 115200
- `timeout` (float): serial read timeout (seconds)

### WiFiTransport

- `host` (string): required in practice (auto will not consider WiFi configured without it)
- `port` (int): defaults to 8080
- `connect_timeout` (float): defaults to 3.0 seconds
- `read_chunk_size` (int): defaults to 4096 bytes

## Framing support

`FlipperTransport` provides:

- `receive_exact(n, timeout)` for framed protocols (like protobuf delimited framing)
- a receive buffer (`_rx_buffer`) and `clear_receive_buffer()`




