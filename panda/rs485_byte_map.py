#!/usr/bin/env python3
"""
RS-485 byte mapping test.

Talks to the rs485_test firmware over USB (COM6) to send a byte-map
pattern (0x00-0xFF) on RS-485 bus 1, while simultaneously reading
COM5 to capture what the FTDI adapter actually receives.

Finds the sync preamble (0xAA x8 + 0x55 x8) in the capture, extracts
the 256-byte payload, and builds an exact sent-vs-received error map.
"""

import time
import threading
import serial
import sys

USB_PORT = "COM6"
RS485_PORT = "COM5"
BAUD = 460800
CAPTURE_DURATION = 8.0

PREAMBLE = bytes([0xAA] * 8 + [0x55] * 8)


def capture_rs485(result):
    try:
        ser = serial.Serial(RS485_PORT, BAUD, timeout=0.5)
        ser.rts = False
        ser.dtr = False
        time.sleep(0.05)
        ser.reset_input_buffer()

        buf = bytearray()
        t0 = time.time()
        while time.time() - t0 < CAPTURE_DURATION:
            n = ser.in_waiting
            chunk = ser.read(max(1, n))
            if chunk:
                buf.extend(chunk)
        ser.close()
        result["data"] = bytes(buf)
    except Exception as e:
        result["error"] = str(e)


def send_bytemap_cmd():
    try:
        ser = serial.Serial(USB_PORT, BAUD, timeout=1.0)
        time.sleep(2.0)

        while ser.in_waiting:
            ser.read(ser.in_waiting)
            time.sleep(0.1)

        ser.write(b'7\n')
        time.sleep(0.5)

        resp = b""
        while ser.in_waiting:
            resp += ser.read(ser.in_waiting)
            time.sleep(0.1)
        print(f"  FW: {resp.decode('ascii', errors='replace').strip()}")

        ser.write(b'1\n')
        time.sleep(0.5)

        t0 = time.time()
        usb_log = bytearray()
        while time.time() - t0 < CAPTURE_DURATION - 1:
            if ser.in_waiting:
                usb_log.extend(ser.read(ser.in_waiting))
            time.sleep(0.2)

        while ser.in_waiting:
            usb_log.extend(ser.read(ser.in_waiting))
            time.sleep(0.1)

        text = usb_log.decode('ascii', errors='replace')
        print(f"  FW log: {text.strip()[-200:]}")
        ser.close()
    except Exception as e:
        print(f"  USB ERROR: {e}")


def find_preamble(data: bytes, preamble: bytes) -> list:
    """Find all offsets where something close to the preamble appears."""
    offsets = []
    # Exact match first
    idx = 0
    while True:
        pos = data.find(preamble, idx)
        if pos < 0:
            break
        offsets.append(("exact", pos))
        idx = pos + 1

    # If no exact match, try fuzzy: look for runs of similar bytes
    if not offsets:
        for i in range(len(data) - 15):
            hi_count = sum(1 for b in data[i:i+8] if b in (0xAA, 0xAB, 0xA8, 0xA9))
            lo_count = sum(1 for b in data[i+8:i+16] if b in (0x55, 0x54, 0x57, 0x56))
            if hi_count >= 5 and lo_count >= 5:
                offsets.append(("fuzzy", i))

        # Also look for garbled preamble: 0xAA<<1 = 0x54, 0x55<<1 = 0xAA
        for i in range(len(data) - 15):
            hi_count = sum(1 for b in data[i:i+8] if b in (0x54, 0x55))
            lo_count = sum(1 for b in data[i+8:i+16] if b in (0xAA, 0xAB))
            if hi_count >= 5 and lo_count >= 5:
                offsets.append(("shifted-preamble", i))

    return offsets


def analyze(received: bytes):
    print(f"\n{'='*70}")
    print(f"  Captured {len(received)} bytes on {RS485_PORT}")
    print(f"{'='*70}")

    if not received:
        print("  No data received!")
        return

    print(f"  hex (first 80): {received[:80].hex(' ')}")

    # Dump first 512 bytes
    print(f"\n  Hex dump (first 512 bytes):")
    for i in range(0, min(512, len(received)), 16):
        chunk = received[i:i+16]
        hexstr = ' '.join(f'{b:02X}' for b in chunk)
        ascstr = ''.join(chr(b) if 0x20 <= b <= 0x7E else '.' for b in chunk)
        print(f"    {i:04X}: {hexstr:<48} {ascstr}")

    # Look for preamble
    print(f"\n  Searching for preamble...")
    offsets = find_preamble(received, PREAMBLE)

    if offsets:
        for kind, off in offsets[:3]:
            print(f"  Found {kind} preamble at offset {off}")
            payload_start = off + 16
            if payload_start + 256 <= len(received):
                payload = received[payload_start:payload_start + 256]
                check_payload(payload)
            else:
                avail = len(received) - payload_start
                print(f"  Only {avail} bytes after preamble (need 256)")
                if avail > 0:
                    payload = received[payload_start:payload_start + avail]
                    check_payload(payload)
    else:
        print("  No preamble found. Trying raw transform search...")
        check_transforms(received)


def check_payload(payload: bytes):
    """Compare payload against expected 0x00..0xFF sequence."""
    expected = bytes(range(min(256, len(payload))))

    exact = sum(1 for a, b in zip(payload, expected) if a == b)
    print(f"  Exact match: {exact}/{len(payload)} bytes ({exact*100//len(payload)}%)")

    if exact > 200:
        print("  ** MOSTLY CORRECT — minor bit errors only **")
        errors = [(i, payload[i], expected[i]) for i in range(len(payload)) if payload[i] != expected[i]]
        for i, got, exp in errors[:20]:
            xor = got ^ exp
            print(f"    byte {i:3d}: sent 0x{exp:02X} got 0x{got:02X}  XOR=0x{xor:02X} ({xor:08b})")
        return

    # Try transforms
    transforms = {
        ">> 1":           lambda b: b >> 1,
        ">> 1 | 0x80":    lambda b: (b >> 1) | 0x80,
        "(b&0xFE)>>1":    lambda b: (b & 0xFE) >> 1,
        "<< 1 & 0xFF":    lambda b: (b << 1) & 0xFF,
        "NOT":            lambda b: (~b) & 0xFF,
        "NOT >> 1":       lambda b: ((~b) & 0xFF) >> 1,
        "bit-reverse":    lambda b: int(f'{b:08b}'[::-1], 2),
        "swap nibbles":   lambda b: ((b & 0x0F) << 4) | ((b >> 4) & 0x0F),
    }

    for name, fn in transforms.items():
        mapped = bytes(fn(b) for b in payload)
        match = sum(1 for a, b in zip(mapped, expected) if a == b)
        if match > len(payload) * 0.3:
            print(f"  Transform '{name}': {match}/{len(payload)} match ({match*100//len(payload)}%)")
            if match > len(payload) * 0.8:
                print(f"    *** THIS IS THE MAPPING ***")
                errors = [(i, payload[i], expected[i], fn(payload[i]))
                          for i in range(len(payload)) if fn(payload[i]) != expected[i]]
                for i, raw, exp, mapped_val in errors[:20]:
                    print(f"    byte {i:3d}: sent 0x{exp:02X} raw 0x{raw:02X} "
                          f"mapped 0x{mapped_val:02X}")


def check_transforms(data: bytes):
    """Try transforms on entire data looking for incrementing sequences."""
    transforms = {
        "identity":       lambda b: b,
        ">> 1":           lambda b: b >> 1,
        ">> 1 | 0x80":    lambda b: (b >> 1) | 0x80,
        "<< 1 & 0xFF":    lambda b: (b << 1) & 0xFF,
        "NOT":            lambda b: (~b) & 0xFF,
        "NOT >> 1":       lambda b: ((~b) & 0xFF) >> 1,
        "bit-reverse":    lambda b: int(f'{b:08b}'[::-1], 2),
    }

    for name, fn in transforms.items():
        mapped = [fn(b) for b in data]

        best_run = 0
        best_start = 0
        run = 1
        run_start = 0
        for i in range(1, len(mapped)):
            if mapped[i] == (mapped[i-1] + 1) & 0xFF:
                run += 1
            else:
                if run > best_run:
                    best_run = run
                    best_start = run_start
                run = 1
                run_start = i
        if run > best_run:
            best_run = run
            best_start = run_start

        if best_run >= 4:
            sample_raw = data[best_start:best_start+min(8, best_run)]
            sample_map = mapped[best_start:best_start+min(8, best_run)]
            print(f"  {name:<18} run={best_run:>4} @ offset {best_start}  "
                  f"raw={sample_raw.hex(' ')}  mapped={[f'{b:02X}' for b in sample_map]}")


def main():
    print("=" * 70)
    print(f"  RS-485 Byte Map Test")
    print(f"  USB: {USB_PORT}  RS-485: {RS485_PORT}  Baud: {BAUD}")
    print("=" * 70)

    result = {}
    cap_thread = threading.Thread(target=capture_rs485, args=(result,))
    cap_thread.start()
    time.sleep(0.5)

    send_bytemap_cmd()

    cap_thread.join()

    if "error" in result:
        print(f"\n  RS-485 capture error: {result['error']}")
        return

    analyze(result.get("data", b""))


if __name__ == "__main__":
    main()
