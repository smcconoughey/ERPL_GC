#!/usr/bin/env python3
"""
Simultaneous read from COM5 (RS-485) and COM6 (Teensy USB).
Compares garbled vs clean to diagnose the RS-485 physical layer issue.
"""

import time
import threading
import serial

BAUD = 460800
DURATION = 3.0
PORTS = {"RS485": "COM5", "USB": "COM6"}


def read_port(port, baud, result_dict, key):
    try:
        ser = serial.Serial(port, baud, timeout=0.3)
        ser.rts = False
        ser.dtr = False
        time.sleep(0.05)
        ser.reset_input_buffer()

        buf = bytearray()
        t0 = time.time()
        while time.time() - t0 < DURATION:
            n = ser.in_waiting
            chunk = ser.read(max(1, n))
            if chunk:
                buf.extend(chunk)
        ser.close()
        result_dict[key] = bytes(buf)
    except Exception as e:
        print(f"  ERROR on {port}: {e}")
        result_dict[key] = b""


def show(label, data):
    print(f"\n{'='*64}")
    print(f"  {label}")
    print(f"{'='*64}")
    if not data:
        print("  (no data)")
        return

    ascii_ct = sum(1 for b in data if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
    pct = ascii_ct / len(data) * 100
    nl = data.count(0x0A)
    print(f"  {len(data)} bytes, {pct:.0f}% ascii, {nl} newlines")
    print(f"  hex (first 80): {data[:80].hex(' ')}")

    if nl > 0:
        lines = data.decode('ascii', errors='replace').split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        print(f"  {len(lines)} text lines:")
        for l in lines[:8]:
            print(f"    | {l[:120]}")
    else:
        preview = data[:120].decode('ascii', errors='replace')
        cleaned = ''.join(c if 0x20 <= ord(c) <= 0x7E else '.' for c in preview)
        print(f"  ascii: {cleaned}")


def byte_histogram(data: bytes, label: str):
    """Show top-20 most frequent bytes."""
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:20]
    print(f"\n  Top bytes in {label}:")
    for val, count in top:
        ch = chr(val) if 0x20 <= val <= 0x7E else '.'
        bar = '#' * min(40, count * 40 // len(data))
        print(f"    0x{val:02X} '{ch}'  {count:>5}  {bar}")


def try_transforms(garbled: bytes):
    """Test common transforms on the garbled data."""
    print(f"\n{'='*64}")
    print("  Transform tests on RS-485 data")
    print(f"{'='*64}")

    transforms = [
        ("bitwise NOT",          lambda b: (~b) & 0xFF),
        ("bit-reverse",          lambda b: int(f'{b:08b}'[::-1], 2)),
        ("NOT + bit-reverse",    lambda b: int(f'{(~b)&0xFF:08b}'[::-1], 2)),
        ("swap nibbles",         lambda b: ((b & 0x0F) << 4) | ((b >> 4) & 0x0F)),
        ("right shift 1",       lambda b: b >> 1),
        ("NOT + right shift 1", lambda b: ((~b) & 0xFF) >> 1),
    ]

    for name, fn in transforms:
        out = bytes(fn(b) for b in garbled)
        nl = out.count(0x0A)
        ascii_ct = sum(1 for b in out if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
        pct = ascii_ct / len(out) * 100 if out else 0

        tag = ""
        if nl > 3 and pct > 80:
            tag = " *** LIKELY FIX ***"
        elif pct > 70:
            tag = " * promising"

        if pct > 50 or nl > 0:
            print(f"\n  {name}: {pct:.0f}% ascii, {nl} newlines{tag}")
            if nl > 0:
                lines = out.decode('ascii', errors='replace').split('\n')
                for l in [x.strip() for x in lines if x.strip()][:4]:
                    print(f"    | {l[:100]}")
            else:
                prev = out[:80].decode('ascii', errors='replace')
                print(f"    {(''.join(c if 0x20<=ord(c)<=0x7E else '.' for c in prev))}")


def main():
    print(f"Reading COM5 and COM6 simultaneously for {DURATION}s...")
    results = {}
    threads = []
    for key, port in PORTS.items():
        t = threading.Thread(target=read_port, args=(port, BAUD, results, key))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    garbled = results.get("RS485", b"")
    clean = results.get("USB", b"")

    show("COM5 — RS-485 (garbled?)", garbled)
    show("COM6 — Teensy USB (reference)", clean)

    if garbled and clean:
        print(f"\n{'='*64}")
        print("  Data rate comparison")
        print(f"{'='*64}")
        print(f"  RS-485: {len(garbled)/DURATION:.0f} bytes/sec")
        print(f"  USB:    {len(clean)/DURATION:.0f} bytes/sec")
        ratio = len(garbled) / len(clean) if clean else 0
        print(f"  Ratio:  {ratio:.2f}x")

        byte_histogram(garbled, "RS-485")

    if garbled and garbled.count(0x0A) == 0:
        try_transforms(garbled)

    print()


if __name__ == "__main__":
    main()
