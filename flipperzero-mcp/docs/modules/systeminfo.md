# `systeminfo` module

The `systeminfo` module provides a single tool for retrieving connection, device, and storage status.

## Tools

### `systeminfo_get`

Returns:

- connection status
- device info (best-effort via RPC)
- transport details (USB port / WiFi host when available)
- MicroSD card availability (best-effort)

Notes:

- This tool is intended to be safe to call at any time.
- It does not require an SD card, but it does report SD card status.





