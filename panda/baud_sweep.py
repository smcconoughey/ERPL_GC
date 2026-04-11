#!/usr/bin/env python3
"""
Comprehensive baud rate sweep + serial config tester.

Tests standard and non-standard baud rates, parity modes, and data bit
widths against COM4 to find the configuration that produces clean ASCII
telemetry from the PandaV2 board.
"""

import time
import serial

PORT = "COM4"
DURATION = 1.5

BAUD_RATES = [
    9600, 19200, 38400, 57600, 74880,
    115200, 128000, 230400, 250000, 256000,
    460800, 500000, 576000, 921600, 1000000,
    1500000, 2000000, 3000000,
]

CONFIGS = [
    (serial.EIGHTBITS, serial.PARITY_NONE,  serial.STOPBITS_ONE,   "8N1"),
    (serial.SEVENBITS, serial.PARITY_NONE,  serial.STOPBITS_ONE,   "7N1"),
    (serial.EIGHTBITS, serial.PARITY_EVEN,  serial.STOPBITS_ONE,   "8E1"),
    (serial.EIGHTBITS, serial.PARITY_ODD,   serial.STOPBITS_ONE,   "8O1"),
    (serial.SEVENBITS, serial.PARITY_EVEN,  serial.STOPBITS_ONE,   "7E1"),
    (serial.EIGHTBITS, serial.PARITY_NONE,  serial.STOPBITS_TWO,   "8N2"),
]


def score(data: bytes) -> dict:
    if not data:
        return {"bytes": 0, "ascii_pct": 0, "newlines": 0, "panda": 0, "lines": []}

    ascii_count = sum(1 for b in data if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
    pct = ascii_count / len(data) * 100
    newlines = data.count(0x0A)

    panda = 0
    lines = []
    if newlines:
        for raw in data.split(b'\n'):
            text = raw.decode('ascii', errors='replace').strip()
            if not text:
                continue
            lines.append(text)
            ch = text[0]
            if ch in ('p', 's', 't', 'v') and ',' in text:
                try:
                    float(text.split(',')[0][1:])
                    panda += 1
                except (ValueError, IndexError):
                    pass
            elif text.startswith(('BB:', 'BOOT', 'PANDA', 'ARM', 'WARN', 'ACT:', 'SEQ')):
                panda += 1

    return {
        "bytes": len(data), "ascii_pct": pct, "newlines": newlines,
        "panda": panda, "lines": lines,
    }


def try_config(baud, bytesize, parity, stopbits, label):
    try:
        ser = serial.Serial(
            PORT, baud, bytesize=bytesize, parity=parity,
            stopbits=stopbits, timeout=0.2)
    except serial.SerialException:
        return None

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
    return bytes(buf)


def main():
    print("=" * 70)
    print(f"Baud Rate Sweep — {PORT}")
    print("=" * 70)

    best_score = 0
    best_label = ""
    best_info = None

    for baud in BAUD_RATES:
        for bytesize, parity, stopbits, cfg_label in CONFIGS:
            label = f"{baud:>8} {cfg_label}"
            data = try_config(baud, bytesize, parity, stopbits, label)
            if data is None:
                continue

            s = score(data)
            quality = s["ascii_pct"] + s["newlines"] * 5 + s["panda"] * 20

            tag = ""
            if s["panda"] > 0:
                tag = " *** PANDA TELEMETRY ***"
            elif s["ascii_pct"] > 85 and s["newlines"] > 2:
                tag = " ** CLEAN ASCII **"
            elif s["ascii_pct"] > 70:
                tag = " * promising"

            if s["bytes"] > 0 and (quality > 50 or tag):
                print(f"  {label}  {s['bytes']:>5}B  "
                      f"ascii={s['ascii_pct']:5.1f}%  "
                      f"nl={s['newlines']:>3}  "
                      f"panda={s['panda']}{tag}")
                if s["lines"]:
                    for ln in s["lines"][:3]:
                        print(f"      | {ln[:100]}")

            if quality > best_score:
                best_score = quality
                best_label = label
                best_info = s

    print()
    print("-" * 70)
    if best_info and best_score > 50:
        print(f"BEST: {best_label}  ascii={best_info['ascii_pct']:.1f}%  "
              f"nl={best_info['newlines']}  panda={best_info['panda']}")
        if best_info["lines"]:
            print("Sample lines:")
            for ln in best_info["lines"][:8]:
                print(f"  | {ln[:120]}")
    else:
        print("No configuration produced clean telemetry data.")
        print()
        print("This confirms a PHYSICAL LAYER issue:")
        print("  1. RS-485 bus contention (adapter driver fighting Panda driver)")
        print("  2. TTL UART adapter on RS-485 bus (voltage mismatch)")
        print("  3. A/B wires swapped + incompatible transceivers")
        print()
        print("QUICK FIX to try: connect Teensy USB directly to PC.")
        print("  The Teensy 4.1 has built-in USB serial.")
        print("  Add Serial.print() to firmware sendTelemetry() to mirror")
        print("  telemetry on USB while debugging the RS-485 link.")
    print("=" * 70)


if __name__ == "__main__":
    main()
