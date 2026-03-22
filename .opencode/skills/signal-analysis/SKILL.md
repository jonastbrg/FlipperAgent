---
name: signal-analysis
description: "RF signal analysis methodology — Sub-GHz capture, protocol identification, timing analysis, rolling vs static code detection, and IR protocol decoding"
---

# RF Signal Analysis Methodology

## Sub-GHz Signal Capture and Analysis

### Frequency Bands
| Band | Common Uses | Flipper Support |
|------|-------------|-----------------|
| 300-348 MHz | Garage doors (US), car remotes | Yes (CC1101) |
| 387-464 MHz | Car key fobs, home automation, weather stations | Yes |
| 779-928 MHz | ISM band, LoRa, Z-Wave, garage doors (EU) | Yes |
| 433.92 MHz | Most common — universal remotes, sensors, doorbells | Yes |
| 315 MHz | North American car fobs, garage doors | Yes |
| 868 MHz | European ISM, smart home, alarm systems | Yes |
| 915 MHz | US ISM, LoRa, smart meters | Yes |

### Capture Workflow
```
flipper_subghz_rx(frequency=433920000, modulation="AM650")
```

1. **Set frequency** — start with 433.92 MHz if unknown, then try 315 MHz, 868 MHz
2. **Set modulation** — AM650 for OOK/ASK, FM238 for FSK
3. **Trigger the target** — press the remote, trigger the sensor, open the door
4. **Capture the signal** — Flipper records the raw signal
5. **Analyze the capture** — identify protocol, extract data bits

### Modulation Types

**OOK (On-Off Keying)** — most common for simple remotes
- Signal is either present (1) or absent (0)
- Easy to identify: clean on/off pattern in time domain
- Used by: garage doors, doorbells, weather stations, simple car fobs

**ASK (Amplitude Shift Keying)** — modulated amplitude
- Similar to OOK but with amplitude variation
- Flipper treats OOK and ASK similarly (AM modulation)

**FSK (Frequency Shift Keying)** — frequency changes encode data
- Two frequencies represent 0 and 1
- Used by: car key fobs (some), TPMS sensors, smart meters
- Set Flipper to FM modulation for capture

**Manchester Encoding** — clock embedded in data
- Each bit has a transition in the middle: low→high = 1, high→low = 0
- Self-clocking — no separate clock signal needed
- Used by: many industrial protocols, some garage doors

## Protocol Identification

### By Timing Analysis

Capture the raw signal and measure:
- **Pulse width** (duration of high signal)
- **Gap width** (duration between pulses)
- **Bit rate** (pulses per second)
- **Preamble** (repeating pattern at start)
- **Sync pulse** (long pulse or gap separating preamble from data)

### Common Protocol Signatures

**Princeton (PT2262/PT2264)**
- Encoding: tri-state (0, 1, float)
- Bit timing: short pulse = 1 unit, long pulse = 3 units
- Typical unit: 350μs (varies by resistor value)
- Address: 8 tri-state bits, Data: 4 tri-state bits
- Preamble: 1 sync pulse (1 high + 31 low units)
- Frequency: 315 MHz or 433.92 MHz
- Very common in cheap remotes, doorbells, power outlets

**CAME**
- Encoding: Manchester
- Bit timing: ~320μs per half-bit
- Fixed code: 12-bit
- Preamble: high pulse followed by specific low gap
- Frequency: 433.92 MHz (EU), 868 MHz
- Used in: gate openers, barrier systems

**NICE FLO**
- Encoding: PWM (pulse width modulation)
- Bit 0: short high + long low
- Bit 1: long high + short low
- Fixed code: 12-bit
- Frequency: 433.92 MHz
- Used in: gate openers (Italy, EU)

**Linear (Multi-Code)**
- Encoding: tri-state
- 10-bit dip switch code
- Frequency: 310 MHz (US)
- Used in: older garage doors, gate systems

**Chamberlain / LiftMaster / Craftsman**
- **SECURITY+** (older) — 40-bit rolling code
- **SECURITY+ 2.0** (current) — encrypted rolling code
- Rolling code: CANNOT be replayed
- Frequency: 315 MHz (US), 390 MHz (US garage)

**GE / Jasco**
- Encoding: fixed code
- 12-bit to 24-bit depending on model
- Frequency: 318 MHz or 433.92 MHz
- Used in: home automation switches

### Identification Decision Tree

1. Measure pulse widths — if consistent short/long ratio ~1:3 → likely Princeton-style
2. Check for Manchester encoding — transitions in middle of each bit period
3. Count total bits — 12-bit = CAME/NICE, 24-bit = common custom, 40+ bit = likely rolling code
4. Check for preamble pattern — long sync pulse = Princeton, short burst = CAME
5. Transmit captured signal — if it works → static code. If not → rolling code or wrong protocol

## Rolling Code vs Static Code Detection

### Static Codes — CAN Be Replayed
- Same button press always produces identical signal
- Capture once, replay unlimited times
- Common in: cheap remotes, doorbells, power outlets, older garage doors, fan remotes
- **Test**: capture two presses of same button, compare — identical = static

### Rolling Codes — CANNOT Be Replayed
- Each press generates a unique code from a synchronized counter
- Replay of a captured code will fail (counter has advanced)
- **Technologies:**
  - **KeeLoq (HCS301/HCS200)** — 66-bit transmission, 32-bit hopping code, 28-bit fixed serial
  - **AUT64** — used by some car manufacturers
  - **HITAG2** — older, known cryptographic weaknesses
  - **Chamberlain Security+ 2.0** — proprietary rolling code

**Detection method:**
1. Capture signal press 1
2. Capture signal press 2 (same button)
3. Compare the two captures
4. If identical → static code (replayable)
5. If different → rolling code (not replayable with simple replay)

**Rolling code attacks (advanced, often impractical):**
- **RollJam** — jam + capture two codes, replay the first (the second is still valid)
- **RollBack** — exploit counter resynchronization window
- These require specialized hardware and are outside normal Flipper capability

## IR Signal Analysis

### Common IR Protocols

**NEC (most common)**
- Carrier: 38 kHz
- Encoding: pulse distance
- Format: 8-bit address + 8-bit inverse + 8-bit command + 8-bit inverse = 32 bits
- Leader: 9ms burst + 4.5ms space
- Bit 0: 562.5μs burst + 562.5μs space
- Bit 1: 562.5μs burst + 1687.5μs space
- Repeat: 9ms burst + 2.25ms space + 562.5μs burst
- Used by: most consumer electronics, many Chinese-made devices

**RC5 (Philips)**
- Carrier: 36 kHz
- Encoding: Manchester (bi-phase)
- Format: 2 start bits + toggle + 5-bit address + 6-bit command = 14 bits
- Toggle bit flips each key press (distinguishes hold from re-press)
- Bit time: 1.778ms (889μs per half)
- Used by: Philips, Marantz, some European brands

**RC6 (Philips, evolved)**
- Carrier: 36 kHz
- Encoding: Manchester with header
- Leader: 2.666ms burst + 889μs space
- Mode bits + toggle + address + command
- Used by: Microsoft MCE remotes, Philips, Xbox 360 media remote

**Samsung32**
- Carrier: 38 kHz
- Encoding: pulse distance (similar to NEC)
- Format: 8-bit custom code (sent twice) + 8-bit data + 8-bit inverted data = 32 bits
- Leader: 4.5ms burst + 4.5ms space
- Used by: Samsung TVs, soundbars

**SIRC (Sony)**
- Carrier: 40 kHz
- Encoding: pulse width
- Format: 12-bit (7 command + 5 device), 15-bit, or 20-bit variants
- Leader: 2.4ms burst + 600μs space
- Bit 0: 600μs burst + 600μs space
- Bit 1: 1.2ms burst + 600μs space
- Message sent 3 times minimum
- Used by: Sony TVs, PlayStation, audio equipment

### IR Capture and Replay
```
flipper_ir_rx()           # Learn raw signal
flipper_ir_tx(signal=...)  # Replay captured signal
```

### IR Analysis Workflow
1. **Capture** the IR signal in raw mode
2. **Identify carrier frequency** — 36 kHz (Philips), 38 kHz (NEC/Samsung), 40 kHz (Sony)
3. **Measure leader pulse** — this uniquely identifies the protocol family
4. **Decode data bits** — apply protocol-specific bit encoding rules
5. **Extract address and command** — map to device functions
6. **Build command library** — capture all buttons, document address:command pairs

## Decoding Unknown Signals

When the Flipper doesn't auto-detect the protocol:

1. **Capture raw** — save the complete signal waveform
2. **Visual inspection** — look at timing patterns in the raw data
3. **Measure timing elements:**
   - Shortest pulse width (this is usually the base unit)
   - Ratio of short to long pulses
   - Total transmission length
   - Preamble/sync pattern
4. **Calculate bit rate** — base unit duration → bits per second
5. **Look for structure:**
   - Fixed header/preamble (same every transmission)
   - Variable data section (changes between button presses)
   - Checksum/CRC at end (last 4-8 bits)
6. **Compare multiple captures:**
   - Same button twice → identify static vs rolling portions
   - Different buttons → identify command field (bits that change)
   - Same button, different devices → identify address field

### Common Signal Structures
```
[Preamble] [Sync] [Address/ID] [Command/Data] [Checksum] [Stop]
```

- Preamble: 4-16 bits of alternating pattern for receiver AGC calibration
- Sync: distinctive pulse/gap pattern separating preamble from data
- Address: device identifier (fixed per remote)
- Command: button/action identifier (varies per button)
- Checksum: XOR or CRC of data bits for error detection

## Operational Notes

- Always capture multiple presses of the same signal for comparison
- Note the distance and angle for successful capture — relevant for report
- Sub-GHz transmission power varies by region (FCC vs CE vs ARIB limits)
- Flipper's CC1101 radio sensitivity: approximately -110 dBm
- Maximum practical Sub-GHz range: 50-100m depending on environment
- IR is line-of-sight only; range typically 5-10m
- Document all captured signals with timestamps, descriptions, and replay success/failure
