# `core.registry`

`flipper_mcp.core.registry.ModuleRegistry` is responsible for discovering, instantiating, loading, and unloading modules.

## Discovery rules

- Modules must be subpackages of `flipper_mcp.modules`
- Each module package must contain a `module.py` file
- The registry imports `<package>.module` and looks for concrete `FlipperModule` subclasses

## Lifecycle

- `discover_modules()` registers module instances
- `load_all()` calls `module.on_load()` for each module in registration order
- `unload_all()` calls `module.on_unload()` in reverse order





