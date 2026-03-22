# `core.server`

`flipper_mcp.core.server.FlipperMCPServer` hosts the MCP server over stdio and delegates all tool calls to modules.

## Startup sequence (high level)

1. Create a `FlipperTransport` via `get_transport(...)`
2. Connect a `FlipperClient`
3. Discover and load modules via `ModuleRegistry`
4. Expose module tools via MCP `list_tools`
5. Route MCP `call_tool` to the owning module

## Stub mode

If the transport connection fails, the server enables a stub mode flag and forces `FlipperClient.connected = True` so that MCP clients can still list tools and exercise module logic. Hardware-backed operations may still fail depending on which APIs are used.





