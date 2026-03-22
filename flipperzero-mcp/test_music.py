#!/usr/bin/env python3
"""Test script for Music Player module - Play Jingle Bells.

This script tests the music module by:
1. Setting up a Flipper client (with optional real connection)
2. Instantiating the MusicModule
3. Formatting "Jingle Bells" in FMF format
4. Playing it on the Flipper Zero
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from flipper_mcp.modules.music import MusicModule
from flipper_mcp.core.flipper_client import FlipperClient
from flipper_mcp.core.transport.usb import USBTransport


def get_jingle_bells_fmf() -> str:
    """
    Get "Jingle Bells" formatted in FMF (Flipper Music Format).
    
    Returns:
        FMF formatted string
    """
    # Jingle Bells melody in FMF v0 format (matches the device's Music Player expectations)
    # Tempo: 120 BPM, Default duration: 4 (quarter notes), Default octave: 4
    # Notes: E E E, E E E, E G C D E, F F F F, F E E E, E D D E D G
    jingle_bells = """Filetype: Flipper Music Format
Version: 0
BPM: 120
Duration: 4
Octave: 4
Notes: 4E, 4E, 4E, 4E, 4E, 4E, 4E, 4G, 4C, 4D, 4E, 4F, 4F, 4F, 4F, 4F, 4E, 4E, 4E, 4E, 4D, 4D, 4E, 4D, 4G, 4E, 4E, 4E, 4E, 4E, 4E, 4E, 4G, 4C, 4D, 4E, 4F, 4F, 4F, 4F, 4F, 4E, 4E, 4E, 4E, 4G, 4G, 4F, 4D, 4C
"""
    
    return jingle_bells


async def test_music_module():
    """Test the Music module by playing Jingle Bells."""
    
    print("=" * 60)
    print("Music Player Module Test - Jingle Bells")
    print("=" * 60)
    print()
    
    # Configuration
    config = {
        "transport": {
            "type": "usb",
            "usb": {
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
        if hasattr(transport, 'port') and transport.port:
            print(f"   Port: {transport.port}")
        else:
            print(f"   Port: Auto-detect")
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
    print("\nStep 3: Testing Music Player module...")
    try:
        module = MusicModule(client)
        print(f"   ✓ Module created: {module.name} v{module.version}")
        
        # Get tools
        tools = module.get_tools()
        print(f"   ✓ Module has {len(tools)} tool(s):")
        for tool in tools:
            print(f"     - {tool.name}")
        
        # Step 4: Get format specification (optional, for reference)
        print("\nStep 4: Getting FMF format specification...")
        format_result = await module.handle_tool_call("music_get_format", {})
        if format_result:
            print(f"   ✓ Format specification retrieved ({len(format_result[0].text)} characters)")
        
        # Step 5: Format and play Jingle Bells
        print("\nStep 5: Formatting Jingle Bells in FMF format...")
        jingle_bells_fmf = get_jingle_bells_fmf()
        print(f"   ✓ FMF formatted ({len(jingle_bells_fmf)} characters)")
        print(f"   Preview: {jingle_bells_fmf[:80]}...")
        
        # Step 6: Play the song
        print("\nStep 6: Playing Jingle Bells on Flipper Zero...")
        print("   Calling music_play tool...")
        result = await module.handle_tool_call("music_play", {
            "song_data": jingle_bells_fmf,
            "filename": "jingle_bells.fmf",
            "play_immediately": True
        })
        
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
        print("\n🎵 Jingle Bells should now be playing on your Flipper Zero!")
        print("   (If in stub mode, the file was 'saved' but not actually sent to device)")
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
        success = asyncio.run(test_music_module())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

