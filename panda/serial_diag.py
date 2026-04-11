#!/usr/bin/env python3
"""
PandaV2 Serial Diagnostic — detect baud rate, polarity, and framing issues.

Tests COM4 at 460800 with various serial configs and signal transformations
to identify why the FTDI RS-485 adapter produces garbled data.

Usage:
    python serial_diag.py                   # full scan
    python serial_diag.py --port COM4       # single port
    python serial_diag.py --baud 460800     # single baud
"""

import argparse
import sys
import time

import serial
import serial.tools.list_ports

BAUD_RATES = [460800, 115200, 230400, 921600]
PROBE_SECONDS = 3.0

SERIAL_CONFIGS = [
    {"label": "8N1",   "bytesize": 8, "parity": "N", "stopbits": 1},
    {"label": "8N2",   "bytesize": 8, "parity": "N", "stopbits": 2},
    {"label": "8E1",   "bytesize": 8, "parity": "E", "stopbits": 1},
    {"label": "8O1",   "bytesize": 8, "parity": "O", "stopbits": 1},
    {"label": "7E1",   "bytesize": 7, "parity": "E", "stopbits": 1},
    {"label": "7O1",   "bytesize": 7, "parity": "O", "stopbits": 1},
]

PARITY_MAP = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN,
              "O": serial.PARITY_ODD}
STOP_MAP = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}


def bit_reverse(b: int) -> int:
    r = 0
    for _ in range(8):
        r = (r << 1) | (b & 1)
        b >>= 1
    return r


TRANSFORMS = [
    ("raw",            lambda b: b),
    ("NOT",            lambda b: (~b) & 0xFF),
    ("bit-reverse",    lambda b: bit_reverse(b)),
    ("NOT+bit-rev",    lambda b: bit_reverse((~b) & 0xFF)),
    ("swap-nibble",    lambda b: ((b << 4) | (b >> 4)) & 0xFF),
    ("NOT+swap-nib",   lambda b: (((~b & 0xFF) << 4) | ((~b & 0xFF) >> 4)) & 0xFF),
    ("shift-R1",       lambda b: (b >> 1)),
    ("shift-L1",       lambda b: (b << 1) & 0xFF),
    ("NOT+shift-R1",   lambda b: ((~b) & 0xFF) >> 1),
]


def score_ascii(data: bytes) -> dict:
    if not data:
        return {"ascii_pct": 0, "newlines": 0, "panda": 0, "lines": []}
    printable = sum(1 for b in data if 0x20 <= b <= 0x7E or b == 0x0A or b == 0x0D)
    newlines = data.count(0x0A)
    lines = []
    panda = 0
    if newlines > 0:
        for raw_line in data.split(b'\n'):
            try:
                text = raw_line.decode('ascii', errors='replace').strip()
            except Exception:
                continue
            if not text:
                continue
            lines.append(text)
            first = text[0] if text else ''
            if first in ('p', 's', 't', 'v') and ',' in text:
                try:
                    tok = text.split(',')[0]
                    float(tok[1:])
                    panda += 1
                except (ValueError, IndexError):
                    pass
            elif text.startswith('BB:') or text in ('BOOT', 'PANDA_V2_INIT'):
                panda += 1
    return {
        "ascii_pct": printable / len(data) * 100,
        "newlines": newlines,
        "panda": panda,
        "lines": lines[:10],
    }


def probe(port, baud, cfg, duration):
    try:
        ser = serial.Serial(
            port, baud, timeout=0.5,
            bytesize=cfg["bytesize"],
            parity=PARITY_MAP[cfg["parity"]],
            stopbits=STOP_MAP[cfg["stopbits"]],
        )
    except serial.SerialException as e:
        return None, str(e)

    ser.reset_input_buffer()
    buf = bytearray()
    t0 = time.time()
    while time.time() - t0 < duration:
        n = ser.in_waiting
        chunk = ser.read(max(1, n))
        if chunk:
            buf.extend(chunk)
    ser.close()
    return bytes(buf), None


def main():
    parser = argparse.ArgumentParser(description="PandaV2 Serial Diagnostic v2")
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", default=None, type=int)
    parser.add_argument("--duration", default=PROBE_SECONDS, type=float)
    args = parser.parse_args()

    print("=" * 72)
    print("PandaV2 Serial Diagnostic v2  (polarity / framing / transform scan)")
    print("=" * 72)

    print("\nCOM ports:")
    ports = serial.tools.list_ports.comports()
    for p in sorted(ports, key=lambda x: x.device):
        print(f"  {p.device:8s}  {p.description}  [{p.hwid}]")

    test_ports = [args.port] if args.port else [p.device for p in ports]
    test_bauds = [args.baud] if args.baud else BAUD_RATES

    best = None

    for port in test_ports:
        for baud in test_bauds:
            for cfg in SERIAL_CONFIGS:
                tag = f"{port} @ {baud} {cfg['label']}"
                print(f"\n--- {tag} ({args.duration:.0f}s) ", end="", flush=True)

                raw, err = probe(port, baud, cfg, args.duration)
                if err:
                    print(f"ERROR: {err}")
                    continue
                if not raw:
                    print("no data")
                    continue

                print(f"{len(raw)}B ", end="")

                for tname, tfn in TRANSFORMS:
                    transformed = bytes(tfn(b) for b in raw)
                    s = score_ascii(transformed)
                    if s["panda"] > 0 or (s["ascii_pct"] > 85 and s["newlines"] > 2):
                        flag = "*** MATCH ***" if s["panda"] > 0 else "ascii-ok"
                        print(f"\n  >> {tname:16s}  ascii={s['ascii_pct']:.0f}%  "
                              f"newlines={s['newlines']}  panda={s['panda']}  {flag}")
                        for ln in s["lines"][:5]:
                            print(f"     | {ln[:100]}")
                        if s["panda"] > 0 and (best is None or s["panda"] > best[3]):
                            best = (port, baud, cfg["label"], s["panda"], tname)

                raw_score = score_ascii(raw)
                if raw_score["ascii_pct"] < 85 and raw_score["panda"] == 0:
                    no_match = True
                    for tname, tfn in TRANSFORMS:
                        transformed = bytes(tfn(b) for b in raw)
                        s = score_ascii(transformed)
                        if s["panda"] > 0 or (s["ascii_pct"] > 85 and s["newlines"] > 2):
                            no_match = False
                            break
                    if no_match:
                        print(f"ascii={raw_score['ascii_pct']:.0f}% "
                              f"nl={raw_score['newlines']} -- no transform matched")

                if cfg["label"] != "8N1":
                    break  # only try non-8N1 configs at first baud

    print("\n" + "=" * 72)
    if best:
        print(f"SOLUTION: {best[0]} @ {best[1]} {best[2]}  "
              f"transform={best[4]}  ({best[3]} panda packets)")
        if best[4] == "NOT":
            print("  -> RS-485 polarity is inverted (A/B wires swapped)")
            print("  -> Fix: swap A and B on the cable, OR invert RXD in FTDI EEPROM")
        elif best[4] == "raw":
            print("  -> Connection is correct! Update main.py baud/config to match.")
        else:
            print(f"  -> Unusual transform needed: {best[4]}")
    else:
        print("No valid PandaV2 telemetry found with any config/transform.")
        print("\nHex dump at 460800 8N1 (first 80 bytes):")
        raw460, err = probe(test_ports[-1] if test_ports else "COM4",
                            460800, SERIAL_CONFIGS[0], 2.0)
        if raw460:
            print(f"  {raw460[:80].hex(' ')}")
            print(f"\n  NOT:      {bytes((~b) & 0xFF for b in raw460[:80]).hex(' ')}")
            print(f"  bit-rev:  {bytes(bit_reverse(b) for b in raw460[:80]).hex(' ')}")
        print("\nPossible hardware issues:")
        print("  1. RS-485 A/B wires swapped (swap them at either end)")
        print("  2. FTDI adapter EEPROM needs 'Invert RXD' (use FTDI FT_PROG)")
        print("  3. Cable too long / no termination / ground issue")
        print("  4. Both ends driving bus simultaneously (DE contention)")
    print("=" * 72)


if __name__ == "__main__":
    main()
