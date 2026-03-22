#!/usr/bin/env python3
"""Test script to verify Flipper Zero connection and basic operations.

This script tests:
1. USB port detection (especially on macOS)
2. Connection establishment
3. Reading device info
4. Listing files from device storage
"""

import asyncio
import sys
import os
from pathlib import Path

# Try to import directly - if package is installed, this will work
try:
    # Import the transport factory which doesn't require mcp
    from flipper_mcp.core.transport.usb import USBTransport
    from flipper_mcp.core.flipper_client import FlipperClient
except ImportError:
    # Fallback: add src to path and import with modified sys.path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    # Import core modules directly (they don't depend on mcp)
    from flipper_mcp.core.transport.usb import USBTransport
    from flipper_mcp.core.flipper_client import FlipperClient


async def test_connection():
    """Test Flipper Zero connection and basic operations."""
    
    print("=" * 60)
    print("Flipper Zero Connection Test")
    print("=" * 60)
    print()
    
    # Configuration
    port_override = os.environ.get("FLIPPER_PORT")
    config = {
        "transport": {
            "type": "usb",
            "usb": {
                **({"port": port_override} if port_override else {}),
                "baudrate": 115200,
                "timeout": 2.0
            }
        }
    }
    
    # Step 1: Create transport
    print("Step 1: Creating USB transport...")
    try:
        usb_config = config.get("transport", {}).get("usb", {})
        transport = USBTransport(usb_config)
        print(f"   ✓ Transport created")
        print(f"   Port: {transport.port}")
    except Exception as e:
        print(f"   ❌ Failed to create transport: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Create client and connect
    print("\nStep 2: Connecting to Flipper Zero...")
    client = FlipperClient(transport)
    
    try:
        connected = await client.connect()
        if not connected:
            print("   ❌ Failed to connect to Flipper Zero")
            print()
            print("   Troubleshooting:")
            print("     - Make sure Flipper Zero is connected via USB")
            print("     - Make sure device is powered on")
            print("     - Close other applications using the serial port:")
            print("       * qFlipper")
            print("       * Flipper CLI tools")
            print("       * Serial terminal applications")
            print()
            print("   To check what's using the port, run:")
            print(f"     lsof {transport.port}")
            return False
        
        print("   ✓ Connected to Flipper Zero")
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False
    
    # Step 3: Get device info
    print("\nStep 3: Reading device information...")
    try:
        device_info = await client.get_device_info()
        print(f"   ✓ Device Info:")
        print(f"     Name: {device_info.get('name', 'Unknown')}")
        print(f"     Hardware: {device_info.get('hardware', 'Unknown')}")
        print(f"     Firmware: {device_info.get('firmware', 'Unknown')}")
    except Exception as e:
        print(f"   ⚠️  Could not read device info: {e}")
        print("   (This is okay - device is still connected)")
    
    # Step 4: Test storage operations
    print("\nStep 4: Testing storage operations...")
    
    # Test listing root directory
    print("   Testing: List /ext directory...")
    try:
        files = await client.storage.list("/ext")
        if files:
            print(f"   ✓ Found {len(files)} items in /ext:")
            for f in files[:10]:  # Show first 10
                print(f"     - {f}")
            if len(files) > 10:
                print(f"     ... and {len(files) - 10} more")
        else:
            print("   ⚠️  No files found (directory may be empty or path incorrect)")
    except Exception as e:
        print(f"   ⚠️  Error listing files: {e}")
        print("   (This may be normal if RPC protocol is not fully implemented)")
    
    # Test listing badusb directory
    print("\n   Testing: List /ext/badusb directory...")
    try:
        files = await client.storage.list("/ext/badusb")
        if files:
            print(f"   ✓ Found {len(files)} BadUSB scripts:")
            for f in files[:10]:
                print(f"     - {f}")
        else:
            print("   ⚠️  No BadUSB scripts found")
    except Exception as e:
        print(f"   ⚠️  Error listing BadUSB files: {e}")
    
    # Step 5: Cleanup
    print("\nStep 5: Disconnecting...")
    try:
        await client.disconnect()
        print("   ✓ Disconnected")
    except Exception as e:
        print(f"   ⚠️  Error during disconnect: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_connection())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

