---
name: protocol-analysis
description: "Reverse-engineer binary protocols — CRC detection with crcbeagle, CRC calculation, packet structure analysis"
---

# Protocol Analysis

Reverse-engineer checksums (CRC) from captured packets and analyze binary protocol structures. Uses crcbeagle for automated CRC parameter detection.

The crcbeagle library is available locally at `./crcbeagle/`.

## Prerequisites

```bash
pip install crccheck   # For CRC calculation with custom parameters
```

crcbeagle is bundled locally. Reference it via path when importing.

## CRC detection

Automatically detect the CRC algorithm (polynomial, init value, XOR output) from captured packets. Provide at least 2-3 example packets where only one field changes (e.g., same command with different data values).

```bash
python3 -c "
import sys
sys.path.insert(0, './crcbeagle')
from crcbeagle.crcbeagle import CRCBeagle

# Example hex packets (replace with your captured data)
packets_hex = [
    'aa0800a823704201501165660000f226a8bd',
    'aa0800a82370420150116566000072579a5c',
    'aa0800a823704201501165660000b2875b1e',
]

crc_size = 4  # CRC size in bytes: 1 (CRC-8), 2 (CRC-16), or 4 (CRC-32)

# Parse hex to bytes, split data from CRC
packets = [bytes.fromhex(h.replace(' ', '')) for h in packets_hex]
data_parts = [p[:-crc_size] for p in packets]
crc_parts = [p[-crc_size:] for p in packets]

crc = CRCBeagle()

# Call the appropriate search function based on CRC size
if crc_size == 1:
    result = crc.search_crc8(data_parts, crc_parts)
elif crc_size == 2:
    result = crc.search_crc16(data_parts, crc_parts)
else:
    result = crc.search_crc32(data_parts, crc_parts)

if result:
    print(f'CRC-{crc_size*8} algorithm detected:')
    print(f'  Result: {result}')
else:
    print('Could not detect CRC algorithm. Try more packets or different CRC size.')
"
```

**Tips for CRC detection:**
- Need at least 2 packets, 3+ is better.
- Packets should have the same structure but varying data fields.
- Try `crc_size=2` if `crc_size=4` fails -- many IoT protocols use CRC-16.
- CRC is usually at the end of the packet; if at the start, adjust slicing to `p[:crc_size]` for CRC and `p[crc_size:]` for data.

## CRC calculation

Calculate a CRC checksum for given data using known parameters (e.g., after detection).

```bash
python3 -c "
from crccheck.crc import Crc32Base

# Parameters from crc_detect or protocol documentation
class CustomCRC(Crc32Base):
    _poly = 0x04C11DB7       # CRC polynomial
    _initvalue = 0xFFFFFFFF  # Initial value
    _xor_output = 0xFFFFFFFF # XOR applied to final CRC
    _reflect_input = True    # Reflect input bytes
    _reflect_output = True   # Reflect output CRC

data_hex = 'aa0800a8237042015011656600'  # Data without CRC
data = bytes.fromhex(data_hex)
crc = CustomCRC.calc(data)
crc_size = 4  # bytes

crc_hex = format(crc, f'0{crc_size*2}x')
crc_le = bytes.fromhex(crc_hex)[::-1].hex()

print(f'Data:                  {data_hex}')
print(f'CRC (big-endian):      0x{crc_hex}')
print(f'CRC (little-endian):   0x{crc_le}')
print(f'Full packet (LE CRC):  {data_hex}{crc_le}')
"
```

For CRC-8 or CRC-16, use `Crc8Base` or `Crc16Base` from `crccheck.crc` respectively.

## Packet decoding

Analyze a binary packet structure byte-by-byte, or decode with a known field format.

### Auto-analysis (byte-by-byte)

```bash
python3 -c "
packet_hex = 'aa0800a823704201501165660000f226a8bd'
raw = bytes.fromhex(packet_hex.replace(' ', ''))
print(f'Packet: {packet_hex} ({len(raw)} bytes)')
print()
print('Byte-by-byte analysis:')
for i, b in enumerate(raw):
    ascii_char = chr(b) if 32 <= b < 127 else '.'
    print(f'  [{i:3d}] 0x{b:02X}  {b:3d}  \"{ascii_char}\"')

print()
print('Integer interpretations:')
if len(raw) >= 2:
    print(f'  uint16 LE [0:2]: {int.from_bytes(raw[0:2], \"little\")}')
    print(f'  uint16 BE [0:2]: {int.from_bytes(raw[0:2], \"big\")}')
if len(raw) >= 4:
    print(f'  uint32 LE [0:4]: {int.from_bytes(raw[0:4], \"little\")}')
    print(f'  uint32 BE [0:4]: {int.from_bytes(raw[0:4], \"big\")}')
    print(f'  uint32 LE [-4:]: {int.from_bytes(raw[-4:], \"little\")}')
    print(f'  uint32 BE [-4:]: {int.from_bytes(raw[-4:], \"big\")}')
"
```

### Structured field decoding

Decode a packet with a known format specification (`name:bytes` pairs).

```bash
python3 -c "
packet_hex = 'aa0800a823704201501165660000f226a8bd'
fmt = 'header:1,length:1,flags:1,addr:4,counter:2,data:4,crc:4'

raw = bytes.fromhex(packet_hex.replace(' ', ''))
print(f'Packet: {packet_hex} ({len(raw)} bytes)')
print()
print('Field breakdown:')
offset = 0
for field_spec in fmt.split(','):
    name, size = field_spec.strip().split(':')
    size = int(size)
    if offset + size > len(raw):
        print(f'  {name}: OVERFLOW (packet too short)')
        break
    field_bytes = raw[offset:offset+size]
    hex_val = field_bytes.hex()
    int_le = int.from_bytes(field_bytes, 'little')
    int_be = int.from_bytes(field_bytes, 'big')
    line = f'  {name:15s} [{offset}:{offset+size}] = 0x{hex_val}'
    if size <= 4:
        line += f'  (LE:{int_le}, BE:{int_be})'
    try:
        text = field_bytes.decode('utf-8')
        if text.isprintable():
            line += f'  \"{text}\"'
    except:
        pass
    print(line)
    offset += size
if offset < len(raw):
    remaining = raw[offset:]
    print(f'  {\"(remaining)\":15s} [{offset}:{len(raw)}] = 0x{remaining.hex()} ({len(remaining)} bytes)')
"
```

## Notes

- All protocol analysis operations are LOW risk -- computation only, no device interaction.
- crcbeagle supports CRC-8, CRC-16, and CRC-32 detection.
- For protocols with CRC at the start of the packet instead of the end, reverse the data/CRC split.
- Common IoT CRC polynomials:
  - CRC-32: `0x04C11DB7` (Ethernet, ZIP)
  - CRC-16/CCITT: `0x1021`
  - CRC-16/Modbus: `0x8005`
  - CRC-8/MAXIM: `0x31`
