#!/usr/bin/env python3
"""
Quick RS-485 bus contention test.

Many USB-to-RS485 adapters use RTS to control the driver-enable (DE) pin.
If the adapter's TX driver is always on, it fights the Panda's driver on the
bus, garbling every byte.  This script tries disabling the adapter's driver
by toggling RTS/DTR, then reads data to see if it becomes clean.

Usage:  python serial_quick_test.py
"""

import time
import serial

PORT = "COM4"
BAUD = 460800
DURATION = 3.0


def try_read(label, rts, dtr):
    print(f"\n--- {label}  (rts={rts}, dtr={dtr}) ---")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.5)
        ser.rts = rts
        ser.dtr = dtr
        time.sleep(0.1)
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
        print(f"  ERROR: {e}")
        return

    if not buf:
        print("  no data received")
        return

    ascii_count = sum(1 for b in buf if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
    newlines = buf.count(0x0A) + buf.count(0x0D)
    pct = ascii_count / len(buf) * 100

    print(f"  {len(buf)} bytes, {pct:.0f}% ascii, {newlines} newline chars")
    print(f"  hex (first 80): {buf[:80].hex(' ')}")

    if newlines > 0:
        lines = buf.decode('ascii', errors='replace').split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        print(f"  {len(lines)} text lines:")
        for l in lines[:8]:
            print(f"    | {l[:120]}")
    else:
        printable = buf.decode('ascii', errors='replace')
        preview = ''.join(c if 0x20 <= ord(c) <= 0x7E else '.' for c in printable[:120])
        print(f"  ascii preview: {preview}")


print("=" * 60)
print(f"RS-485 Bus Contention Test — {PORT} @ {BAUD}")
print("=" * 60)

try_read("Default (both high)",       rts=True,  dtr=True)
try_read("RTS=low  (disable TX DE?)", rts=False, dtr=True)
try_read("DTR=low",                   rts=True,  dtr=False)
try_read("Both low",                  rts=False, dtr=False)

print("\n" + "=" * 60)
print("If one config shows >90% ascii with newlines, that's the fix.")
print("If all are garbled, the adapter doesn't use RTS/DTR for DE.")
print("=" * 60)
