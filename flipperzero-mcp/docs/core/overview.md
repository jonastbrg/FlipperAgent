# Core package

The core server implementation lives under `src/flipper_mcp/core/`.

Key responsibilities:

- run an MCP server over stdio (`core/server.py`)
- discover and load modules (`core/registry.py`)
- connect to Flipper via a transport (`core/transport/`)
- provide an RPC client stack (`core/flipper_client.py`, `core/rpc.py`, `core/protobuf_rpc.py`)

See:

- `server.md`
- `registry.md`
- `transports.md`
- `rpc.md`





