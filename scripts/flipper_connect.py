#!/usr/bin/env python3
"""Connect to Flipper Zero, run a CLI command or return device info.

Usage:
    python3 scripts/flipper_connect.py                  # device info (JSON)
    python3 scripts/flipper_connect.py info              # device info (JSON)
    python3 scripts/flipper_connect.py cli <command...>  # run CLI command, print result

Outputs structured JSON to stdout, logs to stderr.
"""

import argparse
import asyncio
import json
import os
import sys

# Ensure the MCP library is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flipperzero-mcp', 'src'))

from flipper_mcp.core.server import FlipperMCPServer


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _build_config() -> dict:
    """Build transport config from environment, matching the MCP server defaults."""
    env_transport = os.environ.get("FLIPPER_TRANSPORT")
    env_port = os.environ.get("FLIPPER_PORT")
    env_wifi_host = os.environ.get("FLIPPER_WIFI_HOST")
    env_wifi_port = os.environ.get("FLIPPER_WIFI_PORT")
    return {
        "transport": {
            "type": env_transport or "auto",
            "usb": {
                **({"port": env_port} if env_port else {}),
                "baudrate": 115200,
            },
            "wifi": {
                **({"host": env_wifi_host} if env_wifi_host else {}),
                "port": int(env_wifi_port) if env_wifi_port else 8080,
            },
            "bluetooth": {"address": None},
        },
    }


async def _run(args: argparse.Namespace) -> int:
    config = _build_config()
    server = FlipperMCPServer(config)

    _log("Connecting to Flipper Zero...")
    # Initialize just the client, not the full MCP stdio server
    from flipper_mcp.core.transport import get_transport
    from flipper_mcp.core.flipper_client import FlipperClient

    transport_type = config["transport"]["type"]
    transport = get_transport(transport_type, config)
    client = FlipperClient(transport)

    if not await client.connect():
        _log("ERROR: Failed to connect to Flipper Zero")
        print(json.dumps({"error": "Failed to connect to Flipper Zero"}))
        return 1

    _log("Connected.")

    try:
        if args.subcommand == "cli":
            cmd = " ".join(args.command)
            _log(f"Running CLI command: {cmd}")
            result = await client.run_cli(cmd)
            print(json.dumps({"command": cmd, "result": result}))
        else:
            # Default: device info
            info = await client.get_device_info()
            print(json.dumps(info, indent=2))
    finally:
        await client.disconnect()
        _log("Disconnected.")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect to Flipper Zero and run commands"
    )
    sub = parser.add_subparsers(dest="subcommand")

    # info subcommand (default)
    sub.add_parser("info", help="Get device info (default)")

    # cli subcommand
    cli_parser = sub.add_parser("cli", help="Run a CLI command on the Flipper")
    cli_parser.add_argument("command", nargs="+", help="CLI command to execute")

    args = parser.parse_args()

    # Default to info if no subcommand given
    if args.subcommand is None:
        args.subcommand = "info"

    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
