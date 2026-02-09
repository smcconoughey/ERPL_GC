# ERPL Ground Control (ERPL_GC)

Unified ground control software for ERPL test stand operations. Combines NI DAQ hardware acquisition with PANDA serial-based control.

## Quick Start

| Command | Description |
|---------|-------------|
| `start_nidaq.bat` | Start NI DAQ system only (cDAQ-9189) |
| `stop_nidaq.bat` | Stop NI DAQ system |
| `start_panda.bat` | Start PANDA system only (Teensy serial) |
| `stop_panda.bat` | Stop PANDA system |
| `start_all.bat` | Start both systems |
| `stop_all.bat` | Stop everything |

## Web Interfaces

| System | URL | Description |
|--------|-----|-------------|
| NI DAQ | http://localhost:3000 | High-speed PT/LC/TC monitoring |
| PANDA | http://localhost:8080/panda-daq-ui.html | Valve control + telemetry |
| PANDA PID | http://localhost:8080/pid.html | P&ID diagram view |
| PANDA Sequencer | http://localhost:8080/sequencer.html | Test sequence builder |

## Sensor Configuration

All sensors are configured in `sensor_config.csv` - edit with Excel or any CSV editor.

### CSV Columns
- `system`: `ni_daq` or `panda`
- `type`: `PT`, `LC`, `TC`, `DC`
- `channel`: Hardware channel (0-indexed)
- `id`, `name`, `short_name`: Identification
- `serial`: Sensor serial number
- `group`: `lox`, `fuel`, `other`, etc.
- `units`: Engineering units
- `range_min`, `range_max`: Display/scale range
- `warning_low/high`, `critical_low/high`: Alert thresholds
- `cal_slope`, `cal_offset`, `cal_tare`: Load cell calibration
- `cal_zero_ma`, `cal_max_psi`: PT 4-20mA calibration
- `tc_type`: Thermocouple type (K, J, etc.)
- `dc_type`, `abort_role`: DC channel roles

## Folder Structure

```
ERPL_GC/
├── sensor_config.csv      # Master sensor configuration
├── start_*.bat            # Startup scripts
├── stop_*.bat             # Shutdown scripts
├── ni_daq/                # NI DAQ system
│   ├── daq_streamer.py    # Main DAQ acquisition
│   ├── server.js          # WebSocket server
│   ├── config.py          # Hardware config
│   ├── devices/           # Device drivers
│   └── *.json             # Channel configs
├── panda/                 # PANDA system
│   ├── main.py            # Serial bridge
│   └── configs/           # Channel configs
├── public/                # Web UI files
│   ├── daq_ui.html        # NI DAQ dashboard
│   ├── panda-daq-ui.html  # PANDA dashboard
│   └── ...
└── logs/                  # Data logs
```

## Hardware

### NI DAQ (cDAQ-9189 at 192.168.8.236)
- **Slot 1**: NI-9237 (4-ch bridge/load cell)
- **Slot 2**: NI-9208 (16-ch 4-20mA PT)
- **Slot 3**: NI-9211 (4-ch thermocouple)

### PANDA (Teensy via COM4)
- 16-ch PT (ADC)
- 6-ch LC (strain gauge)
- 6-ch TC (thermocouple)
- 12-ch DC (solenoid control)

## Requirements

- Python 3.8+
- Node.js 18+
- NI-DAQmx Runtime (for NI DAQ)
- USB serial drivers (for PANDA)
