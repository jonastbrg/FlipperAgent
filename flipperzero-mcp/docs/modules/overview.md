# Modules

Modules are the unit of functionality in this MCP server. Each module registers one or more MCP tools and handles tool execution.

## Where modules live

Built-in modules are under:

- `src/flipper_mcp/modules/`

Each module is a Python package containing a `module.py` file.

## Discovery and loading

`flipper_mcp.core.registry.ModuleRegistry`:

- scans `flipper_mcp.modules` for subpackages
- imports `<module_package>.module`
- finds concrete `FlipperModule` subclasses
- instantiates them with a `FlipperClient`
- calls `on_load()` during server initialization

## Conventions

- **Tool naming**: `{module}_{action}` (e.g. `badusb_generate`)
- **Safety**: dangerous operations should require an explicit confirmation parameter (e.g. `confirm=true`)
- **SD card**: modules that write to `/ext/*` should check SD card availability and provide actionable error messages





