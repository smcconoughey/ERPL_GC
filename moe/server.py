import asyncio
import json
import logging
import threading
import time
import queue
import math
import csv
import socket
import serial.tools.list_ports
import argparse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import serial
import websockets
from websockets.server import WebSocketServerProtocol
import os
import http.server
import socketserver


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChannelData:
    """Normalized channel reading"""
    value: float
    units: str
    name: str
    timestamp: Optional[str] = None


@dataclass
class DeviceState:
    """Current state of a connected device"""
    device_id: str
    device_type: str
    connected: bool
    armed: bool = False
    pt: Dict[str, Dict] = field(default_factory=dict)
    lc: Dict[str, Dict] = field(default_factory=dict)
    tc: Dict[str, Dict] = field(default_factory=dict)
    dc: Dict[str, Dict] = field(default_factory=dict)
    bb: Dict[str, Dict] = field(default_factory=dict)  # bang-bang status per bus ('l'/'f')
    last_update: str = ""


class DeviceConnection:
    """Base class for device connections"""

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.connected = False
        self.armed = False
        self.state = DeviceState(device_id, device_type, False)

    async def connect(self) -> bool:
        raise NotImplementedError

    async def disconnect(self):
        self.connected = False

    async def send_command(self, command: str) -> bool:
        raise NotImplementedError

    async def read_data(self) -> Optional[Dict]:
        raise NotImplementedError

    def update_state(self):
        """Update device state dict"""
        self.state.connected = self.connected
        self.state.armed = self.armed
        self.state.last_update = datetime.utcnow().isoformat() + 'Z'


class PandaConnection(DeviceConnection):
    """Serial connection to a Panda device (V1 or V2)"""

    def __init__(self, device_id: str, device_type: str, port: str, baud: int = 460800):
        super().__init__(device_id, device_type)
        self.port = port
        self.baud = baud
        self.ser = None
        self.read_thread = None
        self.stop_reading = False

        self.pt_count = 16
        self.dc_count = 16 if device_type == "panda_v2" else 12

        # Calibration state (ported from main.py)
        self.apply_pt_calibration = True
        self.pt_min_ma = 4.0
        self.pt_max_ma = 20.0
        self.pt_shunt_ohms = 47.0
        self.pt_shunt_ohms_list = [self.pt_shunt_ohms for _ in range(16)]
        self.pt_input_mode = "volts"
        self.pt_offsets = [0.0 for _ in range(16)]
        self._last_pt_mA = [0.0 for _ in range(16)]
        self._last_pt_raw = [0.0 for _ in range(16)]
        self.auto_shunt_v_ambient = True
        self._ambient_v_sum = 0.0
        self._ambient_v_count = 0
        self.dc_threshold = 0.100

        self.pt_meta = self._load_pt_metadata()
        self._init_channels()

    def _init_channels(self):
        """Initialize channel data structures"""
        for i in range(1, 17):
            meta = self.pt_meta[i-1] if i <= len(self.pt_meta) else {}
            self.state.pt[str(i)] = {
                "value": 0.0,
                "units": meta.get('units', 'psi'),
                "name": meta.get('name', f'PT{i}')
            }

        for i in range(1, 7):
            self.state.lc[str(i)] = {"value": 0.0, "units": "lbf", "name": f"LC{i}"}
            self.state.tc[str(i)] = {"value": 0.0, "units": "degF", "name": f"TC{i}"}

        for i in range(1, self.dc_count + 1):
            self.state.dc[str(i)] = {"value": 0.0, "state": False, "name": f"DC{i}"}

        for bus in ('l', 'f'):
            self.state.bb[bus] = {"enabled": False, "valve_open": False, "pressure": 0.0}

    def _load_pt_metadata(self) -> List[Dict]:
        """Load PT channel metadata from config"""
        meta = [{} for _ in range(16)]
        for i in range(16):
            meta[i] = {
                "id": i + 1,
                "name": f"PT{i+1}",
                "units": "psi",
                "range": [0, 500]
            }
        return meta

    def _to_mA(self, values: List[float]) -> List[float]:
        """Convert PT values to milliamps based on input mode"""
        if not values:
            return []

        mode = self.pt_input_mode

        if mode == "volts":
            out = []
            for idx, v in enumerate(values):
                pol = -1.0 if v < 0.0 else 1.0
                r = self.pt_shunt_ohms_list[idx] if idx < len(self.pt_shunt_ohms_list) else self.pt_shunt_ohms
                r = r if r and r > 0.0 else self.pt_shunt_ohms
                out.append(((pol * v) / max(r, 0.001)) * 1000.0)
            return out

        if mode == "ma":
            return values[:]

        # auto mode
        vmax = max(values) if values else 0.0
        if 0.0 <= vmax <= 2.0:
            out = []
            for idx, v in enumerate(values):
                pol = -1.0 if v < 0.0 else 1.0
                r = self.pt_shunt_ohms_list[idx] if idx < len(self.pt_shunt_ohms_list) else self.pt_shunt_ohms
                r = r if r and r > 0.0 else self.pt_shunt_ohms
                out.append(((pol * v) / max(r, 0.001)) * 1000.0)
            return out

        if 0.0 <= vmax <= 30.0:
            return values[:]

        return []

    def _compute_eng_from_ma_no_tare(self, vals_mA: List[float]) -> List[float]:
        """Convert mA to engineering units"""
        out = []
        for idx, mA in enumerate(vals_mA):
            norm = (mA - self.pt_min_ma) / (self.pt_max_ma - self.pt_min_ma)
            norm = max(0.0, min(1.0, norm))
            meta = self.pt_meta[idx] if idx < len(self.pt_meta) else {}
            rng = meta.get('range', [0, 1000])
            min_eng, max_eng = float(rng[0]), float(rng[1])
            out.append(min_eng + norm * (max_eng - min_eng))
        return out

    def _calibrate_pt_values(self, values: List[float]) -> List[float]:
        """Apply PT calibration and tare"""
        if not self.apply_pt_calibration or not values:
            return values

        mA_vals = self._to_mA(values)
        if not mA_vals:
            return values

        # Auto-estimate shunt from ambient
        if self.pt_input_mode == "volts" and self.auto_shunt_v_ambient:
            try:
                avg_abs_v = sum(abs(v) for v in values[:min(16, len(values))]) / float(min(16, len(values)))
                self._ambient_v_sum += max(0.0, avg_abs_v)
                self._ambient_v_count += 1
                if self._ambient_v_count >= 5:
                    mean_v = self._ambient_v_sum / self._ambient_v_count
                    est_r = max(1.0, mean_v / 0.004)
                    self.pt_shunt_ohms = est_r
                    self.auto_shunt_v_ambient = False
                    logger.info(f"Auto-set pt_shunt_ohms≈{est_r:.2f}Ω")
            except Exception as e:
                logger.debug(f"Shunt estimation error: {e}")

        eng = self._compute_eng_from_ma_no_tare(mA_vals)

        # Apply per-channel tare
        out = []
        for i, val in enumerate(eng):
            offset = self.pt_offsets[i] if i < len(self.pt_offsets) else 0.0
            out.append(val - offset)

        return out

    def _parse_serial_packet(self, line: str) -> Optional[Dict]:
        """Parse a serial packet and extract channel data"""

        # Bang-bang status: "BB:L:<enabled>:<valve_open>:<pressure>"
        if line.startswith('BB:') and line.count(':') >= 4:
            parts = line.split(':')
            bus = parts[1].lower()  # 'l' or 'f'
            if bus in self.state.bb:
                try:
                    self.state.bb[bus]['enabled']    = parts[2] == '1'
                    self.state.bb[bus]['valve_open'] = parts[3] == '1'
                    self.state.bb[bus]['pressure']   = float(parts[4])
                except (IndexError, ValueError):
                    pass
            self.update_state()
            return {}

        if not line or ',' not in line:
            return None

        tokens = [tok.strip() for tok in line.split(',')]
        if not tokens:
            return None

        def _to_float(tok: str) -> float:
            try:
                s = ''.join(ch for ch in tok if ch.isdigit() or ch in ['-', '+', '.'])
                return float(s) if s not in ['', '+', '-'] else 0.0
            except:
                return 0.0

        id_char = tokens[0][0].lower() if tokens[0] else ''
        numeric = [_to_float(tok) for tok in tokens]

        data = {}

        if id_char == 'p':
            if self.apply_pt_calibration:
                self._last_pt_raw = (numeric + [0.0]*16)[:16]
                try:
                    mA_vals = self._to_mA(numeric)
                    if len(mA_vals) < 16:
                        mA_vals = mA_vals + [0.0]*(16-len(mA_vals))
                    self._last_pt_mA = mA_vals[:16]
                except:
                    pass

            calibrated = self._calibrate_pt_values(numeric)
            for i, val in enumerate(calibrated[:16], 1):
                self.state.pt[str(i)]["value"] = val

        elif id_char == 't':
            # LC (0-5) + TC (0-5)
            for i, val in enumerate(numeric[:6], 1):
                self.state.lc[str(i)]["value"] = val
            for i, val in enumerate(numeric[6:12], 1):
                self.state.tc[str(i)]["value"] = val

        elif id_char == 's':
            # DC solenoid currents
            currents = numeric
            for i, val in enumerate(currents[:self.dc_count], 1):
                threshold = self.dc_threshold
                self.state.dc[str(i)]["value"] = val
                self.state.dc[str(i)]["state"] = val >= threshold

        self.update_state()
        return data

    async def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=2)
            self.connected = True
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            logger.info(f"{self.device_id} connected to {self.port}")
            return True
        except Exception as e:
            logger.error(f"{self.device_id} connection failed: {e}")
            return False

    async def disconnect(self):
        self.stop_reading = True
        self.connected = False
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None

    def _read_loop(self):
        """Background thread: read serial data"""
        while self.connected and not self.stop_reading:
            try:
                if self.ser and self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._parse_serial_packet(line)
            except Exception as e:
                logger.debug(f"{self.device_id} read error: {e}")
                time.sleep(0.01)

    async def send_command(self, command: str) -> bool:
        """Send a command to the device"""
        if not self.connected or not self.ser:
            return False

        try:
            self.ser.write((command + '\n').encode('utf-8'))
            self.ser.flush()

            # Handle arm/disarm commands
            if command.lower() == 'a':
                self.armed = True
            elif command.lower() == 'r':
                self.armed = False

            self.update_state()
            return True
        except Exception as e:
            logger.error(f"{self.device_id} send_command failed: {e}")
            return False

    async def read_data(self) -> Optional[Dict]:
        """Get current state"""
        self.update_state()
        return asdict(self.state)

    def tare_pt(self, channel: Optional[int] = None):
        """Tare PT sensor(s)"""
        if channel is not None:
            if 1 <= channel <= 16:
                idx = channel - 1
                if idx < len(self._last_pt_mA):
                    mA = self._last_pt_mA[idx]
                    eng = self._compute_eng_from_ma_no_tare([mA])[0]
                    self.pt_offsets[idx] = eng
                    logger.info(f"{self.device_id} PT{channel} tared")
        else:
            eng = self._compute_eng_from_ma_no_tare(self._last_pt_mA)
            self.pt_offsets = eng
            logger.info(f"{self.device_id} all PTs tared")


class NIDAQConnection(DeviceConnection):
    """TCP connection to NI DAQ streamer"""

    def __init__(self, device_id: str, host: str = "localhost", port: int = 5001):
        super().__init__(device_id, "ni_daq")
        self.host = host
        self.port = port
        self.sock = None
        self.read_thread = None
        self.stop_reading = False
        self._init_channels()

    def _init_channels(self):
        """Initialize channel structures"""
        for i in range(1, 17):
            self.state.pt[str(i)] = {"value": 0.0, "units": "psi", "name": f"PT{i}"}

        for i in range(1, 9):
            self.state.lc[str(i)] = {"value": 0.0, "units": "lbf", "name": f"LC{i}"}

    async def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2)
            self.sock.connect((self.host, self.port))
            self.connected = True
            self.stop_reading = False
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            logger.info(f"{self.device_id} connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"{self.device_id} connection failed: {e}")
            return False

    async def disconnect(self):
        self.stop_reading = True
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def _read_loop(self):
        """Background thread: read TCP data"""
        while self.connected and not self.stop_reading:
            try:
                if self.sock:
                    data = self.sock.recv(1024).decode('utf-8', errors='ignore')
                    if data:
                        self._parse_data(data)
            except socket.timeout:
                pass
            except Exception as e:
                logger.debug(f"{self.device_id} read error: {e}")
                time.sleep(0.01)

    def _parse_data(self, data: str):
        """Parse incoming data"""
        try:
            for line in data.strip().split('\n'):
                if not line:
                    continue
                msg = json.loads(line)

                if 'pt' in msg:
                    for ch, val in msg['pt'].items():
                        if str(ch) in self.state.pt:
                            self.state.pt[str(ch)]["value"] = val

                if 'lc' in msg:
                    for ch, val in msg['lc'].items():
                        if str(ch) in self.state.lc:
                            self.state.lc[str(ch)]["value"] = val
        except Exception as e:
            logger.debug(f"{self.device_id} parse error: {e}")

        self.update_state()

    async def send_command(self, command: str) -> bool:
        return False  # NI DAQ is read-only

    async def read_data(self) -> Optional[Dict]:
        self.update_state()
        return asdict(self.state)


class MOEBackend:
    """Unified MOE ground control backend"""

    def __init__(self, config_file: str = "configs/moe_system.json", test_mode: bool = False):
        self.config_file = config_file
        self.test_mode = test_mode
        self.config = self._load_config()
        self.devices: Dict[str, DeviceConnection] = {}
        self.clients: List[WebSocketServerProtocol] = []
        self.clients_lock = threading.Lock()

        # Logging
        self.logging_enabled = False
        self.log_file = None
        self.log_writer = None
        self.log_filename = None
        self.log_lock = threading.Lock()
        self.current_data = {}

        # Presets
        self.presets = {}
        self._load_presets()

        # Bang-bang configs
        self.bb_configs = {}

        self._init_devices()
        self._init_logging()

    def _load_config(self) -> Dict:
        """Load system configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return minimal default config"""
        return {
            "system_name": "MOE",
            "devices": [],
            "network": {
                "ws_port": 3942,
                "http_port": 8081,
                "udp_group": "239.255.0.1",
                "udp_port": 5006
            }
        }

    def _init_devices(self):
        """Initialize device connections from config"""
        for dev_cfg in self.config.get('devices', []):
            device_id = dev_cfg.get('device_id', '')
            device_type = dev_cfg.get('device_type', '')
            conn_cfg = dev_cfg.get('connection', {})

            if not device_id or not device_type:
                continue

            if device_type.startswith('panda'):
                port = conn_cfg.get('port', 'COM4')
                baud = conn_cfg.get('baud', 460800)
                self.devices[device_id] = PandaConnection(device_id, device_type, port, baud)

            elif device_type == 'ni_daq':
                host = conn_cfg.get('host', 'localhost')
                port = conn_cfg.get('port', 5001)
                self.devices[device_id] = NIDAQConnection(device_id, host, port)

            logger.info(f"Initialized device: {device_id} ({device_type})")

    def _init_logging(self):
        """Initialize CSV logging"""
        log_dir = Path(self.config.get('logging', {}).get('log_dir', 'logs'))
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        self.log_filename = str(log_dir / f"moe_{timestamp}.csv")

    def _load_presets(self):
        """Load preset sequences"""
        try:
            preset_file = Path(self.config_file).parent / "presets.json"
            if preset_file.exists():
                with open(preset_file, 'r') as f:
                    self.presets = json.load(f)
        except Exception as e:
            logger.debug(f"Preset load error: {e}")

    async def connect_all(self):
        """Connect to all configured devices"""
        tasks = []
        for device_id, device in self.devices.items():
            tasks.append(self._connect_device(device_id, device))

        results = await asyncio.gather(*tasks)
        logger.info(f"Connected {sum(results)}/{len(self.devices)} devices")

    async def _connect_device(self, device_id: str, device: DeviceConnection) -> bool:
        """Connect a single device"""
        result = await device.connect()
        if result:
            logger.info(f"Connected {device_id}")
        return result

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        with self.clients_lock:
            self.clients.append(websocket)

        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            with self.clients_lock:
                self.clients.remove(websocket)

    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket message"""
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return

        action = msg.get('action', '')
        device = msg.get('device', '')

        try:
            if action == 'send':
                command = msg.get('command', '')
                if device in self.devices:
                    await self.devices[device].send_command(command)

            elif action == 'arm':
                if device in self.devices:
                    await self.devices[device].send_command('a')

            elif action == 'disarm':
                if device in self.devices:
                    await self.devices[device].send_command('r')

            elif action == 'abort':
                await self._abort_all()

            elif action == 'estop':
                await self._estop_all()

            elif action == 'connect_device':
                port = msg.get('port', '')
                if device in self.devices:
                    await self.devices[device].connect()

            elif action == 'list_ports':
                ports = [p.device for p in serial.tools.list_ports.comports()]
                await websocket.send(json.dumps({
                    'type': 'ports',
                    'ports': ports
                }))

            elif action == 'get_status':
                await self._send_status()

            elif action == 'start_logging':
                self._start_logging()

            elif action == 'stop_logging':
                self._stop_logging()

            elif action == 'tare_pts':
                if device in self.devices and isinstance(self.devices[device], PandaConnection):
                    ch = msg.get('channel')
                    self.devices[device].tare_pt(ch)

            elif action == 'bb_config':
                # Push bang-bang config to firmware: setpoint, deadband, wait_ms
                bus      = msg.get('bus', '')       # 'lox' or 'fuel'
                setpoint = float(msg.get('setpoint', 200))
                deadband = float(msg.get('deadband', 10))
                wait_ms  = int(msg.get('wait_ms', 500))
                bus_char = 'L' if bus == 'lox' else 'F'
                cmd = f'B{bus_char}{int(setpoint)},{int(deadband)},{wait_ms}'
                if device in self.devices:
                    await self.devices[device].send_command(cmd)
                    logger.info(f"BB config pushed to {device}: {cmd}")

            elif action == 'bb_enable':
                # Enable or disable bang-bang on firmware
                bus     = msg.get('bus', '')        # 'lox' or 'fuel'
                enable  = bool(msg.get('enable', False))
                bus_char = 'L' if bus == 'lox' else 'F'
                cmd = f'b{bus_char}{"1" if enable else "0"}'
                if device in self.devices:
                    await self.devices[device].send_command(cmd)
                    logger.info(f"BB {'enable' if enable else 'disable'} sent to {device}: {cmd}")

            elif action == 'preset_save':
                name = msg.get('name', '')
                sequence = msg.get('sequence', '')
                self.presets[name] = sequence
                self._save_presets()

            elif action == 'preset_load':
                name = msg.get('name', '')
                if name in self.presets:
                    await websocket.send(json.dumps({
                        'type': 'preset',
                        'name': name,
                        'sequence': self.presets[name]
                    }))

        except Exception as e:
            logger.error(f"Message handling error: {e}")

    async def _abort_all(self):
        """Abort all devices — disarm first (kills actuators on firmware side),
        then explicitly zero each DC as belt-and-suspenders.
        SAFETY: never short-circuit on error; every device gets attempted."""
        logger.warning(">>> ABORT ALL DEVICES <<<")
        for device_id, device in self.devices.items():
            # Phase 1: disarm (firmware-side kill)
            try:
                if isinstance(device, PandaConnection):
                    await device.send_command('r')
            except Exception as e:
                logger.error(f"ABORT disarm {device_id} failed: {e}")
            # Phase 2: explicit DC off (belt-and-suspenders)
            try:
                if isinstance(device, PandaConnection):
                    for i in range(1, device.dc_count + 1):
                        try:
                            await device.send_command(f's{i}0.00000')
                        except Exception:
                            pass  # keep going
            except Exception as e:
                logger.error(f"ABORT DC-off {device_id} failed: {e}")

    async def _estop_all(self):
        """E-stop: abort + force disarm + log loudly.
        More aggressive than abort — intended for 'something is wrong, stop now'."""
        logger.critical(">>> E-STOP ALL DEVICES <<<")
        await self._abort_all()
        # Force armed=False on all devices even if serial send failed
        for device in self.devices.values():
            device.armed = False
            device.update_state()

    async def _send_status(self):
        """Broadcast current status to all clients"""
        status = {
            'type': 'data',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'devices': {}
        }

        for device_id, device in self.devices.items():
            data = await device.read_data()
            status['devices'][device_id] = data

        await self._broadcast(json.dumps(status))

    async def _broadcast(self, message: str):
        """Broadcast message to all connected clients"""
        with self.clients_lock:
            clients = self.clients[:]

        if not clients:
            return

        await asyncio.gather(
            *[client.send(message) for client in clients],
            return_exceptions=True
        )

    def _start_logging(self):
        """Start CSV logging with all channels from all devices"""
        if self.logging_enabled:
            return

        try:
            now = datetime.now()
            log_dir = Path(self.config.get('logging', {}).get('log_dir', 'logs')) / now.strftime("%m%d")
            log_dir.mkdir(parents=True, exist_ok=True)
            fname = log_dir / f"moe_{now.strftime('%H%M%S')}.csv"
            self.log_filename = str(fname)

            with self.log_lock:
                self.log_file = open(fname, 'w', newline='')
                self._log_headers = ['timestamp', 'elapsed_ms']
                self._log_start_time = time.time()
                self._log_count = 0

                for device_id, device in self.devices.items():
                    for ch in sorted(device.state.pt.keys(), key=lambda x: int(x)):
                        self._log_headers.append(f'{device_id}.PT{ch}_psi')
                    for ch in sorted(device.state.lc.keys(), key=lambda x: int(x)):
                        self._log_headers.append(f'{device_id}.LC{ch}_lbf')
                    for ch in sorted(device.state.tc.keys(), key=lambda x: int(x)):
                        self._log_headers.append(f'{device_id}.TC{ch}_degF')
                    for ch in sorted(device.state.dc.keys(), key=lambda x: int(x)):
                        self._log_headers.append(f'{device_id}.DC{ch}_A')

                self.log_writer = csv.writer(self.log_file)
                self.log_writer.writerow(self._log_headers)
                self.log_file.flush()
                self.logging_enabled = True
                logger.info(f"Logging started: {self.log_filename}")
        except Exception as e:
            logger.error(f"Logging start failed: {e}")

    def _stop_logging(self):
        """Stop CSV logging"""
        if not self.logging_enabled:
            return

        with self.log_lock:
            if self.log_file:
                self.log_file.close()
            self.logging_enabled = False
            logger.info("Logging stopped")

    def _save_presets(self):
        """Save presets to file"""
        try:
            preset_file = Path(self.config_file).parent / "presets.json"
            with open(preset_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Preset save error: {e}")

    async def data_broadcast_loop(self):
        """Periodically broadcast device data"""
        while True:
            try:
                await self._send_status()

                if self.logging_enabled and self.log_writer:
                    elapsed_ms = int((time.time() - self._log_start_time) * 1000)
                    row = [datetime.utcnow().isoformat() + 'Z', elapsed_ms]
                    for device_id, device in self.devices.items():
                        for ch in sorted(device.state.pt.keys(), key=lambda x: int(x)):
                            row.append(device.state.pt[ch]['value'])
                        for ch in sorted(device.state.lc.keys(), key=lambda x: int(x)):
                            row.append(device.state.lc[ch]['value'])
                        for ch in sorted(device.state.tc.keys(), key=lambda x: int(x)):
                            row.append(device.state.tc[ch]['value'])
                        for ch in sorted(device.state.dc.keys(), key=lambda x: int(x)):
                            row.append(device.state.dc[ch]['value'])

                    with self.log_lock:
                        if self.log_writer and self.log_file:
                            self.log_writer.writerow(row)
                            self._log_count += 1
                            if self._log_count % 10 == 0:
                                self.log_file.flush()

                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
                await asyncio.sleep(1)


class TestDataGenerator:
    """Generates fake sensor data for testing without hardware"""

    def __init__(self, backend: MOEBackend):
        self.backend = backend
        self.start_time = time.time()
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._generate_loop, daemon=True).start()
        logger.info("Test data generator started")

    def _generate_loop(self):
        import random
        while self.running:
            t = time.time() - self.start_time
            for device_id, device in self.backend.devices.items():
                # Mark as connected for test mode
                device.connected = True
                device.update_state()

                for ch in device.state.pt:
                    base = 150.0 + int(ch) * 10
                    noise = random.uniform(-2.5, 2.5)
                    drift = 5.0 * math.sin(t * 0.1 + int(ch))
                    device.state.pt[ch]['value'] = base + noise + drift

                for ch in device.state.lc:
                    base = 50.0 + int(ch) * 20
                    noise = random.uniform(-3.0, 3.0)
                    device.state.lc[ch]['value'] = base + noise

                for ch in device.state.tc:
                    base = 70.0 + int(ch) * 5
                    noise = random.uniform(-1.0, 1.0)
                    device.state.tc[ch]['value'] = base + noise

                for ch in device.state.dc:
                    device.state.dc[ch]['value'] = 0.0
                    device.state.dc[ch]['state'] = False

            time.sleep(0.1)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_http_server(http_port: int):
    web_root = str(Path(__file__).parent / "public")
    import os
    os.chdir(web_root)
    handler = http.server.SimpleHTTPRequestHandler
    try:
        httpd = ReusableTCPServer(("0.0.0.0", http_port), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        logger.info(f"HTTP server on http://0.0.0.0:{http_port}")
        return httpd
    except Exception as e:
        logger.error(f"HTTP server failed: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(description="MOE Ground Control Server")
    parser.add_argument('--config', default='configs/moe_system.json')
    parser.add_argument('--test', action='store_true', help='Run with simulated data')
    parser.add_argument('--ws-port', type=int, default=3942)
    parser.add_argument('--http-port', type=int, default=8081)
    args = parser.parse_args()

    backend = MOEBackend(args.config, test_mode=args.test)

    http_port = args.http_port
    httpd = start_http_server(http_port)
    if httpd:
        logger.info(f"  MOE UI: http://localhost:{http_port}/moe.html")
        logger.info(f"  Index:  http://localhost:{http_port}/index.html")

    if args.test:
        test_gen = TestDataGenerator(backend)
        test_gen.start()
    else:
        await backend.connect_all()

    ws_server = await websockets.serve(
        backend.handle_client,
        "0.0.0.0",
        args.ws_port
    )
    logger.info(f"WebSocket server on ws://0.0.0.0:{args.ws_port}")

    if backend.config.get('logging', {}).get('auto_start', False):
        backend._start_logging()

    broadcast_task = asyncio.create_task(backend.data_broadcast_loop())

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        ws_server.close()
        await ws_server.wait_closed()
        for device in backend.devices.values():
            await device.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
