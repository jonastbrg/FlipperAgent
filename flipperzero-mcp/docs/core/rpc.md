# RPC stack

The core client stack is layered:

- `FlipperClient` owns the connection and exposes high-level helpers (`storage`, `app`)
- `FlipperRPC` provides best-effort operations and prefers protobuf RPC when available
- `ProtobufRPC` implements nanopb-delimited protobuf framing and RPC session negotiation

## Storage operations

`FlipperClient.storage` calls through to `FlipperRPC` methods such as:

- `storage_list`
- `storage_read`
- `storage_write`
- `storage_delete`
- `storage_mkdir`
- `storage_info`

## App launching

`FlipperClient.app.launch(...)` exists for module ergonomics, but is currently a stub that returns `True`.





