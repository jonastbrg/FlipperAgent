#!/usr/bin/env python3
"""Test script for SystemInfo module.

This script tests the systeminfo module by:
1. Setting up a Flipper client (with optional real connection)
2. Instantiating the SystemInfoModule
3. Calling the systeminfo_get tool
4. Displaying the results
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from flipper_mcp.modules.systeminfo import SystemInfoModule
from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport


async def test_systeminfo_module():
    """Test the SystemInfo module."""
    
    print("=" * 60)
    print("SystemInfo Module Test")
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
    
    # Step 1: Create transport and client
    print("Step 1: Setting up Flipper client...")
    try:
        usb_config = config.get("transport", {}).get("usb", {})
        transport = USBTransport(usb_config)
        client = FlipperClient(transport)
        print(f"   ✓ Client created")
        print(f"   Port: {transport.port}")
    except Exception as e:
        print(f"   ❌ Failed to create client: {e}")
        return False
    
    # Step 2: Try to connect (optional - module works even if not connected)
    print("\nStep 2: Attempting connection...")
    try:
        connected = await client.connect()
        if connected:
            print("   ✓ Connected to Flipper Zero")
        else:
            print("   ⚠️  Not connected (will test in stub mode)")
            client.connected = True  # Enable stub mode for testing
    except Exception as e:
        print(f"   ⚠️  Connection failed: {e}")
        print("   (Continuing in stub mode for testing)")
        client.connected = True  # Enable stub mode
    
    # Step 3: Create and test module
    print("\nStep 3: Testing SystemInfo module...")
    try:
        module = SystemInfoModule(client)
        print(f"   ✓ Module created: {module.name} v{module.version}")
        
        # Get tools
        tools = module.get_tools()
        print(f"   ✓ Module has {len(tools)} tool(s):")
        for tool in tools:
            print(f"     - {tool.name}")
        
        # Call the tool
        print("\nStep 4: Calling systeminfo_get tool...")
        result = await module.handle_tool_call("systeminfo_get", {})
        
        if result:
            print("\n" + "=" * 60)
            print("Tool Output:")
            print("=" * 60)
            for content in result:
                if hasattr(content, 'text'):
                    print(content.text)
                else:
                    print(str(content))
            print("=" * 60)
        else:
            print("   ❌ No result returned")
            return False
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"   ❌ Error testing module: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            await client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        success = asyncio.run(test_systeminfo_module())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

