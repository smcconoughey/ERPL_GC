#!/usr/bin/env python3
"""
Bit-level UART re-framing test.

When RS-485 A/B polarity is swapped, a simple byte-level NOT doesn't work
because the UART receiver mis-frames the inverted bit stream. This script
reconstructs the original bit stream, tries inverting it, and re-frames
to extract the actual bytes.

Also tests whether the FTDI adapter is a plain TTL-UART (not RS-485) by
checking if the data decodes at half the baud rate (one-wire RS-485 hack).
"""

import time
import serial

PORT = "COM4"
BAUD = 460800
DURATION = 3.0


def bytes_to_bits(data: bytes) -> list:
    """Convert UART-received bytes back to their bit stream (8N1, LSB first).
    Each byte becomes: [START=0, D0, D1, D2, D3, D4, D5, D6, D7, STOP=1]
    """
    bits = []
    for byte in data:
        bits.append(0)  # start bit
        for i in range(8):
            bits.append((byte >> i) & 1)
        bits.append(1)  # stop bit
    return bits


def bits_to_bytes(bits: list) -> bytes:
    """Scan a bit stream for UART frames (8N1, LSB first).
    Looks for start bits (1->0 transition) and extracts bytes.
    """
    result = []
    i = 0
    while i < len(bits) - 9:
        if bits[i] == 1 and i + 1 < len(bits) and bits[i + 1] == 0:
            # Found falling edge -> potential start bit at i+1
            start = i + 1
            if start + 9 >= len(bits):
                break
            # Sample at center of each bit (start + 0.5, D0 at +1.5, etc.)
            byte_val = 0
            for bit_idx in range(8):
                pos = start + 1 + bit_idx
                if pos < len(bits):
                    byte_val |= bits[pos] << bit_idx
            stop_pos = start + 9
            if stop_pos < len(bits) and bits[stop_pos] == 1:
                result.append(byte_val)
                i = stop_pos
            else:
                result.append(byte_val)
                i = stop_pos
        else:
            i += 1
    return bytes(result)


def analyze(label: str, data: bytes):
    if not data:
        print(f"  {label}: (empty)")
        return False
    ascii_count = sum(1 for b in data if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
    newlines = data.count(0x0A)
    pct = ascii_count / len(data) * 100 if data else 0
    panda = 0
    lines = []
    if newlines > 0:
        for raw_line in data.split(b'\n'):
            text = raw_line.decode('ascii', errors='replace').strip()
            if not text:
                continue
            lines.append(text)
            first = text[0] if text else ''
            if first in ('p', 's', 't', 'v') and ',' in text:
                try:
                    float(text.split(',')[0][1:])
                    panda += 1
                except (ValueError, IndexError):
                    pass
            elif text.startswith(('BB:', 'BOOT', 'PANDA', 'ARM', 'WARN', 'ACT:')):
                panda += 1

    print(f"  {label}: {len(data)}B  ascii={pct:.0f}%  nl={newlines}  panda={panda}")
    preview = data[:60].hex(' ')
    print(f"    hex: {preview}")
    if lines:
        for ln in lines[:6]:
            print(f"    | {ln[:120]}")
        return True
    else:
        text = data[:100].decode('ascii', errors='replace')
        preview = ''.join(c if 0x20 <= ord(c) <= 0x7E else '.' for c in text)
        print(f"    ascii: {preview}")
    return panda > 0


def main():
    print("=" * 64)
    print(f"Bit-level UART decode test — {PORT} @ {BAUD}")
    print("=" * 64)

    print(f"\nReading {PORT} at {BAUD} for {DURATION}s...")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.5)
        ser.reset_input_buffer()
        buf = bytearray()
        t0 = time.time()
        while time.time() - t0 < DURATION:
            n = ser.in_waiting
            chunk = ser.read(max(1, n))
            if chunk:
                buf.extend(chunk)
        ser.close()
    except Exception as e:
        print(f"ERROR: {e}")
        return

    raw = bytes(buf)
    print(f"Captured {len(raw)} bytes\n")

    if not raw:
        print("No data received!")
        return

    analyze("1. Raw (as received)", raw)

    print()
    not_raw = bytes((~b) & 0xFF for b in raw)
    analyze("2. Simple NOT (byte-level inversion)", not_raw)

    print("\n--- Bit-level re-framing tests ---")

    bit_stream = bytes_to_bits(raw)
    print(f"\nBit stream: {len(bit_stream)} bits from {len(raw)} bytes")

    inv_bits = [1 - b for b in bit_stream]
    reframed = bits_to_bytes(inv_bits)
    print()
    found = analyze("3. Invert bits + re-frame UART", reframed)

    shifted = [1 - b for b in bit_stream]
    for offset in [1, -1, 2, -2]:
        if offset > 0:
            test_bits = shifted[offset:] + [1] * offset
        else:
            test_bits = [1] * (-offset) + shifted[:offset]
        decoded = bits_to_bytes(test_bits)
        print()
        found = analyze(f"4. Invert + shift({offset:+d}) + re-frame", decoded) or found

    not_then_reframe = bytes_to_bits(not_raw)
    decoded = bits_to_bytes(not_then_reframe)
    print()
    found = analyze("5. NOT bytes then re-frame", decoded)

    print("\n--- Direct raw byte transforms ---")
    for name, fn in [
        ("right-shift 1", lambda b: b >> 1),
        ("NOT + right-shift 1", lambda b: ((~b) & 0xFF) >> 1),
        ("left-shift 1 + OR 1", lambda b: ((b << 1) | 1) & 0xFF),
        ("NOT + left-shift 1", lambda b: ((~b) << 1) & 0xFF),
        ("swap bits 0,7", lambda b: (b & 0x7E) | ((b >> 7) & 1) | ((b & 1) << 7)),
    ]:
        transformed = bytes(fn(b) for b in raw)
        print()
        found = analyze(f"6. {name}", transformed) or found

    if not found:
        print("\n" + "=" * 64)
        print("No transform produced valid PandaV2 telemetry.")
        print()
        print("LIKELY CAUSE: The USB adapter (FTDI FT230X) may be a plain")
        print("USB-to-TTL-UART adapter, NOT a USB-to-RS485 adapter.")
        print()
        print("CHECK: What is the physical adapter? Does it have A/B")
        print("screw terminals (RS-485) or TX/RX/GND pins (TTL UART)?")
        print()
        print("If it's TTL UART, you need either:")
        print("  a) A proper USB-to-RS485 adapter (with MAX485/ISL83491)")
        print("  b) Connect the FTDI's TX/RX to the Teensy's UART pins")
        print("     directly (bypass RS-485 entirely)")
        print("=" * 64)


if __name__ == "__main__":
    main()
