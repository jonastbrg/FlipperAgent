#!/usr/bin/env python3
"""Flipper Zero storage operations — list, read, write, mkdir, info.

Outputs structured JSON to stdout, logs to stderr.

Usage:
    python3 scripts/flipper_storage.py list /ext
    python3 scripts/flipper_storage.py list /ext/subghz
    python3 scripts/flipper_storage.py read /ext/subghz/signal.sub
    python3 scripts/flipper_storage.py write /ext/test.txt "Hello Flipper"
    python3 scripts/flipper_storage.py mkdir /ext/my_dir
    python3 scripts/flipper_storage.py info /ext
"""

import argparse
import asyncio
import json
import os
import sys

# Ensure the MCP library is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'flipperzero-mcp', 'src'))


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _build_config() -> dict:
    """Build transport config from environment."""
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


def _validate_path(path: str) -> None:
    """Basic safety validation for Flipper paths."""
    if not path:
        raise ValueError("Path is empty")
    if ".." in path:
        raise ValueError("Path traversal ('..') not allowed")
    blocked_prefixes = ["/int/"]
    blocked_suffixes = [".key", ".priv", ".secret"]
    p = path.rstrip("/")
    if p == "/int":
        raise ValueError("Internal storage is blocked")
    if any(path.startswith(pfx) for pfx in blocked_prefixes):
        raise ValueError(f"Path '{path}' is blocked (protected system path)")
    if any(path.endswith(sfx) for sfx in blocked_suffixes):
        raise ValueError(f"Path '{path}' is blocked (sensitive file extension)")


async def _connect():
    """Connect to Flipper and return client."""
    from flipper_mcp.core.transport import get_transport
    from flipper_mcp.core.flipper_client import FlipperClient

    config = _build_config()
    transport_type = config["transport"]["type"]
    transport = get_transport(transport_type, config)
    client = FlipperClient(transport)

    if not await client.connect():
        raise ConnectionError("Failed to connect to Flipper Zero")

    return client


async def _cmd_list(args: argparse.Namespace) -> int:
    path = args.path or "/ext"
    _log(f"Listing {path}...")
    client = await _connect()
    try:
        files = await client.storage.list(path)
        result = {"path": path, "entries": files if files else []}
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "path": path}))
        return 1
    finally:
        await client.disconnect()


async def _cmd_read(args: argparse.Namespace) -> int:
    path = args.path
    _validate_path(path)
    _log(f"Reading {path}...")
    client = await _connect()
    try:
        content = await client.storage.read(path)
        result = {"path": path, "content": content or "", "size": len(content or "")}
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "path": path}))
        return 1
    finally:
        await client.disconnect()


async def _cmd_write(args: argparse.Namespace) -> int:
    path = args.path
    content = args.content
    _validate_path(path)

    # Read content from stdin if "-" is specified
    if content == "-":
        content = sys.stdin.read()

    _log(f"Writing {len(content)} bytes to {path}...")
    client = await _connect()
    try:
        ok = await client.storage.write(path, content)
        result = {"path": path, "written": ok, "size": len(content)}
        print(json.dumps(result, indent=2))
        return 0 if ok else 1
    except Exception as e:
        print(json.dumps({"error": str(e), "path": path}))
        return 1
    finally:
        await client.disconnect()


async def _cmd_mkdir(args: argparse.Namespace) -> int:
    path = args.path
    _log(f"Creating directory {path}...")
    client = await _connect()
    try:
        ok = await client.storage.mkdir(path)
        result = {"path": path, "created": ok}
        print(json.dumps(result, indent=2))
        return 0 if ok else 1
    except Exception as e:
        print(json.dumps({"error": str(e), "path": path}))
        return 1
    finally:
        await client.disconnect()


async def _cmd_info(args: argparse.Namespace) -> int:
    path = args.path or "/ext"
    _log(f"Getting storage info for {path}...")
    client = await _connect()
    try:
        # storage.info may not exist on all FlipperClient versions; fall back
        if hasattr(client.storage, 'info'):
            info = await client.storage.info(path)
        elif client.rpc and hasattr(client.rpc, 'storage_info'):
            info = await client.rpc.storage_info(path)
        else:
            info = None

        if info:
            total = info.get("total_space", 0)
            free = info.get("free_space", 0)
            result = {
                "path": path,
                "total_bytes": total,
                "free_bytes": free,
                "used_bytes": total - free,
                "total_mb": total // (1024 * 1024),
                "free_mb": free // (1024 * 1024),
            }
        else:
            result = {"path": path, "error": "Storage info unavailable"}

        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "path": path}))
        return 1
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Flipper Zero storage operations")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = sub.add_parser("list", help="List directory contents")
    p_list.add_argument("path", nargs="?", default="/ext", help="Directory path (default: /ext)")

    # read
    p_read = sub.add_parser("read", help="Read a file")
    p_read.add_argument("path", help="File path to read")

    # write
    p_write = sub.add_parser("write", help="Write content to a file")
    p_write.add_argument("path", help="File path to write")
    p_write.add_argument("content", help='Content to write (use "-" for stdin)')

    # mkdir
    p_mkdir = sub.add_parser("mkdir", help="Create a directory")
    p_mkdir.add_argument("path", help="Directory path to create")

    # info
    p_info = sub.add_parser("info", help="Get storage usage info")
    p_info.add_argument("path", nargs="?", default="/ext", help="Storage path (default: /ext)")

    args = parser.parse_args()

    dispatch = {
        "list": _cmd_list,
        "read": _cmd_read,
        "write": _cmd_write,
        "mkdir": _cmd_mkdir,
        "info": _cmd_info,
    }

    rc = asyncio.run(dispatch[args.subcommand](args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
