


#!/usr/bin/env python3
"""List all COM ports with details to identify Teensy vs FTDI adapters."""
import serial.tools.list_ports

print(f"{'PORT':<10} {'VID:PID':<12} {'Serial#':<20} {'Description'}")
print("-" * 80)
for p in sorted(serial.tools.list_ports.comports()):
    vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid else "----:----"
    sn = p.serial_number or ""
    print(f"{p.device:<10} {vid_pid:<12} {sn:<20} {p.description}")
    if p.manufacturer:
        print(f"{'':>10} mfg: {p.manufacturer}  hwid: {p.hwid}")
