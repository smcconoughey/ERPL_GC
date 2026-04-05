# MOE Unified Ground Control Backend

A flight-critical unified backend for the MOE rocket system. Manages multiple Panda devices (V1/V2 over serial) and NI DAQ hardware (over TCP) through a single WebSocket interface.

## Features

- Multi-device support: Connect multiple Pandas and NI DAQ simultaneously
- Normalized data model: V1/V2 differences abstracted from UI
- Full PT calibration and tare support (ported from original main.py)
- Bang-bang control, solenoid sequences, presets
- CSV logging across all devices
- Safety-critical abort/estop operations
- UDP multicast for spectator UIs

## Installation

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Edit `configs/moe_system.json` to specify:
- Device connections (serial ports, TCP hosts)
- Channel counts and names
- Logging directory
- Safety sequences

Channel configs are in `configs/rocket_*.json` and `configs/gse_*.json`.

## Usage

### Start Server

**Windows:**
```bash
start_moe.bat
```

**Linux/Mac:**
```bash
./start_moe.sh
```

Server listens on:
- WebSocket: `ws://localhost:3942`
- HTTP (static files): `http://localhost:8081`

### WebSocket Commands

All commands are JSON. Send to device or broadcast:

```json
{"action": "arm", "device": "rocket_panda"}
{"action": "disarm", "device": "rocket_panda"}
{"action": "send", "device": "rocket_panda", "command": "s11.00000"}
{"action": "abort"}
{"action": "estop"}
{"action": "get_status"}
{"action": "list_ports"}
{"action": "start_logging"}
{"action": "stop_logging"}
{"action": "tare_pts", "device": "rocket_panda", "channel": 1}
{"action": "preset_save", "name": "gox_purge", "sequence": "..."}
```

### PT Calibration

All PandaConnections inherit calibration from original main.py:
- 4-20 mA normalization
- Per-channel shunt estimation (auto-ambient mode)
- Per-channel tare offsets
- Range mapping to engineering units

Tare via `tare_pts` action (channels 1-16 or all if no channel specified).

## Architecture

### DeviceConnection (Base)
- Abstract interface for all device types
- Handles connect/disconnect/read/send

### PandaConnection (Serial)
- Manages Panda V1/V2 over serial
- Full calibration pipeline: raw → mA → engineering units
- Solenoid command handling
- DC current monitoring with configurable threshold

### NIDAQConnection (TCP)
- Connects to existing NI DAQ streamer
- Read-only (spectator mode)
- Receives PT and LC data via TCP JSON

### MOEBackend
- Central orchestrator
- Multi-client WebSocket server
- Unified CSV logging
- Preset/state persistence
- Safety routing (abort/estop fan-out)

## Logging

CSV logs to `logs/moe_YYYYMMDD_HHMMSS.csv` with columns:
```
timestamp,rocket_panda.PT1,rocket_panda.PT2,...,gse_panda.PT1,...,ni_daq.PT1,...
```

Start/stop logging via WebSocket action.

## Safety

### Abort
- Disarm all devices
- Turn off all DC channels
- Iterate all devices, don't stop on first error

### E-Stop
- Same as abort (defined in config)

## Status Broadcast

Server broadcasts device state every 500ms:
```json
{
    "type": "data",
    "timestamp": "2026-04-03T14:30:45.123Z",
    "devices": {
        "rocket_panda": {
            "device_id": "rocket_panda",
            "device_type": "panda_v2",
            "connected": true,
            "armed": false,
            "pt": {"1": {"value": 142.5, "units": "psi", "name": "LOX Tank"}, ...},
            "lc": {"1": {"value": 23.1, "units": "lbf", "name": "Thrust"}, ...},
            "tc": {"1": {"value": 72.3, "units": "degF", "name": "LOX Inlet"}, ...},
            "dc": {"1": {"value": 0.05, "state": false, "name": "LOX Main"}, ...}
        },
        ...
    }
}
```

## Command Line Options

```bash
python server.py [--config FILE] [--test] [--ws-port PORT] [--http-port PORT]
```

- `--config`: Path to moe_system.json (default: configs/moe_system.json)
- `--test`: Enable test mode (generates fake data)
- `--ws-port`: WebSocket port (default: 3942)
- `--http-port`: HTTP port (default: 8081)

## Test Mode

```bash
python server.py --test
```

Generates realistic sensor data with configurable noise/trends for all configured devices.

## Notes

- PT calibration fully ported from original `panda/main.py` SerialProcessor
- V1 devices have 12 DC channels; V2 devices have 16
- Serial protocol identical between V1 and V2
- DC on-current threshold configurable (default 0.1 A)
- Tare is per-device, per-channel, persistent during session
- All safety operations (abort/estop) are non-blocking and log failures but continue
