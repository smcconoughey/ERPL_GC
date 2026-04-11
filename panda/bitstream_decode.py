#!/usr/bin/env python3
"""
Bit-stream level decode of garbled RS-485 data.

Tests the hypothesis that the received data is offset by N bits in the
UART bit stream (continuous shift across byte boundaries).
"""

import time
import threading
import serial

BAUD = 460800
DURATION = 3.0


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
        print(f"  ERROR {port}: {e}")
        result_dict[key] = b""


def to_bitstream(data: bytes) -> list:
    """Convert bytes to bit list (LSB first per byte, as UART transmits)."""
    bits = []
    for b in data:
        for i in range(8):
            bits.append((b >> i) & 1)
    return bits


def from_bitstream(bits: list) -> bytes:
    """Convert bit list back to bytes (LSB first, 8 bits per byte)."""
    result = []
    for i in range(0, len(bits) - 7, 8):
        val = 0
        for j in range(8):
            val |= bits[i + j] << j
        result.append(val)
    return bytes(result)


def score_data(data: bytes):
    if not data:
        return 0, 0, 0, 0
    ascii_ct = sum(1 for b in data if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D))
    pct = ascii_ct / len(data) * 100
    nl = data.count(0x0A)
    panda = 0
    if nl > 0:
        for raw in data.split(b'\n'):
            t = raw.decode('ascii', errors='replace').strip()
            if not t:
                continue
            if t[0] in 'pstv' and ',' in t:
                try:
                    float(t.split(',')[0][1:])
                    panda += 1
                except (ValueError, IndexError):
                    pass
            elif t.startswith(('BB:', 'BOOT', 'PANDA')):
                panda += 1
    return pct, nl, panda, len(data)


def show_result(label, data, detail=False):
    pct, nl, panda, sz = score_data(data)
    tag = ""
    if panda > 0:
        tag = " *** PANDA TELEMETRY ***"
    elif nl > 3 and pct > 85:
        tag = " ** CLEAN **"
    elif pct > 75:
        tag = " * promising"
    print(f"  {label:<42} {sz:>5}B  ascii={pct:5.1f}%  nl={nl:>3}  panda={panda}{tag}")
    if detail and nl > 0:
        lines = data.decode('ascii', errors='replace').split('\n')
        for ln in [l.strip() for l in lines if l.strip()][:6]:
            print(f"      | {ln[:110]}")
    elif detail:
        prev = data[:100].decode('ascii', errors='replace')
        print(f"      {(''.join(c if 0x20<=ord(c)<=0x7E else '.' for c in prev))}")


def main():
    print("Reading COM5 (RS-485) and COM6 (USB)...")
    results = {}
    threads = []
    for key, port in [("rs485", "COM5"), ("usb", "COM6")]:
        t = threading.Thread(target=read_port, args=(port, BAUD, results, key))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    garbled = results.get("rs485", b"")
    clean = results.get("usb", b"")

    print(f"\nCOM6 (USB reference): {len(clean)} bytes, 100% ascii")
    print(f"COM5 (RS-485):       {len(garbled)} bytes\n")

    if not garbled:
        print("No RS-485 data!")
        return

    bits = to_bitstream(garbled)
    inv_bits = [1 - b for b in bits]

    print("=" * 80)
    print("  Bit-stream shift tests (continuous shift across byte boundaries)")
    print("=" * 80)

    best_score = 0
    best_label = ""
    best_data = b""

    for shift in range(-7, 8):
        for invert in [False, True]:
            src = inv_bits if invert else bits
            if shift >= 0:
                shifted = src[shift:]
            else:
                shifted = [0] * (-shift) + src[:shift]

            decoded = from_bitstream(shifted)
            pct, nl, panda, sz = score_data(decoded)
            quality = pct + nl * 5 + panda * 50

            inv_label = "INV+" if invert else ""
            label = f"{inv_label}shift({shift:+d})"

            if quality > 60:
                show_result(label, decoded, detail=(panda > 0 or (nl > 3 and pct > 85)))

            if quality > best_score:
                best_score = quality
                best_label = label
                best_data = decoded

    print()
    print("=" * 80)
    print(f"  BEST: {best_label}")
    print("=" * 80)
    show_result(best_label, best_data, detail=True)

    if best_data.count(0x0A) == 0:
        print("\n  Still no newlines. Trying UART-level reframing...\n")

        for shift in range(-3, 4):
            for invert in [False, True]:
                src = inv_bits if invert else bits
                if shift >= 0:
                    test = src[shift:]
                else:
                    test = [0] * (-shift) + src[:shift]

                # Scan for UART frames: look for 0 (start), read 8 data bits, expect 1 (stop)
                result = []
                i = 0
                while i < len(test) - 9:
                    if test[i] == 0:  # start bit
                        byte_val = 0
                        for bit_idx in range(8):
                            byte_val |= test[i + 1 + bit_idx] << bit_idx
                        stop = test[i + 9] if i + 9 < len(test) else 1
                        if stop == 1:
                            result.append(byte_val)
                            i += 10
                        else:
                            i += 1
                    else:
                        i += 1

                decoded = bytes(result)
                pct, nl, panda, sz = score_data(decoded)
                quality = pct + nl * 5 + panda * 50

                inv_label = "INV+" if invert else ""
                label = f"UART-reframe {inv_label}shift({shift:+d})"

                if quality > 60:
                    show_result(label, decoded, detail=(panda > 0 or (nl > 3 and pct > 85)))


if __name__ == "__main__":
    main()
